import datetime

# Liste des jours fériés US (NYSE) pour les années courantes, à compléter si besoin
US_MARKET_HOLIDAYS = [
    # Nouvel An
    (1, 1),
    # Martin Luther King Jr. Day (3ème lundi de janvier)
    # Presidents' Day (3ème lundi de février)
    # Good Friday (variable)
    # Memorial Day (dernier lundi de mai)
    # Juneteenth (19 juin)
    (6, 19),
    # Independence Day
    (7, 4),
    # Labor Day (1er lundi de septembre)
    # Thanksgiving (4ème jeudi de novembre)
    # Christmas
    (12, 25),
]

def is_us_market_holiday(date):
    # Vérifie si la date est un jour férié fixe (hors calculs dynamiques)
    return (date.month, date.day) in US_MARKET_HOLIDAYS

def getLastDateMarche(ref_date=None):
    """
    Retourne la dernière date où le marché US était ouvert (hors week-end et jours fériés principaux).
    :param ref_date: date de référence (datetime.date ou None pour aujourd'hui)
    :return: datetime.date
    """
    if ref_date is None:
        ref_date = datetime.date.today()
    d = ref_date
    while True:
        d -= datetime.timedelta(days=1)
        # Marché fermé le samedi (5) et dimanche (6)
        if d.weekday() >= 5:
            continue
        if is_us_market_holiday(d):
            continue
        return d

