import os
import pandas as pd
import numpy as np
import pytest
from src.core.nlp import detect_bursts_kleinberg
from src.core.meta_analysis import EffectSizeSynthesizer
from src.core.viz import Visualization

def test_kleinberg_burst_detection():
    # Construct synthetic dataset with a burst in 'transformer' around 2021-2023
    data = []
    for y in range(2015, 2025):
        # Baseline noise
        for _ in range(20):
            data.append({"keyword": "eeg", "Year": y})
            data.append({"keyword": "ica", "Year": y})
        # Burst term
        burst_count = 15 if y in [2021, 2022, 2023] else 1
        for _ in range(burst_count):
            data.append({"keyword": "transformer", "Year": y})

    df = pd.DataFrame(data)
    burst_df = detect_bursts_kleinberg(df, term_col="keyword", year_col="Year", s=2.0)
    assert not burst_df.empty
    assert "transformer" in burst_df["Term"].values
    trans_row = burst_df[burst_df["Term"] == "transformer"].iloc[0]
    assert trans_row["Start_Year"] in [2020, 2021]
    assert trans_row["Weight"] > 0

def test_trim_and_fill_publication_bias():
    synthesizer = EffectSizeSynthesizer()
    # Asymmetric distribution of effect sizes (missing left side / negative studies)
    df = pd.DataFrame({
        "effect_size": [0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 0.9],
        "sample_size": [60, 55, 50, 45, 40, 35, 30, 25, 20]
    })

    res = synthesizer.run_trim_and_fill(df, effect_col="effect_size", n_col="sample_size", side="left")
    assert "k0_missing" in res
    assert res["k0_missing"] >= 0
    assert "adjusted_estimate" in res
    assert "imputed_df" in res
    assert len(res["imputed_df"]) >= len(df)

def test_contour_funnel_and_sankey_viz(tmp_path):
    viz = Visualization()
    # Funnel
    df = pd.DataFrame({
        "d_i": [0.2, 0.3, 0.4, 0.5, 0.6],
        "v_i": [0.04, 0.05, 0.06, 0.07, 0.08],
        "is_imputed": [False, False, False, True, True]
    })
    funnel_pdf = os.path.join(tmp_path, "test_contour_funnel.pdf")
    fig1 = viz.plot_funnel(df, effect_col="d_i", var_col="v_i", show_contours=True, save_path=funnel_pdf)
    assert fig1 is not None
    assert os.path.exists(funnel_pdf)

    # Sankey
    sankey_df = pd.DataFrame({
        "Epoch": ["2015-2019"] * 10 + ["2020-2024"] * 10,
        "Theme": ["ICA"] * 6 + ["Wavelet"] * 4 + ["CNN"] * 7 + ["Transformers"] * 3
    })
    sankey_pdf = os.path.join(tmp_path, "test_thematic_sankey.pdf")
    fig2 = viz.plot_thematic_evolution_sankey(sankey_df, epoch_col="Epoch", theme_col="Theme", save_path=sankey_pdf)
    assert fig2 is not None
    assert os.path.exists(sankey_pdf)

    # Burst timeline
    burst_df = pd.DataFrame({
        "Term": ["Transformer", "Deep Learning", "ICA"],
        "Weight": [12.5, 8.2, 5.1],
        "Start_Year": [2021, 2018, 2014],
        "End_Year": [2024, 2022, 2017],
        "Duration": [4, 5, 4]
    })
    burst_pdf = os.path.join(tmp_path, "test_burst_timeline.pdf")
    fig3 = viz.plot_burst_table_timeline(burst_df, top_n=5, save_path=burst_pdf)
    assert fig3 is not None
    assert os.path.exists(burst_pdf)
