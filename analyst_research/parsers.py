"""Parsers Yahoo — normalisation des snapshots analyst (RESEARCH ONLY).

Convertit les objets bruts ``yfinance`` (``earnings_estimate``,
``revenue_estimate``, ``analyst_price_targets``, ``recommendations``) en lignes
normalisées destinées aux tables append-only MySQL.

Règles (todo3.txt) :
- Champ absent → NULL (jamais 0). ``NaN``/``NaT`` → ``None``.
- Si un champ REQUIS est absent (changement de schéma Yahoo) →
  :class:`ProviderSchemaChangedError` (classifié ``PROVIDER_SCHEMA_CHANGED``).
- ``raw_payload_json`` = portion brute de la réponse ; ``raw_hash`` = SHA-256
  déterministe du payload canonique (audit / reparsing / comparaison snapshots).
- Yahoo ne fournit PAS l'identité de période fiscale → ``relative_horizon_only``
  toujours True et ``fiscal_period_end``/``fiscal_year``/``fiscal_quarter`` NULL.
- Recommendations : une ligne par ``period_raw`` (0m/-1m/-2m/…) ; ces buckets
  sont des agrégats du snapshot courant, PAS un historique PIT fiable.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any, Mapping

import pandas as pd

PROVIDER = "yahoo"
SCHEMA_VERSION = "1.0"

HORIZON_MAP: dict[str, str] = {
    "0q": "CURRENT_QUARTER",
    "+1q": "NEXT_QUARTER",
    "0y": "CURRENT_YEAR",
    "+1y": "NEXT_YEAR",
    "-1q": "PREVIOUS_QUARTER",
    "-1y": "PREVIOUS_YEAR",
    "0h": "CURRENT_HALF",
    "+1h": "NEXT_HALF",
}

# Statuts de classification d'une réponse (miroir du collecteur).
STATUS_OK = "OK"
STATUS_EMPTY = "EMPTY"
STATUS_RATE_LIMIT = "RATE_LIMIT"
STATUS_TEMPORARY_ERROR = "TEMPORARY_ERROR"
STATUS_INVALID_SYMBOL = "INVALID_SYMBOL"
STATUS_PROVIDER_SCHEMA_CHANGED = "PROVIDER_SCHEMA_CHANGED"
STATUS_PARSE_ERROR = "PARSE_ERROR"


class ProviderSchemaChangedError(ValueError):
    """Schéma Yahoo inattendu (colonne requise absente ou structure différente)."""


class ParseError(ValueError):
    """Réponse non interprétable (structure invalide)."""


# ── Helpers ───────────────────────────────────────────────────────────────

def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _int(v: Any) -> int | None:
    f = _num(v)
    return int(f) if f is not None else None


def _jsonable(v: Any) -> Any:
    """Convertit une valeur pandas en type JSON-serialisable (None pour NaN)."""
    if v is None:
        return None
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Series, pd.Index)):
        return v.tolist()
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def compute_raw_hash(payload: Any) -> str:
    """SHA-256 déterministe du payload canonique (JSON trié, séparateurs stricts)."""
    canon = json.dumps(
        _jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _period_series(df: pd.DataFrame) -> pd.Series:
    """Extrait la série des horizons (``period`` en colonne ou en index)."""
    if "period" in df.columns:
        return df["period"].astype(str).str.strip()
    if isinstance(df.index, pd.Index) and len(df.index) > 0:
        return df.index.astype(str).str.strip()
    raise ProviderSchemaChangedError("colonne 'period' absente")


def _norm_estimate_row(
    period: str,
    row: pd.Series,
    *,
    estimate_type: str,
    provider: str,
    symbol: str,
    snapshot_date: date,
    observed_at: datetime,
    available_at: datetime,
    payload: Any,
    schema_version: str,
) -> dict[str, Any]:
    horizon_normalized = HORIZON_MAP.get(period, period)
    return {
        "provider": provider,
        "symbol": symbol,
        "snapshot_date": snapshot_date,
        "observed_at": observed_at,
        "available_at": available_at,
        "estimate_type": estimate_type,
        "horizon_raw": period,
        "horizon_normalized": horizon_normalized,
        "fiscal_period_end": None,
        "fiscal_year": None,
        "fiscal_quarter": None,
        "relative_horizon_only": True,
        "avg_value": _num(row.get("avg")),
        "low_value": _num(row.get("low")),
        "high_value": _num(row.get("high")),
        "analyst_count": _int(row.get("numberOfAnalysts")),
        "growth_value": _num(row.get("growth")),
        "raw_payload_json": json.dumps(_jsonable(payload), ensure_ascii=True),
        "raw_hash": compute_raw_hash(payload),
        "provider_schema_version": schema_version,
    }


# ── Parsers publics ───────────────────────────────────────────────────────

def parse_estimate(
    df: Any,
    *,
    estimate_type: str,
    symbol: str,
    provider: str = PROVIDER,
    snapshot_date: date,
    observed_at: datetime,
    available_at: datetime,
    schema_version: str = SCHEMA_VERSION,
) -> list[dict[str, Any]]:
    """Normalise ``earnings_estimate`` (EPS) ou ``revenue_estimate`` (REVENUE).

    Retourne la liste des lignes normalisées (vide → EMPTY).
    Lève :class:`ProviderSchemaChangedError` si ``avg`` absent.
    """
    if isinstance(df, tuple):  # yfinance peut retourner (df, meta)
        df = df[0]
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    if "avg" not in df.columns:
        raise ProviderSchemaChangedError(
            f"colonne 'avg' absente pour {estimate_type} (schéma Yahoo modifié)"
        )
    periods = _period_series(df)
    rows: list[dict[str, Any]] = []
    for period, (_, row) in zip(periods, df.iterrows()):
        payload = {"period": period, **{
            str(c): row[c] for c in df.columns if c != "period"
        }}
        rows.append(_norm_estimate_row(
            period, row, estimate_type=estimate_type, provider=provider,
            symbol=symbol, snapshot_date=snapshot_date, observed_at=observed_at,
            available_at=available_at, payload=payload, schema_version=schema_version,
        ))
    return rows


def parse_targets(
    d: Any,
    *,
    symbol: str,
    provider: str = PROVIDER,
    snapshot_date: date,
    observed_at: datetime,
    available_at: datetime,
    schema_version: str = SCHEMA_VERSION,
) -> list[dict[str, Any]]:
    """Normalise ``analyst_price_targets`` (dict current/high/low/mean/median)."""
    if isinstance(d, tuple):
        d = d[0]
    if d is None:
        return []
    if not isinstance(d, dict):
        raise ParseError(f"analyst_price_targets non-dict: {type(d).__name__}")
    known = {k: d.get(k) for k in ("current", "high", "low", "mean", "median")}
    if all(v is None for v in known.values()):
        return []  # EMPTY
    payload = dict(d)
    return [{
        "provider": provider,
        "symbol": symbol,
        "snapshot_date": snapshot_date,
        "observed_at": observed_at,
        "available_at": available_at,
        "current_price": _num(d.get("current")),
        "target_low": _num(d.get("low")),
        "target_mean": _num(d.get("mean")),
        "target_median": _num(d.get("median")),
        "target_high": _num(d.get("high")),
        "analyst_count": None,  # Yahoo n'expose pas le nb d'analystes ici
        "raw_payload_json": json.dumps(_jsonable(payload), ensure_ascii=True),
        "raw_hash": compute_raw_hash(payload),
        "provider_schema_version": schema_version,
    }]


def parse_recommendations(
    df: Any,
    *,
    symbol: str,
    provider: str = PROVIDER,
    snapshot_date: date,
    observed_at: datetime,
    available_at: datetime,
    schema_version: str = SCHEMA_VERSION,
) -> list[dict[str, Any]]:
    """Normalise ``recommendations`` — une ligne par ``period_raw``."""
    if isinstance(df, tuple):
        df = df[0]
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    periods = _period_series(df)
    rows: list[dict[str, Any]] = []
    for period, (_, row) in zip(periods, df.iterrows()):
        payload = {"period": period, **{
            str(c): row[c] for c in df.columns if c != "period"
        }}
        rows.append({
            "provider": provider,
            "symbol": symbol,
            "snapshot_date": snapshot_date,
            "observed_at": observed_at,
            "available_at": available_at,
            "period_raw": period,
            "strong_buy": _int(row.get("strongBuy")),
            "buy": _int(row.get("buy")),
            "hold": _int(row.get("hold")),
            "sell": _int(row.get("sell")),
            "strong_sell": _int(row.get("strongSell")),
            "raw_payload_json": json.dumps(_jsonable(payload), ensure_ascii=True),
            "raw_hash": compute_raw_hash(payload),
            "provider_schema_version": schema_version,
        })
    return rows
