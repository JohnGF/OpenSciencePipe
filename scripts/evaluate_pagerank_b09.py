#!/usr/bin/env python3
"""
PageRank Benchmark: NetworkX (CPU) vs. igraph (C/C++ CPU) vs. cuGraph (GPU).

Evaluates PageRank (damping alpha=0.85) on the exported EEG co-authorship graphs:
- EEG 18k Subset (outputs/pipeline_results_18k/network_edges.csv: 11,937 nodes, 50,668 edges)
- EEG 37k Subset (outputs/pipeline_results_37k/data/network_edges.csv: 86,157 nodes, 405,918 edges)

Run on host for igraph/NetworkX:
    uv run python scripts/evaluate_pagerank_b09.py
Run in RAPIDS container for cuGraph/NetworkX:
    podman exec biblio-dev python scripts/evaluate_pagerank_b09.py
"""

import os
import time
import numpy as np
import pandas as pd
import networkx as nx


def bench_target(label: str, path: str, repeats: int = 5):
    if not os.path.exists(path):
        print(f"{label:20s} | MISSING {path}")
        return
    df = pd.read_csv(path)
    c0, c1 = df.columns[0], df.columns[1]
    w_col = df.columns[2] if len(df.columns) > 2 else None

    # 1. NetworkX CPU
    G_nx = nx.Graph()
    if w_col:
        G_nx.add_weighted_edges_from(
            zip(df[c0].astype(str), df[c1].astype(str), df[w_col].astype(float))
        )
    else:
        G_nx.add_edges_from(zip(df[c0].astype(str), df[c1].astype(str)))

    nx_times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        pr_nx = nx.pagerank(G_nx, alpha=0.85, weight="weight" if w_col else None)
        nx_times.append(time.perf_counter() - t0)
    print(
        f"{label:20s} | V={G_nx.number_of_nodes():6,d} E={G_nx.number_of_edges():7,d} | "
        f"NetworkX={np.mean(nx_times):.4f} +/- {np.std(nx_times):.4f} s"
    )

    # 2. igraph C/C++ CPU (if installed)
    try:
        import igraph as ig

        tuples = (
            list(zip(df[c0].astype(str), df[c1].astype(str), df[w_col].astype(float)))
            if w_col
            else list(zip(df[c0].astype(str), df[c1].astype(str)))
        )
        g_ig = ig.Graph.TupleList(tuples, directed=False, weights=bool(w_col))
        ig_times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            g_ig.pagerank(damping=0.85, weights="weight" if w_col else None)
            ig_times.append(time.perf_counter() - t0)
        print(
            f"{'':20s} | igraph  ={np.mean(ig_times):.4f} +/- {np.std(ig_times):.4f} s "
            f"({np.mean(nx_times)/np.mean(ig_times):.1f}x vs NetworkX)"
        )
    except ImportError:
        pass

    # 3. cuGraph GPU (if installed)
    try:
        import cudf
        import cugraph

        nodes = sorted(G_nx.nodes())
        idx_map = {n: i for i, n in enumerate(nodes)}
        src = [idx_map[u] for u, v in G_nx.edges()]
        dst = [idx_map[v] for u, v in G_nx.edges()]
        pdf = pd.DataFrame({"src": src, "dst": dst})
        if w_col:
            pdf["w"] = [float(d.get("weight", 1.0)) for _, _, d in G_nx.edges(data=True)]
        gdf = cudf.DataFrame.from_pandas(pdf)
        G_gpu = cugraph.Graph()
        G_gpu.from_cudf_edgelist(
            gdf, source="src", destination="dst", edge_attr="w" if w_col else None, renumber=False
        )
        # Warmup
        cugraph.pagerank(G_gpu, alpha=0.85)
        gpu_times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            cugraph.pagerank(G_gpu, alpha=0.85)
            gpu_times.append(time.perf_counter() - t0)
        print(
            f"{'':20s} | cuGraph ={np.mean(gpu_times):.4f} +/- {np.std(gpu_times):.4f} s "
            f"({np.mean(nx_times)/np.mean(gpu_times):.1f}x vs NetworkX)"
        )
    except ImportError:
        pass


def main():
    targets = [
        ("EEG 18k Subset", "outputs/pipeline_results_18k/network_edges.csv"),
        ("EEG 37k Subset", "outputs/pipeline_results_37k/data/network_edges.csv"),
    ]
    for label, path in targets:
        bench_target(label, path, repeats=5)


if __name__ == "__main__":
    main()
