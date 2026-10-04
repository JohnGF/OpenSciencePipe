import pandas as pd
import pytest
from src.core.meta_analysis import EffectSizeSynthesizer

def test_subgroup_analysis():
    synthesizer = EffectSizeSynthesizer()
    df = pd.DataFrame({
        "effect_size": [0.8, 0.6, 0.7, 0.2, 0.1, 0.3],
        "sample_size": [50, 40, 60, 50, 45, 55],
        "subgroup": ["High Dose", "High Dose", "High Dose", "Low Dose", "Low Dose", "Low Dose"]
    })

    res = synthesizer.run_subgroup_analysis(df, group_col="subgroup", effect_col="effect_size", n_col="sample_size")
    assert "subgroups" in res
    assert "High Dose" in res["subgroups"]
    assert "Low Dose" in res["subgroups"]
    assert res["q_between"] > 0
    assert "p_between" in res

def test_meta_regression():
    synthesizer = EffectSizeSynthesizer()
    # Create dataset with linear relationship between dosage/year and effect size
    df = pd.DataFrame({
        "effect_size": [0.2, 0.4, 0.6, 0.8, 1.0],
        "sample_size": [50, 50, 50, 50, 50],
        "dosage_mg": [10, 20, 30, 40, 50]
    })

    res = synthesizer.run_meta_regression(df, moderator_col="dosage_mg", effect_col="effect_size", n_col="sample_size")
    assert res["k_studies"] == 5
    assert res["beta"] > 0
    assert res["p_value"] < 0.05
    assert res["r_squared"] > 0.8
