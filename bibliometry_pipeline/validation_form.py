"""Blinded human-validation Likert form for the Latin.Science 2026 paper.

The paper (see ``NOTES/latin_science_full_paper_plan.md``, sections
"Rubrica humana Likert" and "Amostragem de validação") validates its two
theory-guided semantic axes — **T** (technological specificity: generic AI →
named GenAI model) and **G** (governance orientation: workflow support →
governance/integrity) — against independent human ratings collected on a
*blinded* form.  Each rater sees only title + abstract (never the automatic
scores, cluster, year, journal, citations, authors, DOI, or data source) and
rates the two 1–5 Likert scales with an explicit "insufficient information"
option that is analysed as missing data (not forced to the midpoint).

Sampling follows the paper plan:

* Confirmatory sample: target 300 papers, minimum 200; if the corpus is smaller
  than the target, all available papers are used.
* Separate pilot round of 20 papers at the beginning with the same
  stratification (kept disjoint from the confirmatory sample).
* Stratified by year cohort (2020–22, 2023, 2024, 2025–26), by data source
  (when present), and by the quintile of each axis score, so the full score
  range is validated and not just the "easy" cases.
* Strata that are too small are merged with an adjacent stratum; any remaining
  shortfall is redistributed over the pool.

Outputs (written to ``RunPaths.indicators_dir``):

* ``validation_form.csv``        — blinded data-collection sheet.  Pre-fills
  ``form_id``, ``corpus_id``, ``sample_type``, ``title`` and ``abstract``;
  leaves all ``rater*`` columns empty for the raters to complete.
* ``validation_form.html``       — self-contained, offline, dark/light capable
  HTML form: pilot section (clearly separated), confirmatory section, rubric
  anchors visible per paper, "insufficient information" checkboxes, a progress
  indicator, and a button that exports the current rater's ratings as CSV.
* ``validation_metadata.json``   — sampling parameters, stratification counts,
  rubric text (Portuguese), pilot/confirmatory split, per-paper form_id ↔
  corpus_id ↔ automatic scores mapping (for the later IAA / calibration
  analysis), and the generation date.
"""

from __future__ import annotations

import html
import json
import random
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .config import MIN_ABSTRACT_LENGTH
from .paths import RunPaths, ensure_run_dirs
from .utils import clean_html_text, write_json

# ---------------------------------------------------------------------------
# Rubric (Portuguese) — frozen before results, per the paper plan
# ---------------------------------------------------------------------------

RUBRIC_T: dict[str, Any] = {
    "label": "T — Especificidade Tecnológica (IA Genérica → Modelos GenAI Nomeados)",
    "short": "Especificidade Tecnológica",
    "anchors": [
        "1. IA/ML genérica, nenhum sistema/modelo generativo nomeado é central.",
        "2. GenAI/LLM aparece genericamente, sem modelo nomeado como objeto central.",
        "3. Caso misto ou menção incidental a produto/modelo.",
        "4. Um modelo/família nomeada é importante para o estudo.",
        "5. O estudo avalia, compara ou discute centralmente um ou mais modelos nomeados.",
    ],
}

RUBRIC_G: dict[str, Any] = {
    "label": "G — Orientação do Trabalho (Apoio ao Fluxo de Trabalho → Governança/Integridade)",
    "short": "Orientação do Trabalho",
    "anchors": [
        "1. Centralmente apoio a tarefas de pesquisa/escrita/revisão/síntese.",
        "2. Predominantemente apoio ao fluxo de trabalho, com menção secundária a regras.",
        "3. Equilíbrio ou foco indeterminado.",
        "4. Predominantemente integridade, autoria, disclosure, política ou salvaguardas.",
        "5. Centralmente governança/integridade/política; apoio à tarefa é secundário.",
    ],
}

INSUFFICIENT_LABEL = (
    "Informação insuficiente (analisar como dado ausente, não forçar ao ponto médio)"
)
MISSING_ABSTRACT_PLACEHOLDER = "(resumo indisponível)"
NO_ABSTRACT_NOTICE = (
    "Resumo indisponível. Avaliar apenas pelo título, ou marcar 'informação insuficiente'."
)

# ---------------------------------------------------------------------------
# Sampling parameters
# ---------------------------------------------------------------------------

PILOT_N = 20
CONFIRMATORY_TARGET = 300
CONFIRMATORY_MIN = 200
AXIS_QUINTILES = 5

YEAR_COHORT_RANGES: dict[str, tuple[int, ...]] = {
    "2020-22": (2020, 2021, 2022),
    "2023": (2023,),
    "2024": (2024,),
    "2025-26": (2025, 2026),
}
COHORT_ORDER = ["2020-22", "2023", "2024", "2025-26", "unknown"]

# Random form ids use an unambiguous alphabet (no 0/O/1/I).
FORM_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
FORM_ID_LENGTH = 5

# Exact column layout of the blinded collection CSV.
COLLECTION_COLUMNS = [
    "form_id",
    "corpus_id",
    "sample_type",
    "title",
    "abstract",
    "rater1_T",
    "rater1_G",
    "rater1_T_insufficient",
    "rater1_G_insufficient",
    "rater2_T",
    "rater2_G",
    "rater2_T_insufficient",
    "rater2_G_insufficient",
    "notes",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _year_cohort(year: object) -> str:
    """Map a publication year to the paper's cohort label."""
    try:
        y = int(year)
    except (TypeError, ValueError):
        return "unknown"
    if y <= 2022:
        return "2020-22"
    if y == 2023:
        return "2023"
    if y == 2024:
        return "2024"
    if y >= 2025:
        return "2025-26"
    return "unknown"


def _clean_source(value: object) -> str:
    """Normalise a data-source label; missing values become 'unknown'."""
    if value is None:
        return "unknown"
    s = str(value).strip()
    if s in ("", "nan", "None", "<NA>", "NaN"):
        return "unknown"
    return s


def _to_int(value: object, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_int_or_none(value: object) -> int | None:
    try:
        if value is None or pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float_or_none(value: object) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_quintile(series: pd.Series) -> pd.Series:
    """Bin scores into ``AXIS_QUINTILES`` ordered strata (0..q-1).

    Uses ``rank(method='first')`` so ties are broken deterministically and the
    corpus-wide score range is always split into exactly five bins, even when a
    quantile boundary falls inside a run of equal scores.  This guarantees the
    sampling covers the full range of each axis rather than only the easy cases.
    """
    if series.nunique() <= 1:
        return pd.Series([0] * len(series), index=series.index, dtype=int)
    bins = pd.qcut(series.rank(method="first"), q=AXIS_QUINTILES, labels=False)
    return pd.Series(np.asarray(bins).astype(int), index=series.index)


def _allocate_largest_remainder(n: int, weights: Sequence[float]) -> list[int]:
    """Allocate ``n`` integer quotas across groups proportionally to ``weights``.

    Uses the largest-remainder (Hamilton) method so the quotas sum exactly to
    ``n`` when ``weights`` are all positive.
    """
    n_groups = len(weights)
    if n <= 0 or n_groups == 0:
        return [0] * n_groups
    total = float(sum(weights))
    if total <= 0:
        base = n // n_groups
        rem = n % n_groups
        return [base + 1 if i < rem else base for i in range(n_groups)]
    quotas = [w / total * n for w in weights]
    floors = [int(q) for q in quotas]
    remainder = n - sum(floors)
    fracs = sorted(
        ((quotas[i] - floors[i], i) for i in range(n_groups)),
        key=lambda x: (-x[0], x[1]),
    )
    for k in range(remainder):
        floors[fracs[k % n_groups][1]] += 1
    return floors


def _merge_small_cohorts(cohort_counts: dict[str, int], n_target: int) -> dict[str, str]:
    """Merge cohorts with too few papers into a chronologically adjacent cohort.

    Returns a mapping ``original-cohort -> merged-cohort``.  The floor is a
    small share of the target (never less than 2 papers), so merging only
    triggers for genuinely sparse cohorts.
    """
    floor = max(2, int(np.ceil(n_target / 40)))
    merged = {c: c for c in COHORT_ORDER}
    counts = {c: int(cohort_counts.get(c, 0)) for c in COHORT_ORDER}
    present = [c for c in COHORT_ORDER if counts[c] > 0]

    changed = True
    while changed:
        changed = False
        small = [c for c in present if counts[c] > 0 and counts[c] < floor]
        if not small:
            break
        c = min(small, key=lambda x: (counts[x], COHORT_ORDER.index(x)))
        idx = COHORT_ORDER.index(c)
        neighbors = [
            COHORT_ORDER[i]
            for i in (idx - 1, idx + 1)
            if 0 <= i < len(COHORT_ORDER)
            and COHORT_ORDER[i] in present
            and COHORT_ORDER[i] != c
        ]
        if not neighbors:
            others = [x for x in present if x != c and counts[x] > 0]
            if not others:
                break
            neighbors = others
        nbr = min(neighbors, key=lambda x: counts[x])
        counts[nbr] += counts[c]
        counts[c] = 0
        present.remove(c)
        # Update every key that currently points at ``c`` so later merges of
        # ``nbr`` propagate transitively.
        for key, target in list(merged.items()):
            if target == c:
                merged[key] = nbr
        changed = True

    return {c: merged.get(c, c) for c in COHORT_ORDER}


def _sample_cell(cell_df: pd.DataFrame, quota: int, rng) -> list[int]:
    """Sample up to ``quota`` row positions from one stratum cell.

    Guarantees coverage across the joint (T-quintile, G-quintile) grid: the
    first pass takes one paper from as many distinct grid cells as the quota
    allows; the second pass fills the remainder proportionally across the cells
    that still have available rows.
    """
    n = len(cell_df)
    if quota <= 0 or n == 0:
        return []
    quota = min(quota, n)
    if n <= quota:
        return cell_df["_row"].tolist()

    cells = list(cell_df.groupby(["_tq", "_gq"], observed=True).groups.items())
    rng.shuffle(cells)
    selected: list[int] = []
    remaining: set[int] = set(cell_df["_row"].tolist())

    # Pass 1 — skeleton: one paper per distinct (T,G) quintile cell.
    for (_tq, _gq), idxs in cells:
        if len(selected) >= quota:
            break
        pool = [i for i in idxs if i in remaining]
        if pool:
            pick = int(pool[rng.integers(len(pool))])
            selected.append(pick)
            remaining.discard(pick)

    # Pass 2 — fill the rest proportionally across still-available cells.
    if len(selected) < quota:
        avail = {k: [i for i in v if i in remaining] for k, v in cells}
        keys = [k for k, v in avail.items() if v]
        deficit = quota - len(selected)
        while deficit > 0 and keys:
            weights = np.array([len(avail[k]) for k in keys], dtype=float)
            alloc = _allocate_largest_remainder(deficit, weights)
            new_keys: list[Any] = []
            took_any = False
            for k, a in zip(keys, alloc):
                if a <= 0:
                    new_keys.append(k)
                    continue
                pool = avail[k]
                take = min(a, len(pool))
                picks = [int(i) for i in rng.choice(pool, size=take, replace=False)]
                selected.extend(picks)
                deficit -= len(picks)
                remaining.difference_update(picks)
                avail[k] = [i for i in pool if i not in set(picks)]
                if avail[k]:
                    new_keys.append(k)
                took_any = True
            keys = new_keys
            if not took_any:
                break

    return selected[:quota]


def _sample_stratified(
    work: pd.DataFrame,
    n_target: int,
    rng,
    t_col: str,
    g_col: str,
) -> list[Any]:
    """Return index values of an ``n_target``-sized stratified sample.

    Stratification is by ``(year_cohort, data_source)`` with proportional
    allocation, then within each stratum across the joint T×G quintile grid
    (see ``_sample_cell``).  Small year cohorts are merged into adjacent ones;
    any shortfall (strata with too few papers) is redistributed over the pool.

    Expects (and reuses, when present) the columns ``_tq``/``_gq`` (quintiles),
    ``publication_year``/``data_source`` (strata) on ``work``.
    """
    if n_target <= 0 or work.empty:
        return []
    n_target = min(n_target, len(work))

    df = work.copy()
    df["_row"] = np.arange(len(df))
    if "_cohort" not in df.columns:
        df["_cohort"] = df["publication_year"].map(_year_cohort)
    if "_source" not in df.columns:
        if "data_source" in df.columns:
            df["_source"] = df["data_source"].map(_clean_source)
        else:
            df["_source"] = "unknown"
    if "_tq" not in df.columns:
        df["_tq"] = _score_quintile(df[t_col])
    if "_gq" not in df.columns:
        df["_gq"] = _score_quintile(df[g_col])

    # Merge sparse year cohorts into chronologically adjacent cohorts.
    cohort_counts = df["_cohort"].value_counts().to_dict()
    cohort_map = _merge_small_cohorts(cohort_counts, n_target)
    df["_cohort"] = df["_cohort"].map(cohort_map)

    # Allocate the target across (cohort, source) strata proportionally.
    strata = df.groupby(["_cohort", "_source"], observed=True).size().sort_index()
    quotas = _allocate_largest_remainder(n_target, strata.values.astype(float))
    strata_quota = dict(zip(strata.index, quotas))

    selected: list[int] = []
    for (cohort, source), quota in strata_quota.items():
        cell = df[(df["_cohort"] == cohort) & (df["_source"] == source)]
        selected.extend(_sample_cell(cell, quota, rng))

    # Redistribute any shortfall (strata with too few papers) over the pool.
    if len(selected) < n_target:
        chosen = set(selected)
        pool = df[~df["_row"].isin(chosen)]
        deficit = n_target - len(selected)
        if len(pool) > 0:
            extra = [
                int(i)
                for i in rng.choice(
                    pool["_row"].to_numpy(), size=min(deficit, len(pool)), replace=False
                )
            ]
            selected.extend(extra)

    return df.index[selected[:n_target]].tolist()


# ---------------------------------------------------------------------------
# Corpus preparation / axis resolution
# ---------------------------------------------------------------------------


def _attach_axis_scores(
    corpus: pd.DataFrame, paths: RunPaths
) -> tuple[pd.DataFrame, str, str, str]:
    """Ensure T and G axis score columns exist on ``corpus``.

    Resolution order:
    1. paper axis names ``axis_t_technology`` / ``axis_g_governance``;
    2. v14 exploratory names ``axis_e_technology`` / ``axis_g_guardrails``
       (backward compatibility);
    3. merge ``indicators/axis_scores.csv`` by ``id`` (new columns
       ``_t_score`` / ``_g_score`` are added in place).

    Returns ``(corpus, t_col, g_col, provenance_note)``.
    """
    t_col: str | None = None
    g_col: str | None = None

    if "axis_t_technology" in corpus.columns:
        t_col = "axis_t_technology"
    elif "axis_e_technology" in corpus.columns:
        t_col = "axis_e_technology"
    if "axis_g_governance" in corpus.columns:
        g_col = "axis_g_governance"
    elif "axis_g_guardrails" in corpus.columns:
        g_col = "axis_g_guardrails"

    t_src: str | None = None
    g_src: str | None = None
    if (t_col is None or g_col is None) and "id" in corpus.columns:
        axis_path = paths.indicators_dir / "axis_scores.csv"
        if axis_path.exists():
            scores = pd.read_csv(axis_path)
            index = scores.set_index("id")
            if t_col is None:
                for candidate in ("axis_t_technology", "axis_e_technology"):
                    if candidate in scores.columns:
                        corpus["_t_score"] = corpus["id"].map(index[candidate])
                        t_col = "_t_score"
                        t_src = candidate
                        break
            if g_col is None:
                for candidate in ("axis_g_governance", "axis_g_guardrails"):
                    if candidate in scores.columns:
                        corpus["_g_score"] = corpus["id"].map(index[candidate])
                        g_col = "_g_score"
                        g_src = candidate
                        break

    if t_col is None or g_col is None:
        available = [
            c
            for c in (
                "axis_t_technology",
                "axis_g_governance",
                "axis_e_technology",
                "axis_g_guardrails",
            )
            if c in corpus.columns
        ]
        raise ValueError(
            "Could not resolve both semantic axis columns. Expected "
            "axis_t_technology / axis_g_governance (or v14 fallbacks "
            "axis_e_technology / axis_g_guardrails). None of these were present in "
            f"{paths.corpus_paper_path} nor in {paths.indicators_dir / 'axis_scores.csv'}. "
            f"Columns found: {available}. Run the paper_axes stage first."
        )

    if t_col.startswith("_") or g_col.startswith("_"):
        note = f"merged from axis_scores.csv ({t_src} / {g_src})"
    elif t_col == "axis_t_technology":
        note = "corpus axis_t_technology / axis_g_governance"
    else:
        note = "v14 fallback axis_e_technology / axis_g_guardrails"
    return corpus, t_col, g_col, note


def _prepare_abstracts(corpus: pd.DataFrame) -> pd.DataFrame:
    """Clean abstracts, strip HTML/entities, and flag missing/short ones."""
    if "abstract" not in corpus.columns:
        corpus["abstract"] = ""
    cleaned = corpus["abstract"].map(clean_html_text).map(html.unescape)
    corpus["_abstract_clean"] = cleaned
    corpus["_has_abstract"] = cleaned.str.len() >= MIN_ABSTRACT_LENGTH
    return corpus


def _new_form_id(py_rng: random.Random, used: set[str]) -> str:
    while True:
        candidate = "V" + "".join(
            py_rng.choice(FORM_ID_ALPHABET) for _ in range(FORM_ID_LENGTH - 1)
        )
        if candidate not in used:
            used.add(candidate)
            return candidate


def _build_record(
    corpus: pd.DataFrame, idx: Any, sample_type: str, form_id: str, t_col: str, g_col: str
) -> dict[str, Any]:
    row = corpus.loc[idx]
    has_abstract = bool(row.get("_has_abstract", False))
    abstract = str(row.get("_abstract_clean") or "").strip()
    if not has_abstract or not abstract:
        has_abstract = False
        abstract = MISSING_ABSTRACT_PLACEHOLDER
    return {
        "form_id": form_id,
        "corpus_id": str(row.get("id", "")),
        "sample_type": sample_type,
        "title": str(row.get("title") or "").strip(),
        "abstract": abstract,
        "has_abstract": has_abstract,
        "axis_t": _to_float_or_none(row.get(t_col)),
        "axis_g": _to_float_or_none(row.get(g_col)),
        "year_cohort": str(row.get("_cohort") or "unknown"),
        "data_source": str(row.get("_source") or "unknown"),
        "t_quintile": _to_int_or_none(row.get("_tq")),
        "g_quintile": _to_int_or_none(row.get("_gq")),
        "publication_year": _to_int_or_none(row.get("publication_year")),
    }


def _counts(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts().items()}


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_HTML_HEAD = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Validação cega — Latin.Science 2026</title>
<script>
(function(){try{var t=localStorage.getItem("latin2026_validation_theme");
if(t){document.documentElement.setAttribute("data-theme",t);}
else if(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches){
document.documentElement.setAttribute("data-theme","dark");}}catch(e){}})();
</script>
<style>
* { box-sizing: border-box; }
:root {
  --bg:#ffffff; --fg:#1c1e21; --muted:#5f6672; --border:#d4d8dd;
  --card:#f6f7f9; --accent:#1f5fa8; --accent-soft:#e7eef7;
  --pilot:#8a5a00; --pilot-soft:#fdf3e0; --confirm:#176b2f; --confirm-soft:#e7f4ea;
  --danger:#a63a3a; --bar-track:#e4e6e8; --bar-fill:#1f5fa8;
  --radius:10px;
}
html[data-theme="dark"] {
  --bg:#191b1c; --fg:#e8e6e3; --muted:#a8a29b; --border:#3c4043;
  --card:#222628; --accent:#7cb3ef; --accent-soft:#23303c;
  --pilot:#f0b34b; --pilot-soft:#3a2f18; --confirm:#72cf85; --confirm-soft:#183326;
  --danger:#ef8888; --bar-track:#33363a; --bar-fill:#7cb3ef;
}
html { scroll-behavior: smooth; }
body {
  margin:0; font-family:"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif;
  background:var(--bg); color:var(--fg); line-height:1.45;
  padding-bottom: 120px;
}
.topbar {
  position:sticky; top:0; z-index:50; background:var(--bg);
  border-bottom:1px solid var(--border); padding:8px 16px;
  display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center;
}
.topbar .title { font-size:15px; font-weight:700; }
.topbar .subtitle { display:block; font-size:12px; color:var(--muted); font-weight:400; }
.topbar-controls { display:flex; gap:8px; align-items:center; margin-left:auto; flex-wrap:wrap; }
.topbar button, .topbar select {
  font:inherit; font-size:12.5px; padding:5px 10px; border-radius:6px;
  border:1px solid var(--border); background:var(--card); color:var(--fg); cursor:pointer;
}
.topbar button:hover { background:var(--accent-soft); }
.progress { flex:1 1 100%; display:flex; align-items:center; gap:10px; }
.progress-label { font-size:12.5px; color:var(--muted); white-space:nowrap; }
.progress-bar { flex:1; height:8px; background:var(--bar-track); border-radius:4px; overflow:hidden; }
#progress-fill { height:100%; width:0%; background:var(--bar-fill); transition:width .15s ease; }
.rubric {
  margin:12px 16px 0; border:1px solid var(--border); border-radius:var(--radius);
  background:var(--card);
}
.rubric summary { padding:10px 14px; cursor:pointer; font-weight:600; font-size:14px; }
.rubric-body { padding:0 14px 12px; display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:720px){ .rubric-body { grid-template-columns:1fr; } }
.rubric-block { border:1px solid var(--border); border-radius:8px; padding:10px 12px; background:var(--bg); }
.rubric-block h4 { margin:0 0 6px; font-size:13.5px; }
.rubric-block ol { margin:0; padding-left:20px; font-size:12.8px; }
.insufficient-hint { font-size:12.5px; color:var(--muted); padding:0 14px 12px; }
.section { margin:20px 16px; }
.section h2 { font-size:18px; border-bottom:1px solid var(--border); padding-bottom:6px; }
.section-hint { font-size:13px; color:var(--muted); margin-top:-4px; }
.paper {
  border:1px solid var(--border); border-radius:var(--radius); padding:14px 16px;
  margin:14px 0; background:var(--card);
}
.paper-head { display:flex; align-items:center; gap:10px; margin-bottom:4px; }
.badge { font-size:11px; font-weight:700; letter-spacing:.04em; padding:2px 8px; border-radius:4px; }
.badge.pilot { background:var(--pilot-soft); color:var(--pilot); }
.badge.confirm { background:var(--confirm-soft); color:var(--confirm); }
.paper-id { font-size:12px; color:var(--muted); }
.paper-title { margin:6px 0 6px; font-size:15px; line-height:1.35; }
.paper-abstract {
  font-size:13.5px; white-space:pre-wrap; border:1px dashed var(--border);
  background:var(--bg); border-radius:8px; padding:8px 10px; margin-bottom:8px;
}
.no-abstract-notice { font-size:12.5px; color:var(--danger); margin:0 0 6px; }
.axis-group { border:1px solid var(--border); border-radius:8px; padding:10px 12px; margin:10px 0; background:var(--bg); }
.axis-group.insuff { opacity:.55; }
.axis-title { font-size:13px; font-weight:600; margin-bottom:6px; }
.likert { display:flex; flex-direction:column; gap:2px; }
.opt {
  display:flex; gap:8px; align-items:flex-start; font-size:12.8px;
  padding:3px 4px; border-radius:5px; cursor:pointer;
}
.opt:hover { background:var(--accent-soft); }
.opt input { margin-top:2px; }
.opt-num { font-weight:700; min-width:16px; flex:none; }
.insufficient {
  display:flex; gap:8px; align-items:flex-start; font-size:12.5px; margin-top:6px;
  padding-top:6px; border-top:1px dashed var(--border); color:var(--danger); cursor:pointer;
}
.notes-label { display:block; font-size:12.5px; margin-top:8px; }
.notes-label textarea {
  width:100%; font:inherit; font-size:12.5px; padding:6px 8px;
  border:1px solid var(--border); border-radius:6px; background:var(--bg);
  color:var(--fg); resize:vertical; margin-top:2px;
}
footer { margin:24px 16px; font-size:12px; color:var(--muted); }
</style>
</head>
<body data-rater="rater1">
"""


def _rubric_html() -> str:
    t_anchors = "\n".join(f"<li>{html.escape(a)}</li>" for a in RUBRIC_T["anchors"])
    g_anchors = "\n".join(f"<li>{html.escape(a)}</li>" for a in RUBRIC_G["anchors"])
    return f"""
<header class="topbar">
  <div>
    <span class="title">Validação cega — Latin.Science 2026</span>
    <span class="subtitle">Avaliar com base apenas no título e resumo. Não usar conhecimento externo sobre o artigo.</span>
  </div>
  <div class="topbar-controls">
    <label style="font-size:12.5px;">Avaliador:
      <select id="rater-select">
        <option value="rater1">Avaliador 1</option>
        <option value="rater2">Avaliador 2</option>
      </select>
    </label>
    <button id="export-btn" type="button">Exportar CSV</button>
    <button id="clear-btn" type="button">Limpar</button>
    <button id="theme-btn" type="button">Tema</button>
  </div>
  <div class="progress">
    <span class="progress-label" id="progress-text">0 / 0 concluídos</span>
    <div class="progress-bar"><div id="progress-fill"></div></div>
  </div>
</header>

<details class="rubric" open>
  <summary>Rubrica completa (T e G) — usar como referência ao avaliar</summary>
  <div class="rubric-body">
    <div class="rubric-block">
      <h4>{html.escape(RUBRIC_T['label'])}</h4>
      <ol>
{t_anchors}
      </ol>
    </div>
    <div class="rubric-block">
      <h4>{html.escape(RUBRIC_G['label'])}</h4>
      <ol>
{g_anchors}
      </ol>
    </div>
  </div>
  <p class="insufficient-hint">☐ {html.escape(INSUFFICIENT_LABEL)}. Marcada quando o título/resumo não permite decidir; é analisada como dado ausente.</p>
</details>

<main>
"""


def _paper_card(r: dict[str, Any]) -> str:
    fid = r["form_id"]
    sample = r["sample_type"]
    badge = "PILOTO" if sample == "pilot" else "CONFIRMATÓRIA"
    cls = "pilot" if sample == "pilot" else "confirm"
    title = html.escape(r["title"]) if r["title"] else "(sem título)"
    abstract = html.escape(r["abstract"]) if r["abstract"] else html.escape(MISSING_ABSTRACT_PLACEHOLDER)
    notice = (
        f'<p class="no-abstract-notice">{html.escape(NO_ABSTRACT_NOTICE)}</p>'
        if not r["has_abstract"]
        else ""
    )

    t_anchors = "\n".join(
        f'<label class="opt"><input type="radio" name="T-{fid}" value="{i + 1}">'
        f'<span class="opt-num">{i + 1}</span><span>{html.escape(anchor)}</span></label>'
        for i, anchor in enumerate(RUBRIC_T["anchors"])
    )
    g_anchors = "\n".join(
        f'<label class="opt"><input type="radio" name="G-{fid}" value="{i + 1}">'
        f'<span class="opt-num">{i + 1}</span><span>{html.escape(anchor)}</span></label>'
        for i, anchor in enumerate(RUBRIC_G["anchors"])
    )

    return f"""
<article class="paper" data-form-id="{fid}" data-sample="{sample}">
  <div class="paper-head">
    <span class="badge {cls}">{badge}</span>
    <span class="paper-id">ID: {fid}</span>
  </div>
  <h3 class="paper-title">{title}</h3>
  <div class="paper-abstract">{abstract}</div>
  {notice}
  <div class="axis-group tg-t">
    <div class="axis-title">Eixo T — {html.escape(RUBRIC_T['short'])} (1 = IA genérica → 5 = modelo nomeado)</div>
    <div class="likert">
{t_anchors}
    </div>
    <label class="insufficient"><input type="checkbox" data-axis="T"> {html.escape(INSUFFICIENT_LABEL)}</label>
  </div>
  <div class="axis-group tg-g">
    <div class="axis-title">Eixo G — {html.escape(RUBRIC_G['short'])} (1 = apoio ao fluxo → 5 = governança/integridade)</div>
    <div class="likert">
{g_anchors}
    </div>
    <label class="insufficient"><input type="checkbox" data-axis="G"> {html.escape(INSUFFICIENT_LABEL)}</label>
  </div>
  <label class="notes-label">Notas do avaliador:
    <textarea data-notes rows="2" placeholder="(opcional)"></textarea>
  </label>
</article>
"""


_HTML_SCRIPT = """<script>
(function () {
  "use strict";
  var PAPERS = __PAPERS_JSON__;
  var DEFAULTS = __DEFAULTS_JSON__;
  var PREFIX = "latin2026_validation_";

  var currentRater = "rater1";
  var ratings = {};

  function storageKey() { return PREFIX + currentRater; }

  function defaultFor(id) {
    var d = DEFAULTS[id] || {};
    return { T: null, G: null, insuffT: !!d.insuffT, insuffG: !!d.insuffG, notes: "" };
  }
  function defaultRatings() {
    var r = {};
    PAPERS.forEach(function (id) { r[id] = defaultFor(id); });
    return r;
  }
  function load() {
    try {
      var raw = localStorage.getItem(storageKey());
      if (raw) { ratings = JSON.parse(raw); return; }
    } catch (e) {}
    ratings = defaultRatings();
  }
  function save() {
    try { localStorage.setItem(storageKey(), JSON.stringify(ratings)); } catch (e) {}
  }

  function updateProgress() {
    var done = 0;
    PAPERS.forEach(function (id) {
      var r = ratings[id]; if (!r) return;
      var tDone = r.T !== null || r.insuffT;
      var gDone = r.G !== null || r.insuffG;
      if (tDone && gDone) done++;
    });
    var total = PAPERS.length;
    var pct = total ? Math.round(100 * done / total) : 0;
    document.getElementById("progress-text").textContent =
      done + " / " + total + " concluídos (" + pct + "%)";
    document.getElementById("progress-fill").style.width = pct + "%";
  }

  function updateCardState(card, id) {
    var r = ratings[id];
    var tRadios = card.querySelectorAll('input[name^="T-"]');
    var gRadios = card.querySelectorAll('input[name^="G-"]');
    var tIns = card.querySelector('input[data-axis="T"]');
    var gIns = card.querySelector('input[data-axis="G"]');
    var tg = card.querySelector(".axis-group.tg-t");
    var gg = card.querySelector(".axis-group.tg-g");
    tRadios.forEach(function (el) { el.disabled = !!r.insuffT; });
    gRadios.forEach(function (el) { el.disabled = !!r.insuffG; });
    if (tg) tg.classList.toggle("insuff", !!r.insuffT);
    if (gg) gg.classList.toggle("insuff", !!r.insuffG);
    if (tIns) tIns.checked = !!r.insuffT;
    if (gIns) gIns.checked = !!r.insuffG;
  }

  function applyToDom() {
    PAPERS.forEach(function (id) {
      var card = document.querySelector('.paper[data-form-id="' + id + '"]');
      if (!card) return;
      var r = ratings[id] || (ratings[id] = defaultFor(id));
      var tRadio = card.querySelector('input[name="T-' + id + '"][value="' + r.T + '"]');
      var gRadio = card.querySelector('input[name="G-' + id + '"][value="' + r.G + '"]');
      if (tRadio) tRadio.checked = true;
      if (gRadio) gRadio.checked = true;
      var notes = card.querySelector("textarea[data-notes]");
      if (notes) notes.value = r.notes || "";
      updateCardState(card, id);
    });
    updateProgress();
  }

  document.addEventListener("change", function (ev) {
    var el = ev.target;
    var card = el.closest(".paper");
    if (!card) return;
    var id = card.getAttribute("data-form-id");
    var r = ratings[id] || (ratings[id] = defaultFor(id));
    if (el.type === "radio") {
      if (el.name.indexOf("T-") === 0) r.T = parseInt(el.value, 10);
      else if (el.name.indexOf("G-") === 0) r.G = parseInt(el.value, 10);
    } else if (el.type === "checkbox") {
      var axis = el.getAttribute("data-axis");
      if (axis === "T") r.insuffT = el.checked;
      else if (axis === "G") r.insuffG = el.checked;
    }
    save(); updateCardState(card, id); updateProgress();
  });
  document.addEventListener("input", function (ev) {
    var el = ev.target;
    if (el.matches("textarea[data-notes]")) {
      var card = el.closest(".paper");
      var id = card.getAttribute("data-form-id");
      if (ratings[id]) ratings[id].notes = el.value;
      save();
    }
  });

  function csvEscape(v) {
    v = (v === null || v === undefined) ? "" : String(v);
    if (/[",\\n\\r]/.test(v)) v = '"' + v.replace(/"/g, '""') + '"';
    return v;
  }

  document.getElementById("export-btn").addEventListener("click", function () {
    var rows = [["form_id", "sample_type", "rater", "T", "G", "T_insufficient", "G_insufficient", "notes"]];
    PAPERS.forEach(function (id) {
      var card = document.querySelector('.paper[data-form-id="' + id + '"]');
      var sampleType = card ? card.getAttribute("data-sample") : "";
      var r = ratings[id] || defaultFor(id);
      var T = r.insuffT ? "" : (r.T === null ? "" : r.T);
      var G = r.insuffG ? "" : (r.G === null ? "" : r.G);
      var Tins = r.insuffT ? "1" : (r.T === null ? "" : "0");
      var Gins = r.insuffG ? "1" : (r.G === null ? "" : "0");
      rows.push([id, sampleType, currentRater, T, G, Tins, Gins, (r.notes || "")].map(csvEscape));
    });
    var csv = rows.map(function (row) { return row.join(","); }).join("\\r\\n");
    var blob = new Blob(["\\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    var ts = new Date().toISOString().slice(0, 10);
    a.href = URL.createObjectURL(blob);
    a.download = "validation_ratings_" + currentRater + "_" + ts + ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  });

  document.getElementById("clear-btn").addEventListener("click", function () {
    if (!window.confirm("Limpar todas as respostas deste avaliador?")) return;
    ratings = defaultRatings();
    save();
    applyToDom();
  });

  document.getElementById("theme-btn").addEventListener("click", function () {
    var cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", cur);
    try { localStorage.setItem(PREFIX + "theme", cur); } catch (e) {}
  });

  var raterSel = document.getElementById("rater-select");
  raterSel.addEventListener("change", function () {
    save();
    currentRater = raterSel.value;
    document.body.setAttribute("data-rater", currentRater);
    try { localStorage.setItem(PREFIX + "rater", currentRater); } catch (e) {}
    load();
    applyToDom();
  });

  function init() {
    try {
      var savedRater = localStorage.getItem(PREFIX + "rater");
      if (savedRater === "rater2") currentRater = "rater2";
    } catch (e) {}
    raterSel.value = currentRater;
    document.body.setAttribute("data-rater", currentRater);
    load();
    applyToDom();
  }
  document.addEventListener("DOMContentLoaded", init);
})();
</script>
"""


def _build_html(records: list[dict[str, Any]]) -> str:
    pilot = [r for r in records if r["sample_type"] == "pilot"]
    confirm = [r for r in records if r["sample_type"] == "confirmatory"]

    papers_js = json.dumps([r["form_id"] for r in records], ensure_ascii=True).replace("</", "<\\/")
    defaults_js = json.dumps(
        {
            r["form_id"]: {
                "insuffT": not r["has_abstract"],
                "insuffG": not r["has_abstract"],
            }
            for r in records
        },
        ensure_ascii=True,
    ).replace("</", "<\\/")

    parts = [_HTML_HEAD]
    parts.append(_rubric_html())
    parts.append("<main>")

    if pilot:
        parts.append('<section id="pilot" class="section">')
        parts.append(f"<h2>Rodada-piloto — {len(pilot)} textos</h2>")
        parts.append(
            '<p class="section-hint">Usar esta rodada para esclarecer a rubrica. '
            "Não misturar com a amostra confirmatória no relato.</p>"
        )
        parts.extend(_paper_card(r) for r in pilot)
        parts.append("</section>")

    if confirm:
        parts.append('<section id="confirmatory" class="section">')
        parts.append(f"<h2>Amostra confirmatória — {len(confirm)} textos</h2>")
        parts.append(
            '<p class="section-hint">Avaliar cada texto de forma independente, '
            "com base apenas no título e resumo.</p>"
        )
        parts.extend(_paper_card(r) for r in confirm)
        parts.append("</section>")

    parts.append("</main>")
    parts.append(
        _HTML_SCRIPT.replace("__PAPERS_JSON__", papers_js).replace("__DEFAULTS_JSON__", defaults_js)
    )
    parts.append("</body></html>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(
    paths: RunPaths,
    *,
    target_n: int = CONFIRMATORY_TARGET,
    min_n: int = CONFIRMATORY_MIN,
    pilot_n: int = PILOT_N,
    random_state: int = 42,
) -> None:
    """Generate the blinded human-validation form from the paper corpus.

    Parameters
    ----------
    paths:
        Run paths for the paper run.  ``corpus_paper_path`` must exist with the
        filtered paper corpus; T/G axis scores are read from it directly or from
        ``indicators/axis_scores.csv`` (with the v14 exploratory names as a
        fallback).
    target_n:
        Target number of confirmatory papers (default 300).
    min_n:
        Minimum acceptable confirmatory sample (default 200).  Reported in the
        metadata; no error is raised when the corpus is smaller than this.
    pilot_n:
        Size of the separate pilot sample at the beginning (default 20).
    random_state:
        Seed for the reproducible stratified sampling and random form ids.
    """
    ensure_run_dirs(paths)

    corpus_path = paths.corpus_paper_path
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Paper corpus not found: {corpus_path}. Run the screening stage first."
        )

    corpus = pd.read_csv(corpus_path)
    required = ["id", "title"]
    missing = [c for c in required if c not in corpus.columns]
    if missing:
        raise ValueError(f"Corpus missing required columns: {missing}")

    # Resolve axis columns (paper names -> v14 fallbacks -> axis_scores.csv).
    corpus, t_col, g_col, axis_note = _attach_axis_scores(corpus, paths)

    n_before_scores = len(corpus)
    corpus = corpus.dropna(subset=[t_col, g_col])
    n_dropped_missing_scores = n_before_scores - len(corpus)
    if corpus.empty:
        raise ValueError(
            f"No papers with both T and G axis scores ({t_col!r} / {g_col!r}) "
            f"available for validation in {corpus_path}."
        )

    corpus = corpus.reset_index(drop=True)
    corpus = _prepare_abstracts(corpus)

    # Corpus-wide strata used by both sampling and metadata.
    if "publication_year" in corpus.columns:
        corpus["_cohort"] = corpus["publication_year"].map(_year_cohort)
    else:
        corpus["_cohort"] = "unknown"
    if "data_source" in corpus.columns:
        corpus["_source"] = corpus["data_source"].map(_clean_source)
    else:
        corpus["_source"] = "unknown"
    corpus["_tq"] = _score_quintile(corpus[t_col])
    corpus["_gq"] = _score_quintile(corpus[g_col])

    n_available = len(corpus)
    pilot_actual = min(pilot_n, n_available)
    confirmatory_actual = min(target_n, max(0, n_available - pilot_actual))

    rng = np.random.default_rng(random_state)
    py_rng = random.Random(random_state)

    # Draw the pilot first, then the confirmatory sample from the remainder so
    # the two samples are disjoint.
    pilot_idx = _sample_stratified(corpus, pilot_actual, rng, t_col, g_col)
    pilot_mask = corpus.index.isin(pilot_idx)
    remain = corpus[~pilot_mask].copy()
    confirm_idx = _sample_stratified(remain, confirmatory_actual, rng, t_col, g_col)

    used_form_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for idx in pilot_idx:
        records.append(
            _build_record(corpus, idx, "pilot", _new_form_id(py_rng, used_form_ids), t_col, g_col)
        )
    for idx in confirm_idx:
        records.append(
            _build_record(
                corpus, idx, "confirmatory", _new_form_id(py_rng, used_form_ids), t_col, g_col
            )
        )

    # ------------------------------------------------------------------ CSV
    collection = pd.DataFrame(
        [
            {
                "form_id": r["form_id"],
                "corpus_id": r["corpus_id"],
                "sample_type": r["sample_type"],
                "title": r["title"],
                "abstract": r["abstract"],
            }
            for r in records
        ]
    )
    rater_cols = [
        "rater1_T",
        "rater1_G",
        "rater1_T_insufficient",
        "rater1_G_insufficient",
        "rater2_T",
        "rater2_G",
        "rater2_T_insufficient",
        "rater2_G_insufficient",
        "notes",
    ]
    for col in rater_cols:
        collection[col] = np.nan
    collection = collection[COLLECTION_COLUMNS]
    collection.to_csv(paths.indicators_dir / "validation_form.csv", index=False)

    # ------------------------------------------------------------------ HTML
    html_text = _build_html(records)
    (paths.indicators_dir / "validation_form.html").write_text(html_text, encoding="utf-8")

    # --------------------------------------------------------------- metadata
    sample_df = pd.DataFrame(
        [
            {
                "form_id": r["form_id"],
                "sample_type": r["sample_type"],
                "year_cohort": r["year_cohort"],
                "data_source": r["data_source"],
                "t_quintile": r["t_quintile"],
                "g_quintile": r["g_quintile"],
            }
            for r in records
        ]
    )

    metadata: dict[str, Any] = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_corpus": str(corpus_path),
        "axis_columns": {"T": t_col, "G": g_col, "provenance": axis_note},
        "sampling_parameters": {
            "confirmatory_target": target_n,
            "confirmatory_minimum": min_n,
            "pilot_target": pilot_n,
            "axis_quintiles": AXIS_QUINTILES,
            "random_state": random_state,
            "year_cohorts": {k: list(v) for k, v in YEAR_COHORT_RANGES.items()},
        },
        "corpus_summary": {
            "n_corpus_with_scores": n_available,
            "n_dropped_missing_axis_score": n_dropped_missing_scores,
            "n_missing_abstract": int((~corpus["_has_abstract"]).sum()),
            "n_available_before_score_filter": n_before_scores,
        },
        "sample": {
            "n_total": len(records),
            "n_pilot": pilot_actual,
            "n_confirmatory": confirmatory_actual,
            "target_met": bool(confirmatory_actual >= min_n),
            "below_minimum": bool(n_available < min_n + pilot_actual),
            "axis_note": axis_note,
        },
        "stratification_counts": {
            "corpus_by_year_cohort": _counts(corpus["_cohort"]),
            "corpus_by_data_source": _counts(corpus["_source"]),
            "corpus_by_t_quintile": _counts(corpus["_tq"]),
            "corpus_by_g_quintile": _counts(corpus["_gq"]),
            "sample_by_year_cohort": _counts(sample_df["year_cohort"]),
            "sample_by_data_source": _counts(sample_df["data_source"]),
            "sample_by_t_quintile": _counts(sample_df["t_quintile"]),
            "sample_by_g_quintile": _counts(sample_df["g_quintile"]),
            "pilot_by_year_cohort": _counts(
                sample_df.loc[sample_df["sample_type"] == "pilot", "year_cohort"]
            ),
            "confirmatory_by_year_cohort": _counts(
                sample_df.loc[sample_df["sample_type"] == "confirmatory", "year_cohort"]
            ),
        },
        "rubric": {
            "T": RUBRIC_T,
            "G": RUBRIC_G,
            "insufficient_option": INSUFFICIENT_LABEL,
        },
        "split": {
            "pilot_form_ids": [r["form_id"] for r in records if r["sample_type"] == "pilot"],
            "confirmatory_form_ids": [
                r["form_id"] for r in records if r["sample_type"] == "confirmatory"
            ],
        },
        "papers": [
            {
                "form_id": r["form_id"],
                "corpus_id": r["corpus_id"],
                "sample_type": r["sample_type"],
                "has_abstract": r["has_abstract"],
                "publication_year": r["publication_year"],
                "stratum": {
                    "year_cohort": r["year_cohort"],
                    "data_source": r["data_source"],
                    "t_quintile": r["t_quintile"],
                    "g_quintile": r["g_quintile"],
                },
                "automatic_scores": {"T": r["axis_t"], "G": r["axis_g"]},
            }
            for r in records
        ],
    }
    write_json(paths.indicators_dir / "validation_metadata.json", metadata)

    # ---------------------------------------------------------------- report
    print(f"Saved: {paths.indicators_dir / 'validation_form.csv'}")
    print(f"Saved: {paths.indicators_dir / 'validation_form.html'}")
    print(f"Saved: {paths.indicators_dir / 'validation_metadata.json'}")
    print(
        f"Validation form: {confirmatory_actual} confirmatory + {pilot_actual} pilot papers "
        f"(axes {t_col!r} / {g_col!r}; {axis_note})."
    )
    if confirmatory_actual < min_n:
        print(
            f"NOTE: confirmatory sample ({confirmatory_actual}) is below the paper "
            f"minimum ({min_n}); the corpus only had {n_available} scored papers."
        )
