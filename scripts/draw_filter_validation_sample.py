"""Draw stratified n=300 filter-validation sample (branch eeg-bci-neurorehab).

Strata (deterministic, seed=42):
  - 100 auto-keep BCI-core
  -  50 auto-keep hab-only
  -  75 auto-excluded clinical (exclude-term hit)
  -  75 auto-out-of-scope broad (no include, no exclude term)
Output: outputs/paper3_clean/data/filter_validation_sample_n300.csv
with blank annotator columns for dual independent coding.
"""
import csv
import random
import re
from pathlib import Path

SRC = Path("outputs/paper3_clean/data/publication_dataset.csv")
DST = Path("outputs/paper3_clean/data/filter_validation_sample_n300.csv")
SEED = 42

BCI_CORE = [
    r"brain[\s\-]*computer[\s\-]*interface", r"\bbci\b",
    r"motor[\s\-]*imagery", r"steady[\s\-]*state\s+visual", r"\bssvep\b",
    r"\bp300\b", r"event[\s\-]*related\s+desynch",
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


def classify(text: str) -> str:
    b, h, e = bool(bci_re.search(text)), bool(hab_re.search(text)), bool(exc_re.search(text))
    if b:
        return "keep_bci_core"
    if h and not e:
        return "keep_hab_only"
    if e:
        return "excluded_clinical"
    if h and e:
        return "excluded_clinical"
    return "out_of_scope_broad"


quotas = {"keep_bci_core": 100, "keep_hab_only": 50, "excluded_clinical": 75, "out_of_scope_broad": 75}


def main() -> None:
    rng = random.Random(SEED)
    pools: dict[str, list[dict]] = {k: [] for k in quotas}
    with SRC.open(newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            text = " ".join([row.get("Title", ""), row.get("Abstract", ""), row.get("Author Keywords", "")])
            pools[classify(text)].append((i, row))
    for k, v in pools.items():
        print(f"pool {k}: {len(v)} (quota {quotas[k]})")
        assert len(v) >= quotas[k], f"pool {k} too small"
    sample = []
    for k, q in quotas.items():
        sample.extend([(k, i, r) for i, r in rng.sample(pools[k], q)])
    rng.shuffle(sample)
    with DST.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "auto_arm", "Year", "Title", "Abstract",
                    "Author_Keywords", "DOI", "annotator1_include_0_1",
                    "annotator2_include_0_1", "notes"])
        for sid, (arm, _, r) in enumerate(sample, 1):
            w.writerow([sid, arm, r.get("Year", ""), r.get("Title", ""),
                        r.get("Abstract", "")[:2000], r.get("Author Keywords", "")[:500],
                        r.get("DOI", ""), "", "", ""])
    print(f"wrote {DST} n={len(sample)} seed={SEED}")


if __name__ == "__main__":
    main()
