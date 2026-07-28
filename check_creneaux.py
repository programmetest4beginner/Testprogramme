"""
Surveillance des créneaux de rendez-vous Doctolib pour le cabinet NORDERM.

Ce script reproduit le parcours manuel de prise de rendez-vous jusqu'à la
dernière étape, sans jamais réserver quoi que ce soit et sans jamais se
connecter à un compte Doctolib (parcours "invité"). Si le texte
"Aucune disponibilité en ligne" n'apparaît plus, un créneau est probablement
disponible : une notification Telegram est envoyée.

Ne fait AUCUNE réservation automatique. Ne contourne aucune protection
(CAPTCHA, limitation de fréquence) : si le site bloque ou change de
structure, le script échoue simplement et prévient au lieu d'insister.
"""

import os
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DOCTOLIB_URL = "https://www.doctolib.fr/cabinet-medical/lambersart/norderm"
NO_SLOT_TEXT = "Aucune disponibilité en ligne"

# Récupérés depuis les secrets GitHub (jamais écrits en dur dans le code)
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
    except Exception as e:
        print(f"Erreur d'envoi Telegram : {e}")


def check_creneaux() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(DOCTOLIB_URL, timeout=30000)

            # 1. "PRENDRE RENDEZ-VOUS"
            page.get_by_text("PRENDRE RENDEZ-VOUS", exact=False).first.click(timeout=15000)

            # 2. "Avez-vous déjà consulté un soignant de cet établissement ?" -> Non
            page.get_by_text("Non", exact=True).first.click(timeout=15000)

            # 3. Catégorie
            page.get_by_text("CONSULTATION", exact=True).first.click(timeout=15000)

            # 4. Motif
            page.get_by_text("Consultation de dermatologie", exact=False).first.click(timeout=15000)

            # 5. Soignant
            page.get_by_text("Je n'ai pas de préférence", exact=False).first.click(timeout=15000)

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
            send_telegram(
                "⚠️ Le script de surveillance NORDERM a rencontré une erreur "
                "(Doctolib a peut-être changé sa page). Vérifie manuellement "
                "et préviens-moi si ça persiste."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    check_creneaux()
