#!/usr/bin/env python3
"""
Generates publication-grade PDF figures for the OpenSciencePipe manuscript:
1. figures/network_force_community.pdf (Figure 2a): Force-directed community
   layout of the Electrophysiology co-authorship core (colored by igraph
   Louvain community, labeling only the top hub author(s) per community).
2. figures/benchmark_cr_country_bars.pdf (Figure 3): Two-panel comparison of
   (a) per-benchmark Cluster Recovery (BERTopic vs 5-seed LDA vs chance) and
   (b) per-benchmark Top-5 Nation Overlap (OpenSciencePipe vs Naive Global Top-5).
"""

import os
import sys
import json
from collections import Counter
import numpy as np
import pandas as pd
import igraph as ig
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.ingestion import extract_countries
from scripts.regenerate_table5 import BENCHMARKS, NAIVE_GLOBAL_TOP5, norm_country
from scripts.run_head_to_head_baselines import evaluate_panel_a

FIG_DIR = "manuscripts/paper4_opensciencepipe_landmark/figures"


def build_force_community_figure():
    edges_df = pd.read_csv("outputs/paper3_clean/network_edges.csv")
    src = "Source" if "Source" in edges_df.columns else "source"
    dst = "Target" if "Target" in edges_df.columns else ("target" if "target" in edges_df.columns else "destination")
    edges = list(zip(edges_df[src].astype(str), edges_df[dst].astype(str)))
    g = ig.Graph.TupleList(edges, directed=False)
    part = g.community_multilevel()

    # Select top 8 largest communities (each >= 15 nodes) and top 18 nodes per community by degree
    comm_sizes = sorted([(cid, len(nodes)) for cid, nodes in enumerate(part)], key=lambda x: -x[1])
    top_cids = [cid for cid, _ in comm_sizes[:8]]
    cid_to_rank = {cid: idx for idx, cid in enumerate(top_cids)}

    keep_vertices = []
    vertex_comm = {}
    for cid in top_cids:
        nodes = part[cid]
        degs = [(v, g.degree(v)) for v in nodes]
        degs.sort(key=lambda x: -x[1])
        for v, _ in degs[:18]:
            keep_vertices.append(v)
            vertex_comm[v] = cid_to_rank[cid]

    sub = g.induced_subgraph(keep_vertices)
    # Map subgraph vertex index -> community rank
    sub_comms = [vertex_comm[v] for v in keep_vertices]
    sub_names = [g.vs[v]["name"] for v in keep_vertices]
    sub_degs = np.array([g.degree(v) for v in keep_vertices], dtype=float)

    layout = sub.layout_fruchterman_reingold(niter=800)
    coords = np.array(layout.coords)

    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=300)
    cmap = plt.get_cmap("tab10")

    # Draw edges lightly
    for e in sub.es:
        u, v = e.tuple
        ax.plot(
            [coords[u, 0], coords[v, 0]],
            [coords[u, 1], coords[v, 1]],
            color="#9aa0a6",
            alpha=0.22,
            linewidth=0.5,
            zorder=1,
        )

    # Draw nodes colored by community
    node_sizes = 25 + 180 * (sub_degs - sub_degs.min()) / max(sub_degs.max() - sub_degs.min(), 1.0)
    node_colors = [cmap(c % 10) for c in sub_comms]
    ax.scatter(
        coords[:, 0],
        coords[:, 1],
        s=node_sizes,
        c=node_colors,
        edgecolors="white",
        linewidths=0.6,
        alpha=0.92,
        zorder=2,
    )

    # Label only the top 1 hub author per community
    for c_rank in range(len(top_cids)):
        c_indices = [i for i, c in enumerate(sub_comms) if c == c_rank]
        if not c_indices:
            continue
        best_i = max(c_indices, key=lambda i: sub_degs[i])
        label = sub_names[best_i]
        # Shorten long names cleanly
        parts = label.split()
        if len(parts) >= 2:
            label = f"{parts[0][0]}. {' '.join(parts[1:])}"
        ax.annotate(
            label,
            (coords[best_i, 0], coords[best_i, 1]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7.5,
            fontweight="bold",
            color="#202124",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
            zorder=3,
        )

    ax.set_title(
        f"Force-Directed Co-Authorship Core (Top 8 Louvain Communities, $N={sub.vcount()}$ Hubs)",
        fontsize=9.5,
        pad=8,
    )
    ax.axis("off")
    plt.tight_layout()
    out_p = os.path.join(FIG_DIR, "network_force_community.pdf")
    fig.savefig(out_p, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_p}")


def build_cr_country_bars_figure():
    panel_a, _ = evaluate_panel_a()
    # Order by benchmark ID
    panel_a = sorted(panel_a, key=lambda r: r["id"])
    cr_labels = [r["id"] for r in panel_a]
    osp_cr = [100.0 * r["osp_rec"] / r["k_pub"] for r in panel_a]
    lda_cr = [100.0 * r["lda_all_mean"] / r["k_pub"] for r in panel_a]
    chance_cr = [5.9] * len(panel_a)  # Empirical permutation baseline at tau=0.10

    # Country overlap across 16 benchmarks
    c_labels, pipe_ov, naive_ov = [], [], []
    for bid, _, _, slug in BENCHMARKS:
        if bid == "B09":
            continue
        with open(f"data/benchmarks/{slug}.json", "r", encoding="utf-8") as f:
            b_meta = json.load(f)
        gt_raw = b_meta.get("scientometrics", {}).get("top_countries", [])
        if not gt_raw:
            continue
        gt_top5 = [norm_country(c["country"] if isinstance(c, dict) else c) for c in gt_raw[:5]]
        df_c = pd.read_csv(f"data/collected_{slug}.csv")
        counts = Counter()
        if "Affiliations" in df_c.columns:
            for aff in df_c["Affiliations"].dropna():
                for country in extract_countries(str(aff)):
                    counts[norm_country(country)] += 1
        pipe_top5 = [c for c, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:5]]
        c_labels.append(bid)
        pipe_ov.append(100.0 * len(set(pipe_top5) & set(gt_top5)) / len(gt_top5))
        naive_ov.append(100.0 * len(NAIVE_GLOBAL_TOP5 & set(gt_top5)) / len(gt_top5))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.0), dpi=300, gridspec_kw={"width_ratios": [1.0, 1.8]})

    # Panel A: Cluster Recovery
    x1 = np.arange(len(cr_labels))
    w1 = 0.35
    ax1.bar(x1 - w1 / 2, osp_cr, width=w1, label="OpenSciencePipe (BERTopic)", color="#1f77b4")
    ax1.bar(x1 + w1 / 2, lda_cr, width=w1, label="Classical LDA (5-seed mean)", color="#ff7f0e")
    ax1.axhline(5.9, color="#d62728", linestyle="--", linewidth=1.1, label="Permutation baseline (5.9%)")
    ax1.set_xticks(x1)
    ax1.set_xticklabels(cr_labels, fontsize=8.5)
    ax1.set_ylim(0, 85)
    ax1.set_ylabel("Cluster Recovery (%)", fontsize=9)
    ax1.set_title("(a) Thematic Cluster Recovery ($\\tau = 0.10$, Hungarian)", fontsize=9.5)
    ax1.grid(axis="y", linestyle=":", alpha=0.5)
    ax1.legend(fontsize=7.5, loc="upper right")

    # Panel B: Country Overlap
    x2 = np.arange(len(c_labels))
    w2 = 0.36
    ax2.bar(x2 - w2 / 2, pipe_ov, width=w2, label=f"OpenSciencePipe (mean {np.mean(pipe_ov):.1f}%)", color="#2ca02c")
    ax2.bar(x2 + w2 / 2, naive_ov, width=w2, label=f"Naive Global Top-5 (mean {np.mean(naive_ov):.1f}%)", color="#7f7f7f")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(c_labels, fontsize=7.5, rotation=35, ha="right")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Top-5 Nation Overlap (%)", fontsize=9)
    ax2.set_title("(b) Top-5 Nation Overlap: Pipeline vs. Naive Global Baseline", fontsize=9.5)
    ax2.grid(axis="y", linestyle=":", alpha=0.5)
    ax2.legend(fontsize=7.5, loc="upper right")

    plt.tight_layout()
    out_p = os.path.join(FIG_DIR, "benchmark_cr_country_bars.pdf")
    fig.savefig(out_p, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_p}")


if __name__ == "__main__":
    os.makedirs(FIG_DIR, exist_ok=True)
    build_force_community_figure()
    build_cr_country_bars_figure()
