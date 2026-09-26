# Publication status (September 2026)

The final manuscript is `manuscript/main.tex` and the publication supplement is
`supplement/`. The frozen corpus remains N=711. Validation uses the same
129 human-rating pairs matched to final scores: Spearman rho=0.755 for T and
0.623 for G. The principal coefficient remains 0.206. `S11_PUBLICATION_RESULTS.json`
and `S10_REPRODUCTION_MANIFEST.md` in the public supplement are the current results
and artifact map. Citation analysis is omitted from the publication. The August
status below is retained as historical context.

## Historical working notes from 2026-08-08

The following notes predate the final human-validation analysis. Use the public
`supplement/` files and the publication landing page for current results.

## Use this dataset for the manuscript draft

The current provisional analytical dataset is:

```text
runs/latin_science_2026/indicators/corpus_paper.csv
filter: decision == "include"
N = 711
```

Do **not** include the eight `needs_review` records in figures, models,
validation sampling or narrative counts. They are retained only for eventual
manual adjudication.

## Artifact map

| Local artifact | Current role | Status |
|---|---|---|
| `screening_decisions.csv` | complete decision ledger for 6,261 source records | 711 include; 8 pending; 5,542 exclude |
| `indicators/corpus_paper.csv` | screened corpus with metadata | contains 711 include + 8 pending; filter required |
| `indicators/axis_scores.csv` | T/G scores for source corpus | numerical scores usable; decision/reason columns are from an older screen and must not be used |
| `indicators/statistical_results.json` | initial article statistics | runs on the 711 included records |
| `indicators/validation_sample_130.csv` | automatic-score sampling frame | 130 included records |
| `indicators/validation_ratings_130.xlsx` | blinded human-rating workbook | ready; no completed ratings yet |
| `indicators/pilot_ratings_*.json` | rubric-development pilot | 14 matched double ratings; not confirmatory evidence |

## Corpus snapshot

The publication year in this table is not a record-capture date. Local broad
corpus-processing artifacts and manual exports are dated 10--11 April 2026;
focused screening, scoring, and initial statistics were produced on 8 August
2026. Per-record retrieval timestamps and complete source-query logs were not
retained, so this is an April 2026 project snapshot, not a continuously updated
or precisely time-stamped census. See `supplement/S1_SEARCH_AND_CORPUS.md`.

| Year | Included records |
|---:|---:|
| 2020 | 4 |
| 2021 | 6 |
| 2022 | 10 |
| 2023 | 99 |
| 2024 | 196 |
| 2025 | 314 |
| 2026 | 82 |

The very small pre-2023 base means a pre/post descriptive comparison is more
defensible than a claim of smooth linear growth in a semantic score.

## Cohort-first outputs

`indicators/cohort_descriptives.csv` is the current temporal reporting table.
It provides medians, IQRs, and 10,000-resample bootstrap confidence intervals
for 2020--2022, 2023, 2024, 2025, and provisional 2026. The 2026 cohort is
descriptive only. `indicators/cohort_sensitivity_results.json` contains the
pre-specified T--G robustness models, including the 2023--2025 categorical-year
model. The earlier binary pre-2023/2023+ result remains an archived diagnostic,
not the intended main temporal result.

## Data actions, in order

1. Manually resolve the eight pending screening decisions and record the person,
   date and rationale in `screening_decisions.csv`.
2. Export one `corpus_final.csv` containing only included records, then generate
   a matching final axis-score table keyed by `id`.
3. Regenerate only the manuscript tables/figures from those two final files.
4. Keep the 130-record Excel workbook unchanged once it is sent to raters;
   preserve a crosswalk from its `Form ID` to the sample `id` before collecting
   ratings.
5. Run human-validation analysis after two independent completed workbooks are
   received. It can update the method/results section without changing the
   paper's central descriptive analysis.
