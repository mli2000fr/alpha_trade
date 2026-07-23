"""risk_management/batch_diagnostics.py — Filtrage ML batch diagnostics dans Risk.

Appliqué dans l'étape 11 (Risk Management) AVANT la persistance des
``portfolio_targets``, pour que les décisions de filtrage soient auditées
dans ``risk_decisions`` et que l'étape 12 (Execution) n'ait plus qu'un
rôle de filet de sécurité (exclusion uniquement, sans boost).
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from modelFactory.batch_diagnostics import (
    BatchFilters,
    _load_config_defaults,
    get_batch_filters,
)
from risk_management.models import PortfolioEntry

LOGGER = logging.getLogger(__name__)


def apply_batch_diagnostics_to_entries(
    entries: list[PortfolioEntry],
    engine: Any,
    *,
    prefer_multiplier: float | None = None,
    prefer_top_n: int | None = None,
) -> tuple[list[PortfolioEntry], int, int, str | None]:
    """Applique le filtre batch diagnostics aux entries du Risk.

    Étape 1 — Exclusion : retire les entries dont le side est incompatible
              avec les listes exclude_long / exclude_short.
    Étape 2 — Boost prefer : multiplie ``approved_shares`` et ``target_notional``
              pour les symboles du top N.

    Args:
        entries: Liste des PortfolioEntry produites par le PortfolioBuilder.
        engine: Engine SQLAlchemy pour interroger model_batch_diagnostics.
        prefer_multiplier: Multiplicateur de sizing pour les prefer.
            Défaut : config.yaml (prefer_sizing_multiplier) ou 1.2.
        prefer_top_n: Nombre de symboles du top à booster.
            Défaut : config.yaml (prefer_top_n) ou 10.

    Returns:
        (filtered_entries, excluded_count, boosted_count, batch_id)
    """
    if not entries:
        return entries, 0, 0, None

    # ── Charger les filtres ──
    try:
        filters: BatchFilters = get_batch_filters(engine)
    except Exception as exc:
        LOGGER.warning(
            "risk batch_diagnostics: impossible de charger les filtres: %s",
            exc,
        )
        return entries, 0, 0, None

    if not filters.batch_id:
        LOGGER.info("risk batch_diagnostics: aucun batch complété, skip.")
        return entries, 0, 0, None

    # ── Résoudre les paramètres ──
    if prefer_multiplier is None or prefer_top_n is None:
        cfg = _load_config_defaults()
        if prefer_multiplier is None:
            prefer_multiplier = float(cfg.get("prefer_sizing_multiplier", 1.2))
        if prefer_top_n is None:
            prefer_top_n = int(cfg.get("prefer_top_n", 10))

    # ── Construire le prefer set limité à prefer_top_n ──
    prefer_set: frozenset[str] = filters.prefer  # déjà filtré par get_batch_filters
    if filters.prefer:
        prefer_df = filters.all_diagnostics
        if not prefer_df.empty and "rank_position" in prefer_df.columns:
            prefer_set = frozenset(
                prefer_df[
                    (prefer_df["rank_type"] == "top")
                    & (prefer_df["rank_position"] <= prefer_top_n)
                ]["symbol"]
            )

    # ── Étape 1 : Exclusion ──
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

    # ── Étape 2 : Boost prefer ──
    boosted_count = 0
    boosted_syms: list[str] = []
    if prefer_set and prefer_multiplier != 1.0:
        boosted_entries: list[PortfolioEntry] = []
        for entry in filtered_entries:
            sym = str(entry.symbol).strip().upper()
            if sym in prefer_set:
                boosted_count += 1
                boosted_syms.append(sym)
                entry = replace(
                    entry,
                    approved_shares=entry.approved_shares * prefer_multiplier,
                    target_notional=entry.target_notional * prefer_multiplier,
                )
            boosted_entries.append(entry)
        filtered_entries = boosted_entries

    # ── Résumé consolidé ──
    if excluded_count > 0 or boosted_count > 0:
        _lines = [f"batch_diagnostics summary (batch={filters.batch_id}):"]
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
        if boosted_syms:
            _lines.append(
                f"  ⭐ BOOSTÉS x{prefer_multiplier:.1f} ({len(boosted_syms)}): "
                + ", ".join(sorted(boosted_syms))
            )
        _lines.append(
            f"  ➡️ {len(entries)}→{len(filtered_entries)} entries "
            f"(−{excluded_count} exclus, +{boosted_count} boostés)"
        )
        LOGGER.info("\n".join(_lines))

    return filtered_entries, excluded_count, boosted_count, filters.batch_id
