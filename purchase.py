#!/usr/bin/env python3
"""
CLI entrypoint: purchase a parking pass for today or tomorrow.
Usage: python purchase.py today | python purchase.py tomorrow
"""
import argparse
from datetime import date, timedelta

from parkonect_purchase import run_purchase, PurchaseResult


def parse_args():
    parser = argparse.ArgumentParser(
        description="Purchase a parking pass for 540 W Madison (Parkonect)."
    )
    parser.add_argument(
        "when",
        choices=["today", "tomorrow"],
        help="Day to purchase the pass for",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    today = date.today()
    target = today if args.when == "today" else today + timedelta(days=1)

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
