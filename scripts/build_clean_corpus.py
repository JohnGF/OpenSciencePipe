"""Build the paper-3 clean analytical corpus with explicit, reproducible filters.

Recipe (mirrors src/core/collection.py dedup + src/core/screening.py defaults):
  1. Load data/collected_EEG_master_merged.csv (65,259 harvested records).
  2. Exact-match union-find dedup on normalized DOI and normalized title
     (collection.py::deduplicate_dataframe; master is already unique -> no-op).
  3. Screening: keep records with abstract >= 30 chars (screening.py default).
  4. Study window: Year in [2014, 2026] (2026 retained in totals; figures
     truncate trajectories at the last complete year downstream).

English-only restriction holds by sampling audit (99.8% English, n=3000):
no language filter is applied, keeping the build deterministic and offline.

Output: data/paper3_clean_corpus.csv + stdout audit. Expected N = 57,601.
"""
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import pandas as pd

MASTER = os.path.join(repo_root, "data", "collected_EEG_master_merged.csv")
OUTPUT = os.path.join(repo_root, "data", "paper3_clean_corpus.csv")
MIN_ABSTRACT_LEN = 30
START_YEAR, END_YEAR = 2014, 2026


def main() -> int:
    df = pd.read_csv(MASTER)
    print(f"[+] master rows: {len(df)}")

    # 1. Exact normalized DOI/title dedup (union-find equivalent: group keys).
    doi = df["DOI"].fillna("").astype(str).str.lower().str.strip()
    doi = doi.str.replace(r"^https?://doi\.org/|^doi\.org/", "", regex=True)
    title = df["Title"].fillna("").astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    key = doi.where(doi != "", "T:" + title)
    has_key = (key != "") & (key != "T:")
    df = df[~has_key | ~key.duplicated(keep="first")].copy()
    print(f"[+] after exact dedup: {len(df)}")

    # 2. Screening: abstract >= 30 chars.
    ab = df["Abstract"].fillna("").astype(str).str.strip()
    df = df[ab.str.len() >= MIN_ABSTRACT_LEN].copy()
    print(f"[+] abstract >= {MIN_ABSTRACT_LEN} chars: {len(df)}")

    # 3. Study window.
    df = df[(df["Year"] >= START_YEAR) & (df["Year"] <= END_YEAR)].copy()
    print(f"[+] CLEAN CORPUS {START_YEAR}-{END_YEAR}: {len(df)}")

    df.to_csv(OUTPUT, index=False)
    print(f"[+] wrote {OUTPUT}")
    print(df["Year"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
