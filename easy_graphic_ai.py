#!/usr/bin/env python3
"""
Easy Graphic AI Lead Scraper
Cerca attività su Google Maps e le salva in Firebase
"""
import os, json, time, requests, datetime
from itertools import cycle

# ── CONFIG ────────────────────────────────────────────────────────
OUTSCRAPER_KEY = os.environ.get('OUTSCRAPER_KEY', '')
FIREBASE_PROJECT = 'easy-graphic-8a7eb'
FIREBASE_URL = f'https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)/documents'

# Nicchie per collaboratore
NICCHIE = {
    'mattia':   'parrucchieri',
    'jacopo':   'centro estetico',
    'emanuele': 'consulenti',
    'fabio':    'impresa edile',
}

# Città Nord Italia in ordine
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

LEADS_PER_MEMBRO = 25  # ogni ciclo cerca 25 lead per nicchia

# ── STATO (quale città siamo arrivati) ───────────────────────────
def get_stato():
    try:
        r = requests.get(
            f'{FIREBASE_URL}/ai_stato/progress',
            params={'key': ''}
        )
        if r.status_code == 200:
            fields = r.json().get('fields', {})
            return {
                'citta_index': int(fields.get('citta_index', {}).get('integerValue', 0)),
            }
    except:
        pass
    return {'citta_index': 0}

def save_stato(citta_index):
    data = {
        'fields': {
            'citta_index': {'integerValue': str(citta_index)},
            'last_run': {'stringValue': datetime.datetime.now().isoformat()},
        }
    }
    requests.patch(
        f'{FIREBASE_URL}/ai_stato/progress',
        json=data,
        headers={'Content-Type': 'application/json'}
    )

# ── OUTSCRAPER ────────────────────────────────────────────────────
def cerca_attivita(nicchia, citta, limit=25):
    """Cerca attività su Google Maps tramite Outscraper"""
    query = f'{nicchia} {citta} Italy'
    print(f'  Cerco: {query}')
    
    # Avvia ricerca asincrona
    r = requests.get(
        'https://api.app.outscraper.com/maps/search-v3',
        headers={'X-API-KEY': OUTSCRAPER_KEY},
        params={'query': query, 'limit': limit, 'async': 'true'}
    )
    
    if r.status_code not in [200, 202]:
        print(f'  Errore Outscraper: {r.status_code}')
        return []
    
    data = r.json()
    request_id = data.get('id')
    if not request_id:
        print(f'  Nessun request_id')
        return []
    
    # Aspetta risultati (max 60 secondi)
    for attempt in range(12):
        time.sleep(5)
        r2 = requests.get(
            f'https://api.outscraper.com/requests/{request_id}',
            headers={'X-API-KEY': OUTSCRAPER_KEY}
        )
        if r2.status_code == 200:
            result = r2.json()
            if result.get('status') == 'Success':
                results = result.get('data', [[]])[0]
                print(f'  Trovati {len(results)} risultati')
                return results
            elif result.get('status') == 'Pending':
                print(f'  In attesa... ({attempt+1}/12)')
                continue
        break
    
    return []

# ── FIREBASE ──────────────────────────────────────────────────────
def salva_in_firebase(attivita, membro_id, nicchia, citta):
    """Salva un'attività nella collection emaillist di Firebase"""
    nome = attivita.get('name', '')
    telefono = attivita.get('phone', '')
    email_az = attivita.get('email', '') or attivita.get('site', '')
    sito = attivita.get('website', '')
    indirizzo = attivita.get('full_address', '') or attivita.get('street', '')
    rating = str(attivita.get('rating', ''))
    recensioni = str(attivita.get('reviews', ''))
    
    if not nome:
        return False
    
    data = {
        'fields': {
            'nome':       {'stringValue': nome},
            'tel':        {'stringValue': telefono or ''},
            'email':      {'stringValue': email_az or ''},
            'sito':       {'stringValue': sito or ''},
            'indirizzo':  {'stringValue': indirizzo or ''},
            'citta':      {'stringValue': citta},
            'nicchia':    {'stringValue': nicchia},
            'chiusoDa':   {'stringValue': membro_id},
            'contattato': {'booleanValue': False},
            'fonte':      {'stringValue': 'AI'},
            'rating':     {'stringValue': rating},
            'recensioni': {'stringValue': recensioni},
            'data':       {'stringValue': datetime.date.today().strftime('%d/%m/%Y')},
            'ts':         {'integerValue': str(int(time.time() * 1000))},
        }
    }
    
    r = requests.post(
        f'{FIREBASE_URL}/emaillist',
        json=data,
        headers={'Content-Type': 'application/json'}
    )
    
    return r.status_code == 200

# ── MAIN ──────────────────────────────────────────────────────────
def run():
    print(f'\n{"="*50}')
    print(f'Easy Graphic AI — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}')
    print(f'{"="*50}')
    
    if not OUTSCRAPER_KEY:
        print('ERRORE: OUTSCRAPER_KEY non configurata!')
        return
    
    # Leggi stato corrente
    stato = get_stato()
    citta_index = stato['citta_index']
    
    # Se abbiamo finito tutte le città, ricomincia
    if citta_index >= len(ALL_CITTA):
        citta_index = 0
        print('Completato tutto il giro! Ricomincio da capo.')
    
    citta = ALL_CITTA[citta_index]
    print(f'\nCittà corrente: {citta} ({citta_index+1}/{len(ALL_CITTA)})')
    
    totale_salvati = 0
    
    for membro_id, nicchia in NICCHIE.items():
        print(f'\n[{membro_id.upper()}] Nicchia: {nicchia}')
        
        attivita = cerca_attivita(nicchia, citta, LEADS_PER_MEMBRO)
        
        salvati = 0
        for a in attivita:
            if salva_in_firebase(a, membro_id, nicchia, citta):
                salvati += 1
        
        print(f'  Salvati in Firebase: {salvati}/{len(attivita)}')
        totale_salvati += salvati
        
        # Pausa tra nicchie
        time.sleep(3)
    
    # Avanza alla prossima città
    next_index = citta_index + 1
    save_stato(next_index)
    
    print(f'\nRiepilogo: {totale_salvati} contatti salvati in Firebase')
    print(f'Prossima città: {ALL_CITTA[next_index] if next_index < len(ALL_CITTA) else "Ricomincia da capo"}')

if __name__ == '__main__':
    run()
