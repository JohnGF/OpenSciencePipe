"""Paradigm shares on the BCI-neurorehab subset (branch eeg-bci-neurorehab).

Implements the manuscript's 3-paradigm taxonomy as ORDERED rules
(first hit wins — precedence documented because broad P1 terms
like 'filtering'/'denois' shadow DL papers and inflate Paradigm 1;
see exporter method_application_exporter.py for the same effect).
"""
import pandas as pd

SRC = "outputs/paper3_clean/data/publication_dataset_bci_neurorehab.csv"

P1 = ["ica", "wavelet", "artifact removal", "filtering", "suppression",
      "denois", "blind source separation", "bss", "iclabel"]
P2 = ["deep learning", "cnn", "convolutional", "transformer",
      "neural network", "eegnet", "deepconvnet", "gan ", "diffusion",
      "end-to-end", "latent"]
P3 = ["aperiodic", "1/f", "specparam", "fooof", "irasa", "scale-free",
      "excitation", "e/i balance", "pink noise"]


def paradigm(text: str) -> str:
    if any(w in text for w in P1):
        return "P1_explicit_filtering"
    if any(w in text for w in P2):
        return "P2_latent_decoding"
    if any(w in text for w in P3):
        return "P3_noise_as_information"
    return "unclassified_general"


def main() -> None:
    df = pd.read_csv(SRC, usecols=["Title", "Abstract"])
    text = (df["Title"].fillna("") + " " + df["Abstract"].fillna("")).str.lower()
    labels = text.map(paradigm)
    n = len(labels)
    print(f"n={n} (exclusive, first-hit)")
    for k, c in labels.value_counts().items():
        print(f"{k}: {c} ({c / n:.1%})")
    print("any-mention (same term lists, no precedence):")
    for name, terms in [("P1", P1), ("P2", P2), ("P3", P3)]:
        m = text.apply(lambda x, ts=terms: any(w in x for w in ts))
        print(f"{name}: {m.sum()} ({m.mean():.2%})")


if __name__ == "__main__":
    main()
