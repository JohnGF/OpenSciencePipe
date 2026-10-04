import os
import pytest
import pandas as pd
import numpy as np
from src.core.temporal_delta import TemporalDeltaAnalysis

def test_compute_temporal_deltas_baseline():
    tda = TemporalDeltaAnalysis()
    df = pd.DataFrame({
        "Keyword": ["deep learning"] * 10 + ["ica"] * 20 + ["deep learning"] * 30 + ["ica"] * 10,
        "Year": [2015] * 30 + [2022] * 40
    })
    delta_df = tda.compute_temporal_deltas(df, category_col="Keyword", year_col="Year", split_year=2020)
    assert not delta_df.empty
    assert "Delta_Share_Pct" in delta_df.columns
    assert "Fold_Change" in delta_df.columns
    dl_row = delta_df[delta_df["Category"] == "deep learning"].iloc[0]
    assert dl_row["Delta_Share_Pct"] > 0
    assert dl_row["Trajectory"] == "Emerging Frontier"

def test_compute_temporal_deltas_paper_penetration():
    tda = TemporalDeltaAnalysis()
    # 10 papers in 2015 (p1..p10): 8 have eeg, 2 have deep learning
    records = []
    for i in range(1, 11):
        pid = f"p_2015_{i}"
        if i <= 8:
            records.append({"Keyword": "eeg", "Year": 2015, "Paper_ID": pid})
        else:
            records.append({"Keyword": "ica", "Year": 2015, "Paper_ID": pid})
        if i <= 2:
            records.append({"Keyword": "deep learning", "Year": 2015, "Paper_ID": pid})

    # 20 papers in 2022 (p1..p20): 19 have eeg, 12 have deep learning
    for i in range(1, 21):
        pid = f"p_2022_{i}"
        if i <= 19:
            records.append({"Keyword": "eeg", "Year": 2022, "Paper_ID": pid})
        else:
            records.append({"Keyword": "ica", "Year": 2022, "Paper_ID": pid})
        if i <= 12:
            records.append({"Keyword": "deep learning", "Year": 2022, "Paper_ID": pid})

    df = pd.DataFrame(records)
    delta_df = tda.compute_temporal_deltas(df, category_col="Keyword", year_col="Year", split_year=2020, paper_id_col="Paper_ID")
    assert not delta_df.empty

    eeg_row = delta_df[delta_df["Category"] == "eeg"].iloc[0]
    assert eeg_row["Baseline_Share_Pct"] == 80.0
    assert eeg_row["Modern_Share_Pct"] == 95.0
    assert eeg_row["Delta_Share_Pct"] == 15.0

    dl_row = delta_df[delta_df["Category"] == "deep learning"].iloc[0]
    assert dl_row["Baseline_Share_Pct"] == 20.0
    assert dl_row["Modern_Share_Pct"] == 60.0
    assert dl_row["Delta_Share_Pct"] == 40.0

def test_compute_annual_trajectories():
    tda = TemporalDeltaAnalysis()
    # 5 years, two categories
    records = []
    for y in range(2018, 2023):
        # Category A: 10 papers every year
        for _ in range(10):
            records.append({"Technique": "A", "Year": y})
        # Category B: exponentially growing 2, 4, 8, 16, 32
        count_b = 2 ** (y - 2017)
        for _ in range(count_b):
            records.append({"Technique": "B", "Year": y})

    df = pd.DataFrame(records)
    trajectories = tda.compute_annual_trajectories(df, category_col="Technique", year_col="Year", top_n=2)
    assert not trajectories.empty
    assert set(trajectories["Category"].unique()) == {"A", "B"}
    assert "Market_Share_Pct" in trajectories.columns
    assert "YoY_Delta_Pct" in trajectories.columns

    # Category B market share should be strictly increasing
    b_shares = trajectories[trajectories["Category"] == "B"]["Market_Share_Pct"].tolist()
    assert b_shares[-1] > b_shares[0]

def test_compute_multi_epoch_crosstab():
    tda = TemporalDeltaAnalysis()
    records = []
    for y in range(2014, 2026):
        method = "DL" if y >= 2020 else "ICA"
        app = "Clinical" if y % 2 == 0 else "BCI"
        records.append({"Method": method, "Application": app, "Year": y})

    df = pd.DataFrame(records)
    matrices = tda.compute_multi_epoch_crosstab(df, row_col="Method", col_col="Application", year_col="Year", n_bins=3)
    assert len(matrices) > 0
    for label, matrix in matrices.items():
        assert isinstance(matrix, pd.DataFrame)
        assert not matrix.empty

def test_plot_annual_share_and_faceted_viz(tmp_path):
    from src.core.viz import Visualization
    viz = Visualization()
    tda = TemporalDeltaAnalysis()

    # Synthetic trajectory
    df = pd.DataFrame([
        {"Year": 2020, "Category": "DL", "Market_Share_Pct": 10.0},
        {"Year": 2021, "Category": "DL", "Market_Share_Pct": 20.0},
        {"Year": 2020, "Category": "ICA", "Market_Share_Pct": 90.0},
        {"Year": 2021, "Category": "ICA", "Market_Share_Pct": 80.0},
    ])
    traj_pdf = str(tmp_path / "trajectories.pdf")
    viz.plot_annual_share_trajectories(df, save_path=traj_pdf)
    assert os.path.exists(traj_pdf)

    # Synthetic faceted heatmap
    m1 = pd.DataFrame({"BCI": [30.0, 70.0], "Clinical": [60.0, 40.0]}, index=["DL", "ICA"])
    m2 = pd.DataFrame({"BCI": [60.0, 40.0], "Clinical": [40.0, 60.0]}, index=["DL", "ICA"])
    heatmap_pdf = str(tmp_path / "faceted_heatmap.pdf")
    viz.plot_faceted_crosstab_heatmap({"2014-2019": m1, "2020-2026": m2}, save_path=heatmap_pdf)
    assert os.path.exists(heatmap_pdf)

