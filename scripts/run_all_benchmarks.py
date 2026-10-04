import os
import sys
import glob
import json
import pandas as pd
from typing import Dict, Any, List

def run_suite():
    benchmarks_dir = "data/benchmarks"
    benchmark_files = sorted(glob.glob(os.path.join(benchmarks_dir, "*.json")))
    
    # Exclude template
    benchmark_files = [f for f in benchmark_files if not f.endswith("benchmark_template.json")]
    
    print("=" * 85)
    print(f">>> AUTOMATED MULTI-FIELD BENCHMARK SUITE: {len(benchmark_files)} Benchmarks Registered")
    print("=" * 85)
    
    # Mapping of benchmark files to existing run result directories if available
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
    
    summary_rows = []
    
    for b_path in benchmark_files:
        b_name = os.path.basename(b_path)
        b_stem = os.path.splitext(b_name)[0]
        with open(b_path, "r", encoding="utf-8") as f:
            b_data = json.load(f)
            
        title = b_data.get("benchmark_title", b_name)
        doi = b_data.get("reference_doi", "N/A")
        year = b_data.get("year", "N/A")
        journal = b_data.get("journal", "N/A")
        
        has_slr = bool(b_data.get("screening", {}).get("ground_truth_included_dois"))
        has_meta = bool(b_data.get("meta_analysis"))
        has_scientometrics = bool(b_data.get("scientometrics"))
        
        assigned_dir = results_map.get(b_name, None)
        if assigned_dir and not os.path.exists(assigned_dir) and os.path.exists(os.path.join("outputs", assigned_dir)):
            assigned_dir = os.path.join("outputs", assigned_dir)

        if not assigned_dir or not os.path.exists(assigned_dir):
            candidate_dir = f"pipeline_results_{b_stem}"
            if os.path.exists(candidate_dir):
                assigned_dir = candidate_dir
            elif os.path.exists(os.path.join("outputs", candidate_dir)):
                assigned_dir = os.path.join("outputs", candidate_dir)
        
        status = "Registered & Configured"
        sensitivity = "N/A"
        specificity = "N/A"
        f1_score = "N/A"
        country_overlap = "N/A"
        
        if assigned_dir and os.path.exists(assigned_dir):
            status = f"Validated ({assigned_dir})"
            # Evaluate if screening
            if has_slr:
                try:
                    from scripts.validate_against_benchmark import evaluate_screening
                    s_res = evaluate_screening(assigned_dir, b_data)
                    if s_res and "error" not in s_res:
                        sensitivity = f"{s_res.get('recall_sensitivity_pct', 0.0):.1f}%"
                        f1_score = f"{s_res.get('f1_score_pct', 0.0):.1f}%"
                        if s_res.get('specificity_pct') is not None:
                            specificity = f"{s_res.get('specificity_pct'):.1f}%"
                except Exception:
                    pass
            if has_scientometrics:
                try:
                    from scripts.validate_against_benchmark import evaluate_scientometrics
                    sc_res = evaluate_scientometrics(assigned_dir, b_data)
                    if sc_res and "country_overlap_pct" in sc_res:
                        country_overlap = f"{sc_res['country_overlap_pct']:.1f}%"
                except Exception:
                    pass
                
        summary_rows.append({
            "Benchmark": title[:45] + "..." if len(title) > 45 else title,
            "Reference": f"{doi} ({year})",
            "Journal": journal[:25] + "..." if len(journal) > 25 else journal,
            "SLR Target": "Yes" if has_slr else "No",
            "Meta-Analysis": "Yes" if has_meta else "No",
            "Scientometrics": "Yes" if has_scientometrics else "No",
            "Sensitivity": sensitivity,
            "F1-Score": f1_score,
            "Country Overlap": country_overlap,
            "Status": status
        })
        
    df = pd.DataFrame(summary_rows)
    print(df.to_string(index=False))
    
    # Export LaTeX Table
    tables_dir = "tables"
    os.makedirs(tables_dir, exist_ok=True)
    tex_path = os.path.join(tables_dir, "tab_publication_benchmark_validation_matrix.tex")
    
    latex_table = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\caption{Consolidated Multi-Field Benchmark Validation Matrix Across Diverse Scientific Domains}",
        r"\label{tab:benchmark_validation_matrix}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{p{4.5cm}p{3.2cm}p{3.2cm}cccp{3.0cm}}",
        r"\hline",
        r"\textbf{Benchmark Study} & \textbf{Reference DOI} & \textbf{Journal / Field} & \textbf{SLR} & \textbf{Meta} & \textbf{Scientom.} & \textbf{Validation Metric} \\",
        r"\hline",
    ]

    for row in summary_rows:
        b_title = row["Benchmark"].replace("&", r"\&").replace("_", r"\_")
        b_ref = row["Reference"].replace("_", r"\_")
        b_jour = row["Journal"].replace("&", r"\&")
        slr_s = row["SLR Target"]
        meta_s = row["Meta-Analysis"]
        sci_s = row["Scientometrics"]

        if row["Sensitivity"] != "N/A":
            metric_str = f"Sens: {row['Sensitivity']}, F1: {row['F1-Score']}"
        elif row["Country Overlap"] != "N/A":
            metric_str = f"Country Overlap: {row['Country Overlap']}"
        else:
            metric_str = "Ground-Truth Indexed"

        metric_str = metric_str.replace("%", r"\%")
        latex_table.append(f"{b_title} & {{\\footnotesize\\nolinkurl{{{b_ref}}}}} & {b_jour} & {slr_s} & {meta_s} & {sci_s} & {metric_str} \\\\")

    latex_table.extend([
        r"\hline",
        r"\end{tabular}%",
        r"}",
        r"\end{table*}"
    ])
    
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(latex_table) + "\n")
    print(f">>> [SUCCESS] Consolidated benchmark table written -> {tex_path}")
    
    paper4_tables = "manuscripts/paper4_opensciencepipe_landmark/tables"
    if os.path.exists(paper4_tables):
        import shutil
        shutil.copy(tex_path, os.path.join(paper4_tables, os.path.basename(tex_path)))
        print(f">>> [SYNCED] Copied {tex_path} to {paper4_tables}")

if __name__ == "__main__":
    run_suite()
