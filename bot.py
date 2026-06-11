#!/usr/bin/env python3
"""
Idealista Valencia Bot — GitHub Actions version
S'exécute une fois, envoie les nouvelles annonces, puis s'arrête.
"""

import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE      = "seen_ids.json"

# ─── CRITÈRES ─────────────────────────────────────────────────────────────────

SEARCH_URL = (
    "https://www.idealista.com/alquiler-viviendas/valencia-valencia/"
    "con-precio-hasta_1900,habitaciones-3-4-5-mas-de-5,"
    "banos-2-mas-de-2,amueblado,con-terraza,larga-temporada,"
    "metros-cuadrados-mas-de_100/"
    "?ordenado-por=fecha-publicacion-desc"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.idealista.com/",
}

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─── SEEN IDS (fichier JSON committé dans le repo) ────────────────────────────

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ─── SCRAPING ─────────────────────────────────────────────────────────────────

def scrape_annonces() -> list:
    try:
        resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Erreur HTTP : {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    annonces = []

    for article in soup.select("article.item"):
        try:
            annonce_id = article.get("data-adid") or article.get("data-element-id")
            if not annonce_id:
                link_tag = article.select_one("a.item-link, a[href*='/inmueble/']")
                if link_tag:
                    href = link_tag.get("href", "")
                    annonce_id = href.strip("/").split("/")[-1]
            if not annonce_id:
                continue

            titre_tag = article.select_one(".item-title, h2.item-title a, a.item-link")
            titre = titre_tag.get_text(strip=True) if titre_tag else "Sans titre"

            prix_tag = article.select_one(".item-price, .price-row")
            prix = prix_tag.get_text(strip=True) if prix_tag else "Prix inconnu"

            link_tag = article.select_one("a.item-link, a[href*='/inmueble/']")
            url = "https://www.idealista.com" + link_tag["href"] if link_tag else SEARCH_URL

            details_tags = article.select(".item-detail")
            details = " · ".join(d.get_text(strip=True) for d in details_tags) if details_tags else ""

            zone_tag = article.select_one(".item-detail-location, .item-location")
            zone = zone_tag.get_text(strip=True) if zone_tag else ""

            annonces.append({
                "id": str(annonce_id),
                "titre": titre,
                "prix": prix,
                "details": details,
                "zone": zone,
                "url": url,
            })
        except Exception as e:
            log.warning(f"Erreur parsing : {e}")
            continue

    log.info(f"{len(annonces)} annonces trouvées")
    return annonces

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def envoyer_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Erreur Telegram : {e}")

def formater_message(annonce: dict) -> str:
    lignes = [f"🏠 <b>{annonce['titre']}</b>", f"💶 <b>{annonce['prix']}</b>"]
    if annonce.get("zone"):
        lignes.append(f"📍 {annonce['zone']}")
    if annonce.get("details"):
        lignes.append(f"📐 {annonce['details']}")
    lignes.append(f"🔗 <a href=\"{annonce['url']}\">Voir l'annonce</a>")
    return "\n".join(lignes)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log.info("🔍 Vérification des nouvelles annonces...")
    seen = load_seen()
    annonces = scrape_annonces()
    nouvelles = 0

    for annonce in annonces:
        if annonce["id"] not in seen:
            log.info(f"Nouvelle : {annonce['id']} — {annonce['titre']}")
            envoyer_telegram(formater_message(annonce))
            seen.add(annonce["id"])
            nouvelles += 1
            time.sleep(1)

    save_seen(seen)
    log.info(f"✅ {nouvelles} nouvelles annonces envoyées.")

if __name__ == "__main__":
    main()
