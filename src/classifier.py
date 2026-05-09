"""
classifier.py — LLM classification logic using Claude API
"""

import json
import re
import httpx

from config import settings
from runbooks import RUNBOOK_MAP


SYSTEM_PROMPT = """You are a senior technical support triage specialist with 10+ years experience classifying enterprise SaaS support tickets. Your job is to analyse incoming tickets and return a structured classification.

Return ONLY valid JSON — no markdown fences, no preamble, no explanation. Schema:

{
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "category": "<one of the categories below>",
  "confidence": <float 0.0–1.0>,
  "runbook_id": "<runbook ID string>",
  "next_step": "<one concrete, specific action the engineer should take first>"
}

Severity guidelines:
- CRITICAL: system down, data loss, security breach, all users blocked
- HIGH: major feature broken, significant subset of users affected, SLA risk
- MEDIUM: degraded performance, workaround exists, single user/team affected
- LOW: cosmetic issue, how-to question, minor inconvenience

Categories (use exactly as written):
- API / OAuth
- API / Webhook
- API / Rate Limiting
- Database / Sync
- Database / Performance
- Database / Connectivity
- Infrastructure / Docker
- Infrastructure / Network
- Infrastructure / Deployment
- Authentication / SSO
- Authentication / Permissions
- Billing / Account
- Data / Import-Export
- UI / Bug
- How-To / Documentation
- Unknown

Pick the runbook_id from this list that best matches. If none fits, return "RB-000":
RB-001: API Key Invalid or Expired
RB-002: OAuth Token Rotation Failure
RB-003: Webhook Delivery Failure
RB-004: Rate Limit Exceeded
RB-005: Database Replication Lag
RB-006: Database Connection Pool Exhausted
RB-007: Database Query Performance
RB-008: Docker Container Crash Loop
RB-009: Network Connectivity / DNS
RB-010: SSO / SAML Misconfiguration
RB-011: Permission / Role Misconfiguration
RB-012: Data Import Failure
RB-013: Service Deployment Failure
RB-014: Billing / Subscription Issue
RB-000: Unknown / No Matching Runbook
"""


async def classify_ticket(ticket_text: str) -> dict:
    """
    Send ticket text to Claude API and return structured classification dict.
    Falls back gracefully on API errors.
    """
    payload = {
        "model": settings.claude_model,
        "max_tokens": 512,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Classify this support ticket:\n\n{ticket_text}"
            }
        ]
    }

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        raw_text = data["content"][0]["text"].strip()

        # Strip markdown fences if the model wrapped anyway
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)
        result = _validate_and_enrich(result)
        return result

    except httpx.HTTPStatusError as e:
        return _fallback(ticket_text, f"API error {e.response.status_code}")
    except (json.JSONDecodeError, KeyError) as e:
        return _fallback(ticket_text, f"Parse error: {e}")
    except Exception as e:
        return _fallback(ticket_text, f"Unexpected error: {e}")


def _validate_and_enrich(result: dict) -> dict:
    """Validate fields and add runbook title."""
    valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    if result.get("severity") not in valid_severities:
        result["severity"] = "MEDIUM"

    confidence = float(result.get("confidence", 0.5))
    result["confidence"] = max(0.0, min(1.0, confidence))

    runbook_id = result.get("runbook_id", "RB-000")
    result["runbook_id"] = runbook_id
    result["runbook"] = RUNBOOK_MAP.get(runbook_id, {}).get("title", "Unknown Runbook")
    result["runbook_url"] = RUNBOOK_MAP.get(runbook_id, {}).get("url", "")

    if "next_step" not in result:
        result["next_step"] = "Review ticket and assign to appropriate team."

    return result


def _fallback(ticket_text: str, reason: str) -> dict:
    """Return a safe fallback classification when the LLM call fails."""
    return {
        "severity": "MEDIUM",
        "category": "Unknown",
        "confidence": 0.0,
        "runbook_id": "RB-000",
        "runbook": "Unknown / No Matching Runbook",
        "runbook_url": "",
        "next_step": "Classification failed — manual review required.",
        "error": reason,
    }
