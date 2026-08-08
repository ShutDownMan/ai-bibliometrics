# Latin.Science 2026 article workspace

This directory is the source of truth for the new full-paper rewrite.

## Separation from legacy work

The old broad run is frozen in `runs/academic_production_v14/` and documented under `archive/broad_ai_corpus_v14/`. Do not read root-level generated corpora, indicators or reports as inputs to this article.

## Live locations

| Material | Location | Version-control policy |
|---|---|---|
| Protocol and manuscript source | `paper/latinscience2026/` | tracked |
| Screening ledger and blinded ratings | `paper/latinscience2026/screening/`, `validation/` | local during review; release de-identified version later |
| New pipeline output | `runs/latinscience2026_v1/` | local and ignored |
| Full-paper plan | `NOTES/latin_science_full_paper_plan.md` | tracked |

## Required records before writing results

1. `protocol.md`: frozen question, hypotheses, sources, criteria and axis definitions.
2. `screening/screening_decisions.csv`: a decision and reason for every borderline or excluded record.
3. `validation/rubric.md` and a blinded ratings file from two independent raters.
4. A run manifest identifying the corpus and code version used by each table and figure.

No result enters the manuscript unless it can be regenerated from those records.
