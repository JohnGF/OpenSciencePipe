#!/usr/bin/env python3
"""
OpenSciencePipe: Interactive API Keys Onboarding Wizard & Credential Manager.

Usage:
    python scripts/setup_keys.py            # Interactive step-by-step onboarding
    python scripts/setup_keys.py --check    # Diagnose and validate current credentials
    python scripts/setup_keys.py --init     # Create .env from template if missing
    python scripts/setup_keys.py --email me@univ.edu  # Quick non-interactive email setup
"""

import os
import sys
import shutil
import argparse
from typing import Dict

# Ensure repository root is on Python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.validate_keys import load_env, validate_all_keys

ENV_FILE = os.path.join(REPO_ROOT, ".env")
ENV_EXAMPLE = os.path.join(REPO_ROOT, ".env.example")

def mask_val(v: str) -> str:
    if not v:
        return "(empty)"
    if "@" in v:
        user, domain = v.split("@", 1)
        return f"{user[:2]}***@{domain}"
    if len(v) > 8:
        return f"{v[:4]}...{v[-4:]}"
    return f"{v[:2]}***"

def prompt_var(name: str, description: str, current_val: str, default: str = "") -> str:
    print(f"\n--- {name} ---")
    print(description)
    display_curr = mask_val(current_val)
    prompt_msg = f"Enter value [{display_curr}]: "
    try:
        user_input = input(prompt_msg).strip()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        sys.exit(1)

    if not user_input:
        return current_val if current_val else default
    return user_input

def save_env_file(config: Dict[str, str]):
    if os.path.exists(ENV_FILE):
        backup_path = f"{ENV_FILE}.bak"
        shutil.copy2(ENV_FILE, backup_path)
        print(f"\nBacked up existing .env to {backup_path}")

    # Read template structure if available to maintain comments
    template_lines = []
    if os.path.exists(ENV_EXAMPLE):
        with open(ENV_EXAMPLE, "r", encoding="utf-8") as f:
            template_lines = f.readlines()

    written_keys = set()
    output_lines = []

    if template_lines:
        for line in template_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in config:
                    output_lines.append(f'{k}="{config[k]}"\n')
                    written_keys.add(k)
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)
    else:
        for k, v in config.items():
            output_lines.append(f'{k}="{v}"\n')
            written_keys.add(k)

    # Append any remaining keys not present in template
    for k, v in config.items():
        if k not in written_keys and v:
            output_lines.append(f'{k}="{v}"\n')

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

    print(f"Successfully updated configuration at {ENV_FILE}")

def run_interactive_wizard():
    print("=" * 70)
    print("   OpenSciencePipe: Interactive API Keys Onboarding Wizard   ")
    print("=" * 70)
    print("OpenSciencePipe connects to multiple open and commercial scholarly indexes.")
    print("To run at maximum speed, you only need to provide an email for the free")
    print("polite pool (OpenAlex / Crossref). Commercial keys are completely optional.\n")

    current_config = load_env(ENV_FILE)
    new_config = dict(current_config)

    # 1. Contact email for polite pools
    curr_email = current_config.get("OPENALEX_EMAIL", "")
    email = prompt_var(
        name="Polite Pool Contact Email (HIGHLY RECOMMENDED)",
        description=(
            "Used in User-Agent headers for OpenAlex and Crossref.\n"
            "Completely free, no registration required, unlocks 10 req/s polite throughput."
        ),
        current_val=curr_email,
        default="user@example.com"
    )
    new_config["OPENALEX_EMAIL"] = email
    new_config["CROSSREF_EMAIL"] = email

    # 2. Semantic Scholar API Key
    curr_ss = current_config.get("SS_API_KEY", "")
    ss_key = prompt_var(
        name="Semantic Scholar API Key (OPTIONAL)",
        description=(
            "Free API key grants dedicated rate limits (up to 100 req/min).\n"
            "Request free key: https://www.semanticscholar.org/product/api#api-key-form\n"
            "Press Enter to keep current or skip."
        ),
        current_val=curr_ss
    )
    new_config["SS_API_KEY"] = ss_key

    # 3. PubMed / NCBI Key
    curr_pm = current_config.get("PUBMED_API_KEY", "")
    pm_key = prompt_var(
        name="NCBI PubMed API Key (OPTIONAL)",
        description=(
            "Free NCBI key increases rate limit from 3 req/s to 10 req/s.\n"
            "Request free key: https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/\n"
            "Press Enter to keep current or skip."
        ),
        current_val=curr_pm
    )
    new_config["PUBMED_API_KEY"] = pm_key

    # 4. Elsevier Scopus
    curr_scopus = current_config.get("SCOPUS_API_KEY", "")
    scopus_key = prompt_var(
        name="Elsevier Scopus API Key (OPTIONAL / INSTITUTIONAL)",
        description=(
            "Requires university library subscription and developer portal key.\n"
            "Portal: https://dev.elsevier.com/\n"
            "Press Enter to keep current or skip."
        ),
        current_val=curr_scopus
    )
    new_config["SCOPUS_API_KEY"] = scopus_key

    if scopus_key:
        curr_token = current_config.get("SCOPUS_INST_TOKEN", "")
        token = prompt_var(
            name="Elsevier Institutional Token (OPTIONAL)",
            description="Used alongside Scopus key for off-campus/remote institutional validation.",
            current_val=curr_token
        )
        new_config["SCOPUS_INST_TOKEN"] = token

    # 5. Clarivate Web of Science
    curr_wos = current_config.get("WOS_API_KEY", "")
    wos_key = prompt_var(
        name="Clarivate Web of Science API Key (OPTIONAL / INSTITUTIONAL)",
        description=(
            "Requires Clarivate institutional subscription and developer portal account.\n"
            "Portal: https://developer.clarivate.com/\n"
            "Press Enter to keep current or skip."
        ),
        current_val=curr_wos
    )
    new_config["WOS_API_KEY"] = wos_key

    # 6. IEEE Xplore
    curr_ieee = current_config.get("IEEE_API_KEY", "")
    ieee_key = prompt_var(
        name="IEEE Xplore API Key (OPTIONAL)",
        description=(
            "Direct IEEE API key. (Note: IEEE papers are already indexed via OpenAlex).\n"
            "Press Enter to keep current or skip."
        ),
        current_val=curr_ieee
    )
    new_config["IEEE_API_KEY"] = ieee_key

    # Save to .env
    save_env_file(new_config)

    print("\nRunning live connection tests...")
    validate_all_keys(verbose=True)

def init_env():
    if os.path.exists(ENV_FILE):
        print(f"Configuration file {ENV_FILE} already exists. Skipping init.")
        return
    if os.path.exists(ENV_EXAMPLE):
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
        print(f"Created {ENV_FILE} from {ENV_EXAMPLE}.")
        print("Run 'python scripts/setup_keys.py' to configure credentials interactively.")
    else:
        print(f"Error: {ENV_EXAMPLE} not found.")

def set_email_quick(email: str):
    config = load_env(ENV_FILE)
    config["OPENALEX_EMAIL"] = email
    config["CROSSREF_EMAIL"] = email
    save_env_file(config)
    print(f"Configured polite pool email: {email}")
    validate_all_keys(verbose=True)

def main():
    parser = argparse.ArgumentParser(
        description="OpenSciencePipe: API Keys Onboarding & Diagnostics Wizard",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="Validate current credentials against live endpoints")
    parser.add_argument("--init", action="store_true", help="Initialize .env from .env.example if missing")
    parser.add_argument("--email", type=str, help="Quickly set contact email for OpenAlex/Crossref polite pools")
    args = parser.parse_args()

    if args.check:
        success, _ = validate_all_keys(verbose=True)
        sys.exit(0 if success else 1)
    elif args.init:
        init_env()
    elif args.email:
        set_email_quick(args.email)
    else:
        run_interactive_wizard()

if __name__ == "__main__":
    main()
