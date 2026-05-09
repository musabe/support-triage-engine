# 🤖 AI-Powered Support Triage Engine

> Classifies incoming support tickets by severity, category, and suggested runbook — using an LLM API backed by PostgreSQL, Docker, and a webhook endpoint compatible with Freshdesk and Jira.

![Language](https://img.shields.io/badge/language-Python-blue?style=flat-square)
![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20PostgreSQL%20%7C%20Docker-green?style=flat-square)
![Status](https://img.shields.io/badge/status-active-brightgreen?style=flat-square)

---

## 🎯 Overview

Support teams waste significant time manually routing tickets — reading, categorising, and assigning before any diagnosis begins. This tool automates that first pass: paste or POST a raw ticket, and the engine returns a structured classification (severity, category, suggested runbook) powered by an LLM trained on real support patterns.

Built from 10 years of hands-on pattern recognition across global enterprise SaaS support. The classifications aren't generic — they reflect how API, database, and infrastructure failures actually present in production tickets.

---

## 🏗️ Architecture

![Architecture diagram showing the flow: Freshdesk webhook → FastAPI → Claude API → Freshdesk update, with PostgreSQL persisting each classification](docs/screenshots/architecture-diagram.png)

A new ticket in Freshdesk triggers a webhook POST to the FastAPI server. The server validates and queues the classification request asynchronously — responding immediately to Freshdesk to avoid timeout — then calls the Claude API to classify severity, category, and runbook. The result is written back to Freshdesk (priority, tags, private note) and persisted to PostgreSQL for audit and pattern analysis.

---

## 📸 Screenshots

### Ticket classification output (CLI)
![CLI output showing ticket classification](docs/screenshots/cli-classification-output.png)
*Raw ticket in → structured triage output with severity, category, and runbook suggestion*

### REST endpoint response (Postman)
![Postman showing POST /triage response](docs/screenshots/postman-triage-response.png)
*POST /triage endpoint returning JSON — ready to plug into a Freshdesk or Jira webhook*

### PostgreSQL log — classification history
![pgAdmin or psql showing triage_log table](docs/screenshots/postgres-triage-log.png)
*Every classification persisted to PostgreSQL for audit, pattern analysis, and retraining*

### Docker Compose — services running
![Terminal showing docker-compose up output](docs/screenshots/docker-compose-up.png)
*Full stack spun up in one command — API server, PostgreSQL, and pgAdmin*

---

## 🧰 Tech Stack

- **Language** — Python 3.11
- **API Framework** — FastAPI
- **Database** — PostgreSQL 15
- **Infrastructure** — Docker Compose
- **LLM** — Claude API (claude-sonnet-4-20250514)
- **HTTP client** — httpx
- **DB driver** — asyncpg
- **Testing** — Postman, pytest

---

## 📁 Project Structure

```
support-triage-engine/
├── docker-compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── main.py              # FastAPI app + CLI entrypoint
│   ├── classifier.py        # LLM prompt logic + response parsing
│   ├── db.py                # PostgreSQL connection + triage_log schema
│   ├── config.py            # Env vars, model config
│   ├── freshdesk.py         # Freshdesk REST API client
│   └── runbooks.py          # Runbook mapping by category
├── tests/
│   └── test_classifier.py   # pytest integration tests
└── docs/
    ├── FRESHDESK_SETUP.md   # Step-by-step Freshdesk webhook guide
    └── screenshots/
        └── architecture-diagram.png
```

---

## 🚀 Getting Started

### ✅ Prerequisites

- Docker installed and running
- Python 3.9+
- An Anthropic API key
- A Freshdesk account (API key from Profile Settings)

### ▶️ Step 1 — Clone and configure

```bash
git clone https://github.com/musabe/ai-support-triage-engine
cd ai-support-triage-engine
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, FRESHDESK_DOMAIN, FRESHDESK_API_KEY
```

### ▶️ Step 2 — Start containers

```bash
docker-compose up -d
```

### ▶️ Step 3 — Install dependencies (local dev)

```bash
pip install -r requirements.txt
```

### ▶️ Step 4 — Run via CLI

```bash
python src/main.py --ticket "Webhook deliveries failing with 401 after OAuth token rotation"
```

Expected output:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TRIAGE RESULT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Severity  : HIGH
 Category  : API / OAuth
 Confidence: 0.94
 Runbook   : RB-002 — OAuth Token Rotation Failure
 Next step : Verify token expiry window; check webhook signing secret rotation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Logged to PostgreSQL → triage_log
```

### ▶️ Step 5 — Or call the REST endpoint

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"ticket": "Webhook deliveries failing with 401 after OAuth token rotation"}'
```

---

## 🔌 Freshdesk Integration

See **[docs/FRESHDESK_SETUP.md](docs/FRESHDESK_SETUP.md)** for the full step-by-step guide, including:

- Where to find your Freshdesk API key
- How to create the webhook automation rule
- The exact JSON payload template to paste into Freshdesk
- Using ngrok for local testing

When a ticket is created, the engine automatically:

1. Sets the **priority** — CRITICAL→Urgent, HIGH→High, MEDIUM→Medium, LOW→Low
2. Adds **tags** — `ai-triaged`, `triage:high`, `category:api-oauth`, etc.
3. Posts a **private note** with the full triage summary, confidence score, and suggested next step

---

## 🧠 How Classification Works

1. Ticket text is sent to Claude with a structured system prompt built from real support patterns
2. The model returns a JSON object: `{ severity, category, confidence, runbook_id, next_step }`
3. Result is validated, mapped to a runbook, and persisted to PostgreSQL
4. Freshdesk is updated via REST API; CLI and REST responses are formatted from the same output

Categories covered: `API / OAuth`, `API / Webhook`, `API / Rate Limiting`, `Database / Sync`, `Database / Performance`, `Database / Connectivity`, `Infrastructure / Docker`, `Infrastructure / Network`, `Infrastructure / Deployment`, `Authentication / SSO`, `Authentication / Permissions`, `Billing / Account`, `Data / Import-Export`, `UI / Bug`, `How-To / Documentation`, `Unknown`

---

## 🚧 Status

| Feature | Status |
|---|---|
| CLI classifier | ✅ Done |
| FastAPI REST endpoint | ✅ Done |
| PostgreSQL triage log | ✅ Done |
| Docker Compose stack | ✅ Done |
| Runbook mapping (14 runbooks) | ✅ Done |
| Freshdesk webhook integration | ✅ Done |
| Confidence scoring + fallback | ✅ Done |
| Jira webhook integration | 🔜 Planned |
| Web UI dashboard | 🔜 Planned |

---

## 👤 Author

**Mustapha Abella**
Senior Technical Support Engineer
Focused on API-driven SaaS, data integration, and developer-facing support

[github.com/musabe](https://github.com/musabe)
