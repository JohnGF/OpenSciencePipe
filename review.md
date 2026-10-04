# Peer Review Report

**Manuscript Title:** OpenSciencePipe: An End-to-End Framework for Autonomous Science Mapping and Systematic Evidence Synthesis  
**Authors:** Joao Garcia Farinha, Carlos Duarte  
**Target Venue:** *Journal of Informetrics* / *Quantitative Science Studies* / *Scientometrics*  
**Review Date:** October 2026  

---

## 1. Recommendation and Evaluation Summary

### Explicit Recommendation Decision
**Major Revision**

The manuscript introduces an ambitious and technically substantial computational framework that unifies macroscopic science mapping with microscopic PRISMA systematic evidence synthesis. The technical execution—leveraging NVIDIA RAPIDS GPU acceleration for sub-second community detection, density-based neural clustering with explicit noise rejection, local zero-shot language model screening, and DerSimonian-Laird meta-analytic pooling—represents an innovative contribution to informetric infrastructure.

However, the manuscript suffers from significant empirical inconsistencies between text and tables (e.g., claiming 13/13 screened clinical trials in Section 5.2 while Table 4 reports a target of N=5), pervasive textual repetition across six separate sections, unverified statistical assertions (reporting Cohen's kappa >= 0.82 and WSS@95 = 0.898 without presenting them in any validation table), and several grammatical and typographical regressions in the most recent uncommitted revisions. A rigorous major revision is required to align all empirical claims, eliminate marketing-style hyperbole, consolidate redundant passages, and correct accounting errors across the benchmark suite.

### Formal Evaluation Scores (Scale: 1 to 10)
- **Technical Rigor:** 7.5 / 10  
  Sound algorithmic choices (RAPIDS cugraph, BERTopic with HDBSCAN, DerSimonian-Laird pooling). However, effect size notation is conflated under Cohen's d for non-standardized metrics, Cochran's Q is cited without table documentation, and Spearman rank correlations on n=3 and n=4 lack inferential power.
- **Empirical Validity:** 7.0 / 10  
  Extensive multi-field evaluation across 26 studies and 4 meta-analyses. However, empirical claims are weakened by sample discrepancies (N=5 vs. 13 in clinical screening), selective omission of negative correlations (e.g., rho = -0.40 in institutional and geopolitical ranks), two completely empty N/A rows in Table 4, and missing benchmark entries in Table 3.
- **Clarity and Economy of Text:** 6.5 / 10  
  Heavy repetition of benchmark metrics across Abstract, Highlights, Introduction, Table 1, Section 2.6, Section 4, Section 5.2, and Conclusion. Recent working-tree edits introduced grammatical regressions and informal phrasing.
- **Originality:** 9.0 / 10  
  First framework to bridge the methodological divide between exploratory science mapping and confirmatory meta-analysis within a unified, reproducible, headless pipeline.
- **Overall Score:** 7.5 / 10  

---

## 2. Assessment of Recent Edits (Git Diff Against HEAD and Working Tree)

The author has undertaken several structural and stylistic revisions. A critical evaluation of these changes reveals a mixture of genuine improvements and new errors:

### A. Removal of Buzzwords and 'Heuristic'
- **Status:** Partially successful, incomplete.
- **Evaluation:** In Section 1 (line 75), replacing "relies on heuristic bag-of-words assumptions" with "relies on bag-of-words assumptions" improves academic sobriety. Bag-of-words is a formal representation model, not merely a heuristic.
- **Remaining Issues:** The word "heuristic" was left intact in line 226 (Figure 1 Tier 3: "Three-tier heuristic") and line 307 ("beyond bag-of-words heuristics"). The author should replace "heuristics" in line 307 with "frequency-based representations" or "lexical models".

### B. Removal of '10-page IEEEtran'
- **Status:** Inconsistently applied, with grammatical degradation.
- **Evaluation:** Removing "complete 10-page IEEEtran manuscript" in Section 3.5 (line 348) to say "complete manuscript (\nolinkurl{paper_scaffold.pdf})" appropriately decouples the framework from a specific publisher template.
- **Critical Flaw:** The working-tree edit in Section 1 (line 83) introduced a broken sentence:
  `and compiles on users favorite publication-grade \LaTeX{} manuscripts templates.`
  This sentence contains a missing apostrophe ("users favorite"), redundant nouns ("manuscripts templates"), and ungrammatical prepositions. It must be rewritten as: `and compiles publication-ready \LaTeX{} manuscripts across standard journal templates.`
- Furthermore, the term "IEEEtran" remains embedded in Table 1 (line 141) and Section 2.6 (line 156), creating internal inconsistency.

### C. Smoothing Paragraph Transitions in Section 1
- **Status:** Structurally positive, but marred by grammatical regressions.
- **Evaluation:** Replacing disjoint sub-headings (`\paragraph{Ingestion...}`, `\paragraph{Heuristic...}`) with flowing narrative transitions (`First, data ingestion...`, `Second, classical thematic modeling...`, `Third, graph topologies...`, `Finally, in systematic evidence synthesis...`) substantially enhances the prose rhythm of the Introduction.
- **Critical Flaws in Working Tree:** The uncommitted modifications introduced egregious errors that undermine the paper's professional standard:
  1. Line 48: `Beyond seeking to superseding the limiations of individual legacy tools, OpenSciencePipe introduces six distinct methodological and architectural innovations that to our knowledge don't exist in prior systems:`
     - "seeking to superseding" is a double participle error.
     - "limiations" is a typographical error.
     - "don't" is an informal contraction unsuitable for formal scholarly prose.
  2. Line 473: `over 28 minutes (pre warmed RAM)`
     - "pre warmed RAM" is technically awkward. Memory caches are warmed; RAM is allocated. It should read: `over 28 minutes under warm-cache conditions`.
  3. Line 492: `separate software ecosystems exploratory tools`
     - Dropped punctuation (a colon or dash was omitted during editing).
  4. Line 494: `\subsection{Direct Drop-in Replacement?}`
     - Section headings in scientific journals should be declarative rather than rhetorical questions. Rename to: `\subsection{Drop-in Replacement Audit and Mathematical Parity}`.
  5. Line 516: `To our knowledge no legacy tool spans...`
     - Missing comma after the introductory dependent clause.

### D. Benchmark Taxonomy Breakdown (26 Studies / 4 Meta-Analyses / 11 Software Families)
- **Status:** Conceptual clarification achieved, but internal accounting errors introduced.
- **Evaluation:** Disambiguating the empirical suite into 26 published bibliometric/synthesis studies and 4 canonical meta-analyses (yielding 30 evaluation benchmarks across 11 software families) resolves the previous ambiguity between 23, 26, and 30 benchmarks.
- **Audit Findings and Critical Contradictions:**
  1. **Table 1 (`tab_benchmark_tool_distribution.tex`) Accounting Errors:**
     - Row 20 lists `PRISMA Manual Consensus & 2 & Nosocomial Infection Global Prevalence, BCI Neurorehabilitation`.
     - Row 21 lists `RevMan / Stata / metafor & 5 & BCI Stroke, Rosiglitazone Risk, BCG Vaccine, Psychotherapy, Minimum Wage`.
     - BCI Stroke and BCI Neurorehabilitation refer to the exact same benchmark study (Ren et al., 2024, DOI 10.3389/fnhum.2024.1438095). Listing it under both categories results in double-counting.
     - Furthermore, where are `benchmark_parkinsons_eeg.json` (PRISMA Meta) and `benchmark_rent_control_econometrics.json` (Stata / metafor)? Both exist in `data/benchmarks/` and are listed in Table 2, but they are omitted from the category examples in Table 1.
  2. **Table 2 vs. Table 3 Coverage Discrepancy:**
     - Table 2 contains 26 studies (the 23 original studies plus 3 newly added studies: CitNetExplorer, Gephi, Bibexcel).
     - Table 3 (`tab_validation_thematic_clustering.tex`) still only contains 23 studies. The 3 newly added studies were never evaluated or added to Table 3.
  3. **Table 4 Placeholder Rows:**
     - Table 4 contains two completely empty rows with `N/A` across every single evaluation metric (Quantitative EEG Parkinson's and Rent Control). Empty placeholder rows must be removed from empirical validation tables.

---

## 3. Redundancy, Repetition, and Textual Economy

The manuscript suffers from severe structural repetition. The same core quantitative claims are recited nearly verbatim across six different sections:
- 0.84 seconds execution on >50,000 publications (>1,000x CPU speedup)
- Topic Diversity TD = 0.79 vs. 0.58 in classical models
- 100.0% sensitivity on clinical trials and 96.5% precision on machine reviews
- Effect size replication |Delta d| <= 0.0308 and exact heterogeneity I^2 = 87.5%
- Geopolitical rank preservation rho = 0.9912 (p < 0.001)

These exact numbers appear in:
1. Abstract (line 50)
2. Highlights (lines 53-58)
3. Introduction (lines 85-92)
4. Table 1 (Taxonomy, column 5, lines 134-141)
5. Section 2.6 (Novelties, lines 151-156)
6. Section 4 (Results, lines 461, 468, 473, 480, 487)
7. Section 5.2 (Drop-in Replacement Audit, lines 498, 507, 510, 513)
8. Conclusion (line 536)

This recitation dilutes readability and creates an echo chamber. The following specific prunings and consolidations must be executed:

### Section 2.6 (Methodological Novelties)
- **Problem:** Section 2.6 front-loads empirical benchmark results (0.84s, TD=0.79, kappa >= 0.82, |Delta d| <= 0.0308) before the architecture has even been introduced in Section 3.
- **Remedy:** Strip all numerical benchmark results from Section 2.6. Rewrite Section 2.6 to focus strictly on architectural mechanisms (e.g., Compressed Sparse Row GPU memory management, two-tier prompt inversion consensus, unified corpus branching). Let the empirical results speak for themselves in Section 4.

### Table 1 (Comparative Taxonomy)
- **Problem:** Column 5 ("Evaluated Metric & Performance") contains empirical benchmark numbers (e.g., "0.84 s on >50,000 nodes; Top-K nation overlap 93.3%").
- **Remedy:** Rename Column 5 to "Evaluated Metric & Scope". State the formal metrics evaluated (e.g., "Modularity Q, PageRank execution latency; Top-K Spearman rank correlation") without embedding preliminary results in a literature review taxonomy table.

### Section 5.2 (Drop-in Replacement Audit)
- **Problem:** Paragraphs under VOSviewer, Classical LDA, Rayyan/ASReview, and Cochrane RevMan re-hash the exact statistics already presented in Section 4.
- **Remedy:** Do not re-state the statistical output numbers. Shift the prose entirely toward qualitative and workflow trade-offs: data provenance automation, absence of desktop GUI freezing, memory footprint on consumer workstations, and the operational trade-off between manual interactive thresholding vs. automated pipeline defaults.

### Consolidation Between Section 1 and Section 2
- **Problem:** Section 1 lines 73-79 (Ingestion, Thematic modeling, Graph scalability, Screening labor) repeats the exact same operational critique presented in Section 2.2-2.4 (Exploratory mappers, Evidence synthesis, Deep learning).
- **Remedy:** Keep Section 1 focused on the high-level epistemological bifurcation (macro science mapping vs. micro evidence synthesis). Move the detailed software-by-software operational limitations into Section 2.2, eliminating the 1:1 conceptual mirroring.

---

## 4. Assessment of Proposed Addition: GUI Learning Curves vs. Single Query Prompt

The author proposes adding a contrast between the GUI learning curves of legacy tools (VOSviewer, CiteSpace, SciMAT) and OpenSciencePipe's single query prompt ("like a Google search") in the Introduction and Discussion.

### Informetric Assessment
- **Merit:** The underlying argument is valid and important. In informetrics and meta-research, reproducibility is heavily impaired by GUI-driven pipelines. CiteSpace requires configuring dozens of interdependent threshold controls, time-slicing intervals, and link pruning algorithms (Pathfinder vs. Minimum Spanning Tree). SciMAT requires manual period definitions and complex matrix imports. These manual GUI steps are rarely documented fully in published papers, hindering exact computational replication. Programmatic single-query execution provides deterministic reproducibility.
- **Fluff and Tone Warning:** Comparing OpenSciencePipe's execution to "like a Google search" is superficial, colloquial, and completely inappropriate for top-tier venues like *Journal of Informetrics* or *Quantitative Science Studies*. It trivializes the complex algorithmic pipeline (API pagination, deduplication, Louvain clustering, BERTopic, PRISMA screening) and sounds like commercial product marketing.

### Prescribed Academic Phrasing
- **For Section 1 (Introduction):**
  > "Whereas existing science mapping environments require manual parameter calibration across multi-stage graphical user interfaces (such as threshold selection, time-slice partitioning, and layout tuning in CiteSpace or SciMAT), OpenSciencePipe operates via a declarative, single-query specification. This design abstracts multi-tier data ingestion, topological discovery, and evidence synthesis into an automated, fully reproducible execution run."
- **For Section 5 (Discussion):**
  > "A defining operational distinction between OpenSciencePipe and legacy platforms lies in the transition from interactive graphical parameter exploration to declarative computational execution. In suites such as CiteSpace and SciMAT, analysts must navigate extensive menus to tune network pruning, temporal slicing, and threshold cut-offs—a process that affords visual intuition but introduces operational friction and impedes scriptable replication. By contrast, OpenSciencePipe's headless CLI and API interfaces prioritize end-to-end provenance: a single query string orchestrates ingestion, GPU network analysis, neural topic extraction, and manuscript compilation. While seasoned bibliometricians may still value interactive GUIs for ad-hoc visual experimentation, declarative pipelines provide the automation required for high-throughput, cross-corpus synthesis."

---

## 5. Mathematical, Statistical, and Empirical Rigor Audit

### A. The Screening Sample Size Contradiction (Target N=5 vs. 13)
- In Section 5.2 (line 510), the manuscript states:
  `On clinical trials (Ren et al., 2024), OpenSciencePipe achieved 100.0% sensitivity (recovering 13/13 eligible trials with zero false negatives) and saved 89.8% of manual screening labor (WSS@95 = 0.898)...`
- However, Table 4 (`tab_validation_screening_prisma.tex`) explicitly reports:
  `Target N = 5, Recall = 100.0%, Prec = 83.3%, Spec = 75.0%, F_1 = 90.9%, WMCC = 0.7746`
- Examination of `data/benchmarks/bci_stroke_ren2024_benchmark.json` reveals exactly 5 ground-truth included DOIs and 4 excluded DOIs (a total candidate pool of 9 papers).
- **Reviewer Critique:**
  1. Claiming "recovering 13/13 eligible trials" in Section 5.2 directly contradicts the empirical table and benchmark dataset.
  2. More critically, evaluating screening sensitivity on a total candidate pool of **nine papers** (5 targets, 4 negatives) is a toy validation, not a realistic systematic review screening scenario. Real systematic reviews triage 2,000 to 10,000 candidate records. To claim that the framework achieves "100.0% clinical screening sensitivity with zero false negatives" across the entire paper based on an evaluation of 5 target papers is an unacceptable empirical overreach. The authors must state the sample size (N=5) transparently in all claims and explicitly discuss the limitations of evaluating small candidate subsets.

### B. Selective Reporting in Macro-Structural Concordance
- In Section 4.2 (lines 468-470), the authors highlight:
  - Electrophysiology geopolitical overlap: 93.3% (rho = 0.9912, p < 0.001)
  - ChatGPT geopolitical overlap: 100.0% (rho = 0.9607, p < 0.001)
  - Electrophysiology institutional overlap: 100.0% (rho = 0.8571, p = 0.0065)
  - ChatGPT institutional overlap: 100.0% (rho = 0.6667, p = 0.071)
  - Environmental microplastics institutional recovery: 100.0%
  - BCI neurorehabilitation institutional recovery: 100.0%
- **Reviewer Critique:**
  Look at Table 3 for what the text conveniently omits:
  - BCI Neurorehabilitation institutional rank correlation is **negative**: `rho = -0.40 (n=5)`.
  - Mobile Commerce geopolitical rank correlation is **negative**: `rho = -0.40 (n=4)`.
  - Leading Universities geopolitical rank correlation is **inverted**: `rho = -1.00 (n=3)`.
  - Public Health Top-100 institutional overlap is **0.0%** (Table 3 line 28).
  Reporting 100.0% entity overlap while completely suppressing negative rank-order correlations (rho = -0.40) constitutes selective reporting. The authors must discuss why rank orders inverted (e.g., differences in fractional vs. full author counting between Scopus and OpenAlex).

### C. Statistical Fragility of Small-Sample Spearman Correlations
- Reporting Spearman rank correlations on samples of n=3 (Blockchain rho=1.00; Leading Universities rho=-1.00) and n=4 (Microplastics rho=0.80; Solar Power rho=0.80; Mobile Commerce rho=-0.40) is statistically meaningless.
- For n=4 with rho=0.80, the two-tailed t-test yields t = 1.886 (df=2), which corresponds to p = 0.200 (not statistically significant). For n=3, there are only 6 possible permutations.
- These small-sample metrics must not be presented alongside rigorous inferential statistics without an explicit disclaimer that they represent purely descriptive concordance.

### D. Outlier Noise Range and NPMI Value Discrepancies
- In Section 4.1 (line 463), the text asserts:
  `isolated an average of 31.8% of documents as unclustered boundary noise across active corpora (ranging from 9.5% in cohesive domains to 56.5% in highly heterogeneous domains such as Distance Learning).`
- Look at Table 3: Mobile Commerce has an outlier percentage of **0.0%**. Why does the text report the lower bound as 9.5% (which is Social Work)? If Mobile Commerce is an active corpus (K=2, TD=0.9500), the range is 0.0% to 56.5%.
- In Section 4.1 (line 463), the text states:
  `empirical C_NPMI values across benchmark corpora ranged from -0.037 to -0.837 (with an average of -0.32).`
- Calculating the arithmetic mean of the 17 NPMI values in Table 3 yields `-0.3064`. Standard mathematical rounding yields `-0.31`, not `-0.32`.

### E. Overgeneralization of Meta-Analytic Heterogeneity (I^2 = 87.5%)
- Throughout the manuscript (Abstract line 50, Highlights line 58, Intro line 91, Section 2.6 line 155, Section 5.2 line 513, Conclusion line 536), the text boasts:
  `replicates published effect sizes within |\Delta d| <= 0.0308 and exact heterogeneity (I^2 = 87.5%).`
- Look at Table 5 (`tab_validation_meta_analysis.tex`):
  - Doucouliagos & Stanley: Ground Truth I^2 = **N/A**
  - Nissen & Wolski: Ground Truth I^2 = **N/A**
  - Smith & Glass: Ground Truth I^2 = **N/A**
  - Colditz et al.: Ground Truth I^2 = 87.46%, Tool I^2 = 87.5%
- "Exact heterogeneity" was verified on **only one single benchmark** (Colditz et al.). Repeating "exact heterogeneity (I^2 = 87.5%)" as a broad performance generalization across all six sections is empirically unjustified. State clearly that heterogeneity replication was validated on Colditz et al. (87.5% vs. 87.46%), while the other three canonical studies lacked published ground-truth I^2 figures.

### F. Imprecision in Effect Size Notation (The Uniform Use of 'd')
- In Table 5 and Section 4.5, all effect sizes are denoted as "d".
- In Colditz et al., the metric is a log risk ratio ($\ln \text{RR} = -0.7606$).
- In Doucouliagos & Stanley, the metric is a partial correlation meta-regression coefficient.
- In Nissen & Wolski, the metric is an odds ratio / log odds ratio.
- In Smith & Glass, the metric is standardized mean difference (Cohen's d).
- Using "$d$" uniformly conflates distinct epidemiological and econometric metrics under Cohen's d. Table 5 should use the standard meta-analytic notation $\hat{\theta}$ or designate the metric column explicitly (e.g., Metric: $\ln \text{RR}$, $r$, Cohen's $d$, $\ln \text{OR}$).

### G. Asserted Metrics Missing from Tables
- **Cohen's kappa >= 0.82:** Asserted in Highlights, Table 1, Section 2.6, and Section 5.2. Missing from Table 4.
- **WSS@95 = 0.898:** Asserted in Section 5.2 and Table 1. Missing from Table 4.
- **Cochran's Q = 95.68:** Asserted in Section 4.5 line 487. Missing from Table 5.
- Every numerical metric cited in the narrative text must appear in the corresponding empirical table.

---

## 6. Specific Line-by-Line Revision Guide

### Front Matter & Abstract
- **Line 50:**  
  *What to trim:* "reproduces human reviewer consensus with 100.0% sensitivity on clinical trials"  
  *What to preserve:* Exact reported metrics.  
  *Recommendation:* Qualify the clinical trial sample: "achieves 100.0% sensitivity on a verified clinical trial benchmark (N=5) and 96.5% precision on machine-assisted reviews".
- **Lines 52-59 (Highlights):**  
  *What to trim:* Redundant recitation of metrics. Item 2 states "across 26 published studies and 11 legacy software ecosystems (30 evaluations)", which obscures the 4 meta-analyses.  
  *Recommendation:* Revise Item 2 to: "Comprehensive empirical benchmark across 26 bibliometric studies and 4 canonical meta-analyses."

### Section 1: Introduction
- **Line 75:**  
  *What to preserve:* The revised narrative flow without paragraph sub-headings.
- **Line 83:**  
  *What to trim:* `compiles on users favorite publication-grade \LaTeX{} manuscripts templates.`  
  *Recommendation:* Replace immediately with: `and compiles publication-ready \LaTeX{} manuscripts across standard journal templates.`
- **Lines 85-92:**  
  *What to trim:* The numbered list of 5 quantitative dimensions. This list repeats the exact structure of Section 3.6 / Section 4.  
  *Recommendation:* Condense into a single concise paragraph.

### Section 2: Related Work
- **Lines 103-111:**  
  *What to trim:* Repetitive critiques of desktop GUIs across every single tool paragraph.  
  *What to preserve:* Citations and historical taxonomy.
- **Lines 124-145 (Table 1):**  
  *What to trim:* Empirical numbers in Column 5 ("0.84 s on >50,000 nodes", "93.3%, rho=0.99").  
  *Recommendation:* Re-title Column 5 to "Target Validation Metrics" and list metric definitions rather than results.
- **Lines 148-157 (Section 2.6):**  
  *What to trim:*  
  1. Line 148 typos: "Beyond seeking to superseding the limiations...", "don't".  
  2. Numerical results in Items 2, 3, 4, 5 (0.84s, TD=0.58, kappa >= 0.82, |Delta d| <= 0.0308).  
  *Recommendation:* Focus entirely on the architectural mechanisms: Compressed Sparse Row GPU computation, density-based noise routing via HDBSCAN, dual-prompt inversion consensus, and automated LaTeX AST assembly.

### Section 3: Architecture
- **Line 226 (Figure 1 Tier 3):**  
  *What to trim:* "Three-tier heuristic"  
  *Recommendation:* Replace with: "Three-tier disambiguation protocol".
- **Line 307:**  
  *What to trim:* "beyond bag-of-words heuristics"  
  *Recommendation:* Replace with: "beyond frequency-based bag-of-words representations".
- **Line 348:**  
  *What to preserve:* Removal of "10-page IEEEtran".

### Section 4: Benchmark Methodology & Results
- **Line 403 (Table 1 - Distribution):**  
  *What to fix:* Correct the double-counting of BCI Stroke under both PRISMA and RevMan. Insert Parkinson's EEG and Rent Control into the representative examples. Ensure the studies listed sum cleanly to 30.
- **Line 407 (Table 2 - Matrix):**  
  *What to fix:* Fix LaTeX formatting on line 24 (escaped ampersand in `Journal of Innovation \& Knowledge`).
- **Line 459 (Table 3 - Thematic Clustering):**  
  *What to fix:* Add rows for the 3 newly introduced benchmarks (CitNetExplorer, Gephi, Bibexcel) or explain why they are excluded.
- **Line 463:**  
  *What to fix:* Correct the outlier noise range from `9.5% to 56.5%` to `0.0% to 56.5%` (or explain why Mobile Commerce at 0.0% is excluded). Correct the average NPMI from `-0.32` to `-0.31`.
- **Line 470:**  
  *What to fix:* Transparently report the negative rank correlations: institutional concordance for BCI Neurorehabilitation is $\rho = -0.40$ ($n=5$), and geopolitical concordance for Mobile Commerce is $\rho = -0.40$ ($n=4$).
- **Line 473:**  
  *What to trim:* `over 28 minutes (pre warmed RAM)`  
  *Recommendation:* Replace with: `over 28 minutes under warm-cache conditions`.
- **Line 478 (Table 4 - PRISMA Screening):**  
  *What to fix:*  
  1. Add columns for Cohen's $\kappa$ and $\text{WSS}@95$, or remove those claims from the text.  
  2. Remove the two empty placeholder rows (Parkinson's EEG and Rent Control).
- **Line 480:**  
  *What to preserve:* The honest discussion of low specificity (26.7%) and negative WMCC (-0.1414) on the ASReview cyberbullying corpus. This is excellent scientific self-critique.
- **Line 485 (Table 5 - Meta-Analysis):**  
  *What to fix:* Change column header from "GT d / Tool d" to "GT Effect ($\hat{\theta}$) / Tool Effect ($\hat{\theta}$)" and add a column indicating the specific effect metric. Add Cochran's $Q$ column to support the claim in line 487.

### Section 5: Discussion & Conclusion
- **Line 492:**  
  *What to fix:* Restore missing punctuation: `completely separate software ecosystems: exploratory tools...`
- **Line 494:**  
  *What to fix:* Rename `\subsection{Direct Drop-in Replacement?}` to `\subsection{Drop-in Replacement Audit and Mathematical Parity}`.
- **Lines 497-514:**  
  *What to trim:* Remove all repetitive recitation of Section 4 metrics.
- **Line 510:**  
  *What to fix:* Correct the contradiction: change "recovering 13/13 eligible trials" to "recovering 5/5 eligible trials ($N=5$)".
- **Line 516:**  
  *What to fix:* Add missing comma: `To our knowledge, no legacy tool spans...`
- **Line 536 (Conclusion):**  
  *What to trim:* Tighten the conclusion into a forward-looking summary rather than another recitation of metrics.

---

## 7. Concluding Editorial Remarks

OpenSciencePipe is a significant, high-potential software project that addresses genuine operational bottlenecks in scientometrics. The core engineering is impressive, and the empirical scope is commendable. However, the manuscript must adhere to the highest standards of scientometric and informetric scholarship. Once the empirical contradictions are resolved, the textual redundancies pruned, and the marketing rhetoric replaced with sober academic analysis, this manuscript will make a strong contribution to the literature.
