#!/usr/bin/env python3
"""
Idealista Valencia Bot
Scrape les nouvelles annonces longue durée et notifie via Telegram.
"""

import os
import json
import time
import sqlite3
import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TON_TOKEN_ICI")
CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID", "TON_CHAT_ID_ICI")
DB_PATH        = os.path.join(os.path.dirname(__file__), "annonces.db")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "3600"))  # secondes (défaut 1h)

# ─── CRITÈRES ─────────────────────────────────────────────────────────────────

# URL de recherche Idealista — longue durée, Valencia, 3ch+, 2SDB+, meublé, terrasse, max 1900€
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── DATABASE ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS annonces (
            id TEXT PRIMARY KEY,
            titre TEXT,
            prix TEXT,
            url TEXT,
            vu_le TEXT
        )
    """)
    conn.commit()
    conn.close()

def est_nouvelle(annonce_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id FROM annonces WHERE id = ?", (annonce_id,)).fetchone()
    conn.close()
    return row is None

def sauvegarder(annonce: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO annonces (id, titre, prix, url, vu_le) VALUES (?, ?, ?, ?, ?)",
        (annonce["id"], annonce["titre"], annonce["prix"], annonce["url"], datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# ─── SCRAPING ─────────────────────────────────────────────────────────────────

def scrape_annonces() -> list[dict]:
    """Scrape la page de résultats Idealista et retourne les annonces."""
    try:
        resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Erreur HTTP : {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    annonces = []

    articles = soup.select("article.item")
    if not articles:
        # Fallback si structure différente
        articles = soup.select("[class*='item-info-container']")

    for article in articles:
        try:
            # ID de l'annonce
            annonce_id = article.get("data-adid") or article.get("data-element-id")
            if not annonce_id:
                link_tag = article.select_one("a.item-link, a[href*='/inmueble/']")
                if link_tag:
                    href = link_tag.get("href", "")
                    annonce_id = href.strip("/").split("/")[-1]
            if not annonce_id:
                continue

            # Titre
            titre_tag = article.select_one(".item-title, h2.item-title a, a.item-link")
            titre = titre_tag.get_text(strip=True) if titre_tag else "Sans titre"

            # Prix
            prix_tag = article.select_one(".item-price, .price-row")
            prix = prix_tag.get_text(strip=True) if prix_tag else "Prix inconnu"

            # URL
            link_tag = article.select_one("a.item-link, a[href*='/inmueble/']")
            url = "https://www.idealista.com" + link_tag["href"] if link_tag else SEARCH_URL

            # Détails (m², chambres, étage)
            details_tags = article.select(".item-detail")
            details = " · ".join(d.get_text(strip=True) for d in details_tags) if details_tags else ""

            # Zone / quartier
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
            log.warning(f"Erreur parsing annonce : {e}")
            continue

    log.info(f"{len(annonces)} annonces trouvées sur la page")
    return annonces

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def envoyer_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Erreur Telegram : {e}")

def formater_message(annonce: dict) -> str:
    lignes = [
        f"🏠 <b>{annonce['titre']}</b>",
        f"💶 <b>{annonce['prix']}</b>",
    ]
    if annonce.get("zone"):
        lignes.append(f"📍 {annonce['zone']}")
    if annonce.get("details"):
        lignes.append(f"📐 {annonce['details']}")
    lignes.append(f"🔗 <a href=\"{annonce['url']}\">Voir l'annonce</a>")
    return "\n".join(lignes)

# ─── BOUCLE PRINCIPALE ────────────────────────────────────────────────────────

def verifier_nouvelles_annonces():
    log.info("Vérification des nouvelles annonces...")
    annonces = scrape_annonces()
    nouvelles = 0

    for annonce in annonces:
        if est_nouvelle(annonce["id"]):
            log.info(f"Nouvelle annonce : {annonce['id']} — {annonce['titre']}")
            message = formater_message(annonce)
            envoyer_telegram(message)
            sauvegarder(annonce)
            nouvelles += 1
            time.sleep(1)  # petite pause entre messages

    if nouvelles == 0:
        log.info("Aucune nouvelle annonce.")
    else:
        log.info(f"{nouvelles} nouvelles annonces envoyées.")

def main():
    log.info("🤖 Démarrage du bot Idealista Valencia")
    log.info(f"Intervalle de vérification : {CHECK_INTERVAL}s ({CHECK_INTERVAL//3600}h)")
    init_db()

    # Premier check immédiat au démarrage
    verifier_nouvelles_annonces()

    while True:
        log.info(f"Prochain check dans {CHECK_INTERVAL // 60} minutes...")
        time.sleep(CHECK_INTERVAL)
        verifier_nouvelles_annonces()

if __name__ == "__main__":
    main()
