#!/usr/bin/env python3
"""
Evaluates:
1. F3a: Multi-seed BERTopic/UMAP stability (seeds 42..46) on B04, B07, B10.
2. F3b: Outlier sample extraction on B08 (56.5% outliers) for qualitative audit.
3. F6: Author disambiguation split & merge rates on an ORCID-linked OpenAlex sample.
"""

import os
import sys
import json
import httpx
import numpy as np
import pandas as pd
from collections import defaultdict
from bertopic import BERTopic
from umap import UMAP
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.disambiguation import AuthorDisambiguator
from scripts.evaluate_clustering_benchmarks import compute_topic_diversity
from scripts.evaluate_thematic_validation import tokenize_keywords, match_topics_to_clusters

SEEDS = [42, 43, 44, 45, 46]


def eval_bertopic_stability():
    print("=" * 80)
    print("F3a: MULTI-SEED BERTOPIC STABILITY (5 UMAP SEEDS: 42..46)")
    print("=" * 80)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    targets = [
        ("B04", "benchmark_blockchain_vosviewer"),
        ("B07", "benchmark_digital_transformation_kraus2021"),
        ("B10", "benchmark_genai_education_vosviewer"),
    ]
    for bid, slug in targets:
        df = pd.read_csv(f"data/collected_{slug}.csv")
        texts = [
            f"{t}. {a}".strip()
            for t, a in zip(df["Title"].fillna("").astype(str), df["Abstract"].fillna("").astype(str))
            if a.strip()
        ]
        embeddings = embedder.encode(texts, show_progress_bar=False)

        with open(f"data/benchmarks/{slug}.json", "r", encoding="utf-8") as f:
            b_meta = json.load(f)
        clusters = b_meta.get("scientometrics", {}).get("clusters", [])
        cluster_sets = [tokenize_keywords(c["keywords"]) for c in clusters] if clusters else []

        ks, tds, outs, crs = [], [], [], []
        for seed in SEEDS:
            umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=seed)
            hdbscan_model = HDBSCAN(min_cluster_size=10, metric="euclidean", cluster_selection_method="eom", prediction_data=False)
            topic_model = BERTopic(umap_model=umap_model, hdbscan_model=hdbscan_model, verbose=False)
            topics, _ = topic_model.fit_transform(texts, embeddings=embeddings)

            info = topic_model.get_topic_info()
            valid = info[info["Topic"] != -1]
            k_val = int(len(valid))
            out_cnt = int(info[info["Topic"] == -1]["Count"].sum())
            out_pct = 100.0 * out_cnt / len(texts)

            t_words = []
            for tid in valid["Topic"]:
                words = [w for w, _ in topic_model.get_topic(int(tid))[:10]]
                t_words.append(words)
            td_val = compute_topic_diversity(t_words, top_k=10)

            ks.append(k_val)
            tds.append(td_val)
            outs.append(out_pct)
            if cluster_sets:
                t_sets = [tokenize_keywords(w) for w in t_words]
                _, rec_h, _ = match_topics_to_clusters(t_sets, cluster_sets, threshold=0.10)
                crs.append(100.0 * len(rec_h) / len(cluster_sets))

        cr_str = f", CR={np.mean(crs):.1f}%+/-{np.std(crs):.1f}%" if crs else ""
        print(
            f"{bid} (N_abs={len(texts)}): K={np.mean(ks):.2f}+/-{np.std(ks):.2f} (range {min(ks)}-{max(ks)}), "
            f"TD={np.mean(tds):.4f}+/-{np.std(tds):.4f}, Out={np.mean(outs):.1f}%+/-{np.std(outs):.1f}%{cr_str}"
        )


def eval_b08_outlier_audit():
    print("\n" + "=" * 80)
    print("F3b: SECOND OUTLIER AUDIT ON B08 (DISTANCE LEARNING, 56.5% OUTLIERS)")
    print("=" * 80)
    df = pd.read_csv("data/collected_benchmark_distance_learning_landscape.csv")
    texts = [
        (str(t).strip(), str(a).strip())
        for t, a in zip(df["Title"].fillna(""), df["Abstract"].fillna(""))
        if str(a).strip()
    ]
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    raw_docs = [f"{t}. {a}" for t, a in texts]
    embeddings = embedder.encode(raw_docs, show_progress_bar=False)
    umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42)
    hdbscan_model = HDBSCAN(min_cluster_size=10, metric="euclidean", cluster_selection_method="eom")
    topic_model = BERTopic(umap_model=umap_model, hdbscan_model=hdbscan_model, verbose=False)
    topics, _ = topic_model.fit_transform(raw_docs, embeddings=embeddings)

    out_indices = [i for i, t in enumerate(topics) if t == -1]
    print(f"B08 N_abs={len(texts)}, Topic -1 count={len(out_indices)} ({100*len(out_indices)/len(texts):.1f}%)")
    rng = np.random.default_rng(42)
    sample_idx = rng.choice(out_indices, size=min(30, len(out_indices)), replace=False)

    # Heuristic domain check: distance/online/e-learning/MOOC/blended/remote/virtual/student/education
    domain_kw = {"distance", "online", "learning", "education", "e-learning", "mooc", "blended", "remote", "virtual", "student", "teaching", "course"}
    in_domain = 0
    for idx in sample_idx:
        title, abst = texts[idx]
        blob = (title + " " + abst).lower()
        if any(k in blob for k in domain_kw):
            in_domain += 1
    print(f"B08 Topic -1 sample (n={len(sample_idx)}, seed 42): {in_domain}/{len(sample_idx)} ({100*in_domain/len(sample_idx):.1f}%) contain core distance/online education terms.")


def eval_author_disambiguation_orcid():
    print("\n" + "=" * 80)
    print("F6: AUTHOR DISAMBIGUATION BENCHMARK ON ORCID-LINKED OPENALEX SAMPLE")
    print("=" * 80)
    # Fetch 150 recent OpenAlex works with ORCIDs in Digital Transformation / Scientometrics
    url = "https://api.openalex.org/works?filter=has_orcid:true,publication_year:2020-2024&search=bibliometric+OR+scientometric&per-page=150&select=doi,title,authorships"
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    works = r.json().get("results", [])

    records = []
    ground_truth_occ = []  # list of (paper_idx, pos_idx, base_name, orcid)
    for p_idx, w in enumerate(works):
        authorships = w.get("authorships", [])
        names = []
        affils = []
        orcids = []
        for a in authorships:
            au = a.get("author") or {}
            name = (au.get("display_name") or "").strip()
            orcid = (au.get("orcid") or "").strip()
            insts = [i.get("display_name", "") for i in (a.get("institutions") or []) if i.get("display_name")]
            aff = insts[0] if insts else ""
            if name and orcid:
                names.append(name)
                affils.append(aff)
                orcids.append(orcid)
        if names:
            records.append({
                "DOI": w.get("doi") or f"doc_{p_idx}",
                "Title": w.get("title") or "",
                "Authors": "; ".join(names),
                "Affiliations": "; ".join(affils),
            })
            for pos, (nm, orc) in enumerate(zip(names, orcids)):
                ground_truth_occ.append((len(records) - 1, pos, nm, orc))

    df = pd.DataFrame(records)
    dis = AuthorDisambiguator()
    df_out, _ = dis.disambiguate_dataset(df)

    # Compare predicted disambiguated ID vs true ORCID
    orcid_to_preds = defaultdict(set)
    pred_to_orcids = defaultdict(set)
    occ_pairs = []

    for p_idx, row in df_out.iterrows():
        pred_list = [x.strip() for x in str(row["Disambiguated Authors"]).split(";") if x.strip()]
        gt_for_p = [g for g in ground_truth_occ if g[0] == p_idx]
        if len(pred_list) != len(gt_for_p):
            continue
        for pred_id, (_, _, _, true_orcid) in zip(pred_list, gt_for_p):
            orcid_to_preds[true_orcid].add(pred_id)
            pred_to_orcids[pred_id].add(true_orcid)
            occ_pairs.append((pred_id, true_orcid))

    n_orcids = len(orcid_to_preds)
    n_preds = len(pred_to_orcids)
    split_orcids = sum(1 for v in orcid_to_preds.values() if len(v) > 1)
    merged_preds = sum(1 for v in pred_to_orcids.values() if len(v) > 1)

    # Pairwise Precision / Recall / F1 over occurrences
    tp = fp = fn = 0
    for i in range(len(occ_pairs)):
        for j in range(i + 1, len(occ_pairs)):
            same_pred = occ_pairs[i][0] == occ_pairs[j][0]
            same_true = occ_pairs[i][1] == occ_pairs[j][1]
            if same_pred and same_true:
                tp += 1
            elif same_pred and not same_true:
                fp += 1
            elif not same_pred and same_true:
                fn += 1

    prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    print(f"ORCID-linked papers: {len(df)}, Author occurrences: {len(occ_pairs)}, Unique ORCIDs: {n_orcids}, Predicted IDs: {n_preds}")
    print(f"Splitting rate (ORCIDs split across >1 predicted ID): {split_orcids}/{n_orcids} ({100*split_orcids/n_orcids:.2f}%)")
    print(f"Merging rate (predicted IDs merging >1 ORCID):      {merged_preds}/{n_preds} ({100*merged_preds/n_preds:.2f}%)")
    print(f"Pairwise P={prec:.4f}, R={rec:.4f}, F1={f1:.4f} (TP={tp}, FP={fp}, FN={fn})")


if __name__ == "__main__":
    eval_bertopic_stability()
    eval_b08_outlier_audit()
    eval_author_disambiguation_orcid()
