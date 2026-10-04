import os
import glob
import json
import re
import urllib.request

def fetch_openalex_details():
    benchmarks_dir = "data/benchmarks"
    b_files = sorted(glob.glob(os.path.join(benchmarks_dir, "*.json")))
    b_files = [f for f in b_files if not f.endswith("benchmark_template.json")]
    
    tools = [
        "VOSviewer", "CiteSpace", "Bibliometrix", "biblioshiny", "SciMAT",
        "CitNetExplorer", "HistCite", "Gephi", "Pajek", "Bibexcel",
        "Rayyan", "ASReview", "RevMan", "Review Manager", "metafor", "Stata", "SPSS", "CMA", "Comprehensive Meta-Analysis"
    ]
    
    known = {
        "bci_stroke_ren2024_benchmark.json": ["RevMan", "PRISMA"],
        "benchmark_asreview_cyberbullying_2022.json": ["ASReview", "PRISMA"],
        "benchmark_atmospheric_co2_bibliometrix.json": ["Bibliometrix", "biblioshiny"],
        "benchmark_biochar_citespace.json": ["CiteSpace"],
        "benchmark_blockchain_vosviewer.json": ["VOSviewer"],
        "benchmark_digital_transformation_kraus2021.json": ["VOSviewer", "Bibliometrix"],
        "benchmark_genai_education_vosviewer.json": ["VOSviewer"],
        "benchmark_manual_nosocomial_pone2023.json": ["Comprehensive Meta-Analysis", "PRISMA"],
        "benchmark_rayyan_neurodegenerative_2024.json": ["Rayyan", "PRISMA"],
        "benchmark_rent_control_econometrics.json": ["Stata", "metafor"],
        "colditz1994_bcg_meta.json": ["RevMan", "metafor"],
        "doucouliagos_stanley2009_minimum_wage_meta.json": ["Stata", "metafor"],
        "nissen2007_rosiglitazone_meta.json": ["Comprehensive Meta-Analysis", "metafor"],
        "smith_glass1977_psychotherapy_meta.json": ["SPSS", "metafor"],
    }
    
    results = {}
    for fpath in b_files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            b_data = json.load(f)
            
        doi = b_data.get("reference_doi", "")
        title = b_data.get("benchmark_title", "")
        journal = b_data.get("journal", "")
        year = b_data.get("year", "")
        
        # Check known first
        if fname in known:
            results[doi] = {
                "file": fname,
                "title": title,
                "journal": journal,
                "year": year,
                "tools": known[fname]
            }
            continue
            
        # Try fetching abstract from OpenAlex
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        req = urllib.request.Request(url, headers={"User-Agent": "mailto:john@example.com"})
        abstract_text = ""
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                # reconstruct inverted abstract
                inv = data.get("abstract_inverted_index", {})
                if inv:
                    words = [None] * (max(max(pos) for pos in inv.values()) + 1)
                    for word, positions in inv.items():
                        for pos in positions:
                            words[pos] = word
                    abstract_text = " ".join([w for w in words if w])
        except Exception as e:
            abstract_text = ""
            
        text_to_search = f"{title} {abstract_text}"
        found = []
        for t in tools:
            if re.search(r"\b" + re.escape(t) + r"\b", text_to_search, re.IGNORECASE):
                if t.lower() in ["biblioshiny"]:
                    found.append("Bibliometrix")
                elif t.lower() in ["review manager"]:
                    found.append("RevMan")
                else:
                    found.append(t)
        found = sorted(list(set(found)))
        
        results[doi] = {
            "file": fname,
            "title": title,
            "journal": journal,
            "year": year,
            "tools": found if found else ["VOSviewer/Manual"]
        }
        
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    fetch_openalex_details()
