"""Sprint S9 — Page Streamlit "Parité Backtest ↔ Live".

Lit les artefacts ``artifacts/parity_runs/<YYYY-MM-DD>/parity_summary.json``
écrits par :mod:`scripts.run_daily_parity` et expose :

- KPI (matched / divergent / score) pour la date sélectionnée ;
- tableau filtrable des divergences ;
- bouton « relancer » (best-effort, subprocess) ;
- **Sprint S11 / S11.5** — vue rolling 30 j (ligne de score quotidien),
  agrégat top divergences récurrentes par symbole, drill-down par symbole.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

PARITY_ROOT = Path("artifacts/parity_runs")


def _list_available_dates(root: Path = PARITY_ROOT) -> list[str]:
    if not root.exists():
        return []
    out: list[str] = []
    for entry in sorted(root.iterdir(), reverse=True):
        if entry.is_dir() and (entry / "parity_summary.json").exists():
            out.append(entry.name)
    return out


def _load_summary(trade_date: str, root: Path = PARITY_ROOT) -> dict | None:
    target = root / trade_date / "parity_summary.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("[parity_page] lecture %s impossible: %s", target, exc)
        return None


def load_rolling_summaries(
    *, root: Path = PARITY_ROOT, window: int = 30
) -> list[dict[str, Any]]:
    """Charge les ``window`` derniers ``parity_summary.json`` (ordre chrono décroissant).

    Sprint S11 / S11.5 — entrée du dashboard rolling. Pure (testable sans Streamlit).
    """
    summaries: list[dict[str, Any]] = []
    for trade_date in _list_available_dates(root)[:window]:
        payload = _load_summary(trade_date, root)
        if payload is None:
            continue
        payload.setdefault("trade_date", trade_date)
        summaries.append(payload)
    return summaries


def aggregate_top_divergent_symbols(
    summaries: list[dict[str, Any]],
    *,
    top_n: int = 20,
    threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Agrège les divergences par symbole sur l'ensemble des summaries fournis.

    Retourne une liste triée par fréquence décroissante :
    ``[{"symbol": "AAPL", "divergent_days": 5, "total_days": 30, "kinds": {...}}, ...]``
    """
    per_symbol: dict[str, dict[str, Any]] = {}
    total_days = len(summaries)
    for summary in summaries:
        seen: set[str] = set()
        for row in summary.get("rows") or []:
            symbol = str(row.get("symbol") or "").strip()
            if not symbol:
                continue
            kind = str(row.get("divergence_kind") or "").strip()
            if not kind or kind == "match":
                continue
            entry = per_symbol.setdefault(
                symbol, {"symbol": symbol, "divergent_days": 0, "kinds": Counter()}
            )
            entry["kinds"][kind] += 1
            if symbol not in seen:
                entry["divergent_days"] += 1
                seen.add(symbol)
    aggregated = []
    for entry in per_symbol.values():
        if entry["divergent_days"] < threshold:
            continue
        aggregated.append(
            {
                "symbol": entry["symbol"],
                "divergent_days": entry["divergent_days"],
                "total_days": total_days,
                "frequency_pct": (entry["divergent_days"] / total_days) if total_days else 0.0,
                "kinds": dict(entry["kinds"]),
            }
        )
    aggregated.sort(key=lambda r: (-r["divergent_days"], r["symbol"]))
    return aggregated[:top_n]


def _badge_color(score: float, threshold: float = 0.10) -> str:
    if score <= threshold * 0.5:
        return "🟢"
    if score <= threshold:
        return "🟡"
    return "🔴"


def _render_rolling_section(st, pd, summaries: list[dict[str, Any]]) -> None:
    """Sprint S11 / S11.5 — rendu de la section rolling 30 j."""
    st.subheader("📈 Vue rolling")
    if not summaries:
        st.info("Aucune donnée rolling disponible.")
        return

    rolling_df = pd.DataFrame(
        [
            {
                "trade_date": pd.to_datetime(s.get("trade_date")),
                "divergence_score": float(s.get("divergence_score") or 0.0),
                "n_matched": int(s.get("n_matched") or 0),
                "n_divergent": int(s.get("n_divergent") or 0),
            }
            for s in summaries
        ]
    ).sort_values("trade_date").reset_index(drop=True)

    cols = st.columns(4)
    cols[0].metric("Jours analysés", len(rolling_df))
    cols[1].metric("Score moyen", f"{rolling_df['divergence_score'].mean():.2%}")
    cols[2].metric("Score max", f"{rolling_df['divergence_score'].max():.2%}")
    cols[3].metric(
        "Jours > 10 %", int((rolling_df["divergence_score"] > 0.10).sum())
    )

    st.line_chart(rolling_df.set_index("trade_date")["divergence_score"])

    st.subheader("🔝 Top symboles divergents (récurrence)")
    top = aggregate_top_divergent_symbols(summaries, top_n=20)
    if not top:
        st.info("Aucun symbole récurrent dans la fenêtre.")
    else:
        top_df = pd.DataFrame(
            [
                {
                    "Symbole": row["symbol"],
                    "Jours divergents": row["divergent_days"],
                    "Total": row["total_days"],
                    "Fréquence": f"{row['frequency_pct']:.1%}",
                    "Catégories": ", ".join(f"{k}:{v}" for k, v in sorted(row["kinds"].items())),
                }
                for row in top
            ]
        )
        st.dataframe(top_df, use_container_width=True, hide_index=True)


def _render_symbol_drilldown(st, pd, summaries: list[dict[str, Any]]) -> None:
    """Sprint S11 / S11.5 — drill-down par symbole."""
    st.subheader("🔍 Drill-down par symbole")
    all_symbols: set[str] = set()
    for summary in summaries:
        for row in summary.get("rows") or []:
            symbol = str(row.get("symbol") or "").strip()
            if symbol:
                all_symbols.add(symbol)
    if not all_symbols:
        st.info("Aucun symbole exploitable dans la fenêtre.")
        return

    options = sorted(all_symbols)
    selected_symbol = st.selectbox("Symbole à inspecter", options=options, key="parity_drilldown_symbol")
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        trade_date = summary.get("trade_date")
        for row in summary.get("rows") or []:
            if str(row.get("symbol") or "").strip() != selected_symbol:
                continue
            entry = dict(row)
            entry["trade_date"] = trade_date
            rows.append(entry)
    if not rows:
        st.info(f"{selected_symbol} : aucune ligne trouvée dans la fenêtre.")
        return
    df = pd.DataFrame(rows).sort_values("trade_date")
    st.dataframe(df, use_container_width=True, hide_index=True)


def render() -> None:
    """Entry-point Streamlit (signature attendue par ihm.services.navigation)."""
    try:
        import streamlit as st
    except ImportError:  # pragma: no cover - hors contexte Streamlit
        LOGGER.error("[parity_page] streamlit indisponible — page non rendable.")
        return

    import pandas as pd

    st.title("🔀 Parité Backtest ↔ Live")
    st.caption("Compare les décisions risk live vs replay backtest pour détecter les divergences (Sprint S9 / S11).")

    available = _list_available_dates()
    if not available:
        st.info(
            "Aucun run de parité disponible. Lance `python -m scripts.run_daily_parity --trade-date YYYY-MM-DD` "
            "pour produire un premier artefact."
        )
        return

    # --- Sprint S11 / S11.5 — vue rolling 30 j en haut de page ---
    rolling_window = st.sidebar.number_input(
        "Fenêtre rolling (jours)", min_value=7, max_value=365, value=30, step=1
    )
    rolling_summaries = load_rolling_summaries(window=int(rolling_window))
    _render_rolling_section(st, pd, rolling_summaries)
    _render_symbol_drilldown(st, pd, rolling_summaries)

    st.divider()
    st.subheader("📅 Détail par date")

    selected = st.selectbox("Date du run de parité", options=available, index=0)
    summary = _load_summary(selected)
    if summary is None:
        st.warning(f"Artefact manquant ou corrompu pour {selected}.")
        return

    score = float(summary.get("divergence_score", 0.0))
    badge = _badge_color(score)

    cols = st.columns(5)
    cols[0].metric("Symboles live", summary.get("n_symbols_live", 0))
    cols[1].metric("Symboles replay", summary.get("n_symbols_replay", 0))
    cols[2].metric("✅ Matched", summary.get("n_matched", 0))
    cols[3].metric("⚠️ Divergent", summary.get("n_divergent", 0))
    cols[4].metric(f"{badge} Score", f"{score:.2%}")

    st.caption(
        f"Live run_id : `{summary.get('live_run_id') or '—'}`  •  "
        f"Replay run_id : `{summary.get('replay_run_id') or '—'}`  •  "
        f"généré le {summary.get('generated_at', '—')}"
    )

    rows = summary.get("rows") or []
    if not rows:
        st.info("Aucune ligne de détail.")
    else:
        df = pd.DataFrame(rows)
        kinds = sorted(df["divergence_kind"].dropna().unique().tolist())
        selected_kinds = st.multiselect(
            "Filtrer par catégorie de divergence",
            options=kinds,
            default=[k for k in kinds if k != "match"] or kinds,
        )
        if selected_kinds:
            df = df[df["divergence_kind"].isin(selected_kinds)]
        st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("⚙️ Relancer le job parité maintenant"):
        target_date_str = st.text_input(
            "Date à recalculer (YYYY-MM-DD)",
            value=selected,
            key="parity_relaunch_date",
        )
        if st.button("Lancer scripts.run_daily_parity"):
            try:
                date.fromisoformat(target_date_str)
            except ValueError:
                st.error("Date invalide.")
            else:
                cmd = [sys.executable, "-m", "scripts.run_daily_parity",
                       "--trade-date", target_date_str, "--no-alert"]
                try:
                    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if out.returncode in (0, 2):
                        st.success(f"Job exécuté (exit={out.returncode}).")
                    else:
                        st.error(f"Job en erreur (exit={out.returncode}).")
                    if out.stdout:
                        st.code(out.stdout[-2000:])
                except (subprocess.SubprocessError, OSError) as exc:
                    st.error(f"Échec subprocess : {exc}")


__all__ = [
    "render",
    "load_rolling_summaries",
    "aggregate_top_divergent_symbols",
    "PARITY_ROOT",
]

