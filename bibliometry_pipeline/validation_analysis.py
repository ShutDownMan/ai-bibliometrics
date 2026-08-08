"""Validation analysis for the Latin.Science 2026 paper.

Computes inter-rater agreement, convergent validity, and calibration metrics
between automated semantic-axis scores and blind human Likert ratings.

Metrics reported (per the paper plan § "Critérios de validação"):
- Krippendorff's alpha (ordinal) or weighted kappa between raters
- Spearman correlation between automated score and human mean
- Mean absolute error after rescaling automated score to 1–5
- AUC for binary classification (1–2 vs 4–5, excluding 3)
- Calibration: human mean by quintile of automated score
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from .paths import RunPaths, ensure_run_dirs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIKERT_RANGE = (1, 5)
BINARY_LOW = (1, 2)
BINARY_HIGH = (4, 5)
N_BOOTSTRAP = 2000
CI_ALPHA = 0.05  # 95% CI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rescale_to_likert(scores: np.ndarray, likert_min: int = 1, likert_max: int = 5) -> np.ndarray:
    """Linearly rescale continuous scores to the Likert range."""
    s_min, s_max = scores.min(), scores.max()
    if s_max - s_min < 1e-9:
        return np.full_like(scores, (likert_min + likert_max) / 2.0)
    return likert_min + (likert_max - likert_min) * (scores - s_min) / (s_max - s_min)


def _bootstrap_ci(data: np.ndarray, statistic_fn, n_bootstrap: int = N_BOOTSTRAP, alpha: float = CI_ALPHA):
    """Bootstrap confidence interval for a statistic computed on paired arrays or a single array.

    ``data`` should be a 2D array of shape (n_observations, n_variables) for
    statistics that need multiple columns (e.g. correlation), or 1D for
    single-array statistics.
    """
    n = len(data)
    stats = []
    rng = np.random.default_rng(42)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sample = data[idx]
        try:
            stats.append(statistic_fn(sample))
        except (ValueError, ZeroDivisionError):
            continue
    stats = np.array(stats)
    stats = stats[~np.isnan(stats)]
    lo = np.percentile(stats, 100 * alpha / 2)
    hi = np.percentile(stats, 100 * (1 - alpha / 2))
    return np.mean(stats), lo, hi


def _weighted_kappa(r1: np.ndarray, r2: np.ndarray) -> float:
    """Quadratic-weighted kappa using scipy cohen_kappa with quadratic weights."""
    from sklearn.metrics import cohen_kappa_score
    return cohen_kappa_score(r1, r2, weights="quadratic")


def _krippendorff_alpha_ordinal(ratings: np.ndarray) -> float:
    """Krippendorff's alpha for ordinal data (simplified computation).

    ``ratings`` shape: (n_items, n_raters). NaN entries are treated as missing.
    """
    # Simple ordinal alpha via the agreement coefficient.
    # Uses the identity metric for ordinal (squared-difference weighting).
    n_items, n_raters = ratings.shape
    if n_items < 2 or n_raters < 2:
        return np.nan

    # Flatten to pairs
    mask = ~np.isnan(ratings)
    n_valid = mask.sum()

    # Mean per item (over raters who rated it)
    item_means = np.nanmean(ratings, axis=1)
    grand_mean = np.nanmean(ratings)

    # Observed disagreement
    do = 0.0
    count = 0
    for i in range(n_items):
        for r1 in range(n_raters):
            for r2 in range(n_raters):
                if r1 >= r2:
                    continue
                if mask[i, r1] and mask[i, r2]:
                    do += (ratings[i, r1] - ratings[i, r2]) ** 2
                    count += 1
    if count == 0:
        return np.nan
    do /= count

    # Expected disagreement
    de = 0.0
    count_e = 0
    for i in range(n_items):
        for r1 in range(n_raters):
            for r2 in range(n_raters):
                if r1 == r2:
                    continue
                if mask[i, r1]:
                    # Compare with all possible values from other items
                    for j in range(n_items):
                        if mask[j, r2]:
                            de += (ratings[i, r1] - ratings[j, r2]) ** 2
                            count_e += 1
    if count_e == 0:
        return np.nan
    de /= count_e

    if de < 1e-9:
        return 1.0 if do < 1e-9 else 0.0

    return 1.0 - do / de


def _compute_auc(y_true_binary: np.ndarray, y_score: np.ndarray) -> float:
    """ROC AUC for binary classification."""
    try:
        from sklearn.metrics import roc_auc_score
        return roc_auc_score(y_true_binary, y_score)
    except (ImportError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def run_validation_analysis(
    validation_form_path: Path,
    axis_scores_path: Path,
    output_dir: Path,
) -> dict:
    """Run the full validation analysis.

    Parameters
    ----------
    validation_form_path:
        Path to ``validation_form.csv`` with rater columns filled (``rater1_T``,
        ``rater1_G``, ``rater2_T``, ``rater2_G``).
    axis_scores_path:
        Path to ``axis_scores.csv`` with automated ``axis_t_technology`` and
        ``axis_g_governance`` columns.
    output_dir:
        Directory for output files.

    Returns
    -------
    dict
        Validation metrics for both axes.
    """
    vf = pd.read_csv(validation_form_path)
    axis = pd.read_csv(axis_scores_path)

    # Merge automated scores
    vf = vf.merge(
        axis[["id", "axis_t_technology", "axis_g_governance"]],
        left_on="corpus_id",
        right_on="id",
        how="left",
        suffixes=("", "_auto"),
    )

    results = {}
    for axis_name, axis_col, rater1_col, rater2_col, insuf1_col, insuf2_col in [
        ("T", "axis_t_technology", "rater1_T", "rater2_T", "rater1_T_insufficient", "rater2_T_insufficient"),
        ("G", "axis_g_governance", "rater1_G", "rater2_G", "rater1_G_insufficient", "rater2_G_insufficient"),
    ]:
        # Filter: use only confirmatory sample, exclude "insufficient information"
        subset = vf[vf["sample_type"] == "confirmatory"].copy()
        if insuf1_col in subset.columns:
            r1_insuf = subset[insuf1_col].fillna(False).astype(bool)
            r2_insuf = subset[insuf2_col].fillna(False).astype(bool)
            subset = subset[~(r1_insuf | r2_insuf)]

        r1 = pd.to_numeric(subset[rater1_col], errors="coerce")
        r2 = pd.to_numeric(subset[rater2_col], errors="coerce")
        auto = pd.to_numeric(subset[axis_col], errors="coerce")

        valid = r1.notna() & r2.notna() & auto.notna()
        r1 = r1[valid].values
        r2 = r2[valid].values
        auto = auto[valid].values
        n = len(r1)

        if n < 10:
            results[axis_name] = {"error": f"Too few valid ratings: {n}", "n": n}
            continue

        # Human mean
        human_mean = np.mean([r1, r2], axis=0)

        # 1. Inter-rater agreement
        ratings_matrix = np.column_stack([r1, r2])
        kalpha = _krippendorff_alpha_ordinal(ratings_matrix)
        wkappa = _weighted_kappa(r1.astype(int), r2.astype(int))

        # Bootstrap CI for weighted kappa
        paired = np.column_stack([r1, r2])

        def _wk_fn(data):
            return _weighted_kappa(data[:, 0].astype(int), data[:, 1].astype(int))

        wk_mean, wk_lo, wk_hi = _bootstrap_ci(paired, _wk_fn)

        # 2. Spearman correlation: automated vs human mean
        spear_r, spear_p = sp_stats.spearmanr(auto, human_mean)

        def _spear_fn(data):
            return sp_stats.spearmanr(data[:, 0], data[:, 1])[0]

        spear_ci_data = np.column_stack([auto, human_mean])
        spear_mean, spear_lo, spear_hi = _bootstrap_ci(spear_ci_data, _spear_fn)

        # 3. MAE after rescaling
        auto_rescaled = _rescale_to_likert(auto)
        mae = np.mean(np.abs(auto_rescaled - human_mean))

        def _mae_fn(data):
            a = _rescale_to_likert(data[:, 0])
            return np.mean(np.abs(a - data[:, 1]))

        mae_data = np.column_stack([auto, human_mean])
        mae_mean, mae_lo, mae_hi = _bootstrap_ci(mae_data, _mae_fn)

        # 4. AUC for binary 1-2 vs 4-5 (excluding 3)
        binary_mask = (human_mean <= 2) | (human_mean >= 4)
        if binary_mask.sum() >= 6:
            y_true = (human_mean[binary_mask] >= 4).astype(int)
            y_score_bin = auto_rescaled[binary_mask]
            auc_val = _compute_auc(y_true, y_score_bin)

            def _auc_fn(data):
                hm = data[:, 1]
                bm = (hm <= 2) | (hm >= 4)
                if bm.sum() < 6:
                    return np.nan
                yt = (hm[bm] >= 4).astype(int)
                ys = _rescale_to_likert(data[:, 0][bm])
                return _compute_auc(yt, ys)

            auc_data = np.column_stack([auto, human_mean])
            auc_mean, auc_lo, auc_hi = _bootstrap_ci(auc_data, _auc_fn)
        else:
            auc_val = np.nan
            auc_mean = auc_lo = auc_hi = np.nan

        # 5. Calibration: human mean by quintile of automated score
        quintiles = pd.qcut(auto, 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
        calibration = {}
        for q in sorted(set(quintiles.astype(str))):
            mask_q = quintiles.astype(str) == q
            calibration[q] = {
                "n": int(mask_q.sum()),
                "auto_mean": float(np.mean(auto[mask_q])),
                "auto_range": [float(np.min(auto[mask_q])), float(np.max(auto[mask_q]))],
                "human_mean": float(np.mean(human_mean[mask_q])),
                "human_sd": float(np.std(human_mean[mask_q])),
            }

        results[axis_name] = {
            "n": n,
            "inter_rater": {
                "krippendorff_alpha": float(kalpha),
                "weighted_kappa": float(wkappa),
                "weighted_kappa_bootstrap_mean": float(wk_mean),
                "weighted_kappa_95ci": [float(wk_lo), float(wk_hi)],
            },
            "convergent_validity": {
                "spearman_r": float(spear_r),
                "spearman_p": float(spear_p),
                "spearman_bootstrap_mean": float(spear_mean),
                "spearman_95ci": [float(spear_lo), float(spear_hi)],
            },
            "mae": {
                "mae_rescaled": float(mae_mean),
                "mae_95ci": [float(mae_lo), float(mae_hi)],
            },
            "auc_binary": {
                "auc": float(auc_mean) if not np.isnan(auc_mean) else None,
                "auc_95ci": [float(auc_lo), float(auc_hi)] if not np.isnan(auc_mean) else None,
            },
            "calibration": calibration,
        }

    # Write results
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "validation_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"Saved: {out_path}")

    return results


def print_validation_report(results: dict) -> None:
    """Print a human-readable validation report."""
    for axis_name in ["T", "G"]:
        r = results.get(axis_name, {})
        if "error" in r:
            print(f"\nAxis {axis_name}: ERROR — {r['error']}")
            continue

        print(f"\n{'='*60}")
        print(f"  Axis {axis_name} — Validation Report (n={r['n']})")
        print(f"{'='*60}")

        ir = r["inter_rater"]
        print(f"\n  Inter-rater agreement:")
        print(f"    Krippendorff's alpha (ordinal): {ir['krippendorff_alpha']:.4f}")
        print(f"    Weighted kappa (quadratic):     {ir['weighted_kappa']:.4f}")
        print(f"    Weighted kappa 95% CI:          [{ir['weighted_kappa_95ci'][0]:.4f}, {ir['weighted_kappa_95ci'][1]:.4f}]")

        cv = r["convergent_validity"]
        print(f"\n  Convergent validity (automated vs human mean):")
        print(f"    Spearman rho:  {cv['spearman_r']:.4f} (p={cv['spearman_p']:.4f})")
        print(f"    Spearman 95% CI: [{cv['spearman_95ci'][0]:.4f}, {cv['spearman_95ci'][1]:.4f}]")

        m = r["mae"]
        print(f"\n  Mean absolute error (rescaled auto → 1-5):")
        print(f"    MAE:      {m['mae_rescaled']:.3f}")
        print(f"    MAE 95% CI: [{m['mae_95ci'][0]:.3f}, {m['mae_95ci'][1]:.3f}]")

        a = r.get("auc_binary", {})
        if a.get("auc") is not None:
            print(f"\n  AUC (binary: 1-2 vs 4-5, excluding 3):")
            print(f"    AUC:      {a['auc']:.4f}")
            if a.get("auc_95ci"):
                print(f"    AUC 95% CI: [{a['auc_95ci'][0]:.4f}, {a['auc_95ci'][1]:.4f}]")

        print(f"\n  Calibration (human mean by auto-score quintile):")
        for q, c in r.get("calibration", {}).items():
            print(f"    {q}: n={c['n']:3d}  auto=[{c['auto_range'][0]:+.4f}, {c['auto_range'][1]:+.4f}]  human_mean={c['human_mean']:.2f}  human_sd={c['human_sd']:.2f}")

    # Decision rule
    print(f"\n{'='*60}")
    print(f"  DECISION RULE CHECK")
    print(f"{'='*60}")
    for axis_name in ["T", "G"]:
        r = results.get(axis_name, {})
        if "error" in r:
            print(f"  Axis {axis_name}: INCONCLUSIVE — {r['error']}")
            continue
        spear = r["convergent_validity"]["spearman_r"]
        kalpha = r["inter_rater"]["krippendorff_alpha"]
        spear_ok = spear >= 0.50
        kalpha_ok = kalpha >= 0.60
        status = "PASS" if (spear_ok and kalpha_ok) else "WEAK — report as limitation"
        print(f"  Axis {axis_name}: Spearman={spear:.3f} (≥.50: {spear_ok}), "
              f"Krippendorff={kalpha:.3f} (≥.60: {kalpha_ok}) → {status}")
