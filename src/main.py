"""
AI Support Triage Engine — main.py
FastAPI app (webhook endpoint) + CLI entrypoint
"""

import argparse
import asyncio
import json
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path
from pydantic import BaseModel

from classifier import classify_ticket
from db import init_db, log_classification
from freshdesk import update_ticket
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Support Triage Engine",
    description="Classifies Freshdesk tickets by severity, category, and runbook using Claude",
    version="1.0.0",
    lifespan=lifespan,
)


class TicketPayload(BaseModel):
    ticket: str


class FreshdeskWebhookPayload(BaseModel):
    """Freshdesk webhook shape — only fields we need"""
    freshdesk_webhook: dict | None = None


# ── REST endpoint (direct) ────────────────────────────────────────────────────

@app.post("/triage")
async def triage_ticket(payload: TicketPayload, background_tasks: BackgroundTasks):
    """Classify a raw ticket string. Returns structured triage result."""
    result = await classify_ticket(payload.ticket)
    background_tasks.add_task(log_classification, payload.ticket, result, source="api")
    return result


# ── Freshdesk webhook endpoint ────────────────────────────────────────────────

@app.post("/webhook/freshdesk")
async def freshdesk_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives Freshdesk webhook events (ticket.created / ticket.updated).
    Classifies the ticket and writes results back to Freshdesk.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Freshdesk webhook envelope
    # https://support.freshdesk.com/support/solutions/articles/37602
    freshdesk_data = body.get("freshdesk_webhook", body)

    ticket_id = freshdesk_data.get("ticket_id") or freshdesk_data.get("id")
    subject = freshdesk_data.get("ticket_subject", "")
    description = freshdesk_data.get("ticket_description", "")

    if not ticket_id:
        raise HTTPException(status_code=400, detail="Missing ticket_id in payload")

    ticket_text = f"{subject}\n\n{description}".strip()
    if not ticket_text:
        raise HTTPException(status_code=400, detail="Empty ticket text")

    # Classify (await so we can respond quickly then update Freshdesk async)
    result = await classify_ticket(ticket_text)

    # Fire-and-forget: update Freshdesk + log to DB
    background_tasks.add_task(update_ticket, ticket_id, result)
    background_tasks.add_task(log_classification, ticket_text, result,
                              source="freshdesk", ticket_id=str(ticket_id))

    return {"status": "ok", "ticket_id": ticket_id, "triage": result}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-support-triage-engine"}


@app.get("/")
async def root():
    return {
        "service": "AI Support Triage Engine",
        "endpoints": {
            "POST /triage": "Classify a raw ticket string",
            "POST /webhook/freshdesk": "Freshdesk webhook receiver",
            "GET /health": "Health check",
            "GET /logs": "Recent classification log",
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
        "CRITICAL": "\033[91m",  # red
        "HIGH":     "\033[93m",  # yellow
        "MEDIUM":   "\033[94m",  # blue
        "LOW":      "\033[92m",  # green
    }
    sev = result.get("severity", "UNKNOWN")
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
    parser.add_argument("--serve", action="store_true", help="Start the API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.serve:
        uvicorn.run("main:app", host=args.host, port=args.port, reload=True)
    elif args.ticket:
        asyncio.run(_cli_classify(args.ticket))
    else:
        parser.print_help()
        sys.exit(1)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the web dashboard."""
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
