"""
AI Support Triage Engine — main.py
FastAPI app (webhook endpoint) + CLI entrypoint
"""

import argparse
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from classifier import classify_ticket
from db import init_db, log_classification
from freshdesk import update_ticket
from jira_client import update_issue
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Support Triage Engine",
    description="Classifies support tickets by severity, category, and runbook using Claude",
    version="1.0.0",
    lifespan=lifespan,
)


class TicketPayload(BaseModel):
    ticket: str


# ── REST endpoint (direct) ────────────────────────────────────────────────────

@app.post("/triage")
async def triage_ticket(payload: TicketPayload, background_tasks: BackgroundTasks):
    """Classify a raw ticket string. Returns structured triage result."""
    result = await classify_ticket(payload.ticket)
    background_tasks.add_task(log_classification, payload.ticket, result, source="api")
    return result


# ── Freshdesk webhook ─────────────────────────────────────────────────────────

@app.post("/webhook/freshdesk")
async def freshdesk_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives Freshdesk webhook events (ticket.created).
    Classifies and writes results back to Freshdesk.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    freshdesk_data = body.get("freshdesk_webhook", body)
    ticket_id   = freshdesk_data.get("ticket_id") or freshdesk_data.get("id")
    subject     = freshdesk_data.get("ticket_subject", "")
    description = freshdesk_data.get("ticket_description", "")

    if not ticket_id:
        raise HTTPException(status_code=400, detail="Missing ticket_id in payload")

    ticket_text = f"{subject}\n\n{description}".strip()
    if not ticket_text:
        raise HTTPException(status_code=400, detail="Empty ticket text")

    result = await classify_ticket(ticket_text)
    background_tasks.add_task(update_ticket, ticket_id, result)
    background_tasks.add_task(log_classification, ticket_text, result,
                              source="freshdesk", ticket_id=str(ticket_id))

    return {"status": "ok", "ticket_id": ticket_id, "triage": result}


# ── Jira webhook ──────────────────────────────────────────────────────────────

@app.post("/webhook/jira")
async def jira_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives Jira webhook events (issue_created).
    Only processes issue types defined in JIRA_ISSUE_TYPES.
    Classifies and writes results back to Jira.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Jira webhook envelope
    event = body.get("webhookEvent", "")
    issue = body.get("issue", {})
    fields = issue.get("fields", {})

    issue_key  = issue.get("key")
    issue_type = fields.get("issuetype", {}).get("name", "")
    summary    = fields.get("summary", "")
    description = _extract_jira_description(fields.get("description", ""))

    if not issue_key:
        raise HTTPException(status_code=400, detail="Missing issue key in payload")

    # Filter by issue type
    allowed_types = [t.strip() for t in settings.jira_issue_types.split(",")]
    if issue_type and issue_type not in allowed_types:
        return {
            "status": "skipped",
            "reason": f"Issue type '{issue_type}' not in triage list ({settings.jira_issue_types})",
            "issue_key": issue_key
        }

    ticket_text = f"{summary}\n\n{description}".strip()
    if not ticket_text:
        raise HTTPException(status_code=400, detail="Empty issue text")

    result = await classify_ticket(ticket_text)
    background_tasks.add_task(update_issue, issue_key, result)
    background_tasks.add_task(log_classification, ticket_text, result,
                              source="jira", ticket_id=issue_key)

    return {"status": "ok", "issue_key": issue_key, "triage": result}


def _extract_jira_description(description) -> str:
    """
    Extract plain text from Jira description.
    Jira Cloud uses Atlassian Document Format (ADF) — a nested JSON structure.
    Falls back gracefully if description is already a string or None.
    """
    if not description:
        return ""
    if isinstance(description, str):
        return description

    # ADF format — recursively extract text nodes
    texts = []

    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(description)
    return " ".join(texts).strip()


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the web dashboard."""
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Utility endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-support-triage-engine"}


@app.get("/")
async def root():
    return {
        "service": "AI Support Triage Engine",
        "endpoints": {
            "POST /triage":            "Classify a raw ticket string",
            "POST /webhook/freshdesk": "Freshdesk webhook receiver",
            "POST /webhook/jira":      "Jira webhook receiver",
            "GET  /dashboard":         "Web UI dashboard",
            "GET  /health":            "Health check",
            "GET  /logs":              "Recent classification log",
        }
    }


@app.get("/logs")
async def get_logs(limit: int = 20):
    """Return recent classifications from the database."""
    from db import get_recent_logs
    rows = await get_recent_logs(limit)
    return {"logs": rows}


# ── CLI entrypoint ────────────────────────────────────────────────────────────

async def _cli_classify(ticket_text: str):
    await init_db()
    result = await classify_ticket(ticket_text)
    await log_classification(ticket_text, result, source="cli")

    severity_colors = {
        "CRITICAL": "\033[91m",
        "HIGH":     "\033[93m",
        "MEDIUM":   "\033[94m",
        "LOW":      "\033[92m",
    }
    sev   = result.get("severity", "UNKNOWN")
    color = severity_colors.get(sev, "")
    reset = "\033[0m"

    print("\n" + "━" * 44)
    print(" TRIAGE RESULT")
    print("━" * 44)
    print(f" Severity  : {color}{sev}{reset}")
    print(f" Category  : {result.get('category', 'Unknown')}")
    print(f" Confidence: {result.get('confidence', 0):.2f}")
    print(f" Runbook   : {result.get('runbook', 'N/A')}")
    print(f" Next step : {result.get('next_step', 'N/A')}")
    print("━" * 44)
    print(f" Logged to PostgreSQL → triage_log")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Support Triage Engine")
    parser.add_argument("--ticket", type=str, help="Ticket text to classify")
    parser.add_argument("--serve",  action="store_true", help="Start the API server")
    parser.add_argument("--host",   default="0.0.0.0")
    parser.add_argument("--port",   type=int, default=8000)

    args = parser.parse_args()

    if args.serve:
        uvicorn.run("main:app", host=args.host, port=args.port, reload=True)
    elif args.ticket:
        asyncio.run(_cli_classify(args.ticket))
    else:
        parser.print_help()
        sys.exit(1)
