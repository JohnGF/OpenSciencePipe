# OpenSciencePipe: Manuscript & Framework Action Plan
Tracking resolutions for Carlos Duarte's Round 2 Review (October 14, 2026).
Review reference: `manuscripts/paper4_opensciencepipe_landmark/reviewer_round2.md`

---

## 1. Manual Review & Decisions (For You / John Only)

These items require your scientific judgment, authorial decisions, or external ground-truth knowledge.

- [x] **Decided on Option A (Science mapping focus for Paper 4):**
  - *Context:* Carlos Duarte recommended focusing Paper 4 strictly on science mapping / informetrics for *Quantitative Science Studies* (QSS) or *Scientometrics*, moving PRISMA screening and meta-analysis extraction into a separate dedicated manuscript.
  - *Resolution:* Adopted Option A. Paper 4 is streamlined to bibliometric science mapping (ingestion, deduplication, GPU network analysis, neural topic modeling vs LDA, geopolitical concordance, and automated report compilation). Evidence synthesis is framed as modular companion capabilities with dedicated validation in companion Paper 2 (`manuscripts/paper2_meta_analysis_benchmark`).

### 1.2 Ground Truth Sources to Verify or Remove
- [x] **ChatGPT benchmark corrected to Barrington et al. (2023):**
  - *Context:* The previous citation accidentally pointed to Kung et al. (2023) USMLE exam performance.
  - *Resolution:* Replaced with the actual bibliometric benchmark: Barrington et al. (2023), *"A Bibliometric Analysis of the Rise of ChatGPT in Medical Research"*, *Medical Sciences*, DOI: `10.3390/medsci11030061`. Updated `data/benchmarks/benchmark_chatgpt_medicine.json` and all LaTeX tables.
- [x] **Top-8 Institutional Rankings (Section 5.2):**
  - *Context:* Section 5.2 listed specific top universities (e.g. UC, Toronto, Sapienza for EEG) as ground truth, but these did not link to verified tables in published papers (Reviewer 2, Comment F3/Round 2).
  - *Resolution:* Removed unreferenced institutional rank concordance and removed the sparse `Inst. Overlap` column from Table 4. Refocused macro-structural validation on robust geopolitical (country-level) concordance ($\rho = 0.99$ on Electrophysiology, $\rho = 0.96$ on ChatGPT), and added methodological rationale explaining that institutional concordance across open (OpenAlex/ROR) and proprietary (WoS/Scopus) databases is dominated by parent-child entity aggregation divergence rather than algorithmic differences.
- [x] **Audit of Topic -1 Outlier Pool (Section 5.1):**
  - *Context:* Section 5.1 asserted "automated scholarly API harvesting inevitably retrieves 20-40% peripheral records" to justify a 32.1% HDBSCAN outlier rate (Reviewer 2, Comment F4).
  - *Resolution:* Executed forensic qualitative audit on a random sample ($n = 30$, seed 42) from the Topic -1 unclustered pool of the 57,601-paper Electrophysiology corpus. Found: 20.0% (6/30) genuine API/keyword retrieval noise (cybersecurity, drone vision, plant disease), 16.7% (5/30) interdisciplinary/boundary applications (VR traffic safety, wearables), and 63.3% (19/30) authentic in-domain publications falling below the HDBSCAN density threshold ($m_{\text{cl}} = 10$). Replaced unsupported circular assertion in `main.tex` Section 5.1 with empirical audit numbers and explicitly documented the Blockchain small-corpus failure mode (100% outliers, 0 themes).

### 1.3 Governance & Authorship
- [x] **CRediT Roles for Carlos Duarte:**
  - *Context:* The current draft listed Carlos only for "Review & editing" (Reviewer 2, line 215).
  - *Resolution:* Updated author contribution statement in `manuscripts/paper4_opensciencepipe_landmark/main.tex` to: "Carlos Duarte: Conceptualization, Methodology, Supervision, Investigation, Writing -- review & editing."
- [ ] **API Key Revocation / Rotation:**
  - *Context:* The `.env` file that was previously tracked on GitHub contained template strings, but if any real API keys were ever committed to remote history, revoke and regenerate them at provider dashboards (OpenAlex, Elsevier, Clarivate, NCBI).

---

## 2. Automated AI Fixes (AI-Managed)

These items are executed automatically in Python code, scripts, and LaTeX files.

### 2.1 Statistical & Algorithmic Corrections
- [x] **Fix NPMI Coherence calculation (`scripts/evaluate_clustering_benchmarks.py`):**
  - Removed naive whitespace splitting; implemented regex word boundary tokenization.
  - Eliminated hardcoded `-1.0` penalty; applied standard Laplace/epsilon smoothing matching Eq. 14.
  - Updated Section 5.1 explanation in `main.tex`.
- [x] **Correct BCG vaccine meta-analysis statistics (`manuscripts/paper4_opensciencepipe_landmark/main.tex`):**
  - Removed claim that Colditz et al. (1994) published I^2 (I^2 formulated in 2002).
  - Recomputed exact DerSimonian-Laird on standard 13-trial Colditz dataset (`metafor::dat.bcg`: ln RR = -0.714, Q = 152.2, I^2 = 92.1%).
  - Updated Table 6 and Section 5.5 narrative with verified figures and transparent error reporting.
- [x] **Implement Levenshtein fuzzy deduplication (`src/core/collection.py`):**
  - Implemented token-sorted Levenshtein edit distance with ratio >= 0.92 in `UnifiedCollector` matching Equation 2.
- [x] **Implement Rank-Biased Overlap (RBO) (`src/core/countries.py` & `scripts/validate_against_benchmark.py`):**
  - Implemented Webber et al. RBO and Jaccard@K metrics alongside Spearman rank correlation to evaluate disjoint top-K lists properly.

### 2.2 Empirical Baselines & Execution
- [x] **Execute and report head-to-head baselines (`scripts/run_head_to_head_baselines.py`):**
  - Ran BERTopic vs LDA baseline comparisons: LDA yields Topic Diversity = 0.58 (high lexical redundancy) and 0.0% outliers (forced assignment), whereas BERTopic achieves TD = 0.80 with explicit Topic -1 noise isolation (32.1%).
  - Added NetworkX Louvain baseline in `run_head_to_head_baselines.py` computing modularity Q (0.9731) and runtime.

### 2.3 Visualizations & Figures
- [x] **Refactor Figure 2a & 2b (`src/core/viz.py` & `main.tex`):**
  - Restricted circular network labeling to top prominent authors per community instead of printing all 100 author names around the perimeter.
  - Updated Figure 2 caption in `main.tex` to explicitly specify national research publication volume with log10 units.
- [x] **Decoupled Figure 3 from Paper 4 under Option A:**
  - *Context:* Figure 3a contained PRISMA flow arithmetic discrepancies.
  - *Resolution:* Under Option A, Figure 3 (PRISMA flow, Forest plot, Funnel plot) and evidence synthesis evaluation tables are decoupled from Paper 4 into companion Paper 2 (`manuscripts/paper2_meta_analysis_benchmark`), removing review surface and arithmetic discrepancies from Paper 4.

### 2.4 Text & Manuscript Polish (`manuscripts/paper4_opensciencepipe_landmark/main.tex`)
- [x] **Tone down overclaims:**
  - Section 2.6: Rephrased from "six mechanisms that do not exist in prior systems" to "six cohesive methodological capabilities integrated into a single reproducible engine".
  - Section 6.4: Framed cross-database agreement as empirical consistency across open metadata and proprietary indexes rather than "capturing true underlying structure".
  - Replaced "autonomous manuscript generation" with "automated reproducible report scaffolding".
- [x] **Update citations and terminology:**
  - Replaced BERT arXiv preprint with Devlin et al. (NAACL-HLT 2019).
  - Added citations for Higgins & Thompson (2002) (I^2), Begg & Mazumdar (1994) (Begg's test), revtools (Westgate 2019), and metagear (Lajeunesse 2016).
  - Updated Acknowledgements wording ("kindly granting ... free of charge", "developer APIs").
  - Fixed repository URL to `https://github.com/JohnGF/OpenSciencePipe`.
  - Added formal Generative AI disclosure statement.

---

## 3. Completed & Verified

- [x] **Carlos Duarte Round 2 review archived:** Saved to `manuscripts/paper4_opensciencepipe_landmark/reviewer_round2.md`.
- [x] **`.env` removed from GitHub tracking:** Purged from `origin/main` tree.
- [x] **Configuration template created:** Added `/.env.example` and `settings/.env.example`.
- [x] **Framework features merged to `main`:** Fast-forwarded and merged PRISMA, meta-analysis orchestrator, and test suites into `origin/main`.
- [x] **MIT License on `main`:** Verified presence in repository root.
- [x] **Clean compilation of `main.pdf`:** Compiled cleanly (28 pages, 0 errors).
