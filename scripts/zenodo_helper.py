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
    token = (
        os.environ.get("ZENODO_TOKEN")
        or os.environ.get("ZENODO_ACCESS_TOKEN")
        or os.environ.get("ZENODO_API")
    )
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

def build_replication_bundle(output_zip: str = "opensciencepipe_qss_replication_v1.1.1.zip"):
    print(f">>> Assembling OpenSciencePipe QSS replication bundle into: {output_zip}")
    repo_root = Path(__file__).resolve().parent.parent

    files_to_pack = []

    # 1. Benchmark definitions & frozen corpora
    benchmarks_dir = repo_root / "data" / "benchmarks"
    if benchmarks_dir.exists():
        for f in sorted(benchmarks_dir.glob("*.json")):
            files_to_pack.append((f, f"data/benchmarks/{f.name}"))

    data_dir = repo_root / "data"
    for f in sorted(data_dir.glob("collected_benchmark_*.csv")):
        files_to_pack.append((f, f"data/{f.name}"))
    b14_exact = data_dir / "collected_b14_exact_100.csv"
    if b14_exact.exists():
        files_to_pack.append((b14_exact, f"data/{b14_exact.name}"))

    # 2. Pipeline topic & network outputs for benchmark reproduction
    outputs_dir = repo_root / "outputs"
    for b_out in sorted(outputs_dir.glob("pipeline_results_benchmark_*")):
        for fname in ["topic_info.csv", "network_nodes.csv", "network_edges.csv"]:
            fp = b_out / fname
            if fp.exists():
                files_to_pack.append((fp, f"outputs/{b_out.name}/{fname}"))
    eeg_18k = outputs_dir / "pipeline_results_18k"
    for fname in ["network_nodes.csv", "network_edges.csv"]:
        fp = eeg_18k / fname
        if fp.exists():
            files_to_pack.append((fp, f"outputs/pipeline_results_18k/{fname}"))

    # 3. Evaluation & Baseline Scripts
    scripts_to_include = [
        "evaluate_thematic_validation.py",
        "evaluate_clustering_benchmarks.py",
        "run_head_to_head_baselines.py",
        "regenerate_table5.py",
        "regenerate_exact_corpus_parity.py",
        "evaluate_stability_and_disambiguation.py",
        "evaluate_igraph_b09.py",
        "evaluate_mcl_ablation.py",
        "evaluate_b09_outlier_audit.py",
        "generate_manuscript_figures.py",
        "extract_clusters_from_pdfs.py",
        "zenodo_helper.py",
    ]
    for s in scripts_to_include:
        s_path = repo_root / "scripts" / s
        if s_path.exists():
            files_to_pack.append((s_path, f"scripts/{s}"))

    # 4. Tables
    tables_dir = repo_root / "manuscripts" / "paper4_opensciencepipe_landmark" / "tables"
    if tables_dir.exists():
        for t in sorted(tables_dir.glob("*.tex")):
            files_to_pack.append((t, f"tables/{t.name}"))

    # 5. License & Citation
    for meta_file in ["LICENSE", "CITATION.cff", "README.md"]:
        p = repo_root / meta_file
        if p.exists():
            files_to_pack.append((p, meta_file))

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, arc_name in files_to_pack:
            zf.write(file_path, arc_name)

    print(f">>> Successfully created {output_zip} ({os.path.getsize(output_zip)} bytes, {len(files_to_pack)} files)")
    return output_zip


def publish_new_version(token: str, deposition_id: int, zip_path: str, version: str, publish: bool = False):
    import datetime
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Create new version draft
    req = urllib.request.Request(f"{ZENODO_API_URL}/deposit/depositions/{deposition_id}/actions/newversion", data=b"", headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        draft_meta = json.loads(resp.read().decode())
    draft_url = draft_meta["links"]["latest_draft"]
    draft_id = int(draft_url.rstrip("/").split("/")[-1])
    print(f">>> Created draft deposition ID: {draft_id}")

    # 2. Fetch draft details to get bucket URL and existing files
    req = urllib.request.Request(f"{ZENODO_API_URL}/deposit/depositions/{draft_id}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        draft = json.loads(resp.read().decode())
    bucket_url = draft["links"]["bucket"]

    # 3. Delete old files from draft
    for old_f in draft.get("files", []):
        fid = old_f["id"]
        dreq = urllib.request.Request(f"{ZENODO_API_URL}/deposit/depositions/{draft_id}/files/{fid}", headers={"Authorization": f"Bearer {token}"}, method="DELETE")
        urllib.request.urlopen(dreq).read()
        print(f">>> Removed old file: {old_f.get('filename')}")

    # 4. Upload new bundle via bucket PUT
    zip_name = os.path.basename(zip_path)
    with open(zip_path, "rb") as f:
        data = f.read()
    ureq = urllib.request.Request(
        f"{bucket_url}/{zip_name}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        method="PUT",
    )
    with urllib.request.urlopen(ureq) as resp:
        up = json.loads(resp.read().decode())
        print(f">>> Uploaded {zip_name} ({up.get('size')} bytes)")

    # 5. Update metadata version and date
    meta = draft.get("metadata", {})
    meta["version"] = version
    meta["publication_date"] = datetime.date.today().isoformat()
    preq = urllib.request.Request(
        f"{ZENODO_API_URL}/deposit/depositions/{draft_id}",
        data=json.dumps({"metadata": meta}).encode(),
        headers=headers,
        method="PUT",
    )
    with urllib.request.urlopen(preq) as resp:
        json.loads(resp.read().decode())

    if publish:
        pub_req = urllib.request.Request(f"{ZENODO_API_URL}/deposit/depositions/{draft_id}/actions/publish", data=b"", headers=headers, method="POST")
        with urllib.request.urlopen(pub_req) as resp:
            pub_data = json.loads(resp.read().decode())
        print(f">>> Published! New ID: {pub_data.get('id')} | DOI: {pub_data.get('doi')} | Concept DOI: {pub_data.get('conceptdoi')}")
        return pub_data
    return draft

def main():
    parser = argparse.ArgumentParser(description="Zenodo API & Replication Packaging Helper")
    parser.add_argument("--list", action="store_true", help="List depositions on Zenodo")
    parser.add_argument("--sandbox", action="store_true", help="Use Zenodo Sandbox API")
    parser.add_argument("--bundle", action="store_true", help="Build replication bundle ZIP")
    parser.add_argument("--output", default="opensciencepipe_qss_replication_v1.1.1.zip", help="Bundle ZIP output path")
    parser.add_argument("--new-version", type=int, default=0, help="Existing Zenodo deposition ID to create a new version from")
    parser.add_argument("--version", default="1.1.1", help="Version string for new Zenodo version")
    parser.add_argument("--publish", action="store_true", help="Publish the new Zenodo version immediately")
    args = parser.parse_args()

    if args.bundle:
        build_replication_bundle(args.output)
        if not args.new_version:
            return

    if args.new_version:
        token = get_token()
        if not token:
            import subprocess
            res = subprocess.run(["secret-tool", "lookup", "Title", "ZENODO_API"], capture_output=True, text=True)
            token = res.stdout.strip()
        if not token:
            print("Error: Zenodo token not found in env or KeePassXC.")
            sys.exit(1)
        if not os.path.exists(args.output):
            build_replication_bundle(args.output)
        publish_new_version(token, args.new_version, args.output, args.version, publish=args.publish)
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
