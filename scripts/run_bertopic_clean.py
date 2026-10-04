"""BERTopic rerun on the paper-3 clean corpus (CPU, pipeline-faithful settings).

Mirrors src/core/nlp.py::BERTopicPipeline.fit_model CPU branch:
  embedding all-MiniLM-L6-v2, UMAP(5 comps, 15 neighbors, min_dist 0,
  cosine, rs 42), HDBSCAN(min_cluster_size 10, euclidean, eom),
  CountVectorizer(english stopwords, min_df 2, 1-2grams).
Docs: Abstract text (clean corpus guarantees >=30 chars).

Outputs to outputs/bertopic_clean/: topic_info.csv, doc_topics.csv, run_meta.json
"""
import json
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(repo_root, "outputs", "bertopic_clean")
CORPUS = os.path.join(repo_root, "data", "paper3_clean_corpus.csv")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    import pandas as pd

    df = pd.read_csv(CORPUS, usecols=["Title", "Abstract", "Year", "DOI"])
    docs = df["Abstract"].fillna("").astype(str).tolist()
    print(f"[+] docs: {len(docs)}", flush=True)

    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP as CPU_UMAP
    from hdbscan import HDBSCAN as CPU_HDBSCAN
    from bertopic import BERTopic

    vectorizer_model = CountVectorizer(stop_words="english", min_df=2, ngram_range=(1, 2))
    umap_model = CPU_UMAP(n_components=5, n_neighbors=15, min_dist=0.0, metric="cosine", random_state=42)
    hdbscan_model = CPU_HDBSCAN(min_cluster_size=10, metric="euclidean",
                                cluster_selection_method="eom", prediction_data=True)
    model = BERTopic(embedding_model="all-MiniLM-L6-v2", umap_model=umap_model,
                     hdbscan_model=hdbscan_model, vectorizer_model=vectorizer_model,
                     calculate_probabilities=True)
    t0 = time.time()
    topics, _ = model.fit_transform(docs)
    print(f"[+] fit_transform done in {time.time()-t0:.1f}s", flush=True)

    info = model.get_topic_info()
    info.to_csv(os.path.join(OUT, "topic_info.csv"), index=False)
    pd.DataFrame({"DOI": df["DOI"], "Year": df["Year"], "topic": topics}).to_csv(
        os.path.join(OUT, "doc_topics.csv"), index=False)
    n_topics = int((info["Topic"] != -1).sum())
    n_out = int((info.set_index("Topic").loc[-1, "Count"]) if -1 in info["Topic"].values else 0)
    meta = {"n_docs": len(docs), "n_topics": n_topics, "n_outliers": n_out,
            "fit_seconds": round(time.time() - t0, 1)}
    json.dump(meta, open(os.path.join(OUT, "run_meta.json"), "w"), indent=2)
    print("[+] " + json.dumps(meta), flush=True)
    print(info.head(12).to_string(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
