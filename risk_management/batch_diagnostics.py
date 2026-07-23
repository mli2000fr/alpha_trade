"""risk_management/batch_diagnostics.py — Filtrage ML batch diagnostics dans Risk.

Appliqué dans l'étape 11 (Risk Management) :
- **Avant** le PortfolioBuilder : boost du score de conviction pour les
  symboles prefer (top N). Le builder intègre naturellement ce boost
  dans le sizing, les contraintes et les poids → cohérence parfaite.
- **Après** le PortfolioBuilder : exclusion des entries dont le side
  est incompatible avec les listes exclude_long / exclude_short.
"""
from __future__ import annotations

import logging
from typing import Any

from modelFactory.batch_diagnostics import (
    BatchFilters,
    _load_config_defaults,
    get_batch_filters,
)
from risk_management.models import PortfolioEntry

LOGGER = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────

def _load_filters(engine: Any) -> BatchFilters | None:
    """Charge les BatchFilters pour le live (respecte live_batch_id config)."""
    _live_batch_id: str | None = None
    try:
        _cfg = _load_config_defaults()
        _live_batch_id = str(_cfg.get("live_batch_id", "") or "").strip() or None
    except Exception:
        pass
    try:
        filters: BatchFilters = get_batch_filters(engine, batch_id=_live_batch_id)
    except Exception as exc:
        LOGGER.warning(
            "risk batch_diagnostics: impossible de charger les filtres: %s", exc
        )
        return None
    if not filters.batch_id:
        LOGGER.info("risk batch_diagnostics: aucun batch complété, skip.")
        return None
    return filters


def _resolve_prefer_set(filters: BatchFilters, prefer_top_n: int) -> frozenset[str]:
    """Construit le set des symboles prefer limité à prefer_top_n."""
    prefer_set: frozenset[str] = filters.prefer
    if filters.prefer:
        prefer_df = filters.all_diagnostics
        if not prefer_df.empty and "rank_position" in prefer_df.columns:
            prefer_set = frozenset(
                prefer_df[
                    (prefer_df["rank_type"] == "top")
                    & (prefer_df["rank_position"] <= prefer_top_n)
                ]["symbol"]
            )
    return prefer_set


# ── API publique ────────────────────────────────────────────────────

def boost_candidate_scores(
    candidates: list[Any],
    engine: Any,
    *,
    prefer_multiplier: float | None = None,
    prefer_top_n: int | None = None,
) -> tuple[int, str | None]:
    """Augmente le score de conviction (p_side) des candidats prefer AVANT le sizing.

    Doit être appelé AVANT ``PortfolioBuilder.build_from_ml_candidates()``.
    Le builder intègre naturellement le score boosté dans le sizing,
    les contraintes et les target_weight → cohérence parfaite live/backtest.

    Args:
        candidates: Liste de ``MLRankedCandidate``.
        engine: Engine SQLAlchemy.
        prefer_multiplier: Multiplicateur de score. Défaut : config.yaml (1.2).
        prefer_top_n: Nombre de symboles du top à booster. Défaut : config.yaml (10).

    Returns:
        (boosted_count, batch_id)
    """
    if not candidates:
        return 0, None

    filters = _load_filters(engine)
    if filters is None:
        return 0, None

    if prefer_multiplier is None or prefer_top_n is None:
        cfg = _load_config_defaults()
        if prefer_multiplier is None:
            prefer_multiplier = float(cfg.get("prefer_sizing_multiplier", 1.2))
        if prefer_top_n is None:
            prefer_top_n = int(cfg.get("prefer_top_n", 10))

    prefer_set = _resolve_prefer_set(filters, prefer_top_n)
    if not prefer_set or prefer_multiplier == 1.0:
        return 0, filters.batch_id

    boosted_count = 0
    boosted_syms: list[str] = []
    for c in candidates:
        sym = str(getattr(c, "symbol", "")).strip().upper()
        if sym in prefer_set:
            boosted_count += 1
            boosted_syms.append(sym)
            # Booster p_side → impacte le conviction_score → sizing naturel
            old_p_side = float(getattr(c, "p_side", 0) or 0)
            c.p_side = min(old_p_side * prefer_multiplier, 1.0)
            # Booster aussi la proba directionnelle correspondante
            side = str(getattr(c, "side", "")).strip().lower()
            if side == "long":
                old_p = float(getattr(c, "p_long", 0) or 0)
                c.p_long = min(old_p * prefer_multiplier, 1.0)
            elif side == "short":
                old_p = float(getattr(c, "p_short", 0) or 0)
                c.p_short = min(old_p * prefer_multiplier, 1.0)

    if boosted_count > 0:
        _comment_info = f" | comment={filters.batch_comment}" if filters.batch_comment else ""
        LOGGER.info(
            "batch_diagnostics score boost (batch=%s%s): "
            "⭐ BOOSTÉS x%.1f (%d): %s",
            filters.batch_id, _comment_info,
            prefer_multiplier, boosted_count,
            ", ".join(sorted(boosted_syms)),
        )

    return boosted_count, filters.batch_id


def apply_batch_diagnostics_to_entries(
    entries: list[PortfolioEntry],
    engine: Any,
) -> tuple[list[PortfolioEntry], int, str | None]:
    """Exclut les entries dont le side est incompatible avec les listes
    exclude_long / exclude_short.

    Le boost prefer est désormais fait EN AMONT via ``boost_candidate_scores()``,
    avant le PortfolioBuilder. Cette fonction ne fait QUE l'exclusion.

    Args:
        entries: Liste des PortfolioEntry produites par le PortfolioBuilder.
        engine: Engine SQLAlchemy.

    Returns:
        (filtered_entries, excluded_count, batch_id)
    """
    if not entries:
        return entries, 0, None

    filters = _load_filters(engine)
    if filters is None:
        return entries, 0, None

    excluded_count = 0
    excluded_long_syms: list[str] = []
    excluded_short_syms: list[str] = []
    filtered_entries: list[PortfolioEntry] = []
    for entry in entries:
        sym = str(entry.symbol).strip().upper()
        side = str(getattr(entry, "side", "buy") or "buy").strip().lower()

        if side in ("sell", "short") and sym in filters.exclude_short:
            excluded_count += 1
            excluded_short_syms.append(sym)
            continue
        if side in ("buy", "long") and sym in filters.exclude_long:
            excluded_count += 1
            excluded_long_syms.append(sym)
            continue
        filtered_entries.append(entry)

    if excluded_count > 0:
        _comment_info = f" | comment={filters.batch_comment}" if filters.batch_comment else ""
        _lines = [f"batch_diagnostics exclusion (batch={filters.batch_id}{_comment_info}):"]
        if excluded_long_syms:
            _lines.append(
                f"  🚫 LONG filtrés  ({len(excluded_long_syms)}): "
                + ", ".join(sorted(excluded_long_syms))
            )
        if excluded_short_syms:
            _lines.append(
                f"  🚫 SHORT filtrés ({len(excluded_short_syms)}): "
                + ", ".join(sorted(excluded_short_syms))
            )
        _lines.append(
            f"  ➡️ {len(entries)}→{len(filtered_entries)} entries (−{excluded_count} exclus)"
        )
        LOGGER.info("\n".join(_lines))

    return filtered_entries, excluded_count, filters.batch_id
