"""analyze_clusters.py — Inspect cluster profiles to design semantic axes."""
import argparse
import re
from collections import Counter
from pathlib import Path


def _resolve_run_dir() -> Path:
    parser = argparse.ArgumentParser(description="Inspect cluster profiles for exploratory axis design.")
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


df = pd.read_csv(ROOT / "corpus_clustered.csv")
emb = np.load(ROOT / "embeddings_bgem3.npy")

def get_kws(s):
    return [n.lower() for n in re.findall(r"'display_name': '([^']+)'", str(s))]

print("=" * 70)
print("PER-CLUSTER PROFILE")
print("=" * 70)

for c in sorted(df["cluster"].unique()):
    sub = df[df["cluster"] == c]
    idx = sub.index.tolist()

    all_kws = []
    for row in sub["keywords"]:
        all_kws.extend(get_kws(row))
    top_kw = [k for k, n in Counter(all_kws).most_common(10)]

    top_topics = sub["primary_topic"].value_counts().head(5).index.tolist()
    cit = sub["cited_by_count"]
    cats = sub["category"].value_counts().head(4)
    years = sub["publication_year"].value_counts().sort_index()

    print(f"\nCluster {c} — n={len(sub)}")
    print(f"  Citations: median={cit.median():.0f}  mean={cit.mean():.1f}  max={cit.max()}")
    print(f"  Years: {dict(years)}")
    print(f"  Category: {dict(cats)}")
    print(f"  Keywords: {top_kw}")
    print(f"  Topics: {top_topics}")

# ── Cross-cluster keyword contrast (TF-IDF style) ──────────────────────────
print("\n\n" + "=" * 70)
print("DISTINCTIVE KEYWORDS PER CLUSTER (vs rest of corpus)")
print("=" * 70)

total_n = len(df)
all_kws_global = Counter()
for row in df["keywords"]:
    all_kws_global.update(get_kws(row))

for c in sorted(df["cluster"].unique()):
    sub = df[df["cluster"] == c]
    cluster_kws = Counter()
    for row in sub["keywords"]:
        cluster_kws.update(get_kws(row))

    # Score: (cluster_freq / cluster_size) / (global_freq / total_n)
    scores = {}
    for kw, freq in cluster_kws.items():
        global_freq = all_kws_global[kw]
        tf_cluster = freq / len(sub)
        tf_global = global_freq / total_n
        if tf_global > 0:
            scores[kw] = tf_cluster / tf_global

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:8]
    print(f"\nCluster {c}: {[k for k, s in top]}")

# ── Abstract word frequency per cluster ──────────────────────────────────
print("\n\n" + "=" * 70)
print("TOP ABSTRACT WORDS PER CLUSTER (excluding stopwords)")
print("=" * 70)

STOPWORDS = {
    "the","a","an","and","or","of","to","in","for","with","is","are","this",
    "that","on","at","as","be","by","from","it","its","their","they","have",
    "has","was","were","been","not","but","also","can","which","these","those",
    "more","than","between","such","study","paper","results","findings","show",
    "shows","among","using","used","through","within","while","research","based",
    "about","both","well","how","may","we","our","ai","artificial","intelligence",
    "language","english","learning","education","model","models","academic",
    "writing","tool","tools","use","uses","students","student","teachers","teacher"
}

for c in sorted(df["cluster"].unique()):
    sub = df[df["cluster"] == c]
    words = Counter()
    for abs_text in sub["abstract"].fillna(""):
        tokens = re.findall(r"\b[a-z]{4,}\b", abs_text.lower())
        words.update(t for t in tokens if t not in STOPWORDS)
    top_words = [w for w, n in words.most_common(15)]
    print(f"Cluster {c}: {top_words}")
