from __future__ import annotations

import time
from html import unescape

import pandas as pd
import requests

from .utils import clean_html_text


EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
CROSSREF_WORKS_URL = "https://api.crossref.org/works/"


def _bare_doi(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _normalise_abstract(text: object) -> str:
    value = clean_html_text(unescape(str(text or "")))
    return value.strip()


def _fetch_europe_pmc_abstract(session: requests.Session, doi: str) -> str:
    response = session.get(
        EUROPE_PMC_SEARCH_URL,
        params={
            "query": f"DOI:{doi}",
            "format": "json",
            "pageSize": 1,
            "resultType": "core",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("resultList", {}).get("result", [])
    if isinstance(results, dict):
        results = [results]
    if not results:
        return ""
    return _normalise_abstract(results[0].get("abstractText", ""))


def _fetch_crossref_abstract(session: requests.Session, doi: str) -> str:
    response = session.get(f"{CROSSREF_WORKS_URL}{requests.utils.quote(doi, safe='')}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    return _normalise_abstract((payload.get("message") or {}).get("abstract", ""))


def backfill_missing_abstracts(
    frame: pd.DataFrame,
    *,
    max_records: int,
    min_abstract_length: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    work = frame.copy()
    if "abstract" not in work.columns or "doi" not in work.columns or max_records <= 0:
        return work, {"attempted": 0, "filled": 0, "filled_europe_pmc": 0, "filled_crossref": 0}

    needs_backfill = work["abstract"].fillna("").str.len() < min_abstract_length
    has_doi = work["doi"].fillna("").astype(str).str.strip() != ""
    candidate_index = list(work[needs_backfill & has_doi].index[:max_records])
    if not candidate_index:
        return work, {"attempted": 0, "filled": 0, "filled_europe_pmc": 0, "filled_crossref": 0}

    session = requests.Session()
    session.headers.update({"User-Agent": "bibliometry-unioeste/1.1 (mail@unioeste.br)"})
    doi_cache: dict[str, tuple[str, str]] = {}
    stats = {"attempted": 0, "filled": 0, "filled_europe_pmc": 0, "filled_crossref": 0}

    for row_index in candidate_index:
        doi = _bare_doi(work.at[row_index, "doi"])
        if not doi:
            continue

        stats["attempted"] += 1
        if doi not in doi_cache:
            abstract = ""
            provider = ""
            try:
                abstract = _fetch_europe_pmc_abstract(session, doi)
                if abstract:
                    provider = "europe_pmc"
            except requests.RequestException:
                abstract = ""

            if not abstract:
                try:
                    abstract = _fetch_crossref_abstract(session, doi)
                    if abstract:
                        provider = "crossref"
                except requests.RequestException:
                    abstract = ""

            doi_cache[doi] = (abstract, provider)
            time.sleep(0.2)

        abstract, provider = doi_cache[doi]
        if abstract and len(abstract) >= min_abstract_length:
            work.at[row_index, "abstract"] = abstract
            stats["filled"] += 1
            if provider == "europe_pmc":
                stats["filled_europe_pmc"] += 1
            elif provider == "crossref":
                stats["filled_crossref"] += 1

    return work, stats