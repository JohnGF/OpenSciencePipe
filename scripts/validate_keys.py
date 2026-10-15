import os
import sys
import httpx
import logging
from typing import Dict, Tuple

# Simple .env parser using standard library
def load_env(env_path: str = None) -> Dict[str, str]:
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    k = key.strip()
                    v = val.strip().strip('"').strip("'")
                    env_vars[k] = v
                    if k not in os.environ:
                        os.environ[k] = v
    return env_vars

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def validate_all_keys(verbose: bool = True) -> Tuple[bool, Dict[str, str]]:
    load_env()
    results = {}
    has_failure = False

    if verbose:
        print("==================================================")
        print("   Bibliometric API Credentials Validation Check  ")
        print("==================================================\n")

    oa_email = os.environ.get("OPENALEX_EMAIL")
    cr_email = os.environ.get("CROSSREF_EMAIL") or oa_email
    pm_key = os.environ.get("PUBMED_API_KEY")
    scopus_key = os.environ.get("SCOPUS_API_KEY")
    scopus_token = os.environ.get("SCOPUS_INST_TOKEN")
    ss_key = os.environ.get("SS_API_KEY")
    wos_key = os.environ.get("WOS_API_KEY")
    ieee_key = os.environ.get("IEEE_API_KEY")
    springer_key = os.environ.get("SPRINGER_API_KEY")

    # 1. OpenAlex
    if oa_email and "example.com" not in oa_email:
        url = "https://api.openalex.org/works?search=eeg&per_page=1"
        try:
            r = httpx.get(url, headers={"mailto": oa_email}, timeout=10.0)
            if r.status_code == 200:
                results["openalex"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] OpenAlex (Polite Pool: {oa_email}) -> HTTP 200 OK")
            else:
                results["openalex"] = f"WARNING ({r.status_code})"
                if verbose:
                    print(f"[WARNING] OpenAlex returned HTTP {r.status_code}")
        except Exception as e:
            results["openalex"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] OpenAlex connection error: {e}")
    else:
        results["openalex"] = "SKIPPED"
        if verbose:
            print("[INFO] OpenAlex: No email configured (unauthenticated rate limits apply).")

    # 2. Crossref
    if cr_email and "example.com" not in cr_email:
        url = "https://api.crossref.org/works?rows=1"
        try:
            headers = {"User-Agent": f"OpenSciencePipe/1.0 (mailto:{cr_email})"}
            r = httpx.get(url, headers=headers, timeout=10.0)
            if r.status_code == 200:
                results["crossref"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] Crossref (Polite Pool: {cr_email}) -> HTTP 200 OK")
            else:
                results["crossref"] = f"WARNING ({r.status_code})"
                if verbose:
                    print(f"[WARNING] Crossref returned HTTP {r.status_code}")
        except Exception as e:
            results["crossref"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] Crossref connection error: {e}")
    else:
        results["crossref"] = "SKIPPED"
        if verbose:
            print("[INFO] Crossref: No polite email configured (public rate limits apply).")

    # 3. PubMed (NCBI)
    if pm_key:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=eeg&retmode=json&retmax=1&api_key={pm_key}"
        try:
            r = httpx.get(url, timeout=10.0)
            if r.status_code == 200 and "esearchresult" in r.json():
                results["pubmed"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] PubMed (NCBI Key: {pm_key[:6]}...) -> HTTP 200 OK (10 req/s)")
            else:
                results["pubmed"] = f"FAILED ({r.status_code})"
                has_failure = True
                if verbose:
                    print(f"[FAILED] PubMed returned status {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results["pubmed"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] PubMed check error: {e}")
    else:
        results["pubmed"] = "SKIPPED"
        if verbose:
            print("[INFO] PubMed: No dedicated API key (running on public rate limits: 3 req/s).")

    # 4. Semantic Scholar
    if ss_key:
        url = "https://api.semanticscholar.org/graph/v1/paper/search?query=eeg&limit=1"
        try:
            r = httpx.get(url, headers={"x-api-key": ss_key}, timeout=10.0)
            if r.status_code == 200:
                results["semantic_scholar"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] Semantic Scholar (Key: {ss_key[:6]}...) -> HTTP 200 OK")
            else:
                results["semantic_scholar"] = f"FAILED ({r.status_code})"
                has_failure = True
                if verbose:
                    print(f"[FAILED] Semantic Scholar HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results["semantic_scholar"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] Semantic Scholar check error: {e}")
    else:
        results["semantic_scholar"] = "SKIPPED"
        if verbose:
            print("[INFO] Semantic Scholar: No dedicated API key (using public shared endpoint).")

    # 5. Elsevier Scopus
    if scopus_key:
        url = "https://api.elsevier.com/content/search/scopus"
        headers = {"Accept": "application/json", "X-ELS-APIKey": scopus_key}
        if scopus_token:
            headers["X-ELS-Insttoken"] = scopus_token
        params = {"query": "TITLE-ABS-KEY(eeg)", "count": 1}
        try:
            r = httpx.get(url, headers=headers, params=params, timeout=10.0)
            if r.status_code == 200 and "search-results" in r.json():
                total = r.json().get("search-results", {}).get("opensearch:totalResults", "N/A")
                results["scopus"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] Elsevier Scopus (Key: {scopus_key[:6]}...) -> HTTP 200 OK (Found {total} hits)")
            elif r.status_code == 401:
                results["scopus"] = "FAILED (401 Unauthorized)"
                has_failure = True
                if verbose:
                    print("[FAILED] Scopus HTTP 401 Unauthorized: Invalid API key or IP address not recognized.")
            elif r.status_code == 403:
                results["scopus"] = "FAILED (403 Forbidden)"
                has_failure = True
                if verbose:
                    print("[FAILED] Scopus HTTP 403 Forbidden: API key requires institutional token or university VPN.")
            else:
                results["scopus"] = f"WARNING ({r.status_code})"
                if verbose:
                    print(f"[WARNING] Scopus HTTP {r.status_code}: {r.text[:150]}")
        except Exception as e:
            results["scopus"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] Scopus check error: {e}")
    else:
        results["scopus"] = "SKIPPED"
        if verbose:
            print("[INFO] Elsevier Scopus: No API key configured (commercial index skipped).")

    # 6. Clarivate Web of Science (WoS)
    if wos_key:
        url = "https://api.clarivate.com/api/woslite"
        headers = {"Accept": "application/json", "X-ApiKey": wos_key}
        params = {"usrQuery": "TS=(eeg)", "count": 1, "firstRecord": 1}
        try:
            r = httpx.get(url, headers=headers, params=params, timeout=10.0)
            if r.status_code == 200:
                results["wos"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] Clarivate Web of Science (Key: {wos_key[:6]}...) -> HTTP 200 OK")
            elif r.status_code == 401:
                results["wos"] = "FAILED (401 Unauthorized)"
                has_failure = True
                if verbose:
                    print("[FAILED] Web of Science HTTP 401 Unauthorized: Invalid API key.")
            elif r.status_code == 403:
                results["wos"] = "FAILED (403 Forbidden)"
                has_failure = True
                if verbose:
                    print("[FAILED] Web of Science HTTP 403 Forbidden: Key lacks entitlements or requires institutional IP.")
            else:
                results["wos"] = f"WARNING ({r.status_code})"
                if verbose:
                    print(f"[WARNING] Web of Science HTTP {r.status_code}: {r.text[:150]}")
        except Exception as e:
            results["wos"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] Web of Science check error: {e}")
    else:
        results["wos"] = "SKIPPED"
        if verbose:
            print("[INFO] Clarivate Web of Science: No API key configured (commercial index skipped).")

    # 7. IEEE Xplore
    if ieee_key:
        url = f"https://ieeexploreapi.ieee.org/api/v1/search/articles?apikey={ieee_key}&querytext=eeg&max_records=1&format=json"
        try:
            r = httpx.get(url, timeout=10.0)
            if r.status_code == 200:
                results["ieee"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] IEEE Xplore (Key: {ieee_key[:6]}...) -> HTTP 200 OK")
            else:
                results["ieee"] = f"WARNING ({r.status_code})"
                if verbose:
                    print(f"[WARNING] IEEE Xplore HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results["ieee"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] IEEE Xplore check error: {e}")
    else:
        results["ieee"] = "SKIPPED"
        if verbose:
            print("[INFO] IEEE Xplore: No API key (IEEE papers covered via OpenAlex/Crossref indexes).")

    # 8. Springer Nature
    if springer_key:
        url = f"https://api.springernature.com/meta/v1/json?q=eeg&api_key={springer_key}&p=1"
        try:
            r = httpx.get(url, timeout=10.0)
            if r.status_code == 200:
                results["springer"] = "SUCCESS"
                if verbose:
                    print(f"[SUCCESS] Springer Nature (Key: {springer_key[:6]}...) -> HTTP 200 OK")
            else:
                results["springer"] = f"WARNING ({r.status_code})"
                if verbose:
                    print(f"[WARNING] Springer Nature HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results["springer"] = f"FAILED ({e})"
            has_failure = True
            if verbose:
                print(f"[FAILED] Springer Nature check error: {e}")
    else:
        results["springer"] = "SKIPPED"
        if verbose:
            print("[INFO] Springer Nature: No API key configured (open access metadata via OpenAlex).")

    if verbose:
        print("\nValidation complete.")
        print(f"Overall status: {'ALL CHECKS PASSED OR SKIPPED' if not has_failure else 'FAILURES DETECTED'}")

    return (not has_failure), results

if __name__ == "__main__":
    success, _ = validate_all_keys(verbose=True)
    sys.exit(0 if success else 1)
