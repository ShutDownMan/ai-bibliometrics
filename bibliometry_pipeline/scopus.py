"""Elsevier Scopus Search API client.

Produces a DataFrame with the same interface as openalex.flatten_records /
semantic_scholar.flatten_records so it can be merged with existing candidates
before relevance scoring.

Rate limits (institutional key via CAFe/CAPES):
    - Typically ~20,000 requests/week on the Scopus Search API.
    - Service-level result-page limits vary by key.
    - The client attempts 200/page first, then falls back to 25/page when
        Elsevier rejects the larger page size.

Access note:
  - If accessing from outside the institution network, you may need BOTH
    SCOPUS_API_KEY and SCOPUS_INST_TOKEN (X-ELS-Insttoken).
  - From the institution network, the API key alone is sufficient.
  - Keys are managed at https://dev.elsevier.com/ (API Key Management).

Columns guaranteed after flatten_records():
    id, doi, title, abstract, publication_year, type, journal, countries,
    primary_topic, is_in_doaj, cited_by_count, keyword_terms, topic_terms,
    open_access, data_source, matched_search_terms, matched_search_term_count
"""
from __future__ import annotations

import time
from collections import defaultdict

import pandas as pd
import requests


BASE_URL = "https://api.elsevier.com/content/search/scopus"

# Attempt 200 results per request first to reduce request volume.
# Some Elsevier service levels reject that count and only allow 25,
# so fetch_per_query() automatically falls back when needed.
PAGE_SIZE = 200
SAFE_PAGE_SIZE = 25

# Hard ceiling on results per query.  Keep this conservative because the
# current service level only exposes search metadata, not abstracts, so
# very deep pagination has poor downstream value under the strict abstract
# filter used by fetch.py.
MAX_RESULTS_PER_QUERY = 150

# Fields to retrieve with each result from the Search API.
# Under the current entitlement, abstracts are not available here;
# they would require per-record Abstract API calls.
_FIELDS = (
    "dc:identifier,eid,dc:title,prism:doi,"
    "prism:publicationName,prism:coverDate,"
    "citedby-count,subtypeDescription,"
    "authkeywords,affiliation"
)

# Scopus subtypeDescription → unified pipeline type values
_TYPE_MAP: dict[str, str] = {
    "Article": "article",
    "Article in Press": "article",
    "Review": "review",
    "Conference Paper": "article",
    "Conference Review": "review",
    "Short Survey": "review",
}

# Scopus country names → ISO 2-letter codes for common research nations.
# Unmapped countries are passed through as-is (lowercase, spaces replaced with _).
_COUNTRY_CODES: dict[str, str] = {
    "United States": "US", "United Kingdom": "GB", "China": "CN",
    "Germany": "DE", "Australia": "AU", "Canada": "CA", "France": "FR",
    "Spain": "ES", "Italy": "IT", "Netherlands": "NL", "Brazil": "BR",
    "India": "IN", "Japan": "JP", "South Korea": "KR", "Portugal": "PT",
    "Turkey": "TR", "Sweden": "SE", "Switzerland": "CH", "Poland": "PL",
    "Norway": "NO", "Ireland": "IE", "New Zealand": "NZ", "Belgium": "BE",
    "Taiwan": "TW", "Malaysia": "MY", "Indonesia": "ID", "Saudi Arabia": "SA",
    "United Arab Emirates": "AE", "Iran": "IR", "Pakistan": "PK",
    "South Africa": "ZA", "Mexico": "MX", "Argentina": "AR", "Colombia": "CO",
    "Chile": "CL", "Egypt": "EG", "Nigeria": "NG",
}


def fetch_per_query(
    query: str,
    *,
    api_key: str,
    inst_token: str | None = None,
    max_results: int = MAX_RESULTS_PER_QUERY,
    min_delay: float = 1.1,
    max_error_retries: int = 2,
) -> list[dict]:
    """Fetch all results for a single Scopus Boolean *query*, paginated.

    Args:
        query: Scopus Boolean query string (e.g. TITLE-ABS-KEY(...) AND ...).
        api_key: Elsevier API key (X-ELS-APIKey).
        inst_token: Optional institution token (X-ELS-Insttoken).  Required
            when accessing from outside the institution's IP range.
        max_results: Maximum total results to retrieve for this query.
        min_delay: Minimum seconds to sleep between paginated requests.
        max_error_retries: Number of retries on non-auth HTTP errors (5xx).

    Returns:
        List of raw result dicts from the Scopus JSON response.
    """
    headers: dict[str, str] = {
        "Accept": "application/json",
        "X-ELS-APIKey": api_key,
        "User-Agent": "bibliometry-unioeste/1.1 (mail@unioeste.br)",
    }
    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token

    records: list[dict] = []
    start = 0
    page_size = PAGE_SIZE
    consecutive_errors = 0

    while start < max_results:
        params: dict[str, object] = {
            "query": query,
            "field": _FIELDS,
            "count": page_size,
            "start": start,
            "sort": "-coverDate",   # most recent first
        }
        try:
            response = requests.get(BASE_URL, params=params, headers=headers, timeout=60)

            if response.status_code == 400:
                status_text = ""
                try:
                    status_text = str(
                        response.json().get("service-error", {}).get("status", {}).get("statusText", "")
                    )
                except Exception:
                    status_text = response.text[:240]

                if page_size > SAFE_PAGE_SIZE and "Exceeds the maximum number allowed for the service level" in status_text:
                    print(
                        f"  [Scopus] count={page_size} exceeds this key's service level; "
                        f"retrying with count={SAFE_PAGE_SIZE}."
                    )
                    page_size = SAFE_PAGE_SIZE
                    continue

                print(f"  [Scopus] 400 Bad Request — {status_text}")
                break

            if response.status_code == 401:
                print(
                    "  [Scopus] 401 Unauthorized — check SCOPUS_API_KEY in config.py or\n"
                    "  the query uses fields/views that exceed your subscription entitlement.\n"
                    "  Keys are managed at https://dev.elsevier.com/"
                )
                break

            if response.status_code == 403:
                print(
                    "  [Scopus] 403 Forbidden — access denied.\n"
                    "  If accessing from outside the institution network, set\n"
                    "  SCOPUS_INST_TOKEN in config.py (X-ELS-Insttoken header)."
                )
                break

            if response.status_code == 429:
                print(
                    "  [Scopus] 429 Quota Exceeded — weekly API budget exhausted.\n"
                    "  Remaining Scopus queries will be skipped."
                )
                return records   # return what we have; no point retrying other queries

            if response.status_code >= 500:
                consecutive_errors += 1
                if consecutive_errors > max_error_retries:
                    print(f"  [Scopus] {max_error_retries} consecutive 5xx errors; aborting query.")
                    break
                backoff = 5 * consecutive_errors
                print(f"  [Scopus] HTTP {response.status_code}; retry {consecutive_errors}/{max_error_retries} in {backoff}s …")
                time.sleep(backoff)
                continue

            consecutive_errors = 0
            response.raise_for_status()

        except requests.RequestException as exc:
            print(f"  [Scopus] Request error (start={start}): {exc}; aborting query.")
            break

        try:
            payload = response.json()
            results_container = payload.get("search-results", {})
            batch = results_container.get("entry", [])
            total_str = results_container.get("opensearch:totalResults", "0")
            total = int(total_str) if str(total_str).isdigit() else 0
        except Exception as exc:
            print(f"  [Scopus] JSON parse error: {exc}; aborting query.")
            break

        # Detect error payload (some auth errors return 200 with error content)
        if batch and isinstance(batch[0], dict) and "error" in batch[0]:
            print(f"  [Scopus] API error in response: {batch[0]['error']!r}")
            break

        records.extend(batch)
        print(
            f"  [Scopus] start={start}: +{len(batch)} records"
            f"  (Scopus total: {total})"
        )

        if total > max_results:
            print(
                f"  [Scopus] Query returned {total} total results;"
                f" capped at {max_results} to protect API budget."
            )

        if len(batch) < page_size or start + len(batch) >= min(total, max_results):
            break

        start += len(batch)
        time.sleep(min_delay)

    return records


def fetch_all(
    queries: list[str],
    *,
    api_key: str,
    inst_token: str | None = None,
    max_results_per_query: int = MAX_RESULTS_PER_QUERY,
) -> tuple[dict[str, dict], dict[str, set[str]]]:
    """Fetch records for every Scopus query string; deduplicate by Scopus EID.

    Deduplication uses the `eid` field (stable Scopus identifier).  Where an
    EID is absent, falls back to DOI, then title normalisation.

    Args:
        queries: List of Scopus Boolean query strings from SCOPUS_QUERIES.
        api_key: Elsevier API key.
        inst_token: Optional institution token.
        max_results_per_query: Per-query result cap.

    Returns:
        (union_records, matched_query_terms) where keys are "scopus:<eid>".
    """
    union_records: dict[str, dict] = {}
    matched_query_terms: dict[str, set[str]] = defaultdict(set)
    for i, query in enumerate(queries):
        label = f"Q{i + 1}"
        print(f"\n  [Scopus] {label}: {query[:80]}{'…' if len(query) > 80 else ''}")
        batch = fetch_per_query(
            query,
            api_key=api_key,
            inst_token=inst_token,
            max_results=max_results_per_query,
        )
        # If the very first query returned 0 records due to auth failure, abort early
        if i == 0 and not batch:
            print("  [Scopus] First query returned no records; aborting remaining queries.")
            break

        for record in batch:
            eid = record.get("eid", "")
            uid = f"scopus:{eid}" if eid else f"scopus:doi:{_bare_doi(record.get('prism:doi', ''))}"
            if not uid or uid == "scopus:doi:":
                # Last resort: use normalised title as key
                uid = f"scopus:title:{record.get('dc:title', '')[:60].lower().strip()}"
            matched_query_terms[uid].add(label)
            union_records[uid] = record

    return dict(union_records), dict(matched_query_terms)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _bare_doi(doi_value: object) -> str:
    """Return a bare DOI string in lower case (no URL prefix), or empty string."""
    if not isinstance(doi_value, str) or not doi_value:
        return ""
    doi = doi_value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _map_type(subtype_description: object) -> str:
    return _TYPE_MAP.get(str(subtype_description or ""), "article")


def _extract_year(cover_date: object) -> int | None:
    """Extract year from Scopus coverDate string ("YYYY-MM-DD")."""
    if not isinstance(cover_date, str) or len(cover_date) < 4:
        return None
    try:
        return int(cover_date[:4])
    except ValueError:
        return None


def _extract_keywords(record: dict) -> str:
    """Reconstruct author-keyword string from authkeywords field.

    Scopus returns `authkeywords` as a pipe-separated string like
    "machine learning | peer review | academic integrity".
    """
    raw = record.get("authkeywords")
    if not isinstance(raw, str) or not raw:
        return ""
    # Normalise separators: some records use "; " or " | "
    parts = [kw.strip() for kw in raw.replace(" | ", "|").replace("; ", "|").split("|") if kw.strip()]
    return " | ".join(parts[:8])


def _extract_countries(affiliations: object) -> str:
    """Extract ISO country codes from Scopus affiliation list."""
    if not isinstance(affiliations, list):
        if isinstance(affiliations, dict):
            affiliations = [affiliations]
        else:
            return ""
    codes: set[str] = set()
    for aff in affiliations:
        if not isinstance(aff, dict):
            continue
        country_name = aff.get("affiliation-country", "")
        if not country_name:
            continue
        code = _COUNTRY_CODES.get(country_name, country_name[:2].upper())
        codes.add(code)
    return "|".join(sorted(codes))


# ---------------------------------------------------------------------------
# Public flatten function
# ---------------------------------------------------------------------------

def flatten_records(
    union_records: dict[str, dict],
    matched_query_terms: dict[str, set[str]],
) -> pd.DataFrame:
    """Convert raw Scopus results to the unified pipeline DataFrame format.

    Args:
        union_records: ``{"scopus:<eid>": raw_record}`` from fetch_all().
        matched_query_terms: ``{"scopus:<eid>": set(query_labels)}`` from fetch_all().

    Returns:
        DataFrame (may be empty if no records).
    """
    if not union_records:
        return pd.DataFrame()

    rows: list[dict] = []
    for uid, rec in union_records.items():
        bare_doi = _bare_doi(rec.get("prism:doi", ""))
        terms = matched_query_terms.get(uid, set())
        # Search API results do not expose abstract text at the current service level.
        # Leave this empty unless a later enrichment step populates it.
        abstract = rec.get("abstract") or rec.get("dc:description") or ""
        rows.append({
            "id": uid,
            "doi": bare_doi,
            "title": rec.get("dc:title") or "",
            "abstract": abstract,
            "publication_year": _extract_year(rec.get("prism:coverDate")),
            "type": _map_type(rec.get("subtypeDescription")),
            "journal": rec.get("prism:publicationName") or "",
            "countries": _extract_countries(rec.get("affiliation")),
            "primary_topic": "",    # Scopus has subject area codes, not topic labels
            "is_in_doaj": False,
            "cited_by_count": int(rec.get("citedby-count") or 0),
            "keyword_terms": _extract_keywords(rec),
            "topic_terms": "",
            "open_access": {},
            "data_source": "scopus",
            "matched_search_terms": "|".join(sorted(terms)),
            "matched_search_term_count": len(terms),
        })

    df = pd.DataFrame(rows)
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).astype(int)
    return df
