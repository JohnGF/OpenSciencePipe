import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict, Optional, List, Any

logger = logging.getLogger(__name__)

class TemporalDeltaAnalysis:
    r"""
    Computes scientific temporal dynamics and delta shifts (\Delta) between
    baseline (historical) vs modern epochs for bibliometric features.
    """
    def __init__(self):
        pass

    def compute_temporal_deltas(
        self, 
        df: pd.DataFrame, 
        category_col: str, 
        year_col: str = "Year",
        split_year: Optional[int] = None,
        paper_id_col: Optional[str] = None
    ) -> pd.DataFrame:
        r"""
        Computes volume and market share deltas (\Delta Share %) between two temporal epochs.
        If paper_id_col is provided, calculates multi-label Paper Penetration Rate (% of unique papers
        containing each category). Otherwise, calculates token occurrence share.
        """
        if df.empty or category_col not in df.columns or year_col not in df.columns:
            logger.warning(f"Required columns missing for temporal delta analysis on '{category_col}'.")
            return pd.DataFrame()

        clean_df = df.dropna(subset=[category_col, year_col]).copy()
        clean_df[year_col] = pd.to_numeric(clean_df[year_col], errors="coerce")
        clean_df = clean_df.dropna(subset=[year_col])
        clean_df[year_col] = clean_df[year_col].astype(int)

        years = sorted(clean_df[year_col].unique())
        if len(years) < 2:
            logger.warning("Insufficient year span for temporal delta calculation.")
            return pd.DataFrame()

        if split_year is None:
            split_year = int(np.median(years))

        t1_df = clean_df[clean_df[year_col] < split_year]
        t2_df = clean_df[clean_df[year_col] >= split_year]

        use_paper_penetration = paper_id_col is not None and paper_id_col in clean_df.columns
        if use_paper_penetration:
            total_t1 = t1_df[paper_id_col].nunique()
            total_t2 = t2_df[paper_id_col].nunique()
            t1_counts = t1_df.groupby(category_col)[paper_id_col].nunique()
            t2_counts = t2_df.groupby(category_col)[paper_id_col].nunique()
        else:
            total_t1 = len(t1_df)
            total_t2 = len(t2_df)
            t1_counts = t1_df[category_col].value_counts()
            t2_counts = t2_df[category_col].value_counts()

        total_t1 = max(total_t1, 1)
        total_t2 = max(total_t2, 1)

        all_categories = set(t1_counts.index).union(set(t2_counts.index))

        records = []
        for cat in all_categories:
            n_t1 = int(t1_counts.get(cat, 0))
            n_t2 = int(t2_counts.get(cat, 0))
            
            s_t1 = (n_t1 / total_t1) * 100.0
            s_t2 = (n_t2 / total_t2) * 100.0
            
            delta_share = s_t2 - s_t1
            fold_change = (s_t2 / s_t1) if s_t1 > 0 else (s_t2 if s_t2 > 0 else 1.0)
            
            if delta_share > 1.5:
                trajectory = "Emerging Frontier"
            elif delta_share < -1.5:
                trajectory = "Maturing/Declining"
            else:
                trajectory = "Sustained Core"

            records.append({
                "Category": cat,
                "Baseline_Count_T1": n_t1,
                "Modern_Count_T2": n_t2,
                "Baseline_Share_Pct": round(s_t1, 2),
                "Modern_Share_Pct": round(s_t2, 2),
                "Delta_Share_Pct": round(delta_share, 2),
                "Fold_Change": round(fold_change, 2),
                "Trajectory": trajectory
            })

        result_df = pd.DataFrame(records)
        if not result_df.empty:
            result_df = result_df.sort_values("Delta_Share_Pct", ascending=False).reset_index(drop=True)

        logger.info(f"Computed temporal delta analysis across {len(result_df)} items (Split Year: {split_year}, Multi-Label Paper Penetration: {use_paper_penetration}).")
        return result_df

    def compute_annual_trajectories(
        self,
        df: pd.DataFrame,
        category_col: str,
        year_col: str = "Year",
        top_n: int = 10,
        min_total_count: int = 5,
        paper_id_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Computes year-by-year normalized market share (%) and counts for top categories.
        If paper_id_col is provided, computes multi-label paper penetration share (% of papers).
        Returns a tidy DataFrame with columns:
        [Year, Category, Count, Total_Year_Pubs, Market_Share_Pct, YoY_Delta_Pct]
        """
        if df.empty or category_col not in df.columns or year_col not in df.columns:
            logger.warning(f"Required columns missing for annual trajectory analysis on '{category_col}'.")
            return pd.DataFrame()

        clean_df = df.dropna(subset=[category_col, year_col]).copy()
        clean_df[year_col] = pd.to_numeric(clean_df[year_col], errors="coerce")
        clean_df = clean_df.dropna(subset=[year_col])
        clean_df[year_col] = clean_df[year_col].astype(int)

        years = sorted(clean_df[year_col].unique())
        if len(years) < 2:
            logger.warning("Insufficient year span for annual trajectory calculation.")
            return pd.DataFrame()

        use_paper_penetration = paper_id_col is not None and paper_id_col in clean_df.columns
        if use_paper_penetration:
            cat_counts = clean_df.groupby(category_col)[paper_id_col].nunique()
            annual_totals = clean_df.groupby(year_col)[paper_id_col].nunique().to_dict()
        else:
            cat_counts = clean_df[category_col].value_counts()
            annual_totals = clean_df.groupby(year_col).size().to_dict()

        cat_counts = cat_counts[cat_counts >= min_total_count]
        top_cats = cat_counts.sort_values(ascending=False).head(top_n).index.tolist()

        if not top_cats:
            return pd.DataFrame()

        records = []
        for cat in top_cats:
            cat_df = clean_df[clean_df[category_col] == cat]
            if use_paper_penetration:
                annual_cat_counts = cat_df.groupby(year_col)[paper_id_col].nunique().to_dict()
            else:
                annual_cat_counts = cat_df.groupby(year_col).size().to_dict()

            prev_share = None
            for yr in years:
                count = int(annual_cat_counts.get(yr, 0))
                tot = int(annual_totals.get(yr, 1))
                share_pct = round((count / tot) * 100.0, 3) if tot > 0 else 0.0
                yoy_delta = round(share_pct - prev_share, 3) if prev_share is not None else 0.0
                prev_share = share_pct

                records.append({
                    "Year": yr,
                    "Category": cat,
                    "Count": count,
                    "Total_Year_Pubs": tot,
                    "Market_Share_Pct": share_pct,
                    "YoY_Delta_Pct": yoy_delta
                })

        res = pd.DataFrame(records)
        logger.info(f"Computed annual trajectories for {len(top_cats)} categories across {len(years)} years.")
        return res

    def compute_multi_epoch_crosstab(
        self,
        df: pd.DataFrame,
        row_col: str,
        col_col: str,
        year_col: str = "Year",
        epoch_bins: Optional[List[Tuple[int, int, str]]] = None,
        n_bins: int = 3
    ) -> Dict[str, pd.DataFrame]:
        """
        Computes normalized contingency tables across multiple temporal epochs.
        Returns a dict mapping epoch_label -> DataFrame of row x col percentages.
        """
        if df.empty or row_col not in df.columns or col_col not in df.columns or year_col not in df.columns:
            logger.warning("Missing columns for multi-epoch crosstabulation.")
            return {}

        clean_df = df.dropna(subset=[row_col, col_col, year_col]).copy()
        clean_df[year_col] = pd.to_numeric(clean_df[year_col], errors="coerce")
        clean_df = clean_df.dropna(subset=[year_col])
        clean_df[year_col] = clean_df[year_col].astype(int)

        years = sorted(clean_df[year_col].unique())
        if len(years) < 2:
            return {}

        if epoch_bins is None:
            min_yr, max_yr = min(years), max(years)
            step = max(1, int(round((max_yr - min_yr + 1) / n_bins)))
            epoch_bins = []
            cur_start = min_yr
            for i in range(n_bins):
                cur_end = min(max_yr, cur_start + step - 1) if i < n_bins - 1 else max_yr
                label = f"{cur_start}-{cur_end}"
                epoch_bins.append((cur_start, cur_end, label))
                cur_start = cur_end + 1
                if cur_start > max_yr:
                    break

        matrices = {}
        for start, end, label in epoch_bins:
            sub = clean_df[(clean_df[year_col] >= start) & (clean_df[year_col] <= end)]
            if sub.empty:
                continue
            ct = pd.crosstab(sub[row_col], sub[col_col], normalize="index") * 100.0
            matrices[label] = ct.round(2)

        logger.info(f"Computed multi-epoch crosstabs across {len(matrices)} epochs.")
        return matrices

