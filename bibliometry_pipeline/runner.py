from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from .paths import RunPaths


StageFn = Callable[[RunPaths], object]


_ORDERED_STAGE_NAMES = [
    "fetch",
    "clean",
    "enrich",
    "indicators",
    "embed",
    "axes",
    "analyses",
    "summary",
    "report-text",
    "report-viz",
    "report-pdf",
    "tex-pdf",
    "screening",
]


def _stage_modules() -> dict[str, str]:
    return {
        "fetch": "fetch",
        "clean": "clean",
        "enrich": "enrich",
        "indicators": "indicators",
        "embed": "embeddings",
        "axes": "semantic_axes",
        "analyses": "analyses",
        "summary": "report_summary",
        "report-text": "report_text",
        "report-viz": "report_viz",
        "report-pdf": "report_pdf",
        "tex-pdf": "tex_pdf",
        "screening": "screening",
    }


def _load_stage(stage_name: str) -> StageFn:
    module = import_module(f"{__package__}.{stage_name}")
    return getattr(module, "run")


def ordered_stage_names() -> list[str]:
    return list(_ORDERED_STAGE_NAMES)


def resolve_stage_names(
    selected_stages: list[str] | None = None,
    *,
    start_from: str | None = None,
    excluded_stages: list[str] | None = None,
) -> list[str]:
    ordered = ordered_stage_names()
    excluded = set(excluded_stages or [])

    if start_from is not None:
        start_index = ordered.index(start_from)
        base = ordered[start_index:]
    else:
        base = ordered

    if selected_stages:
        requested = list(dict.fromkeys(selected_stages))
        stage_names = [stage for stage in base if stage in requested]
    else:
        stage_names = list(base)

    stage_names = [stage for stage in stage_names if stage not in excluded]
    return stage_names


def run_stages(stage_names: list[str], paths: RunPaths) -> None:
    stage_modules = _stage_modules()
    for name in stage_names:
        if name not in stage_modules:
            raise KeyError(f"Unknown stage: {name}")
        print(f"\n>>> RUNNING STAGE: {name}")
        _load_stage(stage_modules[name])(paths)