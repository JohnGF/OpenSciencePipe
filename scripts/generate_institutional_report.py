#!/usr/bin/env python3
"""
Universal Institutional Bibliometric Report Generator.

Generates hard data CSVs, figures (bar chart & co-authorship network),
scientist dyads, and compiles an executive PDF report for ANY institution,
faculty, partner country, and year.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
import httpx
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import pycountry
import seaborn as sns

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_INSTITUTIONS_URL = "https://api.openalex.org/institutions"


def resolve_country(query: str):
    """Resolves country name or alpha-2 code to code and common display name."""
    query = query.strip()
    try:
        if len(query) == 2:
            c = pycountry.countries.get(alpha_2=query.upper())
            if c:
                return c.alpha_2, c.name
        c = pycountry.countries.search_fuzzy(query)
        if c:
            return c[0].alpha_2, c[0].name
    except Exception:
        pass
    # Fallback
    common = {"USA": ("US", "United States"), "UK": ("GB", "United Kingdom"), "CHINA": ("CN", "China")}
    if query.upper() in common:
        return common[query.upper()]
    return query.upper()[:2], query


KNOWN_INSTITUTIONS = {
    "universidade de lisboa": {"id": "I141596103", "display_name": "University of Lisbon", "country_code": "PT"},
    "university of lisbon": {"id": "I141596103", "display_name": "University of Lisbon", "country_code": "PT"},
    "universidade do porto": {"id": "I182534213", "display_name": "Universidade do Porto", "country_code": "PT"},
    "university of porto": {"id": "I182534213", "display_name": "Universidade do Porto", "country_code": "PT"},
    "universidade de coimbra": {"id": "I8061405", "display_name": "University of Coimbra", "country_code": "PT"},
    "universidade nova de lisboa": {"id": "I83558840", "display_name": "Universidade Nova de Lisboa", "country_code": "PT"},
    "fcul": {"id": "I141596103", "display_name": "University of Lisbon", "country_code": "PT"},
}


def resolve_institution(query: str) -> dict:
    """Finds OpenAlex institution ID and display name."""
    clean = query.strip().lower()
    if clean in KNOWN_INSTITUTIONS:
        return KNOWN_INSTITUTIONS[clean]

    params = {"search": query}
    try:
        resp = httpx.get(OPENALEX_INSTITUTIONS_URL, params=params, timeout=15.0)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            best = results[0]
            # Disambiguate if needed
            q_lower = query.lower()
            for r in results:
                d_name = r.get("display_name", "").lower()
                if "nova" not in q_lower and "nova" in d_name:
                    continue
                if q_lower in d_name or d_name in q_lower or "lisbon" in d_name:
                    best = r
                    break
            return {
                "id": best["id"].replace("https://openalex.org/", ""),
                "display_name": best.get("display_name", query),
                "country_code": best.get("country_code", "PT"),
            }
    except Exception as e:
        print(f"Warning resolving institution: {e}")
    return {"id": None, "display_name": query, "country_code": "PT"}


def run_pipeline(institution: str, faculty: str, country: str, year: int, output_base: str = "outputs"):
    iso_code, country_name = resolve_country(country)
    inst_info = resolve_institution(institution)
    inst_id = inst_info["id"]
    inst_name = inst_info["display_name"]

    slug = f"{inst_name}_{faculty}_{country_name}_{year}".lower()
    slug = "".join([c if c.isalnum() else "_" for c in slug]).strip("_")
    out_dir = os.path.join(output_base, slug)
    data_dir = os.path.join(out_dir, "data")
    figures_dir = os.path.join(out_dir, "figures")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(figures_dir, exist_ok=True)

    print("\n" + "=" * 75)
    print(f"GENERATING INSTITUTIONAL REPORT")
    print(f"Institution : {inst_name} (ID: {inst_id})")
    print(f"Faculty/Unit: {faculty}")
    print(f"Partner     : {country_name} ({iso_code})")
    print(f"Year        : {year}")
    print(f"Output Dir  : {out_dir}")
    print("=" * 75 + "\n")

    email = os.environ.get("OPENALEX_EMAIL", "scholar@opensciencepipe.org")
    headers = {"User-Agent": f"OpenSciencePipe/1.0 (mailto:{email})"}

    # Search variations for the faculty
    search_terms = [faculty]
    if "ciências" in faculty.lower():
        search_terms.extend(["Faculty of Sciences", "Faculty of Science", "FCUL", "Instituto Dom Luiz", "LASIGE", "Ce3C", "BioISI", "CFTC", "IA-Lisboa"])

    work_dict = {}
    print("Harvesting publications from OpenAlex...")
    for term in search_terms:
        filters = [
            f"publication_year:{year}",
            f"raw_affiliation_strings.search:{term}",
            f"authorships.countries:{iso_code}",
        ]
        if inst_id:
            filters.append(f"institutions.id:{inst_id}")

        params = {
            "filter": ",".join(filters),
            "per_page": 100,
            "select": "id,doi,title,publication_year,cited_by_count,primary_topic,authorships",
        }
        try:
            r = httpx.get(OPENALEX_WORKS_URL, params=params, headers=headers, timeout=25.0)
            if r.status_code == 200:
                for w in r.json().get("results", []):
                    work_dict[w["id"]] = w
            time.sleep(0.15)
        except Exception as e:
            print(f"Warning fetching term {term}: {e}")

    works = list(work_dict.values())
    total_papers = len(works)
    print(f"Harvested {total_papers} joint publications.")

    if total_papers == 0:
        print("No joint publications found matching criteria.")
        return

    # Process metrics
    partner_inst_stats = defaultdict(lambda: {"publications": 0, "citations": 0, "topics": Counter()})
    fcul_authors = Counter()
    fcul_author_cits = defaultdict(int)
    fcul_author_topics = defaultdict(Counter)
    network_edges = Counter()
    network_nodes = {}
    dyads = Counter()
    dyad_citations = defaultdict(int)
    dyad_topics = defaultdict(Counter)
    paper_rows = []

    for w in works:
        cits = w.get("cited_by_count", 0)
        topic = (w.get("primary_topic") or {}).get("display_name", "N/A")
        paper_partner_insts = set()
        pt_in_paper = set()
        foreign_in_paper = set()

        for a in w.get("authorships", []):
            author_name = (a.get("author") or {}).get("display_name")
            if not author_name:
                continue
            raw_affs = " ".join(a.get("raw_affiliation_strings", [])).lower()
            countries = a.get("countries", [])
            inst_countries = [inst.get("country_code") for inst in a.get("institutions", [])]

            is_domestic = any(t.lower() in raw_affs for t in search_terms)
            is_foreign = (iso_code in countries) or (iso_code in inst_countries)

            if is_domestic:
                pt_in_paper.add(author_name)
                fcul_authors[author_name] += 1
                fcul_author_cits[author_name] += cits
                fcul_author_topics[author_name][topic] += 1

            if is_foreign:
                partner_insts = [inst.get("display_name") for inst in a.get("institutions", []) if inst.get("country_code") == iso_code]
                main_inst = partner_insts[0] if partner_insts else f"{country_name} Institution"
                foreign_in_paper.add((author_name, main_inst))

            for inst in a.get("institutions", []):
                if inst.get("country_code") == iso_code:
                    name = inst.get("display_name")
                    if name:
                        paper_partner_insts.add(name)

        for p_inst in paper_partner_insts:
            partner_inst_stats[p_inst]["publications"] += 1
            partner_inst_stats[p_inst]["citations"] += cits
            partner_inst_stats[p_inst]["topics"][topic] += 1
            network_nodes[p_inst] = {"country": iso_code, "type": "Foreign Institution"}
            network_nodes[faculty] = {"country": inst_info["country_code"], "type": "Domestic Faculty"}
            edge = tuple(sorted([faculty, p_inst]))
            network_edges[edge] += 1

        for pt_a in pt_in_paper:
            for f_a, f_inst in foreign_in_paper:
                k = (pt_a, f_a, f_inst)
                dyads[k] += 1
                dyad_citations[k] += cits
                dyad_topics[k][topic] += 1

        paper_rows.append({
            "OpenAlex_ID": w["id"].replace("https://openalex.org/", ""),
            "DOI": w.get("doi", ""),
            "Title": w.get("title", ""),
            "Year": year,
            "Citations": cits,
            "Primary_Topic": topic,
            "Partner_Institutions": "; ".join(sorted(paper_partner_insts)),
        })

    # Save CSVs
    df_papers = pd.DataFrame(paper_rows)
    df_papers.to_csv(os.path.join(data_dir, "joint_papers.csv"), index=False)

    inst_rows = [
        {"Institution": k, "Publications": v["publications"], "Percentage": round((v["publications"] / total_papers) * 100, 2), "Total_Citations": v["citations"], "Top_Topic": v["topics"].most_common(1)[0][0] if v["topics"] else "N/A"}
        for k, v in partner_inst_stats.items()
    ]
    df_inst = pd.DataFrame(inst_rows).sort_values("Publications", ascending=False)
    df_inst.to_csv(os.path.join(data_dir, "partner_institutions.csv"), index=False)

    sci_rows = [
        {"Scientist": k, "Publications": v, "Total_Citations": fcul_author_cits[k], "Top_Topic": fcul_author_topics[k].most_common(1)[0][0] if fcul_author_topics[k] else "N/A"}
        for k, v in fcul_authors.most_common(50)
    ]
    df_sci = pd.DataFrame(sci_rows)
    df_sci.to_csv(os.path.join(data_dir, "lead_scientists.csv"), index=False)

    dyad_rows = [
        {"Domestic_Scientist": k[0], "Foreign_Scientist": k[1], "Foreign_Institution": k[2], "Joint_Papers": cnt, "Total_Citations": dyad_citations[k], "Primary_Topic": dyad_topics[k].most_common(1)[0][0]}
        for k, cnt in dyads.most_common(50)
    ]
    df_dyads = pd.DataFrame(dyad_rows)
    df_dyads.to_csv(os.path.join(data_dir, "scientist_dyads.csv"), index=False)

    # Plot Figure 1
    top_inst = df_inst.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(top_inst["Institution"], top_inst["Publications"], color="#2980b9", edgecolor="#1a5276", height=0.65)
    for bar, pct in zip(bars, top_inst["Percentage"]):
        w = bar.get_width()
        ax.text(w + 0.15, bar.get_y() + bar.get_height() / 2, f"{int(w)} ({pct:.1f}%)", va="center", fontsize=9, fontweight="bold", color="#2c3e50")
    ax.set_title(f"Top {country_name} Institutions Collaborating with {faculty} ({year}, N = {total_papers})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Number of Joint Publications", fontweight="bold")
    ax.set_xlim(0, max(top_inst["Publications"]) + 2.5)
    plt.tight_layout()
    fig1_path = os.path.join(figures_dir, "Figure_1_partner_institutions.pdf")
    fig.savefig(fig1_path, dpi=300)
    fig.savefig(os.path.join(figures_dir, "Figure_1_partner_institutions.png"), dpi=300)
    plt.close(fig)

    # Plot Figure 2 (Bipartite network)
    G = nx.Graph()
    for (u, v), w in network_edges.most_common(20):
        G.add_edge(u, v, weight=w)
    fig, ax = plt.subplots(figsize=(14, 10))
    pos = nx.spring_layout(G, k=0.8, seed=42)
    node_colors = ["#2980b9" if n == faculty else "#e74c3c" for n in G.nodes()]
    node_sizes = [1800 if n == faculty else 500 + sum(d["weight"] for _, _, d in G.edges(n, data=True)) * 90 for n in G.nodes()]
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.5, edge_color="#7f8c8d")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, edgecolors="#2c3e50")
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=8.5, font_weight="bold")
    ax.set_title(f"Co-Authorship Network: {faculty} <---> {country_name} Institutions ({year})", fontsize=13, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    fig2_path = os.path.join(figures_dir, "Figure_2_coauthorship_network.pdf")
    fig.savefig(fig2_path, dpi=300)
    fig.savefig(os.path.join(figures_dir, "Figure_2_coauthorship_network.png"), dpi=300)
    plt.close(fig)

    # Compile PDF Report via pdflatex
    tex_path = os.path.join(out_dir, "report.tex")
    tex = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[margin=2.2cm]{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{booktabs}",
        r"\usepackage{xcolor}",
        r"\usepackage{hyperref}",
        r"\usepackage{microtype}",
        r"\usepackage{array}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}",
        r"\newcolumntype{R}[1]{>{\raggedleft\arraybackslash}p{#1}}",
        r"\newcolumntype{C}[1]{>{\centering\arraybackslash}p{#1}}",
        r"\definecolor{primary}{RGB}{41, 128, 185}",
        r"\definecolor{darkgray}{RGB}{44, 62, 80}",
        r"\hypersetup{colorlinks=true, linkcolor=primary, urlcolor=primary}",
        r"\begin{document}",
        rf"\begin{{center}}",
        rf"{{\LARGE\bfseries\color{{primary}} Institutional Bibliometric Report:}}\\[0.4em]",
        rf"{{\Large\bfseries {faculty} ({inst_name}) $\longleftrightarrow$ {country_name}}}\\[0.5em]",
        rf"{{\normalsize\bfseries Publication Year: {year} \quad | \quad Total Joint Papers: {total_papers}}}\\[0.3em]",
        rf"{{\small Generated autonomously by \textbf{{OpenSciencePipe}}}}",
        r"\end{center}",
        r"\vspace{1em}",
        r"\section*{1. Executive Overview}",
        rf"This dossier maps the international collaboration footprint between \textbf{{{faculty}}} (\textit{{{inst_name}}}) and scientific institutions in \textbf{{{country_name}}} for the calendar year \textbf{{{year}}}.",
        r"\vspace{0.8em}",
        r"\begin{center}",
        r"\begin{tabular}{@{}L{10.0cm} R{5.5cm}@{}}",
        r"\toprule",
        r"\textbf{Key Indicator} & \textbf{Value} \\",
        r"\midrule",
        rf"Total Joint Publications & \textbf{{{total_papers}}} papers \\",
        rf"Total Citations Accrued & \textbf{{{df_papers['Citations'].sum():,}+}} citations \\",
        rf"Distinct Partner Institutions & \textbf{{{len(df_inst)}}} institutions \\",
        rf"Active Lead Scientists & \textbf{{{len(df_sci)}}} domestic investigators \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{center}",
        r"\vspace{1em}",
        r"\section*{2. Partner Institutions}",
        r"\begin{figure}[htbp]",
        r"\centering",
        r"\includegraphics[width=0.92\textwidth]{figures/Figure_1_partner_institutions.pdf}",
        rf"\caption{{Top {country_name} institutions collaborating with {faculty} in {year}.}}",
        r"\end{figure}",
        r"\vspace{0.5em}",
        r"\begin{table}[htbp]",
        r"\centering\footnotesize\sloppy",
        r"\begin{tabular}{@{}L{8.0cm} C{2.0cm} C{2.2cm} C{2.5cm}@{}}",
        r"\toprule",
        r"\textbf{Institution} & \textbf{Joint Papers} & \textbf{Share (\%)} & \textbf{Citations} \\",
        r"\midrule",
    ]
    for _, r in df_inst.head(10).iterrows():
        name = r["Institution"].replace("&", r"\&")
        tex.append(f"{name} & {r['Publications']} & {r['Percentage']:.1f}\\% & {r['Total_Citations']} \\\\")
    tex.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        r"\newpage",
        r"\section*{3. Co-Authorship Network Architecture}",
        r"\begin{figure}[htbp]",
        r"\centering",
        r"\includegraphics[width=0.95\textwidth]{figures/Figure_2_coauthorship_network.pdf}",
        rf"\caption{{Bipartite network linking {faculty} to top {country_name} universities.}}",
        r"\end{figure}",
        r"\section*{4. Lead Scientists \& Dyads}",
        r"\begin{table}[htbp]",
        r"\centering\footnotesize\sloppy",
        r"\begin{tabular}{@{}L{3.8cm} L{3.8cm} C{1.8cm} L{5.8cm}@{}}",
        r"\toprule",
        r"\textbf{Domestic Scientist} & \textbf{Foreign Scientist} & \textbf{Papers} & \textbf{Primary Field} \\",
        r"\midrule",
    ])
    for _, r in df_dyads.head(8).iterrows():
        p1 = str(r["Domestic_Scientist"]).replace("&", r"\&")[:24]
        p2 = str(r["Foreign_Scientist"]).replace("&", r"\&")[:24]
        top_t = str(r["Primary_Topic"]).replace("&", r"\&")[:30]
        tex.append(f"{p1} & {p2} & {r['Joint_Papers']} & {top_t} \\\\")
    tex.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        r"\end{document}",
    ])

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex) + "\n")

    print(f"Compiling executive PDF report via pdflatex...")
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "report.tex"], cwd=out_dir, capture_output=True)

    pdf_out = os.path.join(out_dir, "report.pdf")
    if os.path.exists(pdf_out):
        print(f"\nSUCCESS! Generated executive PDF report: {pdf_out} ({os.path.getsize(pdf_out):,} bytes)")
    print(f"CSVs, figures, and LaTeX stored in: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Universal Institutional Bibliometric Dossier Generator.")
    parser.add_argument("--institution", type=str, default="Universidade de Lisboa", help="Parent university/institution name")
    parser.add_argument("--faculty", type=str, default="Faculdade de Ciências", help="Faculty or department name")
    parser.add_argument("--country", type=str, default="ES", help="Partner country name or 2-letter ISO code (e.g. 'ES', 'Spain', 'US', 'Germany')")
    parser.add_argument("--year", type=int, default=2023, help="Publication year to audit")
    parser.add_argument("--output-base", type=str, default="outputs", help="Base output directory")
    args = parser.parse_args()

    run_pipeline(
        institution=args.institution,
        faculty=args.faculty,
        country=args.country,
        year=args.year,
        output_base=args.output_base,
    )


if __name__ == "__main__":
    main()
