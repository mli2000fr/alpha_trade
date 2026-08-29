"""Feature builder analyst — révisions EPS/revenue/target (RESEARCH ONLY).

Lit EXCLUSIVEMENT MySQL (tables append-only de la collecte). Ne calcule AUCUNE
feature avant persistance DB.

Règles (todo3.txt §18-25) :
- ``revision_abs = new - old`` ; ``revision_pct`` avec dénominateur ``abs(old)``
  + epsilon ; si ``abs(old) < epsilon`` → NULL (jamais de fausse révision %).
- **Fiscal rollover** : Yahoo ne fournit pas l'identité fiscale
  (``relative_horizon_only``) → une révision qui TRAVERSE un rollover est NULL.
  Détection du rollover : un earnings RAPPORTÉ entre les deux snapshots
  (``stock_earnings_calendar.earnings_date``) fait basculer l'horizon relatif
  → la variation de CURRENT_QUARTER n'est PAS une vraie révision.
- ``days_since_last_revision`` : absence de changement = information aussi.
- Les rangs cross-sectionnels (``*_xs_rank``) exigent que TOUTES les lignes
  utilisées soient disponibles à J (PIT) : calcul par date sur les snapshots
  dont ``available_at <= date J``.

Ces fonctions ne sont exploitables qu'une fois l'historique accumulé
(jalons : ~20 sessions QA, ~60 smoke, ~120 1er diagnostic, ~252 validation).
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from analyst_research.parsers import HORIZON_MAP
from database.repositories.analyst_snapshots import AnalystSnapshotRepository

LOGGER = logging.getLogger(__name__)

# Epsilon minimum pour le dénominateur de la révision en % (todo3.txt §22).
PCT_EPSILON = 1e-9


def revision_pct(new: float | None, old: float | None, *, epsilon: float = PCT_EPSILON) -> float | None:
    """Révision en % avec règle documentée : dénom = abs(old), NULL si |old| < epsilon."""
    if new is None or old is None:
        return None
    if abs(old) < epsilon:
        return None
    return float((new - old) / abs(old))


def _rollover_dates(engine: Any, symbol: str, lo: datetime, hi: datetime) -> set[date]:
    """Dates d'earnings RAPPORTÉS dans (lo, hi] pour le symbole (détection rollover)."""
    try:
        import pandas as _pd
        from sqlalchemy import text
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT earnings_date FROM stock_earnings_calendar "
                "WHERE symbol = :sym AND earnings_date > :lo AND earnings_date <= :hi"
            ), {"sym": symbol.upper(), "lo": lo.date(), "hi": hi.date()}).all()
        return {r[0] for r in rows}
    except Exception as e:  # noqa: BLE001 - table absente → pas de détection
        LOGGER.warning("rollover_dates indisponible (%s)", e)
        return set()


def estimate_revision_series(
    symbol: str,
    estimate_type: str,
    horizon_normalized: str,
    repo: AnalystSnapshotRepository | None = None,
    engine: Any = None,
) -> pd.DataFrame:
    """Série de révisions pour (symbole, type, horizon) — PIT, rollover-gardé.

    Colonnes : available_at, avg_value, revision_abs, revision_pct,
    days_since_last_revision, rollover_flag, n_analysts.
    """
    repo = repo or AnalystSnapshotRepository()
    rows = repo.get_estimate_history(symbol.upper(), estimate_type=estimate_type,
                                     horizon_normalized=horizon_normalized)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["available_at"] = pd.to_datetime(df["available_at"], errors="coerce")
    df = df.sort_values("available_at").reset_index(drop=True)

    prev_avg: float | None = None
    prev_at: datetime | None = None
    abs_list: list[float | None] = []
    pct_list: list[float | None] = []
    dslr: list[int | None] = []
    roll: list[bool] = []
    for _, r in df.iterrows():
        cur = r["avg_value"]
        if prev_avg is None or prev_at is None or cur is None:
            abs_list.append(None)
            pct_list.append(None)
            dslr.append(None)
            roll.append(False)
        else:
            crossed = False
            if engine is not None:
                crossed = bool(_rollover_dates(engine, symbol, prev_at, r["available_at"]))
            abs_list.append(float(cur - prev_avg) if not crossed else None)
            pct_list.append(revision_pct(cur, prev_avg) if not crossed else None)
            dslr.append(int((r["available_at"] - prev_at).days) if not crossed else None)
            roll.append(crossed)
        prev_avg = cur
        prev_at = r["available_at"]

    df["revision_abs"] = abs_list
    df["revision_pct"] = pct_list
    df["days_since_last_revision"] = dslr
    df["rollover_flag"] = roll
    df = df[["available_at", "avg_value", "revision_abs", "revision_pct",
             "days_since_last_revision", "rollover_flag", "analyst_count"]]
    return df


def target_revision_series(
    symbol: str,
    repo: AnalystSnapshotRepository | None = None,
) -> pd.DataFrame:
    """Série de révisions de target price (mean/median/high/low)."""
    repo = repo or AnalystSnapshotRepository()
    rows = repo.get_target_history(symbol.upper())
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["available_at"] = pd.to_datetime(df["available_at"], errors="coerce")
    df = df.sort_values("available_at").reset_index(drop=True)
    out = pd.DataFrame({"available_at": df["available_at"]})
    for col in ("target_mean", "target_median", "target_high", "target_low"):
        vals = df[col].astype(float)
        out[f"{col}_revision_abs"] = vals.diff()
        out[f"{col}_revision_pct"] = [
            revision_pct(b, a) for a, b in zip(vals.shift(1), vals)
        ]
    out["days_since_last_target_revision"] = (
        out["available_at"].diff().dt.days
    )
    return out


def target_upside(mean_target: float | None, pit_price: float | None) -> float | None:
    """Upside target : (mean/price - 1). NULL si prix absent/nul."""
    if mean_target is None or pit_price is None or pit_price == 0:
        return None
    return float(mean_target / pit_price - 1.0)


def xs_rank(df: pd.DataFrame, value_col: str, date_col: str = "available_at") -> pd.Series:
    """Rang percentile cross-sectionnel [0,1] par date (toutes lignes PIT à J)."""
    return df.groupby(date_col)[value_col].rank(pct=True)
