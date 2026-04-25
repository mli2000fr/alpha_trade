"""Lecture des artefacts de diagnostic screener pour l'IHM Streamlit."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ihm.services.pipeline_runner import PROJECT_ROOT

DEFAULT_SCREENER_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "screener_diagnostics"
OBJECTIVE_DISPLAY_ORDER = (
    "robust",
    "offensive",
    "bear_defensive",
    "executable_compromise",
)


def get_screener_artifacts_dir(artifacts_dir: Path | str | None = None) -> Path:
    return Path(artifacts_dir) if artifacts_dir is not None else DEFAULT_SCREENER_ARTIFACTS_DIR


def _read_json_file(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"Fichier absent : `{path.name}`"
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        return {}, f"JSON invalide dans `{path.name}` : {exc}"
    except Exception as exc:  # pragma: no cover
        return {}, f"Lecture impossible de `{path.name}` : {exc}"
    if not isinstance(payload, dict):
        return {}, f"Le fichier `{path.name}` doit contenir un objet JSON en racine."
    return payload, None


def _read_csv_file(path: Path) -> tuple[pd.DataFrame, str | None]:
    if not path.exists():
        return pd.DataFrame(), f"Fichier absent : `{path.name}`"
    try:
        return pd.read_csv(path), None
    except Exception as exc:  # pragma: no cover
        return pd.DataFrame(), f"Lecture impossible de `{path.name}` : {exc}"


def _coverage_label(metadata: dict[str, Any]) -> str:
    trading_dates = metadata.get("trading_dates")
    if not isinstance(trading_dates, list):
        return "Période non renseignée"
    normalized = [str(value) for value in trading_dates if str(value).strip()]
    if not normalized:
        return "Période non renseignée"
    return f"{normalized[0]} → {normalized[-1]} ({len(normalized)} séance(s))"


def _format_updated_at(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "inconnue"


def _objective_order_key(objective: object) -> tuple[int, str]:
    name = str(objective or "")
    try:
        return (OBJECTIVE_DISPLAY_ORDER.index(name), name)
    except ValueError:
        return (len(OBJECTIVE_DISPLAY_ORDER), name)


def _build_objective_rows_from_summary(summary_payload: dict[str, Any]) -> pd.DataFrame:
    objectives = summary_payload.get("objectives")
    if not isinstance(objectives, dict):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    available_objectives = summary_payload.get("available_objectives")
    ordered_objectives = [str(value) for value in available_objectives] if isinstance(available_objectives, list) else list(objectives.keys())
    ordered_objectives = sorted({*ordered_objectives, *map(str, objectives.keys())}, key=_objective_order_key)

    for objective in ordered_objectives:
        payload = objectives.get(objective)
        if not isinstance(payload, dict):
            continue
        leader = payload.get("recommended_scenario") if isinstance(payload.get("recommended_scenario"), dict) else {}
        rows.append(
            {
                "objective": objective,
                "objective_label": payload.get("label") or objective,
                "objective_scope": payload.get("scope") or "global",
                "objective_scope_regime": payload.get("scope_regime"),
                "scenario_name": leader.get("scenario_name"),
                "rank": leader.get("rank"),
                "objective_score": leader.get("objective_score"),
                "overall_score": leader.get("overall_score"),
                "robustness_score": leader.get("robustness_score"),
                "survival_score": leader.get("survival_score"),
                "forward_quality_score": leader.get("forward_quality_score"),
                "confidence_score": leader.get("confidence_score"),
                "reason": leader.get("reason") or payload.get("description"),
                "description": payload.get("description"),
                "analyzed_scenarios": payload.get("analyzed_scenarios"),
            }
        )

    return pd.DataFrame(rows)


def _build_objective_rows_from_recommendations(recommendations: pd.DataFrame) -> pd.DataFrame:
    if recommendations.empty or "objective" not in recommendations.columns:
        return pd.DataFrame()

    frame = recommendations.copy()
    if "rank" in frame.columns:
        frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
    frame["_objective_order"] = frame["objective"].map(lambda value: _objective_order_key(value))
    sort_columns = [column for column in ["_objective_order", "rank", "scenario_name"] if column in frame.columns]
    frame = frame.sort_values(sort_columns, ascending=[True] * len(sort_columns))
    leaders = frame.groupby("objective", dropna=False, as_index=False).head(1).copy()
    leaders = leaders.sort_values(by="_objective_order", ascending=True).drop(columns=["_objective_order"])

    for column in [
        "objective_label",
        "objective_scope",
        "objective_scope_regime",
        "scenario_name",
        "objective_score",
        "overall_score",
        "robustness_score",
        "survival_score",
        "forward_quality_score",
        "confidence_score",
        "objective_reason",
    ]:
        if column not in leaders.columns:
            leaders[column] = None

    leaders = leaders.rename(columns={"objective_reason": "reason"})
    leaders["description"] = None
    leaders["analyzed_scenarios"] = None
    return leaders[
        [
            "objective",
            "objective_label",
            "objective_scope",
            "objective_scope_regime",
            "scenario_name",
            "rank",
            "objective_score",
            "overall_score",
            "robustness_score",
            "survival_score",
            "forward_quality_score",
            "confidence_score",
            "reason",
            "description",
            "analyzed_scenarios",
        ]
    ]


def _build_leaderboard(recommendations: pd.DataFrame) -> pd.DataFrame:
    if recommendations.empty:
        return pd.DataFrame()

    columns = [
        "objective",
        "objective_label",
        "objective_scope",
        "rank",
        "scenario_name",
        "objective_score",
        "overall_score",
        "robustness_score",
        "survival_score",
        "forward_quality_score",
        "confidence_score",
        "objective_reason",
        "objective_recommendation_label",
    ]
    available_columns = [column for column in columns if column in recommendations.columns]
    leaderboard = recommendations.loc[:, available_columns].copy()
    if "rank" in leaderboard.columns:
        leaderboard["rank"] = pd.to_numeric(leaderboard["rank"], errors="coerce")
    if "objective" in leaderboard.columns:
        leaderboard["_objective_order"] = leaderboard["objective"].map(lambda value: _objective_order_key(value))
        sort_columns = [column for column in ["_objective_order", "rank", "scenario_name"] if column in leaderboard.columns]
        leaderboard = leaderboard.sort_values(sort_columns, ascending=[True] * len(sort_columns))
        leaderboard = leaderboard.drop(columns=["_objective_order"])
    else:
        sort_columns = [column for column in ["rank", "scenario_name"] if column in leaderboard.columns]
        if sort_columns:
            leaderboard = leaderboard.sort_values(sort_columns, ascending=[True] * len(sort_columns))
    return leaderboard.reset_index(drop=True)


def load_screener_recommendation_report(artifacts_dir: Path | str | None = None) -> dict[str, Any]:
    root = get_screener_artifacts_dir(artifacts_dir)
    summary_path = root / "recommendation_summary_by_objective.json"
    recommendations_path = root / "scenario_recommendations_by_objective.csv"
    metadata_path = root / "metadata.json"

    errors: list[str] = []
    if not root.exists() or not root.is_dir():
        return {
            "artifacts_dir": root,
            "summary_path": summary_path,
            "recommendations_path": recommendations_path,
            "metadata_path": metadata_path,
            "summary": {},
            "metadata": {},
            "recommendations_df": pd.DataFrame(),
            "objective_rows_df": pd.DataFrame(),
            "leaderboard_df": pd.DataFrame(),
            "coverage_label": "Période non renseignée",
            "updated_at": None,
            "updated_at_label": "inconnue",
            "available": False,
            "errors": [f"Répertoire d'artefacts absent : `{root}`"],
        }

    summary_payload, summary_error = _read_json_file(summary_path)
    if summary_error:
        errors.append(summary_error)
    metadata_payload, metadata_error = _read_json_file(metadata_path)
    if metadata_error:
        errors.append(metadata_error)
    recommendations_df, recommendations_error = _read_csv_file(recommendations_path)
    if recommendations_error:
        errors.append(recommendations_error)

    objective_rows_df = _build_objective_rows_from_summary(summary_payload)
    if objective_rows_df.empty:
        objective_rows_df = _build_objective_rows_from_recommendations(recommendations_df)

    leaderboard_df = _build_leaderboard(recommendations_df)
    available = not objective_rows_df.empty or not leaderboard_df.empty
    updated_at_path = summary_path if summary_path.exists() else recommendations_path if recommendations_path.exists() else None

    return {
        "artifacts_dir": root,
        "summary_path": summary_path,
        "recommendations_path": recommendations_path,
        "metadata_path": metadata_path,
        "summary": summary_payload,
        "metadata": metadata_payload,
        "recommendations_df": recommendations_df,
        "objective_rows_df": objective_rows_df,
        "leaderboard_df": leaderboard_df,
        "coverage_label": _coverage_label(metadata_payload),
        "updated_at": updated_at_path,
        "updated_at_label": _format_updated_at(updated_at_path) if updated_at_path is not None else "inconnue",
        "available": available,
        "errors": errors,
    }


__all__ = [
    "DEFAULT_SCREENER_ARTIFACTS_DIR",
    "OBJECTIVE_DISPLAY_ORDER",
    "get_screener_artifacts_dir",
    "load_screener_recommendation_report",
]



