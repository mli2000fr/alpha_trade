"""modelFactory/global_direction/config.py — Configuration GlobalDirection H20.

Réutilise la résolution de batch_id de l'Oracle (``oracle.batch_id`` puis
``batch_diagnostics.backtest_batch_id``) : GlobalDirection partage le même
univers de labels (``global_oracle_labels``) que l'Oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modelFactory.oracle.config import (
    load_backtest_batch_id,
    load_oracle_config,
)

DEFAULT_HORIZON = 20
DEFAULT_TOP_PCT = 0.10      # TOP/BOTTOM 10% cross-sectionnel (D10 / D1)
DEFAULT_POOL_PCT = 0.20     # Gate Oracle : top 20% du jour par proba_extreme
DEFAULT_M24 = 24            # TOP m24 sélectionnés dans le pool (LONG only)
_CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True, slots=True)
class GlobalDirectionConfig:
    """Paramètres GlobalDirection (labels + entraînement + pipeline)."""

    horizon: int = DEFAULT_HORIZON
    top_pct: float = DEFAULT_TOP_PCT
    pool_pct: float = DEFAULT_POOL_PCT
    m24: int = DEFAULT_M24
    batch_id: str | None = None


def load_global_direction_config(path: Path | str = _CONFIG_PATH) -> GlobalDirectionConfig:
    """Lit la section ``global_direction:`` de config.yaml (absente → défauts)."""
    raw: dict = {}
    try:
        import yaml

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except Exception:
        raw = {}
    section = raw.get("global_direction") or {}

    def _int(key: str, default: int) -> int:
        try:
            return int(section.get(key, default))
        except (TypeError, ValueError):
            return default

    def _float(key: str, default: float) -> float:
        try:
            return float(section.get(key, default))
        except (TypeError, ValueError):
            return default

    return GlobalDirectionConfig(
        horizon=_int("horizon", DEFAULT_HORIZON),
        top_pct=_float("top_pct", DEFAULT_TOP_PCT),
        pool_pct=_float("pool_pct", DEFAULT_POOL_PCT),
        m24=_int("m24", DEFAULT_M24),
        batch_id=str(section.get("batch_id") or "").strip() or None,
    )


def resolve_global_direction_batch_id(path: Path | str = _CONFIG_PATH) -> str | None:
    """Batch_id du Global Model utilisé pour les labels GlobalDirection.

    Priorité : ``global_direction.batch_id``, puis ``oracle.batch_id``, puis
    ``batch_diagnostics.backtest_batch_id``.
    """
    cfg = load_global_direction_config(path)
    if cfg.batch_id:
        return cfg.batch_id
    oracle_cfg = load_oracle_config(path)
    return oracle_cfg.batch_id or load_backtest_batch_id(path)
