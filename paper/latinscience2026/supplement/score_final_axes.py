"""Apply the published anchors to preserved document embeddings.

Requires the original embedding matrix, its ID index, and an included-record
CSV. These source records are not redistributed with the supplement.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

CHECKPOINT = "5617a9f61b028005a4858fdac845db406aefb181"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--anchors", type=Path, default=Path(__file__).parent / "S4_SELECTED_PROTOTYPE_TEXTS.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--revision", default=CHECKPOINT)
    args = parser.parse_args()
    vectors = np.load(args.embeddings).astype(np.float32)
    index = pd.read_csv(args.index)
    corpus = pd.read_csv(args.corpus)
    if "decision" in corpus:
        corpus = corpus[corpus.decision == "include"]
    if len(corpus) != 711 or not corpus.id.is_unique or not index.id.is_unique or len(index) != len(vectors):
        raise ValueError("The embedding index and 711-record corpus are inconsistent")
    lookup = dict(zip(index.id, range(len(index))))
    vectors = vectors[[lookup[record_id] for record_id in corpus.id]]
    anchors = pd.read_csv(args.anchors)
    model = SentenceTransformer("BAAI/bge-m3", revision=args.revision)
    model.eval()
    result = corpus[["id"]].copy()
    for axis in ("T", "G"):
        centroids = {}
        for pole in ("neg", "pos"):
            texts = anchors[(anchors.axis == axis) & (anchors.pole == pole)].sort_values("position").text
            if len(texts) != 5:
                raise ValueError("Expected five anchors at each pole")
            centroids[pole] = np.stack([
                model.encode(text, normalize_embeddings=True).astype(np.float32) for text in texts
            ]).mean(axis=0)
        direction = centroids["pos"] - centroids["neg"]
        direction /= np.linalg.norm(direction)
        center = float((centroids["pos"] @ direction + centroids["neg"] @ direction) / 2)
        result[f"{axis}_score"] = vectors @ direction - center
    if args.reference:
        reference = pd.read_csv(args.reference).rename(columns={"axis_t_technology": "T_score", "axis_g_governance": "G_score"})
        matched = result.merge(reference[["id", "T_score", "G_score"]], on="id", validate="one_to_one", suffixes=("", "_reference"))
        if len(matched) != 711:
            raise ValueError("The reference does not contain all included IDs")
        for axis in ("T", "G"):
            error = np.max(np.abs(matched[f"{axis}_score"] - matched[f"{axis}_score_reference"]))
            print(f"{axis}: maximum absolute difference from frozen scores = {error:.9g}")
            if error > 1e-6:
                raise ValueError("Fresh anchor encoding does not reproduce the frozen scores")
    result.to_csv(args.output, index=False, float_format="%.9g")


if __name__ == "__main__":
    main()
