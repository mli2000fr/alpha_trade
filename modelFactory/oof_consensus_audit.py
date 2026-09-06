"""Audit research-only du consensus entre modèles directionnels OOF existants.

Les scores hétérogènes sont transformés en rangs cross-sectionnels quotidiens.
Les variantes d'une même famille sont moyennées avant le consensus afin de ne
pas leur donner plusieurs voix. Aucun modèle n'est réentraîné et aucun poids
n'est optimisé sur les rendements futurs.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _score(frame: pd.DataFrame, definition: dict[str, Any]) -> pd.Series:
    kind = definition.get("type", "column")
    if kind == "column":
        column = str(definition["column"])
        if column not in frame:
            raise ValueError(f"Colonne de score absente: {column}")
        return pd.to_numeric(frame[column], errors="coerce")
    if kind == "difference":
        positive, negative = str(definition["positive"]), str(definition["negative"])
        missing = sorted({positive, negative}.difference(frame.columns))
        if missing:
            raise ValueError(f"Colonnes de différence absentes: {missing}")
        return pd.to_numeric(frame[positive], errors="coerce") - pd.to_numeric(
            frame[negative], errors="coerce"
        )
    raise ValueError(f"Type de score inconnu: {kind}")


def load_component(root: Path, component: dict[str, Any]) -> pd.DataFrame:
    path = _resolve(root, str(component["path"]))
    if not path.exists():
        raise FileNotFoundError(f"Artefact OOF introuvable: {path}")
    source = pd.read_parquet(path)
    missing = sorted({"date", "symbol"}.difference(source.columns))
    if missing:
        raise ValueError(f"Clés OOF absentes dans {path}: {missing}")
    result = source[["date", "symbol"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()
    result["raw_score"] = _score(source, component.get("score", {}))
    for column in ("future_return", "fold_index"):
        if column in source:
            result[column] = pd.to_numeric(source[column], errors="coerce")
    result = result.dropna(subset=["date", "symbol", "raw_score"])
    if result.duplicated(["date", "symbol"]).any():
        raise ValueError(f"Artefact non unique par date/symbole: {path}")
    result["component_rank"] = result.groupby("date")["raw_score"].rank(
        method="average", pct=True
    )
    return result


def build_family(root: Path, family: dict[str, Any]) -> pd.DataFrame:
    components = family.get("components") or []
    if not components:
        raise ValueError(f"Famille sans composant: {family.get('name')}")
    merged: pd.DataFrame | None = None
    for index, component in enumerate(components):
        current = load_component(root, component).rename(
            columns={"component_rank": f"component_{index}_rank"}
        )
        keep = ["date", "symbol", f"component_{index}_rank"]
        if merged is None:
            keep += [c for c in ("future_return", "fold_index") if c in current]
            merged = current[keep].copy()
        else:
            merged = merged.merge(
                current[["date", "symbol", f"component_{index}_rank"]],
                on=["date", "symbol"], how="inner", validate="one_to_one",
            )
    assert merged is not None
    rank_columns = [c for c in merged if c.startswith("component_")]
    merged["family_rank"] = merged[rank_columns].mean(axis=1)
    merged["family_rank"] = merged.groupby("date")["family_rank"].rank(
        method="average", pct=True
    )
    return merged[["date", "symbol", "family_rank"] + [
        c for c in ("future_return", "fold_index") if c in merged
    ]]


def build_horizon_panel(
    root: Path, horizon: int, families: list[dict[str, Any]]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    panel: pd.DataFrame | None = None
    inventory: list[dict[str, Any]] = []
    for family in families:
        name = str(family["name"])
        current = build_family(root, family).rename(columns={"family_rank": f"rank_{name}"})
        inventory.append({
            "name": name,
            "components": len(family["components"]),
            "rows": int(len(current)),
            "dates": int(current["date"].nunique()),
        })
        if panel is None:
            if "future_return" not in current or "fold_index" not in current:
                raise ValueError("La première famille doit fournir future_return et fold_index.")
            panel = current.copy()
        else:
            panel = panel.merge(
                current[["date", "symbol", f"rank_{name}"]],
                on=["date", "symbol"], how="inner", validate="one_to_one",
            )
    if panel is None or panel.empty:
        raise ValueError(f"Intersection OOF vide à H{horizon}.")
    rank_columns = [c for c in panel if c.startswith("rank_")]
    panel["consensus_score"] = panel[rank_columns].mean(axis=1)
    panel["consensus_rank"] = panel.groupby("date")["consensus_score"].rank(
        method="average", pct=True
    )
    panel["long_vote_share"] = panel[rank_columns].gt(0.5).mean(axis=1)
    panel["short_vote_share"] = panel[rank_columns].lt(0.5).mean(axis=1)
    panel["horizon"] = int(horizon)
    panel["semester"] = panel["date"].dt.year.astype(str) + np.where(
        panel["date"].dt.month.le(6), "H1", "H2"
    )
    diagnostics = {
        "families": inventory,
        "intersection_rows": int(len(panel)),
        "intersection_dates": int(panel["date"].nunique()),
        "intersection_symbols": int(panel["symbol"].nunique()),
        "first_date": str(panel["date"].min().date()),
        "last_date": str(panel["date"].max().date()),
        "family_count": len(rank_columns),
    }
    return panel, diagnostics


def _daily_ic(frame: pd.DataFrame, score: str) -> pd.Series:
    def correlation(group: pd.DataFrame) -> float:
        valid = group[[score, "future_return"]].dropna()
        if len(valid) < 10 or valid[score].nunique() < 2 or valid["future_return"].nunique() < 2:
            return np.nan
        return float(valid[score].corr(valid["future_return"], method="spearman"))

    return frame.groupby("date", sort=True).apply(correlation, include_groups=False).dropna()


def _selection_metrics(frame: pd.DataFrame, score: str, fraction: float) -> dict[str, Any]:
    ranked = frame.copy()
    ranked["selection_rank"] = ranked.groupby("date")[score].rank(method="average", pct=True)
    long_rows = ranked[ranked["selection_rank"].gt(1.0 - fraction)]
    short_rows = ranked[ranked["selection_rank"].le(fraction)]
    pool_mean = float(ranked["future_return"].mean())

    def side(rows: pd.DataFrame, multiplier: float, baseline: float) -> dict[str, Any]:
        signed = multiplier * rows["future_return"]
        return {
            "rows": int(len(rows)),
            "dates": int(rows["date"].nunique()),
            "mean_signed_return": float(signed.mean()),
            "median_signed_return": float(signed.median()),
            "hit_rate": float(signed.gt(0).mean()),
            "lift_vs_pool": float(signed.mean() - baseline),
        }

    long = side(long_rows, 1.0, pool_mean)
    short = side(short_rows, -1.0, -pool_mean)
    return {
        "fraction": fraction,
        "pool_mean_return": pool_mean,
        "long": long,
        "short": short,
        "top_bottom_spread": float(
            long_rows["future_return"].mean() - short_rows["future_return"].mean()
        ),
        "selected_mean_absolute_return": float(pd.concat([
            long_rows["future_return"].abs(), short_rows["future_return"].abs()
        ]).mean()),
        "pool_mean_absolute_return": float(ranked["future_return"].abs().mean()),
    }


def evaluate_score(frame: pd.DataFrame, score: str, fraction: float) -> dict[str, Any]:
    daily_ic = _daily_ic(frame, score)
    selection = _selection_metrics(frame, score, fraction)
    folds: list[dict[str, Any]] = []
    for fold, group in frame.groupby("fold_index", sort=True):
        ic = _daily_ic(group, score)
        metrics = _selection_metrics(group, score, fraction)
        folds.append({
            "fold_index": int(fold),
            "mean_daily_ic": float(ic.mean()) if len(ic) else None,
            "top_bottom_spread": metrics["top_bottom_spread"],
            "long_lift_vs_pool": metrics["long"]["lift_vs_pool"],
            "short_lift_vs_pool": metrics["short"]["lift_vs_pool"],
        })
    semesters: dict[str, Any] = {}
    for semester, group in frame.groupby("semester", sort=True):
        ic = _daily_ic(group, score)
        metrics = _selection_metrics(group, score, fraction)
        semesters[str(semester)] = {
            "rows": int(len(group)),
            "mean_daily_ic": float(ic.mean()) if len(ic) else None,
            "top_bottom_spread": metrics["top_bottom_spread"],
            "long_signed_return": metrics["long"]["mean_signed_return"],
            "short_signed_return": metrics["short"]["mean_signed_return"],
        }
    return {
        "mean_daily_ic": float(daily_ic.mean()),
        "median_daily_ic": float(daily_ic.median()),
        "positive_ic_day_rate": float(daily_ic.gt(0).mean()),
        "selection": selection,
        "folds": folds,
        "semesters": semesters,
    }


def evaluate_agreement(frame: pd.DataFrame, fraction: float) -> dict[str, Any]:
    ranked = frame.copy()
    ranked["selection_rank"] = ranked.groupby("date")["consensus_score"].rank(
        method="average", pct=True
    )
    policies = {"supermajority": 2.0 / 3.0, "unanimous": 1.0}
    output: dict[str, Any] = {}
    pool_mean = float(ranked["future_return"].mean())
    for name, threshold in policies.items():
        long_rows = ranked[
            ranked["selection_rank"].gt(1.0 - fraction)
            & ranked["long_vote_share"].ge(threshold)
        ]
        short_rows = ranked[
            ranked["selection_rank"].le(fraction)
            & ranked["short_vote_share"].ge(threshold)
        ]
        output[name] = {
            "long_rows": int(len(long_rows)),
            "short_rows": int(len(short_rows)),
            "long_coverage_vs_tail": float(len(long_rows) / max(1, (ranked["selection_rank"] > 1 - fraction).sum())),
            "short_coverage_vs_tail": float(len(short_rows) / max(1, (ranked["selection_rank"] <= fraction).sum())),
            "long_signed_return": float(long_rows["future_return"].mean()) if len(long_rows) else None,
            "short_signed_return": float(-short_rows["future_return"].mean()) if len(short_rows) else None,
            "long_lift_vs_pool": float(long_rows["future_return"].mean() - pool_mean) if len(long_rows) else None,
            "short_lift_vs_pool": float(-short_rows["future_return"].mean() + pool_mean) if len(short_rows) else None,
        }
    return output


def pairwise_correlations(frame: pd.DataFrame) -> list[dict[str, Any]]:
    columns = [c for c in frame if c.startswith("rank_")]
    rows: list[dict[str, Any]] = []
    for index, left in enumerate(columns):
        for right in columns[index + 1:]:
            def safe_correlation(
                group: pd.DataFrame, left_col: str = left, right_col: str = right
            ) -> float:
                valid = group[[left_col, right_col]].dropna()
                if len(valid) < 3 or valid[left_col].nunique() < 2 or valid[right_col].nunique() < 2:
                    return np.nan
                return float(valid[left_col].corr(valid[right_col], method="spearman"))

            correlations = frame.groupby("date").apply(
                safe_correlation,
                include_groups=False,
            ).dropna()
            rows.append({
                "left": left.removeprefix("rank_"),
                "right": right.removeprefix("rank_"),
                "mean_daily_spearman": float(correlations.mean()),
            })
    return rows


def evaluate_daily_overlay(
    frame: pd.DataFrame,
    overlay: pd.DataFrame,
    *,
    fraction: float,
) -> dict[str, Any]:
    joined = frame.merge(overlay, on="date", how="inner", validate="many_to_one")
    joined["selection_rank"] = joined.groupby("date")["consensus_score"].rank(
        method="average", pct=True
    )
    long_tail = joined[joined["selection_rank"].gt(1.0 - fraction)]
    short_tail = joined[joined["selection_rank"].le(fraction)]
    long_rows = long_tail[long_tail["daily_overlay_score"].gt(0)]
    short_rows = short_tail[short_tail["daily_overlay_score"].lt(0)]
    pool_mean = float(joined["future_return"].mean())
    return {
        "available_dates": int(joined["date"].nunique()),
        "date_coverage": float(joined["date"].nunique() / frame["date"].nunique()),
        "long_rows": int(len(long_rows)),
        "short_rows": int(len(short_rows)),
        "long_coverage_vs_tail": float(len(long_rows) / max(1, len(long_tail))),
        "short_coverage_vs_tail": float(len(short_rows) / max(1, len(short_tail))),
        "long_signed_return": float(long_rows["future_return"].mean()) if len(long_rows) else None,
        "short_signed_return": float(-short_rows["future_return"].mean()) if len(short_rows) else None,
        "long_lift_vs_pool": float(long_rows["future_return"].mean() - pool_mean) if len(long_rows) else None,
        "short_lift_vs_pool": float(-short_rows["future_return"].mean() + pool_mean) if len(short_rows) else None,
    }


def load_daily_overlay(root: Path, definition: dict[str, Any]) -> pd.DataFrame:
    path = _resolve(root, str(definition["path"]))
    source = pd.read_parquet(path)
    columns = [str(value) for value in definition["columns"]]
    missing = sorted({"date", *columns}.difference(source.columns))
    if missing:
        raise ValueError(f"Overlay quotidien incomplet: {missing}")
    result = source[["date", *columns]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["daily_overlay_score"] = result[columns].mean(axis=1)
    result = result.dropna(subset=["date", "daily_overlay_score"])
    if result.duplicated("date").any():
        raise ValueError("Overlay quotidien non unique par date.")
    return result[["date", "daily_overlay_score"]]


def evaluate_gates(consensus: dict[str, Any], baselines: dict[str, Any]) -> dict[str, Any]:
    best_ic = max(value["mean_daily_ic"] for value in baselines.values())
    folds = consensus["folds"]
    semesters = consensus["semesters"]
    values = {
        "mean_daily_ic_gte_0_02": consensus["mean_daily_ic"] >= 0.02,
        "ic_lift_vs_best_family_gte_0_005": consensus["mean_daily_ic"] - best_ic >= 0.005,
        "positive_spread_folds_gte_6": sum(
            row["top_bottom_spread"] > 0 for row in folds
        ) >= 6,
        "positive_spread_semester_rate_gte_0_60": (
            sum(row["top_bottom_spread"] > 0 for row in semesters.values())
            / max(1, len(semesters))
        ) >= 0.60,
        "long_lift_positive": consensus["selection"]["long"]["lift_vs_pool"] > 0,
        "short_lift_positive": consensus["selection"]["short"]["lift_vs_pool"] > 0,
    }
    return {
        "values": values,
        "best_family_mean_daily_ic": best_ic,
        "consensus_ic_lift_vs_best_family": consensus["mean_daily_ic"] - best_ic,
        "all_gates_passed": all(values.values()),
    }


def run_audit(manifest_path: Path, output: Path, *, project_root: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selection_fraction = float(manifest.get("selection_fraction", 0.20))
    if not 0 < selection_fraction < 0.5:
        raise ValueError("selection_fraction doit être dans ]0,0.5[.")
    panels: list[pd.DataFrame] = []
    results: dict[str, Any] = {}
    daily_overlay = (
        load_daily_overlay(project_root, manifest["daily_overlay"])
        if manifest.get("daily_overlay") else None
    )
    for horizon_text, definition in sorted(
        manifest["horizons"].items(), key=lambda item: int(item[0])
    ):
        horizon = int(horizon_text)
        panel, diagnostics = build_horizon_panel(
            project_root, horizon, list(definition["families"])
        )
        rank_columns = [c for c in panel if c.startswith("rank_")]
        baselines = {
            column.removeprefix("rank_"): evaluate_score(panel, column, selection_fraction)
            for column in rank_columns
        }
        consensus = evaluate_score(panel, "consensus_score", selection_fraction)
        results[horizon_text] = {
            "diagnostics": diagnostics,
            "baselines": baselines,
            "consensus": consensus,
            "agreement": evaluate_agreement(panel, selection_fraction),
            "pairwise_correlations": pairwise_correlations(panel),
            "gates": evaluate_gates(consensus, baselines),
            "verdict": "GO_RESEARCH" if evaluate_gates(consensus, baselines)["all_gates_passed"] else "NO_GO",
        }
        if horizon == 20 and daily_overlay is not None:
            results[horizon_text]["daily_regime_overlay"] = evaluate_daily_overlay(
                panel, daily_overlay, fraction=selection_fraction
            )
        panels.append(panel)
    output.mkdir(parents=True, exist_ok=True)
    predictions = pd.concat(panels, ignore_index=True, sort=False)
    predictions.to_parquet(output / "consensus_predictions.parquet", index=False)
    report = {
        "schema_version": 1,
        "experiment": "OOF_CONSENSUS_AUDIT_V1",
        "generated_at": datetime.now(UTC).isoformat(),
        "research_only": True,
        "serving_ready": False,
        "manifest": str(manifest_path),
        "oracle_batch_id": manifest.get("oracle_batch_id"),
        "scientific_contract": {
            "normalization": "within_date_percentile_rank",
            "family_aggregation": "equal_weight_mean_of_component_ranks",
            "consensus": "equal_weight_mean_of_family_ranks",
            "selection_fraction_each_side": selection_fraction,
            "missingness": "strict_intersection_no_imputation",
            "weights_or_thresholds_tuned": False,
        },
        "results": results,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit du consensus de modèles OOF existants.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    report = run_audit(args.manifest, args.output, project_root=args.project_root)
    for horizon, result in report["results"].items():
        consensus = result["consensus"]
        selection = consensus["selection"]
        print(
            f"H{horizon}: familles={result['diagnostics']['family_count']} "
            f"rows={result['diagnostics']['intersection_rows']} "
            f"IC={consensus['mean_daily_ic']:+.4f} "
            f"LONG={selection['long']['mean_signed_return']:+.2%} "
            f"SHORT={selection['short']['mean_signed_return']:+.2%} "
            f"verdict={result['verdict']}"
        )


if __name__ == "__main__":
    main()
