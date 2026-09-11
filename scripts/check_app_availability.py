"""Check the public converter UI without submitting queries or waking sleeping apps.

Requires Playwright and Chromium. Enable hosted automation only after confirming
that the hosting provider permits it. This is not an uptime guarantee.
"""

import argparse
import os
import sys
from urllib.parse import urlsplit

EXPECTED_TITLE = "Evidentia-CSC: a Clinical Search Convertor"


def validate_app_url(value: str) -> str:
    """Accept only a bare HTTPS Community Cloud app URL, without credentials."""
    value = value.strip()
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not host.endswith(".streamlit.app")
        or host == "streamlit.app"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("APP_URL must be a bare HTTPS *.streamlit.app URL.")
    return value.rstrip("/") + "/"


def check_page(page, url: str, timeout_ms: int) -> None:
    """Require the actual interactive UI; HTTP 200 alone is not a success."""
    page.set_default_timeout(timeout_ms)
    response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    if response is None or not response.ok:
        raise RuntimeError("The app did not return a successful page response.")
    # Do not click a wake-up prompt, log in, solve challenges, or submit a search.
    page.get_by_role("heading", name=EXPECTED_TITLE, exact=True).wait_for(state="visible")
    entry = page.get_by_role("textbox", name="Ovid MEDLINE strategy", exact=True)
    entry.wait_for(state="visible")
    button = page.get_by_role("button", name="Convert", exact=True)
    button.wait_for(state="visible")
    if not entry.is_editable() or not button.is_enabled():
        raise RuntimeError("The converter controls are not usable.")
    if page.locator('[data-testid="stException"]').count():
        raise RuntimeError("The app contains a Streamlit exception.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("APP_URL", ""))
    parser.add_argument("--timeout", type=int, default=90, help="Timeout in seconds (5-120).")
    args = parser.parse_args()
    try:
        url = validate_app_url(args.url)
        if not 5 <= args.timeout <= 120:
            raise ValueError("--timeout must be between 5 and 120 seconds.")
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                check_page(page, url, args.timeout * 1000)
            finally:
                browser.close()
    except Exception as exc:
        # Avoid writing complete page contents, URLs, or uploaded user data to logs.
        print(f"Availability check failed ({type(exc).__name__}). "
              "Open the app manually and inspect its status.", file=sys.stderr)
        return 1
    print("Availability check passed: converter interface is visible and usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
