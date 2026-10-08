"""Filter frozen broad EEG corpus to BCI-neurorehab subset (branch eeg-bci-neurorehab).

Input : outputs/paper3_clean/data/publication_dataset.csv (frozen by tag eeg-broad-57k-v2)
Output: outputs/paper3_clean/data/publication_dataset_bci_neurorehab.csv + PRISMA counts to stdout
Rule  : include on BCI core OR neurorehab context; clinical exclusions override
        UNLESS a BCI-core term is also present (BCI priority).
"""
import csv
import re
import sys
from pathlib import Path

SRC = Path("outputs/paper3_clean/data/publication_dataset.csv")
DST = Path("outputs/paper3_clean/data/publication_dataset_bci_neurorehab.csv")

BCI_CORE = [
    r"brain[\s\-]*computer[\s\-]*interface", r"\bbci\b",
    r"motor[\s\-]*imagery", r"steady[\s\-]*state\s+visual", r"\bssvep\b",
    r"\bp300\b", r"event[\s\-]*related\s+desynch", r"\berd\b.?\/?\s*.?\bers\b",
    r"common\s+spatial", r"\bcsp\b",
    r"neuroprosthes", r"neurofeedback",
    r"closed[\s\-]*loop.*\beeg\b", r"\beeg\b.*closed[\s\-]*loop",
]
NEUROHAB = [
    r"neurorehab", r"\bstroke\b", r"hemipares", r"spinal\s*cord\s*injur",
    r"amyotrophic", r"\bals\b", r"prosthes", r"exoskelet",
    r"motor\s+recover", r"upper[\s\-]*limb\s+rehab", r"gait\s+rehab",
]
EXCLUDE = [
    r"epilep", r"seizure", r"\bsleep\b", r"insomnia", r"polysomnograph",
    r"autism", r"\basd\b", r"schizophrenia", r"psychosis",
    r"alzheimer", r"dementia", r"neonatal", r"anesthesia",
]

bci_re = re.compile("|".join(f"(?:{p})" for p in BCI_CORE), re.I)
hab_re = re.compile("|".join(f"(?:{p})" for p in NEUROHAB), re.I)
exc_re = re.compile("|".join(f"(?:{p})" for p in EXCLUDE), re.I)


def main() -> None:
    assert SRC.exists(), f"missing {SRC} — run from repo root"
    n_in = n_bci = n_hab_only = n_excluded = 0
    with SRC.open(newline="", encoding="utf-8") as fin, DST.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        rdr = csv.DictReader(fin)
        w = csv.DictWriter(fout, fieldnames=rdr.fieldnames)
        w.writeheader()
        for row in rdr:
            n_in += 1
            text = " ".join(
                [
                    row.get("Title", ""),
                    row.get("Abstract", ""),
                    row.get("Author Keywords", ""),
                ]
            )
            has_bci = bool(bci_re.search(text))
            has_hab = bool(hab_re.search(text))
            has_exc = bool(exc_re.search(text))
            if has_bci:
                n_bci += 1
                w.writerow(row)
            elif has_hab and not has_exc:
                n_hab_only += 1
                w.writerow(row)
            elif has_hab and has_exc:
                n_excluded += 1
            elif has_exc:
                n_excluded += 1
            # else: broad non-BCI, non-hab → out of scope, counted implicitly
    n_out = n_bci + n_hab_only
    print(f"input={n_in} bci_core={n_bci} hab_only={n_hab_only} "
          f"kept={n_out} share={n_out / n_in:.1%} excluded_clinical={n_excluded}")
    print(f"wrote {DST}")


if __name__ == "__main__":
    sys.exit(main())
