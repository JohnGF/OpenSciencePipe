import json
from io import BytesIO
from unittest.mock import patch

import pandas as pd

from src.core.nlp import BERTopicPipeline


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._data = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyTopicModel:
    def __init__(self):
        self.labels_set = None
        self._info = pd.DataFrame([
            {"Topic": -1, "Name": "-1_outlier_noise", "Count": 5},
            {"Topic": 0, "Name": "0_eeg_bci_motor", "Count": 25},
            {"Topic": 1, "Name": "1_fmri_bold_cortex", "Count": 18},
        ])

    def get_topic_info(self):
        return self._info

    def get_topic(self, topic_id):
        if topic_id == 0:
            return [("eeg", 0.3), ("bci", 0.25), ("motor", 0.2)]
        if topic_id == 1:
            return [("fmri", 0.3), ("bold", 0.2), ("cortex", 0.15)]
        return []

    def get_representative_docs(self, topic_id):
        return [f"Representative abstract for topic {topic_id}."]

    def set_topic_labels(self, labels):
        self.labels_set = labels
        self._info["CustomName"] = self._info["Topic"].map(labels)


def test_label_topic_with_llm_disabled_returns_none():
    pipe = BERTopicPipeline(llm_model=None)
    assert pipe.label_topic_with_llm(["eeg", "bci"]) is None


def test_label_topic_with_llm_parses_ollama_json():
    pipe = BERTopicPipeline(llm_model="llama3.2:3b")
    fake_body = {"response": json.dumps({"label": "Motor Imagery EEG Interfaces"})}

    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake_body)):
        label = pipe.label_topic_with_llm(["eeg", "bci", "motor"], ["An EEG study."])

    assert label == "Motor Imagery EEG Interfaces"


def test_label_topic_with_llm_connection_error_returns_none():
    pipe = BERTopicPipeline(llm_model="llama3.2:3b", ollama_url="http://127.0.0.1:59999")
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert pipe.label_topic_with_llm(["eeg", "bci"]) is None


def test_apply_llm_topic_labels_and_get_research_lines():
    pipe = BERTopicPipeline(llm_model="llama3.2:3b")
    pipe.topic_model = _DummyTopicModel()

    responses = iter([
        _FakeResponse({"response": json.dumps({"label": "Motor Imagery BCI Systems"})}),
        OSError("timeout on topic 1"),
    ])

    def _side_effect(*args, **kwargs):
        nxt = next(responses)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    with patch("urllib.request.urlopen", side_effect=_side_effect):
        labels = pipe.apply_llm_topic_labels()

    assert labels == {
        0: "Motor Imagery BCI Systems",
        1: "1_fmri_bold_cortex",
    }
    assert -1 not in labels
    assert pipe.topic_model.labels_set == labels

    rl = pipe.get_research_lines()
    assert list(rl["topic_label"]) == ["Motor Imagery BCI Systems", "1_fmri_bold_cortex"]


def test_subcluster_oversized_topics_splits_large_cluster():
    pipe = BERTopicPipeline(llm_model="llama3.2:3b")
    pipe.topic_model = _DummyTopicModel()
    pipe.custom_labels = {0: "Biochar Soil Carbon Production", 1: "Biochar Adsorption"}

    # 45 docs in topic 0 (oversized), 10 docs in topic 1 (not oversized)
    docs = [f"Doc {i} about biochar soil" for i in range(45)] + [f"Doc {i} about fmri" for i in range(10)]
    topics = [0] * 45 + [1] * 10

    class _FakeSubModel:
        def fit_transform(self, sub_docs):
            return ([0] * 25 + [1] * 20), None

        def get_topic_info(self):
            return pd.DataFrame([
                {"Topic": 0, "Name": "0_pyrolysis_temp", "Count": 25},
                {"Topic": 1, "Name": "1_soil_carbon", "Count": 20},
            ])

        def get_topic(self, tid):
            return [("pyrolysis", 0.4), ("biochar", 0.3)] if tid == 0 else [("soil", 0.4), ("carbon", 0.3)]

        def get_representative_docs(self, tid):
            return ["Sample abstract."]

    responses = iter([
        _FakeResponse({"response": json.dumps({"label": "Pyrolysis Temperature Effects"})}),
        _FakeResponse({"response": json.dumps({"label": "Soil Carbon Sequestration"})}),
    ])

    with patch.object(pipe, "_build_bertopic", return_value=_FakeSubModel()), \
         patch("urllib.request.urlopen", side_effect=lambda *a, **kw: next(responses)):
        sub_df = pipe.subcluster_oversized_topics(docs=docs, topics=topics, min_parent_size=40, max_passes=2)

    assert len(sub_df) == 2
    assert list(sub_df["subtopic_id"]) == ["0.0", "0.1"]
    assert list(sub_df["subtopic_label"]) == ["Pyrolysis Temperature Effects", "Soil Carbon Sequestration"]
    assert list(sub_df["pass_depth"]) == [2, 2]

