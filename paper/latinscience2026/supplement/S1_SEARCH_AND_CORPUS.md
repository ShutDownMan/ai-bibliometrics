# S1. Search and corpus

## Scope

The retrieval covered records dated 2020--2026. It sought AI work on scholarly
writing, publishing, peer review, evidence synthesis, research integrity, and
institutional academic-AI policy. Search results were deduplicated, cleaned,
and screened at title-and-abstract level. A retrieved record was not assumed to
be in scope.

## Source concepts

All source searches paired AI terms with scholarly-workflow terms.

**AI terms:** `artificial intelligence`, `machine learning`, `large language
model`, `generative AI`, `ChatGPT`, `GPT-4`, and `LLM`.

**Scholarly-workflow terms:** manuscript or scientific writing; scholarly or
scientific publishing; peer review; editorial process; journal policy;
systematic review; evidence synthesis; abstract screening; research integrity;
academic integrity; paper mills; reference management; research workflow; and
research assistant.

The specifications below are preserved query definitions and export descriptions,
not a complete execution log. The local files support an April 2026 snapshot:
processing artifacts are dated 10 April and a manual export bears an early
11-April timestamp. Exact source-specific execution times, time zones and
per-record capture dates cannot be reconstructed reliably. Focused screening
began on 8 August; final anchors and analyses were refined during August 2026.
Publication year is distinct from capture time. No census or hard per-record
11-April retrieval cutoff is claimed.

## Sources, queries, and retrieval counts

### Shared AI term block

`AI_TERMS` below is substituted wherever an AI-term group is required (except
where a query carries its own explicit AI list):

```text
"artificial intelligence" OR "inteligência artificial" OR "inteligencia artificial"
OR "machine learning" OR "aprendizado de máquina" OR "aprendizaje automático"
OR "large language model" OR "large language models" OR "modelo de linguagem"
OR "modelos de linguagem" OR "modelo de lenguaje" OR "modelos de lenguaje"
OR "generative AI" OR "IA generativa" OR "ChatGPT" OR "GPT" OR "LLM"
```

### Scopus (automated API)

Nine `TITLE-ABS-KEY` queries were run against the Scopus Search API
(`https://api.elsevier.com/content/search/scopus`) with page size 200 (falling
back to 25 when the service level rejects the larger page), a cap of 150
results per query, and `sort=-coverDate`. Under the institutional entitlement
the Search API does not return abstracts; abstracts for up to 120 DOIs were
backfilled from Europe PMC/Crossref.

```text
Q1 TITLE-ABS-KEY(("manuscript writing" OR "scientific manuscript" OR "manuscrito científico" OR "redação científica" OR "redacción científica") AND (AI_TERMS))
Q2 TITLE-ABS-KEY(("scholarly publishing" OR "scientific publishing" OR "publicação científica" OR "publicación científica" OR "comunicação científica" OR "comunicación científica") AND (AI_TERMS))
Q3 TITLE-ABS-KEY(("peer review" OR "revisão por pares" OR "revisión por pares") AND ("automated" OR AI_TERMS))
Q4 TITLE-ABS-KEY(("systematic review" OR "revisão sistemática" OR "revisión sistemática") AND ("automation" OR "automated screening" OR AI_TERMS))
Q5 TITLE-ABS-KEY(("evidence synthesis" OR "síntese de evidências" OR "síntesis de evidencia") AND (AI_TERMS))
Q6 TITLE-ABS-KEY(("academic integrity" OR "integridade acadêmica" OR "integridad académica") AND (AI_TERMS))
Q7 TITLE-ABS-KEY(("paper mill" OR "AI-generated text" OR "AI generated manuscript") AND ("detection" OR "classifier" OR "machine learning"))
Q8 TITLE-ABS-KEY(("reference management" OR "gestão de referências" OR "gestión de referencias") AND (AI_TERMS))
Q9 TITLE-ABS-KEY(("research workflow" OR "research assistant" OR "assistente de pesquisa" OR "asistente de investigación" OR "fluxo de trabalho de pesquisa" OR "flujo de trabajo de investigación") AND (AI_TERMS))
```

Retrieved candidates: 1,160 (1,082 new after DOI/title dedup against the pool).

### Scopus (manual GUI supplement)

Five `TITLE-ABS-KEY` query families were run in the Scopus web interface
(filters 2020--2026, document types Article/Review, language English):

```text
S1 TITLE-ABS-KEY(( "manuscript writing" OR "scientific manuscript" OR "scholarly writing" OR "academic writing" OR "scientific writing" OR "research paper writing" OR "academic paper writing" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "generative AI" OR "ChatGPT" OR "GPT-4" OR "LLM" ))
S2 TITLE-ABS-KEY(( "scholarly publishing" OR "scientific publishing" OR "peer review" OR "editorial process" OR "journal policy" OR "open access publishing" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "generative AI" OR "ChatGPT" OR "LLM" ))
S3 TITLE-ABS-KEY(( "systematic review" OR "evidence synthesis" OR "abstract screening" OR "literature screening" OR "study selection" OR "scoping review" ) AND ( "automation" OR "automated" OR "artificial intelligence" OR "machine learning" OR "large language model" OR "LLM" OR "ChatGPT" ))
S4 TITLE-ABS-KEY(( "academic integrity" OR "research integrity" OR "paper mill" OR "AI-generated text" OR "AI-generated manuscript" OR "authorship" OR "publication ethics" OR "plagiarism detection" OR "text detection" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "LLM" OR "ChatGPT" OR "generative AI" ))
S5 TITLE-ABS-KEY(( "reference management" OR "research workflow" OR "research assistant" OR "citation management" OR "literature search" OR "knowledge management" ) AND ( "artificial intelligence" OR "machine learning" OR "large language model" OR "LLM" OR "ChatGPT" OR "GPT" ))
```

Only a limited number of records were actually downloaded from this interface:
17 PDFs and a 10-record CSV export. The CSV was produced on 11 April, after the
main normalisation run, and is not part of the processed corpus. GUI total-hit
counts for each query were not preserved.

### Web of Science

Two `TS=` queries were run in Web of Science Core Collection (Advanced Search;
filters 2020--2026, document types Article/Review/Early Access) and exported
as tab-delimited full records:

```text
W1 TS=("artificial intelligence" OR "machine learning" OR "large language model" OR "generative AI" OR "ChatGPT" OR "GPT-4" OR "LLM") AND TS=("peer review" OR "manuscript" OR "scientific writing" OR "scholarly publishing" OR "scientific publishing" OR "systematic review" OR "literature review" OR "reference management" OR "evidence synthesis" OR "academic integrity" OR "research workflow" OR "paper mill" OR "research assistant" OR "abstract screening")

W2 TS=("AI-generated text" OR "AI-generated content" OR "paper mill" OR "authorship integrity" OR "ghost authorship" OR "ChatGPT authorship" OR "LLM authorship") AND TS=("academic" OR "research" OR "scientific" OR "journal")
```

Exported records: 2,102 (W1: 1,000; W2: 1,102).

### PubMed/MEDLINE

One title/abstract query was run in PubMed (filters Journal Article / Review /
Systematic Review; publication date 2020--2026) and exported in MEDLINE tagged
format (includes abstracts):

```text
P1 ("artificial intelligence"[tiab] OR "machine learning"[tiab] OR "large language model"[tiab] OR "ChatGPT"[tiab] OR "LLM"[tiab] OR "generative AI"[tiab]) AND ("systematic review"[tiab] OR "peer review"[tiab] OR "scholarly publishing"[tiab] OR "scientific writing"[tiab] OR "manuscript"[tiab] OR "abstract screening"[tiab] OR "research integrity"[tiab] OR "academic integrity"[tiab] OR "evidence synthesis"[tiab] OR "literature review"[tiab])
```

Exported records: 4,500.

### ACM Digital Library

One query was run (publication-date filter 2020--2026) and exported as BibTeX,
with abstracts in the `abstract` field:

```text
A1 ("artificial intelligence" OR "machine learning" OR "LLM" OR "ChatGPT" OR "large language model" OR "generative AI") AND ("peer review" OR "scholarly writing" OR "scientific publishing" OR "systematic review" OR "research workflow" OR "academic integrity" OR "manuscript" OR "research assistant")
```

Exported records: 350 (seven batches of 50).

### IEEE Xplore

One query was run (year filter 2020--2026; content types Journals / Early
Access / Conference Publications) and exported as **BibTeX** (compact IEEE
BibTeX; abstracts included):

```text
I1 ("artificial intelligence" OR "machine learning" OR "LLM" OR "large language model" OR "generative AI" OR "ChatGPT") AND ("peer review" OR "scientific writing" OR "scholarly publishing" OR "systematic review" OR "research workflow" OR "academic integrity" OR "manuscript" OR "research integrity")
```

Exported records: 428 (four batches of 100 plus one of 28).

> **Export-format note:** both ACM and IEEE records were exported as **BibTeX**.
> The manuscript's "ACM/IEEE BibTeX export" wording is therefore correct. No
> RIS files were used. (An earlier supplement draft describing the IEEE export
> as RIS was incorrect.)

### OpenAlex

The OpenAlex `works` API was queried with the filter

```text
title.search:artificial intelligence OR machine learning OR large language model OR generative AI OR ChatGPT OR GPT OR LLM OR inteligência artificial OR inteligencia artificial OR aprendizado de máquina OR aprendizaje automático OR modelo de linguagem OR modelos de linguagem OR modelo de lenguaje OR modelos de lenguaje OR IA generativa,publication_year:>2019,type:article|review
```

combined, one at a time, with each curated scholarly-workflow topic search term
in the pipeline configuration (English, Portuguese, and Spanish terms for
manuscript preparation, peer review, evidence synthesis, integrity, editorial
policy, AI-text detection, and research workflow). Pagination used a 200-row
cursor; only title, DOI, year, type, authorships, journal, keywords, topics,
open-access, and citation-count fields were selected.

Unique candidate records: 60.

### Europe PMC

Six queries were run through the Europe PMC REST interface with a first-
publication-date window `FIRST_PDATE:[2020-01-01 TO 2026-12-31]`:

```text
E1 ("peer review" OR "revisão por pares" OR "revisión por pares") AND (AI_TERMS) AND FIRST_PDATE:[2020-01-01 TO 2026-12-31]
E2 ("systematic review" OR "revisão sistemática" OR "revisión sistemática") AND (AI_TERMS) AND FIRST_PDATE:[2020-01-01 TO 2026-12-31]
E3 ("evidence synthesis" OR "síntese de evidências" OR "síntesis de evidencia") AND (AI_TERMS) AND FIRST_PDATE:[2020-01-01 TO 2026-12-31]
E4 ("academic integrity" OR "integridade acadêmica" OR "integridad académica") AND (AI_TERMS) AND FIRST_PDATE:[2020-01-01 TO 2026-12-31]
E5 ("scholarly publishing" OR "scientific publishing" OR "publicação científica" OR "publicación científica") AND (AI_TERMS) AND FIRST_PDATE:[2020-01-01 TO 2026-12-31]
E6 ("reference management" OR "gestão de referências" OR "gestión de referencias") AND (AI_TERMS) AND FIRST_PDATE:[2020-01-01 TO 2026-12-31]
```

Unique candidate records: 507.

### Semantic Scholar

Configured as an optional source but disabled during this run (no API key
available), so it contributed no records.

## Retrieval and export counts

| Source | Mode | Records retrieved/exported |
|---|---:|---:|
| Web of Science | Manual GUI export (W1, W2) | 2,102 |
| PubMed/MEDLINE | Manual GUI export (P1) | 4,500 |
| ACM Digital Library | Manual BibTeX export (A1) | 350 |
| IEEE Xplore | Manual BibTeX export (I1) | 428 |
| Scopus | API (9 queries) | 1,160 candidates |
| Scopus | Manual GUI (17 PDFs + 10-record CSV) | 27 |
| Europe PMC | API (6 queries) | 507 candidates |
| OpenAlex | API (filter + topic search) | 60 candidates |
| Semantic Scholar | disabled | 0 |

Counts are pre-deduplication raw exports/retrievals. Within the manual exports,
deduplication by DOI and title reduced the raw total to 7,031 unique records;
deduplication against the API pool left 6,752 new manual records. The union of
all sources produced 8,400 unique candidates, which after cleaning and
embedding eligibility became the 6,261-record semantic corpus below.

Per-query total-hit counts (matches a database reported before export caps)
were not preserved for the manual interfaces; the table above lists only the
exported counts.

## Corpus accounting

| Stage | Records |
|---|---:|
| Broad corpus after cleaning and embedding eligibility | 6,261 |
| Included after title-and-abstract scope screening | 711 |
| Excluded at screening | 5,542 |
| Unresolved borderline records, excluded from analysis | 8 |

The 711 included records were assigned a source label using the fixed
first-seen order used in processing: Web of Science, PubMed/MEDLINE, Europe
PMC, ACM/IEEE exports, Scopus, and OpenAlex. The source table therefore
describes both coverage and that assignment rule.

Source labels of the included records (current analysis run):

| Source label | Records |
|---|---:|
| Web of Science export | 533 |
| PubMed/MEDLINE export | 87 |
| Europe PMC | 40 |
| ACM/IEEE BibTeX export | 40 |
| Scopus | 9 |
| OpenAlex | 2 |
