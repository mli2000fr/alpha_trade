"""Sprint 7-B : profil relatif au benchmark FR, artefacts de recherche uniquement."""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from modelFactory.fr_feature_profile_freeze import FEATURES, load_policy, qualify
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256

HORIZONS = (1, 5, 10, 20)
RELATIVE_FEATURES = (
    *(f"benchmark_return_{h}" for h in HORIZONS),
    *(f"excess_return_{h}" for h in HORIZONS),
    "beta20",
    "correlation20",
    "relative_volatility20",
    "residual_return20",
)
RELATIVE_SPECS = {
    **{f"benchmark_return_{h}": f"produit(1 + rendement quotidien benchmark, {h}) - 1, même segment" for h in HORIZONS},
    **{f"excess_return_{h}": f"return_{h} - benchmark_return_{h}" for h in HORIZONS},
    "beta20": "covariance échantillon(titre,benchmark,20) / variance échantillon(benchmark,20)",
    "correlation20": "covariance / (écart-type titre * écart-type benchmark), 20 paires quotidiennes",
    "relative_volatility20": "écart-type titre / écart-type benchmark, 20 paires quotidiennes",
    "residual_return20": "return_20 - beta20 * benchmark_return_20 ; approximation, pas résidu de régression cumulé",
}


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (cfg.get("schema_version"), cfg.get("profile"), cfg.get("market_code"), cfg.get("database_alias")) != (
        1,
        "fr_price_benchmark_v1",
        "FR_EQ",
        "fr_primary",
    ):
        raise ValueError("Profil benchmark France incompatible")
    if (
        tuple(cfg["return_horizons"]) != HORIZONS
        or cfg["statistics_window"] != 20
        or cfg["variance_floor"] != 1e-12
        or cfg["benchmark_code"] != "FR_RESEARCH_EW_PRICE_V1"
    ):
        raise ValueError("Formules et fenêtres benchmark figées")
    if cfg.get("sector_features_enabled") or cfg.get("canonical_writes_enabled"):
        raise ValueError("Profil de recherche sans secteurs ni écriture canonique")
    return cfg


def benchmark_windows(rows: pd.DataFrame, sessions: list[str]) -> pd.DataFrame:
    if rows["source_session_date"].duplicated().any():
        raise ValueError("Séance benchmark dupliquée")
    position = {s: i for i, s in enumerate(sessions)}
    for row in rows.itertuples():
        i = position.get(row.source_session_date)
        if i is None or i + 1 >= len(sessions) or sessions[i + 1] != row.decision_session_date:
            raise ValueError("Disponibilité benchmark non J+1 XPAR")
    frame = rows.set_index("source_session_date").reindex(sessions)
    known = frame["benchmark_state"].eq("KNOWN")
    values = pd.to_numeric(frame["price_return"], errors="coerce")
    if (known & (~np.isfinite(values) | values.le(-1) | frame["segment_id"].isna())).any():
        raise ValueError("Benchmark KNOWN incohérent")
    if (~known & (values.notna() | frame["segment_id"].notna())).any():
        raise ValueError("Benchmark UNKNOWN porteur de valeurs")
    # Un segment ne doit jamais être réutilisé après une interruption.
    runs = (frame["segment_id"].ne(frame["segment_id"].shift()) | ~known).cumsum()
    segment_runs = pd.DataFrame({"segment": frame.loc[known, "segment_id"], "run": runs[known]})
    if segment_runs.groupby("segment")["run"].nunique().gt(1).any():
        raise ValueError("Segment benchmark réutilisé après rupture")
    result = pd.DataFrame(index=frame.index)
    result["benchmark_state"] = frame["benchmark_state"].fillna("UNKNOWN")
    result["benchmark_segment_id"] = frame["segment_id"]
    result["benchmark_decision_session_date"] = frame["decision_session_date"]
    for h in HORIZONS:
        result[f"benchmark_return_{h}"] = np.nan
    result["benchmark_daily_return"] = values.where(known)
    result["benchmark_window20_complete"] = False
    for _, group in frame.loc[known].groupby(runs[known], sort=False):
        series = values.loc[group.index]
        for h in HORIZONS:
            result.loc[group.index, f"benchmark_return_{h}"] = (1 + series).rolling(h, min_periods=h).apply(
                np.prod, raw=True
            ) - 1
        result.loc[group.index, "benchmark_window20_complete"] = series.rolling(20).count().ge(20)
    return result


def enrich(base: pd.DataFrame, benchmark: pd.DataFrame, sessions: list[str], variance_floor=1e-12) -> pd.DataFrame:
    if base.duplicated(["decision_session_date", "research_uid"]).any():
        raise ValueError("Décision titre dupliquée")
    position = {d: i for i, d in enumerate(sessions)}
    for r in base.itertuples():
        i = position.get(r.source_session_date)
        if i is None or i + 1 >= len(sessions) or sessions[i + 1] != r.decision_session_date:
            raise ValueError("Disponibilité titre non J+1 XPAR")
    frame = base.merge(benchmark.reset_index(), on="source_session_date", how="left", validate="many_to_one")
    calendar = get_market_calendar("FR_EQ")
    availability = {
        d: calendar.session(date.fromisoformat(sessions[position[d] + 1])).open_at_utc.isoformat()
        for d in frame["source_session_date"].unique()
    }
    frame["benchmark_available_at"] = frame["source_session_date"].map(availability)
    if (
        pd.to_datetime(frame["benchmark_available_at"], utc=True) > pd.to_datetime(frame["decision_at"], utc=True)
    ).any():
        raise ValueError("Benchmark disponible après décision")
    for h in HORIZONS:
        frame[f"excess_return_{h}"] = frame[f"return_{h}"] - frame[f"benchmark_return_{h}"]
    for name in ("beta20", "correlation20", "relative_volatility20", "residual_return20"):
        frame[name] = np.nan
    for _, group in frame.groupby("research_uid", sort=False):
        # Pas de compression des dates : une absence dans le panel casse la fenêtre.
        stock = group.set_index("source_session_date")["return_1"].reindex(sessions)
        market = benchmark["benchmark_daily_return"]
        paired = np.isfinite(stock) & np.isfinite(market)
        x, y = stock.where(paired), market.where(paired)
        market_var = y.rolling(20, min_periods=20).var(ddof=1)
        stock_var = x.rolling(20, min_periods=20).var(ddof=1)
        covariance = x.rolling(20, min_periods=20).cov(y)
        valid = benchmark["benchmark_window20_complete"] & market_var.gt(variance_floor) & stock_var.gt(variance_floor)
        beta = (covariance / market_var).where(valid)
        correlation = (covariance / np.sqrt(stock_var * market_var)).clip(-1, 1).where(valid)
        ratio = np.sqrt(stock_var / market_var).where(valid)
        for name, series in (("beta20", beta), ("correlation20", correlation), ("relative_volatility20", ratio)):
            frame.loc[group.index, name] = group["source_session_date"].map(series).to_numpy()
    frame["residual_return20"] = frame["return_20"] - frame["beta20"] * frame["benchmark_return_20"]
    frame["benchmark_complete"] = np.isfinite(frame[list(RELATIVE_FEATURES)].to_numpy(dtype=float)).all(axis=1)
    frame["max_input_available_at"] = (
        pd.concat(
            [
                pd.to_datetime(frame["max_input_available_at"], utc=True),
                pd.to_datetime(frame["benchmark_available_at"], utc=True),
            ],
            axis=1,
        )
        .max(axis=1)
        .map(lambda t: t.isoformat())
    )
    if (
        pd.to_datetime(frame["max_input_available_at"], utc=True) > pd.to_datetime(frame["decision_at"], utc=True)
    ).any():
        raise ValueError("Entrée titre ou benchmark disponible après décision")
    return frame.drop(
        columns=["benchmark_daily_return", "benchmark_window20_complete", "benchmark_decision_session_date"]
    )


def run(config_path: Path, output_root: Path) -> dict:
    cfg = load_config(config_path)
    policy = load_policy(ROOT / cfg["base_profile"])
    base_path, reference_path = ROOT / cfg["base_panel"], ROOT / cfg["benchmark_report"]
    if _sha256(base_path) != cfg["base_sha256"]:
        raise ValueError("Panel prix différent du gel")
    frozen = json.loads(base_path.with_name("frozen_profile.json").read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if frozen["policy"] != policy or frozen["panel_sha256"] != cfg["base_sha256"]:
        raise ValueError("Contrat du profil prix divergent")
    if (
        reference["benchmark"]["code"] != cfg["benchmark_code"]
        or reference["liquidity_run_id"] != "fr6b-1893879d6d198892-e8c13cb66979"
    ):
        raise ValueError("Provenance du benchmark incompatible")
    meta = reference["files"]["benchmark_daily"]
    benchmark_path = Path(meta["path"])
    if _sha256(benchmark_path) != cfg["benchmark_sha256"] or meta["sha256"] != cfg["benchmark_sha256"]:
        raise ValueError("Benchmark différent du gel")
    with gzip.open(benchmark_path, "rt", encoding="utf-8") as stream:
        rows = pd.DataFrame([json.loads(line) for line in stream])
    if len(rows) != meta["rows"]:
        raise ValueError("Nombre de séances benchmark divergent")
    sessions = [
        s.session_date.isoformat()
        for s in get_market_calendar("FR_EQ").sessions(
            date.fromisoformat(policy["start_date"]),
            max(date.fromisoformat(policy["end_date"]), date.fromisoformat(rows["decision_session_date"].max())),
        )
        if s.is_open
    ]
    benchmark = benchmark_windows(rows, sessions)
    frame = enrich(pd.read_parquet(base_path), benchmark, sessions, cfg["variance_floor"])
    # Réutiliser exactement les gates 7-A2 en qualifiant la complétude jointe.
    qualification = frame.copy()
    qualification.loc[~frame["benchmark_complete"], "return_1"] = np.nan
    qualified, periods = qualify(qualification, policy, sessions)
    frame["common_row_ready"] = qualified["profile_row_ready"].to_numpy()
    frame["common_period_coverage_state"] = qualified["period_coverage_state"].to_numpy()
    frame["common_offline_qualified"] = frame["offline_qualified"] & qualified["offline_qualified"].to_numpy()
    for feature in RELATIVE_FEATURES:
        frame[f"{feature}_missing"] = ~np.isfinite(frame[feature])
    fingerprint = _fingerprint(
        {
            "config": cfg,
            "implementation": _sha256(Path(__file__)),
            "qualification_implementation": _sha256(ROOT / "modelFactory/fr_feature_profile_freeze.py"),
            "reference": _sha256(reference_path),
            "frozen": _sha256(base_path.with_name("frozen_profile.json")),
            "sessions": sessions,
        }
    )
    destination = output_root / f"fr-benchmark-v1-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=True)
    temporary, final = destination / "panel.build.parquet", destination / "panel.parquet"
    frame.to_parquet(temporary, engine="pyarrow", compression="zstd", index=False)
    digest = _sha256(temporary)
    if final.exists():
        if _sha256(final) != digest:
            raise ValueError("Reconstruction divergente ; artefact précédent conservé")
        temporary.unlink()
    else:
        temporary.replace(final)
    for p in periods:
        base_period = next(b for b in frozen["periods"] if b["period"] == p["period"])
        p["base_ready_rows"] = base_period["ready_rows"]
        p["lost_ready_rows"] = base_period["ready_rows"] - p["ready_rows"]
    report = {
        "profile": cfg["profile"],
        "artifact_directory": str(destination),
        "config": cfg,
        "features": list(FEATURES) + list(RELATIVE_FEATURES),
        "relative_feature_dictionary": RELATIVE_SPECS,
        "fingerprint": fingerprint,
        "panel_sha256": digest,
        "candidate_rows": len(frame),
        "base_ready_rows": int(frame["profile_row_ready"].sum()),
        "common_ready_rows": int(frame["common_row_ready"].sum()),
        "common_offline_qualified_rows": int(frame["common_offline_qualified"].sum()),
        "periods": periods,
        "coverage_by_feature": {f: int(np.isfinite(frame[f]).sum()) for f in RELATIVE_FEATURES},
        "source_hashes": {
            "base": cfg["base_sha256"],
            "benchmark": cfg["benchmark_sha256"],
            "reference": _sha256(reference_path),
        },
        "availability_basis": frozen["availability_basis"],
        "labels_used": False,
        "canonical_writes": False,
        "serving_enabled": False,
        "period_gate_scope": frozen["period_gate_scope"],
        "benchmark_scope": "INTERNAL_EQUAL_WEIGHT_RAW_PRICE_NOT_CAC40_NOT_TOTAL_RETURN",
    }
    _atomic_json(destination / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/features_fr/fr_price_benchmark_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/features/fr_price_benchmark_v1")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    report = run(args.profile, args.output_root)
    if args.verify_rebuild and report != run(args.profile, args.output_root):
        raise ValueError("Rapports reconstruits différents")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
