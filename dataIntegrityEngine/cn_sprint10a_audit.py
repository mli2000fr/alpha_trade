"""Auditer les labels Oracle CN_A annuels avant tout entraînement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_oracle_labels import DEFAULT_OUTPUT_ROOT

REASONS_TAIL = {"FUTURE_HORIZON_UNAVAILABLE", "AVAILABILITY_SESSION_UNAVAILABLE"}
AUDIT_COLUMNS = (
    "market_code", "session_date", "instrument_id", "decision_at",
    "exit_date", "available_date", "available_at_utc", "target_quality_valid",
    "target_quality_reason", "rank_universe_count", "oracle_decile",
    "oracle_extreme20", "path_limit_locked", "execution_data_eligible",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(root: Path, *, start_year: int = 2018, end_year: int = 2025) -> dict[str, Any]:
    current_sha = _sha256(ROOT / "modelFactory" / "cn_oracle_labels.py")
    yearly: list[dict[str, Any]] = []
    errors: list[str] = []
    for year in range(start_year, end_year + 1):
        matches: list[tuple[Path, dict[str, Any]]] = []
        for path in (root / "cn_oracle_labels_v1").glob(
            f"cn-labels-{year}0101-{year}1231-*/report.json"
        ):
            report = json.loads(path.read_text(encoding="utf-8"))
            if report.get("implementation_sha256") == current_sha:
                matches.append((path, report))
        if len(matches) != 1:
            errors.append(f"{year}: {len(matches)} rapports pour le code courant")
            continue
        report_path, report = matches[0]
        expected_rows = int(report["candidate_rows"])
        horizon_summary = {}
        for horizon in (5, 10, 15, 20):
            item = report["horizons"].get(str(horizon))
            if item is None:
                errors.append(f"{year} H{horizon}: rapport manquant")
                continue
            path = report_path.parent / f"h{horizon}.parquet"
            if not path.exists() or _sha256(path) != item["panel_sha256"]:
                errors.append(f"{year} H{horizon}: Parquet absent ou SHA différent")
                continue
            labels = pd.read_parquet(path, columns=list(AUDIT_COLUMNS))
            if len(labels) != expected_rows or len(labels) != int(item["rows"]):
                errors.append(f"{year} H{horizon}: population différente du panel source")
            if labels.duplicated(["session_date", "instrument_id"]).any():
                errors.append(f"{year} H{horizon}: doublons de clés")
            if set(labels["market_code"].dropna()) != {"CN_A"}:
                errors.append(f"{year} H{horizon}: marché non CN_A")
            valid = labels["target_quality_valid"].astype(bool)
            matured = ~labels["target_quality_reason"].isin(REASONS_TAIL)
            if valid.any():
                available = pd.to_datetime(labels.loc[valid, "available_date"])
                exit_date = pd.to_datetime(labels.loc[valid, "exit_date"])
                decision_at = pd.to_datetime(labels.loc[valid, "decision_at"])
                available_at = pd.to_datetime(labels.loc[valid, "available_at_utc"])
                if not (available > exit_date).all() or not (available_at > decision_at).all():
                    errors.append(f"{year} H{horizon}: label disponible trop tôt")
                if (labels.loc[valid, "rank_universe_count"] < 20).any():
                    errors.append(f"{year} H{horizon}: décile avec coupe < 20")
                if not labels.loc[valid, "oracle_decile"].between(1, 10).all():
                    errors.append(f"{year} H{horizon}: décile invalide")
                extreme_fraction = float(labels.loc[valid, "oracle_extreme20"].mean())
                if not 0.15 <= extreme_fraction <= 0.25:
                    errors.append(f"{year} H{horizon}: proportion extrême anormale")
            if labels.loc[~valid, "oracle_decile"].notna().any():
                errors.append(f"{year} H{horizon}: décile présent pour un label invalide")
            matured_valid = float(valid.sum() / matured.sum()) if matured.any() else 0.0
            if matured_valid < 0.95:
                errors.append(f"{year} H{horizon}: couverture mûre {matured_valid:.3f} < 0.95")
            horizon_summary[str(horizon)] = {
                "rows": len(labels), "valid": int(valid.sum()),
                "matured": int(matured.sum()),
                "valid_fraction_among_matured": round(matured_valid, 6),
                "locked_path_fraction": round(float(labels["path_limit_locked"].mean()), 6),
                "execution_data_eligible_fraction": round(float(labels["execution_data_eligible"].mean()), 6),
                "sha256": item["panel_sha256"],
            }
        yearly.append({"year": year, "candidate_rows": expected_rows,
                       "feature_panel_sha256": report["feature_panel_sha256"],
                       "horizons": horizon_summary, "report": str(report_path)})
    return {
        "status": "PASS_LABELS_PRICE_ONLY" if not errors else "INCOMPLETE_OR_FAILED",
        "years_expected": end_year - start_year + 1, "years_found": len(yearly),
        "implementation_sha256": current_sha,
        "yearly": yearly, "errors": errors,
        "price_limits_used_to_filter_deciles": False,
        "training_or_backtest_executed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()
    result = audit(args.output_root, start_year=args.start_year, end_year=args.end_year)
    report_path = args.report_path or args.output_root / f"sprint10a_audit_{args.start_year}_{args.end_year}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS_LABELS_PRICE_ONLY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
