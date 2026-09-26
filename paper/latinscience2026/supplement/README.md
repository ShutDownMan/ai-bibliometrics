# Publication supplement

**Mapping AI in Scholarly Communication: Research Workflows, Named Models, and Governance**

This release accompanies the final Latin.Science 2026 manuscript. The population
remains 711 included records from the preserved April 2026 snapshot. The eight
unresolved records are excluded. Human ratings are unchanged; S9 now uses the
same final automated scores as the principal model. Citation analysis is not
part of the publication.

The [camera-ready PDF](../manuscript/main.pdf), [source](../manuscript/main.tex),
and [citation metadata](../CITATION.cff) are available alongside these files.

## Contents

| File | Content |
|---|---|
| S1 | Preserved search specifications, accounting and provenance limits |
| S2 | Screening rules and aggregate decisions |
| S3 | Semantic definitions, equations and encoding implementation |
| S4 | The 20 exact selected anchors |
| S5 | All 140 candidate texts |
| S6 | Final configuration and selection diagnostics |
| S7 | Validation protocol and final results |
| S8 | 711 de-identified records and final T/G scores |
| S9 | 129 rating pairs, final scores and IDs matching S8 |
| S10 | Chronology, manuscript-to-input map and reproduction commands |
| S11 | Reproduced principal, sensitivity and validation statistics |
| S12 | Final software versions and provenance qualifications |
| S13 | Frozen final anchor configuration and LOO diagnostics |
| reproduce.py | Statistical reproduction from S8 and S9 |
| score_final_axes.py | Apply final anchors to preserved document embeddings |
| figures.py | Generate the three published figures from released inputs |
| SHA256SUMS.txt | Release file checksums |

## Reproduction

Use Python 3.12 and install `requirements-statistics.txt`. From this directory:

```text
python reproduce.py --check
python figures.py --output-dir reproduced_figures
```

`--check` verifies reported outputs without modifying the JSON. `--write`
recalculates it. Figures use S8, S11 and S13. S10 documents scoring with the
original embeddings, which are not redistributed. Re-running the general
pipeline with its initial anchors does not reproduce the final configuration.

## Interpretation and omissions

Validation correlations are unweighted within a deliberately stratified sample.
Publication years are distinct from capture dates; 2026 is incomplete. Exact
per-record retrieval timestamps were not retained.

This release omits raw database exports, titles, abstracts, DOI lists, private
record IDs, the screening ledger, rater workbooks and rater identities. S8 IDs
are release-specific. S9 links to them without exposing form IDs or the private
crosswalk. Prototype texts are authored measurement inputs, not published
abstracts.
