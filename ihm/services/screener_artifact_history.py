"""Historique global des répertoires d'artefacts screener pour l'IHM."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ihm.services.backtesting_registry import load_backtesting_history
from ihm.services.pipeline_runner import PROJECT_ROOT
from ihm.services.screener_recommendations import (
    DEFAULT_SCREENER_ARTIFACTS_DIR,
    build_screener_artifact_summary,
    get_screener_artifacts_dir,
)

SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY = "ihm_selected_screener_artifacts_dir"
SCREENER_RUN_KINDS = frozenset({"diagnose-screener", "recommend-screener"})


def normalize_screener_artifacts_dir(artifacts_dir: Path | str | None = None) -> str:
    return str(get_screener_artifacts_dir(artifacts_dir))


def _artifacts_dir_label(artifacts_dir: str) -> str:
    path = Path(artifacts_dir)
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _last_run_timestamp(run_record: dict[str, object]) -> str:
    return str(run_record.get("finished_at") or run_record.get("executed_at") or "")


def _history_sort_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    summary = entry.get("summary") if isinstance(entry.get("summary"), dict) else {}
    updated_at_iso = str(summary.get("updated_at_iso") or "")
    last_run_at = str(entry.get("last_run_at") or "")
    is_default = "1" if str(entry.get("artifacts_dir", "")) == normalize_screener_artifacts_dir(DEFAULT_SCREENER_ARTIFACTS_DIR) else "0"
    return (max(updated_at_iso, last_run_at), is_default, str(entry.get("artifacts_dir", "")))


def build_global_screener_artifact_history(
    additional_dirs: list[Path | str] | None = None,
) -> list[dict[str, Any]]:
    grouped_runs: dict[str, list[dict[str, object]]] = {}
    source_tags: dict[str, set[str]] = {}

    def register_dir(raw_dir: Path | str | None, *, source_tag: str) -> None:
        if raw_dir is None:
            return
        text = str(raw_dir).strip()
        if not text:
            return
        normalized = normalize_screener_artifacts_dir(text)
        grouped_runs.setdefault(normalized, [])
        source_tags.setdefault(normalized, set()).add(source_tag)

    register_dir(DEFAULT_SCREENER_ARTIFACTS_DIR, source_tag="défaut")

    for run in load_backtesting_history():
        if str(run.get("run_kind", "")) not in SCREENER_RUN_KINDS:
            continue
        artifacts_dir = run.get("screener_artifacts_dir")
        if not artifacts_dir:
            continue
        normalized = normalize_screener_artifacts_dir(str(artifacts_dir))
        grouped_runs.setdefault(normalized, []).append(run)
        source_tags.setdefault(normalized, set()).add("runs IHM")

    for extra_dir in additional_dirs or []:
        register_dir(extra_dir, source_tag="sélection manuelle")

    entries: list[dict[str, Any]] = []
    for artifacts_dir, runs in grouped_runs.items():
        ordered_runs = sorted(runs, key=_last_run_timestamp, reverse=True)
        last_run = ordered_runs[0] if ordered_runs else {}
        summary = build_screener_artifact_summary(artifacts_dir)
        entries.append(
            {
                "artifacts_dir": artifacts_dir,
                "artifacts_dir_label": _artifacts_dir_label(artifacts_dir),
                "available": bool(summary.get("available")),
                "coverage_label": str(summary.get("coverage_label") or "Période non renseignée"),
                "updated_at_label": str(summary.get("updated_at_label") or "inconnue"),
                "baseline_name": summary.get("baseline_name"),
                "objective_count": int(summary.get("objective_count") or 0),
                "scenario_count": int(summary.get("scenario_count") or 0),
                "file_count": int(summary.get("file_count") or 0),
                "market_regime_count": len(summary.get("market_regimes", []))
                if isinstance(summary.get("market_regimes"), list)
                else 0,
                "diagnostic_available": bool(summary.get("diagnostic_available")),
                "recommendation_available": bool(summary.get("recommendation_available")),
                "regime_analysis_available": bool(summary.get("regime_analysis_available")),
                "run_count": len(runs),
                "last_run_id": last_run.get("run_id"),
                "last_run_label": last_run.get("run_label") or last_run.get("run_kind"),
                "last_run_kind": last_run.get("run_kind"),
                "last_run_status": last_run.get("status"),
                "last_run_at": _last_run_timestamp(last_run) if last_run else "",
                "source_tags": sorted(source_tags.get(artifacts_dir, set())),
                "summary": summary,
            }
        )

    entries.sort(key=_history_sort_key, reverse=True)
    return entries


def format_screener_artifact_history_label(entry: dict[str, Any]) -> str:
    parts = [str(entry.get("artifacts_dir_label") or entry.get("artifacts_dir") or "répertoire inconnu")]
    if entry.get("recommendation_available"):
        parts.append(f"obj={int(entry.get('objective_count') or 0)}")
    if entry.get("coverage_label"):
        parts.append(str(entry.get("coverage_label")))
    if entry.get("updated_at_label"):
        parts.append(f"MAJ {entry.get('updated_at_label')}")
    run_count = int(entry.get("run_count") or 0)
    if run_count:
        parts.append(f"runs={run_count}")
    return " | ".join(parts)


def build_screener_artifact_history_rows(entries: list[dict[str, Any]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in entries:
        rows.append(
            {
                "Répertoire": entry.get("artifacts_dir_label") or entry.get("artifacts_dir") or "—",
                "Disponible": "oui" if bool(entry.get("available")) else "non",
                "Couverture": entry.get("coverage_label") or "Période non renseignée",
                "MAJ": entry.get("updated_at_label") or "inconnue",
                "Baseline": entry.get("baseline_name") or "—",
                "Reco objectifs": int(entry.get("objective_count") or 0),
                "Scénarios": int(entry.get("scenario_count") or 0),
                "Fichiers": int(entry.get("file_count") or 0),
                "Régimes": int(entry.get("market_regime_count") or 0),
                "Runs IHM": int(entry.get("run_count") or 0),
                "Dernier run": entry.get("last_run_label") or "—",
                "Statut": entry.get("last_run_status") or "—",
                "Origines": ", ".join(str(value) for value in entry.get("source_tags", []) if str(value).strip()) or "—",
                "Chemin": entry.get("artifacts_dir") or "—",
            }
        )
    return rows


__all__ = [
    "SCREENER_RUN_KINDS",
    "SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY",
    "build_global_screener_artifact_history",
    "build_screener_artifact_history_rows",
    "format_screener_artifact_history_label",
    "normalize_screener_artifacts_dir",
]

