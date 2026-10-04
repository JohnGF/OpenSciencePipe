#!/usr/bin/env python3
import os
import re
import json
import argparse
import httpx
from typing import List, Dict, Any, Optional

from scripts.download_and_verify_benchmark import download_oa_pdf

def search_top_candidates(
    tool_type: str = "vosviewer",
    years: List[int] = [2021, 2022, 2023, 2024],
    per_year: int = 2,
    email: str = "john@example.com"
) -> List[Dict[str, Any]]:
    """
    Finds the most-cited papers per year that explicitly used VOSviewer/CiteSpace or PRISMA Meta-Analysis.
    """
    candidates = []
    headers = {"User-Agent": f"BibliometricDiscovery/1.0 (mailto:{email})"}
    base_url = "https://api.openalex.org/works"

    if tool_type.lower() == "vosviewer":
        query_filter = 'default.search:"VOSviewer",type:article'
    elif tool_type.lower() == "citespace":
        query_filter = 'default.search:"CiteSpace",type:article'
    elif tool_type.lower() == "bibliometrix":
        query_filter = 'default.search:"Bibliometrix",type:article'
    elif tool_type.lower() == "rayyan":
        query_filter = 'default.search:"Rayyan",title.search:"systematic review",type:article'
    elif tool_type.lower() == "asreview":
        query_filter = 'default.search:"ASReview",type:article'
    elif tool_type.lower() == "distillersr":
        query_filter = 'default.search:"DistillerSR",title.search:"systematic review",type:article'
    elif tool_type.lower() in ["manual_slr", "manual"]:
        query_filter = 'default.search:"two independent reviewers",title.search:"systematic review",type:article'
    elif tool_type.lower() == "meta_analysis":
        query_filter = 'title.search:"systematic review and meta-analysis",default.search:"PRISMA",type:article'
    else:
        query_filter = f'default.search:"{tool_type}",type:article'

    for yr in years:
        params = {
            "filter": f"from_publication_date:{yr}-01-01,to_publication_date:{yr}-12-31,has_doi:true,is_oa:true,{query_filter}",
            "sort": "cited_by_count:desc",
            "per_page": per_year * 2,
            "select": "id,doi,title,publication_year,cited_by_count,primary_location,authorships"
        }
        try:
            resp = httpx.get(base_url, params=params, headers=headers, timeout=15.0)
            if resp.status_code != 200:
                print(f"[WARN] OpenAlex HTTP {resp.status_code} for year {yr}")
                continue
            
            results = resp.json().get("results", [])
            valid_for_year = 0
            for item in results:
                doi = item.get("doi")
                if not doi:
                    continue
                clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
                title = item.get("title", "")
                cites = item.get("cited_by_count", 0)
                authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]
                
                candidates.append({
                    "tool": tool_type,
                    "year": yr,
                    "doi": clean_doi,
                    "title": title,
                    "citations": cites,
                    "authors": authors[:5],
                    "pdf_url": (item.get("primary_location") or {}).get("pdf_url")
                })
                valid_for_year += 1
                if valid_for_year >= per_year:
                    break
        except Exception as e:
            print(f"[ERROR] Query failed for year {yr}: {e}")

    return candidates

def main():
    parser = argparse.ArgumentParser(description="Find top cited benchmark candidates by tool and year.")
    parser.add_argument("--tool", default="vosviewer", help="Tool or methodology to search for (e.g. vosviewer, citespace, bibliometrix, revman, meta_analysis)")
    parser.add_argument("--years", nargs="+", type=int, default=[2021, 2022, 2023, 2024])
    parser.add_argument("--per-year", type=int, default=2)
    parser.add_argument("--download-pdf", action="store_true", help="Download open-access PDF automatically")
    parser.add_argument("--output-dir", default="benchmark_references")
    parser.add_argument("--email", default="john@example.com")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"\nSearching top-cited OA candidates for tool: '{args.tool}' in years {args.years}...")
    candidates = search_top_candidates(args.tool, args.years, args.per_year, email=args.email)

    print(f"\nFound {len(candidates)} candidate benchmark papers:\n")
    for i, c in enumerate(candidates, 1):
        print(f"{i}. [{c['year']}] ({c['citations']} citations) {c['title']}")
        print(f"   DOI: {c['doi']}")
        print(f"   Authors: {', '.join(c['authors'])}")

        if args.download_pdf:
            safe_name = c['doi'].replace('/', '_').replace('.', '_') + ".pdf"
            pdf_path = os.path.join(args.output_dir, safe_name)
            if not os.path.exists(pdf_path):
                print(f"   --> Downloading OA PDF to {pdf_path}...")
                import asyncio
                res = asyncio.run(download_oa_pdf(c['doi'], pdf_path, email=args.email))
                if res:
                    print(f"   --> Saved PDF: {res}")
                else:
                    print(f"   --> Could not fetch direct PDF (may require manual download).")
            else:
                print(f"   --> PDF already present: {pdf_path}")
        print()

if __name__ == "__main__":
    main()
