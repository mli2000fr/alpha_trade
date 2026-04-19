"""Abstraction de provider pour l'ingestion des corporate actions."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import date
from typing import Any
import urllib.parse
import requests

from corporate_actions.models import CaType, CorporateActionEvent
from service.alpaca.clientAlpaca import get_alpaca_credentials

LOGGER = logging.getLogger(__name__)

_DATA_BASE = "https://data.alpaca.markets"
_DEFAULT_TIMEOUT = 10
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_PAUSE_BETWEEN_CALLS = 0.2


# ---------------------------------------------------------------------------
# Interface abstraite — extensible vers Polygon, Finnhub, etc.
# ---------------------------------------------------------------------------

class CorporateActionProvider(ABC):
    """Contrat pour tout fournisseur de corporate actions."""

    @abstractmethod
    def fetch_events(
        self,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateActionEvent]:
        """Récupère les corporate actions pour les symboles donnés."""
        ...


# ---------------------------------------------------------------------------
# Implémentation Alpaca (Corporate Actions API v1beta1)
# ---------------------------------------------------------------------------

class AlpacaCorporateActionProvider(CorporateActionProvider):
    """
    Provider Alpaca pour les corporate actions.

    Utilise l'endpoint v1/corporate-actions de l'API Market Data.
    Ref: https://docs.alpaca.markets/reference/corporateactions
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        api_key, secret_key = get_alpaca_credentials()
        self._session.headers.update({
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        })

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{_DATA_BASE}{path}"
        # Construction de l'URL complète avec les paramètres pour le log
        full_url = url + "?" + urllib.parse.urlencode(params)
        LOGGER.info("[Alpaca] GET %s", full_url)
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                time.sleep(_PAUSE_BETWEEN_CALLS)
                resp = self._session.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
                data = resp.json()
                print(data.keys())
                print(data)
                if resp.status_code == 429 or resp.status_code >= 500:
                    delay = _BACKOFF_BASE * (2 ** attempt)
                    LOGGER.warning("Alpaca CA %s → %s, retry in %.1fs", path, resp.status_code, delay)
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                delay = _BACKOFF_BASE * (2 ** attempt)
                LOGGER.warning("Alpaca CA %s → %s, retry in %.1fs", path, type(exc).__name__, delay)
                time.sleep(delay)
        raise last_exc or RuntimeError("Max retries exceeded for Alpaca corporate actions")

    def fetch_events(
        self,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateActionEvent]:
        """Récupère dividendes et splits depuis Alpaca Corporate Actions API."""
        events: list[CorporateActionEvent] = []
        # Alpaca ca types: cash_dividend, forward_split, reverse_split, ...
        ca_types_to_fetch = ["cash_dividend", "forward_split", "reverse_split"]
        params: dict[str, Any] = {
            "types": ",".join(ca_types_to_fetch),
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        if start_date:
            params["start"] = start_date.isoformat()
        if end_date:
            params["end"] = end_date.isoformat()

        try:
            data = self._request("/v1/corporate-actions", params)
            LOGGER.debug("Réponse Alpaca corporate_actions: %r", data)
            LOGGER.info("Type de data: %s", type(data))
        except Exception:
            LOGGER.exception("Erreur lors de la récupération des corporate actions Alpaca")
            return events

        # Parsing explicite selon la structure réelle Alpaca
        # cash_dividends
        for raw in data.get("cash_dividends", []):
            if not isinstance(raw, dict):
                LOGGER.error("cash_dividend inattendu (non-dict): %r", raw)
                continue
            events.append(self._parse_dividend(raw))
        # forward_splits
        for raw in data.get("forward_splits", []):
            if not isinstance(raw, dict):
                LOGGER.error("forward_split inattendu (non-dict): %r", raw)
                continue
            events.append(self._parse_split(raw, CaType.SPLIT))
        # reverse_splits
        for raw in data.get("reverse_splits", []):
            if not isinstance(raw, dict):
                LOGGER.error("reverse_split inattendu (non-dict): %r", raw)
                continue
            events.append(self._parse_split(raw, CaType.REVERSE_SPLIT))

        LOGGER.info(
            "Alpaca corporate actions fetched | symbols=%s range=%s→%s events=%d",
            len(symbols), start_date, end_date, len(events),
        )
        return events

    @staticmethod
    def _parse_dividend(raw: dict[str, Any]) -> CorporateActionEvent:
        return CorporateActionEvent(
            provider="alpaca",
            provider_event_id=raw.get("id"),
            symbol=str(raw.get("symbol", "")).upper(),
            ca_type=CaType.SPECIAL_DIVIDEND if raw.get("subtype") == "special" else CaType.CASH_DIVIDEND,
            amount_per_share=float(raw.get("rate", 0)),
            currency=str(raw.get("currency", "USD")),
            ex_date=date.fromisoformat(raw["ex_date"]),
            record_date=date.fromisoformat(raw["record_date"]) if raw.get("record_date") else None,
            payable_date=date.fromisoformat(raw["payable_date"]) if raw.get("payable_date") else None,
            announcement_date=date.fromisoformat(raw["announcement_date"]) if raw.get("announcement_date") else None,
            raw_payload=raw,
        )

    @staticmethod
    def _parse_split(raw: dict[str, Any], ca_type: str) -> CorporateActionEvent:
        return CorporateActionEvent(
            provider="alpaca",
            provider_event_id=raw.get("id"),
            symbol=str(raw.get("symbol", "")).upper(),
            ca_type=ca_type,
            split_from=int(raw.get("old_rate", raw.get("from_factor", 1))),
            split_to=int(raw.get("new_rate", raw.get("to_factor", 1))),
            ex_date=date.fromisoformat(raw["ex_date"]),
            record_date=date.fromisoformat(raw["record_date"]) if raw.get("record_date") else None,
            payable_date=date.fromisoformat(raw["payable_date"]) if raw.get("payable_date") else None,
            announcement_date=date.fromisoformat(raw["announcement_date"]) if raw.get("announcement_date") else None,
            raw_payload=raw,
        )
