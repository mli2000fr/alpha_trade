"""ihm/components/market_regime_banner.py — Bannière compacte du régime marché.

Composant réutilisable affichant le **dernier `MarketRegimeSnapshot` persisté**
par ``run_execution.run()`` dans ``artifacts/market_regime/``. Permet à toutes
les pages opérationnelles (Overview, Execution, Risk, Backtesting…) de
montrer en un coup d'œil :

* le mode courant (``normal`` / ``capital_preservation`` / ``close_only`` /
  ``cash_only``),
* le ``risk_multiplier`` et ``allowed_slots`` effectifs,
* les patterns calendaires actifs et secteurs blacklistés,
* la valeur VIX / Δ 10Y (5j) issue du provider EODHD/Stooq,
* l'autorisation ou non d'ouvrir de nouvelles entrées.

Usage minimal :

>>> from ihm.components.market_regime_banner import render_market_regime_banner
>>> render_market_regime_banner()

Le composant est strictement en lecture, jamais bloquant : tout problème
(absence de fichier, JSON invalide…) se traduit par un ``return`` silencieux
ou un ``st.caption`` neutre, conformément à l'objectif C17 du plan
``prompt/parttern/plan.md`` (axe C — pré-flight live).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "market_regime"

_MODE_BADGE = {
    "normal": ("🟢", "info"),
    "capital_preservation": ("🟠", "warning"),
    "close_only": ("🔴", "error"),
    "cash_only": ("🔴", "error"),
}


def load_latest_snapshot(directory: Path | None = None) -> dict[str, Any] | None:
    """Retourne le snapshot le plus récent ou ``None`` si introuvable.

    Lecture best-effort : aucun raise. Triée par nom de fichier décroissant
    car les snapshots sont nommés ``snapshot_<YYYYMMDDTHHMMSS>_<account>.json``.
    """
    base = directory or ARTIFACTS_DIR
    if not base.exists():
        return None
    files = sorted(base.glob("snapshot_*.json"), reverse=True)
    for fp in files:
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def render_market_regime_banner(
    *,
    snapshot: dict[str, Any] | None = None,
    compact: bool = True,
    show_link_hint: bool = True,
) -> dict[str, Any] | None:
    """Affiche la bannière régime marché dans la page courante.

    Args:
        snapshot: snapshot à afficher. Si ``None``, lit le plus récent depuis
            ``artifacts/market_regime/``.
        compact: si ``True``, n'affiche que mode + 4 métriques principales.
            Sinon, ajoute patterns/secteurs/macro.
        show_link_hint: ajoute une ``st.caption`` rappelant l'existence de
            la page dédiée *Régime Marché*.

    Returns:
        Le snapshot affiché (utile pour tests + composition).
    """
    snap = snapshot if snapshot is not None else load_latest_snapshot()
    if not snap:
        st.caption(
            "📊 Régime marché : aucun snapshot disponible "
            "(le pré-flight `service.market` se déclenche au prochain run d'exécution)."
        )
        return None

    mode = str(snap.get("mode", "normal"))
    badge, _ = _MODE_BADGE.get(mode, ("⚪", "info"))
    risk_mult = float(snap.get("risk_multiplier") or 1.0)
    eff_max = snap.get("effective_max_positions")
    slots = snap.get("allowed_slots")
    allow_new = snap.get("allow_new_entries", True)
    trade_date = snap.get("trade_date") or "—"

    # Bandeau principal coloré selon le mode
    headline = (
        f"{badge} **Régime marché : `{mode}`** — risk×{risk_mult:.2f} · "
        f"slots {slots if slots is not None else '—'} · max_pos "
        f"{eff_max if eff_max is not None else '—'} · "
        f"new_entries {'✅' if allow_new else '🛑'} · {trade_date}"
    )
    if mode in {"close_only", "cash_only"}:
        st.error(headline)
    elif mode == "capital_preservation":
        st.warning(headline)
    else:
        st.info(headline)

    if not compact:
        macro = snap.get("macro") or {}
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "VIX",
            f"{macro.get('vix'):.2f}" if isinstance(macro.get("vix"), (int, float)) else "n/a",
        )
        y10 = macro.get("yield_10y_5d_pct")
        col2.metric(
            "Δ 10Y (5j)",
            f"{y10 * 100:.2f}%" if isinstance(y10, (int, float)) else "n/a",
        )
        col3.metric(
            "Sentiment",
            (snap.get("sentiment") or {}).get("level", "neutral"),
        )

        active = snap.get("active_patterns") or []
        if active:
            st.caption("Patterns actifs : " + ", ".join(active))
        blocked = snap.get("blocked_sectors") or []
        if blocked:
            st.caption("Secteurs bloqués : " + ", ".join(blocked))
        reasons = snap.get("reasons") or []
        if reasons:
            st.caption("Motifs : " + " · ".join(str(r) for r in reasons))

    if show_link_hint:
        st.caption(
            "ℹ️ Détails complets et historique → page **Régime Marché** "
            "(menu *Trading*)."
        )
    return snap


__all__ = ["render_market_regime_banner", "load_latest_snapshot", "ARTIFACTS_DIR"]

