# Manuscript Revision & Re-Review Summary Package

**Manuscript Title:** OpenSciencePipe: An End-to-End Framework for Autonomous Science Mapping and Systematic Evidence Synthesis  
**Authors:** Joao Garcia Farinha, Carlos Duarte  
**Target Venue:** *Journal of Informetrics* / *Quantitative Science Studies* / *Scientometrics*  
**Date:** October 2026  

---

## 1. Package Overview

This folder contains the complete revision artifacts prepared for editorial/mentor review:
- **Compiled PDF:** `main.pdf` (28 pages, compiled with `pdflatex`)
- **Master LaTeX Source:** `main.tex` and accompanying tables in `tables/`
- **Initial Detailed Peer Review:** `../../review.md` (the original comprehensive critique)
- **Detailed Point-by-Point Author Response:** `RESPONSE_TO_REVIEWERS.md`

---

## 2. Executive Summary of Improvements

### A. De-duplication and Textual Economy
- **Eliminated Front-Matter Echo:** Highlights were rewritten to focus on core methodological contributions rather than repeating the identical numerical statistics verbatim from the Abstract.
- **Section 2.6 (Methodological Novelties):** Completely shifted from premature performance statistics to architectural mechanisms (Compressed Sparse Row GPU memory management, HDBSCAN local density boundary clustering, and local zero-shot language model screening).
- **Section 5.2 (Discussion):** Re-titled to *"Comparative Functional Audit: Workflow Migration and Usability Trade-offs"*. Converted the entire section into a qualitative workflow and cognitive friction audit (contrasting multi-dialog GUI overhead in VOSviewer, CiteSpace, and SciMAT with OpenSciencePipe's declarative, single-query specification) rather than reciting numbers.
- **Section 1 vs. Section 2:** Consolidated the Introduction's five evaluation dimensions into a single paragraph, delegating software-by-software operational taxonomies to Section 2.

### B. Statistical Rigor and Sample Size Disclosures
- **Clinical Screening Sample Size ($N=5$):** Explicitly declared in the Abstract, Section 4.4, and Table 4 that clinical trial sensitivity was evaluated on a verified ground-truth cohort of $N=5$ eligible studies (Ren et al., 2024), discussing the trade-offs of small-sample validation.
- **Heterogeneity Scope:** Clarified in Section 4.5 and Table 5 that published ground-truth heterogeneity was available only for Colditz et al. ($I^2 = 87.5\%$ vs. $87.46\%$), avoiding overgeneralization.
- **Full Reporting of Concordance:** Transparently disclosed negative rank correlations ($\rho = -0.40$ on $n=4$ for Mobile Commerce geopolitical rankings; $\rho = -0.40$ on $n=5$ for BCI institutional rankings), noting that small-sample Spearman correlations ($n \le 5$) are purely descriptive.
- **Public Health Divergence:** Explicitly explained in Section 4.2 the 0.0% institutional recovery on the Public Health benchmark as stemming from single-institution ground truth ($N=1$, Harvard) from proprietary Web of Science categories evaluated against sparse affiliation records ($25/200$) in open harvests.
- **Purged Unsupported Assertions:** Excised unverified references to Cohen's $\kappa \ge 0.82$, $\text{WSS}@95 = 0.898$, and abstract baseline $\text{TD} = 0.58$.

### C. Tabular Integrity and Benchmark Coverage
- **Table 1 (`tab_benchmark_tool_distribution.tex`):** Updated RevMan / Stata / metafor to 6 studies (integrating Doucouliagos & Stanley minimum wage) and reconciled non-meta categories to 24 unique studies, cleanly summing all 11 software families to 30 evaluations.
- **Table 3 (`tab_validation_thematic_clustering.tex`):** Resolved an `import re` bug in `src/core/collectors/openalex.py`, ran the pipeline, and integrated the 3 missing benchmarks (CitNetExplorer, Gephi, Bibexcel/Pajek). Recomputed Section 4.1 aggregate means ($\overline{\text{TD}} = 0.80$, noise isolation $= 32.1\%$, $C_{\text{NPMI}} = -0.28$). Added descriptive correlation footnote.
- **Table 4 (`tab_validation_screening_prisma.tex`):** Removed empty `N/A` placeholder rows and stripped draft section prefix from caption.
- **Table 5 (`tab_validation_meta_analysis.tex`):** Unified under meta-analytic effect parameter $\hat{\theta}$, designated distinct effect metrics ($\ln\text{RR}$, partial $r$, $\ln\text{OR}$, Cohen's $d$), and added Cochran's $Q$. Stripped draft section prefix from caption.

---

## 3. Independent Re-Review Assessment

An independent re-review of the revised manuscript confirmed complete resolution across all primary critique dimensions. The manuscript compiles with 0 errors and 0 undefined references.
