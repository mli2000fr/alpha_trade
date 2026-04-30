"""
backtesting.cli — package CLI du module de backtesting.

Refactor Phase G.1 : la CLI historique (1 fichier de ~1445 LOC) a été éclatée en un
sous-package. Le module ``_impl`` héberge l'implémentation source de référence ;
les modules par sous-commande (``run``, ``backfill``, ``diagnose``, ``recommend``,
``calibrate``, ``walk_forward``) exposent uniquement le handler concerné, ce qui
respecte le principe de responsabilité unique tout en garantissant une compatibilité
ascendante totale (les imports historiques ``from backtesting.cli import main`` /
``_build_parser`` continuent de fonctionner).
"""
from __future__ import annotations

from backtesting.cli._impl import (
    _build_parser,
    _explicit_flags,
    _parse_csv_values,
    _run_backfill_scores_history,
    _run_backtest,
    _run_calibrate_sentiment_weights,
    _run_screener_diagnostics,
    _run_screener_recommendation,
    _run_walk_forward_sentiment,
    _safe_print,
    main,
)

__all__ = [
    "main",
    "_build_parser",
    "_safe_print",
    "_explicit_flags",
    "_parse_csv_values",
    "_run_backtest",
    "_run_backfill_scores_history",
    "_run_screener_diagnostics",
    "_run_screener_recommendation",
    "_run_calibrate_sentiment_weights",
    "_run_walk_forward_sentiment",
]


