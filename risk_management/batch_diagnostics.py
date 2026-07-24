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
    RANK_TYPE_BOTTOM,
    RANK_TYPE_WEAK_LONG,
    RANK_TYPE_WEAK_SHORT,
    RANK_TYPE_ZERO_SHORT,
    _load_config_defaults,
    get_batch_filters,
)
from risk_management.models import PortfolioEntry

LOGGER = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────

def _classify_exclusion(
    sym: str,
    side: str,
    filters: BatchFilters,
) -> str:
    """Retourne la règle qui a causé l'exclusion d'un symbole.

    Args:
        sym: Symbole (uppercase).
        side: ``"long"`` ou ``"short"``.
        filters: BatchFilters chargés.

    Returns:
        Code de la règle : ``bottom``, ``weak_long``, ``weak_short``,
        ``zero_short``, ``s7_exclude_all``, ``s7_flat_pathological``,
        ``s7_long_only``, ``s7_short_only``, ou ``unknown``.
    """
    s7 = filters.section7
    sym_u = sym.upper()

    # ── Vérifier §7 d'abord (plus informatif) ──
    if s7.is_active():
        if sym_u in s7.exclude_all:
            return "s7_exclude_all"
        if sym_u in s7.exclude_flat_pathological:
            return "s7_flat_pathological"
        if side == "long" and sym_u in s7.short_only:
            return "s7_short_only"
        if side == "short" and sym_u in s7.long_only:
            return "s7_long_only"

    # ── Vérifier règles existantes via all_diagnostics ──
    diag = filters.all_diagnostics
    if not diag.empty:
        sym_rows = diag[diag["symbol"].astype(str).str.upper() == sym_u]
        if not sym_rows.empty:
            rank_types = set(sym_rows["rank_type"].values)
            if side == "long":
                if RANK_TYPE_BOTTOM in rank_types:
                    return "bottom"
                if RANK_TYPE_WEAK_LONG in rank_types:
                    return "weak_long"
            elif side == "short":
                if RANK_TYPE_BOTTOM in rank_types:
                    return "bottom"
                if RANK_TYPE_ZERO_SHORT in rank_types:
                    return "zero_short"
                if RANK_TYPE_WEAK_SHORT in rank_types:
                    return "weak_short"

    return "unknown"

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

    # ── §7.0 — log des candidats dans les sets §7 (info contexte) ──
    if filters.section7.is_active():
        s7 = filters.section7
        s7_affected: dict[str, list[str]] = {}
        for c in candidates:
            sym = str(getattr(c, "symbol", "")).strip().upper()
            side = str(getattr(c, "side", "")).strip().lower()
            if sym in s7.exclude_all:
                s7_affected.setdefault("s7_exclude_all", []).append(sym)
            elif sym in s7.exclude_flat_pathological:
                s7_affected.setdefault("s7_flat_pathological", []).append(sym)
            elif side == "short" and sym in s7.long_only:
                s7_affected.setdefault("s7_long_only", []).append(sym)
            elif side == "long" and sym in s7.short_only:
                s7_affected.setdefault("s7_short_only", []).append(sym)
            elif sym in s7.monitor:
                s7_affected.setdefault("s7_monitor", []).append(sym)
        if s7_affected:
            _parts = []
            for _rule in sorted(s7_affected.keys()):
                _parts.append(f"{_rule}={len(s7_affected[_rule])}")
            LOGGER.info(
                "batch_diagnostics §7 candidats affectés (batch=%s): %s",
                filters.batch_id, " | ".join(_parts),
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
    # Détail par règle pour le log
    excluded_by_rule: dict[str, list[str]] = {}
    excluded_long_syms: list[str] = []
    excluded_short_syms: list[str] = []
    filtered_entries: list[PortfolioEntry] = []
    for entry in entries:
        sym = str(entry.symbol).strip().upper()
        side = str(getattr(entry, "side", "buy") or "buy").strip().lower()

        if side in ("sell", "short") and sym in filters.exclude_short:
            excluded_count += 1
            excluded_short_syms.append(sym)
            _rule = _classify_exclusion(sym, "short", filters)
            excluded_by_rule.setdefault(_rule, []).append(sym)
            continue
        if side in ("buy", "long") and sym in filters.exclude_long:
            excluded_count += 1
            excluded_long_syms.append(sym)
            _rule = _classify_exclusion(sym, "long", filters)
            excluded_by_rule.setdefault(_rule, []).append(sym)
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
        # ── Détail par règle ──
        if excluded_by_rule:
            _lines.append("  📋 Détail par règle:")
            for _rule in sorted(excluded_by_rule.keys()):
                _syms = sorted(excluded_by_rule[_rule])
                _lines.append(f"     {_rule} ({len(_syms)}): {', '.join(_syms)}")
        _lines.append(
            f"  ➡️ {len(entries)}→{len(filtered_entries)} entries (−{excluded_count} exclus)"
        )
        LOGGER.info("\n".join(_lines))

    # ── §7.0 — log supplémentaire si actif ──
    if filters.section7.is_active():
        s7 = filters.section7
        LOGGER.info(
            "batch_diagnostics §7 actif (batch=%s): "
            "exclude_all=%d flat_path=%d long_only=%d short_only=%d monitor=%d",
            filters.batch_id,
            len(s7.exclude_all), len(s7.exclude_flat_pathological),
            len(s7.long_only), len(s7.short_only), len(s7.monitor),
        )
        if s7.monitor:
            LOGGER.warning(
                "batch_diagnostics §7 MONITOR (⚠️ à surveiller, non exclus): %s",
                ", ".join(sorted(s7.monitor)),
            )

    return filtered_entries, excluded_count, filters.batch_id
