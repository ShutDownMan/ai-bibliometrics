"""Reproduce the publication statistics from the released derived data.

Usage: python reproduce.py --write
       python reproduce.py --check
The release includes this file as reproduce.py beside the input CSV files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BOOTSTRAP_VALIDATION = 10_000
VALIDATION_SEED = 20260810


def rank_ci(x, y, rng):
    values = []
    for _ in range(10):
        indices = rng.integers(0, len(x), (1000, len(x)))
        a = stats.rankdata(np.asarray(x)[indices], axis=1)
        b = stats.rankdata(np.asarray(y)[indices], axis=1)
        a -= a.mean(axis=1, keepdims=True)
        b -= b.mean(axis=1, keepdims=True)
        rho = (a * b).sum(axis=1) / np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
        if not np.isfinite(rho).all():
            raise ValueError("A validation bootstrap sample has undefined correlation")
        values.extend(rho.tolist())
    return np.quantile(values, [0.025, 0.975]).tolist()


def correlation(x, y, rng):
    rho, p = stats.spearmanr(x, y)
    return {
        "spearman_rho": float(rho), "p": float(p),
        "spearman_ci_95": rank_ci(x, y, rng),
        "pearson_r": float(stats.pearsonr(x, y).statistic),
    }


def regression(frame, categorical=False, seed=42):
    t = frame.T_score.to_numpy(dtype=float)
    g = frame.G_score.to_numpy(dtype=float)
    years = frame.publication_year.to_numpy(dtype=float)
    if categorical:
        year_columns = pd.get_dummies(years, drop_first=True).to_numpy(dtype=float)
    else:
        year_columns = years[:, None]
    baseline = np.column_stack([np.ones(len(frame)), year_columns])
    design = np.column_stack([np.ones(len(frame)), t, year_columns])
    beta = np.linalg.lstsq(design, g, rcond=None)[0]
    total = np.square(g - g.mean()).sum()
    r2 = float(1 - np.square(g - design @ beta).sum() / total)
    r2_year = float(1 - np.square(g - baseline @ np.linalg.lstsq(baseline, g, rcond=None)[0]).sum() / total)
    rt = t - baseline @ np.linalg.lstsq(baseline, t, rcond=None)[0]
    rg = g - baseline @ np.linalg.lstsq(baseline, g, rcond=None)[0]
    partial = stats.pearsonr(rt, rg)
    partial_df = len(frame) - baseline.shape[1] - 1
    partial_t = float(partial.statistic) * np.sqrt(partial_df / (1 - float(partial.statistic) ** 2))
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(2000):
        indices = rng.integers(0, len(frame), len(frame))
        draws.append(float(np.linalg.lstsq(design[indices], g[indices], rcond=None)[0][1]))
    return {
        "n": len(frame), "year_adjustment": "categorical" if categorical else "continuous",
        "beta_t": float(beta[1]), "beta_t_ci_95": np.quantile(draws, [.025, .975]).tolist(),
        "partial_r": float(partial.statistic), "partial_p": float(2 * stats.t.sf(abs(partial_t), partial_df)),
        "partial_test_df": partial_df,
        "r_squared": r2, "r_squared_year_only": r2_year,
        "f_squared_t": float((r2 - r2_year) / (1 - r2)),
        "bootstrap_resamples": 2000, "bootstrap_seed": seed,
    }


def calculate(package):
    corpus = pd.read_csv(package / "S8_DERIVED_ANALYSIS_DATA.csv")
    ratings = pd.read_csv(package / "S9_VALIDATION_SCORES.csv")
    if len(corpus) != 711 or not corpus.record_id.is_unique:
        raise ValueError("Expected 711 unique included records")
    if len(ratings) != 129 or not ratings.record_id.is_unique:
        raise ValueError("Expected 129 unique validation records")
    crosswalk = ratings.merge(corpus, left_on="record_id", right_on="record_id", validate="one_to_one")
    if len(crosswalk) != 129:
        raise ValueError("Validation records do not all match the final corpus")
    for axis in ("T", "G"):
        if not np.allclose(crosswalk[f"{axis}_automated"], crosswalk[f"{axis}_score"], atol=1e-9, rtol=0):
            raise ValueError(f"Validation {axis} scores differ from the final corpus")
        expected = (ratings[f"{axis}_rater_a"] + ratings[f"{axis}_rater_b"]) / 2
        if not np.array_equal(expected, ratings[f"{axis}_human_mean"]):
            raise ValueError(f"Validation {axis} human means are inconsistent")
        if not ratings[[f"{axis}_rater_a", f"{axis}_rater_b"]].isin([1, 2, 3, 4, 5]).all().all():
            raise ValueError("Human ratings must use the 1-5 scale")

    rng = np.random.default_rng(VALIDATION_SEED)
    validation = {"n": len(ratings), "bootstrap_resamples": BOOTSTRAP_VALIDATION, "bootstrap_seed": VALIDATION_SEED}
    for axis in ("T", "G"):
        a = ratings[f"{axis}_rater_a"].to_numpy()
        b = ratings[f"{axis}_rater_b"].to_numpy()
        result = correlation(a, b, rng)
        observed = pd.crosstab(a, b).reindex(index=range(1, 6), columns=range(1, 6), fill_value=0).to_numpy()
        weights = np.square(np.arange(5)[:, None] - np.arange(5)[None, :]) / 16
        expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / observed.sum()
        result["quadratic_weighted_kappa"] = float(1 - (weights * observed).sum() / (weights * expected).sum())
        validation[axis] = {"inter_rater": result}
    for axis in ("T", "G"):
        auto = ratings[f"{axis}_automated"].to_numpy()
        human = ratings[f"{axis}_human_mean"].to_numpy()
        result = validation[axis]
        result["human_automated"] = correlation(human, auto, rng)
        result["per_rater_spearman"] = {
            rater: float(stats.spearmanr(ratings[f"{axis}_rater_{rater}"], auto).statistic)
            for rater in ("a", "b")
        }
        quintiles = pd.qcut(auto, 5, labels=False, duplicates="raise")
        result["quintiles"] = [
            {"quintile": int(q + 1), "n": int((quintiles == q).sum()), "mean_human": float(human[quintiles == q].mean())}
            for q in range(5)
        ]
    return {
        "corpus_n": len(corpus),
        "snapshot": "locally preserved April 2026 multi-source snapshot",
        "principal": regression(corpus),
        "sensitivity_excluding_2026": regression(corpus[corpus.publication_year < 2026], seed=20260808),
        "sensitivity_2023_2025": regression(corpus[corpus.publication_year.between(2023, 2025)], categorical=True, seed=20260808),
        "validation": validation,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).parent)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = calculate(args.package)
    path = args.package / "S11_PUBLICATION_RESULTS.json"
    if args.write:
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    else:
        expected = json.loads(path.read_text(encoding="utf-8"))
        def same(a, b):
            if isinstance(a, dict):
                return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
            if isinstance(a, list):
                return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
            if isinstance(a, float):
                return bool(np.isclose(a, b, rtol=1e-9, atol=1e-12))
            return a == b
        if not same(result, expected):
            raise ValueError("Calculated results differ from S11_PUBLICATION_RESULTS.json")
    print(json.dumps({"principal": result["principal"], "validation": result["validation"]}, indent=2))


if __name__ == "__main__":
    main()
