"""Modèle directionnel mutualisé conditionné par les événements Oracle OOF.

Ce module est volontairement séparé du serving de production. Il entraîne un
unique CatBoost sur toutes les lignes du TOP20 Oracle strictement OOF et mesure
sa capacité à ordonner D1 versus D10. Une promotion vers la prédiction/backtest
ne doit intervenir qu'après passage des gates Walk-Forward documentés.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.cross_sectional import _load_sector_mapping, _map_to_gics_sector
from modelFactory.data_loader import load_benchmark_bars, load_universe_bars
from modelFactory.oracle.dataset import GUARD_COL, build_dataset as build_oracle_dataset
from modelFactory.oracle.leakage import assert_no_forbidden_features, assert_no_future_features
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.calibration import PlattCalibrator

LOGGER = logging.getLogger(__name__)

TARGET_COL = "shared_direction_target"
SCORE_COL = "direction_score"
SYMBOL_COL = "symbol_context"
SECTOR_COL = "sector_context"
SIGNED_TARGET_COL = "signed_return_target"
LONG_TARGET_COL = "dual_long_target"
SHORT_TARGET_COL = "dual_short_target"
P_LONG_COL = "proba_long"
P_SHORT_COL = "proba_short"
DIRECTION_MARGIN_COL = "direction_margin"
RAW_LONG_PROBA_COL = "raw_proba_long"
CAL_LONG_PROBA_COL = "calibrated_proba_long"
ORACLE_GATE_SCORE_COL = "oracle_gate_score"
SPY_RETURN_COL = "spy_future_return"
EXCESS_SPY_COL = "future_return_excess_spy"
SECTOR_RESIDUAL_COL = "future_return_sector_residual"
DEFAULT_PROFILE = Path("config/features/shared_direction/shared.json")
DEFAULT_ARTIFACTS_ROOT = Path("artifacts/models/shared_directional")
FORBIDDEN_FEATURES = {
    "proba_extreme", "directional_oracle_proba_extreme", "global_rank_20",
    "future_return", "oracle_decile", "oracle_pct_rank", ORACLE_GATE_SCORE_COL, TARGET_COL,
}


@dataclass(frozen=True, slots=True)
class SharedDirectionalConfig:
    horizon: int = 20
    pool_pct: float = 0.20
    top_fraction: float = 0.10
    min_train_dates: int = 504
    val_dates: int = 126
    test_dates: int = 126
    step_dates: int = 126
    max_splits: int = 12
    iterations: int = 600
    depth: int = 6
    learning_rate: float = 0.03
    random_seed: int = 42
    amplitude_weight_min: float = 0.50
    amplitude_weight_max: float = 3.00
    context_mode: str = "symbol_sector"
    amplitude_weighting: bool = True
    objective: str = "classifier"
    target_mode: str = "decile_direction"
    residualization: str = "spy_sector"
    sector_min_members: int = 5
    target_winsor_lower: float = 0.01
    target_winsor_upper: float = 0.99
    target_up_threshold: float = 0.03
    target_down_threshold: float = -0.03
    calibration_max_iter: int = 100

    def __post_init__(self) -> None:
        if not 0.0 < self.pool_pct < 1.0:
            raise ValueError("pool_pct doit être dans ]0,1[.")
        if not 0.0 < self.top_fraction < 0.5:
            raise ValueError("top_fraction doit être dans ]0,0.5[.")
        if min(self.min_train_dates, self.val_dates, self.test_dates, self.step_dates) < 1:
            raise ValueError("Les tailles Walk-Forward doivent être positives.")
        if self.max_splits < 1 or self.iterations < 10 or self.depth < 1:
            raise ValueError("Configuration d'entraînement mutualisé invalide.")
        if self.context_mode not in {"symbol_sector", "sector", "none"}:
            raise ValueError("context_mode doit être symbol_sector, sector ou none.")
        if self.objective not in {"classifier", "pairwise_ranker", "regressor", "dual_classifier"}:
            raise ValueError("objective directionnel inconnu.")
        if self.target_mode not in {
            "decile_direction", "signed_return", "dual_threshold", "long_h3_confirmation",
        }:
            raise ValueError("target_mode directionnel inconnu.")
        if self.residualization not in {"raw", "spy", "spy_sector"}:
            raise ValueError("residualization doit être raw, spy ou spy_sector.")
        if self.sector_min_members < 2:
            raise ValueError("sector_min_members doit être supérieur ou égal à 2.")
        if not 0.0 <= self.target_winsor_lower < self.target_winsor_upper <= 1.0:
            raise ValueError("Bornes de winsorisation de cible invalides.")
        if self.target_mode == "signed_return" and self.objective != "regressor":
            raise ValueError("La cible signed_return exige objective=regressor.")
        if self.target_mode == "decile_direction" and self.objective == "regressor":
            raise ValueError("objective=regressor exige target_mode=signed_return.")
        if self.target_mode == "dual_threshold" and self.objective != "dual_classifier":
            raise ValueError("La cible dual_threshold exige objective=dual_classifier.")
        if self.objective == "dual_classifier" and self.target_mode != "dual_threshold":
            raise ValueError("objective=dual_classifier exige target_mode=dual_threshold.")
        if self.target_mode == "long_h3_confirmation" and self.objective != "classifier":
            raise ValueError("long_h3_confirmation exige objective=classifier.")
        if self.target_down_threshold >= 0 or self.target_up_threshold <= 0:
            raise ValueError("Les seuils E2 doivent encadrer zéro.")
        if self.calibration_max_iter < 1:
            raise ValueError("calibration_max_iter doit être positif.")


def load_profile(path: Path | str = DEFAULT_PROFILE) -> dict[str, Any]:
    profile_path = Path(path)
    raw = profile_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if int(payload.get("schema_version", 0)) != 1 or payload.get("direction") != "shared":
        raise ValueError(f"Profil directionnel mutualisé invalide: {profile_path}")
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not columns or len(columns) != len(set(columns)):
        raise ValueError("feature_columns mutualisées doivent être non vides et sans doublon.")
    forbidden = FORBIDDEN_FEATURES.intersection(columns)
    if forbidden:
        raise ValueError(f"Features interdites dans le profil mutualisé: {sorted(forbidden)}")
    return {
        **payload,
        "profile_path": str(profile_path.resolve()),
        "profile_file": profile_path.name,
        "sha256": sha256(raw).hexdigest(),
    }


def _load_gate(path: Path, pool_pct: float) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Cache Oracle OOF introuvable: {path}")
    gate = pd.read_parquet(path)
    required = {
        "date", "symbol", "directional_oracle_eligible",
        "directional_oracle_oof_available", "directional_oracle_extreme_pct",
    }
    missing = sorted(required.difference(gate.columns))
    if missing:
        raise ValueError(f"Cache Oracle OOF incomplet: {missing}")
    gate = gate.copy()
    gate["date"] = pd.to_datetime(gate["date"], errors="coerce").dt.normalize()
    gate["symbol"] = gate["symbol"].astype(str).str.upper()
    threshold = 1.0 - float(pool_pct)
    recomputed = gate["directional_oracle_extreme_pct"].astype(float) >= threshold
    declared = gate["directional_oracle_eligible"].fillna(False).astype(bool)
    available = gate["directional_oracle_oof_available"].fillna(False).astype(bool)
    if bool((declared & ~available).any()):
        raise ValueError("Cache Oracle OOF invalide: ligne éligible sans disponibilité OOF.")
    # Le percentile est la source canonique si l'utilisateur change pool_pct.
    gate["shared_oracle_eligible"] = available & recomputed
    gate[ORACLE_GATE_SCORE_COL] = pd.to_numeric(
        gate["directional_oracle_extreme_pct"], errors="coerce"
    )
    return gate[["date", "symbol", "shared_oracle_eligible", ORACLE_GATE_SCORE_COL]]


def build_shared_dataset(
    engine: Any,
    oracle_batch_id: str,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    gate_path: Path,
    profile: dict[str, Any],
    config: SharedDirectionalConfig,
) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]:
    """Assemble le panel TOP20 Oracle OOF et la cible D1/D10.

    D2-D9 restent dans les folds de test pour mesurer le classement réel mais
    sont exclus du fit. ``proba_extreme`` sert uniquement de gate et n'entre
    jamais dans les features.
    """
    requested = [str(c) for c in profile["feature_columns"]]
    frame, feature_columns = build_oracle_dataset(
        engine,
        oracle_batch_id,
        symbols,
        start_date=start_date,
        end_date=end_date,
        horizon=config.horizon,
        require_global_rank=False,
        need_targets=True,
        feature_whitelist=requested,
        generator_options=dict(profile.get("generator_options") or {}),
    )
    if frame.empty:
        raise ValueError("Dataset mutualisé vide avant application du gate Oracle.")
    assert_no_forbidden_features(feature_columns)
    assert_no_future_features(feature_columns)
    forbidden = FORBIDDEN_FEATURES.intersection(feature_columns)
    if forbidden:
        raise ValueError(f"Features de fuite détectées: {sorted(forbidden)}")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    gate = _load_gate(gate_path, config.pool_pct)
    frame = frame.merge(gate, on=["date", "symbol"], how="inner", validate="one_to_one")
    frame = frame[frame["shared_oracle_eligible"]].copy()
    if frame.empty:
        raise ValueError("Aucun événement dans le TOP Oracle OOF mutualisé.")

    decile = pd.to_numeric(frame["oracle_decile"], errors="coerce")
    frame[TARGET_COL] = np.where(decile.eq(10), 1.0, np.where(decile.eq(1), 0.0, np.nan))
    frame[SYMBOL_COL] = frame["symbol"].fillna("UNKNOWN").astype(str)
    try:
        raw_sector = _load_sector_mapping(engine) or {}
    except Exception:  # noqa: BLE001
        LOGGER.warning("Mapping secteur indisponible; fallback UNKNOWN.", exc_info=True)
        raw_sector = {}
    sector_map = {
        str(symbol).upper(): _map_to_gics_sector(str(sector))
        for symbol, sector in raw_sector.items() if sector is not None
    }
    frame[SECTOR_COL] = frame["symbol"].map(sector_map).fillna("UNKNOWN").astype(str)
    categorical_columns = {
        "symbol_sector": [SYMBOL_COL, SECTOR_COL],
        "sector": [SECTOR_COL],
        "none": [],
    }[config.context_mode]
    diagnostics = {
        "rows_oracle_pool": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "labeled_d1": int(decile.eq(1).sum()),
        "labeled_d10": int(decile.eq(10).sum()),
        "middle_rejected_for_fit": int((~decile.isin([1, 10])).sum()),
        "sector_coverage": float(frame[SECTOR_COL].ne("UNKNOWN").mean()),
        "first_date": str(frame["date"].min().date()),
        "last_date": str(frame["date"].max().date()),
    }
    return frame, feature_columns, categorical_columns, diagnostics


def build_forward_return_panel(
    bars: pd.DataFrame,
    benchmark: pd.DataFrame,
    sector_map: dict[str, str],
    horizons: Iterable[int],
    *,
    sector_min_members: int = 5,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Calcule les cibles futures brutes, excess-SPY et sector-neutral.

    Le rendement secteur est la médiane, à la même date et au même horizon,
    des rendements excess-SPY des membres du secteur. Si le secteur est absent
    ou trop petit, la cible retombe explicitement sur l''excess-SPY.
    """
    required = {"date", "symbol"}
    if not required.issubset(bars.columns) or "date" not in benchmark.columns:
        raise ValueError("Barres incomplètes pour calculer les cibles signées.")
    price_col = "adj_close" if "adj_close" in bars.columns else "close"
    benchmark_price_col = "adj_close" if "adj_close" in benchmark.columns else "close"
    if price_col not in bars.columns or benchmark_price_col not in benchmark.columns:
        raise ValueError("Prix ajusté/close absent pour calculer les cibles signées.")

    normalized_horizons = sorted({int(value) for value in horizons})
    if not normalized_horizons or min(normalized_horizons) < 1:
        raise ValueError("Les horizons de rendement doivent être positifs.")

    panel = bars[["date", "symbol", price_col]].copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["symbol"] = panel["symbol"].astype(str).str.upper()
    panel[price_col] = pd.to_numeric(panel[price_col], errors="coerce")
    panel = panel.dropna(subset=["date", "symbol", price_col]).sort_values(["symbol", "date"])
    panel[SECTOR_COL] = panel["symbol"].map(sector_map).fillna("UNKNOWN").astype(str)

    spy = benchmark[["date", benchmark_price_col]].copy()
    spy["date"] = pd.to_datetime(spy["date"], errors="coerce").dt.normalize()
    spy[benchmark_price_col] = pd.to_numeric(spy[benchmark_price_col], errors="coerce")
    spy = spy.dropna(subset=["date", benchmark_price_col]).sort_values("date")

    outputs: list[pd.DataFrame] = []
    diagnostics: dict[str, Any] = {"horizons": {}, "sector_min_members": int(sector_min_members)}
    for horizon in normalized_horizons:
        raw_col = f"future_return_h{horizon}"
        spy_col = f"spy_future_return_h{horizon}"
        panel[raw_col] = panel.groupby("symbol", sort=False)[price_col].shift(-horizon) / panel[price_col] - 1.0
        spy[spy_col] = spy[benchmark_price_col].shift(-horizon) / spy[benchmark_price_col] - 1.0
        target = panel[["date", "symbol", SECTOR_COL, raw_col]].merge(
            spy[["date", spy_col]], on="date", how="left", validate="many_to_one",
        )
        target[EXCESS_SPY_COL] = target[raw_col] - target[spy_col]

        known_sector = target[SECTOR_COL].ne("UNKNOWN") & target[EXCESS_SPY_COL].notna()
        sector_stats = (
            target.loc[known_sector]
            .groupby(["date", SECTOR_COL], as_index=False)[EXCESS_SPY_COL]
            .agg(sector_excess_return="median", sector_members="count")
        )
        target = target.merge(sector_stats, on=["date", SECTOR_COL], how="left", validate="many_to_one")
        usable_sector = target["sector_members"].fillna(0).ge(int(sector_min_members))
        target[SECTOR_RESIDUAL_COL] = target[EXCESS_SPY_COL] - target["sector_excess_return"].where(
            usable_sector, 0.0
        )
        target = target.rename(columns={raw_col: "future_return", spy_col: SPY_RETURN_COL})
        target["horizon"] = horizon
        valid = target["future_return"].notna()
        diagnostics["horizons"][str(horizon)] = {
            "rows": int(valid.sum()),
            "dates": int(target.loc[valid, "date"].nunique()),
            "sector_residual_coverage": float(usable_sector[valid].mean()) if bool(valid.any()) else 0.0,
            "spy_coverage": float(target.loc[valid, SPY_RETURN_COL].notna().mean()) if bool(valid.any()) else 0.0,
        }
        outputs.append(target[[
            "date", "symbol", "horizon", "future_return", SPY_RETURN_COL,
            EXCESS_SPY_COL, SECTOR_RESIDUAL_COL, "sector_members",
        ]])
    return pd.concat(outputs, ignore_index=True), diagnostics


def load_forward_return_panel(
    engine: Any,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    horizons: Iterable[int],
    sector_min_members: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Charge une fois les prix nécessaires à toute la campagne multi-horizons."""
    normalized_horizons = sorted({int(value) for value in horizons})
    future_end = (
        pd.Timestamp(end_date) + pd.Timedelta(days=max(normalized_horizons) * 3 + 10)
    ).date().isoformat()
    bars = load_universe_bars(engine, symbols, start_date=start_date, end_date=future_end)
    benchmark = load_benchmark_bars(engine, "SPY", start_date=start_date, end_date=future_end)
    if bars.empty or benchmark.empty:
        raise ValueError("Barres univers ou SPY absentes pour la campagne signed_return.")
    try:
        raw_sector = _load_sector_mapping(engine) or {}
    except Exception:  # noqa: BLE001
        LOGGER.warning("Mapping secteur indisponible; résidualisation SPY seulement.", exc_info=True)
        raw_sector = {}
    sector_map = {
        str(symbol).upper(): _map_to_gics_sector(str(sector))
        for symbol, sector in raw_sector.items() if sector is not None
    }
    return build_forward_return_panel(
        bars, benchmark, sector_map, normalized_horizons,
        sector_min_members=sector_min_members,
    )


def attach_signed_return_target(
    oracle_pool: pd.DataFrame,
    forward_panel: pd.DataFrame,
    *,
    horizon: int,
    residualization: str,
) -> pd.DataFrame:
    """Joint une cible Hx au pool Oracle sans exposer cette cible en feature."""
    target_column = {
        "raw": "future_return",
        "spy": EXCESS_SPY_COL,
        "spy_sector": SECTOR_RESIDUAL_COL,
    }.get(residualization)
    if target_column is None:
        raise ValueError("Résidualisation signed_return inconnue.")
    pool = oracle_pool.copy()
    if "future_return" in pool.columns:
        pool = pool.rename(columns={"future_return": "oracle_future_return_h20"})
    selected = forward_panel[forward_panel["horizon"].eq(int(horizon))].drop(columns=["horizon"])
    pool = pool.merge(selected, on=["date", "symbol"], how="left", validate="one_to_one")
    pool[SIGNED_TARGET_COL] = pd.to_numeric(pool[target_column], errors="coerce")
    pool[TARGET_COL] = pool[SIGNED_TARGET_COL]
    return pool


def attach_dual_threshold_targets(
    oracle_pool: pd.DataFrame,
    forward_panel: pd.DataFrame,
    *,
    horizon: int,
    up_threshold: float,
    down_threshold: float,
) -> pd.DataFrame:
    """Construit deux labels terminaux indépendants sur tous les événements Oracle."""
    if down_threshold >= 0 or up_threshold <= 0:
        raise ValueError("Les seuils dual_threshold doivent encadrer zéro.")
    pool = oracle_pool.copy()
    if "future_return" in pool.columns:
        pool = pool.rename(columns={"future_return": "oracle_future_return_h20"})
    selected = forward_panel[forward_panel["horizon"].eq(int(horizon))].drop(columns=["horizon"])
    pool = pool.merge(selected, on=["date", "symbol"], how="left", validate="one_to_one")
    raw = pd.to_numeric(pool["future_return"], errors="coerce")
    pool[LONG_TARGET_COL] = raw.ge(float(up_threshold)).astype(float).where(raw.notna())
    pool[SHORT_TARGET_COL] = raw.le(float(down_threshold)).astype(float).where(raw.notna())
    if bool(((pool[LONG_TARGET_COL] == 1) & (pool[SHORT_TARGET_COL] == 1)).any()):
        raise ValueError("Une ligne E2 ne peut pas être simultanément LONG et SHORT.")
    return pool


def amplitude_weights(future_return: pd.Series, config: SharedDirectionalConfig) -> np.ndarray:
    if not config.amplitude_weighting:
        return np.ones(len(future_return), dtype=float)
    amplitude = pd.to_numeric(future_return, errors="coerce").abs().to_numpy(float)
    finite = amplitude[np.isfinite(amplitude) & (amplitude > 0)]
    scale = float(np.median(finite)) if finite.size else 1.0
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    return np.clip(amplitude / scale, config.amplitude_weight_min, config.amplitude_weight_max)


def clip_signed_targets_from_train(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    config: SharedDirectionalConfig,
) -> tuple[pd.DataFrame, pd.DataFrame | None, tuple[float, float]]:
    """Winsorise train/validation avec des quantiles calculés sur train seul."""
    values = pd.to_numeric(train[TARGET_COL], errors="coerce").dropna()
    if values.empty:
        raise ValueError("Cible signed_return vide avant winsorisation.")
    lower = float(values.quantile(config.target_winsor_lower))
    upper = float(values.quantile(config.target_winsor_upper))
    if not np.isfinite(lower) or not np.isfinite(upper) or lower >= upper:
        raise ValueError("Quantiles de winsorisation signed_return invalides.")
    clipped_train = train.copy()
    clipped_train[TARGET_COL] = pd.to_numeric(
        clipped_train[TARGET_COL], errors="coerce"
    ).clip(lower, upper)
    clipped_valid = None
    if valid is not None:
        clipped_valid = valid.copy()
        clipped_valid[TARGET_COL] = pd.to_numeric(
            clipped_valid[TARGET_COL], errors="coerce"
        ).clip(lower, upper)
    return clipped_train, clipped_valid, (lower, upper)


def binary_probability_to_ternary(probability_long: Iterable[float]) -> pd.DataFrame:
    """Convertit P(D10|D1∨D10) en probabilités avec abstention native.

    La masse directionnelle vaut ``|2p-1|`` et le reste devient FLAT. Les
    trois probabilités sont bornées et somment exactement à un.
    """
    raw = np.clip(np.asarray(list(probability_long), dtype=float), 0.0, 1.0)
    confidence = np.abs(2.0 * raw - 1.0)
    p_long = np.where(raw >= 0.5, confidence, 0.0)
    p_short = np.where(raw < 0.5, confidence, 0.0)
    p_flat = 1.0 - confidence
    return pd.DataFrame({"proba_short": p_short, "proba_flat": p_flat, "proba_long": p_long})


def _prepare_X(frame: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame:
    X = frame[numeric + categorical].copy()
    for column in numeric:
        X[column] = pd.to_numeric(X[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    for column in categorical:
        X[column] = X[column].fillna("UNKNOWN").astype(str)
    return X


def _fit_catboost(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    numeric: list[str],
    categorical: list[str],
    config: SharedDirectionalConfig,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostClassifier, CatBoostRanker, CatBoostRegressor

    common = dict(
        iterations=int(iterations or config.iterations),
        depth=config.depth,
        learning_rate=config.learning_rate,
        l2_leaf_reg=5.0,
        random_seed=config.random_seed,
        random_strength=1.0,
        bootstrap_type="Bayesian",
        bagging_temperature=1.0,
        allow_writing_files=False,
        verbose=False,
        thread_count=-1,
    )
    if config.objective == "pairwise_ranker":
        model = CatBoostRanker(loss_function="PairLogit", eval_metric="NDCG:top=10", **common)
    elif config.objective == "regressor":
        model = CatBoostRegressor(loss_function="RMSE", eval_metric="RMSE", **common)
    else:
        model = CatBoostClassifier(loss_function="Logloss", eval_metric="AUC", **common)
    train = train.sort_values(["date", "symbol"]).copy()
    if valid is not None:
        valid = valid.sort_values(["date", "symbol"]).copy()
    X_train = _prepare_X(train, numeric, categorical)
    y_train = (
        train[TARGET_COL].astype(float)
        if config.objective == "regressor"
        else train[TARGET_COL].astype(int)
    )
    kwargs: dict[str, Any] = {"cat_features": categorical}
    if config.objective == "pairwise_ranker":
        kwargs["group_id"] = train["date"].dt.strftime("%Y-%m-%d").to_numpy()
    elif config.objective == "classifier":
        kwargs["sample_weight"] = amplitude_weights(train["future_return"], config)
    if valid is not None and not valid.empty:
        valid_target = (
            valid[TARGET_COL].astype(float)
            if config.objective == "regressor"
            else valid[TARGET_COL].astype(int)
        )
        eval_set: Any = (_prepare_X(valid, numeric, categorical), valid_target)
        if config.objective == "pairwise_ranker":
            from catboost import Pool
            eval_set = Pool(
                _prepare_X(valid, numeric, categorical),
                label=valid[TARGET_COL].astype(int),
                group_id=valid["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                cat_features=categorical,
            )
        kwargs.update({
            "eval_set": eval_set,
            "early_stopping_rounds": 60,
            "use_best_model": True,
        })
    model.fit(X_train, y_train, **kwargs)
    return model


def _tail(frame: pd.DataFrame, score: str, fraction: float, ascending: bool) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("date", sort=False):
        n = max(1, math.ceil(len(group) * fraction))
        parts.append(group.nsmallest(n, score) if ascending else group.nlargest(n, score))
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()


def _mean_daily_ic(frame: pd.DataFrame, return_col: str = "future_return") -> float | None:
    values: list[float] = []
    for _, group in frame.groupby("date"):
        valid = group[[SCORE_COL, return_col]].dropna()
        if len(valid) >= 3 and valid[SCORE_COL].nunique() > 1:
            values.append(float(valid[SCORE_COL].corr(valid[return_col], method="spearman")))
    return float(np.nanmean(values)) if values else None


def _semester_label(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    return f"{timestamp.year}H{1 if timestamp.month <= 6 else 2}"


def evaluate_signed_return_oos(frame: pd.DataFrame, top_fraction: float) -> dict[str, Any]:
    """Évalue un score continu contre le rendement brut et la cible résiduelle."""
    required = [SCORE_COL, "future_return", SIGNED_TARGET_COL, "date", "symbol"]
    work = frame.dropna(subset=required).copy()
    if work.empty:
        return {"rows": 0, "mean_daily_ic_raw": None, "mean_daily_ic_target": None}
    long_tail = _tail(work, SCORE_COL, top_fraction, ascending=False)
    short_tail = _tail(work, SCORE_COL, top_fraction, ascending=True)

    def tail_metrics(tail: pd.DataFrame, sign: float) -> dict[str, Any]:
        raw_signed = sign * tail["future_return"]
        residual_signed = sign * tail[SIGNED_TARGET_COL]
        return {
            "rows": int(len(tail)),
            "dates": int(tail["date"].nunique()),
            "symbols": int(tail["symbol"].nunique()),
            "mean_raw_signed_return": float(raw_signed.mean()),
            "median_raw_signed_return": float(raw_signed.median()),
            "raw_hit_rate": float((raw_signed > 0).mean()),
            "mean_residual_signed_return": float(residual_signed.mean()),
            "median_residual_signed_return": float(residual_signed.median()),
            "residual_hit_rate": float((residual_signed > 0).mean()),
        }

    score = work[SCORE_COL].to_numpy(float)
    target = work[SIGNED_TARGET_COL].to_numpy(float)
    raw = work["future_return"].to_numpy(float)
    target_sign = np.sign(target)
    predicted_sign = np.sign(score)
    nonzero = target_sign != 0
    semester_metrics: dict[str, Any] = {}
    for semester, group in work.groupby(work["date"].map(_semester_label), sort=True):
        semester_long = _tail(group, SCORE_COL, top_fraction, ascending=False)
        semester_short = _tail(group, SCORE_COL, top_fraction, ascending=True)
        semester_metrics[str(semester)] = {
            "rows": int(len(group)),
            "mean_daily_ic_raw": _mean_daily_ic(group, "future_return"),
            "mean_daily_ic_target": _mean_daily_ic(group, SIGNED_TARGET_COL),
            "long_mean_raw_return": float(semester_long["future_return"].mean()),
            "short_mean_signed_raw_return": float((-semester_short["future_return"]).mean()),
        }

    ranked = work.copy()
    ranked["score_bucket"] = (
        ranked.groupby("date")[SCORE_COL].rank(method="first", pct=True).mul(10).sub(1e-12)
        .astype(int).clip(0, 9)
    )
    buckets = []
    for bucket, group in ranked.groupby("score_bucket", sort=True):
        buckets.append({
            "bucket": int(bucket) + 1,
            "rows": int(len(group)),
            "mean_score": float(group[SCORE_COL].mean()),
            "mean_raw_return": float(group["future_return"].mean()),
            "mean_residual_return": float(group[SIGNED_TARGET_COL].mean()),
            "raw_positive_rate": float(group["future_return"].gt(0).mean()),
        })
    return {
        "rows": int(len(work)),
        "mean_daily_ic_raw": _mean_daily_ic(work, "future_return"),
        "mean_daily_ic_target": _mean_daily_ic(work, SIGNED_TARGET_COL),
        "global_spearman_raw": float(pd.Series(score).corr(pd.Series(raw), method="spearman")),
        "global_spearman_target": float(pd.Series(score).corr(pd.Series(target), method="spearman")),
        "rmse_target": float(np.sqrt(np.mean(np.square(score - target)))),
        "mae_target": float(np.mean(np.abs(score - target))),
        "sign_accuracy_target": float((predicted_sign[nonzero] == target_sign[nonzero]).mean()) if nonzero.any() else None,
        "long_top_decile": tail_metrics(long_tail, 1.0),
        "short_bottom_decile": tail_metrics(short_tail, -1.0),
        "long_short_raw_spread": float(long_tail["future_return"].mean() - short_tail["future_return"].mean()),
        "long_short_residual_spread": float(
            long_tail[SIGNED_TARGET_COL].mean() - short_tail[SIGNED_TARGET_COL].mean()
        ),
        "score_buckets": buckets,
        "semesters": semester_metrics,
    }


def _fit_dual_head(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: SharedDirectionalConfig,
    target_column: str,
    *,
    iterations: int | None = None,
) -> Any:
    """Réutilise le classifieur binaire sans pondération d'amplitude."""
    train_head = train.copy()
    train_head[TARGET_COL] = train_head[target_column].astype(int)
    valid_head = None
    if valid is not None:
        valid_head = valid.copy()
        valid_head[TARGET_COL] = valid_head[target_column].astype(int)
    head_config = replace(
        config, objective="classifier", target_mode="decile_direction",
        amplitude_weighting=False,
    )
    return _fit_catboost(
        train_head, valid_head, feature_columns, categorical_columns,
        head_config, iterations=iterations,
    )


def evaluate_dual_oos(frame: pd.DataFrame, top_fraction: float) -> dict[str, Any]:
    """Mesure séparément les deux têtes et leurs décisions avec abstention."""
    required = [
        "date", "symbol", "future_return", LONG_TARGET_COL, SHORT_TARGET_COL,
        P_LONG_COL, P_SHORT_COL,
    ]
    work = frame.dropna(subset=required).copy()
    if work.empty:
        return {"rows": 0, "auc_long": None, "auc_short": None}
    work[DIRECTION_MARGIN_COL] = work[P_LONG_COL] - work[P_SHORT_COL]
    work[SCORE_COL] = work[DIRECTION_MARGIN_COL]

    def head_metrics(target_col: str, probability_col: str) -> dict[str, Any]:
        y = work[target_col].astype(int).to_numpy()
        probability = work[probability_col].astype(float).clip(0.0, 1.0).to_numpy()
        selected = probability >= 0.50
        reliability = []
        buckets = np.minimum((probability * 10).astype(int), 9)
        for bucket in range(10):
            mask = buckets == bucket
            if not mask.any():
                continue
            reliability.append({
                "bucket": bucket + 1,
                "rows": int(mask.sum()),
                "mean_probability": float(probability[mask].mean()),
                "observed_rate": float(y[mask].mean()),
            })
        return {
            "base_rate": float(y.mean()),
            "auc": roc_auc(y, probability) if len(np.unique(y)) == 2 else None,
            "brier": float(np.mean(np.square(probability - y))),
            "selected_rows_at_0_50": int(selected.sum()),
            "precision_at_0_50": float(y[selected].mean()) if selected.any() else None,
            "recall_at_0_50": float(y[selected].sum() / max(1, y.sum())),
            "reliability": reliability,
        }

    def side_metrics(selected: pd.DataFrame, side: str) -> dict[str, Any]:
        sign = 1.0 if side == "long" else -1.0
        target_col = LONG_TARGET_COL if side == "long" else SHORT_TARGET_COL
        opposite_col = SHORT_TARGET_COL if side == "long" else LONG_TARGET_COL
        signed_return = sign * selected["future_return"]
        return {
            "rows": int(len(selected)),
            "dates": int(selected["date"].nunique()),
            "symbols": int(selected["symbol"].nunique()),
            "target_precision": float(selected[target_col].mean()) if len(selected) else None,
            "opposite_rate": float(selected[opposite_col].mean()) if len(selected) else None,
            "mean_signed_return": float(signed_return.mean()) if len(selected) else None,
            "median_signed_return": float(signed_return.median()) if len(selected) else None,
            "hit_rate": float((signed_return > 0).mean()) if len(selected) else None,
        }

    long_tail = _tail(work, SCORE_COL, top_fraction, ascending=False)
    short_tail = _tail(work, SCORE_COL, top_fraction, ascending=True)
    policies: dict[str, Any] = {}
    for min_probability in (0.50, 0.55, 0.60, 0.65, 0.70):
        for min_margin in (0.00, 0.05, 0.10, 0.15, 0.20):
            long_selected = work[
                work[P_LONG_COL].ge(min_probability)
                & work[DIRECTION_MARGIN_COL].ge(min_margin)
            ]
            short_selected = work[
                work[P_SHORT_COL].ge(min_probability)
                & (-work[DIRECTION_MARGIN_COL]).ge(min_margin)
            ]
            selected_rows = len(long_selected) + len(short_selected)
            key = f"p{min_probability:.2f}_m{min_margin:.2f}"
            policies[key] = {
                "min_probability": min_probability,
                "min_margin": min_margin,
                "coverage": float(selected_rows / len(work)),
                "long": side_metrics(long_selected, "long"),
                "short": side_metrics(short_selected, "short"),
            }

    semesters: dict[str, Any] = {}
    for semester, group in work.groupby(work["date"].map(_semester_label), sort=True):
        long_group = _tail(group, SCORE_COL, top_fraction, ascending=False)
        short_group = _tail(group, SCORE_COL, top_fraction, ascending=True)
        semesters[str(semester)] = {
            "rows": int(len(group)),
            "auc_long": roc_auc(
                group[LONG_TARGET_COL].astype(int).to_numpy(), group[P_LONG_COL].to_numpy()
            ) if group[LONG_TARGET_COL].nunique() == 2 else None,
            "auc_short": roc_auc(
                group[SHORT_TARGET_COL].astype(int).to_numpy(), group[P_SHORT_COL].to_numpy()
            ) if group[SHORT_TARGET_COL].nunique() == 2 else None,
            "mean_daily_direction_ic": _mean_daily_ic(group, "future_return"),
            "long_top": side_metrics(long_group, "long"),
            "short_bottom": side_metrics(short_group, "short"),
        }

    long_head = head_metrics(LONG_TARGET_COL, P_LONG_COL)
    short_head = head_metrics(SHORT_TARGET_COL, P_SHORT_COL)
    return {
        "rows": int(len(work)),
        "auc_long": long_head["auc"],
        "auc_short": short_head["auc"],
        "long_head": long_head,
        "short_head": short_head,
        "mean_daily_direction_ic": _mean_daily_ic(work, "future_return"),
        "long_top_decile": side_metrics(long_tail, "long"),
        "short_bottom_decile": side_metrics(short_tail, "short"),
        "long_short_raw_spread": float(
            long_tail["future_return"].mean() - short_tail["future_return"].mean()
        ),
        "policies": policies,
        "semesters": semesters,
    }


def summarize_dual_fold_stability(folds: list[dict[str, Any]]) -> dict[str, Any]:
    """Résume la stabilité sans mélanger les échelles de probabilité des folds."""
    if not folds:
        return {}

    def summarize(key: str) -> dict[str, Any]:
        values = np.asarray([fold[key] for fold in folds if fold.get(key) is not None], dtype=float)
        return {
            "mean": float(values.mean()) if values.size else None,
            "std": float(values.std()) if values.size else None,
            "min": float(values.min()) if values.size else None,
            "median": float(np.median(values)) if values.size else None,
            "positive_folds": int((values > 0).sum()) if values.size else 0,
            "above_half_folds": int((values > 0.5).sum()) if values.size else 0,
            "valid_folds": int(values.size),
        }

    long_returns = [fold["long_top_decile"]["mean_signed_return"] for fold in folds]
    short_returns = [fold["short_bottom_decile"]["mean_signed_return"] for fold in folds]
    return {
        "auc_long": summarize("auc_long"),
        "auc_short": summarize("auc_short"),
        "daily_direction_ic": summarize("mean_daily_direction_ic"),
        "long_return_positive_folds": int(sum(value > 0 for value in long_returns)),
        "short_return_positive_folds": int(sum(value > 0 for value in short_returns)),
    }


def _probability_logit(probability: Iterable[float]) -> np.ndarray:
    values = np.clip(np.asarray(list(probability), dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(values / (1.0 - values))


def fit_non_inverting_platt(
    raw_probability: Iterable[float],
    target: Iterable[int],
    *,
    max_iter: int = 100,
) -> tuple[PlattCalibrator, dict[str, Any]]:
    """Ajuste Platt sur validation et interdit un retournement opportuniste du rang."""
    probability = np.asarray(list(raw_probability), dtype=float)
    labels = np.asarray(list(target), dtype=int)
    if len(probability) < 2 or len(np.unique(labels)) < 2:
        raise ValueError("Validation insuffisante pour calibrer E2-B.")
    calibrator = PlattCalibrator(max_iter=max_iter).fit(_probability_logit(probability), labels)
    fallback = None
    if not calibrator.fitted or not np.isfinite(calibrator.slope) or calibrator.slope <= 0:
        prevalence = float(np.clip(labels.mean(), 1e-6, 1.0 - 1e-6))
        calibrator = PlattCalibrator(
            slope=0.0,
            intercept=float(np.log(prevalence / (1.0 - prevalence))),
            fitted=True,
            max_iter=max_iter,
        )
        fallback = "non_positive_slope_to_validation_prevalence"
    return calibrator, {
        "method": "platt",
        "fit_scope": "validation_only",
        "slope": float(calibrator.slope),
        "intercept": float(calibrator.intercept),
        "fallback": fallback,
    }


def apply_platt(calibrator: PlattCalibrator, raw_probability: Iterable[float]) -> np.ndarray:
    return np.asarray(
        calibrator.predict_proba(_probability_logit(raw_probability)), dtype=float,
    ).reshape(-1)


def _expected_calibration_error(labels: np.ndarray, probability: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for index in range(bins):
        mask = (probability >= edges[index]) & (
            probability <= edges[index + 1] if index == bins - 1 else probability < edges[index + 1]
        )
        if mask.any():
            result += float(mask.mean()) * abs(float(labels[mask].mean()) - float(probability[mask].mean()))
    return float(result)


def _long_selection_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "rows": 0, "dates": 0, "symbols": 0, "precision": None,
            "mean_return": None, "median_return": None, "hit_rate": None,
        }
    returns = pd.to_numeric(frame["future_return"], errors="coerce")
    return {
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "precision": float(frame[LONG_TARGET_COL].mean()),
        "mean_return": float(returns.mean()),
        "median_return": float(returns.median()),
        "hit_rate": float(returns.gt(0).mean()),
    }


def _matched_pool_expectation(frame: pd.DataFrame, fraction: float) -> dict[str, Any]:
    """Espérance d'un tirage aléatoire de même taille dans chaque pool journalier."""
    weighted_returns: list[float] = []
    weighted_targets: list[float] = []
    total = 0
    for _, group in frame.groupby("date", sort=False):
        count = max(1, math.ceil(len(group) * fraction))
        total += count
        weighted_returns.extend([float(group["future_return"].mean())] * count)
        weighted_targets.extend([float(group[LONG_TARGET_COL].mean())] * count)
    return {
        "rows": int(total),
        "expected_mean_return": float(np.mean(weighted_returns)) if weighted_returns else None,
        "expected_precision": float(np.mean(weighted_targets)) if weighted_targets else None,
    }


def evaluate_long_confirmation(
    frame: pd.DataFrame,
    fractions: Iterable[float] = (0.05, 0.10, 0.20),
) -> dict[str, Any]:
    """Évalue E2-B sans chercher de seuil sur le test."""
    required = [
        "date", "symbol", "future_return", LONG_TARGET_COL,
        RAW_LONG_PROBA_COL, CAL_LONG_PROBA_COL, ORACLE_GATE_SCORE_COL,
    ]
    work = frame.dropna(subset=required).copy()
    if work.empty:
        return {"rows": 0}
    labels = work[LONG_TARGET_COL].astype(int).to_numpy()
    raw = work[RAW_LONG_PROBA_COL].astype(float).to_numpy()
    calibrated = work[CAL_LONG_PROBA_COL].astype(float).to_numpy()
    prevalence = float(labels.mean())
    constant_brier = float(prevalence * (1.0 - prevalence))
    selections: dict[str, Any] = {}
    for fraction in sorted({float(value) for value in fractions}):
        model_selected = _tail(work, CAL_LONG_PROBA_COL, fraction, ascending=False)
        oracle_selected = _tail(work, ORACLE_GATE_SCORE_COL, fraction, ascending=False)
        model_metrics = _long_selection_metrics(model_selected)
        oracle_metrics = _long_selection_metrics(oracle_selected)
        matched = _matched_pool_expectation(work, fraction)
        model_metrics["precision_lift_vs_matched"] = float(
            model_metrics["precision"] - matched["expected_precision"]
        )
        model_metrics["return_lift_vs_matched"] = float(
            model_metrics["mean_return"] - matched["expected_mean_return"]
        )
        selections[f"top_{int(round(fraction * 100)):02d}_pct"] = {
            "fraction": fraction,
            "model": model_metrics,
            "oracle_amplitude": oracle_metrics,
            "matched_random_expectation": matched,
        }

    threshold_policies: dict[str, Any] = {}
    for threshold in (0.30, 0.35, 0.40, 0.45, 0.50):
        selected = work[work[CAL_LONG_PROBA_COL].ge(threshold)]
        threshold_policies[f"p{threshold:.2f}"] = {
            "coverage": float(len(selected) / len(work)),
            **_long_selection_metrics(selected),
        }
    work[SCORE_COL] = work[CAL_LONG_PROBA_COL]
    return {
        "rows": int(len(work)),
        "base_rate": prevalence,
        "pool_mean_return": float(work["future_return"].mean()),
        "auc_raw": roc_auc(labels, raw),
        "auc_calibrated": roc_auc(labels, calibrated),
        "brier_constant": constant_brier,
        "brier_raw": float(np.mean(np.square(raw - labels))),
        "brier_calibrated": float(np.mean(np.square(calibrated - labels))),
        "ece_raw": _expected_calibration_error(labels, raw),
        "ece_calibrated": _expected_calibration_error(labels, calibrated),
        "mean_daily_ic": _mean_daily_ic(work, "future_return"),
        "selections": selections,
        "threshold_policies": threshold_policies,
    }


def evaluate_oos(
    frame: pd.DataFrame,
    top_fraction: float,
    *,
    probability_score: bool = True,
) -> dict[str, Any]:
    work = frame.dropna(subset=[SCORE_COL, "future_return", "oracle_decile"]).copy()
    extremes = work[work["oracle_decile"].isin([1, 10])]
    long_tail = _tail(work, SCORE_COL, top_fraction, ascending=False)
    short_tail = _tail(work, SCORE_COL, top_fraction, ascending=True)

    def tail_metrics(tail: pd.DataFrame, expected_decile: int, opposite_decile: int, sign: float) -> dict[str, Any]:
        signed = sign * tail["future_return"]
        return {
            "rows": int(len(tail)),
            "dates": int(tail["date"].nunique()),
            "symbols": int(tail["symbol"].nunique()),
            "target_decile_precision": float(tail["oracle_decile"].eq(expected_decile).mean()),
            "opposite_decile_contamination": float(tail["oracle_decile"].eq(opposite_decile).mean()),
            "mean_signed_return": float(signed.mean()),
            "median_signed_return": float(signed.median()),
            "hit_rate": float((signed > 0).mean()),
        }

    abstention: dict[str, Any] = {}
    for raw_threshold in ((0.55, 0.60, 0.65, 0.70, 0.75, 0.80) if probability_score else ()):
        selected = extremes[(extremes[SCORE_COL] >= raw_threshold) | (extremes[SCORE_COL] <= 1.0 - raw_threshold)]
        correct = (
            ((selected[SCORE_COL] >= raw_threshold) & selected["oracle_decile"].eq(10))
            | ((selected[SCORE_COL] <= 1.0 - raw_threshold) & selected["oracle_decile"].eq(1))
        )
        abstention[f"raw_{raw_threshold:.2f}"] = {
            "coverage_extremes": float(len(selected) / len(extremes)) if len(extremes) else 0.0,
            "direction_accuracy": float(correct.mean()) if len(selected) else None,
            "rows": int(len(selected)),
        }
    y = extremes["oracle_decile"].eq(10).astype(int).to_numpy()
    return {
        "rows": int(len(work)),
        "extreme_rows": int(len(extremes)),
        "auc_d10_vs_d1": roc_auc(y, extremes[SCORE_COL].to_numpy()) if len(np.unique(y)) == 2 else None,
        "mean_daily_direction_ic": _mean_daily_ic(work),
        "long_top_decile": tail_metrics(long_tail, 10, 1, 1.0),
        "short_bottom_decile": tail_metrics(short_tail, 1, 10, -1.0),
        "abstention": abstention,
    }


def train_shared_directional(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: SharedDirectionalConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=config.min_train_dates,
        val_dates=config.val_dates,
        test_dates=config.test_dates,
        step_dates=config.step_dates,
        max_splits=config.max_splits,
        forecast_horizon=config.horizon,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward mutualisé valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    best_iterations: list[int] = []
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[TARGET_COL]).copy()
        valid = fold["val"].dropna(subset=[TARGET_COL]).copy()
        test = fold["test"].dropna(subset=[TARGET_COL]).copy()
        invalid_classes = (
            config.target_mode == "decile_direction"
            and (train[TARGET_COL].nunique() < 2 or valid[TARGET_COL].nunique() < 2)
        )
        if invalid_classes or train.empty or valid.empty or test.empty:
            LOGGER.warning("shared_direction fold=%d skipped: cible ou test insuffisants", index)
            continue
        fit_train, fit_valid = train, valid
        target_clip: tuple[float, float] | None = None
        if config.target_mode == "signed_return":
            fit_train, fit_valid, target_clip = clip_signed_targets_from_train(train, valid, config)
        model = _fit_catboost(fit_train, fit_valid, feature_columns, categorical_columns, config)
        if config.objective in {"pairwise_ranker", "regressor"}:
            score = np.asarray(model.predict(_prepare_X(test, feature_columns, categorical_columns)), dtype=float)
        else:
            score = model.predict_proba(_prepare_X(test, feature_columns, categorical_columns))[:, 1]
        score_columns = ["date", "symbol", "future_return", "oracle_decile", TARGET_COL]
        if config.target_mode == "signed_return":
            score_columns.extend([
                SIGNED_TARGET_COL, SPY_RETURN_COL, EXCESS_SPY_COL,
                SECTOR_RESIDUAL_COL, "sector_members",
            ])
        scored = test[list(dict.fromkeys(score_columns))].copy()
        scored[SCORE_COL] = score
        scored["fold_index"] = index
        oos_parts.append(scored)
        metrics = (
            evaluate_signed_return_oos(scored, config.top_fraction)
            if config.target_mode == "signed_return"
            else evaluate_oos(
                scored, config.top_fraction,
                probability_score=config.objective == "classifier",
            )
        )
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows_extreme": int(len(train)),
            "valid_rows_extreme": int(len(valid)),
            "target_clip_train_only": (
                {"lower": target_clip[0], "upper": target_clip[1]}
                if target_clip is not None else None
            ),
        })
        fold_metrics.append(metrics)
        best_iterations.append(max(1, int(model.get_best_iteration()) + 1))
        if config.target_mode == "signed_return":
            LOGGER.info(
                "shared_signed_return h=%d fold=%d ic_raw=%s ic_target=%s long_ret=%s short_ret=%s",
                config.horizon, index, metrics.get("mean_daily_ic_raw"),
                metrics.get("mean_daily_ic_target"),
                metrics.get("long_top_decile", {}).get("mean_raw_signed_return"),
                metrics.get("short_bottom_decile", {}).get("mean_raw_signed_return"),
            )
        else:
            LOGGER.info(
                "shared_direction fold=%d auc=%s ic=%s long_ret=%s short_ret=%s",
                index, metrics["auc_d10_vs_d1"], metrics["mean_daily_direction_ic"],
                metrics["long_top_decile"]["mean_signed_return"],
                metrics["short_bottom_decile"]["mean_signed_return"],
            )
    if not oos_parts:
        raise ValueError("Tous les folds mutualisés ont été rejetés.")

    oos = pd.concat(oos_parts, ignore_index=True)
    overall = (
        evaluate_signed_return_oos(oos, config.top_fraction)
        if config.target_mode == "signed_return"
        else evaluate_oos(
            oos, config.top_fraction,
            probability_score=config.objective == "classifier",
        )
    )
    labeled = dataset.dropna(subset=[TARGET_COL]).copy()
    final_iterations = max(10, int(np.median(best_iterations)))
    final_fit = labeled
    final_target_clip: tuple[float, float] | None = None
    if config.target_mode == "signed_return":
        final_fit, _, final_target_clip = clip_signed_targets_from_train(labeled, None, config)
    final_model = _fit_catboost(
        final_fit, None, feature_columns, categorical_columns, config,
        iterations=final_iterations,
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_path = artifact_dir / "model.cbm"
    final_model.save_model(str(model_path))
    oos_path = artifact_dir / "oof_predictions.parquet"
    oos.to_parquet(oos_path, index=False)
    metrics = {
        "status": "completed",
        "model_role": "direction_shared",
        "model_name": {
            "pairwise_ranker": "catboost_pairwise",
            "regressor": "catboost_signed_return_regressor",
            "classifier": "catboost_classifier",
        }[config.objective],
        "objective": config.objective,
        "target_mode": config.target_mode,
        "horizon": config.horizon,
        "residualization": config.residualization if config.target_mode == "signed_return" else None,
        "target_clip_final": (
            {"lower": final_target_clip[0], "upper": final_target_clip[1]}
            if final_target_clip is not None else None
        ),
        "n_folds": len(fold_metrics),
        "final_iterations": final_iterations,
        "overall": overall,
        "folds": fold_metrics,
        "feature_count_numeric": len(feature_columns),
        "categorical_columns": categorical_columns,
        "trained_rows_extreme": int(len(labeled)),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "trained_through_date": str(pd.Timestamp(dataset["date"].max()).date()),
        "artifact_paths": {"model": str(model_path), "oof": str(oos_path)},
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def train_dual_directional(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: SharedDirectionalConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Entraîne les têtes LONG et SHORT avec les mêmes folds temporels."""
    if config.target_mode != "dual_threshold" or config.objective != "dual_classifier":
        raise ValueError("train_dual_directional exige le contrat E2.")
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=config.min_train_dates,
        val_dates=config.val_dates,
        test_dates=config.test_dates,
        step_dates=config.step_dates,
        max_splits=config.max_splits,
        forecast_horizon=config.horizon,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E2 valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    long_iterations: list[int] = []
    short_iterations: list[int] = []
    target_columns = [LONG_TARGET_COL, SHORT_TARGET_COL]
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=target_columns).copy()
        valid = fold["val"].dropna(subset=target_columns).copy()
        test = fold["test"].dropna(subset=target_columns).copy()
        classes_valid = all(
            train[column].nunique() == 2 and valid[column].nunique() == 2
            for column in target_columns
        )
        if not classes_valid or train.empty or valid.empty or test.empty:
            LOGGER.warning("shared_dual h=%d fold=%d skipped: classes insuffisantes", config.horizon, index)
            continue
        long_model = _fit_dual_head(
            train, valid, feature_columns, categorical_columns, config, LONG_TARGET_COL,
        )
        short_model = _fit_dual_head(
            train, valid, feature_columns, categorical_columns, config, SHORT_TARGET_COL,
        )
        X_test = _prepare_X(test, feature_columns, categorical_columns)
        scored = test[[
            "date", "symbol", "future_return", SPY_RETURN_COL, EXCESS_SPY_COL,
            SECTOR_RESIDUAL_COL, "oracle_decile", LONG_TARGET_COL, SHORT_TARGET_COL,
        ]].copy()
        scored[P_LONG_COL] = long_model.predict_proba(X_test)[:, 1]
        scored[P_SHORT_COL] = short_model.predict_proba(X_test)[:, 1]
        scored[DIRECTION_MARGIN_COL] = scored[P_LONG_COL] - scored[P_SHORT_COL]
        scored["fold_index"] = index
        oos_parts.append(scored)
        metrics = evaluate_dual_oos(scored, config.top_fraction)
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows": int(len(train)),
            "valid_rows": int(len(valid)),
        })
        fold_metrics.append(metrics)
        long_iterations.append(max(1, int(long_model.get_best_iteration()) + 1))
        short_iterations.append(max(1, int(short_model.get_best_iteration()) + 1))
        LOGGER.info(
            "shared_dual h=%d fold=%d auc_long=%s auc_short=%s ic=%s long_ret=%s short_ret=%s",
            config.horizon, index, metrics["auc_long"], metrics["auc_short"],
            metrics["mean_daily_direction_ic"],
            metrics["long_top_decile"]["mean_signed_return"],
            metrics["short_bottom_decile"]["mean_signed_return"],
        )
    if not oos_parts:
        raise ValueError("Tous les folds E2 ont été rejetés.")

    oos = pd.concat(oos_parts, ignore_index=True)
    overall = evaluate_dual_oos(oos, config.top_fraction)
    labeled = dataset.dropna(subset=target_columns).copy()
    final_long_iterations = max(10, int(np.median(long_iterations)))
    final_short_iterations = max(10, int(np.median(short_iterations)))
    final_long = _fit_dual_head(
        labeled, None, feature_columns, categorical_columns, config,
        LONG_TARGET_COL, iterations=final_long_iterations,
    )
    final_short = _fit_dual_head(
        labeled, None, feature_columns, categorical_columns, config,
        SHORT_TARGET_COL, iterations=final_short_iterations,
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    long_path = artifact_dir / "long_model.cbm"
    short_path = artifact_dir / "short_model.cbm"
    oos_path = artifact_dir / "oof_predictions.parquet"
    final_long.save_model(str(long_path))
    final_short.save_model(str(short_path))
    oos.to_parquet(oos_path, index=False)
    metrics = {
        "status": "completed",
        "model_role": "direction_shared_dual",
        "model_name": "catboost_dual_threshold",
        "objective": config.objective,
        "target_mode": config.target_mode,
        "horizon": config.horizon,
        "target_up_threshold": config.target_up_threshold,
        "target_down_threshold": config.target_down_threshold,
        "n_folds": len(fold_metrics),
        "final_iterations": {
            "long": final_long_iterations, "short": final_short_iterations,
        },
        "overall": overall,
        "folds": fold_metrics,
        "fold_stability": summarize_dual_fold_stability(fold_metrics),
        "feature_count_numeric": len(feature_columns),
        "categorical_columns": categorical_columns,
        "trained_rows": int(len(labeled)),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "trained_through_date": str(pd.Timestamp(dataset["date"].max()).date()),
        "artifact_paths": {
            "long_model": str(long_path), "short_model": str(short_path), "oof": str(oos_path),
        },
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def train_long_confirmation(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: SharedDirectionalConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    """E2-B : LONG H3, Platt validation-only, politique top-k figée."""
    if config.horizon != 3:
        raise ValueError("E2-B est figé sur H3.")
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=config.min_train_dates,
        val_dates=config.val_dates,
        test_dates=config.test_dates,
        step_dates=config.step_dates,
        max_splits=config.max_splits,
        forecast_horizon=config.horizon,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E2-B valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    best_iterations: list[int] = []
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[LONG_TARGET_COL]).copy()
        valid = fold["val"].dropna(subset=[LONG_TARGET_COL]).copy()
        test = fold["test"].dropna(subset=[LONG_TARGET_COL]).copy()
        if any(part.empty or part[LONG_TARGET_COL].nunique() < 2 for part in (train, valid, test)):
            LOGGER.warning("long_confirmation fold=%d skipped: cible insuffisante", index)
            continue
        model = _fit_dual_head(
            train, valid, feature_columns, categorical_columns, config, LONG_TARGET_COL,
        )
        raw_valid = model.predict_proba(_prepare_X(valid, feature_columns, categorical_columns))[:, 1]
        calibrator, calibration_contract = fit_non_inverting_platt(
            raw_valid, valid[LONG_TARGET_COL].astype(int).to_numpy(),
            max_iter=config.calibration_max_iter,
        )
        raw_test = model.predict_proba(_prepare_X(test, feature_columns, categorical_columns))[:, 1]
        calibrated_test = apply_platt(calibrator, raw_test)
        scored = test[[
            "date", "symbol", "future_return", LONG_TARGET_COL,
            ORACLE_GATE_SCORE_COL, "oracle_decile", SPY_RETURN_COL,
            EXCESS_SPY_COL, SECTOR_RESIDUAL_COL,
        ]].copy()
        scored[RAW_LONG_PROBA_COL] = raw_test
        scored[CAL_LONG_PROBA_COL] = calibrated_test
        scored["fold_index"] = index
        oos_parts.append(scored)
        metrics = evaluate_long_confirmation(scored)
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows": int(len(train)),
            "valid_rows": int(len(valid)),
            "calibration": calibration_contract,
        })
        fold_metrics.append(metrics)
        best_iterations.append(max(1, int(model.get_best_iteration()) + 1))
        top10 = metrics["selections"]["top_10_pct"]["model"]
        LOGGER.info(
            "long_confirmation fold=%d auc=%s brier=%s top10_precision_lift=%s return_lift=%s",
            index, metrics["auc_raw"], metrics["brier_calibrated"],
            top10["precision_lift_vs_matched"], top10["return_lift_vs_matched"],
        )
    if not oos_parts:
        raise ValueError("Tous les folds E2-B ont été rejetés.")

    oos = pd.concat(oos_parts, ignore_index=True)
    overall = evaluate_long_confirmation(oos)
    auc_values = np.asarray([fold["auc_raw"] for fold in fold_metrics], dtype=float)
    top10_precision_lifts = np.asarray([
        fold["selections"]["top_10_pct"]["model"]["precision_lift_vs_matched"]
        for fold in fold_metrics
    ], dtype=float)
    top10_return_lifts = np.asarray([
        fold["selections"]["top_10_pct"]["model"]["return_lift_vs_matched"]
        for fold in fold_metrics
    ], dtype=float)
    calibration_better_folds = sum(
        fold["brier_calibrated"] < fold["brier_constant"] for fold in fold_metrics
    )
    gates = {
        "mean_fold_auc_gte_0_53": bool(auc_values.mean() >= 0.53),
        "auc_above_half_folds_gte_7": bool((auc_values > 0.5).sum() >= 7),
        "top10_precision_lift_gte_0_02": bool(
            overall["selections"]["top_10_pct"]["model"]["precision_lift_vs_matched"] >= 0.02
        ),
        "top10_return_lift_gte_0_0025": bool(
            overall["selections"]["top_10_pct"]["model"]["return_lift_vs_matched"] >= 0.0025
        ),
        "top10_positive_return_lift_folds_gte_7": bool((top10_return_lifts > 0).sum() >= 7),
        "calibrated_brier_better_than_constant": bool(
            overall["brier_calibrated"] < overall["brier_constant"]
        ),
    }

    # Modèle de confirmation : les dernières dates restent réservées à Platt.
    labeled = dataset.dropna(subset=[LONG_TARGET_COL]).sort_values(["date", "symbol"]).copy()
    unique_dates = np.asarray(sorted(pd.to_datetime(labeled["date"]).dt.normalize().unique()))
    if len(unique_dates) <= config.val_dates + config.horizon:
        raise ValueError("Historique insuffisant pour réserver la calibration finale E2-B.")
    calibration_dates = unique_dates[-config.val_dates:]
    cutoff_index = len(unique_dates) - config.val_dates - config.horizon
    train_dates = unique_dates[:cutoff_index]
    final_train = labeled[labeled["date"].isin(train_dates)].copy()
    final_calibration = labeled[labeled["date"].isin(calibration_dates)].copy()
    final_iterations = max(10, int(np.median(best_iterations)))
    final_model = _fit_dual_head(
        final_train, None, feature_columns, categorical_columns, config,
        LONG_TARGET_COL, iterations=final_iterations,
    )
    final_cal_raw = final_model.predict_proba(
        _prepare_X(final_calibration, feature_columns, categorical_columns)
    )[:, 1]
    final_calibrator, final_calibration_contract = fit_non_inverting_platt(
        final_cal_raw, final_calibration[LONG_TARGET_COL].astype(int).to_numpy(),
        max_iter=config.calibration_max_iter,
    )

    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_path = artifact_dir / "long_h3_model.cbm"
    calibrator_path = artifact_dir / "long_h3_platt.json"
    oos_path = artifact_dir / "oof_predictions.parquet"
    final_model.save_model(str(model_path))
    calibrator_path.write_text(
        json.dumps(final_calibrator.state_dict(), indent=2), encoding="utf-8"
    )
    oos.to_parquet(oos_path, index=False)
    metrics = {
        "status": "completed",
        "experiment": "E2B_long_h3_nested_calibration",
        "n_folds": len(fold_metrics),
        "final_iterations": final_iterations,
        "overall": overall,
        "folds": fold_metrics,
        "fold_stability": {
            "auc_mean": float(auc_values.mean()),
            "auc_std": float(auc_values.std()),
            "auc_min": float(auc_values.min()),
            "auc_above_half_folds": int((auc_values > 0.5).sum()),
            "top10_precision_lift_mean": float(top10_precision_lifts.mean()),
            "top10_return_lift_mean": float(top10_return_lifts.mean()),
            "top10_positive_return_lift_folds": int((top10_return_lifts > 0).sum()),
            "calibration_better_than_constant_folds": int(calibration_better_folds),
        },
        "development_gates": gates,
        "development_gates_passed": bool(all(gates.values())),
        "untouched_confirmation_completed": False,
        "promotion_ready": False,
        "final_training": {
            "train_start": str(pd.Timestamp(final_train["date"].min()).date()),
            "train_end": str(pd.Timestamp(final_train["date"].max()).date()),
            "calibration_start": str(pd.Timestamp(final_calibration["date"].min()).date()),
            "calibration_end": str(pd.Timestamp(final_calibration["date"].max()).date()),
            "calibration": final_calibration_contract,
        },
        "artifact_paths": {
            "model": str(model_path), "calibrator": str(calibrator_path), "oof": str(oos_path),
        },
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_experiment(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    config: SharedDirectionalConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    config = config or SharedDirectionalConfig()
    profile = load_profile(profile_path)
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, oracle_batch_id, config.horizon)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    source_root = Path("artifacts/models") / oracle_batch_id
    gate_path = source_root / "_oracle_oof_gate.parquet"
    dataset, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=config,
    )
    run_id = f"shared-direction-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    artifact_dir = artifacts_root / run_id
    metrics = train_shared_directional(dataset, features, categoricals, config, artifact_dir)
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "source_oracle_batch_id": oracle_batch_id,
        "status": metrics["status"],
        "serving_ready": False,
        "research_only": True,
        "population": population,
        "target_contract": {
            "mode": "pairwise_d1_vs_d10_by_date" if config.objective == "pairwise_ranker" else "binary_d1_vs_d10",
            "middle_class": "excluded_from_fit_scored_in_oof",
            "horizon": config.horizon,
            "return_basis": "cross_sectional_decile",
            "amplitude_weighting": [config.amplitude_weight_min, config.amplitude_weight_max],
            "amplitude_weighting_enabled": (
                config.amplitude_weighting and config.objective == "classifier"
            ),
            "amplitude_weighting_note": (
                "PairLogit n'accepte pas les poids individuels."
                if config.objective == "pairwise_ranker" else None
            ),
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test",
            "pool_pct": config.pool_pct,
            "oracle_score_is_feature": False,
            "gate_path": str(gate_path),
        },
        "abstention": {
            "mapping": "directional_mass=abs(2*p_d10-1); remainder=flat",
            "promotion_threshold": "not_selected_during_research",
        },
        "feature_profile": profile,
        "feature_columns": features,
        "categorical_columns": categoricals,
        "context_mode": config.context_mode,
        "objective": config.objective,
        "walk_forward": {
            "min_train_dates": config.min_train_dates,
            "val_dates": config.val_dates,
            "test_dates": config.test_dates,
            "step_dates": config.step_dates,
            "max_splits": config.max_splits,
        },
        "metrics": metrics,
    }
    (artifact_dir / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (artifact_dir / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return artifact_dir, contract


def run_signed_return_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    horizons: Iterable[int] = (3, 5, 10, 20),
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    config: SharedDirectionalConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Exécute E1 sur plusieurs horizons en réutilisant une matrice de features."""
    normalized_horizons = sorted({int(value) for value in horizons})
    if not normalized_horizons or min(normalized_horizons) < 1:
        raise ValueError("La campagne signed_return exige au moins un horizon positif.")
    config = config or SharedDirectionalConfig(
        objective="regressor", target_mode="signed_return", amplitude_weighting=False,
    )
    if config.target_mode != "signed_return" or config.objective != "regressor":
        raise ValueError("Configuration incompatible avec la campagne signed_return.")
    profile = load_profile(profile_path)
    from modelFactory.oracle.train import get_universe_symbols

    # Le gate et la population Oracle restent ceux du contrat canonique H20.
    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    source_root = Path("artifacts/models") / oracle_batch_id
    gate_path = source_root / "_oracle_oof_gate.parquet"
    base_config = replace(
        config, horizon=20, objective="classifier", target_mode="decile_direction",
    )
    oracle_pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=base_config,
    )
    forward_panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date,
        horizons=normalized_horizons, sector_min_members=config.sector_min_members,
    )

    run_id = f"shared-signed-return-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    campaign_dir = artifacts_root / run_id
    campaign_dir.mkdir(parents=True, exist_ok=False)
    results: dict[str, Any] = {}
    for horizon in normalized_horizons:
        horizon_config = replace(
            config, horizon=horizon, objective="regressor",
            target_mode="signed_return", amplitude_weighting=False,
        )
        dataset = attach_signed_return_target(
            oracle_pool, forward_panel, horizon=horizon,
            residualization=horizon_config.residualization,
        )
        usable = dataset[TARGET_COL].notna()
        if int(usable.sum()) < 100:
            raise ValueError(f"Cible signed_return H{horizon} insuffisante: {int(usable.sum())} lignes.")
        horizon_dir = campaign_dir / f"h{horizon}"
        metrics = train_shared_directional(
            dataset, features, categoricals, horizon_config, horizon_dir,
        )
        horizon_contract = {
            "schema_version": 1,
            "run_id": run_id,
            "source_oracle_batch_id": oracle_batch_id,
            "status": metrics["status"],
            "serving_ready": False,
            "research_only": True,
            "target_contract": {
                "mode": "continuous_signed_return",
                "horizon_sessions": horizon,
                "residualization": horizon_config.residualization,
                "raw_return_retained_for_economic_evaluation": True,
                "price_convention": "adjusted_close",
                "fit_population": "all_oracle_oof_pool_events",
                "oracle_h20_deciles_used_as_target": False,
                "sector_fallback": "excess_spy_when_sector_members_below_threshold",
                "sector_min_members": horizon_config.sector_min_members,
                "target_winsorization": {
                    "lower_quantile": horizon_config.target_winsor_lower,
                    "upper_quantile": horizon_config.target_winsor_upper,
                    "fit_scope": "train_only_per_fold",
                    "raw_returns_clipped_for_economic_metrics": False,
                },
            },
            "conditioning": {
                "source": "oracle_walk_forward_oof_test",
                "pool_pct": horizon_config.pool_pct,
                "oracle_score_is_feature": False,
                "gate_path": str(gate_path),
            },
            "population": {
                **population,
                "target_rows": int(usable.sum()),
                "target_coverage": float(usable.mean()),
            },
            "feature_profile": profile,
            "feature_columns": features,
            "categorical_columns": categoricals,
            "context_mode": horizon_config.context_mode,
            "walk_forward": {
                "min_train_dates": horizon_config.min_train_dates,
                "val_dates": horizon_config.val_dates,
                "test_dates": horizon_config.test_dates,
                "step_dates": horizon_config.step_dates,
                "max_splits": horizon_config.max_splits,
            },
            "metrics": metrics,
        }
        (horizon_dir / "contract.json").write_text(
            json.dumps(horizon_contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        results[str(horizon)] = horizon_contract

    campaign = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment": "E1_signed_return_multi_horizon",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed",
        "serving_ready": False,
        "research_only": True,
        "horizons": normalized_horizons,
        "residualization": config.residualization,
        "target_diagnostics": target_diagnostics,
        "results": results,
    }
    (campaign_dir / "campaign.json").write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (campaign_dir / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return campaign_dir, campaign


def _format_signed_campaign(path: Path, campaign: dict[str, Any]) -> str:
    residualization = campaign.get("residualization")
    lines = [
        f"E1 signed_return terminé: {path}",
        f"Résidualisation: {residualization}",
    ]
    for horizon in campaign["horizons"]:
        metrics = campaign["results"][str(horizon)]["metrics"]
        overall = metrics["overall"]
        folds = metrics.get("n_folds")
        ic_raw = overall.get("mean_daily_ic_raw")
        ic_target = overall.get("mean_daily_ic_target")
        long_return = overall["long_top_decile"]["mean_raw_signed_return"]
        short_return = overall["short_bottom_decile"]["mean_raw_signed_return"]
        lines.append(
            f"H{horizon}: folds={folds} "
            f"IC brut={ic_raw:+.4f} IC cible={ic_target:+.4f} "
            f"LONG={long_return:+.2%} SHORT={short_return:+.2%}"
        )
    lines.append("Serving désactivé: E1 est une expérience OOS, pas un modèle de production.")
    return "\n".join(lines)


def run_dual_threshold_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    horizons: Iterable[int] = (3, 5, 10, 20),
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    config: SharedDirectionalConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Exécute E2 avec deux classifieurs indépendants par horizon."""
    normalized_horizons = sorted({int(value) for value in horizons})
    if not normalized_horizons or min(normalized_horizons) < 1:
        raise ValueError("La campagne dual_threshold exige des horizons positifs.")
    config = config or SharedDirectionalConfig(
        objective="dual_classifier", target_mode="dual_threshold", amplitude_weighting=False,
    )
    if config.target_mode != "dual_threshold" or config.objective != "dual_classifier":
        raise ValueError("Configuration incompatible avec la campagne dual_threshold.")
    profile = load_profile(profile_path)
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    source_root = Path("artifacts/models") / oracle_batch_id
    gate_path = source_root / "_oracle_oof_gate.parquet"
    base_config = replace(
        config, horizon=20, objective="classifier", target_mode="decile_direction",
    )
    oracle_pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=base_config,
    )
    forward_panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date,
        horizons=normalized_horizons, sector_min_members=config.sector_min_members,
    )

    run_id = f"shared-dual-threshold-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    campaign_dir = artifacts_root / run_id
    campaign_dir.mkdir(parents=True, exist_ok=False)
    results: dict[str, Any] = {}
    for horizon in normalized_horizons:
        horizon_config = replace(
            config, horizon=horizon, objective="dual_classifier",
            target_mode="dual_threshold", amplitude_weighting=False,
        )
        dataset = attach_dual_threshold_targets(
            oracle_pool, forward_panel, horizon=horizon,
            up_threshold=horizon_config.target_up_threshold,
            down_threshold=horizon_config.target_down_threshold,
        )
        usable = dataset[[LONG_TARGET_COL, SHORT_TARGET_COL]].notna().all(axis=1)
        if int(usable.sum()) < 100:
            raise ValueError(f"Cibles E2 H{horizon} insuffisantes: {int(usable.sum())} lignes.")
        horizon_dir = campaign_dir / f"h{horizon}"
        metrics = train_dual_directional(
            dataset, features, categoricals, horizon_config, horizon_dir,
        )
        horizon_contract = {
            "schema_version": 1,
            "run_id": run_id,
            "source_oracle_batch_id": oracle_batch_id,
            "status": metrics["status"],
            "serving_ready": False,
            "research_only": True,
            "target_contract": {
                "mode": "dual_terminal_threshold",
                "horizon_sessions": horizon,
                "long_label": f"adjusted_return >= {horizon_config.target_up_threshold}",
                "short_label": f"adjusted_return <= {horizon_config.target_down_threshold}",
                "heads": "independent_binary_classifiers",
                "fit_population": "all_oracle_oof_pool_events",
                "path_first_touch": False,
                "calibration": "none_raw_oof_probabilities",
            },
            "conditioning": {
                "source": "oracle_walk_forward_oof_test",
                "pool_pct": horizon_config.pool_pct,
                "oracle_score_is_feature": False,
                "gate_path": str(gate_path),
            },
            "population": {
                **population,
                "target_rows": int(usable.sum()),
                "target_coverage": float(usable.mean()),
                "long_base_rate": float(dataset.loc[usable, LONG_TARGET_COL].mean()),
                "short_base_rate": float(dataset.loc[usable, SHORT_TARGET_COL].mean()),
            },
            "feature_profile": profile,
            "feature_columns": features,
            "categorical_columns": categoricals,
            "context_mode": horizon_config.context_mode,
            "walk_forward": {
                "min_train_dates": horizon_config.min_train_dates,
                "val_dates": horizon_config.val_dates,
                "test_dates": horizon_config.test_dates,
                "step_dates": horizon_config.step_dates,
                "max_splits": horizon_config.max_splits,
            },
            "metrics": metrics,
        }
        (horizon_dir / "contract.json").write_text(
            json.dumps(horizon_contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        results[str(horizon)] = horizon_contract

    campaign = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment": "E2_dual_threshold_multi_horizon",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed",
        "serving_ready": False,
        "research_only": True,
        "horizons": normalized_horizons,
        "up_threshold": config.target_up_threshold,
        "down_threshold": config.target_down_threshold,
        "target_diagnostics": target_diagnostics,
        "results": results,
    }
    (campaign_dir / "campaign.json").write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (campaign_dir / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return campaign_dir, campaign


def _format_dual_campaign(path: Path, campaign: dict[str, Any]) -> str:
    lines = [
        f"E2 dual_threshold terminé: {path}",
        f"Seuils: LONG>={campaign['up_threshold']:+.2%} SHORT<={campaign['down_threshold']:+.2%}",
    ]
    for horizon in campaign["horizons"]:
        metrics = campaign["results"][str(horizon)]["metrics"]
        overall = metrics["overall"]
        lines.append(
            f"H{horizon}: folds={metrics['n_folds']} "
            f"AUC-L={overall['auc_long']:.4f} AUC-S={overall['auc_short']:.4f} "
            f"IC={overall['mean_daily_direction_ic']:+.4f} "
            f"LONG={overall['long_top_decile']['mean_signed_return']:+.2%} "
            f"SHORT={overall['short_bottom_decile']['mean_signed_return']:+.2%}"
        )
    lines.append("Serving désactivé: E2 reste une expérience OOS.")
    return "\n".join(lines)


def run_long_confirmation_experiment(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    config: SharedDirectionalConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Construit et entraîne le paquet figé E2-B LONG H3."""
    config = config or SharedDirectionalConfig(
        horizon=3, objective="classifier", target_mode="long_h3_confirmation",
        amplitude_weighting=False, context_mode="none",
    )
    if config.target_mode != "long_h3_confirmation" or config.horizon != 3:
        raise ValueError("E2-B exige target=long_h3_confirmation et horizon H3.")
    profile = load_profile(profile_path)
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    base_config = replace(config, horizon=20, target_mode="decile_direction", objective="classifier")
    oracle_pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=base_config,
    )
    forward_panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date, horizons=[3],
        sector_min_members=config.sector_min_members,
    )
    dataset = attach_dual_threshold_targets(
        oracle_pool, forward_panel, horizon=3,
        up_threshold=config.target_up_threshold,
        down_threshold=config.target_down_threshold,
    )
    run_id = f"shared-long-h3-confirm-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    artifact_dir = artifacts_root / run_id
    metrics = train_long_confirmation(dataset, features, categoricals, config, artifact_dir)
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment": "E2B_long_h3_nested_calibration",
        "source_oracle_batch_id": oracle_batch_id,
        "status": metrics["status"],
        "research_only": True,
        "serving_ready": False,
        "confirmation_ready": True,
        "target_contract": {
            "horizon_sessions": 3,
            "long_label": f"adjusted_return >= {config.target_up_threshold}",
            "up_threshold": config.target_up_threshold,
            "down_threshold": config.target_down_threshold,
            "selection_fractions": [0.05, 0.10, 0.20],
            "primary_policy": "top_10_pct_daily",
            "short_enabled": False,
            "oracle_score_is_feature": False,
            "sector_min_members": config.sector_min_members,
        },
        "population": population,
        "target_diagnostics": target_diagnostics,
        "feature_profile": profile,
        "feature_columns": features,
        "categorical_columns": categoricals,
        "context_mode": config.context_mode,
        "conditioning": {
            "pool_pct": config.pool_pct,
            "oof_gate_path": str(gate_path),
        },
        "metrics": metrics,
    }
    (artifact_dir / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (artifact_dir / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return artifact_dir, contract


def run_long_untouched_confirmation(
    engine: Any,
    artifact_dir: Path,
    *,
    start_date: str,
    end_date: str,
) -> tuple[Path, dict[str, Any]]:
    """Score une période postérieure au calibrateur avec l'Oracle persisté."""
    artifact_dir = Path(artifact_dir)
    contract_path = artifact_dir / "contract.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Contrat E2-B introuvable: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("experiment") != "E2B_long_h3_nested_calibration":
        raise ValueError("L'artefact fourni n'est pas un paquet E2-B.")
    calibration_end = pd.Timestamp(contract["metrics"]["final_training"]["calibration_end"])
    if pd.Timestamp(start_date) <= calibration_end:
        raise ValueError("La confirmation doit commencer après la période de calibration.")
    oracle_batch_id = str(contract["source_oracle_batch_id"])
    pool_pct = float(contract["conditioning"]["pool_pct"])
    up_threshold = float(contract["target_contract"].get("up_threshold", 0.03))
    down_threshold = float(contract["target_contract"].get("down_threshold", -0.03))
    sector_min_members = int(contract["target_contract"].get("sector_min_members", 5))
    profile = dict(contract["feature_profile"])
    features = list(contract["feature_columns"])
    categoricals = list(contract.get("categorical_columns") or [])

    from catboost import CatBoostClassifier
    from modelFactory.oracle.extreme_gate import compute_extreme_gate
    from modelFactory.oracle.predictions_store import load_oracle_predictions
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    oracle_predictions = load_oracle_predictions(
        engine, batch_id=oracle_batch_id, start_date=start_date, end_date=end_date,
    )
    if oracle_predictions.empty:
        raise ValueError("Aucune prédiction Oracle persistée sur la confirmation.")
    oracle_predictions = compute_extreme_gate(oracle_predictions, pool_pct=pool_pct)
    oracle_gate = oracle_predictions.loc[
        oracle_predictions["extreme_gate"], ["date", "symbol", "extreme_pct"]
    ].rename(columns={"extreme_pct": ORACLE_GATE_SCORE_COL})
    oracle_gate["date"] = pd.to_datetime(oracle_gate["date"]).dt.normalize()
    oracle_gate["symbol"] = oracle_gate["symbol"].astype(str).str.upper()

    frame, resolved_features = build_oracle_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, horizon=20,
        require_global_rank=False, need_targets=False,
        feature_whitelist=features,
        generator_options=dict(profile.get("generator_options") or {}),
    )
    if resolved_features != features:
        raise ValueError("Le contrat de features E2-B n'est pas reproduit exactement.")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    requested = frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    frame = frame.loc[requested].merge(
        oracle_gate, on=["date", "symbol"], how="inner", validate="one_to_one",
    )
    if frame.empty:
        raise ValueError("Aucun événement Oracle TOP20 avec features sur la confirmation.")
    frame[SYMBOL_COL] = frame["symbol"].astype(str)
    if SECTOR_COL in categoricals:
        raw_sector = _load_sector_mapping(engine) or {}
        sector_map = {
            str(symbol).upper(): _map_to_gics_sector(str(sector))
            for symbol, sector in raw_sector.items() if sector is not None
        }
        frame[SECTOR_COL] = frame["symbol"].map(sector_map).fillna("UNKNOWN")

    forward_panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date, horizons=[3],
        sector_min_members=sector_min_members,
    )
    frame = attach_dual_threshold_targets(
        frame, forward_panel, horizon=3, up_threshold=up_threshold, down_threshold=down_threshold,
    ).dropna(subset=[LONG_TARGET_COL])
    model = CatBoostClassifier()
    model.load_model(str(artifact_dir / "long_h3_model.cbm"))
    raw_probability = model.predict_proba(_prepare_X(frame, features, categoricals))[:, 1]
    calibrator_state = json.loads((artifact_dir / "long_h3_platt.json").read_text(encoding="utf-8"))
    calibrator = PlattCalibrator.from_state_dict(calibrator_state)
    frame[RAW_LONG_PROBA_COL] = raw_probability
    frame[CAL_LONG_PROBA_COL] = apply_platt(calibrator, raw_probability)
    metrics = evaluate_long_confirmation(frame)
    top10 = metrics["selections"]["top_10_pct"]["model"]
    confirmation_gates = {
        "auc_gte_0_53": bool(metrics["auc_raw"] >= 0.53),
        "top10_precision_lift_gte_0_02": bool(top10["precision_lift_vs_matched"] >= 0.02),
        "top10_return_lift_gte_0_0025": bool(top10["return_lift_vs_matched"] >= 0.0025),
        "calibrated_brier_better_than_constant": bool(
            metrics["brier_calibrated"] < metrics["brier_constant"]
        ),
    }
    confirmation_id = f"confirmation-{pd.Timestamp(start_date):%Y%m%d}-{pd.Timestamp(end_date):%Y%m%d}"
    output_dir = artifact_dir / confirmation_id
    output_dir.mkdir(parents=True, exist_ok=False)
    predictions_path = output_dir / "predictions.parquet"
    frame[[
        "date", "symbol", "future_return", LONG_TARGET_COL, ORACLE_GATE_SCORE_COL,
        RAW_LONG_PROBA_COL, CAL_LONG_PROBA_COL,
    ]].to_parquet(predictions_path, index=False)
    result = {
        "schema_version": 1,
        "experiment": "E2B_untouched_confirmation",
        "source_artifact": str(artifact_dir),
        "source_oracle_batch_id": oracle_batch_id,
        "start_date": start_date,
        "end_date": end_date,
        "strictly_after_calibration": True,
        "target_diagnostics": target_diagnostics,
        "metrics": metrics,
        "confirmation_gates": confirmation_gates,
        "confirmation_gates_passed": bool(all(confirmation_gates.values())),
        "development_gates_passed": bool(contract["metrics"].get("development_gates_passed", False)),
        "promotion_ready": bool(
            all(confirmation_gates.values())
            and contract["metrics"].get("development_gates_passed", False)
        ),
        "predictions_path": str(predictions_path),
    }
    (output_dir / "confirmation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output_dir, result


def _format_long_confirmation(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    overall = metrics["overall"]
    top10 = overall["selections"]["top_10_pct"]["model"]
    return "\n".join([
        f"E2-B LONG H3 terminé: {path}",
        f"AUC moyenne folds={metrics['fold_stability']['auc_mean']:.4f} ",
        f"Top10 lift précision={top10['precision_lift_vs_matched']:+.2%} ",
        f"Top10 lift rendement={top10['return_lift_vs_matched']:+.2%} ",
        f"Brier calibré={overall['brier_calibrated']:.4f} baseline={overall['brier_constant']:.4f}",
        f"Gates développement={metrics['development_gates_passed']}",
        "Étape suivante: confirmation strictement postérieure, sans réentraînement.",
    ])


def _format_untouched_confirmation(path: Path, result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    top10 = metrics["selections"]["top_10_pct"]["model"]
    return "\n".join([
        f"Confirmation E2-B terminée: {path}",
        f"AUC={metrics['auc_raw']:.4f}",
        f"Top10 précision={top10['precision']:.2%} lift={top10['precision_lift_vs_matched']:+.2%}",
        f"Top10 rendement={top10['mean_return']:+.2%} lift={top10['return_lift_vs_matched']:+.2%}",
        f"Gates confirmation={result['confirmation_gates_passed']}",
        f"Promotion prête={result['promotion_ready']}",
    ])


def _format_summary(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    overall = metrics["overall"]
    long = overall["long_top_decile"]
    short = overall["short_bottom_decile"]
    population = contract["population"]
    return "\n".join([
        f"SharedDirectional terminé: {path}",
        f"Population Oracle OOF: {population['rows_oracle_pool']} lignes, "
        f"{population['symbols']} symboles, {population['dates']} dates",
        f"Folds valides: {metrics['n_folds']}",
        f"AUC D10/D1: {overall['auc_d10_vs_d1']:.4f}",
        f"IC directionnel quotidien: {overall['mean_daily_direction_ic']:+.4f}",
        f"TOP LONG: D10={long['target_decile_precision']:.2%} "
        f"D1={long['opposite_decile_contamination']:.2%} ret={long['mean_signed_return']:+.2%}",
        f"TOP SHORT: D1={short['target_decile_precision']:.2%} "
        f"D10={short['opposite_decile_contamination']:.2%} ret={short['mean_signed_return']:+.2%}",
        "Serving désactivé: promotion uniquement après validation des gates OOS.",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Direction mutualisée sur événements Oracle OOF.")
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--target", choices=[
            "decile_direction", "signed_return", "dual_threshold", "long_h3_confirmation",
        ],
        default="decile_direction",
    )
    parser.add_argument("--horizons", default="3,5,10,20")
    parser.add_argument("--return-residualization", choices=["raw", "spy", "spy_sector"], default="spy_sector")
    parser.add_argument("--sector-min-members", type=int, default=5)
    parser.add_argument("--target-winsor-lower", type=float, default=0.01)
    parser.add_argument("--target-winsor-upper", type=float, default=0.99)
    parser.add_argument("--target-up-threshold", type=float, default=0.03)
    parser.add_argument("--target-down-threshold", type=float, default=-0.03)
    parser.add_argument("--calibration-max-iter", type=int, default=100)
    parser.add_argument("--confirmation-artifact", type=Path, default=None)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--context-mode", choices=["symbol_sector", "sector", "none"], default="symbol_sector")
    parser.add_argument("--no-amplitude-weighting", action="store_true", default=False)
    parser.add_argument("--objective", choices=["classifier", "pairwise_ranker"], default="classifier")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    objective = {
        "signed_return": "regressor",
        "dual_threshold": "dual_classifier",
    }.get(args.target, args.objective)
    cfg = SharedDirectionalConfig(
        horizon=3 if args.target == "long_h3_confirmation" else 20,
        min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size,
        test_dates=args.wf_test_size,
        step_dates=args.wf_step_size,
        max_splits=args.wf_max_splits,
        iterations=args.iterations,
        depth=args.depth,
        learning_rate=args.learning_rate,
        context_mode=args.context_mode,
        amplitude_weighting=(not args.no_amplitude_weighting) and args.target != "signed_return",
        objective=objective,
        target_mode=args.target,
        residualization=args.return_residualization,
        sector_min_members=args.sector_min_members,
        target_winsor_lower=args.target_winsor_lower,
        target_winsor_upper=args.target_winsor_upper,
        target_up_threshold=args.target_up_threshold,
        target_down_threshold=args.target_down_threshold,
        calibration_max_iter=args.calibration_max_iter,
    )
    engine = get_sqlalchemy_engine()
    if args.target == "long_h3_confirmation":
        if args.confirmation_artifact is not None:
            path, confirmation = run_long_untouched_confirmation(
                engine, args.confirmation_artifact,
                start_date=args.start_date, end_date=args.end_date,
            )
            print(_format_untouched_confirmation(path, confirmation))
        else:
            path, contract = run_long_confirmation_experiment(
                engine, args.oracle_batch_id,
                start_date=args.start_date, end_date=args.end_date,
                profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
                symbols_limit=args.symbols_limit, config=cfg,
            )
            print(_format_long_confirmation(path, contract))
    elif args.target in {"signed_return", "dual_threshold"}:
        try:
            horizons = [int(value.strip()) for value in str(args.horizons).split(",") if value.strip()]
        except ValueError as exc:
            raise ValueError("--horizons doit contenir des entiers séparés par des virgules.") from exc
        if args.target == "signed_return":
            path, campaign = run_signed_return_campaign(
                engine, args.oracle_batch_id,
                start_date=args.start_date, end_date=args.end_date, horizons=horizons,
                profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
                symbols_limit=args.symbols_limit, config=cfg,
            )
            print(_format_signed_campaign(path, campaign))
        else:
            path, campaign = run_dual_threshold_campaign(
                engine, args.oracle_batch_id,
                start_date=args.start_date, end_date=args.end_date, horizons=horizons,
                profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
                symbols_limit=args.symbols_limit, config=cfg,
            )
            print(_format_dual_campaign(path, campaign))
    else:
        path, contract = run_experiment(
            engine, args.oracle_batch_id,
            start_date=args.start_date, end_date=args.end_date,
            profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
            symbols_limit=args.symbols_limit, config=cfg,
        )
        print(_format_summary(path, contract))


if __name__ == "__main__":
    main()
