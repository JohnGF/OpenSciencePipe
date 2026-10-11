import pytest
import polars as pl
import pandas as pd
from src.core.network import NetworkAnalysis

def test_build_co_authorship_graph():
    # Test network generation with data acceleration
    analyzer = NetworkAnalysis(use_gpu=False) # Fallback to CPU to ensure tests run anywhere
    df = pl.DataFrame([
        {
            "Title": "Paper A",
            "DOI": "10.1",
            "Authors": "Alice; Bob",
            "Affiliations": "Univ A",
            "Cite Count": 10
        },
        {
            "Title": "Paper B",
            "DOI": "10.2",
            "Authors": "Bob; Charlie",
            "Affiliations": "Univ B",
            "Cite Count": 5
        }
    ])
    
    edges, nodes = analyzer.build_co_authorship_graph(df)
    
    assert not edges.empty
    # Alice-Bob, Bob-Charlie
    assert len(edges) == 2
    assert "source_id" in edges.columns
    assert "dest_id" in edges.columns
    assert "weight" in edges.columns
    
    # Check that weight for Alice-Bob is 1
    assert set(edges["weight"]) == {1}
    
    # Check node metadata
    assert not nodes.empty
    assert "author_name" in nodes.columns
    assert "total_citations" in nodes.columns
    assert "num_publications" in nodes.columns
    
    # Bob is in both papers
    bob_node = nodes[nodes["author_name"] == "Bob"]
    assert len(bob_node) == 1
    assert bob_node["num_publications"].values[0] == 2
    assert bob_node["total_citations"].values[0] == 15

def test_build_directed_citation_graph():
    analyzer = NetworkAnalysis(use_gpu=False)
    df = pl.DataFrame([
        {
            "Title": "Paper A",
            "DOI": "10.1",
            "Year": 2020,
            "Cite Count": 10,
            "References": "10.2; 10.3"
        }
    ])
    
    edges, nodes = analyzer.build_directed_citation_graph(df)
    
    assert not edges.empty
    # Paper A cites 10.2 and 10.3
    assert len(edges) == 2
    assert set(edges["source"].unique()) == {"10.1"}
    assert set(edges["destination"]) == {"10.2", "10.3"}
    
    assert not nodes.empty
    assert "paper_id" in nodes.columns
    assert "pagerank" in nodes.columns
