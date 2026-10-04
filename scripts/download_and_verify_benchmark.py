import os
import sys
import re
import json
import argparse
import difflib
import httpx
import asyncio
from typing import Dict, Any, Optional

try:
    import pymupdf as fitz
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[^\w\s]', ' ', str(text).lower())
    return " ".join(text.split())

def string_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

async def resolve_metadata_crossref(doi: str, email: str = "test@example.com") -> Optional[Dict[str, Any]]:
    clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
    url = f"https://api.crossref.org/works/{clean_doi}"
    headers = {"User-Agent": f"BibliometricBenchmark/1.0 (mailto:{email})"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                titles = msg.get("title", [])
                title = titles[0] if titles else ""
                authors_list = [f"{a.get('family', '')}, {a.get('given', '')}".strip() for a in msg.get("author", [])]
                year = None
                if "published-print" in msg:
                    parts = msg["published-print"].get("date-parts", [[]])[0]
                    if parts: year = parts[0]
                elif "published-online" in msg:
                    parts = msg["published-online"].get("date-parts", [[]])[0]
                    if parts: year = parts[0]
                return {
                    "doi": clean_doi,
                    "title": title,
                    "authors": "; ".join(authors_list),
                    "year": year,
                    "abstract": msg.get("abstract", "")
                }
    except Exception as e:
        print(f">>> [WARN] Crossref lookup failed: {e}")
    return None

async def download_oa_pdf(doi: str, output_path: str, email: str = "test@example.com") -> Optional[str]:
    clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
    
    # 1. Unpaywall
async def download_oa_pdf(doi: str, output_path: str, email: str = "john@example.com") -> Optional[str]:
    clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
    
    # 1. Direct Publisher Patterns
    direct_urls = []
    if "3389/" in clean_doi:  # Frontiers
        direct_urls.append(f"https://www.frontiersin.org/articles/{clean_doi}/pdf")
    elif "1371/journal." in clean_doi:  # PLOS
        parts = clean_doi.split("journal.")
        journal_sub = parts[1].split(".")[0] if len(parts) > 1 else ""
        if journal_sub == "pdig":
            direct_urls.append(f"https://journals.plos.org/digitalhealth/article/file?id={clean_doi}&type=printable")
        elif journal_sub == "pone":
            direct_urls.append(f"https://journals.plos.org/plosone/article/file?id={clean_doi}&type=printable")
    elif "3390/" in clean_doi:  # MDPI
        direct_urls.append(f"https://www.mdpi.com/{clean_doi}/pdf")
    elif "1186/" in clean_doi:  # BMC
        direct_urls.append(f"https://link.springer.com/content/pdf/{clean_doi}.pdf")
    elif "arxiv." in clean_doi.lower() or "48550/arxiv." in clean_doi.lower():
        m = re.search(r'([0-9]{4}\.[0-9]{4,5})', clean_doi)
        if m:
            direct_urls.append(f"https://arxiv.org/pdf/{m.group(1)}.pdf")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for d_url in direct_urls:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(d_url, headers=headers)
                if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path
        except Exception:
            pass

    # 2. Unpaywall
    unpaywall_url = f"https://api.unpaywall.org/v2/{clean_doi}?email={email}"
    pdf_url = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(unpaywall_url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("is_oa") and data.get("best_oa_location"):
                    pdf_url = data["best_oa_location"].get("url_for_pdf")
    except Exception:
        pass

    # 3. OpenAlex fallback
    if not pdf_url:
        try:
            oa_url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(oa_url, headers={"User-Agent": f"mailto:{email}"})
                if resp.status_code == 200:
                    data = resp.json()
                    best_oa = data.get("best_oa_location", {}) or {}
                    pdf_url = best_oa.get("pdf_url")
        except Exception:
            pass

    if pdf_url:
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(pdf_url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 1024:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path
                elif resp.status_code == 429:
                    print(f"\n[RATE LIMIT] Open-Access PDF host returned HTTP 429 Too Many Requests. Quota exceeded; please wait up to 24h.")
        except Exception as e:
            print(f">>> [WARN] PDF download error: {e}")
    else:
        print(f"\n[INFO] Open-access PDF could not be resolved from unpaywall/OpenAlex/publisher endpoints. If daily quota was hit, retry in 24 hours.")
    return None

def extract_pdf_header_text(pdf_path: str) -> Dict[str, Any]:
    if not HAS_PYMUPDF:
        return {"error": "PyMuPDF not installed on host. Text extraction skipped."}
    
    doc = fitz.open(pdf_path)
    if len(doc) == 0:
        return {}
    first_page = doc[0].get_text()
    meta = doc.metadata
    return {
        "page_count": len(doc),
        "pdf_meta_title": meta.get("title", ""),
        "pdf_meta_author": meta.get("author", ""),
        "first_page_snippet": first_page[:600]
    }

async def main():
    parser = argparse.ArgumentParser(description="Download Reference PDF and Verify Metadata Concordance")
    parser.add_argument("--doi", type=str, required=True, help="Target Paper DOI")
    parser.add_argument("--expected-title", type=str, help="Expected paper title for concordance check")
    parser.add_argument("--output-dir", type=str, default="benchmark_references", help="Directory to save downloaded PDF and metadata")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", args.doi.strip())
    safe_name = re.sub(r'[^\w\-]', '_', clean_doi)
    pdf_dest = os.path.join(args.output_dir, f"{safe_name}.pdf")
    meta_dest = os.path.join(args.output_dir, f"{safe_name}_meta.json")

    print("=" * 70)
    print(f">>> BENCHMARK VERIFICATION & DOWNLOAD TOOL")
    print(f">>> DOI: {clean_doi}")
    print("=" * 70)

    print(">>> 1. Querying Crossref / OpenAlex Metadata...")
    meta = await resolve_metadata_crossref(clean_doi)
    if not meta:
        print(">>> [ERROR] Could not resolve metadata via Crossref.")
        return

    print(f"    - Title:   {meta['title']}")
    print(f"    - Authors: {meta['authors']}")
    print(f"    - Year:    {meta['year']}")

    if args.expected_title:
        sim = string_similarity(args.expected_title, meta['title'])
        print(f"\n>>> Title Concordance Score: {sim * 100:.1f}%")
        if sim >= 0.80:
            print("    [MATCH] Title matches expected benchmark definition.")
        else:
            print(f"    [WARNING] Title discrepancy detected!")
            print(f"    Expected: {args.expected_title}")
            print(f"    Received: {meta['title']}")

    print("\n>>> 2. Attempting Open-Access PDF Download...")
    downloaded = await download_oa_pdf(clean_doi, pdf_dest)
    if downloaded and os.path.exists(pdf_dest):
        size_kb = os.path.getsize(pdf_dest) / 1024
        print(f"    [SUCCESS] Downloaded PDF: {pdf_dest} ({size_kb:.1f} KB)")
        
        pdf_info = extract_pdf_header_text(pdf_dest)
        meta["pdf_validation"] = pdf_info
        if "first_page_snippet" in pdf_info:
            print(f"    - PDF Total Pages: {pdf_info.get('page_count')}")
    else:
        print("    [INFO] Direct Open-Access PDF link not publicly available for this DOI.")

    with open(meta_dest, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4)
    print(f"\n>>> Metadata saved to: {meta_dest}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
