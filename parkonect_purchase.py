"""
Parkonect 540 W Madison parking pass purchase flow.
Single entrypoint run_purchase(target_date) for CLI or future messenger triggers.
"""
import re
from dataclasses import dataclass
from datetime import date

from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import (
    get_billing,
    get_card,
    get_parkonect_credentials,
    is_debug,
    is_headless,
)

BASE_URL = "https://secure.parkonect.com/GarageDetail4.aspx?GarageID=72"
DEFAULT_TIMEOUT_MS = 15_000


def _confirm(prompt: str, default: bool = True) -> bool:
    """Prompt with (Y/n) or (y/N); return True for yes, False for no. Default used for empty Enter."""
    suffix = "(Y/n): " if default else "(y/N): "
    raw = input(prompt + suffix).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


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
    debug = is_debug()
    headless = False if debug else is_headless()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()

        try:
            # Step 1: Open garage page and set date if possible
            page.goto(BASE_URL, wait_until="networkidle")
            _set_date_and_search(page, target_date)

            # Step 2: Choose pass (Daily Parking or fallback to Afternoon Special) and Reserve Now
            reserve_clicked = _select_pass_and_reserve(page, debug=debug)
            if not reserve_clicked:
                browser.close()
                return PurchaseResult(success=False, message="Purchase failed: could not select pass or click Reserve Now (check date and availability).")

            # Step 3: Login
            if not _do_login(page, email, password):
                browser.close()
                return PurchaseResult(success=False, message="Purchase failed: login failed.")

            # Step 4: Checkout – billing and phone, then Confirm My Purchase
            if not _do_checkout_billing(page, billing_first, billing_last, phone):
                browser.close()
                return PurchaseResult(success=False, message="Purchase failed: checkout/billing failed.")

            # Step 5: Payment – card details and Submit (interactive when debug)
            if debug:
                print("At payment page.")
                if _confirm("Fill payment form?", default=True):
                    if not _do_payment(page, card_number, card_expiry, card_cvv, debug=True):
                        print("Could not fill payment form automatically.")
                if _confirm("Submit payment?", default=True):
                    if _click_payment_submit(page):
                        result = _detect_success_or_failure(page)
                        browser.close()
                        return result
                    print("Could not find or click Submit button.")
                browser.close()
                return PurchaseResult(success=True, message="Purchase successful.")

            if not _do_payment(page, card_number, card_expiry, card_cvv, debug=False):
                browser.close()
                return PurchaseResult(success=False, message="Purchase failed: payment form failed.")

            # Step 6: Detect success or failure
            result = _detect_success_or_failure(page)
            browser.close()
            return result

        except PlaywrightTimeoutError as e:
            browser.close()
            msg = str(e).strip() or "timeout"
            return PurchaseResult(success=False, message=f"Purchase failed: timeout ({msg}).")
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            msg = str(e).strip() or "unknown error"
            return PurchaseResult(success=False, message=f"Purchase failed: {msg}")


def _set_date_and_search(page: Page, target_date: date) -> None:
    """Set the parking date and click Search to refresh options (Parkonect garage page)."""
    date_str = target_date.strftime("%m/%d/%Y")
    # Parkonect GarageDetail4: date input id ctl00_ContentPlaceHolder1_txt_start_date, then Search button
    date_input = page.locator('#ctl00_ContentPlaceHolder1_txt_start_date').or_(
        page.locator('input[id*="txt_start_date" i], input[name*="txt_start_date" i]')
    ).first
    if date_input.count() > 0:
        try:
            date_input.fill(date_str)
            search_btn = page.locator('#ctl00_ContentPlaceHolder1_btn_update').or_(
                page.locator('input[value="Search"][type="submit"], input.searchevent, button:has-text("Search")')
            ).first
            if search_btn.count() > 0:
                search_btn.click()
                page.wait_for_load_state("networkidle")
            return
        except Exception:
            pass
    # Fallback: generic date input then look for Search
    date_input = page.locator('input[type="date"], input[id*="Date"], input[name*="Date"]').first
    if date_input.count() > 0:
        try:
            date_input.fill(target_date.isoformat())
        except Exception:
            pass
    for selector in ['input[id*="date" i], input[name*="date" i]', 'input[placeholder*="date" i]']:
        try:
            el = page.locator(selector).first
            if el.count() > 0:
                el.fill(date_str)
                search_btn = page.locator('input[value="Search" i], button:has-text("Search")').first
                if search_btn.count() > 0:
                    search_btn.click()
                    page.wait_for_load_state("networkidle")
                return
        except Exception:
            pass
    return


def _select_pass_and_reserve(page: Page, *, debug: bool = False) -> bool:
    """Select Daily Parking if available, else Afternoon Special; click Reserve Now. Returns True if clicked."""
    reserve_text = re.compile(r"reserve\s*now", re.I)
    # Parkonect uses table id GridViewSpecials; Reserve Now is <input type="button" value="Reserve Now" class="reservenow">
    reserve_selector = "a, button, input[type='submit'], input[type='button']"
    grid = page.locator("#ctl00_ContentPlaceHolder1_GridViewSpecials").or_(page.locator("table.events[id*='GridViewSpecials']"))
    for pass_name in ("Daily Parking", "Afternoon Special"):
        row = grid.locator("tr").filter(has_text=pass_name).first
        if row.count() == 0:
            if debug:
                print(f"[DEBUG] No row found for '{pass_name}'")
            continue
        row_text = row.inner_text()
        # Only skip if actually 0/sold out (e.g. "100 spaces remain" must not match)
        if re.search(r"\b0\s+spaces\s+remain", row_text, re.I) or "sold out" in row_text.lower():
            if debug:
                print(f"[DEBUG] '{pass_name}' skipped: {row_text[:80]}...")
            continue
        # Reserve Now on Parkonect is input type=button with value="Reserve Now" (same row, last td)
        reserve = (
            row.get_by_role("button", name="Reserve Now")
            .or_(row.locator("input.reservenow, input[type='button'][value='Reserve Now']"))
            .or_(row.locator(f"{reserve_selector}").filter(has_text=reserve_text))
            .first
        )
        if reserve.count() == 0:
            reserve = row.locator("a:has-text('Reserve Now'), button:has-text('Reserve Now'), input[value*='Reserve']").first
        if reserve.count() > 0:
            if debug:
                print(f"[DEBUG] Clicking Reserve Now for '{pass_name}'")
            reserve.click()
            page.wait_for_load_state("networkidle")
            return True
        if debug:
            print(f"[DEBUG] Row found for '{pass_name}' but no Reserve Now link/button. Row text: {row_text[:120]}...")
    if debug:
        # Dump a snippet of page text so we can see what's actually there
        body = page.locator("body").first
        if body.count() > 0:
            snippet = body.inner_text()[:500].replace("\n", " ")
            print(f"[DEBUG] Page body snippet: {snippet}...")
    return False


def _do_login(page: Page, email: str, password: str) -> bool:
    """Fill login form and submit. Returns True if we appear to have left the login page."""
    try:
        # Parkonect may label the field "User Name", "Username", or "Email"
        user_input = (
            page.get_by_label("User Name")
            .or_(page.get_by_label("Username"))
            .or_(page.get_by_label("Email"))
            .or_(page.locator('input[type="email"]'))
            .or_(page.locator('input[name*="user" i], input[name*="mail" i], input[id*="User" i], input[id*="mail" i], input[id*="Email" i]'))
        ).first
        pw_input = page.get_by_label("Password").or_(page.locator('input[type="password"]')).first
        if user_input.count() > 0:
            user_input.fill(email)
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
        # Wait for checkout form (billing page after login)
        page.wait_for_load_state("networkidle")
        # Wait for at least one billing-like input to appear (form may render after JS)
        page.wait_for_selector(
            'input[id*="First" i], input[id*="Last" i], input[id*="Phone" i], label:has-text("First"), label:has-text("Billing")',
            state="attached",
            timeout=DEFAULT_TIMEOUT_MS,
        )
        # Billing fields: label, placeholder, then id/name (ASP.NET: ctl00_MainContent_txtFirstName etc.)
        first_el = (
            page.get_by_label("Billing First Name")
            .or_(page.get_by_label("First Name"))
            .or_(page.get_by_placeholder("First Name"))
            .or_(page.get_by_placeholder("Billing First Name"))
            .or_(page.locator('input[id*="FirstName" i]:not([type="hidden"]), input[id*="BillingFirst" i]:not([type="hidden"]), input[name*="FirstName" i]:not([type="hidden"]), input[name*="First" i]:not([type="hidden"])'))
        ).first
        last_el = (
            page.get_by_label("Billing Last Name")
            .or_(page.get_by_label("Last Name"))
            .or_(page.get_by_placeholder("Last Name"))
            .or_(page.get_by_placeholder("Billing Last Name"))
            .or_(page.locator('input[id*="LastName" i]:not([type="hidden"]), input[id*="BillingLast" i]:not([type="hidden"]), input[name*="LastName" i]:not([type="hidden"]), input[name*="Last" i]:not([type="hidden"])'))
        ).first
        phone_el = (
            page.get_by_label("Text Receipt & Pass")
            .or_(page.get_by_label("Text Receipt"))
            .or_(page.get_by_label("Cell"))
            .or_(page.get_by_placeholder("Phone"))
            .or_(page.get_by_placeholder("Cell"))
            .or_(page.locator('input[id*="Phone" i]:not([type="hidden"]), input[id*="Cell" i]:not([type="hidden"]), input[id*="TextReceipt" i]:not([type="hidden"]), input[name*="Phone" i]:not([type="hidden"]), input[name*="Cell" i]:not([type="hidden"])'))
        ).first
        filled_any = False
        if first_el.count() > 0:
            first_el.scroll_into_view_if_needed()
            first_el.fill(first)
            filled_any = True
        if last_el.count() > 0:
            last_el.scroll_into_view_if_needed()
            last_el.fill(last)
            filled_any = True
        if phone_el.count() > 0:
            phone_el.scroll_into_view_if_needed()
            phone_el.fill(phone)
            filled_any = True
        if not filled_any:
            return False
        # Confirm My Purchase: button, link, or input with that text/value
        confirm = (
            page.get_by_role("button", name="Confirm My Purchase")
            .or_(page.get_by_role("link", name="Confirm My Purchase"))
            .or_(page.get_by_text("Confirm My Purchase", exact=True))
            .or_(page.locator('input[type="submit"][value*="Confirm" i]'))
            .or_(page.locator('input[type="image"][alt*="Confirm" i]'))
            .or_(page.locator('a:has-text("Confirm My Purchase"), button:has-text("Confirm My Purchase")'))
        ).first
        if confirm.count() == 0:
            return False
        confirm.scroll_into_view_if_needed()
        confirm.click()
        page.wait_for_load_state("networkidle")
        return True
    except Exception:
        pass
    return False


def _parse_expiry(card_expiry: str) -> tuple[str, str]:
    """Parse MM/YY or MM/YYYY into (month, year). Year as 2-digit for dropdowns that use it."""
    parts = card_expiry.replace(" ", "").split("/")
    if len(parts) != 2:
        return ("", "")
    month = parts[0].zfill(2)
    year = parts[1].strip()
    if len(year) == 4:
        year = year[2:]
    return (month, year)


def _fill_transax_payment_form(page: Page, card_number: str, exp_month: str, exp_year: str, card_cvv: str) -> bool:
    """Fast path for Transax/Parkonect hosted payment page: exact ids txt_ccnumber, dd_expdatemonth, dd_expdateyear, txt_cvv2."""
    try:
        page.wait_for_selector("#txt_ccnumber", state="attached", timeout=10_000)
        year_4 = f"20{exp_year}"
        page.locator("#txt_ccnumber").fill(card_number)
        page.locator("#dd_expdatemonth").select_option(value=exp_month)
        page.locator("#dd_expdateyear").select_option(value=year_4)
        page.locator("#txt_cvv2").fill(card_cvv)
        return True
    except Exception:
        return False


def _do_payment(page: Page, card_number: str, card_expiry: str, card_cvv: str, *, debug: bool = False) -> bool:
    """Fill card number, expiration (dropdowns or input), CVV and submit (unless debug). No logging of card data."""
    exp_month, exp_year = _parse_expiry(card_expiry)

    def fill_field(loc, value: str) -> bool:
        if loc.count() == 0:
            return False
        loc.scroll_into_view_if_needed()
        loc.click()
        loc.fill(value)
        return True

    def fill_expiry_dropdowns(ctx) -> bool:
        """Fill month/year select dropdowns. Returns True if both filled."""
        year_val_4 = f"20{exp_year}"
        month_sel = ctx.locator('select[id*="Month" i], select[name*="Month" i]').first
        year_sel = ctx.locator('select[id*="Year" i], select[name*="Year" i]').first
        if month_sel.count() > 0 and year_sel.count() > 0:
            month_sel.scroll_into_view_if_needed()
            try:
                month_sel.select_option(value=exp_month)
            except Exception:
                month_sel.select_option(label=exp_month)
            year_sel.scroll_into_view_if_needed()
            try:
                year_sel.select_option(value=exp_year)
            except Exception:
                try:
                    year_sel.select_option(value=year_val_4)
                except Exception:
                    year_sel.select_option(label=exp_year)
            return True
        if month_sel.count() > 0:
            try:
                month_sel.select_option(value=exp_month)
            except Exception:
                month_sel.select_option(label=exp_month)
            return True
        if year_sel.count() > 0:
            try:
                year_sel.select_option(value=exp_year)
            except Exception:
                try:
                    year_sel.select_option(value=year_val_4)
                except Exception:
                    year_sel.select_option(label=exp_year)
            return True
        return False

    def fill_expiry_combined_dropdown(ctx) -> bool:
        """One select with options like 01/26, 12/28. Select by value or label."""
        combined = ctx.locator('select[id*="Expir" i], select[name*="Expir" i], select[id*="ExpDate" i], select[id*="Expiry" i]').first
        if combined.count() == 0:
            return False
        target = f"{exp_month}/{exp_year}"
        try:
            combined.select_option(value=target)
            return True
        except Exception:
            pass
        try:
            combined.select_option(label=target)
            return True
        except Exception:
            pass
        return False

    def fill_payment_form(ctx) -> bool:
        """Fill card fields in the given context (page or iframe). Returns True if all three filled."""
        # 1. Card number (input only)
        num_el = (
            ctx.get_by_label("Card Number")
            .or_(ctx.get_by_label("Credit Card Number"))
            .or_(ctx.get_by_placeholder("Card Number"))
            .or_(ctx.get_by_placeholder("Credit Card"))
            .or_(ctx.locator('input[id*="CardNumber" i]:not([type="hidden"]), input[id*="CreditCard" i]:not([type="hidden"]), input[id*="CardNum" i]:not([type="hidden"]), input[name*="CardNumber" i]:not([type="hidden"]), input[name*="CreditCard" i]:not([type="hidden"]), input[name*="Card" i]:not([type="hidden"])'))
        ).first
        # 2. Expiration: try dropdowns first (month/year or combined), then text input
        exp_filled = fill_expiry_dropdowns(ctx)
        if not exp_filled:
            exp_filled = fill_expiry_combined_dropdown(ctx)
        if not exp_filled:
            exp_el = (
                ctx.get_by_label("Expiration Date")
                .or_(ctx.get_by_label("Expiration"))
                .or_(ctx.get_by_label("Expiry"))
                .or_(ctx.get_by_placeholder("MM/YY"))
                .or_(ctx.locator('input[id*="Expir" i]:not([type="hidden"]), input[id*="Expiry" i]:not([type="hidden"]), input[id*="ExpDate" i]:not([type="hidden"]), input[name*="Expir" i]:not([type="hidden"]), input[name*="Expiry" i]:not([type="hidden"])'))
            ).first
            exp_filled = fill_field(exp_el, card_expiry)
        # 3. CVV (input only – never use a generic “second/third” input; expiration may be dropdowns)
        cvv_el = (
            ctx.get_by_label("CVV2")
            .or_(ctx.get_by_label("CVV"))
            .or_(ctx.get_by_label("Security Code"))
            .or_(ctx.get_by_placeholder("CVV"))
            .or_(ctx.get_by_placeholder("Security Code"))
            .or_(ctx.locator('input[id*="CVV" i]:not([type="hidden"]), input[id*="Cvv" i]:not([type="hidden"]), input[id*="CVC" i]:not([type="hidden"]), input[id*="SecurityCode" i]:not([type="hidden"]), input[name*="CVV" i]:not([type="hidden"]), input[name*="Cvv" i]:not([type="hidden"]), input[name*="CVC" i]:not([type="hidden"])'))
        ).first
        num_filled = fill_field(num_el, card_number)
        cvv_filled = fill_field(cvv_el, card_cvv)
        return num_filled and exp_filled and cvv_filled

    try:
        page.wait_for_load_state("domcontentloaded")
        filled = _fill_transax_payment_form(page, card_number, exp_month, exp_year, card_cvv)
        if not filled:
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(
                'input[id*="Card" i], input[id*="CVV" i], select[id*="Month" i], select[id*="Year" i]',
                state="attached",
                timeout=10_000,
            )
            filled = fill_payment_form(page)
            if not filled:
                for frame in page.frames:
                    if frame != page.main_frame:
                        filled = fill_payment_form(frame)
                        if filled:
                            break
        if not filled:
            return False
        if debug:
            return True  # Payment form filled; caller will not submit
        submit = (
            page.get_by_role("button", name="Submit")
            .or_(page.get_by_role("button", name="Submit Payment"))
            .or_(page.locator('input[type="submit"][value*="Submit" i]'))
            .or_(page.locator('input[type="submit"]'))
            .or_(page.locator('button[type="submit"]'))
            .or_(page.locator('input[type="image"][alt*="Submit" i]'))
            .or_(page.locator('a:has-text("Submit"), button:has-text("Submit")'))
        ).first
        if submit.count() == 0:
            return False
        submit.scroll_into_view_if_needed()
        submit.click()
        page.wait_for_load_state("networkidle")
        return True
    except Exception:
        pass
    return False


def _click_payment_submit(page: Page) -> bool:
    """Find and click the payment form Submit button. Returns True if clicked."""
    try:
        transax_btn = page.locator("#btn_submit")
        if transax_btn.count() > 0:
            transax_btn.wait_for(state="visible", timeout=5_000)
            page.wait_for_selector("#btn_submit:not([disabled])", timeout=5_000)
            transax_btn.click()
            page.wait_for_load_state("networkidle")
            return True
        submit = (
            page.get_by_role("button", name="Submit")
            .or_(page.get_by_role("button", name="Submit Payment"))
            .or_(page.locator('input[type="submit"][value*="Submit" i]'))
            .or_(page.locator('input[type="submit"]'))
            .or_(page.locator('button[type="submit"]'))
            .or_(page.locator('input[type="image"][alt*="Submit" i]'))
            .or_(page.locator('a:has-text("Submit"), button:has-text("Submit")'))
        ).first
        if submit.count() == 0:
            return False
        submit.scroll_into_view_if_needed()
        submit.click()
        page.wait_for_load_state("networkidle")
        return True
    except Exception:
        return False


def _detect_success_or_failure(page: Page) -> PurchaseResult:
    """Inspect the page after payment submit and return success or failure result."""
    url = page.url.lower()
    text_lower = page.locator("body").inner_text().lower() if page.locator("body").count() > 0 else ""
    if "confirm" in text_lower and ("success" in text_lower or "thank" in text_lower or "receipt" in text_lower):
        return PurchaseResult(success=True, message="Purchase successful.")
    if "error" in text_lower or "declined" in text_lower or "invalid" in text_lower:
        return PurchaseResult(success=False, message="Purchase failed.")
    if "confirm" in url or "receipt" in url or "success" in url:
        return PurchaseResult(success=True, message="Purchase successful.")
    if "dashboard" in text_lower and ("my orders" in text_lower or "my account" in text_lower):
        return PurchaseResult(success=True, message="Purchase successful.")
    if "default.aspx" in url or "myorders" in url:
        return PurchaseResult(success=True, message="Purchase successful.")
    return PurchaseResult(success=False, message="Purchase failed.")
