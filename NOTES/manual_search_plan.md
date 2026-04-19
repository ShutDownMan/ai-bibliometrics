# Manual Search Plan — AI in Academic Production

> **Goal**: Supplement the automated corpus (136 papers) with records missed by the pipeline,
> especially the ~1,000 Scopus candidates dropped for `no_abstract` (API tier limitation)
> and Web of Science (not in the automated pipeline at all).
>
> **Deposit exports** to: `c:\Users\Jedson Gabriel\ws\bibliometry\manual_exports\`
> **Parser script**: `parse_manual_exports.py` (generates `manual_exports\normalized.csv`)

---

## Why the Programmatic Fetch Falls Short

| Stage | Count |
|-------|-------|
| Unique candidates identified | 1,648 |
| **Excluded — no abstract** | **1,042 (63%)** |
| Excluded — off-topic title | 121 |
| Excluded — weak alignment | 228 |
| Excluded — low relevance | 121 |
| **Kept in final corpus** | **136** |

The no-abstract wall is almost entirely Scopus: the institutional Elsevier API key available here
only returns metadata-level views; abstract fields are rejected. A **GUI export from scopus.com
with the "Abstract" checkbox** would recover these records with full text.

Web of Science is entirely absent from the automated pipeline and is a major source of
interdisciplinary CS/AI papers in journals like *Nature*, *PLOS ONE*, *Scientometrics*, etc.

---

## Access Setup

All databases below are accessible via **[Portal de Periódicos CAPES](https://www.periodicos.capes.gov.br/)**.

1. Go to https://www.periodicos.capes.gov.br/
2. Click **Acesso CAFe** → choose your institution → log in
3. From the CAPES portal, open each database link below (the session cookie carries through)

Alternatively, if your institution provides a VPN or proxy: access each database directly and
authenticate via the **"Institutional login"** / **"Access through your institution"** link.

---

## Phase 1 — Scopus GUI (Highest Priority)

**URL**: https://www.scopus.com → login via institution

The goal is to run the same narrow queries used in the API pipeline but export with full abstracts.

### Preparation

1. Open Scopus → **Document search** → **Advanced**
2. Paste each query below, click **Search**, then apply filters
3. Export all results from that query before moving to the next

### Universal filters for every query (apply in the left panel after searching):

- **Publish year**: 2020 – 2026
- **Document type**: Article, Review
- **Language**: English (optionally also Portuguese, Spanish)

### Query S1 — Manuscript & Academic Writing

```
TITLE-ABS-KEY( ( "manuscript writing" OR "scientific manuscript" OR "scholarly writing" OR "academic writing" OR "scientific writing" OR "research paper writing" OR "academic paper writing" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "generative AI" OR "ChatGPT" OR "GPT-4" OR "LLM" ) )
```

### Query S2 — Scholarly Publishing & Peer Review

```
TITLE-ABS-KEY( ( "scholarly publishing" OR "scientific publishing" OR "peer review" OR "editorial process" OR "journal policy" OR "open access publishing" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "generative AI" OR "ChatGPT" OR "LLM" ) )
```

### Query S3 — Systematic Review & Evidence Synthesis Automation

```
TITLE-ABS-KEY( ( "systematic review" OR "evidence synthesis" OR "abstract screening" OR "literature screening" OR "study selection" OR "scoping review" ) AND ( "automation" OR "automated" OR "artificial intelligence" OR "machine learning" OR "large language model" OR "LLM" OR "ChatGPT" ) )
```

### Query S4 — Research Integrity & AI Authorship

```
TITLE-ABS-KEY( ( "academic integrity" OR "research integrity" OR "paper mill" OR "AI-generated text" OR "AI-generated manuscript" OR "authorship" OR "publication ethics" OR "plagiarism detection" OR "text detection" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "LLM" OR "ChatGPT" OR "generative AI" ) )
```

### Query S5 — Reference Management & Research Workflow

```
TITLE-ABS-KEY( ( "reference management" OR "research workflow" OR "research assistant" OR "citation management" OR "literature search" OR "knowledge management" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "LLM" OR "ChatGPT" OR "GPT" ) )
```

### Export Instructions (Scopus)

1. After searching, click **Select all** (or select page by page if >2000)
2. Click **Export**
3. Choose **CSV** format
4. Check these fields: **Abstract**, **Author keywords**, **Index keywords**, **DOI**, **Source title**,
   **Year**, **Cited by count**, **Authors**, **Author affiliations**, **Document type**, **Language**
5. Click **Export** and save as: `scopus_s<N>_YYYYMMDD.csv`
   _(e.g., `scopus_s1_20260410.csv` for Query S1)_

---

## Phase 2 — Web of Science (Key Missing Source)

**URL**: https://www.webofscience.com → login via institution

WoS covers Science Citation Index Expanded (SCIE) and Social Sciences Citation Index (SSCI),
with strong coverage of interdisciplinary AI/research methods journals.

### Preparation

1. Open Web of Science Core Collection
2. Click **Advanced Search**
3. Paste the query string into the search box

### Query W1 — Core topic (broad)

```
TS=("artificial intelligence" OR "machine learning" OR "large language model" OR "generative AI" OR "ChatGPT" OR "GPT-4" OR "LLM") AND TS=("peer review" OR "manuscript" OR "scientific writing" OR "scholarly publishing" OR "scientific publishing" OR "systematic review" OR "literature review" OR "reference management" OR "evidence synthesis" OR "academic integrity" OR "research workflow" OR "paper mill" OR "research assistant" OR "abstract screening")
```

Filters: **Publication year**: 2020–2026 | **Document types**: Article, Review, Early Access

### Query W2 — Research integrity / AI authorship (narrower)

```
TS=("AI-generated text" OR "AI-generated content" OR "paper mill" OR "authorship integrity" OR "ghost authorship" OR "ChatGPT authorship" OR "LLM authorship") AND TS=("academic" OR "research" OR "scientific" OR "journal")
```

### Export Instructions (WoS)

WoS limits exports to 500 records per batch:

1. Click **Export** → **Tab-delimited file** (or **Plain Text File**)
2. Select: **Full Record and Cited References**
3. If results > 500: export records 1–500, then 501–1000, etc.
4. Save as: `wos_<query>_<batch>_YYYYMMDD.txt`
   _(e.g., `wos_w1_001_20260410.txt`)_

> **Important**: The WoS `.txt` format uses two-letter field tags (`TI`, `AB`, `DO`, `SO`, `PY`, `DE`, etc.)
> The parser handles this format automatically.

---

## Phase 3 — PubMed / MEDLINE (Systematic Review Pipeline Papers)

**URL**: https://pubmed.ncbi.nlm.nih.gov (free, no login needed)

PubMed is particularly strong for systematic review methodology and evidence synthesis papers
published in biomedical / health informatics journals.

### Query P1

```
("artificial intelligence"[tiab] OR "machine learning"[tiab] OR "large language model"[tiab] OR "ChatGPT"[tiab] OR "LLM"[tiab] OR "generative AI"[tiab]) AND ("systematic review"[tiab] OR "peer review"[tiab] OR "scholarly publishing"[tiab] OR "scientific writing"[tiab] OR "manuscript"[tiab] OR "abstract screening"[tiab] OR "research integrity"[tiab] OR "academic integrity"[tiab] OR "evidence synthesis"[tiab] OR "literature review"[tiab])
```

Filters (left panel): **Article types**: Journal Article, Review, Systematic Review | **Publication date**: 2020–2026

### Export Instructions (PubMed)

1. Click **Save** (top of results)
2. Selection: **All results** (or select page first if partial)
3. Format: **PubMed** (this is the tagged MEDLINE format — includes abstracts)
4. Save as: `pubmed_p1_YYYYMMDD.txt`

---

## Phase 4 — ACM Digital Library (CS/AI Tools)

**URL**: https://dl.acm.org (access via institution link or CAFe)

ACM covers Computer Science conferences and journals; important for AI tool papers and
CHI/CSCW papers on research assistants.

### Query A1

Use the **Advanced Search** with the "Anywhere" field:

```
("artificial intelligence" OR "machine learning" OR "LLM" OR "ChatGPT" OR "large language model" OR "generative AI") AND ("peer review" OR "scholarly writing" OR "scientific publishing" OR "systematic review" OR "research workflow" OR "academic integrity" OR "manuscript" OR "research assistant")
```

Filters: Publication date 2020–2026

### Export Instructions (ACM)

1. Select all results (checkbox at top, then "Select all X results")
2. Click **Export Citations** → choose **BibTeX**
3. Save as: `acm_a1_YYYYMMDD.bib`

> **Note**: ACM BibTeX exports include abstracts in the `abstract = {...}` field.

---

## Phase 5 — IEEE Xplore (AI Applications in Research)

**URL**: https://ieeexplore.ieee.org (login via institution / CAFe)

IEEE covers AI/ML conferences (NeurIPS, ICML, AAAI) and journals relevant for AI tool papers.

### Query I1

Use **Advanced Search → Command Search**:

```
("artificial intelligence" OR "machine learning" OR "LLM" OR "large language model" OR "generative AI" OR "ChatGPT") AND ("peer review" OR "scientific writing" OR "scholarly publishing" OR "systematic review" OR "research workflow" OR "academic integrity" OR "manuscript" OR "research integrity")
```

Filters: **Year**: 2020–2026 | **Content types**: Journals, Early Access Articles, Conference Publications

### Export Instructions (IEEE)

> **How IEEE export actually works**: The export dialog only operates on *selected* records —
> there is no "export all results" option. You must select records page by page first.
> The available formats are: **Plain Text**, **BibTeX**, **RIS**, RefWorks — **no CSV**.

**Recommended approach to handle ~5,000 results without losing sanity:**

First, cut the result count down with an additional filter before exporting:

- In the left panel click **Document Type** and keep only: `Journals` + `Early Access Articles`
  (this already excludes conference papers — uncheck **Conferences** in the active filters at top)
  
OR apply a tighter keyword filter to focus on the most relevant subset. The current query returns
5,160 results because the topic terms are broad; adding a title filter is more practical:

> In "Search within results" (top-left of results page) type:
> `peer review OR manuscript OR scholarly publishing OR academic integrity`
> This narrows to several hundred records where the research context is unambiguous.

**Per-batch export steps (repeat until all desired records are covered):**

1. Set **Items Per Page** to **100** (top-right dropdown)
2. Tick **Select All on Page** (checkbox at top of result list)
3. Click **Export** (top-right) → **Citations** tab
4. Format: **RIS** | Include: **Citation and Abstract**
5. Click **Download** — browser saves one `.ris` file
6. Advance to the next page and repeat from step 2
7. Save each file as: `ieee_i1_NNN_20260410.ris` (e.g. `ieee_i1_001_20260410.ris`, `ieee_i1_002_20260410.ris`, …)

> At 100 records per batch, exporting 500 records = 5 iterations (~10 min).
> Exporting the full 5,160 = ~52 iterations and is not recommended without pre-filtering.
> **Suggested target**: export the top ~500–1,000 by relevance after applying the
> "Search within results" refinement above.

---

## What to Skip / Exclude During Export

You can optionally apply a quick visual scan and de-select obvious off-topic clusters:

| Pattern in title | Likely off-topic | Action |
|-----------------|-----------------|--------|
| "EFL", "ESL", "English learning", "language teaching" | English language teaching | Skip |
| "clinical trial", "drug", "patient", "hospital" | Medical/clinical | Skip (unless topic is systematic review automation) |
| "remote sensing", "satellite", "image segmentation" | Engineering | Skip |
| "recommendation system", "e-commerce" | Non-research context | Skip |

> **When in doubt: include it.** The parser + pipeline will score and filter automatically.

---

## File Naming & Deposit Location

```
c:\Users\Jedson Gabriel\ws\bibliometry\manual_exports\
├── scopus_s1_20260410.csv
├── scopus_s2_20260410.csv
├── scopus_s3_20260410.csv
├── scopus_s4_20260410.csv
├── scopus_s5_20260410.csv
├── wos_w1_001_20260410.txt
├── wos_w1_002_20260410.txt   ← second batch if >500
├── wos_w2_001_20260410.txt
├── pubmed_p1_20260410.txt
├── acm_a1_20260410.bib
├── ieee_i1_001_20260410.ris  ← one file per 100-record page
├── ieee_i1_002_20260410.ris
├── ...                       ← continue until desired coverage
└── normalized.csv            ← generated by parse_manual_exports.py
```

---

## After Depositing: Run the Parser

```powershell
cd "c:\Users\Jedson Gabriel\ws\bibliometry"
& ".venv\Scripts\python.exe" parse_manual_exports.py
```

This will:
1. Read all files in `manual_exports\`
2. Auto-detect format (Scopus CSV, WoS tab-delimited, PubMed MEDLINE, BibTeX, RIS)
3. Normalize to the pipeline schema (same columns as `indicators\fetch_raw_candidates.csv`)
4. Deduplicate internally (by DOI, then by title)
5. Deduplicate against the existing corpus (`corpus_clean.csv`)
6. Save `manual_exports\normalized.csv` with counts reported

Then review `normalized.csv` and run the pipeline with:

```powershell
# Option A: run the full pipeline fresh from fetch (adds manual_exports as a source)
& ".venv\Scripts\python.exe" run_pipeline.py --run-dir runs/academic_production_v14

# Option B: just merge normalized.csv into the current corpus manually, then re-clean
```

---

## Estimated Time per Database

| Database | Queries | Est. results | Export time |
|----------|---------|-------------|-------------|
| Scopus | 5 | 300–2000 each | ~30 min total |
| Web of Science | 2 | 100–500 each | ~15 min |
| PubMed | 1 | 200–600 | ~5 min |
| ACM DL | 1 | 50–200 | ~5 min |
| IEEE | 1 | ~500–1,000 (after refinement) | ~15–20 min (5–10 page batches) |

Total: ~1 hour of manual work.
