# Parking pass purchase automation

Purchases a daily parking pass for 540 W Madison (Parkonect) via CLI. Uses Playwright for browser automation and locally stored credentials in `.env`.

## Setup

1. Create a virtualenv and install dependencies:

   ```bash
   cd parking-purchase
   python3 -m venv venv
   source venv/bin/activate   # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. Install Playwright browsers (one-time):

   ```bash
   playwright install chromium
   ```

3. Copy `.env.example` to `.env` and fill in your values. Never commit `.env`.

### Environment variables

| Variable | Description |
|----------|-------------|
| `PARKONECT_USERNAME` | Parkonect login (username or email) |
| `PARKONECT_PASSWORD` | Parkonect account password |
| `BILLING_FIRST_NAME` | Billing first name at checkout |
| `BILLING_LAST_NAME` | Billing last name at checkout |
| `TEXT_RECEIPT_PHONE` | Cell number for text receipt/pass |
| `CARD_NUMBER` | Card number (no spaces) |
| `CARD_EXPIRY` | Expiration, e.g. `MM/YY` |
| `CARD_CVV` | CVV2 |
| `HEADLESS` | Optional. `true` to run browser in background |
| `DEBUG` | Optional. `true` = browser visible, fill payment form but do not submit (verify then press Enter to close) |

## Usage

```bash
# Purchase for today or tomorrow
python purchase.py today
python purchase.py tomorrow

# Purchase for a day of the week (next occurrence; same day = today). Case insensitive.
python purchase.py monday
python purchase.py mon
python purchase.py tue
python purchase.py wednesday
python purchase.py fri
```

Optional: set `HEADLESS=true` in `.env` to run the browser in the background. Set `DEBUG=true` for interactive mode: browser visible, and at the payment page you get Y/n prompts to fill the form and to submit (e.g. "Fill payment form? (Y/n):", "Submit payment? (Y/n):").

## Pushing to GitHub

This project has a git repo with `origin` set to `git@github.com:jyy/parking-purchase.git`. To push:

1. Create an empty repository on GitHub: [Create repo](https://github.com/new?name=parking-purchase) (name: `parking-purchase`, no README or .gitignore).
2. Push: `git push -u origin main`.

## Later: messenger integration

You can trigger the same purchase flow from a messaging app (e.g. Signal, Telegram) by having a listener parse commands like "parking today" and call `run_purchase(target_date)` from `parkonect_purchase.py`. No changes to the purchase module are required.
