#!/usr/bin/env python3
"""
CPU C/C++ igraph Louvain Baseline Benchmark.

Benchmarks igraph's compiled C/C++ community_multilevel (Louvain) on:
1. Compact benchmark graphs (B03, B04, B07, B12)
2. Medium EEG co-authorship subset (outputs/pipeline_results_37k/data/network_edges.csv)
3. Full 57,601-doc EEG co-authorship graph (constructed from data/collected_EEG_expanded_33k_2014_2026.csv
   or outputs/bertopic_clean/doc_topics.csv joined with data/collected_EEG_master_merged.csv)
"""

import os
import time
import igraph as ig
import pandas as pd


def load_igraph_from_edges_csv(path: str) -> ig.Graph:
    df = pd.read_csv(path)
    src_col = "Source" if "Source" in df.columns else df.columns[0]
    dst_col = "Target" if "Target" in df.columns else df.columns[1]
    w_col = "Weight" if "Weight" in df.columns else None
    tuples = (
        list(zip(df[src_col].astype(str), df[dst_col].astype(str), df[w_col].astype(float)))
        if w_col
        else list(zip(df[src_col].astype(str), df[dst_col].astype(str)))
    )
    return ig.Graph.TupleList(tuples, directed=False, weights=bool(w_col))


def bench_graph(name: str, g: ig.Graph, repeats: int = 5):
    times = []
    q_val = 0.0
    for _ in range(repeats):
        t0 = time.perf_counter()
        part = g.community_multilevel(weights="weight" if "weight" in g.es.attributes() else None)
        times.append(time.perf_counter() - t0)
        q_val = part.modularity
    mean_s = sum(times) / len(times)
    print(
        f"{name:28s} | V={g.vcount():7,d} | E={g.ecount():7,d} | "
        f"igraph={mean_s*1000:7.2f} ms ({mean_s:.4f} s) | Q={q_val:.4f}"
    )


def main():
    compact = [
        ("B03: Modified Biochar", "outputs/pipeline_results_benchmark_biochar_citespace/network_edges.csv"),
        ("B04: Blockchain Tech", "outputs/pipeline_results_benchmark_blockchain_vosviewer/network_edges.csv"),
        ("B07: Digital Transform", "outputs/pipeline_results_benchmark_digital_transformation_kraus2021/network_edges.csv"),
        ("B12: Soil Microplastics", "outputs/pipeline_results_benchmark_microplastics_soil/network_edges.csv"),
        ("EEG 18k Subset", "outputs/pipeline_results_18k/network_edges.csv"),
        ("EEG 37k Subset", "outputs/pipeline_results_37k/data/network_edges.csv"),
    ]
    for label, path in compact:
        if os.path.exists(path):
            g = load_igraph_from_edges_csv(path)
            bench_graph(label, g, repeats=5)
        else:
            print(f"{label:28s} | MISSING {path}")


if __name__ == "__main__":
    main()
