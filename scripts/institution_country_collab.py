#!/usr/bin/env python3
"""
Institutional Bibliometrics and Country Collaboration Tool.

Extracts publication counts and international collaboration metrics for a specific
institution or faculty in a given year using the OpenAlex API.
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional
import httpx
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_INSTITUTIONS_URL = "https://api.openalex.org/institutions"


import time

def _make_request(url: str, params: dict, max_retries: int = 5) -> dict:
    email = os.environ.get("OPENALEX_EMAIL", "scholar@opensciencepipe.org")
    headers = {"User-Agent": f"OpenSciencePipe/1.0 (mailto:{email})"}
    for attempt in range(max_retries):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=25.0)
            if resp.status_code == 429:
                retry_after = min(2.0 * (attempt + 1), 10.0)
                logger.warning(f"OpenAlex 429 received. Throttling {retry_after}s...")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            time.sleep(0.2)
            return resp.json()
        except httpx.HTTPError as exc:
            if attempt == max_retries - 1:
                logger.error(f"HTTP error requesting {url}: {exc}")
                raise
            time.sleep(1.5 * (attempt + 1))
    return {}


def find_institution_id(query: str) -> Optional[Dict[str, str]]:
    """Resolves an institution name to an OpenAlex ID and display name."""
    try:
        data = _make_request(OPENALEX_INSTITUTIONS_URL, {"search": query})
        results = data.get("results", [])
        if not results:
            return None

        # Prioritize matching display name or best fit
        query_lower = query.lower().strip()
        best_match = results[0]
        for res in results:
            d_name = res.get("display_name", "").lower()
            # If user didn't ask for 'nova', avoid 'universidade nova'
            if "nova" not in query_lower and "nova" in d_name:
                continue
            if query_lower in d_name or d_name in query_lower:
                best_match = res
                break
            # English translation fallback (e.g. Lisbon / Lisboa)
            if "lisboa" in query_lower and "lisbon" in d_name:
                best_match = res
                break
            if "porto" in query_lower and "porto" in d_name:
                best_match = res
                break
            if "coimbra" in query_lower and "coimbra" in d_name:
                best_match = res
                break

        return {
            "id": best_match["id"].replace("https://openalex.org/", ""),
            "display_name": best_match.get("display_name"),
            "country_code": best_match.get("country_code"),
            "ror": best_match.get("ror"),
        }
    except Exception as exc:
        logger.error(f"Failed to query institution: {exc}")
        return None




def get_country_collaborations(
    institution_id: Optional[str] = None,
    faculty_affiliation: Optional[str] = None,
    year: int = 2023,
    top_n: int = 20,
) -> Dict:
    """Queries OpenAlex for publication count and collaborating countries."""
    filters = [f"publication_year:{year}"]

    if institution_id:
        filters.append(f"institutions.id:{institution_id}")
    if faculty_affiliation:
        filters.append(f"raw_affiliation_strings.search:{faculty_affiliation}")

    filter_str = ",".join(filters)

    # 1. Total publications
    total_data = _make_request(OPENALEX_WORKS_URL, {"filter": filter_str, "per_page": 1})
    total_works = total_data.get("meta", {}).get("count", 0)

    if total_works == 0:
        return {
            "filter": filter_str,
            "total_publications": 0,
            "international_publications": 0,
            "international_rate": 0.0,
            "countries": [],
            "institutions": [],
        }

    # 1b. International publications (countries_distinct_count > 1)
    intl_filter = f"{filter_str},countries_distinct_count:>1"
    intl_data = _make_request(OPENALEX_WORKS_URL, {"filter": intl_filter, "per_page": 1})
    intl_works = intl_data.get("meta", {}).get("count", 0)
    intl_rate = round((intl_works / total_works) * 100, 2) if total_works > 0 else 0.0

    # 2. Country aggregation
    countries_data = _make_request(OPENALEX_WORKS_URL, {"filter": filter_str, "group_by": "authorships.countries"})
    country_groups = countries_data.get("group_by", [])

    # Format country list
    country_list = []
    for c in country_groups[:top_n]:
        code = c["key"].replace("https://openalex.org/countries/", "")
        count = c["count"]
        pct = (count / total_works) * 100 if total_works > 0 else 0
        country_list.append(
            {
                "country_code": code,
                "country_name": c.get("key_display_name", code),
                "publications": count,
                "percentage": round(pct, 2),
            }
        )

    # 3. Top collaborating institutions
    inst_data = _make_request(OPENALEX_WORKS_URL, {"filter": filter_str, "group_by": "authorships.institutions.id"})
    inst_groups = inst_data.get("group_by", [])

    collab_institutions = []
    for inst in inst_groups[:top_n]:
        collab_institutions.append(
            {
                "institution_name": inst.get("key_display_name"),
                "publications": inst.get("count"),
            }
        )

    return {
        "filter": filter_str,
        "total_publications": total_works,
        "international_publications": intl_works,
        "international_rate": intl_rate,
        "countries": country_list,
        "institutions": collab_institutions,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract country collaborations and bibliometrics for an institution."
    )
    parser.add_argument(
        "--institution",
        type=str,
        default="Universidade de Lisboa",
        help="Parent institution name to search in OpenAlex (e.g., 'Universidade de Lisboa').",
    )
    parser.add_argument(
        "--faculty",
        type=str,
        default="Faculdade de Ciências",
        help="Sub-unit or faculty string to filter raw affiliations.",
    )
    parser.add_argument(
        "--institution-id",
        type=str,
        default=None,
        help="Direct OpenAlex institution ID (e.g. I141596103) if known.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Publication year to analyze (default: 2023).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top countries/institutions to display.",
    )
    parser.add_argument(
        "--csv-out",
        type=str,
        default=None,
        help="Optional path to export country results as CSV.",
    )

    args = parser.parse_args()

    inst_id = args.institution_id
    inst_name = args.institution
    if not inst_id and args.institution:
        inst_info = find_institution_id(args.institution)
        if inst_info:
            inst_id = inst_info["id"]
            inst_name = inst_info["display_name"]
            logger.info(f"Resolved '{args.institution}' to OpenAlex ID: {inst_id} ({inst_name})")
        else:
            logger.warning(f"Could not resolve institution '{args.institution}'. Proceeding with faculty filter only.")

    target_desc = f"{args.faculty} - {inst_name}" if args.faculty else inst_name
    print(f"\nAnalyzing bibliometrics for: {target_desc} (Year: {args.year})")

    results = get_country_collaborations(
        institution_id=inst_id,
        faculty_affiliation=args.faculty,
        year=args.year,
        top_n=args.top,
    )

    total_works = results["total_publications"]
    intl_works = results.get("international_publications", 0)
    intl_rate = results.get("international_rate", 0.0)

    print(f"Total publications: {total_works}")
    print(f"International co-authored publications: {intl_works} ({intl_rate}%)\n")

    if total_works == 0:
        print("No publications found for the specified criteria.")
        sys.exit(0)

    countries = results["countries"]
    df_countries = pd.DataFrame(countries)

    print("Top Collaborating Countries:")
    print(df_countries.to_string(index=False))

    if args.csv_out:
        df_countries.to_csv(args.csv_out, index=False)
        print(f"\nSaved country breakdown to: {args.csv_out}")

    print("\nTop Collaborating Institutions:")
    df_inst = pd.DataFrame(results["institutions"])
    print(df_inst.to_string(index=False))


if __name__ == "__main__":
    main()
