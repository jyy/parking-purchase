"""Load .env and expose credentials and flags for the purchase flow."""
import os
from pathlib import Path

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
    return _require("PARKONECT_EMAIL"), _require("PARKONECT_PASSWORD")


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


def is_headless() -> bool:
    return os.environ.get("HEADLESS", "").strip().lower() in ("1", "true", "yes")
