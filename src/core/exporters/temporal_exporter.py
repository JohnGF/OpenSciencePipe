import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_temporal_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_temporal_deltas.tex containing Scientific Market Share Deltas (Delta %)."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_temporal_deltas.tex")
    top_fpath = os.path.join(output_dir, "annex_temporal_deltas.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    pub_csv = os.path.join(output_dir, "data", "publication_dataset.csv")
    if not os.path.exists(pub_csv):
        pub_csv = os.path.join(output_dir, "publication_dataset.csv")
    if not os.path.exists(pub_csv):
        logger.warning(f"Could not find publication dataset in {output_dir}; returning empty.")
        return

    if os.path.exists(pub_csv):
        try:
            df = pd.read_csv(pub_csv)
            from src.core.temporal_delta import TemporalDeltaAnalysis
            tda = TemporalDeltaAnalysis()
            if "Author Keywords" in df.columns and "Year" in df.columns:
                import re
                records = []
                for idx, r in df.dropna(subset=["Author Keywords", "Year"]).iterrows():
                    yr = int(r["Year"])
                    kws = str(r["Author Keywords"]).split(";")
                    paper_id = r.get("DOI", r.get("doi", r.get("Title", idx)))
                    for k in kws:
                        k_clean = k.strip().lower()
                        # Clean parenthetical Wikidata disambiguations like "(linguistics)", "(evolution)"
                        k_clean = re.sub(r"\s*\([^)]*\)", "", k_clean).strip()
                        if k_clean and k_clean not in ["key", "lock", "nan", "none"]:
                            records.append({"Keyword": k_clean, "Year": yr, "Paper_ID": paper_id})
                kdf = pd.DataFrame(records)
                delta_df = tda.compute_temporal_deltas(
                    kdf, category_col="Keyword", year_col="Year", paper_id_col="Paper_ID"
                )
                if not delta_df.empty:
                    tex = []
                    tex.append(r"\subsection{Scientific Temporal Dynamics \& Author Keywords Market Share Deltas (\texorpdfstring{$\Delta$}{Delta})}")
                    tex.append(r"\begin{table}[htbp]")
                    tex.append(r"\caption{Author Keyword Temporal Dynamics: Baseline ($T_1$) vs Modern ($T_2$) Relative Share Deltas}")
                    tex.append(r"\label{tab:temporal_deltas}")
                    tex.append(r"\small")
                    tex.append(r"\setlength{\tabcolsep}{4pt}")
                    tex.append(r"\begin{tabular}{p{0.26\linewidth} r r r r p{0.18\linewidth}}")
                    tex.append(r"\toprule")
                    tex.append(r"\textbf{Author Keyword} & \textbf{$T_1$ (\%)} & \textbf{$T_2$ (\%)} & \textbf{$\Delta$ (\%)} & \textbf{Fold} & \textbf{Trajectory} \\")
                    tex.append(r"\midrule")
                    for _, r in delta_df.head(15).iterrows():
                        cat = str(r["Category"]).replace("_", r"\_").replace("&", r"\&")
                        st1 = float(r["Baseline_Share_Pct"])
                        st2 = float(r["Modern_Share_Pct"])
                        delta = float(r["Delta_Share_Pct"])
                        fold_val = r["Fold_Change"]
                        fold_str = f"{float(fold_val):.1f}x" if pd.notna(fold_val) and st1 > 0 else "N/A"
                        traj = str(r["Trajectory"])
                        tex.append(f"{cat[:28]} & {st1:.1f}\\% & {st2:.1f}\\% & {delta:+.2f}\\% & {fold_str} & {traj} \\\\")
                    tex.append("\\bottomrule")
                    tex.append("\\multicolumn{6}{p{0.95\\linewidth}}{\\scriptsize \\textit{Note: Metric reflects the multi-label paper penetration rate (\\% of publications in each epoch specifying the author keyword).}} \\\\")
                    tex.append("\\end{tabular}")
                    tex.append("\\end{table}")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(tex))
                    with open(top_fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(tex))
                    logger.info(f"Generated {fpath} successfully!")
                    return
        except Exception as e:
            logger.warning(f"Could not generate annex_temporal_deltas.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% Temporal Deltas Annex\n\\subsection{Temporal Delta Shifts}\n\\label{tab:temporal_deltas}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_temporal_table(out_dir, force=True)
