import argparse
import re
from pathlib import Path


def _resolve_run_dir() -> Path:
    parser = argparse.ArgumentParser(description="Audit a fetched corpus for obvious scope issues.")
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


df = pd.read_csv(ROOT / "corpus.csv")

# ── 1. Off-topic detection ─────────────────────────────────────────────────────
OFF_TOPIC = re.compile(
    r"\b(cardiology|orthodontics|dental|surgery|plastic surg|ortho|medical|clinical|patient care|"
    r"food|agriculture|supply chain|manufacturing|drug|pharma|imaging|radiology|cancer|tumor|"
    r"cardiac|periodontal|dermatol|ophthalm|gynecol|urol|pediat|neonat|anaesth|pathol|"
    r"sport|athlete|physical education|sports science)\b",
    re.I,
)
df["offtopic"] = df["title"].str.contains(OFF_TOPIC, regex=True).fillna(False)
offtopic_n = df["offtopic"].sum()
print(f"Likely off-topic (medical/engineering/sports): {offtopic_n} / {len(df)}")
print()
print("=== OFF-TOPIC SAMPLE (first 20) ===")
for t in df[df["offtopic"]]["title"].head(20).tolist():
    print(" -", str(t)[:100])

# ── 2. Language-learning subcategory ──────────────────────────────────────────
LANG = re.compile(r"\b(EFL|ESL|language learn|English learn|language teach|foreign language|second language)\b", re.I)
df["lang_learn"] = df["title"].str.contains(LANG, regex=True).fillna(False)
ll_n = df["lang_learn"].sum()

# ── 3. Clearly on-topic core ──────────────────────────────────────────────────
CORE = re.compile(
    r"\b(academic writ|scientific writ|research support|academic product|scholarly commun|"
    r"research paper|thesis|dissertation|peer.?review|literature review|citation|bibliometr|"
    r"writing assist|research assist|academic integr|plagiar|academic tool|research tool)\b",
    re.I,
)
df["core"] = df["title"].str.contains(CORE, regex=True).fillna(False)
core_n = df["core"].sum()

print()
print(f"Language-learning papers : {ll_n} ({100*ll_n/len(df):.0f}%)")
print(f"Core academic-production : {core_n} ({100*core_n/len(df):.0f}%)")
print(f"Off-topic (medical etc.) : {offtopic_n} ({100*offtopic_n/len(df):.0f}%)")
print(f"Other / grey area        : {len(df)-ll_n-core_n-offtopic_n} ({100*(len(df)-ll_n-core_n-offtopic_n)/len(df):.0f}%)")
print()

# ── 4. What journals are the off-topic papers in? ─────────────────────────────
print("=== TOP JOURNALS among off-topic papers ===")
for j, n in df[df["offtopic"]]["journal"].value_counts().head(10).items():
    print(f"  {n:3d}  {j}")

print()

# ── 5. Open access check ──────────────────────────────────────────────────────
print(f"Total papers: {len(df)}")
print(f"With abstract (>50): {(df['abstract'].str.len() > 50).sum()}")
print(f"With DOI: {df['doi'].notna().sum()}")

# ── 6. Year × type breakdown ──────────────────────────────────────────────────
print()
print("=== YEAR × TYPE ===")
print(pd.crosstab(df["publication_year"].astype(int), df["type"]))

# ── 7. Sample full titles for manual review (sorted by citations) ──────────────
print()
print("=== TOP 30 PAPERS BY CITATIONS (for manual relevance check) ===")
df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce")
top = df.nlargest(30, "cited_by_count")[["title", "publication_year", "cited_by_count", "journal"]]
for _, row in top.iterrows():
    flag = "[OFFTOPIC?]" if row.get("offtopic") else ""
    print(f"  [{int(row['cited_by_count']) if pd.notna(row['cited_by_count']) else 0:5d}] {flag} {str(row['title'])[:90]}")
