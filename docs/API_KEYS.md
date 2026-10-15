# OpenSciencePipe: API Credentials & Data Provider Guide

This document outlines how OpenSciencePipe connects to scholarly databases, how to configure credentials, and how to troubleshoot connectivity.

---

## 1. Quick Start: 30-Second Guided Setup

OpenSciencePipe provides an interactive onboarding wizard:

```bash
# Interactive setup wizard (prompts for email and optional keys)
python scripts/setup_keys.py

# Or via the pipeline CLI
biblio-pipeline --setup-keys
```

To diagnose and test your configured credentials against live endpoints at any time:

```bash
python scripts/setup_keys.py --check
# or
biblio-pipeline --check-keys
```

---

## 2. Supported Scholarly Databases Overview

| Provider | Access Model | Rate Limits | Required Config | Signup / Request Link |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAlex** | Open & Free | 10 req/s (polite) | `OPENALEX_EMAIL` | No signup needed. Use any valid contact email. |
| **Crossref** | Open & Free | 50 req/s (polite) | `CROSSREF_EMAIL` | No signup needed. Use any valid contact email. |
| **PubMed (NCBI)** | Open & Free | 3 req/s (public)<br>10 req/s (key) | `PUBMED_API_KEY` | [NCBI API Key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) |
| **Semantic Scholar** | Open & Free | Shared (public)<br>100 req/min (key) | `SS_API_KEY` | [Semantic Scholar API](https://www.semanticscholar.org/product/api#api-key-form) |
| **arXiv** | Open & Free | 3 req/s | None | Public API (no credentials needed). |
| **bioRxiv** | Open & Free | 3 req/s | `OPENALEX_EMAIL` | Public REST API. |
| **Elsevier Scopus** | Commercial / Institutional | 20,000 req/week | `SCOPUS_API_KEY`<br>`SCOPUS_INST_TOKEN` | [Elsevier Developer Portal](https://dev.elsevier.com/) |
| **Clarivate Web of Science** | Commercial / Institutional | Tiered | `WOS_API_KEY` | [Clarivate Developer Portal](https://developer.clarivate.com/) |
| **IEEE Xplore** | Commercial / Institutional | Tiered | `IEEE_API_KEY` | [IEEE Developer Portal](https://developer.ieee.org/) |
| **Springer Nature** | Commercial / Developer | Tiered | `SPRINGER_API_KEY` | [Springer Nature Developer](https://dev.springernature.com/) |

---

## 3. Configuration File (`.env`)

Credentials are read from `.env` in the repository root. You can generate `.env` automatically from the template:

```bash
cp .env.example .env
```

### Template Example (`.env`):

```bash
# Contact email for OpenAlex & Crossref polite pools (RECOMMENDED)
OPENALEX_EMAIL="researcher@university.edu"
CROSSREF_EMAIL="researcher@university.edu"

# Optional free API keys
PUBMED_API_KEY=""
SS_API_KEY=""

# Optional institutional keys (leave empty if not subscribed)
SCOPUS_API_KEY=""
SCOPUS_INST_TOKEN=""
WOS_API_KEY=""
IEEE_API_KEY=""
SPRINGER_API_KEY=""
```

---

## 4. How to Obtain API Keys

### OpenAlex & Crossref (Recommended, 100% Free)
- OpenAlex and Crossref do **not** require API keys or developer accounts.
- By sending a valid email address in the request header, OpenAlex and Crossref route your requests into their dedicated "polite pools," unlocking significantly higher speed and reliability.
- Set `OPENALEX_EMAIL="your_email@domain.com"` in `.env`.

### Semantic Scholar
1. Go to the [Semantic Scholar API Key Form](https://www.semanticscholar.org/product/api#api-key-form).
2. Fill in your project information (academic research, bibliometric study).
3. Once approved, copy your API key and set `SS_API_KEY="..."` in `.env`.

### NCBI PubMed (E-Utilities)
1. Sign in to your [NCBI Account](https://www.ncbi.nlm.nih.gov/account/).
2. Navigate to **Account Settings** -> **API Key Management**.
3. Click **Create an API key** and copy the string.
4. Set `PUBMED_API_KEY="..."` in `.env`.

### Elsevier Scopus (Institutional)
1. Register on the [Elsevier Developer Portal](https://dev.elsevier.com/) using your university email address.
2. Under **My API Keys**, click **Create API Key**.
3. Set your organization name and the redirect URL (e.g., `http://localhost`).
4. Set `SCOPUS_API_KEY="..."`. If connecting from outside your university network or VPN, request an Institutional Token (`SCOPUS_INST_TOKEN`) from your campus librarian.

### Clarivate Web of Science (Institutional)
1. Register on the [Clarivate Developer Portal](https://developer.clarivate.com/).
2. Submit an application for the **Web of Science Starter API** or **Expanded API**.
3. Set `WOS_API_KEY="..."`.

---

## 5. Security Best Practices

- **Never Commit Credentials:** `.env` is listed in `.gitignore`. Never commit or publish `.env` files to git repositories.
- **Environment Fallbacks:** OpenSciencePipe automatically falls back to system environment variables (e.g. in containerized CI environments, `export OPENALEX_EMAIL=...`).
- **RAM Security on Linux:** If using credential managers, credentials can be loaded directly from memory via `/run/user/1000/credentials/api_keys.env` without touching disk storage.
- **Revocation:** If an API key is accidentally exposed, immediately revoke and regenerate it via the respective provider developer console.

---

## 6. Troubleshooting Common Errors

### HTTP 401 Unauthorized
- **Cause:** The provided API key is invalid, expired, or improperly formatted.
- **Fix:** Verify key string in `.env` with no extra spaces or quotes. Run `python scripts/setup_keys.py --check`.

### HTTP 403 Forbidden (Scopus / Web of Science)
- **Cause:** Your institution does not have an active subscription to the API endpoint, or you are connecting from an unapproved IP range (off-campus without university VPN).
- **Fix:** Connect via your university VPN or add your `SCOPUS_INST_TOKEN`. If unavailable, leave the commercial keys blank; OpenSciencePipe will seamlessly harvest from OpenAlex, Crossref, and PubMed.

### HTTP 429 Too Many Requests
- **Cause:** The public rate limit was exceeded.
- **Fix:** Set a polite email in `OPENALEX_EMAIL` to enter the high-speed polite pool. The collector also features exponential backoff retries via `tenacity`.
