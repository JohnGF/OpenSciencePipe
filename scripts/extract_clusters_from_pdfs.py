#!/usr/bin/env python3
"""
Blind Cluster Extraction Helper for Benchmark PDFs (M1).
Scans PDFs in a target directory (default: data/benchmark_pdfs/) using PyMuPDF
and extracts verbatim candidate cluster definitions, table/figure captions, and
page numbers via regex so human extractors can populate data/benchmarks/*.json
without inspecting BERTopic outputs.

Usage:
    uv run python scripts/extract_clusters_from_pdfs.py --pdf-dir data/benchmark_pdfs
"""

import os
import re
import glob
import argparse
import pymupdf

CLUSTER_PATTERNS = [
    re.compile(r"(?:Cluster\s*[#0-9A-Za-z][^\n]{0,160})", re.IGNORECASE),
    re.compile(r"(?:(?:Red|Green|Blue|Yellow|Purple|Orange|Cyan)\s+cluster[^\n]{0,160})", re.IGNORECASE),
    re.compile(r"(?:Table\s+\d+[^\n]{0,160}(?:cluster|theme|keyword|co-occurrence)[^\n]{0,120})", re.IGNORECASE),
    re.compile(r"(?:Fig(?:ure|\.)?\s*\d+[^\n]{0,160}(?:cluster|co-occurrence|network|thematic)[^\n]{0,120})", re.IGNORECASE),
]


def extract_candidates_from_pdf(pdf_path: str, context_chars: int = 250) -> list:
    doc = pymupdf.open(pdf_path)
    hits = []
    seen_snippets = set()
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text("text")
        for pat in CLUSTER_PATTERNS:
            for m in pat.finditer(text):
                start = max(0, m.start() - 60)
                end = min(len(text), m.end() + context_chars)
                snippet = " ".join(text[start:end].split())
                key = (page_idx + 1, snippet[:80])
                if key not in seen_snippets:
                    seen_snippets.add(key)
                    hits.append({
                        "page": page_idx + 1,
                        "match": m.group(0).strip(),
                        "snippet": snippet,
                    })
    return hits


def main():
    parser = argparse.ArgumentParser(description="Extract verbatim cluster candidates from benchmark PDFs.")
    parser.add_argument("--pdf-dir", default="data/benchmark_pdfs", help="Directory containing benchmark PDFs")
    parser.add_argument("--out", default=".scratch/pdf_cluster_candidates.md", help="Output Markdown report")
    args = parser.parse_args()

    os.makedirs(args.pdf_dir, exist_ok=True)
    pdfs = sorted(glob.glob(os.path.join(args.pdf_dir, "*.pdf")))
    if not pdfs:
        print(f"No PDFs found in {args.pdf_dir}/. Place benchmark PDFs there (e.g., B03.pdf, B08.pdf) and re-run.")
        return

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    lines = ["# Extracted Cluster Candidates from Benchmark PDFs\n"]
    for pdf_p in pdfs:
        fname = os.path.basename(pdf_p)
        hits = extract_candidates_from_pdf(pdf_p)
        lines.append(f"## {fname} ({len(hits)} candidate matches)\n")
        for h in hits:
            lines.append(f"- **Page {h['page']}** (`{h['match']}`):\n  > {h['snippet']}\n")
        lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Scanned {len(pdfs)} PDFs and wrote {args.out}")


if __name__ == "__main__":
    main()
