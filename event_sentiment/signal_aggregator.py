"""
event_sentiment/signal_aggregator.py
=====================================
Fusion des scores de sentiment (pipeline FinBERT) avec les scores quantitatifs
du screener/selector (table stock_scores).

Contexte : le pipeline EventSentimentPipeline produit deux types de features :
  - ticker_daily_features  : sentiment_net_mean_1d, news_count_1d, major_event_flag, … par (symbol, trade_date)
  - sector_daily_features  : sector_impact_score, macro_event_intensity, … par (sector, trade_date)

Ces scores n'étaient JAMAIS consommés par AlphaScanner. Ce module crée la jonction.

Architecture :
  AlphaScanner.run()                         EventSentimentPipeline.run()
       │                                              │
       ▼                                              ▼
  stock_scores (DB)                    ticker_daily_features (DB)
       │                               sector_daily_features (DB)
       └──────────── SentimentSignalAggregator.merge() ─────────────┐
                                                                     ▼
                                                        final_score ajusté (sentiment boost)

Usage typique :
    from event_sentiment.signal_aggregator import SentimentSignalAggregator, SentimentBoostConfig
    from sqlalchemy.engine import Engine

    config = SentimentBoostConfig(sentiment_weight=0.15, macro_sector_weight=0.10)
    agg = SentimentSignalAggregator(engine, config)
    adjusted_scores = agg.merge(scores_df, trade_date=date.today())
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, cast
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.utils import configure_root_logging
from core.conviction import SentimentFusionWeights, fuse_sentiment
from core.run_summary import attach_live_progress
from database.run_business_summaries import persist_run_business_summary
from event_sentiment.config import EventSentimentConfig

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
STEP_KEY = "event_sentiment_signal_aggregator"

#: Répertoire des verrous d'idempotence (audit S1 / A-022).
#: Une exécution réussie de signal_aggregator pour un trade_date donné
#: dépose un fichier ``{trade_date}.lock`` ; un re-lancement le même jour
#: sur le même périmètre (--all-symbols ou non) est rejeté en sortie 0
#: avec un WARNING, sauf si --allow-rerun est passé.
SIGNAL_AGGREGATOR_LOCK_DIR_ENV = "SIGNAL_AGGREGATOR_LOCK_DIR"
SIGNAL_AGGREGATOR_LOCK_DEFAULT = Path("artifacts") / "signal_aggregator_runs"


def _resolve_lock_dir() -> Path:
    raw = os.environ.get(SIGNAL_AGGREGATOR_LOCK_DIR_ENV)
    return Path(raw) if raw else SIGNAL_AGGREGATOR_LOCK_DEFAULT


def _lock_path(trade_date: date, all_symbols: bool) -> Path:
    scope = "all" if all_symbols else "scored"
    return _resolve_lock_dir() / f"{trade_date.isoformat()}_{scope}.lock"


def _is_already_run(trade_date: date, all_symbols: bool) -> bool:
    return _lock_path(trade_date, all_symbols).exists()


def _mark_run_done(trade_date: date, all_symbols: bool) -> None:
    lock = _lock_path(trade_date, all_symbols)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(
            {
                "trade_date": trade_date.isoformat(),
                "all_symbols": all_symbols,
                "completed_at": _utc_now_naive().isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    if not bool(summary.get("progress_live")):
        try:
            persist_run_business_summary(
                summary=summary,
                step_key=STEP_KEY,
                run_kind="step",
                status=str(summary.get("status", "") or "") or None,
                summary_run_id=str(summary.get("run_id", "") or "") or None,
                entity_run_id=str(summary.get("run_id", "") or "") or None,
                trade_date=summary.get("trade_date"),
                started_at=summary.get("started_at"),
                finished_at=summary.get("finished_at"),
            )
        except Exception:
            LOGGER.debug("Persistance run_summaries indisponible pour event_sentiment.", exc_info=True)
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _is_missing_scalar(value: object) -> bool:
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, (float, np.floating)):
        return bool(np.isnan(float(value)))
    if isinstance(value, pd.Timestamp):
        return bool(pd.isna(value))
    return False


def _scalar_float(value: object, default: float = 0.0) -> float:
    if _is_missing_scalar(value):
        return default
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        as_float = float(value)
        return default if not np.isfinite(as_float) else as_float
    try:
        as_float = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return default if not np.isfinite(as_float) else as_float


def _scalar_int(value: object, default: int = 0) -> int:
    if _is_missing_scalar(value):
        return default
    return int(_scalar_float(value, default=float(default)))


def _scalar_bool(value: object, default: bool = False) -> bool:
    return default if _is_missing_scalar(value) else bool(value)


def _parse_timestamp(value: object) -> pd.Timestamp | None:
    if _is_missing_scalar(value):
        return None
    if isinstance(value, pd.Timestamp):
        return None if bool(pd.isna(value)) else value
    if isinstance(value, (datetime, date)):
        return pd.Timestamp(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = pd.Timestamp(raw)
        except (TypeError, ValueError):
            return None
        return None if bool(pd.isna(parsed)) else parsed
    return None


def _age_days_from_reference(value: object, *, reference_date: date) -> int:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return 0
    return max((pd.Timestamp(reference_date).normalize() - parsed.normalize()).days, 0)


def _read_sql_query_dataframe(statement: object, connection: object, *, params: dict[str, Any]) -> pd.DataFrame:
    return cast(pd.DataFrame, pd.read_sql_query(statement, connection, params=cast(Any, params)))


def _get_checkpoint_order_guard_status(
    repository: object,
    *,
    source_name: str,
    symbols: list[str],
) -> dict[str, object]:
    getter = getattr(repository, "get_signal_aggregator_guard_status", None)
    if not callable(getter):
        return {
            "source_name": source_name,
            "scoped_symbols": len(symbols),
            "checkpoint_rows": 0,
            "symbols_with_news": 0,
            "ready": True,
        }
    try:
        raw_status = getter(source_name=source_name, symbols=symbols) or {}
    except Exception as exc:  # noqa: BLE001 - compat schéma/tests partiels
        LOGGER.warning(
            "Guard status checkpoint indisponible ; fallback permissif | source_name=%s symbols=%s error=%s",
            source_name,
            len(symbols),
            exc,
        )
        return {
            "source_name": source_name,
            "scoped_symbols": len(symbols),
            "checkpoint_rows": 0,
            "symbols_with_news": 0,
            "ready": True,
            "guard_available": False,
            "guard_error": str(exc),
        }
    if isinstance(raw_status, dict):
        status_items = raw_status.items()
    elif hasattr(raw_status, "items"):
        status_items = cast(Any, raw_status).items()
    else:
        status_items = []
    return {str(key): value for key, value in status_items}


def _enforce_checkpoint_order_guard(
    repository: object,
    *,
    source_name: str,
    symbols: list[str],
) -> dict[str, object]:
    status = _get_checkpoint_order_guard_status(
        repository,
        source_name=source_name,
        symbols=symbols,
    )
    if bool(status.get("ready", True)):
        return status
    stale_relevance = status.get("stale_relevance_symbols") or []
    stale_contextual = status.get("stale_contextual_symbols") or []
    stale_features = status.get("stale_feature_symbols") or []
    raise RuntimeError(
        "Ordre `event_sentiment` invalide avant `signal_aggregator` : "
        f"relevance_backfill<{source_name}.news_ingested pour {len(stale_relevance)} symbole(s), "
        f"contextual_scoring obsolète pour {len(stale_contextual)} symbole(s), "
        f"features_aggregated obsolète pour {len(stale_features)} symbole(s)."
    )


def _build_cli_run_summary(
    *,
    config: "SentimentBoostConfig",
    trade_date: date,
    all_symbols: bool,
    loaded_symbols: int,
    updated_symbols: int,
    enriched: pd.DataFrame,
    started_at: datetime,
    finished_at: datetime,
    finbert_fingerprints: list[str] | None = None,
) -> dict[str, object]:
    signal_active_symbols = 0
    total_news = 0
    avg_final_score_sentiment = None
    max_final_score_sentiment = None
    if not enriched.empty:
        if "signal_active" in enriched.columns:
            signal_active_symbols = int(enriched["signal_active"].fillna(False).astype(bool).sum())
        if "total_news" in enriched.columns:
            total_news_series = pd.Series(pd.to_numeric(enriched["total_news"], errors="coerce"), index=enriched.index)
            total_news = int(total_news_series.fillna(0).sum())
        if "final_score_sentiment" in enriched.columns:
            score_series = pd.Series(
                [_scalar_float(value, default=float("nan")) for value in enriched["final_score_sentiment"].tolist()],
                index=enriched.index,
                dtype=float,
            ).dropna()
            if not score_series.empty:
                avg_final_score_sentiment = round(_scalar_float(score_series.mean()), 4)
                max_final_score_sentiment = round(_scalar_float(score_series.max()), 4)

    return {
        "run_id": _build_run_id("signal-aggregator"),
        "trade_date": trade_date.isoformat(),
        "all_symbols": all_symbols,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "loaded_symbols": int(loaded_symbols),
        "updated_symbols": int(updated_symbols),
        "signal_active_symbols": signal_active_symbols,
        "total_news": total_news,
        "sentiment_weight": round(float(config.sentiment_weight), 4),
        "macro_sector_weight": round(float(config.macro_sector_weight), 4),
        "quant_weight": round(float(config.quant_weight), 4),
        "lookback_days": int(config.lookback_days),
        "min_news_count": int(config.min_news_count),
        "avg_final_score_sentiment": avg_final_score_sentiment,
        "max_final_score_sentiment": max_final_score_sentiment,
        "finbert_model_fingerprints": list(finbert_fingerprints or []),
    }


@dataclass(frozen=True, slots=True)
class SentimentBoostConfig:
    """
    Paramètres de fusion sentiment → score quantitatif.

    sentiment_weight     : fraction du final_score attribuée au signal de sentiment
                           ticker (sentiment_net_mean_1d normalisé). Défaut 0 %.
                           (IC ≈ 0.01, t-stat ≈ 1.1 — non significatif, désactivé
                           par défaut ; conservé dans la grille de calibration).
    macro_sector_weight  : fraction attribuée au signal macro sectoriel
                           (sector_impact_score normalisé). Défaut 0 %.
                           (IC ≈ 0, t-stat ≈ 0 — désactivé car aucun pouvoir
                           prédictif mesuré sur capital_2001_5000, 2020-2025).
    quant_weight         : fraction conservée pour le score quantitatif originel.
                           Défaut 100 %. La somme des trois doit être 1.0.
    lookback_days              : fenêtre en jours pour la moyenne glissante du sentiment
                                 (robustesse au bruit d'un seul article). Défaut 5 jours.
    min_news_count             : nb minimal d'articles pour activer le boost sentiment
                                 (évite les signaux sur 1 seul article). Défaut 2.
    time_decay_half_life_days  : demi-vie (en jours) de la décroissance exponentielle
                                 appliquée aux jours anciens dans la fenêtre. Défaut 2 jours.

    Validation : sentiment_weight + macro_sector_weight + quant_weight doit ≈ 1.0.
    Pour calibrer les poids, calculer IC (Information Coefficient) sentiment → retour
    J+1/J+5 sur historique via backtest.
    """
    sentiment_weight: float = 0.00
    macro_sector_weight: float = 0.00
    quant_weight: float = 1.00
    lookback_days: int = 5
    min_news_count: int = 2
    time_decay_half_life_days: float = 2.0
    ticker_horizon_weights: tuple[tuple[int, float], ...] = ((1, 0.35), (3, 0.25), (5, 0.20), (10, 0.10), (20, 0.10))
    sector_horizon_weights: tuple[tuple[int, float], ...] = ((1, 0.40), (3, 0.25), (5, 0.20), (10, 0.10), (20, 0.05))

    def __post_init__(self) -> None:
        total = self.sentiment_weight + self.macro_sector_weight + self.quant_weight
        if not np.isclose(total, 1.0, atol=1e-4):
            raise ValueError(
                f"sentiment_weight + macro_sector_weight + quant_weight doit être égal à 1.0 "
                f"(actuel : {total:.4f})."
            )
        if self.lookback_days < 1:
            raise ValueError("lookback_days doit être >= 1.")
        if self.min_news_count < 1:
            raise ValueError("min_news_count doit être >= 1.")
        if self.time_decay_half_life_days <= 0:
            raise ValueError("time_decay_half_life_days doit être > 0.")
        self._validate_horizon_weights("ticker_horizon_weights", self.ticker_horizon_weights)
        self._validate_horizon_weights("sector_horizon_weights", self.sector_horizon_weights)

    @staticmethod
    def _validate_horizon_weights(name: str, weights: tuple[tuple[int, float], ...]) -> None:
        if not weights:
            raise ValueError(f"{name} ne doit pas être vide.")
        horizons = [int(horizon) for horizon, _ in weights]
        if any(horizon < 1 for horizon in horizons):
            raise ValueError(f"{name} doit contenir des horizons >= 1.")
        if horizons != sorted(set(horizons)):
            raise ValueError(f"{name} doit être trié et sans doublons.")
        if all(float(weight) <= 0 for _, weight in weights):
            raise ValueError(f"{name} doit contenir au moins un poids positif.")

    @classmethod
    def from_global_config(
        cls,
        config: dict | None = None,
        **overrides,
    ) -> "SentimentBoostConfig":
        """Sprint S8 — construit la config en lisant la section ``conviction:``.

        Si ``config`` est ``None``, on charge ``config.yaml`` via
        :func:`common.config_loader.load_config`. Les ``overrides`` (kwargs)
        priment sur les valeurs YAML, qui priment sur les défauts dataclass.

        Permet la calibration formelle des poids 75/15/10 (cf. plan §S8) sans
        toucher au code applicatif.
        """
        if config is None:
            try:
                from common.config_loader import load_config
                config = load_config() or {}
            except Exception:
                config = {}
        conviction_cfg = (config.get("conviction") or {}) if isinstance(config, dict) else {}
        kwargs: dict = {}
        if "quant_weight" in conviction_cfg:
            kwargs["quant_weight"] = float(conviction_cfg["quant_weight"])
        if "sentiment_weight" in conviction_cfg:
            kwargs["sentiment_weight"] = float(conviction_cfg["sentiment_weight"])
        if "macro_weight" in conviction_cfg:
            kwargs["macro_sector_weight"] = float(conviction_cfg["macro_weight"])
        # macro_sector_weight prime sur macro_weight si fourni explicitement
        if "macro_sector_weight" in conviction_cfg:
            kwargs["macro_sector_weight"] = float(conviction_cfg["macro_sector_weight"])
        kwargs.update(overrides)
        return cls(**kwargs)

    def to_fusion_weights(self) -> SentimentFusionWeights:
        """Convertit en :class:`core.conviction.SentimentFusionWeights`."""
        return SentimentFusionWeights(
            quant_weight=float(self.quant_weight),
            sentiment_weight=float(self.sentiment_weight),
            macro_weight=float(self.macro_sector_weight),
        )

    @staticmethod
    def _normalized_horizon_weights(weights: tuple[tuple[int, float], ...]) -> list[tuple[int, float]]:
        positive_weights = [(int(horizon), float(weight)) for horizon, weight in weights if float(weight) > 0]
        total = sum(weight for _, weight in positive_weights)
        return [(horizon, weight / total) for horizon, weight in positive_weights] if total > 0 else []


class SentimentSignalAggregator:
    """
    Fusionne les scores du screener (stock_scores) avec les features de sentiment
    (ticker_daily_features, sector_daily_features) pour produire un final_score ajusté.

    Le signal sentiment est additif et borné : il ne peut pas inverser un signal
    quantitatif fort — il amplifie ou atténue légèrement la conviction.
    """

    def __init__(self, engine: Engine, config: SentimentBoostConfig | None = None) -> None:
        self.engine = engine
        self.config = config or SentimentBoostConfig()
        self.progress_callback: Callable[[dict[str, object]], None] | None = None

    def _emit_progress(
        self,
        summary: dict[str, object],
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        item: str | None = None,
        unit: str = "étapes",
    ) -> None:
        if not callable(self.progress_callback):
            return
        self.progress_callback(
            attach_live_progress(
                summary,
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit=unit,
                item=item,
            )
        )

    def _feature_fetch_window_days(self, horizon_weights: tuple[tuple[int, float], ...]) -> int:
        max_horizon = max((int(horizon) for horizon, _ in horizon_weights), default=1)
        return max(int(self.config.lookback_days), max_horizon)

    # ------------------------------------------------------------------
    # Chargement depuis la DB
    # ------------------------------------------------------------------

    def _load_ticker_sentiment(self, symbols: list[str], trade_date: date) -> pd.DataFrame:
        """Charge les features de sentiment ticker pour les N derniers jours."""
        if not symbols:
            return pd.DataFrame()

        cutoff = pd.Timestamp(trade_date) - pd.Timedelta(days=self._feature_fetch_window_days(self.config.ticker_horizon_weights))
        stmt = text(
            """
            SELECT symbol,
                   trade_date,
                   news_count_1d,
                   sentiment_net_mean_1d,
                   sentiment_confidence_mean_1d,
                   major_event_flag
            FROM ticker_daily_sentiment_features
            WHERE symbol IN :symbols
              AND trade_date >= :cutoff
              AND trade_date <= :trade_date
            ORDER BY symbol, trade_date
            """
        ).bindparams(symbols=symbols, cutoff=cutoff.date(), trade_date=trade_date)

        try:
            from sqlalchemy import bindparam
            stmt = text(
                """
                SELECT symbol,
                       trade_date,
                       news_count_1d,
                       news_count_3d,
                       news_count_5d,
                       news_count_10d,
                       news_count_20d,
                       sentiment_net_mean_1d,
                       sentiment_confidence_mean_1d,
                       sentiment_net_mean_3d,
                       sentiment_net_mean_5d,
                       sentiment_net_mean_10d,
                       sentiment_net_mean_20d,
                       sentiment_confidence_mean_3d,
                       sentiment_confidence_mean_5d,
                       sentiment_confidence_mean_10d,
                       sentiment_confidence_mean_20d,
                       major_event_flag,
                       major_event_day_count_3d,
                       major_event_day_count_5d,
                       major_event_day_count_10d,
                       major_event_day_count_20d
                FROM ticker_daily_sentiment_features
                WHERE symbol IN :symbols
                  AND trade_date >= :cutoff
                  AND trade_date <= :trade_date
                ORDER BY symbol, trade_date
                """
            ).bindparams(bindparam("symbols", expanding=True))
            with self.engine.connect() as conn:
                return _read_sql_query_dataframe(
                    stmt,
                    conn,
                    params={"symbols": list(symbols), "cutoff": cutoff.date(), "trade_date": trade_date},
                )
        except Exception:
            LOGGER.warning("ticker_daily_sentiment_features indisponible — boost sentiment desactive.")
            return pd.DataFrame()

    def _load_sector_sentiment(self, sectors: list[str], trade_date: date) -> pd.DataFrame:
        """Charge les features macro sectorielles pour les N derniers jours."""
        if not sectors:
            return pd.DataFrame()

        cutoff = pd.Timestamp(trade_date) - pd.Timedelta(days=self._feature_fetch_window_days(self.config.sector_horizon_weights))
        try:
            from sqlalchemy import bindparam
            stmt = text(
                """
                SELECT sector,
                       trade_date,
                       sector_impact_score,
                       macro_event_intensity,
                       macro_event_flag,
                       sector_impact_score_3d,
                       sector_impact_score_5d,
                       sector_impact_score_10d,
                       sector_impact_score_20d,
                       macro_event_intensity_3d,
                       macro_event_intensity_5d,
                       macro_event_intensity_10d,
                       macro_event_intensity_20d,
                       macro_event_day_count_3d,
                       macro_event_day_count_5d,
                       macro_event_day_count_10d,
                       macro_event_day_count_20d
                FROM sector_daily_sentiment_features
                WHERE sector IN :sectors
                  AND trade_date >= :cutoff
                  AND trade_date <= :trade_date
                ORDER BY sector, trade_date
                """
            ).bindparams(bindparam("sectors", expanding=True))
            with self.engine.connect() as conn:
                return _read_sql_query_dataframe(
                    stmt,
                    conn,
                    params={"sectors": list(sectors), "cutoff": cutoff.date(), "trade_date": trade_date},
                )
        except Exception:
            LOGGER.warning("sector_daily_sentiment_features indisponible — boost macro desactive.")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Agrégation + normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_time_decay_weight(
        trade_dates: pd.Series,
        reference_date: date,
        half_life_days: float,
    ) -> pd.Series:
        """
        Calcule un poids de décroissance exponentielle par date.

        Poids = 0.5 ** (age_jours / half_life_days)
        → le poids est divisé par 2 tous les `half_life_days` jours.
        """
        reference_ts = pd.Timestamp(reference_date).normalize()
        weights: list[float] = []
        for raw_value in trade_dates.tolist():
            parsed = _parse_timestamp(raw_value)
            if parsed is None:
                age_days = 0
            else:
                normalized = parsed.normalize()
                age_days = max((reference_ts - normalized).days, 0)
            weights.append(float(np.power(0.5, age_days / half_life_days)))
        return pd.Series(weights, index=trade_dates.index, dtype=float)

    @staticmethod
    def _aggregate_ticker_window(
        ticker_df: pd.DataFrame,
        min_news_count: int,
        reference_date: date,
        half_life_days: float,
    ) -> pd.DataFrame:
        """
        Agrège les N derniers jours de sentiment par symbole.
        Pondère par news_count et par récence pour donner plus de poids aux jours
        récents et aux jours avec plus d'articles.
        Retourne : [symbol, sentiment_net_agg, major_event_flag_agg, total_news]
        """
        if ticker_df.empty:
            return pd.DataFrame(columns=["symbol", "sentiment_net_agg", "major_event_flag_agg", "total_news"])

        records = ticker_df.to_dict(orient="records")
        trade_dates = pd.Series([record.get("trade_date") for record in records], dtype="object")
        time_weights = SentimentSignalAggregator._compute_time_decay_weight(
            trade_dates,
            reference_date=reference_date,
            half_life_days=half_life_days,
        ).tolist()

        grouped: dict[str, list[dict[str, float | int]]] = {}
        for record, time_weight in zip(records, time_weights, strict=False):
            symbol = str(record.get("symbol", ""))
            if not symbol:
                continue
            news_count = float(record.get("news_count_1d") or 0.0)
            sentiment_net = float(record.get("sentiment_net_mean_1d") or 0.0)
            major_event_flag = int(record.get("major_event_flag") or 0)
            grouped.setdefault(symbol, []).append(
                {
                    "news_count_1d": news_count,
                    "sentiment_net_mean_1d": sentiment_net,
                    "major_event_flag": major_event_flag,
                    "time_decay_weight": float(time_weight),
                }
            )

        rows: list[dict[str, object]] = []
        for symbol, group in grouped.items():
            total_news = sum(float(item["news_count_1d"]) for item in group)
            if total_news < min_news_count:
                rows.append(
                    {
                        "symbol": symbol,
                        "sentiment_net_agg": 0.0,
                        "major_event_flag_agg": 0,
                        "total_news": int(total_news),
                        "signal_active": False,
                    }
                )
                continue

            effective_weights = [float(item["news_count_1d"]) * float(item["time_decay_weight"]) for item in group]
            weight_sum = sum(effective_weights)
            if weight_sum <= 0:
                effective_weights = [float(item["news_count_1d"]) for item in group]
                weight_sum = sum(effective_weights)

            weighted_net = sum(
                float(item["sentiment_net_mean_1d"]) * (weight / weight_sum)
                for item, weight in zip(group, effective_weights, strict=False)
            ) if weight_sum > 0 else 0.0
            rows.append(
                {
                    "symbol": symbol,
                    "sentiment_net_agg": float(weighted_net),
                    "major_event_flag_agg": max(int(item["major_event_flag"]) for item in group),
                    "total_news": int(total_news),
                    "signal_active": True,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _aggregate_sector_window(
        sector_df: pd.DataFrame,
        reference_date: date,
        half_life_days: float,
    ) -> pd.DataFrame:
        """
        Agrège les N derniers jours d'impact macro par secteur.
        La moyenne est pondérée par récence pour atténuer les impacts anciens.
        Retourne : [sector, sector_impact_agg, macro_event_flag_agg]
        """
        if sector_df.empty:
            return pd.DataFrame(columns=["sector", "sector_impact_agg", "macro_event_flag_agg"])

        records = sector_df.to_dict(orient="records")
        trade_dates = pd.Series([record.get("trade_date") for record in records], dtype="object")
        time_weights = SentimentSignalAggregator._compute_time_decay_weight(
            trade_dates,
            reference_date=reference_date,
            half_life_days=half_life_days,
        ).tolist()

        grouped: dict[str, list[dict[str, float | int]]] = {}
        for record, time_weight in zip(records, time_weights, strict=False):
            sector = str(record.get("sector", ""))
            if not sector:
                continue
            grouped.setdefault(sector, []).append(
                {
                    "sector_impact_score": float(record.get("sector_impact_score") or 0.0),
                    "macro_event_flag": int(record.get("macro_event_flag") or 0),
                    "time_decay_weight": float(time_weight),
                }
            )

        rows: list[dict[str, object]] = []
        for sector, group in grouped.items():
            weights = [float(item["time_decay_weight"]) for item in group]
            weight_sum = sum(weights)
            if weight_sum <= 0:
                weights = [1.0 for _ in group]
                weight_sum = float(len(group))
            weighted_impact = sum(
                float(item["sector_impact_score"]) * (weight / weight_sum)
                for item, weight in zip(group, weights, strict=False)
            ) if weight_sum > 0 else 0.0
            rows.append(
                {
                    "sector": sector,
                    "sector_impact_agg": float(weighted_impact),
                    "macro_event_flag_agg": max(int(item["macro_event_flag"]) for item in group),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _normalize_to_01(series: pd.Series) -> pd.Series:
        """Normalisation min-max avec winsorisation 1%-99%."""
        def _percentile(values: list[float], q: float) -> float:
            ordered = sorted(values)
            if len(ordered) == 1:
                return ordered[0]
            position = (len(ordered) - 1) * q
            lower_index = int(position)
            upper_index = min(lower_index + 1, len(ordered) - 1)
            if lower_index == upper_index:
                return ordered[lower_index]
            fraction = position - lower_index
            return ordered[lower_index] + ((ordered[upper_index] - ordered[lower_index]) * fraction)

        numeric_values: list[float] = []
        valid_values: list[float] = []
        for value in series.tolist():
            as_float = _scalar_float(value, default=float("nan"))
            if np.isnan(as_float):
                numeric_values.append(float("nan"))
            else:
                numeric_values.append(as_float)
                valid_values.append(as_float)

        if not valid_values:
            return pd.Series([0.5] * len(numeric_values), index=series.index, dtype=float)

        lo = _percentile(valid_values, 0.01)
        hi = _percentile(valid_values, 0.99)
        if np.isclose(hi, lo):
            return pd.Series([0.5] * len(numeric_values), index=series.index, dtype=float)

        normalized: list[float] = []
        for value in numeric_values:
            if np.isnan(value):
                normalized.append(0.5)
                continue
            clipped = min(max(value, lo), hi)
            normalized.append(min(max((clipped - lo) / (hi - lo), 0.0), 1.0))

        return pd.Series(normalized, index=series.index, dtype=float)

    @staticmethod
    def _normalize_identifier(value: object) -> str | None:
        if _is_missing_scalar(value):
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _normalize_signed_signal(series: pd.Series) -> pd.Series:
        numeric = pd.Series(pd.to_numeric(series, errors="coerce"), index=series.index, dtype=float)
        numeric = numeric.where(np.isfinite(numeric), np.nan)
        clipped = numeric.clip(-1.0, 1.0).fillna(0.0)
        return ((clipped + 1.0) / 2.0).astype(float)

    @staticmethod
    def _numeric_value(value: object, default: float = 0.0) -> float:
        return _scalar_float(value, default=default)

    @classmethod
    def _compute_staleness_weight(
        cls,
        trade_date_value: object,
        *,
        reference_date: date,
        half_life_days: float,
    ) -> float:
        series = pd.Series([trade_date_value], dtype="object")
        return float(
            cls._compute_time_decay_weight(
                series,
                reference_date=reference_date,
                half_life_days=half_life_days,
            ).iloc[0]
        )

    @staticmethod
    def _latest_rows_by_key(df: pd.DataFrame, key_column: str) -> pd.DataFrame:
        if df.empty or key_column not in df.columns or "trade_date" not in df.columns:
            return pd.DataFrame()
        ordered = df.copy()
        ordered["trade_date"] = pd.to_datetime(ordered["trade_date"], errors="coerce")
        ordered = ordered.dropna(subset=[key_column, "trade_date"]).sort_values([key_column, "trade_date"])
        if ordered.empty:
            return pd.DataFrame()
        return ordered.groupby(key_column, as_index=False).tail(1).reset_index(drop=True)

    @classmethod
    def _compose_horizon_signal(
        cls,
        row: dict[str, object],
        *,
        value_columns: dict[int, str],
        horizon_weights: tuple[tuple[int, float], ...],
        coverage_columns: dict[int, str] | None = None,
        coverage_cap: float = 1.0,
    ) -> float:
        weighted_sum = 0.0
        total_weight = 0.0
        for horizon, weight in SentimentBoostConfig._normalized_horizon_weights(horizon_weights):
            column_name = value_columns.get(horizon)
            if column_name is None or column_name not in row:
                continue
            signal_value = max(-1.0, min(1.0, cls._numeric_value(row.get(column_name), default=0.0)))
            coverage = 1.0
            if coverage_columns is not None:
                coverage_column = coverage_columns.get(horizon)
                coverage_raw = cls._numeric_value(row.get(coverage_column), default=0.0) if coverage_column else 0.0
                coverage = min(max(coverage_raw, 0.0), coverage_cap)
            effective_weight = weight * coverage
            if effective_weight <= 0:
                continue
            weighted_sum += signal_value * effective_weight
            total_weight += effective_weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _aggregate_ticker_multi_horizon(self, ticker_df: pd.DataFrame, reference_date: date) -> pd.DataFrame:
        if ticker_df.empty:
            return pd.DataFrame(columns=["symbol", "sentiment_net_agg", "major_event_flag_agg", "total_news", "signal_active", "signal_age_days", "signal_staleness_weight"])
        latest = self._latest_rows_by_key(ticker_df, "symbol")
        if latest.empty:
            return pd.DataFrame(columns=["symbol", "sentiment_net_agg", "major_event_flag_agg", "total_news", "signal_active", "signal_age_days", "signal_staleness_weight"])

        rows: list[dict[str, object]] = []
        count_columns = {1: "news_count_1d", 3: "news_count_3d", 5: "news_count_5d", 10: "news_count_10d", 20: "news_count_20d"}
        major_columns = [
            "major_event_flag",
            "major_event_day_count_3d",
            "major_event_day_count_5d",
            "major_event_day_count_10d",
            "major_event_day_count_20d",
        ]
        for row in latest.to_dict(orient="records"):
            typed_row = cast(dict[str, object], row)
            trade_date_value = typed_row.get("trade_date")
            staleness_weight = self._compute_staleness_weight(
                trade_date_value,
                reference_date=reference_date,
                half_life_days=self.config.time_decay_half_life_days,
            )
            signal_age_days = _age_days_from_reference(trade_date_value, reference_date=reference_date)
            available_count_columns = {
                horizon: column_name
                for horizon, column_name in count_columns.items()
                if column_name in typed_row
            }
            total_news = 0
            if available_count_columns:
                total_news = int(max(self._numeric_value(typed_row.get(column_name), default=0.0) for column_name in available_count_columns.values()))
            rows.append(
                {
                    "symbol": typed_row.get("symbol"),
                    "sentiment_net_agg": self._compose_horizon_signal(
                        typed_row,
                        value_columns={
                            1: "sentiment_net_mean_1d",
                            3: "sentiment_net_mean_3d",
                            5: "sentiment_net_mean_5d",
                            10: "sentiment_net_mean_10d",
                            20: "sentiment_net_mean_20d",
                        },
                        horizon_weights=self.config.ticker_horizon_weights,
                        coverage_columns=available_count_columns,
                        coverage_cap=float(max(self.config.min_news_count, 1)),
                    ) * staleness_weight,
                    "major_event_flag_agg": int(any(self._numeric_value(typed_row.get(column_name), default=0.0) > 0 for column_name in major_columns if column_name in typed_row)),
                    "total_news": total_news,
                    "signal_active": total_news >= self.config.min_news_count,
                    "signal_age_days": signal_age_days,
                    "signal_staleness_weight": staleness_weight,
                }
            )
        return pd.DataFrame(rows)

    def _aggregate_sector_multi_horizon(self, sector_df: pd.DataFrame, reference_date: date) -> pd.DataFrame:
        if sector_df.empty:
            return pd.DataFrame(columns=["sector", "sector_impact_agg", "macro_event_flag_agg", "macro_signal_age_days", "macro_signal_staleness_weight"])
        latest = self._latest_rows_by_key(sector_df, "sector")
        if latest.empty:
            return pd.DataFrame(columns=["sector", "sector_impact_agg", "macro_event_flag_agg", "macro_signal_age_days", "macro_signal_staleness_weight"])

        rows: list[dict[str, object]] = []
        macro_columns = [
            "macro_event_flag",
            "macro_event_day_count_3d",
            "macro_event_day_count_5d",
            "macro_event_day_count_10d",
            "macro_event_day_count_20d",
        ]
        for row in latest.to_dict(orient="records"):
            typed_row = cast(dict[str, object], row)
            trade_date_value = typed_row.get("trade_date")
            staleness_weight = self._compute_staleness_weight(
                trade_date_value,
                reference_date=reference_date,
                half_life_days=self.config.time_decay_half_life_days,
            )
            signal_age_days = _age_days_from_reference(trade_date_value, reference_date=reference_date)
            rows.append(
                {
                    "sector": typed_row.get("sector"),
                    "sector_impact_agg": self._compose_horizon_signal(
                        typed_row,
                        value_columns={
                            1: "sector_impact_score",
                            3: "sector_impact_score_3d",
                            5: "sector_impact_score_5d",
                            10: "sector_impact_score_10d",
                            20: "sector_impact_score_20d",
                        },
                        horizon_weights=self.config.sector_horizon_weights,
                    ) * staleness_weight,
                    "macro_event_flag_agg": int(any(self._numeric_value(typed_row.get(column_name), default=0.0) > 0 for column_name in macro_columns if column_name in typed_row)),
                    "macro_signal_age_days": signal_age_days,
                    "macro_signal_staleness_weight": staleness_weight,
                }
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    def merge(
        self,
        scores_df: pd.DataFrame,
        trade_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Fusionne les scores quantitatifs avec le signal de sentiment.

        :param scores_df: DataFrame issu de AlphaScanner.run() avec au minimum
                          [symbol, final_score, sector].
        :param trade_date: Date de référence (aujourd'hui si None).
        :return: DataFrame enrichi avec les colonnes :
                 - sentiment_net_agg       : sentiment moyen pondéré sur la fenêtre
                 - sector_impact_agg       : impact macro sectoriel moyen
                 - final_score             : score quantitatif AlphaScanner (inchangé)
                 - final_score_sentiment   : score fusionné quant + sentiment (nouveau champ)

        Sprint S8 — feature flag ``ALPHA_TRADE_DISABLE_SENTIMENT`` (CLI
        ``--disable-sentiment``) : si actif, on retourne le DataFrame avec
        ``final_score_sentiment = final_score`` (skip complet de la fusion,
        utile pour mesurer l'apport empirique du sentiment dans
        ``backtesting/attribution.py``).
        """
        if scores_df.empty:
            return scores_df.copy()

        from core.feature_flags import is_sentiment_disabled

        if is_sentiment_disabled():
            LOGGER.warning(
                "[signal_aggregator] feature flag ALPHA_TRADE_DISABLE_SENTIMENT actif → fusion sentiment SKIPPÉE"
            )
            disabled = scores_df.copy()
            if "symbol" in disabled.columns:
                disabled["symbol"] = [self._normalize_identifier(value) for value in disabled["symbol"].tolist()]
                disabled = disabled[disabled["symbol"].notna()].copy()
            final_score_series = (
                disabled["final_score"]
                if "final_score" in disabled.columns
                else pd.Series([0.0] * len(disabled), index=disabled.index, dtype=float)
            )
            quant = pd.Series(
                [_scalar_float(value) for value in final_score_series.tolist()],
                index=disabled.index,
                dtype=float,
            ).fillna(0.0).clip(0.0, 1.0)
            disabled["final_score"] = quant
            disabled["final_score_sentiment"] = quant
            disabled["sentiment_disabled"] = True
            return disabled

        required = {"symbol", "final_score"}
        missing = required - set(scores_df.columns)
        if missing:
            raise ValueError(f"merge : colonnes manquantes dans scores_df : {missing}.")

        ref_date = trade_date or date.today()
        result = scores_df.copy()

        result["symbol"] = [self._normalize_identifier(value) for value in result["symbol"].tolist()]
        result = result[result["symbol"].notna()].copy()
        if result.empty:
            return result

        if "sector" in result.columns:
            result["sector"] = [self._normalize_identifier(value) for value in result["sector"].tolist()]

        quant_scores = pd.Series([_scalar_float(value) for value in result["final_score"].tolist()], index=result.index, dtype=float)
        quant_scores = quant_scores.where(np.isfinite(quant_scores), np.nan).fillna(0.0).clip(0.0, 1.0)
        result["final_score"] = quant_scores

        symbols = sorted(set(result["symbol"].astype(str).tolist()))
        sectors = (
            sorted({sector for sector in result["sector"].dropna().astype(str).tolist() if sector})
            if "sector" in result.columns
            else []
        )

        # --- Chargement ---
        ticker_df = self._load_ticker_sentiment(symbols, ref_date)
        sector_df = self._load_sector_sentiment(sectors, ref_date) if sectors else pd.DataFrame()
        self._emit_progress(
            {
                "trade_date": ref_date.isoformat(),
                "loaded_symbols": len(symbols),
                "loaded_sectors": len(sectors),
                "ticker_feature_rows": int(len(ticker_df)),
                "sector_feature_rows": int(len(sector_df)),
            },
            current=1,
            total=2,
            label="🧠 Progression signal aggregator — chargement features sentiment",
            phase="load_features",
        )

        # --- Agrégation fenêtrée ---
        ticker_agg = self._aggregate_ticker_multi_horizon(ticker_df, reference_date=ref_date)
        if ticker_agg.empty:
            ticker_agg = self._aggregate_ticker_window(
                ticker_df,
                min_news_count=self.config.min_news_count,
                reference_date=ref_date,
                half_life_days=self.config.time_decay_half_life_days,
            )
        sector_agg = self._aggregate_sector_multi_horizon(sector_df, reference_date=ref_date)
        if sector_agg.empty:
            sector_agg = self._aggregate_sector_window(
                sector_df,
                reference_date=ref_date,
                half_life_days=self.config.time_decay_half_life_days,
            )

        LOGGER.info(
            "SentimentSignalAggregator | trade_date=%s symboles=%s ticker_signaux=%s secteurs=%s",
            ref_date,
            len(symbols),
            sum(bool(value) for value in ticker_agg.get("signal_active", pd.Series(dtype=bool)).tolist()) if not ticker_agg.empty else 0,
            len(sector_agg),
        )

        # --- Jointure scores quantitatifs ← ticker sentiment ---
        if not ticker_agg.empty and "symbol" in ticker_agg.columns:
            ticker_map = {
                self._normalize_identifier(row.get("symbol")): row
                for row in ticker_agg.to_dict(orient="records")
                if self._normalize_identifier(row.get("symbol")) is not None
            }
            result["sentiment_net_agg"] = [
                ticker_map.get(self._normalize_identifier(symbol), {}).get("sentiment_net_agg")
                for symbol in result["symbol"].tolist()
            ]
            result["major_event_flag_agg"] = [
                ticker_map.get(self._normalize_identifier(symbol), {}).get("major_event_flag_agg")
                for symbol in result["symbol"].tolist()
            ]
            result["total_news"] = [
                ticker_map.get(self._normalize_identifier(symbol), {}).get("total_news")
                for symbol in result["symbol"].tolist()
            ]
            result["signal_active"] = [
                ticker_map.get(self._normalize_identifier(symbol), {}).get("signal_active")
                for symbol in result["symbol"].tolist()
            ]
            result["signal_age_days"] = [
                ticker_map.get(self._normalize_identifier(symbol), {}).get("signal_age_days")
                for symbol in result["symbol"].tolist()
            ]
            result["signal_staleness_weight"] = [
                ticker_map.get(self._normalize_identifier(symbol), {}).get("signal_staleness_weight")
                for symbol in result["symbol"].tolist()
            ]
        else:
            result["sentiment_net_agg"] = 0.0
            result["major_event_flag_agg"] = 0
            result["total_news"] = 0
            result["signal_active"] = False
            result["signal_age_days"] = 0
            result["signal_staleness_weight"] = 0.0

        # --- Jointure scores quantitatifs ← impact macro sectoriel ---
        if not sector_agg.empty and "sector" in result.columns:
            sector_map = {
                self._normalize_identifier(row.get("sector")): row
                for row in sector_agg.to_dict(orient="records")
                if self._normalize_identifier(row.get("sector")) is not None
            }
            result["sector_impact_agg"] = [
                sector_map.get(self._normalize_identifier(sector), {}).get("sector_impact_agg")
                for sector in result["sector"].tolist()
            ]
            result["macro_event_flag_agg"] = [
                sector_map.get(self._normalize_identifier(sector), {}).get("macro_event_flag_agg")
                for sector in result["sector"].tolist()
            ]
            result["macro_signal_age_days"] = [
                sector_map.get(self._normalize_identifier(sector), {}).get("macro_signal_age_days")
                for sector in result["sector"].tolist()
            ]
            result["macro_signal_staleness_weight"] = [
                sector_map.get(self._normalize_identifier(sector), {}).get("macro_signal_staleness_weight")
                for sector in result["sector"].tolist()
            ]
        else:
            result["sector_impact_agg"] = 0.0
            result["macro_event_flag_agg"] = 0
            result["macro_signal_age_days"] = 0
            result["macro_signal_staleness_weight"] = 0.0

        def _coalesce_float(values: list[object], default: float = 0.0) -> list[float]:
            return [_scalar_float(value, default=default) for value in values]

        def _coalesce_bool(values: list[object], default: bool = False) -> list[bool]:
            return [_scalar_bool(value, default=default) for value in values]

        def _coalesce_int(values: list[object], default: int = 0) -> list[int]:
            return [_scalar_int(value, default=default) for value in values]

        result["sentiment_net_agg"] = _coalesce_float(result["sentiment_net_agg"].tolist())
        result["sector_impact_agg"] = _coalesce_float(result["sector_impact_agg"].tolist())
        result["company_idio_score"] = result["sentiment_net_agg"]
        result["macro_regime_score"] = result["sector_impact_agg"]
        result["major_event_flag_agg"] = _coalesce_int(result["major_event_flag_agg"].tolist())
        result["macro_event_flag_agg"] = _coalesce_int(result["macro_event_flag_agg"].tolist())
        result["total_news"] = _coalesce_int(result["total_news"].tolist())
        result["signal_age_days"] = _coalesce_int(result["signal_age_days"].tolist())
        result["macro_signal_age_days"] = _coalesce_int(result["macro_signal_age_days"].tolist())
        result["signal_staleness_weight"] = _coalesce_float(result["signal_staleness_weight"].tolist())
        result["macro_signal_staleness_weight"] = _coalesce_float(result["macro_signal_staleness_weight"].tolist())
        result["signal_active"] = _coalesce_bool(result["signal_active"].tolist())

        # --- Normalisation des signaux sentiment en [0, 1] ---
        # Mapping stable et déterministe : [-1, 1] -> [0, 1] ; 0.5 = neutre.
        result["sentiment_signal_norm"] = self._normalize_signed_signal(result["sentiment_net_agg"])
        result["macro_signal_norm"] = self._normalize_signed_signal(result["sector_impact_agg"])
        result["company_idio_signal_norm"] = result["sentiment_signal_norm"]
        result["macro_regime_signal_norm"] = result["macro_signal_norm"]

        # --- Composition du final_score_sentiment (score fusionné) ---
        # final_score reste intact (score quantitatif AlphaScanner).
        # Délégation à core.conviction.fuse_sentiment (Phase 4.1.b) : la
        # formule reste strictement identique (cf. tests gold). Les colonnes
        # intermédiaires `quant_component`, `company_idio_component`,
        # `macro_regime_component` sont reconstruites pour préserver le
        # contrat consommé par `save_to_db` et l'IHM.
        fusion_weights = self.config.to_fusion_weights()
        sentiment_arr = np.asarray(result["sentiment_signal_norm"], dtype=float)
        macro_arr = np.asarray(result["macro_signal_norm"], dtype=float)
        quant_arr = np.asarray(result["final_score"], dtype=float)
        active_arr = np.asarray(result["signal_active"], dtype=bool)

        sent_component = np.where(
            active_arr,
            fusion_weights.sentiment_weight * sentiment_arr,
            fusion_weights.sentiment_weight * 0.5,  # neutre si pas assez de news
        )
        macro_component = fusion_weights.macro_weight * macro_arr
        quant_component = fusion_weights.quant_weight * quant_arr

        result["company_idio_component"] = sent_component
        result["macro_regime_component"] = macro_component
        result["quant_component"] = quant_component
        result["final_score_walk_forward"] = pd.NA
        result["walk_forward_sentiment_weight"] = pd.NA
        result["walk_forward_macro_weight"] = pd.NA
        result["walk_forward_quant_weight"] = pd.NA
        result["calibration_run_id"] = pd.NA
        result["calibration_source"] = pd.NA

        result["final_score_sentiment"] = fuse_sentiment(
            quant_score=quant_arr,
            sentiment_signal_norm=sentiment_arr,
            macro_signal_norm=macro_arr,
            weights=fusion_weights,
            signal_active=active_arr,
        )

        score_deltas = [
            _scalar_float(final_score_sentiment) - _scalar_float(final_score)
            for final_score_sentiment, final_score in zip(
                result["final_score_sentiment"].tolist(),
                result["final_score"].tolist(),
                strict=False,
            )
        ]
        avg_delta = (sum(score_deltas) / len(score_deltas)) if score_deltas else 0.0
        LOGGER.info(
            "Boost sentiment applique | symboles_actifs=%s delta_score_moyen=%.4f",
            sum(bool(value) for value in result["signal_active"].tolist()),
            avg_delta,
        )
        self._emit_progress(
            {
                "trade_date": ref_date.isoformat(),
                "loaded_symbols": len(symbols),
                "signal_active_symbols": int(sum(bool(value) for value in result["signal_active"].tolist())),
                "avg_score_delta": round(float(avg_delta), 4),
            },
            current=2,
            total=2,
            label="🧠 Progression signal aggregator — fusion quant + sentiment",
            phase="merge_scores",
        )
        return result

    # ------------------------------------------------------------------
    # Persistance en base
    # ------------------------------------------------------------------

    def save_to_db(self, enriched_df: pd.DataFrame) -> int:
        """
        Persiste les scores de sentiment fusionnés dans stock_scores.

        Met à jour uniquement les colonnes de sentiment + final_score pour
        chaque symbole présent dans enriched_df (résultat de merge()).
        Utilise INSERT … ON DUPLICATE KEY UPDATE (upsert MySQL).

        :param enriched_df: DataFrame retourné par merge().
        :return: Nombre de lignes affectées.
        """
        SENTIMENT_COLS = [
            "sentiment_net_agg",
            "sector_impact_agg",
            "company_idio_score",
            "macro_regime_score",
            "sentiment_signal_norm",
            "macro_signal_norm",
            "company_idio_signal_norm",
            "macro_regime_signal_norm",
            "company_idio_component",
            "macro_regime_component",
            "quant_component",
            "final_score_sentiment",
            "final_score_walk_forward",
            "walk_forward_sentiment_weight",
            "walk_forward_macro_weight",
            "walk_forward_quant_weight",
            "calibration_run_id",
            "calibration_source",
            "signal_active",
            "major_event_flag_agg",
            "macro_event_flag_agg",
            "total_news",
        ]

        required = {"symbol"} | set(SENTIMENT_COLS)
        missing = required - set(enriched_df.columns)
        if missing:
            raise ValueError(
                f"save_to_db : colonnes manquantes dans enriched_df : {missing}. "
                "Appelez merge() avant save_to_db()."
            )

        if enriched_df.empty:
            return 0

        working_df = enriched_df.copy()
        working_df["symbol"] = [self._normalize_identifier(value) for value in working_df["symbol"].tolist()]
        working_df = working_df[working_df["symbol"].notna()].copy()
        if working_df.empty:
            return 0
        working_df = working_df.drop_duplicates(subset=["symbol"], keep="last")

        now = _utc_now_naive()

        def _is_missing(value: object) -> bool:
            return _is_missing_scalar(value)

        float_cols = (
            "sentiment_net_agg",
            "sector_impact_agg",
            "company_idio_score",
            "macro_regime_score",
            "sentiment_signal_norm",
            "macro_signal_norm",
            "company_idio_signal_norm",
            "macro_regime_signal_norm",
            "company_idio_component",
            "macro_regime_component",
            "quant_component",
            "final_score_sentiment",
            "final_score_walk_forward",
            "walk_forward_sentiment_weight",
            "walk_forward_macro_weight",
            "walk_forward_quant_weight",
        )
        bool_cols = ("signal_active", "major_event_flag_agg", "macro_event_flag_agg")
        float_defaults = {
            "sentiment_net_agg": 0.0,
            "sector_impact_agg": 0.0,
            "company_idio_score": 0.0,
            "macro_regime_score": 0.0,
            "sentiment_signal_norm": 0.5,
            "macro_signal_norm": 0.5,
            "company_idio_signal_norm": 0.5,
            "macro_regime_signal_norm": 0.5,
            "company_idio_component": self.config.sentiment_weight * 0.5,
            "macro_regime_component": self.config.macro_sector_weight * 0.5,
            "quant_component": 0.0,
            "final_score_sentiment": 0.0,
            "final_score_walk_forward": 0.0,
            "walk_forward_sentiment_weight": 0.0,
            "walk_forward_macro_weight": 0.0,
            "walk_forward_quant_weight": 0.0,
        }
        float_bounds = {
            "sentiment_net_agg": (-1.0, 1.0),
            "sector_impact_agg": (-1.0, 1.0),
            "company_idio_score": (-1.0, 1.0),
            "macro_regime_score": (-1.0, 1.0),
            "sentiment_signal_norm": (0.0, 1.0),
            "macro_signal_norm": (0.0, 1.0),
            "company_idio_signal_norm": (0.0, 1.0),
            "macro_regime_signal_norm": (0.0, 1.0),
            "company_idio_component": (0.0, 1.0),
            "macro_regime_component": (0.0, 1.0),
            "quant_component": (0.0, 1.0),
            "final_score_sentiment": (0.0, 1.0),
            "final_score_walk_forward": (0.0, 1.0),
            "walk_forward_sentiment_weight": (0.0, 1.0),
            "walk_forward_macro_weight": (0.0, 1.0),
            "walk_forward_quant_weight": (0.0, 1.0),
        }

        clean_records: list[dict[str, object]] = []
        for row in working_df.to_dict(orient="records"):
            clean_row: dict[str, object] = {
                "symbol": row["symbol"],
                "last_updated_sentiment": now,
            }
            for col in float_cols:
                value = row.get(col)
                default_value = float_defaults[col]
                if _is_missing(value):
                    clean_row[col] = default_value
                    continue
                bounded_value = _scalar_float(value, default=default_value)
                if not np.isfinite(bounded_value):
                    clean_row[col] = default_value
                    continue
                lower_bound, upper_bound = float_bounds[col]
                clean_row[col] = min(max(bounded_value, lower_bound), upper_bound)
            for col in bool_cols:
                value = row.get(col)
                clean_row[col] = int(bool(value)) if not _is_missing(value) else 0
            for col in ("calibration_run_id", "calibration_source"):
                value = row.get(col)
                clean_row[col] = None if _is_missing(value) else str(value)
            total_news = row.get("total_news")
            if _is_missing(total_news):
                clean_row["total_news"] = 0
            else:
                clean_row["total_news"] = max(0, _scalar_int(total_news, default=0))
            clean_records.append(clean_row)

        update_set = ", ".join(
            f"{col} = :{col}"
            for col in SENTIMENT_COLS + ["last_updated_sentiment"]
        )

        stmt = text(
            f"""
            UPDATE stock_scores
            SET {update_set}
            WHERE symbol = :symbol
            """
        )

        with self.engine.begin() as conn:
            conn.execute(stmt, clean_records)

        LOGGER.info(
            "save_to_db | %d lignes mises a jour dans stock_scores (colonnes sentiment).",
            len(clean_records),
        )
        self._emit_progress(
            {
                "updated_symbols": len(clean_records),
            },
            current=len(clean_records),
            total=len(clean_records),
            label="🧠 Progression signal aggregator — persistance DB",
            phase="persist_scores",
            unit="symboles",
        )
        return len(clean_records)


# ---------------------------------------------------------------------------
# Point d'entrée standalone
# ---------------------------------------------------------------------------
# Ordre d'exécution recommandé :
#   1. stock_screener.py          → scores quantitatifs de base
#   2. alpha_scanner.py           → trend_score, vcp_score, final_score (quant only)
#   3. sentiment_pipeline.py      → news → FinBERT → ticker/sector daily features
#   4. signal_aggregator.py       → fusion quant + sentiment → final_score définitif
#
# Usage :
#   python -m event_sentiment.signal_aggregator
#   python -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-04-17
#   python -m event_sentiment.signal_aggregator --sentiment-weight 0.20 --macro-weight 0.10
# ---------------------------------------------------------------------------

def _load_scores_from_db(engine: Engine, all_symbols: bool) -> pd.DataFrame:
    """
    Charge depuis stock_scores les colonnes nécessaires à merge().
    Charge tous les symboles du snapshot score; le score ne définit pas le
    périmètre nominal du pipeline sentiment.
    """
    stmt = text(
        f"""
        SELECT symbol,
               final_score,
               trend_score,
               vcp_score,
               total_score,
               sector
        FROM stock_scores
        ORDER BY total_score DESC
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql_query(stmt, conn)
    return df


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="signal_aggregator",
        description=(
            "Fusion des scores quantitatifs (stock_scores) avec le sentiment FinBERT "
            "(ticker_daily_features, sector_daily_features) → met à jour final_score dans stock_scores."
        ),
    )
    parser.add_argument(
        "--news-provider",
        type=str,
        choices=("alpaca", "finnhub", "eodhd"),
        default="eodhd",
        help="Provider news attendu pour vérifier le checkpoint d'ordre S2 avant la fusion signal_aggregator.",
    )
    parser.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="Date de référence ISO (YYYY-MM-DD). Défaut : aujourd'hui.",
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        default=False,
        help="Traite tous les symboles de stock_scores (pas seulement les candidats).",
    )
    parser.add_argument(
        "--sentiment-weight",
        type=float,
        default=0.15,
        help="Poids du signal sentiment ticker [0,1]. Défaut 0.15.",
    )
    parser.add_argument(
        "--macro-weight",
        type=float,
        default=0.10,
        help="Poids du signal macro sectoriel [0,1]. Défaut 0.10.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="Fenêtre glissante en jours pour agréger le sentiment. Défaut 5.",
    )
    parser.add_argument(
        "--min-news-count",
        type=int,
        default=2,
        help="Nombre minimal d'articles pour activer le boost. Défaut 2.",
    )
    parser.add_argument(
        "--time-decay-half-life-days",
        type=float,
        default=2.0,
        help=(
            "Demi-vie en jours de la décroissance temporelle exponentielle appliquee "
            "aux news/scores anciens dans la fenetre. Défaut 2.0."
        ),
    )
    parser.add_argument(
        "--allow-rerun",
        action="store_true",
        default=False,
        help=(
            "Autorise un re-lancement pour un trade_date déjà traité (audit "
            "S1 / A-022). Par défaut, le module refuse une seconde "
            "application le même jour pour éviter une double fusion sentiment."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de log. Défaut INFO.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée principal du script standalone."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    configure_root_logging(
        level=getattr(logging, args.log_level),
        log_path="./log/signal_aggregator.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Résolution de la date de trading
    if args.trade_date:
        ref_date = date.fromisoformat(args.trade_date)
    else:
        ref_date = date.today()

    LOGGER.info(
        "=== SentimentSignalAggregator standalone | trade_date=%s all_symbols=%s ===",
        ref_date, args.all_symbols,
    )

    # Garde-fou idempotence (audit S1 / A-022).
    if _is_already_run(ref_date, bool(args.all_symbols)) and not args.allow_rerun:
        LOGGER.warning(
            "signal_aggregator deja execute pour trade_date=%s scope=%s "
            "(verrou=%s). Re-lancement refuse pour eviter une double fusion "
            "sentiment. Utiliser --allow-rerun pour forcer.",
            ref_date,
            "all" if args.all_symbols else "scored",
            _lock_path(ref_date, bool(args.all_symbols)),
        )
        _emit_run_summary(
            {
                "module": "signal_aggregator",
                "trade_date": ref_date.isoformat(),
                "all_symbols": bool(args.all_symbols),
                "status": "skipped",
                "skipped_reason": "already_applied_today",
            }
        )
        return 0

    # Validation des poids
    quant_weight = round(1.0 - args.sentiment_weight - args.macro_weight, 6)
    if quant_weight < 0:
        LOGGER.error(
            "sentiment_weight (%.2f) + macro_weight (%.2f) > 1.0 — impossible.",
            args.sentiment_weight, args.macro_weight,
        )
        return 1

    config = SentimentBoostConfig(
        sentiment_weight=args.sentiment_weight,
        macro_sector_weight=args.macro_weight,
        quant_weight=quant_weight,
        lookback_days=args.lookback_days,
        min_news_count=args.min_news_count,
        time_decay_half_life_days=args.time_decay_half_life_days,
    )

    from database.connection import get_sqlalchemy_engine
    from event_sentiment.db_io import EventSentimentRepository

    engine = get_sqlalchemy_engine()
    repository = EventSentimentRepository()
    started_at = _utc_now_naive()

    def _emit_cli_progress(
        summary: dict[str, object],
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        item: str | None = None,
        unit: str = "étapes",
    ) -> None:
        _emit_run_summary(
            attach_live_progress(
                summary,
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit=unit,
                item=item,
            )
        )

    # 1. Chargement des scores quantitatifs depuis stock_scores
    LOGGER.info("Chargement des scores depuis stock_scores…")
    scores_df = _load_scores_from_db(engine, args.all_symbols)
    scoped_symbols = sorted({str(symbol).strip().upper() for symbol in scores_df.get("symbol", []).tolist() if str(symbol).strip()}) if not scores_df.empty and "symbol" in scores_df.columns else []
    ordering_guard: dict[str, object] | None = None
    try:
        ordering_guard = _get_checkpoint_order_guard_status(
            repository,
            source_name=EventSentimentConfig.for_provider(args.news_provider).source_name,
            symbols=scoped_symbols,
        )
        if not bool(ordering_guard.get("ready", True)):
            _enforce_checkpoint_order_guard(
                repository,
                source_name=EventSentimentConfig.for_provider(args.news_provider).source_name,
                symbols=scoped_symbols,
            )
    except RuntimeError as exc:
        finished_at = _utc_now_naive()
        _emit_run_summary(
            {
                "module": "signal_aggregator",
                "trade_date": ref_date.isoformat(),
                "all_symbols": bool(args.all_symbols),
                "status": "blocked",
                "failure_reason": "event_sentiment_ordering_guard",
                "ordering_guard": ordering_guard,
                "error": str(exc),
            }
        )
        raise
    _emit_cli_progress(
        {
            "trade_date": ref_date.isoformat(),
            "all_symbols": bool(args.all_symbols),
            "loaded_symbols": int(len(scores_df)),
            "ordering_guard": ordering_guard,
        },
        current=1,
        total=4,
        label="🧠 Progression signal aggregator — chargement stock_scores",
        phase="load_scores",
    )

    if scores_df.empty:
        LOGGER.warning("Aucun symbole trouve dans stock_scores — arret.")
        finished_at = _utc_now_naive()
        _emit_run_summary(
            _build_cli_run_summary(
                config=config,
                trade_date=ref_date,
                all_symbols=bool(args.all_symbols),
                loaded_symbols=0,
                updated_symbols=0,
                enriched=pd.DataFrame(),
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        return 0

    LOGGER.info("Symboles charges : %d", len(scores_df))

    # 2. Fusion quant + sentiment
    aggregator = SentimentSignalAggregator(engine, config)
    aggregator.progress_callback = _emit_run_summary
    enriched = aggregator.merge(scores_df, trade_date=ref_date)

    # 3. Persistance dans stock_scores
    saved = aggregator.save_to_db(enriched)
    finished_at = _utc_now_naive()

    # Phase 4.1.c — fingerprints FinBERT actifs sur la fenêtre courante.
    finbert_fingerprints: list[str] = []
    try:
        from event_sentiment.db_io import EventSentimentRepository

        finbert_fingerprints = EventSentimentRepository().get_active_finbert_fingerprints(ref_date)
    except Exception as exc:  # noqa: BLE001 — best-effort
        LOGGER.warning("Lecture fingerprints FinBERT impossible (%s)", exc)

    _emit_cli_progress(
        {
            "trade_date": ref_date.isoformat(),
            "all_symbols": bool(args.all_symbols),
            "loaded_symbols": len(scores_df),
            "updated_symbols": int(saved),
            "finbert_model_fingerprints": list(finbert_fingerprints),
        },
        current=4,
        total=4,
        label="🧠 Progression signal aggregator — finalisation",
        phase="finalize",
    )

    _emit_run_summary(
        {
            **_build_cli_run_summary(
            config=config,
            trade_date=ref_date,
            all_symbols=bool(args.all_symbols),
            loaded_symbols=len(scores_df),
            updated_symbols=saved,
            enriched=enriched,
            started_at=started_at,
            finished_at=finished_at,
            finbert_fingerprints=finbert_fingerprints,
            ),
            "ordering_guard": ordering_guard,
        }
    )
    LOGGER.info(
        "=== Termine | %d symboles mis a jour dans stock_scores ===", saved
    )
    _mark_run_done(ref_date, bool(args.all_symbols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
