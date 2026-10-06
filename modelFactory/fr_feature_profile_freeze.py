"""Qualification hors ligne du profil France court ; aucune cible ni écriture SQL."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from modelFactory.fr_feature_panel import FEATURE_SPECS
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256

FEATURES = (
    "return_1",
    "return_3",
    "return_5",
    "return_10",
    "return_20",
    "sma20_distance",
    "atr20_pct",
    "realized_vol20",
    "range20_position",
    "volume_ratio20",
    "traded_value_mean20_eur",
    "overnight_gap",
    "intraday_return",
    "intraday_range",
)


def load_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (
        policy.get("schema_version"),
        policy.get("profile"),
        policy.get("market_code"),
        policy.get("database_alias"),
    ) != (1, "fr_price_short_v1", "FR_EQ", "fr_primary"):
        raise ValueError("Profil France court incompatible")
    if tuple(policy.get("features", [])) != FEATURES:
        raise ValueError("Liste ordonnée des 14 features figée : créer une nouvelle version pour la modifier")
    if any(
        policy.get(k) for k in ("benchmark_features_enabled", "sector_features_enabled", "canonical_writes_enabled")
    ):
        raise ValueError("Profil price-only sans écriture canonique")
    gates = policy["period_gates"]
    if policy["min_cross_section"] != 20 or gates != {
        "min_ready_row_fraction": 0.8,
        "min_ready_session_fraction": 0.8,
        "min_ready_sessions": 40,
        "require_complete_semester": True,
    }:
        raise ValueError("Gates de couverture figés")
    if date.fromisoformat(policy["start_date"]) > date.fromisoformat(policy["end_date"]):
        raise ValueError("Période inversée")
    return policy


def qualify(panel: pd.DataFrame, policy: dict, sessions: list[str]) -> tuple[pd.DataFrame, list[dict]]:
    """Le masque ligne ne dépend que de la séance courante ; le gate période est hors ligne."""
    if panel.duplicated(["decision_session_date", "research_uid"]).any():
        raise ValueError("Clés de décision dupliquées")
    if not panel["decision_session_date"].isin(sessions).all():
        raise ValueError("Décision hors calendrier XPAR")
    start, end = policy["start_date"], policy["end_date"]
    frame = panel.loc[panel["decision_session_date"].between(start, end)].copy()
    # Supprimer toutes les anciennes features/masks pour interdire un gate complet 18 implicite.
    metadata = [
        c
        for c in frame
        if c not in FEATURE_SPECS
        and not c.startswith("missing_")
        and not c.startswith("mask_")
        and c not in ("research_ready", "feature_complete_count", "cross_section_count")
    ]
    frame = frame[metadata + list(FEATURES)]
    frame["profile_complete"] = np.isfinite(frame[list(FEATURES)].to_numpy(dtype=float)).all(axis=1)
    frame["profile_complete_count"] = frame.groupby("decision_session_date")["profile_complete"].transform("sum")
    frame["profile_row_ready"] = frame["profile_complete"] & frame["profile_complete_count"].ge(
        policy["min_cross_section"]
    )
    frame["period"] = frame["decision_session_date"].map(lambda d: f"{d[:4]}H{1 if int(d[5:7]) <= 6 else 2}")
    periods = []
    gates = policy["period_gates"]
    for year in range(int(start[:4]), int(end[:4]) + 1):
        for half in (1, 2):
            lower, upper = f"{year}-{'01-01' if half == 1 else '07-01'}", f"{year}-{'06-30' if half == 1 else '12-31'}"
            if upper < start or lower > end:
                continue
            key = f"{year}H{half}"
            group = frame.loc[frame["period"].eq(key)]
            expected = [d for d in sessions if max(start, lower) <= d <= min(end, upper)]
            ready = group.loc[group["profile_row_ready"]]
            row_fraction = len(ready) / len(group) if len(group) else 0.0
            session_fraction = ready["decision_session_date"].nunique() / len(expected) if expected else 0.0
            complete_period = start <= lower and end >= upper
            reasons = []
            if not len(group):
                reasons.append("NO_CANDIDATES")
            if not complete_period:
                reasons.append("PARTIAL_PERIOD")
            if row_fraction < gates["min_ready_row_fraction"]:
                reasons.append("READY_ROWS_BELOW_80PCT")
            if session_fraction < gates["min_ready_session_fraction"]:
                reasons.append("READY_SESSIONS_BELOW_80PCT")
            if ready["decision_session_date"].nunique() < gates["min_ready_sessions"]:
                reasons.append("READY_SESSIONS_BELOW_40")
            periods.append(
                {
                    "period": key,
                    "start": max(start, lower),
                    "end": min(end, upper),
                    "state": "GO_DATA_COVERAGE" if not reasons else "BLOCKED_DATA_COVERAGE",
                    "reasons": reasons,
                    "complete_semester": complete_period,
                    "candidate_rows": len(group),
                    "complete_rows": int(group["profile_complete"].sum()),
                    "ready_rows": len(ready),
                    "official_sessions_observed_range": len(expected),
                    "ready_sessions": int(ready["decision_session_date"].nunique()),
                    "ready_row_fraction": row_fraction,
                    "ready_session_fraction": session_fraction,
                    "ready_symbols": int(ready["research_uid"].nunique()),
                }
            )
    states = {p["period"]: p["state"] for p in periods}
    frame["period_coverage_state"] = frame["period"].map(states)
    frame["offline_qualified"] = frame["profile_row_ready"] & frame["period_coverage_state"].eq("GO_DATA_COVERAGE")
    return frame, periods


def run(policy_path: Path, output_root: Path) -> dict:
    policy = load_policy(policy_path)
    source = ROOT / policy["source_panel"]
    if _sha256(source) != policy["source_sha256"]:
        raise ValueError("Empreinte du panel source différente du gel")
    source_report = json.loads(source.with_name("report.json").read_text(encoding="utf-8"))
    if source_report["panel_sha256"] != policy["source_sha256"]:
        raise ValueError("Rapport source incompatible")
    sessions = [
        s.session_date.isoformat()
        for s in get_market_calendar("FR_EQ").sessions(
            date.fromisoformat(policy["start_date"]), date.fromisoformat(policy["end_date"])
        )
        if s.is_open
    ]
    panel, periods = qualify(pd.read_parquet(source), policy, sessions)
    fingerprint = _fingerprint(
        {
            "policy": policy,
            "implementation": _sha256(Path(__file__)),
            "source_report": _sha256(source.with_name("report.json")),
            "sessions": sessions,
        }
    )
    destination = output_root / f"fr-price-short-v1-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / "panel.build.parquet"
    panel.to_parquet(temporary, engine="pyarrow", compression="zstd", index=False)
    final = destination / "panel.parquet"
    digest = _sha256(temporary)
    if final.exists():
        if _sha256(final) != digest:
            raise ValueError("Reconstruction divergente ; artefact précédent conservé")
        temporary.unlink()
    else:
        temporary.replace(final)
    report = {
        "profile": policy["profile"],
        "market_code": "FR_EQ",
        "artifact_directory": str(destination),
        "features": list(FEATURES),
        "feature_dictionary": {k: FEATURE_SPECS[k] for k in FEATURES},
        "policy": policy,
        "fingerprint": fingerprint,
        "source_sha256": policy["source_sha256"],
        "implementation_sha256": _sha256(Path(__file__)),
        "panel_sha256": digest,
        "candidate_rows": len(panel),
        "complete_rows": int(panel["profile_complete"].sum()),
        "row_ready": int(panel["profile_row_ready"].sum()),
        "offline_qualified_rows": int(panel["offline_qualified"].sum()),
        "periods": periods,
        "availability_basis": source_report["availability_basis"],
        "period_gate_scope": "OFFLINE_DATA_QUALIFICATION_NOT_A_PIT_TRADING_SIGNAL",
        "labels_used": False,
        "benchmark_enabled": False,
        "canonical_writes": False,
    }
    _atomic_json(destination / "frozen_profile.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/features_fr/fr_price_short_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/features/fr_price_short_v1")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    report = run(args.profile, args.output_root)
    if args.verify_rebuild:
        second = run(args.profile, args.output_root)
        if report != second:
            raise ValueError("Rapports reconstruits différents")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
