"""Sentiment circuit breaker — agrégation sur fenêtre courte.

Le score agrégé est fourni en injection (couplage faible avec
``event_sentiment.signal_aggregator``). Si aucune source n'est branchée,
l'évaluation retourne un mode neutre.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from service.market.config import SentimentBreakerConfig

SentimentRegimeLevel = Literal["normal", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class SentimentRegimeEvaluation:
    score: float | None
    level: SentimentRegimeLevel
    suggested_mode: str  # 'normal' | 'close_only' | 'cash_only'
    suggested_max_positions: int | None
    reasons: tuple[str, ...]
    data_quality: str = "ok"


def evaluate_sentiment_regime(
    cfg: SentimentBreakerConfig,
    *,
    score_provider: Callable[[int], float | None] | None,
    execution_context: Literal["live", "backtest"],
) -> SentimentRegimeEvaluation:
    if not cfg.enabled or score_provider is None:
        return SentimentRegimeEvaluation(
            score=None, level="normal", suggested_mode="normal",
            suggested_max_positions=None, reasons=(), data_quality="disabled_or_no_provider",
        )
    try:
        score = score_provider(cfg.lookback_days)
    except Exception:
        return SentimentRegimeEvaluation(
            score=None, level="normal", suggested_mode="normal",
            suggested_max_positions=None, reasons=("sentiment_provider_error",),
            data_quality="provider_error",
        )
    if score is None:
        return SentimentRegimeEvaluation(
            score=None, level="normal", suggested_mode="normal",
            suggested_max_positions=None, reasons=("sentiment_score_missing",),
            data_quality="missing",
        )
    if score <= cfg.critical_threshold:
        mode = cfg.critical_mode_live if execution_context == "live" else cfg.critical_mode_backtest
        return SentimentRegimeEvaluation(
            score=score, level="critical", suggested_mode=mode,
            suggested_max_positions=0 if mode == "cash_only" else None,
            reasons=(f"sentiment_critical:{score:.3f}",),
        )
    if score <= cfg.warning_threshold:
        return SentimentRegimeEvaluation(
            score=score, level="warning", suggested_mode="capital_preservation",
            suggested_max_positions=cfg.warning_max_positions,
            reasons=(f"sentiment_warning:{score:.3f}",),
        )
    return SentimentRegimeEvaluation(
        score=score, level="normal", suggested_mode="normal",
        suggested_max_positions=None, reasons=(),
    )


__all__ = ["evaluate_sentiment_regime", "SentimentRegimeEvaluation", "SentimentRegimeLevel"]

