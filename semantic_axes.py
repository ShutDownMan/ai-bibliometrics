from __future__ import annotations

import argparse

from bibliometry_pipeline.paths import build_run_paths
from bibliometry_pipeline.semantic_axes import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Project the clustered corpus on the semantic axes.")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory. Defaults to the repository root.",
    )
    args = parser.parse_args()
    run(build_run_paths(args.run_dir))


if __name__ == "__main__":
    main()