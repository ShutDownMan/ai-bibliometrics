# S7. Blinded rating study

## Procedure

Two raters independently assessed 129 included records with complete ratings.
They received titles and abstracts only. They did not receive authors, venue,
publication year, source, automated scores, or the other rater's answers.

## Rating scales

### Technological specificity (T)

| Score | Rule |
|---:|---|
| 1 | Generic AI/ML; no named generative model is central. |
| 2 | Generative AI or an LLM is mentioned generally. |
| 3 | Mixed case or incidental named-model mention. |
| 4 | A named model or model family is important. |
| 5 | A named model or model family is central. |

### Governance orientation (G)

| Score | Rule |
|---:|---|
| 1 | Workflow support for research, writing, review, or synthesis is central. |
| 2 | Mostly workflow support; rules or policy are secondary. |
| 3 | Balanced or unclear. |
| 4 | Mostly integrity, authorship, disclosure, policy, or safeguards. |
| 5 | Governance, integrity, or institutional policy is central. |

Raters could mark an axis insufficiently specified rather than guess.

## Sample and final-score alignment

The original sample contained 130 records. The 129 records with complete matched
ratings from both raters are analysed. Sampling used publication-year cohorts
and the automated-score range available at sampling; the sample and human
ratings were not changed after the final anchors were fixed. Final automated
scores are matched through the private form-to-record crosswalk. Public record
IDs in S9 match S8, allowing the equality of the final scores to be checked.

Correlations are unweighted estimates within this deliberately stratified
sample. They do not automatically generalise to the full corpus.

## Analysis and results

Spearman rank correlations use 10,000 paired-record percentile bootstrap
resamples (seed 20260810). The final principal analysis and validation outputs
are reproduced by `python reproduce.py --check`. All published intervals,
per-rater correlations and quintile summaries are in S11.

| Statistic | T | G |
|---|---:|---:|
| Inter-rater Spearman rho | 0.755 | 0.806 |
| Human-mean versus final automated Spearman rho | 0.755 | 0.623 |
| Quadratic-weighted kappa | 0.631 | 0.805 |

T quintile means increase monotonically. G rises overall, with a small reversal between quintiles 2 and 3; monotonic calibration is not claimed for G.
