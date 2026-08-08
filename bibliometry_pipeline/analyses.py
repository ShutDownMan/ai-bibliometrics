from __future__ import annotations

import re
from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer

from .config import CLUSTER_METADATA, YEAR_MAX, YEAR_MIN
from .paths import RunPaths, ensure_run_dirs


KW_NOISE = re.compile(
    r"conflict|publication of this article|to influence the work reported in this paper|https?://|<w:",
    re.IGNORECASE,
)

CLUSTER_PHRASE_STOPLIST = {
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "large language model",
    "large language models",
    "generative ai",
    "systematic review",
    "literature review",
    "scoping review",
    "narrative review",
    "sensitivity specificity",
    "pooled sensitivity",
    "area curve",
    "curve auc",
    "pubmed embase",
    "future directions",
    "chatgpt",
    "humans",
}

CLUSTER_PHRASE_BAD_TOKENS = {
    "review",
    "reviews",
    "study",
    "studies",
    "article",
    "articles",
    "paper",
    "papers",
}

FALLBACK_UNIGRAM_STOPLIST = {
    "artificial",
    "intelligence",
    "machine",
    "learning",
    "deep",
    "language",
    "large",
    "model",
    "models",
    "humans",
    "review",
    "research",
    "systematic",
    "literature",
}


def _mode_text(series: pd.Series) -> str:
    values = series.dropna().astype(str)
    if values.empty:
        return ""
    modes = values.mode()
    return str(modes.iloc[0]) if not modes.empty else str(values.iloc[0])


def _normalize_keyword_terms(value: object) -> list[str]:
    terms: list[str] = []
    if pd.isna(value):
        return terms
    for raw in str(value).split("|"):
        for term in raw.split(";"):
            cleaned = re.sub(r"^\*+", "", term.strip().lower())
            cleaned = re.sub(r"\s+", " ", cleaned)
            if cleaned and 3 < len(cleaned) <= 80 and not KW_NOISE.search(cleaned):
                terms.append(cleaned)
    return terms


def _format_cluster_phrase(phrase: str) -> str:
    # Restore stop-words that CountVectorizer strips from known multi-word terms
    _PHRASE_FIXUPS: dict[str, str] = {
        "internet things": "Internet of Things",
        "end life": "End of Life",
        "point care": "Point of Care",
        "state art": "State of the Art",
    }
    key = re.sub(r"\s+", " ", phrase.strip().lower())
    if key in _PHRASE_FIXUPS:
        return _PHRASE_FIXUPS[key]
    text = phrase.title()
    replacements = {
        "Ai": "AI",
        "Iot": "IoT",
        "Llm": "LLM",
        "Llms": "LLMs",
        "Mri": "MRI",
        "Ct": "CT",
        "Aigc": "AIGC",
        "Nlp": "NLP",
    }
    for src, dst in replacements.items():
        text = re.sub(rf"\b{src}\b", dst, text)
    return text


def _is_valid_cluster_phrase(phrase: str) -> bool:
    cleaned = re.sub(r"\s+", " ", phrase.strip().lower())
    if len(cleaned) < 4:
        return False
    if any(fragment in cleaned for fragment in CLUSTER_PHRASE_STOPLIST):
        return False
    tokens = cleaned.split()
    if any(token in CLUSTER_PHRASE_BAD_TOKENS for token in tokens):
        return False
    if any(fragment in cleaned for fragment in (" using ", " based on ", " et al", "this ")):
        return False
    return True


def _select_cluster_phrases(candidates: list[str], top_n: int = 5) -> list[str]:
    selected: list[str] = []
    seen_tokens: set[str] = set()
    for candidate in candidates:
        tokens = set(candidate.split())
        if candidate in selected:
            continue
        if selected and (tokens.issubset(seen_tokens) or len(tokens & seen_tokens) >= max(2, len(tokens) - 1)):
            continue
        selected.append(candidate)
        seen_tokens.update(tokens)
        if len(selected) == top_n:
            break
    return selected


def _fallback_cluster_phrases(counts: Counter, top_n: int = 5) -> list[str]:
    selected: list[str] = []
    for term, _ in counts.most_common():
        if len(term.split()) > 1:
            if not _is_valid_cluster_phrase(term):
                continue
        elif term in FALLBACK_UNIGRAM_STOPLIST:
            continue
        selected.append(term)
        if len(selected) == top_n:
            break
    return selected


def _extract_cluster_topics(df: pd.DataFrame, cluster_kw_counts: dict[int, Counter]) -> dict[int, list[str]]:
    cluster_ids: list[int] = []
    cluster_docs: list[str] = []
    for cluster_id, group in df.groupby("cluster"):
        cluster_ids.append(int(cluster_id))
        docs: list[str] = []
        for row in group[["title", "abstract", "keyword_terms"]].fillna("").itertuples(index=False):
            keyword_text = " ".join(_normalize_keyword_terms(row.keyword_terms))
            docs.append(f"{row.title} {row.abstract} {keyword_text}")
        cluster_docs.append(" ".join(docs))

    vectorizer = CountVectorizer(
        stop_words="english",
        ngram_range=(2, 3),
        min_df=1,
        max_df=0.8,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
    )
    matrix = vectorizer.fit_transform(cluster_docs)
    if matrix.shape[1] == 0:
        return {
            cluster_id: _fallback_cluster_phrases(cluster_kw_counts.get(cluster_id, Counter()))
            for cluster_id in cluster_ids
        }

    ctfidf = TfidfTransformer(norm=None, use_idf=True, smooth_idf=True).fit_transform(matrix)
    terms = vectorizer.get_feature_names_out()

    cluster_topics: dict[int, list[str]] = {}
    for row_idx, cluster_id in enumerate(cluster_ids):
        scores = ctfidf.getrow(row_idx).toarray().ravel()
        ordered_terms = [
            terms[idx]
            for idx in scores.argsort()[::-1]
            if scores[idx] > 0 and _is_valid_cluster_phrase(terms[idx])
        ]
        selected = _select_cluster_phrases(ordered_terms, top_n=5)
        if len(selected) < 2:
            for term in _fallback_cluster_phrases(cluster_kw_counts.get(cluster_id, Counter())):
                if term not in selected:
                    selected.append(term)
                if len(selected) == 5:
                    break
        cluster_topics[cluster_id] = selected or [f"cluster {cluster_id}"]
    return cluster_topics


def run(paths: RunPaths) -> None:
    ensure_run_dirs(paths)

    scores = pd.read_csv(paths.indicators_dir / "axis_scores.csv")
    _corpus_probe = pd.read_csv(paths.corpus_clustered_path, nrows=0)
    _corpus_base_cols = ["id", "title", "abstract", "cited_by_count", "publication_year",
                         "category", "primary_topic", "keyword_terms"]
    _corpus_extra_cols = [c for c in ["journal", "doi", "countries"] if c in _corpus_probe.columns]
    corpus = pd.read_csv(
        paths.corpus_clustered_path,
        usecols=_corpus_base_cols + _corpus_extra_cols,
    )
    corpus["cited_by_count"] = pd.to_numeric(corpus["cited_by_count"], errors="coerce").fillna(0).astype(int)

    df = scores.merge(corpus, on="id", how="left", suffixes=("", "_c"))
    if "publication_year_c" in df.columns:
        df["publication_year"] = df["publication_year_c"].combine_first(df["publication_year"])
        df.drop(columns=["publication_year_c"], inplace=True)
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")

    cluster_kw_counts: dict[int, Counter] = {}
    for cluster_id, group in df.groupby("cluster"):
        c: Counter = Counter()
        for value in group.get("keyword_terms", pd.Series(dtype=object)).dropna():
            for term in _normalize_keyword_terms(value):
                c[term] += 1
        cluster_kw_counts[int(cluster_id)] = c

    cluster_topics = _extract_cluster_topics(df, cluster_kw_counts)
    cluster_labels: dict[int, str] = {}
    cluster_descriptions: dict[int, str] = {}
    for cid, topics in cluster_topics.items():
        default_label = " · ".join(_format_cluster_phrase(term) for term in topics[:2])
        default_description = (
            "Artigos com foco predominante em: "
            + ", ".join(_format_cluster_phrase(term) for term in topics[:5])
            + "."
        )
        meta = CLUSTER_METADATA.get(int(cid), {})
        cluster_labels[cid] = meta.get("label", default_label)
        cluster_descriptions[cid] = meta.get("description", default_description)

    df["cluster_label"] = df["cluster"].map(cluster_labels)
    df["cluster_description"] = df["cluster"].map(cluster_descriptions)

    years_plot = list(range(YEAR_MIN, YEAR_MAX + 1))
    df_core = df[df["publication_year"].isin(years_plot)].copy()

    temporal_out = df_core.groupby("publication_year").agg(
        n=("id", "count"),
        pct_e_pos=("axis_e_technology", lambda x: (x > 0).mean() * 100),
        mean_e=("axis_e_technology", "mean"),
        mean_g=("axis_g_guardrails", "mean"),
        mean_n=("axis_n_domain", "mean"),
        mean_r=("axis_r_scope", "mean"),
    )
    temporal_out.index.name = "year"
    temporal_out.to_csv(paths.indicators_dir / "temporal_profile.csv")

    cluster_year = (
        df_core.groupby(["publication_year", "cluster"])
        .size()
        .unstack(fill_value=0)
    )
    ordered_cluster_ids = sorted(cluster_labels)
    cluster_year = cluster_year.reindex(columns=ordered_cluster_ids, fill_value=0)
    cluster_year = cluster_year.rename(columns=cluster_labels)
    cluster_year_pct = cluster_year.div(cluster_year.sum(axis=1), axis=0) * 100
    cluster_year_pct.round(2).to_csv(paths.indicators_dir / "cluster_share_by_year.csv")

    save_cols = [
        "id", "title", "publication_year", "cluster", "cluster_label",
        "cluster_description", "category", "primary_topic", "cited_by_count",
        "axis_e_technology", "axis_g_guardrails", "axis_n_domain", "axis_r_scope",
    ]
    df[save_cols].to_csv(paths.indicators_dir / "axis_scores_enriched.csv", index=False)

    print(f"Saved: {paths.indicators_dir / 'temporal_profile.csv'}")
    print(f"Saved: {paths.indicators_dir / 'cluster_share_by_year.csv'}")
    print(f"Saved: {paths.indicators_dir / 'axis_scores_enriched.csv'}")

    # -----------------------------------------------------------------------
    # Zipf analysis: fit rank-frequency to keyword data
    # Standard bibliometric practice: fit over non-singleton terms (freq >= 2)
    # because hapax legomena (freq=1) dominate the long tail and flatten the
    # slope to near-zero when included in the OLS fit.
    # -----------------------------------------------------------------------
    kw_freq_path = paths.indicators_dir / "keyword_freq.csv"
    if kw_freq_path.exists():
        kw_freq_df = pd.read_csv(kw_freq_path)
        kw_freq_df = kw_freq_df[kw_freq_df["freq"] > 0].reset_index(drop=True)
        kw_freq_df = kw_freq_df.sort_values("freq", ascending=False).reset_index(drop=True)
        kw_freq_df["rank"] = range(1, len(kw_freq_df) + 1)
        n_hapax = int((kw_freq_df["freq"] == 1).sum())
        n_total = len(kw_freq_df)
        # Fit on core vocabulary (freq >= 2) for a meaningful Zipf slope
        kw_core = kw_freq_df[kw_freq_df["freq"] >= 2].reset_index(drop=True)
        kw_core["rank_core"] = range(1, len(kw_core) + 1)
        if len(kw_core) >= 5:
            log_rank = np.log(kw_core["rank_core"].values.astype(float))
            log_freq = np.log(kw_core["freq"].values.astype(float))
            slope, intercept, r_value, _p, _se = stats.linregress(log_rank, log_freq)
            zipf_alpha = -slope  # Zipf exponent (positive)
            zipf_r2 = r_value ** 2
            kw_freq_df["freq_expected"] = np.where(
                kw_freq_df["rank"] <= len(kw_core),
                np.exp(intercept) * kw_freq_df["rank"].values ** slope,
                float("nan"),
            )
            kw_freq_df["freq_expected"] = kw_freq_df["freq_expected"].round(2)
        else:
            zipf_alpha = float("nan")
            zipf_r2 = float("nan")
            kw_freq_df["freq_expected"] = float("nan")
        zipf_out = kw_freq_df[["rank", "keyword", "freq", "freq_expected"]].head(50).copy()
        zipf_out.to_csv(paths.indicators_dir / "zipf_analysis.csv", index=False)
        # Save summary stats
        zipf_stats = pd.DataFrame([{
            "n_unique_keywords": n_total,
            "n_hapax": n_hapax,
            "pct_hapax": round(100 * n_hapax / max(n_total, 1), 1),
            "n_core_vocab": len(kw_core),
            "zipf_alpha": round(zipf_alpha, 4) if zipf_alpha == zipf_alpha else None,
            "zipf_r2": round(zipf_r2, 4) if zipf_r2 == zipf_r2 else None,
            "top1_keyword": kw_freq_df.iloc[0]["keyword"] if len(kw_freq_df) else "",
            "top1_freq": int(kw_freq_df.iloc[0]["freq"]) if len(kw_freq_df) else 0,
            "top10_pct_total": round(
                100 * kw_freq_df.head(10)["freq"].sum() / max(kw_freq_df["freq"].sum(), 1), 1
            ),
        }])
        zipf_stats.to_csv(paths.indicators_dir / "zipf_stats.csv", index=False)
        print(f"Saved: {paths.indicators_dir / 'zipf_analysis.csv'} (alpha={zipf_alpha:.3f}, R²={zipf_r2:.3f}, core={len(kw_core)} terms)")

    # -----------------------------------------------------------------------
    # Focus cluster deep-dive: per-cluster top papers, journals, keywords
    # Clusters 3 (ChatGPT/Education/Integrity) and 4 (AI in Higher Ed) are the
    # study's thematic focus since the topic is AI in academic production.
    # We generate one unified CSV covering all clusters so the report can
    # present any cluster it needs.
    # -----------------------------------------------------------------------
    focus_cluster_ids = sorted(cluster_labels.keys())  # all clusters; C3, C4 are the focus
    all_focus_rows: list[dict] = []
    cluster_focus_journals_rows: list[dict] = []
    cluster_focus_keywords_rows: list[dict] = []
    _has_journal = "journal" in df.columns
    _has_doi = "doi" in df.columns

    for cid in focus_cluster_ids:
        c_label = cluster_labels[cid]
        c_df = df[df["cluster"] == cid].copy()
        if c_df.empty:
            continue

        # Top 10 cited papers for this cluster
        top_papers = (
            c_df[["id", "title", "publication_year", "cited_by_count"]
                 + (["journal"] if _has_journal else [])
                 + (["doi"] if _has_doi else [])]
            .nlargest(10, "cited_by_count")
        )
        for _, rr in top_papers.iterrows():
            all_focus_rows.append({
                "cluster_id": cid,
                "cluster_label": c_label,
                "title": str(rr["title"]) if pd.notna(rr.get("title")) else "",
                "publication_year": int(rr["publication_year"]) if pd.notna(rr.get("publication_year")) else 0,
                "cited_by_count": int(rr["cited_by_count"]),
                "journal": str(rr["journal"]) if _has_journal and pd.notna(rr.get("journal")) else "",
                "doi": str(rr["doi"]) if _has_doi and pd.notna(rr.get("doi")) else "",
            })

        # Top 5 journals for this cluster
        if _has_journal:
            jrn_counts: Counter = Counter()
            for v in c_df["journal"].dropna():
                s = str(v).strip()
                if not s or s.lower() == "nan":
                    continue
                # Basic normalization: collapse whitespace and title-case
                s = re.sub(r"\s+", " ", s).title()
                s = re.sub(r"\b(Ieee|Acm|Bmj|Plos|Jmir)\b", lambda m: m.group().upper(), s)
                jrn_counts[s] += 1
            for jrn, cnt in jrn_counts.most_common(5):
                cluster_focus_journals_rows.append({
                    "cluster_id": cid,
                    "cluster_label": c_label,
                    "journal": jrn,
                    "n_papers": cnt,
                    "pct": round(100 * cnt / max(len(c_df), 1), 1),
                })

        # Top 10 keywords for this cluster (from keyword_terms column)
        kw_c: Counter = Counter()
        for v in c_df["keyword_terms"].dropna():
            for term in _normalize_keyword_terms(v):
                kw_c[term] += 1
        top_kws = _fallback_cluster_phrases(kw_c, top_n=10)
        for kw in top_kws:
            cluster_focus_keywords_rows.append({
                "cluster_id": cid,
                "cluster_label": c_label,
                "keyword": kw,
                "freq": kw_c.get(kw, 0),
            })

    if all_focus_rows:
        focus_papers_df = pd.DataFrame(all_focus_rows)
        focus_papers_df.to_csv(paths.indicators_dir / "cluster_focus_papers.csv", index=False)
        print(f"Saved: {paths.indicators_dir / 'cluster_focus_papers.csv'}")

    if cluster_focus_journals_rows:
        focus_journals_df = pd.DataFrame(cluster_focus_journals_rows)
        focus_journals_df.to_csv(paths.indicators_dir / "cluster_focus_journals.csv", index=False)
        print(f"Saved: {paths.indicators_dir / 'cluster_focus_journals.csv'}")

    if cluster_focus_keywords_rows:
        focus_kw_df = pd.DataFrame(cluster_focus_keywords_rows)
        focus_kw_df.to_csv(paths.indicators_dir / "cluster_focus_keywords.csv", index=False)
        print(f"Saved: {paths.indicators_dir / 'cluster_focus_keywords.csv'}")