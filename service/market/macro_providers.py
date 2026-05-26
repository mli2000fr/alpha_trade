"""Implémentations production de :class:`service.market.macro_signals.MacroDataProvider`.

Sources branchées :

- **Stooq** (gratuit, sans clé) — symboles ``^vix`` / ``^vix9d`` / ``^tnx``.
  Utilise :func:`service.stooq.clientStooq.fetch_daily_bars`.
- **EODHD** — symboles ``VIX.INDX`` / ``VXN.INDX`` / ``US10Y.INDX``.
  Utilise :func:`service.eodhd.clientEodhd.fetch_eod`.

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
from typing import Any, Mapping, Sequence, cast

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
    "us10y": "US10Y.INDX",
}

# Combien de jours en arrière chercher pour trouver la dernière clôture
# disponible (week-ends + jours fériés US).
_CLOSE_LOOKBACK_DAYS = 7


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


def _signal_key_for_method(method: str) -> str | None:
    if method == "get_vix_close":
        return "vix"
    if method == "get_vix_short_term_close":
        return "vix_short"
    if method == "get_us10y_history":
        return "yield_10y"
    return None


def _log_successful_fetch(*, provider_name: str, key: str, symbol: str, trade_date: date, bars: Sequence[Mapping[str, Any]]) -> None:
    """Journalise une preuve positive compacte quand un fetch réseau aboutit.

    - ``INFO`` pour ``vix_short`` (preuve opérationnelle la plus utile).
    - ``DEBUG`` pour les autres séries macro afin d'éviter un bruit excessif.
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
    level = logging.INFO if key == "vix_short" else logging.DEBUG
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
        self._cache[cache_key] = list(bars)
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

    def get_macro_source_summary(self) -> dict[str, Any]:
        source_by_signal = dict(self._last_source_by_signal)
        source_effective = _effective_source_from_mapping(source_by_signal)
        if not source_by_signal or source_effective is None:
            return {}
        return {
            "source_effective": source_effective,
            "source_by_signal": source_by_signal,
        }


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

    def get_macro_source_summary(self) -> dict[str, Any]:
        source_by_signal = dict(self._last_source_by_signal)
        source_effective = _effective_source_from_mapping(source_by_signal)
        if not source_by_signal or source_effective is None:
            return {}
        return {
            "source_effective": source_effective,
            "source_by_signal": source_by_signal,
        }


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

    def get_macro_source_summary(self) -> dict[str, Any]:
        source_by_signal = dict(self._last_source_by_signal)
        source_effective = _effective_source_from_mapping(source_by_signal)
        if not source_by_signal or source_effective is None:
            return {}
        return {
            "source_effective": source_effective,
            "source_by_signal": source_by_signal,
        }


def build_default_macro_provider(yaml_cfg: Mapping[str, Any] | None) -> Any | None:
    """Factory : choisit Stooq, EODHD ou un composite selon ``market_regimes``.

    Configuration acceptée (toutes les clés sont optionnelles) :

    ``market_regimes:``
      ``macro_provider: stooq | eodhd | composite | none``  (def. ``composite``)
      ``vix.symbol``, ``vix.short_symbol``, ``yields.symbol_10y``  → overrides

    Retourne ``None`` si l'opérateur a explicitement désactivé la couche
    (``market_regimes.enabled = false`` ET ``macro_provider = none``).
    """
    cfg = (yaml_cfg or {}).get("market_regimes") if isinstance(yaml_cfg, Mapping) else None
    cfg = cfg or {}
    choice = str(cfg.get("macro_provider", "composite") or "composite").strip().lower()
    if choice == "none":
        return None

    # Overrides symbol par symbole (utiles si l'opérateur a un mapping custom).
    vix_sym = (cfg.get("vix") or {}).get("symbol")
    vix_short_sym = (cfg.get("vix") or {}).get("short_symbol")
    y10_sym = (cfg.get("yields") or {}).get("symbol_10y")

    stooq_overrides: dict[str, str] = {}
    eodhd_overrides: dict[str, str] = {}
    if vix_sym:
        # Si l'opérateur précise un symbole "VIX" générique, on l'envoie sur EODHD
        # (Stooq utilise toujours ^vix). On ne casse pas les valeurs par défaut.
        if str(vix_sym).startswith("^"):
            stooq_overrides["vix"] = str(vix_sym)
        else:
            eodhd_overrides["vix"] = str(vix_sym) if "." in str(vix_sym) else f"{vix_sym}.INDX"
    if vix_short_sym:
        if str(vix_short_sym).startswith("^"):
            stooq_overrides["vix_short"] = str(vix_short_sym)
        else:
            eodhd_overrides["vix_short"] = str(vix_short_sym) if "." in str(vix_short_sym) else f"{vix_short_sym}.INDX"
    if y10_sym:
        if str(y10_sym).startswith("^"):
            stooq_overrides["us10y"] = str(y10_sym)
        else:
            eodhd_overrides["us10y"] = str(y10_sym) if "." in str(y10_sym) else f"{y10_sym}.INDX"

    if choice == "stooq":
        return StooqMacroProvider(symbols=stooq_overrides or None)
    if choice == "eodhd":
        return EodhdMacroProvider(symbols=eodhd_overrides or None)
    # Default = composite : Stooq d'abord (gratuit, pas de quota), EODHD en
    # secours si la clé est présente dans l'environnement.
    providers: list[Any] = [StooqMacroProvider(symbols=stooq_overrides or None)]
    import os as _os
    if _os.getenv("EODHD_API_TOKEN") or _os.getenv("EODHD_TOKEN"):
        providers.append(EodhdMacroProvider(symbols=eodhd_overrides or None))
    return CompositeMacroProvider(providers)


__all__ = [
    "StooqMacroProvider",
    "EodhdMacroProvider",
    "CompositeMacroProvider",
    "build_default_macro_provider",
]

