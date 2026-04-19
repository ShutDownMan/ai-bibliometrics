from __future__ import annotations

import itertools
import re
from collections import Counter, defaultdict

import pandas as pd

from .config import KEYWORD_STOPWORDS
from .paths import RunPaths, ensure_run_dirs
from .utils import parse_list


_JOURNAL_CANONICAL_MAP: dict[str, str] = {
    "plos one": "PLOS ONE",
    "plos medicine": "PLOS Medicine",
    "plos biology": "PLOS Biology",
    "plos pathogens": "PLOS Pathogens",
    "plos neglected tropical diseases": "PLOS Neglected Tropical Diseases",
    "plos computational biology": "PLOS Computational Biology",
    "bmj open": "BMJ Open",
    "bmj": "BMJ",
    "npj digital medicine": "NPJ Digital Medicine",
}

_JOURNAL_ACRONYM_RE = re.compile(
    r"\b(Ieee|Acm|Bmj|Plos|Jmir|Njm|Nejm|Jama|Who|Npj|Mdpi|Ijms|Embo|Nih|Fda|Eu|Uk|Us)\b"
)
_JOURNAL_ACRONYM_FIXES: dict[str, str] = {
    "Ieee": "IEEE", "Acm": "ACM", "Bmj": "BMJ", "Plos": "PLOS",
    "Jmir": "JMIR", "Nejm": "NEJM", "Jama": "JAMA", "Who": "WHO",
    "Npj": "NPJ", "Mdpi": "MDPI", "Ijms": "IJMS", "Embo": "EMBO",
    "Nih": "NIH", "Fda": "FDA", "Eu": "EU", "Uk": "UK", "Us": "US",
    "Njm": "NJM",
}


def _canonical_journal_name(name: object) -> str:
    """Normalise a journal name string for deduplication.

    Strips whitespace, applies title-case, then restores known all-caps
    acronyms so that variants like ``IEEE ACCESS`` and ``IEEE Access``
    both map to ``IEEE Access``.
    """
    if not name or (isinstance(name, float)):
        return ""
    s = re.sub(r"\s+", " ", str(name).strip().lower())
    if s in _JOURNAL_CANONICAL_MAP:
        return _JOURNAL_CANONICAL_MAP[s]
    # Title-case the normalised lower form so all-caps variants collapse
    canonical = s.title()
    canonical = _JOURNAL_ACRONYM_RE.sub(lambda m: _JOURNAL_ACRONYM_FIXES.get(m.group(), m.group()), canonical)
    return canonical


def _extract_keywords(value) -> list[str]:
    items = parse_list(value)
    return [item["display_name"] for item in items if isinstance(item, dict) and item.get("display_name")]


def _extract_keyword_terms(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    keywords = []
    seen = set()
    for item in str(value).split("|"):
        keyword = item.strip()
        if not keyword:
            continue
        keyword_lc = keyword.lower()
        if keyword_lc in KEYWORD_STOPWORDS or keyword in seen:
            continue
        seen.add(keyword)
        keywords.append(keyword)
    return keywords


def _extract_authors(value) -> list[dict]:
    items = parse_list(value)
    authors = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get("author") or {}).get("display_name", "")
        institutions = [(inst.get("display_name", ""), inst.get("country_code", "")) for inst in (item.get("institutions") or [])]
        authors.append({
            "name": name,
            "institutions": institutions,
            "countries": [country for _, country in institutions if country],
        })
    return authors


def _series_or_blank(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([""] * len(df), index=df.index, dtype="object")


def _nonempty_text_mask(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    return (text != "") & (text.str.lower() != "nan") & (text != "[]")


def _normalise_author_name(value: object) -> str:
    text = str(value).replace("\n", " ").strip(" ,;{}")
    return re.sub(r"\s+", " ", text)


def _extract_plain_authors(value: object) -> list[dict]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []

    parsed = parse_list(value)
    if parsed and all(isinstance(item, str) for item in parsed):
        raw_names = parsed
    elif ";" in text:
        raw_names = text.split(";")
    elif re.search(r"\s+\band\b\s+", text, flags=re.IGNORECASE):
        raw_names = re.split(r"\s+\band\b\s+", text, flags=re.IGNORECASE)
    elif "|" in text:
        raw_names = text.split("|")
    else:
        raw_names = [text]

    authors = []
    seen: set[str] = set()
    for raw_name in raw_names:
        name = _normalise_author_name(raw_name)
        if not name or name.lower() == "nan" or name in seen:
            continue
        seen.add(name)
        authors.append({"name": name, "institutions": [], "countries": []})
    return authors


def _norm_doi(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _norm_title(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _recover_manual_authors(df: pd.DataFrame, paths: RunPaths) -> pd.Series:
    manual_path = paths.root / "manual" / "normalized.csv"
    recovered = pd.Series([""] * len(df), index=df.index, dtype="object")
    if not manual_path.exists() or "title" not in df.columns:
        return recovered

    manual = pd.read_csv(manual_path, dtype=str, keep_default_na=False)
    if manual.empty or "authors" not in manual.columns or "title" not in manual.columns:
        return recovered

    manual = manual[_nonempty_text_mask(manual["authors"])].copy()
    if manual.empty:
        return recovered

    manual["_doi_norm"] = _series_or_blank(manual, "doi").apply(_norm_doi)
    manual["_title_norm"] = manual["title"].apply(_norm_title)

    authors_by_doi = (
        manual[manual["_doi_norm"] != ""]
        .drop_duplicates(subset="_doi_norm", keep="first")
        .set_index("_doi_norm")["authors"]
    )
    authors_by_title = (
        manual[manual["_title_norm"] != ""]
        .drop_duplicates(subset="_title_norm", keep="first")
        .set_index("_title_norm")["authors"]
    )

    doi_norm = _series_or_blank(df, "doi").apply(_norm_doi)
    title_norm = df["title"].apply(_norm_title)
    recovered = doi_norm.map(authors_by_doi).fillna("")
    missing = recovered.eq("")
    recovered.loc[missing] = title_norm.loc[missing].map(authors_by_title).fillna("")
    return recovered.astype("object")


def run(paths: RunPaths) -> None:
    ensure_run_dirs(paths)

    src = paths.corpus_clean_path
    idir = paths.indicators_dir
    df = pd.read_csv(src)
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).astype(int)

    print("─" * 62)
    print(f"INDICATORS  ({len(df)} papers)")
    print("─" * 62)

    yearly = (
        df.groupby("publication_year")
        .agg(n=("id", "count"), citations=("cited_by_count", "sum"))
        .reset_index()
        .rename(columns={"publication_year": "year"})
    )
    yearly["year"] = yearly["year"].astype(int)
    yearly.to_csv(idir / "yearly_production.csv", index=False)

    _ISO_FIXES = {"LE": "LB"}  # known bad codes from source APIs
    _country_code_re = re.compile(r"^[A-Z]{2}$")
    country_counts: Counter = Counter()
    for value in df["countries"].dropna():
        for code in str(value).split("|"):
            code = code.strip().upper()
            if not code:
                continue
            code = _ISO_FIXES.get(code, code)
            if not _country_code_re.fullmatch(code):
                continue
            country_counts[code] += 1
    geo = pd.DataFrame(country_counts.most_common(), columns=["country_code", "n"])
    if not geo.empty:
        geo["pct"] = (100 * geo["n"] / geo["n"].sum()).round(2)
    else:
        geo["pct"] = []
    geo.to_csv(idir / "geo_countries.csv", index=False)

    journals = (
        df[df["journal"].notna() & (df["journal"] != "")]
        .assign(journal=lambda d: d["journal"].map(_canonical_journal_name))
        .groupby("journal")
        .agg(n=("id", "count"), total_cit=("cited_by_count", "sum"), is_in_doaj=("is_in_doaj", "first"))
        .reset_index()
        .sort_values("n", ascending=False)
    )
    total_journal_papers = int(journals["n"].sum())
    zone_size = max(total_journal_papers // 3, 1)
    cumulative = 0
    zones = {}
    for _, row in journals.iterrows():
        cumulative += int(row["n"])
        if cumulative <= zone_size:
            zones[row["journal"]] = 1
        elif cumulative <= 2 * zone_size:
            zones[row["journal"]] = 2
        else:
            zones[row["journal"]] = 3
    journals["bradford_zone"] = journals["journal"].map(zones)
    journals.to_csv(idir / "journals.csv", index=False)

    author_papers: Counter = Counter()
    author_citations: defaultdict = defaultdict(int)
    author_paper_citations: defaultdict = defaultdict(list)
    authorship_series = _series_or_blank(df, "authorships")
    authors_series = _series_or_blank(df, "authors")
    existing_author_mask = _nonempty_text_mask(authors_series)
    if not existing_author_mask.all():
        recovered_authors = _recover_manual_authors(df, paths)
        recovered_mask = ~existing_author_mask & _nonempty_text_mask(recovered_authors)
        if recovered_mask.any():
            authors_series = authors_series.copy()
            authors_series.loc[recovered_mask] = recovered_authors.loc[recovered_mask]
            print(f"  recovered plain-text authors from manual exports: {int(recovered_mask.sum())}")

    for row_index, row in df.iterrows():
        author_records = _extract_authors(authorship_series.at[row_index])
        if not author_records:
            author_records = _extract_plain_authors(authors_series.at[row_index])

        seen_names: set[str] = set()
        for author in author_records:
            if not author["name"] or author["name"] in seen_names:
                continue
            seen_names.add(author["name"])
            cit = int(row["cited_by_count"])
            author_papers[author["name"]] += 1
            author_citations[author["name"]] += cit
            author_paper_citations[author["name"]].append(cit)

    def _h_index(citations: list[int]) -> int:
        """Compute the h-index: largest h such that ≥h papers each have ≥h citations."""
        sorted_cit = sorted(citations, reverse=True)
        h = 0
        for i, c in enumerate(sorted_cit, 1):
            if c >= i:
                h = i
            else:
                break
        return h

    lotka_dist = Counter(author_papers.values())
    lotka = pd.DataFrame(sorted(lotka_dist.items()), columns=["n_papers", "n_authors"])
    if not lotka.empty:
        lotka["pct_authors"] = (100 * lotka["n_authors"] / lotka["n_authors"].sum()).round(2)
    else:
        lotka["pct_authors"] = []
    lotka.to_csv(idir / "lotka.csv", index=False)

    top_authors = pd.DataFrame(
        [
            {
                "author": name,
                "n_papers": author_papers[name],
                "total_cit": author_citations[name],
                "h_index": _h_index(author_paper_citations[name]),
            }
            for name in author_papers
        ],
        columns=["author", "n_papers", "total_cit", "h_index"],
    )
    if not top_authors.empty:
        top_authors = top_authors.sort_values(["n_papers", "total_cit", "author"], ascending=[False, False, True]).head(30)
    top_authors.to_csv(idir / "top_authors.csv", index=False)

    top_cols = ["title", "publication_year", "cited_by_count", "journal", "doi", "primary_topic", "category"]
    top20 = df.nlargest(20, "cited_by_count")[top_cols].copy()
    # Clean missing journals (API gaps)
    top20["journal"] = top20["journal"].fillna("").astype(str).replace("nan", "")
    # Normalize DOIs: strip leading URL prefix if present
    top20["doi"] = top20["doi"].fillna("").astype(str).replace("nan", "").str.replace(
        r"^https?://doi\.org/", "", regex=True
    )
    top20.to_csv(idir / "top20_cited.csv", index=False)

    kw_freq: Counter = Counter()
    cooc: Counter = Counter()
    min_kw_score = 0.4
    min_cooc = 3
    keywords_series = df["keywords"] if "keywords" in df.columns else pd.Series([None] * len(df), index=df.index)
    keyword_terms_series = df["keyword_terms"] if "keyword_terms" in df.columns else pd.Series([None] * len(df), index=df.index)

    # Explicit alias map: maps any lowercase variant to a canonical display form
    _KW_ALIASES: dict[str, str] = {
        # AI variants (abbreviation and capitalization)
        "artificial intelligence": "Artificial Intelligence",
        "ai": "Artificial Intelligence",
        "artificial intelligence (ai)": "Artificial Intelligence",
        # LLM variants (abbreviations and singular → plural canonical)
        "llm": "Large Language Models",
        "llms": "Large Language Models",
        "large language model": "Large Language Models",
        "large language models.": "Large Language Models",
        "large language models (llm)": "Large Language Models",
        "large language models (llms)": "Large Language Models",
        "large language model(llm)": "Large Language Models",
        "large language model (llm)": "Large Language Models",
        "chatgpt; large language models (llms)": "Large Language Models",
        # Generative AI variants
        "generative ai": "Generative AI",
        "generative artificial intelligence": "Generative AI",
        "gen ai": "Generative AI",
        # NLP abbreviation
        "nlp": "Natural Language Processing",
        "natural language processing (nlp)": "Natural Language Processing",
        # Systematic review plural/singular
        "systematic reviews": "Systematic Review",
        # ChatGPT capitalization fix
        "chatgpt": "ChatGPT",
    }

    def _article_kws(row_index) -> list[str]:
        value = keywords_series.at[row_index]
        items = parse_list(value)
        kws = [
            item["display_name"]
            for item in items
            if isinstance(item, dict)
            and item.get("score", 0) >= min_kw_score
            and item.get("display_name", "").lower() not in KEYWORD_STOPWORDS
        ]
        if not kws:
            kws = _extract_keyword_terms(keyword_terms_series.at[row_index])
        return kws

    # First pass: build canonical form map; aliases pre-populate and always win
    _kw_canonical: dict[str, str] = {}
    for lc, canonical in _KW_ALIASES.items():
        _kw_canonical[lc] = canonical
    for row_index in df.index:
        for kw in _article_kws(row_index):
            key = kw.lower()
            if key not in _kw_canonical:
                _kw_canonical[key] = kw  # first-seen casing for non-aliased terms

    # Second pass: count using canonical forms
    for row_index in df.index:
        kws_raw = _article_kws(row_index)
        kws = list(dict.fromkeys(_kw_canonical.get(kw.lower(), kw) for kw in kws_raw))  # canonical + dedup per article
        for kw in kws:
            kw_freq[kw] += 1
        for pair in itertools.combinations(sorted(set(kws)), 2):
            cooc[pair] += 1

    keyword_freq = pd.DataFrame(kw_freq.most_common(), columns=["keyword", "freq"])
    keyword_freq.to_csv(idir / "keyword_freq.csv", index=False)

    keyword_edges = pd.DataFrame(
        [(a, b, weight) for (a, b), weight in cooc.most_common() if weight >= min_cooc],
        columns=["source", "target", "weight"],
    )
    keyword_edges.to_csv(idir / "keyword_cooc.csv", index=False)

    collab: Counter = Counter()
    for value in df["countries"]:
        if pd.notna(value):
            countries = sorted(set(
                _ISO_FIXES.get(c.strip(), c.strip())
                for c in str(value).split("|")
                if c.strip()
            ))
        else:
            countries = []
        for pair in itertools.combinations(countries, 2):
            collab[pair] += 1
    collab_df = pd.DataFrame(
        [(a, b, n_collab) for (a, b), n_collab in collab.most_common()],
        columns=["country_a", "country_b", "n_collab"],
    )
    collab_df.to_csv(idir / "collab_countries.csv", index=False)

    print("Generated indicator tables in:", idir)