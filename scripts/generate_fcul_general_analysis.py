#!/usr/bin/env python3
"""
FCUL - General All Partnerships Bibliometric Analysis (default year 2023, selectable via --year).
Extracts all international publications for FCUL and its research units across all countries.
Produces CSVs, BERTopic clusters, high-resolution figures, and LaTeX table snippets.
"""

import argparse
import json
import os
import re
import time
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
OUTPUT_DIR = f"outputs/fcul_general_{YEAR}"
INCLUDE_INSTITUTE_PASS = False
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")


def configure_year(year: int, years=None):
    """Binds all module-level paths to the requested publication year(s).

    `years` allows pooling several publication years into one combined report,
    e.g. (2024, 2025) -> outputs/fcul_general_2024_2025.
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
    OUTPUT_DIR = f"outputs/fcul_general_{YEAR_SLUG}"
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

# ---------------------------------------------------------------------------
# Institute-name pass
# ---------------------------------------------------------------------------
# OpenAlex only links a work to institutions.id:I141596103 when the raw
# affiliation resolves to FCUL. Papers that list only an institute name
# (e.g. "Instituto Dom Luiz (IDL), Campo Grande, Lisboa") are therefore
# dropped by the institution-ID filter even though the institute sits at FCUL.
# This pass queries each institute name WITHOUT the institution-ID filter and
# keeps only works that also carry a positive FCUL signal and no non-FCUL
# branch marker.
INSTITUTE_PASS_TERMS = [
    "Instituto Dom Luiz",
    "LASIGE",
    "Ce3C",
    "Centro de Química Estrutural",
    "BioISI",
]

# A work must contain one of these to count as FCUL-affiliated
FCUL_POSITIVE_MARKERS = [
    "fcul",
    "faculdade de ciencias da universidade de lisboa",
    "faculdade de ciências da universidade de lisboa",
    "faculdade de ciências, universidade de lisboa",
    "faculdade de ciencias, universidade de lisboa",
    "faculty of sciences of the university of lisbon",
    "faculty of sciences, university of lisbon",
    "campo grande",
    "1749-016 lisboa",
    "1749-016 lisbon",
    "edificio c1",
    "edifício c1",
    "ed. c1",
    "c1, piso",
    # FCUL institutional email domain is an unambiguous affiliation signal
    "@fc.ul.pt",
    "fc.ul.pt",
]

# Generic faculty names that are NOT sufficient on their own (shared by other
# Portuguese universities, e.g. FCT-UNL, FCT-UC)
FCUL_WEAK_MARKERS = [
    "faculdade de ciencias",
    "faculdade de ciências",
    "faculty of sciences",
    "faculty of science",
]

# Branches/units that are NOT FCUL even though they share the institute name
FCUL_NEGATIVE_MARKERS = [
    "azores",
    "açores",
    "acores",
    "azorean",
    "universidade dos acores",
    "universidade dos açores",
    "utad",
    "tras-os-montes",
    "trás-os-montes",
    "universidade de aveiro",
    "universidade do porto",
    "universidade de coimbra",
    "universidade do minho",
    "universidade nova",
    "nova de lisboa",
    "universidade aberta",
    "iscte",
    "universidade de évora",
    "universidade de evora",
    "universidade do algarve",
    "beira interior",
    "universidade de trás-os-montes",
    "isel",
    "instituto superior de engenharia de lisboa",
    "politecnico",
    "politécnico",
    "polo de lisboa",  # ambiguous branch marker, rejected conservatively
]

FCUL_UNIT_PATTERNS = {
    "IDL (Instituto Dom Luiz)": [r"dom luiz", r"\bidl\b", r"instituto d\.? luiz"],
    "LASIGE (Computer Science)": [r"lasige", r"large-scale informatics systems"],
    "BioISI (Biosystems & Integrative Sciences)": [r"bioisi", r"biosystems"],
    "CQE (Centro de Química Estrutural - FCUL)": [r"centro de qu[ií]mica estrutural", r"\bcqe\b"],
    "Ce3C (Ecology, Evolution & Env Changes)": [r"ce3c", r"ecology, evolution and environmental"],
    "IA (Astrofísica e Ciências do Espaço)": [r"astrof[ií]sica e ci[êe]ncias do espa[çc]o", r"\bia\b"],
    "CFTC (Física Teórica e Computacional)": [r"cftc", r"f[ií]sica te[óo]rica e computacional"],
    "MARE (Marine and Environmental Sciences)": [r"mare\b", r"marine and environmental sciences centre"],
    "LIP (Laboratório de Instrumentação e Física Experimental)": [r"\blip\b", r"instrumenta[çc][ãa]o e f[ií]sica experimental"],
}


def setup_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)


def get_api_key():
    key = os.environ.get("OPENALEX_API_KEY")
    if not key and os.path.exists("/run/user/1000/credentials/api_keys.env"):
        try:
            with open("/run/user/1000/credentials/api_keys.env") as f:
                for line in f:
                    if "OPENALEX_API_KEY" in line:
                        parts = line.strip().split("=", 1)
                        if len(parts) == 2:
                            key = parts[1].strip("\"'").replace("export ", "").strip()
        except Exception:
            pass
    return key or "fOvMSxcGXG2QbrrHOozDwJ"


def year_filter() -> str:
    """OpenAlex publication_year filter, supporting pooled year ranges."""
    return "publication_year:" + "|".join(str(y) for y in YEARS)


def _raw_affiliation_blob(work: dict) -> str:
    """Concatenate every raw affiliation string on the work, lowercased."""
    parts = []
    for authorship in work.get("authorships") or []:
        for raw in authorship.get("raw_affiliation_strings") or []:
            parts.append(raw)
    return " ".join(parts).lower()


def is_fcul_affiliated_work(work: dict, institute_terms=None) -> bool:
    """Decide whether an institute-pass hit is genuinely FCUL.

    The check is per-author: the SAME author must list the target institute and
    an explicit FCUL signal, and must not list a non-FCUL branch or university.
    This avoids accepting a paper because some unrelated co-author happens to be
    at a "Faculty of Sciences" elsewhere.
    """
    terms = [t.lower() for t in (institute_terms or INSTITUTE_PASS_TERMS)]

    for authorship in work.get("authorships") or []:
        raw_strings = [r.lower() for r in (authorship.get("raw_affiliation_strings") or [])]
        if not raw_strings:
            continue
        joined = " ".join(raw_strings)

        # author must actually be at one of the target institutes
        if not any(term in joined for term in terms):
            continue

        # reject non-FCUL branches / other universities FIRST, so that a generic
        # "faculty of sciences" at Coimbra or FCT-UNL can never be accepted
        if any(marker in joined for marker in FCUL_NEGATIVE_MARKERS):
            continue

        # require a strong FCUL signal on this same author
        if any(marker in joined for marker in FCUL_POSITIVE_MARKERS):
            return True

        # generic faculty name alone is only accepted if Lisbon is also named
        if any(marker in joined for marker in FCUL_WEAK_MARKERS) and (
            "lisboa" in joined or "lisbon" in joined
        ):
            return True

    return False


def fetch_institute_pass(work_dict: dict, api_key, headers: dict) -> dict:
    """Query each institute name without the FCUL institution-ID filter.

    Keeps only works whose raw affiliations carry an explicit FCUL signal and
    no non-FCUL branch marker. This closes the gap where OpenAlex fails to link
    an institute-only affiliation (e.g. "Instituto Dom Luiz, Campo Grande")
    back to institutions.id:I141596103.
    """
    added_total = 0
    rejected_total = 0

    for term in INSTITUTE_PASS_TERMS:
        cursor = "*"
        added_term = 0
        checked_term = 0
        while True:
            params = {
                "filter": (
                    f"raw_affiliation_strings.search:{term},"
                    f"{year_filter()},"
                    "countries_distinct_count:>1,"
                    "institutions.id:!I141596103"
                ),
                "per_page": 200,
                "cursor": cursor,
                "api_key": api_key,
                "select": "id,doi,title,publication_year,cited_by_count,primary_topic,topics,authorships,open_access",
            }
            try:
                resp = httpx.get(OPENALEX_WORKS_URL, params=params, headers=headers, timeout=35.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                print(f"  Institute pass warning for '{term}': {exc}")
                break

            results = data.get("results") or []
            if not results:
                break

            for work in results:
                checked_term += 1
                work_id = work.get("id")
                if not work_id or work_id in work_dict:
                    continue
                if is_fcul_affiliated_work(work, [term]):
                    work_dict[work_id] = work
                    added_term += 1
                else:
                    rejected_total += 1

            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break

        added_total += added_term
        print(
            f"  Institute '{term}': {checked_term} candidates, "
            f"{added_term} FCUL-confirmed (running unique total: {len(work_dict)})"
        )

    print(
        f"Institute pass complete: {added_total} works added, "
        f"{rejected_total} rejected as non-FCUL branches"
    )
    return work_dict


def fetch_all_fcul_general_works() -> list:
    raw_cache = os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_raw_works.json")
    if os.path.exists(raw_cache) and os.path.getsize(raw_cache) > 10000:
        with open(raw_cache, "r", encoding="utf-8") as f:
            works = json.load(f)
            print(f"Loaded {len(works)} works from cache: {raw_cache}")
            return works

    work_dict = {}
    api_key = get_api_key()
    headers = {"User-Agent": "OpenSciencePipe/1.0 (mailto:scholar@opensciencepipe.org)"}
    print(f"Fetching all {YEAR_LABEL} international publications for FCUL across all countries...")

    for term in FCUL_SEARCH_TERMS:
        cursor = "*"
        fetched_term = 0
        while True:
            params = {
                "filter": (
                    f"institutions.id:I141596103,"
                    f"raw_affiliation_strings.search:{term},"
                    f"{year_filter()},"
                    f"countries_distinct_count:>1"
                ),
                "per_page": 200,
                "cursor": cursor,
                "api_key": api_key,
                "select": "id,doi,title,publication_year,cited_by_count,primary_topic,topics,authorships,open_access",
            }
            try:
                resp = httpx.get(OPENALEX_WORKS_URL, params=params, headers=headers, timeout=35.0)
                if resp.status_code == 429:
                    print("OpenAlex 429 received, backing off 3s...")
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
                        fetched_term += 1

                cursor = data.get("meta", {}).get("next_cursor")
                if not cursor or len(results) < 200:
                    break
                time.sleep(0.1)
            except Exception as e:
                print(f"Fetch warning for term '{term}': {e}")
                break
        print(f"  Term '{term}': {fetched_term} unique works (Running unique total: {len(work_dict)})")

    if INCLUDE_INSTITUTE_PASS:
        print("\nRunning institute-name pass (institutes without FCUL institution link)...")
        work_dict = fetch_institute_pass(work_dict, api_key, headers)

    works = list(work_dict.values())
    with open(raw_cache, "w", encoding="utf-8") as f:
        json.dump(works, f, ensure_ascii=False, indent=2)
    print(f"Total unique FCUL international works saved to cache: {len(works)}")
    return works


def identify_fcul_units(raw_strings: list) -> list:
    units = set()
    for raw in raw_strings:
        raw_l = raw.lower()
        matched = False
        for unit_name, patterns in FCUL_UNIT_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, raw_l):
                    units.add(unit_name)
                    matched = True
                    break
        if not matched and ("faculdade de ciências" in raw_l or "faculty of science" in raw_l or "fcul" in raw_l):
            units.add("FCUL (Core Faculty / Other Depts)")
    if not units:
        units.add("FCUL (Core Faculty / Other Depts)")
    return sorted(list(units))


def parse_and_process_dataset(works: list):
    papers = []
    country_counts = Counter()
    partner_institutions = defaultdict(lambda: {"publications": 0, "citations": 0, "country": "Unknown", "topics": Counter()})
    fcul_scientists = defaultdict(lambda: {"name": "", "publications": 0, "citations": 0, "units": set(), "partner_countries": set(), "partner_institutions": set()})
    scientist_dyads = defaultdict(lambda: {"fcul_author": "", "partner_author": "", "partner_country": "", "partner_institution": "", "joint_papers": 0, "joint_citations": 0, "topics": Counter()})

    for w in works:
        w_id = w.get("id")
        title = w.get("title") or "Untitled Publication"
        doi = w.get("doi") or ""
        citations = w.get("cited_by_count", 0)
        primary_topic = w.get("primary_topic", {}).get("display_name") if w.get("primary_topic") else "General Science"
        topics_list = [t.get("display_name") for t in w.get("topics", []) if t.get("display_name")]

        fcul_authors = []
        partner_authors = []
        paper_countries = set()
        paper_fcul_units = set()

        for a in w.get("authorships", []):
            author_obj = a.get("author", {})
            author_id = author_obj.get("id")
            author_name = author_obj.get("display_name") or "Unknown"
            raw_affils = a.get("raw_affiliation_strings", [])
            insts = a.get("institutions", [])
            countries = a.get("countries", [])

            is_fcul = False
            for inst in insts:
                if inst.get("id") == "https://openalex.org/I141596103":
                    for raw in raw_affils:
                        raw_l = raw.lower()
                        if any(t.lower() in raw_l for t in ["ciência", "science", "idl", "lasige", "ce3c", "bioisi", "cftc", "ia", "cqe", "mare", "lip"]):
                            is_fcul = True
                            break
                    if not is_fcul and len(insts) == 1:
                        is_fcul = True

            if is_fcul:
                units = identify_fcul_units(raw_affils)
                paper_fcul_units.update(units)
                fcul_authors.append({"id": author_id, "name": author_name, "units": units})
            else:
                for c in countries:
                    if c != "PT":
                        paper_countries.add(c)
                inst_name = insts[0].get("display_name") if insts else (raw_affils[0] if raw_affils else "Foreign Institution")
                inst_country = countries[0] if countries else "International"
                partner_authors.append({
                    "id": author_id,
                    "name": author_name,
                    "institution": inst_name,
                    "country": inst_country
                })

        for c in paper_countries:
            country_counts[c] += 1

        for pa in partner_authors:
            iname = pa["institution"]
            partner_institutions[iname]["publications"] += 1
            partner_institutions[iname]["citations"] += citations
            partner_institutions[iname]["country"] = pa["country"]
            if primary_topic:
                partner_institutions[iname]["topics"][primary_topic] += 1

        for fa in fcul_authors:
            fid = fa["id"] or fa["name"]
            fcul_scientists[fid]["name"] = fa["name"]
            fcul_scientists[fid]["publications"] += 1
            fcul_scientists[fid]["citations"] += citations
            fcul_scientists[fid]["units"].update(fa["units"])
            for pa in partner_authors:
                fcul_scientists[fid]["partner_countries"].add(pa["country"])
                fcul_scientists[fid]["partner_institutions"].add(pa["institution"])

        lead_fcul = fcul_authors[:2] if fcul_authors else []
        lead_partner = partner_authors[:2] if partner_authors else []
        for fa in lead_fcul:
            for pa in lead_partner:
                if pa["country"] != "PT":
                    dyad_key = (fa["name"], pa["name"], pa["institution"])
                    scientist_dyads[dyad_key]["fcul_author"] = fa["name"]
                    scientist_dyads[dyad_key]["partner_author"] = pa["name"]
                    scientist_dyads[dyad_key]["partner_country"] = pa["country"]
                    scientist_dyads[dyad_key]["partner_institution"] = pa["institution"]
                    scientist_dyads[dyad_key]["joint_papers"] += 1
                    scientist_dyads[dyad_key]["joint_citations"] += citations
                    if primary_topic:
                        scientist_dyads[dyad_key]["topics"][primary_topic] += 1

        papers.append({
            "OpenAlex_ID": w_id,
            "DOI": doi,
            "Title": title,
            "Year": w.get("publication_year", YEAR),
            "Citations": citations,
            "Primary_Topic": primary_topic,
            "Topics_List": "; ".join(topics_list),
            "FCUL_Units": "; ".join(sorted(list(paper_fcul_units))),
            "Partner_Countries": "; ".join(sorted(list(paper_countries))),
            "Foreign_Partners_Count": len(partner_authors),
            "FCUL_Authors_Count": len(fcul_authors)
        })

    # Save DataFrames
    df_papers = pd.DataFrame(papers)
    df_papers.to_csv(os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_papers.csv"), index=False)

    # Standard Publication Corpus for biblio-pipeline
    corpus_rows = []
    for p in papers:
        corpus_rows.append({
            "Title": p["Title"],
            "Abstract": f"Primary Focus: {p['Primary_Topic']}. Specific Themes: {p['Topics_List']}.",
            "Authors": p["FCUL_Units"],
            "Author Keywords": p["Topics_List"],
            "Index Keywords": p["Primary_Topic"],
            "Year": p.get("Year", YEAR),
            "Source title": f"FCUL Global International Collaborations {YEAR_LABEL}",
            "Affiliations": p["Partner_Countries"],
            "DOI": p["DOI"],
            "EID": p["OpenAlex_ID"],
            "References": ""
        })
    df_corpus = pd.DataFrame(corpus_rows)
    df_corpus.to_csv(os.path.join(DATA_DIR, "fcul_general_publication_corpus.csv"), index=False)

    # Top Countries
    country_rows = [{"Country": c, "Publications": cnt, "Share_Pct": round(cnt / len(papers) * 100, 1)} for c, cnt in country_counts.most_common(25)]
    df_countries = pd.DataFrame(country_rows)
    df_countries.to_csv(os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_top_countries.csv"), index=False)

    # Top Partner Institutions
    inst_rows = []
    for iname, data in partner_institutions.items():
        if iname not in ["Foreign Institution", "Unknown", "Universidade de Lisboa"]:
            top_t = data["topics"].most_common(1)[0][0] if data["topics"] else "General"
            inst_rows.append({
                "Institution": iname,
                "Country": data["country"],
                "Publications": data["publications"],
                "Citations": data["citations"],
                "Primary_Focus": top_t
            })
    df_inst = pd.DataFrame(inst_rows).sort_values(by="Publications", ascending=False).head(30)
    df_inst.to_csv(os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_partner_institutions.csv"), index=False)

    # Top FCUL Scientists
    sci_rows = []
    for fid, data in fcul_scientists.items():
        sci_rows.append({
            "Scientist": data["name"],
            "FCUL_Units": "; ".join(sorted(list(data["units"]))),
            "Publications": data["publications"],
            "Citations": data["citations"],
            "Partner_Countries_Count": len(data["partner_countries"]),
            "Partner_Institutions_Count": len(data["partner_institutions"])
        })
    df_sci = pd.DataFrame(sci_rows).sort_values(by="Publications", ascending=False).head(25)
    df_sci.to_csv(os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_top_scientists.csv"), index=False)

    # Scientist Dyads
    dyad_rows = []
    for (f_author, p_author, p_inst), data in scientist_dyads.items():
        top_t = data["topics"].most_common(1)[0][0] if data["topics"] else "General"
        dyad_rows.append({
            "FCUL_Scientist": f_author,
            "Foreign_Scientist": p_author,
            "Foreign_Institution": p_inst,
            "Country": data["partner_country"],
            "Joint_Papers": data["joint_papers"],
            "Joint_Citations": data["joint_citations"],
            "Primary_Topic": top_t
        })
    df_dyads = pd.DataFrame(dyad_rows).sort_values(by="Joint_Papers", ascending=False).head(25)
    df_dyads.to_csv(os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_scientist_dyads.csv"), index=False)

    print(f"Data processing complete: {len(df_papers)} publications, {len(df_countries)} countries, {len(df_inst)} institutions.")
    return df_papers, df_countries, df_inst, df_sci, df_dyads


def run_bertopic_clustering(df_papers: pd.DataFrame):
    print("Running BERTopic clustering on FCUL general international dataset...")
    docs = []
    for _, r in df_papers.iterrows():
        title = str(r["Title"])
        primary = str(r["Primary_Topic"])
        topics = str(r["Topics_List"])
        docs.append(f"{title}. Focus: {primary}. {topics}")

    from sklearn.feature_extraction.text import CountVectorizer
    from bertopic import BERTopic
    from umap import UMAP
    from hdbscan import HDBSCAN

    custom_stop = ["research", "study", "analysis", "using", "based", "approach", "results", "paper", "focus", "studies"]
    vectorizer = CountVectorizer(stop_words=custom_stop, min_df=2, ngram_range=(1, 2))
    umap_model = UMAP(n_components=5, n_neighbors=15, min_dist=0.0, metric="cosine", random_state=42)
    hdbscan_model = HDBSCAN(min_cluster_size=12, metric="euclidean", cluster_selection_method="eom", prediction_data=True)

    topic_model = BERTopic(
        embedding_model="all-MiniLM-L6-v2",
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        calculate_probabilities=False
    )
    topics, _ = topic_model.fit_transform(docs)
    topic_info = topic_model.get_topic_info()

    topic_rows = []
    for _, trow in topic_info.iterrows():
        t_id = trow["Topic"]
        cnt = trow["Count"]
        if t_id != -1 and cnt >= 8:
            words = [w[0] for w in topic_model.get_topic(t_id)[:5]]
            clean_name = trow["Name"].split("_", 1)[-1].replace("_", " ").title()
            topic_rows.append({
                "Topic_ID": t_id,
                "Cluster_Name": clean_name,
                "Papers": cnt,
                "Share_Pct": round(cnt / len(df_papers) * 100, 1),
                "Keywords": ", ".join(words)
            })

    df_topics = pd.DataFrame(topic_rows)
    df_topics.to_csv(os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_topics.csv"), index=False)
    df_topics.to_csv(os.path.join(DATA_DIR, "fcul_general_topics.csv"), index=False)
    print(f"Discovered {len(df_topics)} macro-thematic clusters.")
    return df_topics


def generate_visualizations(df_papers, df_countries, df_inst, df_topics):
    print("Generating high-resolution publication figures...")
    sns.set_theme(style="whitegrid", font="sans-serif")

    # Figure 1: Top Partner Countries
    plt.figure(figsize=(9, 5))
    top_c = df_countries.head(12)
    ax = sns.barplot(data=top_c, x="Publications", y="Country", palette="crest_r")
    for p in ax.patches:
        width = p.get_width()
        ax.annotate(f"{int(width):,}", (width + 3, p.get_y() + p.get_height() / 2.), va="center", fontsize=9, weight="bold")
    plt.title("Top International Partner Countries (FCUL 2023)", fontsize=13, weight="bold", pad=12)
    plt.xlabel("Joint Publications", fontsize=10, weight="bold")
    plt.ylabel("Country", fontsize=10, weight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure_top_countries.pdf"))
    plt.savefig(os.path.join(FIGURES_DIR, "figure_top_countries.png"), dpi=300)
    plt.close()

    # Figure 2: Top Global Partner Institutions
    plt.figure(figsize=(10, 6))
    top_i = df_inst.head(10).copy()
    top_i["Short_Name"] = top_i["Institution"].apply(lambda s: (s[:34] + "...") if len(s) > 36 else s)
    ax = sns.barplot(data=top_i, x="Publications", y="Short_Name", palette="mako_r")
    for p in ax.patches:
        width = p.get_width()
        ax.annotate(f"{int(width):,}", (width + 1, p.get_y() + p.get_height() / 2.), va="center", fontsize=9, weight="bold")
    plt.title("Top Global Partner Universities & Institutes (FCUL 2023)", fontsize=13, weight="bold", pad=12)
    plt.xlabel("Joint Publications", fontsize=10, weight="bold")
    plt.ylabel("Institution", fontsize=10, weight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure_top_institutions.pdf"))
    plt.savefig(os.path.join(FIGURES_DIR, "figure_top_institutions.png"), dpi=300)
    plt.close()

    # Figure 3: BERTopic Thematic Clusters
    plt.figure(figsize=(9, 5))
    top_t = df_topics.head(8).copy()
    top_t["Short_Cluster"] = top_t["Cluster_Name"].apply(lambda s: (s[:32] + "...") if len(s) > 34 else s)
    ax = sns.barplot(data=top_t, x="Papers", y="Short_Cluster", palette="viridis")
    for p in ax.patches:
        width = p.get_width()
        ax.annotate(f"{int(width):,} ({width/len(df_papers)*100:.1f}%)", (width + 1, p.get_y() + p.get_height() / 2.), va="center", fontsize=9, weight="bold")
    plt.title("BERTopic Thematic Clusters: FCUL Global Collaborations (2023)", fontsize=13, weight="bold", pad=12)
    plt.xlabel("Publications", fontsize=10, weight="bold")
    plt.ylabel("Research Theme", fontsize=10, weight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure_topic_clusters.pdf"))
    plt.savefig(os.path.join(FIGURES_DIR, "figure_topic_clusters.png"), dpi=300)
    plt.close()

    # Figure 4: FCUL Units Distribution
    unit_counts = Counter()
    for _, r in df_papers.iterrows():
        for u in str(r["FCUL_Units"]).split("; "):
            if u: unit_counts[u] += 1
    df_u = pd.DataFrame([{"Unit": u, "Publications": cnt} for u, cnt in unit_counts.most_common(9)])
    plt.figure(figsize=(9, 5))
    ax = sns.barplot(data=df_u, x="Publications", y="Unit", palette="rocket_r")
    for p in ax.patches:
        width = p.get_width()
        ax.annotate(f"{int(width):,}", (width + 2, p.get_y() + p.get_height() / 2.), va="center", fontsize=9, weight="bold")
    plt.title("International Publications by FCUL Research Unit (2023)", fontsize=13, weight="bold", pad=12)
    plt.xlabel("International Publications", fontsize=10, weight="bold")
    plt.ylabel("Research Unit", fontsize=10, weight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure_fcul_units.pdf"))
    plt.savefig(os.path.join(FIGURES_DIR, "figure_fcul_units.png"), dpi=300)
    plt.close()
    print("All figures successfully saved.")


def export_latex_tables(df_papers, df_countries, df_inst, df_sci, df_dyads, df_topics):
    print("Generating bounded LaTeX tables (0 overfull warnings)...")

    # Table 1: Top Countries
    t1_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Top International Collaborating Countries (FCUL " + YEAR_LABEL + r")}",
        r"\label{tab:general_top_countries}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{C{0.08\linewidth} L{0.44\linewidth} R{0.22\linewidth} R{0.18\linewidth}}",
        r"\toprule",
        r"\textbf{Rank} & \textbf{Country} & \textbf{Publications} & \textbf{Share (\%)} \\",
        r"\midrule",
    ]
    for i, (_, row) in enumerate(df_countries.head(12).iterrows()):
        t1_lines.append(f"{i+1} & {row['Country']} & {int(row['Publications']):,} & {row['Share_Pct']}\\% \\\\")
    t1_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    with open(os.path.join(TABLES_DIR, "tab_top_countries.tex"), "w") as f:
        f.write("\n".join(t1_lines))

    # Table 2: Top Partner Institutions
    t2_lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Top Global Partner Institutions Collaborating with FCUL (" + YEAR_LABEL + r")}",
        r"\label{tab:general_top_institutions}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{C{0.05\linewidth} L{0.36\linewidth} C{0.12\linewidth} R{0.10\linewidth} R{0.10\linewidth} L{0.21\linewidth}}",
        r"\toprule",
        r"\textbf{\#} & \textbf{Institution} & \textbf{Country} & \textbf{Papers} & \textbf{Citations} & \textbf{Primary Domain} \\",
        r"\midrule",
    ]
    for i, (_, row) in enumerate(df_inst.head(10).iterrows()):
        safe_inst = str(row["Institution"]).replace("&", r"\&")
        safe_topic = str(row["Primary_Focus"]).replace("&", r"\&")
        t2_lines.append(f"{i+1} & {safe_inst} & {row['Country']} & {int(row['Publications']):,} & {int(row['Citations']):,} & {safe_topic} \\\\")
    t2_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}"])
    with open(os.path.join(TABLES_DIR, "tab_top_institutions.tex"), "w") as f:
        f.write("\n".join(t2_lines))

    # Table 3: Top FCUL Scientists
    t3_lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Lead FCUL Researchers Ranked by Global International Partnerships (" + YEAR_LABEL + r")}",
        r"\label{tab:general_top_scientists}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{C{0.05\linewidth} L{0.25\linewidth} L{0.32\linewidth} R{0.11\linewidth} R{0.11\linewidth} R{0.10\linewidth}}",
        r"\toprule",
        r"\textbf{\#} & \textbf{Scientist} & \textbf{FCUL Unit(s)} & \textbf{Intl. Papers} & \textbf{Citations} & \textbf{Countries} \\",
        r"\midrule",
    ]
    for i, (_, row) in enumerate(df_sci.head(10).iterrows()):
        safe_name = str(row["Scientist"]).replace("&", r"\&")
        safe_units = str(row["FCUL_Units"]).replace("&", r"\&")
        t3_lines.append(f"{i+1} & {safe_name} & {safe_units} & {int(row['Publications']):,} & {int(row['Citations']):,} & {int(row['Partner_Countries_Count'])} \\\\")
    t3_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}"])
    with open(os.path.join(TABLES_DIR, "tab_top_scientists.tex"), "w") as f:
        f.write("\n".join(t3_lines))

    # Table 4: BERTopic Clusters
    t4_lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{BERTopic Thematic Decomposition: Global Collaboration Macro-Themes (" + YEAR_LABEL + r")}",
        r"\label{tab:general_bertopic_clusters}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{C{0.06\linewidth} L{0.26\linewidth} R{0.10\linewidth} R{0.10\linewidth} L{0.42\linewidth}}",
        r"\toprule",
        r"\textbf{ID} & \textbf{Research Theme} & \textbf{Papers} & \textbf{Share (\%)} & \textbf{c-TF-IDF Representative Keywords} \\",
        r"\midrule",
    ]
    for _, row in df_topics.head(8).iterrows():
        safe_name = str(row["Cluster_Name"]).replace("&", r"\&")
        safe_kw = str(row["Keywords"]).replace("&", r"\&")
        t4_lines.append(f"{row['Topic_ID']} & {safe_name} & {int(row['Papers']):,} & {row['Share_Pct']}\\% & {safe_kw} \\\\")
    t4_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}"])
    with open(os.path.join(TABLES_DIR, "tab_bertopic_clusters.tex"), "w") as f:
        f.write("\n".join(t4_lines))
    print("LaTeX tables exported successfully.")


def main(year: int = YEAR, years=None, include_institute_pass: bool = False):
    global INCLUDE_INSTITUTE_PASS
    INCLUDE_INSTITUTE_PASS = include_institute_pass
    configure_year(year, years)
    setup_directories()
    works = fetch_all_fcul_general_works()
    df_papers, df_countries, df_inst, df_sci, df_dyads = parse_and_process_dataset(works)
    df_topics = run_bertopic_clustering(df_papers)
    generate_visualizations(df_papers, df_countries, df_inst, df_topics)
    export_latex_tables(df_papers, df_countries, df_inst, df_sci, df_dyads, df_topics)
    print(f"\nFCUL General International {YEAR_LABEL} Analysis Complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCUL general international bibliometric analysis")
    parser.add_argument("--year", type=int, default=None, help="Single publication year")
    parser.add_argument("--years", type=int, nargs="+", default=None, help="Pool of publication years, e.g. --years 2024 2025")
    parser.add_argument("--include-institute-pass", action="store_true",
                        help="Also query institute names (IDL, LASIGE, Ce3C, CQE, BioISI) without the "
                             "FCUL institution-ID filter, keeping only works with an explicit FCUL signal")
    parser.add_argument("--force-refetch", action="store_true", help="Ignore the cached raw_works JSON")
    args = parser.parse_args()
    years = args.years or ([args.year] if args.year else None)
    if args.force_refetch:
        configure_year(args.year or YEAR, years)
        cache = os.path.join(DATA_DIR, f"fcul_general_{YEAR_SLUG}_raw_works.json")
        if os.path.exists(cache):
            os.remove(cache)
            print(f"Removed cache {cache}")
    main(args.year or YEAR, years, include_institute_pass=args.include_institute_pass)
