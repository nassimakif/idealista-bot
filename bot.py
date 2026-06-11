#!/usr/bin/env python3
"""
Idealista Valencia Bot — Mobile API version
"""

import os
import json
import time
import logging
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE      = "seen_ids.json"

# Paramètres de recherche
PARAMS = {
    "operation": "rent",
    "propertyType": "homes",
    "locationId": "0-EU-ES-46",  # Valencia province
    "maxPrice": 1900,
    "minRooms": 3,
    "minBathrooms": 2,
    "minSize": 100,
    "furnished": 1,
    "hasTerrace": 1,
    "rentType": "long_term",
    "order": "publicationDate",
    "sort": "desc",
    "numPage": 1,
    "maxItems": 40,
    "locale": "es",
    "country": "es",
}

# Headers simulant l'app mobile Idealista
HEADERS = {
    "User-Agent": "Idealista/7.12.0 (iPhone; iOS 17.0; Scale/3.00)",
    "Accept": "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "X-AppVersion": "7.12.0",
    "X-DeviceOS": "iOS",
    "Connection": "keep-alive",
}

API_URL = "https://api.idealista.com/3.5/es/search"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def scrape_annonces() -> list:
    try:
        resp = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=20)
        log.info(f"Status code: {resp.status_code}")

        if resp.status_code == 403:
            log.error("Bloqué par Idealista (403). Tentative scraping HTML...")
            return scrape_html()

        resp.raise_for_status()
        data = resp.json()
        annonces = []

        for item in data.get("elementList", []):
            annonces.append({
                "id": str(item.get("propertyCode", "")),
                "titre": item.get("suggestedTexts", {}).get("title", item.get("propertyType", "Appartement")),
                "prix": f"{item.get('price', '?')}€/mois",
                "details": f"{item.get('size', '?')}m² · {item.get('rooms', '?')} ch · {item.get('bathrooms', '?')} SDB",
                "zone": item.get("address", item.get("district", "")),
                "url": item.get("url", "https://www.idealista.com"),
            })

        log.info(f"{len(annonces)} annonces trouvées via API mobile")
        return annonces

    except Exception as e:
        log.error(f"Erreur API : {e}")
        return scrape_html()

def scrape_html() -> list:
    """Fallback scraping HTML avec headers renforcés"""
    from bs4 import BeautifulSoup

    url = (
        "https://www.idealista.com/alquiler-viviendas/valencia-valencia/"
        "con-precio-hasta_1900,habitaciones-3-4-5-mas-de-5,"
        "banos-2-mas-de-2,amueblado,con-terraza,larga-temporada,"
        "metros-cuadrados-mas-de_100/"
        "?ordenado-por=fecha-publicacion-desc"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }

    try:
        session = requests.Session()
        # D'abord visiter la homepage pour avoir des cookies
        session.get("https://www.idealista.com/", headers=headers, timeout=15)
        time.sleep(2)
        resp = session.get(url, headers=headers, timeout=20)
        log.info(f"HTML status: {resp.status_code}")

        if resp.status_code != 200:
            log.error(f"HTML bloqué: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        annonces = []

        for article in soup.select("article.item"):
            try:
                annonce_id = article.get("data-adid") or article.get("data-element-id")
                if not annonce_id:
                    link = article.select_one("a[href*='/inmueble/']")
                    if link:
                        annonce_id = link["href"].strip("/").split("/")[-1]
                if not annonce_id:
                    continue

                titre = (article.select_one(".item-title a") or article.select_one("a.item-link"))
                titre = titre.get_text(strip=True) if titre else "Appartement"

                prix = article.select_one(".item-price")
                prix = prix.get_text(strip=True) if prix else "Prix inconnu"

                link = article.select_one("a[href*='/inmueble/']")
                url_ann = "https://www.idealista.com" + link["href"] if link else url

                details = " · ".join(d.get_text(strip=True) for d in article.select(".item-detail"))
                zone = article.select_one(".item-detail-location")
                zone = zone.get_text(strip=True) if zone else ""

                annonces.append({"id": str(annonce_id), "titre": titre, "prix": prix,
                                  "details": details, "zone": zone, "url": url_ann})
            except:
                continue

        log.info(f"{len(annonces)} annonces via HTML")
        return annonces

    except Exception as e:
        log.error(f"Erreur HTML : {e}")
        return []

def envoyer_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message,
                                      "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.error(f"Erreur Telegram : {e}")

def formater_message(a: dict) -> str:
    lignes = [f"🏠 <b>{a['titre']}</b>", f"💶 <b>{a['prix']}</b>"]
    if a.get("zone"): lignes.append(f"📍 {a['zone']}")
    if a.get("details"): lignes.append(f"📐 {a['details']}")
    lignes.append(f"🔗 <a href=\"{a['url']}\">Voir l'annonce</a>")
    return "\n".join(lignes)

def main():
    log.info("🔍 Vérification des nouvelles annonces...")
    seen = load_seen()
    annonces = scrape_annonces()
    nouvelles = 0

    for a in annonces:
        if a["id"] not in seen:
            log.info(f"Nouvelle : {a['id']} — {a['titre']}")
            envoyer_telegram(formater_message(a))
            seen.add(a["id"])
            nouvelles += 1
            time.sleep(1)

    save_seen(seen)
    log.info(f"✅ {nouvelles} nouvelles annonces envoyées.")

if __name__ == "__main__":
    main()
