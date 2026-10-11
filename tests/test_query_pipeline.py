import pytest
from src.cli import main
from unittest.mock import patch, MagicMock

@patch("src.cli.PipelineManager")
def test_cli_query_pipeline(mock_pipeline_manager):
    # Test that the CLI parser correctly translates arguments into a pipeline call
    mock_manager_instance = MagicMock()
    mock_pipeline_manager.return_value = mock_manager_instance
    
    # We mock sys.argv to simulate a CLI call
    import sys
    test_args = ["biblio-pipeline", "--query", "quantum computing", "--limit", "50", "--start-year", "2020"]
    with patch.object(sys, "argv", test_args):
        main()
        
    mock_pipeline_manager.assert_called_once()
    mock_manager_instance.run_with_query.assert_called_once()
