# Ad Hoc Scripts

This folder contains exploratory scripts that are useful for one-off inspection and research work but are not part of the maintained pipeline execution path.

These scripts now live outside the repository root so the root stays focused on the supported pipeline entrypoints and utilities.

Usage pattern:

```powershell
python scripts/adhoc/audit_corpus.py --run-dir runs/academic_production_v14
python scripts/adhoc/axis_probe.py --run-dir runs/academic_production_v14
```

If `--run-dir` is omitted, the scripts default to the repository root for backwards compatibility with older root-level artifacts.