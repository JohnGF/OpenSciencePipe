import logging
import json
import re
import urllib.request
import urllib.error
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
import torch

logger = logging.getLogger(__name__)

# Lazy import for sentence_transformers
try:
    from sentence_transformers import SentenceTransformer, util
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    col_map = {col.lower().strip(): col for col in df.columns}
    for cand in candidates:
        cand_lower = cand.lower().strip()
        if cand_lower in col_map:
            return col_map[cand_lower]
    return None


class GrepRelevanceFilter:
    """
    Deterministic regex/grep-based relevance filter for Systematic Literature Reviews.
    Audits every record against positive inclusion and negative exclusion rules.
    """

    def __init__(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        min_abstract_len: int = 30,
        case_sensitive: bool = False
    ):
        flags = 0 if case_sensitive else re.IGNORECASE
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.min_abstract_len = min_abstract_len

        self._compiled_include = []
        for p in self.include_patterns:
            if p and p.strip():
                try:
                    self._compiled_include.append(re.compile(p.strip(), flags))
                except re.error as e:
                    logger.warning(f"Invalid include regex pattern '{p}': {e}")

        self._compiled_exclude = []
        for p in self.exclude_patterns:
            if p and p.strip():
                try:
                    self._compiled_exclude.append(re.compile(p.strip(), flags))
                except re.error as e:
                    logger.warning(f"Invalid exclude regex pattern '{p}': {e}")

    def evaluate_text(self, title: str, abstract: str, keywords: str = "") -> Tuple[bool, str, str]:
        """
        Evaluates a single record.
        Returns: (is_included: bool, exclusion_stage: str, reason: str)
        """
        combined = f"{title} {abstract} {keywords}".strip()

        # Check abstract presence/length
        if len(abstract.strip()) < self.min_abstract_len:
            return False, "Identification & Screening", f"Missing or short abstract (<{self.min_abstract_len} chars)"

        # Check negative exclusion patterns
        for pattern in self._compiled_exclude:
            if pattern.search(combined):
                return False, "Eligibility Screening", f"Matched exclusion pattern: '{pattern.pattern}'"

        # Check positive inclusion patterns (if specified, at least one must match)
        if self._compiled_include:
            matched_any = any(pattern.search(combined) for pattern in self._compiled_include)
            if not matched_any:
                inc_desc = " | ".join(p.pattern for p in self._compiled_include)
                return False, "Eligibility Screening", f"Did not match required inclusion pattern(s): '{inc_desc}'"

        return True, "Included", "Passed eligibility criteria"

    def filter_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Filters a DataFrame and produces a full PRISMA audit DataFrame.
        """
        if df.empty:
            empty_audit = pd.DataFrame(columns=["Title", "DOI", "Year", "Screening_Status", "Exclusion_Stage", "Reason"])
            return df, empty_audit

        title_col = _find_col(df, ["Title", "title", "paper_title", "headline", "name"])
        abstract_col = _find_col(df, ["Abstract", "abstract", "summary", "description"])
        doi_col = _find_col(df, ["DOI", "doi", "id", "url"])
        year_col = _find_col(df, ["Year", "year", "pub_year", "publication_year"])
        keywords_col = _find_col(df, ["Keywords", "keywords", "author_keywords", "mesh_terms"])

        audit_rows = []
        retained_indices = []

        for idx, row in df.iterrows():
            title = str(row[title_col]) if title_col and not pd.isna(row[title_col]) else ""
            abstract = str(row[abstract_col]) if abstract_col and not pd.isna(row[abstract_col]) else ""
            keywords = str(row[keywords_col]) if keywords_col and not pd.isna(row[keywords_col]) else ""
            doi = str(row[doi_col]) if doi_col and not pd.isna(row[doi_col]) else ""
            year = str(row[year_col]) if year_col and not pd.isna(row[year_col]) else ""

            is_inc, stage, reason = self.evaluate_text(title, abstract, keywords)

            status = "Included" if is_inc else "Excluded"
            audit_rows.append({
                "Title": title,
                "DOI": doi,
                "Year": year,
                "Screening_Status": status,
                "Exclusion_Stage": stage,
                "Reason": reason
            })

            if is_inc:
                retained_indices.append(idx)

        audit_df = pd.DataFrame(audit_rows)
        retained_df = df.loc[retained_indices].copy().reset_index(drop=True)

        logger.info(
            f"GrepRelevanceFilter Complete: Retained {len(retained_df)}/{len(df)} papers "
            f"({len(df) - len(retained_df)} excluded)."
        )
        return retained_df, audit_df


class EmbeddingRelevanceFilter:
    """Option 1: Vector embedding semantic similarity filter using SentenceTransformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", target_prompt: Optional[str] = None):
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers is required for EmbeddingRelevanceFilter. "
                "Please install it via `pip install sentence-transformers`."
            )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"EmbeddingRelevanceFilter: Loading model '{model_name}' on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.target_prompt = target_prompt or "scientific empirical research study methodology evaluation"
        self.target_embedding = self.model.encode(self.target_prompt, convert_to_tensor=True)

    def set_target_prompt(self, prompt: str):
        if prompt and prompt.strip():
            self.target_prompt = prompt.strip()
            self.target_embedding = self.model.encode(self.target_prompt, convert_to_tensor=True)

    def filter_dataframe(
        self,
        df: pd.DataFrame,
        threshold: float = 0.35,
        title_col: Optional[str] = None,
        abstract_col: Optional[str] = None
    ) -> pd.DataFrame:
        """Filters a DataFrame of publications based on semantic relevance threshold."""
        if df.empty:
            return df

        resolved_title_col = title_col or _find_col(df, ["Title", "title", "paper_title", "headline", "name"])
        resolved_abstract_col = abstract_col or _find_col(df, ["Abstract", "abstract", "summary", "description"])

        if not resolved_title_col and not resolved_abstract_col:
            logger.warning("No Title or Abstract column found in DataFrame. Skipping embedding relevance filtering.")
            return df

        titles = df[resolved_title_col].fillna("").astype(str) if resolved_title_col else pd.Series([""] * len(df), index=df.index)
        abstracts = df[resolved_abstract_col].fillna("").astype(str) if resolved_abstract_col else pd.Series([""] * len(df), index=df.index)
        
        texts = (titles + ". " + abstracts).tolist()

        logger.info(f"Computing embeddings for {len(texts)} papers (prompt='{self.target_prompt[:60]}...')...")
        doc_embeddings = self.model.encode(texts, convert_to_tensor=True, batch_size=64, show_progress_bar=False)

        similarities = util.cos_sim(doc_embeddings, self.target_embedding).cpu().numpy().flatten()
        
        df_out = df.copy()
        df_out["relevance_score"] = similarities

        retained_df = df_out[df_out["relevance_score"] >= threshold].copy()
        dropped_count = len(df_out) - len(retained_df)
        logger.info(
            f"Embedding Relevance Filtering Complete: Retained {len(retained_df)}/{len(df_out)} papers "
            f"(threshold={threshold}, dropped {dropped_count} low-similarity papers)."
        )

        return retained_df


class LLMRelevanceClassifier:
    """Option 2: LLM-based zero-shot classifier & dynamic thematic paradigm extractor."""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.2:3b", topic_context: str = "scientific research"):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.topic_context = topic_context

    def classify_paper(self, title: str, abstract: str, temperature: float = 0.0) -> Dict:
        """Classifies a single paper's relevance and methodological/thematic category."""
        prompt = f"""
Analyze this research paper title and abstract for a systematic review regarding: {self.topic_context}.

Title: {title}
Abstract: {abstract}

Return ONLY raw JSON with these exact keys:
- "is_relevant": boolean (true if directly relevant to {self.topic_context}; false otherwise)
- "thematic_category": string (a concise 2-4 word classification of the primary methodology, domain focus, or approach)

JSON response:
"""
        req_data = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    res = json.loads(body.get("response", "{}"))
                    return {
                        "is_relevant": res.get("is_relevant", True),
                        "thematic_category": res.get("thematic_category", "Empirical Investigation")
                    }
        except Exception as e:
            logger.warning(f"LLM Classification failed for title '{title[:30]}...': {e}")
        
        return {"is_relevant": True, "thematic_category": "Empirical Investigation"}

    def categorize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies LLM classification across a DataFrame of papers."""
        if df.empty:
            return df

        title_col = _find_col(df, ["Title", "title", "paper_title", "headline", "name"])
        abstract_col = _find_col(df, ["Abstract", "abstract", "summary", "description"])

        if not title_col and not abstract_col:
            logger.warning("No Title or Abstract column found in DataFrame. Skipping LLM categorization.")
            return df

        logger.info(f"LLM Categorization: Processing {len(df)} papers with model '{self.model}'...")
        
        is_relevant_list = []
        thematic_categories = []

        for idx, row in df.iterrows():
            title = str(row[title_col]) if title_col and not pd.isna(row[title_col]) else ""
            abstract = str(row[abstract_col]) if abstract_col and not pd.isna(row[abstract_col]) else ""
            res = self.classify_paper(title, abstract)
            is_relevant_list.append(res.get("is_relevant", True))
            thematic_categories.append(res.get("thematic_category", "Empirical Investigation"))

        df_out = df.copy()
        df_out["is_relevant"] = is_relevant_list
        df_out["thematic_category"] = thematic_categories
        
        return df_out


class PaperScreener:
    """
    Unified Systematic Review Screener supporting:
    1. Deterministic Grep/Regex inclusion & exclusion filtering with PRISMA audit trails.
    2. Vector Embedding Relevance Filtering (SentenceTransformers).
    3. LLM-based Zero-Shot Categorization (Ollama).
    """

    def __init__(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        use_embedding_filter: bool = False,
        embedding_threshold: float = 0.35,
        target_prompt: Optional[str] = None,
        use_llm_categorization: bool = False,
        llm_model: str = "llama3.2:3b",
        ollama_url: str = "http://localhost:11434",
        topic_context: Optional[str] = None
    ):
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.use_embedding_filter = use_embedding_filter
        self.embedding_threshold = embedding_threshold
        self.target_prompt = target_prompt
        self.use_llm_categorization = use_llm_categorization

        self.grep_filter = GrepRelevanceFilter(
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns
        )
        self.embedding_filter = (
            EmbeddingRelevanceFilter(target_prompt=self.target_prompt)
            if self.use_embedding_filter
            else None
        )
        self.llm_classifier = (
            LLMRelevanceClassifier(
                ollama_url=ollama_url,
                model=llm_model,
                topic_context=topic_context or target_prompt or "scientific research"
            )
            if self.use_llm_categorization
            else None
        )

        self.audit_df = pd.DataFrame()
        self.prisma_metrics = {}

    def screen(self, df: pd.DataFrame, return_audit: bool = False) -> Any:
        """
        Executes systematic screening and produces verified PRISMA metrics.
        """
        if df.empty:
            self.audit_df = pd.DataFrame()
            self.prisma_metrics = {
                "identified": 0, "screened": 0, "excluded_screening": 0,
                "sought": 0, "not_retrieved": 0, "eligible": 0,
                "excluded_fulltext": 0, "included": 0, "exclusion_reasons": {}
            }
            return (df, self.audit_df) if return_audit else df

        total_identified = len(df)

        # Stage 1: Deterministic Grep & Abstract Length Screening
        filtered_df, audit_df = self.grep_filter.filter_dataframe(df)

        # Stage 2: Embedding Semantic Filter (if enabled)
        if self.use_embedding_filter and self.embedding_filter and not filtered_df.empty:
            filtered_df = self.embedding_filter.filter_dataframe(filtered_df, threshold=self.embedding_threshold)
            
            # Update audit log for studies dropped by embedding filter
            retained_dois = set(filtered_df["DOI"].dropna().astype(str)) if "DOI" in filtered_df.columns else set()
            for idx, row in audit_df[audit_df["Screening_Status"] == "Included"].iterrows():
                row_doi = str(row.get("DOI", ""))
                if row_doi and row_doi not in retained_dois:
                    audit_df.at[idx, "Screening_Status"] = "Excluded"
                    audit_df.at[idx, "Exclusion_Stage"] = "Semantic Embedding Screening"
                    audit_df.at[idx, "Reason"] = f"Semantic similarity below threshold ({self.embedding_threshold})"

        # Stage 3: LLM Categorization (if enabled)
        if self.use_llm_categorization and self.llm_classifier and not filtered_df.empty:
            filtered_df = self.llm_classifier.categorize_dataframe(filtered_df)

        # Calculate exact PRISMA metrics based on audit_df
        reasons_series = audit_df[audit_df["Screening_Status"] == "Excluded"]["Reason"]
        exclusion_reasons_dict = reasons_series.value_counts().to_dict()

        has_abstract_count = (audit_df["Reason"] != "Missing or short abstract (<30 chars)").sum()
        excluded_screening_count = (audit_df["Exclusion_Stage"] == "Identification & Screening").sum()
        excluded_eligibility_count = (audit_df["Exclusion_Stage"].isin(["Eligibility Screening", "Semantic Embedding Screening"])).sum()

        included_count = len(filtered_df)
        eligible_count = included_count

        self.prisma_metrics = {
            "identified": int(total_identified),
            "screened": int(has_abstract_count),
            "excluded_screening": int(excluded_screening_count),
            "sought": int(total_identified - excluded_screening_count),
            "not_retrieved": 0,
            "eligible": int(eligible_count),
            "excluded_fulltext": int(excluded_eligibility_count),
            "included": int(included_count),
            "exclusion_reasons": {str(k): int(v) for k, v in exclusion_reasons_dict.items()}
        }

        self.audit_df = audit_df

        if return_audit:
            return filtered_df, audit_df

        return filtered_df

    def prioritize_for_human_screening(
        self,
        df: pd.DataFrame,
        seed_included_texts: Optional[List[str]] = None,
        seed_excluded_texts: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Ranks candidate abstracts in priority order for human screener adjudication.
        Uses active-learning scoring based on semantic proximity to known included vs excluded exemplars.
        """
        ranker = ActiveLearningPriorityRanker()
        return ranker.rank_priority(df, seed_included_texts=seed_included_texts, seed_excluded_texts=seed_excluded_texts)


class ActiveLearningPriorityRanker:
    """
    Active Learning Priority Queue for Title/Abstract Screening (similar to ASReview).
    Ranks unlabelled studies so human reviewers screen the most probable inclusions first,
    dramatically reducing the time needed to find 95%+ of eligible literature.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            if not HAS_SENTENCE_TRANSFORMERS:
                raise ImportError("sentence-transformers is required for ActiveLearningPriorityRanker.")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(self.model_name, device=device)
        return self._model

    def rank_priority(
        self,
        df: pd.DataFrame,
        seed_included_texts: Optional[List[str]] = None,
        seed_excluded_texts: Optional[List[str]] = None,
        title_col: Optional[str] = None,
        abstract_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Computes inclusion probability scores for all unlabelled papers and sorts by descending priority.
        """
        if df.empty:
            return df

        resolved_title = title_col or _find_col(df, ["Title", "title", "paper_title"])
        resolved_abstract = abstract_col or _find_col(df, ["Abstract", "abstract", "summary"])

        titles = df[resolved_title].fillna("").astype(str) if resolved_title else pd.Series([""] * len(df), index=df.index)
        abstracts = df[resolved_abstract].fillna("").astype(str) if resolved_abstract else pd.Series([""] * len(df), index=df.index)
        doc_texts = (titles + ". " + abstracts).tolist()

        try:
            model = self._get_model()
            doc_embeddings = model.encode(doc_texts, convert_to_tensor=True, batch_size=64, show_progress_bar=False)

            if seed_included_texts and len(seed_included_texts) > 0:
                pos_emb = model.encode(seed_included_texts, convert_to_tensor=True)
                pos_sims = util.cos_sim(doc_embeddings, pos_emb).max(dim=1).values.cpu().numpy()
            else:
                # Default query centroid if no seeds provided
                default_prompt = "systematic literature review empirical research evidence study"
                pos_emb = model.encode([default_prompt], convert_to_tensor=True)
                pos_sims = util.cos_sim(doc_embeddings, pos_emb).flatten().cpu().numpy()

            if seed_excluded_texts and len(seed_excluded_texts) > 0:
                neg_emb = model.encode(seed_excluded_texts, convert_to_tensor=True)
                neg_sims = util.cos_sim(doc_embeddings, neg_emb).max(dim=1).values.cpu().numpy()
                priority_scores = pos_sims - 0.5 * neg_sims
            else:
                priority_scores = pos_sims

        except Exception as e:
            logger.warning(f"Active learning ranking fallback to keyword heuristics: {e}")
            priority_scores = [float(len(t)) for t in doc_texts]

        ranked_df = df.copy()
        ranked_df["screening_priority_score"] = priority_scores
        ranked_df["screening_priority_rank"] = ranked_df["screening_priority_score"].rank(ascending=False, method="min").astype(int)
        ranked_df = ranked_df.sort_values(by="screening_priority_score", ascending=False).reset_index(drop=True)

        return ranked_df


