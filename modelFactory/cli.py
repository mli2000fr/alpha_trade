"""modelFactory/cli.py — CLI pour le module Model Factory."""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import threading
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from common.utils import configure_root_logging
from core.run_summary import attach_schema_version
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import (
    load_available_trading_dates,
    load_historical_prediction_scopes_from_scores_history,
)
from modelFactory.features import get_feature_columns
from modelFactory.config import (
    BaselineConfig,
    CalibrationConfig,
    ChampionSelectionConfig,
    DataConfig,
    DEFAULT_PATIENCE,
    GlobalModelConfig,
    ModelConfig,
    ReproducibilityConfig,
    ThresholdOptimizationConfig,
    TargetOptimizationConfig,
    TrainingConfig,
    WalkForwardConfig,
)
from modelFactory.reproducibility import apply_reproducibility
from modelFactory.runtime_status import increment_runtime_counter, reset_runtime_status, snapshot_runtime_status, update_runtime_status


LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
ML_MODES = ("rebuild-all", "rebuild-missing", "refresh-stale")
SYMBOL_SOURCES = (
    "tradable-universe",
    "stock-bars-daily",
    "ticket-recherche",
)
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 60.0
_REPORT_DIR = Path("artifacts/rapport_ml")


def _generate_and_save_batch_report(engine: Engine, batch_id: str) -> None:
    """Génère et sauvegarde le rapport Markdown du batch dans artifacts/rapport_ml/."""
    from modelFactory.report import generate_batch_report

    try:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        md_content = generate_batch_report(engine, batch_id)
        safe_name = batch_id.replace("/", "_").replace("\\", "_")[:100]
        report_path = _REPORT_DIR / f"{safe_name}.md"
        report_path.write_text(md_content, encoding="utf-8")
        LOGGER.info("Rapport batch sauvegardé : %s", report_path)
    except Exception as exc:
        LOGGER.warning("Échec génération rapport batch %s : %s", batch_id, exc)


def _resolve_predict_batch_id(artifacts_dir: Path) -> str | None:
    """Détermine le batch_id pour le mode predict.

    Ordre de priorité :
    1. ``config.yaml`` → ``batch_diagnostics.backtest_batch_id`` (si renseigné)
    2. Dernier composant du chemin ``artifacts_dir`` (ex: ``model-factory-xxx``)
    3. None si indéterminable
    """
    # Priorité 1 : config
    try:
        import yaml as _yaml
        with open("config.yaml", encoding="utf-8") as _fh:
            _raw = _yaml.safe_load(_fh) or {}
        _bd = _raw.get("batch_diagnostics") or {}
        _bid = str(_bd.get("backtest_batch_id", "")).strip()
        if _bid:
            return _bid
    except Exception:
        pass

    # Priorité 2 : dernier composant du chemin artifacts_dir
    try:
        _name = artifacts_dir.resolve().name
        if _name and _name not in (".", "..", ""):
            return _name
    except Exception:
        pass

    return None


def _build_training_batch_command(raw_args: list[str]) -> tuple[str, str]:
    argv = ["python", "-m", "modelFactory", *raw_args]
    return subprocess.list2cmdline(argv), json.dumps(raw_args, ensure_ascii=False)


def _build_training_batch_metadata(opts: argparse.Namespace, cfg: TrainingConfig) -> str:
    feature_columns = get_feature_columns(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=cfg.global_model.stacking_enabled,
        include_fundamentals=cfg.data.include_fundamentals_features,
        include_factors=cfg.data.include_factors_features,
        include_macro_regime=cfg.data.include_macro_regime_features,
    )
    return json.dumps(
        {
            "cli_options": vars(opts),
            "training_config": asdict(cfg),
            "feature_columns": feature_columns,
        },
        default=str,
        ensure_ascii=False,
        sort_keys=True,
    )


def _parse_selector_signal_modes_arg(values: list[str] | None) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values or []:
        for part in str(raw_value).split(","):
            value = part.strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
    return tuple(normalized)


def _parse_iso_date_arg(value: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date attendue au format YYYY-MM-DD.") from exc


class _LiveRunSummaryEmitter:
    def __init__(
        self,
        *,
        run_id: str,
        mode: str,
        heartbeat_interval_seconds: float,
        watchdog_timeout_seconds: int,
        debug_train: bool,
    ) -> None:
        self.run_id = run_id
        self.mode = mode
        self.heartbeat_interval_seconds = max(float(heartbeat_interval_seconds), 0.0)
        self.watchdog_timeout_seconds = max(int(watchdog_timeout_seconds), 0)
        self.debug_train = bool(debug_train)
        self.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_LiveRunSummaryEmitter":
        if self.heartbeat_interval_seconds > 0:
            self.emit_now()  # type: ignore[no-untyped-call]
            self._thread = threading.Thread(target=self._run, daemon=True, name=f"ml-heartbeat-{self.run_id}")
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.heartbeat_interval_seconds, 1.0))

    def _run(self) -> None:
        while not self._stop_event.wait(self.heartbeat_interval_seconds):
            self.emit_now()

    def emit_now(self) -> None:
        heartbeat_count = increment_runtime_counter("heartbeat_count", 1)
        heartbeat_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        runtime_status = update_runtime_status(last_heartbeat_at=heartbeat_dt.isoformat(timespec="seconds"), heartbeat_count=heartbeat_count)
        payload = {
            "run_id": self.run_id,
            "mode": self.mode,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "watchdog_timeout_seconds": self.watchdog_timeout_seconds,
            "last_heartbeat_at": heartbeat_dt.isoformat(timespec="seconds"),
            "heartbeat_count": heartbeat_count,
            "debug_train_enabled": self.debug_train,
            "progress_live": True,
            "progress_label": str(runtime_status.get("progress_label") or "🧠 Progression ML Train"),
            "progress_total": int(runtime_status.get("progress_total", runtime_status.get("symbols_total", 0)) or 0),
            "progress_current": int(runtime_status.get("progress_current", 0) or 0),
            "progress_item": runtime_status.get("progress_item"),
            "current_symbol": runtime_status.get("current_symbol"),
            "current_symbol_index": int(runtime_status.get("current_symbol_index", 0) or 0),
            "current_symbol_total": int(runtime_status.get("current_symbol_total", runtime_status.get("symbols_total", 0)) or 0),
            "symbols_total": int(runtime_status.get("symbols_total", 0) or 0),
            "symbols_completed": int(runtime_status.get("symbols_completed", 0) or 0),
            "symbols_skipped": int(runtime_status.get("symbols_skipped", 0) or 0),
            "symbols_failed": int(runtime_status.get("symbols_failed", 0) or 0),
            "current_phase": runtime_status.get("current_phase"),
            "phase_detail": runtime_status.get("phase_detail"),
            "current_epoch": runtime_status.get("current_epoch"),
            "total_epochs": runtime_status.get("total_epochs"),
            "current_split_index": runtime_status.get("current_split_index"),
        }
        _emit_run_summary(payload)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Model Factory — LSTM per-symbol training & prediction")
    p.add_argument("--mode", choices=["train", "predict"], required=True, help="train ou predict")
    p.add_argument("--symbols", nargs="*", default=None, help="Liste explicite de symboles")
    p.add_argument(
        "--symbol-source",
        type=str,
        default="tradable-universe",
        choices=list(SYMBOL_SOURCES),
        help="Source nominale quand --symbols n'est pas fourni.",
    )
    p.add_argument(
        "--universe-date",
        type=_parse_iso_date_arg,
        default=None,
        help="Date PIT de l'univers tradable (défaut: training-end-date ou date du jour)",
    )
    p.add_argument(
        "--start-symbol",
        type=str,
        default=None,
        help=(
            "Si renseigné, l'entraînement commence au premier symbole alphabétiquement supérieur ou égal à cette valeur. "
            "Exemple : HGI démarre à HGI et ignore les symboles précédents."
        ),
    )
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument("--max-epochs", type=int, default=50)
    p.add_argument("--patience", type=int, default=DEFAULT_PATIENCE,
                   help="Patience pour l'early stopping du LSTM (epochs sans amélioration).")
    p.add_argument("--sequence-length", type=int, default=60)
    p.add_argument("--forecast-horizon", type=int, default=10)
    p.add_argument(
        "--training-start-date",
        type=_parse_iso_date_arg,
        default=date(2020, 1, 1),
        help="Date minimale d'historique utilisée au training (format YYYY-MM-DD)",
    )
    p.add_argument(
        "--training-end-date",
        type=_parse_iso_date_arg,
        default=None,
        help="Date maximale incluse du training / backfill de prédictions historiques (format YYYY-MM-DD)",
    )
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--hidden-size", type=int, default=128)
    p.add_argument("--num-classes", type=int, default=2,
                   help="Nombre de classes : 2=binaire, 3=ternaire long/flat/short")
    p.add_argument("--ternary-weight-short", type=float, default=1.0,
                   help="Poids de la classe short dans la loss ternaire (défaut: 1.0)")
    p.add_argument("--ternary-weight-flat", type=float, default=1.5,
                   help="Poids de la classe flat dans la loss ternaire (défaut: 1.5)")
    p.add_argument("--ternary-weight-long", type=float, default=1.0,
                   help="Poids de la classe long dans la loss ternaire (défaut: 1.0)")
    p.add_argument("--ternary-threshold-short", type=float, default=0.45,
                   help="Seuil minimum de p_short pour autoriser un signal short (défaut: 0.45)")
    p.add_argument("--ternary-threshold-long", type=float, default=0.45,
                   help="Seuil minimum de p_long pour autoriser un signal long (défaut: 0.45)")
    p.add_argument("--ternary-top2-margin", type=float, default=0.05,
                   help="Marge minimale entre la 1ère et 2ème proba pour éviter une décision ambiguë (défaut: 0.05)")
    p.add_argument("--artifacts-dir", type=str, default="artifacts/models")
    p.add_argument("--include-sentiment", action="store_true", default=False,
                   help="Inclure les features sentiment (ticker_daily_sentiment_features) dans le modèle")
    p.add_argument("--include-screener-scores",
                   dest="include_screener_scores", action="store_true", default=False,
                   help="Inclure les scores du screener PIT-safe (trend, VCP, final_score, etc.) comme features ML")
    p.add_argument("--include-short-score", action="store_true", default=False,
                   help="Inclure le score baissier composite (short_score) comme feature ML independante")
    p.add_argument("--include-macro-vix", action="store_true", default=False,
                   help="Inclure les features VIX/VIX9D (volatilité implicite S&P 500) dans le modèle")
    p.add_argument("--include-macro-vxn", action="store_true", default=False,
                   help="Inclure les features VXN (volatilité implicite NASDAQ-100) dans le modèle")
    p.add_argument("--include-macro-vix3m", action="store_true", default=False,
                   help="Inclure les features VIX3M + ratio term structure (contango/backwardation) dans le modèle")
    p.add_argument("--include-macro-move", action="store_true", default=False,
                   help="Inclure les features MOVE (volatilité obligataire ICE BofA) dans le modèle")
    p.add_argument("--include-fundamentals", action="store_true", default=False,
                   help="Inclure les features fondamentales EODHD (PE, ROE, marges, croissance) — Global Model uniquement")
    p.add_argument("--include-factors", action="store_true", default=False,
                   help="Inclure les expositions factorielles CAPM (beta, alpha, R² via rolling 252j)")
    p.add_argument("--include-macro-regime", action="store_true", default=False,
                   help="Inclure les indicateurs de régime macro (SPY_SMA_200_slope + VIX_zscore)")
    p.add_argument("--ranking-top-k-features", type=int, default=0,
                   help="Global Ranking : nombre de features à garder par importance (0 = toutes, ex: 30 = top 30)")
    p.add_argument("--global-ranking-max-symbols", type=int, default=0,
                   help="Global Ranking : nombre max de symboles (0 = tous, top N par volume moyen ou stratifié)")
    p.add_argument("--global-ranking-selection-stratified", action="store_true", default=False,
                   help="Global Ranking : sélection stratifiée par déciles de volume (sinon top N par volume)")
    p.add_argument("--per-symbol-max-symbols", type=int, default=0,
                   help="Per-Symbol : nombre max de symboles à entraîner (0 = tous, top N par volume ou stratifié). Pour test rapide.")
    p.add_argument("--per-symbol-selection-stratified", action="store_true", default=False,
                   help="Per-Symbol : sélection stratifiée par déciles de volume (sinon top N par volume)")
    p.add_argument("--exclude-ticket-symbols", action="store_true", default=False,
                   help="Exclure les symboles listés dans config/ticket_exclude.txt (séparés par virgule)")
    p.add_argument("--enable-cross-sectional", action="store_true", default=False,
                   help="Active les features cross-sectionnelles PIT-safe (rangs percentiles + features sectorielles dynamiques)")
    p.add_argument("--cross-sectional-min-universe", type=int, default=20,
                   help="Nombre minimum de symboles disponibles par date pour calculer des ranks cross-sectionnels fiables")
    # ── Filtrage liquidité (Sprint 2026-07-24) ──
    p.add_argument("--enable-liquidity-filter", action="store_true", default=False,
                   help="Active le filtrage des symboles par liquidité (volume, market cap, spread) avant entraînement")
    p.add_argument("--liquidity-min-avg-volume-20d", type=int, default=500_000,
                   help="Volume quotidien moyen minimum sur 20 jours (défaut: 500k)")
    p.add_argument("--liquidity-min-market-cap", type=float, default=500_000_000.0,
                   help="Market cap minimum en dollars (défaut: 500M)")
    p.add_argument("--liquidity-max-avg-spread-pct", type=float, default=0.5,
                   help="Spread journalier moyen maximum en %% (défaut: 0.5)")
    p.add_argument("--feature-set", type=str, default="v1", choices=["v1", "expert"])
    p.add_argument("--benchmark-symbol", type=str, default="SPY")
    p.add_argument("--target-mode", type=str, default="binary", choices=["binary", "swing_cash", "ternary"])
    p.add_argument("--label-method", type=str, default="fixed_horizon", choices=["fixed_horizon", "triple_barrier"])
    p.add_argument("--triple-barrier-stop-atr-mult", type=float, default=2.0)
    p.add_argument("--triple-barrier-tp-atr-mult", type=float, default=3.0)
    p.add_argument("--triple-barrier-max-sessions", type=int, default=20)
    p.add_argument("--target-up-threshold", type=float, default=0.0,
                   help="Seuil de rendement futur pour classer une hausse tradeable")
    p.add_argument("--target-down-threshold", type=float, default=0.0,
                   help="Seuil de rendement futur pour classer une baisse marquée / zone no-trade")
    p.add_argument("--decision-threshold", type=float, default=0.5,
                   help="Seuil de probabilité pour émettre un signal long (sinon no-trade)")
    p.add_argument("--calibration-method", type=str, default="none", choices=["none", "platt"])
    p.add_argument("--calibration-min-samples", type=int, default=64)
    p.add_argument("--calibration-max-iter", type=int, default=100)
    # Phase 4.2.g — walk-forward actif PAR DÉFAUT (BooleanOptionalAction).
    p.add_argument(
        "--walkforward",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Active une évaluation walk-forward avant l'entraînement final (défaut: ON Phase 4.2.g)",
    )
    p.add_argument(
        "--ml-mode",
        type=str,
        default="rebuild-all",
        choices=list(ML_MODES),
        help="Stratégie d'entraînement (Phase 4.2.g) : rebuild-all | rebuild-missing | refresh-stale",
    )
    p.add_argument("--wf-min-train-size", type=int, default=504)
    p.add_argument("--wf-val-size", type=int, default=126)
    p.add_argument("--wf-test-size", type=int, default=126)
    p.add_argument("--wf-step-size", type=int, default=126)
    p.add_argument("--wf-max-splits", type=int, default=11)
    p.add_argument("--compare-lightgbm", action="store_true", default=False,
                   help="Entraîne aussi une baseline LightGBM et compare ses métriques")
    p.add_argument("--enable-catboost", action="store_true", default=False,
                   help="Entraîne aussi une baseline CatBoost et compare ses métriques")
    p.add_argument("--enable-global-model", action="store_true", default=False,
                   help="Entraîne aussi un modèle global multi-symboles en comparaison")
    p.add_argument("--enable-global-stacking", action="store_true", default=False,
                   help="Utilise la prédiction du Global Model comme feature (Approche 2 — Stacking)")
    p.add_argument("--enable-global-challenger", action="store_true", default=False,
                   help="Inclut le Global Model comme 4ème challenger dans la sélection champion")
    p.add_argument("--global-model-name", type=str, default="catboost", choices=["catboost", "lightgbm"])
    p.add_argument("--global-artifact-symbol", type=str, default="__GLOBAL__")
    p.add_argument("--select-champion", action="store_true", default=False,
                   help="Active la sélection automatique du champion parmi les modèles éligibles à l’inférence")
    p.add_argument("--default-champion", type=str, default="lstm_attention",
                   choices=["lstm_attention", "lightgbm", "catboost", "global_model"])
    # Phase 4.2.e — Quarantaine champion.
    p.add_argument("--champion-min-runs", type=int, default=0,
                   help="Nb min de runs walk-forward complétés avant qu'un nouveau champion soit servi")
    p.add_argument("--champion-min-days", type=int, default=0,
                   help="Nb min de jours d'observation avant qu'un nouveau champion soit servi")
    p.add_argument("--lgbm-max-depth", type=int, default=4)
    p.add_argument("--lgbm-n-estimators", type=int, default=200)
    p.add_argument("--lgbm-learning-rate", type=float, default=0.05)
    p.add_argument("--lgbm-reg-alpha", type=float, default=0.0,
                   help="L1 régularisation LightGBM")
    p.add_argument("--lgbm-reg-lambda", type=float, default=0.0,
                   help="L2 régularisation LightGBM")
    p.add_argument("--lgbm-min-child-samples", type=int, default=20,
                   help="LightGBM min_data_in_leaf")
    p.add_argument("--lgbm-subsample", type=float, default=1.0,
                   help="LightGBM bagging_fraction")
    p.add_argument("--lgbm-colsample-bytree", type=float, default=1.0,
                   help="LightGBM feature_fraction")
    p.add_argument("--lgbm-early-stopping-rounds", type=int, default=30,
                   help="LightGBM early stopping rounds (0 = désactivé)")
    p.add_argument("--catboost-depth", type=int, default=6)
    p.add_argument("--catboost-iterations", type=int, default=300)
    p.add_argument("--catboost-learning-rate", type=float, default=0.03)
    p.add_argument("--catboost-l2-leaf-reg", type=float, default=3.0,
                   help="L2 régularisation CatBoost")
    p.add_argument("--catboost-border-count", type=int, default=254,
                   help="CatBoost border_count (max 255)")
    p.add_argument("--catboost-random-strength", type=float, default=1.0,
                   help="CatBoost random_strength")
    p.add_argument("--catboost-bagging-temperature", type=float, default=1.0,
                   help="CatBoost bagging_temperature")
    p.add_argument("--catboost-od-type", type=str, default="IncToDec",
                   choices=["IncToDec", "Iter"],
                   help="CatBoost overfitting detector")
    p.add_argument("--catboost-od-wait", type=int, default=20,
                   help="CatBoost od_wait")
    p.add_argument("--optimize-target", action="store_true", default=False,
                   help="Sélectionne automatiquement le meilleur horizon swing parmi plusieurs candidats")
    p.add_argument("--candidate-horizons", nargs="*", type=int, default=[3, 5, 10, 15])
    p.add_argument("--candidate-up-thresholds", nargs="*", type=float, default=[0.0, 0.01, 0.02])
    p.add_argument("--candidate-down-thresholds", nargs="*", type=float, default=[0.0, -0.005, -0.01])
    p.add_argument("--min-trades-fraction", type=float, default=0.15)
    p.add_argument("--optimize-thresholds", action="store_true", default=False,
                   help="Sélectionne automatiquement le meilleur decision_threshold sur validation")
    p.add_argument("--candidate-decision-thresholds", nargs="*", type=float, default=[0.50, 0.55, 0.60, 0.65, 0.70])
    p.add_argument("--min-action-rate", type=float, default=0.03)
    p.add_argument("--max-action-rate", type=float, default=0.35)
    p.add_argument("--min-precision-long", type=float, default=0.52)
    p.add_argument("--accelerator", type=str, default="auto", choices=["auto", "cpu", "gpu"])
    p.add_argument("--seed", type=int, default=42, help="Seed racine unique pour numpy / torch / modèles tabulaires")
    p.add_argument(
        "--deterministic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Active les réglages backend déterministes quand possibles (défaut: ON)",
    )
    p.add_argument("--debug-train", action="store_true", default=False,
                   help="Mode debug ML train : logs plus détaillés et exécution plus déterministe côté orchestrateur")
    p.add_argument("--heartbeat-interval-seconds", type=float, default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
                   help="Intervalle d'émission des heartbeats structurés consommés par l'IHM")
    p.add_argument("--comment", type=str, default=None,
                   help="Commentaire libre saisi depuis l'IHM, sauvegardé dans model_training_batch")
    p.add_argument("--watchdog-timeout-seconds", type=int, default=0,
                   help="Timeout heartbeat côté IHM (0 = alerte seule, >0 = échec si heartbeat stale trop longtemps)")
    p.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def main(args: list[str] | None = None) -> None:
    parser = build_arg_parser()
    raw_args = list(args) if args is not None else sys.argv[1:]
    opts = parser.parse_args(raw_args)
    if opts.label_method == "triple_barrier" and (opts.target_mode != "ternary" or opts.num_classes != 3):
        parser.error("--label-method triple_barrier requiert --target-mode ternary et --num-classes 3")

    effective_log_level = logging.DEBUG if opts.debug_train else getattr(logging, opts.log_level)

    configure_root_logging(
        level=effective_log_level,
        log_path="./log/model_factory.log",
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = TrainingConfig(
        data=DataConfig(
            sequence_length=opts.sequence_length,
            forecast_horizon=opts.forecast_horizon,
            training_start_date=opts.training_start_date,
            training_end_date=opts.training_end_date,
            include_sentiment_features=opts.include_sentiment,
            include_screener_scores=opts.include_screener_scores,
            include_short_score_features=opts.include_short_score,
            include_macro_vix_features=opts.include_macro_vix,
            include_macro_vxn_features=opts.include_macro_vxn,
            include_macro_vix3m_features=opts.include_macro_vix3m,
            include_macro_move_features=opts.include_macro_move,
            include_fundamentals_features=opts.include_fundamentals,
            include_factors_features=opts.include_factors,
            include_macro_regime_features=opts.include_macro_regime,
            enable_cross_sectional_features=opts.enable_cross_sectional,
            cross_sectional_min_universe=opts.cross_sectional_min_universe,
            feature_set=opts.feature_set,
            benchmark_symbol=opts.benchmark_symbol,
            target_mode=opts.target_mode,
            label_method=opts.label_method,
            target_up_threshold=opts.target_up_threshold,
            target_down_threshold=opts.target_down_threshold,
            triple_barrier_stop_atr_mult=opts.triple_barrier_stop_atr_mult,
            triple_barrier_tp_atr_mult=opts.triple_barrier_tp_atr_mult,
            triple_barrier_max_sessions=opts.triple_barrier_max_sessions,
            decision_threshold=opts.decision_threshold,
            enable_liquidity_filter=opts.enable_liquidity_filter,
            liquidity_min_avg_volume_20d=opts.liquidity_min_avg_volume_20d,
            liquidity_min_market_cap=opts.liquidity_min_market_cap,
            liquidity_max_avg_spread_pct=opts.liquidity_max_avg_spread_pct,
            global_ranking_max_symbols=opts.global_ranking_max_symbols,
            global_ranking_selection_stratified=opts.global_ranking_selection_stratified,
            per_symbol_max_symbols=opts.per_symbol_max_symbols,
            per_symbol_selection_stratified=opts.per_symbol_selection_stratified,
            exclude_ticket_symbols=opts.exclude_ticket_symbols,
        ),
        model=ModelConfig(
            batch_size=opts.batch_size,
            hidden_size=opts.hidden_size,
            max_epochs=opts.max_epochs,
            patience=opts.patience,
            num_classes=opts.num_classes,
            ternary_weight_short=opts.ternary_weight_short,
            ternary_weight_flat=opts.ternary_weight_flat,
            ternary_weight_long=opts.ternary_weight_long,
            ternary_threshold_short=opts.ternary_threshold_short,
            ternary_threshold_long=opts.ternary_threshold_long,
            ternary_top2_margin=opts.ternary_top2_margin,
        ),
        calibration=CalibrationConfig(
            method=opts.calibration_method,
            min_samples=opts.calibration_min_samples,
            max_iter=opts.calibration_max_iter,
        ),
        walk_forward=WalkForwardConfig(
            enabled=opts.walkforward,
            min_train_size=opts.wf_min_train_size,
            val_size=opts.wf_val_size,
            test_size=opts.wf_test_size,
            step_size=opts.wf_step_size,
            max_splits=opts.wf_max_splits,
        ),
        baseline=BaselineConfig(
            enabled=opts.compare_lightgbm,
            enable_catboost=opts.enable_catboost,
            model_name="lightgbm",
            max_depth=opts.lgbm_max_depth,
            n_estimators=opts.lgbm_n_estimators,
            learning_rate=opts.lgbm_learning_rate,
            catboost_depth=opts.catboost_depth,
            catboost_iterations=opts.catboost_iterations,
            catboost_learning_rate=opts.catboost_learning_rate,
            random_state=opts.seed,
            lgbm_reg_alpha=opts.lgbm_reg_alpha,
            lgbm_reg_lambda=opts.lgbm_reg_lambda,
            lgbm_min_child_samples=opts.lgbm_min_child_samples,
            lgbm_subsample=opts.lgbm_subsample,
            lgbm_colsample_bytree=opts.lgbm_colsample_bytree,
            lgbm_early_stopping_rounds=opts.lgbm_early_stopping_rounds,
            ranking_top_k_features=opts.ranking_top_k_features,
            catboost_l2_leaf_reg=opts.catboost_l2_leaf_reg,
            catboost_border_count=opts.catboost_border_count,
            catboost_random_strength=opts.catboost_random_strength,
            catboost_bagging_temperature=opts.catboost_bagging_temperature,
            catboost_od_type=opts.catboost_od_type,
            catboost_od_wait=opts.catboost_od_wait,
        ),
        global_model=GlobalModelConfig(
            enabled=opts.enable_global_model,
            stacking_enabled=opts.enable_global_stacking,
            challenger_enabled=opts.enable_global_challenger,
            model_name=opts.global_model_name,
            artifact_symbol=opts.global_artifact_symbol,
            use_cross_sectional_features=opts.enable_cross_sectional,
        ),
        champion_selection=ChampionSelectionConfig(
            enabled=opts.select_champion,
            allow_auto_selection=opts.select_champion,
            default_champion=opts.default_champion,
            selection_metric="selection_score",
            min_runs=int(opts.champion_min_runs),
            min_days=int(opts.champion_min_days),
        ),
        target_optimization=TargetOptimizationConfig(
            enabled=opts.optimize_target,
            candidate_horizons=tuple(opts.candidate_horizons),
            candidate_up_thresholds=tuple(opts.candidate_up_thresholds),
            candidate_down_thresholds=tuple(opts.candidate_down_thresholds),
            min_trades_fraction=opts.min_trades_fraction,
        ),
        threshold_optimization=ThresholdOptimizationConfig(
            enabled=opts.optimize_thresholds,
            candidate_decision_thresholds=tuple(opts.candidate_decision_thresholds),
            min_action_rate=opts.min_action_rate,
            max_action_rate=opts.max_action_rate,
            min_precision_long=opts.min_precision_long,
        ),
        reproducibility=ReproducibilityConfig(seed=opts.seed, deterministic=opts.deterministic),
        artifacts_dir=Path(opts.artifacts_dir),
        max_workers=opts.max_workers,
        accelerator=opts.accelerator,
        debug_train=opts.debug_train,
    )

    reproducibility_state = apply_reproducibility(cfg.reproducibility, context=f"cli:{opts.mode}")

    engine = get_sqlalchemy_engine()
    universe_date = opts.universe_date or cfg.data.training_end_date or date.today()

    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run_id = f"model-factory-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    reset_runtime_status(
        {
            "current_phase": "cli_initialized",
            "progress_label": "🧠 Progression ML Train",
            "progress_total": 0,
            "progress_current": 0,
            "symbols_total": 0,
            "symbols_completed": 0,
            "symbols_skipped": 0,
            "symbols_failed": 0,
            "current_symbol_index": 0,
            "current_symbol_total": 0,
            "heartbeat_count": 0,
            "debug_train_enabled": bool(opts.debug_train),
            "reproducibility_seed": int(reproducibility_state.get("seed", cfg.reproducibility.seed) or cfg.reproducibility.seed),
            "reproducibility_deterministic": bool(reproducibility_state.get("deterministic_requested", cfg.reproducibility.deterministic)),
            "reproducibility_deterministic_applied": bool(reproducibility_state.get("deterministic_applied", False)),
        }
    )
    update_runtime_status(
        current_phase="cli_ready",
        phase_detail=(
            f"accelerator={opts.accelerator} max_workers={opts.max_workers} "
            f"log_level={logging.getLevelName(effective_log_level)} seed={cfg.reproducibility.seed} "
            f"deterministic={cfg.reproducibility.deterministic}"
        ),
    )

    if opts.mode == "train":
        from modelFactory.db_registry import insert_training_batch, update_training_batch
        from modelFactory.orchestrator import run_training_batch

        command_line, command_argv_json = _build_training_batch_command(raw_args)
        insert_training_batch(
            engine,
            batch_id=run_id,
            command_line=command_line,
            command_argv_json=command_argv_json,
            metadata_json=_build_training_batch_metadata(opts, cfg),
            symbol_source=opts.symbol_source,
            universe_date=universe_date,
            requested_symbol_count=len(opts.symbols) if opts.symbols else None,
            training_start_date=cfg.data.training_start_date,
            training_end_date=cfg.data.training_end_date,
            started_at=started_at,
            comment=opts.comment,
            stacking_enabled=opts.enable_global_stacking,
        )
        update_runtime_status(current_phase="batch_dispatch")
        try:
            with _LiveRunSummaryEmitter(
                run_id=run_id,
                mode="train",
                heartbeat_interval_seconds=opts.heartbeat_interval_seconds,
                watchdog_timeout_seconds=opts.watchdog_timeout_seconds,
                debug_train=opts.debug_train,
            ):
                results = run_training_batch(
                    cfg,
                    engine,
                    symbols=opts.symbols,
                    mode=opts.ml_mode,
                    symbol_source=opts.symbol_source,
                    universe_date=universe_date,
                    start_symbol=opts.start_symbol,
                    batch_id=run_id,
                )
        except Exception as exc:
            update_training_batch(
                engine,
                run_id,
                status="failed",
                finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
                failure_reason=str(exc),
            )
            raise
        completed = sum(1 for r in results if r.status == "completed")
        skipped = sum(1 for r in results if r.status == "skipped")
        failed = sum(1 for r in results if r.status == "failed")
        quarantined = sum(
            1 for r in results
            if isinstance(getattr(r, "metrics", None), dict)
            and r.metrics.get("champion_quarantine") is True
        )
        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # ── Injecter le diagnostic liquidité dans metadata_json ──
        try:
            from modelFactory.orchestrator import get_last_liquidity_diagnostics

            _liq_diag = get_last_liquidity_diagnostics()
            if _liq_diag and _liq_diag.get("filtered_count", 0) > 0:
                _existing_meta = json.loads(
                    _build_training_batch_metadata(opts, cfg),
                )
                _existing_meta["liquidity_filter"] = _liq_diag
                _updated_meta_json = json.dumps(_existing_meta, default=str, ensure_ascii=False, sort_keys=True)
                update_training_batch(
                    engine, run_id, metadata_json=_updated_meta_json,
                )
                LOGGER.info(
                    "cli: liquidity_filter injected into metadata_json filtered=%d kept=%d",
                    _liq_diag.get("filtered_count", 0),
                    _liq_diag.get("kept_count", 0),
                )
        except Exception as _liq_exc:
            LOGGER.warning("cli: failed to inject liquidity diagnostics: %s", _liq_exc)

        update_training_batch(
            engine,
            run_id,
            status="completed",
            finished_at=finished_at,
            symbols_completed=completed,
            symbols_skipped=skipped,
            symbols_failed=failed,
        )

        # ── Génération automatique du rapport Markdown ──
        _generate_and_save_batch_report(engine, run_id)

        update_runtime_status(
            current_phase="cli_completed",
            progress_live=False,
            progress_current=completed + skipped + failed,
            progress_total=len(opts.symbols or []) or len(results),
            symbols_total=len(opts.symbols or []) or len(results),
            symbols_completed=completed,
            symbols_skipped=skipped,
            symbols_failed=failed,
            phase_detail="training batch finished",
        )
        _emit_run_summary(_build_run_summary(
            mode="train",
            run_id=run_id,
            opts=opts,
            cfg=cfg,
            started_at=started_at,
            finished_at=finished_at,
            symbols_total=len(opts.symbols or []) or len(results),
            completed=completed,
            skipped=skipped,
            failed=failed,
            quarantined=quarantined,
        ))
        print(f"\n{'=' * 60}")
        print(f"  Model Factory — Training Summary")
        print(f"  Completed: {completed}  Skipped: {skipped}  Failed: {failed}")
        print(f"{'=' * 60}")

    elif opts.mode == "predict":
        from modelFactory.db_registry import (
            insert_predictions,
            load_symbols_for_source,
        )
        from modelFactory.predictor import predict_batch
        from modelFactory.drift_monitor import compute_drift
        from modelFactory.drift_policy import (
            apply_kill_switch,
            evaluate_drift_gate,
            persist_kill_switch_event,
            summary_fields as _drift_summary_fields,
        )
        historical_predict_enabled = cfg.data.training_end_date is not None
        persisted_incrementally = False

        def _persist_predictions_chunk(
            chunk: pd.DataFrame,
            *,
            operation: str,
            prediction_date: date | None = None,
        ) -> None:
            if chunk.empty:
                return
            try:
                insert_predictions(engine, chunk)
                if prediction_date is not None:
                    LOGGER.info(
                        "predict persistence persisted date=%s rows=%d operation=%s",
                        prediction_date.isoformat(),
                        len(chunk),
                        operation,
                    )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("predict batch persistence degraded rows=%d operation=%s error=%s", len(chunk), operation, exc)
                increment_runtime_counter("prediction_db_issue_count", 1)
                update_runtime_status(
                    last_db_issue_operation=operation,
                    last_db_issue_reason=f"prediction_persist_failed:{type(exc).__name__}",
                )

        symbols = opts.symbols or load_symbols_for_source(
            engine,
            opts.symbol_source,
            trade_date=universe_date,
        )
        if historical_predict_enabled:
            prediction_dates = load_available_trading_dates(
                engine,
                symbols=symbols,
                start_date=cfg.data.training_start_date,
                end_date=cfg.data.training_end_date,
            )
            LOGGER.info(
                "predict historical_backfill enabled symbols=%d start=%s end=%s dates=%d",
                len(symbols),
                cfg.data.training_start_date,
                cfg.data.training_end_date,
                len(prediction_dates),
            )

            # ── Cascade ML (Étape 3) : prédire les rangs globaux avant per-symbol ──
            _batch_id = _resolve_predict_batch_id(Path(opts.artifacts_dir))
            if _batch_id:
                from modelFactory.predictor import predict_global_rank_history
                LOGGER.info(
                    "predict cascade global_rank_history batch_id=%s start=%s end=%s",
                    _batch_id, cfg.data.training_start_date, cfg.data.training_end_date,
                )
                _gr_results = predict_global_rank_history(
                    start_date=str(cfg.data.training_start_date),
                    end_date=str(cfg.data.training_end_date),
                    batch_id=_batch_id,
                    artifacts_dir=Path(opts.artifacts_dir),
                    engine=engine,
                )
                _gr_total = sum(v for v in _gr_results.values() if v > 0)
                LOGGER.info(
                    "predict cascade global_rank_history DONE — %d dates, %d rows",
                    len(_gr_results), _gr_total,
                )

            prediction_parts = []
            for prediction_date in prediction_dates:
                symbols_for_date = opts.symbols or load_symbols_for_source(
                    engine,
                    opts.symbol_source,
                    trade_date=prediction_date,
                )
                part = predict_batch(
                    symbols_for_date,
                    Path(opts.artifacts_dir),
                    engine,
                    prediction_date=prediction_date,
                    as_of_date=prediction_date,
                    persist=False,
                    accelerator=opts.accelerator,
                    max_workers=opts.max_workers,
                )
                if not part.empty:
                    prediction_parts.append(part)
                    _persist_predictions_chunk(
                        part,
                        operation="insert_predictions_historical_date",
                        prediction_date=prediction_date,
                    )
                else:
                    LOGGER.info(
                        "predict date=%s skipped rows=0 reason=no_valid_predictions", prediction_date.isoformat())
            persisted_incrementally = True
            non_empty_parts = [part for part in prediction_parts if not part.empty]
            preds = (
                pd.concat(non_empty_parts, ignore_index=True)
                if non_empty_parts
                else pd.DataFrame(
                    columns=["symbol", "prediction_date", "predicted_proba", "predicted_class", "run_id"]
                )
            )
        else:
            preds = predict_batch(symbols, Path(opts.artifacts_dir), engine, persist=False, accelerator=opts.accelerator)

        # Sprint S4 (A-021) — drift gate / kill switch ML
        drift_decision = None
        try:
            if (not historical_predict_enabled) and (not preds.empty) and "predicted_proba" in preds.columns:
                today_vals = preds["predicted_proba"].dropna().to_numpy()
                baseline_vals = _load_drift_baseline(engine, days=30)
                if today_vals.size >= 5 and baseline_vals.size >= 30:
                    report = compute_drift(
                        today_vals, baseline_vals,
                        model_id=str(preds.get("model_id", ["batch"]).iloc[0]) if "model_id" in preds.columns else "batch",
                    )
                    drift_decision = evaluate_drift_gate(report)
                    preds = apply_kill_switch(drift_decision, preds)
                    persist_kill_switch_event(drift_decision, engine=engine)
                    update_runtime_status(
                        ml_drift_status=drift_decision.drift_status,
                        ml_kill_switch_active=drift_decision.action == "kill_switch_ml",
                    )
        except Exception as exc:  # pragma: no cover - guarded
            LOGGER.warning("ML drift gate evaluation failed: %s", exc)

        if (
            not preds.empty
            and (drift_decision is None or drift_decision.action != "kill_switch_ml")
            and not persisted_incrementally
        ):
            _persist_predictions_chunk(preds, operation="insert_predictions_batch")
        elif drift_decision is not None and drift_decision.action == "kill_switch_ml":
            LOGGER.warning(
                "predict batch persistence skipped reason=ml_kill_switch_active rows=%d decision=%s",
                len(preds),
                drift_decision.reason,
            )

        print(f"\n{'=' * 60}")
        print(f"  Model Factory — Predictions: {len(preds)} rows")
        if drift_decision is not None:
            print(f"  ML drift status: {drift_decision.drift_status}  gate: {drift_decision.gate}")
        print(f"{'=' * 60}")
        if not preds.empty:
            print(preds.to_string(index=False))
        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        _emit_run_summary(_build_run_summary(
            mode="predict",
            run_id=run_id,
            opts=opts,
            cfg=cfg,
            started_at=started_at,
            finished_at=finished_at,
            symbols_total=len(symbols),
            completed=int(len(preds)),
            skipped=max(0, len(symbols) - int(len(preds))),
            failed=0,
            quarantined=0,
            drift_decision=drift_decision,
        ))


def _load_drift_baseline(engine, *, days: int = 30):
    """Charge la baseline de prédictions pour le drift monitor (best-effort)."""
    import numpy as np
    from sqlalchemy import text
    baseline_start = (datetime.now(timezone.utc) - timedelta(days=int(days))).date()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT predicted_proba FROM model_predictions
                    WHERE prediction_date >= :baseline_start
                      AND predicted_proba IS NOT NULL
                    """
                ),
                {"baseline_start": baseline_start},
            ).fetchall()
        return np.asarray([r[0] for r in rows if r[0] is not None], dtype=float)
    except Exception:  # pragma: no cover - best effort
        import numpy as np
        return np.asarray([], dtype=float)


# ---------------------------------------------------------------------------
# Phase 4.2.h — run_summary ML standardisé.
# ---------------------------------------------------------------------------

def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _build_run_summary(
    *,
    mode: str,
    run_id: str,
    opts: argparse.Namespace,
    cfg: TrainingConfig,
    started_at: datetime,
    finished_at: datetime,
    symbols_total: int,
    completed: int,
    skipped: int,
    failed: int,
    quarantined: int,
    drift_decision: object | None = None,
) -> dict[str, object]:
    from modelFactory.features import fingerprint as compute_feature_fingerprint
    runtime_status = snapshot_runtime_status()
    feature_fp = compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_fundamentals=cfg.data.include_fundamentals_features,
        include_factors=cfg.data.include_factors_features,
        include_macro_regime=cfg.data.include_macro_regime_features,
    )
    payload: dict[str, object] = {
        "run_id": run_id,
        "mode": mode,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "walkforward_enabled": bool(getattr(opts, "walkforward", False)),
        "ml_mode": str(getattr(opts, "ml_mode", "rebuild-all")),
        "training_start_date": cfg.data.training_start_date.isoformat() if cfg.data.training_start_date is not None else None,
        "training_end_date": cfg.data.training_end_date.isoformat() if cfg.data.training_end_date is not None else None,
        "symbol_source": str(getattr(opts, "symbol_source", "tradable-universe")),
        "historical_prediction_range_enabled": bool(mode == "predict" and cfg.data.training_end_date is not None),
        "universe_date": (getattr(opts, "universe_date", None) or cfg.data.training_end_date or date.today()).isoformat(),
        "debug_train_enabled": bool(getattr(opts, "debug_train", False)),
        "heartbeat_interval_seconds": float(getattr(opts, "heartbeat_interval_seconds", DEFAULT_HEARTBEAT_INTERVAL_SECONDS) or 0.0),
        "watchdog_timeout_seconds": int(getattr(opts, "watchdog_timeout_seconds", 0) or 0),
        "last_heartbeat_at": runtime_status.get("last_heartbeat_at"),
        "heartbeat_count": int(runtime_status.get("heartbeat_count", 0) or 0),
        "progress_live": False,
        "progress_label": str(runtime_status.get("progress_label") or "🧠 Progression ML Train"),
        "progress_total": int(runtime_status.get("progress_total", symbols_total) or symbols_total),
        "progress_current": int(runtime_status.get("progress_current", completed + skipped + failed) or (completed + skipped + failed)),
        "progress_item": runtime_status.get("progress_item"),
        "current_symbol": runtime_status.get("current_symbol"),
        "current_symbol_index": int(runtime_status.get("current_symbol_index", 0) or 0),
        "current_symbol_total": int(runtime_status.get("current_symbol_total", symbols_total) or symbols_total),
        "current_phase": runtime_status.get("current_phase"),
        "phase_detail": runtime_status.get("phase_detail"),
        "current_epoch": runtime_status.get("current_epoch"),
        "total_epochs": runtime_status.get("total_epochs"),
        "current_split_index": runtime_status.get("current_split_index"),
        "feature_fingerprint": feature_fp,
        "feature_columns": list(get_feature_columns(
            include_sentiment=cfg.data.include_sentiment_features,
            feature_set=cfg.data.feature_set,
            include_cross_sectional=cfg.data.enable_cross_sectional_features,
            include_screener_scores=cfg.data.include_screener_scores,
            include_short_score=cfg.data.include_short_score_features,
            include_fundamentals=cfg.data.include_fundamentals_features,
            include_factors=cfg.data.include_factors_features,
            include_macro_regime=cfg.data.include_macro_regime_features,
        )),
        "champion_min_runs": int(getattr(opts, "champion_min_runs", 0)),
        "champion_min_days": int(getattr(opts, "champion_min_days", 0)),
        "reproducibility_seed": int(cfg.reproducibility.seed),
        "reproducibility_deterministic": bool(cfg.reproducibility.deterministic),
        "reproducibility_deterministic_applied": bool(runtime_status.get("reproducibility_deterministic_applied", False)),
        "symbols_total": int(symbols_total),
        "symbols_completed": int(completed),
        "symbols_skipped": int(skipped),
        "symbols_failed": int(failed),
        "symbols_quarantined": int(quarantined),
        "prediction_artifact_issue_count": int(runtime_status.get("prediction_artifact_issue_count", 0) or 0),
        "prediction_fallback_count": int(runtime_status.get("prediction_fallback_count", 0) or 0),
        "prediction_calibration_fallback_count": int(runtime_status.get("prediction_calibration_fallback_count", 0) or 0),
        "prediction_db_issue_count": int(runtime_status.get("prediction_db_issue_count", 0) or 0),
        "last_artifact_issue_reason": runtime_status.get("last_artifact_issue_reason"),
        "last_artifact_issue_path": runtime_status.get("last_artifact_issue_path"),
        "last_db_issue_operation": runtime_status.get("last_db_issue_operation"),
        "last_db_issue_reason": runtime_status.get("last_db_issue_reason"),
        "last_fallback_reason": runtime_status.get("last_fallback_reason"),
        "last_requested_model": runtime_status.get("last_requested_model"),
        "last_served_model": runtime_status.get("last_served_model"),
        "last_decision_threshold": runtime_status.get("last_decision_threshold"),
        "last_calibration_method": runtime_status.get("last_calibration_method"),
        "last_prediction_symbol": runtime_status.get("last_prediction_symbol"),
        "last_prediction_date": runtime_status.get("last_prediction_date"),
        "resolved_accelerator": runtime_status.get("resolved_accelerator"),
        "resolved_device_name": runtime_status.get("resolved_device_name"),
    }
    # Sprint S4 (A-021) — exposition policy gate ML drift
    from modelFactory.drift_policy import summary_fields as _drift_summary_fields
    payload.update(_drift_summary_fields(drift_decision))  # type: ignore[arg-type]
    payload["drift_status"] = payload.get("ml_drift_status")
    payload["gate_status"] = "disabled" if bool(payload.get("ml_kill_switch_active")) else "enabled"
    payload["fallback_reason"] = payload.get("last_fallback_reason") or payload.get("last_artifact_issue_reason")
    payload["selected_model"] = payload.get("last_served_model")
    payload["decision_threshold"] = payload.get("last_decision_threshold")
    payload["calibration_method"] = payload.get("last_calibration_method")
    return attach_schema_version(payload, version=1)
