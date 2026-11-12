#!/usr/bin/env python3
"""
Coverage audit: is OpenAlex missing FCUL papers that other indexes have?

Builds a DOI-keyed set from OpenAlex (institutional-ID query, the existing
FCUL methodology) and compares it against DOIs returned by Scopus, IEEE,
PubMed, Crossref, ACM and Semantic Scholar using the same FCUL search terms.

Reports:
  - overlap per source (DOIs in both)
  - OpenAlex-only (potential gaps in the other sources)
  - source-only (potential gaps in OpenAlex)  <-- the answer to the question
  - write the candidate misses to CSV for manual verification

Usage:
    python scripts/audit_fcul_coverage.py --years 2023 2024 2025
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import httpx

_CLOUD_UNLOCK = "/run/user/1000/credentials/api_keys.env"
OPENALEX_WORKS = "https://api.openalex.org/works"
FCUL_OPENALEX_ORG = "I141596103"

# Same affiliation probe set used by the existing FCUL reports
FCUL_TERMS = [
    "Faculty of Sciences",
    "Faculty of Science",
    "Faculdade de Ciências",
    "FCUL",
    "Instituto Dom Luiz",
    "LASIGE",
    "Ce3C",
    "BioISI",
    "Centro de Física Teórica e Computacional",
    "Instituto de Astrofísica e Ciências do Espaço",
    "Centro de Química Estrutural",
    "MARE",
]

# Broader free-text terms for the non-OpenAlex sources (no institution ID available)
BROAD_TERMS = [
    "Faculdade de Ciencias Universidade de Lisboa",
    "Faculty of Sciences University of Lisbon",
    "Instituto Dom Luiz",
    "LASIGE",
    "Ce3C Centro de Ecologia",
    "BioISI",
    "Centro de Fisica Teorica e Computacional",
    "Instituto de Astrofisica e Ciencias do Espaco",
    "Centro de Quimica Estrutural",
    "MARE Marine Environmental Sciences Lisbon",
    "Laboratorio de Instrumentacao e Fisica Experimental de Particulas",
]


def load_credentials():
    if not os.path.exists(_CLOUD_UNLOCK):
        return
    with open(_CLOUD_UNLOCK, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("set -gx "):
                continue
            body = line[len("set -gx "):]
            try:
                k, v = body.split(None, 1)
            except ValueError:
                continue
            k = k.strip()
            v = v.strip().strip('"')
            if k and k not in os.environ:
                os.environ[k] = v


def norm_doi(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if text in ("", "nan", "none"):
        return ""
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = text.replace("doi:", "").strip()
    return text if text.startswith("10.") else ""


def fetch_openalex_dois(years, limit=None):
    """FCUL papers via the OpenAlex institution ID (the existing methodology)."""
    email = os.environ.get("OPENALEX_EMAIL", "scholar@opensciencepipe.org")
    headers = {"User-Agent": f"OpenSciencePipe/1.0 (mailto:{email})"}
    year_filter = "publication_year:" + "|".join(str(y) for y in years)
    dois = {}
    cursor = "*"
    total = 0

    for term in FCUL_TERMS:
        cursor = "*"
        while True:
            params = {
                "filter": ",".join([
                    f"institutions.id:{FCUL_OPENALEX_ORG}",
                    f"raw_affiliation_strings.search:{term}",
                    year_filter,
                ]),
                "per-page": 200,
                "cursor": cursor,
                "select": "id,doi,title,publication_year",
            }
            try:
                resp = httpx.get(OPENALEX_WORKS, params=params, headers=headers, timeout=40.0)
                resp.raise_for_status()
            except Exception as exc:
                print(f"  [openalex] '{term}' failed: {str(exc)[:120]}")
                break
            data = resp.json()
            results = data.get("results") or []
            if not results:
                break
            for w in results:
                doi = norm_doi(w.get("doi"))
                wid = w.get("id", "")
                key = doi or wid
                if key and key not in dois:
                    dois[key] = {
                        "doi": doi,
                        "openalex_id": wid,
                        "title": w.get("title") or "",
                        "year": w.get("publication_year"),
                    }
            total += len(results)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor:
                break
            if limit and total >= limit:
                break
        print(f"  [openalex] '{term[:40]}': cumulative {len(dois)}")
        if limit and total >= limit:
            break

    return dois


def fetch_source_dois(source_name, collector, terms, years, limit_per_term=200):
    """Collect DOIs from a single UnifiedCollector source."""
    found = defaultdict(dict)
    for term in terms:
        try:
            df = collector.fetch_papers(
                term,
                limit=limit_per_term,
                start_year=min(years),
                end_year=max(years),
            )
        except Exception as exc:
            print(f"  [{source_name}] '{term[:40]}' failed: {str(exc)[:100]}")
            continue
        if df is None or df.empty:
            continue
        added = 0
        for _, row in df.iterrows():
            doi = norm_doi(row.get("DOI"))
            if not doi:
                continue
            year = row.get("Year")
            try:
                year = int(year)
            except (TypeError, ValueError):
                continue
            if year not in years:
                continue
            if doi not in found:
                added += 1
            found[doi] = {
                "doi": doi,
                "title": str(row.get("Title") or ""),
                "year": year,
                "affiliations": str(row.get("Affiliations") or ""),
                "source": source_name,
            }
        print(f"  [{source_name}] '{term[:40]}': +{added} (total {len(found)})")
    return found


FCUL_HINTS = [
    "faculdade de ci", "faculty of scien", "universidade de lisboa", "university of lisbon",
    "fcul", "instituto dom luiz", "lasige", "ce3c", "bioisi", "centro de fisica teorica",
    "centro de física teórica", "instituto de astrofisica", "instituto de astrofísica",
    "centro de quimica estrutural", "centro de química estrutural", "mare", "lisboa",
]


def looks_fcul(row) -> bool:
    blob = (str(row.get("affiliations") or "") + " " + str(row.get("title") or "")).lower()
    return any(h in blob for h in FCUL_HINTS)


def main(years, limit_per_term, sources, out_dir):
    load_credentials()
    os.makedirs(out_dir, exist_ok=True)

    from src.core.collection import UnifiedCollector
    uc = UnifiedCollector()

    print(f"\n=== OpenAlex baseline (institution ID {FCUL_OPENALEX_ORG}) ===")
    oa = fetch_openalex_dois(years)
    print(f"OpenAlex FCUL DOIs: {len(oa)}")

    results = {}
    for src in sources:
        if src not in uc.collectors:
            print(f"  [skip] unknown source {src}")
            continue
        if src == "openalex":
            continue
        print(f"\n=== {src} ===")
        results[src] = fetch_source_dois(src, uc.collectors[src], BROAD_TERMS, years, limit_per_term)

    summary_rows = []
    misses_rows = []
    seen_miss = set()

    for src, found in results.items():
        src_dois = set(found)
        oa_dois = {v["doi"] for v in oa.values() if v["doi"]}
        overlap = src_dois & oa_dois
        src_only = src_dois - oa_dois
        oa_only = oa_dois - src_dois
        plausible = [d for d in src_only if looks_fcul(found[d])]

        for doi in plausible:
            if doi in seen_miss:
                continue
            seen_miss.add(doi)
            r = found[doi]
            misses_rows.append({
                "DOI": doi,
                "Year": r["year"],
                "Title": r["title"],
                "Found_In": src,
                "Affiliations": r["affiliations"][:400],
            })

        summary_rows.append({
            "Source": src,
            "Source_DOIs": len(src_dois),
            "Overlap_with_OpenAlex": len(overlap),
            "Source_Only": len(src_only),
            "Source_Only_FCUL_likely": len(plausible),
            "OpenAlex_Only": len(oa_only),
        })

    summary_csv = os.path.join(out_dir, "coverage_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()) if summary_rows else ["Source"])
        w.writeheader()
        w.writerows(summary_rows)

    misses_csv = os.path.join(out_dir, "openalex_candidate_misses.csv")
    with open(misses_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["DOI", "Year", "Title", "Found_In", "Affiliations"])
        w.writeheader()
        w.writerows(misses_rows)

    with open(os.path.join(out_dir, "audit_raw.json"), "w", encoding="utf-8") as f:
        json.dump({
            "years": list(years),
            "openalex_fcul_dois": len(oa),
            "per_source": {k: len(v) for k, v in results.items()},
        }, f, indent=2)

    print("\n=== COVERAGE AUDIT ===")
    hdr = f"{'Source':<20}{'DOIs':>8}{'Overlap':>10}{'Src-only':>10}{'FCUL-likely':>13}{'OA-only':>10}"
    print(hdr)
    print("-" * len(hdr))
    for r in summary_rows:
        print(f"{r['Source']:<20}{r['Source_DOIs']:>8}{r['Overlap_with_OpenAlex']:>10}"
              f"{r['Source_Only']:>10}{r['Source_Only_FCUL_likely']:>13}{r['OpenAlex_Only']:>10}")
    print(f"\nCandidate OpenAlex misses: {len(misses_rows)}")
    print(f"  {misses_csv}")
    print(f"  {summary_csv}")
    return summary_rows, misses_rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Audit OpenAlex coverage of FCUL papers against other indexes")
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    ap.add_argument("--limit-per-term", type=int, default=200)
    ap.add_argument("--sources", nargs="+", default=["scopus", "ieee", "pubmed", "crossref", "acm"])
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "fcul_coverage_audit"))
    args = ap.parse_args()
    main(tuple(args.years), args.limit_per_term, args.sources, args.out)
