"""
wa_leads_bot.py
Bot che ogni giorno aggiunge 30 lead per collaboratore in Firebase wa_leads.
Usa Outscraper per cercare attività su Google Maps (stesso flusso del bot email).
Hostato su Render come cron job — gira ogni mattina alle 09:00 ora italiana.

ENV vars necessarie su Render:
  OUTSCRAPER_KEY     → API key Outscraper
  FIREBASE_KEY       → JSON della service account Firebase (tutto su una riga)

Collections Firebase usate:
  wa_leads           → leads WhatsApp (letti dal CRM)
  wa_bot_stato       → tiene traccia delle città già processate
"""

import os
import json
import time
import random
import logging
from datetime import datetime, date

import requests
from outscraper import ApiClient
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────────

COLLABORATORI = ["fabio", "mattia", "jacopo", "emanuele"]
LEADS_PER_COLLAB = 30          # 30 a testa → 120 totali al giorno

# Stesse nicchie del bot email — una per collaboratore (ruota ogni giorno)
NICCHIE = {
    "fabio":    ["impresa edile", "costruzioni", "ristrutturazioni", "geometra", "impianti elettrici"],
    "mattia":   ["parrucchiere", "barbiere", "salone di bellezza", "hair stylist"],
    "jacopo":   ["centro estetico", "estetista", "nail art", "spa", "centro benessere"],
    "emanuele": ["consulente finanziario", "commercialista", "studio legale", "agenzia immobiliare"],
}

# Città da cui pescare — ruota ogni giorno
CITTA = [
    "Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze", "Palermo",
    "Catania", "Bari", "Venezia", "Verona", "Padova", "Brescia", "Bergamo",
    "Modena", "Parma", "Reggio Emilia", "Genova", "Trieste", "Cagliari",
    "Sassari", "Messina", "Catanzaro", "Salerno", "Foggia", "Pescara",
    "Ancona", "Perugia", "Trento", "Bolzano",
]

MAX_DAILY_CALLS = 5   # max chiamate Outscraper al giorno (risparmio crediti)

# ─── FIREBASE INIT ─────────────────────────────────────────────────────────────

def init_firebase():
    key_json = os.environ.get("FIREBASE_KEY")
    if not key_json:
        raise RuntimeError("FIREBASE_KEY non impostata")
    cred_dict = json.loads(key_json)
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# ─── STATO BOT ─────────────────────────────────────────────────────────────────

def get_stato(db):
    """Legge lo stato del bot da Firestore."""
    ref = db.collection("wa_bot_stato").document("progress")
    doc = ref.get()
    if doc.exists:
        return doc.to_dict()
    return {"citta_index": 0, "nicchia_index": {c: 0 for c in COLLABORATORI}}

def save_stato(db, stato):
    db.collection("wa_bot_stato").document("progress").set(stato)

# ─── OUTSCRAPER ────────────────────────────────────────────────────────────────

def cerca_attivita(client, nicchia, citta, limit=40):
    """Cerca attività su Google Maps via Outscraper. Restituisce lista di dict."""
    query = f"{nicchia} a {citta}, Italia"
    log.info(f"Outscraper: '{query}' limit={limit}")
    try:
        results = client.google_maps_search(
            [query],
            limit=limit,
            language="it",
            fields=["name", "phone", "full_address", "city", "category"]
        )
        if results and isinstance(results[0], list):
            return results[0]
        return results or []
    except Exception as e:
        log.error(f"Outscraper error: {e}")
        return []

def estrai_numero(attivita):
    """Estrai e normalizza il numero di telefono."""
    tel = attivita.get("phone") or attivita.get("phone_1") or ""
    tel = tel.replace(" ", "").replace("-", "").replace("+39", "").replace("(", "").replace(")", "")
    # Mantieni solo numeri
    tel = "".join(c for c in tel if c.isdigit())
    # Scarta numeri fissi (iniziano con 0) o troppo corti
    if not tel or len(tel) < 9 or tel.startswith("0"):
        return ""
    return tel

# ─── DEDUPLICAZIONE ────────────────────────────────────────────────────────────

def get_numeri_esistenti(db):
    """Recupera tutti i numeri già in wa_leads per evitare duplicati."""
    docs = db.collection("wa_leads").stream()
    numeri = set()
    for d in docs:
        data = d.to_dict()
        t = data.get("tel", "").replace(" ", "")
        if t:
            numeri.add(t)
    return numeri

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=== WA LEADS BOT START ===")

    outscraper_key = os.environ.get("OUTSCRAPER_KEY")
    if not outscraper_key:
        raise RuntimeError("OUTSCRAPER_KEY non impostata")

    db = init_firebase()
    client = ApiClient(api_key=outscraper_key)
    stato = get_stato(db)
    oggi = date.today().isoformat()

    log.info(f"Stato corrente: {stato}")

    # Controlla se ha già girato oggi
    if stato.get("last_run") == oggi:
        log.info("Bot già eseguito oggi, skip.")
        return

    numeri_esistenti = get_numeri_esistenti(db)
    log.info(f"Numeri già in wa_leads: {len(numeri_esistenti)}")

    citta_idx = stato.get("citta_index", 0)
    nicchia_idx = stato.get("nicchia_index", {c: 0 for c in COLLABORATORI})

    chiamate_fatte = 0
    totale_aggiunti = 0

    for collab in COLLABORATORI:
        if chiamate_fatte >= MAX_DAILY_CALLS:
            log.warning("Limite chiamate Outscraper raggiunto")
            break

        nicchie_collab = NICCHIE[collab]
        nic_i = nicchia_idx.get(collab, 0) % len(nicchie_collab)
        nicchia = nicchie_collab[nic_i]
        citta = CITTA[citta_idx % len(CITTA)]

        log.info(f"[{collab.upper()}] nicchia='{nicchia}' città='{citta}'")

        attivita = cerca_attivita(client, nicchia, citta, limit=60)
        chiamate_fatte += 1

        # Filtra: devono avere numero mobile
        valide = []
        for a in attivita:
            tel = estrai_numero(a)
            if not tel:
                continue
            if tel in numeri_esistenti:
                continue
            valide.append((a, tel))
            if len(valide) >= LEADS_PER_COLLAB:
                break

        log.info(f"[{collab}] Trovati {len(attivita)} totali, {len(valide)} validi nuovi")

        # Scrivi su Firebase
        batch = db.batch()
        aggiunti = 0
        for a, tel in valide:
            ref = db.collection("wa_leads").document()
            batch.set(ref, {
                "nome":    a.get("name", ""),
                "tel":     tel,
                "nicchia": nicchia,
                "citta":   citta,
                "collab":  collab,
                "stato":   "da_cont",
                "data":    datetime.now().strftime("%d/%m/%Y"),
                "ts":      int(time.time() * 1000),
                "source":  "bot_wa",
                "query":   f"{nicchia} a {citta}",
            })
            numeri_esistenti.add(tel)  # evita duplicati nello stesso batch
            aggiunti += 1

        batch.commit()
        totale_aggiunti += aggiunti
        log.info(f"[{collab}] Aggiunti {aggiunti} lead in wa_leads")

        # Aggiorna indici
        nicchia_idx[collab] = (nic_i + 1) % len(nicchie_collab)
        time.sleep(2)  # pausa tra chiamate Outscraper

    # Avanza città per il giorno dopo
    citta_idx = (citta_idx + 1) % len(CITTA)

    # Salva stato
    stato_nuovo = {
        "citta_index":  citta_idx,
        "nicchia_index": nicchia_idx,
        "last_run":     oggi,
        "leads_aggiunti_oggi": totale_aggiunti,
    }
    save_stato(db, stato_nuovo)
    log.info(f"=== FINE — {totale_aggiunti} lead aggiunti ===")

if __name__ == "__main__":
    main()
