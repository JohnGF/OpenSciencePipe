#!/usr/bin/env python3
"""
Validated coverage audit built from cached audit data (no network calls).

Applies a strict FCUL affiliation validator to the candidate "OpenAlex misses"
produced by scripts/audit_fcul_coverage.py and reports how many survive.

Validator rules (a paper counts as FCUL only if):
  ACCEPT  - contains "faculdade de ci" + "universidade de lisboa" / "university of lisbon"
            as the same institution, OR
          - contains a distinctive FCUL institute token
            (LASIGE, Instituto Dom Luiz, Ce3C, BioISI, CFTC, CQE, LIP, IA)
  REJECT  - "nova", "iscte", "fct", "faculdade de ciencias medicas", "medicas",
            "universidade catolica", "universidade do porto", "coimbra", "algarve", etc.
  Ambiguous entries are reported separately rather than silently counted.

Usage:
    python scripts/validate_fcul_audit.py --audit-dir /tmp/opencode/fcul_audit_probe
"""

import argparse
import csv
import os
import re
from collections import Counter, defaultdict

# Distinctive FCUL-linked institute tokens
INSTITUTE_TOKENS = [
    "lasige",
    "instituto dom luiz",
    "ce3c",
    "c3ec",
    "bioisi",
    "centro de fisica teorica",
    "centro de física teórica",
    "cftc",
    "centro de quimica estrutural",
    "centro de química estrutural",
    "cqe",
    "inferior de particulas lip",
    "instrumentacao e fisica experimental",
    "instrumentação e física experimental",
    "instituto de astrofisica",
    "instituto de astrofísica",
    "ia - instituto de astrofisica",
]

# Phrases that mean Faculdade de Ciencias of Lisbon specifically
FCUL_PHRASES = [
    "faculdade de ciências da universidade de lisboa",
    "faculdade de ciencias da universidade de lisboa",
    "faculdade de ciências, universidade de lisboa",
    "faculdade de ciencias, universidade de lisboa",
    "faculdade de ciências da ul",
    "faculdade de ciencias da ul",
    "faculty of sciences of the university of lisbon",
    "faculty of sciences, university of lisbon",
    "faculty of sciences university of lisbon",
    "faculdade de ciências de lisboa",
    "faculdade de ciencias de lisboa",
    "fcul",
]

# Institutions that are NOT FCUL, even though they contain "Lisboa" or "Faculdade de Ciencias"
NEGATIVE_TOKENS = [
    "nova de lisboa",
    "universidade nova",
    "iscte",
    "faculdade de ciencias e tecnologia",
    "faculdade de ciências e tecnologia",
    "fct-unl",
    "faculdade de ciencias medicas",
    "faculdade de ciências médicas",
    "nms ",
    "nova medical school",
    "universidade catolica",
    "universidade católica",
    "universidade do porto",
    "universidade de coimbra",
    "universidade de aveiro",
    "universidade do minho",
    "universidade do algarve",
    "universidade da beira interior",
    "politecnico",
    "politécnico",
    "instituto superior tecnico",
    "instituto superior técnico",
    "instituto superior de agronomia",
    "faculdade de medicina da universidade de lisboa",
    "faculdade de farmacia",
    "faculdade de farmácia",
    "faculdade de letras",
    "faculdade de direito",
    "faculdade de belas artes",
    "faculdade de psicologia",
    "faculdade de motricidade",
    "faculdade de arquitetura",
]


def classify(affil: str, title: str):
    """Return (verdict, reason). verdict in {accept, reject, ambiguous}."""
    blob = f"{affil} {title}".lower()
    if not blob.strip():
        return "ambiguous", "no affiliation text"

    negatives = [t for t in NEGATIVE_TOKENS if t in blob]
    phrases = [t for t in FCUL_PHRASES if t in blob]
    institutes = [t for t in INSTITUTE_TOKENS if t in blob]

    # A negative institution alone is decisive, unless a distinctive FCUL institute also appears
    if negatives and not institutes:
        return "reject", f"non-FCUL institution: {negatives[0]}"

    if institutes:
        return "accept", f"FCUL institute: {institutes[0]}"

    if phrases:
        return "accept", f"FCUL affiliation phrase: {phrases[0]}"

    # "faculdade de ciencias" + lisbon, without a negative marker
    if "faculdade de ci" in blob and ("lisboa" in blob or "lisbon" in blob):
        return "ambiguous", "faculdade de ciencias + lisbon, no institute token"

    return "ambiguous", "no FCUL signal"


def main(audit_dir, out_dir):
    misses_csv = os.path.join(audit_dir, "openalex_candidate_misses.csv")
    summary_csv = os.path.join(audit_dir, "coverage_summary.csv")
    if not os.path.exists(misses_csv):
        raise SystemExit(f"missing {misses_csv} - run scripts/audit_fcul_coverage.py first")

    os.makedirs(out_dir, exist_ok=True)
    rows = list(csv.DictReader(open(misses_csv, encoding="utf-8")))

    accepted, rejected, ambiguous = [], [], []
    for r in rows:
        verdict, reason = classify(r.get("Affiliations", ""), r.get("Title", ""))
        r["verdict"] = verdict
        r["reason"] = reason
        {"accept": accepted, "reject": rejected, "ambiguous": ambiguous}[verdict].append(r)

    by_source_total = Counter(r["Found_In"] for r in rows)
    by_source_accept = Counter(r["Found_In"] for r in accepted)
    by_year_accept = Counter(r["Year"] for r in accepted)

    out_rows = os.path.join(out_dir, "validated_openalex_misses.csv")
    with open(out_rows, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["DOI", "Year", "Title", "Found_In", "verdict", "reason", "Affiliations"])
        w.writeheader()
        for r in accepted + ambiguous + rejected:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    print("=== VALIDATED COVERAGE AUDIT (cached data) ===")
    print(f"Raw candidates: {len(rows)}")
    print(f"  accepted (real FCUL):   {len(accepted)}")
    print(f"  ambiguous (needs eyes): {len(ambiguous)}")
    print(f"  rejected (not FCUL):    {len(rejected)}")
    print()
    print(f"{'Source':<12}{'candidates':>12}{'accepted':>10}{'ambig':>8}{'rejected':>10}")
    print("-" * 52)
    amb_by_src = Counter(r["Found_In"] for r in ambiguous)
    rej_by_src = Counter(r["Found_In"] for r in rejected)
    for src in sorted(by_source_total):
        print(f"{src:<12}{by_source_total[src]:>12}{by_source_accept.get(src, 0):>10}"
              f"{amb_by_src.get(src, 0):>8}{rej_by_src.get(src, 0):>10}")
    print()
    if by_year_accept:
        print("Accepted misses by year:", dict(sorted(by_year_accept.items())))
    print()
    print("Accepted examples:")
    for r in accepted[:10]:
        print(f"  [{r['Found_In']}] {r['Year']} {r['Title'][:70]}")
        print(f"      {r['reason']}")

    print(f"\nWrote {out_rows}")
    return accepted, ambiguous, rejected


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate cached FCUL coverage-audit candidates")
    ap.add_argument("--audit-dir", default="/tmp/opencode/fcul_audit_probe")
    ap.add_argument("--out", default=os.path.join("outputs", "fcul_coverage_audit", "validated"))
    args = ap.parse_args()
    main(args.audit_dir, args.out)
