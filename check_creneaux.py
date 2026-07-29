import os
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DOCTOLIB_URL = (
    "https://www.doctolib.fr/cabinet-medical/lambersart/norderm/booking/availabilities"
    "?specialityId=6&telehealth=false&placeId=practice-570485&isNewPatient=true"
    "&isNewPatientBlocked=false&motiveCategoryIds%5B%5D=325151"
    "&motiveIds%5B%5D=11853301&practitionerId=NO_PREFERENCE"
    "&profile_skipped=false&source=profile"
)
NO_SLOT_TEXT = "Aucune disponibilité en ligne"

# Récupérés depuis les secrets GitHub (jamais écrits en dur dans le code)
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


SCREENSHOT_PATH = "error.png"


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
    except Exception as e:
        print(f"Erreur d'envoi Telegram : {e}")


def accept_cookies_if_present(page) -> None:
    """Ferme le bandeau de cookies Didomi via son API JavaScript officielle
    (plus fiable qu'un clic simulé), avec un repli sur un clic si l'API
    n'est pas détectée."""
    try:
        page.wait_for_function("() => window.Didomi !== undefined", timeout=8000)
        page.evaluate(
            "window.Didomi.setUserAgreeToAll();"
            "if (window.Didomi.notice) { window.Didomi.notice.hide(); }"
        )
        page.wait_for_timeout(1000)
        print("Consentement cookies accepté via l'API Didomi.")
        return
    except PlaywrightTimeoutError:
        print("API Didomi non détectée, tentative de fermeture par clic...")

    page.wait_for_timeout(1500)
    for frame in page.frames:
        for text in ["ACCEPTER", "Tout accepter", "Accepter tout", "Accepter", "J'accepte"]:
            try:
                frame.get_by_text(text, exact=False).first.click(timeout=4000, force=True)
                print(f"Bandeau cookies fermé via '{text}' (frame : {frame.url})")
                return
            except PlaywrightTimeoutError:
                continue
    print("Aucun bandeau de cookies fermé (API absente et clic infructueux).")


def click_text(page, text: str, exact: bool = False, timeout: int = 15000) -> None:
    """Clique sur un texte donné ; si ça échoue, retente après avoir fermé un
    éventuel bandeau de cookies apparu entre-temps."""
    try:
        page.get_by_text(text, exact=exact).first.click(timeout=timeout)
    except PlaywrightTimeoutError:
        print(f"Clic sur '{text}' a échoué au premier essai, nouvelle tentative après fermeture d'un éventuel bandeau...")
        accept_cookies_if_present(page)
        page.get_by_text(text, exact=exact).first.click(timeout=timeout)


def check_creneaux() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Émule un téléphone Android, pour reproduire la mise en page vue manuellement
        context = browser.new_context(
            viewport={"width": 412, "height": 915},
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
            ),
            locale="fr-FR",
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        try:
            page.goto(DOCTOLIB_URL, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            accept_cookies_if_present(page)

            # 1. Motif
            click_text(page, "Consultation de dermatologie")

            # 2. Soignant
            click_text(page, "Je n'ai pas de préférence")

            page.wait_for_timeout(2000)  # laisser la page finir de charger
            page_text = page.content()

            if NO_SLOT_TEXT in page_text:
                print("Aucun créneau disponible.")
            else:
                print("Un créneau semble disponible !")
                send_telegram(
                    "🚨 Un créneau semble disponible chez NORDERM (dermatologue) !\n"
                    f"{DOCTOLIB_URL}"
                )
        except PlaywrightTimeoutError as e:
            print(f"Timeout pendant le parcours : {e}")
            try:
                page.screenshot(path=SCREENSHOT_PATH, full_page=True)
                print(f"Capture d'écran enregistrée : {SCREENSHOT_PATH}")
            except Exception as screenshot_error:
                print(f"Impossible de prendre une capture : {screenshot_error}")
            send_telegram(
                "⚠️ Le script de surveillance NORDERM a rencontré une erreur "
                "(Doctolib a peut-être changé sa page). Une capture d'écran "
                "est disponible dans l'onglet Artifacts du run GitHub Actions."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    check_creneaux()