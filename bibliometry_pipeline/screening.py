"""Screening stage for the Latin.Science 2026 paper corpus.

The paper (see ``NOTES/latin_science_full_paper_plan.md``) restricts its
population of interest to articles and reviews that discuss AI applied to
scholarly communication, scientific publishing, academic writing, peer review,
evidence synthesis as a *research* activity, research integrity/governance, or
institutional use of generative AI in higher education tied to academic writing
and assessment.  Everything else (clinical AI, engineering/industrial AI, EFL
pedagogy) must be excluded *before* any semantic analysis.

This module consumes the already-clustered corpus produced by the fetch/clean/
enrich/embed stages (``corpus_clustered.csv``) and turns the paper's scope rules
into a versioned, auditable decision table plus a filtered corpus for the
paper's own analyses.

Decision model
--------------

Screening is LEXICAL-FIRST: a paper's scope is decided by the positive and
negative scope rules in ``config.py`` applied to its ``title + abstract``.  The
cluster assignment is carried through the decision table purely as
*informational* context — the v14 audit (NOTES/screening_audit_report.md §1/§5.3)
found the clusters are contaminated in both directions (~387 out-of-scope papers
in clusters 3+4 and ~152 in-scope papers in clusters 0-2), so cluster membership
must not drive the decision.

For every record the following logic is applied (audit §5.3; the category-aware
override logic is grounded in three independent review slices under
``runs/latin_science_2026/indicators/review_slice_{a,b,c}_report.md``):

1. Integrity/quality filters (highest priority, every record): retracted,
   missing/too-short abstract, low-quality abstract, hard off-topic title,
   publication year outside the paper window.
2. Positive scope signal: any ``POSITIVE_SCOPE_RULES`` match on title+abstract.
3. Negative scope signal: any ``HARD_NEGATIVE_SCOPE_RULES`` match.
4. AI signal: the corpus is *AI applied to* scholarly communication, so a paper
   with a positive scope hit but no ``AI_SIGNAL_RULES`` match is flagged
   (reason ``no_ai_signal``): a strong scholarly-communication category
   (``STRONG_AI_REQUIRED_CATEGORIES``) -> ``needs_review`` (likely pre-AI
   authorship/integrity papers), otherwise -> ``exclude``.
5. Decision:
   * neither signal       -> ``exclude`` (reason ``no_scope_signal``)
   * negative signal only -> ``exclude`` (reason ``hard_negative:<rules>``)
   * positive signal only -> ``include``
   * both signals         -> category-aware override:
     + any matched positive category in ``POSITIVE_OVERRIDES`` that covers all
       matched negative categories -> ``include`` (e.g. ``research_writing`` +
       ``medical``: the medical tag fires on domain vocabulary, not clinical
       intent — Review B found 12/14 such papers are genuine scholarly-writing
       papers).
     + any matched positive category in ``NEGATIVE_OVERRIDES`` that covers all
       matched negative categories -> ``exclude`` (e.g. ``research_workflow`` +
       ``medical``: method-word positives that must not beat a true
       hard-negative — Review A found 44/50 are clinical systematic reviews).
     + otherwise -> ``needs_review`` (reason
       ``positive:<rules>|negative:<rules>``).

Outputs (all written to the run directory/indicators dir):

* ``screening_decisions.csv`` — one row per paper with a machine-readable
  ``decision`` (include/exclude/needs_review) and ``reason`` code, plus the
  positive/negative scope rules that fired.  This file is intended to be
  version-controlled and human-audited (the paper mandates a blind audit of
  >= 50 included and >= 50 excluded records).
* ``indicators/corpus_paper.csv`` — the filtered corpus (include + needs_review)
  with the decision columns appended, consumed by downstream paper analyses.
* ``indicators/screening_audit.json`` — audit statistics (totals, exclusions by
  reason, and year/source/cluster distributions of the included set).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .config import (
    AI_SIGNAL_RULES,
    HARD_NEGATIVE_SCOPE_RULES,
    HARD_OFFTOPIC_TITLE_RE,
    LOW_QUALITY_ABSTRACT_RE,
    MIN_ABSTRACT_LENGTH,
    POSITIVE_SCOPE_RULES,
    RETRACTED_TITLE_RE,
    YEAR_MAX,
    YEAR_MIN,
)
from .paths import RunPaths, ensure_run_dirs
from .utils import clean_html_text, write_json

# ---------------------------------------------------------------------------
# Screening constants
# ---------------------------------------------------------------------------

# Source clustered corpus used when the paper run directory is empty (the paper
# run starts fresh and consumes the v14 corpus).
DEFAULT_SOURCE_RUN = "academic_production_v14"

# Bump whenever the screening rules change so that audit files are comparable.
SCREENING_VERSION = "2.2"

DECISION_INCLUDE = "include"
DECISION_EXCLUDE = "exclude"
DECISION_NEEDS_REVIEW = "needs_review"

# Machine-readable reason codes.  ``hard_negative`` is always suffixed with the
# specific rules, e.g. ``hard_negative:medical|industrial``.  A borderline
# record with both positive and negative scope signals that survives the
# category-aware overrides uses the ``positive:<rules>|negative:<rules>``
# format (audit §5.3).  ``no_ai_signal`` flags a positive-scope paper that
# mentions no AI at all (the corpus is *AI applied to* scholarly communication).
REASON_RETRACTED = "retracted"
REASON_MISSING_ABSTRACT = "missing_abstract"
REASON_LOW_QUALITY_ABSTRACT = "low_quality_abstract"
REASON_OFFTOPIC_TITLE = "hard_offtopic_title"
REASON_YEAR_OUT_OF_RANGE = "year_out_of_range"
REASON_HARD_NEGATIVE = "hard_negative"
REASON_NO_SCOPE_SIGNAL = "no_scope_signal"
REASON_NO_AI_SIGNAL = "no_ai_signal"

# Legacy advisory set: names the scholarly-communication categories whose
# conflict with a hard-negative a human reviewer should treat as a probable
# false negative.  Kept for the audit file's ``rules_used`` schema; the actual
# include/exclude precedence is now decided by the explicit
# ``POSITIVE_OVERRIDES`` / ``NEGATIVE_OVERRIDES`` tables below (grounded in the
# three independent review slices,
# runs/latin_science_2026/indicators/review_slice_{a,b,c}_report.md).
STRONG_POSITIVE_OVERRIDE_CATEGORIES = frozenset({
    "research_writing",
    "integrity_governance",
    "research_workflow",
    "evidence_synthesis",
    "scholarly_publishing",
})

# Category-aware override: when BOTH positive and negative scope rules fire, the
# decision depends on *which* positive category matched.  Each entry maps a
# matched positive category to the set of negative categories it overrides — the
# positive rule wins (INCLUDE) only when every matched negative category is in
# that set.  Review-based rationale is documented per entry below.
POSITIVE_OVERRIDES = {
    # research_writing + medical -> INCLUDE: "medical writing" IS scholarly
    # communication.  Review B found 12/14 of these papers are genuine
    # scholarly-writing / AI-in-writing papers; the medical tag fires on domain
    # vocabulary ("medical", "clinical", "healthcare"), not clinical intent.
    "research_writing": {"medical"},
    # scholarly_publishing + medical -> INCLUDE: journal/editorial-policy and
    # medical-writing papers in medical journals are scholarly communication
    # even when the medical hard-negative fires on their domain vocabulary.
    "scholarly_publishing": {"medical"},
}

# Negative override: when BOTH signals fire, the negative tag is the true signal
# and beats the matched positive category (EXCLUDE) whenever every matched
# positive category is in the listed set.
NEGATIVE_OVERRIDES = {
    # research_workflow + medical -> EXCLUDE: clinical systematic reviews embed
    # "literature search" / "peer review" method language that fires
    # research_workflow, but their object is clinical AI.  Review A found 44/50
    # are clinical systematic reviews, not scholarly communication.
    "research_workflow": {"medical"},
    # integrity_governance + industrial -> EXCLUDE: industrial negatives are
    # genuine.  Review C found 4/6 industrial-tagged integrity papers are
    # correctly excluded (the ~2 IN cases are lexical artifacts — "arms race" /
    # "policing" metaphors — too rare to justify keeping the rest).
    "integrity_governance": {"industrial"},
    # evidence_synthesis + medical -> EXCLUDE: Review D found 114/135 (84%) are
    # clinical systematic reviews where AI is the clinical subject being surveyed
    # (diagnostic performance, outcome prediction, imaging analysis), not the
    # tool doing the evidence-synthesis work.  The positive rule fires on SR
    # methodology vocabulary ("screening", "PRISMA", "evidence synthesis").
    "evidence_synthesis": {"medical"},
    # ai_literacy + medical -> EXCLUDE: Review FG found 14/14 are health/clinical
    # AI literacy (radiology, dermatology, nursing, pharmacy) — no academic
    # writing, assessment, or scholarly integrity component.
    # ai_literacy + language_learning -> EXCLUDE: Review FG found 4/4 are
    # EFL/ESL skills, teacher PD, or translation — no substantive academic
    # writing or integrity link.
    "ai_literacy": {"medical", "language_learning"},
}

# Strong scholarly-communication categories for the AI-signal requirement.  The
# corpus is *AI applied to* scholarly communication, so a paper that matches a
# positive rule but names no AI at all is likely a pre-AI authorship/integrity
# paper (Review C §2 found three such medical-tagged papers) or a method-word
# false positive.  Strong categories get a human look (``needs_review``, reason
# ``no_ai_signal``); weak positives (research_workflow, evidence_synthesis) are
# auto-excluded with the same reason.
STRONG_AI_REQUIRED_CATEGORIES = frozenset({
    "research_writing",
    "integrity_governance",
    "scholarly_publishing",
})

# Column layout of the versioned decision table.
SCREENING_DECISIONS_COLUMNS = [
    "id",
    "title",
    "source",
    "decision",
    "reason",
    "responsible",
    "cluster",
    "publication_year",
    "scope_positive_hits",
    "scope_negative_hits",
    "positive_rules_matched",
    "negative_rules_matched",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _resolve_source_corpus(paths: RunPaths, source_run: str | Path | None) -> Path:
    """Resolve the clustered corpus to screen.

    ``source_run`` may point at a run directory (containing
    ``corpus_clustered.csv``) or directly at a CSV file.  When omitted, the
    current run's own ``corpus_clustered.csv`` is used if present, otherwise the
    default v14 corpus.
    """
    if source_run is not None:
        path = Path(source_run)
        if not path.is_absolute():
            path = paths.root / path
        if path.is_dir():
            path = path / "corpus_clustered.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Screening source corpus not found: {path}. "
                "Pass source_run=<run dir or CSV>."
            )
        return path

    if paths.corpus_clustered_path.exists():
        return paths.corpus_clustered_path

    default = paths.root / "runs" / DEFAULT_SOURCE_RUN / "corpus_clustered.csv"
    if not default.exists():
        raise FileNotFoundError(
            f"No clustered corpus in {paths.corpus_clustered_path} and default "
            f"source missing: {default}. Pass source_run=..."
        )
    return default


def _clean_abstract(abstract: object) -> str:
    text = "" if abstract is None else str(abstract)
    return clean_html_text(text)


def _has_ai_signal(title: str, abstract: str) -> bool:
    """Return True if any ``AI_SIGNAL_RULES`` matches ``title + abstract``.

    The corpus is *AI applied to* scholarly communication, so a paper that
    matches a positive scope rule but names no AI at all is out of scope (or at
    least needs a human) rather than auto-included (Review A §3.3).
    """
    text = f"{title} {abstract}"
    return any(rule.search(text) for rule in AI_SIGNAL_RULES.values())


def _classify(row: pd.Series) -> tuple[str, str, str, str]:
    """Return ``(decision, reason, positive_rules_matched, negative_rules_matched)``.

    Scope is decided lexically from ``title + abstract`` (audit §5.3; the
    category-aware override logic is grounded in the three independent review
    slices, runs/latin_science_2026/indicators/review_slice_{a,b,c}_report.md).
    The ``cluster`` column is deliberately *not* consulted for the decision — it
    is carried through the output as informational context only.
    """
    title = str(row.get("title") or "")
    abstract = str(row.get("abstract") or "")

    # -- 1. Integrity / quality filters (highest priority, every record) ------
    if RETRACTED_TITLE_RE.search(title):
        return DECISION_EXCLUDE, REASON_RETRACTED, "", ""
    if len(_clean_abstract(abstract)) < MIN_ABSTRACT_LENGTH:
        return DECISION_EXCLUDE, REASON_MISSING_ABSTRACT, "", ""
    if LOW_QUALITY_ABSTRACT_RE.search(abstract):
        return DECISION_EXCLUDE, REASON_LOW_QUALITY_ABSTRACT, "", ""
    if HARD_OFFTOPIC_TITLE_RE.search(title):
        return DECISION_EXCLUDE, REASON_OFFTOPIC_TITLE, "", ""

    year_raw = row.get("publication_year")
    if pd.notna(year_raw):
        year = int(year_raw)
        if not (YEAR_MIN <= year <= YEAR_MAX):
            return DECISION_EXCLUDE, REASON_YEAR_OUT_OF_RANGE, "", ""

    # -- 2. Lexical scope signals (title + abstract) --------------------------
    clean_abstract = _clean_abstract(abstract)
    search_text = f"{title} {clean_abstract}"
    pos_hits = [
        name
        for name, rule in POSITIVE_SCOPE_RULES.items()
        if rule.search(search_text)
    ]
    neg_hits = [
        name
        for name, rule in HARD_NEGATIVE_SCOPE_RULES.items()
        if rule.search(search_text)
    ]
    has_positive = bool(pos_hits)
    has_negative = bool(neg_hits)
    pos_matched = ",".join(pos_hits)
    neg_matched = ",".join(neg_hits)

    # -- 3. AI signal requirement (the corpus is *AI applied to* scholarship) --
    # A paper with a positive scope hit but no AI signal is outside the paper's
    # population: either a pre-AI scholarly-integrity/authorship paper (Review C
    # §2 found three medical-tagged examples) or a method-word false positive.
    # Strong scholarly-communication categories are routed to a human; weak
    # positives are excluded outright (Review A §3.3).
    if has_positive and not _has_ai_signal(title, clean_abstract):
        if any(pos in STRONG_AI_REQUIRED_CATEGORIES for pos in pos_hits):
            return DECISION_NEEDS_REVIEW, REASON_NO_AI_SIGNAL, pos_matched, neg_matched
        return DECISION_EXCLUDE, REASON_NO_AI_SIGNAL, pos_matched, neg_matched

    # -- 4. Decision (NOTES/screening_audit_report.md §5.3) -------------------
    if not has_positive and not has_negative:
        # No scope signal either way.  Review C §3: 25/30 no-scope-signal papers
        # are true negatives; the ~3 in-scope misses are better caught by
        # improving positive rules than by manually reviewing the whole corpus.
        return DECISION_EXCLUDE, REASON_NO_SCOPE_SIGNAL, "", ""

    if not has_positive and has_negative:
        # Only a negative signal — out of scope.
        return (
            DECISION_EXCLUDE,
            f"{REASON_HARD_NEGATIVE}:{'|'.join(neg_hits)}",
            "",
            neg_matched,
        )

    if has_positive and not has_negative:
        # Only a positive signal (AI signal already confirmed above) — in scope.
        return DECISION_INCLUDE, "", pos_matched, ""

    # -- Both positive and negative signals: category-aware override. ---------
    # The negative rules are context-blind and routinely fire on domain
    # vocabulary (e.g. "medical" from a journal name) even for genuinely
    # in-scope papers, but three independent reviewers audited 160 such papers
    # and found the outcome depends on *which* positive category matched.
    neg_set = set(neg_hits)

    # (a) Positive override wins -> INCLUDE.  research_writing + medical:
    # Review B found 12/14 are genuine scholarly-writing/AI-in-writing papers
    # (medical writing IS scholarly communication); scholarly_publishing +
    # medical: journal/editorial-policy and medical-writing papers in medical
    # journals are scholarly communication.
    for pos in pos_hits:
        if pos in POSITIVE_OVERRIDES and neg_set <= POSITIVE_OVERRIDES[pos]:
            return DECISION_INCLUDE, "", pos_matched, neg_matched

    # (b) Negative override wins -> EXCLUDE.  research_workflow + medical:
    # Review A found 44/50 are clinical systematic reviews whose "literature
    # search"/"peer review" method language fires the positive rule — the object
    # is clinical AI, not scholarly communication.  integrity_governance +
    # industrial: Review C found 4/6 industrial negatives are genuine.
    for pos in pos_hits:
        if pos in NEGATIVE_OVERRIDES and neg_set <= NEGATIVE_OVERRIDES[pos]:
            return (
                DECISION_EXCLUDE,
                f"{REASON_HARD_NEGATIVE}:{'|'.join(neg_hits)}",
                pos_matched,
                neg_matched,
            )

    # (c) Unresolved conflict — escalate for human review.
    return (
        DECISION_NEEDS_REVIEW,
        f"positive:{'|'.join(pos_hits)}|negative:{'|'.join(neg_hits)}",
        pos_matched,
        neg_matched,
    )


def _build_audit(decisions: pd.DataFrame, source_path: Path) -> dict:
    total = len(decisions)
    n_included = int((decisions["decision"] == DECISION_INCLUDE).sum())
    n_needs_review = int((decisions["decision"] == DECISION_NEEDS_REVIEW).sum())
    n_excluded = int((decisions["decision"] == DECISION_EXCLUDE).sum())

    excluded = decisions[decisions["decision"] == DECISION_EXCLUDE]
    included = decisions[decisions["decision"] == DECISION_INCLUDE]

    excluded_by_reason = excluded["reason"].value_counts().to_dict()
    included_year = (
        included["publication_year"].dropna().astype(int).value_counts().sort_index()
    )
    included_source = included["source"].value_counts()
    included_cluster = (
        included["cluster"].dropna().astype(int).value_counts().sort_index()
    )

    return {
        "screening_version": SCREENING_VERSION,
        "source_corpus": str(source_path),
        "rules_used": {
            "positive_scope_rules": list(POSITIVE_SCOPE_RULES.keys()),
            "hard_negative_scope_rules": list(HARD_NEGATIVE_SCOPE_RULES.keys()),
            "ai_signal_rules": list(AI_SIGNAL_RULES.keys()),
            "hard_offtopic_title_re": True,
            "retracted_title_re": True,
            "low_quality_abstract_re": True,
            "min_abstract_length": MIN_ABSTRACT_LENGTH,
            "year_range": [YEAR_MIN, YEAR_MAX],
            "positive_override_categories": {
                k: sorted(v) for k, v in POSITIVE_OVERRIDES.items()
            },
            "negative_override_categories": {
                k: sorted(v) for k, v in NEGATIVE_OVERRIDES.items()
            },
            "strong_ai_required_categories": sorted(STRONG_AI_REQUIRED_CATEGORIES),
            "strong_positive_override_categories": sorted(STRONG_POSITIVE_OVERRIDE_CATEGORIES),
        },
        "n_total": total,
        "n_included": n_included,
        "included_pct": round(100 * n_included / total, 2) if total else 0.0,
        "n_needs_review": n_needs_review,
        "n_excluded": n_excluded,
        "excluded_by_reason": {str(k): int(v) for k, v in excluded_by_reason.items()},
        "included_year_distribution": {str(k): int(v) for k, v in included_year.items()},
        "included_source_distribution": {str(k): int(v) for k, v in included_source.items()},
        "included_cluster_distribution": {str(k): int(v) for k, v in included_cluster.items()},
    }


def _print_audit(stats: dict) -> None:
    print("\n=== SCREENING AUDIT (Latin.Science 2026) ===")
    print(f"Total papers screened : {stats['n_total']}")
    print(f"Included             : {stats['n_included']} ({stats['included_pct']}%)")
    print(f"Needs review         : {stats['n_needs_review']}")
    print(f"Excluded             : {stats['n_excluded']}")
    print("\nExcluded by reason:")
    for reason, count in stats["excluded_by_reason"].items():
        print(f"  {reason}: {count}")
    print("\nIncluded by year:")
    for year, count in stats["included_year_distribution"].items():
        print(f"  {year}: {count}")
    print("\nIncluded by source:")
    for source, count in stats["included_source_distribution"].items():
        print(f"  {source}: {count}")
    print("\nIncluded by cluster:")
    for cluster, count in stats["included_cluster_distribution"].items():
        print(f"  {cluster}: {count}")
    print("=" * 45)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(paths: RunPaths, source_run: str | Path | None = None) -> dict:
    """Screen the clustered corpus and emit the versioned screening artifacts.

    Parameters
    ----------
    paths:
        Run paths for the paper run.  ``run_dir`` may be empty; the clustered
        corpus is then read from the default v14 run (see
        ``_resolve_source_corpus``).
    source_run:
        Optional override for the source corpus: a run directory containing
        ``corpus_clustered.csv``, or a direct path to the CSV.

    Returns
    -------
    dict
        The audit statistics (also saved to ``screening_audit.json``).
    """
    ensure_run_dirs(paths)

    # Prefer UTF-8 stdout so cluster labels (e.g. "·" separators) and other
    # non-ASCII text render correctly on Windows consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    source_path = _resolve_source_corpus(paths, source_run)
    print(f"[screening] Source corpus: {source_path}")

    corpus = pd.read_csv(source_path)
    required = ["id", "title", "data_source", "cluster", "publication_year"]
    missing = [col for col in required if col not in corpus.columns]
    if missing:
        raise ValueError(f"Screening corpus missing required columns: {missing}")

    # Build the decision columns. A plain apply+list comprehension keeps the
    # column layout correct even when the corpus is empty (result_type="expand"
    # does not preserve shape on empty frames).
    classified = pd.DataFrame(
        corpus.apply(_classify, axis=1).tolist(),
        columns=["decision", "reason", "positive_rules_matched", "negative_rules_matched"],
    )

    decisions = pd.DataFrame(
        {
            "id": corpus["id"],
            "title": corpus["title"].fillna(""),
            "source": corpus["data_source"].fillna(""),
            "decision": classified["decision"],
            "reason": classified["reason"],
            "responsible": "",
            "cluster": corpus["cluster"],
            "publication_year": pd.to_numeric(
                corpus["publication_year"], errors="coerce"
            ),
            "scope_positive_hits": (
                corpus["scope_positive_hits"].fillna("")
                if "scope_positive_hits" in corpus.columns
                else ""
            ),
            "scope_negative_hits": (
                corpus["scope_negative_hits"].fillna("")
                if "scope_negative_hits" in corpus.columns
                else ""
            ),
            "positive_rules_matched": classified["positive_rules_matched"],
            "negative_rules_matched": classified["negative_rules_matched"],
        }
    )
    decisions = decisions[SCREENING_DECISIONS_COLUMNS]

    decisions.to_csv(paths.screening_decisions_path, index=False)
    print(f"Saved: {paths.screening_decisions_path}")

    # -- Filtered corpus for the paper: include + needs_review ----------------
    keep = decisions["decision"].isin({DECISION_INCLUDE, DECISION_NEEDS_REVIEW})
    keep_idx = decisions.index[keep]
    paper_corpus = corpus.loc[keep_idx].copy()
    paper_corpus["decision"] = decisions.loc[keep_idx, "decision"].values
    paper_corpus["screening_reason"] = decisions.loc[keep_idx, "reason"].values
    paper_corpus.to_csv(paths.corpus_paper_path, index=False)
    print(f"Saved: {paths.corpus_paper_path}")

    # -- Audit statistics -----------------------------------------------------
    stats = _build_audit(decisions, source_path)
    write_json(paths.screening_audit_path, stats)
    print(f"Saved: {paths.screening_audit_path}")

    _print_audit(stats)
    return stats
