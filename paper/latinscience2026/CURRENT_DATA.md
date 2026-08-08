# Current data status — 2026-08-08

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
