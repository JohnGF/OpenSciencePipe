import os
import sys
import pandas as pd
import logging
import ast
import re

logger = logging.getLogger(__name__)

def _clean_keywords(r, tid):
    raw_rep = r.get("Representation", None)
    if pd.notna(raw_rep) and str(raw_rep).strip().startswith("["):
        try:
            terms = ast.literal_eval(str(raw_rep))
            if isinstance(terms, list) and terms:
                clean_terms = [str(t).replace("_", " ").replace("&", r"\&").strip() for t in terms[:4] if str(t).strip()]
                return ", ".join(clean_terms)
        except Exception:
            pass
    raw_name = str(r.get("Name", "")).lower()
    raw_name = re.sub(rf"^{tid}_", "", raw_name)
    parts = [p.strip().replace("&", r"\&") for p in raw_name.split("_") if p.strip()]
    return ", ".join(parts[:4])

def _infer_meta_theme(name: str) -> str:
    name_l = name.lower()
    if any(w in name_l for w in ["artifact", "ica", "wavelet", "noise", "tms", "emg", "filter", "electrode", "kalman", "memd", "ceemdan", "afe", "amplifier"]):
        return "Advanced Artifact Suppression"
    elif any(w in name_l for w in ["bci", "motor", "mi", "ssvep", "cca", "intent", "imagery", "p300"]):
        return "Brain-Computer Interface Systems"
    elif any(w in name_l for w in ["diffusion", "gan", "generative", "gcn", "transformer", "deep learning", "neural"]):
        return "Machine Learning Frontiers"
    elif any(w in name_l for w in ["aperiodic", "1/f", "timescale", "complexity", "entropy", "criticality"]):
        return "Neural Dynamics \\& Complexity"
    else:
        return "Clinical \\& Biological Applications"

def export_bertopic_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_bertopic_details.tex containing BERTopic Meta-Theme Taxonomy."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_bertopic_details.tex")
    top_fpath = os.path.join(output_dir, "annex_bertopic_details.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    topic_csv = os.path.join(output_dir, "data", "topic_info.csv")
    if not os.path.exists(topic_csv):
        topic_csv = os.path.join(output_dir, "topic_info.csv")

    if os.path.exists(topic_csv):
        try:
            df = pd.read_csv(topic_csv)
            valid = df[df["Topic"] != -1] if "Topic" in df.columns else df
            if len(valid) == 0:
                valid = df

            tex = []
            tex.append("\\subsection{AI-Driven Content Analysis \\& BERTopic Taxonomy}")
            tex.append("\\begin{table}[htbp]")
            tex.append("\\caption{BERTopic Thematic Decomposition: Foundational Macro-Themes and Emergent Frontier Micro-Clusters}")
            tex.append("\\label{tab:bertopic_clusters}")
            tex.append("\\scriptsize")
            tex.append("\\setlength{\\tabcolsep}{4pt}")
            tex.append("\\begin{tabular}{r p{0.32\\linewidth} p{0.38\\linewidth} r}")
            tex.append("\\toprule")
            tex.append("\\textbf{\\#} & \\textbf{Consolidated Meta-Theme} & \\textbf{c-TF-IDF Representative Keywords} & \\textbf{Papers} \\\\")
            tex.append("\\midrule")

            if len(valid) > 15:
                # Two-panel structure
                panel_a = valid.head(10)
                # Select diverse micro-clusters with Count >= 10 from beyond top 15
                candidates = valid.iloc[10:]
                panel_b = candidates[candidates["Count"] >= 10].tail(12) if len(candidates[candidates["Count"] >= 10]) >= 12 else candidates.tail(12)

                tex.append("\\multicolumn{4}{l}{\\textit{\\textbf{Panel A: Foundational Macro-Clusters (High-Volume Pillars)}}} \\\\")
                tex.append("\\midrule")
                for _, r in panel_a.iterrows():
                    tid = int(r.get("Topic", 0))
                    theme = _infer_meta_theme(str(r.get("Name", "")))
                    clean_kw = _clean_keywords(r, tid)
                    cnt = int(r.get("Count", 0))
                    tex.append(f"T{tid} & {theme} & {clean_kw} & {cnt:,} \\\\")

                tex.append("\\midrule")
                tex.append("\\multicolumn{4}{l}{\\textit{\\textbf{Panel B: Emergent Frontier Micro-Clusters (Fine-Grained Specializations)}}} \\\\")
                tex.append("\\midrule")
                for _, r in panel_b.iterrows():
                    tid = int(r.get("Topic", 0))
                    theme = _infer_meta_theme(str(r.get("Name", "")))
                    clean_kw = _clean_keywords(r, tid)
                    cnt = int(r.get("Count", 0))
                    tex.append(f"T{tid} & {theme} & {clean_kw} & {cnt:,} \\\\")
            else:
                for _, r in valid.iterrows():
                    tid = int(r.get("Topic", 0))
                    theme = _infer_meta_theme(str(r.get("Name", "")))
                    clean_kw = _clean_keywords(r, tid)
                    cnt = int(r.get("Count", 0))
                    tex.append(f"T{tid} & {theme} & {clean_kw} & {cnt:,} \\\\")

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
            logger.warning(f"Could not generate annex_bertopic_details.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% BERTopic Details Annex\n\\subsection{BERTopic Details}\n\\label{tab:bertopic_clusters}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_bertopic_table(out_dir, force=True)
