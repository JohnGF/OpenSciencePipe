#!/usr/bin/env python3
"""
HDBSCAN min_cluster_size (m_cl) Ablation Across Verified Ground-Truth Benchmarks.

Evaluates m_cl in {3, 5, 7, 10} on the 6 benchmarks with published verbatim
cluster taxonomies (B04, B07, B08, B12, B16, B17) using identical BERTopic
hyperparameters (all-MiniLM-L6-v2, UMAP n_neighbors=15, n_components=5,
min_dist=0.0, metric='cosine', random_state=42; HDBSCAN cluster_selection_method='eom').
Reports mean outlier %, mean Topic Diversity (TD), and Hungarian Cluster Recovery
(CR at tau=0.10).
"""

import json
import os
import sys
import numpy as np
import pandas as pd
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.evaluate_thematic_validation import (
    BENCHMARK_SLUGS,
    match_topics_to_clusters,
    tokenize_keywords,
)

MCL_VALUES = [3, 5, 7, 10]
JACCARD_THRESHOLD = 0.10


def main():
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    verified = []
    for bid, short_name, slug in BENCHMARK_SLUGS:
        json_path = f"data/benchmarks/{slug}.json"
        csv_path = f"data/collected_{slug}.csv"
        with open(json_path, "r", encoding="utf-8") as f:
            b_meta = json.load(f)
        clusters = b_meta.get("scientometrics", {}).get("clusters", [])
        if not clusters:
            continue

        df = pd.read_csv(csv_path)
        docs = []
        for _, row in df.iterrows():
            title = str(row.get("Title", "") or "").strip()
            abs_txt = str(row.get("Abstract", "") or "").strip()
            if abs_txt.lower() in ("", "nan", "none", "no abstract available", "null"):
                continue
            if len(abs_txt) < 20:
                continue
            docs.append(f"{title}. {abs_txt}")

        embs = model.encode(docs, show_progress_bar=False)
        cluster_sets = [
            tokenize_keywords([c.get("label", "")] + list(c.get("keywords", [])))
            for c in clusters
        ]
        verified.append({
            "bid": bid,
            "name": short_name,
            "docs": docs,
            "embs": embs,
            "cluster_sets": cluster_sets,
            "k_pub": len(clusters),
        })

    print(f"Loaded {len(verified)} verified benchmarks ({sum(b['k_pub'] for b in verified)} published clusters).")
    for m_cl in MCL_VALUES:
        tds = []
        outs = []
        total_hung = 0
        total_pub = 0
        for b in verified:
            umap_model = UMAP(
                n_neighbors=15,
                n_components=5,
                min_dist=0.0,
                metric="cosine",
                random_state=42,
            )
            hdbscan_model = HDBSCAN(
                min_cluster_size=m_cl,
                metric="euclidean",
                cluster_selection_method="eom",
                prediction_data=True,
            )
            vec = CountVectorizer(stop_words="english", ngram_range=(1, 2))
            bt = BERTopic(
                umap_model=umap_model,
                hdbscan_model=hdbscan_model,
                vectorizer_model=vec,
                verbose=False,
            )
            topics, _ = bt.fit_transform(b["docs"], embeddings=b["embs"])
            topics_arr = np.array(topics)
            out_pct = float((topics_arr == -1).mean() * 100.0)
            outs.append(out_pct)

            valid_t = [t for t in set(topics) if t != -1]
            if valid_t:
                all_words = [w for t in valid_t for w, _ in bt.get_topic(t)[:10]]
                td = len(set(all_words)) / (len(valid_t) * 10)
                topic_sets = [
                    tokenize_keywords([w for w, _ in bt.get_topic(t)[:10]])
                    for t in valid_t
                ]
            else:
                td = 0.0
                topic_sets = []
            tds.append(td)

            _, rec_hung, _ = match_topics_to_clusters(
                topic_sets, b["cluster_sets"], threshold=JACCARD_THRESHOLD
            )
            total_hung += len(rec_hung)
            total_pub += b["k_pub"]

        cr_pct = 100.0 * total_hung / total_pub
        print(
            f"m_cl={m_cl:2d}: mean_outliers={np.mean(outs):.1f}%, "
            f"mean_TD={np.mean(tds):.2f}, CR={total_hung}/{total_pub} ({cr_pct:.1f}%)"
        )


if __name__ == "__main__":
    main()
