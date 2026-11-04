import os
import re
from playwright.sync_api import sync_playwright

# Učitavanje kredencijala iz GitHub Secrets / Environment Variables
EMAIL = os.environ.get("EMIRATES_EMAIL")
PASSWORD = os.environ.get("EMIRATES_PASSWORD")
LOGIN_URL = "https://external.emiratesgroupcareers.com/en_US/careersmarketplace/Login"
TARGET_URL = "https://external.emiratesgroupcareers.com/en_US/careersmarketplace/ProfileJobApplications"

def send_alert_email(detected_status):
    """
    Ovdje implementiraj svoju logiku za slanje e-maila (npr. smtplib, SendGrid, itd.)
    """
    print(f"📧 Alert email triggers for status: {detected_status}")

def run_checker():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Postavljanje standardnog User-Agenta radi zaobilaženja anti-bot blokada
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Navigating to login page: {LOGIN_URL}...")
        page.goto(LOGIN_URL, wait_until="networkidle")

        # -------------------------------------------------------------
        # 1. PRIHVATANJE KOLAČIĆA (COOKIE BANNER)
        # -------------------------------------------------------------
        try:
            cookie_btn = page.query_selector("button:has-text('Accept'), button:has-text('Agree'), #onetrust-accept-btn-handler")
            if cookie_btn:
                print("Accepting cookies banner...")
                cookie_btn.click()
                page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Cookie banner check passed/skipped: {e}")

        # -------------------------------------------------------------
        # 2. UNOS KREDENCIJALA (PROŠIRENI SELEKTORI & LOCATOR.FIRST)
        # -------------------------------------------------------------
        print("Entering email...")
        email_selector = "input[name='username'], input[id*='username'], input[name*='email'], input[id*='email'], input[type='email'], input[type='text']"
        page.wait_for_selector(email_selector, state="visible", timeout=15000)
        page.locator(email_selector).first.fill(EMAIL)

        print("Entering password...")
        password_selector = "input[type='password'], input[name='password'], input[id*='password']"
        page.wait_for_selector(password_selector, state="visible", timeout=10000)
        page.locator(password_selector).first.fill(PASSWORD)

        print("Clicking submit button...")
        submit_selector = "button[type='submit'], input[type='submit'], button:has-text('Log in'), button:has-text('Login'), #loginBtn"
        page.locator(submit_selector).first.click()

        # Čekanje da se autentifikacija obradi
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # -------------------------------------------------------------
        # 3. NAVIGACIJA NA TARGET STRANICU SA PRIJAVAMA
        # -------------------------------------------------------------
        print(f"Navigating to target page: {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="networkidle")
        
        # Čekanje od 5s da se JavaScript tabela sa statusom u potpunosti izrenderuje
        page.wait_for_timeout(5000)

        page_content = page.content()
        page_text_lower = page_content.lower()

        # -------------------------------------------------------------
        # 4. SIGURNOSNA PROVJERA (SPREČAVANJE LAŽNIH ALARMA USLJED RE-DIRECTA)
        # -------------------------------------------------------------
        if "already registered?" in page_text_lower or "forgot your password?" in page_text_lower:
            print("❌ UPOZORENJE: Skripta je preusmjerena na Login stranicu! (Sesija nije uspjela ili postoji rate-limit)")
            print("Status provjera preskočena kako se ne bi slali lažni alarmi.")
            
            with open("login_failed_debug.html", "w", encoding="utf-8") as f:
                f.write(page_content)
                
            browser.close()
            return

        # -------------------------------------------------------------
        # 5. DETEKCIJA PROMJENE STATUSES
        # -------------------------------------------------------------
        has_under_review = "application under review" in page_text_lower
        print(f"Has 'Application Under Review': {has_under_review}")

        if has_under_review:
            print("Current detected status: Application Under Review")
            print("State synchronized: Nema promjene statusa.")
        else:
            print("⚠️ DETEKOVANA PROMJENA STATUS / STATUS_CHANGED!")
            
            # Sačuvaj HTML dump za detaljnu analizu u slučaju promjene
            with open("status_change_debug.html", "w", encoding="utf-8") as f:
                f.write(page_content)

            detected_status = "STATUS_CHANGED (Potrebna ručna provjera na portalu)"
            if "under process" in page_text_lower:
                detected_status = "Application Under Process"
            elif "shortlisted" in page_text_lower:
                detected_status = "Shortlisted"
            elif "interview" in page_text_lower:
                detected_status = "Interview Scheduled / Invited"

            print(f"Novi identifikovani status: {detected_status}")
            send_alert_email(detected_status)

        browser.close()

if __name__ == "__main__":
    run_checker()
