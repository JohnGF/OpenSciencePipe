#!/usr/bin/env python3
"""
Regenerates Table 5 (tab_validation_thematic_clustering.tex) from committed code,
frozen benchmark configurations (data/benchmarks/*.json), collected corpora
(data/collected_*.csv), and BERTopic outputs (outputs/pipeline_results_*/topic_info.csv).

Computes:
- N (total corpus records) and N_abs (clustered records in topic_info.csv)
- K (discovered non-outlier topics)
- Topic Diversity (TD, top-10 terms)
- Topic Coherence (C_NPMI across full corpus Title + Abstract texts, eps=1e-6)
- Outlier % (Topic -1)
- Pipeline Top-5 Nation Overlap vs. Naive Global Top-5 Baseline Overlap
"""

import os
import sys
import ast
import json
from collections import Counter
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.ingestion import extract_countries
from scripts.evaluate_clustering_benchmarks import (
    compute_topic_diversity,
    compute_cv_coherence_approx,
)

NAIVE_GLOBAL_TOP5 = {"United States", "China", "United Kingdom", "Germany", "Japan"}

COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "england": "United Kingdom",
    "great britain": "United Kingdom",
    "peoples r china": "China",
    "people's republic of china": "China",
    "republic of korea": "South Korea",
    "korea": "South Korea",
}

BENCHMARKS = [
    ("B01", "Antidiabetic Drugs Top 100", "Future Science OA", "benchmark_antidiabetic_drugs_top100"),
    ("B02", "Atmospheric CO$_2$ Review", "Environments", "benchmark_atmospheric_co2_bibliometrix"),
    ("B03", "Modified Biochar Heavy Metals", "Carbon Research", "benchmark_biochar_citespace"),
    ("B04", "Blockchain Technology in Business", "Sustainability", "benchmark_blockchain_vosviewer"),
    ("B05", "ChatGPT in Medical Research", "Medical Sciences", "benchmark_chatgpt_medicine"),
    ("B06", "Top Papers in Dentistry (ESI)", "Clin. Exp. Dental Res.", "benchmark_dentistry_esi_top"),
    ("B07", "Digital Transformation Trends", "SAGE Open", "benchmark_digital_transformation_kraus2021"),
    ("B08", "Distance Learning Longitudinal", "Int. J. Learn. Teach. Ed.", "benchmark_distance_learning_landscape"),
    ("B09", "Decadal Electrophysiology", "OpenAlex Graph", "benchmark_eeg_neuroscience"),
    ("B10", "Transforming Education", "Sustainability", "benchmark_genai_education_vosviewer"),
    ("B11", "Universities in Innovation", "J. Innov. \\& Knowledge", "benchmark_innovation_universities"),
    ("B12", "Microplastics in Soil", "Sustainability", "benchmark_microplastics_soil"),
    ("B13", "Mobile Commerce Mapping", "Eur. Res. Manag. Bus. Econ.", "benchmark_mobile_commerce_mapping"),
    ("B14", "Public Health Top 100", "Int. J. Env. Res. Pub. H.", "benchmark_public_health_top100"),
    ("B15", "Social Work and Migration", "SAGE Open", "benchmark_social_work_migration"),
    ("B16", "Solar Power Generation", "Env. Sci. Pollut. Res.", "benchmark_solar_power_generation"),
    ("B17", "Sustainable Business Dynamics", "Econ. Res.-Ekon. Istraz.", "benchmark_sustainable_business_performance"),
    ("B18", "CitNetExplorer Lineages", "Journal of Informetrics", "benchmark_citnetexplorer_genealogy"),
    ("B19", "Forty-Five Years of JBR", "Journal of Business Research", "benchmark_gephi_modularity"),
    ("B20", "Drones in Agriculture Matrix", "Comp. Electron. Agric.", "benchmark_bibexcel_agriculture"),
]


def norm_country(c: str) -> str:
    cl = c.strip().lower()
    return COUNTRY_ALIASES.get(cl, c.strip())


def parse_topic_words(df_topics: pd.DataFrame) -> list:
    topic_words = []
    for _, row in df_topics[df_topics["Topic"] != -1].iterrows():
        rep = row.get("Representation", "[]")
        words = []
        if isinstance(rep, str):
            try:
                words = ast.literal_eval(rep)
            except Exception:
                words = [w.strip(" '\"[]") for w in rep.split(",")]
        elif isinstance(rep, list):
            words = rep
        if words:
            topic_words.append([str(w) for w in words])
    return topic_words


def main():
    rows = []
    for bid, label, journal, slug in BENCHMARKS:
        json_path = f"data/benchmarks/{slug}.json"
        csv_path = f"data/collected_{slug}.csv"
        topic_path = f"outputs/pipeline_results_{slug}/topic_info.csv"

        # Special handling for B09 macro-scalability corpus if bertopic_clean is present
        if bid == "B09" and os.path.exists("outputs/bertopic_clean/topic_info.csv"):
            topic_path = "outputs/bertopic_clean/topic_info.csv"
            if os.path.exists("data/collected_EEG_expanded_33k_2014_2026.csv"):
                csv_path = "data/collected_EEG_expanded_33k_2014_2026.csv"

        with open(json_path, "r", encoding="utf-8") as f:
            b_meta = json.load(f)

        df_corpus = pd.read_csv(csv_path)
        df_topics = pd.read_csv(topic_path)

        total_n = int(df_topics["Count"].sum()) if bid == "B09" else int(len(df_corpus))
        clustered_n = int(df_topics["Count"].sum())
        out_row = df_topics[df_topics["Topic"] == -1]
        out_count = int(out_row["Count"].values[0]) if not out_row.empty else 0
        out_pct = (out_count / clustered_n * 100.0) if clustered_n > 0 else 0.0

        valid_topics = df_topics[df_topics["Topic"] != -1]
        k_val = int(len(valid_topics))
        topic_words = parse_topic_words(df_topics)
        td_val = compute_topic_diversity(topic_words, top_k=10)

        # Build corpus texts (Title + Abstract) for NPMI
        titles = df_corpus["Title"].fillna("").astype(str) if "Title" in df_corpus.columns else pd.Series([""] * len(df_corpus))
        abstracts = df_corpus["Abstract"].fillna("").astype(str) if "Abstract" in df_corpus.columns else pd.Series([""] * len(df_corpus))
        corpus_texts = [
            f"{t}. {a}".strip()
            for t, a in zip(titles, abstracts)
            if a.strip() or t.strip()
        ]
        npmi_val = compute_cv_coherence_approx(topic_words, corpus_texts, top_k=10, epsilon=1e-6)

        # Country concordance vs. Naive Global Top-5
        gt_countries_raw = b_meta.get("scientometrics", {}).get("top_countries", [])
        pipe_str = "--"
        naive_str = "--"
        pipe_pct = None
        naive_pct = None
        if gt_countries_raw and bid != "B09":
            gt_top5 = [
                norm_country(c["country"] if isinstance(c, dict) else c)
                for c in gt_countries_raw[:5]
            ]
            c_counts = Counter()
            if "Affiliations" in df_corpus.columns:
                for aff in df_corpus["Affiliations"].dropna():
                    for country in extract_countries(str(aff)):
                        c_counts[norm_country(country)] += 1
            pipe_top5 = [c for c, _ in sorted(c_counts.items(), key=lambda x: (-x[1], x[0]))[:5]]
            p_hits = len(set(pipe_top5) & set(gt_top5))
            n_hits = len(NAIVE_GLOBAL_TOP5 & set(gt_top5))
            pipe_pct = (p_hits / len(gt_top5)) * 100.0
            naive_pct = (n_hits / len(gt_top5)) * 100.0
            pipe_str = f"{pipe_pct:.1f}\\% (${p_hits}/{len(gt_top5)}$)"
            naive_str = f"{naive_pct:.1f}\\% (${n_hits}/{len(gt_top5)}$)"

        rows.append({
            "id": bid,
            "label": label,
            "journal": journal,
            "total_n": total_n,
            "clustered_n": clustered_n,
            "k": k_val,
            "td": td_val,
            "npmi": npmi_val,
            "out_pct": out_pct,
            "pipe_str": pipe_str,
            "naive_str": naive_str,
            "pipe_pct": pipe_pct,
            "naive_pct": naive_pct,
        })
        print(f"{bid}: N={total_n} (clustered={clustered_n}), K={k_val}, TD={td_val:.4f}, NPMI={npmi_val:.4f}, Out={out_pct:.1f}%, Pipe={pipe_pct}, Naive={naive_pct}")

    tds = [r["td"] for r in rows]
    npmis = [r["npmi"] for r in rows]
    outs = [r["out_pct"] for r in rows]
    pipes = [r["pipe_pct"] for r in rows if r["pipe_pct"] is not None]
    naives = [r["naive_pct"] for r in rows if r["naive_pct"] is not None]

    print("-" * 80)
    print(f"TD: mean={np.mean(tds):.4f}, median={np.median(tds):.4f}, range={min(tds):.4f}-{max(tds):.4f}")
    print(f"NPMI: mean={np.mean(npmis):.4f}, median={np.median(npmis):.4f}")
    print(f"Outliers: mean={np.mean(outs):.1f}%, median={np.median(outs):.1f}%, range={min(outs):.1f}%-{max(outs):.1f}%")
    print(f"Country Pipeline (n={len(pipes)}): mean={np.mean(pipes):.1f}%, median={np.median(pipes):.1f}%")
    print(f"Country Naive (n={len(naives)}): mean={np.mean(naives):.1f}%, median={np.median(naives):.1f}%")

    # Emit LaTeX Table 5
    out_tex = "manuscripts/paper4_opensciencepipe_landmark/tables/tab_validation_thematic_clustering.tex"
    lines = [
        "% Auto-generated by scripts/regenerate_table5.py",
        "\\begin{table*}[t]",
        "\\centering",
        "\\small",
        "\\caption{BERTopic \\& cuGraph Structural Clustering Quality Across Evaluated Scientometric Benchmark Corpora}",
        "\\label{tab:validation_thematic_clustering}",
        "\\resizebox{\\textwidth}{!}{%",
        "\\begin{tabular}{llp{2.6cm}ccccccc}",
        "\\hline",
        "\\textbf{ID} & \\textbf{Benchmark Investigation} & \\textbf{Journal / Source} & \\textbf{Docs ($N$ / $N_{\\text{abs}}$)} & \\textbf{Themes ($K$)} & \\textbf{Diversity ($\\text{TD}$)} & \\textbf{Coherence ($C_{\\text{NPMI}}$)} & \\textbf{Outlier \\% (Topic -1)} & \\textbf{Top-$K$ Nation Overlap} & \\textbf{Naive Top-5 Overlap} \\\\",
        "\\hline",
    ]
    for r in rows:
        n_str = f"{r['total_n']:,}" if r["total_n"] == r["clustered_n"] else f"{r['total_n']:,} ({r['clustered_n']:,})"
        n_str = n_str.replace(",", "{,}")
        lines.append(
            f"{r['id']} & {r['label']} & {r['journal']} & {n_str} & {r['k']} & {r['td']:.4f} & {r['npmi']:.4f} & {r['out_pct']:.1f}\\% & {r['pipe_str']} & {r['naive_str']} \\\\"
        )
    lines.extend([
        "\\hline",
        "\\end{tabular}%",
        "}",
        (
            f"\\vspace{{2pt}}\\par\\raggedright\\scriptsize\\textit{{Note:}} Across the 20 benchmark corpora, "
            f"mean topic diversity is $\\overline{{\\text{{TD}}}} = {np.mean(tds):.2f}$ (median {np.median(tds):.2f}, range {min(tds):.4f}--{max(tds):.4f}), "
            f"mean topic coherence is $\\overline{{C}}_{{\\text{{NPMI}}}} = {np.mean(npmis):.2f}$ (median {np.median(npmis):.2f}), "
            f"and mean density outlier isolation rate is {np.mean(outs):.1f}\\% (median {np.median(outs):.1f}\\%, range {min(outs):.1f}\\%--{max(outs):.1f}\\%). "
            f"$N$ reports total harvested records; $N_{{\\text{{abs}}}}$ (in parentheses when smaller) reports the subset with non-empty abstracts entering BERTopic. "
            f"Top-$K$ nation overlap covers the {len(pipes)} domain benchmarks publishing national rankings ($K=5$; "
            f"pipeline: range {min(pipes):.1f}\\%--{max(pipes):.1f}\\%, mean {np.mean(pipes):.1f}\\%, median {np.median(pipes):.1f}\\% vs.\\ "
            f"naive OpenAlex global top-5 baseline [USA, China, UK, Germany, Japan]: mean {np.mean(naives):.1f}\\%, median {np.median(naives):.1f}\\%)."
        ),
        "\\end{table*}",
    ])
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_tex}")


if __name__ == "__main__":
    main()
