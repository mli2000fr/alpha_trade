"""Sprint S9 — CLI quotidien de parité backtest ↔ live.

Usage::

    python -m scripts.run_daily_parity --trade-date 2026-05-05
    python -m scripts.run_daily_parity --trade-date 2026-05-05 --no-alert
    python -m scripts.run_daily_parity --threshold 0.05 --account default

Exit codes :
- ``0`` : parité OK (divergence_score ≤ seuil) ou pas de données.
- ``2`` : divergence > seuil (utile pour scheduler/cron monitoring).
- ``1`` : erreur inattendue.

Les loaders ``live`` / ``replay`` peuvent être surchargés via les hooks
``--use-stub-replay`` (utile pour tests d'intégration sans BacktestEngine).
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from backtesting.parity import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DIVERGENCE_THRESHOLD,
    DEFAULT_QTY_TOLERANCE_ABS,
    DEFAULT_QTY_TOLERANCE_PCT,
    run_daily_parity,
)
from common.utils import configure_root_logging
from service.alerting import build_notifier_from_env

LOGGER = logging.getLogger("scripts.run_daily_parity")


def _default_live_loader(trade_date: date, account_id: str) -> pd.DataFrame:
    """Loader live par défaut : interroge ``risk_decisions`` via :class:`RiskRepository`."""
    from risk_management.db_io import RiskRepository

    repo = RiskRepository()
    acct = None if account_id in (None, "", "default") else account_id
    return repo.load_risk_decisions_for_date(trade_date, account_id=acct)


def _stub_replay_loader(trade_date: date, account_id: str) -> pd.DataFrame:
    """Loader replay « stub » : ré-utilise le live comme baseline (zéro divergence).

    Utilisé par défaut tant que le replay réel
    (``backtesting.signal_replay`` + ``backtesting.risk_bridge``) n'est pas
    intégré derrière une API stable. Permet à la CI de valider la mécanique
    parité (artefacts + alerting) sans BacktestEngine.
    """
    df = _default_live_loader(trade_date, account_id)
    if df.empty:
        return df
    out = df.copy()
    if "run_id" in out.columns:
        out["run_id"] = out["run_id"].astype(str) + "-replay-stub"
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    today = date.today()
    p = argparse.ArgumentParser(description="Job quotidien de parité backtest ↔ live (Sprint S9).")
    p.add_argument("--trade-date", type=str, default=today.isoformat(),
                   help="Date au format YYYY-MM-DD (défaut : aujourd'hui).")
    p.add_argument("--account", default="default", help="ID du compte (défaut: default).")
    p.add_argument("--threshold", type=float, default=DEFAULT_DIVERGENCE_THRESHOLD,
                   help="Seuil de divergence_score déclenchant l'alerte.")
    p.add_argument("--qty-tolerance-pct", type=float, default=DEFAULT_QTY_TOLERANCE_PCT,
                   help="Tolérance relative sur approved_shares.")
    p.add_argument("--qty-tolerance-abs", type=float, default=DEFAULT_QTY_TOLERANCE_ABS,
                   help="Tolérance absolue sur approved_shares (en parts).")
    p.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR),
                   help="Dossier d'écriture des artefacts.")
    p.add_argument("--no-alert", action="store_true", help="Désactive l'envoi d'alerte.")
    p.add_argument("--use-stub-replay", action="store_true",
                   help="Utilise un replay stub (live recopié) — utile en CI.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    configure_root_logging(level=logging.INFO, log_path="./log/run_daily_parity.log",
                          fmt="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        trade_date_value = date.fromisoformat(args.trade_date)
    except ValueError:
        LOGGER.error("[parity] --trade-date invalide: %s", args.trade_date)
        return 1

    notifier = None if args.no_alert else build_notifier_from_env()
    replay_loader = _stub_replay_loader if args.use_stub_replay else _default_replay_loader

    try:
        report = run_daily_parity(
            trade_date_value,
            live_loader=_default_live_loader,
            replay_loader=replay_loader,
            account_id=args.account,
            artifacts_dir=Path(args.artifacts_dir),
            notifier=notifier,
            divergence_threshold=float(args.threshold),
            qty_tolerance_pct=float(args.qty_tolerance_pct),
            qty_tolerance_abs=float(args.qty_tolerance_abs),
        )
    except Exception:
        LOGGER.exception("[parity] échec inattendu du job")
        return 1

    LOGGER.info(
        "[parity] résumé | date=%s account=%s matched=%d divergent=%d score=%.4f live_run=%s replay_run=%s",
        report.trade_date, report.account_id, report.n_matched, report.n_divergent,
        report.divergence_score, report.live_run_id, report.replay_run_id,
    )
    return 2 if report.divergence_score > float(args.threshold) else 0


def _default_replay_loader(trade_date: date, account_id: str) -> pd.DataFrame:
    """Loader replay réel — délègue à ``backtesting.parity_replay`` si dispo,
    sinon retombe sur le stub avec WARNING.

    Le module ``backtesting/parity_replay.py`` (replay backtest réel via
    ``signal_replay`` + ``risk_bridge``) est laissé en TODO post-S9 :
    nécessite de figer une API stable au-dessus de
    ``RiskRepository.load_selection_inputs_asof`` + ``PortfolioBuilder``.
    """
    try:
        from backtesting.parity_replay import replay_decisions_for_date  # type: ignore[import-not-found]
        return replay_decisions_for_date(trade_date, account_id=account_id)
    except ImportError:
        LOGGER.warning(
            "[parity] backtesting.parity_replay indisponible -> stub (live=replay). "
            "Implémenter parity_replay pour activer la comparaison effective."
        )
        return _stub_replay_loader(trade_date, account_id)


if __name__ == "__main__":
    sys.exit(main())

