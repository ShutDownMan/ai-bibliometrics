"""inspect_xml_abstracts.py — Find and show abstracts with Word XML artifacts."""
import argparse
import re
from pathlib import Path


def _resolve_run_dir() -> Path:
    parser = argparse.ArgumentParser(description="Inspect clustered abstracts for Word XML artifacts.")
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

import pandas as pd


df = pd.read_csv(ROOT / "corpus_clustered.csv")

# Word XML artifacts pattern
XML_PATTERN = re.compile(r"(lsdexception|unhidewhenused|semihidden|w:lsd|<w:)", re.IGNORECASE)

bad = df[df["abstract"].str.contains(XML_PATTERN, na=False)]
print(f"Papers with Word XML in abstract: {len(bad)}")
print()

for _, r in bad.iterrows():
    print(f"[Cluster {r['cluster']}] DOI: {r['doi']}")
    print(f"  Title: {str(r['title'])[:80]}")
    abs_text = str(r['abstract'])
    # Show first 300 and where XML starts
    xml_pos = XML_PATTERN.search(abs_text)
    if xml_pos:
        start = max(0, xml_pos.start() - 100)
        print(f"  XML at pos {xml_pos.start()} (of {len(abs_text)} chars)")
        print(f"  Context: ...{abs_text[start:start+200]}...")
    print()
