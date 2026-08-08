# Data conventions

Generated data are intentionally kept in `runs/latin_science_2026/` and ignored
by GitHub. This avoids uploading raw database exports, large derived corpora,
and potentially non-redistributable metadata.

For the paper, create a small local `final/` snapshot only after the eight
pending records are resolved:

```text
final/
  corpus_final.csv
  axis_scores_final.csv
  analysis_manifest.json
  figures/
```

`analysis_manifest.json` must record source files, row counts, SHA-256 hashes,
code commit, model name and command/date used. Do not overwrite the current run
or v14 archive while making that snapshot.
