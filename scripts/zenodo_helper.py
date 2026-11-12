#!/usr/bin/env python3
"""
Zenodo Helper Script for OpenSciencePipe Replication Packaging & API Interaction
Reference: https://developers.zenodo.org/
"""

import os
import sys
import json
import zipfile
import argparse
from pathlib import Path
import urllib.request
import urllib.error

ZENODO_API_URL = "https://zenodo.org/api"
ZENODO_SANDBOX_URL = "https://sandbox.zenodo.org/api"

def get_token() -> str:
    token = os.environ.get("ZENODO_TOKEN") or os.environ.get("ZENODO_ACCESS_TOKEN")
    if not token:
        # Check secret-tool or file if available
        pass
    return token or ""

def list_depositions(token: str, sandbox: bool = False):
    base_url = ZENODO_SANDBOX_URL if sandbox else ZENODO_API_URL
    url = f"{base_url}/deposit/depositions"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f">>> Found {len(data)} depositions on Zenodo ({'Sandbox' if sandbox else 'Production'}):")
            for dep in data:
                dep_id = dep.get("id")
                title = dep.get("title") or dep.get("metadata", {}).get("title", "Untitled")
                doi = dep.get("doi") or dep.get("metadata", {}).get("doi", "Pending")
                state = dep.get("state", "draft")
                submitted = dep.get("submitted", False)
                print(f"    - ID: {dep_id} | State: {state} | Submitted: {submitted} | DOI: {doi} | Title: {title[:50]}")
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(e.read().decode())
        return None
    except Exception as e:
        print(f"Error querying Zenodo: {e}")
        return None

def build_replication_bundle(output_zip: str = "opensciencepipe_qss_replication_v1.0.0.zip"):
    print(f">>> Assembling OpenSciencePipe QSS replication bundle into: {output_zip}")
    repo_root = Path(__file__).resolve().parent.parent

    files_to_pack = []

    # 1. Benchmark definitions
    benchmarks_dir = repo_root / "data" / "benchmarks"
    if benchmarks_dir.exists():
        for f in benchmarks_dir.glob("*.json"):
            files_to_pack.append((f, f"data/benchmarks/{f.name}"))

    # 2. Evaluation & Baseline Scripts
    scripts_to_include = [
        "evaluate_thematic_validation.py",
        "evaluate_clustering_benchmarks.py",
        "run_head_to_head_baselines.py",
    ]
    for s in scripts_to_include:
        s_path = repo_root / "scripts" / s
        if s_path.exists():
            files_to_pack.append((s_path, f"scripts/{s}"))

    # 3. Tables
    tables_dir = repo_root / "manuscripts" / "paper4_opensciencepipe_landmark" / "tables"
    if tables_dir.exists():
        for t in tables_dir.glob("*.tex"):
            files_to_pack.append((t, f"tables/{t.name}"))

    # 4. License & Citation
    for meta_file in ["LICENSE", "CITATION.cff", "README.md"]:
        p = repo_root / meta_file
        if p.exists():
            files_to_pack.append((p, meta_file))

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, arc_name in files_to_pack:
            print(f"    + Adding {arc_name}")
            zf.write(file_path, arc_name)

    print(f">>> Successfully created {output_zip} ({os.path.getsize(output_zip)} bytes, {len(files_to_pack)} files)")
    return output_zip

def main():
    parser = argparse.ArgumentParser(description="Zenodo API & Replication Packaging Helper")
    parser.add_argument("--list", action="store_true", help="List depositions on Zenodo")
    parser.add_argument("--sandbox", action="store_true", help="Use Zenodo Sandbox API")
    parser.add_argument("--bundle", action="store_true", help="Build replication bundle ZIP")
    parser.add_argument("--output", default="opensciencepipe_qss_replication_v1.0.0.zip", help="Bundle ZIP output path")
    args = parser.parse_args()

    if args.bundle:
        build_replication_bundle(args.output)
        return

    if args.list:
        token = get_token()
        if not token:
            print("Error: ZENODO_TOKEN or ZENODO_ACCESS_TOKEN environment variable not set.")
            print("Create a token at https://zenodo.org/account/settings/applications/tokens/new/ (scopes: deposit:actions, deposit:write)")
            sys.exit(1)
        list_depositions(token, sandbox=args.sandbox)
        return

    parser.print_help()

if __name__ == "__main__":
    main()
