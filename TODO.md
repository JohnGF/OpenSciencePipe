# Bibliometric Research Pipeline: Development TODO List

This list tracks planned enhancements and advanced features to elevate the bibliometric research pipeline to a publication-grade framework.

---

## 🟥 Priority 1: Scraper Stability, Metadata Completeness & New Sources

- [x] **Add New Scrapers/Collectors**:
  - **PubMed (NCBI Entrez E-utilities)**: Essential for medical and life sciences research (public API, no keys required).
  - **Elsevier (Scopus Search API)**: High-quality citation data and keywords. Requires Elsevier API Key (`X-ELS-APIKey`).
  - **Web of Science (WoS API)**: High-impact indexing. Requires Clarivate WoS API Key.
- [ ] **API Rate Limiting & Retries**:
  - Implement exponential backoff retries (e.g. using `tenacity` or a custom retry decorator) in `src/core/collectors/` to handle `429 Too Many Requests` limits gracefully.
  - Add request rate throttling/delays.
- [ ] **Cross-Source DOI Enrichment**:
  - Update `UnifiedCollector` to run a secondary "enrichment pass." If a paper is fetched from one API but is missing an `Abstract` or `Author Keywords`, query OpenAlex or Semantic Scholar directly *by DOI* to pull and merge the missing metadata.

---

## 🟨 Priority 2: Advanced NLP & Temporal Evolution

- [ ] **Dynamic Topic Modeling (DTM)**:
  - Leverage BERTopic's native Topics-over-Time feature to analyze how identified research topics grow, decline, or evolve conceptually across the years, using the non-null `Year` field of the papers.
- [ ] **Topic-Keyword Correlation**:
  - Map and visualize which author keywords correspond most strongly to which BERTopic clusters.

---

## 🟨 Priority 3: Network Topologies & Centralities

- [ ] **Bridge & Hub Identification**:
  - Add calculations for **Betweenness Centrality** (to find bridge researchers between clusters) and **Degree Centrality** (most prolific co-authors) in `src/core/network.py`.
- [ ] **Community Impact Metrics**:
  - Calculate the average citation count or aggregate H-index of Louvain partition communities to highlight the most influential sub-fields in the network.
- [ ] **Directed Citation Networks**:
  - Create a directed network tracking citation flows (which papers cite which other papers in the collection) to map the conceptual lineage of ideas.

---

## 🟩 Priority 4: Geopolitical & Collaboration Analysis

- [ ] **Co-Country Collaboration Network**:
  - Use parsed author affiliation countries to build a country-to-country undirected network where edges represent co-authorship. This visualizes international collaboration clusters and research partnerships.

---

## Priority 5: Repository Tree Reorganization & Path Decoupling

- [ ] **Categorize `scripts/` with Symlink Preservation**:
  - Partition 45+ flat scripts into functional subdirectories:
    - `scripts/env/`: Environment runners and setup (`start_local_ai_pod.sh`, `start_dev_container.sh`, `setup_keys.py`, `serve_results.py`).
    - `scripts/institutional/`: Institutional report generators (`generate_fcul_general_analysis.py`, `compile_fcul_general_report.py`, `generate_fcul_china_analysis.py`, `compile_fcul_china_report.py`, `institution_country_collab.py`).
    - `scripts/benchmarks/`: Systematic benchmark replication suite (`run_all_benchmarks.py`, `auto_validate_benchmarks.py`, `run_screening_benchmarks.py`, `run_head_to_head_baselines.py`, `evaluate_clustering_benchmarks.py`).
    - `scripts/domain_studies/`: BCI/Neurorehab manuscript scripts (`filter_bci_neurorehab.py`, `paradigm_shares.py`, `build_clean_corpus.py`, `generate_percolation_plot.py`).
  - Maintain backwards-compatible relative symlinks in `scripts/` so in-text manuscript citations (`main.tex#L97`), `Makefile` commands, and `README.md` examples never break.
- [ ] **Decouple Root `tables/` Output Target**:
  - Update `scripts/auto_validate_benchmarks.py`, `scripts/run_head_to_head_baselines.py`, and `src/core/meta_validator.py` to write into dedicated output directories while retaining fallback links.
- [ ] **Dataset & Output Namespace Partitioning**:
  - Group benchmark replication inputs in `data/` and execution runs in `outputs/` into namespaced subfolders (`data/benchmarks/`, `outputs/benchmarks/`, `outputs/institutional/`) while updating or symlinking paths in `scripts/run_head_to_head_baselines.py` and manuscript audit trails.
- [ ] **Release Artifact Quarantine**:
  - Consolidate loose release packages (`zenodo_bundle/` and `zenodo_upload_Z_PENDING/`) into a unified `releases/` folder.
