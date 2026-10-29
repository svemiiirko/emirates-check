import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Load .env file automatically if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TARGET_URL = "https://external.emiratesgroupcareers.com/en_US/careersmarketplace/ProfileJobApplications"
LOGIN_URL = "https://external.emiratesgroupcareers.com/en_US/careersmarketplace/Login"

USER_EMAIL = os.getenv("EMIRATES_EMAIL")
USER_PASSWORD = os.getenv("EMIRATES_PASSWORD")
STATE_FILE = "emirates_app_state.json"

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

APPLICATION_KEY = "emirates_job_application_status"
EXPECTED_STATUS = "Application Under Review"


def send_email_alert(old_status, new_status, full_text=""):
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("Missing email configuration. Skipping email alert.")
        return False

    subject = "Emirates Job Application Status Update!"
    body = (
        f"Your Emirates job application status has changed!\n\n"
        f"Previous Status: {old_status}\n"
        f"New Detected Status: {new_status}\n\n"
        f"Context snippet:\n{full_text[:500]}\n\n"
        f"Check your portal: {TARGET_URL}"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())

        print("Alert email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send alert email: {e}")
        return False


def load_seen_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading state file: {e}")
    return {}


def save_seen_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def fetch_application_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            print(f"Navigating to login page: {LOGIN_URL}...")
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)

            # Dismiss the OneTrust cookie banner if it appears
            cookie_btn = page.locator("#onetrust-accept-btn-handler").first
            if cookie_btn.is_visible():
                print("Accepting cookies banner...")
                cookie_btn.click(force=True)
                page.wait_for_timeout(1000)

            email_input = page.locator(
                "input[type='email'], input[name='email'], input[id*='email'], input[id*='user']"
            ).first
            if email_input.is_visible():
                print("Entering email...")
                email_input.fill(USER_EMAIL)

            password_input = page.locator(
                "input[type='password'], input[name='password']"
            ).first
            if password_input.is_visible():
                print("Entering password...")
                password_input.fill(USER_PASSWORD)

            submit_btn = page.locator(
                "button[type='submit'], input[type='submit'], button:has-text('Sign In'), button:has-text('Log In')"
            ).first
            if submit_btn.is_visible():
                print("Clicking submit button...")
                submit_btn.click(force=True)
            else:
                password_input.press("Enter")

            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            print(f"Navigating to target page: {TARGET_URL}...")
            page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            return page.content()

        finally:
            browser.close()


def parse_and_check(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    seen_data = load_seen_state()

    page_text = soup.get_text(" ", strip=True)

    has_expected_status = bool(
        re.search(r"Application\s+Under\s+Review", page_text, re.IGNORECASE)
    )

    current_status = EXPECTED_STATUS if has_expected_status else "STATUS_CHANGED"

    print(f"Has '{EXPECTED_STATUS}': {has_expected_status}")
    print(f"Current detected status: {current_status}")

    if APPLICATION_KEY not in seen_data:
        print("No previous state stored. Saving initial baseline:", current_status)
        seen_data[APPLICATION_KEY] = current_status
        save_seen_state(seen_data)
        return

    previous_status = seen_data[APPLICATION_KEY]
    print(f"Previous status: {previous_status}")

    if previous_status == EXPECTED_STATUS and current_status != EXPECTED_STATUS:
        print("Status change detected! Sending alert...")
        if send_email_alert(previous_status, current_status, page_text):
            seen_data[APPLICATION_KEY] = current_status
            save_seen_state(seen_data)
        else:
            print("Failed to send email. Retaining state.")
        return

    seen_data[APPLICATION_KEY] = current_status
    save_seen_state(seen_data)
    print("State synchronized:", current_status)


if __name__ == "__main__":
    html = fetch_application_page()
    parse_and_check(html)
