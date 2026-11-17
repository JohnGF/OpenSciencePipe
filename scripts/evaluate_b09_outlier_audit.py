#!/usr/bin/env python3
"""
Deterministic Forensic Audit Sampler for B09 Electrophysiology Topic -1 Outliers.

Draws the exact random_state=42 sample of n=30 documents from the 22,428
Topic -1 outlier records in outputs/bertopic_clean/doc_topics.csv and joins
titles/abstracts from data/collected_EEG_master_merged.csv for inspection.
"""

import os
import pandas as pd


def main():
    doc_topics_path = "outputs/bertopic_clean/doc_topics.csv"
    corpus_path = "data/collected_EEG_master_merged.csv"
    if not os.path.exists(doc_topics_path):
        raise FileNotFoundError(f"Missing {doc_topics_path}")

    dt = pd.read_csv(doc_topics_path)
    outliers = dt[dt["topic"] == -1].copy()
    print(f"Total docs: {len(dt):,}, Topic -1 outliers: {len(outliers):,} ({100.0 * len(outliers) / len(dt):.2f}%)")

    if os.path.exists(corpus_path):
        raw = pd.read_csv(corpus_path, usecols=lambda c: c in {"DOI", "Title", "Year", "Abstract"})
        raw["DOI_norm"] = raw["DOI"].astype(str).str.strip().str.lower()
        outliers["DOI_norm"] = outliers["DOI"].astype(str).str.strip().str.lower()
        outliers = outliers.merge(
            raw.drop_duplicates(subset=["DOI_norm"]),
            on="DOI_norm",
            how="left",
            suffixes=("", "_raw"),
        )

    sample = outliers.sample(n=30, random_state=42).reset_index(drop=True)
    print("\nSeed=42 Sample (n=30) from B09 Topic -1 Pool:")
    for idx, row in sample.iterrows():
        title = str(row.get("Title", "<Title unavailable>"))[:110]
        print(f"{idx+1:2d}. [{row.get('DOI', '')}] {title}")


if __name__ == "__main__":
    main()
