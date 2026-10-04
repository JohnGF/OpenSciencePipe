import os
import sys
import json
import argparse
import re
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import scipy.stats as stats

def _normalize_doi(doi_str: Any) -> str:
    if not doi_str or pd.isna(doi_str):
        return ""
    s = str(doi_str).lower().strip()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    return s.strip()

def evaluate_screening(results_dir: str, benchmark_data: dict) -> Dict[str, Any]:
    screening_cfg = benchmark_data.get("screening", {})
    gt_included = [_normalize_doi(d) for d in screening_cfg.get("ground_truth_included_dois", []) if d]
    gt_excluded = [_normalize_doi(d) for d in screening_cfg.get("ground_truth_excluded_dois", []) if d]

    if not gt_included:
        return {}

    audit_csv = os.path.join(results_dir, "data", "screening_audit.csv")
    included_csv = os.path.join(results_dir, "data", "screened_included_studies.csv")
    
    if not os.path.exists(audit_csv) and not os.path.exists(included_csv):
        return {"error": f"No screening output files found in {results_dir}/data/"}

    pipeline_included_dois = set()
    pipeline_excluded_dois = set()

    if os.path.exists(audit_csv):
        audit_df = pd.read_csv(audit_csv)
        doi_col = next((c for c in ["DOI", "doi", "id"] if c in audit_df.columns), None)
        if doi_col:
            for _, row in audit_df.iterrows():
                ndoi = _normalize_doi(row[doi_col])
                if ndoi:
                    if row.get("Screening_Status") == "Included":
                        pipeline_included_dois.add(ndoi)
                    else:
                        pipeline_excluded_dois.add(ndoi)
    elif os.path.exists(included_csv):
        inc_df = pd.read_csv(included_csv)
        doi_col = next((c for c in ["DOI", "doi", "id"] if c in inc_df.columns), None)
        if doi_col:
            pipeline_included_dois = set(_normalize_doi(d) for d in inc_df[doi_col].dropna())

    tp = sum(1 for d in gt_included if d in pipeline_included_dois)
    fn = len(gt_included) - tp
    
    if gt_excluded:
        tn = sum(1 for d in gt_excluded if d in pipeline_excluded_dois)
        fp = len(gt_excluded) - tn
    else:
        fp = len([d for d in pipeline_included_dois if d not in set(gt_included)])
        tn = 0

    recall = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
    precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    specificity = (tn / (tn + fp)) * 100.0 if (tn + fp) > 0 and gt_excluded else None

    # Work Saved over Sampling at 95% target recall (WSS@95)
    # WSS@95 = ((TN + FN) / N) - (1 - Recall_target)
    # where Recall_target is typically 0.95. If recall < 0.95, WSS penalizes proportionally.
    total_eval = tp + fn + fp + tn
    if total_eval > 0 and (tn + fp) > 0:
        recall_val = recall / 100.0
        wss_95 = ((tn + fn) / total_eval) - (1.0 - 0.95)
        # Standard formulation: WSS@R = (TN + FN)/N - (1 - R)
        wss_95_pct = wss_95 * 100.0
    else:
        wss_95_pct = None

    # Weighted Matthews Correlation Coefficient (WMCC) for extreme class imbalance
    # MCC = (TP*TN - FP*FN) / sqrt((TP+FP)*(TP+FN)*(TN+FP)*(TN+FN))
    # Weighted MCC adjusts for class prevalence w_pos and w_neg
    if gt_excluded and (tp + fp) > 0 and (tp + fn) > 0 and (tn + fp) > 0 and (tn + fn) > 0:
        numerator = float(tp * tn - fp * fn)
        denominator = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
        mcc = numerator / denominator if denominator > 0 else 0.0
        # WMCC weighting based on class ratio: w_p = total / (2 * P), w_n = total / (2 * N)
        pos = tp + fn
        neg = tn + fp
        w_p = total_eval / (2.0 * pos) if pos > 0 else 1.0
        w_n = total_eval / (2.0 * neg) if neg > 0 else 1.0
        w_tp = w_p * tp
        w_tn = w_n * tn
        w_fp = w_n * fp
        w_fn = w_p * fn
        w_num = float(w_tp * w_tn - w_fp * w_fn)
        w_den = np.sqrt(float((w_tp + w_fp) * (w_tp + w_fn) * (w_tn + w_fp) * (w_tn + w_fn)))
        wmcc = w_num / w_den if w_den > 0 else mcc
    else:
        mcc = None
        wmcc = None

    return {
        "ground_truth_total_included": len(gt_included),
        "ground_truth_total_excluded": len(gt_excluded),
        "true_positives": tp,
        "false_negatives": fn,
        "false_positives": fp,
        "true_positives_retained_dois": [d for d in gt_included if d in pipeline_included_dois],
        "false_negatives_missed_dois": [d for d in gt_included if d not in pipeline_included_dois],
        "recall_sensitivity_pct": recall,
        "precision_pct": precision,
        "f1_score_pct": f1,
        "specificity_pct": specificity,
        "wss_95_pct": wss_95_pct,
        "mcc": round(mcc, 4) if mcc is not None else None,
        "wmcc": round(wmcc, 4) if wmcc is not None else None
    }

def evaluate_scientometrics(results_dir: str, benchmark_data: dict) -> Dict[str, Any]:
    sc_cfg = benchmark_data.get("scientometrics", {})
    gt_authors = sc_cfg.get("top_authors", [])
    gt_countries = sc_cfg.get("top_countries", [])

    metrics = {}

    # 1. Author ranking correlation
    if gt_authors:
        author_candidates = [
            os.path.join(results_dir, "data", "top_authors.csv"),
            os.path.join(results_dir, "data", "network_nodes.csv"),
            os.path.join(results_dir, "network_nodes.csv"),
            os.path.join(results_dir, "top_authors.csv"),
        ]
        authors_csv = next((p for p in author_candidates if os.path.exists(p)), None)
        
        if authors_csv:
            adf = pd.read_csv(authors_csv)
            name_col = next((c for c in ["Author", "author_name", "name", "vertex", "label"] if c in adf.columns), None)
            if name_col:
                pipeline_ranked = [str(a).lower().strip() for a in adf[name_col].head(len(gt_authors) * 2)]
                gt_ranked_names = [str(a["author"]).lower().strip() for a in gt_authors if "author" in a]
                
                # Overlap
                overlap = len(set(gt_ranked_names).intersection(set(pipeline_ranked)))
                metrics["author_overlap_count"] = overlap
                metrics["author_overlap_pct"] = (overlap / len(gt_ranked_names)) * 100.0 if gt_ranked_names else 0.0

    # 2. Country ranking correlation
    if gt_countries:
        country_candidates = [
            os.path.join(results_dir, "data", "top_countries.csv"),
            os.path.join(results_dir, "data", "country_counts.csv"),
            os.path.join(results_dir, "country_counts.csv"),
            os.path.join(results_dir, "country_evolution.csv"),
            os.path.join(results_dir, "top_countries.csv"),
        ]
        country_csv = next((p for p in country_candidates if os.path.exists(p)), None)
        
        if country_csv:
            cdf = pd.read_csv(country_csv)
            c_col = next((c for c in ["Country", "country", "affiliation_country"] if c in cdf.columns), None)
            if c_col:
                if "Count" in cdf.columns:
                    cdf_agg = cdf.groupby(c_col, as_index=False)["Count"].sum().sort_values("Count", ascending=False)
                else:
                    cdf_agg = cdf[c_col].value_counts().reset_index()
                    cdf_agg.columns = [c_col, "Count"]
                
                pipeline_countries = [str(c).lower().strip() for c in cdf_agg[c_col].head(len(gt_countries) * 2)]
                gt_c_names = [str(c["country"]).lower().strip() for c in gt_countries if "country" in c]
                overlap_c = len(set(gt_c_names).intersection(set(pipeline_countries)))
                metrics["country_overlap_count"] = overlap_c
                metrics["country_overlap_pct"] = (overlap_c / len(gt_c_names)) * 100.0 if gt_c_names else 0.0

                # Spearman Rank Correlation across matched items
                common = [c for c in gt_c_names if c in pipeline_countries]
                if len(common) >= 3:
                    gt_ranks = [gt_c_names.index(c) + 1 for c in common]
                    pipe_ranks = [pipeline_countries.index(c) + 1 for c in common]
                    rho, p_val = stats.spearmanr(gt_ranks, pipe_ranks)
                    metrics["country_spearman_rho"] = round(float(rho), 4) if not np.isnan(rho) else None
                    metrics["country_spearman_p"] = round(float(p_val), 4) if not np.isnan(p_val) else None

    # 3. Institution ranking correlation
    gt_institutions = sc_cfg.get("top_institutions", [])
    if gt_institutions:
        inst_candidates = [
            os.path.join(results_dir, "data", "top_institutions.csv"),
            os.path.join(results_dir, "top_institutions.csv"),
            os.path.join(results_dir, "data", "publication_dataset.csv"),
            os.path.join(results_dir, "publication_dataset.csv"),
            os.path.join(results_dir, "data", "network_nodes.csv"),
            os.path.join(results_dir, "network_nodes.csv"),
        ]
        inst_csv = next((p for p in inst_candidates if os.path.exists(p)), None)
        if inst_csv:
            idf = pd.read_csv(inst_csv)
            pipeline_institutions = []

            inst_col = next((c for c in ["Institution", "institution", "affiliations", "Affiliation", "name"] if c in idf.columns), None)
            if inst_col and "Count" in idf.columns:
                pipeline_institutions = [str(x).lower().strip() for x in idf.sort_values("Count", ascending=False)[inst_col].dropna().head(max(50, len(gt_institutions) * 4))]
            elif "Affiliations" in idf.columns or "affiliations_str" in idf.columns:
                affil_col = "Affiliations" if "Affiliations" in idf.columns else "affiliations_str"
                counts = {}
                for raw_val in idf[affil_col].dropna():
                    parts = [p.strip() for p in str(raw_val).split(";") if p.strip()]
                    for part in parts:
                        clean_part = re.sub(r"\s+", " ", part).strip()
                        clean_part = re.sub(r"^(department|school|faculty|institute|center|laboratory|division|college)\s+of\s+[^,]+,\s*", "", clean_part, flags=re.I)
                        clean_part = clean_part.split(",")[0].strip()
                        if clean_part and clean_part.lower() not in ("nan", "none", "unknown") and len(clean_part) > 2:
                            clean_lower = clean_part.lower()
                            counts[clean_lower] = counts.get(clean_lower, 0) + 1
                sorted_insts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                pipeline_institutions = [x[0] for x in sorted_insts[:max(50, len(gt_institutions) * 4)]]

            if pipeline_institutions:
                gt_inst_names = [str(x["institution"]).lower().strip() for x in gt_institutions if "institution" in x]
                matched_pairs = []
                matched_pipe_indices = set()

                for idx, gt_i in enumerate(gt_inst_names):
                    for p_rank, pipe_i in enumerate(pipeline_institutions):
                        if p_rank in matched_pipe_indices:
                            continue
                        if gt_i in pipe_i or pipe_i in gt_i:
                            matched_pairs.append((idx + 1, p_rank + 1, gt_i, pipe_i))
                            matched_pipe_indices.add(p_rank)
                            break
                        gt_tokens = set(re.findall(r"\b[a-z]{3,}\b", gt_i)) - {"university", "college", "institute", "school", "hospital", "the", "and", "of"}
                        pipe_tokens = set(re.findall(r"\b[a-z]{3,}\b", pipe_i)) - {"university", "college", "institute", "school", "hospital", "the", "and", "of"}
                        if gt_tokens and gt_tokens.issubset(pipe_tokens):
                            matched_pairs.append((idx + 1, p_rank + 1, gt_i, pipe_i))
                            matched_pipe_indices.add(p_rank)
                            break

                overlap_inst = len(matched_pairs)
                metrics["institution_overlap_count"] = overlap_inst
                metrics["institution_overlap_pct"] = (overlap_inst / len(gt_inst_names)) * 100.0 if gt_inst_names else 0.0

                if len(matched_pairs) >= 3:
                    gt_ranks = [p[0] for p in matched_pairs]
                    pipe_ranks = [p[1] for p in matched_pairs]
                    rho, p_val = stats.spearmanr(gt_ranks, pipe_ranks)
                    metrics["institution_spearman_rho"] = round(float(rho), 4) if not np.isnan(rho) else None
                    metrics["institution_spearman_p"] = round(float(p_val), 4) if not np.isnan(p_val) else None

    return metrics

def evaluate_meta_analysis(results_dir: str, benchmark_data: dict) -> Dict[str, Any]:
    gt_meta = benchmark_data.get("meta_analysis", {})
    if not gt_meta:
        return {}

    meta_json_path = os.path.join(results_dir, "meta_analysis_results.json")
    if not os.path.exists(meta_json_path):
        return {"error": f"meta_analysis_results.json not found in {results_dir}"}

    with open(meta_json_path, "r") as f:
        pipeline_meta = json.load(f)

    re_res = pipeline_meta.get("random_effects", {})
    het_res = pipeline_meta.get("heterogeneity", {})

    tool_est = re_res.get("estimate", None)
    tool_i2 = het_res.get("i_squared_pct", None)

    gt_est = gt_meta.get("pooled_effect_d")
    gt_i2 = gt_meta.get("i_squared_pct")

    res = {
        "ground_truth_pooled_d": gt_est,
        "pipeline_pooled_d": tool_est,
        "ground_truth_i_squared": gt_i2,
        "pipeline_i_squared": tool_i2
    }

    if tool_est is not None and gt_est is not None:
        res["effect_size_abs_error"] = abs(tool_est - gt_est)
    if tool_i2 is not None and gt_i2 is not None:
        res["i_squared_abs_error"] = abs(tool_i2 - gt_i2)

    return res

def main():
    parser = argparse.ArgumentParser(description="Validate Bibliometric & SLR Pipeline outputs against published ground-truth benchmarks")
    parser.add_argument("--results-dir", type=str, required=True, help="Path to pipeline output directory")
    parser.add_argument("--benchmark", type=str, required=True, help="Path to benchmark JSON configuration file")
    parser.add_argument("--output-report", type=str, help="Path to save Markdown validation report")
    args = parser.parse_args()

    if not os.path.exists(args.benchmark):
        print(f">>> [ERROR] Benchmark file not found: {args.benchmark}")
        sys.exit(1)

    if not os.path.exists(args.results_dir):
        print(f">>> [ERROR] Results directory not found: {args.results_dir}")
        sys.exit(1)

    with open(args.benchmark, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    title = benchmark_data.get("benchmark_title", "Published Benchmark Paper")
    doi = benchmark_data.get("reference_doi", "N/A")

    print("=" * 75)
    print(f">>> PIPELINE BENCHMARK VALIDATION: {title}")
    print(f">>> Reference Paper DOI: {doi}")
    print(f">>> Results Directory: {args.results_dir}")
    print("=" * 75)

    # 1. Screening Evaluation
    screening_res = evaluate_screening(args.results_dir, benchmark_data)
    if screening_res and "error" not in screening_res:
        print("\n[1. SYSTEMATIC REVIEW & PRISMA SCREENING VALIDATION]")
        print(f"    - Ground-Truth Target Studies (Included): {screening_res['ground_truth_total_included']}")
        print(f"    - Pipeline Correctly Retained (TP):       {screening_res['true_positives']}")
        print(f"    - Pipeline Missed Studies (FN):           {screening_res['false_negatives']}")
        print(f"    - Sensitivity / Recall:                   {screening_res['recall_sensitivity_pct']:.1f}%")
        print(f"    - Screening Precision:                    {screening_res['precision_pct']:.1f}%")
        print(f"    - F1-Score:                               {screening_res['f1_score_pct']:.1f}%")
        if screening_res.get("specificity_pct") is not None:
            print(f"    - Specificity (Exclusion accuracy):       {screening_res['specificity_pct']:.1f}%")
        if screening_res.get("wss_95_pct") is not None:
            print(f"    - Work Saved over Sampling (WSS@95):      {screening_res['wss_95_pct']:.1f}%")
        if screening_res.get("wmcc") is not None:
            print(f"    - Weighted Matthews Corr. Coeff. (WMCC):  {screening_res['wmcc']}")

    # 2. Scientometrics Evaluation
    sc_res = evaluate_scientometrics(args.results_dir, benchmark_data)
    if sc_res:
        print("\n[2. MACRO SCIENTOMETRIC & RANKING CONCORDANCE]")
        if "author_overlap_pct" in sc_res:
            print(f"    - Top Authors Overlap:  {sc_res['author_overlap_pct']:.1f}% ({sc_res['author_overlap_count']} matched)")
        if "country_overlap_pct" in sc_res:
            print(f"    - Top Countries Overlap: {sc_res['country_overlap_pct']:.1f}% ({sc_res['country_overlap_count']} matched)")
        if "institution_overlap_pct" in sc_res:
            inst_p_str = f" (rho={sc_res['institution_spearman_rho']}, p={sc_res['institution_spearman_p']})" if sc_res.get('institution_spearman_rho') is not None else ""
            print(f"    - Top Institutions Overlap: {sc_res['institution_overlap_pct']:.1f}% ({sc_res['institution_overlap_count']} matched){inst_p_str}")

    # 3. Meta-Analysis Evaluation
    meta_res = evaluate_meta_analysis(args.results_dir, benchmark_data)
    if meta_res and "error" not in meta_res:
        print("\n[3. QUANTITATIVE META-ANALYSIS CONCORDANCE]")
        print(f"    - Benchmark Pooled Effect (d):  {meta_res['ground_truth_pooled_d']}")
        print(f"    - Pipeline Pooled Effect (d):   {meta_res['pipeline_pooled_d']:.3f}")
        if "effect_size_abs_error" in meta_res:
            print(f"    - Absolute Error (|d_gt - d_tool|): {meta_res['effect_size_abs_error']:.3f}")
        if "i_squared_abs_error" in meta_res:
            print(f"    - Heterogeneity I^2 Error:          {meta_res['i_squared_abs_error']:.1f}%")

    print("\n" + "=" * 75)
    print(">>> [SUCCESS] Benchmark Validation Complete.")
    print("=" * 75)

    # Export Markdown Report
    report_file = args.output_report or os.path.join(args.results_dir, "benchmark_validation_report.md")
    lines = [
        f"# Benchmark Validation Report: {title}",
        f"- **Reference Paper**: `{doi}`",
        f"- **Evaluated Directory**: `{args.results_dir}`",
        "",
        "## 1. Systematic Review Screening Accuracy",
    ]
    if screening_res and "error" not in screening_res:
        lines.extend([
            f"- **Ground-Truth Target Included Studies**: {screening_res['ground_truth_total_included']}",
            f"- **Pipeline Correctly Retained (TP)**: {screening_res['true_positives']}",
            f"- **Pipeline Missed (FN)**: {screening_res['false_negatives']}",
            f"- **Sensitivity / Recall**: **`{screening_res['recall_sensitivity_pct']:.1f}%`**",
            f"- **Precision**: `{screening_res['precision_pct']:.1f}%`",
            f"- **F1 Score**: `{screening_res['f1_score_pct']:.1f}%`",
        ])
        if screening_res.get("specificity_pct") is not None:
            lines.append(f"- **Specificity**: `{screening_res['specificity_pct']:.1f}%`")
        if screening_res.get("wss_95_pct") is not None:
            lines.append(f"- **Work Saved over Sampling (WSS@95)**: **`{screening_res['wss_95_pct']:.1f}%`**")
        if screening_res.get("wmcc") is not None:
            lines.append(f"- **Weighted Matthews Corr. Coeff. (WMCC)**: **`{screening_res['wmcc']}`**")
    else:
        lines.append("- *Screening validation skipped or no ground-truth included DOIs provided.*")

    if sc_res:
        lines.extend([
            "",
            "## 2. Macro Scientometric Rankings",
            f"- **Top Authors Overlap**: `{sc_res.get('author_overlap_pct', 0.0):.1f}%`",
            f"- **Top Countries Overlap**: `{sc_res.get('country_overlap_pct', 0.0):.1f}%`",
            f"- **Top Institutions Overlap**: `{sc_res.get('institution_overlap_pct', 0.0):.1f}%`",
        ])

    if meta_res and "error" not in meta_res:
        lines.extend([
            "",
            "## 3. Quantitative Meta-Analysis Synthesis",
            f"- **Published Pooled Effect ($d$)**: `{meta_res['ground_truth_pooled_d']}`",
            f"- **Pipeline Pooled Effect ($d$)**: `{meta_res['pipeline_pooled_d']:.3f}`",
            f"- **Absolute Delta**: `{meta_res.get('effect_size_abs_error', 0.0):.3f}`",
        ])

    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write("\n".join(lines))
    print(f">>> Saved full validation report to: {report_file}")

if __name__ == '__main__':
    main()
