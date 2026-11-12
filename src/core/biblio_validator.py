import os
import re
import json
import logging
import argparse
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
import pandas as pd
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


def compute_string_similarity(a: str, b: str) -> float:
    """Computes normalized fuzzy similarity ratio between two strings [0.0, 1.0]."""
    if not a or not b:
        return 0.0
    clean_a = re.sub(r"[^\w\s]", "", a.lower()).strip()
    clean_b = re.sub(r"[^\w\s]", "", b.lower()).strip()
    clean_a = " ".join(clean_a.split())
    clean_b = " ".join(clean_b.split())
    if clean_a == clean_b:
        return 1.0
    return SequenceMatcher(None, clean_a, clean_b).ratio()


def clean_doi_string(raw_doi: Optional[str]) -> Optional[str]:
    """Extracts and normalizes a standard DOI identifier."""
    if not raw_doi or pd.isna(raw_doi):
        return None
    doi_str = str(raw_doi).strip()
    doi_str = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi_str, flags=re.IGNORECASE)
    doi_str = doi_str.strip().rstrip(".").rstrip("/")
    # Basic DOI regex pattern check: 10.xxxx/...
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", doi_str)
    if m:
        return m.group(0).lower()
    return doi_str.lower() if doi_str.startswith("10.") else None


def clean_jats_abstract(raw: Optional[str]) -> str:
    """Removes XML/JATS tags and normalizes whitespace in abstracts."""
    if not raw or pd.isna(raw):
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(raw))
    return " ".join(clean.split()).strip()


def reconstruct_abstract_inverted_index(inv_index: Optional[Dict[str, List[int]]]) -> str:
    """Reconstructs full text abstract from OpenAlex abstract_inverted_index."""
    if not inv_index or not isinstance(inv_index, dict):
        return ""
    pos_map = {}
    for word, positions in inv_index.items():
        for p in positions:
            pos_map[p] = word
    return " ".join(pos_map[i] for i in sorted(pos_map.keys()))


class BiblioValidator:
    """
    Automated Bibliographic Validation and Hallucination Detection Engine.
    Verifies citations, paper titles, DOIs, metadata, study methodology,
    and benchmark ground-truth provenance against authoritative registries
    (Crossref and OpenAlex).
    """

    CROSSREF_API = "https://api.crossref.org/works"
    OPENALEX_API = "https://api.openalex.org/works"

    BIBLIOMETRIC_KEYWORDS = {
        "bibliometric", "bibliometrics", "scientometric", "scientometrics",
        "infometrics", "informetrics", "co-citation", "cocitation", "co-authorship",
        "coauthorship", "vosviewer", "citespace", "scopus", "web of science",
        "science mapping", "citation network", "bibliographic coupling",
        "bibliometrix", "scimat", "histcite", "citnetexplorer", "altmetrics",
        "altmetric", "citation analysis"
    }

    META_ANALYSIS_KEYWORDS = {
        "meta-analysis", "meta-analytic", "systematic review", "prisma",
        "forest plot", "funnel plot", "heterogeneity", "dersimonian-laird",
        "pooled effect", "cochrane", "risk ratio", "odds ratio"
    }

    def __init__(self, email: Optional[str] = None, timeout: float = 12.0):
        self.email = email or os.getenv("OPENALEX_EMAIL") or os.getenv("CROSSREF_EMAIL") or "biblio-validator@opensciencepipe.org"
        self.timeout = timeout
        self.headers = {
            "User-Agent": f"OpenSciencePipe-BiblioValidator/1.0 (mailto:{self.email})"
        }

    # --- File and Input Parsing ---

    @staticmethod
    def parse_bibtex(bib_text: str) -> List[Dict[str, Any]]:
        """Parses raw BibTeX string into structured dictionary records."""
        entries = []
        entry_pattern = re.compile(r"@(\w+)\s*\{\s*([^,]+),", re.IGNORECASE)
        field_pattern = re.compile(r'(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)"|(\d+))', re.DOTALL)

        # Split entries by top-level @entry_type{
        chunks = re.split(r"(?=@\w+\s*\{)", bib_text)
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or not chunk.startswith("@"):
                continue

            entry_match = entry_pattern.search(chunk)
            if not entry_match:
                continue

            entry_type = entry_match.group(1).lower()
            cite_key = entry_match.group(2).strip()

            fields = {
                "cite_key": cite_key,
                "entry_type": entry_type,
                "title": "",
                "author": "",
                "year": None,
                "doi": "",
                "journal": "",
                "booktitle": "",
            }

            body = chunk[entry_match.end():]
            for m in field_pattern.finditer(body):
                key = m.group(1).lower()
                val = m.group(2) or m.group(3) or m.group(4) or ""
                # Clean nested LaTeX braces and extra whitespace
                val = re.sub(r"[{}]", "", val).strip()
                val = re.sub(r"\s+", " ", val)

                if key in ["title", "author", "doi", "journal", "booktitle"]:
                    fields[key] = val
                elif key == "year":
                    try:
                        fields["year"] = int(re.search(r"\d{4}", val).group(0))
                    except Exception:
                        fields["year"] = val

            if fields["title"] or fields["doi"] or fields["cite_key"]:
                entries.append(fields)

        return entries

    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parses citations from BibTeX (.bib), CSV (.csv), JSON (.json), or text/markdown (.md, .tex, .txt)."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".bib"]:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return self.parse_bibtex(f.read())

        elif ext in [".csv", ".tsv"]:
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(file_path, sep=sep)
            entries = []
            col_map = {col.lower().strip(): col for col in df.columns}
            t_col = col_map.get("title") or col_map.get("paper_title")
            d_col = col_map.get("doi")
            a_col = col_map.get("author") or col_map.get("authors")
            y_col = col_map.get("year") or col_map.get("pub_year")
            k_col = col_map.get("id") or col_map.get("cite_key") or col_map.get("key")

            for idx, r in df.iterrows():
                entries.append({
                    "cite_key": str(r[k_col]) if k_col and pd.notnull(r[k_col]) else f"entry_{idx+1}",
                    "title": str(r[t_col]).strip() if t_col and pd.notnull(r[t_col]) else "",
                    "doi": str(r[d_col]).strip() if d_col and pd.notnull(r[d_col]) else "",
                    "author": str(r[a_col]).strip() if a_col and pd.notnull(r[a_col]) else "",
                    "year": r[y_col] if y_col and pd.notnull(r[y_col]) else None,
                })
            return entries

        elif ext in [".json"]:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("entries") or data.get("papers") or [data]

        else:
            # Fallback for plain text, markdown, or LaTeX: extract DOIs and lines
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # First extract explicit BibTeX blocks if embedded
            if "@" in content and "{" in content:
                bib_entries = self.parse_bibtex(content)
                if bib_entries:
                    return bib_entries

            # Otherwise extract embedded DOIs
            found_dois = list(set(re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", content)))
            entries = []
            for idx, doi in enumerate(found_dois):
                entries.append({
                    "cite_key": f"doi_ref_{idx+1}",
                    "doi": doi,
                    "title": "",
                    "author": "",
                    "year": None,
                })
            return entries

    # --- Verification Core ---

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=False
    )
    def query_crossref_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Queries Crossref API by DOI."""
        url = f"{self.CROSSREF_API}/{doi}"
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    item = resp.json().get("message", {})
                    titles = item.get("title", [])
                    gt_title = titles[0] if titles else ""
                    authors = item.get("author", [])
                    au_names = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors if 'family' in a]
                    
                    year = None
                    pub_parts = item.get("published-print", {}).get("date-parts") or item.get("published-online", {}).get("date-parts") or item.get("created", {}).get("date-parts")
                    if pub_parts and len(pub_parts[0]) > 0:
                        year = pub_parts[0][0]

                    clean_abs = clean_jats_abstract(item.get("abstract", ""))
                    subjects = [str(s) for s in item.get("subject", [])]

                    return {
                        "ground_truth_title": gt_title,
                        "ground_truth_authors": "; ".join(au_names),
                        "ground_truth_year": year,
                        "ground_truth_doi": item.get("DOI", doi).lower(),
                        "ground_truth_abstract": clean_abs,
                        "ground_truth_subjects": subjects,
                        "ground_truth_topics": [],
                        "ground_truth_concepts": [],
                        "source": "crossref"
                    }
                elif resp.status_code == 404:
                    return None
        except Exception as e:
            logger.debug(f"Crossref DOI query failed for {doi}: {e}")
        return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=False
    )
    def query_openalex_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Queries OpenAlex API by DOI as secondary authority."""
        url = f"{self.OPENALEX_API}/https://doi.org/{doi}"
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    item = resp.json()
                    gt_title = item.get("title") or item.get("display_name") or ""
                    authorships = item.get("authorships", [])
                    au_names = [a.get("author", {}).get("display_name", "") for a in authorships if a.get("author")]

                    topics = [t.get("display_name", "") for t in item.get("topics", []) if t.get("display_name")]
                    concepts = [c.get("display_name", "") for c in item.get("concepts", []) if c.get("display_name")]
                    clean_abs = reconstruct_abstract_inverted_index(item.get("abstract_inverted_index"))
                    
                    return {
                        "ground_truth_title": gt_title,
                        "ground_truth_authors": "; ".join(au_names),
                        "ground_truth_year": item.get("publication_year"),
                        "ground_truth_doi": (item.get("doi") or f"https://doi.org/{doi}").replace("https://doi.org/", "").lower(),
                        "ground_truth_abstract": clean_abs,
                        "ground_truth_topics": topics,
                        "ground_truth_concepts": concepts,
                        "ground_truth_subjects": [],
                        "source": "openalex"
                    }
        except Exception as e:
            logger.debug(f"OpenAlex DOI query failed for {doi}: {e}")
        return None

    def query_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Queries Crossref and OpenAlex to obtain comprehensive authoritative metadata."""
        rec_cr = self.query_crossref_doi(doi)
        rec_oa = self.query_openalex_doi(doi)
        if not rec_cr and not rec_oa:
            return None
        base = rec_cr or rec_oa
        if rec_cr and rec_oa:
            base["ground_truth_topics"] = rec_oa.get("ground_truth_topics", [])
            base["ground_truth_concepts"] = rec_oa.get("ground_truth_concepts", [])
            if not base.get("ground_truth_abstract"):
                base["ground_truth_abstract"] = rec_oa.get("ground_truth_abstract", "")
            base["source"] = "crossref+openalex"
        return base

    def check_study_methodology(
        self,
        title: str,
        abstract: str = "",
        topics: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
        subjects: Optional[List[str]] = None,
        expected_domain: str = "bibliometric"
    ) -> Tuple[bool, str, List[str]]:
        """
        Validates whether the publication's content, topics, and classification
        match the expected methodological domain (e.g., 'bibliometric' or 'meta_analysis').
        Returns (is_match, reason, matched_cues).
        """
        topics = topics or []
        concepts = concepts or []
        subjects = subjects or []

        combined_text = f"{title} {abstract}".lower()
        metadata_terms = [t.lower() for t in topics + concepts + subjects]

        if expected_domain in ["bibliometric", "scientometrics", "science_mapping"]:
            target_keywords = self.BIBLIOMETRIC_KEYWORDS
        elif expected_domain in ["meta_analysis", "systematic_review", "evidence_synthesis"]:
            target_keywords = self.META_ANALYSIS_KEYWORDS
        else:
            return True, f"Unknown domain filter '{expected_domain}'; skipped.", []

        matched_cues = []
        for kw in target_keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                matched_cues.append(f"text:{kw}")

        for term in metadata_terms:
            for kw in target_keywords:
                if kw in term:
                    matched_cues.append(f"topic:{term}")

        matched_cues = list(dict.fromkeys(matched_cues))

        if matched_cues:
            return True, f"Confirmed {expected_domain} methodology via cues: {matched_cues[:5]}", matched_cues

        top_found_topics = (topics[:3] or concepts[:3])
        return (
            False,
            f"No {expected_domain} keywords found in title, abstract, or OpenAlex/Crossref topics. "
            f"Found topics: {top_found_topics if top_found_topics else 'None'}.",
            []
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=False
    )
    def search_registry_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Searches OpenAlex and Crossref by paper title when DOI is missing or unverified."""
        if not title or len(title.strip()) < 8:
            return None

        # 1. Search OpenAlex
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(f"{self.OPENALEX_API}?search={title}&per-page=3")
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    for res in results:
                        cand_title = res.get("title") or res.get("display_name") or ""
                        sim = compute_string_similarity(title, cand_title)
                        if sim >= 0.70:
                            authorships = res.get("authorships", [])
                            au_names = [a.get("author", {}).get("display_name", "") for a in authorships if a.get("author")]
                            doi_val = res.get("doi") or ""
                            clean_doi = doi_val.replace("https://doi.org/", "").strip().lower()

                            topics = [t.get("display_name", "") for t in res.get("topics", []) if t.get("display_name")]
                            concepts = [c.get("display_name", "") for c in res.get("concepts", []) if c.get("display_name")]
                            clean_abs = reconstruct_abstract_inverted_index(res.get("abstract_inverted_index"))

                            return {
                                "ground_truth_title": cand_title,
                                "ground_truth_authors": "; ".join(au_names),
                                "ground_truth_year": res.get("publication_year"),
                                "ground_truth_doi": clean_doi,
                                "ground_truth_abstract": clean_abs,
                                "ground_truth_topics": topics,
                                "ground_truth_concepts": concepts,
                                "ground_truth_subjects": [],
                                "similarity": round(sim, 3),
                                "source": "openalex"
                            }
        except Exception as e:
            logger.debug(f"OpenAlex title search failed: {e}")

        # 2. Search Crossref
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(f"{self.CROSSREF_API}?query.bibliographic={title}&rows=3")
                if resp.status_code == 200:
                    items = resp.json().get("message", {}).get("items", [])
                    for item in items:
                        titles = item.get("title", [])
                        cand_title = titles[0] if titles else ""
                        sim = compute_string_similarity(title, cand_title)
                        if sim >= 0.70:
                            authors = item.get("author", [])
                            au_names = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors if 'family' in a]
                            doi_val = item.get("DOI", "").lower()
                            year = None
                            pub_parts = item.get("published-print", {}).get("date-parts") or item.get("published-online", {}).get("date-parts")
                            if pub_parts and len(pub_parts[0]) > 0:
                                year = pub_parts[0][0]

                            clean_abs = clean_jats_abstract(item.get("abstract", ""))
                            subjects = [str(s) for s in item.get("subject", [])]

                            return {
                                "ground_truth_title": cand_title,
                                "ground_truth_authors": "; ".join(au_names),
                                "ground_truth_year": year,
                                "ground_truth_doi": doi_val,
                                "ground_truth_abstract": clean_abs,
                                "ground_truth_topics": [],
                                "ground_truth_concepts": [],
                                "ground_truth_subjects": subjects,
                                "similarity": round(sim, 3),
                                "source": "crossref"
                            }
        except Exception as e:
            logger.debug(f"Crossref title search failed: {e}")

        return None

    def verify_entry(self, entry: Dict[str, Any], expected_domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates a single bibliographic entry and diagnoses potential hallucinations
        and methodological domain mismatches.
        Returns a dictionary containing validation status, reason, and ground-truth values.
        """
        cite_key = str(entry.get("cite_key") or "ref")
        input_title = str(entry.get("title") or "").strip()
        input_doi_raw = entry.get("doi")
        input_doi = clean_doi_string(input_doi_raw)
        input_author = str(entry.get("author") or entry.get("authors") or "").strip()
        input_year = entry.get("year")

        result = {
            "cite_key": cite_key,
            "input_title": input_title,
            "input_doi": input_doi or "",
            "input_year": input_year,
            "input_author": input_author,
            "status": "UNVERIFIED",
            "flag_reason": "",
            "is_hallucination_suspect": False,
            "is_domain_mismatch": False,
            "domain_verified": True if not expected_domain else False,
            "domain_cues": [],
            "similarity_score": 0.0,
            "ground_truth_title": "",
            "ground_truth_doi": "",
            "ground_truth_year": None,
            "ground_truth_authors": "",
            "source": ""
        }

        # -------------------------------------------------------------
        # Path 1: DOI is provided
        # -------------------------------------------------------------
        if input_doi:
            gt_record = self.query_doi(input_doi)

            if not gt_record:
                # DOI failed to resolve in both Crossref and OpenAlex
                # Try fallback title search to see if paper exists with a different DOI
                if input_title:
                    fallback_record = self.search_registry_by_title(input_title)
                    if fallback_record and fallback_record.get("similarity", 0) >= 0.85:
                        result["status"] = "FLAGGED_INVALID_DOI_REAL_PAPER"
                        result["is_hallucination_suspect"] = True
                        result["flag_reason"] = (
                            f"Input DOI '{input_doi}' does not exist, but matching paper was found "
                            f"with authentic DOI: '{fallback_record.get('ground_truth_doi')}'."
                        )
                        result["similarity_score"] = fallback_record.get("similarity", 0.0)
                        result["ground_truth_title"] = fallback_record.get("ground_truth_title", "")
                        result["ground_truth_doi"] = fallback_record.get("ground_truth_doi", "")
                        result["ground_truth_year"] = fallback_record.get("ground_truth_year")
                        result["source"] = fallback_record.get("source", "")
                        return result

                result["status"] = "HALLUCINATED_DOI"
                result["is_hallucination_suspect"] = True
                result["flag_reason"] = f"DOI '{input_doi}' not found in Crossref or OpenAlex registries."
                return result

            # DOI resolved successfully. Now verify whether title matches!
            gt_title = gt_record.get("ground_truth_title", "")
            result["ground_truth_title"] = gt_title
            result["ground_truth_doi"] = gt_record.get("ground_truth_doi", input_doi)
            result["ground_truth_year"] = gt_record.get("ground_truth_year")
            result["ground_truth_authors"] = gt_record.get("ground_truth_authors", "")
            result["source"] = gt_record.get("source", "")

            if input_title:
                sim = compute_string_similarity(input_title, gt_title)
                result["similarity_score"] = round(sim, 3)

                if sim >= 0.80:
                    # Clean match!
                    result["status"] = "VERIFIED"
                    result["flag_reason"] = "DOI resolved and title matches ground-truth."
                    result["is_hallucination_suspect"] = False
                elif sim >= 0.55:
                    # Partial match: minor rephrasing or subtitle omission
                    result["status"] = "FLAGGED_PARTIAL_MATCH"
                    result["is_hallucination_suspect"] = False
                    result["flag_reason"] = f"Moderate title similarity ({sim:.2f}). Needs human check: '{gt_title}'"
                else:
                    # Serious mismatch: DOI belongs to a completely different paper!
                    result["status"] = "HALLUCINATED_DOI_MISMATCH"
                    result["is_hallucination_suspect"] = True
                    result["flag_reason"] = (
                        f"Fabricated citation link: DOI '{input_doi}' resolves to an entirely different paper: "
                        f"'{gt_title}' (similarity={sim:.2f})."
                    )
            else:
                # Title was not given, but DOI is valid
                result["status"] = "VERIFIED_BY_DOI"
                result["flag_reason"] = f"Valid DOI resolved to '{gt_title}'."
                result["is_hallucination_suspect"] = False

            # Domain / Methodology Check if requested
            if expected_domain and result["status"].startswith("VERIFIED"):
                is_match, domain_msg, cues = self.check_study_methodology(
                    title=result.get("ground_truth_title") or input_title,
                    abstract=gt_record.get("ground_truth_abstract", ""),
                    topics=gt_record.get("ground_truth_topics", []),
                    concepts=gt_record.get("ground_truth_concepts", []),
                    subjects=gt_record.get("ground_truth_subjects", []),
                    expected_domain=expected_domain,
                )
                result["domain_verified"] = is_match
                result["domain_cues"] = cues
                if not is_match:
                    result["status"] = (
                        "FLAGGED_NON_BIBLIOMETRIC_STUDY"
                        if expected_domain in ["bibliometric", "scientometrics"]
                        else "FLAGGED_DOMAIN_MISMATCH"
                    )
                    result["is_domain_mismatch"] = True
                    result["flag_reason"] = (
                        f"Paper exists and citation is authentic, but study methodology does not match '{expected_domain}'. "
                        f"{domain_msg}"
                    )

            return result

        # -------------------------------------------------------------
        # Path 2: DOI is missing, verify via Title & Authors
        # -------------------------------------------------------------
        if input_title:
            gt_record = self.search_registry_by_title(input_title)

            if not gt_record:
                result["status"] = "HALLUCINATED_TITLE_NOT_FOUND"
                result["is_hallucination_suspect"] = True
                result["flag_reason"] = "No matching publication found in Crossref or OpenAlex registries."
                return result

            sim = gt_record.get("similarity", 0.0)
            result["similarity_score"] = sim
            result["ground_truth_title"] = gt_record.get("ground_truth_title", "")
            result["ground_truth_doi"] = gt_record.get("ground_truth_doi", "")
            result["ground_truth_year"] = gt_record.get("ground_truth_year")
            result["ground_truth_authors"] = gt_record.get("ground_truth_authors", "")
            result["source"] = gt_record.get("source", "")

            if sim >= 0.85:
                result["status"] = "VERIFIED_BY_TITLE"
                result["is_hallucination_suspect"] = False
                result["flag_reason"] = f"Title authenticated in registry (similarity={sim:.2f}); resolved DOI: {result['ground_truth_doi'] or 'N/A'}."
            elif sim >= 0.70:
                result["status"] = "FLAGGED_PARTIAL_MATCH"
                result["is_hallucination_suspect"] = False
                result["flag_reason"] = f"Candidate found with similarity {sim:.2f}. Needs human check: '{result['ground_truth_title']}'."
            else:
                result["status"] = "HALLUCINATED_TITLE_NOT_FOUND"
                result["is_hallucination_suspect"] = True
                result["flag_reason"] = f"Low similarity candidate ({sim:.2f}). High probability of hallucinated title."

            # Domain / Methodology Check if requested
            if expected_domain and result["status"].startswith("VERIFIED"):
                is_match, domain_msg, cues = self.check_study_methodology(
                    title=result.get("ground_truth_title") or input_title,
                    abstract=gt_record.get("ground_truth_abstract", ""),
                    topics=gt_record.get("ground_truth_topics", []),
                    concepts=gt_record.get("ground_truth_concepts", []),
                    subjects=gt_record.get("ground_truth_subjects", []),
                    expected_domain=expected_domain,
                )
                result["domain_verified"] = is_match
                result["domain_cues"] = cues
                if not is_match:
                    result["status"] = (
                        "FLAGGED_NON_BIBLIOMETRIC_STUDY"
                        if expected_domain in ["bibliometric", "scientometrics"]
                        else "FLAGGED_DOMAIN_MISMATCH"
                    )
                    result["is_domain_mismatch"] = True
                    result["flag_reason"] = (
                        f"Paper exists and citation is authentic, but study methodology does not match '{expected_domain}'. "
                        f"{domain_msg}"
                    )

            return result

        # Neither DOI nor title provided
        result["status"] = "FLAGGED_INCOMPLETE_ENTRY"
        result["flag_reason"] = "Missing both title and DOI; cannot validate."
        result["is_hallucination_suspect"] = True
        return result

    # --- Batch Operations & Reporting ---

    def verify_entries(self, entries: List[Dict[str, Any]], expected_domain: Optional[str] = None) -> pd.DataFrame:
        """Validates a list of bibliographic entries and produces a comprehensive audit DataFrame."""
        records = []
        for idx, entry in enumerate(entries):
            res = self.verify_entry(entry, expected_domain=expected_domain)
            records.append(res)
        df_out = pd.DataFrame(records)
        return df_out

    def validate_file(
        self,
        file_path: str,
        output_path: Optional[str] = None,
        expected_domain: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Parses an input file, verifies all citations, prints a diagnostic summary,
        and optionally exports the audit CSV report.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")

        entries = self.parse_file(file_path)
        if not entries:
            logger.warning(f"No citations or bibliographic entries found in {file_path}.")
            df_empty = pd.DataFrame()
            return df_empty, {"total": 0, "verified": 0, "flagged": 0, "hallucinated": 0}

        logger.info(f"BiblioValidator: Validating {len(entries)} entries from '{file_path}' (domain: {expected_domain or 'any'})...")
        df_results = self.verify_entries(entries, expected_domain=expected_domain)

        total = len(df_results)
        verified = int(df_results["status"].str.startswith("VERIFIED").sum())
        hallucinated = int(df_results["is_hallucination_suspect"].sum())
        flagged = total - verified

        metrics = {
            "total_checked": total,
            "verified": verified,
            "flagged_for_human_review": flagged,
            "suspected_hallucinations": hallucinated,
            "verification_rate_pct": round((verified / total) * 100, 1) if total > 0 else 0.0
        }

        if output_path:
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            df_results.to_csv(output_path, index=False)
            logger.info(f"BiblioValidator: Full audit report saved to '{output_path}'.")

        return df_results, metrics

    def validate_benchmark_file(self, benchmark_path: str) -> Dict[str, Any]:
        """
        Validates an OpenSciencePipe benchmark JSON file for:
        1. Reference citation authenticity (via Crossref and OpenAlex).
        2. Methodological domain concordance (verifying it is a true bibliometric study).
        3. Ground-truth ranking provenance (verifying country/institutional rankings trace to documented tables/figures).
        """
        if not os.path.exists(benchmark_path):
            raise FileNotFoundError(f"Benchmark file not found: {benchmark_path}")

        with open(benchmark_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ref_doi = data.get("reference_doi")
        title = data.get("benchmark_title", "")
        entry = {
            "cite_key": os.path.basename(benchmark_path),
            "title": title,
            "doi": ref_doi,
            "authors": data.get("authors", ""),
            "year": data.get("year"),
        }

        verif_res = self.verify_entry(entry, expected_domain="bibliometric")

        # Provenance check
        provenance = data.get("provenance") or data.get("ground_truth_source") or {}
        scientometrics = data.get("scientometrics", {})
        top_countries = scientometrics.get("top_countries", [])
        top_institutions = scientometrics.get("top_institutions", [])
        has_rankings = bool(top_countries or top_institutions)
        provenance_declared = bool(provenance)

        warnings = []
        if has_rankings and not provenance_declared:
            warnings.append(
                "Benchmark contains top_countries/top_institutions rankings without explicit 'provenance' table/figure pointer."
            )

        if verif_res["status"] == "FLAGGED_NON_BIBLIOMETRIC_STUDY":
            warnings.append(verif_res["flag_reason"])
        elif verif_res["is_hallucination_suspect"]:
            warnings.append(f"Citation validation suspect: {verif_res['flag_reason']}")

        status = "PASSED" if not warnings else "FLAGGED"

        return {
            "benchmark_file": os.path.basename(benchmark_path),
            "status": status,
            "reference_doi": ref_doi,
            "benchmark_title": title,
            "citation_status": verif_res["status"],
            "domain_verified": verif_res.get("domain_verified", False),
            "provenance_verified": provenance_declared or not has_rankings,
            "warnings": warnings,
            "details": verif_res
        }


def main():
    parser = argparse.ArgumentParser(
        description="OpenSciencePipe Bibliographic Hallucination Validator & Citation Auditor"
    )
    parser.add_argument("file", type=str, help="Path to input citations file (.bib, .csv, .json, .tex, .md)")
    parser.add_argument("--output", "-o", type=str, default=None, help="Path to save output audit report CSV")
    parser.add_argument("--email", type=str, default=None, help="Email for polite Crossref and OpenAlex API queries")
    parser.add_argument("--domain", type=str, default=None, help="Expected study domain filter (e.g. 'bibliometric' or 'meta_analysis')")
    parser.add_argument("--benchmark", action="store_true", help="Validate input file as an OpenSciencePipe benchmark JSON with provenance auditing")

    args = parser.parse_args()

    validator = BiblioValidator(email=args.email)

    if args.benchmark or args.file.endswith(".json") and "benchmark" in os.path.basename(args.file):
        audit = validator.validate_benchmark_file(args.file)
        print("\n" + "=" * 70)
        print("OPENSCIENCEPIPE BENCHMARK AUDIT REPORT")
        print("=" * 70)
        print(f"File              : {audit['benchmark_file']}")
        print(f"Benchmark Title   : {audit['benchmark_title']}")
        print(f"Reference DOI     : {audit['reference_doi']}")
        print(f"Citation Status   : {audit['citation_status']}")
        print(f"Domain Verified   : {'YES' if audit['domain_verified'] else 'NO (Methodology mismatch)'}")
        print(f"Provenance Status : {'VERIFIED' if audit['provenance_verified'] else 'MISSING PROVENANCE'}")
        print(f"Overall Status    : {audit['status']}")
        if audit["warnings"]:
            print("\nWARNINGS / AUDIT FLAGS:")
            for w in audit["warnings"]:
                print(f"  - {w}")
        print("=" * 70)
        return

    df_res, metrics = validator.validate_file(args.file, output_path=args.output, expected_domain=args.domain)

    print("\n" + "=" * 70)
    print("BIBLIOGRAPHIC VALIDATION & HALLUCINATION AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total Entries Checked    : {metrics.get('total_checked', 0)}")
    print(f"Verified Authentic       : {metrics.get('verified', 0)}")
    print(f"Flagged for Human Review : {metrics.get('flagged_for_human_review', 0)}")
    print(f"Suspected Hallucinations : {metrics.get('suspected_hallucinations', 0)}")
    print(f"Verification Success Rate: {metrics.get('verification_rate_pct', 0.0)}%")
    print("=" * 70)

    if not df_res.empty:
        flagged_df = df_res[~df_res["status"].str.startswith("VERIFIED")]
        if not flagged_df.empty:
            print("\nFLAGGED ENTRIES REQUIRING ATTENTION:")
            for _, r in flagged_df.iterrows():
                print(f"[{r['status']}] Key: {r['cite_key']}")
                print(f"  Title  : {r['input_title']}")
                print(f"  DOI    : {r['input_doi']}")
                print(f"  Reason : {r['flag_reason']}")
                if r['ground_truth_title']:
                    print(f"  Registry Ground Truth: {r['ground_truth_title']} (DOI: {r['ground_truth_doi']})")
                print("-" * 50)
        else:
            print("\nAll entries successfully authenticated against Crossref / OpenAlex.")


if __name__ == "__main__":
    main()
