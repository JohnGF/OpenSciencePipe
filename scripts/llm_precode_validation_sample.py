"""LLM pre-code of the n=300 filter-validation sample (branch eeg-bci-neurorehab).

Model: local Qwen2.5-7B-Instruct GGUF Q4_K_M via llama-cpp-python, greedy (temp=0).
Fills annotator1_include_0_1 + model_notes; human adjudicates as annotator-2.
Usage: .venv/bin/python scripts/llm_precode_validation_sample.py
"""
import csv
import glob
from pathlib import Path

SRC = Path("outputs/paper3_clean/data/filter_validation_sample_n300.csv")
MODEL_GLOB = (
    "models--Qwen--Qwen2.5-7B-Instruct-GGUF/snapshots/*/qwen2.5-7b-instruct-q4_k_m-*.gguf"
)

SYSTEM = (
    "You classify EEG publications for a bibliometric mapping study on "
    "BCI neurorehabilitation. Reply with exactly one character: 1 or 0."
)
USER_TMPL = """Mark 1 (KEEP) if the paper deals with EEG-based brain-computer interfaces or neurorehabilitation with a noise/artifact/decoding component: motor imagery, SSVEP/P300, neurofeedback, stroke/SCI/ALS rehabilitation, prosthetics, exoskeletons, closed-loop or mobile/dry-electrode BCI.

Mark 0 (OUT) if it is purely clinical without BCI link: epilepsy/seizure detection, sleep staging, autism, schizophrenia, Alzheimer/dementia, neonatal, anesthesia.

Title: {title}
Abstract: {abstract}
Keywords: {keywords}

Reply with exactly one character: 1 or 0."""


def main() -> None:
    from llama_cpp import Llama

    shards = sorted(
        glob.glob(str(Path.home() / ".cache/huggingface/hub" / MODEL_GLOB))
    )
    assert len(shards) == 2, f"expected 2 GGUF shards, found {shards}"
    # llama.cpp loads split GGUF via the first shard
    llm = Llama(model_path=shards[0], n_ctx=4096, verbose=False)

    rows = list(csv.DictReader(SRC.open(newline="", encoding="utf-8")))
    coded = sum(1 for r in rows if r.get("annotator1_include_0_1", "").strip() != "")
    print(f"resuming: {coded}/{len(rows)} already coded")
    for r in rows:
        if r.get("annotator1_include_0_1", "").strip() != "":
            continue
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": USER_TMPL.format(
                    title=r.get("Title", "")[:300],
                    abstract=r.get("Abstract", "")[:1500],
                    keywords=r.get("Author_Keywords", "")[:300])},
            ],
            temperature=0.0,
            max_tokens=4,
        )
        txt = out["choices"][0]["message"]["content"].strip()
        digit = next((c for c in txt if c in "01"), "")
        r["annotator1_include_0_1"] = digit
        r["notes"] = f"llm_raw={txt[:20]!r} model=qwen2.5-7b-q4_k_m greedy"
        with SRC.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"sample {r['sample_id']} auto={r['auto_arm']} llm={digit or '?'}")
    print("done — human adjudication next (annotator2 column)")


if __name__ == "__main__":
    main()
