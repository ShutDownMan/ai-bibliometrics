# Archive: broad AI corpus v14

**Status:** frozen legacy study — do not use as the analytical corpus for the Latin.Science 2026 submission.

## What this preserves

`runs/academic_production_v14/` is the last complete run of the original, broad study. It contains the raw/fetched corpus, cleaned corpus, embeddings, semantic scores, indicators and generated reports. Those large artifacts stay local and are deliberately excluded from GitHub; their identity is recorded in [`MANIFEST.sha256`](MANIFEST.sha256).

The source files tracked in the repository commit that adds this archive are the code snapshot for this run. Use that commit or its Git tag to reconstruct the analysis code, not the mutable files at the repository root.

## Known scope limitation

Although the original question concerned AI in academic production, this run has a broad multi-domain corpus (6,261 semantic records) dominated by clinical, medical-imaging and engineering material. Its results are useful for pipeline development, audit trails and future comparative work, but cannot substantiate the Latin.Science article's focused claims about scholarly communication and higher education.

In particular, the five-cluster solution has low separation (silhouette near 0.058) and the old semantic dimensions should be treated as exploratory.

## Preservation rules

1. Do not edit, move, rename or regenerate `runs/academic_production_v14/`.
2. Verify a local artifact with `Get-FileHash -Algorithm SHA256` against the manifest before relying on it.
3. Keep raw source exports and embedding caches local; they are not copied to GitHub because of size, licensing and provenance constraints.
4. All new article work starts in `runs/latinscience2026_v1/` and `paper/latinscience2026/`.

## Relationship to the rewrite

The rewrite is a new, narrower study, not a silent reanalysis of v14. It has a separate protocol, screening ledger, semantic-axis specification and human validation dataset. See [`paper/latinscience2026/README.md`](../../paper/latinscience2026/README.md).
