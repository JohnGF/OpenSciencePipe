#!/usr/bin/env python3
"""
FCUL - China Comprehensive Co-Authorship & Bibliometric Scaffold Generator (default year 2023, selectable via --year).

Includes both language variations ("Faculty of Sciences" in English and "Faculdade de Ciências")
and FCUL-hosted FCT Research Units (IDL, LASIGE, Ce3C, BioISI, CFTC, IA, and FCUL labs in CQE/MARE).
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict
import httpx
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import seaborn as sns

OPENALEX_WORKS_URL = "https://api.openalex.org/works"

YEAR = 2023
YEARS = (YEAR,)
YEAR_SLUG = str(YEAR)
YEAR_LABEL = str(YEAR)
OUTPUT_DIR = f"outputs/fcul_china_{YEAR}"
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")

FCUL_SEARCH_TERMS = [
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
]


def configure_year(year: int, years=None):
    """Binds all module-level paths to the requested publication year(s).

    `years` allows pooling several publication years into one combined report,
    e.g. (2024, 2025) -> outputs/fcul_china_2024_2025.
    """
    global YEAR, YEARS, YEAR_SLUG, YEAR_LABEL, OUTPUT_DIR, DATA_DIR, FIGURES_DIR, TABLES_DIR
    YEARS = tuple(sorted(set(years))) if years else (year,)
    YEAR = YEARS[-1]
    if len(YEARS) == 1:
        YEAR_SLUG = str(YEARS[0])
        YEAR_LABEL = str(YEARS[0])
    else:
        YEAR_SLUG = f"{YEARS[0]}_{YEARS[-1]}"
        YEAR_LABEL = f"{YEARS[0]}-{YEARS[-1]}"
    OUTPUT_DIR = f"outputs/fcul_china_{YEAR_SLUG}"
    DATA_DIR = os.path.join(OUTPUT_DIR, "data")
    FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")
    TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")


def setup_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)


def year_filter() -> str:
    """OpenAlex publication_year filter, supporting pooled year ranges."""
    return "publication_year:" + "|".join(str(y) for y in YEARS)


def fetch_all_fcul_china_works() -> list:
    """Fetches unique publications matching FCUL and its research units with China in YEAR_LABEL."""
    raw_cache = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_raw_works.json")
    if os.path.exists(raw_cache):
        with open(raw_cache, "r", encoding="utf-8") as f:
            works = json.load(f)
            print(f"Loaded {len(works)} works from cache.")
            return works

    work_dict = {}
    email = os.environ.get("OPENALEX_EMAIL", "scholar@opensciencepipe.org")
    headers = {"User-Agent": f"OpenSciencePipe/1.0 (mailto:{email})"}

    for term in FCUL_SEARCH_TERMS:
        cursor = "*"
        while True:
            params = {
                "filter": (
                    f"institutions.id:I141596103,"
                    f"raw_affiliation_strings.search:{term},"
                    f"{year_filter()},"
                    f"authorships.countries:CN"
                ),
                "per_page": 200,
                "cursor": cursor,
                "select": (
                    "id,doi,title,publication_year,cited_by_count,primary_topic,topics,"
                    "authorships,open_access"
                ),
            }
            try:
                resp = httpx.get(OPENALEX_WORKS_URL, params=params, headers=headers, timeout=30.0)
                if resp.status_code == 429:
                    import time
                    time.sleep(3.0)
                    continue
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break
                for w in results:
                    w_id = w["id"]
                    if w_id not in work_dict:
                        work_dict[w_id] = w

                cursor = data.get("meta", {}).get("next_cursor")
                if not cursor:
                    break
            except Exception as e:
                print(f"Fetch warning for {term}: {e}")
                break

    works = list(work_dict.values())
    with open(raw_cache, "w", encoding="utf-8") as f:
        json.dump(works, f, ensure_ascii=False, indent=2)
    return works


def extract_fcul_unit(raw_affiliations: list) -> str:
    """Identifies the prominent FCUL department or research center."""
    text = " ".join(raw_affiliations).lower()
    if "instituto dom luiz" in text or "idl" in text:
        return "Instituto Dom Luiz (IDL)"
    if "instituto de astrofísica" in text or "astrofísica e ciências do espaço" in text or "ia-lisboa" in text:
        return "Inst. de Astrofísica e Ciências do Espaço (IA)"
    if "lasige" in text:
        return "LASIGE"
    if "ce3c" in text or "ecologia, evolução" in text:
        return "Ce3C - Ecology & Evolution"
    if "bioisi" in text:
        return "BioISI - Biosystems & Integrative Sciences"
    if "física teórica" in text or "cftc" in text:
        return "CFTC - Física Teórica e Computacional"
    if "mare" in text or "ciências do mar" in text:
        return "MARE - Marine & Environmental Sciences"
    if "química estrutural" in text or "cqe" in text:
        return "Centro de Química Estrutural (CQE)"
    return "FCUL (Core Faculty / Other Depts)"


def process_publications(works: list):
    paper_rows = []
    cn_inst_stats = defaultdict(lambda: {"publications": 0, "citations": 0, "topics": Counter()})

    network_edges = Counter()
    network_nodes = {}

    fcul_authors = Counter()
    fcul_author_cits = defaultdict(int)
    fcul_author_topics = defaultdict(Counter)
    fcul_author_units = defaultdict(Counter)

    dyads = Counter()
    dyad_citations = defaultdict(int)
    dyad_topics = defaultdict(Counter)

    for w in works:
        work_id = w.get("id", "").replace("https://openalex.org/", "")
        title = w.get("title", "")
        doi = w.get("doi", "")
        citations = w.get("cited_by_count", 0)
        primary_topic = (w.get("primary_topic") or {}).get("display_name", "Unspecified")

        paper_cn_institutions = set()
        paper_fcul_units = set()
        pt_in_paper = set()
        cn_in_paper = set()
        all_authors = []

        for a in w.get("authorships", []):
            author_name = (a.get("author") or {}).get("display_name", "")
            if not author_name:
                continue
            all_authors.append(author_name)

            raw_affs = a.get("raw_affiliation_strings", [])
            aff_str = " ".join(raw_affs).lower()
            is_fcul_affiliated = any(
                term.lower() in aff_str
                for term in [
                    "faculty of science", "faculty of sciences", "faculdade de ciências",
                    "fcul", "instituto dom luiz", "lasige", "ce3c", "bioisi",
                    "cftc", "física teórica e computacional", "ciências do espaço",
                    "ia-lisboa", "campo grande"
                ]
            )
            if is_fcul_affiliated and ("lisboa" in aff_str or "lisbon" in aff_str or "portugal" in aff_str):
                unit = extract_fcul_unit(raw_affs)
                paper_fcul_units.add(unit)
                pt_in_paper.add((author_name, unit))
                fcul_authors[author_name] += 1
                fcul_author_cits[author_name] += citations
                fcul_author_topics[author_name][primary_topic] += 1
                fcul_author_units[author_name][unit] += 1

            countries = a.get("countries", [])
            inst_countries = [inst.get("country_code") for inst in a.get("institutions", [])]
            if "CN" in countries or "CN" in inst_countries:
                inst_names = [inst.get("display_name") for inst in a.get("institutions", []) if inst.get("country_code") == "CN"]
                main_inst = inst_names[0] if inst_names else "Chinese Institution"
                cn_in_paper.add((author_name, main_inst))

            for inst in a.get("institutions", []):
                if inst.get("country_code") == "CN":
                    inst_name = inst.get("display_name")
                    if inst_name:
                        paper_cn_institutions.add(inst_name)

        if not paper_fcul_units:
            paper_fcul_units.add("FCUL (Core Faculty / Other Depts)")

        # Record author dyads (FCUL Author <-> Chinese Author)
        for pt_auth, unit in pt_in_paper:
            for cn_auth, cn_inst in cn_in_paper:
                key = (pt_auth, unit, cn_auth, cn_inst)
                dyads[key] += 1
                dyad_citations[key] += citations
                dyad_topics[key][primary_topic] += 1

        # Record institution stats
        for inst in paper_cn_institutions:
            cn_inst_stats[inst]["publications"] += 1
            cn_inst_stats[inst]["citations"] += citations
            cn_inst_stats[inst]["topics"][primary_topic] += 1

        # Record network edges
        for f_unit in paper_fcul_units:
            network_nodes[f_unit] = {"country": "PT", "type": "FCUL Unit"}
            for cn_inst in paper_cn_institutions:
                network_nodes[cn_inst] = {"country": "CN", "type": "Chinese Institution"}
                edge = tuple(sorted([f_unit, cn_inst]))
                network_edges[edge] += 1

        paper_rows.append(
            {
                "OpenAlex_ID": work_id,
                "DOI": doi,
                "Title": title,
                "Year": w.get("publication_year", YEAR),
                "Citations": citations,
                "Primary_Topic": primary_topic,
                "FCUL_Units": "; ".join(sorted(paper_fcul_units)),
                "Chinese_Institutions": "; ".join(sorted(paper_cn_institutions)),
                "Authors_Count": len(all_authors),
            }
        )

    df_papers = pd.DataFrame(paper_rows)

    # DataFrame for Chinese institutions
    inst_rows = []
    total_papers = len(works)
    for inst, data in cn_inst_stats.items():
        top_topic = data["topics"].most_common(1)[0][0] if data["topics"] else "N/A"
        pct = round((data["publications"] / total_papers) * 100, 2)
        inst_rows.append(
            {
                "Institution": inst,
                "Country": "China",
                "Publications": data["publications"],
                "Percentage": pct,
                "Total_Citations": data["citations"],
                "Top_Topic": top_topic,
            }
        )
    df_institutions = pd.DataFrame(inst_rows).sort_values("Publications", ascending=False)

    edge_rows = [
        {"Source": u, "Target": v, "Weight": w} for (u, v), w in network_edges.items()
    ]
    df_edges = pd.DataFrame(edge_rows).sort_values("Weight", ascending=False)

    node_rows = [
        {"Node": k, "Country": v["country"], "Type": v["type"]}
        for k, v in network_nodes.items()
    ]
    df_nodes = pd.DataFrame(node_rows)

    # Top FCUL scientists DataFrame
    sci_rows = []
    for auth, cnt in fcul_authors.most_common(50):
        unit = fcul_author_units[auth].most_common(1)[0][0]
        top_topic = fcul_author_topics[auth].most_common(1)[0][0] if fcul_author_topics[auth] else "N/A"
        sci_rows.append(
            {
                "Scientist": auth,
                "Affiliation_Unit": unit,
                "Joint_Papers_With_China": cnt,
                "Total_Citations": fcul_author_cits[auth],
                "Primary_Research_Topic": top_topic,
            }
        )
    df_scientists = pd.DataFrame(sci_rows)

    # Scientist dyads DataFrame
    dyad_rows = []
    for (pt_auth, unit, cn_auth, cn_inst), cnt in dyads.most_common(100):
        top_topic = dyad_topics[(pt_auth, unit, cn_auth, cn_inst)].most_common(1)[0][0]
        dyad_rows.append(
            {
                "FCUL_Scientist": pt_auth,
                "FCUL_Unit": unit,
                "Chinese_Scientist": cn_auth,
                "Chinese_Institution": cn_inst,
                "Joint_Publications": cnt,
                "Total_Citations": dyad_citations[(pt_auth, unit, cn_auth, cn_inst)],
                "Primary_Topic": top_topic,
            }
        )
    df_dyads = pd.DataFrame(dyad_rows)

    return df_papers, df_institutions, df_nodes, df_edges, df_scientists, df_dyads


def generate_plots(df_institutions: pd.DataFrame, df_edges: pd.DataFrame, df_nodes: pd.DataFrame, total_papers: int):
    sns.set_theme(style="whitegrid", font="sans-serif")

    # -------------------------------------------------------------
    # Figure 1: Horizontal Bar Chart of Top Chinese Institutions
    # -------------------------------------------------------------
    top_inst = df_institutions.head(15).iloc[::-1]

    fig, ax = plt.subplots(figsize=(12, 7.5))
    bars = ax.barh(
        top_inst["Institution"],
        top_inst["Publications"],
        color="#c0392b",
        edgecolor="#78281f",
        linewidth=1.0,
        height=0.68,
    )

    for bar, pct in zip(bars, top_inst["Percentage"]):
        w = bar.get_width()
        ax.text(
            w + 0.25,
            bar.get_y() + bar.get_height() / 2,
            f"{int(w)} ({pct:.1f}%)",
            va="center",
            ha="left",
            fontsize=9.5,
            fontweight="bold",
            color="#2c3e50",
        )

    ax.set_title(
        f"Top Chinese Institutions Collaborating with FCUL & Research Units (Year {YEAR_LABEL}, Total = {total_papers} Papers)",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Number of Co-Authored Publications", fontsize=11, fontweight="bold")
    ax.set_ylabel("Chinese Partner Institution", fontsize=11, fontweight="bold")
    ax.set_xlim(0, max(top_inst["Publications"]) + 3.0)
    plt.tight_layout()

    fig1_pdf = os.path.join(FIGURES_DIR, "Figure_1_top_chinese_institutions.pdf")
    fig1_png = os.path.join(FIGURES_DIR, "Figure_1_top_chinese_institutions.png")
    fig.savefig(fig1_pdf, dpi=300)
    fig.savefig(fig1_png, dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 2: Co-authorship Bipartite Network Graph
    # -------------------------------------------------------------
    top_inst_names = set(df_institutions.head(20)["Institution"])
    filtered_edges = df_edges[
        df_edges["Source"].isin(top_inst_names) | df_edges["Target"].isin(top_inst_names)
    ]

    G = nx.Graph()
    for _, r in filtered_edges.iterrows():
        G.add_edge(r["Source"], r["Target"], weight=r["Weight"])

    node_meta = df_nodes.set_index("Node").to_dict(orient="index")
    colors = []
    sizes = []

    for n in G.nodes():
        meta = node_meta.get(n, {"Country": "Unknown"})
        if meta.get("Country") == "PT":
            colors.append("#2980b9")  # Royal Blue for FCUL Units
            sizes.append(1500)
        else:
            colors.append("#e74c3c")  # Crimson Red for Chinese Institutions
            deg = sum(d["weight"] for _, _, d in G.edges(n, data=True))
            sizes.append(380 + deg * 70)

    fig, ax = plt.subplots(figsize=(16, 12))
    pos = nx.spring_layout(G, k=0.85, iterations=70, seed=42)

    weights = [min(G[u][v]["weight"] * 1.2, 5.0) for u, v in G.edges()]
    nx.draw_networkx_edges(
        G, pos, ax=ax, width=weights, alpha=0.5, edge_color="#7f8c8d"
    )

    nx.draw_networkx_nodes(
        G, pos, ax=ax, node_color=colors, node_size=sizes, edgecolors="#2c3e50", linewidths=1.2
    )

    labels = {n: n for n in G.nodes()}
    nx.draw_networkx_labels(
        G,
        pos,
        labels=labels,
        ax=ax,
        font_size=8.5,
        font_family="sans-serif",
        font_weight="bold",
    )

    legend_elements = [
        plt.Line2D([0], [0], marker="o", color="w", label="FCUL Departments & Research Centers",
                   markerfacecolor="#2980b9", markersize=12),
        plt.Line2D([0], [0], marker="o", color="w", label="Chinese Collaborating Institutions",
                   markerfacecolor="#e74c3c", markersize=10),
    ]
    ax.legend(handles=legend_elements, loc="upper right", frameon=True, fontsize=11)
    ax.set_title(
        f"FCUL & Research Units - China Co-Authorship Network ({YEAR_LABEL}, N = {total_papers} Papers)",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.axis("off")
    plt.tight_layout()

    fig2_pdf = os.path.join(FIGURES_DIR, "Figure_2_coauthorship_network.pdf")
    fig2_png = os.path.join(FIGURES_DIR, "Figure_2_coauthorship_network.png")
    fig.savefig(fig2_pdf, dpi=300)
    fig.savefig(fig2_png, dpi=300)
    plt.close(fig)


def generate_latex_table(df_institutions: pd.DataFrame):
    top12 = df_institutions.head(12)
    tex_path = os.path.join(TABLES_DIR, "tab_top_chinese_institutions.tex")

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{Top Chinese Collaborating Institutions with FCUL and Associated Research Units (Year {YEAR_LABEL})}}",
        rf"\label{{tab:fcul_china_institutions_{YEAR_SLUG}}}",
        r"\begin{tabular}{lrrr}",
        r"\hline",
        r"\textbf{Institution} & \textbf{Co-authored Papers} & \textbf{Share (\%)} & \textbf{Citations} \\",
        r"\hline",
    ]

    for _, row in top12.iterrows():
        name = row["Institution"].replace("&", r"\&")
        pubs = row["Publications"]
        pct = f"{row['Percentage']:.1f}\\%"
        cits = row["Total_Citations"]
        lines.append(f"{name} & {pubs} & {pct} & {cits} \\\\")

    lines.extend([
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
    ])

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main(year: int = YEAR, years=None):
    configure_year(year, years)
    setup_directories()
    print(f"Fetching comprehensive {YEAR_LABEL} FCUL + research units co-authored publications with China from OpenAlex...")
    works = fetch_all_fcul_china_works()
    print(f"Total retrieved unique publications: {len(works)}")

    if not works:
        print("No works retrieved.")
        return

    df_papers, df_institutions, df_nodes, df_edges, df_scientists, df_dyads = process_publications(works)

    # Save CSVs
    papers_csv = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_papers.csv")
    inst_csv = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_chinese_institutions.csv")
    nodes_csv = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_network_nodes.csv")
    edges_csv = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_network_edges.csv")
    scientists_csv = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_top_scientists.csv")
    dyads_csv = os.path.join(DATA_DIR, f"fcul_china_{YEAR_SLUG}_scientist_dyads.csv")

    df_papers.to_csv(papers_csv, index=False)
    df_institutions.to_csv(inst_csv, index=False)
    df_nodes.to_csv(nodes_csv, index=False)
    df_edges.to_csv(edges_csv, index=False)
    df_scientists.to_csv(scientists_csv, index=False)
    df_dyads.to_csv(dyads_csv, index=False)

    print(f"Saved papers CSV to: {papers_csv}")
    print(f"Saved institutions CSV to: {inst_csv}")
    print(f"Saved network nodes and edges to: {nodes_csv}, {edges_csv}")
    print(f"Saved scientists CSV to: {scientists_csv}")
    print(f"Saved scientist dyads CSV to: {dyads_csv}")

    # Generate figures
    generate_plots(df_institutions, df_edges, df_nodes, len(works))
    print(f"Generated Figure 1 & Figure 2 in {FIGURES_DIR}")

    # Generate LaTeX table
    generate_latex_table(df_institutions)
    print(f"Generated LaTeX table in {TABLES_DIR}/tab_top_chinese_institutions.tex")

    print("\n" + "=" * 80)
    print(f"TOP 10 FCUL SCIENTISTS COLLABORATING WITH CHINA ({YEAR_LABEL})")
    print("=" * 80)
    print(df_scientists.head(10).to_string(index=False))

    print("\n" + "=" * 80)
    print("TOP 10 CO-AUTHORSHIP DYADS (FCUL SCIENTIST <---> CHINESE SCIENTIST)")
    print("=" * 80)
    print(df_dyads.head(10)[["FCUL_Scientist", "FCUL_Unit", "Chinese_Scientist", "Chinese_Institution", "Joint_Publications", "Primary_Topic"]].to_string(index=False))

    print("\n" + "=" * 80)
    print(f"TOP CHINESE INSTITUTIONS (FCUL & RESEARCH UNITS, {YEAR_LABEL})")
    print("=" * 80)
    print(df_institutions.head(10)[["Institution", "Publications", "Percentage", "Total_Citations", "Top_Topic"]].to_string(index=False))


def parse_year_args(parser):
    """Accepts --year YYYY, or --years YYYY YYYY[...] to pool several years."""
    parser.add_argument("--year", type=int, default=None, help="Single publication year")
    parser.add_argument("--years", type=int, nargs="+", default=None, help="Pool of publication years, e.g. --years 2024 2025")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCUL-China bibliometric analysis")
    parse_year_args(parser)
    args = parser.parse_args()
    years = args.years or ([args.year] if args.year else None)
    main(args.year or YEAR, years)
