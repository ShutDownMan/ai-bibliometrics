# Latin.Science 2026 paper and research materials

## Public publication files

The camera-ready manuscript and its supporting research materials are browsable
as individual files in the versioned [Latin.Science 2026 release](https://github.com/ShutDownMan/ai-bibliometrics/tree/latinscience2026-v1.0.0/paper/latinscience2026).

- [Final PDF](manuscript/main.pdf)
- [LaTeX source](manuscript/main.tex)
- [Supplement index](supplement/README.md)
- [Derived analysis data](supplement/S8_DERIVED_ANALYSIS_DATA.csv)
- [Validation data](supplement/S9_VALIDATION_SCORES.csv)
- [Reproduction manifest](supplement/S10_REPRODUCTION_MANIFEST.md)
- [Citation metadata](CITATION.cff)

The released tables and scripts reproduce the published statistics and figures.
The original database records, document embeddings, screening ledger, rater
workbooks, identities, and private form-to-record crosswalk are not included.
Recomputing the document scores requires preserved source inputs that are not
redistributed under the applicable access terms. The S9 validation file uses
release-specific record IDs and contains no form IDs.

## Reproduce the reported statistics and figures

From the repository root, install the dependencies listed in
`paper/latinscience2026/supplement/requirements-statistics.txt`, then run:

```text
python paper/latinscience2026/supplement/reproduce.py --check
python paper/latinscience2026/supplement/figures.py --package paper/latinscience2026/supplement --output-dir reproduced_figures
```

The first command checks the reported estimates against the released derived
tables. The second regenerates the three figures from those tables. Neither
command needs the local corpus, raw database exports, or document embeddings.

To rebuild the PDF, use pdfLaTeX twice from `paper/latinscience2026/manuscript/`:

```text
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

## Repository layout

| Path | Purpose |
|---|---|
| `manuscript/` | Camera-ready PDF, LaTeX source, template files, and figure assets |
| `supplement/` | Individually browsable protocols, derived data, code, and checksums |
| `protocol.md` | Study scope and analysis commitments |
| `CURRENT_DATA.md` | Publication status and clearly marked historical working notes |
| `data/`, `validation/`, `development/` | Study documentation |
| `runs/latin_science_2026/` | Private working inputs and analysis outputs; ignored by Git |
| `submission_artifacts/` | JEMS upload bundles and historical files; ignored by Git |

The optional submission ZIPs are retained locally for portal workflows. The
repository release is the public access point for researchers.
