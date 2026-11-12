#!/usr/bin/env python3
"""
FCUL - Multi-Source Bibliometric Analysis via UnifiedCollector.

Queries all available bibliographic sources (OpenAlex, Crossref, PubMed,
Scopus, IEEE, ACM, Semantic Scholar, arXiv, bioRxiv) using FCUL search terms,
filters hits to FCUL-affiliated papers, then produces partner-institution,
country, scientist-dyad and topic outputs compatible with the existing
single-source FCUL reports.

Usage:
    python scripts/generate_fcul_multisource_analysis.py --years 2023 2024 2025
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core.collection import UnifiedCollector

YEAR = 2023
YEARS = (2023,)
YEAR_SLUG = "2023"

FCUL_SEARCH_TERMS = [
    "Faculty of Sciences University of Lisbon",
    "Faculdade de Ciencias Universidade de Lisboa",
    "Faculty of Science Lisbon",
    "FCUL",
    "Instituto Dom Luiz",
    "LASIGE",
    "Ce3C",
    "BioISI",
    "Centro de Fisica Teorica e Computacional",
    "Instituto de Astrofisica e Ciencias do Espaco",
    "Centro de Quimica Estrutural",
    "MARE Marine and Environmental Sciences Centre",
    "Laboratorio de Instrumentacao e Fisica Experimental de Particulas",
]

# Affiliation substrings that mark an author as FCUL-affiliated.
FCUL_AFFILIATION_MARKERS = [
    "faculdade de ciencias",
    "faculdade de ciências",
    "faculty of sciences",
    "faculty of science",
    "universidade de lisboa",
    "university of lisbon",
    "fcul",
    "instituto dom luiz",
    "lasige",
    "ce3c",
    "cE3c".lower(),
    "bioisi",
    "centro de fisica teorica",
    "centro de física teórica",
    "instituto de astrofisica",
    "instituto de astrofísica",
    "centro de quimica estrutural",
    "centro de química estrutural",
    "mare",
    "lip lisboa",
    "laboratorio de instrumentacao",
    "laboratório de instrumentação",
]

FCUL_UNIT_PATTERNS = {
    "Instituto Dom Luiz (IDL)": [r"instituto dom luiz", r"\bidl\b"],
    "LASIGE": [r"lasige"],
    "Ce3C": [r"ce3c", r"centro de ecolog", r"centre for ecology"],
    "BioISI": [r"bioisi", r"biosystems"],
    "CFTC": [r"centro de f[ií]sica te[oó]rica", r"\bcftc\b"],
    "IA": [r"instituto de astrof[ií]sica", r"\bia\b.*espa[cç]o"],
    "CQE": [r"centro de qu[ií]mica estrutural", r"\bcqe\b"],
    "MARE": [r"\bmare\b", r"marine and environmental"],
    "LIP": [r"laborat[oó]rio de instrumenta", r"\blip\b"],
}


def configure_year(year=None, years=None):
    global YEAR, YEARS, YEAR_SLUG
    if years:
        YEARS = tuple(sorted(set(years)))
        YEAR = YEARS[-1]
    elif year:
        YEAR = year
        YEARS = (year,)
    YEAR_SLUG = "_".join(str(y) for y in YEARS)


def output_paths():
    out_dir = os.path.join(ROOT, "outputs", f"fcul_multisource_{YEAR_SLUG}")
    data_dir = os.path.join(out_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return out_dir, data_dir


def is_fcul_affiliation(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(marker in low for marker in FCUL_AFFILIATION_MARKERS)


def identify_fcul_units(text: str):
    units = set()
    if not text:
        return ["FCUL (Core Faculty / Other Depts)"]
    low = text.lower()
    for unit_name, patterns in FCUL_UNIT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, low):
                units.add(unit_name)
                break
    if not units:
        units.add("FCUL (Core Faculty / Other Depts)")
    return sorted(units)


def split_authors(field) -> list:
    if field is None:
        return []
    if isinstance(field, list):
        return [str(a).strip() for a in field if str(a).strip()]
    text = str(field)
    if ";" in text:
        return [a.strip() for a in text.split(";") if a.strip()]
    return [a.strip() for a in text.split(",") if a.strip()]


def split_affiliations(field) -> list:
    """Affiliations are usually a single blob; split on common separators when multi-institution."""
    if field is None:
        return []
    if isinstance(field, list):
        return [str(a).strip() for a in field if str(a).strip()]
    return [str(field).strip()]


def fetch_multisource(query_terms, limit_per_source=200, sources=None):
    collector = UnifiedCollector()
    merged = {}
    per_source_counts = Counter()

    for term in query_terms:
        try:
            df = collector.fetch_all(
                query=term,
                limit_per_source=limit_per_source,
                sources=sources,
                start_year=min(YEARS),
                end_year=max(YEARS),
            )
        except Exception as exc:
            print(f"  [warn] query failed for '{term}': {exc}")
            continue

        if df is None or df.empty:
            continue

        added = 0
        for _, row in df.iterrows():
            doi_raw = row.get("DOI")
            doi = str(doi_raw).strip().lower() if doi_raw is not None else ""
            if doi in ("", "nan", "none"):
                doi = ""
            title_raw = row.get("Title")
            title = str(title_raw).strip() if title_raw is not None else ""
            if title in ("nan", "none", "untitled"):
                title = ""
            key = doi if doi else title.lower()
            if not key:
                continue
            if key in merged:
                continue
            clean = {}
            for k, v in row.to_dict().items():
                if v is None:
                    clean[k] = ""
                elif isinstance(v, float) and v != v:  # NaN
                    clean[k] = ""
                else:
                    clean[k] = v if isinstance(v, (str, int, float, bool, list)) else str(v)
            merged[key] = clean
            per_source_counts[row.get("Source", "Unknown")] += 1
            added += 1
        print(f"  Term '{term[:48]}': +{added} new (running total: {len(merged)})")

    return list(merged.values()), per_source_counts


def parse_and_process(rows):
    papers = []
    country_counts = Counter()
    partner_institutions = defaultdict(
        lambda: {"publications": 0, "citations": 0, "country": "Unknown", "topics": Counter()}
    )
    fcul_scientists = defaultdict(
        lambda: {"name": "", "publications": 0, "citations": 0, "units": set()}
    )
    scientist_dyads = defaultdict(
        lambda: {
            "fcul_author": "",
            "partner_author": "",
            "partner_country": "",
            "partner_institution": "",
            "joint_papers": 0,
            "joint_citations": 0,
        }
    )
    unit_counts = Counter()
    source_counts = Counter()

    for row in rows:
        source = row.get("Source", "Unknown")
        source_counts[source] += 1

        title = row.get("Title") or "Untitled"
        doi = row.get("DOI") or ""
        year_raw = row.get("Year")
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            continue
        if year not in YEARS:
            continue

        citations = 0
        try:
            citations = int(row.get("Cite Count") or 0)
        except (TypeError, ValueError):
            citations = 0

        topic = row.get("Author Keywords") or "General Science"
        if isinstance(topic, str) and ";" in topic:
            topic = topic.split(";")[0].strip()
        topic = topic or "General Science"

        authors = split_authors(row.get("Authors"))
        affils = split_affiliations(row.get("Affiliations"))
        affil_text = " ".join(affils)

        # FCUL relevance gate: at least one affiliation string must look like FCUL
        if not is_fcul_affiliation(affil_text):
            continue

        # Countries: prefer structured OpenAlex codes, fall back to regex on affiliation text
        countries = row.get("Countries")
        paper_countries = []
        if isinstance(countries, list) and countries:
            paper_countries = [str(c).upper() for c in countries if c]
        else:
            for m in re.findall(r"\b(ES|GB|UK|DE|FR|IT|US|BR|CH|NL|CA|SE|PL|BE|NO|DK|FI|IE|AT|AU|JP|CN|IN)\b", affil_text):
                paper_countries.append("GB" if m == "UK" else m)
        paper_countries = [c for c in paper_countries if c != "PT"]

        for c in set(paper_countries):
            country_counts[c] += 1

        units = identify_fcul_units(affil_text)
        for u in units:
            unit_counts[u] += 1

        fcul_authors = authors[:3] if authors else []
        partner_authors = authors[len(fcul_authors):][:3]

        # Institutions: structured OpenAlex partners, else fall back to the source label
        partner_insts = row.get("Partner_Institutions")
        inst_pairs = []
        if isinstance(partner_insts, list) and partner_insts:
            for entry in partner_insts:
                if "|" in str(entry):
                    iname, icountry = str(entry).split("|", 1)
                    if iname.strip():
                        inst_pairs.append((iname.strip(), (icountry or "Unknown").upper()))
        if not inst_pairs:
            inst_pairs = [(f"Co-author from {source}", "Unknown")]

        for iname, icountry in inst_pairs:
            partner_institutions[iname]["publications"] += 1
            partner_institutions[iname]["citations"] += citations
            partner_institutions[iname]["country"] = icountry
            if topic:
                partner_institutions[iname]["topics"][topic] += 1

        for fa in fcul_authors:
            fcul_scientists[fa]["name"] = fa
            fcul_scientists[fa]["publications"] += 1
            fcul_scientists[fa]["citations"] += citations
            fcul_scientists[fa]["units"].update(units)

        for fa in fcul_authors[:2]:
            for pa in partner_authors[:2]:
                key = (fa, pa, source)
                scientist_dyads[key]["fcul_author"] = fa
                scientist_dyads[key]["partner_author"] = pa
                scientist_dyads[key]["partner_country"] = (
                    inst_pairs[0][1] if inst_pairs else "Unknown"
                )
                scientist_dyads[key]["partner_institution"] = (
                    inst_pairs[0][0] if inst_pairs else f"Unknown ({source})"
                )
                scientist_dyads[key]["joint_papers"] += 1
                scientist_dyads[key]["joint_citations"] += citations

        papers.append(
            {
                "Title": title,
                "Year": year,
                "DOI": doi,
                "Citations": citations,
                "Source": source,
                "Primary_Topic": topic,
                "FCUL_Units": "; ".join(units),
                "Affiliations": affil_text,
                "Authors": "; ".join(authors),
            }
        )

    return {
        "papers": papers,
        "country_counts": country_counts,
        "partner_institutions": partner_institutions,
        "fcul_scientists": fcul_scientists,
        "scientist_dyads": scientist_dyads,
        "unit_counts": unit_counts,
        "source_counts": source_counts,
    }


def write_outputs(result, data_dir):
    slug = f"fcul_multisource_{YEAR_SLUG}"

    papers_csv = os.path.join(data_dir, f"{slug}_papers.csv")
    if result["papers"]:
        with open(papers_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(result["papers"][0].keys()))
            writer.writeheader()
            writer.writerows(result["papers"])

    countries_csv = os.path.join(data_dir, f"{slug}_top_countries.csv")
    total = len(result["papers"]) or 1
    with open(countries_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Country", "Publications", "Share_Pct"])
        for country, count in result["country_counts"].most_common():
            writer.writerow([country, count, round(100.0 * count / total, 1)])

    inst_csv = os.path.join(data_dir, f"{slug}_partner_institutions.csv")
    with open(inst_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Institution", "Country", "Publications", "Citations", "Source"])
        ranked = sorted(
            result["partner_institutions"].items(),
            key=lambda kv: kv[1]["publications"],
            reverse=True,
        )
        for name, stats in ranked:
            writer.writerow([name, stats["country"], stats["publications"], stats["citations"], "UnifiedCollector"])

    units_csv = os.path.join(data_dir, f"{slug}_research_units.csv")
    with open(units_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Research_Unit", "Publications"])
        for unit, count in result["unit_counts"].most_common():
            writer.writerow([unit, count])

    sources_csv = os.path.join(data_dir, f"{slug}_source_breakdown.csv")
    with open(sources_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Publications"])
        for src, count in result["source_counts"].most_common():
            writer.writerow([src, count])

    dyads_csv = os.path.join(data_dir, f"{slug}_scientist_dyads.csv")
    with open(dyads_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["FCUL_Author", "Partner_Author", "Partner_Institution", "Joint_Papers", "Joint_Citations"])
        ranked = sorted(
            result["scientist_dyads"].items(),
            key=lambda kv: kv[1]["joint_papers"],
            reverse=True,
        )
        for _, d in ranked[:500]:
            writer.writerow(
                [d["fcul_author"], d["partner_author"], d["partner_institution"], d["joint_papers"], d["joint_citations"]]
            )

    scientists_csv = os.path.join(data_dir, f"{slug}_top_scientists.csv")
    with open(scientists_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Scientist", "Publications", "Citations", "Units"])
        ranked = sorted(
            result["fcul_scientists"].items(),
            key=lambda kv: kv[1]["publications"],
            reverse=True,
        )
        for _, s in ranked[:200]:
            writer.writerow([s["name"], s["publications"], s["citations"], "; ".join(sorted(s["units"]))])

    return {
        "papers": papers_csv,
        "countries": countries_csv,
        "institutions": inst_csv,
        "units": units_csv,
        "sources": sources_csv,
        "dyads": dyads_csv,
        "scientists": scientists_csv,
    }


def main(year=None, years=None, limit_per_source=200, sources=None):
    configure_year(year, years)
    out_dir, data_dir = output_paths()
    slug = f"fcul_multisource_{YEAR_SLUG}"
    cache_path = os.path.join(data_dir, f"{slug}_raw_rows.json")

    print(f"FCUL multi-source extraction via UnifiedCollector for {', '.join(str(y) for y in YEARS)}")
    print(f"Sources: {sources or 'all available'}")
    print(f"Limit per source per term: {limit_per_source}")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 10000:
        with open(cache_path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        print(f"Loaded {len(rows)} cached rows from {cache_path}")
    else:
        rows, _ = fetch_multisource(FCUL_SEARCH_TERMS, limit_per_source=limit_per_source, sources=sources)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        print(f"Cached {len(rows)} raw rows to {cache_path}")

    result = parse_and_process(rows)
    paths = write_outputs(result, data_dir)

    print("\n=== RESULTS ===")
    print(f"FCUL-affiliated papers ({', '.join(str(y) for y in YEARS)}): {len(result['papers'])}")
    print("\nSource breakdown:")
    for src, count in result["source_counts"].most_common():
        print(f"  {src}: {count}")
    print("\nTop countries:")
    for c, n in result["country_counts"].most_common(10):
        print(f"  {c}: {n}")
    print("\nTop research units:")
    for u, n in result["unit_counts"].most_common():
        print(f"  {u}: {n}")
    print("\nOutputs:")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCUL multi-source bibliometric analysis")
    parser.add_argument("--year", type=int, default=None, help="Single publication year")
    parser.add_argument("--years", type=int, nargs="+", default=None, help="Pool of years")
    parser.add_argument("--limit", type=int, default=200, help="Max results per source per term")
    parser.add_argument("--sources", nargs="+", default=None, help="Restrict to specific sources")
    parser.add_argument("--force", action="store_true", help="Ignore cache and re-fetch")
    args = parser.parse_args()

    if args.force:
        y = args.years or ([args.year] if args.year else None)
        configure_year(args.year, y)
        _, data_dir = output_paths()
        cp = os.path.join(data_dir, f"fcul_multisource_{YEAR_SLUG}_raw_rows.json")
        if os.path.exists(cp):
            os.remove(cp)
            print(f"Removed cache {cp}")

    main(args.year, args.years, limit_per_source=args.limit, sources=args.sources)
