import os
import json
import logging
import subprocess
import pandas as pd
from typing import Optional, Dict, Any, List

from src.core.viz import Visualization
from src.core.screening import PaperScreener
from src.core.exporters.llm_exporter import export_llm_table
from src.core.study_config import load_study_config

logger = logging.getLogger(__name__)

class SystematicReviewOrchestrator:
    """
    Dedicated Orchestrator for Qualitative PRISMA 2020 Systematic Literature Reviews.
    Executes deterministic screening, exclusion auditing, PRISMA flowcharts, and SLR manuscript generation.
    """

    def __init__(self, output_dir: str = "pipeline_results_slr", config: Optional[dict] = None, profiler=None):
        self.output_dir = output_dir
        self.config = config or {}
        self.profiler = profiler
        self.figures_dir = os.path.join(self.output_dir, "figures")
        self.tables_dir = os.path.join(self.output_dir, "tables")
        self.data_dir = os.path.join(self.output_dir, "data")
        self.viz = Visualization()

        os.makedirs(self.figures_dir, exist_ok=True)
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def _parse_patterns(self, val: Any) -> List[str]:
        if not val:
            return []
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        if isinstance(val, str):
            # Split on comma if not containing regex brackets or if intended
            if "," in val and "[" not in val:
                return [v.strip() for v in val.split(",") if v.strip()]
            return [val.strip()]
        return []

    def _load_criteria_file(self, criteria_path: str) -> Dict[str, Any]:
        result = {"include_patterns": [], "exclude_patterns": [], "target_prompt": None}
        if not os.path.exists(criteria_path):
            logger.warning(f"Criteria file '{criteria_path}' not found.")
            return result
        try:
            if criteria_path.endswith(".json"):
                with open(criteria_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    result["include_patterns"] = self._parse_patterns(data.get("include_patterns") or data.get("inclusion") or data.get("include", []))
                    result["exclude_patterns"] = self._parse_patterns(data.get("exclude_patterns") or data.get("exclusion") or data.get("exclude", []))
                    result["target_prompt"] = data.get("target_prompt") or data.get("prompt")
            else:
                with open(criteria_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.lower().startswith("include:"):
                            result["include_patterns"].append(line[8:].strip())
                        elif line.lower().startswith("exclude:"):
                            result["exclude_patterns"].append(line[8:].strip())
                        elif line.lower().startswith("prompt:"):
                            result["target_prompt"] = line[7:].strip()
        except Exception as e:
            logger.warning(f"Error reading criteria file {criteria_path}: {e}")
        return result

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        print("\n========================================================")
        print(">>> [SYSTEMATIC REVIEW PIPELINE] Starting PRISMA Protocol")
        print("========================================================")

        # Stage 1: PICOS Screening & Exclusion Auditing
        if self.profiler: self.profiler.start("1. PICOS Screening & Exclusion")
        print("\n>>> [SLR STAGE 1] Evaluating Studies against PICOS Eligibility Criteria...")

        study_cfg = load_study_config()
        active_query = self.config.get("query") or study_cfg.get("query") or "Empirical Scientific Literature"

        # Resolve patterns
        include_patterns = self._parse_patterns(self.config.get("include_regex") or self.config.get("include_pattern"))
        exclude_patterns = self._parse_patterns(self.config.get("exclude_regex") or self.config.get("exclude_pattern"))
        target_prompt = self.config.get("target_prompt") or active_query

        criteria_file = self.config.get("criteria_file") or self.config.get("picos_config")
        if criteria_file:
            file_criteria = self._load_criteria_file(criteria_file)
            include_patterns.extend(file_criteria.get("include_patterns", []))
            exclude_patterns.extend(file_criteria.get("exclude_patterns", []))
            if file_criteria.get("target_prompt"):
                target_prompt = file_criteria["target_prompt"]

        print(f">>> Active Topic: '{active_query}'")
        if include_patterns:
            print(f">>> Inclusion Grep Patterns ({len(include_patterns)}): {include_patterns}")
        if exclude_patterns:
            print(f">>> Exclusion Grep Patterns ({len(exclude_patterns)}): {exclude_patterns}")

        screener = PaperScreener(
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            use_embedding_filter=self.config.get("screen_embeddings", False),
            embedding_threshold=self.config.get("embedding_threshold", 0.35),
            target_prompt=target_prompt,
            use_llm_categorization=self.config.get("screen_llm", False),
            llm_model=self.config.get("llm_model", "llama3.2:3b"),
            topic_context=active_query
        )

        screened_df, audit_df = screener.screen(df, return_audit=True)
        prisma_metrics = screener.prisma_metrics

        # Save audited outputs
        audit_csv = os.path.join(self.data_dir, "screening_audit.csv")
        audit_df.to_csv(audit_csv, index=False)
        print(f">>> Full PRISMA Screening Audit saved to: {audit_csv}")

        included_csv = os.path.join(self.data_dir, "screened_included_studies.csv")
        screened_df.to_csv(included_csv, index=False)
        print(f">>> Screened & Included Studies ({len(screened_df)}/{len(df)}) saved to: {included_csv}")

        pub_csv = os.path.join(self.data_dir, "publication_dataset.csv")
        df.to_csv(pub_csv, index=False)

        with open(os.path.join(self.output_dir, "prisma_metrics.json"), "w") as f:
            json.dump(prisma_metrics, f, indent=4)

        print(f"\n>>> [PRISMA 2020 SUMMARY]")
        print(f"    - Records Identified: {prisma_metrics['identified']}")
        print(f"    - Records Screened:   {prisma_metrics['screened']} (Excluded: {prisma_metrics['excluded_screening']})")
        print(f"    - Full-Text Assessed: {prisma_metrics['sought']} (Excluded: {prisma_metrics['excluded_fulltext']})")
        print(f"    - Studies Included:   {prisma_metrics['included']}")
        if prisma_metrics.get("exclusion_reasons"):
            print("    - Exclusion Breakdown:")
            for reason, count in prisma_metrics["exclusion_reasons"].items():
                print(f"      * {reason}: {count}")

        if self.profiler: self.profiler.stop("1. PICOS Screening & Exclusion")

        # Stage 2: PRISMA 2020 Flowchart
        if self.profiler: self.profiler.start("2. PRISMA Flow Diagram")
        print("\n>>> [SLR STAGE 2] Rendering PRISMA 2020 Flowchart Diagram...")
        self.viz.plot_prisma_flowchart(prisma_metrics, save_path=os.path.join(self.figures_dir, "prisma_flowchart.pdf"))
        if self.profiler: self.profiler.stop("2. PRISMA Flow Diagram")

        # Stage 3: Thematic Taxonomy Table
        if self.profiler: self.profiler.start("3. Thematic Synthesis")
        print("\n>>> [SLR STAGE 3] Synthesizing Qualitative Thematic Taxonomy...")
        export_llm_table(self.output_dir, force=True)
        if self.profiler: self.profiler.stop("3. Thematic Synthesis")

        # Stage 4: SLR Manuscript Compilation
        if self.profiler: self.profiler.start("4. LaTeX SLR Compilation")
        print("\n>>> [SLR STAGE 4] Compiling Systematic Literature Review Scaffold...")
        from src.core.latex_exporter import LaTeXExporter
        exporter = LaTeXExporter(self.output_dir)
        exporter.copy_cls_template()

        safe_title = active_query.title().replace('&', '\\&').replace('_', ' ')
        n_ident = prisma_metrics["identified"]
        n_inc = prisma_metrics["included"]

        slr_tex = [
            "\\documentclass[journal,onecolumn]{IEEEtran}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage[english]{babel}",
            "\\usepackage{graphicx}",
            "\\graphicspath{{figures/}}",
            "\\usepackage{booktabs}",
            "\\usepackage{hyperref}",
            "\\usepackage{ragged2e}",
            "\\usepackage{array}",
            "\\usepackage{longtable}",
            "",
            f"\\title{{A Systematic Literature Review and PRISMA 2020 Synthesis: {safe_title}}}",
            "\\author{Automated Research Engine}",
            "\\begin{document}",
            "\\maketitle",
            "",
            "\\begin{abstract}",
            f"This Systematic Literature Review applies PRISMA 2020 guidelines to synthesize evidence on {safe_title}. "
            f"A total of {n_ident:,} initial records were screened, resulting in {n_inc:,} included studies evaluated across methodological paradigms and thematic categories.",
            "\\end{abstract}",
            "",
            "\\section{Introduction}",
            f"Systematic literature reviews provide comprehensive, reproducible syntheses of scientific literature. "
            f"This study investigates the state of the art in {active_query} following established PRISMA 2020 protocols.",
            "",
            "\\section{PRISMA 2020 Identification \\& Screening}",
            f"A systematic search identified {n_ident:,} candidate records. After deterministic eligibility and screening audits, "
            f"{n_inc:,} studies satisfied all inclusion criteria. The complete flow of studies is detailed in Fig.~\\ref{{fig:prisma}}.",
            "",
            "\\begin{figure}[htbp]\\centering\\IfFileExists{figures/prisma_flowchart.pdf}{\\includegraphics[width=0.85\\linewidth]{prisma_flowchart.pdf}}{}\\caption{PRISMA 2020 Study Flowchart.}\\label{fig:prisma}\\end{figure}",
            "",
            "\\section{Thematic Taxonomy \\& Categorization}",
            "Table~\\ref{tab:llm_screening} summarizes the distribution of research paradigms and methodologies across the included corpus.",
            "",
            "\\IfFileExists{tables/annex_llm_screening.tex}{\\input{tables/annex_llm_screening.tex}}{}",
            "",
            "\\section{Discussion \\& Future Directions}",
            "Synthesis of qualitative findings reveals major consensus themes, emerging methodologies, and opportunities for standardized empirical protocols.",
            "",
            "\\section{Conclusion}",
            f"This review presents a reproducible, audit-backed synthesis of {n_inc:,} scientific contributions in {active_query}.",
            "\\end{document}"
        ]

        slr_fpath = os.path.join(self.output_dir, "slr_paper_scaffold_onecolumn.tex")
        with open(slr_fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(slr_tex))

        try:
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "slr_paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "slr_paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
            slr_pdf = os.path.join(self.output_dir, "slr_paper_scaffold_onecolumn.pdf")
            if os.path.exists(slr_pdf):
                print(f">>> [SUCCESS] Systematic Review PDF generated: {slr_pdf}")
        except Exception as e:
            logger.warning(f"Could not compile slr_paper_scaffold: {e}")

        if self.profiler: self.profiler.stop("4. LaTeX SLR Compilation")
        print(f"\n>>> [COMPLETE] Systematic Review completed in {self.output_dir}")
        return prisma_metrics

