from __future__ import annotations

import argparse

from bibliometry_pipeline.paths import build_run_paths
from bibliometry_pipeline.runner import ordered_stage_names, resolve_stage_names, run_stages


def _flatten_excluded_stages(excluded_groups: list[list[str]] | None) -> list[str]:
    if not excluded_groups:
        return []
    return [stage for group in excluded_groups for stage in group]


def main() -> None:
    stage_names = ordered_stage_names()
    parser = argparse.ArgumentParser(description="Run the bibliometry pipeline by stage.")
    parser.add_argument(
        "stages",
        nargs="*",
        choices=stage_names,
        help="Optional subset of stages to run, resolved in pipeline order.",
    )
    parser.add_argument(
        "--start-from",
        choices=stage_names,
        default=None,
        help="Start at this stage and run the remaining pipeline steps unless excluded.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        nargs="+",
        choices=stage_names,
        default=None,
        metavar="STAGE",
        help="Stages to skip. Can be repeated, for example: --exclude report-text report-viz",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory. Defaults to the repository root. Use a subfolder like runs/academic_production_v2 to keep retries isolated.",
    )
    args = parser.parse_args()

    excluded_stages = _flatten_excluded_stages(args.exclude)
    stages_to_run = resolve_stage_names(
        args.stages,
        start_from=args.start_from,
        excluded_stages=excluded_stages,
    )
    if not stages_to_run:
        parser.error("No stages selected after applying --start-from and --exclude.")

    paths = build_run_paths(args.run_dir)
    print(f"Run directory: {paths.run_dir}")
    print(f"Stages: {', '.join(stages_to_run)}")
    run_stages(stages_to_run, paths)


if __name__ == "__main__":
    main()