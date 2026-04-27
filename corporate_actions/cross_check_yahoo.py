"""Phase 5.3.c — Cross-check optionnel Yahoo Finance pour les dividendes.

Ce module isole la dépendance ``yfinance`` derrière un import paresseux pour
qu'elle reste **opt-in** (extras ``cross-check`` du ``pyproject.toml``).

Le provider :class:`YahooDividendCrossCheckProvider` retourne, pour une liste
de symboles et une fenêtre temporelle, les dividendes ex-date observés chez
Yahoo Finance, normalisés en :class:`corporate_actions.models.CorporateActionEvent`.

Usage type :

    from corporate_actions.cross_check_yahoo import YahooDividendCrossCheckProvider
    yp = YahooDividendCrossCheckProvider()
    events = yp.fetch_events(symbols=["AAPL"], start_date=..., end_date=...)

Réf. ``prompt/refactor/plan_phase5.md`` § 5.3.c.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from corporate_actions.models import CaType, CorporateActionEvent
from corporate_actions.provider import CorporateActionProvider

LOGGER = logging.getLogger(__name__)


class YahooDividendCrossCheckProvider(CorporateActionProvider):
    """Provider read-only Yahoo Finance pour cross-check dividendes (opt-in).

    - Lazy import ``yfinance`` (extras ``cross-check`` du ``pyproject.toml``).
    - Jamais bloquant : toute exception est convertie en log warning + liste
      vide pour ne pas casser le pipeline corporate_actions principal.
    """

    PROVIDER_NAME = "yahoo"

    def __init__(self) -> None:
        self._yf = None  # initialisé paresseusement

    def _import_yfinance(self) -> Any:
        if self._yf is not None:
            return self._yf
        try:
            import yfinance  # type: ignore
        except ImportError:
            LOGGER.warning(
                "yfinance n'est pas installé — cross-check Yahoo désactivé. "
                "Installer via : pip install 'alpha-trade[cross-check]' "
                "ou pip install yfinance>=0.2"
            )
            return None
        self._yf = yfinance
        return self._yf

    def fetch_events(
        self,
        symbols: list[str] | None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateActionEvent]:
        """Récupère les dividendes Yahoo pour les ``symbols`` ∈ [start, end].

        Si ``yfinance`` est absent ou plante, renvoie une liste vide (jamais
        d'exception propagée).
        """
        if not symbols:
            return []
        yf = self._import_yfinance()
        if yf is None:
            return []
        events: list[CorporateActionEvent] = []
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                series = getattr(ticker, "dividends", None)
                if series is None or len(series) == 0:
                    continue
                for ex_date_raw, amount in series.items():
                    ex_date = self._normalize_date(ex_date_raw)
                    if ex_date is None:
                        continue
                    if start_date and ex_date < start_date:
                        continue
                    if end_date and ex_date > end_date:
                        continue
                    try:
                        amount_f = float(amount)
                    except (TypeError, ValueError):
                        continue
                    if amount_f <= 0:
                        continue
                    events.append(
                        CorporateActionEvent(
                            provider=self.PROVIDER_NAME,
                            provider_event_id=f"yahoo:{sym}:{ex_date.isoformat()}",
                            symbol=sym.upper(),
                            ca_type=CaType.CASH_DIVIDEND,
                            amount_per_share=amount_f,
                            ex_date=ex_date,
                        )
                    )
            except Exception:
                LOGGER.warning(
                    "Cross-check Yahoo : echec recuperation dividendes pour %s (ignore).",
                    sym,
                    exc_info=True,
                )
        return events

    @staticmethod
    def _normalize_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        # pandas Timestamp / autres types datelike
        for attr in ("date", "to_pydatetime"):
            converter = getattr(value, attr, None)
            if callable(converter):
                try:
                    converted = converter()
                except Exception:
                    continue
                if isinstance(converted, datetime):
                    return converted.date()
                if isinstance(converted, date):
                    return converted
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Helper de comparaison (consommé par CLI Phase 5.3.c)
# ---------------------------------------------------------------------------


def diff_dividends(
    *,
    ingested: list[CorporateActionEvent],
    yahoo: list[CorporateActionEvent],
    amount_tolerance: float = 1e-4,
) -> list[dict[str, Any]]:
    """Retourne la liste des anomalies entre events ingérés et events Yahoo.

    Chaque anomalie est un dict ``{symbol, ex_date, kind, ingested, yahoo}``
    avec ``kind`` ∈ ``{"missing_in_ingested", "missing_in_yahoo", "amount_mismatch"}``.
    """
    def _key(ev: CorporateActionEvent) -> tuple[str, str]:
        return (ev.symbol.upper(), ev.ex_date.isoformat())

    ingested_map = {_key(ev): ev for ev in ingested}
    yahoo_map = {_key(ev): ev for ev in yahoo}
    anomalies: list[dict[str, Any]] = []

    for k, yev in yahoo_map.items():
        if k not in ingested_map:
            anomalies.append(
                {
                    "symbol": yev.symbol,
                    "ex_date": yev.ex_date.isoformat(),
                    "kind": "missing_in_ingested",
                    "yahoo_amount": yev.amount_per_share,
                    "ingested_amount": None,
                }
            )
            continue
        iev = ingested_map[k]
        a_i = iev.amount_per_share or 0.0
        a_y = yev.amount_per_share or 0.0
        if abs(a_i - a_y) > amount_tolerance:
            anomalies.append(
                {
                    "symbol": yev.symbol,
                    "ex_date": yev.ex_date.isoformat(),
                    "kind": "amount_mismatch",
                    "yahoo_amount": a_y,
                    "ingested_amount": a_i,
                }
            )

    for k, iev in ingested_map.items():
        if k not in yahoo_map:
            anomalies.append(
                {
                    "symbol": iev.symbol,
                    "ex_date": iev.ex_date.isoformat(),
                    "kind": "missing_in_yahoo",
                    "yahoo_amount": None,
                    "ingested_amount": iev.amount_per_share,
                }
            )

    return anomalies

