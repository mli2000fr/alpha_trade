"""ihm/services/swing_score.py — Swing Score : classement des symboles favorables au swing trade.

Formule utilisateur :

    Swing Score = 25% ATR% + 20% Dollar Volume + 20% Relative Volume
                + 15% Momentum   + 10% Beta        + 10% Market-cap fit

Conventions de scoring (chaque facteur → sous-score 0-100) :

- ``ATR%``, ``Dollar Volume``, ``Relative Volume``, ``Momentum`` :
  rang percentile croissant dans l'univers analysé (plus haut = mieux).
- ``Beta`` : cloche autour de 1.2 avec tolérance ±0.8
  → ``100 × clip(1 − |β − 1.2| / 0.8, 0, 1)``.
- ``Market-cap fit`` : cloche log10 autour de 5 Md$ avec tolérance ±1.5 décade
  → ``100 × clip(1 − |log10(cap / 5e9)| / 1.5, 0, 1)``.
- Facteur indisponible (pas assez d'historique, cap absente…) : score neutre 50.

Données :
- OHLCV : ``stock_bars_daily`` (source eodhd_eod), fenêtre de ~180 jours calendaires.
- Capitalisation : ``stock_metadata.market_cap``.
- Benchmark beta : ``SPY``.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import date

import pandas as pd

from common.universe_files import list_universe_file_sources, universe_file_source_labels
from ihm.services.db import safe_query

LOGGER = logging.getLogger(__name__)

BENCHMARK_SYMBOL = "SPY"
LOOKBACK_CALENDAR_DAYS = 180  # ≈ 120-130 barres boursières

# Poids de la formule utilisateur (somme = 1.0).
WEIGHTS: dict[str, float] = {
    "atr_pct": 0.25,
    "dollar_volume": 0.20,
    "relative_volume": 0.20,
    "momentum": 0.15,
    "beta": 0.10,
    "market_cap_fit": 0.10,
}

_ATR_WINDOW = 14
_VOLUME_WINDOW = 20
_MOMENTUM_WINDOW = 20
_BETA_WINDOW = 60
_BETA_MIN_BARS = 30
_BETA_IDEAL = 1.2
_BETA_TOLERANCE = 0.8
_CAP_IDEAL = 5e9
_CAP_TOLERANCE_LOG10 = 1.5
_IN_CHUNK_SIZE = 500

RESULT_COLUMNS = [
    "rank",
    "symbol",
    "swing_score",
    "atr_pct",
    "dollar_volume",
    "relative_volume",
    "momentum",
    "beta",
    "market_cap",
    "score_atr_pct",
    "score_dollar_volume",
    "score_relative_volume",
    "score_momentum",
    "score_beta",
    "score_market_cap_fit",
    "last_bar_date",
]


def parse_symbols(text_content: str) -> list[str]:
    """Parse un contenu texte de symboles séparés par virgules (aussi espaces, `;`, sauts de ligne)."""
    tokens = re.split(r"[\s,;]+", str(text_content or ""))
    seen: list[str] = []
    for token in tokens:
        symbol = token.strip().upper()
        if symbol and symbol not in seen:
            seen.append(symbol)
    return seen


# ---------------------------------------------------------------------------
# Chargement DB
# ---------------------------------------------------------------------------


def _load_bars_chunk(symbols: list[str]) -> pd.DataFrame:
    """Charge les barres OHLCV d'un lot de symboles via ``safe_query`` (ou engine injecté)."""
    placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
    params = {f"s{i}": sym for i, sym in enumerate(symbols)}
    query = f"""
        SELECT symbol, date, open, high, low, close, volume
        FROM stock_bars_daily
        WHERE symbol IN ({placeholders})
          AND date >= DATE_SUB(CURDATE(), INTERVAL {LOOKBACK_CALENDAR_DAYS} DAY)
        ORDER BY symbol, date
    """
    frame = safe_query(query, params)
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.drop_duplicates(subset=["symbol", "date"], keep="last")
    return frame


def load_bars(symbols: list[str], benchmark: str = BENCHMARK_SYMBOL) -> pd.DataFrame:
    """Charge les barres OHLCV pour ``symbols`` + benchmark (par lots pour les grosses listes)."""
    all_symbols = list(dict.fromkeys([*symbols, benchmark]))
    chunks = [all_symbols[i : i + _IN_CHUNK_SIZE] for i in range(0, len(all_symbols), _IN_CHUNK_SIZE)]
    frames = [_load_bars_chunk(chunk) for chunk in chunks]
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    bars = pd.concat(frames, ignore_index=True)
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return bars.dropna(subset=["date", "close"]).sort_values(["symbol", "date"])


def load_market_caps(symbols: list[str]) -> pd.DataFrame:
    """Charge les capitalisations depuis ``stock_metadata``."""
    chunks = [symbols[i : i + _IN_CHUNK_SIZE] for i in range(0, len(symbols), _IN_CHUNK_SIZE)]
    frames: list[pd.DataFrame] = []
    for chunk in chunks:
        placeholders = ", ".join(f":s{i}" for i in range(len(chunk)))
        params = {f"s{i}": sym for i, sym in enumerate(chunk)}
        query = f"""
            SELECT symbol, market_cap
            FROM stock_metadata
            WHERE symbol IN ({placeholders})
        """
        frame = safe_query(query, params)
        if frame is not None and not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["symbol", "market_cap"])
    caps = pd.concat(frames, ignore_index=True)
    caps["market_cap"] = pd.to_numeric(caps["market_cap"], errors="coerce")
    return caps.drop_duplicates(subset=["symbol"], keep="last")


# ---------------------------------------------------------------------------
# Calcul des facteurs (pur pandas — testable sans DB)
# ---------------------------------------------------------------------------


def _true_range(frame: pd.DataFrame) -> pd.Series:
    prev_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _beta_score(beta: float | None) -> float:
    if beta is None or not math.isfinite(beta):
        return math.nan
    return 100.0 * max(0.0, 1.0 - abs(beta - _BETA_IDEAL) / _BETA_TOLERANCE)


def _market_cap_fit_score(market_cap: float | None) -> float:
    if market_cap is None or not math.isfinite(market_cap) or market_cap <= 0:
        return math.nan
    return 100.0 * max(0.0, 1.0 - abs(math.log10(market_cap / _CAP_IDEAL)) / _CAP_TOLERANCE_LOG10)


def _percentile_score(series: pd.Series) -> pd.Series:
    """Rang percentile 0-100 (plus haut = mieux). NaN conservés (→ score neutre 50)."""
    return series.rank(method="average", pct=True).mul(100.0)


def _symbol_metrics_from_group(
    symbol: str,
    frame: pd.DataFrame,
    sym_rets: pd.Series,
    bench_rets: pd.Series,
) -> dict[str, float | object] | None:
    """Calcule les facteurs d'un symbole depuis son groupe de barres (déjà trié par date)."""
    if len(frame) < _MOMENTUM_WINDOW + 2:
        return None
    close = frame["close"].astype(float)
    volume = frame["volume"].fillna(0.0).astype(float)
    last_close = float(close.iloc[-1])

    atr = float(_true_range(frame).rolling(_ATR_WINDOW).mean().iloc[-1])
    atr_pct = (atr / last_close * 100.0) if last_close else None

    dollar_volume = float((close * volume).tail(_VOLUME_WINDOW).mean())
    prev_volume = float(volume.iloc[-(_VOLUME_WINDOW + 1) : -1].mean())
    relative_volume = float(volume.iloc[-1] / prev_volume) if prev_volume > 0 else None

    ref_close = float(close.iloc[-(_MOMENTUM_WINDOW + 1)])
    momentum = (last_close / ref_close - 1.0) if ref_close else None

    # Beta : aligné sur les DATES communes avec le benchmark (pas sur l'index).
    joined = (
        pd.concat([sym_rets.rename("s"), bench_rets.rename("b")], axis=1, join="inner")
        .dropna()
        .tail(_BETA_WINDOW)
    )
    if len(joined) >= _BETA_MIN_BARS and float(joined["b"].var()) > 0:
        beta = float(joined["b"].cov(joined["s"]) / joined["b"].var())
    else:
        beta = None

    return {
        "symbol": symbol,
        "atr_pct": atr_pct,
        "dollar_volume": dollar_volume,
        "relative_volume": relative_volume,
        "momentum": momentum,
        "beta": beta,
        "last_bar_date": frame["date"].iloc[-1].date(),
    }


def build_swing_scores(
    bars: pd.DataFrame,
    market_caps: pd.DataFrame,
    symbols: list[str],
    benchmark: str = BENCHMARK_SYMBOL,
) -> tuple[pd.DataFrame, list[str]]:
    """Calcule le Swing Score pour ``symbols``.

    Returns:
        Tuple ``(resultats triés décroissant avec colonne ``rank``, symboles sans données suffisantes)``.
    """
    requested = [s.upper() for s in symbols]
    if bars is None or bars.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS), requested

    # Groupes par symbole (O(n) via groupby, pas de scan par symbole).
    keep_symbols = set(requested) | {benchmark}
    bars_filtered = bars[bars["symbol"].isin(keep_symbols)]
    groups: dict[str, pd.DataFrame] = {
        symbol: group.sort_values("date").reset_index(drop=True)
        for symbol, group in bars_filtered.groupby("symbol", sort=False)
    }

    # Rendements journaliers par symbole (indexé par date pour l'alignement beta).
    rets = bars_filtered[["symbol", "date", "close"]].copy()
    rets["ret"] = rets.groupby("symbol", sort=False)["close"].pct_change()
    rets_by_symbol: dict[str, pd.Series] = {
        symbol: group.dropna(subset=["ret"]).set_index("date")["ret"]
        for symbol, group in rets.groupby("symbol", sort=False)
    }
    bench_rets = rets_by_symbol.get(benchmark, pd.Series(dtype=float))

    rows: list[dict[str, float | object]] = []
    missing: list[str] = []
    for symbol in requested:
        frame = groups.get(symbol)
        if frame is None:
            missing.append(symbol)
            continue
        metrics = _symbol_metrics_from_group(
            symbol,
            frame,
            rets_by_symbol.get(symbol, pd.Series(dtype=float)),
            bench_rets,
        )
        if metrics is None:
            missing.append(symbol)
            continue
        rows.append(metrics)

    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS), missing

    frame = pd.DataFrame(rows)
    cap_map = (
        market_caps.set_index("symbol")["market_cap"].to_dict()
        if market_caps is not None and not market_caps.empty
        else {}
    )
    frame["market_cap"] = frame["symbol"].map(lambda s: cap_map.get(s))

    # Sous-scores 0-100.
    score_atr = _percentile_score(frame["atr_pct"])
    score_dollar_volume = _percentile_score(frame["dollar_volume"])
    score_relative_volume = _percentile_score(frame["relative_volume"])
    score_momentum = _percentile_score(frame["momentum"])
    score_beta = frame["beta"].map(_beta_score)
    score_market_cap_fit = frame["market_cap"].map(_market_cap_fit_score)

    # Facteur indisponible → score neutre 50 (ni pénalisé, ni favorisé).
    score_atr = score_atr.fillna(50.0)
    score_dollar_volume = score_dollar_volume.fillna(50.0)
    score_relative_volume = score_relative_volume.fillna(50.0)
    score_momentum = score_momentum.fillna(50.0)
    score_beta = score_beta.fillna(50.0)
    score_market_cap_fit = score_market_cap_fit.fillna(50.0)

    frame["swing_score"] = (
        WEIGHTS["atr_pct"] * score_atr
        + WEIGHTS["dollar_volume"] * score_dollar_volume
        + WEIGHTS["relative_volume"] * score_relative_volume
        + WEIGHTS["momentum"] * score_momentum
        + WEIGHTS["beta"] * score_beta
        + WEIGHTS["market_cap_fit"] * score_market_cap_fit
    ).round(2)

    frame["score_atr_pct"] = score_atr.round(2)
    frame["score_dollar_volume"] = score_dollar_volume.round(2)
    frame["score_relative_volume"] = score_relative_volume.round(2)
    frame["score_momentum"] = score_momentum.round(2)
    frame["score_beta"] = score_beta.round(2)
    frame["score_market_cap_fit"] = score_market_cap_fit.round(2)

    frame = frame.sort_values("swing_score", ascending=False).reset_index(drop=True)
    frame.insert(0, "rank", frame.index + 1)
    return frame[RESULT_COLUMNS], missing


# ---------------------------------------------------------------------------
# Point d'entrée « glue » utilisé par l'IHM
# ---------------------------------------------------------------------------


def compute_swing_scores(symbols: list[str]) -> tuple[pd.DataFrame, dict[str, object]]:
    """Charge les données puis calcule le Swing Score.

    Returns:
        Tuple ``(résultats, diagnostics)`` où diagnostics contient
        ``{"requested": int, "scored": int, "missing": list[str]}``.
    """
    requested = [s.upper() for s in symbols]
    bars = load_bars(requested)
    caps = load_market_caps(requested)
    results, missing = build_swing_scores(bars, caps, requested)
    diagnostics = {
        "requested": len(requested),
        "scored": len(results),
        "missing": missing,
    }
    return results, diagnostics


# ---------------------------------------------------------------------------
# Univers de symboles (liste déroulante identique au bloc « T1. ML Train »
# de la page Pipeline — voir ihm/pages/pipeline.py ML_TRAIN_SYMBOL_SOURCE_*)
# ---------------------------------------------------------------------------

UNIVERSE_SYMBOL_SOURCE_OPTIONS = (
    "stock-bars-daily",
    "tradable-universe",
    "tradable-universe-history",
    *list_universe_file_sources(),
)

UNIVERSE_SYMBOL_SOURCE_LABELS = {
    "stock-bars-daily": "Symboles avec barres daily (stock_bars_daily)",
    "tradable-universe": "Univers tradable PIT canonique (dernier snapshot)",
    "tradable-universe-history": "Univers tradable PIT — union historique",
    **universe_file_source_labels(),
}

# Au-delà de ce seuil, l'IHM affiche un avertissement (calcul plus long).
LARGE_UNIVERSE_WARNING_THRESHOLD = 2000

_UNIVERSE_HISTORY_UNION_SQL = """
    SELECT DISTINCT UPPER(TRIM(symbol)) AS symbol
    FROM tradable_universe_history
    WHERE is_tradable = 1
    ORDER BY symbol
"""


def _load_tradable_universe_history_union() -> list[str]:
    """Union de tous les symboles tradables sur toute l'historique PIT.

    Tous les runs présents en base appartiennent au preset
    ``capital_2001_5000`` (source de vérité par défaut).
    """
    frame = safe_query(_UNIVERSE_HISTORY_UNION_SQL)
    if frame is None or frame.empty:
        return []
    return [str(symbol).strip().upper() for symbol in frame["symbol"] if str(symbol).strip()]


def resolve_universe_symbols(symbol_source: str) -> list[str]:
    """Résout la liste des symboles d'un univers (mêmes sources que le ML Train pipeline).

    ``tradable-universe`` = dernier snapshot PIT canonique publié (asof aujourd'hui).
    ``tradable-universe-history`` = union de tous les symboles tradables sur toute l'histoire.
    """
    from modelFactory.db_registry import load_symbols_for_source

    from ihm.services.db import get_engine

    engine = get_engine()
    if engine is None:
        raise RuntimeError("Base de données indisponible.")
    normalized_source = str(symbol_source).strip().lower()
    if normalized_source == "tradable-universe-history":
        return _load_tradable_universe_history_union()
    trade_date = date.today()
    symbols = load_symbols_for_source(engine, normalized_source, trade_date=trade_date)
    return [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]

