"""
jira_client.py — Jira Cloud REST API client
Writes triage results back to Jira issues:
  - Sets priority
  - Adds labels
  - Posts a comment with triage summary
  - Transitions issue status
"""

import httpx
from config import settings


# ── Priority mapping ──────────────────────────────────────────────────────────
# Jira priority names (must match your Jira project's priority scheme)
# Issue types in this project: Incident, Support
SEVERITY_TO_PRIORITY = {
    "CRITICAL": "Highest",
    "HIGH":     "High",
    "MEDIUM":   "Medium",
    "LOW":      "Low",
}

# ── Status transition mapping ─────────────────────────────────────────────────
# Maps severity to the Jira transition name to apply on new issues.
# These are the DEFAULT Jira Software transition names.
# If your project uses custom statuses, update these to match.
SEVERITY_TO_TRANSITION = {
    "CRITICAL": "In Progress",          # immediately move to In Progress
    "HIGH":     "In Progress",          # same for high
    "MEDIUM":   "Waiting for Customer", # medium → waiting for customer info
    "LOW":      None,                   # leave as To Do
}


async def update_issue(issue_key: str, triage_result: dict) -> bool:
    """
    Write classification results back to a Jira issue:
      1. Set priority
      2. Add triage labels
      3. Post comment with triage summary
      4. Transition status (CRITICAL/HIGH only)
    Returns True on success, False on any error.
    """
    if not settings.jira_domain or not settings.jira_email or not settings.jira_api_token:
        print("[jira] Skipping update — JIRA_DOMAIN, JIRA_EMAIL or JIRA_API_TOKEN not set")
        return False

    base_url  = f"https://{settings.jira_domain}/rest/api/3"
    auth      = (settings.jira_email, settings.jira_api_token)
    headers   = {"Content-Type": "application/json", "Accept": "application/json"}

    severity   = triage_result.get("severity", "MEDIUM")
    category   = triage_result.get("category", "Unknown")
    confidence = triage_result.get("confidence", 0.0)
    runbook_id = triage_result.get("runbook_id", "RB-000")
    runbook    = triage_result.get("runbook", "N/A")
    next_step  = triage_result.get("next_step", "N/A")
    priority   = SEVERITY_TO_PRIORITY.get(severity, "Medium")

    label_severity = f"triage-{severity.lower()}"
    label_category = "triage-" + category.lower().replace(" / ", "-").replace(" ", "-").replace("/", "-")

    async with httpx.AsyncClient(timeout=15.0) as client:

        # 1 — Set priority and labels
        update_resp = await client.put(
            f"{base_url}/issue/{issue_key}",
            auth=auth,
            headers=headers,
            json={
                "fields": {
                    "priority": {"name": priority},
                    "labels":   [label_severity, label_category, "ai-triaged"],
                }
            }
        )

        if update_resp.status_code not in (200, 204):
            print(f"[jira] Issue update failed: {update_resp.status_code} — {update_resp.text[:200]}")
            return False

        # 2 — Post comment
        confidence_pct = f"{confidence * 100:.0f}%"
        comment_body = _build_comment(
            severity, category, confidence_pct, runbook_id, runbook, next_step
        )

        comment_resp = await client.post(
            f"{base_url}/issue/{issue_key}/comment",
            auth=auth,
            headers=headers,
            json={"body": comment_body}
        )

        if comment_resp.status_code not in (200, 201):
            print(f"[jira] Comment failed: {comment_resp.status_code} — {comment_resp.text[:200]}")
            return False

        # 3 — Transition status (CRITICAL/HIGH only)
        transition_name = SEVERITY_TO_TRANSITION.get(severity)
        if transition_name:
            transition_id = await _get_transition_id(
                client, base_url, auth, headers, issue_key, transition_name
            )
            if transition_id:
                t_resp = await client.post(
                    f"{base_url}/issue/{issue_key}/transitions",
                    auth=auth,
                    headers=headers,
                    json={"transition": {"id": transition_id}}
                )
                if t_resp.status_code not in (200, 204):
                    print(f"[jira] Transition failed: {t_resp.status_code} — {t_resp.text[:200]}")
            else:
                print(f"[jira] Transition '{transition_name}' not found — skipping")

    print(f"[jira] Issue {issue_key} updated → severity={severity}, priority={priority}")
    return True


async def _get_transition_id(
    client, base_url: str, auth, headers, issue_key: str, transition_name: str
) -> str | None:
    """Look up the transition ID by name for a given issue."""
    resp = await client.get(
        f"{base_url}/issue/{issue_key}/transitions",
        auth=auth,
        headers=headers,
    )
    if resp.status_code != 200:
        return None

    transitions = resp.json().get("transitions", [])
    for t in transitions:
        if t.get("name", "").lower() == transition_name.lower():
            return t["id"]
    return None


def _build_comment(
    severity: str,
    category: str,
    confidence_pct: str,
    runbook_id: str,
    runbook: str,
    next_step: str,
) -> dict:
    """
    Build a Jira Atlassian Document Format (ADF) comment body.
    ADF is required for Jira Cloud API v3.
    """
    severity_colors = {
        "CRITICAL": "color_red",
        "HIGH":     "color_orange",
        "MEDIUM":   "color_blue",
        "LOW":      "color_green",
    }
    color = severity_colors.get(severity, "color_blue")

    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "🤖 AI Triage Result"}]
            },
            {
                "type": "table",
                "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
                "content": [
                    _table_row("Severity",   severity,        bold_value=True),
                    _table_row("Category",   category),
                    _table_row("Confidence", confidence_pct),
                    _table_row("Runbook",    f"{runbook_id} — {runbook}"),
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Suggested next step: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": next_step},
                ]
            },
            {
                "type": "rule"
            },
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Classified automatically by AI Support Triage Engine. Review and override if needed.",
                        "marks": [{"type": "em"}]
                    }
                ]
            }
        ]
    }


def _table_row(label: str, value: str, bold_value: bool = False) -> dict:
    """Helper to build an ADF table row."""
    value_marks = [{"type": "strong"}] if bold_value else []
    return {
        "type": "tableRow",
        "content": [
            {
                "type": "tableCell",
                "attrs": {},
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": label, "marks": [{"type": "strong"}]}
                ]}]
            },
            {
                "type": "tableCell",
                "attrs": {},
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": value, "marks": value_marks}
                ]}]
            },
        ]
    }


async def get_issue(issue_key: str) -> dict | None:
    """Fetch a single Jira issue (useful for testing)."""
    if not settings.jira_domain or not settings.jira_email or not settings.jira_api_token:
        return None

    base_url = f"https://{settings.jira_domain}/rest/api/3"
    auth     = (settings.jira_email, settings.jira_api_token)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{base_url}/issue/{issue_key}",
            auth=auth,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            return resp.json()
    return None
