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
SCREENER_ARTIFACT_FILE_SPECS = (
    ("metadata", "metadata.json", "json"),
    ("summary_metrics", "summary_metrics.csv", "csv"),
    ("daily_metrics", "daily_metrics.csv", "csv"),
    ("scenarios", "scenarios.csv", "csv"),
    ("market_regimes", "market_regimes.csv", "csv"),
    ("summary_metrics_by_regime", "summary_metrics_by_regime.csv", "csv"),
    ("scenario_recommendations", "scenario_recommendations.csv", "csv"),
    ("recommendation_summary", "recommendation_summary.json", "json"),
    ("scenario_recommendations_by_regime", "scenario_recommendations_by_regime.csv", "csv"),
    ("cross_regime_recommendations", "cross_regime_recommendations.csv", "csv"),
    ("cross_regime_recommendation_summary", "cross_regime_recommendation_summary.json", "json"),
    ("scenario_recommendations_by_objective", "scenario_recommendations_by_objective.csv", "csv"),
    ("recommendation_summary_by_objective", "recommendation_summary_by_objective.json", "json"),
)


def get_screener_artifacts_dir(artifacts_dir: Path | str | None = None) -> Path:
    root = Path(artifacts_dir) if artifacts_dir is not None else DEFAULT_SCREENER_ARTIFACTS_DIR
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root


def _count_data_rows(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            line_count = sum(1 for _ in fh)
    except Exception:
        return None
    if line_count <= 1:
        return 0
    return line_count - 1


def _format_size_label(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} o"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko"
    return f"{size_bytes / (1024 * 1024):.2f} Mo"


def _build_file_snapshot(root: Path, *, key: str, filename: str, kind: str) -> dict[str, Any]:
    path = root / filename
    exists = path.exists() and path.is_file()
    size_bytes = int(path.stat().st_size) if exists else 0
    row_count = _count_data_rows(path) if kind == "csv" and exists else None
    return {
        "key": key,
        "label": filename,
        "path": str(path),
        "exists": exists,
        "kind": kind,
        "size_bytes": size_bytes,
        "size_label": _format_size_label(size_bytes) if exists else "—",
        "row_count": row_count,
    }


def _coerce_scalar(value: object) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # pragma: no cover
            return value
    return value


def _extract_recommended_scenario(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidate = payload.get("recommended_scenario") if isinstance(payload, dict) else None
    if not isinstance(candidate, dict) or not candidate:
        return None
    return {
        "scenario_name": candidate.get("scenario_name"),
        "rank": candidate.get("rank") or candidate.get("cross_regime_rank"),
        "overall_score": candidate.get("overall_score") or candidate.get("cross_regime_overall_score"),
        "objective_score": candidate.get("objective_score"),
        "robustness_score": candidate.get("robustness_score"),
        "survival_score": candidate.get("survival_score"),
        "forward_quality_score": candidate.get("forward_quality_score"),
        "confidence_score": candidate.get("confidence_score"),
        "reason": candidate.get("reason"),
    }


def _build_objective_leaders(report: dict[str, Any]) -> list[dict[str, Any]]:
    objective_rows = report.get("objective_rows_df")
    if not isinstance(objective_rows, pd.DataFrame) or objective_rows.empty:
        return []

    columns = [
        "objective",
        "objective_label",
        "objective_scope",
        "scenario_name",
        "objective_score",
        "overall_score",
        "reason",
    ]
    available_columns = [column for column in columns if column in objective_rows.columns]
    formatted = objective_rows.loc[:, available_columns].copy()
    rows: list[dict[str, Any]] = []
    for row in formatted.to_dict(orient="records"):
        normalized = {key: _coerce_scalar(value) for key, value in row.items()}
        for score_key in ("objective_score", "overall_score"):
            score_value = normalized.get(score_key)
            if isinstance(score_value, (int, float)):
                normalized[score_key] = round(float(score_value), 4)
        rows.append(normalized)
    return rows


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


def build_screener_artifact_summary(artifacts_dir: Path | str | None = None) -> dict[str, Any]:
    root = get_screener_artifacts_dir(artifacts_dir)
    report = load_screener_recommendation_report(root)
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    recommendation_summary, recommendation_summary_error = _read_json_file(root / "recommendation_summary.json")
    cross_regime_summary, cross_regime_error = _read_json_file(root / "cross_regime_recommendation_summary.json")

    files = [
        _build_file_snapshot(root, key=key, filename=filename, kind=kind)
        for key, filename, kind in SCREENER_ARTIFACT_FILE_SPECS
    ]
    file_map = {item["key"]: item for item in files}
    existing_files = [item for item in files if bool(item.get("exists"))]
    trading_dates = metadata.get("trading_dates") if isinstance(metadata.get("trading_dates"), list) else []
    scenarios = metadata.get("scenarios") if isinstance(metadata.get("scenarios"), list) else []
    market_regimes = metadata.get("market_regimes") if isinstance(metadata.get("market_regimes"), list) else []
    objective_leaders = _build_objective_leaders(report)
    errors = [str(error) for error in report.get("errors", []) if str(error).strip()]
    if recommendation_summary_error:
        errors.append(recommendation_summary_error)
    if cross_regime_error:
        errors.append(cross_regime_error)

    return {
        "artifacts_dir": str(root),
        "available": bool(existing_files),
        "diagnostic_available": bool(
            file_map["metadata"]["exists"]
            or file_map["summary_metrics"]["exists"]
            or file_map["daily_metrics"]["exists"]
        ),
        "recommendation_available": bool(
            file_map["scenario_recommendations"]["exists"]
            or file_map["recommendation_summary"]["exists"]
            or file_map["scenario_recommendations_by_objective"]["exists"]
            or file_map["recommendation_summary_by_objective"]["exists"]
        ),
        "regime_analysis_available": bool(
            file_map["summary_metrics_by_regime"]["exists"]
            or file_map["scenario_recommendations_by_regime"]["exists"]
            or file_map["cross_regime_recommendation_summary"]["exists"]
        ),
        "coverage_label": str(report.get("coverage_label") or "Période non renseignée"),
        "updated_at_label": str(report.get("updated_at_label") or "inconnue"),
        "baseline_name": metadata.get("baseline_name"),
        "trading_days": len(trading_dates),
        "scenario_count": len(scenarios),
        "market_regimes": [str(value) for value in market_regimes if str(value).strip()],
        "objective_recommendations": objective_leaders,
        "objective_count": len(objective_leaders),
        "best_compromise": _extract_recommended_scenario(recommendation_summary),
        "best_cross_regime": _extract_recommended_scenario(cross_regime_summary),
        "summary_rows": file_map["summary_metrics"].get("row_count"),
        "daily_rows": file_map["daily_metrics"].get("row_count"),
        "file_count": len(existing_files),
        "files": files,
        "errors": errors,
    }


__all__ = [
    "DEFAULT_SCREENER_ARTIFACTS_DIR",
    "OBJECTIVE_DISPLAY_ORDER",
    "SCREENER_ARTIFACT_FILE_SPECS",
    "build_screener_artifact_summary",
    "get_screener_artifacts_dir",
    "load_screener_recommendation_report",
]



