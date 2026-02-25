#!/usr/bin/env python3
"""
CLI entrypoint: purchase a parking pass for a given day.
Usage: python purchase.py today | tomorrow | monday | mon | ...
Accepts: today, tomorrow; day of week (full or abbrev). Case insensitive.
For day of week, uses the next occurrence (or today if it's that day).
"""
import argparse
import sys
from datetime import date, timedelta
from typing import Optional

from parkonect_purchase import run_purchase, PurchaseResult

# Monday=0 .. Sunday=6 (Python weekday)
WEEKDAY_ALIASES = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


def when_to_date(when: str) -> Optional[date]:
    """Parse 'when' (case insensitive) to a target date. Returns None if invalid."""
    raw = (when or "").strip().lower()
    if not raw:
        return None
    if raw == "today":
        return date.today()
    if raw == "tomorrow":
        return date.today() + timedelta(days=1)
    if raw in WEEKDAY_ALIASES:
        target_weekday = WEEKDAY_ALIASES[raw]
        today = date.today()
        today_weekday = today.weekday()
        days_ahead = (target_weekday - today_weekday) % 7
        if days_ahead == 0:
            return today
        return today + timedelta(days=days_ahead)
    return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Purchase a parking pass for 540 W Madison (Parkonect)."
    )
    parser.add_argument(
        "when",
        help="Day to purchase for: today, tomorrow, or day of week (e.g. monday, mon, tue, wed). Case insensitive.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = when_to_date(args.when)
    if target is None:
        print(
            f"Invalid 'when': {args.when!r}. Use: today, tomorrow, or a day of week (monday, tue, wed, thu, fri, sat, sun).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Purchasing parking pass for {target} ({args.when})...")
    try:
        result: PurchaseResult = run_purchase(target)
    except ValueError as e:
        print("Failed:", e)
        exit(1)
    if result.success:
        print("Success:", result.message)
    else:
        print("Failed:", result.message)
        exit(1)


if __name__ == "__main__":
    main()
