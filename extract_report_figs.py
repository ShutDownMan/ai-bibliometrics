"""Extract base64-encoded PNG figures from the report HTML/Markdown file.

Usage:
    python extract_report_figs.py NOTES/report.md figures/

Scans the file for <img src="data:image/png;base64,..."> tags,
decodes each to a PNG file, and names them by their alt text.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path


def slugify(text: str, maxlen: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:maxlen]


def extract(md_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    content = md_path.read_text(encoding="utf-8")

    pattern = re.compile(
        r'<img\s+src="data:image/png;base64,([^"]+)"'
        r'(?:[^>]*alt="([^"]*)")?',
        re.IGNORECASE | re.DOTALL,
    )

    paths: list[Path] = []
    for i, m in enumerate(pattern.finditer(content), 1):
        b64_data = m.group(1).strip()
        alt = m.group(2) or ""
        name = f"fig{i:02d}_{slugify(alt)}.png" if alt else f"fig{i:02d}.png"
        out_path = out_dir / name
        out_path.write_bytes(base64.b64decode(b64_data))
        paths.append(out_path)
        print(f"  [{i:02d}]  {out_path.name}  ({len(b64_data)//1024} KB b64)")

    return paths


def main() -> None:
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <report.html/md> <output_dir>")
        sys.exit(1)
    md_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not md_path.exists():
        print(f"Not found: {md_path}")
        sys.exit(1)
    imgs = extract(md_path, out_dir)
    print(f"\nExtracted {len(imgs)} figures → {out_dir}")


if __name__ == "__main__":
    main()
