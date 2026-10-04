import os
import sys
import shutil
from typing import Optional

# Ensure repo root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import polars as pl
import pandas as pd
from src.core.viz import Visualization
from src.core.temporal_delta import TemporalDeltaAnalysis


def _dataset_for(output_dir: str) -> Optional[str]:
    """Locate the dataset used for an output directory."""
    candidates = [
        os.path.join(output_dir, "data", "publication_dataset.csv"),
        os.path.join(output_dir, "publication_dataset.csv"),
        os.path.join("data", "collected_EEG_master_merged.csv"),
        os.path.join("..", "data", "collected_EEG_master_merged.csv"),
    ]
    return next((c for c in candidates if os.path.exists(c)), None)


def regenerate_figures(output_dir: str = "pipeline_results_37k") -> int:
    """Regenerates analysis figures from the dataset into the output directory.

    Covers the yearly growth chart, temporal delta shifts, LLM noise paradigm
    donut, and methodology x application field matrix. Figure titles are
    deliberately query-neutral so the scaffold is reusable for any dataset.
    """
    os.makedirs(output_dir, exist_ok=True)
    fig_dir = os.path.join(output_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    dataset = _dataset_for(output_dir)
    if not dataset:
        print("[!] No dataset found for figure regeneration.")
        return 1

    print(f"[+] Reading {dataset} ...")
    df_pd = pd.read_csv(dataset)
    viz = Visualization()

    # The harvest year is incomplete at collection time (flagged is_partial by
    # plot_yearly_growth). Annual trajectory / epoch figures must stop at the
    # last complete year, otherwise 2026 renders as a false collapse.
    LAST_COMPLETE_YEAR = int(pd.Timestamp.now().year) - 1
    print(f"[+] Truncating annual trajectory figures at last complete year: {LAST_COMPLETE_YEAR}")

    def save(name: str, pdf_name: str):
        pdf_src = os.path.join(output_dir, pdf_name)
        if os.path.exists(pdf_src):
            shutil.copyfile(pdf_src, os.path.join(fig_dir, pdf_name))

    # 1. Yearly growth (also writes the growth CSV).
    df = pl.from_pandas(df_pd)
    df = df.filter(pl.col("Year").is_not_null())
    df = df.with_columns(pl.col("Year").cast(pl.Int64))
    growth = viz.plot_yearly_growth(df, save_path=os.path.join(output_dir, "yearly_growth.pdf"))
    if growth is not None and not growth.empty:
        min_yr = int(growth["Year"].min())
        max_yr = int(growth["Year"].max())
        growth.to_csv(os.path.join(output_dir, "yearly_growth.csv"), index=False)
        growth.to_csv(os.path.join(data_dir, "yearly_growth.csv"), index=False)
        print(f"[✓] Regenerated yearly growth ({min_yr}-{max_yr}) -> {output_dir}/yearly_growth.pdf")
    save("yearly_growth.pdf", "yearly_growth.pdf")

    # 2. Temporal delta shifts (requires Author Keywords).
    if "Author Keywords" in df_pd.columns and "Year" in df_pd.columns:
        try:
            records = []
            for _, r in df_pd.dropna(subset=["Author Keywords", "Year"]).iterrows():
                yr = int(r["Year"])
                for k in str(r["Author Keywords"]).split(";"):
                    k_clean = k.strip().lower()
                    if k_clean:
                        records.append({"Keyword": k_clean, "Year": yr})
            kdf = pd.DataFrame(records)
            delta_df = TemporalDeltaAnalysis().compute_temporal_deltas(
                kdf, category_col="Keyword", year_col="Year"
            )
            if delta_df is not None and not delta_df.empty:
                viz.plot_temporal_delta_shifts(
                    delta_df,
                    title_suffix="Research Focus Areas",
                    save_path=os.path.join(output_dir, "temporal_delta_shifts.pdf"),
                )
                print(f"[✓] Regenerated temporal delta shifts -> {output_dir}/temporal_delta_shifts.pdf")
                save("temporal_delta_shifts.pdf", "temporal_delta_shifts.pdf")
        except Exception as e:
            print(f"[!] Could not regenerate temporal delta shifts: {e}")

    # 3. LLM noise treatment paradigm taxonomy.
    try:
        viz.plot_llm_noise_paradigm(df_pd, save_path=os.path.join(output_dir, "llm_noise_paradigm.pdf"))
        print(f"[✓] Regenerated LLM noise paradigm chart -> {output_dir}/llm_noise_paradigm.pdf")
        save("llm_noise_paradigm.pdf", "llm_noise_paradigm.pdf")
    except Exception as e:
        print(f"[!] Could not regenerate LLM noise paradigm chart: {e}")

    # 4. Methodology x application field matrix.
    try:
        viz.plot_method_application_matrix(df_pd, save_path=os.path.join(output_dir, "method_application_matrix.pdf"))
        print(f"[✓] Regenerated methodology x application matrix -> {output_dir}/method_application_matrix.pdf")
        save("method_application_matrix.pdf", "method_application_matrix.pdf")
    except Exception as e:
        print(f"[!] Could not regenerate methodology x application matrix: {e}")

    # 5. Annual market share trajectories for key research techniques.
    if "Author Keywords" in df_pd.columns and "Year" in df_pd.columns:
        try:
            records = []
            for _, r in df_pd.dropna(subset=["Author Keywords", "Year"]).iterrows():
                yr = int(r["Year"])
                for k in str(r["Author Keywords"]).split(";"):
                    k_clean = k.strip().lower()
                    if k_clean:
                        records.append({"Keyword": k_clean, "Year": yr})
            kdf = pd.DataFrame(records)
            trajectories_df = TemporalDeltaAnalysis().compute_annual_trajectories(
                kdf, category_col="Keyword", year_col="Year", top_n=8
            )
            trajectories_df = trajectories_df[trajectories_df["Year"] <= LAST_COMPLETE_YEAR]
            if trajectories_df is not None and not trajectories_df.empty:
                trajectories_df.to_csv(os.path.join(data_dir, "annual_trajectories.csv"), index=False)
                trajectories_df.to_csv(os.path.join(output_dir, "annual_trajectories.csv"), index=False)
                viz.plot_annual_share_trajectories(
                    trajectories_df,
                    category_col="Category",
                    year_col="Year",
                    share_col="Market_Share_Pct",
                    title_suffix="Key Focus Areas & Techniques",
                    save_path=os.path.join(output_dir, "annual_technique_trajectories.pdf"),
                )
                print(f"[✓] Regenerated annual trajectories -> {output_dir}/annual_technique_trajectories.pdf")
                save("annual_technique_trajectories.pdf", "annual_technique_trajectories.pdf")
        except Exception as e:
            print(f"[!] Could not regenerate annual trajectories: {e}")

    # 6. Multi-epoch methodology x application matrix.
    try:
        titles = (
            df_pd["Title"].fillna("").astype(str).str.lower()
            if "Title" in df_pd.columns
            else pd.Series([""] * len(df_pd))
        )
        abstracts = (
            df_pd["Abstract"].fillna("").astype(str).str.lower()
            if "Abstract" in df_pd.columns
            else pd.Series([""] * len(df_pd))
        )
        text = titles + " " + abstracts

        methods = []
        apps = []
        for t in text:
            if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                m = "ICA / Wavelet Denoising"
            elif any(w in t for w in ["deep learning", "cnn", "convolutional", "transformer", "neural network"]):
                m = "Deep Learning (CNN/DL)"
            elif any(w in t for w in ["csp", "fbcsp", "ssvep", "spatial pattern", "evoked"]):
                m = "Spatial Patterns (CSP/SSVEP)"
            elif any(w in t for w in ["stochastic", "resonance", "entropy", "variability"]):
                m = "Stochastic Noise Dynamics"
            else:
                m = "General Signal Processing"

            if any(w in t for w in ["epilep", "seiz"]):
                a = "Epilepsy & Seizures"
            elif any(w in t for w in ["sleep", "apnea", "polysomn"]):
                a = "Sleep Staging"
            elif any(w in t for w in ["workload", "fatigue", "drows", "vigilance", "mental load"]):
                a = "Cognitive Workload"
            elif any(w in t for w in ["motor imagery", "mi-bci", "prosthet", "stroke", "rehab"]):
                a = "Motor Imagery BCI"
            elif any(w in t for w in ["emotion", "affective", "valence", "arousal"]):
                a = "Emotion Recognition"
            else:
                a = "General Clinical & Bio"
            methods.append(m)
            apps.append(a)

        mapped_df = df_pd.copy()
        mapped_df["Method"] = methods
        mapped_df["Application"] = apps
        mapped_df = mapped_df[
            mapped_df["Year"].isna() | (mapped_df["Year"].astype(int) <= LAST_COMPLETE_YEAR)
        ]
        if "Year" in mapped_df.columns:
            epoch_matrices = TemporalDeltaAnalysis().compute_multi_epoch_crosstab(
                mapped_df, row_col="Method", col_col="Application", year_col="Year", n_bins=3
            )
            if epoch_matrices:
                viz.plot_faceted_crosstab_heatmap(
                    epoch_matrices,
                    title_prefix="Methodology vs Application Evolution Across Eras",
                    save_path=os.path.join(output_dir, "method_application_multi_epoch.pdf"),
                )
                print(f"[✓] Regenerated multi-epoch method x application matrix -> {output_dir}/method_application_multi_epoch.pdf")
                save("method_application_multi_epoch.pdf", "method_application_multi_epoch.pdf")
    except Exception as e:
        print(f"[!] Could not regenerate multi-epoch methodology x application matrix: {e}")

    # 7. Annual paradigm market share trajectory (Methodology level: DL vs ICA vs CSP vs Stochastic vs General)
    try:
        method_traj_df = TemporalDeltaAnalysis().compute_annual_trajectories(
            mapped_df, category_col="Method", year_col="Year", top_n=5
        )
        method_traj_df = method_traj_df[method_traj_df["Year"] <= LAST_COMPLETE_YEAR]
        if method_traj_df is not None and not method_traj_df.empty:
            method_traj_df.to_csv(os.path.join(data_dir, "annual_method_trajectories.csv"), index=False)
            method_traj_df.to_csv(os.path.join(output_dir, "annual_method_trajectories.csv"), index=False)
            viz.plot_annual_share_trajectories(
                method_traj_df,
                category_col="Category",
                year_col="Year",
                share_col="Market_Share_Pct",
                title_suffix="EEG Noise Processing Paradigms",
                save_path=os.path.join(output_dir, "annual_method_trajectories.pdf"),
            )
            print(f"[✓] Regenerated annual method trajectories -> {output_dir}/annual_method_trajectories.pdf")
            save("annual_method_trajectories.pdf", "annual_method_trajectories.pdf")
    except Exception as e:
        print(f"[!] Could not regenerate annual method trajectories: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(regenerate_figures(sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"))
