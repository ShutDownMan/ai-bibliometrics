from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


def parse_list(value):
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return []
    try:
        parsed = ast.literal_eval(str(value))
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def read_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_html_text(text: str) -> str:
    value = "" if text is None else str(text)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"^Abstract[\s:]+", "", value, flags=re.IGNORECASE)
    return value.strip()


def corpus_fingerprint(df: pd.DataFrame, *, text_column: str = "abstract") -> str:
    cols = [c for c in ["id", "title", text_column] if c in df.columns]
    joined = "\n".join(
        "\t".join(str(row[col]) for col in cols)
        for _, row in df[cols].fillna("").iterrows()
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def get_cluster_label(cluster_id: int) -> str:
    from .config import CLUSTER_METADATA

    meta = CLUSTER_METADATA.get(int(cluster_id), {})
    return meta.get("label", f"Cluster {int(cluster_id)}")


def get_cluster_description(cluster_id: int) -> str:
    from .config import CLUSTER_METADATA

    meta = CLUSTER_METADATA.get(int(cluster_id), {})
    return meta.get("description", "")