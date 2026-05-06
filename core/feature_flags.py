"""Sprint S8 — Feature flags globaux pour la gouvernance ML / sentiment.

Permet de désactiver dynamiquement et de manière testable :

- la fusion sentiment dans :class:`event_sentiment.signal_aggregator.SentimentSignalAggregator`
  (``--disable-sentiment``) ;
- la consommation de ``model_predictions`` côté risk
  (``--disable-ml``).

Les flags sont propagés via variables d'environnement processus :

- ``ALPHA_TRADE_DISABLE_SENTIMENT`` (``"1"`` / ``"true"`` / ``"yes"``).
- ``ALPHA_TRADE_DISABLE_ML``        (``"1"`` / ``"true"`` / ``"yes"``).

Cela évite d'avoir à plomber un objet de config supplémentaire dans tous
les contextes (CLI, IHM, sub-process, tests).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

ENV_DISABLE_SENTIMENT = "ALPHA_TRADE_DISABLE_SENTIMENT"
ENV_DISABLE_ML = "ALPHA_TRADE_DISABLE_ML"

_TRUTHY = {"1", "true", "yes", "on", "y", "t"}


def _coerce_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in _TRUTHY


@dataclass(frozen=True)
class FeatureFlags:
    """Snapshot immuable des feature flags ML / sentiment."""

    disable_sentiment: bool = False
    disable_ml: bool = False

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "FeatureFlags":
        source = env if env is not None else os.environ
        return cls(
            disable_sentiment=_coerce_bool(source.get(ENV_DISABLE_SENTIMENT)),
            disable_ml=_coerce_bool(source.get(ENV_DISABLE_ML)),
        )

    def export_env(self, env: Optional[dict] = None) -> None:
        """Pousse les flags dans ``os.environ`` (ou ``env`` si fourni).

        Sémantique drapeau : ``True`` → set "1" ; ``False`` → unset (delete).
        Évite les pollutions inter-tests : un flag à False ne laisse aucune
        variable d'environnement résiduelle.

        Utile pour propager les flags d'un parent CLI vers un sub-process.
        """
        target = env if env is not None else os.environ
        for key, value in (
            (ENV_DISABLE_SENTIMENT, self.disable_sentiment),
            (ENV_DISABLE_ML, self.disable_ml),
        ):
            if value:
                target[key] = "1"
            else:
                target.pop(key, None)

    def to_run_summary(self) -> dict:
        """Représentation prête pour ``run_summary["feature_flags"]``."""
        return {
            "disable_sentiment": bool(self.disable_sentiment),
            "disable_ml": bool(self.disable_ml),
        }


def is_sentiment_disabled() -> bool:
    return _coerce_bool(os.environ.get(ENV_DISABLE_SENTIMENT))


def is_ml_disabled() -> bool:
    return _coerce_bool(os.environ.get(ENV_DISABLE_ML))


__all__ = [
    "ENV_DISABLE_SENTIMENT",
    "ENV_DISABLE_ML",
    "FeatureFlags",
    "is_sentiment_disabled",
    "is_ml_disabled",
]


