from __future__ import annotations

import time
from collections import defaultdict

import pandas as pd
import requests


BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PAGE_SIZE = 100
MAX_RESULTS_PER_QUERY = 150


def fetch_per_query(
    query: str,
    *,
    max_results: int = MAX_RESULTS_PER_QUERY,
    min_delay: float = 0.35,
) -> list[dict]:
    records: list[dict] = []
    page = 1

    while len(records) < max_results:
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": PAGE_SIZE,
            "page": page,
        }
        try:
            response = requests.get(BASE_URL, params=params, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"  [EuropePMC] Request error (page={page}): {exc}; aborting query.")
            break

        payload = response.json()
        results = payload.get("resultList", {}).get("result", [])
        if isinstance(results, dict):
            results = [results]
        hit_count_raw = payload.get("hitCount", 0)
        hit_count = int(hit_count_raw) if str(hit_count_raw).isdigit() else 0
        batch = list(results)
        records.extend(batch)
        print(f"  [EuropePMC] page={page}: +{len(batch)} records  (Europe PMC total: {hit_count})")

        if hit_count > max_results:
            print(
                f"  [EuropePMC] Query returned {hit_count} total results;"
                f" capped at {max_results} to protect API budget."
            )

        if len(batch) < PAGE_SIZE or len(records) >= min(hit_count, max_results):
            break

        page += 1
        time.sleep(min_delay)

    return records[:max_results]


def fetch_all(
    queries: list[str],
    *,
    max_results_per_query: int = MAX_RESULTS_PER_QUERY,
) -> tuple[dict[str, dict], dict[str, set[str]]]:
    union_records: dict[str, dict] = {}
    matched_query_terms: dict[str, set[str]] = defaultdict(set)

    for i, query in enumerate(queries):
        label = f"Q{i + 1}"
        print(f"\n  [EuropePMC] {label}: {query[:80]}{'…' if len(query) > 80 else ''}")
        batch = fetch_per_query(query, max_results=max_results_per_query)
        if i == 0 and not batch:
            print("  [EuropePMC] First query returned no records; aborting remaining queries.")
            break

        for record in batch:
            uid = _record_uid(record)
            matched_query_terms[uid].add(label)
            union_records[uid] = record

    return dict(union_records), dict(matched_query_terms)


def _record_uid(record: dict) -> str:
    doi = _bare_doi(record.get("doi", ""))
    if doi:
        return f"europepmc:doi:{doi}"
    source = str(record.get("source", "epmc") or "epmc").lower()
    identifier = str(record.get("id", "") or "").strip()
    if identifier:
        return f"europepmc:{source}:{identifier}"
    title = str(record.get("title", "") or "").lower().strip()
    return f"europepmc:title:{title[:80]}"


def _bare_doi(doi_value: object) -> str:
    if not isinstance(doi_value, str) or not doi_value:
        return ""
    doi = doi_value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _map_type(value: object) -> str:
    text = str(value or "").lower()
    if "review" in text:
        return "review"
    return "article"


def _extract_keywords(record: dict) -> str:
    raw = record.get("keywordList")
    if isinstance(raw, dict):
        raw = raw.get("keyword")
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        return ""

    keywords = []
    seen = set()
    for item in values:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            keywords.append(text)
    return " | ".join(keywords[:8])


def flatten_records(
    union_records: dict[str, dict],
    matched_query_terms: dict[str, set[str]],
) -> pd.DataFrame:
    if not union_records:
        return pd.DataFrame()

    rows: list[dict] = []
    for uid, rec in union_records.items():
        terms = matched_query_terms.get(uid, set())
        rows.append(
            {
                "id": uid,
                "doi": _bare_doi(rec.get("doi", "")),
                "title": rec.get("title") or "",
                "abstract": rec.get("abstractText") or "",
                "publication_year": rec.get("pubYear"),
                "type": _map_type(rec.get("pubType")),
                "journal": rec.get("journalTitle") or "",
                "countries": "",
                "primary_topic": "",
                "is_in_doaj": False,
                "cited_by_count": rec.get("citedByCount") or 0,
                "keyword_terms": _extract_keywords(rec),
                "topic_terms": "",
                "open_access": {"is_oa": str(rec.get("isOpenAccess", "N")).upper() == "Y"},
                "data_source": "europe_pmc",
                "matched_search_terms": "|".join(sorted(terms)),
                "matched_search_term_count": len(terms),
            }
        )

    df = pd.DataFrame(rows)
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).astype(int)
    return df