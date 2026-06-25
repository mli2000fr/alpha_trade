"""ihm/pages/market_regime.py — Page Streamlit ``Régime Marché``.

Affiche, en s'appuyant sur ``service.market`` :

* le snapshot **courant** (mode, risk_multiplier, allowed_slots, patterns
  actifs, secteurs blacklistés, earnings shield, buyback blackout, valeurs
  macro VIX/10Y…),
* l'historique des snapshots persistés dans ``artifacts/market_regime/``
  par ``run_execution.py``.

La page expose aussi une action opérateur pour réalimenter manuellement
``stock_macro_indicators_daily`` sur une plage de dates.
"""
from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "market_regime"

DEMO_SCENARIOS: dict[str, str] = {
    "sentiment_warning": "Sentiment warning → capital_preservation",
    "sentiment_critical_live": "Sentiment critique live → close_only",
    "vix_high": "VIX élevé → capital_preservation",
}


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
            "vxn": (data.get("macro") or {}).get("vxn"),
            "vix3m": (data.get("macro") or {}).get("vix3m"),
            "move": (data.get("macro") or {}).get("move"),
            "yield_10y_5d_pct": (data.get("macro") or {}).get("yield_10y_5d_pct"),
            "reasons": ", ".join(data.get("reasons") or []),
        })
    return pd.DataFrame(rows)


def _compute_live_snapshot(trade_date: _date, equity: float | None) -> dict[str, Any]:
    """Calcule un snapshot à la volée pour l'IHM (cycle hors-run)."""
    yaml_cfg = _load_yaml()
    try:
        from service.market import (
            DbSentimentScoreProvider,
            build_default_macro_provider,
            build_snapshot,
            parse_market_regimes,
        )
    except Exception as exc:  # pragma: no cover - import-time
        return {"error": f"Import service.market impossible : {exc}"}
    cfg = parse_market_regimes(yaml_cfg.get("market_regimes"))
    provider = build_default_macro_provider(yaml_cfg)
    sentiment_provider = DbSentimentScoreProvider(trade_date)
    snap = build_snapshot(
        trade_date,
        config=cfg,
        equity=float(equity) if equity else None,
        execution_context="live",
        macro_provider=provider,
        sentiment_score_provider=sentiment_provider,
        use_cache=False,
    )
    if hasattr(snap, "to_dict"):
        return snap.to_dict()
    if hasattr(snap, "to_summary_dict"):
        return snap.to_summary_dict()
    return {"error": f"Snapshot non sérialisable : {type(snap).__name__}"}


def _populate_macro_table(start_date: _date, end_date: _date) -> dict[str, Any]:
    yaml_cfg = _load_yaml()
    try:
        from service.market import populate_macro_indicators_table
    except Exception as exc:  # pragma: no cover - import-time
        return {"error": f"Import service.market impossible : {exc}"}
    try:
        return populate_macro_indicators_table(
            start_date=start_date,
            end_date=end_date,
            yaml_cfg=yaml_cfg,
        )
    except Exception as exc:
        return {"error": str(exc)}


def _recompute_regime_table(start_date: _date, end_date: _date, equity: float | None) -> dict[str, Any]:
    yaml_cfg = _load_yaml()
    try:
        from service.market import recompute_macro_regime_table
    except Exception as exc:  # pragma: no cover - import-time
        return {"error": f"Import service.market impossible : {exc}"}
    try:
        return recompute_macro_regime_table(
            start_date=start_date,
            end_date=end_date,
            yaml_cfg=yaml_cfg,
            equity=float(equity) if equity else None,
        )
    except Exception as exc:
        return {"error": str(exc)}


def _format_macro_import_command(start_date: _date, end_date: _date) -> str:
    import sys
    return " ".join([
        sys.executable, "-u", "-m", "service.market", "populate-macro",
        "--start", start_date.isoformat(),
        "--end", end_date.isoformat(),
    ])


def _format_regime_recompute_command(start_date: _date, end_date: _date, equity: float | None) -> str:
    import sys
    parts = [
        sys.executable, "-u", "-m", "service.market", "recompute-regime",
        "--start", start_date.isoformat(),
        "--end", end_date.isoformat(),
    ]
    if equity:
        parts.extend(["--equity", str(equity)])
    return " ".join(parts)


def _format_macro_runtime_context(yaml_cfg: dict[str, Any]) -> str:
    mr_cfg = yaml_cfg.get("market_regimes") if isinstance(yaml_cfg, dict) else {}
    mr_cfg = mr_cfg if isinstance(mr_cfg, dict) else {}
    vix_cfg = mr_cfg.get("vix") if isinstance(mr_cfg.get("vix"), dict) else {}
    vxn_cfg = mr_cfg.get("vxn") if isinstance(mr_cfg.get("vxn"), dict) else {}
    vix3m_cfg = mr_cfg.get("vix3m") if isinstance(mr_cfg.get("vix3m"), dict) else {}
    move_cfg = mr_cfg.get("move") if isinstance(mr_cfg.get("move"), dict) else {}
    rvx_cfg = mr_cfg.get("rvx") if isinstance(mr_cfg.get("rvx"), dict) else {}
    yields_cfg = mr_cfg.get("yields") if isinstance(mr_cfg.get("yields"), dict) else {}
    fred_cfg = yaml_cfg.get("fred") if isinstance(yaml_cfg, dict) and isinstance(yaml_cfg.get("fred"), dict) else {}
    macro_provider = str(mr_cfg.get("macro_provider") or "composite")
    fred_series = str(
        yields_cfg.get("fred_series_10y")
        or fred_cfg.get("series_10y")
        or "DGS10"
    )
    vix_symbol = str(vix_cfg.get("symbol") or "VIX.INDX")
    vix_short_symbol = str(vix_cfg.get("short_symbol") or "VIX9D.INDX")
    vxn_symbol = str(vxn_cfg.get("symbol") or "VXN.INDX")
    vix3m_symbol = str(vix3m_cfg.get("symbol") or "VIX3M.INDX")
    move_symbol = str(move_cfg.get("symbol") or "MOVE.INDX")
    rvx_symbol = str(rvx_cfg.get("symbol") or "RVX.INDX")
    return "\n".join([
        f"Config utilisée: {CONFIG_PATH}",
        f"macro_provider: {macro_provider}",
        f"fred_series_10y: {fred_series}",
        f"vix.symbol: {vix_symbol}",
        f"vix.short_symbol: {vix_short_symbol}",
        f"vxn.symbol: {vxn_symbol}",
        f"vix3m.symbol: {vix3m_symbol}",
        f"move.symbol: {move_symbol}",
        f"rvx.symbol: {rvx_symbol}",
    ])


def _compute_demo_snapshot(scenario: str, trade_date: _date, equity: float | None) -> dict[str, Any]:
    """Construit un snapshot déterministe pour validation IHM / métier.

    Utile quand `config.yaml` laisse `market_regimes.enabled = false` ou quand
    les providers externes ne permettent pas de démontrer facilement un mode
    non-`normal` depuis l'interface.
    """
    try:
        from service.market import build_snapshot, parse_market_regimes
    except Exception as exc:  # pragma: no cover - import-time
        return {"error": f"Import service.market impossible : {exc}"}

    mr_cfg: dict[str, Any] = {"enabled": True}
    kwargs: dict[str, Any] = {
        "equity": float(equity) if equity else None,
        "execution_context": "live",
        "use_cache": False,
    }

    if scenario == "sentiment_warning":
        mr_cfg["sentiment_circuit_breaker"] = {
            "enabled": True,
            "warning_threshold": -0.15,
            "critical_threshold": -0.30,
            "warning_max_positions": 2,
            "critical_mode_live": "close_only",
            "critical_mode_backtest": "cash_only",
        }
        kwargs["sentiment_score_provider"] = lambda _days: -0.20
    elif scenario == "sentiment_critical_live":
        mr_cfg["sentiment_circuit_breaker"] = {
            "enabled": True,
            "warning_threshold": -0.15,
            "critical_threshold": -0.30,
            "warning_max_positions": 2,
            "critical_mode_live": "close_only",
            "critical_mode_backtest": "cash_only",
        }
        kwargs["sentiment_score_provider"] = lambda _days: -0.50
    elif scenario == "vix_high":
        mr_cfg["vix"] = {
            "enabled": True,
            "high_threshold": 25.0,
            "inverted_curve_mode": "capital_preservation",
        }

        class _DemoMacroProvider:
            def get_vix_close(self, _trade_date: _date) -> float | None:
                return 30.0

            def get_vix_short_term_close(self, _trade_date: _date) -> float | None:
                return 24.0

            def get_us10y_history(self, _trade_date: _date, lookback_days: int) -> list[float] | None:
                return [4.0] * max(lookback_days, 2)

        kwargs["macro_provider"] = _DemoMacroProvider()
    else:
        return {"error": f"Scénario de démo inconnu : {scenario}"}

    snap = build_snapshot(trade_date, config=parse_market_regimes(mr_cfg), **kwargs)
    if hasattr(snap, "to_dict"):
        payload = snap.to_dict()
    elif hasattr(snap, "to_summary_dict"):
        payload = snap.to_summary_dict()
    else:
        return {"error": f"Snapshot de démo non sérialisable : {type(snap).__name__}"}
    payload.setdefault("reasons", [])
    payload["reasons"] = list(payload.get("reasons") or []) + [f"demo_scenario:{scenario}"]
    return payload


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
    sentiment = snap.get("sentiment") or {}
    col5, col6, col7 = st.columns(3)
    col5.metric("VIX", f"{macro.get('vix'):.2f}" if macro.get("vix") is not None else "n/a")
    col6.metric("VIX inversion", "oui" if macro.get("vix_curve_inverted") else "non")
    col7.metric(
        "Δ 10Y (5j, %)",
        f"{float(macro.get('yield_10y_5d_pct')) * 100:.2f}%" if isinstance(macro.get("yield_10y_5d_pct"), (int, float)) else "n/a",
    )

    col_vxn, col_rvx, col_vix3m, col_move = st.columns(4)
    col_vxn.metric("VXN (Nasdaq vol)", f"{macro.get('vxn'):.2f}" if macro.get("vxn") is not None else "n/a")
    col_rvx.metric("RVX (Russell 2000 vol)", f"{macro.get('rvx'):.2f}" if macro.get("rvx") is not None else "n/a")
    vix3m_raw = macro.get("vix3m")
    vix_raw = macro.get("vix")
    if vix_raw is not None and vix3m_raw is not None and float(vix3m_raw) > 0:
        ratio = float(vix_raw) / float(vix3m_raw)
        ratio_str = f"{vix3m_raw:.2f}  (ratio VIX/VIX3M={ratio:.2f})"
        if ratio > 1.0:
            ratio_str += " ⚠️ backwardation"
    elif vix3m_raw is not None:
        ratio_str = f"{float(vix3m_raw):.2f}"
    else:
        ratio_str = "n/a"
    col_vix3m.metric("VIX3M (term structure)", ratio_str)
    col_move.metric("MOVE (bond vol)", f"{macro.get('move'):.2f}" if macro.get("move") is not None else "n/a")

    col8, col9, col10 = st.columns(3)
    col8.metric(
        "Sentiment score",
        f"{float(sentiment.get('score')):.3f}" if isinstance(sentiment.get("score"), (int, float)) else "n/a",
    )
    col9.metric("Sentiment level", str(sentiment.get("level") or "n/a"))
    col10.metric("Source sentiment", str(sentiment.get("source") or "n/a"))

    st.markdown("**Pourquoi ce mode ?**")
    mode_why = snap.get("mode_why") or {}
    summary = str(mode_why.get("summary") or "Explication indisponible.")
    triggered = [item for item in (snap.get("decision_trace") or []) if item.get("triggered")]
    if mode == "normal":
        st.success(summary)
    elif mode in {"close_only", "cash_only"}:
        st.error(summary)
    else:
        st.warning(summary)

    if triggered:
        st.caption("Sources déclenchantes :")
        for item in triggered:
            label = str(item.get("label") or item.get("source") or "source")
            message = str(item.get("message") or "")
            resulting_mode = str(item.get("resulting_mode") or "normal")
            st.markdown(f"- **{label}** → `{resulting_mode}` — {message}")
    else:
        st.caption("Aucune source défensive active ; détails d'observation ci-dessous.")

    trace_rows = []
    for item in snap.get("decision_trace") or []:
        trace_rows.append({
            "source": item.get("source"),
            "label": item.get("label"),
            "déclenché": "oui" if item.get("triggered") else "non",
            "sévérité": item.get("severity"),
            "mode suggéré": item.get("resulting_mode"),
            "message": item.get("message"),
        })
    if trace_rows:
        with st.expander("Voir toute la trace de décision", expanded=False):
            st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)

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

    st.markdown("---")
    st.subheader("🗃️ Alimenter `stock_macro_indicators_daily`")
    st.caption(
        "Recharge manuellement la table macro sur une plage de séances NYSE en appelant les providers configurés "
        "(EODHD / FRED / Stooq selon `config.yaml`). Les 8 indicateurs (VIX, VIX9D, VXN, VIX3M, MOVE, RVX, 10Y) "
        "sont persistés dans `stock_macro_indicators_daily`. Les lignes existantes sont écrasées par upsert."
    )
    import_col1, import_col2, import_col3 = st.columns([1, 1, 1])
    import_start = import_col1.date_input(
        "Date de début import macro",
        value=_date.today(),
        key="market_regime_macro_import_start",
        help="Première séance à recalculer dans `stock_macro_indicators_daily`.",
    )
    import_end = import_col2.date_input(
        "Date de fin import macro",
        value=_date.today(),
        key="market_regime_macro_import_end",
        help="Dernière séance à recalculer dans `stock_macro_indicators_daily`.",
    )
    if import_col3.button("📥 Alimenter la table macro", use_container_width=True, key="market_regime_macro_import_button"):
        if import_end < import_start:
            st.error("La date de fin doit être postérieure ou égale à la date de début.")
        else:
            with st.spinner("Alimentation de `stock_macro_indicators_daily`…"):
                st.session_state["market_regime_macro_import_summary"] = _populate_macro_table(import_start, import_end)

    st.code(
        _format_macro_import_command(import_start, import_end),
        language="powershell",
    )

    import_summary = st.session_state.get("market_regime_macro_import_summary")
    if isinstance(import_summary, dict):
        if import_summary.get("error"):
            st.error(str(import_summary.get("error")))
        else:
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("Séances traitées", int(import_summary.get("sessions_total") or 0))
            metric_col2.metric("Lignes persistées", int(import_summary.get("persisted_rows") or 0))
            metric_col3.metric("Séances sans donnée", int(import_summary.get("missing_rows") or 0))
            rows = import_summary.get("rows")
            if isinstance(rows, list) and rows:
                with st.expander("Voir le détail du dernier import macro", expanded=False):
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### ♻️ Recalcul des colonnes de régime")
    st.info(
        "Cette action réutilise les valeurs déjà stockées dans `stock_macro_indicators_daily` "
        "(`vix`, `vix9d`, `ten_y`, `vxn`, `vix3m`, `move`, `rvx`) et recalcule uniquement les colonnes dérivées de régime "
        "(`mode`, `risk_multiplier`, `effective_max_positions`, `allow_new_entries`, "
        "`vix_curve_inverted`, `yield_10y_5d_pct`, `sentiment_*`)."
    )
    recalc_col1, recalc_col2 = st.columns([1, 1])
    recalc_equity = recalc_col1.number_input(
        "Equity simulée pour le recalcul ($)",
        min_value=0.0,
        value=0.0,
        step=500.0,
        key="market_regime_macro_recompute_equity",
        help="0 = ignorer la contrainte de capital/min notional lors du recalcul des colonnes dérivées.",
    )
    recalc_equity_value = recalc_equity if recalc_equity > 0 else None
    if st.button("♻️ Recalculer régime", use_container_width=True, key="market_regime_macro_recompute_button"):
        if import_end < import_start:
            st.error("La date de fin doit être postérieure ou égale à la date de début.")
        else:
            with st.spinner("Recalcul des colonnes de régime…"):
                st.session_state["market_regime_macro_recompute_summary"] = _recompute_regime_table(
                    import_start,
                    import_end,
                    recalc_equity_value,
                )

    st.code(
        _format_regime_recompute_command(import_start, import_end, recalc_equity_value),
        language="powershell",
    )

    recompute_summary = st.session_state.get("market_regime_macro_recompute_summary")
    if isinstance(recompute_summary, dict):
        if recompute_summary.get("error"):
            st.error(str(recompute_summary.get("error")))
        else:
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("Séances parcourues", int(recompute_summary.get("sessions_total") or 0))
            metric_col2.metric("Lignes recalculées", int(recompute_summary.get("persisted_rows") or 0))
            metric_col3.metric("Séances en erreur / absentes", int(recompute_summary.get("missing_rows") or 0))
            rows = recompute_summary.get("rows")
            if isinstance(rows, list) and rows:
                with st.expander("Voir le détail du dernier recalcul de régime", expanded=False):
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- Snapshot à la volée -------------------------------------------------
    st.markdown("---")
    st.subheader("Calcul d'un snapshot à la volée")
    col_a, col_b, col_c = st.columns([1, 1, 1])
    sel_date = col_a.date_input("Date de référence", value=_date.today(), help="Date de référence pour le calcul du snapshot de régime de marché.")
    sel_equity = col_b.number_input("Equity simulée ($)", min_value=0.0, value=2000.0, step=500.0, help="Equity totale simulée en dollars pour le calcul du régime de marché.")
    if col_c.button("🔁 Calculer", use_container_width=True):
        with st.spinner("Calcul du snapshot…"):
            snap = _compute_live_snapshot(sel_date, sel_equity if sel_equity > 0 else None)
        st.session_state["market_regime_last_snap"] = snap

    with st.expander("🧪 Scénarios de validation (démo non destructive)", expanded=False):
        st.caption(
            "Permet de vérifier visuellement les modes non-`normal` sans dépendre "
            "de la config active ni des providers externes."
        )
        scenario_key = st.selectbox(
            "Scénario de démonstration",
            options=list(DEMO_SCENARIOS.keys()),
            format_func=lambda key: DEMO_SCENARIOS.get(str(key), str(key)),
            key="market_regime_demo_scenario",
            help="Scénario de démonstration prédéfini pour simuler un régime de marché sans connexion aux providers externes.",
        )
        if st.button("🧪 Charger ce scénario", use_container_width=True, key="market_regime_demo_button"):
            with st.spinner("Calcul du scénario de démonstration…"):
                st.session_state["market_regime_last_snap"] = _compute_demo_snapshot(
                    scenario_key,
                    sel_date,
                    sel_equity if sel_equity > 0 else None,
                )

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

