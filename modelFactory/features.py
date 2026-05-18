"""modelFactory/features.py — Feature engineering à partir de stock_bars_daily."""
from __future__ import annotations

import hashlib
import json
from typing import Optional

import numpy as np
import pandas as pd

# -------------------------------------------------------------------------
# Liste ordonnée des features V1 (dérivées de OHLCV uniquement)
# -------------------------------------------------------------------------
FEATURE_COLUMNS: list[str] = [
    "daily_return",
    "log_return",
    "intraday_range",
    "overnight_gap",
    "close_to_vwap",
    "volume_ratio_20",
    "rolling_volatility_20",
    "rolling_volatility_60",
    "rolling_mean_return_5",
    "rolling_mean_return_20",
    "rsi_14",
    "atr_14_norm",
    "is_filled",
]

EXPERT_FEATURE_COLUMNS: list[str] = [
    "sma20_distance",
    "sma50_distance",
    "sma100_distance",
    "sma200_distance",
    "ema20_distance",
    "ema50_distance",
    "momentum_10",
    "momentum_20",
    "momentum_60",
    "vol_ratio_20_60",
    "range_position_20",
    "market_return_20",
    "market_volatility_20",
    "market_trend_strength_50",
    "relative_strength_20",
    "relative_strength_60",
    "regime_bull_market",
    "regime_risk_off",
]

# Features sentiment auxiliaires (depuis ticker_daily_sentiment_features)
SENTIMENT_FEATURE_COLUMNS: list[str] = [
    "sentiment_net_mean_1d",
    "sentiment_confidence_mean_1d",
    "news_count_log",
    "major_event_flag",
]


def get_feature_columns(
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
) -> list[str]:
    """Retourne la liste complète des colonnes features (OHLCV + optionnel sentiment)."""
    cols = list(FEATURE_COLUMNS)
    if feature_set == "expert":
        cols.extend(EXPERT_FEATURE_COLUMNS)
    if include_cross_sectional:
        from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS

        cols.extend(CROSS_SECTIONAL_FEATURE_COLUMNS)
    if include_sentiment:
        cols.extend(SENTIMENT_FEATURE_COLUMNS)
    return cols


def fingerprint(
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    feature_columns: list[str] | None = None,
) -> str:
    """SHA256[:16] du contrat de features actif (Phase 4.2.b).

    Persisté dans ``config.json`` du modèle ; recalculé à l'inférence
    pour détecter toute dérive silencieuse du contrat de features
    (la valeur **doit** rester stable tant que la liste de colonnes ne
    change pas — un test gold bloque les modifications accidentelles).
    """
    columns = list(feature_columns or get_feature_columns(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
    ))
    payload = {
        "columns": columns,
        "feature_set": feature_set,
        "include_sentiment": bool(include_sentiment),
        "include_cross_sectional": bool(include_cross_sectional),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def normalize_feature_columns(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        return None
    normalized = [str(column) for column in value]
    return normalized or None


def build_feature_contract(
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    feature_columns: list[str] | None = None,
    scaler_feature_names: list[str] | None = None,
) -> dict[str, object]:
    """Construit le manifeste persistant du contrat de features."""
    resolved_columns = list(feature_columns or get_feature_columns(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
    ))
    contract: dict[str, object] = {
        "schema_version": 1,
        "feature_columns": resolved_columns,
        "feature_count": len(resolved_columns),
        "feature_fingerprint": fingerprint(
            include_sentiment=include_sentiment,
            feature_set=feature_set,
            include_cross_sectional=include_cross_sectional,
            feature_columns=resolved_columns,
        ),
        "require_exact_order": True,
        "allow_extra_runtime_columns": True,
    }
    if scaler_feature_names is not None:
        contract["scaler_feature_names"] = list(scaler_feature_names)
    return contract


def validate_feature_contract(
    contract_payload: object,
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    persisted_feature_columns: object = None,
    persisted_feature_fingerprint: object = None,
    scaler_feature_names: object = None,
    route_feature_columns: object = None,
    route_feature_fingerprint: object = None,
    runtime_feature_columns: object = None,
    allow_legacy_missing_contract: bool = False,
) -> str | None:
    expected_columns = get_feature_columns(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
    )
    expected_fingerprint = fingerprint(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
        feature_columns=expected_columns,
    )

    contract = contract_payload if isinstance(contract_payload, dict) else None
    contract_columns = normalize_feature_columns(contract.get("feature_columns")) if contract is not None else None
    contract_fingerprint = str(contract.get("feature_fingerprint") or "").strip() if contract is not None else ""

    if contract is None:
        if not allow_legacy_missing_contract:
            return "feature_contract_missing"
        contract_columns = (
            normalize_feature_columns(persisted_feature_columns)
            or normalize_feature_columns(route_feature_columns)
            or normalize_feature_columns(scaler_feature_names)
            or list(expected_columns)
        )
        contract_fingerprint = fingerprint(
            include_sentiment=include_sentiment,
            feature_set=feature_set,
            include_cross_sectional=include_cross_sectional,
            feature_columns=contract_columns,
        )
    else:
        if contract_columns is None:
            return "feature_contract_columns_missing"
        if contract_columns != list(expected_columns):
            return (
                "feature_contract_columns_mismatch "
                f"persisted={contract_columns} expected={expected_columns}"
            )
        if not contract_fingerprint:
            return "feature_contract_fingerprint_missing"
        if contract_fingerprint != expected_fingerprint:
            return (
                "feature_contract_fingerprint_mismatch "
                f"persisted={contract_fingerprint} expected={expected_fingerprint}"
            )
        scaler_names_in_contract = normalize_feature_columns(contract.get("scaler_feature_names"))
        if scaler_names_in_contract is not None and scaler_names_in_contract != contract_columns:
            return (
                "feature_contract_scaler_names_mismatch "
                f"persisted={scaler_names_in_contract} expected={contract_columns}"
            )

    persisted_columns_normalized = normalize_feature_columns(persisted_feature_columns)
    if persisted_columns_normalized is not None and persisted_columns_normalized != contract_columns:
        return (
            "feature_columns_mismatch "
            f"persisted={persisted_columns_normalized} expected={contract_columns}"
        )

    persisted_fp_normalized = str(persisted_feature_fingerprint or "").strip()
    if persisted_fp_normalized and persisted_fp_normalized != contract_fingerprint:
        return (
            "feature_fingerprint_mismatch "
            f"persisted={persisted_fp_normalized} expected={contract_fingerprint}"
        )

    scaler_feature_names_normalized = normalize_feature_columns(scaler_feature_names)
    if scaler_feature_names_normalized is not None and scaler_feature_names_normalized != contract_columns:
        return (
            "scaler_feature_columns_mismatch "
            f"persisted={scaler_feature_names_normalized} expected={contract_columns}"
        )

    route_feature_columns_normalized = normalize_feature_columns(route_feature_columns)
    if route_feature_columns_normalized is not None and route_feature_columns_normalized != contract_columns:
        return (
            "route_feature_columns_mismatch "
            f"persisted={route_feature_columns_normalized} expected={contract_columns}"
        )

    route_fp_normalized = str(route_feature_fingerprint or "").strip()
    if route_fp_normalized and route_fp_normalized != contract_fingerprint:
        return (
            "route_feature_fingerprint_mismatch "
            f"persisted={route_fp_normalized} expected={contract_fingerprint}"
        )

    runtime_feature_columns_normalized = normalize_feature_columns(runtime_feature_columns)
    if runtime_feature_columns_normalized is not None:
        missing_columns = [column for column in contract_columns if column not in runtime_feature_columns_normalized]
        if missing_columns:
            return (
                "runtime_feature_columns_missing "
                f"missing={missing_columns} expected={contract_columns}"
            )

    return None


def compute_features(
    df: pd.DataFrame,
    sentiment_df: Optional[pd.DataFrame] = None,
    include_sentiment: bool = False,
    benchmark_df: Optional[pd.DataFrame] = None,
    feature_set: str = "v1",
) -> pd.DataFrame:
    """Ajoute les features dérivées à un DataFrame de bars trié par date.

    Le DataFrame d'entrée doit avoir : open, high, low, close, volume, adj_close, vwap, daily_return, is_filled.
    Si include_sentiment=True et sentiment_df fourni, merge les colonnes sentiment sur (symbol, date).
    Retourne une copie avec les colonnes features ajoutées.
    Les premières lignes avec NaN rolling sont supprimées.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    adj_prices = _build_adjusted_price_frame(df)
    close = adj_prices["close"]
    high = adj_prices["high"]
    low = adj_prices["low"]
    opn = adj_prices["open"]
    volume = df["volume"].astype(float)
    vwap = adj_prices["vwap"]

    # --- daily_return : recalculé depuis la série ajustée pour absorber splits/dividendes ---
    df["daily_return"] = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # --- log return ---
    df["log_return"] = np.log(close / close.shift(1))

    # --- intraday range ---
    df["intraday_range"] = (high - low) / close.clip(lower=1e-8)

    # --- overnight gap ---
    df["overnight_gap"] = (opn - close.shift(1)) / close.shift(1).clip(lower=1e-8)

    # --- close to vwap ---
    df["close_to_vwap"] = (close - vwap) / vwap.clip(lower=1e-8)
    df["close_to_vwap"] = df["close_to_vwap"].fillna(0.0)

    # --- volume ratio 20d ---
    vol_ma20 = volume.rolling(20).mean()
    df["volume_ratio_20"] = volume / vol_ma20.clip(lower=1.0)

    # --- rolling volatility ---
    df["rolling_volatility_20"] = df["daily_return"].rolling(20).std()
    df["rolling_volatility_60"] = df["daily_return"].rolling(60).std()

    # --- rolling mean return ---
    df["rolling_mean_return_5"] = df["daily_return"].rolling(5).mean()
    df["rolling_mean_return_20"] = df["daily_return"].rolling(20).mean()

    # --- RSI 14 ---
    df["rsi_14"] = _rsi(close, 14)

    # --- ATR 14 normalized ---
    df["atr_14_norm"] = _atr_norm(high, low, close, 14)

    # --- is_filled as float ---
    df["is_filled"] = df["is_filled"].astype(float)

    # --- Expert feature set: trend / relative strength / regime ---
    if feature_set == "expert":
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma100 = close.rolling(100).mean()
        sma200 = close.rolling(200).mean()
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        df["sma20_distance"] = (close - sma20) / sma20.clip(lower=1e-8)
        df["sma50_distance"] = (close - sma50) / sma50.clip(lower=1e-8)
        df["sma100_distance"] = (close - sma100) / sma100.clip(lower=1e-8)
        df["sma200_distance"] = (close - sma200) / sma200.clip(lower=1e-8)
        df["ema20_distance"] = (close - ema20) / ema20.clip(lower=1e-8)
        df["ema50_distance"] = (close - ema50) / ema50.clip(lower=1e-8)
        df["momentum_10"] = close / close.shift(10) - 1.0
        df["momentum_20"] = close / close.shift(20) - 1.0
        df["momentum_60"] = close / close.shift(60) - 1.0
        df["vol_ratio_20_60"] = df["rolling_volatility_20"] / df["rolling_volatility_60"].clip(lower=1e-8)
        df["range_position_20"] = _range_position(close, 20)

        if benchmark_df is not None and not benchmark_df.empty:
            bench_prices = _build_adjusted_price_frame(benchmark_df.copy().sort_values("date").reset_index(drop=True))
            bench = pd.DataFrame(
                {
                    "date": pd.to_datetime(benchmark_df["date"]),
                    "benchmark_close": bench_prices["close"],
                }
            )
            bench["benchmark_return_20"] = bench["benchmark_close"] / bench["benchmark_close"].shift(20) - 1.0
            bench["benchmark_return_60"] = bench["benchmark_close"] / bench["benchmark_close"].shift(60) - 1.0
            bench_daily_return = bench["benchmark_close"].pct_change(fill_method=None)
            bench["market_return_20"] = bench_daily_return.rolling(20).mean()
            bench["market_volatility_20"] = bench_daily_return.rolling(20).std()
            bench_sma50 = bench["benchmark_close"].rolling(50).mean()
            bench_sma200 = bench["benchmark_close"].rolling(200).mean()
            bench["market_trend_strength_50"] = (bench["benchmark_close"] - bench_sma50) / bench_sma50.clip(lower=1e-8)
            bench["regime_bull_market"] = (bench["benchmark_close"] > bench_sma200).astype(float)
            bench["regime_risk_off"] = (bench["market_volatility_20"] > bench_daily_return.rolling(60).std()).astype(float)
            df = df.merge(
                bench[
                    [
                        "date",
                        "benchmark_return_20",
                        "benchmark_return_60",
                        "market_return_20",
                        "market_volatility_20",
                        "market_trend_strength_50",
                        "regime_bull_market",
                        "regime_risk_off",
                    ]
                ],
                on="date",
                how="left",
            )
            df["relative_strength_20"] = df["momentum_20"] - df["benchmark_return_20"]
            df["relative_strength_60"] = df["momentum_60"] - df["benchmark_return_60"]
        else:
            for col in [
                "market_return_20",
                "market_volatility_20",
                "market_trend_strength_50",
                "relative_strength_20",
                "relative_strength_60",
                "regime_bull_market",
                "regime_risk_off",
            ]:
                df[col] = 0.0

    # --- Sentiment features (optional) ---
    if include_sentiment:
        if sentiment_df is not None and not sentiment_df.empty:
            sent = sentiment_df.copy()
            # Normaliser la colonne date pour le merge
            if "trade_date" in sent.columns:
                sent = sent.rename(columns={"trade_date": "date"})
            sent["date"] = pd.to_datetime(sent["date"])
            sent["news_count_log"] = np.log1p(sent.get("news_count_1d", pd.Series(dtype=float)).fillna(0))
            merge_cols = ["date", "sentiment_net_mean_1d", "sentiment_confidence_mean_1d", "news_count_log", "major_event_flag"]
            if "symbol" in sent.columns and "symbol" in df.columns:
                merge_cols.insert(0, "symbol")
            sent = sent[[c for c in merge_cols if c in sent.columns]]
            df = df.merge(sent, on=[c for c in ["symbol", "date"] if c in sent.columns and c in df.columns], how="left")
        # Remplir les jours sans news par des valeurs neutres
        for col in SENTIMENT_FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = df[col].fillna(0.0).astype(float)

    # Determine active feature columns
    active_features = get_feature_columns(include_sentiment, feature_set=feature_set)

    # Drop warm-up NaN rows (rolling windows need ~60 rows)
    df = df.dropna(subset=active_features).reset_index(drop=True)
    return df


def build_target(
    df: pd.DataFrame,
    horizon: int = 5,
    mode: str = "binary",
    positive_threshold: float = 0.0,
    negative_threshold: float = 0.0,
) -> pd.Series:
    """Construit la target pour l'horizon futur.

    Retourne une Series alignée sur l'index de df.
    Les dernières `horizon` lignes seront NaN.

    Modes
    -----
    - `binary`     : 1 si future_return > positive_threshold, sinon 0.
    - `swing_cash` : 1 si future_return >= positive_threshold,
                     0 si future_return <= negative_threshold,
                     NaN entre les deux (zone no-trade ignorée à l'entraînement).
    """
    close = _build_adjusted_price_frame(df)["close"]
    future_return = close.shift(-horizon) / close - 1.0
    if mode == "binary":
        return (future_return > positive_threshold).astype(float).where(future_return.notna())
    if mode == "swing_cash":
        target = pd.Series(np.nan, index=df.index, dtype=float)
        target = target.mask(future_return >= positive_threshold, 1.0)
        target = target.mask(future_return <= negative_threshold, 0.0)
        return target.where(future_return.notna())
    raise ValueError(f"Unsupported target mode: {mode}")


def compute_future_return(df: pd.DataFrame, horizon: int = 5) -> pd.Series:
    """Retourne le rendement futur aligné à la ligne courante."""
    close = _build_adjusted_price_frame(df)["close"]
    return close.shift(-horizon) / close - 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_adjusted_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruit un OHLCV prix ajusté à partir de `adj_close` quand disponible.

    Pour des barres journalières actions, appliquer le ratio `adj_close / close`
    à OHLC/VWAP permet d'éviter que les splits/dividendes polluent les returns,
    la target et les indicateurs de volatilité.
    """
    close = pd.to_numeric(df["close"], errors="coerce").astype(float)
    adj_close_raw = pd.to_numeric(df["adj_close"], errors="coerce").astype(float) if "adj_close" in df.columns else close.copy()

    ratio = (adj_close_raw / close.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    ratio = ratio.where(ratio > 0.0, np.nan).fillna(1.0)

    def _scaled_col(name: str) -> pd.Series:
        base = df[name] if name in df.columns else close
        return pd.to_numeric(base, errors="coerce").astype(float) * ratio

    adjusted = pd.DataFrame({
        "open": _scaled_col("open"),
        "high": _scaled_col("high"),
        "low": _scaled_col("low"),
        "close": close * ratio,
        "vwap": _scaled_col("vwap"),
    })
    return adjusted


def _range_position(close: pd.Series, window: int) -> pd.Series:
    rolling_low = close.rolling(window).min()
    rolling_high = close.rolling(window).max()
    return (close - rolling_low) / (rolling_high - rolling_low).clip(lower=1e-8)

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.clip(lower=1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr_norm(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr / close.clip(lower=1e-8)

