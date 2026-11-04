import os
import re
from playwright.sync_api import sync_playwright

# Konfiguracija iz Environment Variables (GitHub Secrets)
EMAIL = os.environ.get("EMIRATES_EMAIL")
PASSWORD = os.environ.get("EMIRATES_PASSWORD")
LOGIN_URL = "https://external.emiratesgroupcareers.com/en_US/careersmarketplace/Login"
TARGET_URL = "https://external.emiratesgroupcareers.com/en_US/careersmarketplace/ProfileJobApplications"

def run_checker():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Postavljanje standardnog User-Agenta kako nas bezbjednosni filteri ne bi tretirali kao bota
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Navigating to login page: {LOGIN_URL}...")
        page.goto(LOGIN_URL, wait_until="networkidle")

        # Prihvatanje kolačića ako se pojavio banner
        try:
            cookie_btn = page.query_selector("button:has-text('Accept'), button:has-text('Agree'), #onetrust-accept-btn-handler")
            if cookie_btn:
                print("Accepting cookies banner...")
                cookie_btn.click()
                page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Cookie banner check passed/skipped: {e}")

        # Unos kredencijala
        print("Entering email...")
        page.fill("input[type='email'], input[name='email'], input[id*='email']", EMAIL)
        
        print("Entering password...")
        page.fill("input[type='password'], input[name='password'], input[id*='password']", PASSWORD)

        print("Clicking submit button...")
        page.click("button[type='submit'], input[type='submit'], button:has-text('Log in'), button:has-text('Login')")
        
        # Čekanje da se autentifikacija završi
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        print(f"Navigating to target page: {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="networkidle")
        
        # Eksplicitno čekanje da se dinamička tabela sa prijavama učita u DOM
        page.wait_for_timeout(5000)

        page_content = page.content()
        page_text_lower = page_content.lower()

        # -------------------------------------------------------------
        # SIGURNOSNA PROVJERA: Da li smo zapravo i dalje na Login stranici?
        # -------------------------------------------------------------
        if "already registered?" in page_text_lower or "forgot your password?" in page_text_lower:
            print("❌ UPOZORENJE: Skripta je preusmjerena na Login stranicu! (Sesija nije uspjela / Rate-limit)")
            print("Status provjera preskočena kako se ne bi slali lažni alarmi.")
            # Sačuvaj HTML za analizu zašto login nije uspio
            with open("login_failed_debug.html", "w", encoding="utf-8") as f:
                f.write(page_content)
            browser.close()
            return

        # -------------------------------------------------------------
        # ANALIZA STATUSES NA PROFILU
        # -------------------------------------------------------------
        # Provjera da li postoji uobičajeni status (case-insensitive)
        has_under_review = "application under review" in page_text_lower
        
        print(f"Has 'Application Under Review': {has_under_review}")

        if has_under_review:
            print("Current detected status: Application Under Review")
            print("State synchronized: Nema promjene statusa.")
        else:
            print("⚠️ DETEKOVANA PROMJENA STATUS / STATUS_CHANGED!")
            
            # Sačuvaj tačan HTML u trenutku detekcije promjene
            with open("status_change_debug.html", "w", encoding="utf-8") as f:
                f.write(page_content)
            
            # Pokušaj izvlačenja tačnog teksta iz tabele radi preciznijeg alerta
            detected_status = "STATUS_CHANGED (Potrebna ručna provjera na portalu)"
            if "under process" in page_text_lower:
                detected_status = "Application Under Process"
            elif "shortlisted" in page_text_lower:
                detected_status = "Shortlisted"
            elif "interview" in page_text_lower:
                detected_status = "Interview Scheduled / Invited"

            print(f"Novi identifikovani status: {detected_status}")
            
            # Ovjde pozivaš tvoju funkciju za slanje maila
            send_alert_email(detected_status)

        browser.close()

def send_alert_email(new_status):
    # Ovdje zadrži tvoju postojeću logiku za slanje e-maila
    print(f"Alert email triggers for status: {new_status}")

if __name__ == "__main__":
    run_checker()
