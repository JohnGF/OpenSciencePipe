import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_method_application_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_method_application_matrix.tex containing Methodology vs Application Field Cross-Tabulation."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_method_application_matrix.tex")
    top_fpath = os.path.join(output_dir, "annex_method_application_matrix.tex")

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
            tex = []
            tex.append(r"\subsection{Methodology \texorpdfstring{$\times$}{x} Application Field Bipartite Mapping}")
            tex.append(r"\begin{table}[htbp]")
            tex.append(r"\caption{Methodology vs Application Field Cross-Tabulation}")
            tex.append(r"\label{tab:method_application}")
            tex.append(r"\scriptsize")
            tex.append(r"\setlength{\tabcolsep}{4pt}")
            tex.append(r"\begin{tabular}{p{0.30\linewidth} p{0.30\linewidth} r r}")
            tex.append(r"\toprule")
            tex.append(r"\textbf{Methodology / Technique} & \textbf{Application Field} & \textbf{Papers} & \textbf{Share (\%)} \\")
            tex.append(r"\midrule")

            titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
            abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
            text = titles + " " + abstracts

            methods = []
            apps = []
            for t in text:
                if any(k in t for k in ["deep learning", "cnn", "convolutional", "transformer", "conformer", "autoencoder", "latent representation", "neural network"]):
                    m = "Deep Latent Decoding"
                elif any(k in t for k in ["common spatial", "csp", "fbcsp", "riemannian", "spatial filter"]):
                    m = "Spatial & Riemannian Filtering"
                elif any(k in t for k in ["aperiodic", "1/f", "specparam", "fooof", "irasa", "stochastic", "resonance", "pink noise", "scale-free"]):
                    m = "Aperiodic & Spectral Parameterization"
                elif any(k in t for k in ["ica", "independent component", "blind source", "artifact removal", "artifact correction", "wavelet", "denois", "filtering", "suppression"]):
                    m = "Linear BSS & Explicit Filtering"
                else:
                    m = "General Signal Processing"

                if any(k in t for k in ["stroke", "hemipares", "neurorehab", "motor recovery", "upper limb", "upper-limb", "gait", "exoskelet", "orthos", "fes", "wheelchair", "prosthes", "prosthet", "assistive robot"]):
                    a = "Neurorehab & Assistive Robotics"
                elif any(k in t for k in ["motor imagery", "mi-bci", "sensorimotor rhythm", "mu rhythm", "erd/ers", " erd ", " ers ", "movement intent", "imagined movement", "hand movement"]):
                    a = "Motor Imagery & SMR"
                elif any(k in t for k in ["ssvep", "p300", "speller", "steady-state visual", "steady state visual", "evoked potential", "visual evoked", "event-related potential", "oddball"]):
                    a = "Evoked Potentials (SSVEP / P300)"
                elif any(k in t for k in ["emotion", "affective", "mental workload", "workload", "fatigue", "drowsiness", "vigilance", "cognitive load"]):
                    a = "Passive & Affective BCI"
                elif any(k in t for k in ["neurofeedback", "brain-state", "neuromodulation", "closed-loop", "cognitive training", "alpha training"]):
                    a = "Neurofeedback & Closed-Loop"
                else:
                    a = "General BCI & Neural Decoding"

                methods.append(m)
                apps.append(a)

            ct = pd.crosstab(pd.Series(methods, name="Methodology"), pd.Series(apps, name="Application Field"))
            unstacked = ct.unstack().reset_index(name="Count").sort_values("Count", ascending=False)
            total = unstacked["Count"].sum() if unstacked["Count"].sum() > 0 else 1

            for _, r in unstacked.head(15).iterrows():
                m_name = str(r["Methodology"]).replace("_", "\\_").replace("&", "\\&")
                a_name = str(r["Application Field"]).replace("_", "\\_").replace("&", "\\&")
                cnt = int(r["Count"])
                pct = (cnt / total) * 100.0
                tex.append(f"{m_name} & {a_name} & {cnt:,} & {pct:.1f}\\% \\\\")
            tex.append("\\bottomrule")
            tex.append("\\end{tabular}")
            tex.append("\\end{table}")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(tex))
            with open(top_fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(tex))
            logger.info(f"Generated {fpath} successfully!")
            return
        except Exception as e:
            logger.warning(f"Could not generate annex_method_application_matrix.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% Method-Application Annex\n\\subsection{Methodology vs Application}\n\\label{tab:method_application}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_method_application_table(out_dir, force=True)
