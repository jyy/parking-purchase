"""Load .env and expose credentials and flags for the purchase flow."""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from this package directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value or not value.strip():
        raise ValueError(f"Missing required env var: {name}. Set it in .env (see .env.example).")
    return value.strip()


def get_parkonect_credentials() -> tuple[str, str]:
    return _require("PARKONECT_USERNAME"), _require("PARKONECT_PASSWORD")


def get_billing() -> tuple[str, str, str]:
    return (
        _require("BILLING_FIRST_NAME"),
        _require("BILLING_LAST_NAME"),
        _require("TEXT_RECEIPT_PHONE"),
    )


def get_card() -> tuple[str, str, str]:
    return (
        _require("CARD_NUMBER"),
        _require("CARD_EXPIRY"),
        _require("CARD_CVV"),
    )


def get_backup_card() -> Optional[tuple[str, str, str]]:
    num = os.environ.get("BACKUP_CARD_NUMBER")
    exp = os.environ.get("BACKUP_CARD_EXPIRY")
    cvv = os.environ.get("BACKUP_CARD_CVV")
    if not num or not num.strip():
        return None
    return num.strip(), (exp or "").strip(), (cvv or "").strip()


def is_headless() -> bool:
    return os.environ.get("HEADLESS", "").strip().lower() in ("1", "true", "yes")


def is_debug() -> bool:
    """When True: browser is visible (headless=False) and payment is filled but not submitted."""
    return os.environ.get("DEBUG", "").strip().lower() in ("1", "true", "yes")
