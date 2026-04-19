from __future__ import annotations

import pandas as pd

from .config import FETCH_CLEAN_TOPIC_OVERRIDE, OFFTOPIC_PRIMARY_TOPIC_RE, RETRACTED_TITLE_RE, YEAR_MAX, YEAR_MIN
from .paths import RunPaths, ensure_run_dirs
from .utils import clean_html_text, read_json, write_json


def run(paths: RunPaths) -> pd.DataFrame:
    ensure_run_dirs(paths)

    df = pd.read_csv(paths.corpus_fetch_path)
    log = read_json(paths.fetch_log_path, default={})

    print("=" * 68)
    print("STEP 2 — CLEAN / DEDUP / HYGIENE")
    print("=" * 68)
    print(f"  Loaded candidates: {len(df)}")

    df["title"] = df["title"].apply(clean_html_text)
    df["abstract"] = df["abstract"].apply(clean_html_text)

    has_doi = (
        df["doi"].notna()
        & (df["doi"].astype(str).str.strip() != "")
        & (df["doi"].astype(str).str.strip().str.lower() != "nan")
    )
    before = len(df)
    with_doi = df[has_doi].drop_duplicates(subset="doi", keep="first")
    without_doi = df[~has_doi]
    df = pd.concat([with_doi, without_doi], ignore_index=True)
    removed_doi = before - len(df)

    before = len(df)
    df["_title_norm"] = df["title"].astype(str).str.lower().str.strip()
    df = df.drop_duplicates(subset="_title_norm", keep="first").drop(columns=["_title_norm"])
    removed_title = before - len(df)

    before = len(df)
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")
    df = df[df["publication_year"].between(YEAR_MIN, YEAR_MAX, inclusive="both")]
    removed_year = before - len(df)

    before = len(df)
    retracted_mask = df["title"].str.contains(RETRACTED_TITLE_RE, na=False)
    df = df[~retracted_mask].copy()
    removed_retracted = before - len(df)

    before = len(df)
    offtopic_topic_mask = df["primary_topic"].astype(str).str.contains(OFFTOPIC_PRIMARY_TOPIC_RE, na=False)
    strong_scope_mask = pd.Series(False, index=df.index)
    if "scope_positive_title_hits" in df.columns:
        strong_scope_mask |= df["scope_positive_title_hits"].fillna("").astype(str).str.len() > 0
    if "relevance_index" in df.columns:
        strong_scope_mask |= pd.to_numeric(df["relevance_index"], errors="coerce").fillna(0) >= FETCH_CLEAN_TOPIC_OVERRIDE
    offtopic_topic_mask &= ~strong_scope_mask
    df = df[~offtopic_topic_mask].copy()
    removed_topic = before - len(df)

    print(f"  removed DOI duplicates      : {removed_doi}")
    print(f"  removed title duplicates    : {removed_title}")
    print(f"  removed out-of-range years  : {removed_year}")
    print(f"  removed retracted papers    : {removed_retracted}")
    print(f"  removed off-topic topics    : {removed_topic}")
    print(f"  final clean corpus          : {len(df)}")

    df.to_csv(paths.corpus_clean_path, index=False)

    log.update({
        "n_identified": log.get("n_identified_unique", len(df) + removed_doi + removed_title + removed_year + removed_retracted + removed_topic),
        "n_excluded_doi_dup": removed_doi,
        "n_excluded_title_dup": removed_title,
        "n_excluded_year": removed_year,
        "n_excluded_retracted": removed_retracted,
        "n_excluded_topic": removed_topic,
        "n_final_clean": len(df),
    })
    write_json(paths.fetch_log_path, log)
    print(f"\nSaved → {paths.corpus_clean_path}")
    print(f"Updated → {paths.fetch_log_path}")
    return df