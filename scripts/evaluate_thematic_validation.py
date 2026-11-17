#!/usr/bin/env python3
"""
Thematic Validation Script: Comparing Discovered Neural Topics against Published Scientometric Clusters.
Reads published cluster ground-truth definitions strictly from data/benchmarks/*.json (scientometrics.clusters).

Implements:
- Minimum Jaccard similarity threshold (default tau = 0.10, with sensitivity at 0.05 and 0.15)
- Many-to-one best-match and one-to-one Hungarian assignment (scipy.optimize.linear_sum_assignment)
- Analytical chance floor: 1 - (1 - 1/K_pub)^K
- Empirical permutation baseline (1,000 shuffles of topic keyword sets across benchmarks)
"""

import os
import json
import ast
import random
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from scipy.optimize import linear_sum_assignment

BENCHMARK_SLUGS = [
    ("B07", "Digital Transformation", "benchmark_digital_transformation_kraus2021"),
    ("B03", "Modified Biochar Heavy Metals", "benchmark_biochar_citespace"),
    ("B12", "Soil Microplastics", "benchmark_microplastics_soil"),
    ("B04", "Blockchain Technology", "benchmark_blockchain_vosviewer"),
    ("B08", "Distance Learning Landscape", "benchmark_distance_learning_landscape"),
    ("B10", "Generative AI in Education", "benchmark_genai_education_vosviewer"),
    ("B14", "Top 100 in Public Health", "benchmark_public_health_top100"),
    ("B16", "Solar Power Generation", "benchmark_solar_power_generation"),
    ("B17", "Sustainable Business Performance", "benchmark_sustainable_business_performance"),
    ("B15", "Social Work and Migration", "benchmark_social_work_migration"),
]


def load_extracted_topics(csv_path: str) -> List[Dict]:
    """Loads discovered topics (excluding Topic -1 noise)."""
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    topics = []
    for _, row in df[df["Topic"] != -1].iterrows():
        rep = row.get("Representation", "[]")
        if isinstance(rep, str):
            try:
                words = ast.literal_eval(rep)
            except Exception:
                words = [w.strip(" '\"[]") for w in rep.split(",")]
        elif isinstance(rep, list):
            words = rep
        else:
            words = []
        topics.append({
            "topic_id": int(row["Topic"]),
            "count": int(row["Count"]),
            "name": str(row["Name"]),
            "words": [str(w).lower().strip() for w in words if str(w).strip()],
        })
    return topics


def tokenize_keywords(kw_list: List[str]) -> set:
    tokens = set()
    for kw in kw_list:
        kw_l = kw.lower().strip()
        if kw_l:
            tokens.add(kw_l)
            for part in kw_l.split():
                tokens.add(part)
    return tokens


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_topics_to_clusters(
    topic_word_sets: List[set],
    cluster_word_sets: List[set],
    threshold: float = 0.10,
) -> Tuple[set, set, List[Tuple[int, int, float]]]:
    """
    Returns:
      - recovered_many_to_one: set of cluster indices matched with Jaccard >= threshold
      - recovered_hungarian: set of cluster indices matched 1-to-1 via Hungarian with Jaccard >= threshold
      - per_topic_best: list of (topic_idx, best_cluster_idx, best_jaccard)
    """
    n_t = len(topic_word_sets)
    n_c = len(cluster_word_sets)
    if n_t == 0 or n_c == 0:
        return set(), set(), []

    sim_mat = np.zeros((n_t, n_c), dtype=float)
    for i, tw in enumerate(topic_word_sets):
        for j, cw in enumerate(cluster_word_sets):
            sim_mat[i, j] = jaccard(tw, cw)

    recovered_m2o = set()
    per_topic_best = []
    for i in range(n_t):
        j_best = int(np.argmax(sim_mat[i]))
        s_best = float(sim_mat[i, j_best])
        per_topic_best.append((i, j_best, s_best))
        if s_best >= threshold:
            recovered_m2o.add(j_best)

    row_ind, col_ind = linear_sum_assignment(-sim_mat)
    recovered_hung = set()
    for r, c in zip(row_ind, col_ind):
        if sim_mat[r, c] >= threshold:
            recovered_hung.add(int(c))

    return recovered_m2o, recovered_hung, per_topic_best


def evaluate_benchmark_alignment(threshold: float = 0.10):
    print("=" * 85)
    print(f"THEMATIC VALIDATION AUDIT (Jaccard threshold tau = {threshold:.2f})")
    print("=" * 85)

    results_table = []
    evaluated_benchmarks = []
    pending_benchmarks = []

    for bid, short_name, slug in BENCHMARK_SLUGS:
        json_path = f"data/benchmarks/{slug}.json"
        csv_path = f"outputs/pipeline_results_{slug}/topic_info.csv"
        with open(json_path, "r", encoding="utf-8") as f:
            b_meta = json.load(f)

        clusters = b_meta.get("scientometrics", {}).get("clusters", [])
        if not clusters:
            pending_benchmarks.append(f"{bid} ({short_name})")
            continue

        topics = load_extracted_topics(csv_path)
        if not topics:
            print(f"[!] Warning: No extracted topics for {bid}")
            continue

        cluster_names = [c["cluster_name"] for c in clusters]
        cluster_sets = [tokenize_keywords(c["keywords"]) for c in clusters]
        topic_sets = [tokenize_keywords(t["words"][:10]) for t in topics]

        rec_m2o, rec_hung, per_topic = match_topics_to_clusters(topic_sets, cluster_sets, threshold=threshold)
        k_pub = len(clusters)
        k_disc = len(topics)
        chance_floor = 1.0 - (1.0 - 1.0 / k_pub) ** k_disc

        evaluated_benchmarks.append({
            "bid": bid,
            "name": short_name,
            "k_pub": k_pub,
            "k_disc": k_disc,
            "topic_sets": topic_sets,
            "cluster_sets": cluster_sets,
            "rec_m2o": len(rec_m2o),
            "rec_hung": len(rec_hung),
            "chance_floor": chance_floor,
        })

        for (t_idx, c_idx, sim) in per_topic:
            t = topics[t_idx]
            status = "\\checkmark" if sim >= threshold else "--"
            results_table.append({
                "bench_id": bid,
                "benchmark": short_name,
                "topic_id": t["topic_id"],
                "docs": t["count"],
                "topic_keywords": ", ".join(t["words"][:6]),
                "mapped_cluster_name": cluster_names[c_idx],
                "jaccard_sim": sim,
                "alignment": status,
            })

        print(
            f"-> {bid} {short_name}: K={k_disc}, K_pub={k_pub}, "
            f"M2O={len(rec_m2o)}/{k_pub}, Hungarian={len(rec_hung)}/{k_pub}, "
            f"ChanceFloor={chance_floor*100:.1f}%"
        )

    if pending_benchmarks:
        print("\n[!] Pending blind cluster extraction in data/benchmarks/*.json:")
        for p in pending_benchmarks:
            print(f"    - {p}")

    total_pub = sum(b["k_pub"] for b in evaluated_benchmarks)
    total_m2o = sum(b["rec_m2o"] for b in evaluated_benchmarks)
    total_hung = sum(b["rec_hung"] for b in evaluated_benchmarks)
    expected_chance = sum(b["chance_floor"] * b["k_pub"] for b in evaluated_benchmarks)

    # Sensitivity across thresholds
    for tau in (0.05, 0.10, 0.15):
        m2o_t = 0
        hung_t = 0
        for b in evaluated_benchmarks:
            r_m, r_h, _ = match_topics_to_clusters(b["topic_sets"], b["cluster_sets"], threshold=tau)
            m2o_t += len(r_m)
            hung_t += len(r_h)
        print(f"Sensitivity tau={tau:.2f}: M2O={m2o_t}/{total_pub} ({100*m2o_t/total_pub:.1f}%), Hungarian={hung_t}/{total_pub} ({100*hung_t/total_pub:.1f}%)")

    # Permutation baseline (1,000 shuffles of topic sets across evaluated benchmarks)
    all_topic_sets = [ts for b in evaluated_benchmarks for ts in b["topic_sets"]]
    rng = random.Random(42)
    perm_hung_scores = []
    for _ in range(1000):
        shuffled = list(all_topic_sets)
        rng.shuffle(shuffled)
        idx = 0
        hits = 0
        for b in evaluated_benchmarks:
            k_d = b["k_disc"]
            _, r_h, _ = match_topics_to_clusters(shuffled[idx:idx + k_d], b["cluster_sets"], threshold=threshold)
            hits += len(r_h)
            idx += k_d
        perm_hung_scores.append(hits / total_pub * 100.0)

    print(f"Analytical chance floor (unthresholded): {expected_chance:.1f}/{total_pub} ({100*expected_chance/total_pub:.1f}%)")
    print(f"Permutation baseline (Hungarian, tau={threshold:.2f}, 1000 shuffles): {np.mean(perm_hung_scores):.1f}% +/- {np.std(perm_hung_scores):.1f}%")

    # Emit LaTeX Table 6
    latex_path = "manuscripts/paper4_opensciencepipe_landmark/tables/tab_thematic_validation.tex"
    os.makedirs(os.path.dirname(latex_path), exist_ok=True)
    with open(latex_path, "w", encoding="utf-8") as f:
        f.write("% Auto-generated by scripts/evaluate_thematic_validation.py\n")
        f.write("\\begin{table*}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\scriptsize\n")
        f.write("\\renewcommand{\\arraystretch}{0.88}\n")
        f.write("\\caption{Thematic Validation: Alignment of Discovered Neural Topics with Verified Published Benchmark Clusters}\n")
        f.write("\\label{tab:thematic_validation}\n")
        f.write("\\resizebox{\\textwidth}{!}{%\n")
        f.write("\\begin{tabular}{ll c p{5.0cm} p{4.6cm} c c}\n")
        f.write("\\hline\n")
        f.write("\\textbf{ID} & \\textbf{Benchmark Study} & \\textbf{Topic} & \\textbf{Top Discovered c-TF-IDF Terms} & \\textbf{Mapped Published Benchmark Cluster} & \\textbf{Jaccard} & \\textbf{Match ($J \\ge 0.10$)} \\\\\n")
        f.write("\\hline\n")

        curr_b = None
        for r in results_table:
            topic_str = f"T{r['topic_id']} ($N={r['docs']}$)"
            kw_clean = r["topic_keywords"].replace("_", " ")
            c_name_clean = r["mapped_cluster_name"].replace("&", "\\&").replace("#", "\\#")
            j_str = f"{r['jaccard_sim']:.3f}"
            if curr_b != r["benchmark"]:
                curr_b = r["benchmark"]
                f.write(f"\\textbf{{{r['bench_id']}}} & \\textbf{{{r['benchmark']}}} & {topic_str} & \\texttt{{{kw_clean}}} & {c_name_clean} & {j_str} & {r['alignment']} \\\\\n")
            else:
                f.write(f" & & {topic_str} & \\texttt{{{kw_clean}}} & {c_name_clean} & {j_str} & {r['alignment']} \\\\\n")

        f.write("\\hline\n")
        f.write("\\end{tabular}%\n")
        f.write("}\n")
        f.write(
            f"\\vspace{{2pt}}\\par\\raggedright\\scriptsize\\textit{{Note:}} Evaluates the {len(evaluated_benchmarks)} benchmarks with verbatim published cluster definitions stored in \\texttt{{data/benchmarks/*.json}} "
            f"({total_pub} published clusters total). At Jaccard threshold $\\tau = {threshold:.2f}$, OpenSciencePipe recovers "
            f"{total_m2o}/{total_pub} ({100*total_m2o/total_pub:.1f}\\%) under argmax-per-topic assignment and "
            f"{total_hung}/{total_pub} ({100*total_hung/total_pub:.1f}\\%) under one-to-one Hungarian matching "
            f"(permutation baseline: {np.mean(perm_hung_scores):.1f}\\% $\\pm$ {np.std(perm_hung_scores):.1f}\\%).\n"
        )
        f.write("\\end{table*}\n")

    print(f"Emitted LaTeX validation table to: {latex_path}")
    return evaluated_benchmarks


if __name__ == "__main__":
    evaluate_benchmark_alignment()
