import polars as pl
import pandas as pd
from typing import Tuple
import logging
from src.core.ingestion import extract_countries

logger = logging.getLogger(__name__)

class CountryAnalysis:
    def __init__(self):
        pass

    def process_countries(self, df: pl.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Processes a publication DataFrame, extracts countries from affiliations,
        and computes country evolution statistics over the years.
        
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: 
                - exploded_publications: DataFrame with Title, Year, Country
                - country_evolution: DataFrame with Year, Country, Count
        """
        logger.info("Extracting country affiliation data...")
        df_dicts = df.to_dicts()
        records = []
        
        for row in df_dicts:
            year = row.get("Year")
            affil = row.get("Affiliations")
            title = row.get("Title")
            
            if not affil or year is None:
                continue
                
            try:
                year_val = int(year)
            except (ValueError, TypeError):
                continue
            
            countries = extract_countries(str(affil))
            if not countries:
                continue
                
            for country in countries:
                records.append({
                    "Title": title,
                    "Year": year_val,
                    "Country": country
                })
                
        if not records:
            logger.warning("No country affiliations extracted.")
            return pd.DataFrame(), pd.DataFrame()
            
        exploded_pl = pl.DataFrame(records)
        
        # Calculate yearly country frequency
        evolution_pl = exploded_pl.group_by(["Year", "Country"]).len().sort(["Year", "Country"])
        evolution_pl = evolution_pl.rename({"len": "Count"})
        
        logger.info(f"Extracted {len(records)} country affiliation records across {evolution_pl['Country'].n_unique()} unique countries.")
        return exploded_pl.to_pandas(), evolution_pl.to_pandas()

    def calculate_country_cagr(self, evolution_df: pd.DataFrame, min_total_papers: int = 10) -> pd.DataFrame:
        """
        Computes total publication count and CAGR growth rate (%) for each country.
        """
        if evolution_df.empty or "Country" not in evolution_df.columns:
            return pd.DataFrame()

        records = []
        grouped = evolution_df.groupby("Country")
        
        for country, group in grouped:
            total_count = group["Count"].sum()
            if total_count < min_total_papers:
                continue
                
            sorted_g = group.sort_values("Year")
            first_row = sorted_g.iloc[0]
            last_row = sorted_g.iloc[-1]
            
            y_start = int(first_row["Year"])
            y_end = int(last_row["Year"])
            c_start = int(first_row["Count"])
            c_end = int(last_row["Count"])
            
            y_diff = y_end - y_start
            if y_diff > 0 and c_start > 0:
                cagr = ((c_end / c_start) ** (1.0 / y_diff) - 1.0) * 100.0
            else:
                cagr = 0.0
                
            trend = "Surging" if cagr > 15 else ("Emerging" if cagr > 5 else "Established")
            
            records.append({
                "Country": country,
                "Total_Count": total_count,
                "First_Year": y_start,
                "First_Year_Count": c_start,
                "Last_Year": y_end,
                "Last_Year_Count": c_end,
                "CAGR_percent": cagr,
                "Trend": trend
            })
            
        res_df = pd.DataFrame(records)
        if not res_df.empty:
            res_df = res_df.sort_values("Total_Count", ascending=False).reset_index(drop=True)
        return res_df


def compute_rbo(l1: list, l2: list, p: float = 0.9) -> float:
    """
    Computes Rank-Biased Overlap (RBO) between two ranked lists according to Webber et al. (2010).
    Handles non-conjoint / disjoint rankings without discarding items.
    """
    if not l1 or not l2:
        return 0.0
    k = max(len(l1), len(l2))
    seen1, seen2 = set(), set()
    rbo_sum = 0.0
    for d in range(1, k + 1):
        if d <= len(l1):
            seen1.add(l1[d - 1])
        if d <= len(l2):
            seen2.add(l2[d - 1])
        overlap = len(seen1 & seen2)
        agreement = overlap / d
        rbo_sum += agreement * (p ** (d - 1))
    w_sum = sum(p ** (d - 1) for d in range(1, k + 1))
    return float(rbo_sum / w_sum) if w_sum > 0 else 0.0


def compute_jaccard_at_k(l1: list, l2: list, k: int = 10) -> float:
    """
    Computes Jaccard similarity at depth K between two ranked lists.
    """
    s1 = set(l1[:k])
    s2 = set(l2[:k])
    union_s = s1 | s2
    return float(len(s1 & s2) / len(union_s)) if union_s else 0.0
