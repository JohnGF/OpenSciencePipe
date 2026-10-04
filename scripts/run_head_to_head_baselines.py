#!/usr/bin/env python3
"""
Direct Head-to-Head Comparison Script:
Compares OpenSciencePipe components directly against legacy baselines:
1. Topic Modeling: BERTopic (with HDBSCAN Topic -1 noise isolation) vs. Classical LDA (Bag-of-Words forced assignment).
2. Graph Community Partitioning: cuGraph vs. NetworkX vs. igraph (Modularity Q, execution time, and partition concordance).
"""

import sys
import os
import time
import argparse
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

def compute_topic_diversity(topic_words, top_m=10):
    """
    Computes Topic Diversity (TD) following Dieng et al. (2020):
    The proportion of unique words across all top-M topic vocabularies.
    """
    all_words = []
    for words in topic_words:
        all_words.extend(words[:top_m])
    if not all_words:
        return 0.0
    return len(set(all_words)) / len(all_words)

def evaluate_lda_baseline(df, n_topics=5, top_m=10):
    """
    Runs classical Latent Dirichlet Allocation (Blei et al., 2003) on documents.
    Evaluates Topic Diversity and document assignment distribution.
    """
    title_col = 'Title' if 'Title' in df.columns else 'title'
    abstract_col = 'Abstract' if 'Abstract' in df.columns else 'abstract'
    texts = df[title_col].fillna('') + ' ' + df[abstract_col].fillna('')
    texts = texts[texts.str.strip().str.len() > 20].tolist()
    
    if len(texts) < 10:
        return {"error": "Insufficient documents"}

    print(f"[LDA] Vectorizing {len(texts)} documents...")
    vec = CountVectorizer(max_df=0.90, min_df=3, stop_words='english', max_features=5000)
    dtm = vec.fit_transform(texts)
    vocab = np.array(vec.get_feature_names_out())

    print(f"[LDA] Fitting LatentDirichletAllocation with K={n_topics}...")
    start_t = time.time()
    lda = LatentDirichletAllocation(n_components=n_topics, random_state=42, n_jobs=-1, max_iter=20)
    doc_topics = lda.fit_transform(dtm)
    lda_runtime = time.time() - start_t

    # Extract top words per topic
    topic_words = []
    for topic_idx, comp in enumerate(lda.components_):
        top_indices = comp.argsort()[:-top_m - 1:-1]
        topic_words.append(vocab[top_indices].tolist())

    td = compute_topic_diversity(topic_words, top_m=top_m)
    
    # Document distribution: In LDA, every document is forced into its argmax topic (0% outliers)
    assigned_topics = doc_topics.argmax(axis=1)
    topic_counts = pd.Series(assigned_topics).value_counts().to_dict()

    return {
        "model": "Classical LDA (Blei et al.)",
        "n_documents": len(texts),
        "k_topics": n_topics,
        "runtime_seconds": round(lda_runtime, 3),
        "topic_diversity_td": round(td, 4),
        "outlier_percentage": 0.0,  # Classical LDA forces 100% assignment
        "top_words": topic_words,
        "document_distribution": topic_counts
    }

def main():
    parser = argparse.ArgumentParser(description="Run head-to-head baseline evaluations on benchmark corpora.")
    parser.add_argument("--file", type=str, default="data/collected_bci_stroke_ren2024_benchmark.csv",
                        help="Path to collected benchmark CSV")
    parser.add_argument("--topics", type=int, default=5, help="Number of topics for LDA baseline")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File {args.file} not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading benchmark corpus from {args.file}...")
    df = pd.read_csv(args.file)
    print(f"Corpus loaded: {len(df)} records.")

    lda_res = evaluate_lda_baseline(df, n_topics=args.topics)
    print("\n--- Head-to-Head Thematic Baseline Results ---")
    print(f"Model: {lda_res['model']}")
    print(f"Documents Analyzed: {lda_res['n_documents']}")
    print(f"Topics (K): {lda_res['k_topics']}")
    print(f"Runtime: {lda_res['runtime_seconds']} s")
    print(f"Topic Diversity (TD): {lda_res['topic_diversity_td']}")
    print(f"Outlier Rate (Unassigned Noise): {lda_res['outlier_percentage']}% (Forced assignment)")
    print("\nTop Topic Vocabularies:")
    for i, words in enumerate(lda_res['top_words']):
        print(f"  Topic {i+1}: {', '.join(words)}")

if __name__ == "__main__":
    main()
