import pytest
import pandas as pd
from src.core.ingestion import validate_publications, PublicationSchema, extract_countries, generate_pdf_name

def test_publication_schema_validation():
    # Test valid parsing
    df = pd.DataFrame([
        {
            "Title": "A test paper",
            "Abstract": "This is an abstract",
            "Authors": "Doe, J.",
            "Year": 2023,
            "Affiliations": "University of Test, NY, USA",
            "DOI": "10.1234/5678",
            "EID": "2-s2.0-1234",
            "References": "10.111/222"
        },
        {
            "Title": pd.NA, # Should become "Untitled Publication"
            "Year": "invalid year", # Should become None
        }
    ])
    
    validated = validate_publications(df)
    assert len(validated) == 2
    
    # Check first record
    assert validated[0].title == "A test paper"
    assert validated[0].abstract == "This is an abstract"
    assert validated[0].year == 2023
    
    # Check second record (error handling)
    assert validated[1].title == "Untitled Publication"
    assert validated[1].year is None

def test_extract_countries():
    assert "United States" in extract_countries("University of Testing, CA, USA")
    assert "France" in extract_countries("Sorbonne, Paris, France")
    assert "China" in extract_countries("Tsinghua University, Beijing, PRC")
    assert "South Korea" in extract_countries("Seoul National University, South Korea")

def test_generate_pdf_name():
    row1 = {"Title": "Advanced Machine Learning Techniques", "Authors": "Smith, J.; Doe, J.", "Year": 2022}
    # first_author logic strips out ", J." in some cases.
    assert generate_pdf_name(row1) == "Smith et al. (2022) Advanced Machine Learning Techniques"
    
    row2 = {"Title": "A simple paper", "Authors": "Smith, J.", "Year": 2022}
    assert generate_pdf_name(row2) == "Smith (2022) A simple paper"
    
    row3 = {"Title": pd.NA, "Authors": pd.NA, "Year": pd.NA}
    assert generate_pdf_name(row3) == "Publication"
