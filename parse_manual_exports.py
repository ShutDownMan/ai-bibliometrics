"""
parse_manual_exports.py
=======================
Read manually exported records from manual/ and normalize them into
the pipeline schema.  Supports:

  - Web of Science tab-delimited TSV (.txt — one row per record, 71 columns
    with headers PT, AU, TI, SO, AB, DE, PY, TC, DI, ...)
  - PubMed CSV (.csv — columns: PMID, Title, Authors, Citation,
    First Author, Journal/Book, Publication Year, Create Date, PMCID, DOI)
  - BibTeX (.bib — from ACM DL, IEEE Xplore, Mendeley, etc.;
    handles both standard multi-line and compact single-line formats)
  - Scopus PDF (.pdf — title + year extracted from filename; no abstract)
  - Scopus CSV (.csv with "Title", "Abstract", "DOI", "Year", ...)
  - RIS (.ris — generic)

Output: manual/normalized.csv
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

EXPORTS_DIR = Path(__file__).resolve().parent / "manual"
OUTPUT_PATH = EXPORTS_DIR / "normalized.csv"
CORPUS_PATH = Path(__file__).resolve().parent / "corpus_clean.csv"

# Minimum abstract length to consider a record usable
MIN_ABSTRACT_LEN = 50

# ---------------------------------------------------------------------------
# Schema: columns we want in the output
# ---------------------------------------------------------------------------
SCHEMA_COLS = [
    "id", "title", "abstract", "doi", "year", "data_source",
    "authors", "journal", "cited_by_count", "primary_topic",
    "keyword_terms", "matched_search_terms", "source_file",
]


def _norm_doi(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _make_id(doi: str, title: str, source: str, idx: int) -> str:
    if doi:
        return f"manual:{doi}"
    slug = re.sub(r"[^a-z0-9]+", "_", (title or "").lower())[:40]
    return f"manual:{source}:{idx}:{slug}"


# ---------------------------------------------------------------------------
# Scopus CSV parser
# ---------------------------------------------------------------------------
def _parse_scopus_csv(path: Path) -> list[dict]:
    """Scopus Desktop CSV export (UTF-8 BOM, comma-separated)."""
    records: list[dict] = []
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception:
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")
        except Exception as exc:
            print(f"  [WARN] Cannot read {path.name}: {exc}")
            return records

    col_map = {c.strip().lower(): c for c in df.columns}

    def _get(keys: list[str]) -> pd.Series:
        for k in keys:
            if k in col_map:
                return df[col_map[k]].fillna("")
        return pd.Series("", index=df.index)

    titles = _get(["title"])
    abstracts = _get(["abstract"])
    dois = _get(["doi"])
    years = _get(["year", "publication year"])
    journals = _get(["source title", "journal"])
    cited = _get(["cited by", "cited_by_count"])
    authors = _get(["authors", "author names"])
    keywords = _get(["author keywords", "index keywords", "keywords"])
    doc_types = _get(["document type"])

    for i in range(len(df)):
        title = str(titles.iloc[i]).strip()
        if not title or title.lower() in {"", "nan"}:
            continue
        abstract = str(abstracts.iloc[i]).strip()
        doi = _norm_doi(str(dois.iloc[i]))
        year_raw = str(years.iloc[i]).strip()
        year = int(year_raw[:4]) if re.match(r"\d{4}", year_raw) else None
        records.append({
            "title": title,
            "abstract": abstract,
            "doi": doi,
            "year": year,
            "journal": str(journals.iloc[i]).strip(),
            "cited_by_count": str(cited.iloc[i]).strip(),
            "authors": str(authors.iloc[i]).strip(),
            "keyword_terms": str(keywords.iloc[i]).strip(),
            "primary_topic": str(doc_types.iloc[i]).strip(),
            "data_source": "scopus_manual",
            "source_file": path.name,
        })
    return records


# ---------------------------------------------------------------------------
# Scopus PDF — title + year extracted from filename
# ---------------------------------------------------------------------------
def _parse_scopus_pdf(path: Path) -> list[dict]:
    """Extract metadata from Scopus PDF filename.
    Format: <Title-with-hyphens>_<Year>_<Publisher>.pdf
    """
    stem = path.stem
    m = re.search(r"_(\d{4})_", stem)
    if not m:
        return []
    year = int(m.group(1))
    title_part = stem[:m.start()]
    title = title_part.replace("-", " ").strip()
    if not title:
        return []
    return [{
        "title": title,
        "abstract": "",
        "doi": "",
        "year": year,
        "journal": "",
        "cited_by_count": "",
        "authors": "",
        "keyword_terms": "",
        "primary_topic": "",
        "data_source": "scopus_pdf",
        "source_file": path.name,
    }]


# ---------------------------------------------------------------------------
# Web of Science tab-delimited TSV parser
# (each row = one record; header row with 2-letter column codes)
# ---------------------------------------------------------------------------
def _parse_wos_tsv(path: Path) -> list[dict]:
    """WoS 'Tab-delimited (Win)' export — one row per record, 71+ columns."""
    records: list[dict] = []
    try:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False,
                         encoding="utf-8-sig", on_bad_lines="skip")
    except Exception as exc:
        print(f"  [WARN] Cannot read {path.name}: {exc}")
        return records

    cols = set(df.columns)

    def _col(name: str) -> pd.Series:
        return df[name].fillna("") if name in cols else pd.Series("", index=df.index)

    titles   = _col("TI")
    abstracts = _col("AB")
    dois     = _col("DI")
    years    = _col("PY")
    journals = _col("SO")
    cited    = _col("TC")
    authors  = _col("AU")
    keywords = _col("DE")
    subj     = _col("SC")

    for i in range(len(df)):
        title = str(titles.iloc[i]).strip()
        if not title or title.lower() in {"", "nan"}:
            continue
        doi = _norm_doi(str(dois.iloc[i]))
        year_raw = str(years.iloc[i]).strip()
        year = int(year_raw[:4]) if re.match(r"\d{4}", year_raw) else None
        records.append({
            "title": title,
            "abstract": str(abstracts.iloc[i]).strip(),
            "doi": doi,
            "year": year,
            "journal": str(journals.iloc[i]).strip(),
            "cited_by_count": str(cited.iloc[i]).strip(),
            "authors": str(authors.iloc[i]).strip(),
            "keyword_terms": str(keywords.iloc[i]).strip(),
            "primary_topic": str(subj.iloc[i]).strip(),
            "data_source": "wos_manual",
            "source_file": path.name,
        })
    return records


# ---------------------------------------------------------------------------
# PubMed CSV parser
# (columns: PMID, Title, Authors, Citation, First Author,
#            Journal/Book, Publication Year, Create Date, PMCID, NIHMS ID, DOI)
# ---------------------------------------------------------------------------
def _parse_pubmed_csv(path: Path) -> list[dict]:
    """PubMed 'Send to > File > CSV' export."""
    records: list[dict] = []
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception:
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")
        except Exception as exc:
            print(f"  [WARN] Cannot read {path.name}: {exc}")
            return records

    col_map = {c.strip().lower(): c for c in df.columns}

    def _get(keys: list[str]) -> pd.Series:
        for k in keys:
            if k in col_map:
                return df[col_map[k]].fillna("")
        return pd.Series("", index=df.index)

    titles   = _get(["title"])
    dois     = _get(["doi"])
    years    = _get(["publication year"])
    journals = _get(["journal/book"])
    authors  = _get(["authors"])

    for i in range(len(df)):
        title = str(titles.iloc[i]).strip()
        if not title or title.lower() in {"", "nan"}:
            continue
        doi = _norm_doi(str(dois.iloc[i]))
        year_raw = str(years.iloc[i]).strip()
        year = int(year_raw[:4]) if re.match(r"\d{4}", year_raw) else None
        records.append({
            "title": title,
            "abstract": "",          # PubMed CSV export does not include abstracts
            "doi": doi,
            "year": year,
            "journal": str(journals.iloc[i]).strip(),
            "cited_by_count": "",
            "authors": str(authors.iloc[i]).strip(),
            "keyword_terms": "",
            "primary_topic": "",
            "data_source": "pubmed_manual",
            "source_file": path.name,
        })
    return records


# ---------------------------------------------------------------------------
# BibTeX parser — handles both standard multi-line and compact (IEEE) formats
# ---------------------------------------------------------------------------
def _parse_bibtex(path: Path) -> list[dict]:
    """BibTeX parser for ACM DL, IEEE Xplore, Mendeley etc.

    IEEE Xplore exports compact BibTeX where records run together without
    a blank line (i.e. '}@ARTICLE{').  We normalise this by inserting a
    newline before every '@' that immediately follows '}'.
    """
    records: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"  [WARN] Cannot read {path.name}: {exc}")
        return records

    # Normalise compact IEEE format: "}@TYPE" → "}\n@TYPE"
    text = re.sub(r"\}(@[A-Za-z])", r"}\n\1", text)

    entry_re = re.compile(
        r"@([A-Za-z]+)\s*\{([^,\n]+),(.+?)(?=\n@[A-Za-z]|\Z)", re.DOTALL
    )

    for match in entry_re.finditer(text):
        entry_type = match.group(1).lower()
        if entry_type in {"string", "preamble", "comment"}:
            continue
        body = match.group(3)

        # Extract fields: handle  key = {value},  key = "value",  key = {nested {braces}}
        fields: dict[str, str] = {}
        # Greedy field extractor that handles nested braces
        for fm in re.finditer(
            r'(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}|(\w+)\s*=\s*"([^"]*)"',
            body,
        ):
            if fm.group(1):
                key, val = fm.group(1).lower(), fm.group(2)
            else:
                key, val = fm.group(3).lower(), fm.group(4)
            fields[key] = re.sub(r"[{}]", "", val).strip()

        title = fields.get("title", "").strip()
        if not title:
            continue

        doi_raw = fields.get("doi", "")
        # Some ACM/IEEE records wrap DOI in a URL with proxy; strip it
        doi_raw = re.sub(r"https?://[^/]*doi[^/]*/", "", doi_raw)
        doi = _norm_doi(doi_raw)

        year_raw = fields.get("year", "")
        year = int(year_raw[:4]) if re.match(r"\d{4}", year_raw) else None
        journal = (fields.get("journal") or fields.get("booktitle") or "").strip()
        authors = fields.get("author", "").replace("\n", " ").strip()
        keywords = (fields.get("keywords") or fields.get("keyword") or "").strip()
        abstract = fields.get("abstract", "").strip()

        records.append({
            "title": title,
            "abstract": abstract,
            "doi": doi,
            "year": year,
            "journal": journal,
            "cited_by_count": "",
            "authors": authors,
            "keyword_terms": keywords,
            "primary_topic": "",
            "data_source": "bibtex_manual",
            "source_file": path.name,
        })
    return records


# ---------------------------------------------------------------------------
# RIS parser
# ---------------------------------------------------------------------------
def _parse_ris(path: Path) -> list[dict]:
    """Generic RIS parser."""
    records: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        print(f"  [WARN] Cannot read {path.name}: {exc}")
        return records

    current: dict[str, list[str]] = {}

    def _flush(rec: dict[str, list[str]]) -> None:
        if not rec:
            return
        def _join(tag: str) -> str:
            return " ".join(rec.get(tag, [])).strip()
        title = _join("TI") or _join("T1")
        if not title:
            return
        abstract = _join("AB") or _join("N2")
        doi = _norm_doi(_join("DO") or _join("M3"))
        year_raw = _join("PY") or _join("Y1") or _join("DA")
        year_match = re.search(r"\d{4}", year_raw)
        year = int(year_match.group()) if year_match else None
        journal = _join("JO") or _join("JF") or _join("T2")
        authors = "; ".join(rec.get("AU", rec.get("A1", [])))
        keywords = "; ".join(rec.get("KW", []))
        records.append({
            "title": title,
            "abstract": abstract,
            "doi": doi,
            "year": year,
            "journal": journal,
            "cited_by_count": "",
            "authors": authors,
            "keyword_terms": keywords,
            "primary_topic": "",
            "data_source": "ris_manual",
            "source_file": path.name,
        })

    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9]{1,3})\s+-\s+(.*)$", line)
        if m:
            tag = m.group(1)
            value = m.group(2).strip()
            if tag == "ER":
                _flush(current)
                current = {}
            else:
                current.setdefault(tag, [])
                if value:
                    current[tag].append(value)
        elif line.startswith("  ") and current:
            last_tag = list(current.keys())[-1] if current else None
            if last_tag:
                current[last_tag].append(line.strip())

    _flush(current)
    return records


# ---------------------------------------------------------------------------
# PubMed tagged (legacy MEDLINE .txt) parser — kept for safety
# ---------------------------------------------------------------------------
def _parse_pubmed_tagged(path: Path) -> list[dict]:
    """PubMed MEDLINE tagged .txt format: 'TAG - value' lines."""
    records: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"  [WARN] Cannot read {path.name}: {exc}")
        return records

    current: dict[str, list[str]] = {}
    current_tag: Optional[str] = None

    def _flush(rec: dict[str, list[str]]) -> None:
        if not rec:
            return
        def _join(tag: str) -> str:
            return " ".join(rec.get(tag, [])).strip()
        title = _join("TI")
        if not title:
            return
        abstract = _join("AB")
        doi = ""
        for aid in rec.get("LID", []) + rec.get("AID", []):
            m = re.search(r"(10\.\S+)\s*\[doi\]", aid, re.IGNORECASE)
            if m:
                doi = _norm_doi(m.group(1))
                break
        dp_raw = _join("DP")
        year_match = re.search(r"\d{4}", dp_raw)
        year = int(year_match.group()) if year_match else None
        journal = _join("JT") or _join("TA")
        authors = "; ".join(rec.get("FAU", rec.get("AU", [])))
        keywords = "; ".join(rec.get("MH", []) + rec.get("OT", []))
        records.append({
            "title": title, "abstract": abstract, "doi": doi, "year": year,
            "journal": journal, "cited_by_count": "", "authors": authors,
            "keyword_terms": keywords, "primary_topic": "",
            "data_source": "pubmed_manual", "source_file": path.name,
        })

    for line in text.splitlines():
        m = re.match(r"^([A-Z]{2,4})\s+-\s+(.*)$", line)
        if m:
            current_tag = m.group(1)
            value = m.group(2).strip()
            current.setdefault(current_tag, [])
            if value:
                current[current_tag].append(value)
        elif line.strip() == "" and "TI" in current:
            _flush(current)
            current = {}
            current_tag = None
        elif line.startswith("      ") and current_tag:
            current.setdefault(current_tag, [])
            current[current_tag].append(line.strip())

    _flush(current)
    return records


# ---------------------------------------------------------------------------
# Format detector
# ---------------------------------------------------------------------------
def _detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "scopus_pdf"
    if ext == ".bib":
        return "bibtex"
    if ext == ".ris":
        return "ris"
    if ext == ".txt":
        try:
            head = path.read_text(encoding="utf-8-sig", errors="replace")[:300]
        except Exception:
            head = ""
        # WoS tab-delimited: first line is a header row with 2-letter column codes
        # separated by tabs; check for known WoS columns in first line
        first_line = head.splitlines()[0] if head.splitlines() else ""
        if "\t" in first_line and any(
            col in first_line.split("\t") for col in ("TI", "AB", "AU", "SO", "PY")
        ):
            return "wos_tsv"
        # Tagged MEDLINE/PubMed format
        if re.search(r"^[A-Z]{2,4}\s+-\s+", head, re.MULTILINE):
            return "pubmed_tagged"
        return "unknown"
    if ext == ".csv":
        try:
            first_line = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0].lower()
        except Exception:
            first_line = ""
        # PubMed CSV: contains "pmid" or "publication year" column
        if "pmid" in first_line or ("publication year" in first_line and "title" in first_line):
            return "pubmed_csv"
        # Scopus CSV
        if "cited by" in first_line or "source title" in first_line or "document type" in first_line:
            return "scopus_csv"
        return "scopus_csv"  # default for generic CSV
    return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not EXPORTS_DIR.exists():
        print(f"[ERROR] Folder not found: {EXPORTS_DIR}")
        sys.exit(1)

    # Recursive scan of all subdirectories
    SUPPORTED = {".csv", ".txt", ".bib", ".ris", ".pdf"}
    files = [
        f for f in EXPORTS_DIR.rglob("*")
        if f.is_file()
        and f.suffix.lower() in SUPPORTED
        and f.name != "normalized.csv"
    ]

    if not files:
        print(f"No export files found under {EXPORTS_DIR}")
        sys.exit(0)

    all_records: list[dict] = []
    counts_by_source: dict[str, int] = {}

    for path in sorted(files):
        rel = path.relative_to(EXPORTS_DIR)
        fmt = _detect_format(path)
        print(f"  {rel}  [{fmt}]", end="", flush=True)

        if fmt == "scopus_csv":
            recs = _parse_scopus_csv(path)
        elif fmt == "scopus_pdf":
            recs = _parse_scopus_pdf(path)
        elif fmt == "wos_tsv":
            recs = _parse_wos_tsv(path)
        elif fmt == "pubmed_csv":
            recs = _parse_pubmed_csv(path)
        elif fmt == "pubmed_tagged":
            # legacy MEDLINE tagged format (not current situation, but kept for safety)
            recs = _parse_pubmed_tagged(path)
        elif fmt == "bibtex":
            recs = _parse_bibtex(path)
        elif fmt == "ris":
            recs = _parse_ris(path)
        else:
            print(f"  → [SKIP] Unknown format")
            continue

        src = recs[0]["data_source"] if recs else fmt
        counts_by_source[src] = counts_by_source.get(src, 0) + len(recs)
        print(f"  → {len(recs)} records")
        all_records.extend(recs)

    if not all_records:
        print("No records parsed from any file.")
        sys.exit(0)

    df = pd.DataFrame(all_records)

    for col in SCHEMA_COLS:
        if col not in df.columns:
            df[col] = ""

    df["doi"] = df["doi"].fillna("").apply(_norm_doi)
    df["id"] = [
        _make_id(row["doi"], row["title"], row["data_source"], i)
        for i, row in df.iterrows()
    ]
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    n_raw = len(df)
    print(f"\nTotal raw records parsed: {n_raw}")

    # Internal dedup — prefer records with an abstract
    df["_has_abstract"] = df["abstract"].str.len().fillna(0) >= MIN_ABSTRACT_LEN
    df = df.sort_values("_has_abstract", ascending=False)
    df["_doi_key"] = df["doi"].where(df["doi"] != "", other=None)
    df["_title_key"] = df["title"].str.lower().str.strip()

    df["_is_doi_dup"] = False
    doi_mask = df["_doi_key"].notna()
    df.loc[doi_mask, "_is_doi_dup"] = df[doi_mask].duplicated(subset=["_doi_key"], keep="first")
    df = df[~df["_is_doi_dup"]].copy()
    duped_title = df.duplicated(subset=["_title_key"], keep="first")
    df = df[~duped_title].copy()
    n_internal_dedup = n_raw - len(df)

    # Dedup against existing corpus
    n_corpus_dedup = 0
    if CORPUS_PATH.exists():
        try:
            corpus = pd.read_csv(CORPUS_PATH, dtype=str, keep_default_na=False)
            existing_dois = set(corpus["doi"].dropna().apply(_norm_doi)) - {""}
            existing_titles = set(corpus["title"].fillna("").str.lower().str.strip())
            in_corpus = (
                df["doi"].isin(existing_dois) & (df["doi"] != "")
            ) | df["_title_key"].isin(existing_titles)
            n_corpus_dedup = int(in_corpus.sum())
            df = df[~in_corpus].copy()
        except Exception as exc:
            print(f"  [WARN] Could not load corpus for dedup: {exc}")

    df = df.drop(columns=["_has_abstract", "_doi_key", "_title_key", "_is_doi_dup"], errors="ignore")
    df["matched_search_terms"] = ""

    has_abstract = int((df["abstract"].str.len().fillna(0) >= MIN_ABSTRACT_LEN).sum())
    no_abstract  = len(df) - has_abstract
    year_counts  = df["year"].value_counts().sort_index()

    print(f"\n{'='*60}")
    print(f"  Raw parsed records      : {n_raw}")
    print(f"  Internal duplicates     : {n_internal_dedup}")
    print(f"  Already in corpus       : {n_corpus_dedup}")
    print(f"  → New unique records    : {len(df)}")
    print(f"     with abstract        : {has_abstract}")
    print(f"     no abstract          : {no_abstract}")
    print(f"\nBy source:")
    for src, cnt in df["data_source"].value_counts().items():
        print(f"  {src:<25} {cnt}")
    print(f"\nBy year (top 10):")
    for yr, cnt in year_counts.tail(10).items():
        print(f"  {int(yr) if pd.notna(yr) else '?':>4}: {cnt}")

    df[SCHEMA_COLS].to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
