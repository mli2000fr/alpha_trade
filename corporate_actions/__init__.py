"""
corporate_actions — Gestion automatique des opérations sur titres.

Couvre : dividendes cash, splits, reverse splits.
Extensible vers : mergers, spin-offs, symbol changes, delistings.

Stratégie données de marché :
    Alpha Trade ingère les barres Alpaca avec adjustment="all".
    Les OHLCV sont donc DÉJÀ ajustés côté market-data.
    Ce module ne touche PAS aux prix historiques.
    Il gère uniquement la comptabilité portefeuille :
    - crédit cash pour dividendes
    - ajustement qty / cost basis pour splits
    - audit trail complet et idempotent
"""

