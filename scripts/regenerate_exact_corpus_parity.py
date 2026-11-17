#!/usr/bin/env python3
"""Reproduce Stage 1 vs Stage 2 exact-corpus parity metrics (tab_exact_corpus_parity.tex) using OpenSciencePipe."""

import os
from collections import Counter

import numpy as np
import pandas as pd
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from umap import UMAP

from src.core.ingestion import fetch_zenodo_dataset


def eval_b14():
    df_open = pd.read_csv("data/collected_benchmark_public_health_top100.csv")
    df_exact = pd.read_csv("data/collected_b14_exact_100.csv")

    exact_dois = set(df_exact["DOI"].dropna().str.lower().str.strip()) - {""}
    open_dois = set(df_open["DOI"].dropna().str.lower().str.strip()) - {""}
    doi_recall = len(exact_dois & open_dois)

    gt_authors = {"ware", "altman", "horan", "egger", "charlson", "sherbourne", "moher", "higgins", "thompson", "gotzsche"}
    ac = Counter()
    for val in df_exact["Authors"].dropna():
        for a in str(val).split(";"):
            a = a.strip()
            if a:
                ac[a.split(",")[0].strip().lower() if "," in a else a.split()[-1].lower()] += 1
    top10_authors = {a for a, _ in ac.most_common(10)}

    gt_countries = {"US", "GB", "CA", "CH", "NL"}
    country_map = {"USA": "US", "England": "GB", "Canada": "CA", "Switzerland": "CH", "Netherlands": "NL", "Netherland": "NL"}
    cc = Counter()
    for val in df_exact["Affiliations"].dropna():
        for c in str(val).split(";"):
            c = c.strip()
            if c:
                cc[country_map.get(c, c)] += 1
    top5_countries = {c for c, _ in cc.most_common(5)}

    return {
        "open_n": len(df_open),
        "exact_n": len(df_exact),
        "doi_recall": (doi_recall, len(exact_dois)),
        "exact_countries": len(gt_countries & top5_countries),
        "exact_authors": len(gt_authors & top10_authors),
    }


def eval_zenodo_climate_ed():
    csv_path = fetch_zenodo_dataset("10.5281/zenodo.24269215", dest_dir="data/exact_corpora", filename_hint="Meta data of 323 articles.csv")
    base_dir = os.path.dirname(csv_path)
    df = pd.read_csv(csv_path)
    gt_auth = pd.read_excel(os.path.join(base_dir, "Most_Relevant_Authors_bibliometrix_2026-10-18.xlsx"), header=1)
    gt_docs = pd.read_excel(os.path.join(base_dir, "Most_Global_Cited_Documents_bibliometrix_2026-10-18.xlsx"), header=1)

    ac = Counter()
    for val in df["Author full names"].dropna():
        for a in str(val).split(";"):
            name = a.split("(")[0].strip().upper()
            if name:
                ac[name] += 1
    top10_auth = {a for a, _ in ac.most_common(10)}
    gt_top10_auth = {str(a).strip().upper() for a in gt_auth["Author"].head(10)}

    top10_dois = {str(d).strip().lower() for d in df.sort_values("Cited by", ascending=False)["DOI"].head(10)}
    gt_top10_dois = {str(d).strip().lower() for d in gt_docs["DOI"].head(10)}

    return {
        "n": len(df),
        "author_overlap": len(top10_auth & gt_top10_auth),
        "doi_overlap": len(top10_dois & gt_top10_dois),
    }


def eval_zenodo_llm_testing():
    csv_path = fetch_zenodo_dataset("10.5281/zenodo.24295745", dest_dir="data/exact_corpora", filename_hint="A1_estudios_incluidos_P1-P1032.csv")
    df = pd.read_csv(csv_path)
    docs = (df["Title"].fillna("") + ". " + df["Author Keywords"].fillna("") + "; " + df["Index Keywords"].fillna("")).tolist()

    gt_mask = df["Cluster_bibliometrix"].isin(["software testing", "language model", "application programs", "computational linguistics"]).values
    gt_labels = df.loc[gt_mask, "Cluster_bibliometrix"].values

    embs = SentenceTransformer("all-MiniLM-L6-v2").encode(docs, show_progress_bar=False)
    topic_model = BERTopic(
        umap_model=UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42),
        hdbscan_model=HDBSCAN(min_cluster_size=10, metric="euclidean", cluster_selection_method="eom", prediction_data=True),
        verbose=False,
    )
    topics, _ = topic_model.fit_transform(docs, embeddings=embs)
    topics_arr = np.array(topics)
    valid_topics = [t for t in set(topics) if t != -1]
    all_words = [w for t in valid_topics for w, _ in topic_model.get_topic(t)[:10]]
    td_bt = len(set(all_words)) / (len(valid_topics) * 10)
    outliers_pct = (topics_arr == -1).mean() * 100
    bt_mask = gt_mask & (topics_arr != -1)
    ari_bt = adjusted_rand_score(df.loc[bt_mask, "Cluster_bibliometrix"], topics_arr[bt_mask])
    nmi_bt = normalized_mutual_info_score(df.loc[bt_mask, "Cluster_bibliometrix"], topics_arr[bt_mask])

    vec = CountVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)
    X = vec.fit_transform(docs)
    vocab = np.array(vec.get_feature_names_out())

    def _run_lda(k_lda: int):
        tds, aris, nmis = [], [], []
        for seed in range(42, 47):
            lda = LatentDirichletAllocation(n_components=k_lda, random_state=seed, max_iter=20, learning_method="batch")
            pred = lda.fit_transform(X).argmax(axis=1)
            words = [w for comp in lda.components_ for w in vocab[np.argsort(comp)[-10:]]]
            tds.append(len(set(words)) / (k_lda * 10))
            aris.append(adjusted_rand_score(gt_labels, pred[gt_mask]))
            nmis.append(normalized_mutual_info_score(gt_labels, pred[gt_mask]))
        return float(np.mean(tds)), float(np.mean(aris)), float(np.mean(nmis))

    td_lda, ari_lda, nmi_lda = _run_lda(len(valid_topics))
    td_lda4, ari_lda4, nmi_lda4 = _run_lda(4)

    return {
        "n": len(df),
        "k": len(valid_topics),
        "td_bt": td_bt,
        "outliers": outliers_pct,
        "ari_bt": ari_bt,
        "nmi_bt": nmi_bt,
        "td_lda": td_lda,
        "ari_lda": ari_lda,
        "nmi_lda": nmi_lda,
        "td_lda4": td_lda4,
        "ari_lda4": ari_lda4,
        "nmi_lda4": nmi_lda4,
    }


def main():
    b14 = eval_b14()
    z1 = eval_zenodo_climate_ed()
    z2 = eval_zenodo_llm_testing()
    print("B14:", b14)
    print("Zenodo 24269215:", z1)
    print("Zenodo 24295745:", z2)


if __name__ == "__main__":
    main()
