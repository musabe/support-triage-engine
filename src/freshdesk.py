"""
freshdesk.py — Freshdesk REST API client
Updates ticket priority, tags, and posts a private triage note.
"""

import httpx
from config import settings


# Freshdesk priority mapping (their API uses integers)
SEVERITY_TO_PRIORITY = {
    "CRITICAL": 4,  # Urgent
    "HIGH":     3,  # High
    "MEDIUM":   2,  # Medium
    "LOW":      1,  # Low
}

# Freshdesk status codes
STATUS_OPEN   = 2
STATUS_PENDING = 3


async def update_ticket(ticket_id: int | str, triage_result: dict) -> bool:
    """
    Write classification results back to Freshdesk:
      1. Update ticket priority + add triage tag
      2. Post a private note with the full triage summary
    Returns True on success, False on any error.
    """
    if not settings.freshdesk_domain or not settings.freshdesk_api_key:
        print("[freshdesk] Skipping update — FRESHDESK_DOMAIN or FRESHDESK_API_KEY not set")
        return False

    base_url = f"https://{settings.freshdesk_domain}/api/v2"
    auth = (settings.freshdesk_api_key, "X")  # Freshdesk uses API key as username, "X" as password

    severity  = triage_result.get("severity", "MEDIUM")
    category  = triage_result.get("category", "Unknown")
    confidence = triage_result.get("confidence", 0.0)
    runbook   = triage_result.get("runbook", "N/A")
    next_step = triage_result.get("next_step", "N/A")
    runbook_id = triage_result.get("runbook_id", "RB-000")

    priority = SEVERITY_TO_PRIORITY.get(severity, 2)
    tag = f"triage:{severity.lower()}"

    async with httpx.AsyncClient(timeout=15.0) as client:

        # 1 — Update priority and tags
        update_resp = await client.put(
            f"{base_url}/tickets/{ticket_id}",
            auth=auth,
            json={
                "priority": priority,
                "tags": [tag, f"category:{_slug(category)}", "ai-triaged"],
            }
        )

        if update_resp.status_code not in (200, 201):
            print(f"[freshdesk] Ticket update failed: {update_resp.status_code} — {update_resp.text[:200]}")
            return False

        # 2 — Post private note
        confidence_pct = f"{confidence * 100:.0f}%"
        confidence_bar = _confidence_bar(confidence)

        note_body = f"""<h3>🤖 AI Triage Result</h3>

<table>
  <tr><td><strong>Severity</strong></td><td>{severity}</td></tr>
  <tr><td><strong>Category</strong></td><td>{category}</td></tr>
  <tr><td><strong>Confidence</strong></td><td>{confidence_bar} {confidence_pct}</td></tr>
  <tr><td><strong>Runbook</strong></td><td>{runbook_id} — {runbook}</td></tr>
</table>

<p><strong>Suggested next step:</strong><br>{next_step}</p>

<hr>
<small><em>Classified automatically by AI Support Triage Engine. Review and override if needed.</em></small>
"""

        note_resp = await client.post(
            f"{base_url}/tickets/{ticket_id}/notes",
            auth=auth,
            json={
                "body": note_body,
                "private": True,
                "incoming": False,
            }
        )

        if note_resp.status_code not in (200, 201):
            print(f"[freshdesk] Note post failed: {note_resp.status_code} — {note_resp.text[:200]}")
            return False

    print(f"[freshdesk] Ticket {ticket_id} updated → severity={severity}, priority={priority}")
    return True


async def get_ticket(ticket_id: int | str) -> dict | None:
    """Fetch a single ticket from Freshdesk (useful for testing)."""
    if not settings.freshdesk_domain or not settings.freshdesk_api_key:
        return None

    base_url = f"https://{settings.freshdesk_domain}/api/v2"
    auth = (settings.freshdesk_api_key, "X")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{base_url}/tickets/{ticket_id}", auth=auth)
        if resp.status_code == 200:
            return resp.json()
    return None


def _slug(text: str) -> str:
    """Convert 'API / OAuth' → 'api-oauth' for use as a tag."""
    return text.lower().replace(" / ", "-").replace(" ", "-").replace("/", "-")


def _confidence_bar(confidence: float) -> str:
    """Simple ASCII confidence bar."""
    filled = round(confidence * 10)
    return "█" * filled + "░" * (10 - filled)
