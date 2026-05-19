"""Sprint S7 — CLI ``alpha_scanner`` extrait pour alléger le shim."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from common.utils import configure_root_logging
from selector.config import (
    ABLATION_MODE_OFF,
    SUPPORTED_ABLATION_MODES,
    SUPPORTED_DATA_QUALITY_MODES,
    AlphaScannerConfig,
    SelectorAblationPlan,
    load_selector_ablation_plan_from_file,
)
from selector.run_summary import (
    _build_cli_run_summary,
    _emit_run_summary,
    _utc_now_naive,
)
from selector.scanner import AlphaScanner, SelectorDataQualityError

LOGGER = logging.getLogger("selector.alpha_scanner")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AlphaScanner multi-facteurs")
    parser.add_argument("--preset", choices=["strict"], default="strict", help=argparse.SUPPRESS)
    parser.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks de symboles")
    parser.add_argument("--selection-size", type=int, default=50, help="Nombre final de titres à retenir")
    parser.add_argument("--max-workers", type=int, default=None, help="Nombre maximum de threads")
    parser.add_argument("--liquidity-threshold", type=float, default=None, help="Seuil minimal de liquidité en dollar volume moyen 20j")
    parser.add_argument("--min-close", type=float, default=None, help="Prix minimal de clôture")
    parser.add_argument("--max-volatility-ratio", type=float, default=None, help="Seuil maximal optionnel du ratio de volatilité récente vol10/vol60")
    parser.add_argument("--min-relative-strength-index", type=float, default=None, help="Force relative minimale vs SPY (100 = performance égale au benchmark)")
    parser.add_argument("--min-high-52w-proximity", type=float, default=None, help="Proximité minimale du high 52 semaines en ratio close/high_52w")
    parser.add_argument("--min-weekly-trend-score", type=float, default=None, help="Score trend weekly minimal sur [0,1]")
    parser.add_argument("--min-atr-pct-20", type=float, default=None, help="ATR20 minimale en pourcentage du prix, ex. 0.02 = 2%%")
    parser.add_argument("--max-atr-pct-20", type=float, default=None, help="ATR20 maximale en pourcentage du prix, ex. 0.05 = 5%%")
    parser.add_argument("--min-market-cap", type=float, default=None, help="Capitalisation minimale, ex. 2000000000 = 2 Md$")
    parser.add_argument("--min-beta-126", type=float, default=None, help="Beta minimale calculée sur 126 séances vs SPY")
    parser.add_argument("--max-spread-bps", type=float, default=None, help="Spread bid/ask maximal en basis points")
    parser.add_argument(
        "--spread-data-quality-mode",
        choices=sorted(SUPPORTED_DATA_QUALITY_MODES),
        default=None,
        help="Comportement si les données quotes/spread sont indisponibles: block ou warn_skip_filter.",
    )
    parser.add_argument("--earnings-blackout-days", type=int, default=None, help="Exclut les titres dont les résultats tombent dans les N prochains jours")
    parser.add_argument(
        "--earnings-data-quality-mode",
        choices=sorted(SUPPORTED_DATA_QUALITY_MODES),
        default=None,
        help="Comportement si le calendrier earnings est indisponible: block ou warn_skip_filter.",
    )
    parser.add_argument(
        "--market-cap-data-quality-mode",
        choices=sorted(SUPPORTED_DATA_QUALITY_MODES),
        default=None,
        help="Comportement si la fraîcheur market_cap TTL est indisponible: block ou warn_skip_filter.",
    )
    parser.add_argument("--require-above-ma200", action="store_true", default=False, help="Exige latest_close > MA200")
    parser.add_argument("--max-anomaly-count", type=int, default=20, help="Nombre maximum d'anomalies accepté par titre")
    parser.add_argument("--sector-cap-ratio", type=float, default=0.30, help="Plafond par secteur, ex. 0.30 = 30%%")
    parser.add_argument(
        "--ablation-mode",
        choices=sorted(SUPPORTED_ABLATION_MODES),
        default=None,
        help="Mode d'ablation selector: off ou shadow (variantes non persistées, comparées au primaire).",
    )
    parser.add_argument(
        "--ablation-config",
        type=str,
        default=None,
        help="Chemin vers un fichier JSON/YAML décrivant les variantes d'ablation selector.",
    )
    parser.add_argument("--log-level", type=str, default="INFO", help="Niveau de log (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="Date logique du run (YYYY-MM-DD). Utilisée comme snapshot_date pour l'archivage stock_scores_history. Défaut : aujourd'hui.",
    )
    return parser


def _build_config_from_args(args: argparse.Namespace) -> AlphaScannerConfig:
    ablation_plan: SelectorAblationPlan | None = None
    if args.ablation_config:
        ablation_plan = load_selector_ablation_plan_from_file(Path(args.ablation_config))
    if args.ablation_mode is not None:
        if ablation_plan is None:
            ablation_plan = SelectorAblationPlan(mode=args.ablation_mode)
        else:
            ablation_plan = SelectorAblationPlan(
                mode=args.ablation_mode,
                variants=ablation_plan.variants,
                artifact_dir=ablation_plan.artifact_dir,
            )
    if ablation_plan is not None and ablation_plan.mode == ABLATION_MODE_OFF:
        ablation_plan = ablation_plan if ablation_plan.variants else None

    threshold_overrides: dict[str, object] = {}
    if args.liquidity_threshold is not None:
        threshold_overrides["liquidity_threshold"] = args.liquidity_threshold
    if args.min_close is not None:
        threshold_overrides["min_close"] = args.min_close
    if args.max_volatility_ratio is not None:
        threshold_overrides["max_volatility_ratio"] = args.max_volatility_ratio
    if args.min_relative_strength_index is not None:
        threshold_overrides["min_relative_strength_index"] = args.min_relative_strength_index
    if args.min_high_52w_proximity is not None:
        threshold_overrides["min_high_52w_proximity"] = args.min_high_52w_proximity
    if args.min_weekly_trend_score is not None:
        threshold_overrides["min_weekly_trend_score"] = args.min_weekly_trend_score
    if args.min_atr_pct_20 is not None:
        threshold_overrides["min_atr_pct_20"] = args.min_atr_pct_20
    if args.max_atr_pct_20 is not None:
        threshold_overrides["max_atr_pct_20"] = args.max_atr_pct_20
    if args.min_market_cap is not None:
        threshold_overrides["min_market_cap"] = args.min_market_cap
    if args.min_beta_126 is not None:
        threshold_overrides["min_beta_126"] = args.min_beta_126
    if args.max_spread_bps is not None:
        threshold_overrides["max_spread_bps"] = args.max_spread_bps
    if args.spread_data_quality_mode is not None:
        threshold_overrides["spread_data_quality_mode"] = args.spread_data_quality_mode
    if args.earnings_blackout_days is not None:
        threshold_overrides["earnings_blackout_days"] = args.earnings_blackout_days
    if args.earnings_data_quality_mode is not None:
        threshold_overrides["earnings_data_quality_mode"] = args.earnings_data_quality_mode
    if args.market_cap_data_quality_mode is not None:
        threshold_overrides["market_cap_filter_data_quality_mode"] = args.market_cap_data_quality_mode
    if args.require_above_ma200:
        threshold_overrides["require_above_ma200"] = True

    common_kwargs = {
        "chunk_size": args.chunk_size,
        "selection_size": args.selection_size,
        "max_workers": args.max_workers,
        "max_anomaly_count": args.max_anomaly_count,
        "sector_cap_ratio": args.sector_cap_ratio,
        "ablation_plan": ablation_plan,
        **threshold_overrides,
    }

    return AlphaScannerConfig.strict_swing_cash(**common_kwargs)


def main() -> None:
    args = _build_arg_parser().parse_args()
    configure_root_logging(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        log_path="./log/alpha_scanner.log",
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = _build_config_from_args(args)

    started_at = _utc_now_naive()
    scanner = AlphaScanner(config=config)
    scanner.progress_callback = lambda payload: _emit_run_summary(payload)
    if args.trade_date:
        try:
            scanner.snapshot_date_override = date.fromisoformat(args.trade_date.strip())
        except ValueError:
            LOGGER.warning("Argument --trade-date=%r invalide ; fallback date.today().", args.trade_date)
    try:
        result = scanner.run()
    except SelectorDataQualityError as exc:
        finished_at = _utc_now_naive()
        _emit_run_summary(
            _build_cli_run_summary(
                config=config,
                result=pd.DataFrame(),
                started_at=started_at,
                finished_at=finished_at,
                rejected_by_filter={},
                run_status="blocked",
                failure_reason="data_quality_gate_blocked",
                data_quality_gate=exc.payload,
                preselection_rejections=getattr(scanner, "get_last_preselection_audit", lambda: None)(),
                ablation=getattr(scanner, "get_last_ablation_summary", lambda: None)(),
            )
        )
        print("Run bloqué par le data quality gate selector.")
        return
    finished_at = _utc_now_naive()

    rejected_by_filter: dict[str, int] = {}
    getter = getattr(scanner, "get_aggregated_filter_stats", None)
    if callable(getter):
        try:
            rejected_by_filter = {str(k): int(v) for k, v in dict(getter()).items()}
        except Exception:
            rejected_by_filter = {}

    _emit_run_summary(
        _build_cli_run_summary(
            config=config,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
            rejected_by_filter=rejected_by_filter,
            data_quality_gate=getattr(scanner, "get_last_data_quality_gate", lambda: None)(),
            preselection_rejections=getattr(scanner, "get_last_preselection_audit", lambda: None)(),
            ablation=getattr(scanner, "get_last_ablation_summary", lambda: None)(),
        )
    )

    # Sprint S2 (A-017, A-023) — check télémétrie data_source en fin de run.
    try:
        from database.connection import get_sqlalchemy_engine
        from dataIntegrityEngine.data_source_health import check_data_source_homogeneity

        mix_check = check_data_source_homogeneity(get_sqlalchemy_engine())
        _emit_run_summary({"data_source_mix_check": mix_check})
    except Exception:
        LOGGER.debug("data_source_mix_check indisponible (selector).", exc_info=True)

    if result.empty:
        print("Aucun candidat retenu.")
        return

    display_columns = [
        column
        for column in ["rank", "symbol", "sector", "final_score", "trend_score", "vcp_score"]
        if column in result.columns
    ]
    print(result.loc[:, display_columns].to_string(index=False))


__all__ = ["main", "_build_arg_parser", "_build_config_from_args"]

