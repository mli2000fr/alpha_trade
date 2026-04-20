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

from common.utils import configure_root_logging

LOGGER = logging.getLogger(__name__)


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
    run_p.add_argument("--sentiment-lookback", type=int, default=365, help="Lookback sentiment (jours)")
    run_p.add_argument("--no-save", action="store_true", help="Ne pas sauvegarder les artefacts")

    return parser


def _run_backtest(args: argparse.Namespace) -> None:
    """Exécute le backtest complet."""
    from datetime import datetime

    from database.connection import get_sqlalchemy_engine
    from backtesting.data_loader import load_ohlcv, load_scores, load_predictions, pivot_ohlcv
    from backtesting.signal_replay import replay_signals
    from backtesting.simulator import BacktestConfig, BacktestEngine
    from backtesting.report import generate_report, save_equity_curve, save_trades_csv

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    print(f"\n🚀 Backtest Alpha Trade : {start} → {end}, capital={args.equity:,.0f}$")
    print(f"   TP={args.tp*100:.1f}%, TS={args.ts*100:.1f}%, max_positions={args.max_positions}\n")

    # 1. Charger les données
    engine = get_sqlalchemy_engine()

    print("📊 Chargement OHLCV...")
    ohlcv_df = load_ohlcv(engine, start, end)
    if ohlcv_df.empty:
        print("❌ Aucune donnée OHLCV trouvée. Vérifiez la base de données.")
        sys.exit(1)

    print("📈 Chargement scores...")
    scores_df = load_scores(engine, start, end)
    if scores_df.empty:
        print("❌ Aucun score candidat trouvé sur la période demandée.")
        print("   Vérifie d'abord :")
        print("   - que `stock_scores_history` contient des snapshots historiques ;")
        print("   - ou, à défaut, que `stock_scores` contient un snapshot récent avec `is_candidate = 1`.")
        print("   Pour un vrai backtest 10 ans, il faut historiser les snapshots dans `stock_scores_history`.")
        sys.exit(1)

    print("🤖 Chargement prédictions ML...")
    preds_df = load_predictions(engine, start, end)

    # 2. Pivoter OHLCV
    pivoted = pivot_ohlcv(ohlcv_df)

    # 3. Reconstruire les signaux
    print("🔄 Reconstruction des signaux de conviction...")
    signals_df = replay_signals(
        scores_df, preds_df if not preds_df.empty else None,
        max_positions=args.max_positions,
    )

    # 4. Backtest
    print("⚡ Exécution du backtest vectorbt...")
    bt_config = BacktestConfig(
        start_date=start, end_date=end,
        initial_equity=args.equity,
        profit_taker_pct=args.tp,
        trailing_stop_pct=args.ts,
        max_positions=args.max_positions,
        fees_pct=args.fees,
    )
    bt_engine = BacktestEngine(bt_config)
    pf = bt_engine.run(
        close=pivoted["close"], high=pivoted["high"], low=pivoted["low"],
        signals_df=signals_df,
    )

    # 5. Rapport
    report = generate_report(pf, args.equity)
    report.print_summary()

    # 6. Artefacts
    if not args.no_save:
        print("💾 Sauvegarde des artefacts...")
        save_equity_curve(pf)
        save_trades_csv(pf)
        print("   → artifacts/backtesting/equity_curve.png")
        print("   → artifacts/backtesting/trades.csv")

    print("✅ Backtest terminé.\n")


def main() -> None:
    configure_root_logging()
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        _run_backtest(args)
    else:
        parser.print_help()
        sys.exit(1)


