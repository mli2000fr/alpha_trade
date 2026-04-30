"""Phase 7.3 — Cross-check Alpaca/IEX vs Stooq (audit_global §7.3).

Compare les bars daily ingérés (Alpaca/IEX) avec une source consolidée
indépendante (Stooq) pour détecter les biais IEX (volume sous-évalué x30-50,
écarts OHLC sur small caps).

API minimale, **best-effort** :

    from dataIntegrityEngine.cross_check_stooq import compare_with_stooq
    anomalies = compare_with_stooq(
        ingested_bars={"AAPL": [...]},  # dict symbol -> list[dict bars]
        lookback_days=30,
    )

Les anomalies sont retournées sous forme de liste de dicts JSON-sérialisables,
prêts à être persistés dans ``cleaning_audit_runs.cross_check_anomalies``.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from service.stooq.clientStooq import fetch_daily_bars

LOGGER = logging.getLogger(__name__)

#: Seuil au-delà duquel un écart de close est considéré anormal.
DEFAULT_CLOSE_TOLERANCE_PCT = 0.03  # 3 %

#: Seuil au-delà duquel un ratio volume IEX/Stooq est considéré anormal.
DEFAULT_VOLUME_RATIO_MIN = 0.10


def compare_with_stooq(
    ingested_bars: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    lookback_days: int = 30,
    close_tolerance_pct: float = DEFAULT_CLOSE_TOLERANCE_PCT,
    volume_ratio_min: float = DEFAULT_VOLUME_RATIO_MIN,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Cross-check les bars ingérés vs Stooq sur ``lookback_days`` jours.

    Retourne la liste des anomalies (peut être vide). Format :

        {
            "symbol": "AAPL",
            "trade_date": "2026-04-15",
            "kind": "close_mismatch" | "volume_ratio_low" | "missing_in_stooq",
            "ingested": {"close": ..., "volume": ...},
            "stooq": {"close": ..., "volume": ...},
        }
    """
    today = today or date.today()
    start = today - timedelta(days=lookback_days)
    anomalies: list[dict[str, Any]] = []

    for symbol, ing_bars in ingested_bars.items():
        try:
            stooq_bars = fetch_daily_bars(symbol, start=start, end=today)
        except Exception:  # pragma: no cover - défensif (clientStooq déjà best-effort)
            LOGGER.warning("Stooq cross-check : fetch error for %s", symbol, exc_info=True)
            continue
        stooq_by_date = {b["date"]: b for b in stooq_bars}

        for ing in ing_bars:
            d = ing.get("date") or ing.get("trade_date")
            if isinstance(d, str):
                try:
                    d = date.fromisoformat(d[:10])
                except ValueError:
                    continue
            if not isinstance(d, date) or d < start or d > today:
                continue
            ing_close = _f(ing.get("close"))
            ing_vol = _f(ing.get("volume"))
            if d not in stooq_by_date:
                anomalies.append(
                    {
                        "symbol": symbol,
                        "trade_date": d.isoformat(),
                        "kind": "missing_in_stooq",
                        "ingested": {"close": ing_close, "volume": ing_vol},
                        "stooq": None,
                    }
                )
                continue
            sb = stooq_by_date[d]
            s_close = _f(sb.get("close"))
            s_vol = _f(sb.get("volume"))
            if ing_close and s_close:
                err = abs(ing_close - s_close) / s_close
                if err > close_tolerance_pct:
                    anomalies.append(
                        {
                            "symbol": symbol,
                            "trade_date": d.isoformat(),
                            "kind": "close_mismatch",
                            "ingested": {"close": ing_close, "volume": ing_vol},
                            "stooq": {"close": s_close, "volume": s_vol},
                            "error_pct": round(err, 6),
                        }
                    )
            if s_vol and s_vol > 0:
                ratio = (ing_vol or 0.0) / s_vol
                if ratio < volume_ratio_min:
                    anomalies.append(
                        {
                            "symbol": symbol,
                            "trade_date": d.isoformat(),
                            "kind": "volume_ratio_low",
                            "ingested": {"close": ing_close, "volume": ing_vol},
                            "stooq": {"close": s_close, "volume": s_vol},
                            "volume_ratio": round(ratio, 6),
                        }
                    )
    return anomalies


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


__all__ = ["compare_with_stooq", "DEFAULT_CLOSE_TOLERANCE_PCT", "DEFAULT_VOLUME_RATIO_MIN"]

