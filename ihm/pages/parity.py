"""Sprint S9 — Page Streamlit "Parité Backtest ↔ Live".

Lit les artefacts ``artifacts/parity_runs/<YYYY-MM-DD>/parity_summary.json``
écrits par :mod:`scripts.run_daily_parity` et expose :

- KPI (matched / divergent / score) ;
- tableau filtrable des divergences ;
- bouton « relancer » (best-effort, subprocess).
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

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


def _badge_color(score: float, threshold: float = 0.10) -> str:
    if score <= threshold * 0.5:
        return "🟢"
    if score <= threshold:
        return "🟡"
    return "🔴"


def render() -> None:
    """Entry-point Streamlit (signature attendue par ihm.services.navigation)."""
    try:
        import streamlit as st
    except ImportError:  # pragma: no cover - hors contexte Streamlit
        LOGGER.error("[parity_page] streamlit indisponible — page non rendable.")
        return

    import pandas as pd

    st.title("🔀 Parité Backtest ↔ Live")
    st.caption("Compare les décisions risk live vs replay backtest pour détecter les divergences (Sprint S9).")

    available = _list_available_dates()
    if not available:
        st.info(
            "Aucun run de parité disponible. Lance `python -m scripts.run_daily_parity --trade-date YYYY-MM-DD` "
            "pour produire un premier artefact."
        )
        return

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


__all__ = ["render"]

