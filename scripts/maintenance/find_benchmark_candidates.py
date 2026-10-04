import urllib.request
import json

queries = {
    "CitNetExplorer": "https://api.openalex.org/works?filter=default.search:CitNetExplorer,type:article&sort=cited_by_count:desc&per_page=5",
    "HistCite": "https://api.openalex.org/works?filter=default.search:HistCite%20bibliometric,type:article&sort=cited_by_count:desc&per_page=5",
    "Gephi": "https://api.openalex.org/works?filter=default.search:Gephi%20bibliometric%20co-authorship,type:article&sort=cited_by_count:desc&per_page=5",
    "Bibexcel": "https://api.openalex.org/works?filter=default.search:Bibexcel%20bibliometric,type:article&sort=cited_by_count:desc&per_page=5"
}

for tool, url in queries.items():
    print(f"\n=== Top Candidate Benchmark Papers for {tool} ===")
    req = urllib.request.Request(url, headers={"User-Agent": "mailto:john@example.com"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            for r in results:
                title = r.get("title", "")
                doi = r.get("doi", "").replace("https://doi.org/", "")
                year = r.get("publication_year", "")
                cites = r.get("cited_by_count", 0)
                source = r.get("primary_location", {}).get("source", {}).get("display_name", "") if r.get("primary_location") and r.get("primary_location").get("source") else ""
                print(f"- DOI: {doi} | Year: {year} | Cites: {cites} | Journal: {source}")
                print(f"  Title: {title}")
    except Exception as e:
        print(f"Error fetching {tool}: {e}")
