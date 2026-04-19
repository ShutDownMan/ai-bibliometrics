"""
bibliometry_pipeline.enrich
============================
Post-clean enrichment stage: backfills `cited_by_count` and `countries` via:
  1. OpenAlex /works (batch DOI lookup)
  2. Europe PMC search (fallback for no-DOI PubMed records, matched by PMID)

Results are persisted to per-run JSON caches so re-runs never re-query an
already-resolved DOI/PMID — protecting the free API quota.

Cache files (inside the run directory, hidden):
  .enrich_oa_cache.json   – {bare_doi: {cited_by_count, countries}}
  .enrich_epmc_cache.json – {pmid: cited_by_count}

Any DOI/PMID present in the cache (even with count=0) is skipped on re-run.
Only genuinely new corpus entries trigger new API calls.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

from .paths import RunPaths, ensure_run_dirs


_OA_WORKS_URL = "https://api.openalex.org/works"
_EPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_HEADERS = {"User-Agent": "bibliometry-unioeste/1.1 (mail@unioeste.br)"}
_BATCH_SIZE = 50          # OpenAlex filter OR-list limit
_EPMC_BATCH_SIZE = 25     # Europe PMC OR-query limit (safe conservative value)
_CACHE_SAVE_EVERY = 10    # persist OA cache every N batches (crash resilience)
_RETRY_WAITS = [10, 20, 40, 60]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_json_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_json_cache(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# OpenAlex helpers
# ---------------------------------------------------------------------------

def _bare_doi(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _fetch_batch(dois: list[str]) -> list[dict]:
    """Fetch a batch of DOIs from OpenAlex /works."""
    params = {
        "filter": "doi:" + "|".join(dois),
        "select": "doi,cited_by_count,authorships",
        "per-page": min(len(dois), 200),
    }
    for attempt, wait in enumerate([0] + _RETRY_WAITS):
        if wait:
            time.sleep(wait)
        try:
            resp = requests.get(_OA_WORKS_URL, params=params, headers=_HEADERS, timeout=30)
            if resp.status_code == 429:
                next_wait = _RETRY_WAITS[min(attempt, len(_RETRY_WAITS) - 1)]
                print(f"  [enrich] 429 on attempt {attempt + 1}; retrying in {next_wait}s")
                continue
            resp.raise_for_status()
            return resp.json().get("results", [])
        except requests.RequestException as exc:
            print(f"  [enrich] request error attempt {attempt + 1}: {exc}")
    return []


def _extract_countries(authorships: object) -> str:
    if not isinstance(authorships, list):
        return ""
    codes: set[str] = set()
    for auth in authorships:
        for inst in (auth.get("institutions") or []):
            code = inst.get("country_code", "")
            if code:
                codes.add(code)
    return "|".join(sorted(codes))


def _normalise_oa_doi(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    doi = raw.strip().lower()
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    return doi


# ---------------------------------------------------------------------------
# Europe PMC helpers
# ---------------------------------------------------------------------------

def _normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for title→PMID lookup."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _load_pmid_map(root: Path) -> dict[str, str]:
    """Scan manual/pubmed/*.txt (MEDLINE format) and return {normalised_title: pmid}."""
    pubmed_dir = root / "manual" / "pubmed"
    if not pubmed_dir.exists():
        return {}
    pmid_map: dict[str, str] = {}
    for txt_file in pubmed_dir.glob("*.txt"):
        try:
            text = txt_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        current: dict[str, list[str]] = {}
        current_tag: str | None = None

        def _flush(rec: dict[str, list[str]], store: dict[str, str] = pmid_map) -> None:
            pmid = " ".join(rec.get("PMID", [])).strip()
            title = " ".join(rec.get("TI", [])).strip()
            if pmid and title:
                store[_normalise_title(title)] = pmid

        for line in text.splitlines():
            m = re.match(r"^([A-Z]{2,4})\s*-\s*(.*)$", line)
            if m:
                current_tag = m.group(1)
                value = m.group(2).strip()
                current.setdefault(current_tag, [])
                if value:
                    current[current_tag].append(value)
            elif line.strip() == "" and "PMID" in current:
                _flush(current)
                current = {}
                current_tag = None
            elif line.startswith("      ") and current_tag:
                current.setdefault(current_tag, [])
                current[current_tag].append(line.strip())
        _flush(current)
    return pmid_map


def _fetch_epmc_batch(pmids: list[str]) -> list[dict]:
    """Query Europe PMC for a batch of PMIDs; returns dicts with citedByCount."""
    query = "(" + " OR ".join(f"EXT_ID:{p}" for p in pmids) + ") AND SRC:MED"
    params = {
        "query": query,
        "format": "json",
        "resultType": "lite",
        "pageSize": len(pmids),
    }
    for attempt, wait in enumerate([0] + _RETRY_WAITS):
        if wait:
            time.sleep(wait)
        try:
            resp = requests.get(_EPMC_SEARCH_URL, params=params, headers=_HEADERS, timeout=30)
            if resp.status_code == 429:
                print(f"  [enrich-epmc] 429 on attempt {attempt + 1}; retrying")
                continue
            resp.raise_for_status()
            results = resp.json().get("resultList", {}).get("result", [])
            return results if isinstance(results, list) else [results]
        except requests.RequestException as exc:
            print(f"  [enrich-epmc] request error attempt {attempt + 1}: {exc}")
    return []


# ---------------------------------------------------------------------------
# Main stage entry point
# ---------------------------------------------------------------------------

def run(paths: RunPaths) -> Path:
    ensure_run_dirs(paths)

    # Load per-run caches
    oa_cache_path = paths.run_dir / ".enrich_oa_cache.json"
    epmc_cache_path = paths.run_dir / ".enrich_epmc_cache.json"
    oa_cache: dict[str, dict] = _load_json_cache(oa_cache_path)
    epmc_cache: dict[str, int] = _load_json_cache(epmc_cache_path)
    if oa_cache:
        print(f"[enrich] Loaded OA cache: {len(oa_cache)} entries.")
    if epmc_cache:
        print(f"[enrich] Loaded EPMC cache: {len(epmc_cache)} entries.")

    df = pd.read_csv(paths.corpus_clean_path)
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    has_country = df["countries"].apply(
        lambda v: bool(pd.notna(v) and str(v).strip() not in ("", "nan"))
    )
    df["_bare_doi"] = df["doi"].apply(_bare_doi)
    needs_cit = df["cited_by_count"] == 0
    needs_country = ~has_country

    # -----------------------------------------------------------------------
    # Pass 1 — OpenAlex (DOI-based)
    # -----------------------------------------------------------------------
    candidate_mask = (df["_bare_doi"].str.len() > 0) & (needs_cit | needs_country)
    all_candidate_dois = df.loc[candidate_mask, "_bare_doi"].unique().tolist()
    uncached_dois = [d for d in all_candidate_dois if d not in oa_cache]
    cached_count = len(all_candidate_dois) - len(uncached_dois)

    if uncached_dois:
        n_batches = (len(uncached_dois) - 1) // _BATCH_SIZE + 1
        print(
            f"[enrich] OpenAlex: {len(uncached_dois)} DOIs to fetch ({n_batches} batches);"
            f" {cached_count} already cached → skipped."
        )
        for i in range(0, len(uncached_dois), _BATCH_SIZE):
            batch = uncached_dois[i: i + _BATCH_SIZE]
            results = _fetch_batch(batch)
            fetched_keys: set[str] = set()
            for record in results:
                doi_key = _normalise_oa_doi(record.get("doi", ""))
                if doi_key:
                    oa_cache[doi_key] = {
                        "cited_by_count": record.get("cited_by_count", 0) or 0,
                        "countries": _extract_countries(record.get("authorships", [])),
                    }
                    fetched_keys.add(doi_key)
            # Mark every DOI in the batch so it is never re-queried
            for d in batch:
                oa_cache.setdefault(d, {"cited_by_count": 0, "countries": ""})
            batch_num = i // _BATCH_SIZE + 1
            print(
                f"  batch {batch_num}/{n_batches}: fetched {len(results)},"
                f" cache size {len(oa_cache)}"
            )
            if batch_num % _CACHE_SAVE_EVERY == 0:
                _save_json_cache(oa_cache_path, oa_cache)
        _save_json_cache(oa_cache_path, oa_cache)
        print(f"[enrich] OpenAlex cache saved → {oa_cache_path.name} ({len(oa_cache)} entries).")
    elif all_candidate_dois:
        print(
            f"[enrich] OpenAlex: all {len(all_candidate_dois)} candidate DOIs already cached"
            " — no API calls needed."
        )
    else:
        print("[enrich] OpenAlex: no DOI candidates found — skipping.")

    # Build enrichment lookup from cache
    enrichment: dict[str, dict] = {
        d: oa_cache[d] for d in all_candidate_dois if d in oa_cache
    }

    # Apply OA enrichment to df
    n_cit_updated = 0
    n_country_updated = 0
    for idx, row in df.iterrows():
        key = row["_bare_doi"]
        if not key or key not in enrichment:
            continue
        patch = enrichment[key]
        if row["cited_by_count"] == 0 and patch["cited_by_count"] > 0:
            df.at[idx, "cited_by_count"] = patch["cited_by_count"]
            n_cit_updated += 1
        existing_country = str(row.get("countries", "") or "").strip()
        if (not existing_country or existing_country == "nan") and patch["countries"]:
            df.at[idx, "countries"] = patch["countries"]
            n_country_updated += 1

    # -----------------------------------------------------------------------
    # Pass 2 — Europe PMC fallback (PMID-based, no-DOI PubMed records only)
    # -----------------------------------------------------------------------
    n_epmc_cit = 0
    epmc_lookup: dict[str, int] = {}
    pmid_map = _load_pmid_map(paths.root)
    if pmid_map:
        no_doi_mask = (
            (df["data_source"] == "pubmed_manual")
            & (df["_bare_doi"].str.len() == 0)
            & (df["cited_by_count"] == 0)
        )
        no_doi_pub = df[no_doi_mask].copy()
        if not no_doi_pub.empty:
            no_doi_pub["_pmid"] = no_doi_pub["title"].apply(
                lambda t: pmid_map.get(_normalise_title(str(t) if pd.notna(t) else ""), "")
            )
            matched = no_doi_pub[no_doi_pub["_pmid"] != ""]
            all_pmids = matched["_pmid"].unique().tolist()
            uncached_pmids = [p for p in all_pmids if p not in epmc_cache]
            cached_pmids = len(all_pmids) - len(uncached_pmids)

            if uncached_pmids:
                print(
                    f"[enrich] Europe PMC: {len(uncached_pmids)} PMIDs to fetch"
                    f" ({cached_pmids} already cached)."
                )
                for i in range(0, len(uncached_pmids), _EPMC_BATCH_SIZE):
                    batch_pmids = uncached_pmids[i: i + _EPMC_BATCH_SIZE]
                    results = _fetch_epmc_batch(batch_pmids)
                    fetched_pmids: set[str] = set()
                    for rec in results:
                        pmid = str(rec.get("pmid", "")).strip()
                        count = int(rec.get("citedByCount", 0) or 0)
                        if pmid:
                            epmc_cache[pmid] = count
                            fetched_pmids.add(pmid)
                    for p in batch_pmids:
                        epmc_cache.setdefault(p, 0)
                    if i + _EPMC_BATCH_SIZE < len(uncached_pmids):
                        time.sleep(0.5)
                _save_json_cache(epmc_cache_path, epmc_cache)
                print(f"[enrich] EPMC cache saved → {epmc_cache_path.name} ({len(epmc_cache)} entries).")
            else:
                print(
                    f"[enrich] Europe PMC: all {len(all_pmids)} PMIDs already cached"
                    " — no API calls needed."
                )

            epmc_lookup = {p: epmc_cache[p] for p in all_pmids if p in epmc_cache}
            for idx, row in matched.iterrows():
                count = epmc_lookup.get(row["_pmid"], 0)
                if count > 0:
                    df.at[idx, "cited_by_count"] = count
                    n_epmc_cit += 1
            print(f"[enrich] Europe PMC: {n_epmc_cit} citations filled.")
        else:
            print("[enrich] Europe PMC: no no-DOI PubMed records need filling — skipping.")
    else:
        print("[enrich] Europe PMC: no PMIDs parsed from manual/pubmed — skipping.")

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    df.drop(columns=["_bare_doi"], inplace=True)
    df.to_csv(paths.corpus_clean_path, index=False)
    print(
        f"[enrich] Done. citations updated: {n_cit_updated + n_epmc_cit}"
        f" (OpenAlex: {n_cit_updated}, EuropePMC: {n_epmc_cit}),"
        f" country fields filled: {n_country_updated}"
    )
    print(f"[enrich] Saved enriched corpus → {paths.corpus_clean_path}")

    # Patch corpus_clustered.csv if it exists
    if paths.corpus_clustered_path.exists():
        dfc = pd.read_csv(paths.corpus_clustered_path)
        dfc["cited_by_count"] = pd.to_numeric(dfc["cited_by_count"], errors="coerce").fillna(0)
        dfc["_bare_doi"] = dfc["doi"].apply(_bare_doi)
        n_cit_c = n_country_c = 0
        for idx, row in dfc.iterrows():
            key = row["_bare_doi"]
            if key and key in enrichment:
                patch = enrichment[key]
                if row["cited_by_count"] == 0 and patch["cited_by_count"] > 0:
                    dfc.at[idx, "cited_by_count"] = patch["cited_by_count"]
                    n_cit_c += 1
                existing_country = str(row.get("countries", "") or "").strip()
                if (not existing_country or existing_country == "nan") and patch["countries"]:
                    dfc.at[idx, "countries"] = patch["countries"]
                    n_country_c += 1
            elif not key and str(row.get("data_source", "")) == "pubmed_manual" and pmid_map:
                norm = _normalise_title(str(row.get("title", "")))
                pmid = pmid_map.get(norm, "")
                if pmid and epmc_lookup.get(pmid, 0) > 0 and row["cited_by_count"] == 0:
                    dfc.at[idx, "cited_by_count"] = epmc_lookup[pmid]
                    n_cit_c += 1
        dfc.drop(columns=["_bare_doi"], inplace=True)
        dfc.to_csv(paths.corpus_clustered_path, index=False)
        print(f"[enrich] corpus_clustered patched: citations={n_cit_c}, countries={n_country_c}")

    return paths.corpus_clean_path
