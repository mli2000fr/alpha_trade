import os
import requests

DEFAULT_START_DATE = '2010-01-01T00:00:00Z'

def _get_alpaca_credentials():
    """Récupère les credentials Alpaca depuis les variables d'environnement."""
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY ou ALPACA_SECRET_KEY non définis dans les variables d'environnement système.")
    return api_key, secret_key


def fetch_alpaca_assets():
    ALPACA_API_KEY, ALPACA_SECRET_KEY = _get_alpaca_credentials()
    ALPACA_ENDPOINT = 'https://paper-api.alpaca.markets/v2/assets'
    headers = {
        'APCA-API-KEY-ID': ALPACA_API_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY
    }
    response = requests.get(ALPACA_ENDPOINT, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_hourly_bars(symbol, start_date=None):
    """
    Récupère les bars horaires (1H) pour un symbole donné depuis Alpaca.
    :param symbol: str, le symbole boursier (ex: 'AAPL')
    :param start_date: str ou None, date de début au format 'YYYY-MM-DD' (optionnel)
    :return: list de bars (chaque bar est un dict)
    """
    ALPACA_API_KEY, ALPACA_SECRET_KEY = _get_alpaca_credentials()
    endpoint = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    headers = {
        'APCA-API-KEY-ID': ALPACA_API_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY
    }
    params = {
        'timeframe': '1Hour',
        'limit': 10000  # maximum autorisé par Alpaca
    }
    if start_date:
        params['start'] = start_date
    else:
        params['start'] = DEFAULT_START_DATE
    all_bars = []
    next_token = None
    while True:
        if next_token:
            params['page_token'] = next_token
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        bars = data.get('bars', [])
        if bars is None:
            bars = []
        # Filtrer pour ne garder que les bars strictement > start_date si start_date est fourni
        if start_date:
            import dateutil.parser
            import datetime
            start_dt = dateutil.parser.isoparse(start_date)
            bars = [bar for bar in bars if dateutil.parser.isoparse(bar['t']) > start_dt]
        all_bars.extend(bars)
        next_token = data.get('next_page_token')
        print(f"call Alpaca du symbole : {symbol} {params['start']} {next_token} {len(bars)} bars récupérés")
        if not next_token:
            break
    return all_bars if all_bars is not None else []
