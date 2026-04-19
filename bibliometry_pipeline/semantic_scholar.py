"""Semantic Scholar API client.

Produces a DataFrame with the same interface as the OpenAlex flatten_records
output so it can be merged with the OpenAlex corpus before relevance scoring.

Columns guaranteed to be present after flatten_records():
    id, doi, title, abstract, publication_year, type, journal, countries,
    primary_topic, is_in_doaj, cited_by_count, keyword_terms, topic_terms,
    open_access (dict-like — stubbed), data_source
"""
from __future__ import annotations

import time
from collections import defaultdict

import pandas as pd
import requests


BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PAGE_SIZE = 100   # S2 API maximum per request
MAX_PER_QUERY = 500   # ceiling per search term (offset-based, max useful ~500)

# Fields fetched from S2 — keep lean to stay within response size limits.
FIELDS = (
    "paperId,"
    "externalIds,"
    "title,"
    "abstract,"
    "year,"
    "citationCount,"
    "venue,"
    "journal,"
    "publicationTypes,"
    "fieldsOfStudy,"
    "s2FieldsOfStudy,"
    "openAccessPdf"
)

# Map S2 publicationTypes → unified type values used in this pipeline.
_TYPE_MAP: dict[str, str] = {
    "JournalArticle": "article",
    "Article": "article",
    "Review": "review",
    "Conference": "article",  # conference == article for bibliometric purposes
}


def fetch_per_query(
    query: str,
    *,
    year_min: int,
    year_max: int,
    api_key: str | None = None,
    min_delay: float = 1.1,
    max_429_retries: int = 3,
) -> list[dict]:
    """Fetch all available results for *query* from Semantic Scholar.

    Paginates with offset until fewer than PAGE_SIZE results are returned or
    MAX_PER_QUERY is reached.  Sleeps *min_delay* between requests to respect
    the unauthenticated rate-limit (1 req/s).  With an API key 0.1 s is safe.

    Note: Semantic Scholar requires a free API key for reliable access.
    Without one the endpoint may return 429 consistently.  Register at
    https://www.semanticscholar.org/product/api and set
    SEMANTIC_SCHOLAR_API_KEY in config.py or the S2_API_KEY env var.

    Args:
        query: Free-text search query.
        year_min: Earliest publication year (inclusive).
        year_max: Latest publication year (inclusive).
        api_key: Optional S2 API key.  Allows up to 10 req/s.
        min_delay: Seconds to wait between paginated requests.
        max_429_retries: How many consecutive 429 responses to tolerate
            before giving up on this query entirely.

    Returns:
        List of raw API result dicts, possibly empty on persistent 429.
    """
    headers: dict[str, str] = {"User-Agent": "bibliometry-unioeste/1.1 (mail@unioeste.br)"}
    if api_key:
        headers["x-api-key"] = api_key
        min_delay = max(min_delay, 0.12)  # be polite even with a key

    records: list[dict] = []
    offset = 0
    consecutive_429 = 0

    while offset < MAX_PER_QUERY:
        params: dict[str, object] = {
            "query": query,
            "fields": FIELDS,
            "limit": PAGE_SIZE,
            "offset": offset,
            "publicationTypes": "JournalArticle,Article,Review",
            "year": f"{year_min}-{year_max}",
        }
        try:
            response = requests.get(BASE_URL, params=params, headers=headers, timeout=60)
            if response.status_code == 429:
                consecutive_429 += 1
                backoff = 15 * consecutive_429
                if consecutive_429 > max_429_retries:
                    print(
                        f"    [S2] {max_429_retries} consecutive 429s for {query!r}; "
                        "skipping query. Set SEMANTIC_SCHOLAR_API_KEY for reliable access."
                    )
                    break
                print(f"    [S2] 429 rate-limit (attempt {consecutive_429}); backing off {backoff}s …")
                time.sleep(backoff)
                continue
            consecutive_429 = 0
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"    [S2] Request error for {query!r} (offset={offset}): {exc}; skipping.")
            break

        payload = response.json()
        batch = payload.get("data", [])
        total = payload.get("total", "?")
        records.extend(batch)
        print(
            f"  [S2] query={query!r} offset={offset}: +{len(batch)} records"
            f"  (S2 total: {total})"
        )
        if len(batch) < PAGE_SIZE:
            break
        offset += len(batch)
        time.sleep(min_delay)

    return records


def fetch_all(
    search_terms: list[str],
    *,
    year_min: int,
    year_max: int,
    api_key: str | None = None,
) -> tuple[dict[str, dict], dict[str, set[str]]]:
    """Fetch records for every search term; deduplicate by S2 paperId.

    If the first term immediately exhausts the 429-retry budget (indicating the
    endpoint is fully blocked without an API key), the function returns empty
    results immediately rather than hammering all search terms.

    Args:
        search_terms: List of search term strings (same as RESEARCH_SEARCH_TERMS).
        year_min: Earliest publication year.
        year_max: Latest publication year.
        api_key: Optional S2 API key.

    Returns:
        (union_records, matched_query_terms) where:
          - union_records: ``{"s2:<paperId>": raw_record}``
          - matched_query_terms: ``{"s2:<paperId>": set(search_terms)}``
    """
    union_records: dict[str, dict] = {}
    matched_query_terms: dict[str, set[str]] = defaultdict(set)
    fully_blocked = False

    for i, term in enumerate(search_terms):
        if fully_blocked:
            break
        batch = fetch_per_query(term, year_min=year_min, year_max=year_max, api_key=api_key)
        # If the very first term returns nothing AND we had no API key,
        # assume the endpoint is rate-blocked and skip remaining terms.
        if i == 0 and not batch and not api_key:
            print(
                "  [S2] First query returned no results without an API key; "
                "skipping remaining S2 queries.\n"
                "  → Register at https://www.semanticscholar.org/product/api "
                "and set SEMANTIC_SCHOLAR_API_KEY in config.py."
            )
            fully_blocked = True
            break
        for record in batch:
            pid = record.get("paperId")
            if not pid:
                continue
            uid = f"s2:{pid}"
            matched_query_terms[uid].add(term)
            union_records[uid] = record  # last write wins (same record)

    return dict(union_records), dict(matched_query_terms)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _bare_doi(doi_value: object) -> str:
    """Return a bare DOI string (no URL prefix) in lower case, or empty string."""
    if not isinstance(doi_value, str) or not doi_value:
        return ""
    doi = doi_value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
    return doi.lower()


def _map_type(publication_types: object) -> str:
    if not isinstance(publication_types, list):
        return "article"
    for pt in publication_types:
        mapped = _TYPE_MAP.get(pt, "")
        if mapped:
            return mapped
    return "article"


def _extract_journal(record: dict) -> str:
    journal = record.get("journal")
    if isinstance(journal, dict) and journal.get("name"):
        return str(journal["name"])
    venue = record.get("venue")
    if isinstance(venue, str) and venue:
        return venue
    return ""


def _extract_keyword_terms(record: dict) -> str:
    """Use fieldsOfStudy as keyword proxies (broad subject labels)."""
    fos = record.get("fieldsOfStudy")
    if not isinstance(fos, list):
        return ""
    return " | ".join(str(f) for f in fos if f)


def _extract_topic_terms(record: dict) -> str:
    """Use s2FieldsOfStudy category+source labels as topic proxies."""
    s2fos = record.get("s2FieldsOfStudy")
    if not isinstance(s2fos, list):
        return ""
    seen: set[str] = set()
    parts: list[str] = []
    for entry in s2fos:
        if not isinstance(entry, dict):
            continue
        cat = entry.get("category", "")
        if cat and cat not in seen:
            seen.add(cat)
            parts.append(cat)
    return " | ".join(parts[:3])


def _extract_primary_topic(record: dict) -> str:
    """Take the first s2FieldsOfStudy category as the primary topic string."""
    s2fos = record.get("s2FieldsOfStudy")
    if not isinstance(s2fos, list) or not s2fos:
        return ""
    first = s2fos[0]
    if isinstance(first, dict):
        return str(first.get("category", ""))
    return ""


def _is_open_access(record: dict) -> bool:
    return bool(record.get("openAccessPdf"))


# ---------------------------------------------------------------------------
# Public flatten function
# ---------------------------------------------------------------------------

def flatten_records(
    union_records: dict[str, dict],
    matched_query_terms: dict[str, set[str]],
) -> pd.DataFrame:
    """Convert raw S2 records to the unified pipeline DataFrame format.

    Produces the same column set as ``openalex.flatten_records`` plus the
    ``matched_search_terms``, ``matched_search_term_count``, and
    ``data_source`` columns that fetch.py needs before the merge step.

    Args:
        union_records: ``{"s2:<paperId>": raw_record}`` from fetch_all().
        matched_query_terms: ``{"s2:<paperId>": set(terms)}`` from fetch_all().

    Returns:
        DataFrame (may be empty if no records).
    """
    if not union_records:
        return pd.DataFrame()

    rows: list[dict] = []
    for uid, rec in union_records.items():
        ext_ids = rec.get("externalIds") or {}
        bare_doi = _bare_doi(ext_ids.get("DOI", ""))
        terms = matched_query_terms.get(uid, set())
        rows.append({
            "id": uid,
            "doi": bare_doi,
            "title": rec.get("title") or "",
            "abstract": rec.get("abstract") or "",
            "publication_year": rec.get("year"),
            "type": _map_type(rec.get("publicationTypes")),
            "journal": _extract_journal(rec),
            "countries": "",   # not available from S2 search endpoint
            "primary_topic": _extract_primary_topic(rec),
            "is_in_doaj": False,
            "cited_by_count": rec.get("citationCount") or 0,
            "keyword_terms": _extract_keyword_terms(rec),
            "topic_terms": _extract_topic_terms(rec),
            "open_access": {"is_oa": _is_open_access(rec)},
            "data_source": "semantic_scholar",
            "matched_search_terms": "|".join(sorted(terms)),
            "matched_search_term_count": len(terms),
        })

    df = pd.DataFrame(rows)
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).astype(int)
    return df
