# Manuscripts Directory

This directory contains the self-contained publication scaffolds and camera-ready LaTeX sources for the project's manuscripts. Each manuscript is organized within its own folder, complete with styling templates (`IEEEtran.cls`), tables, figures, LaTeX sources (`main.tex`), and compiled PDFs (`main.pdf`).

---

## Directory Structure

```
manuscripts/
├── README.md                                # This documentation file
│
├── paper1_bibliometric_benchmark/           # Paper 1: Methodological Science Mapping Benchmark
│   ├── main.tex                             # Camera-ready IEEEtran LaTeX source
│   ├── main.pdf                             # Compiled 3-page manuscript
│   ├── IEEEtran.cls                         # IEEE journal formatting class
│   └── tables/                              # Empirical validation tables (16 corpora)
│       ├── tab_validation_thematic_clustering.tex
│       └── tab_publication_benchmark_validation_matrix.tex
│
├── paper2_meta_analysis_benchmark/          # Paper 2: Automated Evidence Synthesis & SLR Benchmark
│   ├── main.tex                             # Camera-ready IEEEtran LaTeX source
│   ├── main.pdf                             # Compiled 3-page manuscript
│   ├── IEEEtran.cls                         # IEEE journal formatting class
│   └── tables/                              # PRISMA screening & statistical meta-analysis tables
│       ├── tab_validation_screening_prisma.tex
│       └── tab_validation_meta_analysis.tex
│
├── paper3_eeg_noise_applied/                # Paper 3: Applied EEG Noise Treatment Science Mapping
│   ├── main.tex                             # Full 6-page IEEEtran manuscript source
│   ├── main.pdf                             # Compiled manuscript with figures & annexes
│   ├── IEEEtran.cls                         # IEEE journal formatting class
│   ├── figures/                             # High-resolution PDF/PNG visual plots
│   └── tables/                              # Annex tables, co-citation, CAGR, and temporal shifts
│
└── paper4_opensciencepipe_landmark/         # Paper 4: Unified Flagship Landmark Article (Journal of Informetrics)
    ├── main.tex                             # Full 15-page Elsevier elsarticle source
    ├── main.pdf                             # Compiled 15-page comprehensive manuscript
    ├── elsarticle.cls                       # Elsevier formatting class
    ├── elsarticle-*.bst                     # Elsevier citation style files
    └── tables/                              # Consolidated empirical benchmark validation suite
        ├── tab_publication_benchmark_validation_matrix.tex
        ├── tab_validation_thematic_clustering.tex
        ├── tab_validation_screening_prisma.tex
        └── tab_validation_meta_analysis.tex
```

---

## Paper Summaries

### 1. Paper 1: OpenSciencePipe Methodological Benchmark (Target: Journal of Informetrics)
- **Title**: *OpenSciencePipe: An End-to-End Computational Framework for Autonomous Bibliometric Science Mapping: Benchmarking Neural Thematic Modeling and GPU Graph Topologies Across 20 Multi-Domain Corpora*
- **Authors**: João Garcia Farinha, Carlos Duarte (LASIGE, Faculdade de Ciências, Universidade de Lisboa)
- **Target Venue**: *Journal of Informetrics* (Elsevier `elsarticle` format)
- **Scope**: Evaluates OpenSciencePipe's bibliometric science mapping capabilities across 20 published corpora.
- **Build**:
  ```bash
  cd manuscripts/paper1_bibliometric_benchmark
  pdflatex -interaction=nonstopmode main.tex
  ```

### 2. Paper 2: Automated Evidence Synthesis & SLR Benchmark
- **Title**: *An End-to-End Automated Pipeline for Evidence Synthesis: Validating High-Recall LLM Screening and Quantitative Meta-Analysis Extraction Across Seminal Benchmarks*
- **Scope**: Validates deterministic regex filtering and zero-shot LLM screening on the Ren et al. (2024) PRISMA review ($100\%$ recall, WSS@95 = $28.3\%$) alongside exact statistical pooling replication across 4 seminal historical datasets (Colditz et al., 1994; Smith & Glass, 1977; Nissen & Wolski, 2007; Doucouliagos & Stanley, 2009).
- **Build**:
  ```bash
  cd manuscripts/paper2_meta_analysis_benchmark
  pdflatex -interaction=nonstopmode main.tex
  ```

### 3. Paper 3: Applied EEG Noise Treatment Science Mapping
- **Title**: *Evolution of Noise Treatment Paradigms in Electroencephalography: An Automated Bibliometric Analysis*
- **Scope**: Science-mapping study of 37,738 EEG publications analyzing explicit artifact filtering, robust latent decoding, and emerging noise-as-information paradigms, complete with temporal delta shifts and co-citation analysis.
- **Build**:
  ```bash
  cd manuscripts/paper3_eeg_noise_applied
  pdflatex -interaction=nonstopmode main.tex
  ```

### 4. Paper 4: OpenSciencePipe Landmark Flagship Article (Target: Journal of Informetrics)
- **Title**: *OpenSciencePipe: An Integrated Computational Framework for Autonomous Science Mapping and Systematic Evidence Synthesis: Benchmarking Neural Thematic Topologies and Quantitative Meta-Analysis Across 20 Multi-Domain Corpora*
- **Authors**: João Garcia Farinha, Carlos Duarte (LASIGE, Faculdade de Ciências, Universidade de Lisboa)
- **Target Venue**: *Journal of Informetrics* (Elsevier `elsarticle` format)
- **Scope**: The definitive flagship manuscript unifying Paper 1 and Paper 2. Bridges exploratory science mapping and confirmatory meta-analysis into a continuous, GPU-accelerated pipeline. Empirically benchmarked across 20 published bibliometric corpora, the Ren et al. (2024) clinical trial review, and 4 gold-standard historical meta-analyses. Integrates all 4 comprehensive validation tables.
- **Build**:
  ```bash
  cd manuscripts/paper4_opensciencepipe_landmark
  pdflatex -interaction=nonstopmode main.tex
  ```
