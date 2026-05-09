"""
tests/ticket_generator.py — generates realistic support tickets using Claude
Batches large requests to avoid API timeouts.
"""

import asyncio
import json
import re
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from config import settings

CATEGORIES = [
    "API / OAuth",
    "API / Webhook",
    "API / Rate Limiting",
    "Database / Sync",
    "Database / Performance",
    "Database / Connectivity",
    "Infrastructure / Docker",
    "Infrastructure / Network",
    "Infrastructure / Deployment",
    "Authentication / SSO",
    "Authentication / Permissions",
    "Billing / Account",
    "Data / Import-Export",
    "UI / Bug",
    "How-To / Documentation",
]

SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

BATCH_SIZE = 10   # max tickets per API call to avoid timeouts
API_TIMEOUT = 120.0  # seconds

GENERATOR_PROMPT = """You are simulating a real enterprise SaaS support inbox.
Generate {count} realistic support tickets. Each ticket should read like something a real customer or engineer would write — varied tone, detail level, and phrasing. Some should be vague, some detailed, some urgent, some casual.

Return ONLY a JSON array. Each object must have:
- "ticket_text": the raw ticket text (50-200 words, realistic)
- "expected_severity": one of CRITICAL, HIGH, MEDIUM, LOW
- "expected_category": one of the exact categories listed below

Categories:
{categories}

Constraints:
- Spread tickets across different categories and severities
- Vary the writing style (terse engineer, frustrated customer, detailed bug report)
- Do not use placeholder names like [Company] — use realistic fake company/product names
- No markdown in ticket_text — plain text only
- Return ONLY the JSON array, no preamble or explanation
"""


async def _generate_batch(count: int, batch_num: int) -> list[dict]:
    """Generate a single batch of tickets."""
    prompt = GENERATOR_PROMPT.format(
        count=count,
        categories="\n".join(f"- {c}" for c in CATEGORIES)
    )

    payload = {
        "model": settings.claude_model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    raw = data["content"][0]["text"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    tickets = json.loads(raw)
    print(f"[generator] Batch {batch_num} → {len(tickets)} tickets generated")
    return tickets


async def generate_tickets(count: int = 20) -> list[dict]:
    """
    Generate {count} tickets, batching into groups of BATCH_SIZE
    to stay within API timeout limits.
    """
    all_tickets = []
    batches = []

    remaining = count
    while remaining > 0:
        batch_count = min(remaining, BATCH_SIZE)
        batches.append(batch_count)
        remaining -= batch_count

    print(f"[generator] Generating {count} tickets in {len(batches)} batch(es) of up to {BATCH_SIZE}...")

    for i, batch_count in enumerate(batches, 1):
        tickets = await _generate_batch(batch_count, i)
        all_tickets.extend(tickets)
        if i < len(batches):
            await asyncio.sleep(1)  # brief pause between batches

    print(f"[generator] Total: {len(all_tickets)} tickets ready")
    return all_tickets


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()

    tickets = asyncio.run(generate_tickets(args.count))
    for i, t in enumerate(tickets, 1):
        print(f"\n--- Ticket {i} [{t['expected_severity']}] [{t['expected_category']}] ---")
        print(t["ticket_text"][:120] + "...")
