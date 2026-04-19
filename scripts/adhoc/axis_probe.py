"""axis_probe.py — Find papers at cluster extremes to test axis candidates."""
import argparse
from pathlib import Path


def _resolve_run_dir() -> Path:
    parser = argparse.ArgumentParser(description="Probe a small set of handcrafted semantic axes.")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory. Defaults to the repository root.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    run_dir = Path(args.run_dir) if args.run_dir else repo_root
    if not run_dir.is_absolute():
        run_dir = repo_root / run_dir
    return run_dir.resolve()


ROOT = _resolve_run_dir()

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer


df = pd.read_csv(ROOT / "corpus_clustered.csv")
emb = np.load(ROOT / "embeddings_bgem3.npy")

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("BAAI/bge-m3", device=device)
model.eval()

# ── Candidate axis pairs to probe ─────────────────────────────────────────
AXES = {
    "efl_classroom_vs_research_production": (
        "Students practise English as a foreign language by interacting with AI chatbots "
        "to improve speaking, writing and grammar skills in school classroom activities.",
        "Academics use artificial intelligence to search the literature, synthesise sources, "
        "generate academic text and accelerate their scholarly writing and research productivity."
    ),
    "descriptive_survey_vs_critical_theory": (
        "This empirical study collects questionnaire data from students and teachers, "
        "applies statistical tests and reports learning outcomes from using an AI tool.",
        "This theoretical article critically analyses how large language models transform "
        "knowledge production, academic authorship, epistemology and scholarly communication."
    ),
    "tool_adoption_vs_societal_impact": (
        "This paper evaluates whether a specific AI tool, such as ChatGPT, helps students "
        "complete academic tasks faster, with higher quality and greater satisfaction.",
        "This paper examines the broader societal consequences: inequality, job displacement, "
        "misinformation, environmental cost and loss of critical thinking from AI adoption."
    ),
}

print("=" * 70)
for axis_name, (neg_text, pos_text) in AXES.items():
    neg_vec = model.encode(neg_text, normalize_embeddings=True)
    pos_vec = model.encode(pos_text, normalize_embeddings=True)
    axis_vec = pos_vec - neg_vec
    axis_vec /= np.linalg.norm(axis_vec)

    scores = emb @ axis_vec
    df[f"score_{axis_name}"] = scores

    print(f"\n{'='*70}")
    print(f"AXIS: {axis_name}")
    print(f"  NEG: {neg_text[:80]}...")
    print(f"  POS: {pos_text[:80]}...")
    print(f"  Score range: {scores.min():.3f} → {scores.max():.3f}  std={scores.std():.3f}")
    print(f"  Mean per cluster:")
    for c in sorted(df["cluster"].unique()):
        m = scores[df["cluster"] == c].mean()
        bar = "█" * int((m + 0.5) * 20)
        print(f"    C{c} (n={sum(df['cluster']==c):3d}): {m:+.3f}  {bar}")

    # Top 5 most positive and most negative papers
    top_pos_idx = np.argsort(scores)[-5:][::-1]
    top_neg_idx = np.argsort(scores)[:5]

    print(f"\n  TOP +5 (most '{axis_name.split('_vs_')[1]}'):")
    for i in top_pos_idx:
        r = df.iloc[i]
        print(f"    [{r['publication_year']} C{r['cluster']} {scores[i]:+.3f}] {str(r['title'])[:70]}")

    print(f"\n  TOP -5 (most '{axis_name.split('_vs_')[0]}'):")
    for i in top_neg_idx:
        r = df.iloc[i]
        print(f"    [{r['publication_year']} C{r['cluster']} {scores[i]:+.3f}] {str(r['title'])[:70]}")

# ── Check orthogonality between axes ──────────────────────────────────────
print("\n\n" + "=" * 70)
print("AXIS CORRELATION MATRIX (Pearson r of projected scores)")
print("Axes are well-suited if |r| < 0.3 between each pair")
axis_cols = [f"score_{a}" for a in AXES]
corr = df[axis_cols].corr()
for col in axis_cols:
    name = col.replace("score_", "")[:30]
    vals = "  ".join([f"{corr.loc[col, c2]:+.3f}" for c2 in axis_cols])
    print(f"  {name:32s} | {vals}")
