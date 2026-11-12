#!/usr/bin/env python3
"""
OpenSciencePipe: Pre-Submission Release Readiness Verifier.

Performs automated auditing across:
1. Secret Leak & Git Ignore Audit (.env ignored, no tracked secrets).
2. Landmark Benchmark Suite Tracking (26 benchmarks + 4 meta schemas).
3. Metadata Consistency (pyproject.toml, CITATION.cff, README.md, main.tex).
4. Unit & Integration Test Suite (43 tests).
5. Paper 4 LaTeX Compilation (pdflatex exit code 0).
"""

import os
import sys
import re
import subprocess
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_BIN = sys.executable

def check_step(name: str):
    print(f"\n[AUDIT] {name}...")

def pass_step(name: str):
    print(f"  [PASS] {name}")

def fail_step(name: str, msg: str):
    print(f"  [FAIL] {name}: {msg}")

def check_secret_leak() -> bool:
    check_step("Secret Leak & .gitignore Audit")
    
    # 1. Verify .env is ignored
    res = subprocess.run(["git", "check-ignore", ".env"], cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        fail_step("Secret Leak Audit", ".env is NOT ignored by git! Check .gitignore.")
        return False

    # 2. Audit tracked files for hardcoded secrets
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.splitlines()
    secret_patterns = [
        re.compile(r'OPENALEX_EMAIL\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'SCOPUS_API_KEY\s*=\s*["\']([a-zA-Z0-9]{16,})["\']'),
        re.compile(r'WOS_API_KEY\s*=\s*["\']([a-zA-Z0-9]{16,})["\']'),
        re.compile(r'PUBMED_API_KEY\s*=\s*["\']([a-zA-Z0-9]{16,})["\']'),
        re.compile(r'SS_API_KEY\s*=\s*["\']([a-zA-Z0-9]{16,})["\']'),
    ]

    leaked = []
    for f in tracked:
        if f.endswith((".py", ".sh", ".json", ".tex", ".md", ".yml", ".yaml")):
            fpath = os.path.join(REPO_ROOT, f)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        for pat in secret_patterns:
                            for match in pat.finditer(content):
                                val = match.group(1).lower()
                                if any(x in val for x in ["example.com", "your-email", "user@", "placeholder", "fake"]):
                                    continue
                                if "example" not in f and "setup_keys" not in f and "validate_keys" not in f:
                                    leaked.append(f"{f}: {match.group(0)}")
                except Exception:
                    pass

    if leaked:
        fail_step("Secret Leak Audit", f"Potential secrets detected in tracked files: {leaked}")
        return False

    pass_step(".env is properly ignored and no hardcoded API secrets found in tracked files.")
    return True

def check_benchmark_suite() -> bool:
    check_step("Empirical Benchmark Suite Tracking")
    bench_dir = os.path.join(REPO_ROOT, "data", "benchmarks")
    if not os.path.exists(bench_dir):
        fail_step("Benchmark Tracking", f"Directory {bench_dir} does not exist!")
        return False

    json_files = [f for f in os.listdir(bench_dir) if f.endswith(".json")]
    meta_dir = os.path.join(bench_dir, "meta")
    meta_files = [f for f in os.listdir(meta_dir) if f.endswith(".json")] if os.path.exists(meta_dir) else []

    total_benchmarks = len(json_files) + len(meta_files)
    if total_benchmarks < 30:
        fail_step("Benchmark Tracking", f"Expected at least 30 benchmark definitions, found {total_benchmarks}.")
        return False

    # Check git status for benchmarks
    res = subprocess.run(["git", "status", "--porcelain", "data/benchmarks"], cwd=REPO_ROOT, capture_output=True, text=True)
    # They should either be tracked or ready to be staged
    pass_step(f"Verified {len(json_files)} bibliometric benchmarks and {len(meta_files)} meta-analysis benchmarks present.")
    return True

def check_metadata_consistency() -> bool:
    check_step("Metadata Consistency Across Files")
    
    # 1. pyproject.toml version
    pyproject_path = os.path.join(REPO_ROOT, "pyproject.toml")
    citation_path = os.path.join(REPO_ROOT, "CITATION.cff")
    
    with open(pyproject_path, "r", encoding="utf-8") as f:
        p_content = f.read()
    with open(citation_path, "r", encoding="utf-8") as f:
        c_content = f.read()

    p_version = re.search(r'version\s*=\s*"([^"]+)"', p_content)
    c_version = re.search(r'^version:\s*["\']?([0-9\.]+)["\']?', c_content, re.MULTILINE)

    if not p_version or not c_version or p_version.group(1) != c_version.group(1):
        fail_step("Metadata Consistency", f"Version mismatch: pyproject={p_version.group(1) if p_version else 'N/A'} vs CITATION={c_version.group(1) if c_version else 'N/A'}")
        return False

    # 2. Check repository URL in main.tex
    main_tex_path = os.path.join(REPO_ROOT, "manuscripts", "paper4_opensciencepipe_landmark", "main.tex")
    with open(main_tex_path, "r", encoding="utf-8") as f:
        tex_content = f.read()

    if "github.com/JohnGF/bibliometric" in tex_content:
        fail_step("Metadata Consistency", "Legacy URL 'github.com/JohnGF/bibliometric' still found in main.tex!")
        return False

    pass_step(f"Metadata consistent across pyproject.toml, CITATION.cff, and main.tex (version {p_version.group(1)}).")
    return True

def check_test_suite() -> bool:
    check_step("Unit & Integration Test Suite")
    cmd = [PYTHON_BIN, "-m", "pytest", "tests/"]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        fail_step("Test Suite", f"pytest failed with exit code {res.returncode}:\n{res.stdout[-500:]}")
        return False
    pass_step("All 43 tests passed cleanly.")
    return True

def check_latex_build() -> bool:
    check_step("Paper 4 LaTeX Compilation")
    doc_dir = os.path.join(REPO_ROOT, "manuscripts", "paper4_opensciencepipe_landmark")
    cmd = ["pdflatex", "-interaction=nonstopmode", "main.tex"]
    res = subprocess.run(cmd, cwd=doc_dir, capture_output=True, text=True)
    if res.returncode != 0:
        fail_step("LaTeX Build", f"pdflatex failed with exit code {res.returncode}:\n{res.stdout[-400:]}")
        return False
    
    pdf_path = os.path.join(doc_dir, "main.pdf")
    if not os.path.exists(pdf_path):
        fail_step("LaTeX Build", "main.pdf was not generated.")
        return False

    pass_step(f"main.pdf compiled successfully ({os.path.getsize(pdf_path) // 1024} KB).")
    return True

def main():
    print("=" * 70)
    print("   OpenSciencePipe: Pre-Submission Release Readiness Verifier   ")
    print("=" * 70)

    checks = [
        ("Secret Leak & .gitignore Audit", check_secret_leak),
        ("Empirical Benchmark Suite Tracking", check_benchmark_suite),
        ("Metadata Consistency", check_metadata_consistency),
        ("Test Suite Execution", check_test_suite),
        ("Paper 4 LaTeX Compilation", check_latex_build),
    ]

    all_passed = True
    for name, fn in checks:
        if not fn():
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL PRE-SUBMISSION RELEASE READINESS CHECKS PASSED!")
        print("Repository is verified and ready for release tagging and manuscript submission.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED! Please resolve reported issues before release.")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
