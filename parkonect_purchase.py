"""
Parkonect 540 W Madison parking pass purchase flow.
Single entrypoint run_purchase(target_date) for CLI or future messenger triggers.
"""
from dataclasses import dataclass
from datetime import date

from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import (
    get_billing,
    get_card,
    get_parkonect_credentials,
    is_headless,
)

BASE_URL = "https://secure.parkonect.com/GarageDetail4.aspx?GarageID=72"
DEFAULT_TIMEOUT_MS = 15_000


@dataclass
class PurchaseResult:
    success: bool
    message: str


def run_purchase(target_date: date) -> PurchaseResult:
    """
    Run the full purchase flow for the given date.
    Returns a result suitable for CLI output or messenger reply.
    """
    email, password = get_parkonect_credentials()
    billing_first, billing_last, phone = get_billing()
    card_number, card_expiry, card_cvv = get_card()
    headless = is_headless()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()

        try:
            # Step 1: Open garage page and set date if possible
            page.goto(BASE_URL, wait_until="networkidle")
            _set_date_if_possible(page, target_date)

            # Step 2: Choose pass (Daily Parking or fallback to Afternoon Special) and Reserve Now
            reserve_clicked = _select_pass_and_reserve(page)
            if not reserve_clicked:
                browser.close()
                return PurchaseResult(
                    success=False,
                    message="Could not find an available pass (Daily Parking or Afternoon Special) or Reserve Now button.",
                )

            # Step 3: Login
            if not _do_login(page, email, password):
                browser.close()
                return PurchaseResult(success=False, message="Login failed or login page not found.")

            # Step 4: Checkout – billing and phone, then Confirm My Purchase
            if not _do_checkout_billing(page, billing_first, billing_last, phone):
                browser.close()
                return PurchaseResult(success=False, message="Checkout (billing) failed or page not found.")

            # Step 5: Payment – card details and Submit
            if not _do_payment(page, card_number, card_expiry, card_cvv):
                browser.close()
                return PurchaseResult(success=False, message="Payment step failed or page not found.")

            # Step 6: Detect success or failure
            result = _detect_success_or_failure(page)
            browser.close()
            return result

        except PlaywrightTimeoutError as e:
            browser.close()
            return PurchaseResult(success=False, message=f"Timeout: {e}")
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return PurchaseResult(success=False, message=str(e))


def _set_date_if_possible(page: Page, target_date: date) -> None:
    """Set the parking date if the page has a date control or same-site Change Date flow."""
    date_str = target_date.strftime("%m/%d/%Y")
    # Try common patterns: date input, or link that stays on same origin
    date_input = page.locator('input[type="date"], input[id*="Date"], input[name*="Date"]').first
    if date_input.count() > 0:
        try:
            # HTML date input expects YYYY-MM-DD
            date_input.fill(target_date.isoformat())
            return
        except Exception:
            pass
    # Try text input that might accept MM/DD/YYYY
    for selector in ['input[id*="date" i], input[name*="date" i]', 'input[placeholder*="date" i]']:
        try:
            el = page.locator(selector).first
            if el.count() > 0:
                el.fill(date_str)
                return
        except Exception:
            pass
    # If "Change Date?" stays on parkonect.com we could click and set; plan notes it may go to another site.
    # Proceed without changing date if we can't find a control (page may default to today).
    return


def _select_pass_and_reserve(page: Page) -> bool:
    """Select Daily Parking if available, else Afternoon Special; click Reserve Now. Returns True if clicked."""
    # Prefer Daily Parking; fallback to Afternoon Special if Daily shows 0 spaces or no button
    for pass_name in ("Daily Parking", "Afternoon Special"):
        row = page.locator("tr").filter(has_text=pass_name).first
        if row.count() == 0:
            continue
        row_text = row.inner_text()
        if "0 spaces remain" in row_text or "sold out" in row_text.lower():
            continue
        reserve = row.get_by_role("link", name="Reserve Now").or_(row.get_by_role("button", name="Reserve Now")).first
        if reserve.count() == 0:
            reserve = row.locator("a:has-text('Reserve Now'), button:has-text('Reserve Now')").first
        if reserve.count() > 0:
            reserve.click()
            page.wait_for_load_state("networkidle")
            return True
    return False


def _do_login(page: Page, email: str, password: str) -> bool:
    """Fill login form and submit. Returns True if we appear to have left the login page."""
    try:
        email_input = page.get_by_label("Email").or_(page.locator('input[type="email"], input[name*="mail" i], input[id*="mail" i]')).first
        pw_input = page.get_by_label("Password").or_(page.locator('input[type="password"]')).first
        if email_input.count() > 0:
            email_input.fill(email)
        if pw_input.count() > 0:
            pw_input.fill(password)
        submit = page.get_by_role("button", name="Login").or_(page.get_by_role("button", name="Sign In")).or_(
            page.get_by_role("link", name="Login").or_(page.get_by_role("link", name="Sign In"))
        ).first
        if submit.count() == 0:
            submit = page.locator('input[type="submit"], button[type="submit"], a:has-text("Login"), a:has-text("Sign In")').first
        if submit.count() > 0:
            submit.click()
            page.wait_for_load_state("networkidle")
            return True
    except Exception:
        pass
    return False


def _do_checkout_billing(page: Page, first: str, last: str, phone: str) -> bool:
    """Fill billing first/last, text receipt phone; click Confirm My Purchase."""
    try:
        first_el = page.get_by_label("Billing First Name").or_(page.locator('input[name*="First" i], input[id*="FirstName" i], input[id*="BillingFirst" i]')).first
        last_el = page.get_by_label("Billing Last Name").or_(page.locator('input[name*="Last" i], input[id*="LastName" i], input[id*="BillingLast" i]')).first
        phone_el = page.get_by_label("Text Receipt").or_(page.get_by_label("Cell")).or_(page.locator('input[name*="Phone" i], input[name*="Cell" i], input[id*="Phone" i]')).first
        if first_el.count() > 0:
            first_el.fill(first)
        if last_el.count() > 0:
            last_el.fill(last)
        if phone_el.count() > 0:
            phone_el.fill(phone)
        confirm = page.get_by_role("button", name="Confirm My Purchase").or_(page.get_by_role("link", name="Confirm My Purchase")).first
        if confirm.count() == 0:
            confirm = page.locator('input[value*="Confirm" i], button:has-text("Confirm"), a:has-text("Confirm My Purchase")').first
        if confirm.count() > 0:
            confirm.click()
            page.wait_for_load_state("networkidle")
            return True
    except Exception:
        pass
    return False


def _do_payment(page: Page, card_number: str, card_expiry: str, card_cvv: str) -> bool:
    """Fill card number, expiration, CVV and submit. No logging of card data."""
    try:
        num_el = page.get_by_label("Card Number").or_(page.locator('input[name*="Card" i], input[id*="CardNumber" i], input[name*="Number" i]')).first
        exp_el = page.get_by_label("Expiration").or_(page.locator('input[name*="Expir" i], input[id*="Expir" i]')).first
        cvv_el = page.get_by_label("CVV").or_(page.locator('input[name*="CVV" i], input[id*="CVV" i]')).first
        if num_el.count() > 0:
            num_el.fill(card_number)
        if exp_el.count() > 0:
            exp_el.fill(card_expiry)
        if cvv_el.count() > 0:
            cvv_el.fill(card_cvv)
        submit = page.get_by_role("button", name="Submit").or_(page.locator('input[type="submit"], button[type="submit"]')).first
        if submit.count() > 0:
            submit.click()
            page.wait_for_load_state("networkidle")
            return True
    except Exception:
        pass
    return False


def _detect_success_or_failure(page: Page) -> PurchaseResult:
    """Inspect the page after payment submit and return success or failure result."""
    url = page.url
    text_lower = page.locator("body").inner_text().lower() if page.locator("body").count() > 0 else ""
    if "confirm" in text_lower and ("success" in text_lower or "thank" in text_lower or "receipt" in text_lower):
        return PurchaseResult(success=True, message="Purchase completed successfully.")
    if "error" in text_lower or "declined" in text_lower or "invalid" in text_lower:
        return PurchaseResult(success=False, message="Payment may have been declined or validation failed. Check the page.")
    if "confirm" in url or "receipt" in url or "success" in url:
        return PurchaseResult(success=True, message="Purchase completed (confirmation URL detected).")
    return PurchaseResult(
        success=False,
        message="Could not confirm success. Check the site or your receipt to verify the purchase.",
    )
