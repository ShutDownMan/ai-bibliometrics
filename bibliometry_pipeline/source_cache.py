from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from .config import SOURCE_CACHE_DIRNAME, SOURCE_CACHE_ENABLED
from .utils import clean_html_text, read_json, write_json


SOURCE_FRAME_COLUMNS = [
    "id",
    "doi",
    "title",
    "abstract",
    "publication_year",
    "type",
    "journal",
    "authors",
    "authorships",
    "countries",
    "primary_topic",
    "is_in_doaj",
    "cited_by_count",
    "keyword_terms",
    "topic_terms",
    "open_access",
    "data_source",
    "matched_search_terms",
    "matched_search_term_count",
]


def source_cache_enabled() -> bool:
    disable_cache = os.environ.get("BIBLIOMETRY_DISABLE_SOURCE_CACHE", "").strip().lower()
    if disable_cache in {"1", "true", "yes", "on"}:
        return False
    return bool(SOURCE_CACHE_ENABLED)


def _cache_dir(root: Path) -> Path:
    return root / SOURCE_CACHE_DIRNAME


def _fingerprint(source: str, key_payload: dict[str, object]) -> str:
    payload = json.dumps(
        {"source": source, "payload": key_payload},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_paths(root: Path, source: str, key_payload: dict[str, object]) -> tuple[Path, Path, str]:
    fingerprint = _fingerprint(source, key_payload)
    source_dir = _cache_dir(root) / source
    return source_dir / f"{fingerprint}.csv", source_dir / f"{fingerprint}.json", fingerprint


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in {"", "0", "false", "no", "off", "nan", "none"}:
        return False
    if text in {"1", "true", "yes", "on"}:
        return True
    return bool(value)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _normalise_open_access(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def normalise_source_frame(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    defaults = {
        "id": "",
        "doi": "",
        "title": "",
        "abstract": "",
        "publication_year": pd.NA,
        "type": "",
        "journal": "",
        "authors": "",
        "authorships": "",
        "countries": "",
        "primary_topic": "",
        "is_in_doaj": False,
        "cited_by_count": 0,
        "keyword_terms": "",
        "topic_terms": "",
        "open_access": "",
        "data_source": source,
        "matched_search_terms": "",
        "matched_search_term_count": 0,
    }

    work = frame.copy()
    for column, default in defaults.items():
        if column not in work.columns:
            work[column] = default

    for column in (
        "id",
        "doi",
        "type",
        "journal",
        "authors",
        "authorships",
        "countries",
        "primary_topic",
        "keyword_terms",
        "topic_terms",
        "matched_search_terms",
        "data_source",
    ):
        work[column] = work[column].apply(_as_text)

    work["title"] = work["title"].apply(lambda value: clean_html_text(_as_text(value)))
    work["abstract"] = work["abstract"].apply(lambda value: clean_html_text(_as_text(value)))
    work["publication_year"] = pd.to_numeric(work["publication_year"], errors="coerce")
    work["cited_by_count"] = pd.to_numeric(work["cited_by_count"], errors="coerce").fillna(0).astype(int)
    work["matched_search_term_count"] = pd.to_numeric(
        work["matched_search_term_count"], errors="coerce"
    ).fillna(0).astype(int)
    work["is_in_doaj"] = work["is_in_doaj"].apply(_as_bool)
    work["open_access"] = work["open_access"].apply(_normalise_open_access)
    work["data_source"] = work["data_source"].replace("", source).fillna(source)

    return work[SOURCE_FRAME_COLUMNS].copy()


def load_source_cache(
    root: Path,
    source: str,
    key_payload: dict[str, object],
) -> tuple[pd.DataFrame | None, dict[str, object]]:
    if not source_cache_enabled():
        return None, {}

    csv_path, meta_path, fingerprint = _cache_paths(root, source, key_payload)
    if not csv_path.exists() or not meta_path.exists():
        return None, {}

    metadata = read_json(meta_path, {})
    if metadata.get("fingerprint") != fingerprint:
        return None, {}

    try:
        frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    except Exception:
        return None, {}
    return normalise_source_frame(frame, source), metadata


def save_source_cache(
    root: Path,
    source: str,
    key_payload: dict[str, object],
    frame: pd.DataFrame,
    *,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    if not source_cache_enabled():
        return {}

    csv_path, meta_path, fingerprint = _cache_paths(root, source, key_payload)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    normalised = normalise_source_frame(frame, source)
    normalised.to_csv(csv_path, index=False)

    payload = {
        "source": source,
        "fingerprint": fingerprint,
        "n_rows": len(normalised),
    }
    if metadata:
        payload.update(metadata)
    write_json(meta_path, payload)
    return payload