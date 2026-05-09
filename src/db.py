"""
db.py — PostgreSQL persistence using asyncpg
Stores every classification in triage_log for audit and pattern analysis.
"""

import json
from datetime import datetime, timezone

import asyncpg

from config import settings

_pool: asyncpg.Pool | None = None


async def init_db():
    """Create connection pool and ensure schema exists."""
    global _pool
    try:
        _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
        await _ensure_schema()
        print("[db] PostgreSQL connected and schema ready")
    except Exception as e:
        print(f"[db] WARNING: Could not connect to PostgreSQL — {e}")
        print("[db] Running without persistence (in-memory fallback active)")
        _pool = None


async def _ensure_schema():
    """Create triage_log table if it doesn't exist."""
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS triage_log (
                id            SERIAL PRIMARY KEY,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source        TEXT NOT NULL DEFAULT 'api',
                ticket_id     TEXT,
                ticket_text   TEXT NOT NULL,
                severity      TEXT,
                category      TEXT,
                confidence    FLOAT,
                runbook_id    TEXT,
                runbook       TEXT,
                next_step     TEXT,
                raw_result    JSONB
            );
            CREATE INDEX IF NOT EXISTS triage_log_created_at_idx ON triage_log (created_at DESC);
            CREATE INDEX IF NOT EXISTS triage_log_severity_idx ON triage_log (severity);
        """)


# In-memory fallback when DB is unavailable
_in_memory_log: list[dict] = []


async def log_classification(
    ticket_text: str,
    result: dict,
    source: str = "api",
    ticket_id: str | None = None,
) -> int | None:
    """Persist a classification. Returns row id or None."""
    row = {
        "source": source,
        "ticket_id": ticket_id,
        "ticket_text": ticket_text[:2000],  # truncate long tickets
        "severity": result.get("severity"),
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "runbook_id": result.get("runbook_id"),
        "runbook": result.get("runbook"),
        "next_step": result.get("next_step"),
        "raw_result": json.dumps(result),
    }

    if _pool is None:
        # In-memory fallback
        row["id"] = len(_in_memory_log) + 1
        row["created_at"] = datetime.now(timezone.utc).isoformat()
        _in_memory_log.append(row)
        print(f"[db] Logged (in-memory, id={row['id']}): {result.get('severity')} / {result.get('category')}")
        return row["id"]

    try:
        async with _pool.acquire() as conn:
            row_id = await conn.fetchval("""
                INSERT INTO triage_log
                    (source, ticket_id, ticket_text, severity, category, confidence,
                     runbook_id, runbook, next_step, raw_result)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
                RETURNING id
            """,
                row["source"], row["ticket_id"], row["ticket_text"],
                row["severity"], row["category"], row["confidence"],
                row["runbook_id"], row["runbook"], row["next_step"],
                row["raw_result"],
            )
            print(f"[db] Logged (PostgreSQL, id={row_id}): {result.get('severity')} / {result.get('category')}")
            return row_id
    except Exception as e:
        print(f"[db] Log error: {e}")
        return None


async def get_recent_logs(limit: int = 20) -> list[dict]:
    """Return recent classifications."""
    if _pool is None:
        return list(reversed(_in_memory_log[-limit:]))

    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, created_at, source, ticket_id, ticket_text,
                       severity, category, confidence, runbook_id, runbook, next_step
                FROM triage_log
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[db] Fetch error: {e}")
        return []
