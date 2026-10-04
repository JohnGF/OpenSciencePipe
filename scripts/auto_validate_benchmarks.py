import os
import sys
import glob
import json
import argparse
import pandas as pd
import numpy as np
from typing import Dict, Any, List

from scripts.validate_against_benchmark import evaluate_screening, evaluate_scientometrics, evaluate_meta_analysis
from scripts.evaluate_clustering_benchmarks import evaluate_thematic_clustering

def run_automated_validation():
    benchmarks_dir = "data/benchmarks"
    benchmark_files = sorted(glob.glob(os.path.join(benchmarks_dir, "*.json")))
    benchmark_files = [f for f in benchmark_files if not f.endswith("benchmark_template.json")]

    print("=" * 95)
    print(f">>> AUTOMATED DUAL-TRACK BENCHMARK VALIDATION ({len(benchmark_files)} Benchmarks Registered)")
    print("=" * 95)

    results_map = {
        "bci_stroke_ren2024_benchmark.json": "pipeline_results_bci_slr",
        "benchmark_blockchain_vosviewer.json": "pipeline_results_blockchain_benchmark",
        "benchmark_microplastics_soil.json": "pipeline_results_microplastics",
        "benchmark_parkinsons_eeg.json": "pipeline_results_parkinsons_eeg",
        "benchmark_rent_control_econometrics.json": "pipeline_results_rent_control_meta",
        "benchmark_chatgpt_medicine.json": "pipeline_results_chatgpt_med",
        "benchmark_eeg_neuroscience.json": "pipeline_results_37k",
        "benchmark_digital_transformation_kraus2021.json": "pipeline_results_dt",
        "benchmark_solar_power_generation.json": "pipeline_results_solar_power",
        "benchmark_sustainable_business_performance.json": "pipeline_results_sustainable_business",
    }

    screening_records = []
    clustering_records = []

    for b_path in benchmark_files:
        b_name = os.path.basename(b_path)
        b_stem = os.path.splitext(b_name)[0]
        with open(b_path, "r", encoding="utf-8") as f:
            b_data = json.load(f)

        title = b_data.get("benchmark_title", b_name)
        doi = b_data.get("reference_doi", "N/A")
        year = b_data.get("year", "N/A")
        journal = b_data.get("journal", "N/A")

        assigned_dir = results_map.get(b_name, None)
        if assigned_dir:
            if not os.path.exists(assigned_dir) and os.path.exists(os.path.join("outputs", assigned_dir)):
                assigned_dir = os.path.join("outputs", assigned_dir)

        if not assigned_dir or not os.path.exists(assigned_dir):
            candidate_dir = f"pipeline_results_{b_stem}"
            if os.path.exists(candidate_dir):
                assigned_dir = candidate_dir
            elif os.path.exists(os.path.join("outputs", candidate_dir)):
                assigned_dir = os.path.join("outputs", candidate_dir)

        is_meta = "meta_analysis" in b_data or "meta" in b_stem or (b_data.get("screening", {}).get("ground_truth_included_dois"))

        if is_meta:
            # Track 1: PRISMA Screening Record
            cohort = b_data.get("tool_cohort", "Manual (PRISMA)")
            s_rec = {
                "Benchmark": title[:34] + "..." if len(title) > 34 else title,
                "Reference": f"{doi} ({year})",
                "Field / Journal": journal[:18] + "..." if len(journal) > 18 else journal,
                "Methodology": cohort,
                "Included_GT": "N/A",
                "Recall": "N/A",
                "Precision": "N/A",
                "Specificity": "N/A",
                "F1": "N/A",
                "WMCC": "N/A"
            }
            if assigned_dir and os.path.exists(assigned_dir):
                s_res = evaluate_screening(assigned_dir, b_data)
                if s_res and "error" not in s_res:
                    s_rec["Included_GT"] = str(s_res.get("ground_truth_total_included", "N/A"))
                    s_rec["Recall"] = f"{s_res['recall_sensitivity_pct']:.1f}%"
                    if s_res.get("precision_pct") is not None:
                        s_rec["Precision"] = f"{s_res['precision_pct']:.1f}%"
                    if s_res.get("specificity_pct") is not None:
                        s_rec["Specificity"] = f"{s_res['specificity_pct']:.1f}%"
                    s_rec["F1"] = f"{s_res['f1_score_pct']:.1f}%"
                    if s_res.get("wmcc") is not None:
                        s_rec["WMCC"] = f"{s_res['wmcc']:.4f}"
            screening_records.append(s_rec)

        # Track 2: Bibliometric / Thematic Clustering Record
        c_rec = {
            "Benchmark": title[:36] + "..." if len(title) > 36 else title,
            "Reference": f"{doi} ({year})",
            "Field / Journal": journal[:20] + "..." if len(journal) > 20 else journal,
            "Topics": "N/A",
            "Diversity_RBO": "N/A",
            "Coherence_NPMI": "N/A",
            "Outlier_Pct": "N/A",
            "Geo_Overlap": "N/A",
            "Inst_Overlap": "N/A"
        }
        if assigned_dir and os.path.exists(assigned_dir):
            c_res = evaluate_thematic_clustering(assigned_dir, b_data)
            if c_res and "error" not in c_res:
                c_rec["Topics"] = str(c_res.get("num_valid_topics", "N/A"))
                c_rec["Diversity_RBO"] = f"{c_res.get('topic_diversity_rbo', 0.0):.4f}"
                c_rec["Coherence_NPMI"] = f"{c_res.get('topic_coherence_npmi', 0.0):.4f}"
                c_rec["Outlier_Pct"] = f"{c_res.get('outlier_isolation_pct', 0.0):.1f}%"

            sc_res = evaluate_scientometrics(assigned_dir, b_data)
            if sc_res and "country_overlap_pct" in sc_res:
                overlap_str = f"{sc_res['country_overlap_pct']:.1f}%"
                if sc_res.get("country_spearman_rho") is not None:
                    p = sc_res.get("country_spearman_p", 1.0)
                    rho_val = sc_res['country_spearman_rho']
                    if p < 0.001:
                        p_txt = "p<0.001"
                    elif p < 0.01:
                        p_txt = "p<0.01"
                    elif p < 0.05:
                        p_txt = "p<0.05"
                    else:
                        p_txt = f"p={p:.2f}"
                    overlap_str += f" ($\\rho={rho_val:.2f}, {p_txt}$)"
                c_rec["Geo_Overlap"] = overlap_str

            if sc_res and "institution_overlap_pct" in sc_res:
                inst_str = f"{sc_res['institution_overlap_pct']:.1f}%"
                if sc_res.get("institution_spearman_rho") is not None:
                    p = sc_res.get("institution_spearman_p", 1.0)
                    rho_val = sc_res['institution_spearman_rho']
                    if p < 0.001:
                        p_txt = "p<0.001"
                    elif p < 0.01:
                        p_txt = "p<0.01"
                    elif p < 0.05:
                        p_txt = "p<0.05"
                    else:
                        p_txt = f"p={p:.2f}"
                    inst_str += f" ($\\rho={rho_val:.2f}, {p_txt}$)"
                c_rec["Inst_Overlap"] = inst_str

        clustering_records.append(c_rec)

    # 1. Print and Export Track 1: Screening Matrix (Section 3.1)
    os.makedirs("tables", exist_ok=True)
    df_s = pd.DataFrame(screening_records)
    print("\n" + "=" * 95)
    print(">>> SECTION 3.1: PRISMA SYSTEMATIC SCREENING BENCHMARK MATRIX")
    print("=" * 95)
    print(df_s.to_string(index=False))

    tex_s_path = "tables/tab_validation_screening_prisma.tex"
    tex_s = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\caption{Section 3.1: LLM Zero-Shot Screening Accuracy Across PRISMA Systematic Review Ground Truths}",
        r"\label{tab:validation_screening_prisma}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{p{4.2cm}p{3.2cm}p{2.2cm}p{2.4cm}cccccc}",
        r"\hline",
        r"\textbf{Benchmark Study} & \textbf{Reference DOI} & \textbf{Field / Journal} & \textbf{Screening Tool} & \textbf{Target $N$} & \textbf{Recall} & \textbf{Prec.} & \textbf{Spec.} & \textbf{$F_1$} & \textbf{WMCC} \\",
        r"\hline",
    ]
    for r in screening_records:
        b_t = r["Benchmark"].replace("&", r"\&").replace("_", r"\_")
        b_r = r["Reference"].replace("_", r"\_")
        b_j = r["Field / Journal"].replace("&", r"\&")
        m_c = r.get("Methodology", "Manual").replace("&", r"\&")
        rec_s = r['Recall'].replace("%", r"\%")
        prec_s = r.get('Precision', 'N/A').replace("%", r"\%")
        spec_s = r['Specificity'].replace("%", r"\%")
        f1_s = r['F1'].replace("%", r"\%")
        tex_s.append(f"{b_t} & {{\\footnotesize\\nolinkurl{{{b_r}}}}} & {b_j} & {m_c} & {r['Included_GT']} & {rec_s} & {prec_s} & {spec_s} & {f1_s} & {r['WMCC']} \\\\")
    tex_s.extend([
        r"\hline",
        r"\end{tabular}%",
        r"}",
        r"\end{table*}"
    ])
    with open(tex_s_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex_s) + "\n")
    print(f">>> [SAVED] {tex_s_path}")

    # 2. Print and Export Track 2: Thematic Clustering Matrix (Section 3.2)
    df_c = pd.DataFrame(clustering_records)
    print("\n" + "=" * 95)
    print(">>> SECTION 3.2: NEURAL THEMATIC CLUSTERING BENCHMARK MATRIX")
    print("=" * 95)
    print(df_c.to_string(index=False))

    tex_c_path = "tables/tab_validation_thematic_clustering.tex"
    ms_tex_c_path = "manuscripts/paper4_opensciencepipe_landmark/tables/tab_validation_thematic_clustering.tex"
    tex_c = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\caption{Section 3.2: BERTopic \& cuGraph Structural Clustering Quality Across Bibliometric Corpora}",
        r"\label{tab:validation_thematic_clustering}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{p{3.8cm}p{2.8cm}p{2.2cm}cccccc}",
        r"\hline",
        r"\textbf{Benchmark Study} & \textbf{Reference DOI} & \textbf{Field / Journal} & \textbf{Themes ($K$)} & \textbf{Diversity (RBO)} & \textbf{Coherence ($C_{\text{NPMI}}$)} & \textbf{Outlier \% (Topic -1)} & \textbf{Geo Overlap} & \textbf{Inst. Overlap} \\",
        r"\hline",
    ]
    for r in clustering_records:
        b_t = r["Benchmark"].replace("&", r"\&").replace("_", r"\_")
        b_r = r["Reference"].replace("_", r"\_")
        b_j = r["Field / Journal"].replace("&", r"\&")
        outlier_str = r['Outlier_Pct'].replace("%", r"\%")
        geo_str = r['Geo_Overlap'].replace("%", r"\%")
        inst_str = r['Inst_Overlap'].replace("%", r"\%")
        tex_c.append(f"{b_t} & {{\\footnotesize\\nolinkurl{{{b_r}}}}} & {b_j} & {r['Topics']} & {r['Diversity_RBO']} & {r['Coherence_NPMI']} & {outlier_str} & {geo_str} & {inst_str} \\\\")
    tex_c.extend([
        r"\hline",
        r"\end{tabular}%",
        r"}",
        r"\end{table*}"
    ])
    with open(tex_c_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex_c) + "\n")
    print(f">>> [SAVED] {tex_c_path}")
    if os.path.exists("manuscripts/paper4_opensciencepipe_landmark/tables"):
        with open(ms_tex_c_path, "w", encoding="utf-8") as f:
            f.write("\n".join(tex_c) + "\n")
        print(f">>> [SAVED] {ms_tex_c_path}")

    meta_records = []
    for b_path in benchmark_files:
        b_name = os.path.basename(b_path)
        b_stem = os.path.splitext(b_name)[0]
        with open(b_path, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        if "meta_analysis" in b_data:
            m_dir = results_map.get(b_name, None) or f"pipeline_results_{b_stem}"
            if not os.path.exists(os.path.join(m_dir, "meta_analysis_results.json")):
                candidate_meta = m_dir.replace("_slr", "_meta")
                if os.path.exists(os.path.join(candidate_meta, "meta_analysis_results.json")):
                    m_dir = candidate_meta
            title = b_data.get("benchmark_title", b_name)
            doi = b_data.get("reference_doi", "N/A")
            m_res = evaluate_meta_analysis(m_dir, b_data) if os.path.exists(m_dir) else {}
            m_rec = {
                "Benchmark": title[:36] + "..." if len(title) > 36 else title,
                "Reference": doi,
                "GT_d": f"{b_data['meta_analysis'].get('pooled_effect_d', 'N/A')}",
                "Pipeline_d": f"{m_res.get('pipeline_pooled_d', 'N/A'):.3f}" if isinstance(m_res.get('pipeline_pooled_d'), (int, float)) else "N/A",
                "Abs_Error_d": f"{m_res.get('effect_size_abs_error', 'N/A'):.3f}" if isinstance(m_res.get('effect_size_abs_error'), (int, float)) else "N/A",
                "GT_I2": f"{b_data['meta_analysis'].get('i_squared_pct', 'N/A')}%",
                "Pipeline_I2": f"{m_res.get('pipeline_i_squared', 'N/A'):.1f}%" if isinstance(m_res.get('pipeline_i_squared'), (int, float)) else "N/A",
            }
            meta_records.append(m_rec)

    if meta_records:
        df_m = pd.DataFrame(meta_records)
        print("\n" + "=" * 95)
        print(">>> SECTION 3.3: QUANTITATIVE META-ANALYSIS SYNTHESIS MATRIX (RevMan / Metafor)")
        print("=" * 95)
        print(df_m.to_string(index=False))

        tex_m_path = "tables/tab_validation_meta_analysis.tex"
        tex_m = [
            r"\begin{table*}[t]",
            r"\centering",
            r"\small",
            r"\caption{Section 3.3: Quantitative Meta-Analysis Pooled Effect Sizes and Heterogeneity Concordance}",
            r"\label{tab:validation_meta_analysis}",
            r"\resizebox{\textwidth}{!}{%",
            r"\begin{tabular}{p{5.5cm}p{4.0cm}ccccc}",
            r"\hline",
            r"\textbf{Benchmark Study} & \textbf{Reference DOI} & \textbf{GT $d$} & \textbf{Tool $d$} & \textbf{Error $|d|$} & \textbf{GT $I^2$} & \textbf{Tool $I^2$} \\",
            r"\hline",
        ]
        for r in meta_records:
            b_t = r["Benchmark"].replace("&", r"\&").replace("_", r"\_")
            b_r = r["Reference"].replace("_", r"\_")
            gt_i2 = r['GT_I2'].replace("%", r"\%")
            pipe_i2 = r['Pipeline_I2'].replace("%", r"\%")
            tex_m.append(f"{b_t} & {{\\footnotesize\\nolinkurl{{{b_r}}}}} & {r['GT_d']} & {r['Pipeline_d']} & {r['Abs_Error_d']} & {gt_i2} & {pipe_i2} \\\\")
        tex_m.extend([
            r"\hline",
            r"\end{tabular}%",
            r"}",
            r"\end{table*}"
        ])
        with open(tex_m_path, "w", encoding="utf-8") as f:
            f.write("\n".join(tex_m) + "\n")
        print(f">>> [SAVED] {tex_m_path}")

    # Sync tables to paper4 manuscript
    paper4_tables = "manuscripts/paper4_opensciencepipe_landmark/tables"
    if os.path.exists(paper4_tables):
        import shutil
        for f in glob.glob("tables/*.tex"):
            shutil.copy(f, paper4_tables)
        print(f">>> [SYNCED] Copied updated tables to {paper4_tables}")

    print("\n" + "=" * 95)
    print(">>> DUAL-TRACK BENCHMARK VALIDATION COMPLETE")
    print("=" * 95)

if __name__ == "__main__":
    run_automated_validation()
