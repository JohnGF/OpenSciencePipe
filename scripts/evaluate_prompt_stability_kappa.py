import os
import sys
import json
import argparse
import pandas as pd
import numpy as np
from typing import List, Dict

# Fleiss' Kappa implementation for inter-rater agreement across multiple runs
def fleiss_kappa(ratings_matrix: np.ndarray) -> float:
    """
    Computes Fleiss' Kappa for a matrix of shape (N, k),
    where N is the number of subjects, and each row contains the category assigned by k raters (or runs).
    Categories are 0 (Exclude) and 1 (Include).
    """
    N, k = ratings_matrix.shape
    if N == 0 or k <= 1:
        return 1.0

    # Count of ratings in each category for each subject: shape (N, num_categories)
    # Categories: 0 and 1
    p_matrix = np.zeros((N, 2))
    for i in range(N):
        p_matrix[i, 0] = np.sum(ratings_matrix[i, :] == 0)
        p_matrix[i, 1] = np.sum(ratings_matrix[i, :] == 1)

    # P_i: extent to which raters agree for subject i
    # P_i = (1 / (k*(k-1))) * (sum(n_ij^2) - k)
    P_i = (np.sum(p_matrix ** 2, axis=1) - k) / (k * (k - 1))
    P_bar = np.mean(P_i)

    # p_j: proportion of all assignments to category j
    p_j = np.sum(p_matrix, axis=0) / (N * k)
    P_bar_e = np.sum(p_j ** 2)

    if 1.0 - P_bar_e == 0:
        return 1.0

    kappa = (P_bar - P_bar_e) / (1.0 - P_bar_e)
    return float(kappa)


def run_stability_benchmark(
    input_csv: str,
    topic_context: str = "brain-computer interface stroke rehabilitation",
    sample_size: int = 200,
    runs: int = 3,
    model: str = "llama3.2:3b",
    ollama_url: str = "http://localhost:11434"
):
    print("=" * 80)
    print(f">>> RUNNING PROMPT STABILITY TEST-RETEST EVALUATION")
    print(f"    Target Dataset:  {input_csv}")
    print(f"    Sample Size:     {sample_size}")
    print(f"    Runs:            {runs} (at Temperature = 0.0)")
    print(f"    Model:           {model}")
    print("=" * 80)

    if not os.path.exists(input_csv):
        print(f"Error: file {input_csv} not found.")
        sys.exit(1)

    df = pd.read_csv(input_csv)
    title_col = next((c for c in ["Title", "title"] if c in df.columns), None)
    abstract_col = next((c for c in ["Abstract", "abstract"] if c in df.columns), None)

    if not title_col or not abstract_col:
        print("Error: Dataset must contain Title and Abstract columns.")
        sys.exit(1)

    # Stratified or random sample
    if len(df) > sample_size:
        eval_df = df.sample(n=sample_size, random_state=42).copy().reset_index(drop=True)
    else:
        eval_df = df.copy().reset_index(drop=True)

    actual_n = len(eval_df)
    print(f">>> Sampled {actual_n} papers for test-retest.")

    from src.core.screening import LLMRelevanceClassifier
    classifier = LLMRelevanceClassifier(ollama_url=ollama_url, model=model, topic_context=topic_context)

    all_runs = []
    for r in range(1, runs + 1):
        print(f"\n>>> Executing Pass {r}/{runs} (Temperature=0.0)...")
        run_decisions = []
        for i, row in eval_df.iterrows():
            t = str(row[title_col])
            a = str(row[abstract_col]) if not pd.isna(row[abstract_col]) else ""
            res = classifier.classify_paper(t, a, temperature=0.0)
            decision = 1 if res.get("is_relevant", True) else 0
            run_decisions.append(decision)
            if (i + 1) % 50 == 0 or (i + 1) == actual_n:
                print(f"    Progress: {i + 1}/{actual_n} screened...")
        all_runs.append(run_decisions)

    # Matrix of shape (N, runs)
    ratings_matrix = np.array(all_runs).T
    kappa = fleiss_kappa(ratings_matrix)

    # Pairwise agreement
    agreements = []
    for i in range(runs):
        for j in range(i + 1, runs):
            agree = np.mean(ratings_matrix[:, i] == ratings_matrix[:, j]) * 100.0
            agreements.append(agree)
    avg_pairwise = np.mean(agreements) if agreements else 100.0

    print("\n" + "=" * 80)
    print(">>> [RESULTS] PROMPT STABILITY (TEST-RETEST)")
    print(f"    - Sample Size (N):               {actual_n}")
    print(f"    - Independent Passes (T=0):      {runs}")
    print(f"    - Mean Pairwise Agreement:       {avg_pairwise:.2f}%")
    print(f"    - Fleiss' Kappa (Reliability):   {kappa:.4f}")
    
    if kappa >= 0.81:
        interp = "Almost Perfect Agreement"
    elif kappa >= 0.61:
        interp = "Substantial Agreement"
    elif kappa >= 0.41:
        interp = "Moderate Agreement"
    else:
        interp = "Fair/Slight Agreement"
    print(f"    - Landis & Koch Interpretation:  {interp}")
    print("=" * 80)

    out_file = "tables/prompt_stability_results.json"
    os.makedirs("tables", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "dataset": input_csv,
            "sample_size": actual_n,
            "runs": runs,
            "mean_pairwise_agreement_pct": round(avg_pairwise, 2),
            "fleiss_kappa": round(kappa, 4),
            "interpretation": interp
        }, f, indent=2)
    print(f">>> Results logged to: {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/collected_bci_stroke_ren2024_benchmark.csv")
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default="llama3.2:3b")
    args = parser.parse_args()

    run_stability_benchmark(
        input_csv=args.file,
        sample_size=args.sample_size,
        runs=args.runs,
        model=args.model
    )
