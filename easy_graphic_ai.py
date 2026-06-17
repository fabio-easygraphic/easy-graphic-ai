#!/usr/bin/env python3
"""
Easy Graphic AI Lead Scraper + Email Sender
1. Cerca attività su Google Maps
2. Manda email commerciale al potenziale cliente
3. Dopo 24h lo mette nella dashboard (emaillist)
"""
import os, json, time, requests, datetime, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── CONFIG ────────────────────────────────────────────────────────
OUTSCRAPER_KEY  = os.environ.get('OUTSCRAPER_KEY', '')
GMAIL_USER      = os.environ.get('GMAIL_USER', '')
GMAIL_PASSWORD  = os.environ.get('GMAIL_PASSWORD', '')
FIREBASE_PROJECT = 'easy-graphic-8a7eb'
FIREBASE_URL    = f'https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)/documents'

# Link da aggiornare quando pronti
LINK_SITO      = os.environ.get('LINK_SITO', '[LINK SITO - coming soon]')
LINK_BROCHURE  = os.environ.get('LINK_BROCHURE', '[LINK BROCHURE - coming soon]')
WHATSAPP_URL   = 'https://wa.me/393934622929'

# Nicchie per collaboratore
NICCHIE = {
    'mattia':   'parrucchieri',
    'jacopo':   'centro estetico',
    'emanuele': 'consulenti',
    'fabio':    'centro massaggi',
}

CITTA_NORD = [
    'Bergamo', 'Milano', 'Torino', 'Brescia', 'Verona',
    'Bologna', 'Venezia', 'Genova', 'Padova', 'Vicenza',
    'Modena', 'Parma', 'Reggio Emilia', 'Trento', 'Trieste',
    'Novara', 'Varese', 'Como', 'Piacenza', 'Udine',
]
CITTA_CENTRO = [
    'Firenze', 'Roma', 'Perugia', 'Ancona', 'Livorno',
    'Pisa', 'Siena', 'Arezzo', 'Grosseto', 'Viterbo',
]
CITTA_SUD = [
    'Napoli', 'Bari', 'Palermo', 'Catania', 'Messina',
    'Reggio Calabria', 'Taranto', 'Brindisi', 'Salerno', 'Foggia',
]
ALL_CITTA = CITTA_NORD + CITTA_CENTRO + CITTA_SUD
LEADS_PER_MEMBRO = 25

# ── EMAIL ─────────────────────────────────────────────────────────
FIRMA_HTML = f"""
  <p style="margin-top:24px">
    <b>Easy Graphic</b><br>
    📞 +39 393 462 2929<br>
    💬 <a href="{WHATSAPP_URL}">WhatsApp diretto</a><br>
    🌐 <a href="https://www.easy-graphic.it">www.easy-graphic.it</a>
  </p>
"""
FIRMA_TESTO = f"""
Easy Graphic
+39 393 462 2929
WhatsApp: {WHATSAPP_URL}
www.easy-graphic.it
"""

def build_email(nome_attivita, ha_sito=False):
    """Sceglie l'email giusta in base a se l'attività ha gia un sito o no."""
    oggetto = "Abbiamo gia il sito pronto per te — gratis, senza impegno"

    if ha_sito:
        # ATTIVITA CON SITO — proposta di rinnovo
        corpo_html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#222;font-size:15px;line-height:1.7">
  <p>Gentile <b>{nome_attivita}</b>,</p>
  <p>mi chiamo Fabio di Easy Graphic, agenzia specializzata in digital marketing e comunicazione a 360&deg;.</p>
  <p>Ho dato un'occhiata al vostro sito attuale e ho notato che c'&egrave; molto margine per renderlo pi&ugrave; moderno ed efficace — e in un mercato sempre pi&ugrave; digitale, un sito curato pu&ograve; fare una differenza concreta nel modo in cui i clienti vi percepiscono.</p>
  <p>Per questo motivo abbiamo gi&agrave; realizzato una <b>bozza di sito rinnovata</b>, pensata appositamente per la vostra realt&agrave;. &Egrave; gratuita e senza impegno — serve semplicemente per mostrarvi in modo concreto cosa potremmo fare insieme. Qualora il progetto dovesse interessarvi, parleremo dei dettagli e dei costi in totale trasparenza.</p>
  <p>Se desiderate visionarla, &egrave; sufficiente rispondere a questa email.</p>
  <p>Cordiali saluti,</p>
  {FIRMA_HTML}
</div>
"""
        corpo_testo = f"""Gentile {nome_attivita},

mi chiamo Fabio di Easy Graphic, agenzia specializzata in digital marketing e comunicazione a 360 gradi.

Ho dato un'occhiata al vostro sito attuale e ho notato che c'e molto margine per renderlo piu moderno ed efficace — e in un mercato sempre piu digitale, un sito curato puo fare una differenza concreta nel modo in cui i clienti vi percepiscono.

Per questo motivo abbiamo gia realizzato una bozza di sito rinnovata, pensata appositamente per la vostra realta. E gratuita e senza impegno — serve semplicemente per mostrarvi in modo concreto cosa potremmo fare insieme. Qualora il progetto dovesse interessarvi, parleremo dei dettagli e dei costi in totale trasparenza.

Se desiderate visionarla, e sufficiente rispondere a questa email.

Cordiali saluti,
{FIRMA_TESTO}"""
    else:
        # ATTIVITA SENZA SITO — proposta di creazione
        corpo_html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#222;font-size:15px;line-height:1.7">
  <p>Gentile <b>{nome_attivita}</b>,</p>
  <p>mi chiamo Fabio di Easy Graphic, agenzia specializzata in digital marketing e comunicazione a 360&deg;.</p>
  <p>Analizzando la vostra presenza online, ho notato che la vostra attivit&agrave; non &egrave; ancora presente sul web con un sito proprio — e in un mercato sempre pi&ugrave; digitale, presentarsi in modo professionale pu&ograve; fare una differenza concreta nel modo in cui i clienti vi percepiscono.</p>
  <p>Per questo motivo abbiamo gi&agrave; realizzato una <b>bozza di sito web</b> pensata appositamente per la vostra realt&agrave;. &Egrave; gratuita e senza impegno — serve semplicemente per mostrarvi in modo concreto cosa potremmo fare insieme. Qualora il progetto dovesse interessarvi, parleremo dei dettagli e dei costi in totale trasparenza.</p>
  <p>Se desiderate visionarla, &egrave; sufficiente rispondere a questa email.</p>
  <p>Cordiali saluti,</p>
  {FIRMA_HTML}
</div>
"""
        corpo_testo = f"""Gentile {nome_attivita},

mi chiamo Fabio di Easy Graphic, agenzia specializzata in digital marketing e comunicazione a 360 gradi.

Analizzando la vostra presenza online, ho notato che la vostra attivita non e ancora presente sul web con un sito proprio — e in un mercato sempre piu digitale, presentarsi in modo professionale puo fare una differenza concreta nel modo in cui i clienti vi percepiscono.

Per questo motivo abbiamo gia realizzato una bozza di sito web pensata appositamente per la vostra realta. E gratuita e senza impegno — serve semplicemente per mostrarvi in modo concreto cosa potremmo fare insieme. Qualora il progetto dovesse interessarvi, parleremo dei dettagli e dei costi in totale trasparenza.

Se desiderate visionarla, e sufficiente rispondere a questa email.

Cordiali saluti,
{FIRMA_TESTO}"""

    return oggetto, corpo_html, corpo_testo

def manda_email(destinatario, nome_attivita, ha_sito=False):
    """Manda email al potenziale cliente. Ritorna True se successo."""
    if not GMAIL_USER or not GMAIL_PASSWORD:
        print(f'  ⚠️  Gmail non configurato, skip email per {destinatario}')
        return False
    if not destinatario or '@' not in destinatario:
        return False

    try:
        oggetto, corpo_html, corpo_testo = build_email(nome_attivita, ha_sito)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = oggetto
        msg['From']    = f'Easy Graphic <{GMAIL_USER}>'
        msg['To']      = destinatario
        msg.attach(MIMEText(corpo_testo, 'plain', 'utf-8'))
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_USER, destinatario, msg.as_string())

        print(f'  ✅ Email inviata a {destinatario}')
        return True
    except Exception as e:
        print(f'  ❌ Errore email {destinatario}: {e}')
        return False

# ── FIREBASE ──────────────────────────────────────────────────────
def get_stato():
    try:
        r = requests.get(f'{FIREBASE_URL}/ai_stato/progress')
        if r.status_code == 200:
            fields = r.json().get('fields', {})
            return {'citta_index': int(fields.get('citta_index', {}).get('integerValue', 0))}
    except:
        pass
    return {'citta_index': 0}

def save_stato(citta_index):
    data = {'fields': {
        'citta_index': {'integerValue': str(citta_index)},
        'last_run':    {'stringValue': datetime.datetime.now().isoformat()},
    }}
    requests.patch(f'{FIREBASE_URL}/ai_stato/progress', json=data,
                   headers={'Content-Type': 'application/json'})

def gia_presente(nome, email):
    """Controlla se il contatto esiste già in emaillist o leads_pending."""
    for collection in ['emaillist', 'leads_pending']:
        try:
            query = {
                'structuredQuery': {
                    'from': [{'collectionId': collection}],
                    'where': {'fieldFilter': {
                        'field': {'fieldPath': 'nome'},
                        'op': 'EQUAL',
                        'value': {'stringValue': nome}
                    }},
                    'limit': 1
                }
            }
            r = requests.post(f'https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)/documents:runQuery',
                              json=query, headers={'Content-Type': 'application/json'})
            if r.status_code == 200:
                results = r.json()
                if results and results[0].get('document'):
                    return True
        except:
            pass
    return False

def salva_pending(attivita, membro_id, nicchia, citta, email_inviata):
    """Salva in leads_pending con timestamp. Dopo 24h passa a emaillist."""
    nome      = attivita.get('name', '')
    telefono  = attivita.get('phone', '')
    email_az  = attivita.get('email', '')
    sito      = attivita.get('website', '')
    indirizzo = attivita.get('full_address', '') or attivita.get('street', '')
    rating    = str(attivita.get('rating', ''))

    if not nome:
        return False

    ora = datetime.datetime.now()
    dashboard_at = (ora + datetime.timedelta(hours=24)).isoformat()

    data = {'fields': {
        'nome':         {'stringValue': nome},
        'tel':          {'stringValue': telefono or ''},
        'email':        {'stringValue': email_az or ''},
        'sito':         {'stringValue': sito or ''},
        'indirizzo':    {'stringValue': indirizzo or ''},
        'citta':        {'stringValue': citta},
        'nicchia':      {'stringValue': nicchia},
        'chiusoDa':     {'stringValue': membro_id},
        'contattato':   {'booleanValue': False},
        'fonte':        {'stringValue': 'AI'},
        'rating':       {'stringValue': rating},
        'data':         {'stringValue': ora.strftime('%d/%m/%Y')},
        'emailInviata': {'booleanValue': email_inviata},
        'emailSentAt':  {'stringValue': ora.isoformat()},
        'dashboardAt':  {'stringValue': dashboard_at},
        'ts':           {'integerValue': str(int(time.time() * 1000))},
    }}

    r = requests.post(f'{FIREBASE_URL}/leads_pending', json=data,
                      headers={'Content-Type': 'application/json'})
    return r.status_code == 200

def promuovi_pending():
    """Sposta da leads_pending a emaillist i contatti con dashboardAt passato."""
    print('\n── Promuovo leads_pending → emaillist ──')
    ora = datetime.datetime.now()

    try:
        r = requests.get(f'{FIREBASE_URL}/leads_pending?pageSize=200')
        if r.status_code != 200:
            return
        docs = r.json().get('documents', [])
        promossi = 0
        for doc in docs:
            fields = doc.get('fields', {})
            dashboard_at_str = fields.get('dashboardAt', {}).get('stringValue', '')
            if not dashboard_at_str:
                continue
            try:
                dashboard_at = datetime.datetime.fromisoformat(dashboard_at_str)
            except:
                continue
            if ora >= dashboard_at:
                # Copia in emaillist
                new_data = {'fields': {k: v for k, v in fields.items()
                                        if k not in ['dashboardAt', 'emailSentAt']}}
                r2 = requests.post(f'{FIREBASE_URL}/emaillist', json=new_data,
                                   headers={'Content-Type': 'application/json'})
                if r2.status_code == 200:
                    # Elimina da pending
                    doc_id = doc['name'].split('/')[-1]
                    requests.delete(f'{FIREBASE_URL}/leads_pending/{doc_id}')
                    promossi += 1
        print(f'  Promossi: {promossi} contatti')
    except Exception as e:
        print(f'  Errore promuovi: {e}')

# ── OUTSCRAPER (libreria ufficiale) ───────────────────────────────
from outscraper import ApiClient

def cerca_attivita(nicchia, citta, limit=25):
    query = f'{nicchia} {citta} Italy'
    print(f'  Cerco: {query}')
    try:
        client = ApiClient(api_key=OUTSCRAPER_KEY)
        results = client.google_maps_search(
            [query],
            limit=limit,
            language='it',
            fields=['name', 'phone', 'email', 'website', 'full_address', 'city', 'rating']
        )
        if results and isinstance(results[0], list):
            print(f'  Trovati {len(results[0])} risultati')
            return results[0]
        print('  0 risultati')
        return results or []
    except Exception as e:
        print(f'  Errore Outscraper: {e}')
        return []

# ── MAIN ──────────────────────────────────────────────────────────
def run():
    print(f'\n{"="*50}')
    print(f'Easy Graphic AI — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}')
    print(f'{"="*50}')

    if not OUTSCRAPER_KEY:
        print('ERRORE: OUTSCRAPER_KEY non configurata!')
        return

    # Prima promuovi i pending pronti
    promuovi_pending()

    stato = get_stato()
    citta_index = stato['citta_index']
    if citta_index >= len(ALL_CITTA):
        citta_index = 0
        print('Completato tutto il giro! Ricomincio da capo.')

    citta = ALL_CITTA[citta_index]
    print(f'\nCittà corrente: {citta} ({citta_index+1}/{len(ALL_CITTA)})')

    totale_salvati = 0
    totale_email   = 0

    for membro_id, nicchia in NICCHIE.items():
        print(f'\n[{membro_id.upper()}] Nicchia: {nicchia}')
        attivita_list = cerca_attivita(nicchia, citta, LEADS_PER_MEMBRO)

        salvati = 0
        for a in attivita_list:
            nome  = a.get('name', '')
            email = a.get('email', '')
            if not nome:
                continue
            if gia_presente(nome, email):
                print(f'  ⏭  Già presente: {nome}')
                continue
            # Capisce se l'attività ha già un sito web
            sito_web = (a.get('website') or '').strip()
            ha_sito = bool(sito_web) and 'facebook' not in sito_web.lower() and 'instagram' not in sito_web.lower()
            # Manda email se c'è l'indirizzo
            email_ok = False
            if email and '@' in email:
                tipo = 'CON sito' if ha_sito else 'SENZA sito'
                print(f'  📧 {nome} ({tipo})')
                email_ok = manda_email(email, nome, ha_sito)
                if email_ok:
                    totale_email += 1
                    time.sleep(2)  # pausa tra email
            # Salva in pending (va in dashboard dopo 24h)
            if salva_pending(a, membro_id, nicchia, citta, email_ok):
                salvati += 1

        print(f'  Salvati in pending: {salvati}/{len(attivita_list)}')
        totale_salvati += salvati
        time.sleep(3)

    next_index = citta_index + 1
    save_stato(next_index)

    print(f'\nRiepilogo: {totale_salvati} contatti salvati, {totale_email} email inviate')
    prossima = ALL_CITTA[next_index] if next_index < len(ALL_CITTA) else 'Ricomincia da capo'
    print(f'Prossima città: {prossima}')

if __name__ == '__main__':
    run()
