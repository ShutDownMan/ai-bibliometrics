"""Pipeline stage: generate HTML/MD reports via visualizations.py.

Runs visualizations.py twice (dark + light) as a subprocess so that
the module-level path and argparse globals are evaluated at call-time
against the correct run_dir, not at import time.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .paths import RunPaths, ensure_run_dirs

_SCRIPT = Path(__file__).resolve().parents[1] / "visualizations.py"


def _run_mode(run_dir: Path, light: bool) -> None:
    label = "light" if light else "dark"
    cmd = [sys.executable, str(_SCRIPT)]
    if light:
        cmd.append("--light")
    if run_dir != _SCRIPT.parent:
        cmd += ["--run-dir", str(run_dir)]
    result = subprocess.run(cmd, check=True)
    _ = result  # returncode checked via check=True


def run(paths: RunPaths) -> None:
    ensure_run_dirs(paths)
    _run_mode(paths.run_dir, light=False)
    _run_mode(paths.run_dir, light=True)
