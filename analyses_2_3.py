from __future__ import annotations

import argparse

from bibliometry_pipeline.analyses import run
from bibliometry_pipeline.paths import build_run_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Run temporal and citation post-processing on the semantic axes.")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory. Defaults to the repository root.",
    )
    args = parser.parse_args()
    run(build_run_paths(args.run_dir))


if __name__ == "__main__":
    main()