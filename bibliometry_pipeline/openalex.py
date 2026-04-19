from __future__ import annotations

import time
from collections import Counter

import pandas as pd
import requests


BASE_URL = "https://api.openalex.org/works"
HEADERS = {"User-Agent": "bibliometry-unioeste/1.1 (mail@unioeste.br)"}
SELECT = (
    "id,doi,title,publication_year,type,authorships,primary_location,"
    "cited_by_count,abstract_inverted_index,keywords,topics,open_access"
)

_OA_MAX_RETRIES = 4
_OA_RETRY_BACKOFF = [10, 20, 40, 60]   # seconds to wait on successive 429s


def fetch_all(filter_str: str, *, search_term: str | None = None) -> list[dict]:
    records: list[dict] = []
    cursor = "*"
    page = 0
    while cursor:
        page += 1
        params = {
            "filter": filter_str,
            "select": SELECT,
            "cursor": cursor,
            "per-page": 200,
        }
        if search_term:
            params["search"] = search_term

        response = None
        for attempt in range(_OA_MAX_RETRIES):
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=60)
            if response.status_code == 429:
                wait = _OA_RETRY_BACKOFF[min(attempt, len(_OA_RETRY_BACKOFF) - 1)]
                print(f"    [OpenAlex] 429 rate-limit (attempt {attempt + 1}); backing off {wait}s …")
                time.sleep(wait)
                continue
            break

        response.raise_for_status()
        payload = response.json()
        batch = payload.get("results", [])
        records.extend(batch)
        cursor = payload.get("meta", {}).get("next_cursor")
        total = payload.get("meta", {}).get("count", "?")
        label = search_term or "(no search term)"
        print(f"  query={label!r} page {page}: +{len(batch)} records  (OpenAlex total: {total})")
        if not batch:
            break
    return records


def reconstruct_abstract(inv: dict) -> str:
    if not inv or not isinstance(inv, dict):
        return ""
    positions = {}
    for word, locs in inv.items():
        for pos in locs:
            positions[pos] = word
    return " ".join(positions[idx] for idx in sorted(positions))


def extract_journal(primary_loc) -> str:
    if not isinstance(primary_loc, dict):
        return ""
    return (primary_loc.get("source") or {}).get("display_name", "")


def extract_countries(authorships) -> str:
    if not isinstance(authorships, list):
        return ""
    codes = set()
    for authorship in authorships:
        for inst in (authorship.get("institutions") or []):
            country = inst.get("country_code", "")
            if country:
                codes.add(country)
    return "|".join(sorted(codes))


def extract_primary_topic(topics) -> str:
    if not topics or not isinstance(topics, list):
        return ""
    first = topics[0] if topics else {}
    return first.get("display_name", "") if isinstance(first, dict) else ""


def extract_is_in_doaj(primary_loc) -> bool:
    if not isinstance(primary_loc, dict):
        return False
    return bool((primary_loc.get("source") or {}).get("is_in_doaj", False))


def flatten_records(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df["abstract"] = df.get(
        "abstract_inverted_index", pd.Series([None] * len(df))
    ).apply(lambda value: reconstruct_abstract(value) if value else "")
    df["journal"] = df.get(
        "primary_location", pd.Series([None] * len(df))
    ).apply(extract_journal)
    df["countries"] = df.get(
        "authorships", pd.Series([None] * len(df))
    ).apply(extract_countries)
    df["primary_topic"] = df.get(
        "topics", pd.Series([None] * len(df))
    ).apply(extract_primary_topic)
    df["is_in_doaj"] = df.get(
        "primary_location", pd.Series([None] * len(df))
    ).apply(extract_is_in_doaj)
    return df


def summarise_countries(df: pd.DataFrame, *, top_n: int = 10) -> list[tuple[str, int]]:
    countries = Counter()
    for value in df["countries"].dropna():
        for code in str(value).split("|"):
            code = code.strip()
            if code:
                countries[code] += 1
    return countries.most_common(top_n)