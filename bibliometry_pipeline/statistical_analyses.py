"""Statistical analyses for the Latin.Science 2026 paper.

Implements the paper plan's § "Testes principais":
- H1: Temporal trend in T axis (technological specificity)
- H2: Temporal trend in G axis (governance orientation)
- H3: Association between T and G, controlling for year
- H4: Exploratory — association between framing and citations

All results are reported with effect sizes, confidence intervals, and bootstrap
CIs where appropriate.  p-values are reported but NOT used as proof of validity.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from .paths import RunPaths, ensure_run_dirs


def _bootstrap_linear_regression(
    X: np.ndarray, y: np.ndarray, n_bootstrap: int = 2000, random_seed: int = 42
) -> dict:
    """Bootstrap CIs for OLS regression coefficients."""
    n = len(y)
    rng = np.random.default_rng(random_seed)
    coefs = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        Xb, yb = X[idx], y[idx]
        try:
            beta = np.linalg.lstsq(Xb, yb, rcond=None)[0]
            coefs.append(beta)
        except np.linalg.LinAlgError:
            continue
    coefs = np.array(coefs)
    results = {}
    for j in range(coefs.shape[1]):
        c = coefs[:, j]
        results[f"beta_{j}"] = {
            "mean": float(np.mean(c)),
            "median": float(np.median(c)),
            "ci_95": [float(np.percentile(c, 2.5)), float(np.percentile(c, 97.5))],
        }
    return results


def _cohens_f2(r2_full: float, r2_reduced: float) -> float:
    """Cohen's f² effect size for a predictor added to a nested model."""
    if r2_full >= 1.0 - 1e-9:
        return float("inf")
    return (r2_full - r2_reduced) / (1.0 - r2_full)


def _interpret_f2(f2: float) -> str:
    if f2 >= 0.35:
        return "large"
    if f2 >= 0.15:
        return "medium"
    if f2 >= 0.02:
        return "small"
    return "negligible"


def run(paths: RunPaths) -> dict:
    """Run H1–H4 analyses on the final corpus.

    Reads ``corpus_paper.csv`` and ``axis_scores.csv`` from the run's indicators
    directory.  Only ``include``-decision papers are analyzed.

    Returns a dict suitable for ``report_summary.json`` and writes
    ``statistical_results.json`` to the indicators directory.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    corpus = pd.read_csv(paths.corpus_paper_path)
    axis = pd.read_csv(paths.indicators_dir / "axis_scores.csv")

    # Merge and filter to included papers only
    df = corpus.merge(
        axis[["id", "axis_t_technology", "axis_g_governance",
              "axis_t_technology_z", "axis_g_governance_z"]],
        on="id", how="left",
    )
    df = df[df["decision"] == "include"].copy()
    n = len(df)
    print(f"[stats] Analyzing {n} included papers")

    # -------------------------------------------------------------------
    # H1 & H2: Temporal trends
    # -------------------------------------------------------------------

    valid = df.dropna(subset=["publication_year", "axis_t_technology", "axis_g_governance"])
    year = valid["publication_year"].values.astype(float)
    T = valid["axis_t_technology"].values
    G = valid["axis_g_governance"].values

    # H1: T ~ year
    X_h1 = np.column_stack([np.ones(len(year)), year])
    beta_h1 = np.linalg.lstsq(X_h1, T, rcond=None)[0]
    T_pred = X_h1 @ beta_h1
    ss_res = np.sum((T - T_pred) ** 2)
    ss_tot = np.sum((T - T.mean()) ** 2)
    r2_h1 = 1.0 - ss_res / ss_tot
    r_h1, p_h1 = sp_stats.pearsonr(year, T)
    bs_h1 = _bootstrap_linear_regression(X_h1, T)
    f2_h1 = _cohens_f2(r2_h1, 0.0)

    # H2: G ~ year
    X_h2 = np.column_stack([np.ones(len(year)), year])
    beta_h2 = np.linalg.lstsq(X_h2, G, rcond=None)[0]
    G_pred = X_h2 @ beta_h2
    ss_res_g = np.sum((G - G_pred) ** 2)
    ss_tot_g = np.sum((G - G.mean()) ** 2)
    r2_h2 = 1.0 - ss_res_g / ss_tot_g
    r_h2, p_h2 = sp_stats.pearsonr(year, G)
    bs_h2 = _bootstrap_linear_regression(X_h2, G)
    f2_h2 = _cohens_f2(r2_h2, 0.0)

    # Pre-2023 vs 2023+ comparison
    pre23 = valid[valid["publication_year"] < 2023]
    post23 = valid[valid["publication_year"] >= 2023]
    pre23_n = len(pre23)
    post23_n = len(post23)

    # T-test with unequal variance
    t_tstat, t_pval = sp_stats.ttest_ind(
        post23["axis_t_technology"], pre23["axis_t_technology"], equal_var=False
    )
    g_tstat, g_pval = sp_stats.ttest_ind(
        post23["axis_g_governance"], pre23["axis_g_governance"], equal_var=False
    )
    # Cohen's d
    t_d = (post23["axis_t_technology"].mean() - pre23["axis_t_technology"].mean()) / np.sqrt(
        (post23["axis_t_technology"].var() + pre23["axis_t_technology"].var()) / 2
    )
    g_d = (post23["axis_g_governance"].mean() - pre23["axis_g_governance"].mean()) / np.sqrt(
        (post23["axis_g_governance"].var() + pre23["axis_g_governance"].var()) / 2
    )

    h1_results = {
        "description": "H1: Temporal trend in T (technological specificity)",
        "n": int(len(year)),
        "pearson_r": float(r_h1),
        "pearson_p": float(p_h1),
        "ols_r2": float(r2_h1),
        "ols_intercept": float(beta_h1[0]),
        "ols_slope": float(beta_h1[1]),
        "slope_95ci": bs_h1["beta_1"]["ci_95"],
        "cohens_f2": float(f2_h1),
        "effect_size": _interpret_f2(f2_h1),
        "pre_2023_n": int(pre23_n),
        "post_2023_n": int(post23_n),
        "pre_2023_T_mean": float(pre23["axis_t_technology"].mean()),
        "post_2023_T_mean": float(post23["axis_t_technology"].mean()),
        "cohort_cohens_d": float(t_d),
        "cohort_ttest_p": float(t_pval),
    }

    h2_results = {
        "description": "H2: Temporal trend in G (governance orientation)",
        "n": int(len(year)),
        "pearson_r": float(r_h2),
        "pearson_p": float(p_h2),
        "ols_r2": float(r2_h2),
        "ols_intercept": float(beta_h2[0]),
        "ols_slope": float(beta_h2[1]),
        "slope_95ci": bs_h2["beta_1"]["ci_95"],
        "cohens_f2": float(f2_h2),
        "effect_size": _interpret_f2(f2_h2),
        "pre_2023_G_mean": float(pre23["axis_g_governance"].mean()),
        "post_2023_G_mean": float(post23["axis_g_governance"].mean()),
        "cohort_cohens_d": float(g_d),
        "cohort_ttest_p": float(g_pval),
    }

    # -------------------------------------------------------------------
    # H3: G ~ T + year
    # -------------------------------------------------------------------
    X_h3 = np.column_stack([np.ones(len(year)), T, year])
    beta_h3 = np.linalg.lstsq(X_h3, G, rcond=None)[0]
    G_pred_h3 = X_h3 @ beta_h3
    ss_res_h3 = np.sum((G - G_pred_h3) ** 2)
    r2_h3 = 1.0 - ss_res_h3 / ss_tot_g

    # Unique contribution of T (beyond year)
    r2_year_only = r2_h2
    f2_T = _cohens_f2(r2_h3, r2_year_only)

    # Partial correlation: T ~ G | year
    # Regress T and G on year, correlate residuals
    beta_T_year = np.linalg.lstsq(X_h2, T, rcond=None)[0]
    resid_T = T - X_h2 @ beta_T_year
    resid_G = G - X_h2 @ beta_h2
    partial_r, partial_p = sp_stats.pearsonr(resid_T, resid_G)

    bs_h3 = _bootstrap_linear_regression(X_h3, G)

    h3_results = {
        "description": "H3: G ~ T + year (association between specificity and governance)",
        "n": int(len(year)),
        "ols_r2": float(r2_h3),
        "ols_r2_year_only": float(r2_year_only),
        "ols_intercept": float(beta_h3[0]),
        "ols_beta_T": float(beta_h3[1]),
        "ols_beta_year": float(beta_h3[2]),
        "beta_T_95ci": bs_h3["beta_1"]["ci_95"],
        "beta_year_95ci": bs_h3["beta_2"]["ci_95"],
        "partial_r_T_G_controlling_year": float(partial_r),
        "partial_r_p": float(partial_p),
        "cohens_f2_T_unique": float(f2_T),
        "effect_size_T": _interpret_f2(f2_T),
    }

    # -------------------------------------------------------------------
    # H4: Citation analysis (exploratory)
    # -------------------------------------------------------------------
    citation_col = None
    for col in ["times_cited", "citation_count", "cited_by_count", "citations"]:
        if col in df.columns:
            citation_col = col
            break

    h4_results = {"description": "H4: Association between framing and citations (exploratory)"}

    if citation_col is not None:
        df_cite = df.dropna(subset=[citation_col, "publication_year",
                                     "axis_t_technology", "axis_g_governance"]).copy()
        df_cite[citation_col] = pd.to_numeric(df_cite[citation_col], errors="coerce")
        df_cite = df_cite.dropna(subset=[citation_col])
        df_cite = df_cite[df_cite[citation_col] >= 0]  # remove negative if any

        if len(df_cite) >= 30:
            cites = df_cite[citation_col].values.astype(float)
            T_cite = df_cite["axis_t_technology"].values
            G_cite = df_cite["axis_g_governance"].values
            year_cite = df_cite["publication_year"].values.astype(float)

            # Log(citations + 1) ~ T + G + year
            log_cites = np.log1p(cites)
            X_h4 = np.column_stack([np.ones(len(log_cites)), T_cite, G_cite, year_cite])
            beta_h4 = np.linalg.lstsq(X_h4, log_cites, rcond=None)[0]
            log_pred = X_h4 @ beta_h4
            ss_res_h4 = np.sum((log_cites - log_pred) ** 2)
            ss_tot_h4 = np.sum((log_cites - log_cites.mean()) ** 2)
            r2_h4 = 1.0 - ss_res_h4 / ss_tot_h4

            # Zero-order correlations
            r_cite_T, p_cite_T = sp_stats.spearmanr(cites, T_cite)
            r_cite_G, p_cite_G = sp_stats.spearmanr(cites, G_cite)

            # Within-year citation percentile
            df_cite["log_cites"] = log_cites
            df_cite["cite_percentile"] = df_cite.groupby("publication_year")[citation_col].rank(pct=True)

            # Percentile means by G quartile
            df_cite["G_quartile"] = pd.qcut(df_cite["axis_g_governance"], 4, labels=["Q1", "Q2", "Q3", "Q4"])
            quartile_means = df_cite.groupby("G_quartile", observed=False)["cite_percentile"].mean().to_dict()

            h4_results.update({
                "n_with_citations": int(len(df_cite)),
                "citation_column_used": citation_col,
                "citation_median": float(np.median(cites)),
                "citation_mean": float(np.mean(cites)),
                "citation_max": int(np.max(cites)),
                "ols_log_r2": float(r2_h4),
                "ols_log_intercept": float(beta_h4[0]),
                "ols_log_beta_T": float(beta_h4[1]),
                "ols_log_beta_G": float(beta_h4[2]),
                "ols_log_beta_year": float(beta_h4[3]),
                "spearman_T_cites": float(r_cite_T),
                "spearman_T_cites_p": float(p_cite_T),
                "spearman_G_cites": float(r_cite_G),
                "spearman_G_cites_p": float(p_cite_G),
                "cite_percentile_by_G_quartile": {str(k): float(v) for k, v in quartile_means.items()},
            })
            print(f"  H4: {len(df_cite)} papers with citation data (median={np.median(cites):.0f})")
        else:
            h4_results["error"] = f"Too few papers with citation data: {len(df_cite)}"
    else:
        h4_results["error"] = f"No citation column found. Available columns: {list(df.columns)}"

    # -------------------------------------------------------------------
    # Assemble and save
    # -------------------------------------------------------------------
    results = {
        "corpus_n": n,
        "years_range": [int(year.min()), int(year.max())],
        "H1": h1_results,
        "H2": h2_results,
        "H3": h3_results,
        "H4": h4_results,
    }

    ensure_run_dirs(paths)
    out_path = paths.indicators_dir / "statistical_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"Saved: {out_path}")

    return results


def print_stats_report(results: dict) -> None:
    """Print a human-readable statistical report."""
    print(f"\n{'='*60}")
    print(f"  STATISTICAL ANALYSES (n={results['corpus_n']})")
    print(f"  Years: {results['years_range'][0]}–{results['years_range'][1]}")
    print(f"{'='*60}")

    for h in ["H1", "H2", "H3"]:
        r = results[h]
        print(f"\n--- {r['description']} ---")
        if h in ("H1", "H2"):
            print(f"  r = {r['pearson_r']:.4f}, p = {r['pearson_p']:.4f}")
            print(f"  R² = {r['ols_r2']:.4f}, slope = {r['ols_slope']:.6f} "
                  f"95% CI [{r['slope_95ci'][0]:.6f}, {r['slope_95ci'][1]:.6f}]")
            print(f"  Cohen's f² = {r['cohens_f2']:.4f} ({r['effect_size']})")
            if "cohort_cohens_d" in r:
                pre_n = r.get('pre_2023_n', '?')
                post_n = r.get('post_2023_n', '?')
                print(f"  Pre-2023 (n={pre_n}) vs 2023+ (n={post_n}): "
                      f"d = {r['cohort_cohens_d']:.3f}, p = {r['cohort_ttest_p']:.4f}")
        elif h == "H3":
            print(f"  Full model R² = {r['ols_r2']:.4f}")
            print(f"  T partial r (controlling year) = {r['partial_r_T_G_controlling_year']:.4f}, "
                  f"p = {r['partial_r_p']:.4f}")
            print(f"  T unique contribution: f² = {r['cohens_f2_T_unique']:.4f} ({r['effect_size_T']})")
            print(f"  β_T = {r['ols_beta_T']:.4f} 95% CI [{r['beta_T_95ci'][0]:.4f}, {r['beta_T_95ci'][1]:.4f}]")

    h4 = results["H4"]
    if "error" in h4:
        print(f"\n--- H4: SKIPPED — {h4['error']} ---")
    else:
        print(f"\n--- H4: Citation analysis (n={h4['n_with_citations']}) ---")
        print(f"  Citation median: {h4['citation_median']:.0f}, mean: {h4['citation_mean']:.1f}")
        print(f"  Spearman r(T, cites) = {h4['spearman_T_cites']:.4f}, p = {h4['spearman_T_cites_p']:.4f}")
        print(f"  Spearman r(G, cites) = {h4['spearman_G_cites']:.4f}, p = {h4['spearman_G_cites_p']:.4f}")
        print(f"  Log-linear R² = {h4['ols_log_r2']:.4f}")
        if "cite_percentile_by_G_quartile" in h4:
            print(f"  Citation percentile by G quartile:")
            for q, v in h4["cite_percentile_by_G_quartile"].items():
                print(f"    {q}: {v:.3f}")
