"""Rerun country / co-authorship / co-citation stages on the paper-3 clean corpus.

Mirrors src/orchestrators/analysis_orchestrator.py stages 3.2 (country),
3.5 (network) and 3.6 (co-citation), writing into outputs/paper3_clean/.
"""
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import pandas as pd
import polars as pl

from src.core.countries import CountryAnalysis
from src.core.network import NetworkAnalysis
from src.core.citations import CitationsAnalysis
from src.core.viz import Visualization

OUT = os.path.join(repo_root, "outputs", "paper3_clean")
FIG = os.path.join(OUT, "figures")
CORPUS = os.path.join(repo_root, "data", "paper3_clean_corpus.csv")


def main() -> int:
    os.makedirs(FIG, exist_ok=True)
    df_pd = pd.read_csv(CORPUS)
    df = pl.from_pandas(df_pd)
    df = df.filter(pl.col("Year").is_not_null())
    df = df.with_columns(pl.col("Year").cast(pl.Int64))
    viz = Visualization()

    # Country.
    try:
        exploded_pub, country_ev = CountryAnalysis().process_countries(df)
        if not country_ev.empty:
            country_ev.to_csv(os.path.join(OUT, "country_evolution.csv"), index=False)
            viz.plot_country_choropleth_map(
                country_ev, save_path=os.path.join(OUT, "country_world_map.pdf"))
            top = country_ev.groupby("Country")["Count"].sum().sort_values(ascending=False).head(5)
            print("[country] top5:", [(c, int(v)) for c, v in top.items()], flush=True)
    except Exception as e:
        print(f"[!] country failed: {e}", flush=True)

    # Co-authorship network.
    try:
        edges_df, node_meta = NetworkAnalysis().build_co_authorship_graph(df)
        if hasattr(edges_df, "to_pandas"):
            edges_df = edges_df.to_pandas()
        if hasattr(node_meta, "to_pandas"):
            node_meta = node_meta.to_pandas()
        edges_df.to_csv(os.path.join(OUT, "network_edges.csv"), index=False)
        node_meta.to_csv(os.path.join(OUT, "network_nodes.csv"), index=False)
        print(f"[network] nodes={len(node_meta):,} edges={len(edges_df):,}", flush=True)
        if not edges_df.empty and not node_meta.empty:
            viz.plot_network(edges_df, node_meta,
                             save_path=os.path.join(OUT, "network_graph.pdf"),
                             top_per_community=1)
            print("[network] plotted network_graph.pdf", flush=True)
    except Exception as e:
        print(f"[!] network failed: {e}", flush=True)

    # Co-citation.
    try:
        ca = CitationsAnalysis()
        ref_df = ca.extract_references_df(df_pd)
        print(f"[cocit] ref links={len(ref_df):,}", flush=True)
        cocit_df, X = ca.calculate_co_citation(ref_df)
        if not cocit_df.empty:
            cocit_df.to_csv(os.path.join(OUT, "network_cocitations.csv"), index=False)
            title_map = {}
            for _, r in df_pd.iterrows():
                eid = str(r.get("EID", "") or "").strip()
                doi = str(r.get("DOI", "") or "").strip()
                t = str(r.get("Title", "") or "").strip()
                url = f"https://doi.org/{doi}" if doi else (f"https://openalex.org/{eid}" if eid else "")
                if eid:
                    title_map[eid] = {"title": t, "url": url}
                if doi:
                    title_map[doi] = {"title": t, "url": url}
            viz.plot_cocitation_network(cocit_df, title_map=title_map,
                                        save_path=os.path.join(OUT, "cocitation_graph.pdf"))
            top = cocit_df.iloc[0]
            print(f"[cocit] pairs={len(cocit_df):,} top='{str(top['cited_1'])[:40]}' & '{str(top['cited_2'])[:40]}' ({int(top['co_citation_count'])})",
                  flush=True)
    except Exception as e:
        print(f"[!] cocitation failed: {e}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
