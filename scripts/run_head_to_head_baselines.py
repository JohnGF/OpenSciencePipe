#!/usr/bin/env python3
"""
Direct Head-to-Head Baseline Evaluation Script (100% Computed, Zero Literals):
1. Panel A: Real Latent Dirichlet Allocation (LDA; Blei et al., 2003) via scikit-learn
   at K = K_pub across 5 random seeds (42..46), evaluated on:
   - All documents with non-empty abstracts (LDA All)
   - Matched non-outlier document count (LDA Matched-N)
   Compared against OpenSciencePipe (BERTopic + HDBSCAN) using Hungarian matching
   at Jaccard threshold tau = 0.10 and an exact McNemar test over published clusters.
2. Panel B: Real NetworkX Louvain community detection on the actual co-authorship
   graphs (network_nodes.csv / network_edges.csv) in outputs/.
   If RAPIDS cuGraph is installed, also runs GPU Louvain and computes partition NMI.
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import binomtest
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.evaluate_thematic_validation import (
    BENCHMARK_SLUGS,
    load_extracted_topics,
    tokenize_keywords,
    match_topics_to_clusters,
)
from scripts.evaluate_clustering_benchmarks import compute_topic_diversity

SEEDS = [42, 43, 44, 45, 46]
JACCARD_THRESHOLD = 0.10


def run_lda_on_texts(texts: list, k_topics: int, seed: int, top_n: int = 10) -> list:
    vec = CountVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_features=5000,
    )
    dtm = vec.fit_transform(texts)
    vocab = vec.get_feature_names_out()
    lda = LatentDirichletAllocation(
        n_components=k_topics,
        max_iter=20,
        learning_method="batch",
        random_state=seed,
    )
    lda.fit(dtm)
    topic_words = []
    for comp in lda.components_:
        top_idx = comp.argsort()[-top_n:][::-1]
        topic_words.append([vocab[i] for i in top_idx])
    return topic_words


def evaluate_panel_a():
    panel_a = []
    # For exact McNemar test across verified clusters (seed 42 LDA vs BERTopic)
    mcnemar_b = 0  # BERTopic=1, LDA=0
    mcnemar_c = 0  # BERTopic=0, LDA=1

    for bid, short_name, slug in BENCHMARK_SLUGS:
        json_path = f"data/benchmarks/{slug}.json"
        csv_path = f"data/collected_{slug}.csv"
        topic_path = f"outputs/pipeline_results_{slug}/topic_info.csv"

        with open(json_path, "r", encoding="utf-8") as f:
            b_meta = json.load(f)

        clusters = b_meta.get("scientometrics", {}).get("clusters", [])
        if not clusters:
            continue

        df_corpus = pd.read_csv(csv_path)
        texts = [
            f"{t}. {a}".strip()
            for t, a in zip(
                df_corpus["Title"].fillna("").astype(str),
                df_corpus["Abstract"].fillna("").astype(str),
            )
            if a.strip()
        ]

        topics = load_extracted_topics(topic_path)
        df_topics_full = pd.read_csv(topic_path)
        total_clustered = int(df_topics_full["Count"].sum())
        out_row = df_topics_full[df_topics_full["Topic"] == -1]
        out_count = int(out_row["Count"].values[0]) if not out_row.empty else 0
        non_out_count = total_clustered - out_count
        out_pct = (out_count / total_clustered * 100.0) if total_clustered > 0 else 0.0

        cluster_sets = [tokenize_keywords(c["keywords"]) for c in clusters]
        k_pub = len(clusters)

        # BERTopic evaluation
        osp_words = [t["words"][:10] for t in topics]
        osp_sets = [tokenize_keywords(w) for w in osp_words]
        _, osp_hung, _ = match_topics_to_clusters(osp_sets, cluster_sets, threshold=JACCARD_THRESHOLD)
        osp_td = compute_topic_diversity(osp_words, top_k=10)

        # LDA across 5 seeds (All non-empty abstract docs)
        lda_all_rec = []
        lda_all_td = []
        lda_seed42_hung = set()
        for seed in SEEDS:
            w_list = run_lda_on_texts(texts, k_pub, seed)
            w_sets = [tokenize_keywords(w) for w in w_list]
            _, r_h, _ = match_topics_to_clusters(w_sets, cluster_sets, threshold=JACCARD_THRESHOLD)
            lda_all_rec.append(len(r_h))
            lda_all_td.append(compute_topic_diversity(w_list, top_k=10))
            if seed == 42:
                lda_seed42_hung = r_h

        # LDA across 5 seeds (Matched-N = same non-outlier document count)
        lda_match_rec = []
        rng = np.random.default_rng(42)
        n_sample = min(non_out_count, len(texts))
        for seed in SEEDS:
            idx = rng.choice(len(texts), size=n_sample, replace=False)
            sub_texts = [texts[i] for i in idx]
            w_list = run_lda_on_texts(sub_texts, k_pub, seed)
            w_sets = [tokenize_keywords(w) for w in w_list]
            _, r_h, _ = match_topics_to_clusters(w_sets, cluster_sets, threshold=JACCARD_THRESHOLD)
            lda_match_rec.append(len(r_h))

        for c_idx in range(k_pub):
            in_osp = c_idx in osp_hung
            in_lda = c_idx in lda_seed42_hung
            if in_osp and not in_lda:
                mcnemar_b += 1
            elif not in_osp and in_lda:
                mcnemar_c += 1

        panel_a.append({
            "id": bid,
            "name": f"{bid}: {short_name}",
            "docs_abs": len(texts),
            "docs_non_out": non_out_count,
            "k_pub": k_pub,
            "lda_all_mean": float(np.mean(lda_all_rec)),
            "lda_all_std": float(np.std(lda_all_rec)),
            "lda_match_mean": float(np.mean(lda_match_rec)),
            "lda_td": float(np.mean(lda_all_td)),
            "osp_rec": len(osp_hung),
            "osp_td": osp_td,
            "osp_out": out_pct,
        })

    n_disc = mcnemar_b + mcnemar_c
    mcnemar_p = float(binomtest(min(mcnemar_b, mcnemar_c), n_disc, 0.5).pvalue) if n_disc > 0 else 1.0
    return panel_a, (mcnemar_b, mcnemar_c, mcnemar_p)


def evaluate_panel_b():
    graph_targets = [
        ("B07", "B07: Digital Transformation", "outputs/pipeline_results_benchmark_digital_transformation_kraus2021"),
        ("B03", "B03: Modified Biochar", "outputs/pipeline_results_benchmark_biochar_citespace"),
        ("B12", "B12: Soil Microplastics", "outputs/pipeline_results_benchmark_microplastics_soil"),
        ("B04", "B04: Blockchain Technology", "outputs/pipeline_results_benchmark_blockchain_vosviewer"),
        ("EEG18k", "EEG Co-Authorship Subset", "outputs/pipeline_results_18k"),
    ]
    has_cugraph = False
    try:
        import cudf
        import cugraph
        from sklearn.metrics import normalized_mutual_info_score
        has_cugraph = True
    except ImportError:
        pass

    panel_b = []
    for gid, label, out_dir in graph_targets:
        nodes_p = os.path.join(out_dir, "network_nodes.csv")
        edges_p = os.path.join(out_dir, "network_edges.csv")
        if not (os.path.exists(nodes_p) and os.path.exists(edges_p)):
            continue
        edges_df = pd.read_csv(edges_p)
        G = nx.Graph()
        src_col = next((c for c in ["Source", "source"] if c in edges_df.columns), None)
        dst_col = next((c for c in ["Target", "target", "destination", "Destination"] if c in edges_df.columns), None)
        if not src_col or not dst_col:
            continue
        for _, row in edges_df.iterrows():
            G.add_edge(row[src_col], row[dst_col])

        t0 = time.perf_counter()
        comms = nx.community.louvain_communities(G, seed=42)
        cpu_s = time.perf_counter() - t0
        q_cpu = nx.community.modularity(G, comms)

        row_dict = {
            "corpus": label,
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "comms": len(comms),
            "q_cpu": q_cpu,
            "cpu_time": f"{cpu_s:.3f}\\,s" if cpu_s < 1.0 else f"{cpu_s:.2f}\\,s",
            "has_cugraph": has_cugraph,
            "q_gpu": None,
            "nmi": None,
            "gpu_time": None,
        }

        if has_cugraph:
            node_list = sorted(G.nodes(), key=str)
            node_to_idx = {n: i for i, n in enumerate(node_list)}
            cpu_part = {}
            for c_id, c_nodes in enumerate(comms):
                for n in c_nodes:
                    cpu_part[node_to_idx[n]] = c_id

            edge_rows = [(node_to_idx[u], node_to_idx[v]) for u, v in G.edges()]
            pdf_edges = pd.DataFrame(edge_rows, columns=["src", "dst"])
            gdf_edges = cudf.DataFrame.from_pandas(pdf_edges)
            G_gpu = cugraph.Graph()
            G_gpu.from_cudf_edgelist(gdf_edges, source="src", destination="dst", renumber=False)

            gpu_times = []
            parts_df = None
            q_gpu = 0.0
            for _ in range(10):
                tg0 = time.perf_counter()
                parts_df, q_gpu = cugraph.louvain(G_gpu)
                gpu_times.append(time.perf_counter() - tg0)

            parts_pd = parts_df.to_pandas()
            gpu_part = dict(zip(parts_pd["vertex"].astype(int), parts_pd["partition"].astype(int)))
            common_v = sorted(cpu_part.keys() & gpu_part.keys())
            y_cpu = [cpu_part[v] for v in common_v]
            y_gpu = [gpu_part[v] for v in common_v]
            nmi_val = float(normalized_mutual_info_score(y_cpu, y_gpu))

            mean_gpu_s = float(np.mean(gpu_times))
            speedup = cpu_s / mean_gpu_s if mean_gpu_s > 0 else 0.0
            gpu_str = (
                f"{mean_gpu_s*1000:.1f}\\,ms (${speedup:.1f}\\times$)"
                if mean_gpu_s < 0.1
                else f"{mean_gpu_s:.2f}\\,s (${speedup:.1f}\\times$)"
            )
            row_dict.update({
                "q_gpu": float(q_gpu),
                "nmi": nmi_val,
                "gpu_time": gpu_str,
            })

        panel_b.append(row_dict)
    return panel_b


def main():
    print("Running Panel A (Real LDA vs BERTopic across verified benchmarks)...")
    panel_a, (mb, mc, mp) = evaluate_panel_a()
    print("Running Panel B (Real NetworkX Louvain benchmarks)...")
    panel_b = evaluate_panel_b()

    total_docs = sum(r["docs_abs"] for r in panel_a)
    total_k = sum(r["k_pub"] for r in panel_a)
    total_osp = sum(r["osp_rec"] for r in panel_a)
    total_lda_all = sum(r["lda_all_mean"] for r in panel_a)
    total_lda_match = sum(r["lda_match_mean"] for r in panel_a)
    mean_lda_td = float(np.mean([r["lda_td"] for r in panel_a]))
    mean_osp_td = float(np.mean([r["osp_td"] for r in panel_a]))
    mean_osp_out = float(np.mean([r["osp_out"] for r in panel_a]))

    print(f"Panel A Summary (n={len(panel_a)} verified benchmarks, K_pub={total_k}):")
    print(f"  LDA (All, 5-seed mean):       {total_lda_all:.1f}/{total_k} ({100*total_lda_all/total_k:.1f}%), TD={mean_lda_td:.2f}")
    print(f"  LDA (Matched-N, 5-seed mean): {total_lda_match:.1f}/{total_k} ({100*total_lda_match/total_k:.1f}%)")
    print(f"  OpenSciencePipe (Hungarian):  {total_osp}/{total_k} ({100*total_osp/total_k:.1f}%), TD={mean_osp_td:.2f}")
    print(f"  Exact McNemar (b={mb}, c={mc}): p={mp:.4f}")

    out_tex = "manuscripts/paper4_opensciencepipe_landmark/tables/tab_baseline_thematic_graph.tex"
    lines = [
        "% Auto-generated by scripts/run_head_to_head_baselines.py",
        "\\begin{table*}[t]",
        "\\centering",
        "\\scriptsize",
        "\\renewcommand{\\arraystretch}{0.90}",
        "\\caption{Head-to-Head Baseline Comparison: Thematic Cluster Recovery (Classical LDA vs.\\ OpenSciencePipe) and CPU Graph Partitioning}",
        "\\label{tab:baseline_thematic_graph}",
        "\\resizebox{\\textwidth}{!}{%",
        "\\begin{tabular}{l c c ccc ccc}",
        "\\hline",
        "\\multicolumn{9}{l}{\\textbf{Panel A: Thematic Cluster Recovery on Verified Ground-Truth Benchmarks (5-Seed LDA at $K = K_{\\text{pub}}$, Hungarian $\\tau = 0.10$)}} \\\\",
        "\\hline",
        "& & & \\multicolumn{3}{c}{\\textbf{Classical LDA (Blei et al., 2003)}} & \\multicolumn{3}{c}{\\textbf{OpenSciencePipe (BERTopic + HDBSCAN)}} \\\\",
        "\\cline{4-6} \\cline{7-9}",
        "\\textbf{Benchmark Investigation} & \\textbf{Docs ($N_{\\text{abs}}$)} & \\textbf{$K_{\\text{pub}}$} & \\textbf{Rec. (All)} & \\textbf{Rec. (Matched-$N$)} & \\textbf{TD} & \\textbf{Recovered} & \\textbf{TD} & \\textbf{Outliers} \\\\",
        "\\hline",
    ]
    for r in panel_a:
        lines.append(
            f"{r['name']} & {r['docs_abs']} & {r['k_pub']} & "
            f"{r['lda_all_mean']:.1f}/{r['k_pub']} ({100*r['lda_all_mean']/r['k_pub']:.1f}\\%) & "
            f"{r['lda_match_mean']:.1f}/{r['k_pub']} ({100*r['lda_match_mean']/r['k_pub']:.1f}\\%) & "
            f"{r['lda_td']:.2f} & "
            f"\\textbf{{{r['osp_rec']}/{r['k_pub']} ({100*r['osp_rec']/r['k_pub']:.1f}\\%)}} & "
            f"\\textbf{{{r['osp_td']:.2f}}} & {r['osp_out']:.1f}\\% \\\\"
        )
    lines.extend([
        "\\hline",
        (
            f"\\textbf{{Total / Summary Mean}} & \\textbf{{{total_docs:,}}} & \\textbf{{{total_k}}} & "
            f"\\textbf{{{total_lda_all:.1f}/{total_k} ({100*total_lda_all/total_k:.1f}\\%)}} & "
            f"\\textbf{{{total_lda_match:.1f}/{total_k} ({100*total_lda_match/total_k:.1f}\\%)}} & "
            f"\\textbf{{{mean_lda_td:.2f}}} & "
            f"\\textbf{{{total_osp}/{total_k} ({100*total_osp/total_k:.1f}\\%)}} & "
            f"\\textbf{{{mean_osp_td:.2f}}} & \\textbf{{{mean_osp_out:.1f}\\%}} \\\\"
        ),
        "\\hline",
        "\\multicolumn{9}{l}{\\textbf{Panel B: Co-Authorship Graph Partitioning (NetworkX CPU vs.\\ RAPIDS cuGraph GPU Louvain)}} \\\\",
        "\\hline",
        "\\textbf{Corpus} & \\textbf{Nodes} & \\textbf{Edges} & \\textbf{Comms} & \\textbf{$Q_{\\text{CPU}}$} & \\textbf{$Q_{\\text{GPU}}$} & \\textbf{NMI} & \\textbf{CPU (NetworkX)} & \\textbf{GPU (cuGraph)} \\\\",
        "\\hline",
    ])
    for g in panel_b:
        if g["has_cugraph"] and g["q_gpu"] is not None:
            lines.append(
                f"{g['corpus']} & {g['nodes']:,} & {g['edges']:,} & {g['comms']:,} & "
                f"{g['q_cpu']:.4f} & {g['q_gpu']:.4f} & {g['nmi']:.3f} & {g['cpu_time']} & {g['gpu_time']} \\\\"
            )
        else:
            lines.append(
                f"{g['corpus']} & {g['nodes']:,} & {g['edges']:,} & {g['comms']:,} & "
                f"{g['q_cpu']:.4f} & -- & -- & {g['cpu_time']} & Container-only \\\\"
            )
    lines.extend([
        "\\hline",
        "\\end{tabular}%",
        "}",
        (
            f"\\vspace{{2pt}}\\par\\raggedright\\scriptsize\\textit{{Note:}} Panel~A evaluates scikit-learn \\texttt{{LatentDirichletAllocation}} "
            f"(English stop words, 1--2-grams, \\texttt{{min\\_df=2}}, 20 batch iterations, seeds 42--46) on both all non-empty abstract documents and "
            f"matched non-outlier document counts against OpenSciencePipe using one-to-one Hungarian matching at Jaccard threshold $\\tau = 0.10$ "
            f"(exact McNemar test between OpenSciencePipe and seed-42 LDA: $b={mb}, c={mc}, p={mp:.4f}$). "
            f"Panel~B reports reproducible host CPU Louvain timings via NetworkX on the exported \\texttt{{network\\_edges.csv}} graphs; "
            f"GPU \\texttt{{cuGraph}} execution requires the RAPIDS container environment."
        ),
        "\\end{table*}",
    ])
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_tex}")


if __name__ == "__main__":
    main()
