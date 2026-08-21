"""modelFactory/oracle/extreme_gate.py — Gate Extreme TOP20 (composant officiel).

Rôle : transformer ``proba_extreme`` (Oracle O0) en un **gate d'univers LONG**,
indépendant du ranking B25 (``global_rank_20``). C'est le composant retenu par la
branche de recherche E6→E13 (synthèse : `doc/synthese_e6_e13_2026-08-20.md`).

SÉMANTIQUE (très important) :
    ``proba_extreme`` n'est **PAS** ``P(LONG)``. C'est le potentiel de **MOUVEMENT
    EXTRÊME** cross-sectionnel selon Oracle. L'edge LONG est **empirique** : E8-E13
    ont montré que le top 20% de ``proba_extreme`` forme un univers porteur, SANS
    qu'Oracle prédise la direction. → Ne jamais interpréter comme un score directionnel.

MÉCANIQUE PIT (aucun lookahead) :
    - ``proba_extreme`` = calculé à la date D avec les données disponibles à D ;
    - le gate est un **percentile cross-sectionnel DU JOUR** : on classe les
      candidats de D entre eux, on garde ceux ≥ ``1 - pool_pct`` (défaut 0.20 →
      top 20% du jour) ;
    - AUCUNE information future (ni seuil global, ni rang de J+1).

Architecture cible :
    Oracle O0 → proba_extreme → percentile cross-sectionnel du jour ≥ 1-pool_pct
    → EXTREME_GATE = True → LONG candidates → m24 (1/24 du budget de risque)
    → lifecycle PROD.

Utilisation :
    - ``compute_extreme_gate(df)`` : ajoute ``extreme_pct`` et ``extreme_gate``.
    - ``build_oracle_rank_map(df)`` : dict {date: {symbol: proba_extreme}} pour
      ``cascade_select(rank_mode="extreme_gate", oracle_rank_map=...)``.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

# Seuil par défaut de l'univers Extreme (top 20% du jour par proba_extreme).
DEFAULT_POOL_PCT = 0.20


def compute_extreme_gate(
    df: pd.DataFrame,
    pool_pct: float = DEFAULT_POOL_PCT,
    proba_col: str = "proba_extreme",
    date_col: str = "date",
) -> pd.DataFrame:
    """Applique le gate Extreme TOP20 (PIT) à un DataFrame date × symbol × proba_extreme.

    Paramètres
    ----------
    df : DataFrame avec au moins ``date_col``, ``symbol`` et ``proba_col``.
    pool_pct : top fraction de l'univers par proba_extreme (0.20 = top 20% du jour).
    proba_col : colonne de ``proba_extreme`` (Oracle O0).
    date_col : colonne de date (normalisée).

    Retour
    ------
    DataFrame identique + :
      - ``extreme_pct``  : percentile cross-sectionnel de ``proba_extreme`` DANS le
        jour (1.0 = plus haut du jour). PIT (aucun lookahead).
      - ``extreme_gate`` : booléen ``extreme_pct >= 1 - pool_pct`` (True = univers
        LONG Extreme TOP20 retenu).

    NB : ``pool_pct <= 0`` garde tout ; ``pool_pct >= 1`` garde le percentile max.
    """
    out = df.copy()
    if len(out) == 0 or proba_col not in out.columns:
        out["extreme_pct"] = float("nan")
        out["extreme_gate"] = False
        return out
    pct = out.groupby(date_col)[proba_col].rank(pct=True)
    out["extreme_pct"] = pct
    out["extreme_gate"] = pct >= (1.0 - float(pool_pct))
    return out


def build_oracle_rank_map(
    df: pd.DataFrame,
    proba_col: str = "proba_extreme",
    date_col: str = "date",
) -> dict[str, dict[str, float]]:
    """Construit {date: {symbol: proba_extreme}} pour ``cascade_select``.

    Le gate étant cross-sectionnel par jour, ``cascade_select(rank_mode="extreme_gate")``
    convertit ces proba en percentile intra-date et garde les ≥ 1 - pool_pct.
    """
    out: dict[str, dict[str, float]] = {}
    for date, g in df.groupby(date_col):
        out[str(pd.Timestamp(date).date())] = {
            str(row["symbol"]): float(row[proba_col]) for _, row in g.iterrows()
        }
    return out
