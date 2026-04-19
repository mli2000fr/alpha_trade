"""Abstraction de provider pour l'ingestion des corporate actions."""
from __future__ import annotations

import logging
import time
import urllib.parse
from abc import ABC, abstractmethod
from datetime import date
from fractions import Fraction
from typing import Any

import requests

from corporate_actions.models import CaType, CorporateActionEvent
from service.alpaca.clientAlpaca import get_alpaca_credentials

LOGGER = logging.getLogger(__name__)

_DATA_BASE = "https://data.alpaca.markets"
_DEFAULT_TIMEOUT = 10
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_PAUSE_BETWEEN_CALLS = 0.2
_PAGE_LIMIT = 1000
_MAX_TIMEOUT_RETRIES = 10
_TIMEOUT_BACKOFF_SECONDS = 5


# ---------------------------------------------------------------------------
# Interface abstraite — extensible vers Polygon, Finnhub, etc.
# ---------------------------------------------------------------------------

class CorporateActionProvider(ABC):
    """Contrat pour tout fournisseur de corporate actions."""

    @abstractmethod
    def fetch_events(
        self,
        symbols: list[str] | None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateActionEvent]:
        """Récupère les corporate actions pour les symboles donnés."""
        ...


# ---------------------------------------------------------------------------
# Implémentation Alpaca (Corporate Actions API v1)
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
        full_url = url + "?" + urllib.parse.urlencode(params)
        LOGGER.info("[Alpaca] GET %s", full_url)
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            timeout_attempts = 0
            try:
                while True:
                    try:
                        time.sleep(_PAUSE_BETWEEN_CALLS)
                        resp = self._session.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
                        if resp.status_code == 429 or resp.status_code >= 500:
                            delay = _BACKOFF_BASE * (2 ** attempt)
                            LOGGER.warning("Alpaca CA %s → %s, retry in %.1fs", path, resp.status_code, delay)
                            time.sleep(delay)
                            raise requests.exceptions.ConnectionError(f"HTTP {resp.status_code}")
                        resp.raise_for_status()
                        return resp.json()
                    except requests.exceptions.Timeout as exc:
                        timeout_attempts += 1
                        last_exc = exc
                        LOGGER.warning(
                            "Timeout Alpaca corporate actions | tentative=%s/%s path=%s",
                            timeout_attempts,
                            _MAX_TIMEOUT_RETRIES,
                            path,
                        )
                        if timeout_attempts >= _MAX_TIMEOUT_RETRIES:
                            LOGGER.error("Abandon après %s timeouts pour %s", _MAX_TIMEOUT_RETRIES, full_url)
                            raise
                        time.sleep(_TIMEOUT_BACKOFF_SECONDS)
            except requests.exceptions.ConnectionError as exc:
                last_exc = exc
                delay = _BACKOFF_BASE * (2 ** attempt)
                LOGGER.warning("Alpaca CA %s → %s, retry in %.1fs", path, type(exc).__name__, delay)
                time.sleep(delay)
        raise last_exc or RuntimeError("Max retries exceeded for Alpaca corporate actions")

    def fetch_events(
        self,
        symbols: list[str] | None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateActionEvent]:
        """Récupère dividendes et splits depuis Alpaca Corporate Actions API avec pagination."""
        events: list[CorporateActionEvent] = []
        ca_types_to_fetch = ["cash_dividend", "forward_split", "reverse_split"]
        params: dict[str, Any] = {
            "types": ",".join(ca_types_to_fetch),
            "limit": _PAGE_LIMIT,
            "sort": "asc",
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        if start_date:
            params["start"] = start_date.isoformat()
        if end_date:
            params["end"] = end_date.isoformat()

        page = 0
        while True:
            page += 1
            try:
                data = self._request("/v1/corporate-actions", params)
            except Exception:
                LOGGER.exception("Erreur lors de la récupération des corporate actions Alpaca (page %d)", page)
                break

            # --- Parsing : data["corporate_actions"] est un dict contenant les listes par type ---
            ca_data = data.get("corporate_actions")
            if not isinstance(ca_data, dict):
                LOGGER.error("Clé 'corporate_actions' absente ou invalide dans la réponse Alpaca (page %d)", page)
                break

            # cash_dividends
            for raw in ca_data.get("cash_dividends", []):
                if not isinstance(raw, dict):
                    continue
                try:
                    events.append(self._parse_dividend(raw))
                except Exception:
                    LOGGER.exception("Erreur parsing dividend: %r", raw)

            # forward_splits
            for raw in ca_data.get("forward_splits", []):
                if not isinstance(raw, dict):
                    continue
                try:
                    events.append(self._parse_split(raw, CaType.SPLIT))
                except Exception:
                    LOGGER.exception("Erreur parsing forward_split: %r", raw)

            # reverse_splits
            for raw in ca_data.get("reverse_splits", []):
                if not isinstance(raw, dict):
                    continue
                try:
                    events.append(self._parse_split(raw, CaType.REVERSE_SPLIT))
                except Exception:
                    LOGGER.exception("Erreur parsing reverse_split: %r", raw)

            # --- Pagination ---
            next_token = data.get("next_page_token")
            if not next_token:
                break
            LOGGER.info("Alpaca CA pagination page=%d events_so_far=%d next_token=%s", page, len(events), next_token[:20])
            params["page_token"] = next_token

        LOGGER.info(
            "Alpaca corporate actions fetched | symbols=%s range=%s→%s total_events=%d pages=%d",
            len(symbols) if symbols is not None else "ALL", start_date, end_date, len(events), page,
        )
        return events

    @staticmethod
    def _parse_dividend(raw: dict[str, Any]) -> CorporateActionEvent:
        return CorporateActionEvent(
            provider="alpaca",
            provider_event_id=raw.get("id"),
            symbol=str(raw.get("symbol", "")).upper(),
            ca_type=CaType.SPECIAL_DIVIDEND if raw.get("special") else CaType.CASH_DIVIDEND,
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
        split_from, split_to = AlpacaCorporateActionProvider._normalize_split_ratio(
            raw.get("old_rate", raw.get("from_factor", 1)),
            raw.get("new_rate", raw.get("to_factor", 1)),
        )
        return CorporateActionEvent(
            provider="alpaca",
            provider_event_id=raw.get("id"),
            symbol=str(raw.get("symbol", "")).upper(),
            ca_type=ca_type,
            split_from=split_from,
            split_to=split_to,
            ex_date=date.fromisoformat(raw["ex_date"]),
            record_date=date.fromisoformat(raw["record_date"]) if raw.get("record_date") else None,
            payable_date=date.fromisoformat(raw["payable_date"]) if raw.get("payable_date") else None,
            announcement_date=date.fromisoformat(raw["announcement_date"]) if raw.get("announcement_date") else None,
            raw_payload=raw,
        )

    @staticmethod
    def _normalize_split_ratio(old_rate: Any, new_rate: Any) -> tuple[int, int]:
        """Convertit les rates Alpaca en couple entier (split_from, split_to)."""
        old_fraction = Fraction(str(old_rate)).limit_denominator(10000)
        new_fraction = Fraction(str(new_rate)).limit_denominator(10000)
        if old_fraction <= 0 or new_fraction <= 0:
            raise ValueError(f"Split rate invalide old={old_rate!r} new={new_rate!r}")
        ratio = (new_fraction / old_fraction).limit_denominator(10000)
        return int(ratio.denominator), int(ratio.numerator)

