from __future__ import annotations

import hashlib
import os

import numpy as np
import pandas as pd
import torch
import umap
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from .config import LOW_QUALITY_ABSTRACT_RE, MIN_EMBED_ABSTRACT_LENGTH, N_CLUSTERS
from .paths import RunPaths, ensure_run_dirs
from .utils import corpus_fingerprint, read_json, write_json

MAX_ABSTRACT_CHARS = 6000
_EMBED_DIM = 1024  # BAAI/bge-m3 output dimension


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _load_global_cache(cache_dir) -> tuple[dict[str, np.ndarray], ...]:
    """Return (hash_to_vec dict).  Empty dict if cache doesn't exist yet."""
    index_path = cache_dir / "index.csv"
    vectors_path = cache_dir / "vectors.npy"
    if not index_path.exists() or not vectors_path.exists():
        return {}
    try:
        index = pd.read_csv(index_path, dtype=str)
        vectors = np.load(vectors_path)
        if len(index) != len(vectors):
            print("  [WARN] Global embed cache index/vectors mismatch — ignoring cache.")
            return {}
        return dict(zip(index["hash"].tolist(), vectors))
    except Exception as exc:
        print(f"  [WARN] Could not load global embed cache: {exc}")
        return {}


def _save_global_cache(cache_dir, hash_to_vec: dict[str, np.ndarray]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    hashes = list(hash_to_vec.keys())
    vectors = np.stack([hash_to_vec[h] for h in hashes]).astype(np.float32)
    pd.DataFrame({"hash": hashes}).to_csv(cache_dir / "index.csv", index=False)
    np.save(cache_dir / "vectors.npy", vectors)
    print(f"  Global embed cache updated: {len(hashes)} entries → {cache_dir}")


def _valid_embedding_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work["abstract"] = work["abstract"].fillna("")
    work["abs_len"] = work["abstract"].str.len()
    mask_bad = (work["abs_len"] < MIN_EMBED_ABSTRACT_LENGTH) | work["abstract"].str.contains(LOW_QUALITY_ABSTRACT_RE, na=False)
    bad = work[mask_bad].copy()
    good = work[~mask_bad].copy().reset_index(drop=True)
    return good, bad


def run(paths: RunPaths) -> None:
    ensure_run_dirs(paths)

    df = pd.read_csv(paths.corpus_clean_path)
    good, bad = _valid_embedding_rows(df)
    bad.to_csv(paths.embedding_exclusions_path, index=False)

    print(f"Loaded {len(df)} papers from {paths.corpus_clean_path.name}")
    if len(bad):
        print(f"Dropping {len(bad)} low-quality abstracts before embedding")
        for _, row in bad.iterrows():
            print(f"  [{int(row['abs_len'])} chars] {str(row['title'])[:80]}")

    fingerprint = corpus_fingerprint(good, text_column="abstract")
    meta = read_json(paths.embedding_meta_path, default={})
    embeddings = None

    if paths.embeddings_path.exists() and paths.embedding_index_path.exists():
        index_df = pd.read_csv(paths.embedding_index_path)
        if (
            meta.get("fingerprint") == fingerprint
            and meta.get("n_rows") == len(good)
            and len(index_df) == len(good)
        ):
            print(f"Loading embeddings from run-dir cache: {paths.embeddings_path.name}")
            embeddings = np.load(paths.embeddings_path)
            # Opportunistically back-fill global cache with any missing entries
            cache_dir = paths.global_embed_cache_dir
            global_cache = _load_global_cache(cache_dir)
            embed_texts = (
                good["title"].fillna("") + ". " + good["abstract"].fillna("").str[:MAX_ABSTRACT_CHARS]
            ).tolist()
            text_hashes = [_text_hash(t) for t in embed_texts]
            new_entries = {h: embeddings[i] for i, h in enumerate(text_hashes) if h not in global_cache}
            if new_entries:
                global_cache.update(new_entries)
                _save_global_cache(cache_dir, global_cache)
        else:
            print("Embedding cache is stale; regenerating embeddings.")

    if embeddings is None:
        # ── Global cache lookup ──────────────────────────────────────────
        cache_dir = paths.global_embed_cache_dir
        global_cache = _load_global_cache(cache_dir)

        embed_texts = (
            good["title"].fillna("") + ". " + good["abstract"].fillna("").str[:MAX_ABSTRACT_CHARS]
        ).tolist()
        text_hashes = [_text_hash(t) for t in embed_texts]

        miss_indices = [i for i, h in enumerate(text_hashes) if h not in global_cache]
        hit_count = len(embed_texts) - len(miss_indices)
        print(f"  Global embed cache: {hit_count} hits, {len(miss_indices)} misses (will encode)")

        if miss_indices:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"  Encoding {len(miss_indices)} new records with BAAI/bge-m3 on {device.upper()}...")
            model = SentenceTransformer("BAAI/bge-m3", device=device)
            model.eval()
            miss_texts = [embed_texts[i] for i in miss_indices]
            new_vecs = model.encode(
                miss_texts,
                batch_size=64,
                show_progress_bar=True,
                normalize_embeddings=True,
            ).astype(np.float32)
            for i, vec in zip(miss_indices, new_vecs):
                global_cache[text_hashes[i]] = vec
            _save_global_cache(cache_dir, global_cache)

        embeddings = np.stack([global_cache[h] for h in text_hashes]).astype(np.float32)
        np.save(paths.embeddings_path, embeddings)
        good[["id", "title", "publication_year"]].to_csv(paths.embedding_index_path, index=False)

    scores = {}
    max_k = min(9, len(good) - 1)
    min_k = 2 if len(good) >= 3 else 1
    if min_k == 1:
        good["cluster"] = 0
        k_best = 1
        scores[1] = float("nan")
        print("\nCorpus too small for silhouette-based clustering; assigning a single cluster.")
    elif N_CLUSTERS > 0:
        k_best = min(N_CLUSTERS, max_k)
        print(f"\nUsing fixed k={k_best} cluster(s) (N_CLUSTERS override; silhouette search skipped).")
        km = KMeans(n_clusters=k_best, random_state=42, n_init=10)
        labels = km.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels, metric="cosine")
        scores[k_best] = float(score)
        print(f"  k={k_best}: silhouette={score:.4f}")
        good["cluster"] = labels
    else:
        print(f"\nSilhouette search (k = {min_k}..{max_k}):")
        for k in range(min_k, max_k + 1):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(embeddings)
            score = silhouette_score(embeddings, labels, metric="cosine")
            scores[k] = float(score)
            print(f"  k={k}: silhouette={score:.4f}")

    if min_k > 1 and N_CLUSTERS == 0:
        k_best = max(scores, key=scores.get)
        km_final = KMeans(n_clusters=k_best, random_state=42, n_init=10)
        labels = km_final.fit_predict(embeddings)
        good["cluster"] = labels

    reducer = umap.UMAP(
        n_components=2,
        random_state=42,
        metric="cosine",
        n_neighbors=max(2, min(15, len(good) - 1)),
        min_dist=0.1,
    )
    coords = reducer.fit_transform(embeddings)
    good["umap_x"] = coords[:, 0]
    good["umap_y"] = coords[:, 1]

    umap_df = good[["id", "title", "publication_year", "cluster", "umap_x", "umap_y"]].copy()
    umap_df.to_csv(paths.indicators_dir / "umap_coords.csv", index=False)
    good.drop(columns=["abs_len"], errors="ignore").to_csv(paths.corpus_clustered_path, index=False)

    meta = {
        "model": "BAAI/bge-m3",
        "fingerprint": fingerprint,
        "n_rows": len(good),
        "n_excluded_no_embedding": len(bad),
        "k_best": int(k_best),
        "silhouette": float(scores[k_best]),
        "silhouette_scores": {str(k): value for k, value in scores.items()},
    }
    write_json(paths.embedding_meta_path, meta)

    fetch_log = read_json(paths.fetch_log_path, default={})
    fetch_log["n_excluded_no_embedding"] = len(bad)
    fetch_log["n_final_semantic"] = len(good)
    write_json(paths.fetch_log_path, fetch_log)

    print(f"Saved: {paths.corpus_clustered_path}")
    print(f"Saved: {paths.indicators_dir / 'umap_coords.csv'}")
    print(f"Saved: {paths.embedding_meta_path}")