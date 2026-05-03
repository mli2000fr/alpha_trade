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
from typing import cast

from common.capital_presets import (
    apply_backtest_defaults_from_preset,
    build_screener_config_kwargs_from_preset,
    build_selector_config_kwargs_from_preset,
    capital_preset_fingerprint,
    resolve_capital_preset_for_equity,
    resolve_effective_capital_preset,
)
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
    run_p.add_argument(
        "--capital-preset-key",
        default=None,
        help="Preset capital à utiliser pour charger les snapshots PIT et, si non contredit, préremplir les contraintes compte/positions.",
    )
    run_p.add_argument("--tp", type=float, default=0.08, help="Take-profit %% (défaut 0.08)")
    run_p.add_argument("--ts", type=float, default=0.05, help="Trailing stop %% (défaut 0.05)")
    run_p.add_argument("--max-positions", type=int, default=20, help="Positions max simultanées")
    run_p.add_argument(
        "--fees",
        type=float,
        default=None,
        help="DÉPRÉCIÉ — utiliser --commission-bps + --slippage-bps. "
        "Conservé pour rétro-compat : si fourni, écrase commission/slippage.",
    )
    run_p.add_argument(
        "--commission-bps",
        type=float,
        default=5.0,
        help="Commission par trade en bps (défaut: 5.0 = 5bps).",
    )
    run_p.add_argument(
        "--slippage-bps",
        type=float,
        default=5.0,
        help="Slippage simulé par trade en bps (défaut: 5.0 = 5bps).",
    )
    run_p.add_argument(
        "--profile",
        choices=["strict_swing_cash", "swing_cash_aggressive", "custom"],
        default="custom",
        help="Profil consolidé (Phase 6.1.e). Les flags CLI explicites overridrent toujours.",
    )
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
    run_p.add_argument(
        "--score-column",
        choices=["auto", "final_score_walk_forward", "final_score_sentiment", "final_score"],
        default="auto",
        help="Colonne de score à privilégier pour le replay (défaut: auto).",
    )
    run_p.add_argument(
        "--walk-forward-artifacts-dir",
        default=None,
        help="Répertoire racine où chercher explicitement les meilleurs poids walk-forward à appliquer au backtest standard.",
    )
    run_p.add_argument(
        "--engine-mode",
        choices=["research", "pipeline"],
        default="research",
        help="Mode du moteur de backtest: research (rapide, tolérant) ou pipeline (strict PIT, diagnostics renforcés).",
    )
    run_p.add_argument(
        "--ml-pit-strategy",
        choices=["auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"],
        default="auto",
        help="Stratégie PIT explicite pour la composante ML. `auto` conserve le comportement historique, `walk-forward-train-then-predict` fail-fast tant que non supporté.",
    )
    run_p.add_argument(
        "--phase2-mode",
        choices=["off", "risk", "risk_execution"],
        default="off",
        help="Phase 2 opt-in: `risk` branche le vrai risk_management pour générer les cibles, `risk_execution` ajoute en plus une simulation d'intents/fills via execution_engine. Par défaut `off` pour zéro régression.",
    )
    run_p.add_argument(
        "--phase3-mode",
        choices=["off", "execution_replay"],
        default="off",
        help="Phase 3 opt-in: `execution_replay` réinjecte chronologiquement les quantités issues du bridge risk+execution dans le moteur de backtest. Exige `--phase2-mode risk_execution`.",
    )
    run_p.add_argument(
        "--phase4-mode",
        choices=["off", "protection_replay"],
        default="off",
        help="Phase 4 opt-in: `protection_replay` rejoue les child intents de protection (TP/initial stop/trailing) dans le moteur de backtest. Exige `--phase3-mode execution_replay`.",
    )
    run_p.add_argument(
        "--phase5-mode",
        choices=["off", "watcher_replay"],
        default="off",
        help="Phase 5 opt-in: `watcher_replay` rejoue les transitions du watcher de protection (trigger -> promotion trailing) dans le moteur de backtest. Exige `--phase4-mode protection_replay`.",
    )
    run_p.add_argument(
        "--phase7-mode",
        choices=["off", "exit_lifecycle_replay"],
        default="off",
        help="Phase 7 opt-in: `exit_lifecycle_replay` rejoue explicitement l'issue terminale des child orders (exit + annulation OCO du sibling) dans le moteur de backtest. Exige `--phase5-mode watcher_replay`.",
    )
    # Phase A.6 (refactor) — risk-free rate annualisé pour Sharpe/Sortino.
    run_p.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.0,
        help="Taux sans risque annualisé (ex 0.04 = 4%%) déduit des returns avant Sharpe/Sortino.",
    )
    # Phase A.4 — seed pour reproductibilité (consigné dans run_metadata).
    run_p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed reproductibilité (consignée dans report.json[run_metadata]).",
    )

    # ------------------------------------------------------------------
    # Phase B (refactor) — micro-structure (slippage volume-aware,
    # initial stop dur, gap filter, intra-bar priority).
    # ------------------------------------------------------------------
    run_p.add_argument(
        "--slippage-model",
        choices=["fixed", "linear", "sqrt"],
        default="fixed",
        help="Modèle de slippage volume-aware additionnel (Phase B.1). 'fixed' = neutre.",
    )
    run_p.add_argument(
        "--slippage-base-bps",
        type=float,
        default=0.0,
        help="Composante fixe (bps) du slippage volume-aware additionnel.",
    )
    run_p.add_argument(
        "--slippage-impact-coef",
        type=float,
        default=0.0,
        help="Coefficient d'impact (bps) appliqué à size/ADV (Phase B.1).",
    )
    run_p.add_argument(
        "--initial-stop-pct",
        type=float,
        default=0.0,
        help="Stop-loss initial dur en fraction (Phase B.2). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--max-entry-gap-pct",
        type=float,
        default=0.0,
        help="Skip d'entrée si |open - prev_close| / prev_close > seuil (Phase B.3). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--intrabar-priority",
        choices=["conservative", "tp_first", "ts_first", "random"],
        default="conservative",
        help="Politique de résolution intra-bar TP/TS (Phase B.4). conservative = TS prioritaire (legacy).",
    )

    # ------------------------------------------------------------------
    # Phase C (refactor) — risk overlays (sizing, regime, sectoral, DD breaker, vol-target).
    # ------------------------------------------------------------------
    run_p.add_argument(
        "--sizing-mode",
        choices=["equal_weight", "conviction_weighted"],
        default="equal_weight",
        help="Mode de sizing du portefeuille (Phase C.1).",
    )
    run_p.add_argument(
        "--sizing-min-weight-pct",
        type=float,
        default=0.005,
        help="Poids min par position quand sizing=conviction_weighted (Phase C.1).",
    )
    run_p.add_argument(
        "--sizing-max-weight-pct",
        type=float,
        default=0.20,
        help="Poids max par position quand sizing=conviction_weighted (Phase C.1).",
    )
    run_p.add_argument(
        "--regime-filter",
        action="store_true",
        help="Active le filtre régime SMA200 sur le benchmark (Phase C.3).",
    )
    run_p.add_argument(
        "--regime-sma-window",
        type=int,
        default=200,
        help="Fenêtre SMA pour le filtre régime (défaut 200).",
    )
    run_p.add_argument(
        "--regime-bear-threshold",
        type=float,
        default=-0.02,
        help="Seuil bear (distance vs SMA) pour bloquer les nouvelles entrées.",
    )
    run_p.add_argument(
        "--max-sector-exposure-pct",
        type=float,
        default=0.0,
        help="Cap d'exposition par secteur en fraction (Phase C.4). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--max-portfolio-dd-pct",
        type=float,
        default=0.0,
        help="Drawdown max avant coupe-circuit nouvelles entrées (Phase C.5). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--dd-recovery-pct",
        type=float,
        default=0.95,
        help="Seuil de recovery pour rouvrir les entrées après coupe-circuit DD (Phase C.5).",
    )
    run_p.add_argument(
        "--target-annual-vol",
        type=float,
        default=None,
        help="Cible de volatilité annualisée portefeuille (Phase C.2). Désactivé si non fourni.",
    )

    # --- backfill-scores-history ---
    backfill_p = sub.add_parser(
        "backfill-scores-history",
        help="Reconstruire stock_scores_history en point-in-time depuis les bars déjà en base",
    )
    backfill_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    backfill_p.add_argument("--end", default=None, help="Date de fin explicite (YYYY-MM-DD)")
    backfill_p.add_argument("--capital", type=float, default=None, help="Capital de référence pour résoudre automatiquement un preset")
    backfill_p.add_argument("--capital-preset-key", default=None, help="Preset capital explicite à utiliser pour reconstruire les snapshots PIT")
    backfill_p.add_argument("--overwrite-existing", action="store_true", help="Recalculer aussi les dates déjà historisées")
    backfill_p.add_argument("--limit-days", type=int, default=None, help="Limiter à N séances (test progressif)")
    backfill_p.add_argument("--chunk-size", type=int, default=1000, help="Taille des chunks symboles screener/scanner")
    backfill_p.add_argument("--selection-size", type=int, default=100, help="Nombre final de candidats selector par séance")
    backfill_p.add_argument("--screener-workers", type=int, default=4, help="Nombre de workers ProcessPool pour le screener PIT")

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
    diag_p.add_argument(
        "--holdout-train-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre d'entraînement (YYYY-MM-DD). Active la validation hold-out.",
    )
    diag_p.add_argument(
        "--holdout-test-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre de test (YYYY-MM-DD).",
    )

    # --- recommend-screener ---
    recommend_p = sub.add_parser(
        "recommend-screener",
        help="Analyser summary_metrics.csv et recommander automatiquement le meilleur compromis",
    )
    recommend_p.add_argument(
        "--input-dir",
        default="artifacts/screener_diagnostics",
        help="Répertoire contenant summary_metrics.csv et éventuellement daily_metrics.csv",
    )
    recommend_p.add_argument(
        "--summary-csv",
        default=None,
        help="Chemin explicite vers un summary_metrics.csv à analyser",
    )
    recommend_p.add_argument(
        "--daily-csv",
        default=None,
        help="Chemin explicite vers un daily_metrics.csv pour enrichir l'analyse de robustesse",
    )
    recommend_p.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire cible pour scenario_recommendations.csv et recommendation_summary.json",
    )
    recommend_p.add_argument(
        "--baseline-name",
        default=None,
        help="Nom explicite du scénario baseline si l'auto-détection n'est pas suffisante",
    )
    recommend_p.add_argument(
        "--target-horizon",
        type=int,
        default=20,
        help="Horizon forward prioritaire pour l'analyse du compromis (défaut: 20)",
    )
    recommend_p.add_argument(
        "--holdout-train-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre d'entraînement (YYYY-MM-DD). Active la validation hold-out.",
    )
    recommend_p.add_argument(
        "--holdout-test-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre de test (YYYY-MM-DD).",
    )

    calibrate_p = sub.add_parser(
        "calibrate-sentiment-weights",
        help="Calibrer les poids sentiment/macro à partir de stock_scores_history et des forward returns.",
    )
    calibrate_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    calibrate_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    calibrate_p.add_argument("--top-n", type=int, default=20, help="Nombre de symboles retenus par jour pour mesurer le spread")
    calibrate_p.add_argument("--horizons", default="5,10,20", help="Horizons forward CSV à évaluer")
    calibrate_p.add_argument(
        "--output-dir",
        default="artifacts/sentiment_calibration",
        help="Répertoire cible pour les artefacts de calibration",
    )
    calibrate_p.add_argument(
        "--all-symbols",
        action="store_true",
        help="Utiliser tout l'univers historisé et pas seulement les candidats",
    )

    walk_forward_p = sub.add_parser(
        "walk-forward-sentiment",
        help="Calibration walk-forward stricte des poids sentiment/macro avec backtest portefeuille hors échantillon.",
    )
    walk_forward_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    walk_forward_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    walk_forward_p.add_argument("--top-n", type=int, default=20, help="Nombre de titres retenus pour les métriques de calibration")
    walk_forward_p.add_argument("--horizons", default="5,10,20", help="Horizons forward CSV à évaluer")
    walk_forward_p.add_argument("--min-train-days", type=int, default=252, help="Séances minimales d'entraînement par fold")
    walk_forward_p.add_argument("--test-days", type=int, default=63, help="Séances hors échantillon par fold")
    walk_forward_p.add_argument("--step-days", type=int, default=None, help="Décalage entre folds (défaut = test-days)")
    walk_forward_p.add_argument("--max-positions", type=int, default=20, help="Nombre maximal de positions simultanées")
    walk_forward_p.add_argument("--equity", type=float, default=100_000, help="Capital initial ($)")
    walk_forward_p.add_argument("--tp", type=float, default=0.08, help="Take-profit %%)")
    walk_forward_p.add_argument("--ts", type=float, default=0.05, help="Trailing stop %%)")
    walk_forward_p.add_argument("--fees", type=float, default=0.001, help="Frais par trade (défaut 0.1%%)")
    walk_forward_p.add_argument(
        "--output-dir",
        default="artifacts/sentiment_walk_forward",
        help="Répertoire cible pour les artefacts walk-forward",
    )
    walk_forward_p.add_argument(
        "--all-symbols",
        action="store_true",
        help="Utiliser tout l'univers historisé et pas seulement les candidats",
    )

    return parser


def _explicit_flags(argv: list[str]) -> set[str]:
    """Retourne les noms d'attributs argparse explicitement passés sur la ligne de commande."""
    explicit: set[str] = set()
    mapping = {
        "--tp": "tp",
        "--ts": "ts",
        "--max-positions": "max_positions",
        "--chunk-size": "chunk_size",
        "--selection-size": "selection_size",
        "--commission-bps": "commission_bps",
        "--slippage-bps": "slippage_bps",
        "--account-type": "account_type",
        "--pdt-rule": "pdt_rule",
        "--swing-only": "swing_only",
        "--fees": "fees",
        "--capital-preset-key": "capital_preset_key",
        "--capital": "capital",
    }
    for token in argv:
        key = token.split("=", 1)[0]
        if key in mapping:
            explicit.add(mapping[key])
    return explicit


def _run_backtest(args: argparse.Namespace) -> None:
    """Exécute le backtest complet."""
    from datetime import datetime

    import pandas as pd

    from backtesting.fidelity import (
        PitHistoryRequiredError,
        PitMlStrategyUnsupportedError,
        build_fidelity_manifest,
        save_fidelity_manifest,
    )
    from database.connection import get_sqlalchemy_engine
    from backtesting.data_loader import load_ohlcv, load_scores, load_predictions, pivot_ohlcv
    from backtesting.resilience import prepare_predictions_for_ml_mode, prepare_scores_for_sentiment_mode
    from backtesting.signal_replay import replay_signals
    from backtesting.trading_constraints import TradingConstraintConfig
    from backtesting.simulator import BacktestConfig, BacktestEngine
    from backtesting.microstructure import MicrostructureConfig, SlippageConfig
    from backtesting.risk_overlay import (
        DrawdownCircuitBreaker,
        RegimeFilterConfig,
        RiskOverlayConfig,
        SectoralCapConfig,
        SizingConfig,
    )
    from backtesting.profiles import apply_profile
    from backtesting.run_metadata import build_run_metadata
    from backtesting.report import (
        extract_diagnostics,
        generate_report,
        load_dividends_received,
        save_equity_curve,
        save_equity_curve_csv,
        save_report_json,
        save_trades_csv,
    )

    # Phase 6.1.e — appliquer le profil avant tout (sans écraser les flags explicites).
    explicit_flags = _explicit_flags(sys.argv[1:])
    apply_profile(args, getattr(args, "profile", None), explicit_flags=explicit_flags)

    effective_preset, preset_source = resolve_effective_capital_preset(
        capital_preset_key=getattr(args, "capital_preset_key", None),
        equity=float(getattr(args, "equity", 0.0) or 0.0),
    )
    detected_from_equity = resolve_capital_preset_for_equity(float(getattr(args, "equity", 0.0) or 0.0))
    if preset_source == "explicit_key" and detected_from_equity is not None and detected_from_equity.key != effective_preset.key:
        _safe_print(
            f"⚠️ Preset explicite `{effective_preset.key}` prioritaire sur le bucket détecté depuis equity `{detected_from_equity.key}`."
        )
    args.capital_preset_key = effective_preset.key
    if preset_source == "explicit_key":
        preset_applied_values = apply_backtest_defaults_from_preset(vars(args), effective_preset, explicit_flags=explicit_flags)
        for field_name, value in preset_applied_values.items():
            setattr(args, field_name, value)
    preset_fingerprint = capital_preset_fingerprint(effective_preset)

    # Phase 6.1.b — gestion --fees (déprécié) vs commission/slippage_bps.
    if args.fees is not None:
        import warnings as _warnings
        _warnings.warn(
            "--fees est déprécié (Phase 6.1.b). Utiliser --commission-bps + --slippage-bps.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Convertit fees pct (ex 0.001 = 10bps) en bps total côté commission.
        total_bps = float(args.fees) * 10_000.0
        args.commission_bps = total_bps
        args.slippage_bps = 0.0
    fees_pct = (float(args.commission_bps) + float(args.slippage_bps)) / 10_000.0

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    engine_mode = str(getattr(args, "engine_mode", "research") or "research").strip().lower()
    ml_pit_strategy = str(getattr(args, "ml_pit_strategy", "auto") or "auto").strip().lower()
    phase2_mode = str(getattr(args, "phase2_mode", "off") or "off").strip().lower()
    phase3_mode = str(getattr(args, "phase3_mode", "off") or "off").strip().lower()
    phase4_mode = str(getattr(args, "phase4_mode", "off") or "off").strip().lower()
    phase5_mode = str(getattr(args, "phase5_mode", "off") or "off").strip().lower()
    phase7_mode = str(getattr(args, "phase7_mode", "off") or "off").strip().lower()
    strict_pit = engine_mode == "pipeline"

    if phase3_mode != "off" and phase2_mode != "risk_execution":
        _safe_print(
            "❌ La Phase 3 `execution_replay` exige `--phase2-mode risk_execution` pour disposer des cibles et fills d'exécution."
        )
        sys.exit(1)
    if phase4_mode != "off" and phase3_mode != "execution_replay":
        _safe_print(
            "❌ La Phase 4 `protection_replay` exige `--phase3-mode execution_replay` pour disposer d'un calendrier d'exécution rejouable."
        )
        sys.exit(1)
    if phase5_mode != "off" and phase4_mode != "protection_replay":
        _safe_print(
            "❌ La Phase 5 `watcher_replay` exige `--phase4-mode protection_replay` pour disposer des protections rejouées."
        )
        sys.exit(1)
    if phase7_mode != "off" and phase5_mode != "watcher_replay":
        _safe_print(
            "❌ La Phase 7 `exit_lifecycle_replay` exige `--phase5-mode watcher_replay` pour disposer du lifecycle du watcher."
        )
        sys.exit(1)

    trading_constraints = TradingConstraintConfig(
        account_type=args.account_type,
        pdt_rule=args.pdt_rule,
        swing_only=args.swing_only,
    )

    _safe_print(f"\n🚀 Backtest Alpha Trade : {start} → {end}, capital={args.equity:,.0f}$")
    _safe_print(f"   preset_capital={effective_preset.key} ({preset_source}) | fingerprint={preset_fingerprint}\n")
    _safe_print(f"   TP={args.tp*100:.1f}%, TS={args.ts*100:.1f}%, max_positions={args.max_positions}\n")
    _safe_print(f"   engine_mode={engine_mode} strict_pit={strict_pit}\n")
    _safe_print(f"   phase2_mode={phase2_mode}\n")
    _safe_print(f"   phase3_mode={phase3_mode}\n")
    _safe_print(f"   phase4_mode={phase4_mode}\n")
    _safe_print(f"   phase5_mode={phase5_mode}\n")
    _safe_print(f"   phase7_mode={phase7_mode}\n")
    _safe_print(f"   ml_mode={args.ml_mode}, sentiment_mode={args.sentiment_mode}\n")
    _safe_print(f"   ml_pit_strategy={ml_pit_strategy}\n")
    _safe_print(
        "   score_column={} walk_forward_artifacts_dir={}\n".format(
            args.score_column,
            args.walk_forward_artifacts_dir or "auto-disabled",
        )
    )
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
    try:
        score_load_result = load_scores(
            engine,
            start,
            end,
            capital_preset_key=effective_preset.key,
            strict_pit=strict_pit,
            return_diagnostics=True,
        )
    except PitHistoryRequiredError as exc:
        _safe_print(f"❌ {exc}")
        _safe_print("   En mode `pipeline`, le backtest exige des snapshots PIT historisés dans `stock_scores_history`.")
        sys.exit(1)
    scores_df = score_load_result.frame
    score_load_diagnostics = score_load_result.diagnostics
    if scores_df.empty:
        _safe_print("❌ Aucun score candidat trouvé sur la période demandée.")
        _safe_print("   Vérifie d'abord :")
        _safe_print("   - que `stock_scores_history` contient des snapshots historiques ;")
        _safe_print("   - ou, à défaut, que `stock_scores` contient un snapshot récent avec `is_candidate = 1`.")
        _safe_print("   Pour un vrai backtest 10 ans, il faut historiser les snapshots dans `stock_scores_history`.")
        sys.exit(1)

    prepared_scores = prepare_scores_for_sentiment_mode(
        engine,
        scores_df,
        sentiment_mode=args.sentiment_mode,
        walk_forward_artifacts_dir=Path(args.walk_forward_artifacts_dir) if args.walk_forward_artifacts_dir else None,
        engine_mode=engine_mode,
        return_diagnostics=True,
    )
    if hasattr(prepared_scores, "frame") and hasattr(prepared_scores, "diagnostics"):
        scores_df = prepared_scores.frame
        sentiment_diagnostics = prepared_scores.diagnostics
    else:
        scores_df = prepared_scores
        sentiment_diagnostics = None

    _safe_print("🤖 Chargement prédictions ML...")
    preds_df = load_predictions(engine, start, end)
    try:
        prepared_predictions = prepare_predictions_for_ml_mode(
            engine,
            scores_df,
            preds_df,
            ml_mode=args.ml_mode,
            artifacts_dir=Path(args.artifacts_dir),
            engine_mode=engine_mode,
            ml_pit_strategy=ml_pit_strategy,
            return_diagnostics=True,
        )
    except PitMlStrategyUnsupportedError as exc:
        _safe_print(f"❌ {exc}")
        sys.exit(1)
    if hasattr(prepared_predictions, "frame") and hasattr(prepared_predictions, "diagnostics"):
        preds_df = prepared_predictions.frame
        ml_diagnostics = prepared_predictions.diagnostics
    else:
        preds_df = prepared_predictions
        ml_diagnostics = None

    # 2. Pivoter OHLCV
    pivoted = pivot_ohlcv(ohlcv_df)

    # 3. Reconstruire les signaux
    _safe_print("🔄 Reconstruction des signaux de conviction...")
    phase2_risk_result = None
    phase2_execution_result = None
    phase3_execution_replay_result = None
    phase4_protection_replay_result = None
    phase5_watcher_replay_result = None
    phase7_exit_lifecycle_result = None
    phase2_risk_run_id = f"bt_phase2_{start:%Y%m%d}_{end:%Y%m%d}"
    if phase2_mode == "off":
        signals_df = replay_signals(
            scores_df, preds_df if not preds_df.empty else None,
            score_column=None if args.score_column == "auto" else args.score_column,
            max_positions=args.max_positions,
        )
    else:
        from backtesting.risk_bridge import build_phase2_risk_result
        from risk_management.config import RiskConfig

        phase2_risk_result = build_phase2_risk_result(
            scores_df=scores_df,
            predictions_df=preds_df if isinstance(preds_df, pd.DataFrame) else pd.DataFrame(),
            close_df=pivoted["close"],
            high_df=pivoted["high"],
            low_df=pivoted["low"],
            risk_config=RiskConfig(
                account_equity=float(args.equity),
                max_positions=int(args.max_positions),
            ),
        )
        signals_df = phase2_risk_result.signals_df
        _safe_print(
            "   Phase 2 risk bridge: snapshots={} entries={} accepted={} signals={}\n".format(
                phase2_risk_result.diagnostics.get("snapshot_dates", 0),
                phase2_risk_result.diagnostics.get("entries_total", 0),
                phase2_risk_result.diagnostics.get("entries_accepted", 0),
                phase2_risk_result.diagnostics.get("signals_generated", 0),
            )
        )
        if phase2_mode == "risk_execution":
            from execution_engine.config import ExecutionConfig

            execution_config = ExecutionConfig(
                broker_mode="paper",
                dry_run=True,
                account_type=args.account_type,
                pdt_rule=args.pdt_rule,
                swing_only=args.swing_only,
                simulated_account_equity=float(args.equity),
                profit_taker_pct=float(args.tp),
                trailing_stop_pct=float(args.ts),
            )
            if phase3_mode == "execution_replay":
                from backtesting.execution_replay import simulate_phase3_execution_replay

                phase3_execution_replay_result = simulate_phase3_execution_replay(
                    phase2_risk_result.entries,
                    execution_config=execution_config,
                    open_df=pivoted["open"],
                    risk_run_id_prefix=phase2_risk_run_id,
                )
                phase2_execution_result = phase3_execution_replay_result.execution_result
                signals_df = phase3_execution_replay_result.signals_df
                if phase4_mode == "protection_replay":
                    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay

                    phase4_protection_replay_result = build_phase4_protection_replay(
                        phase3_execution_replay_result,
                        execution_config=execution_config,
                    )
                    signals_df = phase4_protection_replay_result.signals_df
                    if phase5_mode == "watcher_replay":
                        from backtesting.protection_watcher_replay import build_phase5_watcher_replay

                        phase5_watcher_replay_result = build_phase5_watcher_replay(
                            phase4_protection_replay_result,
                            high_df=pivoted["high"],
                        )
                        signals_df = phase5_watcher_replay_result.signals_df
                        if phase7_mode == "exit_lifecycle_replay":
                            from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay

                            phase7_exit_lifecycle_result = build_phase7_exit_lifecycle_replay(
                                phase5_watcher_replay_result,
                                high_df=pivoted["high"],
                                low_df=pivoted["low"],
                                intrabar_priority=args.intrabar_priority,
                            )
                            signals_df = phase7_exit_lifecycle_result.signals_df
                            _safe_print(
                                "   Phase 7 exit lifecycle replay: exits={} oco_cancels={} trailing={}\n".format(
                                    phase7_exit_lifecycle_result.diagnostics.get("exit_rows", 0),
                                    phase7_exit_lifecycle_result.diagnostics.get("oco_cancels", 0),
                                    phase7_exit_lifecycle_result.diagnostics.get("filled_trailing_stop", 0),
                                )
                            )
                        _safe_print(
                            "   Phase 5 watcher replay: transitions={} pending={} failed={}\n".format(
                                phase5_watcher_replay_result.diagnostics.get("transitioned_items", 0),
                                phase5_watcher_replay_result.diagnostics.get("pending_items", 0),
                                phase5_watcher_replay_result.diagnostics.get("failed_items", 0),
                            )
                        )
                    _safe_print(
                        "   Phase 4 protection replay: protections={} trailing={} initial_stop={}\n".format(
                            phase4_protection_replay_result.diagnostics.get("protections_replayed", 0),
                            phase4_protection_replay_result.diagnostics.get("trailing_stop_protections", 0),
                            phase4_protection_replay_result.diagnostics.get("initial_stop_protections", 0),
                        )
                    )
                _safe_print(
                    "   Phase 3 execution replay: scheduled_entries={} signals={} skipped_no_next_session={}\n".format(
                        phase3_execution_replay_result.diagnostics.get("scheduled_entries", 0),
                        phase3_execution_replay_result.diagnostics.get("signals_generated", 0),
                        phase3_execution_replay_result.diagnostics.get("skipped_no_next_session", 0),
                    )
                )
            else:
                from backtesting.execution_bridge import simulate_phase2_execution

                phase2_execution_result = simulate_phase2_execution(
                    phase2_risk_result.entries,
                    execution_config=execution_config,
                    trade_date=end,
                    risk_run_id=phase2_risk_run_id,
                )
            _safe_print(
                "   Phase 2 execution bridge: targets={} entry_intents={} child_intents={} fills={}\n".format(
                    phase2_execution_result.diagnostics.get("targets", 0),
                    phase2_execution_result.diagnostics.get("entry_intents", 0),
                    phase2_execution_result.diagnostics.get("child_intents", 0),
                    phase2_execution_result.diagnostics.get("fills", 0),
                )
            )

    # 4. Backtest
    _safe_print("⚡ Exécution du backtest vectorbt...")

    # Phase B/C (refactor) — construire les bundles micro-structure et risk overlay
    # depuis les flags CLI. Tout est neutre par défaut (legacy preserved).
    microstructure_cfg = MicrostructureConfig(
        slippage=SlippageConfig(
            base_bps=float(args.slippage_base_bps),
            impact_coef=float(args.slippage_impact_coef),
            model=args.slippage_model,
        ),
        initial_stop_pct=float(args.initial_stop_pct),
        max_entry_gap_pct=float(args.max_entry_gap_pct),
        intrabar_priority=args.intrabar_priority,
    )
    risk_overlay_cfg = RiskOverlayConfig(
        sizing=SizingConfig(
            mode=args.sizing_mode,
            min_weight_pct=float(args.sizing_min_weight_pct),
            max_weight_pct=float(args.sizing_max_weight_pct),
        ),
        regime_filter=RegimeFilterConfig(
            enabled=bool(args.regime_filter),
            sma_window=int(args.regime_sma_window),
            bear_threshold=float(args.regime_bear_threshold),
        ),
        sectoral_cap=SectoralCapConfig(
            enabled=float(args.max_sector_exposure_pct) > 0.0,
            max_sector_exposure_pct=float(args.max_sector_exposure_pct) or 0.40,
        ),
        drawdown_breaker=DrawdownCircuitBreaker(
            enabled=float(args.max_portfolio_dd_pct) > 0.0,
            max_dd_pct=float(args.max_portfolio_dd_pct) or 0.20,
            recovery_pct=float(args.dd_recovery_pct),
        ),
        target_annual_vol=(
            float(args.target_annual_vol) if args.target_annual_vol is not None else None
        ),
    )

    bt_config = BacktestConfig(
        start_date=start, end_date=end,
        initial_equity=args.equity,
        profit_taker_pct=args.tp,
        trailing_stop_pct=args.ts,
        max_positions=args.max_positions,
        fees_pct=fees_pct,
        commission_bps=float(args.commission_bps),
        slippage_bps=float(args.slippage_bps),
        trading_constraints=trading_constraints,
        microstructure=microstructure_cfg,
        risk_overlay=risk_overlay_cfg,
        seed=getattr(args, "seed", None),
        execution_replay_mode=phase3_mode,
        protection_replay_mode=phase4_mode,
        watcher_replay_mode=phase5_mode,
        exit_lifecycle_replay_mode=phase7_mode,
    )
    bt_engine = BacktestEngine(bt_config)
    pf = bt_engine.run(
        open=pivoted["open"], close=pivoted["close"], high=pivoted["high"], low=pivoted["low"],
        signals_df=signals_df,
    )
    diagnostics = extract_diagnostics(pf)

    # Phase 6.1.c — dividendes encaissés (best-effort, fallback 0.0 si DB indispo).
    dividends_received = load_dividends_received(start, end, engine=engine)

    # 5. Rapport
    report = generate_report(
        pf,
        args.equity,
        dividends_received=dividends_received,
        risk_free_rate=float(getattr(args, "risk_free_rate", 0.0) or 0.0),
    )
    report.print_summary()

    output_dir = Path(args.output_dir) if args.output_dir else None
    artifact_paths: dict[str, str] = {}
    fidelity_manifest = build_fidelity_manifest(
        engine_mode=engine_mode,
        start_date=start,
        end_date=end,
        capital_preset_key=effective_preset.key,
        score_diagnostics=score_load_diagnostics,
        sentiment_diagnostics=sentiment_diagnostics,
        ml_diagnostics=ml_diagnostics,
        sentiment_mode=args.sentiment_mode,
        ml_mode=args.ml_mode,
        ml_pit_strategy=ml_pit_strategy,
    )

    common_params: dict[str, object] = {
        "start": args.start,
        "end": args.end,
        "equity": args.equity,
        "tp": args.tp,
        "ts": args.ts,
        "max_positions": args.max_positions,
        # Phase 6.1.b — costs/slippage explicites + rétro-compat fees.
        "commission_bps": float(args.commission_bps),
        "slippage_bps": float(args.slippage_bps),
        "fees_pct": fees_pct,
        "fees": args.fees,  # legacy : conserve la valeur fournie (None si absent).
        # Phase 6.1.e — profil utilisé.
        "profile": getattr(args, "profile", "custom"),
        "capital_preset_key": effective_preset.key,
        "capital_preset_source": preset_source,
        "capital_preset_fingerprint": preset_fingerprint,
        "engine_mode": engine_mode,
        "phase2_mode": phase2_mode,
        "phase3_mode": phase3_mode,
        "phase4_mode": phase4_mode,
        "phase5_mode": phase5_mode,
        "phase7_mode": phase7_mode,
        "ml_pit_strategy": ml_pit_strategy,
        # Phase 6.1.a — fusion conviction unifiée via core.conviction.
        "conviction_weights": {
            "source": "core.conviction",
            "score_weight": 0.40,
            "prediction_weight": 0.60,
        },
        # Phase 6.1.c — dividendes encaissés.
        "dividends_received": float(dividends_received),
        "account_type": trading_constraints.account_type,
        "pdt_rule": trading_constraints.pdt_rule,
        "effective_pdt_rule": trading_constraints.effective_pdt_rule,
        "swing_only": trading_constraints.swing_only,
        "sentiment_lookback": args.sentiment_lookback,
        "ml_mode": args.ml_mode,
        "sentiment_mode": args.sentiment_mode,
        "artifacts_dir": args.artifacts_dir,
        "score_column": args.score_column,
        "walk_forward_artifacts_dir": args.walk_forward_artifacts_dir,
        "execution_timing": bt_config.execution_timing,
        "entry_price_source": "next_session_open",
        "no_save": args.no_save,
        # Phase A.6 — risk-free rate utilisé pour Sharpe/Sortino.
        "risk_free_rate": float(getattr(args, "risk_free_rate", 0.0) or 0.0),
        # Phase B (refactor) — micro-structure activable via CLI.
        "microstructure": {
            "slippage_model": args.slippage_model,
            "slippage_base_bps": float(args.slippage_base_bps),
            "slippage_impact_coef": float(args.slippage_impact_coef),
            "initial_stop_pct": float(args.initial_stop_pct),
            "max_entry_gap_pct": float(args.max_entry_gap_pct),
            "intrabar_priority": args.intrabar_priority,
            "is_default": microstructure_cfg.is_default(),
        },
        # Phase C (refactor) — risk overlays activables via CLI.
        "risk_overlay": {
            "sizing_mode": args.sizing_mode,
            "sizing_min_weight_pct": float(args.sizing_min_weight_pct),
            "sizing_max_weight_pct": float(args.sizing_max_weight_pct),
            "regime_filter_enabled": bool(args.regime_filter),
            "regime_sma_window": int(args.regime_sma_window),
            "regime_bear_threshold": float(args.regime_bear_threshold),
            "max_sector_exposure_pct": float(args.max_sector_exposure_pct),
            "max_portfolio_dd_pct": float(args.max_portfolio_dd_pct),
            "dd_recovery_pct": float(args.dd_recovery_pct),
            "target_annual_vol": (
                float(args.target_annual_vol) if args.target_annual_vol is not None else None
            ),
            "is_default": risk_overlay_cfg.is_default(),
        },
        "phase2": {
            "enabled": phase2_mode != "off",
            "mode": phase2_mode,
            "risk_bridge": phase2_risk_result.diagnostics if phase2_risk_result is not None else None,
            "execution_bridge": phase2_execution_result.diagnostics if phase2_execution_result is not None else None,
            "execution_tca": phase2_execution_result.tca_summary if phase2_execution_result is not None else None,
        },
        "phase3": {
            "enabled": phase3_mode != "off",
            "mode": phase3_mode,
            "execution_replay": (
                phase3_execution_replay_result.diagnostics
                if phase3_execution_replay_result is not None
                else None
            ),
        },
        "phase4": {
            "enabled": phase4_mode != "off",
            "mode": phase4_mode,
            "protection_replay": (
                phase4_protection_replay_result.diagnostics
                if phase4_protection_replay_result is not None
                else None
            ),
        },
        "phase5": {
            "enabled": phase5_mode != "off",
            "mode": phase5_mode,
            "watcher_replay": (
                phase5_watcher_replay_result.diagnostics
                if phase5_watcher_replay_result is not None
                else None
            ),
        },
        "phase7": {
            "enabled": phase7_mode != "off",
            "mode": phase7_mode,
            "exit_lifecycle_replay": (
                phase7_exit_lifecycle_result.diagnostics
                if phase7_exit_lifecycle_result is not None
                else None
            ),
        },
    }

    # Phase A.4 — métadonnées de reproductibilité.
    run_metadata = build_run_metadata(
        seed=getattr(args, "seed", None),
        dataset_frames={
            "ohlcv": ohlcv_df,
            "scores": scores_df,
            "predictions": preds_df if isinstance(preds_df, pd.DataFrame) else None,
        },
    )

    if output_dir is not None:
        _safe_print("📝 Sauvegarde du rapport structuré...")
        equity_curve_csv_path = save_equity_curve_csv(pf, output_dir=output_dir)
        artifact_paths["equity_curve_csv"] = str(equity_curve_csv_path)
        fidelity_manifest_path = save_fidelity_manifest(fidelity_manifest, output_dir)
        artifact_paths["fidelity_manifest_json"] = str(fidelity_manifest_path)
        if phase2_risk_result is not None:
            from backtesting.risk_bridge import save_phase2_risk_artifacts

            artifact_paths.update(save_phase2_risk_artifacts(phase2_risk_result, output_dir))
        if phase2_execution_result is not None and phase3_execution_replay_result is None:
            from backtesting.execution_bridge import save_phase2_execution_artifacts

            artifact_paths.update(save_phase2_execution_artifacts(phase2_execution_result, output_dir))
        if phase3_execution_replay_result is not None:
            from backtesting.execution_replay import save_phase3_execution_replay_artifacts

            phase3_artifacts = cast(
                dict[str, str],
                save_phase3_execution_replay_artifacts(phase3_execution_replay_result, output_dir),
            )
            artifact_paths.update(phase3_artifacts)
        if phase4_protection_replay_result is not None:
            from backtesting.execution_lifecycle_replay import save_phase4_protection_replay_artifacts

            phase4_artifacts = cast(
                dict[str, str],
                save_phase4_protection_replay_artifacts(phase4_protection_replay_result, output_dir),
            )
            artifact_paths.update(phase4_artifacts)
        if phase5_watcher_replay_result is not None:
            from backtesting.protection_watcher_replay import save_phase5_watcher_replay_artifacts

            phase5_artifacts = cast(
                dict[str, str],
                save_phase5_watcher_replay_artifacts(phase5_watcher_replay_result, output_dir),
            )
            artifact_paths.update(phase5_artifacts)
        if phase7_exit_lifecycle_result is not None:
            from backtesting.exit_lifecycle_replay import save_phase7_exit_lifecycle_replay_artifacts

            phase7_artifacts = cast(
                dict[str, str],
                save_phase7_exit_lifecycle_replay_artifacts(phase7_exit_lifecycle_result, output_dir),
            )
            artifact_paths.update(phase7_artifacts)
        report_json_path = save_report_json(
            report,
            output_dir=output_dir,
            artifacts=artifact_paths,
            params=common_params,
            diagnostics=diagnostics,
            run_metadata=run_metadata,
            fidelity=fidelity_manifest,
        )
        artifact_paths["report_json"] = str(report_json_path)
        _safe_print(f"   → {report_json_path}")
        _safe_print(f"   → {equity_curve_csv_path}")
        _safe_print(f"   → {fidelity_manifest_path}")

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
                params=common_params,
                diagnostics=diagnostics,
                run_metadata=run_metadata,
                fidelity=fidelity_manifest,
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
    explicit_flags = _explicit_flags(sys.argv[1:])
    effective_preset, preset_source = resolve_effective_capital_preset(
        capital_preset_key=getattr(args, "capital_preset_key", None),
        equity=float(args.capital) if getattr(args, "capital", None) is not None else None,
    )
    detected_from_capital = (
        resolve_capital_preset_for_equity(float(args.capital)) if getattr(args, "capital", None) is not None else None
    )
    if preset_source == "explicit_key" and detected_from_capital is not None and detected_from_capital.key != effective_preset.key:
        _safe_print(
            f"⚠️ Preset explicite `{effective_preset.key}` prioritaire sur le bucket détecté depuis capital `{detected_from_capital.key}`."
        )
    screener_kwargs = build_screener_config_kwargs_from_preset(effective_preset)
    selector_kwargs = build_selector_config_kwargs_from_preset(effective_preset)
    preset_selection_size = int(selector_kwargs.pop("selection_size"))
    effective_selection_size = int(args.selection_size) if "selection_size" in explicit_flags else preset_selection_size
    preset_fingerprint = capital_preset_fingerprint(effective_preset)

    _safe_print(f"\n🧱 Backfill stock_scores_history : start={start} end={end or 'auto'}")
    _safe_print(
        f"   overwrite={args.overwrite_existing} limit_days={args.limit_days or 'all'} "
        f"chunk_size={args.chunk_size} selection_size={args.selection_size}\n"
    )
    _safe_print(
        f"   preset_capital={effective_preset.key} ({preset_source}) selection_size_effective={effective_selection_size} fingerprint={preset_fingerprint}\n"
    )

    service = BackfillScoresHistoryService(
        screener_config=ScreenerConfig(chunk_size=args.chunk_size, **screener_kwargs),
        scanner_config=AlphaScannerConfig.strict_swing_cash(
            chunk_size=args.chunk_size,
            selection_size=effective_selection_size,
            **selector_kwargs,
        ),
        sentiment_config=SentimentBoostConfig(),
        screener_max_workers=args.screener_workers,
        capital_preset_key=effective_preset.key,
        config_fingerprint=preset_fingerprint,
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
        export_holdout_validation,
        export_screener_objective_recommendations,
        export_screener_regime_recommendations,
        export_screener_recommendations,
        export_screener_diagnostics,
        recommend_screener_scenarios_by_objective,
        recommend_screener_scenarios_by_regime,
        recommend_screener_scenarios,
        validate_recommendations_holdout,
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
    recommendation_frame, recommendation_summary = recommend_screener_scenarios(
        result.summary_metrics,
        daily_metrics=result.daily_metrics,
        baseline_name=result.baseline_name,
    )
    regime_recommendations, regime_summary, cross_regime_recommendations, cross_regime_summary = recommend_screener_scenarios_by_regime(
        result.summary_metrics_by_regime,
        daily_metrics=result.daily_metrics,
        baseline_name=result.baseline_name,
    )
    objective_recommendations, objective_summary = recommend_screener_scenarios_by_objective(
        result.summary_metrics,
        daily_metrics=result.daily_metrics,
        summary_metrics_by_regime=result.summary_metrics_by_regime,
        baseline_name=result.baseline_name,
    )
    artifacts = export_screener_diagnostics(result, args.output_dir)
    artifacts.update(export_screener_recommendations(recommendation_frame, recommendation_summary, args.output_dir))
    if not regime_recommendations.empty or not cross_regime_recommendations.empty:
        artifacts.update(
            export_screener_regime_recommendations(
                regime_recommendations,
                regime_summary,
                cross_regime_recommendations,
                cross_regime_summary,
                args.output_dir,
            )
        )
    if not objective_recommendations.empty:
        artifacts.update(
            export_screener_objective_recommendations(
                objective_recommendations,
                objective_summary,
                args.output_dir,
            )
        )

    # Phase 6.1.d — validation hold-out optionnelle.
    if getattr(args, "holdout_train_end", None) and getattr(args, "holdout_test_end", None):
        holdout_df, holdout_summary = validate_recommendations_holdout(
            result.daily_metrics,
            train_end=args.holdout_train_end,
            test_end=args.holdout_test_end,
        )
        if not holdout_df.empty:
            artifacts.update(export_holdout_validation(holdout_df, holdout_summary, args.output_dir))
            _safe_print(
                "Hold-out (Phase 6.1.d) : {} scénarios, top_k_stable_ratio={:.2f}, avg_rank_delta={:+.2f}".format(
                    holdout_summary.get("scenarios_evaluated"),
                    float(holdout_summary.get("stable_top_k_ratio", 0.0)),
                    float(holdout_summary.get("avg_rank_delta", 0.0)),
                )
            )

    _safe_print("✅ Diagnostic terminé")
    _safe_print(f"   Séances évaluées    : {len(result.trading_dates)}")
    _safe_print(f"   Baseline            : {result.baseline_name}")
    _safe_print(f"   Résumé CSV          : {artifacts['summary_metrics']}")
    _safe_print(f"   Journal quotidien   : {artifacts['daily_metrics']}")
    _safe_print(f"   Scénarios           : {artifacts['scenarios']}")
    _safe_print(f"   Métadonnées         : {artifacts['metadata']}\n")
    _safe_print(f"   Recommandations CSV : {artifacts['scenario_recommendations']}")
    _safe_print(f"   Résumé reco JSON    : {artifacts['recommendation_summary']}\n")
    if "market_regimes" in artifacts:
        _safe_print(f"   Régimes marché CSV  : {artifacts['market_regimes']}")
    if "summary_metrics_by_regime" in artifacts:
        _safe_print(f"   Résumé par régime   : {artifacts['summary_metrics_by_regime']}")
    if "scenario_recommendations_by_regime" in artifacts:
        _safe_print(f"   Reco par régime CSV : {artifacts['scenario_recommendations_by_regime']}")
    if "cross_regime_recommendations" in artifacts:
        _safe_print(f"   Reco cross-régimes  : {artifacts['cross_regime_recommendations']}")
    if "cross_regime_recommendation_summary" in artifacts:
        _safe_print(f"   Résumé cross-régime : {artifacts['cross_regime_recommendation_summary']}\n")
    if "scenario_recommendations_by_objective" in artifacts:
        _safe_print(f"   Reco par objectif   : {artifacts['scenario_recommendations_by_objective']}")
    if "recommendation_summary_by_objective" in artifacts:
        _safe_print(f"   Résumé objectifs    : {artifacts['recommendation_summary_by_objective']}\n")

    if recommendation_summary.get("status") == "ok":
        best = recommendation_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis : {} (overall={:.3f}, robustesse={:.3f}, survie={:.3f}, forward={:.3f})".format(
                best["scenario_name"],
                float(best["overall_score"]),
                float(best["robustness_score"]),
                float(best["survival_score"]),
                float(best["forward_quality_score"]),
            )
        )
        _safe_print(f"   Raison              : {best['reason']}\n")

    if cross_regime_summary.get("status") == "ok":
        best_cross = cross_regime_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis cross-régimes : {} (score={:.3f}, mean={:.3f}, worst={:.3f}, coverage={:.3f})".format(
                best_cross["scenario_name"],
                float(best_cross["cross_regime_overall_score"]),
                float(best_cross["mean_regime_overall_score"]),
                float(best_cross["worst_regime_overall_score"]),
                float(best_cross["regime_coverage_ratio"]),
            )
        )
        _safe_print()

    if objective_summary.get("status") == "ok":
        _safe_print("Recommandations adaptatives par objectif :")
        for objective_name in objective_summary.get("available_objectives", []):
            payload = objective_summary.get("objectives", {}).get(objective_name, {})
            best_objective = payload.get("recommended_scenario")
            if not isinstance(best_objective, dict) or not best_objective:
                continue
            _safe_print(
                " - {} : {} (objective_score={:.3f}, overall={:.3f})".format(
                    payload.get("label", objective_name),
                    best_objective.get("scenario_name", "?"),
                    float(best_objective.get("objective_score", 0.0)),
                    float(best_objective.get("overall_score", 0.0)),
                )
            )
        _safe_print()

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

    if not recommendation_frame.empty:
        recommendation_preview_columns = [
            column
            for column in [
                "rank",
                "scenario_name",
                "recommendation_label",
                "overall_score",
                "robustness_score",
                "survival_score",
                "forward_quality_score",
                "confidence_score",
            ]
            if column in recommendation_frame.columns
        ]
        recommendation_preview = recommendation_frame.loc[:, recommendation_preview_columns].head(10)
        _safe_print("Classement phase 5 (aperçu):")
        _safe_print(recommendation_preview.to_string(index=False))
        _safe_print()

    if not regime_recommendations.empty:
        regime_preview_columns = [
            column
            for column in [
                "market_regime",
                "rank",
                "scenario_name",
                "overall_score",
                "robustness_score",
                "survival_score",
                "forward_quality_score",
            ]
            if column in regime_recommendations.columns
        ]
        regime_preview = regime_recommendations.loc[:, regime_preview_columns].head(12)
        _safe_print("Classement phase 6 par régime (aperçu):")
        _safe_print(regime_preview.to_string(index=False))
        _safe_print()

    if not cross_regime_recommendations.empty:
        cross_preview_columns = [
            column
            for column in [
                "cross_regime_rank",
                "scenario_name",
                "recommendation_label",
                "cross_regime_overall_score",
                "mean_regime_overall_score",
                "worst_regime_overall_score",
                "regime_coverage_ratio",
            ]
            if column in cross_regime_recommendations.columns
        ]
        _safe_print("Classement cross-régimes (aperçu):")
        _safe_print(cross_regime_recommendations.loc[:, cross_preview_columns].head(10).to_string(index=False))
        _safe_print()

    if not objective_recommendations.empty:
        objective_preview_columns = [
            column
            for column in [
                "objective",
                "objective_label",
                "objective_scope",
                "rank",
                "scenario_name",
                "objective_score",
                "overall_score",
                "objective_recommendation_label",
            ]
            if column in objective_recommendations.columns
        ]
        _safe_print("Classement phase 7 par objectif (aperçu):")
        _safe_print(objective_recommendations.loc[:, objective_preview_columns].head(16).to_string(index=False))
        _safe_print()


def _run_screener_recommendation(args: argparse.Namespace) -> None:
    """Analyse un summary_metrics.csv existant et produit une recommandation phase 5."""
    import pandas as pd

    from backtesting.screener_diagnostics import (
        export_holdout_validation,
        export_screener_objective_recommendations,
        export_screener_recommendations,
        export_screener_regime_recommendations,
        recommend_screener_scenarios_by_objective,
        recommend_screener_scenarios,
        recommend_screener_scenarios_by_regime,
        summarize_screener_diagnostics_by_regime,
        validate_recommendations_holdout,
    )

    input_dir = Path(args.input_dir)
    summary_path = Path(args.summary_csv) if args.summary_csv else input_dir / "summary_metrics.csv"
    daily_path = Path(args.daily_csv) if args.daily_csv else input_dir / "daily_metrics.csv"
    output_dir = Path(args.output_dir) if args.output_dir else summary_path.parent

    if not summary_path.exists():
        _safe_print(f"❌ summary_metrics.csv introuvable : {summary_path}")
        sys.exit(1)

    summary_df = pd.read_csv(summary_path)
    daily_df = pd.read_csv(daily_path) if daily_path.exists() else pd.DataFrame()

    recommendation_frame, recommendation_summary = recommend_screener_scenarios(
        summary_df,
        daily_metrics=daily_df if not daily_df.empty else None,
        baseline_name=args.baseline_name,
        target_horizon=args.target_horizon,
    )
    artifacts = export_screener_recommendations(recommendation_frame, recommendation_summary, output_dir)
    regime_recommendations = pd.DataFrame()
    cross_regime_recommendations = pd.DataFrame()
    cross_regime_summary: dict[str, object] = {"status": "empty", "message": "Aucune analyse par régime disponible."}
    objective_recommendations = pd.DataFrame()
    objective_summary: dict[str, object] = {"status": "empty", "message": "Aucune analyse par objectif disponible."}
    summary_by_regime = pd.DataFrame()
    if not daily_df.empty and "market_regime" in daily_df.columns:
        summary_by_regime = summarize_screener_diagnostics_by_regime(daily_df, baseline_name=args.baseline_name)
        regime_recommendations, regime_summary, cross_regime_recommendations, cross_regime_summary = recommend_screener_scenarios_by_regime(
            summary_by_regime,
            daily_metrics=daily_df,
            baseline_name=args.baseline_name,
            target_horizon=args.target_horizon,
        )
        if not regime_recommendations.empty or not cross_regime_recommendations.empty:
            artifacts.update(
                export_screener_regime_recommendations(
                    regime_recommendations,
                    regime_summary,
                    cross_regime_recommendations,
                    cross_regime_summary,
                    output_dir,
                )
            )
    objective_recommendations, objective_summary = recommend_screener_scenarios_by_objective(
        summary_df,
        daily_metrics=daily_df if not daily_df.empty else None,
        summary_metrics_by_regime=summary_by_regime if not summary_by_regime.empty else None,
        baseline_name=args.baseline_name,
        target_horizon=args.target_horizon,
    )
    if not objective_recommendations.empty:
        artifacts.update(
            export_screener_objective_recommendations(
                objective_recommendations,
                objective_summary,
                output_dir,
            )
        )

    # Phase 6.1.d — validation hold-out optionnelle.
    if getattr(args, "holdout_train_end", None) and getattr(args, "holdout_test_end", None) and not daily_df.empty:
        holdout_df, holdout_summary = validate_recommendations_holdout(
            daily_df,
            train_end=args.holdout_train_end,
            test_end=args.holdout_test_end,
        )
        if not holdout_df.empty:
            artifacts.update(export_holdout_validation(holdout_df, holdout_summary, output_dir))
            _safe_print(
                "Hold-out (Phase 6.1.d) : {} scénarios, top_k_stable_ratio={:.2f}, avg_rank_delta={:+.2f}".format(
                    holdout_summary.get("scenarios_evaluated"),
                    float(holdout_summary.get("stable_top_k_ratio", 0.0)),
                    float(holdout_summary.get("avg_rank_delta", 0.0)),
                )
            )

    _safe_print("✅ Analyse phase 5/6 terminée")
    _safe_print(f"   Summary source      : {summary_path}")
    _safe_print(f"   Daily source        : {daily_path if daily_path.exists() else 'absent'}")
    _safe_print(f"   Recommandations CSV : {artifacts['scenario_recommendations']}")
    _safe_print(f"   Résumé reco JSON    : {artifacts['recommendation_summary']}\n")
    if "scenario_recommendations_by_regime" in artifacts:
        _safe_print(f"   Reco par régime CSV : {artifacts['scenario_recommendations_by_regime']}")
    if "cross_regime_recommendations" in artifacts:
        _safe_print(f"   Reco cross-régimes  : {artifacts['cross_regime_recommendations']}")
    if "cross_regime_recommendation_summary" in artifacts:
        _safe_print(f"   Résumé cross-régime : {artifacts['cross_regime_recommendation_summary']}\n")
    if "scenario_recommendations_by_objective" in artifacts:
        _safe_print(f"   Reco par objectif   : {artifacts['scenario_recommendations_by_objective']}")
    if "recommendation_summary_by_objective" in artifacts:
        _safe_print(f"   Résumé objectifs    : {artifacts['recommendation_summary_by_objective']}\n")

    if recommendation_summary.get("status") == "ok":
        best = recommendation_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis : {} (overall={:.3f}, robustesse={:.3f}, survie={:.3f}, forward={:.3f})".format(
                best["scenario_name"],
                float(best["overall_score"]),
                float(best["robustness_score"]),
                float(best["survival_score"]),
                float(best["forward_quality_score"]),
            )
        )
        _safe_print(f"   Raison              : {best['reason']}\n")

    if cross_regime_summary.get("status") == "ok":
        best_cross = cross_regime_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis cross-régimes : {} (score={:.3f}, mean={:.3f}, worst={:.3f}, coverage={:.3f})".format(
                best_cross["scenario_name"],
                float(best_cross["cross_regime_overall_score"]),
                float(best_cross["mean_regime_overall_score"]),
                float(best_cross["worst_regime_overall_score"]),
                float(best_cross["regime_coverage_ratio"]),
            )
        )
        _safe_print()

    if objective_summary.get("status") == "ok":
        _safe_print("Recommandations adaptatives par objectif :")
        for objective_name in objective_summary.get("available_objectives", []):
            payload = objective_summary.get("objectives", {}).get(objective_name, {})
            best_objective = payload.get("recommended_scenario")
            if not isinstance(best_objective, dict) or not best_objective:
                continue
            _safe_print(
                " - {} : {} (objective_score={:.3f}, overall={:.3f})".format(
                    payload.get("label", objective_name),
                    best_objective.get("scenario_name", "?"),
                    float(best_objective.get("objective_score", 0.0)),
                    float(best_objective.get("overall_score", 0.0)),
                )
            )
        _safe_print()

    if not recommendation_frame.empty:
        preview_columns = [
            column
            for column in [
                "rank",
                "scenario_name",
                "recommendation_label",
                "overall_score",
                "robustness_score",
                "survival_score",
                "forward_quality_score",
                "confidence_score",
                "recommendation_warnings",
            ]
            if column in recommendation_frame.columns
        ]
        _safe_print("Top recommandations (aperçu):")
        _safe_print(recommendation_frame.loc[:, preview_columns].head(10).to_string(index=False))
        _safe_print()

    if not cross_regime_recommendations.empty:
        cross_preview_columns = [
            column
            for column in [
                "cross_regime_rank",
                "scenario_name",
                "recommendation_label",
                "cross_regime_overall_score",
                "mean_regime_overall_score",
                "worst_regime_overall_score",
                "regime_coverage_ratio",
            ]
            if column in cross_regime_recommendations.columns
        ]
        _safe_print("Top recommandations cross-régimes (aperçu):")
        _safe_print(cross_regime_recommendations.loc[:, cross_preview_columns].head(10).to_string(index=False))
        _safe_print()

    if not objective_recommendations.empty:
        objective_preview_columns = [
            column
            for column in [
                "objective",
                "objective_label",
                "objective_scope",
                "rank",
                "scenario_name",
                "objective_score",
                "overall_score",
                "objective_recommendation_label",
                "objective_reason",
            ]
            if column in objective_recommendations.columns
        ]
        _safe_print("Top recommandations phase 7 (aperçu):")
        _safe_print(objective_recommendations.loc[:, objective_preview_columns].head(16).to_string(index=False))
        _safe_print()


def _run_calibrate_sentiment_weights(args: argparse.Namespace) -> None:
    from datetime import datetime

    from backtesting.sentiment_calibration import SentimentWeightCalibrator

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())

    _safe_print(f"\n🧪 Calibration poids sentiment : {start} → {end}")
    _safe_print(
        f"   horizons={','.join(str(horizon) for horizon in horizons)} top_n={args.top_n} "
        f"all_symbols={args.all_symbols} output_dir={args.output_dir}\n"
    )

    calibrator = SentimentWeightCalibrator()
    result, ranking_df, artifacts = calibrator.calibrate(
        start_date=start,
        end_date=end,
        horizons=horizons,
        top_n=args.top_n,
        candidates_only=not args.all_symbols,
        output_dir=Path(args.output_dir),
    )

    _safe_print("✅ Calibration terminée")
    _safe_print(f"   Scénarios évalués   : {result.scenarios_evaluated}")
    _safe_print(f"   Lignes évaluées     : {result.rows_evaluated}")
    _safe_print(f"   Meilleur scénario   : {result.best_scenario_name}")
    _safe_print(f"   Score global        : {result.best_overall_score:.4f}")
    if artifacts:
        _safe_print(f"   CSV classement      : {artifacts.get('calibration_csv')}")
        _safe_print(f"   JSON meilleur       : {artifacts.get('best_json')}\n")
    if not ranking_df.empty:
        preview_columns = [
            column
            for column in [
                "scenario_name",
                "sentiment_weight",
                "macro_weight",
                "quant_weight",
                "overall_score",
                "score_5d",
                "score_10d",
                "score_20d",
            ]
            if column in ranking_df.columns
        ]
        _safe_print("Top scénarios calibration (aperçu):")
        _safe_print(ranking_df.loc[:, preview_columns].head(10).to_string(index=False))
        _safe_print()


def _run_walk_forward_sentiment(args: argparse.Namespace) -> None:
    from datetime import datetime

    from backtesting.sentiment_calibration import SentimentWeightCalibrator

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())

    _safe_print(f"\n🧭 Walk-forward sentiment : {start} → {end}")
    _safe_print(
        "   horizons={} top_n={} min_train_days={} test_days={} step_days={} max_positions={} output_dir={}\n".format(
            ",".join(str(horizon) for horizon in horizons),
            args.top_n,
            args.min_train_days,
            args.test_days,
            args.step_days,
            args.max_positions,
            args.output_dir,
        )
    )

    calibrator = SentimentWeightCalibrator()
    result, fold_df, _, _, artifacts = calibrator.walk_forward_backtest(
        start_date=start,
        end_date=end,
        horizons=horizons,
        top_n=args.top_n,
        candidates_only=not args.all_symbols,
        min_train_days=args.min_train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        max_positions=args.max_positions,
        initial_equity=args.equity,
        profit_taker_pct=args.tp,
        trailing_stop_pct=args.ts,
        fees_pct=args.fees,
        output_dir=Path(args.output_dir),
    )

    _safe_print("✅ Walk-forward terminé")
    _safe_print(f"   Folds évalués       : {result.folds_evaluated}")
    _safe_print(f"   Lignes OOS          : {result.out_of_sample_rows}")
    _safe_print(f"   Jours OOS           : {result.out_of_sample_days}")
    _safe_print(f"   Dernier meilleur    : {result.latest_best_scenario_name}")
    _safe_print(f"   Valeur finale       : {result.final_value:,.2f}$")
    _safe_print(f"   Rendement total     : {result.total_return_pct:.2f}%")
    _safe_print(f"   Sharpe              : {result.sharpe_ratio:.3f}")
    _safe_print(f"   Max drawdown        : {result.max_drawdown_pct:.2f}%")
    if artifacts:
        _safe_print(f"   Rapport JSON        : {artifacts.get('report_json')}")
        _safe_print(f"   Folds CSV           : {artifacts.get('walk_forward_folds_csv')}")
        _safe_print(f"   Scores OOS CSV      : {artifacts.get('walk_forward_out_of_sample_scores_csv')}")
        _safe_print(f"   Signaux CSV         : {artifacts.get('walk_forward_selected_signals_csv')}\n")
    if not fold_df.empty:
        preview_columns = [
            column
            for column in [
                "fold_index",
                "train_start_date",
                "train_end_date",
                "test_start_date",
                "test_end_date",
                "best_scenario_name",
                "best_train_overall_score",
                "out_of_sample_overall_score",
            ]
            if column in fold_df.columns
        ]
        _safe_print("Folds walk-forward (aperçu):")
        _safe_print(fold_df.loc[:, preview_columns].to_string(index=False))
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
    elif args.command == "recommend-screener":
        _run_screener_recommendation(args)
    elif args.command == "calibrate-sentiment-weights":
        _run_calibrate_sentiment_weights(args)
    elif args.command == "walk-forward-sentiment":
        _run_walk_forward_sentiment(args)
    else:
        parser.print_help()
        sys.exit(1)


