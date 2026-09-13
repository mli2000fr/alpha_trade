"""Connecteur research-only vers l'API REST locale ThetaData v3."""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests

DEFAULT_BASE_URL = "http://127.0.0.1:25503/v3/"


class ThetaDataError(RuntimeError):
    """Erreur contrôlée du connecteur ThetaData."""


class ThetaDataUnavailable(ThetaDataError):
    """Le terminal local ne répond pas."""


class ThetaDataHttpError(ThetaDataError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"ThetaData HTTP {status_code}: {message}")
        self.status_code = int(status_code)


@dataclass(frozen=True, slots=True)
class ThetaOptionPair:
    symbol: str
    expiration: date
    strike: float
    dte: int


def _validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or (parsed.hostname or "").lower() not in {
        "127.0.0.1", "localhost", "::1",
    }:
        raise ValueError("ThetaData doit utiliser un endpoint HTTP local.")
    return value.rstrip("/") + "/"


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("response", "results", "data"):
            values = payload.get(key)
            if isinstance(values, list):
                return [item for item in values if isinstance(item, dict)]
    return []


class ThetaDataClient:
    """Client synchrone minimal ; l'authentification reste dans Theta Terminal."""

    def __init__(
        self, *, base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 60.0,
        max_retries: int = 2, session: requests.Session | None = None,
        recorder: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.base_url = _validate_base_url(base_url)
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "alpha-trade-thetadata-options-smoke/0.1"})
        self.recorder = recorder

    def get_rows(self, path: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = urljoin(self.base_url, path.lstrip("/"))
        request_params = {**params, "format": "json"}
        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            try:
                response = self.session.get(
                    url, params=request_params, timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise ThetaDataUnavailable(
                    "Theta Terminal est absent ou inaccessible sur le port configuré."
                ) from exc
            elapsed = time.perf_counter() - started
            if (response.status_code == 429 or response.status_code >= 500) and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2**attempt
                time.sleep(delay)
                continue
            if not response.ok:
                message = response.text[:300].replace("\n", " ")
                raise ThetaDataHttpError(response.status_code, message)
            try:
                payload = response.json()
            except (requests.JSONDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ThetaDataError("Réponse ThetaData non JSON.") from exc
            rows = _rows_from_payload(payload)
            if self.recorder is not None:
                encoded = response.content
                self.recorder({
                    "path": path, "params": request_params,
                    "status_code": response.status_code, "elapsed_seconds": elapsed,
                    "response_bytes": len(encoded), "rows": len(rows),
                    "sha256": hashlib.sha256(encoded).hexdigest(), "payload": payload,
                })
            return rows
        raise AssertionError("Boucle de reprise ThetaData incohérente.")

    def list_quoted_contracts(
        self, symbol: str, session_date: date, *, max_dte: int,
    ) -> list[dict[str, Any]]:
        return self.get_rows("option/list/contracts/quote", params={
            "symbol": symbol.upper(), "date": session_date.isoformat(),
            "max_dte": int(max_dte),
        })

    def history_quotes(
        self, pair: ThetaOptionPair, session_date: date, *,
        start_time: str, end_time: str, interval: str = "1m",
    ) -> list[dict[str, Any]]:
        return self.get_rows("option/history/quote", params={
            "symbol": pair.symbol, "expiration": pair.expiration.isoformat(),
            "strike": f"{pair.strike:.3f}", "right": "both",
            "date": session_date.isoformat(), "start_time": start_time,
            "end_time": end_time, "interval": interval,
        })


def choose_atm_pair(
    contracts: list[dict[str, Any]], *, symbol: str, spot: float,
    entry_date: date, min_dte: int = 35, max_dte: int = 55,
    target_dte: int = 45,
) -> ThetaOptionPair | None:
    """Choisit une paire call/put cotée à J+1, sans information future."""
    pairs: dict[tuple[date, float], set[str]] = {}
    for row in contracts:
        try:
            expiration = date.fromisoformat(str(row["expiration"])[:10])
            strike = float(row["strike"])
            right = str(row["right"]).lower()
        except (KeyError, TypeError, ValueError):
            continue
        if right in {"c", "call"}:
            right = "call"
        elif right in {"p", "put"}:
            right = "put"
        else:
            continue
        dte = (expiration - entry_date).days
        if min_dte <= dte <= max_dte and strike > 0:
            pairs.setdefault((expiration, strike), set()).add(right)
    complete = [key for key, rights in pairs.items() if {"call", "put"}.issubset(rights)]
    if not complete or spot <= 0:
        return None
    expiration, strike = min(
        complete,
        key=lambda key: (abs(key[1] / spot - 1), abs((key[0] - entry_date).days - target_dte), key[0]),
    )
    return ThetaOptionPair(
        symbol=symbol.upper(), expiration=expiration, strike=strike,
        dte=(expiration - entry_date).days,
    )


def _normalize_quote(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        right = str(row["right"]).lower()
        right = "call" if right in {"c", "call"} else "put" if right in {"p", "put"} else ""
        timestamp = pd.Timestamp(row["timestamp"])
        bid = float(row["bid"])
        ask = float(row["ask"])
    except (KeyError, TypeError, ValueError):
        return None
    if not right or pd.isna(timestamp) or bid <= 0 or ask <= 0 or ask < bid:
        return None
    return {
        "right": right, "timestamp": timestamp, "bid": bid, "ask": ask,
        "bid_size": int(row.get("bid_size") or 0),
        "ask_size": int(row.get("ask_size") or 0),
    }


def select_synchronized_pair_quote(
    rows: list[dict[str, Any]], *, prefer: str,
    max_skew_seconds: int = 60,
) -> dict[str, Any] | None:
    """Sélectionne la première ou dernière paire NBBO synchrone de la fenêtre."""
    if prefer not in {"first", "last"}:
        raise ValueError("prefer doit valoir first ou last.")
    normalized = [quote for row in rows if (quote := _normalize_quote(row)) is not None]
    calls = [row for row in normalized if row["right"] == "call"]
    puts = [row for row in normalized if row["right"] == "put"]
    candidates: list[tuple[pd.Timestamp, float, dict[str, Any], dict[str, Any]]] = []
    for call in calls:
        for put in puts:
            skew = abs((call["timestamp"] - put["timestamp"]).total_seconds())
            if skew <= max_skew_seconds:
                decision_time = max(call["timestamp"], put["timestamp"])
                candidates.append((decision_time, skew, call, put))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    decision_time, skew, call, put = candidates[0 if prefer == "first" else -1]
    return {
        "timestamp": decision_time.isoformat(), "skew_seconds": float(skew),
        "call": {
            **{key: value for key, value in call.items() if key not in {"right", "timestamp"}},
            "quote_timestamp": call["timestamp"].isoformat(),
        },
        "put": {
            **{key: value for key, value in put.items() if key not in {"right", "timestamp"}},
            "quote_timestamp": put["timestamp"].isoformat(),
        },
    }
