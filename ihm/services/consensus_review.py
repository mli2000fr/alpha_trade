"""Read-only EODHD consensus consultation, bounded by the displayed US date.

No provider request, historical PIT reconstruction, qualification or signal.
"""
from datetime import UTC, date, datetime, time, timedelta
import math
from zoneinfo import ZoneInfo

from sqlalchemy import text


TABLE = 'stock_analyst_consensus_eodhd_history'
# Label and explanation are deliberately independent from vendor numeric units.
GROUPS = {
    'Bénéfice par action — EPS': [
        ('eps_avg', 'Consensus EPS moyen', 'Moyenne des bénéfices par action estimés ; ce n’est pas un cours cible.'),
        ('eps_low', 'EPS le plus bas', 'Estimation EPS la plus basse de la période ; pas un scénario de prix.'),
        ('eps_high', 'EPS le plus haut', 'Estimation EPS la plus haute ; l’écart haut/bas décrit la dispersion des estimations.'),
        ('eps_analyst_count', 'Nombre d’analystes EPS', 'Nombre de contributeurs au consensus EPS ; pas un score de confiance.'),
        ('eps_year_ago', 'EPS de référence année précédente', 'Valeur de référence fournie par EODHD ; nature et comparabilité comptable à qualifier.'),
        ('eps_growth', 'Croissance EPS fournisseur', 'Valeur brute fournisseur, sans conversion en pourcentage tant que l’unité n’est pas qualifiée.'),
    ],
    'Chiffre d’affaires — revenus': [
        ('revenue_avg', 'Consensus de chiffre d’affaires moyen', 'Moyenne des revenus attendus pour cette période ; devise et échelle à qualifier.'),
        ('revenue_low', 'Chiffre d’affaires le plus bas', 'Estimation de revenus la plus basse, pas un bénéfice ni un prix d’action.'),
        ('revenue_high', 'Chiffre d’affaires le plus haut', 'Estimation de revenus la plus haute ; même réserve sur devise et échelle.'),
        ('revenue_analyst_count', 'Nombre d’analystes revenus', 'Contributeurs aux prévisions de revenus ; peut différer du nombre pour l’EPS.'),
        ('revenue_growth', 'Croissance des revenus fournisseur', 'Valeur brute non transformée en pourcentage ; vérifier unités et définition.'),
        ('revenue_year_ago', 'Référence revenus année précédente — non qualifiée', 'Champ source revenueEstimateYearAgoEps : nom ambigu. Ne pas l’assimiler à un chiffre d’affaires réalisé vérifié.'),
    ],
    'Évolution des estimations EPS': [
        ('eps_current', 'EPS courant — tendances', 'Estimation courante de la famille EPS Trends ; pas nécessairement identique à eps_avg.'),
        ('eps_7d_ago', 'Référence EPS à J−7', 'Référence livrée dans cette réponse. Ce n’est pas un snapshot réellement collecté à J−7.'),
        ('eps_30d_ago', 'Référence EPS à J−30', 'Référence sur 30 jours fournie aujourd’hui, pas une preuve de disponibilité historique à cette date.'),
        ('eps_60d_ago', 'Référence EPS à J−60', 'Référence sur 60 jours ; ne pas créer rétroactivement un snapshot à partir de cette valeur.'),
        ('eps_90d_ago', 'Référence EPS à J−90', 'Référence sur 90 jours, pas 90 journées d’historique PIT indépendant.'),
    ],
    'Révisions des estimations EPS': [
        ('revisions_up_7d', 'Révisions haussières — 7 jours', 'Nombre de révisions EPS vers le haut ; pas nécessairement des analystes distincts.'),
        ('revisions_down_7d', 'Révisions baissières — 7 jours', 'Nombre de révisions EPS vers le bas. Une valeur absente ne signifie pas zéro.'),
        ('revisions_up_30d', 'Révisions haussières — 30 jours', 'Nombre de révisions vers le haut sur 30 jours ; fenêtre chevauchant celle de 7 jours.'),
        ('revisions_down_30d', 'Révisions baissières — 30 jours', 'Nombre de révisions vers le bas sur 30 jours ; ne pas additionner les fenêtres 7 et 30 jours.'),
        ('provider_growth', 'Croissance générale fournisseur', 'Champ growth distinct des croissances EPS et revenus ; sémantique non certifiée.'),
    ],
    'Identité et dates': [
        ('symbol', 'Symbole', 'Titre demandé ; ne garantit pas à lui seul une identité historique stable.'),
        ('provider', 'Fournisseur', 'Source du consensus, ici EODHD. Aucune donnée Yahoo n’est substituée.'),
        ('snapshot_date', 'Date de collecte — New York', 'Journée réelle de notre collecte, pas la période fiscale ni une date historique reconstruite.'),
        ('fiscal_period_end', 'Fin de période fiscale fournisseur', 'Période comptable concernée. Ce n’est pas la date d’annonce des résultats.'),
        ('horizon_raw', 'Horizon brut fournisseur', '0q : trimestre courant ; +1q : suivant ; 0y : exercice courant ; +1y : suivant. Attribution à qualifier, surtout sur les anciennes périodes retournées.'),
        ('currency', 'Devise déclarée', 'Non renseignée si absente/non qualifiée ; ne pas supposer USD ni une échelle en millions.'),
        ('observed_at', 'Observation — UTC', 'Heure réelle de réception de cette observation par le collecteur.'),
        ('available_at', 'Disponibilité enregistrée — UTC', 'Borne de réception utilisée pour la consultation, pas une preuve de disponibilité avant notre collecte.'),
    ],
    'Qualification et traçabilité': [
        ('qualification_status', 'Statut de qualification', 'RESEARCH_ONLY signifie recherche uniquement ; aucune activation automatique pour le trading.'),
        ('fiscal_identity_qualified', 'Identité fiscale qualifiée', 'Oui uniquement si l’association horizon/période a été validée ; Non n’invalide pas mécaniquement la collecte.'),
        ('units_qualified', 'Unités qualifiées', 'Indique si devise, échelle et conventions des valeurs ont été vérifiées.'),
        ('historical_pit_qualified', 'Historique PIT qualifié', 'Non : ne pas traiter les dates fiscales anciennes comme des états du consensus connus à l’époque.'),
        ('run_id', 'Collecte d’origine', 'Identifiant pour retrouver le batch et ses compteurs, pas l’analyse LLM.'),
        ('raw_hash', 'Empreinte de la ligne source', 'Empreinte de contrôle du contenu fournisseur archivé ; pas une certification de son exactitude.'),
        ('parser_version', 'Version du parseur', 'Version du code ayant transformé la réponse en colonnes.'),
        ('ingestion_at', 'Horodatage technique d’insertion', 'Horodatage de base ; fuseau non présumé. Ne remplace pas available_at pour la disponibilité.'),
        ('id', 'Identifiant technique', 'Identifiant de cette ligne dans la table dédiée EODHD.'),
    ],
}
FIELDS = [field for group in GROUPS.values() for field, _, _ in group]


def scope(engine, symbol, end_date):
    if engine.dialect.name == 'mysql' and engine.url.database != 'alpha_trade':
        raise ValueError('Consensus de cette popin réservé au marché US')
    symbol = str(symbol or '').strip().upper()
    if not symbol or len(symbol)>32 or any(c.isspace() or ord(c)<32 for c in symbol):
        raise ValueError('Symbole invalide')
    day = end_date if type(end_date) is date else date.fromisoformat(str(end_date))
    cutoff = datetime.combine(day+timedelta(days=1), time(), ZoneInfo('America/New_York')).astimezone(UTC)
    return dict(symbol=symbol, end=day, cutoff=cutoff.replace(tzinfo=None))


def load_snapshot_days(engine, symbol, end_date):
    params = scope(engine,symbol,end_date)
    with engine.connect() as conn:
        return list(conn.execute(text(f'''SELECT DISTINCT snapshot_date FROM {TABLE}
            WHERE provider='eodhd' AND symbol=:symbol AND snapshot_date<=:end
            AND available_at<:cutoff AND observed_at<:cutoff
            ORDER BY snapshot_date DESC LIMIT 90'''),params).scalars())


def load_snapshot(engine, symbol, end_date, snapshot_day):
    params = scope(engine,symbol,end_date)
    params['snapshot'] = date.fromisoformat(str(snapshot_day))
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(f'''SELECT {','.join('`'+f+'`' for f in FIELDS)}
            FROM {TABLE} WHERE provider='eodhd' AND symbol=:symbol
            AND snapshot_date=:snapshot AND snapshot_date<=:end
            AND available_at<:cutoff AND observed_at<:cutoff
            ORDER BY fiscal_period_end DESC,horizon_raw'''),params).mappings()]


def load_period_history(engine, symbol, end_date, snapshot_day, fiscal_end, horizon):
    params = scope(engine,symbol,end_date)
    params.update(snapshot=date.fromisoformat(str(snapshot_day)), fiscal=fiscal_end, horizon=horizon)
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(f'''SELECT snapshot_date,available_at,
            eps_current,eps_avg,revenue_avg,revisions_up_30d,revisions_down_30d
            FROM {TABLE} WHERE provider='eodhd' AND symbol=:symbol AND snapshot_date<=:end
            AND snapshot_date<=:snapshot AND fiscal_period_end=:fiscal AND horizon_raw=:horizon
            AND available_at<:cutoff AND observed_at<:cutoff
            ORDER BY snapshot_date DESC LIMIT 30'''),params).mappings()]


def format_value(value):
    if value is None:
        return 'Non fourni / inconnu'
    if isinstance(value,bool):
        return 'Oui' if value else 'Non'
    if isinstance(value,(date,datetime)):
        return value.isoformat(sep=' ') if isinstance(value,datetime) else value.isoformat()
    if isinstance(value,(int,float)):
        return f'{value:,.6f}'.rstrip('0').rstrip('.') if math.isfinite(value) else 'Non fourni / inconnu'
    return str(value)


def field_rows(row, group):
    return [dict(Indicateur=label, Valeur=format_value(
        bool(row[field]) if field.endswith('_qualified') and row.get(field) is not None else row.get(field)),
        Colonne=field, Explication=explanation) for field,label,explanation in GROUPS[group]]


def change_rows(row):
    """Descriptive differences only; percentages unsafe for zero/negative base."""
    result=[]
    for days in (7,30,60,90):
        current,previous=row.get('eps_current'),row.get(f'eps_{days}d_ago')
        valid=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (current,previous))
        delta=current-previous if valid else None
        result.append({'Comparaison':f'EPS courant − référence J−{days}',
            'Écart EPS (unité source)':format_value(delta),
            'Variation (%)':format_value(100*delta/previous) if valid and previous>0 else 'Non calculée',
            'Lecture':'Description des attentes, pas une probabilité de hausse. Pourcentage uniquement si référence strictement positive.'})
    return result
