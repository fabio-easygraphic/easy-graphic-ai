#!/usr/bin/env python3
"""
Easy Graphic AI — Bot email outreach
Cerca attività su Google Maps, manda email con proposta sito gratuito,
salva in Firebase Firestore per il CRM.

ENV vars su Render:
  OUTSCRAPER_KEY   → chiave API Outscraper
  GMAIL_USER       → email mittente (es. a.f.easygraphic@gmail.com)
  GMAIL_PASSWORD   → password app Gmail (non la password normale)
  LINK_SITO        → https://easy-graphic.it
"""

import os, json, time, smtplib, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG ──────────────────────────────────────────────────────
CHIAVE_SCRAPER = os.environ.get('OUTSCRAPER_KEY', '')
UTENTE_GMAIL   = os.environ.get('GMAIL_USER', '')
PASSWORD_GMAIL = os.environ.get('GMAIL_PASSWORD', '')
PROGETTO_FIREBASE = 'easy-graphic-8a7eb'
URL_FIREBASE   = f'https://firestore.googleapis.com/v1/projects/{PROGETTO_FIREBASE}/databases/(default)/documents'
LINK_SITO      = os.environ.get('LINK_SITO', 'https://easy-graphic.it')

# Nicchie per collaboratore
NICCHIE = {
    'Mattia':   'parrucchiere',
    'Jacopo':   'centro estetico',
    'Emanuele': 'consulente',
    'Fabio':    'impresa edile',
}

# Città — ruota ogni giorno
CITTA_NORD   = ['Milano', 'Torino', 'Bologna', 'Venezia', 'Genova', 'Verona', 'Padova', 'Brescia', 'Bergamo', 'Modena', 'Parma', 'Trieste', 'Trento']
CITTA_CENTRO = ['Roma', 'Firenze', 'Ancona', 'Perugia', 'Pescara']
CITTA_SUD    = ['Napoli', 'Bari', 'Palermo', 'Catania', 'Messina', 'Salerno', 'Catanzaro', 'Foggia', 'Cagliari', 'Sassari']
ALL_CITTA    = CITTA_NORD + CITTA_CENTRO + CITTA_SUD

LEAD_PER_MEMBRO = 30  # lead al giorno per collaboratore

# ── FIREBASE ────────────────────────────────────────────────────

def firebase_get(collection, doc_id):
    url = f"{URL_FIREBASE}/{collection}/{doc_id}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

def firebase_set(collection, doc_id, data):
    url = f"{URL_FIREBASE}/{collection}/{doc_id}"
    fields = {k: _val(v) for k, v in data.items()}
    r = requests.patch(url, json={"fields": fields}, timeout=10)
    return r.status_code in (200, 201)

def firebase_add(collection, data):
    url = f"{URL_FIREBASE}/{collection}"
    fields = {k: _val(v) for k, v in data.items()}
    r = requests.post(url, json={"fields": fields}, timeout=10)
    return r.status_code in (200, 201)

def firebase_query(collection, field, value):
    url = f"https://firestore.googleapis.com/v1/projects/{PROGETTO_FIREBASE}/databases/(default)/documents:runQuery"
    body = {"structuredQuery": {
        "from": [{"collectionId": collection}],
        "where": {"fieldFilter": {"field": {"fieldPath": field}, "op": "EQUAL", "value": _val(value)}}
    }}
    r = requests.post(url, json=body, timeout=10)
    if r.status_code == 200:
        return [d['document'] for d in r.json() if 'document' in d]
    return []

def _val(v):
    if isinstance(v, bool):   return {"booleanValue": v}
    if isinstance(v, int):    return {"integerValue": str(v)}
    if isinstance(v, float):  return {"doubleValue": v}
    if isinstance(v, str):    return {"stringValue": v}
    return {"stringValue": str(v)}

def _read(fields, key, default=''):
    f = fields.get(key, {})
    return f.get('stringValue', f.get('integerValue', f.get('booleanValue', default)))

# ── STATO BOT ───────────────────────────────────────────────────

def get_stato():
    doc = firebase_get('ai_stato', 'progress')
    if doc and 'fields' in doc:
        f = doc['fields']
        return {
            'citta_index': int(_read(f, 'citta_index', 0)),
        }
    return {'citta_index': 0}

def save_stato(stato):
    firebase_set('ai_stato', 'progress', {'citta_index': stato['citta_index']})

# ── OUTSCRAPER ──────────────────────────────────────────────────

def nome_breve(nome_completo):
    """Estrai solo il nome dell'attività, senza indirizzo."""
    return nome_completo.split(',')[0].split(' - ')[0].strip() if nome_completo else ''

def cerca_attivita(nicchia, citta, limit=50):
    """Cerca attività su Google Maps via Outscraper."""
    if not CHIAVE_SCRAPER:
        log.error("OUTSCRAPER_KEY non impostata")
        return []
    
    url = "https://api.app.outscraper.com/maps/search-v3"
    params = {
        "query": f"{nicchia} {citta} Italia",
        "limit": limit,
        "language": "it",
        "fields": "name,full_address,email,phone,website",
        "apiKey": CHIAVE_SCRAPER,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results = data.get('data', [])
        if isinstance(results, list) and results and isinstance(results[0], list):
            results = results[0]
        log.info(f"Outscraper: {len(results)} risultati per '{nicchia} {citta}'")
        return results
    except Exception as e:
        log.error(f"Outscraper error: {e}")
        return []

def estrai_email(attivita):
    """Estrai email dal risultato Outscraper."""
    email = attivita.get('email', '') or ''
    if isinstance(email, list):
        email = email[0] if email else ''
    email = str(email).strip().lower()
    if '@' in email and '.' in email.split('@')[-1]:
        return email
    return ''

# ── EMAIL ────────────────────────────────────────────────────────

def build_email(nome_attivita, nicchia, citta, ha_sito=False):
    """
    ha_sito=False → attività senza sito web
    ha_sito=True  → attività con sito già esistente (versione migliorata)
    """

    if not ha_sito:
        # ── VARIANTE A: niente sito ──────────────────────────────
        oggetto = f"Ho preparato una bozza del sito per {nome_attivita}"
        corpo = f"""Buongiorno,

ho trovato la sua attività online e, guardando come lavorate, ho notato una grande potenzialità che al momento non viene sfruttata: la mancanza di un sito web adeguato.

Non voglio farle perdere tempo, quindi sono andato direttamente al sodo: ho preparato gratuitamente una bozza di come potrebbe essere il sito web di {nome_attivita} — pensata su misura per il settore {nicchia}.

L'idea è semplice: se la bozza le piace, la personalizziamo insieme al 100% e la rendiamo sua. Se non fa per lei, nessun problema — nessun impegno, nessun costo.

Basterebbe una chiamata veloce di 15 minuti per mostrargliela e capire insieme se c'è margine di collaborazione.

Può rispondere a questa email oppure scriverci direttamente su WhatsApp al 351 994 3497 — rispondo personalmente.

Le va?

Fabio — Easy Graphic
{LINK_SITO} | WhatsApp 351 994 3497
"""

    else:
        # ── VARIANTE B: ha già un sito ───────────────────────────
        oggetto = f"Ho rifatto il sito di {nome_attivita} — vuole vederlo?"
        corpo = f"""Buongiorno,

ho visitato il sito di {nome_attivita} e, da grafico, ho visto subito diversi margini di miglioramento — soprattutto in termini di design moderno, velocità e resa su mobile.

Così, senza impegno, ho preparato gratuitamente una versione rinnovata: stessa attività, stesso contenuto, ma con una veste grafica più professionale e pensata per convertire meglio i visitatori in clienti.

Se le fa curiosità vederla, bastano 15 minuti in una chiamata veloce — nessun costo, nessun obbligo.

Può rispondere a questa email oppure scriverci direttamente su WhatsApp al 351 994 3497 — rispondo personalmente.

Se poi le piace, la rendiamo sua al 100%.

Le va di darci un'occhiata?

Fabio — Easy Graphic
{LINK_SITO} | WhatsApp 351 994 3497
"""

    return oggetto, corpo

def manda_email(destinatario, oggetto, corpo):
    """Invia email via Gmail SMTP."""
    if not UTENTE_GMAIL or not PASSWORD_GMAIL:
        log.error("GMAIL_USER o GMAIL_PASSWORD non impostati")
        return False
    try:
        msg = MIMEMultipart()
        msg['From']    = UTENTE_GMAIL
        msg['To']      = destinatario
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(UTENTE_GMAIL, PASSWORD_GMAIL)
            s.sendmail(UTENTE_GMAIL, destinatario, msg.as_string())
        return True
    except Exception as e:
        log.error(f"Email error a {destinatario}: {e}")
        return False

# ── MAIN ─────────────────────────────────────────────────────────

def main():
    log.info("=== EASY GRAPHIC AI BOT START ===")
    
    stato = get_stato()
    citta_idx = stato['citta_index']
    oggi = datetime.now().strftime('%d/%m/%Y')
    ts_now = int(time.time() * 1000)
    ts_domani = ts_now + 86400000  # +24h
    
    # Controlla email già mandate oggi (evita riavvii doppi)
    gia_oggi = firebase_query('leads_pending', 'data_invio', oggi)
    if len(gia_oggi) >= len(NICCHIE) * LEAD_PER_MEMBRO * 0.5:
        log.info(f"Bot già eseguito oggi ({len(gia_oggi)} lead), skip.")
        return
    
    totale_inviati = 0
    
    for collab, nicchia in NICCHIE.items():
        citta = ALL_CITTA[citta_idx % len(ALL_CITTA)]
        log.info(f"[{collab}] nicchia='{nicchia}' città='{citta}'")
        
        # Cerca attività
        attivita = cerca_attivita(nicchia, citta, limit=80)
        
        # Email già contattate (evita duplicati)
        gia_contattati = set()
        esistenti = firebase_query('emaillist', 'collab', collab)
        for doc in esistenti:
            f = doc.get('fields', {})
            e = _read(f, 'email')
            if e: gia_contattati.add(e.lower())
        
        inviati = 0
        for a in attivita:
            if inviati >= LEAD_PER_MEMBRO:
                break
            
            email = estrai_email(a)
            if not email or email in gia_contattati:
                continue
            
            nome = nome_breve(a.get('name', ''))
            if not nome:
                continue
            
            # Determina se ha già un sito
            sito = str(a.get('website', '') or '').strip()
            ha_sito = bool(sito and sito.startswith('http') and len(sito) > 10)

            # Manda email (variante diversa in base alla presenza del sito)
            oggetto, corpo = build_email(nome, nicchia, citta, ha_sito=ha_sito)
            if not manda_email(email, oggetto, corpo):
                continue
            
            gia_contattati.add(email)
            inviati += 1
            totale_inviati += 1
            
            # Salva in leads_pending (passa in emaillist dopo 24h)
            firebase_add('leads_pending', {
                'nome':        nome,
                'email':       email,
                'nicchia':     nicchia,
                'citta':       citta,
                'collab':      collab,
                'chiusoDa':    collab.lower(),
                'data_invio':  oggi,
                'ts':          ts_now,
                'promuovi_ts': ts_domani,
                'esitoChiamata': 'dc',
                'chiamato':    False,
                'ha_sito':     ha_sito,
                'sito_url':    sito if ha_sito else '',
            })
            
            log.info(f"  ✓ Email inviata a {nome} ({email})")
            time.sleep(2)  # pausa tra invii
        
        log.info(f"[{collab}] {inviati} email inviate")
        citta_idx += 1
        time.sleep(3)
    
    # Promuovi leads_pending → emaillist (quelli di ieri)
    promossi = 0
    pending = firebase_query('leads_pending', 'esitoChiamata', 'dc')
    for doc in pending:
        f = doc.get('fields', {})
        promuovi_ts = int(_read(f, 'promuovi_ts', 0))
        if promuovi_ts and promuovi_ts <= ts_now:
            # Sposta in emaillist
            data = {k: _read(f, k) for k in ['nome', 'email', 'nicchia', 'citta', 'collab', 'chiusoDa', 'data_invio', 'esitoChiamata']}
            data['ts'] = ts_now
            if firebase_add('emaillist', data):
                # Elimina da leads_pending
                doc_id = doc.get('name', '').split('/')[-1]
                requests.delete(f"{URL_FIREBASE}/leads_pending/{doc_id}", timeout=10)
                promossi += 1
    
    # Aggiorna stato (avanza città)
    save_stato({'citta_index': citta_idx})
    
    log.info(f"=== FINE — {totale_inviati} email inviate, {promossi} lead promossi in emaillist ===")

if __name__ == "__main__":
    main()
