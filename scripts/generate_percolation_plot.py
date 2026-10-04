import os
import sys
import pandas as pd

# Ensure repository root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.core.viz import Visualization
from src.core.citations import CitationsAnalysis

def main():
    clean_edges = os.path.join(repo_root, "outputs", "paper3_clean", "network_edges.csv")
    out_csv = os.path.join(repo_root, "outputs", "paper3_clean", "percolation_results.csv")

    if os.path.exists(clean_edges):
        print(f"Running percolation analysis on 57k network edges: {clean_edges}...")
        edges_df = pd.read_csv(clean_edges)
        s_col = "source" if "source" in edges_df.columns else edges_df.columns[0]
        d_col = "destination" if "destination" in edges_df.columns else edges_df.columns[1]
        w_col = "weight" if "weight" in edges_df.columns else edges_df.columns[2]

        ca = CitationsAnalysis()
        df = ca.perform_percolation_analysis(edges_df, s_col, d_col, w_col)
        df.to_csv(out_csv, index=False)
        print(f"Percolation sweep complete. Saved to {out_csv}")
    else:
        csv_path = os.path.join(repo_root, "outputs", "pipeline_results_37k", "data", "percolation_results.csv")
        if not os.path.exists(csv_path):
            print(f"Error: {csv_path} not found.")
            sys.exit(1)
        print(f"Loading percolation results from {csv_path}...")
        df = pd.read_csv(csv_path)

    viz = Visualization(style="whitegrid")

    # Target destinations
    destinations = [
        os.path.join(repo_root, "outputs", "paper3_clean"),
        os.path.join(repo_root, "outputs", "pipeline_results_37k"),
        os.path.join(repo_root, "zenodo_bundle"),
        os.path.join(repo_root, "manuscripts", "paper3_eeg_noise_applied", "figures")
    ]

    weight_col = "Edge Weight" if "Edge Weight" in df.columns else ("cutoff" if "cutoff" in df.columns else df.columns[0])

    for dest in destinations:
        os.makedirs(dest, exist_ok=True)
        pdf_path = os.path.join(dest, "percolation_analysis.pdf")
        png_path = os.path.join(dest, "percolation_analysis.png")
        csv_dest = os.path.join(dest, "percolation_results.csv")

        print(f"Generating percolation plots in {dest}...")
        viz.plot_percolation(df, weight_col=weight_col, save_path=pdf_path)
        viz.plot_percolation(df, weight_col=weight_col, save_path=png_path)
        df.to_csv(csv_dest, index=False)

    print("Done!")

if __name__ == "__main__":
    main()
