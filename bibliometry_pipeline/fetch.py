from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .config import (
    ALL_RESEARCH_SEARCH_TERMS,
    AI_SIGNAL_RULES,
    AI_TITLE_SEARCH,
    EUROPE_PMC_ENABLED,
    EUROPE_PMC_QUERIES,
    FETCH_MAX_FINAL,
    FETCH_MIN_FINAL,
    FETCH_RELEVANCE_THRESHOLD,
    FETCH_SEMANTIC_MODEL,
    HARD_NEGATIVE_SCOPE_RULES,
    HARD_OFFTOPIC_TITLE_RE,
    MIN_ABSTRACT_LENGTH,
    OFFTOPIC_PRIMARY_TOPIC_RE,
    POSITIVE_SCOPE_RULES,
    RELEVANCE_NEGATIVE_PROTOTYPES,
    RELEVANCE_POSITIVE_PROTOTYPES,
    SCOPUS_ABSTRACT_BACKFILL_ENABLED,
    SCOPUS_ABSTRACT_BACKFILL_MAX_DOIS,
    SCOPUS_API_KEY,
    SCOPUS_ENABLED,
    SCOPUS_INST_TOKEN,
    SCOPUS_QUERIES,
    SEMANTIC_SCHOLAR_API_KEY,
    SEMANTIC_SCHOLAR_ENABLED,
    YEAR_MAX,
    YEAR_MIN,
)
from .abstract_backfill import backfill_missing_abstracts
from .openalex import fetch_all as openalex_fetch_all, flatten_records as openalex_flatten_records, summarise_countries
from .paths import RunPaths, ensure_run_dirs
from .source_cache import load_source_cache, normalise_source_frame, save_source_cache, source_cache_enabled
from .utils import write_json


def _matching_labels(text: str, rules: dict[str, object]) -> list[str]:
    return [label for label, regex in rules.items() if regex.search(text)]


def _pipe_join(values: list[str] | set[str]) -> str:
    return "|".join(sorted({value for value in values if value}))


def _count_labels(value: str) -> int:
    text = "" if value is None else str(value)
    return len([part for part in text.split("|") if part])


def _extract_display_names(value: object, *, limit: int | None = None) -> str:
    if not isinstance(value, list):
        return ""

    names: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        display_name = str(item.get("display_name") or "").strip()
        if not display_name or display_name in seen:
            continue
        seen.add(display_name)
        names.append(display_name)
        if limit is not None and len(names) >= limit:
            break
    return " | ".join(names)


def _categorise(text: str) -> str:
    matches = _matching_labels(text, POSITIVE_SCOPE_RULES)
    return matches[0] if matches else "other_relevant"


def _normalize_count(series: pd.Series, *, cap: int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).clip(lower=0, upper=cap) / cap


def _norm_doi(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _filter_new_source_records(existing_df: pd.DataFrame, candidate_df: pd.DataFrame) -> pd.DataFrame:
    existing_dois = set(existing_df["doi"].dropna().apply(_norm_doi)) - {""}
    candidate_dois = candidate_df["doi"].apply(_norm_doi)
    new_mask = (~candidate_dois.isin(existing_dois)) | (candidate_dois == "")

    existing_titles_lc = set(existing_df["title"].fillna("").str.lower().str.strip())
    new_mask = new_mask & ~candidate_df["title"].fillna("").str.lower().str.strip().isin(existing_titles_lc)
    return candidate_df[new_mask].copy()


def _find_openalex_seed_frame(paths: RunPaths) -> tuple[pd.DataFrame | None, str]:
    audit_candidates: list = []
    legacy_cache_candidates: list = []
    corpus_candidates: list = []

    runs_dir = paths.root / "runs"
    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            audit_candidates.append(run_dir / "indicators" / "fetch_relevance_audit.csv")
            legacy_cache_candidates.append(run_dir / "openalex_cache.csv")
            corpus_candidates.append(run_dir / "corpus.csv")

    audit_candidates.extend(
        [
            paths.run_dir / "indicators" / "fetch_relevance_audit.csv",
            paths.root / "indicators" / "fetch_relevance_audit.csv",
        ]
    )
    legacy_cache_candidates.append(paths.run_dir / "openalex_cache.csv")
    corpus_candidates.extend([paths.run_dir / "corpus.csv", paths.root / "corpus.csv"])

    seen_paths: set[str] = set()
    for bucket in (audit_candidates, legacy_cache_candidates, corpus_candidates):
        existing_candidates = []
        for candidate in bucket:
            candidate_str = str(candidate)
            if candidate.exists() and candidate_str not in seen_paths:
                seen_paths.add(candidate_str)
                existing_candidates.append(candidate)

        for candidate in sorted(existing_candidates, key=lambda path: path.stat().st_mtime, reverse=True):
            try:
                frame = pd.read_csv(candidate, dtype=str, keep_default_na=False)
            except Exception:
                continue

            if "data_source" in frame.columns:
                frame = frame[frame["data_source"].astype(str).str.strip().str.lower() == "openalex"].copy()
            if frame.empty:
                continue
            if not {"id", "title", "abstract"}.issubset(frame.columns):
                continue
            return normalise_source_frame(frame, "openalex"), str(candidate)

    return None, ""


def _semantic_relevance(texts: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    n_rows = len(texts)
    nan_scores = np.full(n_rows, np.nan, dtype=np.float32)
    zero_scores = np.zeros(n_rows, dtype=np.float32)

    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        print(f"\nSemantic relevance disabled: {exc}")
        return nan_scores, nan_scores, zero_scores, "unavailable"

    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"\nSemantic relevance scoring with {FETCH_SEMANTIC_MODEL} on {device.upper()}...")
        model = SentenceTransformer(FETCH_SEMANTIC_MODEL, device=device)
        model.eval()

        text_embeddings = model.encode(
            texts,
            batch_size=64,
            show_progress_bar=True,
            normalize_embeddings=True,
        ).astype(np.float32)
        positive_embeddings = model.encode(
            RELEVANCE_POSITIVE_PROTOTYPES,
            batch_size=16,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).astype(np.float32)
        negative_embeddings = model.encode(
            RELEVANCE_NEGATIVE_PROTOTYPES,
            batch_size=16,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).astype(np.float32)

        positive_sim = text_embeddings @ positive_embeddings.T  # (n, n_pos)
        negative_sim = text_embeddings @ negative_embeddings.T  # (n, n_neg)

        # mean_top2: more stable than max — less sensitive to one lucky prototype match.
        # With 13 fine-grained positive prototypes, top-2 mean captures the best-matching
        # sub-topic without letting a single generic sentence dominate.
        k_pos = min(2, positive_sim.shape[1])
        positive_score = np.sort(positive_sim, axis=1)[:, -k_pos:].mean(axis=1)

        # For negatives keep max: we want to penalise a paper if it strongly resembles
        # ANY negative domain (EFL survey, medical, industrial, etc.).
        negative_max = negative_sim.max(axis=1)

        margin = positive_score - negative_max
        return positive_score, negative_max, margin, FETCH_SEMANTIC_MODEL
    except Exception as exc:
        print(f"\nSemantic relevance fallback to lexical-only scoring: {exc}")
        return nan_scores, nan_scores, zero_scores, "failed"


def run(paths: RunPaths) -> pd.DataFrame:
    ensure_run_dirs(paths)

    print("=" * 68)
    print("STEP 1 — IDENTIFICATION (broad retrieval + hybrid relevance ranking)")
    print("=" * 68)

    filter_str = (
        f"title.search:{AI_TITLE_SEARCH},"
        f"publication_year:>{YEAR_MIN - 1},"
        "type:article|review"
    )

    cache_enabled = source_cache_enabled()
    source_cache_status: dict[str, str] = {}

    oa_cache_key = {
        "cache_schema": 2,
        "filter": filter_str,
        "search_terms": ALL_RESEARCH_SEARCH_TERMS,
        "year_min": YEAR_MIN,
        "year_max": YEAR_MAX,
    }
    query_hits: list[dict] = []
    total_raw_hits = 0

    df, oa_cache_meta = load_source_cache(paths.root, "openalex", oa_cache_key)
    if df is not None:
        source_cache_status["openalex"] = "hit"
        query_hits = list(oa_cache_meta.get("query_hits", []))
        total_raw_hits = int(oa_cache_meta.get("total_raw_hits", len(df)) or len(df))
        n_oa_unique = len(df)
        print(f"\n  [OpenAlex] Loaded from shared cache ({n_oa_unique} unique candidates) — skipping API calls.")
    else:
        seed_df, seeded_from = _find_openalex_seed_frame(paths)
        if cache_enabled and seed_df is not None:
            oa_cache_meta = save_source_cache(
                paths.root,
                "openalex",
                oa_cache_key,
                seed_df,
                metadata={
                    "total_raw_hits": len(seed_df),
                    "n_unique": len(seed_df),
                    "query_hits": [],
                    "seeded_from": seeded_from,
                },
            )
            df = seed_df
            source_cache_status["openalex"] = "seeded"
            total_raw_hits = int(oa_cache_meta.get("total_raw_hits", len(df)) or len(df))
            n_oa_unique = len(df)
            print(f"\n  [OpenAlex] Seeded shared cache from {seeded_from} ({n_oa_unique} rows) — skipping API calls.")
        else:
            source_cache_status["openalex"] = "miss" if cache_enabled else "disabled"
            union_records: dict[str, dict] = {}
            matched_query_terms: dict[str, set[str]] = {}
            for term in ALL_RESEARCH_SEARCH_TERMS:
                batch = openalex_fetch_all(filter_str, search_term=term)
                query_hits.append({"source": "openalex", "term": term, "n_results": len(batch)})
                total_raw_hits += len(batch)
                for record in batch:
                    record_id = record.get("id")
                    if record_id:
                        matched_query_terms.setdefault(record_id, set()).add(term)
                        union_records[record_id] = record

            df = openalex_flatten_records(list(union_records.values()))
            df["data_source"] = "openalex"
            df["matched_search_terms"] = df["id"].map(lambda value: _pipe_join(matched_query_terms.get(value, set())))
            df["matched_search_term_count"] = df["id"].map(lambda value: len(matched_query_terms.get(value, set())))
            df["keyword_terms"] = df.get("keywords", pd.Series([None] * len(df))).apply(
                lambda value: _extract_display_names(value, limit=8)
            )
            df["topic_terms"] = df.get("topics", pd.Series([None] * len(df))).apply(
                lambda value: _extract_display_names(value, limit=3)
            )
            df = normalise_source_frame(df, "openalex")
            n_oa_unique = len(df)
            print(f"\n  [OpenAlex] Raw query hits (summed): {total_raw_hits}")
            print(f"  [OpenAlex] Unique candidates       : {n_oa_unique}")

            if cache_enabled:
                save_source_cache(
                    paths.root,
                    "openalex",
                    oa_cache_key,
                    df,
                    metadata={
                        "total_raw_hits": total_raw_hits,
                        "n_unique": n_oa_unique,
                        "query_hits": query_hits,
                    },
                )
                print("  [OpenAlex] Shared cache saved.")

    # ------------------------------------------------------------------
    # Merge Semantic Scholar results (optional; deduplicated by bare DOI)
    # ------------------------------------------------------------------
    n_ss_unique = 0
    n_ss_new = 0
    if SEMANTIC_SCHOLAR_ENABLED:
        from . import semantic_scholar as _ss
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        api_key = SEMANTIC_SCHOLAR_API_KEY or os.environ.get("S2_API_KEY", "") or None
        print("\n" + "=" * 68)
        print("STEP 1b — Semantic Scholar supplemental fetch")
        print("=" * 68)

        ss_cache_key = {
            "cache_schema": 1,
            "search_terms": ALL_RESEARCH_SEARCH_TERMS,
            "year_min": YEAR_MIN,
            "year_max": YEAR_MAX,
            "page_size": _ss.PAGE_SIZE,
            "max_per_query": _ss.MAX_PER_QUERY,
        }
        df_ss, _ = load_source_cache(paths.root, "semantic_scholar", ss_cache_key)
        if df_ss is not None:
            source_cache_status["semantic_scholar"] = "hit"
            n_ss_unique = len(df_ss)
            print(f"  [S2] Loaded from shared cache ({n_ss_unique} unique candidates) — skipping API calls.")
        elif not api_key:
            source_cache_status["semantic_scholar"] = "miss_no_key" if cache_enabled else "disabled"
            df_ss = None
            print("  [S2] No S2_API_KEY set — skipping Semantic Scholar (unauthenticated rate-limit is unusable for bulk queries).")
            print("       Set S2_API_KEY in .env or config.py to enable Semantic Scholar.")
        else:
            source_cache_status["semantic_scholar"] = "miss" if cache_enabled else "disabled"
            ss_union, ss_matched = _ss.fetch_all(
                ALL_RESEARCH_SEARCH_TERMS,
                year_min=YEAR_MIN,
                year_max=YEAR_MAX,
                api_key=api_key,
            )
            n_ss_unique = len(ss_union)
            print(f"  [S2] Unique candidates before DOI dedup: {n_ss_unique}")
            df_ss = None
            if ss_union:
                df_ss = normalise_source_frame(_ss.flatten_records(ss_union, ss_matched), "semantic_scholar")
                if cache_enabled:
                    save_source_cache(
                        paths.root,
                        "semantic_scholar",
                        ss_cache_key,
                        df_ss,
                        metadata={
                            "n_unique": n_ss_unique,
                            "year_min": YEAR_MIN,
                            "year_max": YEAR_MAX,
                        },
                    )
                    print("  [S2] Shared cache saved.")

        if df_ss is not None and not df_ss.empty:
            if source_cache_status.get("semantic_scholar") in {"hit"}:
                print(f"  [S2] Unique candidates before DOI dedup: {n_ss_unique}")
            df_ss_new = _filter_new_source_records(df, df_ss)
            n_ss_new = len(df_ss_new)
            print(f"  [S2] New records (not in OpenAlex by DOI/title): {n_ss_new}")

            if n_ss_new > 0:
                df = pd.concat([df, df_ss_new], ignore_index=True)

    # ------------------------------------------------------------------
    # Merge Europe PMC results (optional; abstract-rich, strongest for biomed spillover)
    # ------------------------------------------------------------------
    n_epmc_unique = 0
    n_epmc_new = 0
    if EUROPE_PMC_ENABLED:
        from . import europe_pmc as _epmc

        print("\n" + "=" * 68)
        print("STEP 1bb — Europe PMC supplemental fetch")
        print("=" * 68)

        epmc_cache_key = {
            "cache_schema": 1,
            "queries": EUROPE_PMC_QUERIES,
            "max_results_per_query": _epmc.MAX_RESULTS_PER_QUERY,
            "page_size": _epmc.PAGE_SIZE,
        }
        df_epmc, _ = load_source_cache(paths.root, "europe_pmc", epmc_cache_key)
        if df_epmc is not None:
            source_cache_status["europe_pmc"] = "hit"
            n_epmc_unique = len(df_epmc)
            print(f"  [EuropePMC] Loaded from shared cache ({n_epmc_unique} unique candidates) — skipping API calls.")
        else:
            source_cache_status["europe_pmc"] = "miss" if cache_enabled else "disabled"
            epmc_union, epmc_matched = _epmc.fetch_all(EUROPE_PMC_QUERIES)
            n_epmc_unique = len(epmc_union)
            print(f"  [EuropePMC] Unique candidates before DOI dedup: {n_epmc_unique}")
            df_epmc = None
            if epmc_union:
                df_epmc = normalise_source_frame(_epmc.flatten_records(epmc_union, epmc_matched), "europe_pmc")
                if cache_enabled:
                    save_source_cache(
                        paths.root,
                        "europe_pmc",
                        epmc_cache_key,
                        df_epmc,
                        metadata={"n_unique": n_epmc_unique},
                    )
                    print("  [EuropePMC] Shared cache saved.")

        if df_epmc is not None and not df_epmc.empty:
            if source_cache_status.get("europe_pmc") in {"hit"}:
                print(f"  [EuropePMC] Unique candidates before DOI dedup: {n_epmc_unique}")
            df_epmc_new = _filter_new_source_records(df, df_epmc)
            n_epmc_new = len(df_epmc_new)
            print(f"  [EuropePMC] New records (not in OA/S2 by DOI/title): {n_epmc_new}")
            if n_epmc_new > 0:
                df = pd.concat([df, df_epmc_new], ignore_index=True)

    # ------------------------------------------------------------------
    # Merge Scopus results (optional; uses narrow per-topic queries)
    # ------------------------------------------------------------------
    n_scopus_unique = 0
    n_scopus_new = 0
    if SCOPUS_ENABLED:
        from . import scopus as _sc
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        sc_api_key = SCOPUS_API_KEY or os.environ.get("SCOPUS_API_KEY", "")
        sc_inst_token = SCOPUS_INST_TOKEN or os.environ.get("SCOPUS_INST_TOKEN", "") or None
        print("\n" + "=" * 68)
        print("STEP 1c — Scopus supplemental fetch")
        print("=" * 68)

        sc_cache_key = {
            "cache_schema": 3,
            "queries": SCOPUS_QUERIES,
            "max_results_per_query": _sc.MAX_RESULTS_PER_QUERY,
            "page_size": _sc.PAGE_SIZE,
            "safe_page_size": _sc.SAFE_PAGE_SIZE,
            "abstract_backfill_enabled": SCOPUS_ABSTRACT_BACKFILL_ENABLED,
            "abstract_backfill_max_dois": SCOPUS_ABSTRACT_BACKFILL_MAX_DOIS,
            "min_abstract_length": MIN_ABSTRACT_LENGTH,
        }
        df_sc, _ = load_source_cache(paths.root, "scopus", sc_cache_key)
        if df_sc is not None:
            source_cache_status["scopus"] = "hit"
            n_scopus_unique = len(df_sc)
            print(f"  [Scopus] Loaded from shared cache ({n_scopus_unique} unique candidates) — skipping API calls.")
        elif not sc_api_key:
            source_cache_status["scopus"] = "miss_no_key" if cache_enabled else "disabled"
            df_sc = None
            print(
                "  [Scopus] SCOPUS_API_KEY not set — skipping.\n"
                "  Set it in config.py or via the SCOPUS_API_KEY env var."
            )
        else:
            source_cache_status["scopus"] = "miss" if cache_enabled else "disabled"
            sc_union, sc_matched = _sc.fetch_all(
                SCOPUS_QUERIES,
                api_key=sc_api_key,
                inst_token=sc_inst_token or None,
            )
            n_scopus_unique = len(sc_union)
            print(f"  [Scopus] Unique candidates before DOI dedup: {n_scopus_unique}")
            df_sc = None
            if sc_union:
                df_sc = normalise_source_frame(_sc.flatten_records(sc_union, sc_matched), "scopus")
                if SCOPUS_ABSTRACT_BACKFILL_ENABLED:
                    df_sc, backfill_stats = backfill_missing_abstracts(
                        df_sc,
                        max_records=SCOPUS_ABSTRACT_BACKFILL_MAX_DOIS,
                        min_abstract_length=MIN_ABSTRACT_LENGTH,
                    )
                    print(
                        "  [Scopus] Abstract backfill: "
                        f"attempted={backfill_stats['attempted']} filled={backfill_stats['filled']} "
                        f"(EuropePMC={backfill_stats['filled_europe_pmc']}, Crossref={backfill_stats['filled_crossref']})"
                    )
                if cache_enabled:
                    save_source_cache(
                        paths.root,
                        "scopus",
                        sc_cache_key,
                        df_sc,
                        metadata={
                            "n_unique": n_scopus_unique,
                            "abstract_backfill_enabled": SCOPUS_ABSTRACT_BACKFILL_ENABLED,
                            "abstract_backfill_max_dois": SCOPUS_ABSTRACT_BACKFILL_MAX_DOIS,
                        },
                    )
                    print("  [Scopus] Shared cache saved.")

        if df_sc is not None and not df_sc.empty:
            if source_cache_status.get("scopus") in {"hit"}:
                print(f"  [Scopus] Unique candidates before DOI dedup: {n_scopus_unique}")
            df_sc_new = _filter_new_source_records(df, df_sc)
            n_scopus_new = len(df_sc_new)
            print(f"  [Scopus] New records (not in OA/S2 by DOI/title): {n_scopus_new}")

            if n_scopus_new > 0:
                df = pd.concat([df, df_sc_new], ignore_index=True)

    # ------------------------------------------------------------------
    # Merge manual exports (manual/normalized.csv — human-searched records)
    # ------------------------------------------------------------------
    n_manual_new = 0
    _manual_path = paths.root / "manual" / "normalized.csv"
    if _manual_path.exists():
        print("\n" + "=" * 68)
        print("STEP 1d — Manual export merge (manual/normalized.csv)")
        print("=" * 68)
        df_manual = pd.read_csv(_manual_path, dtype=str, keep_default_na=False)
        if "year" in df_manual.columns and "publication_year" not in df_manual.columns:
            df_manual = df_manual.rename(columns={"year": "publication_year"})
        df_manual_new = _filter_new_source_records(df, df_manual)
        n_manual_new = len(df_manual_new)
        print(f"  [Manual] New records (not already in API pool): {n_manual_new}")
        if n_manual_new > 0:
            df = pd.concat([df, df_manual_new], ignore_index=True)

    df = normalise_source_frame(df, "openalex")

    n_identified_unique = len(df)
    print(f"\n  Total unique candidates after all sources: {n_identified_unique}")

    raw_path = paths.indicators_dir / "fetch_raw_candidates.csv"
    df.to_csv(raw_path, index=False)
    print(f"  Saved raw candidates (pre-filter) → {raw_path}")

    title_blob = df["title"].fillna("")
    title_context_blob = (
        title_blob
        + " "
        + df["primary_topic"].fillna("")
        + " "
        + df["keyword_terms"].fillna("")
    )
    text_blob = title_context_blob + " " + df["topic_terms"].fillna("") + " " + df["abstract"].fillna("")
    df["scope_positive_hits"] = text_blob.apply(lambda value: _pipe_join(_matching_labels(value, POSITIVE_SCOPE_RULES)))
    df["scope_positive_title_hits"] = title_context_blob.apply(
        lambda value: _pipe_join(_matching_labels(value, POSITIVE_SCOPE_RULES))
    )
    df["scope_negative_hits"] = text_blob.apply(
        lambda value: _pipe_join(_matching_labels(value, HARD_NEGATIVE_SCOPE_RULES))
    )
    df["ai_signal_hits"] = text_blob.apply(lambda value: _pipe_join(_matching_labels(value, AI_SIGNAL_RULES)))
    df["category"] = text_blob.apply(_categorise)

    df["scope_positive_count"] = df["scope_positive_hits"].apply(_count_labels)
    df["scope_positive_title_count"] = df["scope_positive_title_hits"].apply(_count_labels)
    df["scope_negative_count"] = df["scope_negative_hits"].apply(_count_labels)
    df["ai_signal_count"] = df["ai_signal_hits"].apply(_count_labels)
    df["core_alignment"] = df["scope_positive_count"] > 0

    df["title_offtopic"] = df["title"].str.contains(HARD_OFFTOPIC_TITLE_RE, na=False)
    df["offtopic_topic"] = df["primary_topic"].astype(str).str.contains(OFFTOPIC_PRIMARY_TOPIC_RE, na=False)
    df["abstract_ok"] = df["abstract"].str.len().fillna(0) >= MIN_ABSTRACT_LENGTH

    semantic_texts = (
        df["title"].fillna("")
        + ". "
        + df["primary_topic"].fillna("")
        + ". "
        + df["keyword_terms"].fillna("")
        + ". "
        + df["abstract"].fillna("").str[:2500]
    ).tolist()
    positive_max, negative_max, semantic_margin, relevance_model = _semantic_relevance(semantic_texts)
    df["semantic_positive_max"] = positive_max
    df["semantic_negative_max"] = negative_max
    df["semantic_margin"] = semantic_margin

    semantic_positive_norm = ((pd.to_numeric(df["semantic_positive_max"], errors="coerce").fillna(-1) + 1) / 2).clip(0, 1)
    semantic_negative_norm = ((pd.to_numeric(df["semantic_negative_max"], errors="coerce").fillna(-1) + 1) / 2).clip(0, 1)
    semantic_margin_pos = pd.to_numeric(df["semantic_margin"], errors="coerce").fillna(0).clip(lower=0, upper=1)

    relevance_index = (
        0.24 * semantic_positive_norm
        + 0.18 * semantic_margin_pos
        + 0.24 * _normalize_count(df["scope_positive_count"], cap=3)
        + 0.10 * _normalize_count(df["scope_positive_title_count"], cap=2)
        + 0.08 * _normalize_count(df["ai_signal_count"], cap=4)
        + 0.05 * _normalize_count(df["matched_search_term_count"], cap=6)
        + 0.05 * df["abstract_ok"].astype(float)
        - 0.22 * _normalize_count(df["scope_negative_count"], cap=3)
        - 0.12 * semantic_negative_norm
        - 0.16 * df["offtopic_topic"].astype(float)
    ).clip(lower=0, upper=1)
    df["relevance_index"] = relevance_index.round(4)

    reason = pd.Series("", index=df.index, dtype="object")
    reason = reason.mask(~df["abstract_ok"], "no_abstract")
    reason = reason.mask(df["title_offtopic"], "offtopic_title")
    reason = reason.mask((reason == "") & ~df["core_alignment"], "weak_domain_alignment")
    df["fetch_exclusion_reason"] = reason

    # Manual imports bypass topic/alignment filters — they were selected by
    # intentional human queries and are presumed topically relevant.
    _MANUAL_SOURCES = {"pubmed_manual", "wos_manual", "bibtex_manual", "scopus_pdf", "ris_manual"}
    _manual_mask = df["data_source"].isin(_MANUAL_SOURCES)
    if _manual_mask.any():
        df.loc[_manual_mask & df["abstract_ok"], "fetch_exclusion_reason"] = ""

    ranked = df[df["fetch_exclusion_reason"] == ""].copy()
    ranked = ranked.sort_values(
        ["relevance_index", "matched_search_term_count", "scope_positive_count", "cited_by_count"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    base_keep_mask = ranked["relevance_index"] >= FETCH_RELEVANCE_THRESHOLD
    n_base_keep = int(base_keep_mask.sum())
    if n_base_keep < FETCH_MIN_FINAL:
        keep_count = min(FETCH_MIN_FINAL, len(ranked))
        keep_strategy = "min_floor_top_ranked"
        kept_ranked = ranked.head(keep_count).copy()
    elif n_base_keep > FETCH_MAX_FINAL:
        keep_count = FETCH_MAX_FINAL
        keep_strategy = "max_cap_top_ranked"
        kept_ranked = ranked.head(keep_count).copy()
    else:
        keep_count = n_base_keep
        keep_strategy = "score_threshold"
        kept_ranked = ranked[base_keep_mask].copy()

    kept_ranked = kept_ranked.reset_index(drop=True)
    keep_ids = set(kept_ranked["id"])
    actual_threshold = float(kept_ranked["relevance_index"].min()) if len(kept_ranked) else FETCH_RELEVANCE_THRESHOLD

    df.loc[df["fetch_exclusion_reason"] == "", "fetch_exclusion_reason"] = "low_relevance"
    df.loc[df["id"].isin(keep_ids), "fetch_exclusion_reason"] = "keep"
    # Manual records with abstracts are always kept regardless of relevance score.
    if _manual_mask.any():
        df.loc[_manual_mask & df["abstract_ok"], "fetch_exclusion_reason"] = "keep"
    df["fetch_keep_rank"] = df["id"].map({record_id: idx + 1 for idx, record_id in enumerate(kept_ranked["id"])})

    excluded = df[df["fetch_exclusion_reason"] != "keep"].copy()
    kept = df[df["fetch_exclusion_reason"] == "keep"].copy().sort_values("fetch_keep_rank")

    print("\nFETCH AUDIT")
    print(f"  excluded — no/short abstract   : {int((df['fetch_exclusion_reason'] == 'no_abstract').sum())}")
    print(f"  excluded — off-topic title     : {int((df['fetch_exclusion_reason'] == 'offtopic_title').sum())}")
    print(f"  excluded — weak alignment      : {int((df['fetch_exclusion_reason'] == 'weak_domain_alignment').sum())}")
    print(f"  ranked candidates              : {len(ranked)}")
    print(f"  excluded — low relevance       : {int((df['fetch_exclusion_reason'] == 'low_relevance').sum())}")
    print(f"  keep strategy                  : {keep_strategy}")
    print(f"  base threshold                 : {FETCH_RELEVANCE_THRESHOLD:.3f}")
    print(f"  applied threshold              : {actual_threshold:.3f}")
    print(f"  kept after hybrid relevance    : {len(kept)}")
    if "data_source" in kept.columns:
        for src, cnt in kept["data_source"].value_counts().items():
            pct = 100 * cnt / len(kept)
            print(f"    └─ {src}: {cnt} ({pct:.0f}%)")

    print("\nCATEGORY BREAKDOWN")
    for category, count in kept["category"].value_counts().items():
        pct = 100 * count / len(kept) if len(kept) else 0
        print(f"  {count:4d} ({pct:4.1f}%)  {category}")

    print("\nTOP COUNTRIES")
    for code, count in summarise_countries(kept):
        print(f"  {code:>3}  {count:4d}")

    audit_path = paths.indicators_dir / "fetch_relevance_audit.csv"
    df.sort_values("relevance_index", ascending=False).to_csv(audit_path, index=False)

    kept = kept.drop(columns=["title_offtopic", "offtopic_topic", "abstract_ok", "core_alignment"])
    kept.to_csv(paths.corpus_fetch_path, index=False)

    fetch_log = {
        "retrieval_profile": "broad_candidate_union_hybrid_relevance",
        "year_min": YEAR_MIN,
        "sources_enabled": (
            ["openalex"]
            + (["semantic_scholar"] if SEMANTIC_SCHOLAR_ENABLED else [])
            + (["europe_pmc"] if EUROPE_PMC_ENABLED else [])
            + (["scopus"] if SCOPUS_ENABLED else [])
        ),
        "n_openalex_unique": n_oa_unique,
        "n_semantic_scholar_candidates": n_ss_unique,
        "n_semantic_scholar_new": n_ss_new,
        "n_europe_pmc_candidates": n_epmc_unique,
        "n_europe_pmc_new": n_epmc_new,
        "n_scopus_candidates": n_scopus_unique,
        "n_scopus_new": n_scopus_new,
        "n_manual_new": n_manual_new,
        "n_query_hits_total": total_raw_hits,
        "n_identified_unique": n_identified_unique,
        "n_candidates_ranked": len(ranked),
        "n_excluded_noabstract": int((df["fetch_exclusion_reason"] == "no_abstract").sum()),
        "n_excluded_offtopic": int((df["fetch_exclusion_reason"] == "offtopic_title").sum()),
        "n_excluded_weak_alignment": int((df["fetch_exclusion_reason"] == "weak_domain_alignment").sum()),
        "n_excluded_low_relevance": int((df["fetch_exclusion_reason"] == "low_relevance").sum()),
        "n_final_fetch": len(kept),
        "relevance_model": relevance_model,
        "relevance_base_threshold": FETCH_RELEVANCE_THRESHOLD,
        "relevance_threshold_applied": actual_threshold,
        "relevance_keep_strategy": keep_strategy,
        "relevance_min_final": FETCH_MIN_FINAL,
        "relevance_max_final": FETCH_MAX_FINAL,
        "source_cache": {
            "enabled": cache_enabled,
            **source_cache_status,
        },
        "query_hits": query_hits,
    }
    write_json(paths.fetch_log_path, fetch_log)

    excluded_path = paths.indicators_dir / "fetch_exclusions.csv"
    excluded.to_csv(excluded_path, index=False)
    print(f"\nSaved → {paths.corpus_fetch_path}")
    print(f"Saved → {excluded_path}")
    print(f"Saved → {audit_path}")
    print(f"Saved → {paths.fetch_log_path}")
    return kept