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
WHATSAPP_URL   = 'https://wa.me/39351994 3497'

# Nicchie per collaboratore
NICCHIE = {
    'mattia':   'parrucchieri',
    'jacopo':   'centro estetico',
    'emanuele': 'consulenti',
    'fabio':    'impresa edile',
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
def build_email(nome_attivita):
    oggetto = f"Easy Graphic — Una proposta per {nome_attivita}"
    corpo_html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#222;font-size:15px;line-height:1.7">
  <p>Ciao <b>{nome_attivita}</b>,</p>

  <p>Ci siamo imbattuti nella tua attività mentre cercavamo realtà interessanti nella zona — e la tua ci ha colpito.
  Si vede la cura che ci hai messo.</p>

  <p>L'unica cosa è che una bella attività senza la comunicazione giusta rischia di restare invisibile —
  e di perdere clienti che avrebbero scelto te.</p>

  <p>Ti lascio la nostra brochure, magari può essere uno spunto interessante.<br>
  👉 <a href="{LINK_BROCHURE}">Scarica la brochure</a></p>

  <p>Se ti va, siamo molto volentieri disponibili per una chiamata conoscitiva — senza impegno,
  solo per capire se possiamo esserti utili.</p>

  <p>A disposizione per qualsiasi cosa, ti ringrazio per il tuo tempo e ti auguro una buona giornata e un buon lavoro!</p>

  <p style="margin-top:24px">
    <b>Fabio — Easy Graphic</b><br>
    📞 351 994 3497<br>
    💬 <a href="{WHATSAPP_URL}">WhatsApp diretto</a><br>
    🌐 <a href="{LINK_SITO}">{LINK_SITO}</a>
  </p>
</div>
"""
    corpo_testo = f"""Ciao {nome_attivita},

Ci siamo imbattuti nella tua attività mentre cercavamo realtà interessanti nella zona — e la tua ci ha colpito. Si vede la cura che ci hai messo.

L'unica cosa è che una bella attività senza la comunicazione giusta rischia di restare invisibile — e di perdere clienti che avrebbero scelto te.

Ti lascio la nostra brochure, magari può essere uno spunto interessante: {LINK_BROCHURE}

Se ti va, siamo molto volentieri disponibili per una chiamata conoscitiva — senza impegno, solo per capire se possiamo esserti utili.

A disposizione per qualsiasi cosa, ti ringrazio per il tuo tempo e ti auguro una buona giornata e un buon lavoro!

Fabio — Easy Graphic
351 994 3497
WhatsApp: {WHATSAPP_URL}
Sito: {LINK_SITO}
"""
    return oggetto, corpo_html, corpo_testo

def manda_email(destinatario, nome_attivita):
    """Manda email al potenziale cliente. Ritorna True se successo."""
    if not GMAIL_USER or not GMAIL_PASSWORD:
        print(f'  ⚠️  Gmail non configurato, skip email per {destinatario}')
        return False
    if not destinatario or '@' not in destinatario:
        return False

    try:
        oggetto, corpo_html, corpo_testo = build_email(nome_attivita)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = oggetto
        msg['From']    = GMAIL_USER
        msg['To']      = destinatario
        msg.attach(MIMEText(corpo_testo, 'plain', 'utf-8'))
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_USER, destinatario, msg.as_bytes())

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


# ── ESTRAI EMAIL DAL SITO ─────────────────────────────────────────
def estrai_email_da_sito(url):
    """Cerca email nel sito web dell'attività."""
    if not url or not url.startswith('http'):
        return ''
    try:
        import re
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; EasyGraphic/1.0)',
            'Accept': 'text/html'
        }
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        if r.status_code != 200:
            return ''
        testo = r.text[:50000]  # primi 50kb
        # Cerca pattern email
        emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', testo)
        # Filtra email generiche/spam
        escludi = ['noreply', 'no-reply', 'wordpress', 'sentry', 'example',
                   'wix', 'squarespace', 'google', 'facebook', 'instagram',
                   'schema', 'jquery', 'bootstrap', 'cloudflare']
        for email in emails:
            email_low = email.lower()
            if any(e in email_low for e in escludi):
                continue
            if len(email) > 60:
                continue
            return email.lower()
    except Exception as e:
        pass
    return ''

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

# ── OUTSCRAPER ────────────────────────────────────────────────────
def cerca_attivita(nicchia, citta, limit=25):
    query = f'{nicchia} {citta} Italy'
    print(f'  Cerco: {query}')
    try:
        r = requests.get('https://api.outscraper.com/maps/search-v3',
            params={'query': query, 'limit': limit, 'async': True},
            headers={'X-API-KEY': OUTSCRAPER_KEY}, timeout=30)
        if r.status_code not in [200, 202]:
            print(f'  Errore Outscraper: {r.status_code}')
            return []
        request_id = r.json().get('id', '')
        if not request_id:
            # Risposta sincrona diretta
            data = r.json().get('data', [[]])
            return data[0] if data else []
        for attempt in range(12):
            time.sleep(10)
            r2 = requests.get(f'https://api.outscraper.com/requests/{request_id}',
                headers={'X-API-KEY': OUTSCRAPER_KEY}, timeout=30)
            if r2.status_code == 200:
                result = r2.json()
                if result.get('status') == 'Success':
                    results = result.get('data', [[]])[0]
                    print(f'  Trovati {len(results)} risultati')
                    return results
                elif result.get('status') == 'Pending':
                    print(f'  In attesa... ({attempt+1}/12)')
    except Exception as e:
        print(f'  Errore: {e}')
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
            # Cerca email: prima da Outscraper, poi dal sito
            email_ok = False
            if not (email and '@' in email):
                sito = a.get('website', '') or a.get('site', '')
                if sito:
                    print(f'  🔍 Cerco email su sito: {sito[:50]}')
                    email = estrai_email_da_sito(sito)
                    if email:
                        print(f'  📧 Email trovata: {email}')
            if email and '@' in email:
                email_ok = manda_email(email, nome)
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
