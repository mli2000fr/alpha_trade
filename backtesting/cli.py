"""
backtesting/cli.py
===================
Interface CLI du module de backtesting.

Usage :
    python -m backtesting run --start 2016-01-01 --end 2026-04-20 --equity 100000
    python -m backtesting run --start 2020-01-01 --end 2026-04-20 --equity 50000 --tp 0.10 --ts 0.04
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from common.utils import configure_root_logging

LOGGER = logging.getLogger(__name__)


def _safe_print(*values: object, sep: str = " ", end: str = "\n") -> None:
    """Affiche un message même si stdout n'accepte pas certains caractères Unicode."""
    text = sep.join(str(v) for v in values) + end
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sanitized = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(sanitized)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backtesting",
        description="Backtest intégré Alpha Trade (vectorbt)",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_p = sub.add_parser("run", help="Lancer un backtest complet")
    run_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    run_p.add_argument("--end", default=str(date.today()), help="Date de fin (YYYY-MM-DD)")
    run_p.add_argument("--equity", type=float, default=100_000, help="Capital initial ($)")
    run_p.add_argument("--tp", type=float, default=0.08, help="Take-profit %% (défaut 0.08)")
    run_p.add_argument("--ts", type=float, default=0.05, help="Trailing stop %% (défaut 0.05)")
    run_p.add_argument("--max-positions", type=int, default=20, help="Positions max simultanées")
    run_p.add_argument("--fees", type=float, default=0.001, help="Frais par trade (défaut 0.1%%)")
    run_p.add_argument(
        "--account-type",
        choices=["margin", "cash"],
        default="margin",
        help="Type de compte simulé: margin|cash",
    )
    run_p.add_argument(
        "--pdt-rule",
        choices=["auto", "off"],
        default="auto",
        help="Application de la règle PDT: auto|off",
    )
    run_p.add_argument(
        "--swing-only",
        action="store_true",
        help="Interdire toute sortie le jour même de l'entrée",
    )
    run_p.add_argument("--sentiment-lookback", type=int, default=365, help="Lookback sentiment (jours)")
    run_p.add_argument("--no-save", action="store_true", help="Ne pas sauvegarder les artefacts")
    run_p.add_argument(
        "--ml-mode",
        choices=["auto", "off", "rebuild-missing"],
        default="auto",
        help="Gestion des prédictions ML manquantes: auto|off|rebuild-missing",
    )
    run_p.add_argument(
        "--sentiment-mode",
        choices=["auto", "off", "rebuild-missing"],
        default="auto",
        help="Gestion du sentiment manquant: auto|off|rebuild-missing",
    )
    run_p.add_argument(
        "--artifacts-dir",
        default="artifacts/models",
        help="Répertoire des artefacts modèles pour reconstruire les prédictions ML",
    )
    run_p.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire cible pour sauvegarder les artefacts et le rapport structurés du run",
    )

    # --- backfill-scores-history ---
    backfill_p = sub.add_parser(
        "backfill-scores-history",
        help="Reconstruire stock_scores_history en point-in-time depuis les bars déjà en base",
    )
    backfill_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    backfill_p.add_argument("--end", default=None, help="Date de fin explicite (YYYY-MM-DD)")
    backfill_p.add_argument("--overwrite-existing", action="store_true", help="Recalculer aussi les dates déjà historisées")
    backfill_p.add_argument("--limit-days", type=int, default=None, help="Limiter à N séances (test progressif)")
    backfill_p.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks symboles screener/scanner")
    backfill_p.add_argument("--selection-size", type=int, default=100, help="Nombre final de candidats selector par séance")
    backfill_p.add_argument("--screener-workers", type=int, default=None, help="Nombre de workers ProcessPool pour le screener PIT")

    # --- diagnose-screener ---
    diag_p = sub.add_parser(
        "diagnose-screener",
        help="Mesurer l'impact PIT des paramètres screener jusqu'au portefeuille cible",
    )
    diag_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    diag_p.add_argument("--end", default=str(date.today()), help="Date de fin (YYYY-MM-DD)")
    diag_p.add_argument("--limit-days", type=int, default=None, help="Limiter à N séances (validation incrémentale)")
    diag_p.add_argument("--mode", choices=["oat", "grid"], default="oat", help="Balayage one-at-a-time ou grille complète")
    diag_p.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks symboles screener/scanner")
    diag_p.add_argument("--selection-size", type=int, default=100, help="Nombre final de candidats selector par séance")
    diag_p.add_argument("--max-positions", type=int, default=20, help="Nombre maximum de positions dans le portefeuille cible")
    diag_p.add_argument("--screener-workers", type=int, default=None, help="Nombre de workers ProcessPool pour le screener PIT")
    diag_p.add_argument("--max-scenarios", type=int, default=64, help="Garde-fou sur le nombre total de scénarios en mode grid")
    diag_p.add_argument(
        "--rs-values",
        default="100,102,105",
        help="Liste CSV des seuils min_relative_strength_index à tester",
    )
    diag_p.add_argument(
        "--range-lookback-values",
        default="252,504,756",
        help="Liste CSV des lookbacks historical_range_lookback_days à tester",
    )
    diag_p.add_argument(
        "--historical-range-score-values",
        default="65,70,75",
        help="Liste CSV des seuils min_historical_range_score à tester",
    )
    diag_p.add_argument(
        "--liquidity-threshold-values",
        default="5000000,10000000,20000000",
        help="Liste CSV des seuils liquidity_threshold_usd à tester",
    )
    diag_p.add_argument(
        "--output-dir",
        default="artifacts/screener_diagnostics",
        help="Répertoire cible pour les CSV/JSON diagnostics",
    )

    return parser


def _run_backtest(args: argparse.Namespace) -> None:
    """Exécute le backtest complet."""
    from datetime import datetime

    from database.connection import get_sqlalchemy_engine
    from backtesting.data_loader import load_ohlcv, load_scores, load_predictions, pivot_ohlcv
    from backtesting.resilience import prepare_predictions_for_ml_mode, prepare_scores_for_sentiment_mode
    from backtesting.signal_replay import replay_signals
    from backtesting.trading_constraints import TradingConstraintConfig
    from backtesting.simulator import BacktestConfig, BacktestEngine
    from backtesting.report import (
        extract_diagnostics,
        generate_report,
        save_equity_curve,
        save_equity_curve_csv,
        save_report_json,
        save_trades_csv,
    )

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    trading_constraints = TradingConstraintConfig(
        account_type=args.account_type,
        pdt_rule=args.pdt_rule,
        swing_only=args.swing_only,
    )

    _safe_print(f"\n🚀 Backtest Alpha Trade : {start} → {end}, capital={args.equity:,.0f}$")
    _safe_print(f"   TP={args.tp*100:.1f}%, TS={args.ts*100:.1f}%, max_positions={args.max_positions}\n")
    _safe_print(f"   ml_mode={args.ml_mode}, sentiment_mode={args.sentiment_mode}\n")
    _safe_print(
        "   account_type={} pdt_rule={} swing_only={}\n".format(
            trading_constraints.account_type,
            trading_constraints.effective_pdt_rule,
            trading_constraints.swing_only,
        )
    )
    _safe_print("   convention_exécution=signal J → entrée J+1 au vrai open\n")

    # 1. Charger les données
    engine = get_sqlalchemy_engine()

    _safe_print("📊 Chargement OHLCV...")
    ohlcv_df = load_ohlcv(engine, start, end)
    if ohlcv_df.empty:
        _safe_print("❌ Aucune donnée OHLCV trouvée. Vérifiez la base de données.")
        sys.exit(1)

    _safe_print("📈 Chargement scores...")
    scores_df = load_scores(engine, start, end)
    if scores_df.empty:
        _safe_print("❌ Aucun score candidat trouvé sur la période demandée.")
        _safe_print("   Vérifie d'abord :")
        _safe_print("   - que `stock_scores_history` contient des snapshots historiques ;")
        _safe_print("   - ou, à défaut, que `stock_scores` contient un snapshot récent avec `is_candidate = 1`.")
        _safe_print("   Pour un vrai backtest 10 ans, il faut historiser les snapshots dans `stock_scores_history`.")
        sys.exit(1)

    scores_df = prepare_scores_for_sentiment_mode(
        engine,
        scores_df,
        sentiment_mode=args.sentiment_mode,
    )

    _safe_print("🤖 Chargement prédictions ML...")
    preds_df = load_predictions(engine, start, end)
    preds_df = prepare_predictions_for_ml_mode(
        engine,
        scores_df,
        preds_df,
        ml_mode=args.ml_mode,
        artifacts_dir=Path(args.artifacts_dir),
    )

    # 2. Pivoter OHLCV
    pivoted = pivot_ohlcv(ohlcv_df)

    # 3. Reconstruire les signaux
    _safe_print("🔄 Reconstruction des signaux de conviction...")
    signals_df = replay_signals(
        scores_df, preds_df if not preds_df.empty else None,
        max_positions=args.max_positions,
    )

    # 4. Backtest
    _safe_print("⚡ Exécution du backtest vectorbt...")
    bt_config = BacktestConfig(
        start_date=start, end_date=end,
        initial_equity=args.equity,
        profit_taker_pct=args.tp,
        trailing_stop_pct=args.ts,
        max_positions=args.max_positions,
        fees_pct=args.fees,
        trading_constraints=trading_constraints,
    )
    bt_engine = BacktestEngine(bt_config)
    pf = bt_engine.run(
        open=pivoted["open"], close=pivoted["close"], high=pivoted["high"], low=pivoted["low"],
        signals_df=signals_df,
    )
    diagnostics = extract_diagnostics(pf)

    # 5. Rapport
    report = generate_report(pf, args.equity)
    report.print_summary()

    output_dir = Path(args.output_dir) if args.output_dir else None
    artifact_paths: dict[str, str] = {}

    if output_dir is not None:
        _safe_print("📝 Sauvegarde du rapport structuré...")
        equity_curve_csv_path = save_equity_curve_csv(pf, output_dir=output_dir)
        artifact_paths["equity_curve_csv"] = str(equity_curve_csv_path)
        report_json_path = save_report_json(
            report,
            output_dir=output_dir,
            artifacts=artifact_paths,
            params={
                "start": args.start,
                "end": args.end,
                "equity": args.equity,
                "tp": args.tp,
                "ts": args.ts,
                "max_positions": args.max_positions,
                "fees": args.fees,
                "account_type": trading_constraints.account_type,
                "pdt_rule": trading_constraints.pdt_rule,
                "effective_pdt_rule": trading_constraints.effective_pdt_rule,
                "swing_only": trading_constraints.swing_only,
                "sentiment_lookback": args.sentiment_lookback,
                "ml_mode": args.ml_mode,
                "sentiment_mode": args.sentiment_mode,
                "artifacts_dir": args.artifacts_dir,
                "execution_timing": bt_config.execution_timing,
                "entry_price_source": "next_session_open",
                "no_save": args.no_save,
            },
            diagnostics=diagnostics,
        )
        artifact_paths["report_json"] = str(report_json_path)
        _safe_print(f"   → {report_json_path}")
        _safe_print(f"   → {equity_curve_csv_path}")

    # 6. Artefacts
    if not args.no_save:
        _safe_print("💾 Sauvegarde des artefacts...")
        equity_curve_path = save_equity_curve(pf, output_dir=output_dir)
        trades_csv_path = save_trades_csv(pf, output_dir=output_dir)
        artifact_paths["equity_curve_png"] = str(equity_curve_path)
        artifact_paths["trades_csv"] = str(trades_csv_path)
        _safe_print(f"   → {equity_curve_path}")
        _safe_print(f"   → {trades_csv_path}")

        if output_dir is not None:
            save_report_json(
                report,
                output_dir=output_dir,
                artifacts=artifact_paths,
                params={
                    "start": args.start,
                    "end": args.end,
                    "equity": args.equity,
                    "tp": args.tp,
                    "ts": args.ts,
                    "max_positions": args.max_positions,
                    "fees": args.fees,
                    "account_type": trading_constraints.account_type,
                    "pdt_rule": trading_constraints.pdt_rule,
                    "effective_pdt_rule": trading_constraints.effective_pdt_rule,
                    "swing_only": trading_constraints.swing_only,
                    "sentiment_lookback": args.sentiment_lookback,
                    "ml_mode": args.ml_mode,
                    "sentiment_mode": args.sentiment_mode,
                    "artifacts_dir": args.artifacts_dir,
                    "execution_timing": bt_config.execution_timing,
                    "entry_price_source": "next_session_open",
                    "no_save": args.no_save,
                },
                diagnostics=diagnostics,
            )

    _safe_print("✅ Backtest terminé.\n")


def _run_backfill_scores_history(args: argparse.Namespace) -> None:
    """Exécute le backfill PIT de stock_scores_history."""
    from datetime import datetime

    from backtesting.backfill_scores_history import BackfillScoresHistoryService
    from event_sentiment.signal_aggregator import SentimentBoostConfig
    from screener.models import ScreenerConfig
    from selector.alpha_scanner import AlphaScannerConfig

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else None

    _safe_print(f"\n🧱 Backfill stock_scores_history : start={start} end={end or 'auto'}")
    _safe_print(
        f"   overwrite={args.overwrite_existing} limit_days={args.limit_days or 'all'} "
        f"chunk_size={args.chunk_size} selection_size={args.selection_size}\n"
    )

    service = BackfillScoresHistoryService(
        screener_config=ScreenerConfig(chunk_size=args.chunk_size),
        scanner_config=AlphaScannerConfig.strict_swing_cash(
            chunk_size=args.chunk_size,
            selection_size=args.selection_size,
        ),
        sentiment_config=SentimentBoostConfig(),
        screener_max_workers=args.screener_workers,
    )
    result = service.backfill(
        start_date=start,
        end_date=end,
        overwrite_existing=args.overwrite_existing,
        limit_days=args.limit_days,
    )

    _safe_print("\n✅ Backfill terminé")
    _safe_print(f"   Période résolue     : {result.start_date} → {result.end_date}")
    _safe_print(f"   Séances traitées    : {result.trading_days_processed}/{result.trading_days_requested}")
    _safe_print(f"   Séances ignorées    : {result.trading_days_skipped_existing}")
    _safe_print(f"   Lignes insérées     : {result.rows_inserted}\n")


def _parse_csv_values(raw: str, *, cast_type):
    values = []
    for token in (part.strip() for part in raw.split(",")):
        if not token:
            continue
        values.append(cast_type(token))
    return values


def _run_screener_diagnostics(args: argparse.Namespace) -> None:
    """Exécute le diagnostic PIT phase 4 du screener."""
    from datetime import datetime

    from backtesting.screener_diagnostics import (
        ScreenerDiagnosticsService,
        build_screener_grid_scenarios,
        build_screener_oat_scenarios,
        export_screener_diagnostics,
    )
    from event_sentiment.signal_aggregator import SentimentBoostConfig
    from risk_management.config import RiskConfig
    from screener.models import ScreenerConfig
    from selector.alpha_scanner import AlphaScannerConfig

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    rs_values = _parse_csv_values(args.rs_values, cast_type=float)
    range_values = _parse_csv_values(args.range_lookback_values, cast_type=int)
    hist_score_values = _parse_csv_values(args.historical_range_score_values, cast_type=float)
    liquidity_values = _parse_csv_values(args.liquidity_threshold_values, cast_type=float)

    base_screener_config = ScreenerConfig(chunk_size=args.chunk_size)
    if args.mode == "grid":
        scenarios = build_screener_grid_scenarios(
            base_screener_config,
            rs_values=rs_values,
            range_lookback_values=range_values,
            historical_range_score_values=hist_score_values,
            liquidity_threshold_values=liquidity_values,
            max_scenarios=args.max_scenarios,
        )
    else:
        scenarios = build_screener_oat_scenarios(
            base_screener_config,
            rs_values=rs_values,
            range_lookback_values=range_values,
            historical_range_score_values=hist_score_values,
            liquidity_threshold_values=liquidity_values,
        )

    _safe_print(f"\n🧪 Diagnostic screener phase 4 : {start} → {end}")
    _safe_print(
        f"   mode={args.mode} scénarios={len(scenarios)} limit_days={args.limit_days or 'all'} "
        f"chunk_size={args.chunk_size} selection_size={args.selection_size} max_positions={args.max_positions}\n"
    )

    service = ScreenerDiagnosticsService(
        base_screener_config=base_screener_config,
        scanner_config=AlphaScannerConfig.strict_swing_cash(
            chunk_size=args.chunk_size,
            selection_size=args.selection_size,
        ),
        sentiment_config=SentimentBoostConfig(),
        risk_config=RiskConfig(max_positions=args.max_positions),
        screener_max_workers=args.screener_workers,
    )
    result = service.analyze_period(
        start_date=start,
        end_date=end,
        scenarios=scenarios,
        limit_days=args.limit_days,
    )
    artifacts = export_screener_diagnostics(result, args.output_dir)

    _safe_print("✅ Diagnostic terminé")
    _safe_print(f"   Séances évaluées    : {len(result.trading_dates)}")
    _safe_print(f"   Baseline            : {result.baseline_name}")
    _safe_print(f"   Résumé CSV          : {artifacts['summary_metrics']}")
    _safe_print(f"   Journal quotidien   : {artifacts['daily_metrics']}")
    _safe_print(f"   Scénarios           : {artifacts['scenarios']}")
    _safe_print(f"   Métadonnées         : {artifacts['metadata']}\n")

    if not result.summary_metrics.empty:
        preferred_columns = [
            column
            for column in [
                "scenario_name",
                "days_evaluated",
                "days_failed",
                "selector_candidate_count_mean",
                "portfolio_target_count_mean",
                "portfolio_survival_ratio_mean",
                "selector_forward_return_20d_mean",
                "portfolio_forward_return_20d_mean",
                "delta_portfolio_survival_ratio_mean",
                "delta_portfolio_forward_return_20d_mean",
            ]
            if column in result.summary_metrics.columns
        ]
        preview = result.summary_metrics.loc[:, preferred_columns].copy()
        sort_column = (
            "portfolio_forward_return_20d_mean"
            if "portfolio_forward_return_20d_mean" in preview.columns
            else "portfolio_survival_ratio_mean"
        )
        preview = preview.sort_values(sort_column, ascending=False).head(10)
        _safe_print("Top scénarios (aperçu):")
        _safe_print(preview.to_string(index=False))
        _safe_print()


def main() -> None:
    configure_root_logging()
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        _run_backtest(args)
    elif args.command == "backfill-scores-history":
        _run_backfill_scores_history(args)
    elif args.command == "diagnose-screener":
        _run_screener_diagnostics(args)
    else:
        parser.print_help()
        sys.exit(1)


