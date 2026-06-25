"""Implémentations production de :class:`service.market.macro_signals.MacroDataProvider`.

Sources branchées :

- **Stooq** (gratuit, sans clé) — symboles ``^vix`` / ``^vix9d`` / ``^tnx``.
  Utilise :func:`service.stooq.clientStooq.fetch_daily_bars`.
- **EODHD** — symboles ``VIX.INDX`` / ``VXN.INDX`` / ``US10Y.INDX``.
  Utilise :func:`service.eodhd.clientEodhd.fetch_eod`.
- **FRED** — série ``DGS10`` (10Y Treasury yield, clé `KEY_FRED`).
  Utilise :func:`service.fred.clientFred.fetch_series_observations`.

Aucune méthode ne lève d'exception : tout échec → ``None`` (consommé en
fallback neutre par ``service.market.regime_manager``). Les réponses sont
mises en cache **par instance** et par ``(symbol, trade_date, lookback)``
pour éviter toute requête réseau supplémentaire dans le même cycle.

Cf. ``prompt/parttern/plan.md`` axe A — branchement effectif du
``MacroDataProvider`` exigé par ``C09`` / ``C10``.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable, Mapping, Sequence, cast

from common.market_calendar import getLastDateMarche, nyse_session_dates
from database.macro_indicators import (
    load_macro_indicator_daily_asof,
    load_macro_indicator_history_asof,
    persist_macro_indicator_daily,
    persist_market_macro_snapshot_daily,
)
from service.market.regime_manager import build_snapshot
from service.market.config import parse_market_regimes
from service.market.models import MarketRegimeState
from service.market.sentiment_provider import DbSentimentScoreProvider

LOGGER = logging.getLogger("service.market.macro_providers")

# Symboles par défaut (peuvent être surchargés via ``config.yaml``).
_DEFAULT_STOOQ_SYMBOLS = {
    "vix": "^vix",
    "vix_short": "^vix9d",
    "us10y": "^tnx",   # 10Y Treasury yield (en %)
}
_DEFAULT_EODHD_SYMBOLS = {
    "vix": "VIX.INDX",
    "vix_short": "VIX9D.INDX",
    "vxn": "VXN.INDX",         # Nasdaq-100 Volatility Index
    "vix3m": "VIX3M.INDX",     # VIX 3-Month (term structure)
    "move": "MOVE.INDX",       # ICE BofA Bond Volatility Index
    "rvx": "RVX.INDX",         # Russell 2000 Volatility Index (Small Caps)
    "us10y": "US10Y.INDX",
}
_DEFAULT_FRED_SERIES = {
    "us10y": "DGS10",
}

# Combien de jours en arrière chercher pour trouver la dernière clôture
# disponible (week-ends + jours fériés US).
_CLOSE_LOOKBACK_DAYS = 7
MACRO_PIT_MODE_ASOF_INCLUSIVE = "asof_inclusive"
MACRO_PIT_MODE_J_MINUS_1_STRICT = "j_minus_1_strict"


def normalize_macro_pit_mode(value: object) -> str:
    resolved = str(value or "").strip().lower()
    aliases = {
        "": MACRO_PIT_MODE_ASOF_INCLUSIVE,
        "asof": MACRO_PIT_MODE_ASOF_INCLUSIVE,
        "asof_inclusive": MACRO_PIT_MODE_ASOF_INCLUSIVE,
        "inclusive": MACRO_PIT_MODE_ASOF_INCLUSIVE,
        "j-1": MACRO_PIT_MODE_J_MINUS_1_STRICT,
        "j_1": MACRO_PIT_MODE_J_MINUS_1_STRICT,
        "j_minus_1": MACRO_PIT_MODE_J_MINUS_1_STRICT,
        "j_minus_1_strict": MACRO_PIT_MODE_J_MINUS_1_STRICT,
        "strict_before": MACRO_PIT_MODE_J_MINUS_1_STRICT,
    }
    return aliases.get(resolved, MACRO_PIT_MODE_ASOF_INCLUSIVE)


def resolve_macro_pit_mode(
    yaml_cfg: Mapping[str, Any] | None,
    *,
    execution_context: str = "live",
    macro_pit_mode: str | None = None,
) -> str:
    requested = str(macro_pit_mode or "").strip().lower()
    if requested and requested != "yaml_default":
        return normalize_macro_pit_mode(requested)
    root_cfg = yaml_cfg if isinstance(yaml_cfg, Mapping) else {}
    market_cfg = root_cfg.get("market_regimes") if isinstance(root_cfg, Mapping) else {}
    market_cfg = market_cfg if isinstance(market_cfg, Mapping) else {}
    if str(execution_context or "live").strip().lower() == "backtest":
        return normalize_macro_pit_mode(market_cfg.get("macro_pit_mode_backtest"))
    return MACRO_PIT_MODE_ASOF_INCLUSIVE


def _is_strict_before_mode(*, yaml_cfg: Mapping[str, Any] | None, execution_context: str, macro_pit_mode: str | None) -> bool:
    return resolve_macro_pit_mode(
        yaml_cfg,
        execution_context=execution_context,
        macro_pit_mode=macro_pit_mode,
    ) == MACRO_PIT_MODE_J_MINUS_1_STRICT


def _resolve_provider_trade_date(trade_date: date, *, strict_before: bool) -> date:
    if not strict_before:
        return trade_date
    try:
        return getLastDateMarche(trade_date)
    except Exception:
        LOGGER.debug("Résolution J-1 macro impossible pour %s ; fallback date courante.", trade_date, exc_info=True)
        return trade_date


def _coerce_float(value: object) -> float | None:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _effective_source_from_mapping(source_by_signal: Mapping[str, str]) -> str | None:
    values = [str(value).strip().lower() for value in source_by_signal.values() if str(value).strip()]
    if not values:
        return None
    unique_values = sorted(set(values))
    if len(unique_values) == 1:
        return unique_values[0]
    return "mixed"


def _build_source_summary(source_by_signal: Mapping[str, str]) -> dict[str, Any]:
    payload = {
        str(key): str(value).strip().lower()
        for key, value in source_by_signal.items()
        if str(key).strip() and str(value).strip()
    }
    source_effective = _effective_source_from_mapping(payload)
    if not payload or source_effective is None:
        return {}
    return {
        "source_effective": source_effective,
        "source_by_signal": payload,
    }


def _signal_key_for_method(method: str) -> str | None:
    if method == "get_vix_close":
        return "vix"
    if method == "get_vix_short_term_close":
        return "vix_short"
    if method == "get_vxn_close":
        return "vxn"
    if method == "get_vix3m_close":
        return "vix3m"
    if method == "get_move_close":
        return "move"
    if method == "get_rvx_close":
        return "rvx"
    if method == "get_us10y_history":
        return "yield_10y"
    return None


def _resolve_signal_source(provider: Any, signal_key: str) -> str | None:
    get_source_summary = getattr(provider, "get_macro_source_summary", None)
    if callable(get_source_summary):
        try:
            summary = get_source_summary()
        except Exception:
            summary = None
        if isinstance(summary, dict):
            by_signal = summary.get("source_by_signal")
            if isinstance(by_signal, dict):
                value = str(by_signal.get(signal_key) or "").strip().lower()
                if value:
                    return value
    fallback = str(getattr(provider, "source_name", type(provider).__name__) or "").strip().lower()
    return fallback or None


def _log_successful_fetch(*, provider_name: str, key: str, symbol: str, trade_date: date, bars: Sequence[Mapping[str, Any]]) -> None:
    """Journalise une preuve positive compacte quand un fetch réseau aboutit.

    - ``INFO`` pour les séries suivies opérationnellement (VIX / VIX9D / 10Y).
    - Aucun log si ``bars`` est vide ou si aucune clôture exploitable n'est trouvée.
    """
    if not bars:
        return
    last_date: date | None = None
    last_close: float | None = None
    for row in bars:
        raw_date = row.get("date")
        if isinstance(raw_date, str):
            try:
                parsed_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                continue
        elif isinstance(raw_date, date):
            parsed_date = raw_date
        else:
            continue
        parsed_close = _coerce_float(row.get("close"))
        if parsed_close is None:
            continue
        if last_date is None or parsed_date > last_date:
            last_date = parsed_date
            last_close = parsed_close
    if last_date is None or last_close is None:
        return
    level = logging.INFO if key in {"vix", "vix_short", "vxn", "vix3m", "move", "rvx", "us10y"} else logging.DEBUG
    LOGGER.log(
        level,
        "%s: fetch %s ok key=%s trade_date=%s rows=%d last_date=%s last_close=%.4f",
        provider_name,
        symbol,
        key,
        trade_date,
        len(bars),
        last_date,
        last_close,
    )


def _last_close(bars: Sequence[Mapping[str, Any]], on_or_before: date) -> float | None:
    """Retourne le dernier ``close`` <= ``on_or_before`` parmi ``bars``."""
    if not bars:
        return None
    best: tuple[date, float] | None = None
    for row in bars:
        d = row.get("date")
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                continue
        if not isinstance(d, date) or d > on_or_before:
            continue
        c = row.get("close")
        if c is None:
            continue
        cf = _coerce_float(c)
        if cf is None:
            continue
        if best is None or d > best[0]:
            best = (d, cf)
    return best[1] if best else None


def _close_history(bars: Sequence[Mapping[str, Any]], on_or_before: date, n: int) -> list[float]:
    """Retourne les ``n`` derniers ``close`` <= ``on_or_before``, ordre chronologique."""
    rows: list[tuple[date, float]] = []
    for row in bars:
        d = row.get("date")
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                continue
        if not isinstance(d, date) or d > on_or_before:
            continue
        c = row.get("close")
        cf = _coerce_float(c)
        if cf is None:
            continue
        rows.append((d, cf))
    rows.sort(key=lambda t: t[0])
    return [c for _, c in rows[-n:]]


def _extract_latest_10y_close(provider: Any, trade_date: date) -> float | None:
    if provider is None:
        return None
    getter = getattr(provider, "get_us10y_close", None)
    if callable(getter):
        try:
            return _coerce_float(getter(trade_date))
        except Exception:
            return None
    try:
        history = provider.get_us10y_history(trade_date, 2)
    except Exception:
        history = None
    if not history:
        return None
    return _coerce_float(history[-1])


# ---------------------------------------------------------------------------
# Stooq
# ---------------------------------------------------------------------------


class StooqMacroProvider:
    """Provider VIX / 10Y basé sur Stooq (CSV public, sans clé)."""

    source_name = "stooq"

    def __init__(self, symbols: Mapping[str, str] | None = None) -> None:
        self._symbols = dict(_DEFAULT_STOOQ_SYMBOLS)
        if symbols:
            self._symbols.update({k: str(v) for k, v in symbols.items() if v})
        self._cache: dict[tuple[str, date, int], list[dict[str, Any]]] = {}
        self._last_source_by_signal: dict[str, str] = {}

    def _fetch(self, key: str, trade_date: date, days_back: int) -> list[dict[str, Any]]:
        cache_key = (key, trade_date, days_back)
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            from service.stooq.clientStooq import fetch_daily_bars
        except Exception:  # pragma: no cover - import-time
            LOGGER.warning("StooqMacroProvider: import service.stooq impossible.", exc_info=True)
            self._cache[cache_key] = []
            return []
        symbol = self._symbols.get(key)
        if not symbol:
            self._cache[cache_key] = []
            return []
        start = trade_date - timedelta(days=days_back)
        try:
            bars = fetch_daily_bars(symbol, start=start, end=trade_date)
        except Exception:
            LOGGER.warning("StooqMacroProvider: fetch %s a échoué.", symbol, exc_info=True)
            bars = []
        normalised = list(bars)
        _log_successful_fetch(
            provider_name="StooqMacroProvider",
            key=key,
            symbol=str(symbol),
            trade_date=trade_date,
            bars=normalised,
        )
        self._cache[cache_key] = normalised
        return self._cache[cache_key]

    def get_vix_close(self, trade_date: date) -> float | None:
        bars = self._fetch("vix", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["vix"] = self.source_name
        else:
            self._last_source_by_signal.pop("vix", None)
        return value

    def get_vix_short_term_close(self, trade_date: date) -> float | None:
        bars = self._fetch("vix_short", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["vix_short"] = self.source_name
        else:
            self._last_source_by_signal.pop("vix_short", None)
        return value

    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None:
        # On élargit la fenêtre : 2 × lookback pour absorber week-ends/feries.
        days = max(lookback_days * 2 + 5, lookback_days + 5)
        bars = self._fetch("us10y", trade_date, days)
        if not bars:
            self._last_source_by_signal.pop("yield_10y", None)
            return None
        history = _close_history(bars, trade_date, lookback_days)
        if len(history) >= 2:
            self._last_source_by_signal["yield_10y"] = self.source_name
            return history
        self._last_source_by_signal.pop("yield_10y", None)
        return None

    def get_us10y_close(self, trade_date: date) -> float | None:
        bars = self._fetch("us10y", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["yield_10y"] = self.source_name
        else:
            self._last_source_by_signal.pop("yield_10y", None)
        return value

    # Stooq ne couvre pas VXN, VIX3M, MOVE, RVX
    def get_vxn_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("vxn", None)
        return None

    def get_vix3m_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("vix3m", None)
        return None

    def get_move_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("move", None)
        return None

    def get_rvx_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("rvx", None)
        return None

    def get_macro_source_summary(self) -> dict[str, Any]:
        return _build_source_summary(self._last_source_by_signal)


# ---------------------------------------------------------------------------
# EODHD
# ---------------------------------------------------------------------------


class EodhdMacroProvider:
    """Provider VIX / 10Y basé sur EODHD (token requis dans l'environnement).

    1 appel = 1 call de quota EODHD. Les réponses sont cachées par instance.
    """

    source_name = "eodhd"

    def __init__(self, symbols: Mapping[str, str] | None = None) -> None:
        self._symbols = dict(_DEFAULT_EODHD_SYMBOLS)
        if symbols:
            self._symbols.update({k: str(v) for k, v in symbols.items() if v})
        self._cache: dict[tuple[str, date, int], list[dict[str, Any]]] = {}
        self._last_source_by_signal: dict[str, str] = {}

    def _fetch(self, key: str, trade_date: date, days_back: int) -> list[dict[str, Any]]:
        cache_key = (key, trade_date, days_back)
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            from service.eodhd.clientEodhd import fetch_eod
        except Exception:
            LOGGER.warning("EodhdMacroProvider: import service.eodhd impossible.", exc_info=True)
            self._cache[cache_key] = []
            return []
        symbol = self._symbols.get(key)
        if not symbol:
            self._cache[cache_key] = []
            return []
        start = (trade_date - timedelta(days=days_back)).isoformat()
        end = trade_date.isoformat()
        try:
            payload = fetch_eod(symbol, start=start, end=end)
        except Exception:
            LOGGER.warning("EodhdMacroProvider: fetch %s a échoué.", symbol, exc_info=True)
            payload = []
        # Normalise le format vers le contrat ``{"date": date, "close": float}``.
        normalised: list[dict[str, Any]] = []
        for row in payload or []:
            d_raw = row.get("date") or row.get("Date")
            if isinstance(d_raw, str):
                try:
                    d = date.fromisoformat(d_raw[:10])
                except ValueError:
                    continue
            elif isinstance(d_raw, date):
                d = d_raw
            else:
                continue
            close = row.get("close") or row.get("adjusted_close") or row.get("Close")
            close_f = _coerce_float(close)
            if close_f is None:
                continue
            normalised.append({"date": d, "close": close_f})
        _log_successful_fetch(
            provider_name="EodhdMacroProvider",
            key=key,
            symbol=str(symbol),
            trade_date=trade_date,
            bars=normalised,
        )
        self._cache[cache_key] = normalised
        return normalised

    def get_vix_close(self, trade_date: date) -> float | None:
        bars = self._fetch("vix", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["vix"] = self.source_name
        else:
            self._last_source_by_signal.pop("vix", None)
        return value

    def get_vix_short_term_close(self, trade_date: date) -> float | None:
        bars = self._fetch("vix_short", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["vix_short"] = self.source_name
        else:
            self._last_source_by_signal.pop("vix_short", None)
        return value

    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None:
        days = max(lookback_days * 2 + 5, lookback_days + 5)
        bars = self._fetch("us10y", trade_date, days)
        if not bars:
            self._last_source_by_signal.pop("yield_10y", None)
            return None
        history = _close_history(bars, trade_date, lookback_days)
        if len(history) >= 2:
            self._last_source_by_signal["yield_10y"] = self.source_name
            return history
        self._last_source_by_signal.pop("yield_10y", None)
        return None

    def get_us10y_close(self, trade_date: date) -> float | None:
        bars = self._fetch("us10y", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["yield_10y"] = self.source_name
        else:
            self._last_source_by_signal.pop("yield_10y", None)
        return value

    def get_vxn_close(self, trade_date: date) -> float | None:
        bars = self._fetch("vxn", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["vxn"] = self.source_name
        else:
            self._last_source_by_signal.pop("vxn", None)
        return value

    def get_vix3m_close(self, trade_date: date) -> float | None:
        bars = self._fetch("vix3m", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["vix3m"] = self.source_name
        else:
            self._last_source_by_signal.pop("vix3m", None)
        return value

    def get_move_close(self, trade_date: date) -> float | None:
        bars = self._fetch("move", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["move"] = self.source_name
        else:
            self._last_source_by_signal.pop("move", None)
        return value

    def get_rvx_close(self, trade_date: date) -> float | None:
        bars = self._fetch("rvx", trade_date, _CLOSE_LOOKBACK_DAYS)
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["rvx"] = self.source_name
        else:
            self._last_source_by_signal.pop("rvx", None)
        return value

    def get_macro_source_summary(self) -> dict[str, Any]:
        return _build_source_summary(self._last_source_by_signal)


# ---------------------------------------------------------------------------
# FRED
# ---------------------------------------------------------------------------


class FredMacroProvider:
    """Provider 10Y basé sur FRED (clé via `KEY_FRED` par défaut)."""

    source_name = "fred"

    def __init__(self, *, series: Mapping[str, str] | None = None, api_key_env: str = "KEY_FRED") -> None:
        self._series = dict(_DEFAULT_FRED_SERIES)
        if series:
            self._series.update({k: str(v) for k, v in series.items() if v})
        self._api_key_env = str(api_key_env or "KEY_FRED")
        self._cache: dict[tuple[str, date, int], list[dict[str, Any]]] = {}
        self._last_source_by_signal: dict[str, str] = {}

    def _fetch(self, key: str, trade_date: date, days_back: int) -> list[dict[str, Any]]:
        cache_key = (key, trade_date, days_back)
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            from service.fred.clientFred import FredFetchError, fetch_series_observations
        except Exception:
            LOGGER.warning("FredMacroProvider: import service.fred impossible.", exc_info=True)
            self._cache[cache_key] = []
            return []
        series_id = self._series.get(key)
        if not series_id:
            self._cache[cache_key] = []
            return []
        start = (trade_date - timedelta(days=days_back)).isoformat()
        end = trade_date.isoformat()
        try:
            payload = fetch_series_observations(
                series_id,
                start=start,
                end=end,
                api_key_env=self._api_key_env,
            )
        except Exception as exc:
            if exc.__class__.__name__ == "FredFetchError":
                LOGGER.warning("FredMacroProvider: fetch %s a échoué.", series_id, exc_info=True)
            else:
                LOGGER.warning("FredMacroProvider: fetch %s a échoué.", series_id, exc_info=True)
            payload = []
        normalised: list[dict[str, Any]] = []
        for row in payload or []:
            raw_date = row.get("date")
            if isinstance(raw_date, str):
                try:
                    parsed_date = date.fromisoformat(raw_date[:10])
                except ValueError:
                    continue
            elif isinstance(raw_date, date):
                parsed_date = raw_date
            else:
                continue
            raw_value = row.get("value")
            if isinstance(raw_value, str) and raw_value.strip() == ".":
                continue
            parsed_value = _coerce_float(raw_value)
            if parsed_value is None:
                continue
            normalised.append({"date": parsed_date, "close": parsed_value})
        _log_successful_fetch(
            provider_name="FredMacroProvider",
            key=key,
            symbol=str(series_id),
            trade_date=trade_date,
            bars=normalised,
        )
        self._cache[cache_key] = normalised
        return normalised

    def get_vix_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("vix", None)
        return None

    def get_vix_short_term_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("vix_short", None)
        return None

    # FRED ne couvre pas VXN, VIX3M, MOVE, RVX
    def get_vxn_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("vxn", None)
        return None

    def get_vix3m_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("vix3m", None)
        return None

    def get_move_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("move", None)
        return None

    def get_rvx_close(self, trade_date: date) -> float | None:
        self._last_source_by_signal.pop("rvx", None)
        return None

    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None:
        days = max(lookback_days * 3 + 10, lookback_days + 10)
        bars = self._fetch("us10y", trade_date, days)
        if not bars:
            self._last_source_by_signal.pop("yield_10y", None)
            return None
        history = _close_history(bars, trade_date, lookback_days)
        if len(history) >= 2:
            self._last_source_by_signal["yield_10y"] = self.source_name
            return history
        self._last_source_by_signal.pop("yield_10y", None)
        return None

    def get_us10y_close(self, trade_date: date) -> float | None:
        bars = self._fetch("us10y", trade_date, max(_CLOSE_LOOKBACK_DAYS * 2, 14))
        value = _last_close(bars, trade_date)
        if value is not None:
            self._last_source_by_signal["yield_10y"] = self.source_name
        else:
            self._last_source_by_signal.pop("yield_10y", None)
        return value

    def get_macro_source_summary(self) -> dict[str, Any]:
        return _build_source_summary(self._last_source_by_signal)


class RoutedMacroProvider:
    """Route chaque signal macro vers un provider dédié, avec synthèse de source."""

    source_name = "routed"

    def __init__(
        self,
        *,
        vix_provider: Any | None = None,
        vix_short_provider: Any | None = None,
        yield_provider: Any | None = None,
    ) -> None:
        self._vix_provider = vix_provider
        self._vix_short_provider = vix_short_provider
        self._yield_provider = yield_provider
        self._last_source_by_signal: dict[str, str] = {}

    def _record_source(self, signal_key: str, provider: Any | None, value: Any) -> None:
        if value is None or provider is None:
            self._last_source_by_signal.pop(signal_key, None)
            return
        resolved_source = _resolve_signal_source(provider, signal_key)
        if resolved_source:
            self._last_source_by_signal[signal_key] = resolved_source
        else:
            self._last_source_by_signal.pop(signal_key, None)

    def get_vix_close(self, trade_date: date) -> float | None:
        provider = self._vix_provider
        if provider is None:
            self._last_source_by_signal.pop("vix", None)
            return None
        try:
            value = provider.get_vix_close(trade_date)
        except Exception:
            value = None
        self._record_source("vix", provider, value)
        return value

    def get_vix_short_term_close(self, trade_date: date) -> float | None:
        provider = self._vix_short_provider
        if provider is None:
            self._last_source_by_signal.pop("vix_short", None)
            return None
        try:
            value = provider.get_vix_short_term_close(trade_date)
        except Exception:
            value = None
        self._record_source("vix_short", provider, value)
        return value

    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None:
        provider = self._yield_provider
        if provider is None:
            self._last_source_by_signal.pop("yield_10y", None)
            return None
        try:
            value = provider.get_us10y_history(trade_date, lookback_days)
        except Exception:
            value = None
        self._record_source("yield_10y", provider, value)
        return value

    def get_us10y_close(self, trade_date: date) -> float | None:
        provider = self._yield_provider
        if provider is None:
            self._last_source_by_signal.pop("yield_10y", None)
            return None
        value = _extract_latest_10y_close(provider, trade_date)
        self._record_source("yield_10y", provider, value)
        return value

    # --- VXN / VIX3M / MOVE / RVX : routés vers le provider primaire ---
    def get_vxn_close(self, trade_date: date) -> float | None:
        provider = self._vix_provider
        if provider is None:
            self._last_source_by_signal.pop("vxn", None)
            return None
        try:
            value = provider.get_vxn_close(trade_date)
        except Exception:
            value = None
        self._record_source("vxn", provider, value)
        return value

    def get_vix3m_close(self, trade_date: date) -> float | None:
        provider = self._vix_provider
        if provider is None:
            self._last_source_by_signal.pop("vix3m", None)
            return None
        try:
            value = provider.get_vix3m_close(trade_date)
        except Exception:
            value = None
        self._record_source("vix3m", provider, value)
        return value

    def get_move_close(self, trade_date: date) -> float | None:
        provider = self._vix_provider
        if provider is None:
            self._last_source_by_signal.pop("move", None)
            return None
        try:
            value = provider.get_move_close(trade_date)
        except Exception:
            value = None
        self._record_source("move", provider, value)
        return value

    def get_rvx_close(self, trade_date: date) -> float | None:
        provider = self._vix_provider
        if provider is None:
            self._last_source_by_signal.pop("rvx", None)
            return None
        try:
            value = provider.get_rvx_close(trade_date)
        except Exception:
            value = None
        self._record_source("rvx", provider, value)
        return value

    def get_macro_source_summary(self) -> dict[str, Any]:
        return _build_source_summary(self._last_source_by_signal)


class TableFirstMacroProvider:
    """Consulte d'abord ``stock_macro_indicators_daily``, puis fallback réseau.

    La table sert de cache partagé inter-runs. En cas de fallback réussi vers le
    provider sous-jacent, la valeur est réinsérée best-effort dans la table afin
    d'éviter les appels EODHD/FRED/Stooq aux runs suivants.
    """

    source_name = "db_cache"

    def __init__(
        self,
        provider: Any | None,
        *,
        engine=None,
        strict_before: bool = False,
        persist_fallback_hits: bool = True,
    ) -> None:
        self._provider = provider
        self._engine = engine
        self._strict_before: bool = True if strict_before else False
        self._persist_fallback_hits: bool = True if persist_fallback_hits else False
        self._last_source_by_signal: dict[str, str] = {}

    def _load_cached_row(self, trade_date: date) -> dict[str, Any] | None:
        try:
            return load_macro_indicator_daily_asof(
                trade_date=trade_date,
                engine=self._engine,
                strict_before=self._strict_before,
            )
        except Exception:
            LOGGER.debug("TableFirstMacroProvider: lecture cache macro impossible.", exc_info=True)
            return None

    def _load_cached_history(self, trade_date: date, *, column: str, lookback_days: int) -> list[float] | None:
        try:
            return load_macro_indicator_history_asof(
                trade_date=trade_date,
                column=column,
                lookback_days=lookback_days,
                engine=self._engine,
                strict_before=self._strict_before,
            )
        except Exception:
            LOGGER.debug("TableFirstMacroProvider: lecture historique macro impossible.", exc_info=True)
            return None

    def _persist_fallback_value(self, *, trade_date: date, value_key: str, value: Any) -> None:
        if not self._persist_fallback_hits or value is None:
            return
        kwargs = {"trade_date": trade_date, value_key: value, "engine": self._engine}
        try:
            persist_macro_indicator_daily(**kwargs)
        except Exception:
            LOGGER.debug("TableFirstMacroProvider: write-back macro cache impossible.", exc_info=True)

    def _record_source(self, signal_key: str, source: str | None) -> None:
        resolved_source = str(source or "").strip().lower()
        if resolved_source:
            self._last_source_by_signal[signal_key] = resolved_source
        else:
            self._last_source_by_signal.pop(signal_key, None)

    def get_vix_close(self, trade_date: date) -> float | None:
        row = self._load_cached_row(trade_date)
        cached_value = _coerce_float(row.get("vix")) if row else None
        if cached_value is not None:
            self._record_source("vix", self.source_name)
            return cached_value
        provider = self._provider
        if provider is None:
            self._record_source("vix", None)
            return None
        provider_trade_date = _resolve_provider_trade_date(trade_date, strict_before=self._strict_before)
        try:
            value = provider.get_vix_close(provider_trade_date)
        except Exception:
            value = None
        if value is not None:
            self._persist_fallback_value(trade_date=provider_trade_date, value_key="vix", value=value)
            self._record_source("vix", _resolve_signal_source(provider, "vix"))
            return value
        self._record_source("vix", None)
        return None

    def get_vix_short_term_close(self, trade_date: date) -> float | None:
        row = self._load_cached_row(trade_date)
        cached_value = _coerce_float(row.get("vix9d")) if row else None
        if cached_value is not None:
            self._record_source("vix_short", self.source_name)
            return cached_value
        provider = self._provider
        if provider is None:
            self._record_source("vix_short", None)
            return None
        provider_trade_date = _resolve_provider_trade_date(trade_date, strict_before=self._strict_before)
        try:
            value = provider.get_vix_short_term_close(provider_trade_date)
        except Exception:
            value = None
        if value is not None:
            self._persist_fallback_value(trade_date=provider_trade_date, value_key="vix9d", value=value)
            self._record_source("vix_short", _resolve_signal_source(provider, "vix_short"))
            return value
        self._record_source("vix_short", None)
        return None

    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None:
        cached_history = self._load_cached_history(trade_date, column="ten_y", lookback_days=lookback_days)
        if cached_history and len(cached_history) >= 2:
            self._record_source("yield_10y", self.source_name)
            return cached_history
        provider = self._provider
        if provider is None:
            self._record_source("yield_10y", None)
            return None
        provider_trade_date: date = trade_date
        if self._strict_before:
            try:
                resolved_trade_date = getLastDateMarche(cast(Any, trade_date))
                if isinstance(resolved_trade_date, date):
                    provider_trade_date = resolved_trade_date
            except Exception:
                LOGGER.debug(
                    "Résolution J-1 yield impossible pour %s ; fallback date courante.",
                    trade_date,
                    exc_info=True,
                )
        try:
            history = cast(list[float] | None, provider.get_us10y_history(provider_trade_date, lookback_days))
        except Exception:
            history = None
        if history is not None and len(history) >= 2:
            self._persist_fallback_value(trade_date=provider_trade_date, value_key="ten_y", value=history[-1])
            self._record_source("yield_10y", _resolve_signal_source(provider, "yield_10y"))
            return history
        self._record_source("yield_10y", None)
        return None

    def get_us10y_close(self, trade_date: date) -> float | None:
        row = self._load_cached_row(trade_date)
        cached_value = _coerce_float(row.get("ten_y")) if row else None
        if cached_value is not None:
            self._record_source("yield_10y", self.source_name)
            return cached_value
        provider = self._provider
        if provider is None:
            self._record_source("yield_10y", None)
            return None
        provider_trade_date = _resolve_provider_trade_date(trade_date, strict_before=self._strict_before)
        value = _extract_latest_10y_close(provider, provider_trade_date)
        if value is not None:
            self._persist_fallback_value(trade_date=provider_trade_date, value_key="ten_y", value=value)
            self._record_source("yield_10y", _resolve_signal_source(provider, "yield_10y"))
            return value
        self._record_source("yield_10y", None)
        return None

    # --- VXN / VIX3M / MOVE / RVX : cache DB + fallback réseau ---
    def _get_cached_or_fallback(
        self,
        trade_date: date,
        *,
        db_column: str,
        signal_key: str,
        provider_method: str,
        persist_value_key: str,
    ) -> float | None:
        """Pattern générique : lit la colonne DB, sinon fallback provider."""
        row = self._load_cached_row(trade_date)
        cached_value = _coerce_float(row.get(db_column)) if row else None
        if cached_value is not None:
            self._record_source(signal_key, self.source_name)
            return cached_value
        provider = self._provider
        if provider is None:
            self._record_source(signal_key, None)
            return None
        provider_trade_date = _resolve_provider_trade_date(trade_date, strict_before=self._strict_before)
        try:
            value = getattr(provider, provider_method)(provider_trade_date)
        except Exception:
            value = None
        if value is not None:
            self._persist_fallback_value(trade_date=provider_trade_date, value_key=persist_value_key, value=value)
            self._record_source(signal_key, _resolve_signal_source(provider, signal_key))
            return value
        self._record_source(signal_key, None)
        return None

    def get_vxn_close(self, trade_date: date) -> float | None:
        return self._get_cached_or_fallback(
            trade_date,
            db_column="vxn",
            signal_key="vxn",
            provider_method="get_vxn_close",
            persist_value_key="vxn",
        )

    def get_vix3m_close(self, trade_date: date) -> float | None:
        return self._get_cached_or_fallback(
            trade_date,
            db_column="vix3m",
            signal_key="vix3m",
            provider_method="get_vix3m_close",
            persist_value_key="vix3m",
        )

    def get_move_close(self, trade_date: date) -> float | None:
        return self._get_cached_or_fallback(
            trade_date,
            db_column="move",
            signal_key="move",
            provider_method="get_move_close",
            persist_value_key="move",
        )

    def get_rvx_close(self, trade_date: date) -> float | None:
        return self._get_cached_or_fallback(
            trade_date,
            db_column="rvx",
            signal_key="rvx",
            provider_method="get_rvx_close",
            persist_value_key="rvx",
        )

    def get_macro_source_summary(self) -> dict[str, Any]:
        return _build_source_summary(self._last_source_by_signal)


# ---------------------------------------------------------------------------
# Composite + factory
# ---------------------------------------------------------------------------


class CompositeMacroProvider:
    """Essaie les providers dans l'ordre fourni : la 1ère valeur non ``None`` gagne."""

    def __init__(self, providers: Sequence[Any]) -> None:
        self._providers = list(providers)
        self._last_source_by_signal: dict[str, str] = {}

    def _first_non_none(self, method: str, *args: Any) -> Any:
        signal_key = _signal_key_for_method(method)
        for p in self._providers:
            try:
                v = getattr(p, method)(*args)
            except Exception:
                v = None
            if v is not None:
                if signal_key is not None:
                    provider_source = str(getattr(p, "source_name", type(p).__name__)).strip().lower()
                    self._last_source_by_signal[signal_key] = provider_source
                return v
        if signal_key is not None:
            self._last_source_by_signal.pop(signal_key, None)
        return None

    def get_vix_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_vix_close", trade_date)

    def get_vix_short_term_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_vix_short_term_close", trade_date)

    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None:
        return self._first_non_none("get_us10y_history", trade_date, lookback_days)

    def get_us10y_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_us10y_close", trade_date)

    def get_vxn_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_vxn_close", trade_date)

    def get_vix3m_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_vix3m_close", trade_date)

    def get_move_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_move_close", trade_date)

    def get_rvx_close(self, trade_date: date) -> float | None:
        return self._first_non_none("get_rvx_close", trade_date)

    def get_macro_source_summary(self) -> dict[str, Any]:
        return _build_source_summary(self._last_source_by_signal)


def _build_primary_macro_provider(
    choice: str,
    *,
    stooq_overrides: Mapping[str, str] | None,
    eodhd_overrides: Mapping[str, str] | None,
) -> Any | None:
    if choice == "none":
        return None
    if choice == "stooq":
        return StooqMacroProvider(symbols=stooq_overrides or None)
    if choice == "eodhd":
        return EodhdMacroProvider(symbols=eodhd_overrides or None)
    providers: list[Any] = [StooqMacroProvider(symbols=stooq_overrides or None)]
    import os as _os
    if _os.getenv("EODHD_API_TOKEN") or _os.getenv("EODHD_TOKEN"):
        providers.append(EodhdMacroProvider(symbols=eodhd_overrides or None))
    return CompositeMacroProvider(providers)


def _build_yield_macro_provider(
    *,
    yields_cfg: Mapping[str, Any],
    fred_cfg: Mapping[str, Any],
    stooq_overrides: Mapping[str, str] | None,
    eodhd_overrides: Mapping[str, str] | None,
    default_provider: Any | None,
) -> Any | None:
    choice = str(yields_cfg.get("provider", "default") or "default").strip().lower()
    if choice in {"", "default", "primary", "auto"}:
        return default_provider
    if choice == "none":
        return None
    if choice == "stooq":
        return StooqMacroProvider(symbols=stooq_overrides or None)
    if choice == "eodhd":
        return EodhdMacroProvider(symbols=eodhd_overrides or None)
    if choice == "fred":
        series_id = str(
            yields_cfg.get("fred_series_10y")
            or fred_cfg.get("series_10y")
            or _DEFAULT_FRED_SERIES["us10y"]
        ).strip().upper()
        api_key_env = str(fred_cfg.get("api_key_env") or "KEY_FRED").strip() or "KEY_FRED"
        fred_provider = FredMacroProvider(series={"us10y": series_id}, api_key_env=api_key_env)
        if default_provider is None:
            return fred_provider
        return CompositeMacroProvider([fred_provider, default_provider])
    return default_provider


def _build_network_macro_provider(yaml_cfg: Mapping[str, Any] | None) -> Any | None:
    root_cfg = yaml_cfg if isinstance(yaml_cfg, Mapping) else {}
    cfg = root_cfg.get("market_regimes") if isinstance(root_cfg, Mapping) else None
    cfg = cfg or {}
    fred_cfg = root_cfg.get("fred") if isinstance(root_cfg, Mapping) else None
    fred_cfg = fred_cfg if isinstance(fred_cfg, Mapping) else {}
    choice = str(cfg.get("macro_provider", "composite") or "composite").strip().lower()

    vix_sym = (cfg.get("vix") or {}).get("symbol")
    vix_short_sym = (cfg.get("vix") or {}).get("short_symbol")
    vxn_sym = (cfg.get("vxn") or {}).get("symbol")
    vix3m_sym = (cfg.get("vix3m") or {}).get("symbol")
    move_sym = (cfg.get("move") or {}).get("symbol")
    rvx_sym = (cfg.get("rvx") or {}).get("symbol")
    y10_sym = (cfg.get("yields") or {}).get("symbol_10y")

    stooq_overrides: dict[str, str] = {}
    eodhd_overrides: dict[str, str] = {}
    if vix_sym:
        if str(vix_sym).startswith("^"):
            stooq_overrides["vix"] = str(vix_sym)
        else:
            eodhd_overrides["vix"] = str(vix_sym) if "." in str(vix_sym) else f"{vix_sym}.INDX"
    if vix_short_sym:
        if str(vix_short_sym).startswith("^"):
            stooq_overrides["vix_short"] = str(vix_short_sym)
        else:
            eodhd_overrides["vix_short"] = str(vix_short_sym) if "." in str(vix_short_sym) else f"{vix_short_sym}.INDX"
    if vxn_sym:
        eodhd_overrides["vxn"] = str(vxn_sym) if "." in str(vxn_sym) else f"{vxn_sym}.INDX"
    if vix3m_sym:
        eodhd_overrides["vix3m"] = str(vix3m_sym) if "." in str(vix3m_sym) else f"{vix3m_sym}.INDX"
    if move_sym:
        eodhd_overrides["move"] = str(move_sym) if "." in str(move_sym) else f"{move_sym}.INDX"
    if rvx_sym:
        eodhd_overrides["rvx"] = str(rvx_sym) if "." in str(rvx_sym) else f"{rvx_sym}.INDX"
    if y10_sym:
        if str(y10_sym).startswith("^"):
            stooq_overrides["us10y"] = str(y10_sym)
        else:
            eodhd_overrides["us10y"] = str(y10_sym) if "." in str(y10_sym) else f"{y10_sym}.INDX"

    primary_provider = _build_primary_macro_provider(
        choice,
        stooq_overrides=stooq_overrides or None,
        eodhd_overrides=eodhd_overrides or None,
    )
    yield_provider = _build_yield_macro_provider(
        yields_cfg=cast(Mapping[str, Any], cfg.get("yields") or {}),
        fred_cfg=fred_cfg,
        stooq_overrides=stooq_overrides or None,
        eodhd_overrides=eodhd_overrides or None,
        default_provider=primary_provider,
    )
    if primary_provider is None and yield_provider is None:
        return None
    if yield_provider is None or yield_provider is primary_provider:
        return primary_provider
    return RoutedMacroProvider(
        vix_provider=primary_provider,
        vix_short_provider=primary_provider,
        yield_provider=yield_provider,
    )


def build_default_macro_provider(
    yaml_cfg: Mapping[str, Any] | None,
    *,
    execution_context: str = "live",
    macro_pit_mode: str | None = None,
    engine=None,
) -> Any | None:
    """Factory : choisit Stooq, EODHD ou un composite selon ``market_regimes``.

    Configuration acceptée (toutes les clés sont optionnelles) :

    ``market_regimes:``
      ``macro_provider: stooq | eodhd | composite | none``  (def. ``composite``)
      ``vix.symbol``, ``vix.short_symbol``, ``yields.symbol_10y``  → overrides

    Retourne ``None`` si l'opérateur a explicitement désactivé la couche
    (``market_regimes.enabled = false`` ET ``macro_provider = none``).
    """
    provider = _build_network_macro_provider(yaml_cfg)
    if provider is None:
        return None
    return TableFirstMacroProvider(
        provider,
        engine=engine,
        strict_before=_is_strict_before_mode(
            yaml_cfg=yaml_cfg,
            execution_context=execution_context,
            macro_pit_mode=macro_pit_mode,
        ),
    )


def _snapshot_to_payload(snapshot: object) -> dict[str, Any]:
    if hasattr(snapshot, "to_dict"):
        return cast(dict[str, Any], dict(cast(Any, snapshot).to_dict()))
    if hasattr(snapshot, "to_summary_dict"):
        return cast(dict[str, Any], dict(cast(Any, snapshot).to_summary_dict()))
    return {}


def _snapshot_to_next_state(snapshot: object, payload: Mapping[str, Any] | None = None) -> MarketRegimeState | None:
    next_state = getattr(snapshot, "next_state", None)
    if isinstance(next_state, MarketRegimeState):
        return next_state
    resolved_payload = payload if isinstance(payload, Mapping) else _snapshot_to_payload(snapshot)
    raw_next_state = resolved_payload.get("next_state") if isinstance(resolved_payload, Mapping) else None
    if isinstance(raw_next_state, Mapping):
        try:
            return MarketRegimeState.from_dict(raw_next_state)
        except Exception:
            return None
    return None


def populate_macro_indicators_table(
    *,
    start_date: date,
    end_date: date,
    yaml_cfg: Mapping[str, Any] | None = None,
    equity: float | None = None,
    engine=None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if end_date < start_date:
        raise ValueError("La date de fin doit être >= à la date de début.")
    provider = _build_network_macro_provider(yaml_cfg)
    if provider is None:
        raise ValueError("Aucun provider macro réseau n'est configuré.")
    root_cfg = yaml_cfg if isinstance(yaml_cfg, Mapping) else {}
    market_cfg = root_cfg.get("market_regimes") if isinstance(root_cfg, Mapping) else {}
    market_cfg = market_cfg if isinstance(market_cfg, Mapping) else {}
    yields_cfg = market_cfg.get("yields") if isinstance(market_cfg, Mapping) else {}
    yields_cfg = yields_cfg if isinstance(yields_cfg, Mapping) else {}
    market_regimes_cfg = parse_market_regimes(market_cfg)
    session_dates = nyse_session_dates(start_date, end_date)
    rows: list[dict[str, Any]] = []
    persisted_rows = 0
    missing_rows = 0
    previous_state: MarketRegimeState | None = None
    for index, session_date in enumerate(session_dates, start=1):
        snapshot = build_snapshot(
            session_date,
            config=market_regimes_cfg,
            equity=equity,
            execution_context="backtest",
            macro_provider=provider,
            sentiment_score_provider=DbSentimentScoreProvider(session_date),
            previous_state=previous_state,
            use_cache=False,
        )
        snap_payload = _snapshot_to_payload(snapshot)
        previous_state = _snapshot_to_next_state(snapshot, snap_payload)
        persisted = persist_market_macro_snapshot_daily(
            trade_date=session_date,
            macro_payload=snap_payload,
            engine=engine,
        )
        source_summary = {}
        get_source_summary = getattr(provider, "get_macro_source_summary", None)
        if callable(get_source_summary):
            try:
                raw_summary = get_source_summary() or {}
                source_summary = dict(raw_summary) if isinstance(raw_summary, Mapping) else {}
            except Exception:
                source_summary = {}
        macro_data = snap_payload.get("macro") if isinstance(snap_payload.get("macro"), Mapping) else {}
        sentiment_data = snap_payload.get("sentiment") if isinstance(snap_payload.get("sentiment"), Mapping) else {}
        if persisted:
            persisted_rows += 1
        else:
            missing_rows += 1
        row_payload = {
            "trade_date": session_date.isoformat(),
            "vix": macro_data.get("vix"),
            "vix9d": macro_data.get("vix_short"),
            "ten_y": macro_data.get("yield_10y"),
            "mode": snap_payload.get("mode"),
            "risk_multiplier": snap_payload.get("risk_multiplier"),
            "effective_max_positions": snap_payload.get("effective_max_positions"),
            "allow_new_entries": snap_payload.get("allow_new_entries"),
            "vix_curve_inverted": macro_data.get("vix_curve_inverted"),
            "yield_10y_5d_pct": macro_data.get("yield_10y_5d_pct"),
            "sentiment_score": sentiment_data.get("score"),
            "sentiment_level": sentiment_data.get("level"),
            "sentiment_source": sentiment_data.get("source"),
            "persisted": bool(persisted),
            **source_summary,
        }
        rows.append(row_payload)
        if callable(progress_callback):
            progress_callback(
                {
                    "current": index,
                    "total": len(session_dates),
                    **row_payload,
                }
            )
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sessions_total": len(session_dates),
        "persisted_rows": persisted_rows,
        "missing_rows": missing_rows,
        "rows": rows,
    }


def recompute_macro_regime_table(
    *,
    start_date: date,
    end_date: date,
    yaml_cfg: Mapping[str, Any] | None = None,
    equity: float | None = None,
    engine=None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if end_date < start_date:
        raise ValueError("La date de fin doit être >= à la date de début.")
    root_cfg = yaml_cfg if isinstance(yaml_cfg, Mapping) else {}
    market_cfg = root_cfg.get("market_regimes") if isinstance(root_cfg, Mapping) else {}
    market_cfg = market_cfg if isinstance(market_cfg, Mapping) else {}
    market_regimes_cfg = parse_market_regimes(market_cfg)
    provider = TableFirstMacroProvider(
        None,
        engine=engine,
        strict_before=False,
        persist_fallback_hits=False,
    )
    session_dates = nyse_session_dates(start_date, end_date)
    rows: list[dict[str, Any]] = []
    persisted_rows = 0
    missing_rows = 0
    total_sessions = len(session_dates)
    previous_state: MarketRegimeState | None = None
    for index, session_date in enumerate(session_dates, start=1):
        existing_row = load_macro_indicator_daily_asof(
            trade_date=session_date,
            engine=engine,
            strict_before=False,
        )
        exact_row = existing_row if existing_row and existing_row.get("trade_date") == session_date else None
        if exact_row is None:
            missing_rows += 1
            row_payload = {
                "trade_date": session_date.isoformat(),
                "persisted": False,
                "error": "Aucune ligne macro brute disponible pour cette séance.",
            }
            rows.append(row_payload)
            if callable(progress_callback):
                progress_callback({"current": index, "total": total_sessions, **row_payload})
            continue

        try:
            snapshot = build_snapshot(
                session_date,
                config=market_regimes_cfg,
                equity=equity,
                execution_context="backtest",
                macro_provider=provider,
                sentiment_score_provider=DbSentimentScoreProvider(session_date, engine=engine),
                previous_state=previous_state,
                use_cache=False,
            )
            snap_payload = _snapshot_to_payload(snapshot)
            previous_state = _snapshot_to_next_state(snapshot, snap_payload)
            macro_data = snap_payload.get("macro") if isinstance(snap_payload.get("macro"), Mapping) else {}
            sentiment_data = snap_payload.get("sentiment") if isinstance(snap_payload.get("sentiment"), Mapping) else {}
            persisted = persist_macro_indicator_daily(
                trade_date=session_date,
                vix=exact_row.get("vix"),
                vix9d=exact_row.get("vix9d"),
                ten_y=exact_row.get("ten_y"),
                mode=snap_payload.get("mode"),
                risk_multiplier=snap_payload.get("risk_multiplier"),
                effective_max_positions=snap_payload.get("effective_max_positions"),
                allow_new_entries=snap_payload.get("allow_new_entries"),
                vix_curve_inverted=macro_data.get("vix_curve_inverted"),
                yield_10y_5d_pct=macro_data.get("yield_10y_5d_pct"),
                sentiment_score=sentiment_data.get("score"),
                sentiment_level=sentiment_data.get("level"),
                sentiment_source=sentiment_data.get("source"),
                engine=engine,
            )
            if persisted:
                persisted_rows += 1
            else:
                missing_rows += 1
            row_payload = {
                "trade_date": session_date.isoformat(),
                "vix": exact_row.get("vix"),
                "vix9d": exact_row.get("vix9d"),
                "ten_y": exact_row.get("ten_y"),
                "mode": snap_payload.get("mode"),
                "risk_multiplier": snap_payload.get("risk_multiplier"),
                "effective_max_positions": snap_payload.get("effective_max_positions"),
                "allow_new_entries": snap_payload.get("allow_new_entries"),
                "vix_curve_inverted": macro_data.get("vix_curve_inverted"),
                "yield_10y_5d_pct": macro_data.get("yield_10y_5d_pct"),
                "sentiment_score": sentiment_data.get("score"),
                "sentiment_level": sentiment_data.get("level"),
                "sentiment_source": sentiment_data.get("source"),
                "persisted": bool(persisted),
                "source_effective": "db_cache",
            }
        except Exception as exc:
            missing_rows += 1
            row_payload = {
                "trade_date": session_date.isoformat(),
                "vix": exact_row.get("vix"),
                "vix9d": exact_row.get("vix9d"),
                "ten_y": exact_row.get("ten_y"),
                "persisted": False,
                "error": str(exc),
            }
        rows.append(row_payload)
        if callable(progress_callback):
            progress_callback({"current": index, "total": total_sessions, **row_payload})
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sessions_total": total_sessions,
        "persisted_rows": persisted_rows,
        "missing_rows": missing_rows,
        "rows": rows,
    }


__all__ = [
    "MACRO_PIT_MODE_ASOF_INCLUSIVE",
    "MACRO_PIT_MODE_J_MINUS_1_STRICT",
    "StooqMacroProvider",
    "EodhdMacroProvider",
    "FredMacroProvider",
    "TableFirstMacroProvider",
    "CompositeMacroProvider",
    "RoutedMacroProvider",
    "normalize_macro_pit_mode",
    "resolve_macro_pit_mode",
    "build_default_macro_provider",
    "populate_macro_indicators_table",
    "recompute_macro_regime_table",
]

