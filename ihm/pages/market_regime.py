"""ihm/pages/market_regime.py — Page Streamlit ``Régime Marché``.

Affiche, en s'appuyant sur ``service.market`` :

* le snapshot **courant** (mode, risk_multiplier, allowed_slots, patterns
  actifs, secteurs blacklistés, earnings shield, buyback blackout, valeurs
  macro VIX/10Y…),
* l'historique des snapshots persistés dans ``artifacts/market_regime/``
  par ``run_execution.py``.

Aucune action métier n'est déclenchée : la page est strictement en lecture.
Elle remplit l'objectif C17 du plan ``prompt/parttern/plan.md`` côté IHM.
"""
from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "market_regime"


def _load_yaml() -> dict[str, Any]:
    try:
        from common.config_loader import load_config
        return load_config() or {}
    except Exception:
        return {}


def _list_history(limit: int = 50) -> list[Path]:
    if not ARTIFACTS_DIR.exists():
        return []
    files = sorted(ARTIFACTS_DIR.glob("snapshot_*.json"), reverse=True)
    return files[:limit]


def _load_history_df(limit: int = 50) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fp in _list_history(limit=limit):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({
            "fichier": fp.name,
            "trade_date": data.get("trade_date"),
            "mode": data.get("mode"),
            "risk_multiplier": data.get("risk_multiplier"),
            "effective_max_positions": data.get("effective_max_positions"),
            "allowed_slots": data.get("allowed_slots"),
            "allow_new_entries": data.get("allow_new_entries"),
            "active_patterns": ", ".join(data.get("active_patterns") or []),
            "blocked_sectors": ", ".join(data.get("blocked_sectors") or []),
            "earnings_shield_n": len(data.get("earnings_shielded_symbols") or {}),
            "buyback_blackout_n": len(data.get("buyback_blackout_symbols") or {}),
            "vix": (data.get("macro") or {}).get("vix"),
            "yield_10y_5d_pct": (data.get("macro") or {}).get("yield_10y_5d_pct"),
            "reasons": ", ".join(data.get("reasons") or []),
        })
    return pd.DataFrame(rows)


def _compute_live_snapshot(trade_date: _date, equity: float | None) -> dict[str, Any]:
    """Calcule un snapshot à la volée pour l'IHM (cycle hors-run)."""
    yaml_cfg = _load_yaml()
    try:
        from service.market import (
            build_default_macro_provider,
            build_snapshot,
            parse_market_regimes,
        )
    except Exception as exc:  # pragma: no cover - import-time
        return {"error": f"Import service.market impossible : {exc}"}
    cfg = parse_market_regimes(yaml_cfg.get("market_regimes"))
    provider = build_default_macro_provider(yaml_cfg)
    snap = build_snapshot(
        trade_date,
        config=cfg,
        equity=float(equity) if equity else None,
        execution_context="live",
        macro_provider=provider,
        use_cache=False,
    )
    if hasattr(snap, "to_dict"):
        return snap.to_dict()
    if hasattr(snap, "to_summary_dict"):
        return snap.to_summary_dict()
    return {"error": f"Snapshot non sérialisable : {type(snap).__name__}"}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_summary(snap: dict[str, Any]) -> None:
    if "error" in snap:
        st.error(snap["error"])
        return
    mode = snap.get("mode", "normal")
    badge = {
        "normal": "🟢",
        "capital_preservation": "🟠",
        "close_only": "🔴",
        "cash_only": "🔴",
    }.get(mode, "⚪")
    st.subheader(f"{badge} Mode régime : `{mode}`")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Risk multiplier", f"{float(snap.get('risk_multiplier') or 1.0):.2f}")
    col2.metric("Effective max positions", snap.get("effective_max_positions") or "—")
    col3.metric("Allowed slots", snap.get("allowed_slots") or "—")
    col4.metric("Allow new entries", "✅" if snap.get("allow_new_entries") else "🛑")

    macro = snap.get("macro") or {}
    col5, col6, col7 = st.columns(3)
    col5.metric("VIX", f"{macro.get('vix'):.2f}" if macro.get("vix") is not None else "n/a")
    col6.metric("VIX inversion", "oui" if macro.get("vix_curve_inverted") else "non")
    col7.metric(
        "Δ 10Y (5j, %)",
        f"{macro.get('yield_10y_5d_pct') * 100:.2f}%" if isinstance(macro.get("yield_10y_5d_pct"), (int, float)) else "n/a",
    )

    if snap.get("active_patterns"):
        st.markdown("**Patterns calendaires actifs :**")
        st.write(", ".join(snap["active_patterns"]))

    if snap.get("blocked_sectors"):
        st.markdown("**Secteurs blacklistés :**")
        st.write(", ".join(snap["blocked_sectors"]))

    eshield = snap.get("earnings_shielded_symbols") or {}
    if eshield:
        st.markdown(f"**Earnings shield :** {len(eshield)} symbole(s)")
        st.dataframe(
            pd.DataFrame([{"symbol": s, "mode": m} for s, m in eshield.items()]),
            use_container_width=True,
            hide_index=True,
        )

    blackout = snap.get("buyback_blackout_symbols") or {}
    if blackout:
        st.markdown(f"**Buyback blackout :** {len(blackout)} symbole(s)")
        st.dataframe(
            pd.DataFrame([{"symbol": s, "ml_score_multiplier": m} for s, m in blackout.items()]),
            use_container_width=True,
            hide_index=True,
        )

    if snap.get("reasons"):
        st.caption("Raisons : " + " · ".join(snap["reasons"]))


def render() -> None:
    st.title("📊 Régime Marché — Couche Market-Aware")
    st.caption(
        "Pré-flight `service.market.regime_manager` : Tax Day, Sept. Slump, "
        "Santa, OpEx, VIX, 10Y, sentiment circuit breaker, earnings shield, "
        "buyback blackout. Cf. `prompt/parttern/plan.md` (axes A → F)."
    )

    yaml_cfg = _load_yaml()
    mr_cfg = yaml_cfg.get("market_regimes") or {}
    enabled = bool(mr_cfg.get("enabled", False))
    if not enabled:
        st.warning(
            "`market_regimes.enabled = false` dans `config.yaml`. "
            "Les snapshots resteront neutres tant que la couche n'est pas activée."
        )

    with st.expander("🔧 Configuration active (config.yaml > market_regimes)", expanded=False):
        st.json(mr_cfg)

    # --- Snapshot à la volée -------------------------------------------------
    st.markdown("---")
    st.subheader("Calcul d'un snapshot à la volée")
    col_a, col_b, col_c = st.columns([1, 1, 1])
    sel_date = col_a.date_input("Date de référence", value=_date.today())
    sel_equity = col_b.number_input("Equity simulée ($)", min_value=0.0, value=2000.0, step=500.0)
    if col_c.button("🔁 Calculer", use_container_width=True):
        with st.spinner("Calcul du snapshot…"):
            snap = _compute_live_snapshot(sel_date, sel_equity if sel_equity > 0 else None)
        st.session_state["market_regime_last_snap"] = snap

    snap = st.session_state.get("market_regime_last_snap")
    if snap:
        _render_summary(snap)
        with st.expander("Snapshot brut (JSON)", expanded=False):
            st.json(snap)

    # --- Historique persisté --------------------------------------------------
    st.markdown("---")
    st.subheader("Historique des snapshots persistés")
    df = _load_history_df()
    if df.empty:
        st.info(
            "Aucun snapshot persisté trouvé dans "
            f"`{ARTIFACTS_DIR.relative_to(Path.cwd()) if ARTIFACTS_DIR.exists() else ARTIFACTS_DIR}`. "
            "Les snapshots sont créés à chaque run de `run_execution.py`."
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


run_page_if_standalone(__file__, render)

