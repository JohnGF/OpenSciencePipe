import os
import sys
import re
import collections
import pandas as pd
import logging

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "of", "to", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "this", "that", "these", "those", "from",
    "as", "using", "based", "study", "analysis", "results", "paper", "data", "method",
    "methods", "approach", "proposed", "via", "towards", "between", "into", "through",
    "can", "we", "our", "their", "such", "than", "more", "also", "which", "over"
}

def _extract_top_keyphrases(texts: list, top_k: int = 6) -> list:
    """Extracts top bi-gram/tri-gram themes from free-form text dynamically."""
    phrase_counts = collections.Counter()
    
    for t in texts:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', str(t).lower())
        filtered = [w for w in words if w not in STOPWORDS]
        # Bigrams
        for i in range(len(filtered) - 1):
            w1, w2 = filtered[i], filtered[i+1]
            if w1 != w2:
                phrase_counts[f"{w1.capitalize()} {w2.capitalize()}"] += 1
                
    top_phrases = [p for p, _ in phrase_counts.most_common(top_k)]
    return top_phrases if top_phrases else ["Empirical Investigation", "Theoretical Analysis", "Methodological Evaluation"]

def export_llm_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_llm_screening.tex containing domain-aware AI/LLM Thematic Categorization."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_llm_screening.tex")
    top_fpath = os.path.join(output_dir, "annex_llm_screening.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    pub_csv = os.path.join(output_dir, "data", "screened_included_studies.csv")
    if not os.path.exists(pub_csv):
        pub_csv = os.path.join(output_dir, "data", "publication_dataset.csv")
    if not os.path.exists(pub_csv):
        pub_csv = os.path.join(output_dir, "publication_dataset.csv")
    if not os.path.exists(pub_csv):
        logger.warning(f"Could not find publication dataset in {output_dir}; returning empty.")
        return

    try:
        df = pd.read_csv(pub_csv)
        tex = []
        tex.append("\\subsection{Automated Thematic \\& Methodological Taxonomy}")
        tex.append("\\begin{table}[htbp]")
        tex.append("\\caption{Synthesized Thematic \\& Methodological Categorization}")
        tex.append("\\label{tab:llm_screening}")
        tex.append("\\small")
        tex.append("\\begin{tabular}{p{0.50\\linewidth} r r}")
        tex.append("\\toprule")
        tex.append("\\textbf{Research Focus / Paradigm} & \\textbf{Papers} & \\textbf{Share (\\%)} \\\\")
        tex.append("\\midrule")

        # Check if LLM/classifier category column is present
        category_col = None
        for cand in ["thematic_category", "llm_category", "meta_theme", "dominant_topic", "Topic_Name"]:
            if cand in df.columns and df[cand].notna().sum() > 0:
                category_col = cand
                break

        # Check if topic_info.csv exists from BERTopic
        topic_info_csv = os.path.join(output_dir, "data", "topic_info.csv")
        if not category_col and os.path.exists(topic_info_csv):
            try:
                tdf = pd.read_csv(topic_info_csv)
                if "Topic" in tdf.columns and "Count" in tdf.columns and "Name" in tdf.columns:
                    valid_topics = tdf[tdf["Topic"] != -1].head(8)
                    total = valid_topics["Count"].sum()
                    if total > 0:
                        for _, trow in valid_topics.iterrows():
                            tname = str(trow["Name"]).split("_", 1)[-1].replace("_", " ").title()
                            tname = tname.replace('&', '\\&')
                            cnt = int(trow["Count"])
                            pct = (cnt / total) * 100.0
                            tex.append(f"{tname} & {cnt:,} & {pct:.1f}\\% \\\\")
                        category_col = "DONE_FROM_TOPIC_INFO"
            except Exception:
                pass

        if category_col and category_col != "DONE_FROM_TOPIC_INFO":
            counts = df[category_col].value_counts().head(8)
            total = len(df)
            for p_name, cnt in counts.items():
                pct = (cnt / total) * 100.0
                safe_name = str(p_name).replace('&', '\\&').replace('_', ' ')
                tex.append(f"{safe_name} & {cnt:,} & {pct:.1f}\\% \\\\")
        elif category_col != "DONE_FROM_TOPIC_INFO":
            # Dynamic extraction based on actual dataset text
            titles = df["Title"].fillna("").astype(str) if "Title" in df.columns else pd.Series([""] * len(df))
            abstracts = df["Abstract"].fillna("").astype(str) if "Abstract" in df.columns else pd.Series([""] * len(df))
            text = (titles + " " + abstracts).tolist()

            top_phrases = _extract_top_keyphrases(text, top_k=6)
            
            # Categorize papers by closest matching keyphrase
            paradigms = []
            for t in text:
                t_lower = str(t).lower()
                matched = False
                for p in top_phrases:
                    words = p.lower().split()
                    if any(w in t_lower for w in words):
                        paradigms.append(p)
                        matched = True
                        break
                if not matched:
                    paradigms.append("General Domain Studies")

            counts = pd.Series(paradigms).value_counts()
            total = len(paradigms) if len(paradigms) > 0 else 1
            for p_name, cnt in counts.items():
                pct = (cnt / total) * 100.0
                safe_name = str(p_name).replace('&', '\\&').replace('_', ' ')
                tex.append(f"{safe_name} & {cnt:,} & {pct:.1f}\\% \\\\")

        tex.append("\\bottomrule")
        tex.append("\\end{tabular}")
        tex.append("\\end{table}")

        with open(fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        with open(top_fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        logger.info(f"Generated {fpath} successfully!")
    except Exception as e:
        logger.warning(f"Could not generate annex_llm_screening.tex: {e}")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_llm_table(out_dir, force=True)

