import os
import sys
import glob
import json
import subprocess
import pandas as pd
from typing import Dict, Any, List

from src.core.collection import UnifiedCollector

def run_podman_gpu_pipeline(input_csv: str, output_dir: str):
    """Executes the pipeline with GPU acceleration inside the Podman container."""
    os.makedirs(output_dir, exist_ok=True)
    # Check if podman with GPU is available
    cmd = [
        "podman", "run", "--rm",
        "--device", "nvidia.com/gpu=all",
        "-v", f"{os.getcwd()}:/app:z",
        "-w", "/app",
        "--entrypoint", "python",
        "biblio-pipeline",
        "-m", "src.pipeline",
        "--file", input_csv,
        "--output-dir", output_dir,
        "--skip-llm"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode == 0:
            print(f">>> [SUCCESS] Podman GPU Pipeline completed -> {output_dir}")
            return True
        else:
            print(f">>> [WARN] Podman GPU execution failed, attempting local fallback...\n{res.stderr[-300:]}")
    except Exception as e:
        print(f">>> [WARN] Podman invocation error ({e}), running locally...")

    # Fallback to local execution
    local_cmd = [
        sys.executable, "-m", "src.pipeline",
        "--file", input_csv,
        "--output-dir", output_dir,
        "--skip-llm"
    ]
    res_local = subprocess.run(local_cmd, capture_output=True, text=True)
    return res_local.returncode == 0

def process_benchmark(b_path: str, collector: UnifiedCollector) -> bool:
    b_name = os.path.splitext(os.path.basename(b_path))[0]
    with open(b_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("benchmark_title", b_name)
    query = data.get("search_query")
    year_range = data.get("year_range", [2010, 2024])
    start_year, end_year = year_range[0], year_range[1]

    os.makedirs("data", exist_ok=True)
    out_csv = os.path.join("data", f"collected_{b_name}.csv")
    results_dir = f"pipeline_results_{b_name}"

    print("\n" + "=" * 80)
    print(f">>> [BENCHMARK] {title}")
    print(f"    Query:      {query}")
    print(f"    Years:      {start_year} - {end_year}")
    print(f"    CSV:        {out_csv}")
    print(f"    Output:     {results_dir}")
    print("=" * 80)

    # 1. Fetch & Save incrementally
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) < 1000:
        print(f">>> Fetching publication records (OpenAlex + Crossref fallback)...")
        try:
            df = collector.fetch_all(
                query=query,
                start_year=start_year,
                end_year=end_year,
                limit_per_source=200,
                sources=["crossref", "openalex", "semantic_scholar"]
            )
            if not df.empty:
                df.to_csv(out_csv, index=False)
                print(f">>> [SAVED] {len(df)} records saved to {out_csv}")
            else:
                print(f">>> [WARN] 0 records returned.")
                return False
        except Exception as e:
            print(f">>> [ERROR] Fetch error: {e}")
            return False
    else:
        print(f">>> [CACHE] Found existing dataset: {out_csv}")

    # 2. Run GPU Pipeline
    has_results = (
        os.path.exists(os.path.join(results_dir, "yearly_growth.csv"))
        or os.path.exists(os.path.join(results_dir, "data", "yearly_growth.csv"))
        or os.path.exists(os.path.join(results_dir, "data", "publication_dataset.csv"))
        or os.path.exists(os.path.join(results_dir, "publication_dataset.csv"))
    )
    if not has_results:
        print(f">>> Running Podman GPU Pipeline -> {results_dir}")
        success = run_podman_gpu_pipeline(out_csv, results_dir)
        if not success:
            print(f">>> [WARN] Pipeline processing had warnings for {b_name}")
    else:
        print(f">>> [CACHE] Found existing pipeline results in {results_dir}")

    # 3. Save progress incrementally to LaTeX matrix
    print(">>> Updating validation matrices incrementally...")
    try:
        from scripts.auto_validate_benchmarks import run_automated_validation
        run_automated_validation()
    except Exception as e:
        print(f">>> [WARN] Validation matrix update warning: {e}")
    try:
        from scripts.run_all_benchmarks import run_suite
        run_suite()
    except Exception as e:
        print(f">>> [WARN] run_all_benchmarks suite update warning: {e}")
    return True

def main():
    benchmarks_dir = "data/benchmarks"
    benchmark_files = sorted(glob.glob(os.path.join(benchmarks_dir, "*.json")))
    benchmark_files = [f for f in benchmark_files if not f.endswith("benchmark_template.json")]
    total = len(benchmark_files)

    progress_file = "data/benchmark_milestones_progress.json"
    milestones = {}
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r") as pf:
                milestones = json.load(pf)
        except Exception:
            milestones = {}

    collector = UnifiedCollector(config={"openalex_email": "john.researcher@academic.org"})

    print("=" * 85)
    print(f">>> STARTING MULTI-DOMAIN BENCHMARK SUITE ({total} Benchmarks Total)")
    print("=" * 85)

    for idx, b_path in enumerate(benchmark_files, start=1):
        b_name = os.path.basename(b_path)
        pct = (idx / total) * 100.0
        bar_len = 20
        filled = int(bar_len * idx // total)
        bar = "=" * filled + "-" * (bar_len - filled)
        
        print(f"\n[{idx}/{total}] [{bar}] {pct:.1f}% -> Processing: {b_name}")

        status = "Failed"
        try:
            success = process_benchmark(b_path, collector)
            status = "Completed" if success else "Warnings/Incomplete"
        except Exception as e:
            print(f">>> [ERROR] Unexpected exception in {b_path}: {e}")
            status = f"Error: {e}"

        milestones[b_name] = {
            "index": idx,
            "total": total,
            "status": status,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        with open(progress_file, "w", encoding="utf-8") as pf:
            json.dump(milestones, pf, indent=2)
        print(f">>> [MILESTONE SAVED] Progress saved to {progress_file}")

    print("\n" + "=" * 90)
    print(">>> [DONE] Full Multi-Benchmark Suite Complete.")
    print(f">>> All milestones saved to: {progress_file}")
    print("=" * 90)

if __name__ == "__main__":
    main()
