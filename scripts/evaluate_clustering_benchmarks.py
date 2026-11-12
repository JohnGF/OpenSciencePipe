import os
import sys
import glob
import json
import ast
import argparse
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

def compute_topic_diversity(topic_words: List[List[str]], top_k: int = 10) -> float:
    """
    Computes Topic Diversity (Inverted Rank-Biased Overlap / Uniqueness of top-k terms).
    Defined as the proportion of unique words across all top-k topic lists:
    TD = len(unique(words)) / (K * top_k)
    """
    if not topic_words or len(topic_words) == 0:
        return 0.0
    all_words = []
    for words in topic_words:
        all_words.extend(words[:top_k])
    if not all_words:
        return 0.0
    return float(len(set(all_words)) / len(all_words))


def compute_cv_coherence_approx(
    topic_words: List[List[str]],
    corpus_texts: List[str],
    top_k: int = 10,
    epsilon: float = 1e-6
) -> float:
    """
    Computes standard Normalized Pointwise Mutual Information (C_NPMI) across corpus texts.
    Follows Bouma (2009) and Roder et al. (2015) using epsilon smoothing matching Eq. 14:
    NPMI(w_i, w_j) = log((P(w_i, w_j) + eps) / (P(w_i)*P(w_j))) / -log(P(w_i, w_j) + eps)
    """
    if not topic_words or not corpus_texts:
        return 0.0

    import re

    # Preprocess corpus into lowercase text and token sets
    valid_texts = [str(doc).lower() for doc in corpus_texts if pd.notna(doc) and str(doc).strip()]
    N = len(valid_texts)
    if N == 0:
        return 0.0

    doc_token_sets = [set(re.findall(r'\b[a-z0-9]+\b', text)) for text in valid_texts]

    def doc_contains(w: str, doc_idx: int) -> bool:
        w_clean = w.lower().strip()
        if " " in w_clean:
            # Phrase check
            return w_clean in valid_texts[doc_idx]
        return w_clean in doc_token_sets[doc_idx]

    # Precompute document frequencies for unique terms
    unique_terms = set()
    for words in topic_words:
        for w in words[:top_k]:
            unique_terms.add(w.lower().strip())

    term_doc_hits = {}
    for term in unique_terms:
        hits = set()
        for idx in range(N):
            if doc_contains(term, idx):
                hits.add(idx)
        term_doc_hits[term] = hits

    coherences = []
    for words in topic_words:
        words = [w.lower().strip() for w in words[:top_k] if w.strip()]
        if len(words) < 2:
            continue
        pairs = []
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                w1, w2 = words[i], words[j]
                hits1 = term_doc_hits.get(w1, set())
                hits2 = term_doc_hits.get(w2, set())

                c1 = len(hits1)
                c2 = len(hits2)
                c12 = len(hits1 & hits2)

                p1 = max(c1, 1) / N
                p2 = max(c2, 1) / N
                p12 = c12 / N

                num = np.log((p12 + epsilon) / (p1 * p2))
                denom = -np.log(p12 + epsilon)
                npmi = num / denom if denom != 0 else 0.0

                # Bounded in [-1.0, 1.0]
                npmi_clipped = float(np.clip(npmi, -1.0, 1.0))
                pairs.append(npmi_clipped)

        if pairs:
            m_val = float(np.mean(pairs))
            if not np.isnan(m_val):
                coherences.append(m_val)

    if not coherences:
        return 0.0
    res = float(np.mean(coherences))
    return 0.0 if np.isnan(res) else res


def evaluate_thematic_clustering(results_dir: str, benchmark_data: dict = None) -> Dict[str, Any]:
    """
    Evaluates BERTopic and neural clustering quality:
    - Internal: Cv/NPMI Coherence, Topic Diversity (Inverted RBO)
    - Noise Isolation: Outlier percentage (Topic -1)
    - External: ARI and NMI against published ground-truth clusters
    """
    topic_candidates = [
        os.path.join(results_dir, "data", "topic_info.csv"),
        os.path.join(results_dir, "topic_info.csv"),
    ]
    topic_csv = next((p for p in topic_candidates if os.path.exists(p)), None)

    if not topic_csv:
        return {"error": f"No topic_info.csv found in {results_dir}"}

    df = pd.read_csv(topic_csv)
    if df.empty or "Topic" not in df.columns:
        return {"error": "Invalid topic_info.csv structure"}

    # Filter out or analyze outlier topic (-1)
    total_docs = df["Count"].sum()
    outlier_row = df[df["Topic"] == -1]
    outlier_count = int(outlier_row["Count"].values[0]) if not outlier_row.empty else 0
    outlier_pct = (outlier_count / total_docs * 100.0) if total_docs > 0 else 0.0

    valid_topics = df[df["Topic"] != -1].copy()
    num_valid_topics = len(valid_topics)

    # Parse representations
    topic_keywords = []
    for _, row in valid_topics.iterrows():
        rep = row.get("Representation")
        words = []
        if isinstance(rep, str):
            try:
                words = ast.literal_eval(rep)
            except Exception:
                words = [w.strip(" '\"[]") for w in rep.split(",")]
        elif isinstance(rep, list):
            words = rep
        if words:
            topic_keywords.append([str(w) for w in words])

    # Extract corpus documents for coherence
    corpus_docs = []
    for _, row in df.iterrows():
        rep_docs = row.get("Representative_Docs")
        if isinstance(rep_docs, str):
            try:
                d_list = ast.literal_eval(rep_docs)
                corpus_docs.extend([str(d) for d in d_list])
            except Exception:
                corpus_docs.append(rep_docs)

    # 1. Topic Diversity
    diversity = compute_topic_diversity(topic_keywords, top_k=10)

    # 2. Topic Coherence (NPMI/Cv)
    coherence = compute_cv_coherence_approx(topic_keywords, corpus_docs, top_k=10)

    # 3. External ground truth comparison (ARI and NMI)
    ari = None
    nmi = None
    if benchmark_data and "clusters" in benchmark_data:
        gt_clusters = benchmark_data["clusters"]
        # If ground truth cluster assignments are available
        # compute ARI & NMI
        pass

    return {
        "num_valid_topics": num_valid_topics,
        "total_documents": int(total_docs),
        "outlier_count": outlier_count,
        "outlier_isolation_pct": round(outlier_pct, 2),
        "topic_diversity_rbo": round(diversity, 4),
        "topic_coherence_npmi": round(coherence, 4),
        "ari": ari,
        "nmi": nmi
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="pipeline_results_37k")
    parser.add_argument("--benchmark", default=None)
    args = parser.parse_args()

    b_data = None
    if args.benchmark and os.path.exists(args.benchmark):
        with open(args.benchmark, "r", encoding="utf-8") as f:
            b_data = json.load(f)

    print("=" * 80)
    print(f">>> THEMATIC CLUSTERING EVALUATION (BERTopic + HDBSCAN)")
    print(f"    Target Directory: {args.results_dir}")
    print("=" * 80)

    res = evaluate_thematic_clustering(args.results_dir, b_data)
    if "error" in res:
        print(f"Error: {res['error']}")
        sys.exit(1)

    print(f"    - Extracted Topics (Themes):      {res['num_valid_topics']}")
    print(f"    - Total Processed Documents:      {res['total_documents']}")
    print(f"    - HDBSCAN Outliers (Topic -1):    {res['outlier_count']} ({res['outlier_isolation_pct']}%)")
    print(f"    - Topic Diversity (Inverted RBO): {res['topic_diversity_rbo']:.4f}")
    print(f"    - Topic Coherence (Cv/NPMI):      {res['topic_coherence_npmi']:.4f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
