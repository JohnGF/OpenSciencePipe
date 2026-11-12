import logging
import argparse
import os
import sys

from src.orchestrators.pipeline_manager import PipelineManager

# Path to cloud-unlock RAM-disk credentials (KeePassXC-backed tmpfs)
_CLOUD_UNLOCK_PATH = "/run/user/1000/credentials/api_keys.env"

def _load_dotenv_if_exists(dotenv_path: str = ".env"):
    """Load credentials from .env first, then optionally fall back to cloud-unlock
    RAM-disk credentials (tmpfs). This supports two workflows:
      1. Standard: place keys in a local ``.env`` file (copied from ``.env.example``)
      2. Secure: unlock KeePassXC database via ``cloud-unlock`` which exports keys
         to a tmpfs file at ``/run/user/1000/credentials/api_keys.env``
    Keys already present in the environment (``os.environ``) are never overwritten.
    """
    # Priority 1: standard local .env file
    for target_path in (dotenv_path, _CLOUD_UNLOCK_PATH):
        if target_path and os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line and "\t" not in line and " " not in line:
                            continue
                        if "=" in line:
                            # Standard .env format: KEY=value
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
                        elif "\t" in line:
                            # cloud-unlock fish format: set -gx KEY "value"
                            parts = line.split(None, 2)
                            if len(parts) >= 3 and parts[1].startswith("set") and parts[1].endswith("gx"):
                                k = parts[1][1:]
                            if line.startswith("set -gx "):
                                line = line[len("set -gx "):]
                                k, v = line.split(None, 1)
                                k, v = k.strip(), v.strip().strip('"')
                                if k and k not in os.environ:
                                    os.environ[k] = v
            except Exception:
                pass

def main():
    _load_dotenv_if_exists()
    parser = argparse.ArgumentParser(
        description="Bibliometric Research & PRISMA Systematic Review Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--file", type=str, help="Path to local CSV/Parquet file")
    parser.add_argument("--refs-file", type=str, help="Path to external references CSV file")
    parser.add_argument("--query", type=str, help="Search query for autonomous collection")
    parser.add_argument("--query-file", type=str, help="Path to text file containing search query")
    parser.add_argument("--limit", type=int, default=100, help="Limit per source for collection")
    parser.add_argument("--start-year", type=int, help="Start year for collection")
    parser.add_argument("--end-year", type=int, help="End year for collection")
    parser.add_argument("--output", "--output-dir", dest="output", type=str, default="outputs/pipeline_results", help="Output directory")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM screening stage (default if not screening)")
    parser.add_argument("--openalex-email", type=str, help="Email for OpenAlex polite pool")
    parser.add_argument("--ss-api-key", type=str, help="API Key for Semantic Scholar")
    parser.add_argument("--crossref-email", type=str, help="Email for Crossref User-Agent")
    parser.add_argument("--pubmed-api-key", type=str, help="API Key for PubMed (optional)")
    parser.add_argument("--scopus-api-key", type=str, help="API Key for Elsevier Scopus")
    parser.add_argument("--scopus-inst-token", type=str, help="Institutional Token for Scopus (optional)")
    parser.add_argument("--wos-api-key", type=str, help="API Key for Web of Science")

    # Paper Screening & Systematic Review Filtering Options
    parser.add_argument("--include-regex", "--include-pattern", type=str, help="Grep/regex pattern(s) that MUST be present for study inclusion (e.g. 'algorithm|circuit|qubit')")
    parser.add_argument("--exclude-regex", "--exclude-pattern", type=str, help="Grep/regex pattern(s) triggering study exclusion (e.g. 'review|survey|editorial|rat|mice')")
    parser.add_argument("--criteria-file", type=str, help="Path to JSON or text file specifying systematic inclusion/exclusion criteria")
    parser.add_argument("--target-prompt", type=str, help="Target semantic prompt for embedding/LLM screening (defaults to active search query)")
    parser.add_argument("--screen-embeddings", action="store_true", help="Enable Option 1: Embedding semantic relevance filter")
    parser.add_argument("--embedding-threshold", type=float, default=0.35, help="Similarity threshold for embedding filter")
    parser.add_argument("--screen-llm", action="store_true", help="Enable Option 2: LLM zero-shot classification")
    parser.add_argument("--llm-model", type=str, default="llama3.2:3b", help="Model name for Ollama LLM screening")
    parser.add_argument("--include-preprints", action="store_true", help="Include preprints from arXiv and bioRxiv")

    # Modular Stage Control Options
    parser.add_argument("--top-per-community", type=int, default=1, help="Top N representative author leaders per community")
    parser.add_argument("--min-publications", type=int, default=1, help="Minimum publications threshold for network node inclusion")
    parser.add_argument("--stages", type=str, help="Comma-separated list of stages to run (options: growth,country,cagr,nlp,network,percolation)")
    parser.add_argument("--skip-nlp", action="store_true", help="Skip BERTopic modeling stage")
    parser.add_argument("--skip-network", action="store_true", help="Skip co-authorship network stage")
    parser.add_argument("--skip-cagr", action="store_true", help="Skip keyword CAGR stage")
    parser.add_argument("--skip-country", action="store_true", help="Skip country evolution stage")
    parser.add_argument("--skip-percolation", action="store_true", help="Skip percolation analysis stage")


    # Key Management & Onboarding
    parser.add_argument("--setup-keys", action="store_true", help="Launch interactive API keys setup wizard")
    parser.add_argument("--check-keys", action="store_true", help="Diagnose and validate configured API credentials")

    # Project Orchestration Options
    parser.add_argument("--project-dir", type=str, help="Path to project directory for end-to-end orchestration")
    parser.add_argument("--skip-collection", action="store_true", help="Skip data collection when running a project")

    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive graph parameter editor REPL session")

    # Pipeline Execution Mode
    parser.add_argument("--mode", type=str, choices=["biblio", "systematic", "meta", "all"], default="biblio", help="Execution mode: 'biblio' (bibliometric), 'systematic' (PRISMA review), 'meta' (quantitative meta-analysis), or 'all'")

    # Meta-Analysis Options
    parser.add_argument("--meta-analysis", action="store_true", help="Run full-text PDF parsing, extraction, and meta-analysis stats")
    parser.add_argument("--picos-config", type=str, help="Path to PICOS configuration JSON file")

    # Bibliographic Validation & Hallucination Auditing
    parser.add_argument("--validate-bib", type=str, help="Validate citations file (.bib, .csv, .json, .tex, .md) against Crossref/OpenAlex to flag hallucinations")

    # Institutional Intelligence & Collaboration Options
    parser.add_argument("--institution", type=str, help="Target institution for bibliometrics (e.g. 'Universidade de Lisboa')")
    parser.add_argument("--faculty", type=str, help="Sub-unit or faculty name (e.g. 'Faculdade de Ciências')")
    parser.add_argument("--year", type=int, default=2023, help="Publication year for institutional analysis")

    args = parser.parse_args()

    if args.setup_keys:
        from scripts.setup_keys import run_interactive_wizard
        run_interactive_wizard()
        return

    if args.check_keys:
        from scripts.validate_keys import validate_all_keys
        success, _ = validate_all_keys(verbose=True)
        sys.exit(0 if success else 1)

    if args.validate_bib:
        from src.core.biblio_validator import BiblioValidator
        validator = BiblioValidator(email=args.openalex_email or args.crossref_email)
        out_report = os.path.join(args.output, "biblio_validation_report.csv") if args.output else "biblio_validation_report.csv"
        df_res, metrics = validator.validate_file(args.validate_bib, output_path=out_report)
        print("\n" + "=" * 70)
        print("BIBLIOGRAPHIC VALIDATION & HALLUCINATION AUDIT SUMMARY")
        print("=" * 70)
        print(f"Total Entries Checked    : {metrics.get('total_checked', 0)}")
        print(f"Verified Authentic       : {metrics.get('verified', 0)}")
        print(f"Flagged for Human Review : {metrics.get('flagged_for_human_review', 0)}")
        print(f"Suspected Hallucinations : {metrics.get('suspected_hallucinations', 0)}")
        print(f"Verification Success Rate: {metrics.get('verification_rate_pct', 0.0)}%")
        print(f"Audit Report Saved To    : {out_report}")
        print("=" * 70)
        return

    if args.interactive:
        from scripts.interactive_viz import InteractiveVizSession
        session = InteractiveVizSession(output_dir=args.output)
        session.run_menu()
        return

    if args.institution:
        from scripts.institution_country_collab import find_institution_id, get_country_collaborations
        import pandas as pd
        inst_id = None
        inst_name = args.institution
        inst_info = find_institution_id(args.institution)
        if inst_info:
            inst_id = inst_info["id"]
            inst_name = inst_info["display_name"]
        
        target_desc = f"{args.faculty} - {inst_name}" if args.faculty else inst_name
        print(f"\nAnalyzing bibliometrics for: {target_desc} (Year: {args.year})")
        res = get_country_collaborations(
            institution_id=inst_id,
            faculty_affiliation=args.faculty,
            year=args.year,
            top_n=20
        )
        total_works = res["total_publications"]
        intl_works = res.get("international_publications", 0)
        intl_rate = res.get("international_rate", 0.0)
        print(f"Total publications: {total_works}")
        print(f"International co-authored publications: {intl_works} ({intl_rate}%)\n")
        if total_works > 0:
            print("Top Collaborating Countries:")
            print(pd.DataFrame(res["countries"]).to_string(index=False))
            print("\nTop Collaborating Institutions:")
            print(pd.DataFrame(res["institutions"]).to_string(index=False))
        return

    if (args.query or args.query_file) and not os.environ.get("OPENALEX_EMAIL") and not os.path.exists(".env"):
        print("[INFO] Running in public rate-limited mode. For higher throughput, configure polite access with: python scripts/setup_keys.py")

    active_query = args.query
    if args.query_file and os.path.exists(args.query_file):
        with open(args.query_file, "r", encoding="utf-8") as qf:
            lines = [l.strip() for l in qf if l.strip() and not l.strip().startswith("#")]
            active_query = " ".join(lines)

    config = {}
    config["mode"] = args.mode
    if active_query: config["query"] = active_query
    if args.openalex_email: config["openalex_email"] = args.openalex_email
    if args.ss_api_key: config["ss_api_key"] = args.ss_api_key
    if args.crossref_email: config["crossref_email"] = args.crossref_email
    if args.pubmed_api_key: config["pubmed_api_key"] = args.pubmed_api_key
    if args.scopus_api_key: config["scopus_api_key"] = args.scopus_api_key
    if args.scopus_inst_token: config["scopus_inst_token"] = args.scopus_inst_token
    if args.wos_api_key: config["wos_api_key"] = args.wos_api_key

    config["include_regex"] = args.include_regex
    config["exclude_regex"] = args.exclude_regex
    config["criteria_file"] = args.criteria_file
    config["target_prompt"] = args.target_prompt
    config["screen_embeddings"] = args.screen_embeddings
    config["embedding_threshold"] = args.embedding_threshold
    config["screen_llm"] = args.screen_llm
    config["llm_model"] = args.llm_model
    config["include_preprints"] = args.include_preprints

    if args.stages:
        config["stages"] = [s.strip().lower() for s in args.stages.split(",")]
    config["top_per_community"] = args.top_per_community
    config["min_publications"] = args.min_publications
    config["skip_nlp"] = args.skip_nlp
    config["skip_network"] = args.skip_network
    config["skip_cagr"] = args.skip_cagr
    config["skip_country"] = args.skip_country
    config["skip_percolation"] = args.skip_percolation
    config["meta_analysis"] = args.meta_analysis
    config["picos_config"] = args.picos_config


    manager = PipelineManager(output_dir=args.output, config=config)

    if args.project_dir:
        logger = logging.getLogger("project_orchestrator")
        project_dir = args.project_dir
        data_dir = os.path.join(project_dir, "data")
        results_dir = os.path.join(project_dir, "results")
        query_file = os.path.join(data_dir, "query.txt")
        dataset_file = os.path.join(data_dir, "collected_papers.csv")

        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(results_dir, exist_ok=True)

        # Redirect manager output
        manager.output_dir = results_dir
        manager.analysis_orch.output_dir = results_dir

        if not args.skip_collection:
            if not os.path.exists(query_file):
                logger.info(f"Query file not found at {query_file}. Creating an empty one.")
                with open(query_file, "w", encoding="utf-8") as f:
                    f.write("brain-computer interface\n")
                logger.warning(f"Created a default query file at {query_file}. Please update it with your desired query and re-run.")
                return

            logger.info("=== PHASE 1: DATA COLLECTION ===")
            with open(query_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
                project_query = " ".join(lines)

            logger.info(f"Fetching data for project query: {project_query}")

            # Use unified collector manually to enforce the exact project path
            from src.core.collection import UnifiedCollector
            collector = UnifiedCollector(config=config)
            df_pd = collector.fetch_all(
                query=project_query,
                limit_per_source=args.limit,
                start_year=args.start_year,
                end_year=args.end_year
            )
            df_pd = collector.deduplicate_dataframe(df_pd)
            df_pd.to_csv(dataset_file, index=False)
            logger.info(f"Data saved to {dataset_file}")

        if not os.path.exists(dataset_file):
            logger.error(f"Cannot proceed: {dataset_file} not found.")
            return

        logger.info("=== PHASE 2: PIPELINE ANALYSIS ===")
        manager.run(dataset_file, refs_path=args.refs_file)

        logger.info("=== PROJECT EXECUTION COMPLETE ===")
        return

    if active_query:

        manager.run_with_query(active_query, limit=args.limit, start_year=args.start_year, end_year=args.end_year)
    elif args.file:
        manager.run(args.file, refs_path=args.refs_file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
