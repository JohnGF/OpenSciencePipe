import polars as pl
import pandas as pd
from bertopic import BERTopic
from typing import List, Dict, Optional
import numpy as np
import logging

# GPU Detection
try:
    import torch
    HAS_TORCH_CUDA = torch.cuda.is_available()
    if HAS_TORCH_CUDA:
        try:
            from cuml.cluster import HDBSCAN
            from cuml.manifold import UMAP
            HAS_RAPIDS_CUML = True
        except ImportError:
            HAS_RAPIDS_CUML = False
    else:
        HAS_RAPIDS_CUML = False
except Exception:
    HAS_TORCH_CUDA = False
    HAS_RAPIDS_CUML = False

# --- Default Mapping (Extracted from Keyword.ipynb) ---

DEFAULT_TERM_MAPPING = {
    "bci": "brain-computer interface",
    "brain-computer interface (bci)": "brain-computer interface",
    "brain computer interface (bci)": "brain-computer interface",
    "brain computer interface": "brain-computer interface",
    "affective brain-computer interface": "brain-computer interface",
    "brain–computer interfaces": "brain-computer interface",
    "brain–computer interface": "brain-computer interface",
    "brain-computer interfaces": "brain-computer interface",
    "brain–computer interface (bci)": "brain-computer interface",
    "motor imagery (mi)": "motor imagery",
    "erp": "event-related potentials",
    "event-related potential": "event-related potentials",
    "steady-state visual evoked potential": "ssvep",
    "cnn": "convolutional neural network",
    "electrocardiography": "ecg",
    "electromyography": "emg",
    "convolutional neural network (cnn)": "convolutional neural network",
    "convolutional neural networks": "convolutional neural network",
    "svm": "support vector machine",
    "ica": "independent component analysis",
    "independent component analysis (ica)": "independent component analysis",
    "meg": "magnetoencephalography",
    "neuronal networks": "neural network",
    "neural networks": "neural network",
    "artifacts": "artifact removal",
    "emotion": "emotion recognition",
    "deep learning (dl)": "deep learning",
    "explainable artificial intelligence": "explainable ai",
}

class BERTopicPipeline:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", term_mapping: Optional[Dict] = None):
        self.model_name = model_name
        self.term_mapping = term_mapping or DEFAULT_TERM_MAPPING
        self.topic_model = None

    def preprocess_keywords(self, df: pl.DataFrame, column: str = "Author Keywords") -> pl.DataFrame:
        """Standardizes and explodes keywords as per existing logic."""
        return df.with_columns(
            pl.col(column).str.split(";").alias("keyword_list")
        ).explode("keyword_list").with_columns(
            pl.col("keyword_list")
            .str.strip_chars()
            .str.to_lowercase()
            .alias("processed_keyword")
        ).filter(
            ~pl.col("processed_keyword").str.contains("(?i)eeg|electroencephalo")
        ).with_columns(
            pl.col("processed_keyword")
            .replace_strict(self.term_mapping, default=pl.col("processed_keyword"))
            .alias("standardized_word")
        )

    def fit_model(self, docs: List[str]):
        """Fits BERTopic on a list of documents (abstracts)."""
        device = "cuda" if HAS_TORCH_CUDA else "cpu"
        logging.info(f"BERTopic: Fitting model using {device} (RAPIDS accelerated: {HAS_RAPIDS_CUML})")
        
        from sklearn.feature_extraction.text import CountVectorizer
        min_df_val = 2 if len(docs) > 50 else 1
        vectorizer_model = CountVectorizer(stop_words="english", min_df=min_df_val, ngram_range=(1, 2))

        if HAS_RAPIDS_CUML:
            # RAPIDS-accelerated pipeline with fixed deterministic seed
            umap_model = UMAP(n_components=5, n_neighbors=15, min_dist=0.0, random_state=42)
            hdbscan_model = HDBSCAN(min_cluster_size=10, prediction_data=True)
            self.topic_model = BERTopic(
                embedding_model=self.model_name, 
                umap_model=umap_model, 
                hdbscan_model=hdbscan_model,
                vectorizer_model=vectorizer_model,
                calculate_probabilities=True
            )
        else:
            # Standard CPU pipeline with explicit deterministic UMAP
            from umap import UMAP as CPU_UMAP
            from hdbscan import HDBSCAN as CPU_HDBSCAN
            umap_model = CPU_UMAP(n_components=5, n_neighbors=15, min_dist=0.0, metric="cosine", random_state=42)
            hdbscan_model = CPU_HDBSCAN(min_cluster_size=10, metric="euclidean", cluster_selection_method="eom", prediction_data=True)
            self.topic_model = BERTopic(
                embedding_model=self.model_name,
                umap_model=umap_model,
                hdbscan_model=hdbscan_model,
                vectorizer_model=vectorizer_model,
                calculate_probabilities=True
            )
        
        topics, probs = self.topic_model.fit_transform(docs)
        return topics, probs

    def calculate_cagr(self, df: pl.DataFrame, count_col: str = "count", year_col: str = "Year") -> pl.DataFrame:
        """Calculates Compound Annual Growth Rate for standardized terms."""
        cagr_data = df.sort(year_col).group_by("standardized_word").agg(
            first_year_count=pl.col(count_col).first(),
            last_year_count=pl.col(count_col).last(),
            first_year=pl.col(year_col).first(),
            last_year=pl.col(year_col).last()
        )
        
        cagr_data = cagr_data.with_columns(
            years_diff=(pl.col("last_year") - pl.col("first_year")).cast(pl.Float64)
        )
        
        cagr_data = cagr_data.with_columns(
            pl.when((pl.col("years_diff") > 0) & (pl.col("first_year_count") > 0))
            .then((pl.col("last_year_count") / pl.col("first_year_count")).pow(1.0 / pl.col("years_diff")) - 1)
            .otherwise(None)
            .alias("cagr")
        ).with_columns(
            (pl.col("cagr") * 100).alias("cagr_percent")
        )
        
        return cagr_data.filter(
            (pl.col("years_diff") > 0) & (pl.col("last_year_count") >= 10)
        ).sort("cagr_percent", descending=True)

    def get_topics(self):
        if self.topic_model:
            return self.topic_model.get_topic_info()
        return None

    def get_topics_over_time(self, docs: List[str], timestamps: List[int]) -> pd.DataFrame:
        """Leverages BERTopic's topics_over_time to analyze how topics evolve."""
        if not self.topic_model:
            return pd.DataFrame()
        try:
            topics_over_time = self.topic_model.topics_over_time(docs, timestamps)
            return topics_over_time
        except Exception as e:
            logging.error(f"Failed to generate topics over time: {e}")
            return pd.DataFrame()

    def get_topic_keyword_matrix(self, df: pl.DataFrame, docs_col: str, keyword_col: str = "standardized_word") -> pd.DataFrame:
        """
        Creates a correlation matrix mapping author keywords to BERTopic clusters.
        Assumes `df` is the output of `preprocess_keywords` and has a `Topic` column
        assigned from the BERTopic predictions.
        """
        if not self.topic_model or "Topic" not in df.columns:
            return pd.DataFrame()

        try:
            # We want a crosstab/pivot of Topic vs Keyword
            pandas_df = df.to_pandas()
            # Filter out outlier topic
            pandas_df = pandas_df[pandas_df["Topic"] != -1]
            if pandas_df.empty:
                return pd.DataFrame()

            # Group by Topic and Keyword, count occurrences
            matrix = pd.crosstab(pandas_df["Topic"], pandas_df[keyword_col])

            # Map topic IDs to Topic Names for better readability
            topic_info = self.topic_model.get_topic_info()
            topic_name_map = dict(zip(topic_info['Topic'], topic_info['Name']))

            matrix.index = matrix.index.map(lambda x: topic_name_map.get(x, f"Topic {x}"))
            return matrix
        except Exception as e:
            logging.error(f"Failed to generate topic-keyword correlation: {e}")
            return pd.DataFrame()

    def get_research_lines(self, docs: Optional[List[str]] = None, nr_clusters: int = 5) -> pd.DataFrame:
        """Groups topics into broader 'Research Lines' using hierarchical clustering."""
        if not self.topic_model or len(self.topic_model.get_topic_info()) < 2:
            return pd.DataFrame()

        try:
            # Get basic topic info
            topic_info = self.topic_model.get_topic_info()
            
            research_lines = []
            for _, row in topic_info.iterrows():
                topic_id = row['Topic']
                if topic_id == -1: continue # Skip outliers
                
                # Get the top keywords for this topic
                words = [w[0] for w in self.topic_model.get_topic(topic_id)[:5]]
                
                research_lines.append({
                    "topic_id": topic_id,
                    "topic_label": row.get('Name', f"Topic {topic_id}"),
                    "keywords": ", ".join(words),
                    "count": row.get('Count', 0),
                })
                
            return pd.DataFrame(research_lines)
        except Exception as e:
            logging.error(f"Failed to generate research lines: {e}")
            return pd.DataFrame()


def detect_bursts_kleinberg(
    df: pd.DataFrame,
    term_col: str = "keyword",
    year_col: str = "Year",
    s: float = 2.0,
    gamma: float = 1.0,
    min_burst_weight: float = 1.0
) -> pd.DataFrame:
    """
    Implements Kleinberg's 2-state burst detection automaton over discrete annual counts.
    Identifies sudden surges in scientific term adoption across years (CiteSpace style).
    
    Parameters:
        df: DataFrame with term occurrences and publication years.
        term_col: Column containing the scientific term or keyword.
        year_col: Column containing the publication year.
        s: State transition multiplier (rate scaling parameter, typical 2.0).
        gamma: Transition cost scaling parameter (typical 1.0).
        min_burst_weight: Minimum weight threshold to retain burst.
    """
    if df.empty or term_col not in df.columns or year_col not in df.columns:
        return pd.DataFrame()

    clean = df.dropna(subset=[term_col, year_col]).copy()
    clean[year_col] = pd.to_numeric(clean[year_col], errors="coerce")
    clean = clean.dropna(subset=[year_col])
    clean[year_col] = clean[year_col].astype(int)

    all_years = sorted(clean[year_col].unique())
    if len(all_years) < 3:
        return pd.DataFrame()

    total_per_year = clean.groupby(year_col).size().to_dict()
    total_docs = sum(total_per_year.values())
    if total_docs == 0:
        return pd.DataFrame()

    bursts = []
    terms = clean[term_col].value_counts()
    top_terms = terms[terms >= 3].index.tolist()

    for term in top_terms:
        term_df = clean[clean[term_col] == term]
        term_counts = term_df.groupby(year_col).size().to_dict()

        # Vectors of occurrences (r_t) and total trials (d_t) per year
        r = np.array([term_counts.get(y, 0) for y in all_years], dtype=float)
        d = np.array([total_per_year.get(y, 1) for y in all_years], dtype=float)
        n_years = len(all_years)

        # Baseline probability p0 and burst probability p1
        p0 = float(sum(r)) / float(sum(d)) if sum(d) > 0 else 1e-6
        p0 = min(max(p0, 1e-6), 0.99)
        p1 = min(p0 * s, 0.999)

        if p1 <= p0:
            continue

        # Dynamic programming / Viterbi decoding over 2 states: 0 (baseline), 1 (burst)
        # Cost matrix: cost of emitting r[t] given state q in {0, 1}
        # Binomial log-likelihood loss
        def emit_cost(q, k, n):
            p = p1 if q == 1 else p0
            # negative log-likelihood: - (k*log(p) + (n-k)*log(1-p))
            k_clamped = min(k, n)
            return - (k_clamped * np.log(p) + (n - k_clamped) * np.log(1.0 - p))

        # Transition cost tau(q_prev, q_curr)
        # 0 -> 1: gamma * log(n_years), 1 -> 0: 0, 0 -> 0: 0, 1 -> 1: 0
        trans_cost_01 = gamma * np.log(n_years) if n_years > 1 else 0.0

        dp = np.zeros((n_years, 2))
        path = np.zeros((n_years, 2), dtype=int)

        dp[0, 0] = emit_cost(0, r[0], d[0])
        dp[0, 1] = emit_cost(1, r[0], d[0]) + trans_cost_01

        for t in range(1, n_years):
            # State 0 at t
            c00 = dp[t-1, 0]
            c10 = dp[t-1, 1]
            if c00 <= c10:
                dp[t, 0] = c00 + emit_cost(0, r[t], d[t])
                path[t, 0] = 0
            else:
                dp[t, 0] = c10 + emit_cost(0, r[t], d[t])
                path[t, 0] = 1

            # State 1 at t
            c01 = dp[t-1, 0] + trans_cost_01
            c11 = dp[t-1, 1]
            if c01 <= c11:
                dp[t, 1] = c01 + emit_cost(1, r[t], d[t])
                path[t, 1] = 0
            else:
                dp[t, 1] = c11 + emit_cost(1, r[t], d[t])
                path[t, 1] = 1

        # Traceback best state sequence
        best_state = 0 if dp[-1, 0] <= dp[-1, 1] else 1
        states = [best_state]
        for t in range(n_years - 1, 0, -1):
            best_state = path[t, best_state]
            states.append(best_state)
        states.reverse()

        # Identify contiguous burst spans (state == 1)
        in_burst = False
        start_idx = 0
        for idx, st in enumerate(states):
            if st == 1 and not in_burst:
                in_burst = True
                start_idx = idx
            elif st == 0 and in_burst:
                in_burst = False
                end_idx = idx - 1
                # Calculate burst weight / strength
                burst_r = sum(r[start_idx:end_idx+1])
                burst_d = sum(d[start_idx:end_idx+1])
                expected = burst_d * p0
                weight = max(0.0, burst_r - expected)
                if weight >= min_burst_weight:
                    bursts.append({
                        "Term": term,
                        "Weight": round(weight, 2),
                        "Start_Year": all_years[start_idx],
                        "End_Year": all_years[end_idx],
                        "Duration": all_years[end_idx] - all_years[start_idx] + 1
                    })

        if in_burst:
            end_idx = n_years - 1
            burst_r = sum(r[start_idx:end_idx+1])
            burst_d = sum(d[start_idx:end_idx+1])
            expected = burst_d * p0
            weight = max(0.0, burst_r - expected)
            if weight >= min_burst_weight:
                bursts.append({
                    "Term": term,
                    "Weight": round(weight, 2),
                    "Start_Year": all_years[start_idx],
                    "End_Year": all_years[end_idx],
                    "Duration": all_years[end_idx] - all_years[start_idx] + 1
                })

    res_df = pd.DataFrame(bursts)
    if not res_df.empty:
        res_df = res_df.sort_values(by=["Weight", "Start_Year"], ascending=[False, False]).reset_index(drop=True)
    return res_df

