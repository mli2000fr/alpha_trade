"""Pré-flight Market-Aware (Axe C du plan ``prompt/parttern/plan.md``).

Helper formatant un ``MarketRegimeSnapshot`` pour affichage console + JSON
en début de cycle ``run_execution.py``. Délibérément autonome — ne fait
aucun appel I/O (ni broker ni DB).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

LOGGER = logging.getLogger("market_regime_preflight")


def render_text_summary(snapshot_dict: dict[str, Any]) -> str:
    """Rend un résumé lisible (multilignes) du snapshot régime."""
    lines = [
        "=" * 60,
        "  Market-Aware Regime Pre-flight",
        "=" * 60,
        f"  trade_date              = {snapshot_dict.get('trade_date')}",
        f"  mode                    = {snapshot_dict.get('mode')}",
        f"  risk_multiplier         = {snapshot_dict.get('risk_multiplier'):.2f}"
        if snapshot_dict.get('risk_multiplier') is not None else "  risk_multiplier         = (n/a)",
        f"  effective_max_positions = {snapshot_dict.get('effective_max_positions')}",
        f"  enforced_min_notional   = {snapshot_dict.get('enforced_min_notional')}",
        f"  allowed_slots           = {snapshot_dict.get('allowed_slots')}",
        f"  allow_new_entries       = {snapshot_dict.get('allow_new_entries')}",
        f"  active_patterns         = {snapshot_dict.get('active_patterns') or '[]'}",
        f"  blocked_sectors         = {snapshot_dict.get('blocked_sectors') or '[]'}",
        f"  earnings_shield         = {len(snapshot_dict.get('earnings_shielded_symbols') or {})} sym.",
        f"  buyback_blackout        = {len(snapshot_dict.get('buyback_blackout_symbols') or {})} sym.",
        f"  macro                   = {snapshot_dict.get('macro') or {}}",
        f"  reasons                 = {snapshot_dict.get('reasons') or '[]'}",
        "=" * 60,
    ]
    return "\n".join(lines)


def emit_preflight(snapshot_dict: dict[str, Any], *, also_log: bool = True) -> str:
    """Construit le résumé + journalise (best-effort)."""
    text = render_text_summary(snapshot_dict)
    if also_log:
        for line in text.splitlines():
            LOGGER.info(line)
    return text


def derive_entry_mode(snapshot_dict: dict[str, Any]) -> str:
    """Mappe le mode du snapshot vers ``ExecutionConfig.entry_mode``."""
    mode = snapshot_dict.get("mode") or "normal"
    if mode in ("close_only", "cash_only", "capital_preservation"):
        return mode
    if not snapshot_dict.get("allow_new_entries", True):
        return "close_only"
    return "normal"


__all__ = ["render_text_summary", "emit_preflight", "derive_entry_mode"]

