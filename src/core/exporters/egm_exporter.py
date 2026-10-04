import os
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def export_egm_tables(output_dir: str = "pipeline_results", force: bool = False):
    """
    Exports Evidence Gap Map (EGM) cross-tabulated LaTeX tables.
    Summarizes study density across intervention types and outcome domains.
    """
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    
    egm_csv = os.path.join(output_dir, "evidence_gap_map_matrix.csv")
    out_tex = os.path.join(tables_dir, "tab_evidence_gap_map.tex")
    
    if not os.path.exists(egm_csv):
        alt_csv = os.path.join(output_dir, "data", "evidence_gap_map_matrix.csv")
        if os.path.exists(alt_csv):
            egm_csv = alt_csv
        else:
            return

    try:
        matrix_df = pd.read_csv(egm_csv, index_col=0)
        if matrix_df.empty:
            return

        interventions = list(matrix_df.index)
        outcomes = list(matrix_df.columns)
        
        col_spec = "l " + " ".join(["r"] * len(outcomes))
        
        tex = [
            "\\subsection{Evidence Gap Map (EGM) Cross-Tabulation}",
            "\\begin{table}[htbp]",
            "\\caption{Evidence Gap Map: Study Distribution Across Interventions and Outcome Domains}",
            "\\label{tab:evidence_gap_map}",
            "\\scriptsize",
            "\\setlength{\\tabcolsep}{4pt}",
            f"\\begin{{tabular}}{{{col_spec}}}",
            "\\toprule",
            "\\textbf{Intervention / Method} & " + " & ".join([f"\\textbf{{{c}}}" for c in outcomes]) + " \\\\",
            "\\midrule"
        ]
        
        for idx, row in matrix_df.iterrows():
            clean_idx = str(idx).replace("&", "\\&").replace("_", " ").title()
            row_vals = []
            for col in outcomes:
                val = row[col]
                if pd.isna(val) or val == 0:
                    row_vals.append("---")
                else:
                    row_vals.append(str(int(val)))
            tex.append(f"{clean_idx} & " + " & ".join(row_vals) + " \\\\")
            
        tex.append("\\bottomrule")
        tex.append("\\end{tabular}")
        tex.append("\\end{table}")
        
        with open(out_tex, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        logger.info(f"Generated {out_tex} successfully.")
    except Exception as e:
        logger.warning(f"Could not export tab_evidence_gap_map.tex: {e}")
