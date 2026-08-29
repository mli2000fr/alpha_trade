"""analyst_research — Collecte prospective Yahoo analyst (RESEARCH ONLY).

Modules :
- ``parsers``        : normalisation + validation schéma des réponses Yahoo.
- ``available_at``   : contrat PIT (observed_at → available_at).
- ``universe``       : univers figé ~400 symboles (config.yaml).
- ``collector``      : collecteur (réseau, retry, classification, persistance DB).
- ``monitor``        : suivi / visualisation (snapshot-status).
- ``features``       : feature builder (révisions EPS/revenue/target), MySQL-only.

Aucune intégration PROD (ni Global Rank, ni Oracle, ni cascade, ni live, ni
backtesting). Aucun stockage fichier : MySQL = unique source de vérité.
"""
