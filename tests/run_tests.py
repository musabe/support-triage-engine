"""
tests/run_tests.py — automated test runner with HTML report generation

Usage:
    python tests/run_tests.py              # run with 20 tickets
    python tests/run_tests.py --count 50  # run with 50 tickets
    python tests/run_tests.py --count 20 --output reports/my_report.html
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from classifier import classify_ticket
from ticket_generator import generate_tickets

REPORTS_DIR = Path(__file__).parent.parent / "reports"


async def run_tests(count: int = 20, output_path: Path = None) -> dict:
    """Generate tickets, classify each one, return results dict."""

    print(f"\n[runner] Generating {count} test tickets via Claude...")
    tickets = await generate_tickets(count)

    print(f"[runner] Classifying {len(tickets)} tickets...\n")
    results = []

    for i, ticket in enumerate(tickets, 1):
        print(f"  [{i}/{len(tickets)}] {ticket['expected_category']} / {ticket['expected_severity']}", end=" → ")
        result = await classify_ticket(ticket["ticket_text"])

        sev_match  = result.get("severity")  == ticket["expected_severity"]
        cat_match  = result.get("category")  == ticket["expected_category"]
        confidence = result.get("confidence", 0.0)

        status = "PASS" if (sev_match and cat_match) else ("PARTIAL" if (sev_match or cat_match) else "FAIL")
        print(f"{status} (conf: {confidence:.2f})")

        results.append({
            "ticket_text":         ticket["ticket_text"],
            "expected_severity":   ticket["expected_severity"],
            "expected_category":   ticket["expected_category"],
            "got_severity":        result.get("severity", "—"),
            "got_category":        result.get("category", "—"),
            "confidence":          confidence,
            "runbook":             result.get("runbook", "—"),
            "runbook_id":          result.get("runbook_id", "—"),
            "next_step":           result.get("next_step", "—"),
            "sev_match":           sev_match,
            "cat_match":           cat_match,
            "status":              status,
            "error":               result.get("error"),
        })

    stats = _compute_stats(results)
    report_path = output_path or REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    _write_html_report(results, stats, report_path)
    print(f"\n[runner] Report saved → {report_path}")
    print(f"[runner] Results: {stats['pass']} PASS / {stats['partial']} PARTIAL / {stats['fail']} FAIL")
    print(f"[runner] Severity accuracy: {stats['sev_accuracy']:.0f}% | Category accuracy: {stats['cat_accuracy']:.0f}% | Avg confidence: {stats['avg_confidence']:.0f}%")

    return {"results": results, "stats": stats, "report_path": str(report_path)}


def _compute_stats(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    passes   = sum(1 for r in results if r["status"] == "PASS")
    partials = sum(1 for r in results if r["status"] == "PARTIAL")
    fails    = sum(1 for r in results if r["status"] == "FAIL")
    sev_correct = sum(1 for r in results if r["sev_match"])
    cat_correct = sum(1 for r in results if r["cat_match"])
    avg_conf = sum(r["confidence"] for r in results) / n

    sev_breakdown = {}
    for r in results:
        s = r["expected_severity"]
        if s not in sev_breakdown:
            sev_breakdown[s] = {"total": 0, "correct": 0}
        sev_breakdown[s]["total"] += 1
        if r["sev_match"]:
            sev_breakdown[s]["correct"] += 1

    cat_breakdown = {}
    for r in results:
        c = r["expected_category"]
        if c not in cat_breakdown:
            cat_breakdown[c] = {"total": 0, "correct": 0}
        cat_breakdown[c]["total"] += 1
        if r["cat_match"]:
            cat_breakdown[c]["correct"] += 1

    return {
        "total":            n,
        "pass":             passes,
        "partial":          partials,
        "fail":             fails,
        "sev_accuracy":     sev_correct / n * 100,
        "cat_accuracy":     cat_correct / n * 100,
        "avg_confidence":   avg_conf * 100,
        "sev_breakdown":    sev_breakdown,
        "cat_breakdown":    cat_breakdown,
        "run_at":           datetime.now(timezone.utc).isoformat(),
    }


def _write_html_report(results: list[dict], stats: dict, path: Path):
    """Write a self-contained HTML report."""

    sev_rows = "".join(
        f"""<tr>
            <td>{sev}</td>
            <td>{d['total']}</td>
            <td>{d['correct']}</td>
            <td>{d['correct']/d['total']*100:.0f}%</td>
        </tr>"""
        for sev, d in stats.get("sev_breakdown", {}).items()
    )

    cat_rows = "".join(
        f"""<tr>
            <td>{cat}</td>
            <td>{d['total']}</td>
            <td>{d['correct']}</td>
            <td class="{'good' if d['correct']/d['total'] >= 0.8 else 'bad'}">{d['correct']/d['total']*100:.0f}%</td>
        </tr>"""
        for cat, d in sorted(stats.get("cat_breakdown", {}).items(), key=lambda x: -x[1]["correct"]/x[1]["total"])
    )

    result_rows = "".join(
        f"""<tr class="row-{r['status'].lower()}">
            <td><span class="badge {r['status']}">{r['status']}</span></td>
            <td><span class="sev {r['expected_severity']}">{r['expected_severity']}</span></td>
            <td><span class="sev {r['got_severity']}">{r['got_severity']}</span></td>
            <td>{'✓' if r['cat_match'] else '✗'} {r['got_category']}</td>
            <td>{r['confidence']*100:.0f}%</td>
            <td class="ticket-text" title="{r['ticket_text'].replace(chr(34), '&quot;')}">{r['ticket_text'][:100]}...</td>
            <td>{r['runbook_id']}</td>
        </tr>"""
        for r in results
    )

    run_at = datetime.fromisoformat(stats["run_at"]).strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Triage Engine — Test Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f7f4; color: #1a1a18; font-size: 14px; padding: 2rem; }}
  h1 {{ font-size: 22px; font-weight: 500; margin-bottom: 4px; }}
  .meta {{ color: #6b6a65; font-size: 13px; margin-bottom: 2rem; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 2rem; }}
  .metric {{ background: #fff; border: 0.5px solid rgba(0,0,0,0.1); border-radius: 10px; padding: 1rem 1.25rem; }}
  .metric-label {{ font-size: 11px; color: #9b9a95; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }}
  .metric-value {{ font-size: 28px; font-weight: 500; }}
  .metric-value.green {{ color: #3B6D11; }}
  .metric-value.amber {{ color: #BA7517; }}
  .metric-value.red   {{ color: #A32D2D; }}
  .metric-value.purple {{ color: #534AB7; }}
  .section {{ background: #fff; border: 0.5px solid rgba(0,0,0,0.08); border-radius: 10px; padding: 1.25rem; margin-bottom: 1.5rem; }}
  .section-title {{ font-size: 11px; font-weight: 500; color: #9b9a95; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 0 12px 8px; font-size: 11px; color: #9b9a95; text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 0.5px solid rgba(0,0,0,0.08); font-weight: 500; }}
  td {{ padding: 9px 12px; border-bottom: 0.5px solid rgba(0,0,0,0.05); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8f7f4; }}
  .good {{ color: #3B6D11; font-weight: 500; }}
  .bad  {{ color: #A32D2D; font-weight: 500; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }}
  .badge.PASS    {{ background: #EAF3DE; color: #27500A; }}
  .badge.PARTIAL {{ background: #FAEEDA; color: #633806; }}
  .badge.FAIL    {{ background: #FCEBEB; color: #791F1F; }}
  .sev {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }}
  .sev.CRITICAL {{ background: #FCEBEB; color: #791F1F; }}
  .sev.HIGH     {{ background: #FAEEDA; color: #633806; }}
  .sev.MEDIUM   {{ background: #E6F1FB; color: #0C447C; }}
  .sev.LOW      {{ background: #EAF3DE; color: #27500A; }}
  .ticket-text {{ color: #6b6a65; max-width: 300px; }}
  .row-fail td  {{ background: #fffafa; }}
</style>
</head>
<body>

<h1>Triage Engine — Test Report</h1>
<p class="meta">Run at {run_at} &nbsp;·&nbsp; {stats['total']} tickets generated and classified by Claude</p>

<div class="metrics">
  <div class="metric">
    <div class="metric-label">Total tickets</div>
    <div class="metric-value purple">{stats['total']}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Pass</div>
    <div class="metric-value green">{stats['pass']}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Partial</div>
    <div class="metric-value amber">{stats['partial']}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Fail</div>
    <div class="metric-value red">{stats['fail']}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Severity accuracy</div>
    <div class="metric-value {'green' if stats['sev_accuracy'] >= 80 else 'amber'}">{stats['sev_accuracy']:.0f}%</div>
  </div>
  <div class="metric">
    <div class="metric-label">Category accuracy</div>
    <div class="metric-value {'green' if stats['cat_accuracy'] >= 80 else 'amber'}">{stats['cat_accuracy']:.0f}%</div>
  </div>
  <div class="metric">
    <div class="metric-label">Avg confidence</div>
    <div class="metric-value purple">{stats['avg_confidence']:.0f}%</div>
  </div>
</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 1.5rem;">
  <div class="section">
    <div class="section-title">Severity accuracy</div>
    <table>
      <thead><tr><th>Severity</th><th>Total</th><th>Correct</th><th>Accuracy</th></tr></thead>
      <tbody>{sev_rows}</tbody>
    </table>
  </div>
  <div class="section">
    <div class="section-title">Category accuracy</div>
    <table>
      <thead><tr><th>Category</th><th>Total</th><th>Correct</th><th>Accuracy</th></tr></thead>
      <tbody>{cat_rows}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="section-title">All results</div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Expected sev</th>
        <th>Got sev</th>
        <th>Category</th>
        <th>Confidence</th>
        <th>Ticket (truncated)</th>
        <th>Runbook</th>
      </tr>
    </thead>
    <tbody>{result_rows}</tbody>
  </table>
</div>

</body>
</html>"""

    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Triage Engine — automated test runner")
    parser.add_argument("--count",  type=int, default=20, help="Number of tickets to generate (default: 20)")
    parser.add_argument("--output", type=str, default=None, help="Output path for HTML report")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    asyncio.run(run_tests(count=args.count, output_path=output))
