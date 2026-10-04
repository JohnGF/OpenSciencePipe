import os
import pandas as pd
import pytest
from src.core.viz import Visualization
from src.core.exporters.egm_exporter import export_egm_tables

def test_evidence_gap_map_viz(tmp_path):
    viz = Visualization()
    df = pd.DataFrame({
        "intervention": ["Cognitive Training", "Pharmacotherapy", "Cognitive Training", "Neuromodulation", "Neuromodulation"],
        "outcome": ["Memory Recall", "Memory Recall", "Attention Span", "Attention Span", "Motor Function"],
        "effect_direction": ["positive", "mixed", "positive", "negative", "positive"]
    })
    
    save_pdf = os.path.join(tmp_path, "test_egm.pdf")
    fig = viz.plot_evidence_gap_map(df, intervention_col="intervention", outcome_col="outcome", effect_dir_col="effect_direction", save_path=save_pdf)
    assert fig is not None
    assert os.path.exists(save_pdf)
    assert os.path.exists(save_pdf.replace(".pdf", ".png"))

def test_egm_exporter(tmp_path):
    matrix_df = pd.DataFrame({
        "Memory Recall": [5, 2],
        "Attention Span": [3, 0]
    }, index=["Cognitive Training", "Neuromodulation"])
    
    csv_path = os.path.join(tmp_path, "evidence_gap_map_matrix.csv")
    matrix_df.to_csv(csv_path)
    
    export_egm_tables(output_dir=str(tmp_path))
    tex_path = os.path.join(tmp_path, "tables", "tab_evidence_gap_map.tex")
    assert os.path.exists(tex_path)
    with open(tex_path, "r") as f:
        content = f.read()
        assert "Evidence Gap Map" in content
        assert "Cognitive Training" in content
