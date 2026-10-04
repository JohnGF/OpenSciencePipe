import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from src.core.meta_analysis import EffectSizeSynthesizer

logger = logging.getLogger(__name__)

class MetaAnalysisBenchmarkValidator:
    """
    Validates the EffectSizeSynthesizer against gold-standard published benchmark datasets
    across Medicine (Colditz 1994, Nissen 2007), Psychology (Smith & Glass 1977), and
    Economics (Doucouliagos & Stanley 2009).
    """

    def __init__(self, benchmarks_dir: str = "data/benchmarks/meta"):
        self.benchmarks_dir = Path(benchmarks_dir)
        self.synthesizer = EffectSizeSynthesizer()

    def run_all_benchmarks(self) -> List[Dict[str, Any]]:
        """Executes validation tests against all benchmark JSON files in the directory."""
        results = []
        if not self.benchmarks_dir.exists():
            logger.error(f"Benchmarks directory not found: {self.benchmarks_dir}")
            return results

        json_files = sorted(list(self.benchmarks_dir.glob("*.json")))
        for jf in json_files:
            res = self.validate_benchmark_file(jf)
            results.append(res)
        return results

    def validate_benchmark_file(self, file_path: Path) -> Dict[str, Any]:
        """Runs validation for a single benchmark JSON specification."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        bench_id = data.get("benchmark_id", file_path.stem)
        name = data.get("name", bench_id)
        domain = data.get("domain", "General")
        expected = data.get("expected_statistics", {})
        studies = data.get("studies", [])

        df = pd.DataFrame(studies)
        meta_res, clean_df = self.synthesizer.run_meta_analysis(df, effect_col="d_i", var_col="v_i")

        checks = []
        # Check Random Effects estimate
        if "random_effects_pooled_estimate" in expected:
            actual_re = meta_res.get("random_effects", {}).get("estimate", np.nan)
            exp_re = expected["random_effects_pooled_estimate"]
            diff = abs(actual_re - exp_re)
            passed = diff <= 0.08  # tolerance
            checks.append({
                "metric": "Random Effects Pooled Estimate",
                "expected": exp_re,
                "actual": round(actual_re, 4),
                "diff": round(diff, 4),
                "passed": passed
            })

        # Check Q statistic
        if "q_statistic" in expected:
            actual_q = meta_res.get("heterogeneity", {}).get("q_stat", np.nan)
            exp_q = expected["q_statistic"]
            diff_q = abs(actual_q - exp_q)
            passed_q = (diff_q / max(1.0, exp_q)) <= 0.10
            checks.append({
                "metric": "Cochran's Q Statistic",
                "expected": exp_q,
                "actual": round(actual_q, 2),
                "diff": round(diff_q, 2),
                "passed": passed_q
            })

        # Check I-squared
        if "i_squared_pct" in expected:
            actual_i2 = meta_res.get("heterogeneity", {}).get("i_squared_pct", np.nan)
            exp_i2 = expected["i_squared_pct"]
            diff_i2 = abs(actual_i2 - exp_i2)
            passed_i2 = diff_i2 <= 5.0
            checks.append({
                "metric": "I-squared Heterogeneity (%)",
                "expected": exp_i2,
                "actual": round(actual_i2, 2),
                "diff": round(diff_i2, 2),
                "passed": passed_i2
            })

        # Check Meta-Regression if moderator exists
        if "meta_regression_ablat_beta" in expected and "ablat" in df.columns:
            reg_res = self.synthesizer.run_meta_regression(df, moderator_col="ablat", effect_col="d_i", var_col="v_i")
            actual_beta = reg_res.get("beta", np.nan)
            exp_beta = expected["meta_regression_ablat_beta"]
            diff_beta = abs(actual_beta - exp_beta)
            passed_beta = diff_beta <= 0.015
            checks.append({
                "metric": "Meta-Regression Slope (ablat)",
                "expected": exp_beta,
                "actual": round(actual_beta, 4),
                "diff": round(diff_beta, 4),
                "passed": passed_beta
            })

        all_passed = all(c["passed"] for c in checks) if checks else False

        return {
            "benchmark_id": bench_id,
            "name": name,
            "domain": domain,
            "source_doi": data.get("source_doi", "N/A"),
            "num_studies": len(df),
            "all_passed": all_passed,
            "checks": checks,
            "meta_results": meta_res,
            "expected": expected
        }

    def export_latex_table(self, results: List[Dict[str, Any]], output_path: str = "tables/tab_validation_meta_analysis.tex"):
        """Exports the benchmark results to LaTeX table format."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            r"\begin{table*}[t]",
            r"\centering",
            r"\small",
            r"\caption{Section 3.3: Quantitative Meta-Analysis Pooled Effect Sizes and Heterogeneity Concordance Across Gold-Standard Domains}",
            r"\label{tab:validation_meta_analysis}",
            r"\begin{tabular}{p{4.8cm}p{3.2cm}p{2.2cm}ccccc}",
            r"\hline",
            r"\textbf{Benchmark Study} & \textbf{Reference DOI} & \textbf{Domain} & \textbf{GT $d$} & \textbf{Tool $d$} & \textbf{Error $|d|$} & \textbf{GT $I^2$} & \textbf{Tool $I^2$} \\",
            r"\hline",
        ]

        for r in results:
            name = r["name"].replace("&", r"\&").replace("_", r"\_")
            doi = r.get("source_doi", "N/A").replace("_", r"\_")
            domain = r["domain"].replace("&", r"\&").split("/")[0].strip()
            exp = r.get("expected", {})
            gt_d = exp.get("random_effects_pooled_estimate", "N/A")
            gt_i2 = f"{exp.get('i_squared_pct', 'N/A')}\\%" if "i_squared_pct" in exp else "N/A"

            actual_d = r.get("meta_results", {}).get("random_effects", {}).get("estimate", np.nan)
            actual_i2 = r.get("meta_results", {}).get("heterogeneity", {}).get("i_squared_pct", np.nan)

            tool_d = f"{actual_d:.4f}" if not np.isnan(actual_d) else "N/A"
            diff_d = f"{abs(actual_d - gt_d):.4f}" if not np.isnan(actual_d) and isinstance(gt_d, (int, float)) else "N/A"
            tool_i2 = f"{actual_i2:.1f}\\%" if not np.isnan(actual_i2) else "N/A"

            lines.append(f"{name} & \\texttt{{{doi}}} & {domain} & {gt_d} & {tool_d} & {diff_d} & {gt_i2} & {tool_i2} \\\\")

        lines.extend([
            r"\hline",
            r"\end{tabular}",
            r"\end{table*}"
        ])

        with open(out_p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f">>> [SAVED] {output_path}")

if __name__ == "__main__":
    validator = MetaAnalysisBenchmarkValidator()
    results = validator.run_all_benchmarks()
    for r in results:
        status = "PASSED" if r["all_passed"] else "FAILED"
        print(f"[{status}] {r['name']} ({r['domain']}) - {r['num_studies']} studies")
        for c in r["checks"]:
            c_status = "PASS" if c["passed"] else "FAIL"
            print(f"   [{c_status}] {c['metric']}: Expected {c['expected']}, Got {c['actual']} (Diff: {c['diff']})")
    validator.export_latex_table(results)
