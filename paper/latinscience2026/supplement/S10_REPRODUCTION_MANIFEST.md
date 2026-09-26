# S10. Publication reproduction manifest

## Chronology

| Activity | Supported chronology |
|---|---|
| Broad corpus | April 2026 snapshot; processing files dated 10 April and a manual-export filename dated early 11 April |
| Focused screening | Began 8 August on the stored corpus |
| Final anchors, scores and study analysis | Refined during August; original manuscript PDF dated 13 August |
| Final validation reconciliation and figure production | Production timestamp recorded in S12; original sample and human ratings retained |

These dates do not establish exact per-record retrieval times. Complete execution
logs and historical embedding-runtime versions were not retained. S1 documents
preserved query specifications rather than a complete execution log.

## Manuscript-to-input map

| Published item | Input |
|---|---|
| Table I: corpus profile | S8: publication_year and source_group |
| Table II: selection flow | S1 and S2: frozen aggregate counts |
| Figure 1: axis instrument | S3-S6: definitions and anchors; S8: distribution; S13: LOO |
| Figure 2: annual counts and cohort distributions | S8; figures.py |
| Figure 3: T-G scatter | S8 and S11; figures.py; adjusted fit evaluated at mean year |
| Principal association | S8; reproduce.py; S11 principal |
| Models excluding 2026 / restricted to 2023-2025 | S8; reproduce.py; S11 sensitivity outputs |
| Validation Results and Abstract | S9 with scores verified against S8; S7 and S11 |

## Statistics

The principal model is OLS, G ~ T + continuous publication year, N = 711.
Its coefficient interval uses 2,000 paired-record percentile bootstrap resamples,
seed 42. Preserved row order reproduces the original principal result. Sensitivity
models use 2,000 resamples and seed 20260808; the 2023-2025 model uses categorical
year adjustment. Partial correlation residualises both T and G on year;
its two-sided t test uses N - 3 = 708 degrees of freedom for one control variable.

Validation uses 129 complete paired human assessments and final automated scores.
Spearman intervals use 10,000 paired-record percentile bootstrap resamples,
seed 20260810. Calculation order is inter-rater T, inter-rater G,
human-automated T, human-automated G. Quadratic-weighted kappa uses squared
ordinal-distance weights on the 1-5 scale. Quintiles use final scores within the
validation sample. Sampling used earlier automated scores; estimates are
unweighted and do not automatically generalise to the full corpus.

## Final scoring

The scorer uses the exact S4 anchors and preserved document embeddings, with
unnormalised pole centroids and a normalised centroid-difference vector.
The available checkpoint is
`BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`.
Re-encoding anchors with this revision reproduces every frozen score within 1e-6.
This check does not reconstruct the historical acquisition-time runtime.

The public release supports statistical and figure reproduction from the
included derived tables. Recomputing scores additionally requires the original
document embeddings, their index, and the included-record source table, which
are not redistributed. With those preserved inputs available locally, run:

```text
python supplement/score_final_axes.py --embeddings /path/to/embeddings_bgem3.npy --index /path/to/embeddings_bgem3_index.csv --corpus /path/to/included_corpus.csv --anchors supplement/S4_SELECTED_PROTOTYPE_TEXTS.csv --reference /path/to/final_axis_scores.csv --output reproduced_scores.csv
```

The scorer matches by ID, requires exactly 711 unique included records, and
rejects inconsistent input. It does not repeat retrieval, screening, anchor
selection or human rating. Source texts and embeddings are not distributed;
statistical and figure reproduction run from this supplement alone.

S12 records final production software. S13 preserves the frozen configuration
and original final LOO diagnostics, which are not recalculated from scalar scores.
`SHA256SUMS.txt` covers each release file other than itself.
