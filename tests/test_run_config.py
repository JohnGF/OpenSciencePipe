import json
import sys
from argparse import Namespace
from unittest.mock import MagicMock, patch

from src import cli


def test_save_and_load_run_config_excludes_secrets(tmp_path):
    args = Namespace(
        query="brain-computer interface",
        query_file=None,
        file=None,
        refs_file=None,
        limit=250,
        start_year=2020,
        end_year=2024,
        output=str(tmp_path),
        mode="biblio",
        stages="nlp,network",
        include_regex="eeg|bci",
        exclude_regex="review",
        criteria_file=None,
        target_prompt=None,
        screen_embeddings=True,
        embedding_threshold=0.4,
        screen_llm=False,
        llm_model="llama3.2:3b",
        llm_topic_naming=False,
        subcluster_threshold=0,
        subcluster_passes=2,
        include_preprints=False,
        top_per_community=1,
        min_publications=2,
        skip_nlp=False,
        skip_network=False,
        skip_cagr=False,
        skip_country=False,
        skip_percolation=False,
        skip_llm=False,
        skip_collection=False,
        meta_analysis=False,
        picos_config=None,
        project_dir=None,
        openalex_email="secret@example.com",
        ss_api_key="ss-secret-key",
        scopus_api_key="scopus-secret-key",
    )

    cfg_path = cli._save_run_config(str(tmp_path), args, active_query="brain-computer interface")
    assert cfg_path.endswith("run_config.json")

    with open(cfg_path, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert saved["query"] == "brain-computer interface"
    assert saved["limit"] == 250
    assert saved["start_year"] == 2020
    assert saved["end_year"] == 2024
    assert saved["stages"] == ["nlp", "network"]
    assert saved["screen_embeddings"] is True
    assert saved["embedding_threshold"] == 0.4
    assert "created_at" in saved
    assert saved["reproduce_command"] == f"biblio-pipeline --config {cfg_path}"

    for secret_key in ("openalex_email", "ss_api_key", "scopus_api_key"):
        assert secret_key not in saved

    loaded = cli._load_run_config(cfg_path)
    assert loaded["query"] == "brain-computer interface"
    assert loaded["limit"] == 250
    assert loaded["stages"] == "nlp,network"


def test_cli_replays_saved_config_and_allows_overrides(tmp_path):
    out_dir = tmp_path / "run_out"
    cfg_path = tmp_path / "run_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "query": "neural decoding",
                "limit": 150,
                "start_year": 2019,
                "end_year": 2024,
                "output": str(out_dir),
                "mode": "biblio",
                "stages": ["nlp", "network"],
            }
        ),
        encoding="utf-8",
    )

    mock_manager = MagicMock()
    with patch("src.cli.PipelineManager", return_value=mock_manager) as mock_cls, patch.object(
        sys, "argv", ["biblio-pipeline", "--config", str(cfg_path), "--limit", "50"]
    ):
        cli.main()

    mock_cls.assert_called_once()
    _, kwargs = mock_cls.call_args
    assert kwargs["output_dir"] == str(out_dir)
    assert kwargs["config"]["stages"] == ["nlp", "network"]
    mock_manager.run_with_query.assert_called_once_with(
        "neural decoding", limit=50, start_year=2019, end_year=2024
    )
    assert (out_dir / "run_config.json").exists()


def test_cli_file_overrides_query_from_config(tmp_path):
    out_dir = tmp_path / "run_out"
    cfg_path = tmp_path / "run_config.json"
    cfg_path.write_text(
        json.dumps({"query": "neural decoding", "output": str(out_dir)}),
        encoding="utf-8",
    )
    local_csv = tmp_path / "author_a.csv"
    local_csv.write_text("title,doi\nPaper A,10.1000/a\n", encoding="utf-8")

    mock_manager = MagicMock()
    with patch("src.cli.PipelineManager", return_value=mock_manager), patch.object(
        sys, "argv", ["biblio-pipeline", "--config", str(cfg_path), "--file", str(local_csv)]
    ):
        cli.main()

    mock_manager.run_with_query.assert_not_called()
    mock_manager.run.assert_called_once_with(str(local_csv), refs_path=None)


def test_cli_merge_file_combines_and_deduplicates_datasets(tmp_path):
    import pandas as pd
    from src.core.collection import UnifiedCollector

    out_dir = tmp_path / "merged_out"
    cfg_path = tmp_path / "run_config.json"
    cfg_path.write_text(
        json.dumps({"query": "neural decoding", "output": str(out_dir), "limit": 10}),
        encoding="utf-8",
    )

    author_a_csv = tmp_path / "author_a.csv"
    pd.DataFrame([
        {"title": "Paper One", "doi": "10.1000/1", "year": 2023, "cite_count": 5},
        {"title": "Paper Two", "doi": "10.1000/2", "year": 2024, "cite_count": 3},
    ]).to_csv(author_a_csv, index=False)

    author_b_csv = tmp_path / "author_b_collected.csv"
    pd.DataFrame([
        {"title": "Paper One", "doi": "10.1000/1", "year": 2023, "cite_count": 8},
        {"title": "Paper Three", "doi": "10.1000/3", "year": 2024, "cite_count": 1},
    ]).to_csv(author_b_csv, index=False)

    mock_manager = MagicMock()
    mock_manager.data_orch.collector = UnifiedCollector(config={})
    mock_manager.data_orch.collect_data.return_value = str(author_b_csv)

    with patch("src.cli.PipelineManager", return_value=mock_manager), patch.object(
        sys,
        "argv",
        ["biblio-pipeline", "--config", str(cfg_path), "--merge-file", str(author_a_csv)],
    ):
        cli.main()

    mock_manager.data_orch.collect_data.assert_called_once_with(
        "neural decoding", limit=10, start_year=None, end_year=None
    )
    mock_manager.run.assert_called_once()
    merged_arg = mock_manager.run.call_args.args[0]
    assert merged_arg.endswith("merged_dataset.csv")

    merged_df = pd.read_csv(merged_arg)
    assert len(merged_df) == 3
    assert set(merged_df["DOI"]) == {"10.1000/1", "10.1000/2", "10.1000/3"}
    paper_one = merged_df.loc[merged_df["DOI"] == "10.1000/1"].iloc[0]
    assert int(paper_one["Cite Count"]) == 8


def test_collector_respects_sources_and_skip_sources_from_config():
    import pandas as pd
    from src.core.collection import UnifiedCollector

    called = []

    def make_stub(name):
        stub = MagicMock()
        def _fetch(query, limit=100, start_year=None, end_year=None):
            called.append(name)
            return pd.DataFrame([{"Title": f"From {name}", "DOI": f"10.1000/{name}"}])
        stub.fetch_papers.side_effect = _fetch
        return stub

    collector = UnifiedCollector(config={"sources": ["web_of_science", "scopus"], "skip_sources": ["scopus"]})
    collector.collectors = {k: make_stub(k) for k in ("openalex", "crossref", "scopus", "web_of_science")}

    df = collector.fetch_all("brain-computer interface", limit_per_source=10)
    assert called == ["web_of_science"]
    assert len(df) == 1
    assert df.iloc[0]["DOI"] == "10.1000/web_of_science"
    assert collector.last_source_status["web_of_science"] == {"status": "success", "count": 1}
    assert collector.last_source_status["scopus"] == {"status": "skipped", "count": 0}


def test_collector_records_missing_key_status_without_network_call(monkeypatch):
    import pandas as pd
    from src.core.collection import UnifiedCollector

    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)
    monkeypatch.delenv("WOS_API_KEY", raising=False)

    collector = UnifiedCollector(config={"sources": ["openalex", "scopus"]})
    oa_stub = MagicMock()
    oa_stub.fetch_papers.return_value = pd.DataFrame([{"Title": "OA Paper", "DOI": "10.1000/oa"}])
    collector.collectors["openalex"] = oa_stub
    collector.collectors["scopus"].api_key = None

    df = collector.fetch_all("bci", limit_per_source=5)
    assert len(df) == 1
    assert collector.last_source_status["openalex"] == {"status": "success", "count": 1}
    assert collector.last_source_status["scopus"]["status"] == "missing_key"
    assert collector.last_source_status["scopus"]["required_env"] == "SCOPUS_API_KEY"


def test_cli_fetch_missing_only_queries_missing_sources_and_merges(tmp_path, capsys):
    import pandas as pd
    from src.core.collection import UnifiedCollector

    prev_csv = tmp_path / "author_a_dataset.csv"
    pd.DataFrame([
        {"Title": "OA Paper", "DOI": "10.1000/oa", "Year": 2023, "Cite Count": 4},
    ]).to_csv(prev_csv, index=False)

    out_dir = tmp_path / "author_b_out"
    cfg_path = tmp_path / "run_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "query": "neural decoding",
                "output": str(out_dir),
                "limit": 10,
                "dataset_file": str(prev_csv),
                "source_status": {
                    "openalex": {"status": "success", "count": 1},
                    "scopus": {"status": "missing_key", "required_env": "SCOPUS_API_KEY", "count": 0},
                    "web_of_science": {"status": "missing_key", "required_env": "WOS_API_KEY", "count": 0},
                },
            }
        ),
        encoding="utf-8",
    )

    scopus_csv = tmp_path / "scopus_only.csv"
    pd.DataFrame([
        {"Title": "Scopus Paper", "DOI": "10.1000/scopus", "Year": 2024, "Cite Count": 7},
    ]).to_csv(scopus_csv, index=False)

    collector = UnifiedCollector(config={"scopus_api_key": "valid-scopus-key"})
    collector.collectors["scopus"].api_key = "valid-scopus-key"
    collector.collectors["web_of_science"].api_key = None
    collector.last_source_status = {"scopus": {"status": "success", "count": 1}}

    mock_manager = MagicMock()
    mock_manager.config = {}
    mock_manager.data_orch.config = {}
    mock_manager.data_orch.collector = collector
    mock_manager.data_orch.collect_data.return_value = str(scopus_csv)

    with patch("src.cli.PipelineManager", return_value=mock_manager), patch.object(
        sys,
        "argv",
        ["biblio-pipeline", "--config", str(cfg_path), "--fetch-missing"],
    ):
        cli.main()

    out = capsys.readouterr().out
    assert "SAVED RUN SOURCE SUMMARY" in out
    assert "WOS_API_KEY" in out
    assert collector.config["sources"] == ["scopus"]

    mock_manager.run.assert_called_once()
    merged_arg = mock_manager.run.call_args.args[0]
    merged_df = pd.read_csv(merged_arg)
    assert set(merged_df["DOI"]) == {"10.1000/oa", "10.1000/scopus"}

    updated_cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    assert updated_cfg["source_status"]["openalex"] == {"status": "success", "count": 1}
    assert updated_cfg["source_status"]["scopus"] == {"status": "success", "count": 1}


def test_fetch_zenodo_dataset_and_cli_integration(tmp_path):
    from src.core.ingestion import fetch_zenodo_dataset

    class _FakeResp:
        def __init__(self, data: bytes):
            self._data = data
        def read(self):
            return self._data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    api_payload = json.dumps({
        "files": [
            {"key": "notes.txt", "size": 10, "links": {"self": "https://zenodo.org/files/notes.txt"}},
            {"key": "corpus_323.csv", "size": 500, "links": {"self": "https://zenodo.org/files/corpus_323.csv"}},
        ]
    }).encode("utf-8")
    csv_payload = b"Title,DOI\nPaper A,10.1000/a\n"

    def _fake_urlopen(req, timeout=20):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        return _FakeResp(api_payload if "api/records" in url else csv_payload)

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        local_path = fetch_zenodo_dataset("10.5281/zenodo.24269215", dest_dir=str(tmp_path))

    assert local_path.endswith("corpus_323.csv")
    assert "Paper A" in open(local_path, encoding="utf-8").read()

    out_dir = tmp_path / "zenodo_out"
    mock_manager = MagicMock()
    with patch("src.core.ingestion.fetch_zenodo_dataset", return_value=local_path) as mock_fetch, patch(
        "src.cli.PipelineManager", return_value=mock_manager
    ), patch.object(
        sys, "argv", ["biblio-pipeline", "--zenodo", "10.5281/zenodo.24269215", "--output", str(out_dir)]
    ):
        cli.main()

    mock_fetch.assert_called_once_with("10.5281/zenodo.24269215")
    mock_manager.run.assert_called_once_with(local_path, refs_path=None)
