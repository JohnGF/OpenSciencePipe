# Second review — OpenSciencePipe manuscript (revised)

Oct 14, 2026 · @Carlos Duarte

## Summary and recommendation

**Recommendation: not ready for submission; major revision.** The revision fixes most of the bookkeeping problems from the first review, but it doubles the scope (adding PRISMA screening, meta-analysis and manuscript generation) without validating the new parts, and several headline results do not survive a check against the repository or the cited sources.

The revised manuscript reframes OpenSciencePipe as a single pipeline for both science mapping and evidence synthesis. It reports 30 benchmarks: topic diversity and coherence, country and institution rank concordance, a GPU timing, LLM screening on four systematic reviews, and DerSimonian–Laird pooling on four classic meta-analyses.

What improved: tables and text now agree on the country results, the diversity metric is named correctly, sample sizes are reported for every correlation, negative results are shown, and there are figures and a much richer related-work section.

What blocks submission, in order of seriousness:

1. **Results that do not trace to their sources.** The BCG meta-analysis "ground truth" (θ = −0.7606, I² = 87.46%) is not what the standard Colditz data give (I recomputed: −0.714, I² = 92.1%), and I² did not exist in 1994. The ChatGPT/USMLE paper used for country and institution concordance reports neither. The institutional ground truths exist only in the manuscript text.
2. **Code that does not match the paper.** The public `main` branch has no meta-analysis, screening orchestration, fuzzy deduplication or benchmark data; the coherence script assigns −1 to every non-co-occurring word pair, which explains the uniformly negative NPMI.
3. **Screening evaluated on 9 to 128 records per review**, with prevalence up to 92%, so the reported precision says nothing about real screening.
4. **Meta-analysis replication tests arithmetic on hand-entered data**, not the end-to-end extraction the paper claims.
5. **Scope.** Two papers' worth of claims are packed into one, with the informetrics core still lacking baselines, ablations and thematic validation. The repository already contains separate drafts for a bibliometric paper and a meta-analysis paper; that split is the right one.

A security problem also needs immediate action: the repository's `main` branch still tracks a `.env` file with API keys (see the repository section).

## Status of first-review issues

**Of the 14 issues raised in the first review, 1 is fixed, 7 are partly addressed, 5 are not addressed and 1 is mixed.** The fixes are mostly in reporting; the evaluation gaps remain.

| Issue (first review) | Status | What changed / what remains |
| --- | --- | --- |
| M1 Inconsistencies between text and tables | Partly fixed | Country figures now agree across Tables 3–4 and text. Remaining: "Solar Power" and "GenAI Education" in Table 2 have no Table 3 entry; "Electrophysiology" vs "Electroencephalography"; the IJERPH top-100 study is "Dentistry" in Table 2 and "Public Health" in Section 5.2; Section 6.4 still generalises ρ ≥ 0.96. |
| M2 Diversity metric mislabelled | Fixed | Now TD with Dieng et al. as source. Still no baseline to say what "high" means. |
| M3 Negative NPMI not discussed | Partly addressed | Now discussed, but the explanation is wrong (see N4); the two former "nan" values now have numbers with no explanation. |
| M4 Spearman on tiny samples | Partly fixed | n reported; n ≤ 5 labelled descriptive. Still intersection-only, no top-k measure such as RBO (now in the reference list but never used), no naive baseline. |
| M5 Benchmark design | Partly addressed | Legacy-tool column added. Still no query/N protocol, no selection criteria; non-bibliometric studies still counted as bibliometric. |
| M6 Novel components untested | Not addressed | No LDA or co-occurrence baseline, no ablation, no thematic validation, though the repository has a baseline script (see N6). |
| M7 Outliers presented as success | Not addressed | Sensitivity analysis claimed, not shown; a new unsupported "20–40% peripheral records" claim added. |
| S1 LLM tier unevaluated | Partly addressed | Four reviews now, but tiny, positive-enriched sets (N3). No WSS@95, no comparison with ASReview. |
| S2 GPU baseline | Not addressed | Still NetworkX only; CPU time changed from 14 to 28 min between versions; GPU hardware no longer named. |
| S3 Deduplication | Not addressed | No evaluation; the public code uses exact title matching, not the Levenshtein rule in Eq. 2 (N2). |
| S4 Author disambiguation | Partly addressed | Now described; not evaluated; Figure 2 shows visible failures (N7). |
| S5 Data model | Partly addressed | Co-citation/coupling matrices described; schema (Eq. 1) still lacks references, countries, keywords. |
| S6 BERTopic configuration | Not addressed | No hyperparameters, seeds or embedding comparison. |
| S7 Overclaiming | Fixed in places, worse in others | Conclusion is now appropriately cautious; but Section 2.6 claims six mechanisms that "do not exist in prior systems" and "first system", and 6.4 claims to capture "true" structures. |

## Strengths

1. **Honest reporting of negative results.** The ρ = −1.00 and −0.40 cases, the failed cyberbullying screening (WMCC = −0.14) and the 0% institutional overlap for the IJERPH study are reported and discussed rather than hidden. Reviewers respond well to this.
2. **Statistical caution where it was missing.** Every correlation now carries its n, and n ≤ 5 is explicitly labelled descriptive (Section 5.2, Table 4 note). The conclusion now says screening and small-sample concordance need larger validation.
3. **Internal consistency of the country results.** Table 3, Table 4 and the text now agree; the TD summary statistics are correct (I recomputed mean 0.798, median 0.80 over 20 corpora, and mean NPMI −0.281).
4. **Much stronger related work.** The five-class tool taxonomy (Section 2.2) and Table 1 give a clear map of the landscape, and most references suggested in the first review were adopted and correctly cited (Dieng, Röder, Bouma, Hoyle, Visser, Martín-Martín, Cohen, Kleinberg, PRISMA 2020).
5. **Figures.** The architecture diagram (Figure 1) is clear, and example outputs make the system tangible.
6. **Meta-analysis equations are correct.** Eqs. 6–10 state the DerSimonian–Laird estimator and I² properly; the PageRank normalisation is now stated.
7. **Usability trade-offs acknowledged.** Section 6.2 concedes what GUI tools still do better, which is fairer than the first version.
8. **New institutional-level analysis.** Comparing institution rankings is a sensible complement to country rankings, once the ground truth is traceable (N1).

## Major issues

Eight issues, ordered by risk. N1 and N2 concern whether the reported numbers are what they claim to be; a reviewer who finds either will likely stop reading.

### N1. Several ground truths are not traceable, and some cannot be correct

**BCG vaccine (Colditz et al., 1994).** Table 6 reports a published θ = −0.7606, I² = 87.46% and an "exact replication" (error 0.0000). Two problems:

- I² was introduced by Higgins and Thompson in 2002, so a 1994 paper cannot have published it.
- I recomputed DerSimonian–Laird on the standard 13-trial BCG dataset (the one distributed with metafor as `dat.bcg`): ln RR = −0.714 (RR = 0.49, consistent, as far as I recall, with the pooled RR Colditz et al. report for the trials), Q = 152.2, I² = 92.1%. The paper's values (−0.7606, Q = 95.68, I² = 87.5%) correspond to different input data. The "exact" match therefore compares the tool with values in its own benchmark file, not with the publication. Please verify with `metafor::rma(measure="RR", ai=tpos, bi=tneg, ci=cpos, di=cneg, data=dat.bcg, method="DL")`.

**ChatGPT on USMLE (Kung et al., 2023).** This is an evaluation of ChatGPT on licensing-exam questions; it publishes no country or institution rankings. Yet it carries two of the paper's strongest results (100% country overlap, ρ = 0.96; 100% institution overlap). The repository's reference file for this DOI holds only title, authors and abstract. Either the DOI is wrong (perhaps a bibliometric study of ChatGPT in medicine was intended) or the ground truth came from elsewhere. Until resolved, these results must be removed.

**Institutional rankings.** The top-8 institution lists in Section 5.2 (e.g., EEG: University of California, Toronto, Sapienza…) appear in the manuscript source but in no data file I could find in the repository. Every ground-truth value needs a pointer to the table or figure of the source paper it was read from.

**Other meta-analyses.** Doucouliagos and Stanley's −0.0150 is a publication-bias-corrected meta-regression estimate; the tool's −0.0458 is a plain random-effects mean. These are different estimands, and a three-fold difference is not a replication. Smith and Glass (1977) predates random-effects pooling and averaged several hundred effect sizes without weighting; a tool I² of 0% for psychotherapy outcomes is implausible and suggests very few input values. Nissen and Wolski pooled odds ratios with a fixed-effect method (Peto, as far as I recall; please check), so a DL estimate is not expected to match.

**What counts as a "bibliometric study".** Of the 26 entries in Table 3, six are systematic reviews or meta-analyses (BCI-FES, cyberbullying, nosocomial infection, qEEG Parkinson's, ML neurodegeneration, rent control), one is an empirical LLM study (USMLE) and one is a software paper (CitNetExplorer). "26 published bibliometric studies" in the abstract, highlights and Section 4 is inaccurate.

**Benchmark list drift.** The repository's `benchmark_references/` folder contains DOIs not in the paper (e.g., 10.1016/j.apmr.2024.04.001, 10.1109/access.2023.3337669, 10.3390/w13152041) and lacks several that are (CitNetExplorer, JBR, drones, the screening and meta-analysis benchmarks). A frozen, versioned benchmark manifest is needed.

### N2. The paper describes code that is not in the public repository

I cloned the repository on 14 October 2026. The `main` branch (which the Data Availability statement points to) does not contain the meta-analysis engine, `MetaOrchestrator`, `SystematicOrchestrator`, `GrepRelevanceFilter`, `ActiveLearningPriorityRanker`, Egger/Begg/trim-and-fill, WMCC or author disambiguation. Most of these exist only on an unmerged branch (`feat/automated-meta-analysis-…`, last commit 8 October 2026). Table 1 cites `src/core/meta_analysis.py` and `meta_validator.py`, which are not on `main`.

- **Deduplication (Eq. 2).** On both branches, titles are lower-cased, stripped to alphanumerics and matched exactly. I found no Levenshtein distance and no 0.92 threshold anywhere in the source. Either the paper or the code must change.
- **Benchmark data.** The paper says all benchmark datasets are under `data/benchmarks/`. On both branches `data/` is git-ignored and holds only a `.gitkeep`. The per-study effect sizes and variances used for Table 6 are not public, so Table 6 cannot be reproduced.
- **Stated plan vs delivered evaluation.** The branch's own `BENCHMARK_PAPER_PLAN.md` sets screening recall ≥ 95%, WSS@95 and ARI/NMI against VOSviewer/CiteSpace partitions as targets. None appear in the paper. Reviewers who open the repository will see this.

### N3. The screening evaluation uses tiny, positive-enriched sets

Back-calculating the confusion matrices from Table 5:

| Benchmark | Eligible | Records evaluated (approx.) | Prevalence | Implication |
| --- | --- | --- | --- | --- |
| BCI-FES (Ren et al.) | 5 | 9 (TP 5, FP 1, TN 3) | 56% | Not a screening task |
| Cyberbullying (Zhang et al.) | 25 | \~40 (TN 4) | \~62% | Specificity from 15 negatives |
| Nosocomial infection (Rafiei et al.) | 17 | 17 (no negatives; specificity N/A) | 100% | Precision = 100% is automatic |
| ML neurodegeneration (Yousefi et al.) | 118 | \~128 (FP 3, TN 7) | 92% | 96.5% precision reflects prevalence |

Real title/abstract screening typically has prevalence of a few percent, which is why the paper motivates WMCC by "extreme class imbalance (P ≪ N)"; here the imbalance runs the other way. Precision and "eliminates 26.7%–75% of non-qualifying records" are therefore not interpretable, and recall of 60%–70% is well below the \~95% normally expected. Headlining "100% sensitivity" (n = 5) and "96.5% precision" in the abstract is not defensible.

The same benchmark is also internally inconsistent: Table 5 has 5 eligible studies, but the Figure 3 forest plot for "the Ren et al. benchmark" pools 10 studies, and its PRISMA diagram reports 1,880 included records. The forest plot includes Cervera et al. (2018), which I believe is itself a meta-analysis, and Ramos-Murguialday et al. (2013), which as far as I know used an orthosis rather than FES. Please check these against Ren et al.'s included trials.

What a credible evaluation needs: the full set of records each original review screened (or fully labelled public datasets such as SYNERGY or CLEF TAR), recall/precision/WSS@95 on those, the exact model, prompt and criteria, repeated-run agreement, a comparison with ASReview on the same data, and a statement of which of the four screening modes (regex, embedding, LLM, active learning) produced each number.

### N4. The negative NPMI is an implementation artefact, and the explanation offered is incorrect

The paper attributes uniformly negative coherence (−0.04 to −0.84) to small corpora and c-TF-IDF, citing Röder et al. and Hoyle et al. Neither, as far as I know, makes that claim, and the 57,601-paper EEG corpus is negative too (−0.15).

The branch's `scripts/evaluate_clustering_benchmarks.py` (function `compute_cv_coherence_approx`) explains it: documents are tokenised with a bare whitespace split (punctuation stays attached, so `learning,` ≠ `learning`); multi-word c-TF-IDF terms can never match a single token; marginal counts are floored at 1; and **any pair that never co-occurs is assigned −1.0** rather than ε as in Eq. 14. A few unmatched pairs per topic are enough to drive the mean negative.

Fix: compute C\_NPMI with a standard implementation (gensim `CoherenceModel` or OCTIS) using the same tokeniser as the topic vectoriser, report the reference corpus and window, run the same computation on an LDA baseline and on random word sets as sanity checks, and rewrite the explanation.

### N5. Meta-analysis "replication" tests arithmetic, not the pipeline

The validator reads per-study effect sizes and variances (`d_i`, `v_i`, plus `ablat`, the BCG latitude moderator from metafor's dataset) from hand-prepared JSON files and checks pooled values against expected numbers, with a pass tolerance of 0.08 on θ and 5 percentage points on I². This only confirms that a correctly coded DL formula gives DL results, which metafor already guarantees.

It does not test what Section 2.6 (item 5) claims: extraction of statistical parameters from the screened corpus. Section 6.5 also says extraction currently uses abstracts and that full-text extraction is future work, but abstracts of 1977 and 1994 papers do not contain per-study data. Further points:

- Absolute deviation across ln RR, ln OR, partial r and d is not a common scale; report relative error and confidence-interval overlap per study.
- DL is known to underestimate τ² with few or heterogeneous studies; offer REML and the Hartung–Knapp–Sidik–Jonkman adjustment.
- Egger's test and trim-and-fill are not recommended with fewer than about ten studies; Figure 3 applies them to ten.

**For the informetrics route, I recommend removing evidence synthesis from this paper** (keep one paragraph in future work) and developing it as a separate paper for a research-synthesis venue once extraction is validated. The repository already has separate drafts for a bibliometric paper and a meta-analysis paper.

### N6. The informetrics core still lacks baselines and thematic validation

This was the central request of the first review and it remains open. The repository already contains `scripts/run_head_to_head_baselines.py` (BERTopic vs LDA; cuGraph vs NetworkX vs igraph, with modularity and partition concordance), but its results are not in the paper. Running it is the fastest improvement available.

Still needed: thematic validity against the benchmarks' published clusters (ARI/NMI, or rater mapping), as the authors' own plan proposes; ablation of the embedding model and HDBSCAN parameters; stability across seeds; and the claimed `mcl ∈ [10, 50]` sensitivity analysis, which Section 5.1 asserts but does not show.

The software-parity claims also lack results. Section 4 says the suite verifies "computational parity" with CitNetExplorer, Gephi and Bibexcel on their "mathematical primitives", and Table 1 lists modularity Q, PageRank, CAGR and percolation as evaluated metrics. None of these is reported for any benchmark; Table 4 gives only TD, NPMI and outliers for the CitNetExplorer, JBR and drones studies.

### N7. Author disambiguation visibly fails in Figure 2

Section 6.4 says disambiguation prevents false merges and preserves true topology. Figure 2a, on the EEG corpus, shows "Tzyy-Ping Jung" and "Tzyy Ping Jung" as separate nodes (a split) and single nodes for highly homonymous names such as "Wei Wang", "Wei Zhang", "Lei Zhang", "Yang Liu" and "Jing Wang" (likely merges of many people). These are exactly the errors the paper says it prevents. Evaluate disambiguation on an ORCID-linked subset, report split and merge rates, state whether OpenAlex author IDs are used as given, and remove the claim until then.

### N8. Overclaiming and positioning

- **"Six mechanisms that do not exist in prior systems" (Section 2.6).** GPU graph analytics is what cuGraph provides; HDBSCAN noise isolation is BERTopic's default behaviour; LLM screening has a growing literature; DL pooling is in metafor; report generation exists in R Markdown and Quarto. The contribution is the integration; say so.
- **"First system to bridge" mapping and evidence synthesis.** Prior tools combine parts of this: revtools (screening supported by topic models) and metagear (screening, extraction and meta-analysis in R). Cite and position against them.
- **Related work regressed.** The first version fairly acknowledged that VOSviewer has API connectors; the revision now calls VOSviewer, CiteSpace and Bibliometrix "isolated GUI desktop applications" with "manual batch exports", and says Bibliometrix is tied to a Shiny session, though it is a scriptable R package. QSS and Scientometrics reviewers will include these tools' authors.
- **Section 6.4 logic.** Agreement between OpenAlex and WoS rankings shows the databases agree, not that the pipeline captures the "true underlying" structure. It also rests on two benchmarks, one of which (USMLE) is in question.
- **Usability claims without users.** Section 6.2 makes claims about onboarding, cognitive cost and friction. Either support them with a small user study or state them as design rationale.
- **"Autonomous" and automated manuscript compilation.** Reviewers may read a tool that "generates complete manuscripts" as paper-mill infrastructure. Frame Tier 5 as reproducible report generation, and keep "automated" rather than "autonomous".

## Further methodological concerns

### F1. GPU benchmark

- The CPU time for the same corpus changed from "over 14 minutes" (first version) to "over 28 minutes under warm-cache conditions" (revision), while the GPU time (0.84 s) and the ">1,000×" claim stayed fixed. Explain what changed.
- The GPU is no longer named. The first version said RTX 4090 (24 GB); the revision speaks of "standard 6 GB VRAM" and "older consumer graphics cards". Name the hardware for both sides.
- The baseline is still single-threaded NetworkX. Report igraph (already in the authors' baseline script) and ideally NetworKit or graph-tool, plus Leiden, which cuGraph also offers.
- "Graphs exceeding 50,000 publications" conflates papers and nodes: the co-authorship graph's nodes are authors. Report nodes, edges, what is timed (construction, transfer, algorithm), repetitions and spread, and modularity on both sides.

### F2. Rank-concordance statistics

Spearman is still computed only on the intersection of the two top-K lists, which conditions on agreement. Webber et al.'s RBO is now in the reference list (\[38\]) but never used; use it, or Jaccard@K, on the full lists. Add a naive baseline (the field's overall country ranking in OpenAlex for the same years) to show the query-specific corpus does better than the prior. Also, Visser et al. and Martín-Martín et al. (\[33, 34\]) compare database coverage; they do not define a top-K rank-validation protocol, so "following cross-database validation protocols \[33, 34\]" overstates them.

### F3. The "leading universities" explanation is untested

ρ = −1.00 is attributed to Scopus fractional counting versus OpenAlex author-level attribution. That is a plausible hypothesis, but it can be tested directly: recompute with fractional counting and report whether the inversion disappears.

### F4. Outlier pool claims

"Automated scholarly API harvesting inevitably retrieves 20%–40% peripheral or homonymous records" has no source or data, and is used to justify the 32% outlier rate, which is circular. Audit a random sample of Topic −1 documents per corpus and report the fraction that is genuinely off-topic. Blockchain (0 topics, 100% outliers) is still a silent failure case.

### F5. WMCC

The weighting (w\_pos = N/2P, w\_neg = N/2N\_neg) is a class-balanced MCC with no citation. Give its formula, a reference or justification, and report standard MCC and balanced accuracy alongside it.

### F6. Data model and configuration

- Eq. 1 still lacks reference lists, countries, keywords and identifiers, yet co-citation (X⊤X), coupling (XX⊤), country and institution analyses need them. Define X and extend the schema.
- Report all BERTopic hyperparameters (UMAP, HDBSCAN, vectoriser, c-TF-IDF options), seeds and library versions; the embedding model (all-MiniLM-L6-v2) truncates long abstracts and is not domain-specific.
- State the Ollama model actually used for Table 5 (the code default is llama3.2:3b), its digest, the prompt and the JSON schema; report the rate of invalid outputs.
- Record API query dates or an OpenAlex snapshot date for every benchmark.

### F7. Scopus and IEEE data

The acknowledgements thank IEEE for elevated API limits and Elsevier for API access. State which benchmarks used Scopus or IEEE data. This matters for two reasons: the OpenAlex-vs-WoS/Scopus argument is muddied if some corpora came from Scopus, and Elsevier's API terms restrict redistributing Scopus records, which conflicts with "all benchmark datasets fully accessible".

## Code and data availability

**None of the repository fixes from the first review has been made, and one is now a live security problem.** I cloned the [repository](https://github.com/JohnGF/OpenSciencePipe) on 14 October 2026 (`main` at commit 7da0f65, 11 October 2026) and fetched the `feat/automated-meta-analysis` branch.

| Item | Status on `main` | Action |
| --- | --- | --- |
| `.env` file | Still tracked, with non-empty values for Scopus, IEEE, PubMed, Semantic Scholar and Web of Science keys. Listing `.env` in `.gitignore` does not untrack an already-committed file. | Revoke and reissue all keys now; remove the file from git history; `git rm --cached .env`. |
| Licence | No LICENSE file on `main`; the README shows only an MIT badge. A LICENSE exists on the unmerged branch. | Merge it; the paper's "MIT licence" claim depends on it. |
| Repository URL | The paper cites github.com/JohnGF/bibliometric, which redirects to OpenSciencePipe; README and CITATION.cff still cite "bibliometric" by "GF, John". | Use one name and URL everywhere; fix authorship metadata. |
| Benchmark data | `data/` is git-ignored and empty on both branches. | Publish the benchmark manifest, ground-truth values with source locations, and per-study meta-analysis inputs. |
| Described components | Meta-analysis, screening orchestration, active learning, disambiguation, WMCC: branch only. Fuzzy deduplication: nowhere. | Merge, tag a release, archive it (e.g., Zenodo), and cite the DOI of the exact version used. |
| "Build passing" badge | A static image, not linked to any CI; there is no `.github/` workflow. | Add CI or remove the badge, which reviewers will read as misleading. |
| Hygiene | `patch_export.py`, `patch_fetch.py`, `test_script.py`, agent configuration folders and `GEMINI.md` at the root. | Move or remove. |

The agent configuration files suggest AI-assisted development and possibly writing. Elsevier and most publishers require a generative-AI declaration covering the manuscript; the revision has none.

## Minor issues

### Figures

- **Figure 2a** shows roughly 100 author names around a chord diagram; at print size it is unreadable and the chord layout hides community structure. Show a conventional network layout coloured by community, labelling only the top nodes.
- **Figure 2b** is titled "Global Research Output & Institutional Heatmap by Country" and shows publication volume, but the caption calls it collaboration intensity. The colour bar (0–6, "log scale") needs units.
- **Figure 3a** is arithmetically inconsistent: 2,867 identified minus 987 excluded gives 1,880, but the screening box says 2,547, and eligibility equals inclusion (1,880) for a meta-analysis of about ten trials. See also N3.

### Tables

- Tables 3 and 4 still truncate titles and journal names mid-word and fill many cells with N/A. Assign benchmark IDs (B1–B30), cite every benchmark in the reference list, add corpus size N and query date, and split Table 4 into topic-quality and concordance tables containing only applicable benchmarks.
- Table 2: "PRISMA" is a reporting guideline, not software; "Solar Power" and "GenAI Education" do not appear in Table 3; the VOSviewer count (9) does not match Table 3, where 10 entries list VOSviewer alone or with another tool.
- Table 6 reports I² but "Q: N/A" for two rows; I² is computed from Q, so Q is known. Add k (number of studies) per row.

### Text

- The abstract still states "26 published bibliometric studies" (see N1) and an absolute deviation of 0.0308 pooled across incommensurable effect metrics.
- The highlights exceed Elsevier's 85-character limit and repeat the "11 software paradigms" claim.
- Author disambiguation is described twice (Sections 3.3 and 6.4) with different mechanisms ("temporal overlap" vs "positional author-institution pairing"). Describe it once, accurately.
- Section 4.1.3 says NPMI "strongly correlates with human conceptual interpretability", citing Röder et al. and Bouma; Bouma does not address human judgement, and Hoyle et al. \[41\], cited elsewhere, argue the correlation is weak for neural topic models. Nuance the claim.
- **Acknowledgements:** "gratuitously granting" means "without good reason" in English; use "kindly granting … free of charge". Elsevier's APIs are not "open"; say "developer APIs".
- **CRediT:** Carlos Duarte is now listed only for "Review & editing", although the first version listed Conceptualization, Methodology, Supervision and Investigation. At minimum add "Supervision"; the roles should reflect what actually happened.

### References

- &#91;16\] BERT: cite the NAACL-HLT 2019 version instead of the arXiv preprint (raised in the first review).
- &#91;54\] metaknowledge is listed as "Quantitative Science Studies / arXiv (2017)"; QSS did not exist in 2017. Cite the arXiv preprint (1709.07436) or the actual venue.
- &#91;56\] Börner's *Atlas of Science* is a book, cited for the Sci2 Tool; cite the Sci2 Tool itself.
- &#91;38\] (Webber et al.) is listed but never cited in the text.
- Uncited: Begg's rank correlation test, Higgins and Thompson's I², Connected Papers and Litmaps.

## Suggested references

All entries below are real works. Those marked "checked" were confirmed by a web search today; the rest are well-established references I am confident of. Verify page numbers and volumes against the source before citing.

### Meta-analysis methods (N1, N5)

- Higgins, J. P. T., & Thompson, S. G. (2002). Quantifying heterogeneity in a meta-analysis. *Statistics in Medicine*, 21(11), 1539–1558. Origin of I²; dates the BCG issue.
- Viechtbauer, W. (2005). Bias and efficiency of meta-analytic variance estimators in the random-effects model. *Journal of Educational and Behavioral Statistics*, 30(3), 261–293. Background for offering REML beside DL.
- Veroniki, A. A., Jackson, D., Viechtbauer, W., et al. (2016). Methods to estimate the between-study variance and its uncertainty in meta-analysis. *Research Synthesis Methods*, 7(1), 55–79.
- IntHout, J., Ioannidis, J. P. A., & Borm, G. F. (2014). The Hartung–Knapp–Sidik–Jonkman method for random effects meta-analysis is straightforward and considerably outperforms the standard DerSimonian–Laird method. *BMC Medical Research Methodology*, 14, 25.
- Sterne, J. A. C., Sutton, A. J., Ioannidis, J. P. A., et al. (2011). Recommendations for examining and interpreting funnel plot asymmetry in meta-analyses of randomised controlled trials. *BMJ*, 343, d4002. Source for the \~10-study minimum for Egger's test.
- Begg, C. B., & Mazumdar, M. (1994). Operating characteristics of a rank correlation test for publication bias. *Biometrics*, 50(4), 1088–1101. Begg's test is used but not cited.

### Screening evaluation (N3)

- De Bruin, J., Ma, Y., Ferdinands, G., Teijema, J., & Van de Schoot, R. (2023). SYNERGY – Open machine learning dataset on study selection in systematic reviews. DataverseNL. Fully labelled screening datasets, including excluded records. (checked; [project page](https://www.uu.nl/en/research/ai-labs/disc-ai-lab/projects/software-tools-and-infrastructure/synergy))
- Kanoulas, E., Li, D., Azzopardi, L., & Spijker, R. (2017). CLEF 2017 technologically assisted reviews in empirical medicine overview. *CEUR Workshop Proceedings*, Vol. 1866. The CLEF TAR benchmark collections.
- Guo, E., Gupta, M., Deng, J., Park, Y.-J., Paget, M., & Naugler, C. (2024). Automated paper screening for clinical reviews using large language models: Data analysis study. *Journal of Medical Internet Research*, 26, e48996. (checked; [JMIR](https://jmir.org/2024/1/e48996/authors))
- Khraisha, Q., Put, S., Kappenberg, J., Warraitch, A., & Hadfield, K. (2024). Can large language models replace humans in systematic reviews? Evaluating GPT-4's efficacy in screening and extracting data from peer-reviewed and grey literature in multiple languages. *Research Synthesis Methods*. doi:10.1002/jrsm.1715. (checked; [arXiv version](https://arxiv.org/abs/2310.17526))

### Integrated evidence-synthesis tools (N8)

- Westgate, M. J. (2019). revtools: An R package to support article screening for evidence synthesis. *Research Synthesis Methods*, 10(4), 606–614. (checked; [preprint](https://www.biorxiv.org/content/10.1101/262881v2))
- Lajeunesse, M. J. (2016). Facilitating systematic reviews, data extraction and meta-analysis with the metagear package for R. *Methods in Ecology and Evolution*, 7(3), 323–330. (package checked on [CRAN](https://cran.r-project.org/web/packages/metagear/); confirm the article details)

### Still outstanding from the first review

- Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden: Guaranteeing well-connected communities. *Scientific Reports*, 9, 5233. (F1)
- Lau, J. H., Newman, D., & Baldwin, T. (2014). Machine reading tea leaves: Automatically evaluating topic coherence and topic model quality. *Proceedings of EACL 2014*. For the human topic evaluation (N6).
- Terragni, S., et al. (2021). OCTIS: Comparing and optimizing topic models is simple! *Proceedings of EACL 2021: System Demonstrations*. Standard coherence implementation (N4).
- Šubelj, L., van Eck, N. J., & Waltman, L. (2016). Clustering scientific publications based on citation relations: A systematic comparison of different methods. *PLOS ONE*, 11(4), e0154404. For thematic validation against citation-based clusters (N6).
- Cohan, A., Feldman, S., Beltagy, I., Downey, D., & Weld, D. S. (2020). SPECTER: Document-level representation learning using citation-informed transformers. *Proceedings of ACL 2020*. Embedding ablation (F6).
- Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. *Proceedings of NAACL-HLT 2019*. Replaces \[16\].

Sources checked today: [revtools preprint](https://www.biorxiv.org/content/10.1101/262881v2), [metagear on CRAN](https://cran.r-project.org/web/packages/metagear/), [Guo et al. (JMIR)](https://jmir.org/2024/1/e48996/authors), [Khraisha et al. (arXiv)](https://arxiv.org/abs/2310.17526), [SYNERGY](https://www.uu.nl/en/research/ai-labs/disc-ai-lab/projects/software-tools-and-infrastructure/synergy), [OpenSciencePipe repository](https://github.com/JohnGF/OpenSciencePipe).

## Prioritized revision plan

The target remains QSS, with Scientometrics as the fallback. The first block is about integrity and must come before anything else; the second makes the informetrics paper publishable.

**Immediately**

- [ ] Revoke and reissue every key in the committed `.env`; purge it from git history.
- [ ] Trace every ground-truth value to a table or figure in its source paper; drop the USMLE benchmark unless a real ground truth exists.
- [ ] Replace the BCG ground truth with the published estimate (and no published I²); re-run all four meta-analysis checks against the actual publications.
- [ ] Make the paper describe the code that exists: either implement Levenshtein deduplication or describe exact matching; merge the branch; publish the benchmark data.
- [ ] Fix the NPMI computation with a standard implementation and rewrite Section 5.1's explanation.

**Before submission to QSS**

- [ ] Narrow the paper to science mapping; move screening and meta-analysis to a separate paper (the repository already has separate drafts).
- [ ] Report the existing baseline script results (LDA; NetworkX, igraph and cuGraph with modularity and partition agreement).
- [ ] Add thematic validation against the benchmarks' published clusters (ARI/NMI or rater mapping), ablations and seed stability.
- [ ] Evaluate deduplication and author disambiguation (precision/recall on labelled samples; ORCID-linked subset); fix Figure 2.
- [ ] Recompute rank concordance with RBO on full lists plus a naive OpenAlex baseline; test the fractional-counting explanation.
- [ ] Correct the benchmark count and labels; add a protocol table (database, query, dates, original N, retrieved N).
- [ ] Restore a fair related-work account of VOSviewer and Bibliometrix; position against revtools and metagear only if evidence synthesis stays.
- [ ] Tone down Sections 2.6 and 6.4; add a generative-AI declaration; fix CRediT roles, acknowledgements wording and references.
- [ ] Tag a release, archive it with a DOI, add a LICENSE and CI.

**For the later evidence-synthesis paper**

- [ ] Screening on fully labelled datasets (SYNERGY, CLEF TAR) with recall, WSS@95 and an ASReview comparison.
- [ ] Validate extraction of effect sizes separately from pooling; add REML and HKSJ options.

The immediate block is small in effort but decisive: a reviewer who finds the BCG or USMLE problems will doubt every other number in the paper.
