import pandas as pd
import pytest
from src.core.screening import ActiveLearningPriorityRanker, PaperScreener

def test_active_learning_priority_ranking():
    ranker = ActiveLearningPriorityRanker()
    df = pd.DataFrame({
        "Title": [
            "Randomized controlled trial of cognitive therapy for major depression",
            "Survey of deep reinforcement learning methods for robotics",
            "Efficacy of antidepressant medication vs psychological interventions"
        ],
        "Abstract": [
            "We conducted a clinical trial with 200 patients evaluating cognitive outcomes.",
            "This paper provides an overview of robot manipulation algorithms.",
            "Meta-analytic evaluation of clinical recovery rates in adult patients."
        ]
    })

    seed_included = ["Clinical trial of therapy and patient depression treatment outcomes"]
    seed_excluded = ["Robot manipulation reinforcement learning hardware robotics"]

    ranked_df = ranker.rank_priority(df, seed_included_texts=seed_included, seed_excluded_texts=seed_excluded)
    
    assert "screening_priority_score" in ranked_df.columns
    assert "screening_priority_rank" in ranked_df.columns
    assert len(ranked_df) == 3
    # First ranked study should be relevant to clinical depression/therapy, not robotics
    top_title = ranked_df.iloc[0]["Title"]
    assert "depression" in top_title.lower() or "antidepressant" in top_title.lower()

def test_paper_screener_prioritization():
    screener = PaperScreener()
    df = pd.DataFrame({
        "Title": ["Study A", "Study B"],
        "Abstract": ["Randomized controlled trial clinical outcome", "Random noise unrelated text"]
    })
    res_df = screener.prioritize_for_human_screening(df)
    assert len(res_df) == 2
    assert "screening_priority_rank" in res_df.columns
