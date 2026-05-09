"""
tests/scheduler.py — runs the test suite on a configurable schedule

Usage:
    python tests/scheduler.py                        # run every 24 hours, 20 tickets
    python tests/scheduler.py --interval 6 --count 10   # every 6 hours, 10 tickets
    python tests/scheduler.py --once                 # run once immediately and exit
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from run_tests import run_tests


async def run_once(count: int):
    print(f"\n[scheduler] Starting test run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    result = await run_tests(count=count)
    stats = result["stats"]
    print(f"[scheduler] Done — report: {result['report_path']}")
    print(f"[scheduler] Severity: {stats['sev_accuracy']:.0f}% | Category: {stats['cat_accuracy']:.0f}% | Confidence: {stats['avg_confidence']:.0f}%")
    return result


async def run_scheduled(interval_hours: float, count: int):
    print(f"[scheduler] Starting — running every {interval_hours}h with {count} tickets")
    print(f"[scheduler] Press Ctrl+C to stop\n")

    while True:
        try:
            await run_once(count)
        except Exception as e:
            print(f"[scheduler] Run failed: {e}")

        next_run = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[scheduler] Next run in {interval_hours}h — waiting...")
        await asyncio.sleep(interval_hours * 3600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Triage Engine — test scheduler")
    parser.add_argument("--interval", type=float, default=24.0,
                        help="Hours between test runs (default: 24)")
    parser.add_argument("--count",    type=int,   default=20,
                        help="Tickets per run (default: 20)")
    parser.add_argument("--once",     action="store_true",
                        help="Run once immediately and exit")
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_once(args.count))
    else:
        asyncio.run(run_scheduled(args.interval, args.count))
