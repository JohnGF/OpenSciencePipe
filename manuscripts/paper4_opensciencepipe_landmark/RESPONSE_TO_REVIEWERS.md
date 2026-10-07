# Response to Reviewers

**Manuscript Title:** OpenSciencePipe: An End-to-End Framework for Autonomous Science Mapping and Systematic Evidence Synthesis  
**Authors:** Joao Garcia Farinha, Carlos Duarte  
**Target Venue:** *Journal of Informetrics* / *Quantitative Science Studies* / *Scientometrics*  

---

We thank the reviewer for the rigorous, insightful, and constructive critique of our manuscript. In response, we have comprehensively revised the text and empirical tables to eliminate textual repetition, ground all assertions in reproducible repository artifacts, resolve statistical and sample size ambiguities, and provide a transparent audit of both performance and usability trade-offs.

Below is our point-by-point response detailing the specific revisions made to the manuscript.

---

### 1. Textual Economy and Elimination of the "Echo Chamber"

> **Reviewer Comment:** *The manuscript currently repeats the exact same benchmark metrics across 8 separate sections: Highlights, Abstract, Section 1 (Intro), Table 1, Section 2.6 (Novelties), Section 4 (Results), Section 5.2 (Discussion), and Section 6 (Conclusion).*

**Author Response:**  
We have overhauled the narrative distribution across the manuscript:
1. **Highlights:** Replaced hyper-specific numerical strings with high-level conceptual and architectural contributions (macroscopic to microscopic integration, GPU scaling, HDBSCAN noise rejection, zero-shot screening, and automated compilation).
2. **Section 1 (Introduction):** Condensed the five-dimension performance list into a single paragraph outlining evaluation scope, directing readers to Section 4 for empirical results.
3. **Table 1 (Taxonomy):** Renamed Column 5 to "Target Validation Metrics & Scope", listing formal metric definitions (e.g., Modularity $Q$, PageRank latency, Spearman $\rho$) rather than premature empirical results.
4. **Section 2.6 (Novelties):** Shifted entirely from reporting benchmark numbers to detailing underlying architectural mechanisms (e.g., Compressed Sparse Row memory layout on device, HDBSCAN local density boundary clustering, zero-shot screening logic).
5. **Section 5.2 (Discussion):** Re-titled to *"Comparative Functional Audit: Workflow Migration and Usability Trade-offs"*. Replaced verbatim numerical statistics with a qualitative audit contrasting multi-dialog GUI onboarding and cognitive friction in legacy tools (VOSviewer, CiteSpace, SciMAT) against OpenSciencePipe's declarative, single-query specification.
6. **Section 6 (Conclusion):** Replaced repetitive numerical lists with a forward-looking summary and honest framing of methodological boundaries.

---

### 2. Empirical Accuracy, Sample Sizes, and Statistical Rigor

> **Reviewer Comment:** *Evaluating clinical screening on N=5 eligible trials was framed as broad clinical perfection, and exact heterogeneity ($I^2 = 87.5\%$) was asserted broadly when ground truth existed for only one benchmark.*

**Author Response:**  
- **Clinical Screening Sample Size ($N=5$):** Transparently stated across the Abstract, Section 4.4, and Table 4 that clinical trial sensitivity was benchmarked on a verified cohort of $N=5$ eligible studies (Ren et al., 2024), explicitly discussing the limitations of small-sample evaluation.
- **Heterogeneity Scope:** Explicitly clarified in Section 4.5 and Table 5 that published ground-truth heterogeneity was available only for Colditz et al. ($I^2 = 87.5\%$ vs. $87.46\%$), while other benchmarks lacked published ground-truth $I^2$ values.
- **Negative Rank Concordance Disclosure:** Rather than selectively reporting positive overlaps, Section 4.2 now explicitly discusses the observed negative Spearman correlations ($\rho = -0.40$ on $n=4$ for Mobile Commerce geopolitical rankings; $\rho = -0.40$ on $n=5$ for BCI institutional rankings), noting that small-sample correlations ($n \le 5$) are purely descriptive.
- **Unverified Assertions Removed:** Unsupported textual claims regarding Cohen's $\kappa \ge 0.82$ and $\text{WSS}@95 = 0.898$ were purged from the manuscript and tables.

---

### 3. Tabular Corrections and Benchmark Suite Coverage

> **Reviewer Comment:** *Table 1 double-counted BCI Neurorehabilitation. Table 3 omitted CitNetExplorer, Gephi, and Bibexcel. Table 4 had empty placeholder rows. Table 5 conflated all effect metrics under 'd'.*

**Author Response:**  
- **Table 1 (`tab_benchmark_tool_distribution.tex`):** Removed BCI Neurorehabilitation from the PRISMA row and retained it under RevMan. Integrated Parkinson's EEG (PRISMA) and Rent Control (RevMan / Stata). All 11 software families now sum cleanly to exactly 30 evaluations.
- **Table 3 (`tab_validation_thematic_clustering.tex`):** Fixed an `import re` bug in `src/core/collectors/openalex.py` that had truncated API harvests, executed the three benchmarks, and added rows for CitNetExplorer, Gephi, and Bibexcel/Pajek. Recomputed aggregate metrics in Section 4.1 ($\overline{\text{TD}} = 0.80$, noise isolation $= 32.1\%$, $C_{\text{NPMI}} = -0.28$).
- **Table 4 (`tab_validation_screening_prisma.tex`):** Removed empty `N/A` placeholder rows (Parkinson's EEG and Rent Control).
- **Table 5 (`tab_validation_meta_analysis.tex`):** Replaced uniform "$d$" labeling with standard meta-analytic effect notation $\hat{\theta}$. Added an "Effect Metric" column ($\ln\text{RR}$, partial $r$, $\ln\text{OR}$, Cohen's $d$) and a column for Cochran's $Q$ ($95.68$ for Colditz et al.).

---

### 4. Technical Tone, Academic Sobriety, and Clean Compilation

> **Reviewer Comment:** *Eliminate informal phrasing ('like a Google search', 'pre warmed RAM', 'don't') and ensure proper LaTeX compilation.*

**Author Response:**  
- Replaced informal phrasing with formal academic terminology (e.g., *"declarative, single-query specification"*, *"under warm-cache conditions"*, and removed contractions).
- Corrected double-participle and typographical errors.
- Verified that `main.tex` compiles cleanly with `pdflatex` (exit code 0, 0 undefined references, 27 pages).
