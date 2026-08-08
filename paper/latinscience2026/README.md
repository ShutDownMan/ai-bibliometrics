# Latin.Science 2026 article workspace

This directory is the tracked source of truth for the full-paper rewrite. Large
data and generated artifacts remain local under `runs/latin_science_2026/`.

## Current article direction

**Working title:** *From Generic AI to Named Models and Institutional
Guardrails: A Bibliometric Map of AI in Scholarly Communication and Research
Workflows, 2020–2026.*

The paper maps AI used **for scholarly communication and research workflows**:
scientific writing, publishing, peer review, integrity, evidence-synthesis
automation, and higher-education governance. It does not claim to map AI
research generally, clinical AI, or education technology generally.

## Directory map

| Location | Purpose | Git policy |
|---|---|---|
| `protocol.md` | frozen scope, questions and analysis commitments | tracked |
| `CURRENT_DATA.md` | current facts, artifact map and data decisions | tracked |
| `data/` | documentation for the local analytical dataset | tracked docs only |
| `validation/` | validation procedure and returned-ratings conventions | tracked docs only during blind review |
| `manuscript/` | paper source, figures selected for submission and references | tracked |
| `development/` | rule-development/audit documentation | tracked |
| `runs/latin_science_2026/` | screened corpus, scores, samples and outputs | local / ignored |
| `archive/broad_ai_corpus_v14/` | frozen broad predecessor study | tracked manifest; data local |

## Operating rules

1. Do not edit or move the v14 archive or current run artifacts merely to make
   the tree look cleaner.
2. The final analytical population is the 711 records with `decision=include`.
   The eight `needs_review` records are excluded from every result until manually
   adjudicated.
3. Every manuscript table/figure must name its local input artifact and the run
   date in its caption or supplementary manifest.
4. Only code, protocol, manuscript source and lightweight documentation belong
   on GitHub. Corpora, raw exports, ratings workbooks and PDFs stay local until
   an intentional de-identified release is prepared.
