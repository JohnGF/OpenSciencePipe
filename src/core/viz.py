import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import polars as pl
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Tuple



class Visualization:
    def __init__(self, style: str = "whitegrid"):
        sns.set_style(style)
        plt.rcParams["figure.figsize"] = (12, 7)

    @staticmethod
    def _world_geojson_path() -> Optional[str]:
        """Resolve world.geojson: settings/templates/maps/ first, src/templates/ legacy fallback."""
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.abspath(os.path.join(here, "..", ".."))
        for cand in (
            os.path.join(repo_root, "settings", "templates", "maps", "world.geojson"),
            os.path.join(here, "..", "templates", "world.geojson"),
        ):
            if os.path.exists(cand):
                return cand
        return None

    def plot_yearly_growth(
        self,
        df: pl.DataFrame,
        save_path: Optional[str] = None,
        max_year: Optional[int] = None,
        min_year: Optional[int] = None,
    ) -> Optional[pd.DataFrame]:
        """Plots publication counts and YoY growth percentages for complete historical years.

        The study window defaults to the date bounds in the query configuration
        file (data/query.txt) and is always expanded to cover the actual data range.
        """
        if df.is_empty():
            return None

        # Derive year bounds from the query config, falling back to the data range.
        from src.core.study_config import load_study_config

        cfg = load_study_config()

        data_years = df.select(pl.col("Year").cast(pl.Int64).drop_nulls())
        data_min = int(data_years.min().item()) if not data_years.is_empty() else None
        data_max = int(data_years.max().item()) if not data_years.is_empty() else None

        if min_year is None:
            min_year = cfg.get("start_year") or data_min
        if max_year is None:
            max_year = cfg.get("end_year") or data_max

        # Never truncate the available data.
        if data_min is not None and min_year is not None:
            min_year = min(min_year, data_min)
        if data_max is not None and max_year is not None:
            max_year = max(max_year, data_max)

        # Filter complete historical years (excluding incomplete/future indexing artifacts > max_year)
        filtered_df = df.filter(
            (pl.col("Year") >= min_year) & (pl.col("Year") <= max_year)
        )
        if filtered_df.is_empty():
            filtered_df = df

        yearly_counts = filtered_df.group_by("Year").len().sort("Year")
        yearly_counts = yearly_counts.with_columns(pl.col("len").cast(pl.Int64))

        pdf = yearly_counts.to_pandas()
        pdf["previous_year_len"] = pdf["len"].shift(1)
        pdf["growth_pct"] = (
            (pdf["len"] - pdf["previous_year_len"]) / pdf["previous_year_len"]
        ) * 100
        pdf["growth_pct"] = pdf["growth_pct"].fillna(0.0)

        pdf["is_projected"] = False
        pdf["projected_len"] = pdf["len"]
        pdf["projected_growth_pct"] = pdf["growth_pct"]

        # Mark the current calendar year as partial (YTD) since it is still in progress.
        current_year = datetime.date.today().year
        pdf["is_partial"] = pdf["Year"] == current_year
        has_partial = bool(pdf["is_partial"].any())

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        years = pdf["Year"].astype(str).tolist()

        # Plot 1: Counts
        partial_labeled = False
        observed_labeled = False
        for i, row in pdf.iterrows():
            if row["is_partial"]:
                label = "Partial Year (YTD)" if not partial_labeled else ""
                partial_labeled = True
                ax1.bar(
                    years[i],
                    row["len"],
                    color="skyblue",
                    edgecolor="black",
                    linewidth=0.8,
                    hatch="///",
                    alpha=0.85,
                    label=label,
                )
            else:
                label = "Observed Publications" if not observed_labeled else ""
                observed_labeled = True
                ax1.bar(years[i], row["len"], color="skyblue", label=label)
            ax1.text(
                i,
                row["len"] + (row["len"] * 0.01),
                f"{int(row['len']):,}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

        ax1.set_ylabel("Number of Publications", fontsize=11, fontweight="bold")
        ax1.set_title(
            f"Historical Publication Evolution ({min_year} - {max_year})",
            fontsize=14,
            pad=15,
            fontweight="bold",
        )
        ax1.grid(axis="y", linestyle="--", alpha=0.7)
        ax1.legend(loc="upper left")

        # Plot 2: YoY Growth Rate (%)
        partial_labeled = False
        for i, row in pdf.iterrows():
            yval = row["growth_pct"]
            color = "lightcoral" if yval >= 0 else "lightskyblue"
            if row["is_partial"]:
                label = "Partial Year (YTD)" if not partial_labeled else ""
                partial_labeled = True
                ax2.bar(
                    years[i],
                    yval,
                    color=color,
                    edgecolor="black",
                    linewidth=0.8,
                    hatch="///",
                    alpha=0.85,
                    label=label,
                )
            else:
                ax2.bar(years[i], yval, color=color, edgecolor="black", linewidth=0.5)
            offset = 0.5 if yval >= 0 else -2.5
            ytd_suffix = " (YTD)" if row["is_partial"] else ""
            ax2.text(
                i,
                yval + offset,
                f"{yval:+.1f}%{ytd_suffix}",
                ha="center",
                va="bottom" if yval >= 0 else "top",
                fontsize=9,
                fontweight="bold",
            )

        ax2.set_ylabel("YoY Growth Rate (%)", fontsize=11, fontweight="bold")
        ax2.axhline(0, color="grey", linewidth=0.8, linestyle="--")
        ax2.grid(axis="y", linestyle="--", alpha=0.7)
        ax2.legend(loc="best")

        plt.xticks(rotation=45)
        if has_partial:
            plt.figtext(
                0.5,
                0.01,
                f"Note: {current_year} is still in progress and shown as a partial year (YTD).",
                ha="center",
                fontsize=9,
                style="italic",
                alpha=0.75,
            )
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
        plt.close()
        return pdf

    def plot_heatmap(
        self, matrix_df: pl.DataFrame, title: str, save_path: Optional[str] = None
    ):
        """Generates a seaborn heatmap for correlation or co-occurrence matrices."""
        plt.figure(figsize=(14, 10))
        sns.heatmap(
            matrix_df.to_pandas().set_index(matrix_df.columns[0]),
            annot=False,
            cmap="YlGnBu",
        )
        plt.title(title)
        if save_path:
            plt.savefig(save_path)
        return plt.gcf()

    def plot_country_evolution(
        self, df: pd.DataFrame, top_n: int = 10, save_path: Optional[str] = None
    ):
        """
        Plots the temporal evolution of the top N countries.

        Args:
            df: DataFrame containing Year, Country, Count columns.
            top_n: Number of top countries to include based on total counts.
            save_path: Optional path to save the generated high-res PDF.
        """
        if df.empty:
            return None

        # Find top N countries by total contributions
        top_countries = df.groupby("Country")["Count"].sum().nlargest(top_n).index
        filtered_df = df[df["Country"].isin(top_countries)]

        plt.figure(figsize=(14, 8))
        sns.lineplot(
            data=filtered_df,
            x="Year",
            y="Count",
            hue="Country",
            marker="o",
            linewidth=2.5,
            palette="tab10",
        )

        plt.title(
            f"Evolution of Top {top_n} Research Contributor Countries",
            fontsize=16,
            pad=15,
        )
        plt.xlabel("Year", fontsize=12)
        plt.ylabel("Publication Count", fontsize=12)
        plt.legend(
            title="Countries", bbox_to_anchor=(1.05, 1), loc="upper left", frameon=True
        )
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

    def plot_country_choropleth_map(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ):
        """
        Plots a global choropleth heatmap of research publication volume by country.
        """
        import os
        import numpy as np
        import logging

        logger = logging.getLogger(__name__)

        if df.empty or "Country" not in df.columns or "Count" not in df.columns:
            logger.warning("No country counts available for choropleth map.")
            return

        try:
            import geopandas as gpd
        except ImportError:
            logger.warning("geopandas not available; skipping country choropleth map.")
            return

        # Aggregate total counts per country
        country_totals = df.groupby("Country")["Count"].sum().reset_index()

        # Alias map for common name mismatches
        aliases = {
            "United States": "United States of America",
            "USA": "United States of America",
            "US": "United States of America",
            "UK": "United Kingdom",
            "Great Britain": "United Kingdom",
            "South Korea": "South Korea",
            "Korea": "South Korea",
            "Russia": "Russian Federation",
        }
        country_totals["Country"] = country_totals["Country"].replace(aliases)
        country_totals = country_totals.groupby("Country")["Count"].sum().reset_index()

        geojson_path = self._world_geojson_path()
        if not geojson_path:
            logger.warning("world.geojson not found; skipping choropleth map.")
            return

        try:
            world = gpd.read_file(geojson_path)
            world["Country"] = world["name"]
            merged = world.merge(country_totals, on="Country", how="left")
            merged["Count"] = merged["Count"].fillna(0)
            merged["LogCount"] = np.log1p(merged["Count"])

            fig, ax = plt.subplots(figsize=(14, 8))
            merged.plot(
                column="LogCount",
                cmap="YlOrRd",
                linewidth=0.4,
                ax=ax,
                edgecolor="#555555",
                legend=False,
                missing_kwds={"color": "#e0e0e0", "edgecolor": "#cccccc"},
            )

            sm = plt.cm.ScalarMappable(
                cmap="YlOrRd", norm=plt.Normalize(vmin=0, vmax=merged["LogCount"].max())
            )
            sm._A = []
            cbar = fig.colorbar(
                sm, ax=ax, orientation="horizontal", pad=0.04, shrink=0.65
            )
            cbar.set_label(
                "Publication Volume (Log Scale)", fontsize=11, fontweight="bold"
            )

            ax.set_title(
                "Global Research Output & Institutional Heatmap by Country",
                fontsize=16,
                pad=15,
                fontweight="bold",
            )
            ax.set_axis_off()
            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                png_path = save_path.replace(".pdf", ".png")
                plt.savefig(png_path, dpi=300, bbox_inches="tight")
                logger.info(
                    f"Saved country choropleth map to {save_path} and {png_path}"
                )
            plt.close()
        except Exception as e:
            logger.warning(f"Could not render country choropleth map: {e}")

    def plot_temporal_delta_shifts(
        self,
        delta_df: pd.DataFrame,
        title_suffix: str = "Research Topics",
        save_path: Optional[str] = None,
    ):
        r"""
        Plots a horizontal Diverging Bar Chart showing the Market Share Delta (\Delta Share %)
        between baseline vs modern epochs.
        """
        import logging

        logger = logging.getLogger(__name__)

        if (
            delta_df.empty
            or "Category" not in delta_df.columns
            or "Delta_Share_Pct" not in delta_df.columns
        ):
            logger.warning("Invalid DataFrame for temporal delta plot.")
            return

        top_emerging = delta_df.nlargest(10, "Delta_Share_Pct")
        top_declining = delta_df.nsmallest(10, "Delta_Share_Pct")
        plot_df = (
            pd.concat([top_emerging, top_declining])
            .drop_duplicates()
            .sort_values("Delta_Share_Pct")
        )

        colors = [
            "#2ca02c" if val >= 0 else "#d62728" for val in plot_df["Delta_Share_Pct"]
        ]

        plt.figure(figsize=(12, 7))
        bars = plt.barh(
            plot_df["Category"],
            plot_df["Delta_Share_Pct"],
            color=colors,
            edgecolor="#333333",
            height=0.6,
        )

        plt.axvline(0, color="black", linewidth=1, linestyle="--")
        plt.title(
            f"Scientific Temporal Shift (\\Delta Market Share %): {title_suffix}",
            fontsize=15,
            pad=15,
            fontweight="bold",
        )
        plt.xlabel(
            "Market Share Delta (\\Delta % Points between Baseline vs Modern Epoch)",
            fontsize=11,
            fontweight="bold",
        )
        plt.ylabel(title_suffix, fontsize=11, fontweight="bold")
        plt.grid(True, linestyle="--", alpha=0.5)

        for bar in bars:
            val = bar.get_width()
            offset = 0.1 if val >= 0 else -0.5
            plt.text(
                val + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}%",
                va="center",
                fontsize=9,
                fontweight="bold",
            )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved temporal delta chart to {save_path} and {png_path}")
        plt.close()

    def plot_annual_share_trajectories(
        self,
        trajectory_df: pd.DataFrame,
        category_col: str = "Category",
        year_col: str = "Year",
        share_col: str = "Market_Share_Pct",
        title_suffix: str = "Technique",
        save_path: Optional[str] = None,
    ):
        """
        Plots annual market share trajectories (%) over time for key categories.
        """
        import logging

        logger = logging.getLogger(__name__)

        if (
            trajectory_df.empty
            or category_col not in trajectory_df.columns
            or year_col not in trajectory_df.columns
            or share_col not in trajectory_df.columns
        ):
            logger.warning("Invalid DataFrame for annual trajectory plot.")
            return

        plt.figure(figsize=(12, 7))
        categories = trajectory_df[category_col].unique()

        palette = sns.color_palette("tab10", len(categories))
        for idx, cat in enumerate(categories):
            cat_df = trajectory_df[trajectory_df[category_col] == cat].sort_values(year_col)
            plt.plot(
                cat_df[year_col],
                cat_df[share_col],
                marker="o",
                linewidth=2.2,
                label=str(cat),
                color=palette[idx % len(palette)],
            )

        plt.title(
            f"Annual Market Share Evolution (%): {title_suffix}",
            fontsize=15,
            pad=15,
            fontweight="bold",
        )
        plt.xlabel("Year", fontsize=11, fontweight="bold")
        plt.ylabel("Annual Market Share (%)", fontsize=11, fontweight="bold")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", frameon=True)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved annual share trajectories to {save_path} and {png_path}")
        plt.close()

    def plot_faceted_crosstab_heatmap(
        self,
        epoch_matrices: Dict[str, pd.DataFrame],
        title_prefix: str = "Methodology vs Application Evolution",
        save_path: Optional[str] = None,
    ):
        """
        Plots side-by-side faceted heatmaps across multiple epochs.
        """
        import logging

        logger = logging.getLogger(__name__)

        if not epoch_matrices:
            logger.warning("No epoch matrices provided for faceted heatmap.")
            return

        n_epochs = len(epoch_matrices)
        fig, axes = plt.subplots(1, n_epochs, figsize=(max(12, 6 * n_epochs), 6), sharey=True)
        if n_epochs == 1:
            axes = [axes]

        max_val = max((m.values.max() for m in epoch_matrices.values() if not m.empty), default=10.0)
        vmax = max(10.0, float(max_val))

        for ax, (epoch_label, matrix) in zip(axes, epoch_matrices.items()):
            sns.heatmap(
                matrix,
                annot=True,
                fmt=".1f",
                cmap="Blues",
                vmin=0,
                vmax=vmax,
                cbar=(ax == axes[-1]),
                ax=ax,
            )
            ax.set_title(f"Epoch: {epoch_label}", fontsize=12, fontweight="bold")
            ax.set_xlabel("Application Field", fontsize=10, fontweight="bold")
            if ax == axes[0]:
                ax.set_ylabel("Methodology / Technique", fontsize=10, fontweight="bold")
            else:
                ax.set_ylabel("")

        plt.suptitle(title_prefix, fontsize=14, fontweight="bold", y=1.02)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved faceted crosstab heatmap to {save_path} and {png_path}")
        plt.close()

    def plot_llm_noise_paradigm(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ):
        """
        Plots a donut chart visualization of LLM / AI Noise Treatment Paradigms across papers.
        """
        import logging

        logger = logging.getLogger(__name__)

        if df.empty:
            return

        paradigm_col = "noise_paradigm" if "noise_paradigm" in df.columns else None
        if not paradigm_col:
            titles = (
                df["Title"].fillna("").astype(str).str.lower()
                if "Title" in df.columns
                else pd.Series([""] * len(df))
            )
            abstracts = (
                df["Abstract"].fillna("").astype(str).str.lower()
                if "Abstract" in df.columns
                else pd.Series([""] * len(df))
            )
            text = titles + " " + abstracts

            paradigms = []
            for t in text:
                if any(
                    w in t
                    for w in [
                        "ica",
                        "wavelet",
                        "artifact removal",
                        "filtering",
                        "suppression",
                        "denois",
                    ]
                ):
                    paradigms.append("Artifact Filtering & Removal")
                elif any(
                    w in t
                    for w in ["stochastic", "resonance", "information", "entropy"]
                ):
                    paradigms.append("Noise-as-Information")
                elif any(
                    w in t
                    for w in ["deep learning", "cnn", "robust", "decoding", "latent"]
                ):
                    paradigms.append("Robust Latent Decoding")
                else:
                    paradigms.append("General Analysis")
            counts = pd.Series(paradigms).value_counts()
        else:
            label_map = {
                "filtering_removal": "Artifact Filtering & Removal",
                "noise_as_information": "Noise-as-Information",
                "robust_decoding": "Robust Latent Decoding",
                "unspecified": "General Analysis",
            }
            counts = df[paradigm_col].replace(label_map).value_counts()

        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"][: len(counts)]

        fig, ax = plt.subplots(figsize=(10, 7))
        wedges, texts, autotexts = ax.pie(
            counts.values,
            labels=counts.index,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.75,
            wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
        )

        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_weight("bold")
            autotext.set_fontsize(11)

        ax.set_title("Deterministic Keyword-Rule Paradigm Taxonomy", fontsize=15, pad=15, fontweight="bold")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved LLM noise paradigm chart to {save_path} and {png_path}")
        plt.close()

    def plot_method_application_matrix(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ):
        """
        Plots a 2D Heatmap Matrix pairing Methodologies / Techniques with Application Fields.
        """
        import logging
        import seaborn as sns

        logger = logging.getLogger(__name__)

        if df.empty:
            return

        titles = (
            df["Title"].fillna("").astype(str).str.lower()
            if "Title" in df.columns
            else pd.Series([""] * len(df))
        )
        abstracts = (
            df["Abstract"].fillna("").astype(str).str.lower()
            if "Abstract" in df.columns
            else pd.Series([""] * len(df))
        )
        text = titles + " " + abstracts

        methods = []
        apps = []

        for t in text:
            if any(
                w in t
                for w in [
                    "ica",
                    "wavelet",
                    "artifact removal",
                    "filtering",
                    "suppression",
                    "denois",
                ]
            ):
                m = "ICA / Wavelet Denoising"
            elif any(
                w in t
                for w in [
                    "deep learning",
                    "cnn",
                    "convolutional",
                    "transformer",
                    "neural network",
                ]
            ):
                m = "Deep Learning (CNN/DL)"
            elif any(
                w in t for w in ["csp", "fbcsp", "ssvep", "spatial pattern", "evoked"]
            ):
                m = "Spatial Patterns (CSP/SSVEP)"
            elif any(
                w in t for w in ["stochastic", "resonance", "entropy", "variability"]
            ):
                m = "Stochastic Noise Dynamics"
            else:
                m = "General Signal Processing"

            if any(
                w in t
                for w in [
                    "motor imagery",
                    "bci",
                    "rehabilitation",
                    "prosthetic",
                    "neuroprosthet",
                ]
            ):
                a = "Motor Imagery BCI"
            elif any(w in t for w in ["epilepsy", "seizure", "hfo", "spike", "ictal"]):
                a = "Epilepsy & Seizures"
            elif any(
                w in t for w in ["emotion", "affective", "deap", "valence", "arousal"]
            ):
                a = "Emotion Recognition"
            elif any(w in t for w in ["sleep", "somnology", "staging", "drowsiness"]):
                a = "Sleep Staging"
            elif any(
                w in t
                for w in ["workload", "fatigue", "driving", "cognitive", "mental"]
            ):
                a = "Cognitive Workload"
            else:
                a = "General Clinical & Bio"

            methods.append(m)
            apps.append(a)

        ct = pd.crosstab(
            pd.Series(methods, name="Methodology"),
            pd.Series(apps, name="Application Field"),
        )

        plt.figure(figsize=(11, 7))
        sns.heatmap(
            ct,
            annot=True,
            fmt="d",
            cmap="YlGnBu",
            linewidths=1,
            cbar_kws={"label": "Publication Count"},
        )
        plt.title(
            "Methodology vs Application Field Cross-Tabulation Matrix",
            fontsize=15,
            pad=15,
            fontweight="bold",
        )
        plt.xlabel("Application Field", fontsize=11, fontweight="bold")
        plt.ylabel("Methodology / Technique Used", fontsize=11, fontweight="bold")
        plt.xticks(rotation=30, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(
                f"Saved methodology vs application matrix to {save_path} and {png_path}"
            )
        plt.close()

    def plot_network(
        self,
        edges_df: pd.DataFrame,
        node_meta: pd.DataFrame,
        save_path: Optional[str] = None,
        top_per_community: int = 2,
        show_heatmap: bool = True,
    ):
        """
        Plots a high-resolution, publication-grade co-authorship network focusing on the
        Giant Connected Component and prominent core research communities.
        """
        import networkx as nx

        if edges_df.empty or node_meta.empty:
            return None

        fig, ax = plt.subplots(figsize=(16, 12))

        # Build full NetworkX Graph
        G_full = nx.Graph()
        for _, row in node_meta.iterrows():
            G_full.add_node(
                row["vertex"],
                name=row["author_name"],
                partition=row["partition"],
                size=row.get("num_publications", 1),
                citations=row.get("total_citations", 0),
            )
        for _, row in edges_df.iterrows():
            G_full.add_edge(row["source_id"], row["dest_id"], weight=row["weight"])

        # Filter for Giant Connected Component & prominent nodes to eliminate ugly isolated 2-node noise
        if len(G_full) > 150:
            # Extract components with at least 4 nodes or top 150 authors by citations/pubs
            components = [c for c in nx.connected_components(G_full) if len(c) >= 3]
            if components:
                nodes_to_keep = set().union(*components)
            else:
                nodes_to_keep = set(G_full.nodes())

            # Filter top 150 most prominent authors if network is huge
            top_nodes = sorted(
                nodes_to_keep,
                key=lambda n: (G_full.nodes[n]["size"], G_full.nodes[n]["citations"]),
                reverse=True,
            )[:150]
            G = G_full.subgraph(top_nodes).copy()
        else:
            G = G_full.copy()

        if len(G) == 0:
            G = G_full

        # Layout calculation: calculate clean spring layout with optimal node separation
        pos = nx.spring_layout(G, k=0.45, iterations=120, seed=42)

        # 1. Edge Density Heatmap Layer
        if show_heatmap and len(G.edges) > 5:
            try:
                edge_x = []
                edge_y = []
                for u, v in G.edges:
                    p1 = pos[u]
                    p2 = pos[v]
                    edge_x.extend([p1[0], p2[0], (p1[0] + p2[0]) / 2])
                    edge_y.extend([p1[1], p2[1], (p1[1] + p2[1]) / 2])

                if len(edge_x) > 10:
                    sns.kdeplot(
                        x=edge_x,
                        y=edge_y,
                        ax=ax,
                        cmap="Blues",
                        fill=True,
                        thresh=0.05,
                        levels=12,
                        alpha=0.25,
                        zorder=1,
                    )
            except Exception:
                pass

        # Color mapping (community partitions)
        partitions = [G.nodes[n]["partition"] for n in G.nodes]
        unique_partitions = list(set(partitions))
        color_palette = sns.color_palette("tab10", max(len(unique_partitions), 10))
        partition_colors = {
            p: color_palette[i % len(color_palette)]
            for i, p in enumerate(unique_partitions)
        }
        node_colors = [partition_colors[G.nodes[n]["partition"]] for n in G.nodes]

        # Node sizing scaling
        all_sizes = [G.nodes[n]["size"] for n in G.nodes]
        max_s = max(all_sizes) if all_sizes else 1
        node_sizes = [(G.nodes[n]["size"] / max_s) * 600 + 120 for n in G.nodes]

        # Edge weights scaling
        all_w = [G[u][v]["weight"] for u, v in G.edges]
        max_w = max(all_w) if all_w else 1
        edge_widths = [(G[u][v]["weight"] / max_w) * 3.0 + 0.5 for u, v in G.edges]

        # Draw elements
        edges_collection = nx.draw_networkx_edges(
            G, pos, ax=ax, width=edge_widths, alpha=0.3, edge_color="#555555"
        )
        if edges_collection is not None:
            if isinstance(edges_collection, list):
                for e in edges_collection:
                    e.set_zorder(2)
            else:
                edges_collection.set_zorder(2)

        nodes_collection = nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.9,
            edgecolors="white",
            linewidths=1.0,
        )
        if nodes_collection is not None:
            nodes_collection.set_zorder(3)

        # 2. Prominent Representative Labeling (Top community leaders)
        community_nodes = {}
        for n in G.nodes:
            part = G.nodes[n]["partition"]
            community_nodes.setdefault(part, []).append(n)

        candidate_nodes = []
        for part, nodes_in_part in community_nodes.items():
            sorted_nodes = sorted(
                nodes_in_part,
                key=lambda node: (G.nodes[node]["size"], G.nodes[node]["citations"]),
                reverse=True,
            )
            for rep_node in sorted_nodes[:top_per_community]:
                candidate_nodes.append(rep_node)

        # Limit to top 12 overall core leaders
        candidate_nodes = sorted(
            candidate_nodes, key=lambda n: G.nodes[n]["size"], reverse=True
        )[:12]
        labels = {n: G.nodes[n]["name"] for n in candidate_nodes}

        # Draw popping labels with crisp rounded callout boxes
        for node_id, label_text in labels.items():
            if node_id in pos:
                x, y = pos[node_id]
                ax.text(
                    x,
                    y + 0.04,
                    label_text,
                    fontsize=10,
                    fontweight="bold",
                    ha="center",
                    va="bottom",
                    zorder=4,
                    bbox=dict(
                        boxstyle="round,pad=0.3",
                        fc="white",
                        ec=partition_colors[G.nodes[node_id]["partition"]],
                        alpha=0.95,
                        lw=1.5,
                    ),
                )

        plt.title(
            "Co-authorship Network Density & Key Community Leaders",
            fontsize=18,
            pad=15,
            fontweight="bold",
        )
        plt.axis("off")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_circular_community_network(
        self,
        edges_df: pd.DataFrame,
        node_meta: pd.DataFrame,
        save_path: Optional[str] = None,
        top_per_community: int = 2,
        edge_alpha: float = 0.45,
        max_edge_width: float = 3.5,
    ):
        """
        Plots a publication-grade, uncluttered co-authorship network using a
        Louvain-Grouped Circular Ring Layout with community-colored inter-community collaboration chords.
        """
        import networkx as nx
        import numpy as np
        import matplotlib.patches as mpatches
        from matplotlib.path import Path

        if edges_df.empty or node_meta.empty:
            return None

        fig, ax = plt.subplots(figsize=(16, 14))

        # Build full NetworkX Graph
        G_full = nx.Graph()
        for _, row in node_meta.iterrows():
            G_full.add_node(
                row["vertex"],
                name=row["author_name"],
                partition=row["partition"],
                size=row.get("num_publications", 1),
                citations=row.get("total_citations", 0),
            )
        for _, row in edges_df.iterrows():
            G_full.add_edge(row["source_id"], row["dest_id"], weight=row["weight"])

        # Select top prominent nodes across communities to keep visual presentation ultra-clean
        if len(G_full) > 100:
            top_nodes = sorted(
                G_full.nodes(),
                key=lambda n: (G_full.nodes[n]["size"], G_full.nodes[n]["citations"]),
                reverse=True,
            )[:100]
            G = G_full.subgraph(top_nodes).copy()
        else:
            G = G_full.copy()

        if len(G) == 0:
            G = G_full

        # --- LOUVAIN-GROUPED CIRCULAR LAYOUT ALGORITHM ---
        community_nodes = {}
        for n in G.nodes:
            part = G.nodes[n]["partition"]
            community_nodes.setdefault(part, []).append(n)

        sorted_partitions = sorted(
            community_nodes.keys(), key=lambda p: len(community_nodes[p]), reverse=True
        )
        total_nodes = len(G.nodes)
        pos = {}
        angles = {}

        current_angle = 0.0
        gap_angle = (2 * np.pi * 0.15) / max(len(sorted_partitions), 1)
        available_angle = 2 * np.pi - (gap_angle * len(sorted_partitions))

        color_palette = sns.color_palette("tab10", max(len(sorted_partitions), 10))
        partition_colors = {
            p: color_palette[i % len(color_palette)]
            for i, p in enumerate(sorted_partitions)
        }

        radius = 1.0
        for i, part in enumerate(sorted_partitions):
            nodes_in_part = sorted(
                community_nodes[part], key=lambda n: G.nodes[n]["size"], reverse=True
            )
            part_angle_span = available_angle * (len(nodes_in_part) / total_nodes)

            angle_step = part_angle_span / max(len(nodes_in_part), 1)
            for j, node in enumerate(nodes_in_part):
                theta = current_angle + (j + 0.5) * angle_step
                pos[node] = (radius * np.cos(theta), radius * np.sin(theta))
                angles[node] = theta

            current_angle += part_angle_span + gap_angle

        # 1. Draw Community-Colored Inter-Community Collaboration Chords
        all_w = [G[u][v]["weight"] for u, v in G.edges]
        max_w = max(all_w) if all_w else 1

        for u, v in G.edges:
            p1, p2 = pos[u], pos[v]
            part1, part2 = G.nodes[u]["partition"], G.nodes[v]["partition"]
            w = G[u][v]["weight"]
            lw = (w / max_w) * max_edge_width + 0.8

            edge_c = partition_colors[part1]  # Color by source community

            if part1 == part2:
                # Intra-community edge (perimeter arc)
                ax.plot(
                    [p1[0], p2[0]],
                    [p1[1], p2[1]],
                    color=edge_c,
                    alpha=edge_alpha + 0.1,
                    lw=lw,
                    zorder=2,
                )
            else:
                # Inter-community curved chord
                path_data = [
                    (Path.MOVETO, p1),
                    (Path.CURVE3, (0.0, 0.0)),
                    (Path.CURVE3, p2),
                ]
                codes, verts = zip(*path_data)
                path = Path(verts, codes)
                patch = mpatches.PathPatch(
                    path,
                    facecolor="none",
                    edgecolor=edge_c,
                    alpha=edge_alpha,
                    lw=lw,
                    zorder=1,
                )
                ax.add_patch(patch)

        # 2. Draw Nodes along Circular Ring
        all_sizes = [G.nodes[n]["size"] for n in G.nodes]
        max_s = max(all_sizes) if all_sizes else 1
        node_sizes = [(G.nodes[n]["size"] / max_s) * 500 + 100 for n in G.nodes]
        node_colors = [partition_colors[G.nodes[n]["partition"]] for n in G.nodes]

        ax.scatter(
            [pos[n][0] for n in G.nodes],
            [pos[n][1] for n in G.nodes],
            s=node_sizes,
            c=node_colors,
            alpha=0.95,
            edgecolors="white",
            linewidths=1.2,
            zorder=3,
        )

        # 3. Radial Outward Vector Labeling for ALL Nodes
        for node_id in G.nodes:
            if node_id in pos:
                theta = angles[node_id]
                r_label = radius + 0.04
                lx, ly = r_label * np.cos(theta), r_label * np.sin(theta)

                label_text = G.nodes[node_id]["name"]
                deg_angle = np.degrees(theta) % 360

                # Polar angle text orientation (readable text math)
                if 90 < deg_angle <= 270:
                    rot = deg_angle + 180
                    ha = "right"
                else:
                    rot = deg_angle
                    ha = "left"

                # Font size scaled by publication importance
                size_ratio = G.nodes[node_id]["size"] / max_s
                fs = 7.0 + (size_ratio * 4.0)
                font_weight = "bold" if size_ratio > 0.3 else "normal"

                ax.text(
                    lx,
                    ly,
                    label_text,
                    fontsize=fs,
                    fontweight=font_weight,
                    ha=ha,
                    va="center",
                    rotation=rot,
                    rotation_mode="anchor",
                    color=partition_colors[G.nodes[node_id]["partition"]],
                    zorder=4,
                )

        ax.set_xlim(-1.65, 1.65)
        ax.set_ylim(-1.65, 1.65)
        plt.title(
            "Louvain Community Clustered Co-authorship Ring Network",
            fontsize=18,
            pad=25,
            fontweight="bold",
        )
        plt.axis("off")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_cocitation_network(
        self,
        cocit_df: pd.DataFrame,
        top_n: int = 30,
        title_map: Optional[dict] = None,
        save_path: Optional[str] = None,
    ):
        """
        Plots top co-cited papers network graph with short paper titles and
        clickable OpenAlex / DOI hyperlinked badges.
        """
        if cocit_df.empty:
            return None

        import networkx as nx

        top_cocit = cocit_df.nlargest(top_n * 2, "co_citation_count")
        G = nx.Graph()

        # Built-in seminal paper titles dictionary for co-citation literature
        seminal_titles = {
            "W31182665": "Delorme et al. (2004) EEGLAB",
            "W2122816088": "Oostenveld et al. (2011) FieldTrip",
            "W2768132193": "Lawhern et al. (2018) EEGNet",
            "W2804784400": "Koelstra et al. (2012) DEAP Dataset",
            "W3003415550": "Goldberger et al. (2000) PhysioNet",
            "W4315754639": "Schirrmeister et al. (2017) Deep Learning",
            "W1861891407": "Makeig et al. (1996) BSS Artifact Removal",
            "W1877917243": "Wolpaw et al. (2002) Brain-Computer Interfaces",
            "W1502633200": "Ang et al. (2008) Filter Bank CSP",
            "W1502967669": "Pfurtscheller et al. (1999) Event-Related Sync",
            "W1593442063": "Polich et al. (2007) Updating P300",
            "W2137604100": "Klimesch et al. (1999) EEG Alpha Oscillations",
            "W2567564314": "Bell & Sejnowski (1995) InfoMax ICA",
            "W2125744415": "Brainard et al. (1997) Psychophysics Toolbox",
        }

        # Build node title lookup
        def _get_short_title(raw_id: str) -> str:
            clean_id = str(raw_id).strip().rstrip("/")
            wid = clean_id.split("/")[-1]
            if wid in seminal_titles:
                return seminal_titles[wid]

            if title_map:
                if clean_id in title_map and title_map[clean_id].get("title"):
                    words = title_map[clean_id]["title"].split()
                    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")
                if wid in title_map and title_map[wid].get("title"):
                    words = title_map[wid]["title"].split()
                    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")

            if wid.startswith("W"):
                try:
                    import urllib.request, json

                    req = urllib.request.Request(
                        f"https://api.openalex.org/works/{wid}",
                        headers={"User-Agent": "BibliometricPipeline/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        t = res_data.get("display_name", "")
                        authors = res_data.get("authorships", [])
                        yr = res_data.get("publication_year", "")
                        if t:
                            words = t.split()
                            short_t = " ".join(words[:4]) + (
                                "..." if len(words) > 4 else ""
                            )
                            if authors:
                                first_au = (
                                    authors[0]
                                    .get("author", {})
                                    .get("display_name", "")
                                    .split()[-1]
                                )
                                title_str = f"{first_au} et al. ({yr}) {short_t}"
                            else:
                                title_str = short_t
                            seminal_titles[wid] = title_str
                            return title_str
                except Exception:
                    pass

            if "10." in clean_id:
                return f"DOI: {clean_id[:25]}..."
            return str(clean_id)[:30]

        def _get_url(raw_id: str) -> str:
            clean_id = str(raw_id).strip().rstrip("/")
            wid = clean_id.split("/")[-1]
            if title_map:
                if clean_id in title_map and title_map[clean_id].get("url"):
                    return title_map[clean_id]["url"]
                if wid in title_map and title_map[wid].get("url"):
                    return title_map[wid]["url"]
            if wid in seminal_titles:
                return f"https://openalex.org/{wid}"
            if wid.startswith("W"):
                return f"https://openalex.org/{wid}"
            elif "10." in clean_id:
                doi = clean_id[clean_id.find("10.") :]
                return f"https://doi.org/{doi}"
            return f"https://openalex.org/{wid}"

        for _, row in top_cocit.iterrows():
            c1_raw = str(row["cited_1"]).strip()
            c2_raw = str(row["cited_2"]).strip()

            c1_label = _get_short_title(c1_raw)
            c2_label = _get_short_title(c2_raw)

            G.add_node(c1_label, raw_id=c1_raw, url=_get_url(c1_raw))
            G.add_node(c2_label, raw_id=c2_raw, url=_get_url(c2_raw))
            G.add_edge(c1_label, c2_label, weight=row["co_citation_count"])

        if G.number_of_nodes() == 0:
            return None

        fig, ax = plt.subplots(figsize=(16, 12))
        pos = nx.spring_layout(G, k=0.45, iterations=60, seed=42)

        degrees = dict(G.degree(weight="weight"))
        node_sizes = [degrees.get(n, 1) * 35 + 120 for n in G.nodes]

        nx.draw_networkx_edges(
            G, pos, ax=ax, alpha=0.3, edge_color="#444444", width=1.5
        )

        # Draw node circles with hyperlinks attached
        for n in G.nodes:
            x, y = pos[n]
            sz = degrees.get(n, 1) * 35 + 120
            url = G.nodes[n].get("url", "")
            ax.scatter(
                x,
                y,
                s=sz,
                c="#1f77b4",
                alpha=0.9,
                edgecolors="white",
                linewidths=1.2,
                zorder=3,
                url=url,
            )

        # Attach hyperlinked text badges for all nodes
        top_labels = sorted(G.nodes, key=lambda n: degrees.get(n, 0), reverse=True)
        for n in top_labels:
            x, y = pos[n]
            url = G.nodes[n].get("url", "")

            txt_obj = ax.text(
                x,
                y + 0.035,
                n,
                fontsize=8.5,
                fontweight="bold",
                ha="center",
                va="bottom",
                url=url,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    fc="white",
                    ec="#1f77b4",
                    alpha=0.95,
                    lw=1.2,
                ),
            )
            txt_obj.set_url(url)

        plt.title(
            "Co-Citation Network (Top Frequently Co-Cited Reference Literature)",
            fontsize=16,
            pad=15,
            fontweight="bold",
        )
        plt.axis("off")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_keywords_cagr(
        self, cagr_df: pd.DataFrame, top_n: int = 15, save_path: Optional[str] = None
    ):
        """Plots the CAGR percentage of the top N keywords."""
        if cagr_df.empty:
            return None

        # Sort and get top N keywords
        top_data = cagr_df.nlargest(top_n, "cagr_percent")

        plt.figure(figsize=(14, 8))
        sns.barplot(
            data=top_data, x="cagr_percent", y="standardized_word", palette="viridis"
        )

        plt.title(
            f"Top {top_n} Trending Research Focus Areas (Keyword CAGR %)",
            fontsize=16,
            pad=15,
        )
        plt.xlabel("Compound Annual Growth Rate (CAGR %)", fontsize=12)
        plt.ylabel("Research Keyword", fontsize=12)
        plt.grid(True, axis="x", linestyle="--", alpha=0.5)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

    def plot_topic_distribution(
        self,
        topic_info_df: pd.DataFrame,
        top_n: int = 10,
        save_path: Optional[str] = None,
    ):
        """Plots the size (number of publications) of top BERTopic clusters."""
        if topic_info_df.empty:
            return None

        # Drop outlier topic (-1) if present
        df = topic_info_df[topic_info_df["Topic"] != -1].nlargest(top_n, "Count")

        plt.figure(figsize=(14, 8))
        sns.barplot(data=df, x="Count", y="Name", palette="mako")

        plt.title(
            f"Dominant Research Themes (Publications per Topic)", fontsize=16, pad=15
        )
        plt.xlabel("Number of Publications", fontsize=12)
        plt.ylabel("Topic Description (Top Words)", fontsize=12)
        plt.grid(True, axis="x", linestyle="--", alpha=0.5)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

    def plot_percolation(
        self,
        percolation_df: pd.DataFrame,
        weight_col: str,
        save_path: Optional[str] = None,
    ):
        """Plots 3-subplot percolation analysis (Network Size, Connected Components, and LCC % vs cutoff)."""
        if percolation_df.empty:
            return None

        plt.figure(figsize=(18, 7))

        # Subplot 1: Network Size (Log Scale)
        plt.subplot(1, 3, 1)
        plt.plot(
            percolation_df["cutoff"],
            percolation_df["num_edges"],
            marker="o",
            linestyle="-",
            color="blue",
            label="Number of Edges",
        )
        plt.plot(
            percolation_df["cutoff"],
            percolation_df["num_nodes_in_filtered_graph"],
            marker="x",
            linestyle="--",
            color="green",
            label="Nodes in Filtered Graph",
        )
        plt.title(f"Network Size vs. {weight_col} Cutoff")
        plt.xlabel(f"{weight_col} Cutoff (exclusive)")
        plt.ylabel("Count (Log Scale)")
        plt.yscale("log")
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.legend()

        # Subplot 2: Number of Components
        plt.subplot(1, 3, 2)
        plt.plot(
            percolation_df["cutoff"],
            percolation_df["num_components"],
            marker="o",
            linestyle="-",
            color="orange",
            label="Number of Components",
        )
        plt.title(f"Number of Components vs. {weight_col} Cutoff")
        plt.xlabel(f"{weight_col} Cutoff (exclusive)")
        plt.ylabel("Number of Components")
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.legend()

        # Subplot 3: LCC Size (%)
        plt.subplot(1, 3, 3)
        plt.plot(
            percolation_df["cutoff"],
            percolation_df["lcc_nodes_percentage_of_filtered"],
            marker="o",
            linestyle="-",
            color="red",
            label="LCC % (of filtered nodes)",
        )
        plt.plot(
            percolation_df["cutoff"],
            percolation_df["lcc_nodes_percentage_of_total_initial"],
            marker="x",
            linestyle="--",
            color="purple",
            label="LCC % (of total initial nodes)",
        )
        plt.title(f"LCC Size (%) vs. {weight_col} Cutoff")
        plt.xlabel(f"{weight_col} Cutoff (exclusive)")
        plt.ylabel("LCC Size Percentage")
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300)
            plt.close()
        return plt.gcf()

    def plot_forest(self, df: pd.DataFrame, meta_results: dict, effect_col=None, var_col="v_i", save_path: str = None):
        """Generates a Forest Plot for meta-analysis results."""
        if df.empty:
            return None

        # Resolve effect size column
        eff_candidates = [c for c in [effect_col, "d_i", "meta_standardized_effect_d", "meta_effect_size_d"] if c and c in df.columns]
        if not eff_candidates:
            return None
        actual_eff_col = eff_candidates[0]

        if var_col not in df.columns:
            return None

        fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.4 + 2)))

        y_pos = __import__('numpy').arange(len(df))
        effects = pd.to_numeric(df[actual_eff_col], errors='coerce').values
        variances = pd.to_numeric(df[var_col], errors='coerce').fillna(0.1).values
        ci_lower = effects - 1.96 * __import__('numpy').sqrt(variances)
        ci_upper = effects + 1.96 * __import__('numpy').sqrt(variances)

        # Plot study lines
        ax.errorbar(effects, y_pos, xerr=[effects - ci_lower, ci_upper - effects], fmt='o', color='black', ecolor='gray', capsize=0, label='Studies')

        # Plot summary diamond (Random Effects)
        if "random_effects" in meta_results:
            re = meta_results["random_effects"]
            re_est = re.get("estimate", 0.0)
            re_lower = re.get("ci_lower", 0.0)
            re_upper = re.get("ci_upper", 0.0)

            diamond_x = [re_lower, re_est, re_upper, re_est]
            diamond_y = [-1.5, -1.2, -1.5, -1.8]
            ax.add_patch(plt.Polygon(list(zip(diamond_x, diamond_y)), color='red', label='Random Effects Summary'))
            ax.axvline(re_est, color='red', linestyle='--', alpha=0.5)

        ax.axvline(0, color='black', linestyle='-')
        ax.set_yticks(y_pos)

        # Add labels
        if 'Authors' in df.columns and 'Year' in df.columns:
            labels = [f"{str(row.get('Authors', '')).split(';')[0]} ({str(row.get('Year', '')).replace('.0','')})" for _, row in df.iterrows()]
        else:
            labels = [f"Study {i+1}" for i in range(len(df))]

        ax.set_yticklabels(labels)
        ax.invert_yaxis()  # top-to-bottom
        ax.set_xlabel('Standardized Effect Size (d)')
        ax.set_title('Meta-Analysis Forest Plot')

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300)
            png_path = save_path.replace('.pdf', '.png')
            plt.savefig(png_path, dpi=300)
            plt.close()
        return fig

    def plot_funnel(
        self,
        df: pd.DataFrame,
        effect_col: Optional[str] = None,
        var_col: str = "v_i",
        show_contours: bool = True,
        save_path: Optional[str] = None
    ):
        """
        Generates a Contour-Enhanced Funnel Plot for publication bias evaluation.
        Renders statistical significance contour zones (p < 0.01, 0.05, 0.10) and
        distinguishes observed studies from trim-and-fill imputed studies.
        """
        if df.empty:
            return None

        eff_candidates = [c for c in [effect_col, "d_i", "meta_standardized_effect_d", "meta_effect_size_d"] if c and c in df.columns]
        if not eff_candidates:
            return None
        actual_eff_col = eff_candidates[0]

        if var_col not in df.columns:
            return None

        fig, ax = plt.subplots(figsize=(9, 7))

        effects = pd.to_numeric(df[actual_eff_col], errors='coerce').values
        variances = pd.to_numeric(df[var_col], errors='coerce').fillna(0.1).values
        se = __import__('numpy').sqrt(variances)

        weights = 1.0 / variances
        pooled_effect = float(__import__('numpy').average(effects, weights=weights))
        max_se = float(__import__('numpy').max(se) * 1.15) if len(se) > 0 else 1.0

        y_vals = __import__('numpy').linspace(0.001, max_se, 200)

        # Statistical significance contours centered at null effect (0.0)
        if show_contours:
            # 90% contour (p < 0.10 -> z = 1.645)
            # 95% contour (p < 0.05 -> z = 1.960)
            # 99% contour (p < 0.01 -> z = 2.576)
            x_min = min(float(effects.min()) - 1.0, -3.0 * max_se)
            x_max = max(float(effects.max()) + 1.0, 3.0 * max_se)

            ax.fill_betweenx(y_vals, -2.576 * y_vals, 2.576 * y_vals, color='#D3D3D3', alpha=0.4, label='p > 0.01 (White/Gray)')
            ax.fill_betweenx(y_vals, -1.960 * y_vals, 1.960 * y_vals, color='#E8E8E8', alpha=0.6, label='p > 0.05')
            ax.fill_betweenx(y_vals, -1.645 * y_vals, 1.645 * y_vals, color='#F8F8F8', alpha=0.8, label='p > 0.10')

        # Pseudo 95% confidence limits based on pooled estimate
        x_left = pooled_effect - 1.96 * y_vals
        x_right = pooled_effect + 1.96 * y_vals

        ax.plot(x_left, y_vals, 'k--', alpha=0.8, label='Pseudo 95% CI (Pooled)')
        ax.plot(x_right, y_vals, 'k--', alpha=0.8)
        ax.axvline(pooled_effect, color='red', linestyle='-', linewidth=1.5, alpha=0.9, label=f'Pooled Estimate ({pooled_effect:.2f})')
        ax.axvline(0, color='gray', linestyle=':', alpha=0.7)

        # Plot observed vs imputed studies
        is_imputed = df["is_imputed"].values if "is_imputed" in df.columns else [False] * len(df)
        obs_mask = [not x for x in is_imputed]
        imp_mask = [bool(x) for x in is_imputed]

        if any(obs_mask):
            ax.scatter(effects[obs_mask], se[obs_mask], color='#1f77b4', s=45, alpha=0.8, edgecolors='black', label='Observed Studies', zorder=4)
        if any(imp_mask):
            ax.scatter(effects[imp_mask], se[imp_mask], color='#ff7f0e', s=55, marker='D', alpha=0.9, edgecolors='black', label='Imputed Studies (Trim & Fill)', zorder=5)

        ax.set_ylim(max_se, 0)  # Invert y-axis
        ax.set_xlabel('Standardized Effect Size (d)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Standard Error (SE)', fontsize=11, fontweight='bold')
        ax.set_title('Contour-Enhanced Funnel Plot', fontsize=13, fontweight='bold', pad=15)
        ax.legend(loc='upper right', fontsize=9, framealpha=0.9)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300)
            png_path = save_path.replace('.pdf', '.png')
            plt.savefig(png_path, dpi=300)
            plt.close()
        return fig

    def plot_prisma_flowchart(self, metrics: dict, save_path: str = None):
        """Generates a PRISMA 2020 Flow Diagram using matplotlib."""
        fig, ax = plt.subplots(figsize=(8, 10))
        ax.axis('off')

        box_width = 0.6
        box_height = 0.12
        x_center = 0.5

        identified = metrics.get("identified", 0)
        screened = metrics.get("screened", 0)
        eligible = metrics.get("eligible", 0)
        included = metrics.get("included", 0)

        boxes = [
            (f"Identification\n(n = {identified})", 0.9),
            (f"Screening\n(n = {screened})", 0.65),
            (f"Eligibility\n(n = {eligible})", 0.4),
            (f"Included\n(n = {included})", 0.15)
        ]

        for text, y in boxes:
            rect = plt.Rectangle((x_center - box_width/2, y - box_height/2), box_width, box_height,
                                 fill=True, facecolor='#EAEAF2', edgecolor='black', zorder=2)
            ax.add_patch(rect)
            ax.text(x_center, y, text, ha='center', va='center', fontsize=12, zorder=3)

        arrow_props = dict(facecolor='black', edgecolor='black', width=2, headwidth=8)
        ax.annotate('', xy=(x_center, 0.65 + box_height/2), xytext=(x_center, 0.9 - box_height/2), arrowprops=arrow_props)
        ax.annotate('', xy=(x_center, 0.4 + box_height/2), xytext=(x_center, 0.65 - box_height/2), arrowprops=arrow_props)
        ax.annotate('', xy=(x_center, 0.15 + box_height/2), xytext=(x_center, 0.4 - box_height/2), arrowprops=arrow_props)

        if "exclusion_reasons" in metrics:
            exc = metrics["exclusion_reasons"]
            total_exc = sum(exc.values())
            if total_exc > 0:
                exc_text = f"Records excluded\n(n = {total_exc})"
                rect = plt.Rectangle((0.75, 0.65 - box_height/2), box_width/1.5, box_height,
                                     fill=True, facecolor='#F2EAEA', edgecolor='black', zorder=2)
                ax.add_patch(rect)
                ax.text(0.75 + box_width/3, 0.65, exc_text, ha='center', va='center', fontsize=10, zorder=3)
                ax.annotate('', xy=(0.75, 0.65), xytext=(x_center + box_width/2, 0.65), arrowprops=arrow_props)

        plt.title('PRISMA 2020 Flow Diagram', fontsize=16)

        if save_path:
            plt.savefig(save_path, dpi=300)
            png_path = save_path.replace('.pdf', '.png')
            plt.savefig(png_path, dpi=300)
            plt.close()
        return fig

    def plot_evidence_gap_map(
        self,
        df: pd.DataFrame,
        intervention_col: str = "intervention",
        outcome_col: str = "outcome",
        effect_dir_col: Optional[str] = "effect_direction",
        save_path: Optional[str] = None
    ):
        """
        Generates a 2D Evidence Gap Map (EGM) Bubble Grid Matrix.
        X-axis: Intervention Categories / Study Methods
        Y-axis: Measured Outcome Domains
        Bubble Size: Study Count (density of evidence)
        Bubble Color: Dominant Finding / Effect Direction
        """
        if df.empty or intervention_col not in df.columns or outcome_col not in df.columns:
            logger.warning("Dataframe lacks required columns for Evidence Gap Map.")
            return None

        clean_df = df.dropna(subset=[intervention_col, outcome_col]).copy()
        if clean_df.empty:
            return None

        # Aggregate counts and directions
        grouped = clean_df.groupby([intervention_col, outcome_col]).size().reset_index(name="count")
        
        # Color mapping if effect direction is present
        color_map = {}
        if effect_dir_col and effect_dir_col in clean_df.columns:
            dir_summary = clean_df.groupby([intervention_col, outcome_col])[effect_dir_col].agg(
                lambda s: s.value_counts().index[0] if not s.dropna().empty else "neutral"
            ).reset_index()
            merged = pd.merge(grouped, dir_summary, on=[intervention_col, outcome_col], how="left")
        else:
            merged = grouped
            merged["effect_direction"] = "neutral"

        interventions = sorted(clean_df[intervention_col].unique())
        outcomes = sorted(clean_df[outcome_col].unique())

        fig, ax = plt.subplots(figsize=(max(8, len(interventions) * 1.5), max(6, len(outcomes) * 1.2)))

        # Background grid
        ax.set_xticks(range(len(interventions)))
        ax.set_yticks(range(len(outcomes)))
        ax.set_xticklabels([str(i).replace('_', ' ').title() for i in interventions], rotation=30, ha="right", fontsize=11, fontweight="bold")
        ax.set_yticklabels([str(o).replace('_', ' ').title() for o in outcomes], fontsize=11, fontweight="bold")

        ax.grid(True, linestyle="--", alpha=0.5, color="gray")

        # Color palette for evidence directions
        palette = {
            "positive": "#2ca02c",  # green
            "negative": "#d62728",  # red
            "mixed": "#ff7f0e",     # orange
            "neutral": "#1f77b4"    # blue
        }

        x_map = {name: idx for idx, name in enumerate(interventions)}
        y_map = {name: idx for idx, name in enumerate(outcomes)}

        max_count = merged["count"].max() if not merged.empty else 1

        for _, row in merged.iterrows():
            x = x_map[row[intervention_col]]
            y = y_map[row[outcome_col]]
            cnt = row["count"]
            direction = str(row.get("effect_direction", "neutral")).lower()
            col = palette.get(direction, "#1f77b4")
            size = 150 + (cnt / max_count) * 1200

            ax.scatter(x, y, s=size, color=col, alpha=0.75, edgecolors="black", linewidth=1.5, zorder=3)
            ax.text(x, y, str(cnt), ha="center", va="center", color="white" if direction in ["positive", "negative"] else "black",
                    fontsize=10, fontweight="bold", zorder=4)

        # Set bounds
        ax.set_xlim(-0.6, len(interventions) - 0.4)
        ax.set_ylim(-0.6, len(outcomes) - 0.4)

        # Legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='Positive Finding', markerfacecolor='#2ca02c', markersize=10, markeredgecolor='k'),
            Line2D([0], [0], marker='o', color='w', label='Negative Finding', markerfacecolor='#d62728', markersize=10, markeredgecolor='k'),
            Line2D([0], [0], marker='o', color='w', label='Mixed / Neutral', markerfacecolor='#1f77b4', markersize=10, markeredgecolor='k'),
        ]
        ax.legend(handles=legend_elements, loc="upper right", bbox_to_anchor=(1.25, 1.0), title="Finding Direction")

        ax.set_title("Evidence Gap Map (EGM): Interventions vs. Outcome Domains", fontsize=14, fontweight="bold", pad=20)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300)
            png_path = save_path.replace('.pdf', '.png')
            plt.savefig(png_path, dpi=300)
            plt.close()
        return fig

    def plot_burst_table_timeline(
        self,
        burst_df: pd.DataFrame,
        top_n: int = 15,
        save_path: Optional[str] = None
    ):
        """
        Renders a CiteSpace-style Citation / Keyword Burst Timeline.
        Displays top burst terms sorted by burst strength, with blue baseline timelines
        and thick red spans indicating active surge intervals.
        """
        if burst_df.empty:
            return None

        plot_df = burst_df.sort_values(by=["Weight", "Start_Year"], ascending=[False, False]).head(top_n).copy()
        plot_df = plot_df.sort_values(by="Start_Year", ascending=True).reset_index(drop=True)

        min_year = int(plot_df["Start_Year"].min()) - 1
        max_year = int(plot_df["End_Year"].max()) + 1

        fig, ax = plt.subplots(figsize=(10, max(4, len(plot_df) * 0.45 + 1.5)))

        y_positions = list(range(len(plot_df)))

        for idx, row in plot_df.iterrows():
            term = row["Term"]
            weight = row["Weight"]
            start_yr = int(row["Start_Year"])
            end_yr = int(row["End_Year"])

            # Baseline line (entire study span)
            ax.plot([min_year, max_year], [idx, idx], color="#b0bec5", linewidth=2.5, zorder=1)

            # Burst interval in thick red
            ax.plot([start_yr, end_yr], [idx, idx], color="#d32f2f", linewidth=6.5, solid_capstyle='round', zorder=2)

        ax.set_yticks(y_positions)
        labels = [f"{row['Term']} (w={row['Weight']:.1f})" for _, row in plot_df.iterrows()]
        ax.set_yticklabels(labels, fontsize=10, fontweight="bold")
        ax.set_xlim(min_year - 0.5, max_year + 0.5)
        ax.set_xticks(range(min_year, max_year + 1, max(1, (max_year - min_year) // 8)))
        ax.set_xlabel("Year", fontsize=11, fontweight="bold")
        ax.set_title("Top Keyword / Citation Surges (Kleinberg's Burst Detection)", fontsize=13, fontweight="bold", pad=15)
        ax.grid(axis='x', linestyle='--', alpha=0.5)
        ax.invert_yaxis()  # Top to bottom

        from matplotlib.lines import Line2D
        custom_legend = [
            Line2D([0], [0], color='#d32f2f', lw=5, label='Active Surge (Burst State)'),
            Line2D([0], [0], color='#b0bec5', lw=2, label='Baseline Period')
        ]
        ax.legend(handles=custom_legend, loc="lower right", framealpha=0.9)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300)
            png_path = save_path.replace('.pdf', '.png')
            plt.savefig(png_path, dpi=300)
            plt.close()
        return fig

    def plot_thematic_evolution_sankey(
        self,
        df: pd.DataFrame,
        epoch_col: str = "Epoch",
        theme_col: str = "Theme",
        save_path: Optional[str] = None
    ):
        """
        Renders a Multi-Epoch Thematic Evolution Flowchart (Bibliometrix / Alluvial style).
        Visualizes how research themes across temporal epochs migrate, split, and merge.
        """
        if df.empty or epoch_col not in df.columns or theme_col not in df.columns:
            return None

        clean = df.dropna(subset=[epoch_col, theme_col]).copy()
        epochs = sorted(clean[epoch_col].unique())
        if len(epochs) < 2:
            return None

        fig, ax = plt.subplots(figsize=(11, 7))

        # Node positions per epoch
        epoch_themes = {}
        for ep in epochs:
            counts = clean[clean[epoch_col] == ep][theme_col].value_counts()
            epoch_themes[ep] = counts

        x_coords = {ep: idx * 3.0 for idx, ep in enumerate(epochs)}
        palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

        # Render theme nodes per epoch
        node_pos = {}
        for ep_idx, ep in enumerate(epochs):
            x = x_coords[ep]
            counts = epoch_themes[ep]
            total = counts.sum()
            y_curr = 0.0

            for t_idx, (theme, cnt) in enumerate(counts.items()):
                height = (cnt / total) * 5.0
                color = palette[t_idx % len(palette)]
                rect = plt.Rectangle((x - 0.25, y_curr), 0.5, height, facecolor=color, edgecolor='black', alpha=0.85, zorder=3)
                ax.add_patch(rect)
                ax.text(x, y_curr + height / 2.0, f"{str(theme)[:18]}\n({cnt})", ha='center', va='center', fontsize=9, fontweight='bold', color='white', zorder=4)
                node_pos[(ep, theme)] = (x, y_curr, height, color)
                y_curr += height + 0.35

        # Render alluvial transition ribbons between consecutive epochs
        for ep_i in range(len(epochs) - 1):
            ep_from = epochs[ep_i]
            ep_to = epochs[ep_i + 1]
            
            # Simple overlap simulation / transition curves
            for (t_from, (x1, y1, h1, col1)) in [(t, node_pos[(ep_from, t)]) for t in epoch_themes[ep_from].index]:
                for (t_to, (x2, y2, h2, _)) in [(t, node_pos[(ep_to, t)]) for t in epoch_themes[ep_to].index]:
                    # Curve between nodes
                    x_span = np.linspace(x1 + 0.25, x2 - 0.25, 50)
                    y_top = y1 + h1 + (y2 + h2 - (y1 + h1)) * (0.5 - 0.5 * np.cos(np.pi * (x_span - (x1 + 0.25)) / (x2 - x1 - 0.5)))
                    y_bot = y1 + (y2 - y1) * (0.5 - 0.5 * np.cos(np.pi * (x_span - (x1 + 0.25)) / (x2 - x1 - 0.5)))
                    ax.fill_between(x_span, y_bot, y_top, color=col1, alpha=0.15, zorder=2)

        ax.set_xticks([x_coords[ep] for ep in epochs])
        ax.set_xticklabels([f"Epoch: {ep}" for ep in epochs], fontsize=11, fontweight='bold')
        ax.set_yticks([])
        ax.axis('off')
        ax.set_title("Thematic Evolution Flow Across Epochs (Bibliometrix Sankey Mapping)", fontsize=13, fontweight='bold', pad=15)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300)
            png_path = save_path.replace('.pdf', '.png')
            plt.savefig(png_path, dpi=300)
            plt.close()
        return fig


