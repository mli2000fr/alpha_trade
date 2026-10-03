"""Sprint 8-A : labels bruts France, censure des chemins et plan de folds sans training."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256
from service.fr.universe_liquidity_6b import _iter_manifest, _load_symbol_bars


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    fixed = {
        "schema_version": 1,
        "profile": "fr_labels_v1",
        "market_code": "FR_EQ",
        "horizons": [5, 10, 20],
        "entry": "decision_session_open",
        "exit": "decision_plus_h_sessions_close",
        "availability": "next_xpar_open_after_exit",
        "return_basis": "raw_price_no_costs_no_dividends",
        "oracle_amplitude": "absolute_terminal_return",
        "oracle_top_fraction": 0.2,
        "min_cross_section": 20,
        "min_label_coverage": 0.8,
        "tie_policy": "whole_rank_interval_inside_bucket",
        "canonical_writes_enabled": False,
    }
    if any(cfg.get(k) != v for k, v in fixed.items()):
        raise ValueError("Contrat labels France incompatible ; nouvelle version requise")
    if cfg["walk_forward"] != {
        "min_train_sessions": 504,
        "validation_sessions": 126,
        "test_sessions": 126,
        "step_sessions": 126,
        "purge_embargo_sessions": 21,
        "development_end": "2025-12-31",
        "reserved_confirmation_start": "2026-01-01",
    }:
        raise ValueError("Contrat de folds modifié")
    return cfg


def path_label(
    decision: str, horizon: int, sessions: list[str], bars: dict, admitted: dict, isin: str, cutoff: str
) -> dict:
    """H compte les décalages après J : H+1 barres, puis publication après sortie."""
    i = sessions.index(decision)
    output = {
        "entry_session_date": decision,
        "exit_session_date": None,
        "label_available_session_date": None,
        "entry_price": np.nan,
        "exit_price": np.nan,
        "future_return": np.nan,
        "absolute_terminal_return": np.nan,
        "path_state": "IMMATURE",
        "censor_reason": "EXIT_OR_PUBLICATION_AFTER_CUTOFF",
    }
    if i + horizon + 1 >= len(sessions):
        return output
    exit_day, available = sessions[i + horizon], sessions[i + horizon + 1]
    output.update(exit_session_date=exit_day, label_available_session_date=available)
    if available > cutoff:
        return output
    for day in sessions[i : i + horizon + 1]:
        proof = admitted.get(day)
        if not proof or not proof.get("research_j1_eligible") or proof.get("isin") != isin:
            return {**output, "path_state": "CENSORED", "censor_reason": "PATH_NOT_ADMITTED_OR_IDENTITY_CHANGED"}
        bar = bars.get(day)
        if not bar:
            return {**output, "path_state": "CENSORED", "censor_reason": "MISSING_BAR"}
        values = np.array([bar.get(k, np.nan) for k in ("open", "high", "low", "close", "volume")], dtype=float)
        o, high, low, c, volume = values
        if (
            not np.isfinite(values).all()
            or min(o, high, low, c) <= 0
            or volume <= 0
            or high < max(o, c, low)
            or low > min(o, c, high)
        ):
            return {**output, "path_state": "CENSORED", "censor_reason": "INVALID_OHLCV_OR_ZERO_VOLUME"}
    entry, exit_price = float(bars[decision]["open"]), float(bars[exit_day]["close"])
    value = exit_price / entry - 1
    return {
        **output,
        "path_state": "VALID",
        "censor_reason": "NONE",
        "entry_price": entry,
        "exit_price": exit_price,
        "future_return": value,
        "absolute_terminal_return": abs(value),
    }


def rank_labels(frame: pd.DataFrame, min_count=20, min_coverage=0.8, top_fraction=0.2) -> pd.DataFrame:
    """Rangs sur tout l'univers candidat PIT, pas sur les seuls survivors/features prêtes."""
    result = frame.copy()
    result["decile"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["oracle_extreme"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["cross_section_state"] = "BLOCKED"
    result["decile_state"] = "NO_CROSS_SECTION"
    result["oracle_state"] = "NO_CROSS_SECTION"
    result["candidate_count"] = 0
    result["valid_path_count"] = 0
    result["label_coverage"] = 0.0
    for _, group in result.groupby(["decision_session_date", "horizon"], sort=True):
        valid = group.loc[group["path_state"].eq("VALID")]
        n, coverage = len(valid), len(valid) / len(group)
        result.loc[group.index, "candidate_count"] = len(group)
        result.loc[group.index, "valid_path_count"] = n
        result.loc[group.index, "label_coverage"] = coverage
        if n < min_count or coverage < min_coverage:
            continue
        result.loc[group.index, "cross_section_state"] = "QUALIFIED"
        returns = valid["future_return"]
        lower = np.ceil(returns.rank(method="min") * 10 / n).astype(int)
        upper = np.ceil(returns.rank(method="max") * 10 / n).astype(int)
        untied = lower.eq(upper)
        result.loc[valid.index, "decile_state"] = "TIE_BOUNDARY"
        result.loc[valid.index[untied], "decile"] = lower[untied]
        result.loc[valid.index[untied], "decile_state"] = "KNOWN"
        amplitude = valid["absolute_terminal_return"]
        best, worst = amplitude.rank(method="min", ascending=False), amplitude.rank(method="max", ascending=False)
        k = math.ceil(top_fraction * n)
        inside, outside = worst.le(k), best.gt(k)
        result.loc[valid.index, "oracle_state"] = "TIE_BOUNDARY"
        result.loc[valid.index[inside], "oracle_extreme"] = 1
        result.loc[valid.index[outside], "oracle_extreme"] = 0
        result.loc[valid.index[inside | outside], "oracle_state"] = "KNOWN"
    return result


def make_fold_plan(sessions: list[str], cfg: dict) -> list[dict]:
    wf = cfg["walk_forward"]
    development = [s for s in sessions if s <= wf["development_end"]]
    plan = []
    for validation in range(
        wf["min_train_sessions"] + wf["purge_embargo_sessions"], len(development), wf["step_sessions"]
    ):
        test = validation + wf["validation_sessions"]
        end = test + wf["test_sessions"]
        if end > len(development):
            break
        plan.append(
            {
                "fold": len(plan),
                "train_start": development[0],
                "train_end": development[validation - wf["purge_embargo_sessions"] - 1],
                "validation_start": development[validation],
                "validation_end": development[test - 1],
                "test_start": development[test],
                "test_end": development[end - 1],
                "purge_embargo_sessions": wf["purge_embargo_sessions"],
                "mandatory_train_rule": "label_available_at < validation_open",
                "mandatory_validation_rule": "label_available_at < test_open",
                "status": "PLAN_ONLY_SUPPORT_NOT_YET_VALIDATED",
            }
        )
    return plan


def run(config_path: Path, output_root: Path) -> dict:
    cfg = load_config(config_path)
    base_path = ROOT / cfg["base_panel"]
    if _sha256(base_path) != cfg["base_sha256"]:
        raise ValueError("Panel France différent du gel")
    frozen = json.loads(base_path.with_name("frozen_profile.json").read_text(encoding="utf-8"))
    liquidity = json.loads((ROOT / cfg["liquidity_report"]).read_text(encoding="utf-8"))
    reference = json.loads((ROOT / cfg["reference_report"]).read_text(encoding="utf-8"))
    if reference["liquidity_run_id"] != liquidity["liquidity_run_id"]:
        raise ValueError("Provenances France divergentes")
    manifest_path = Path(liquidity["source_manifest_path"])
    identity_path = Path(reference["files"]["identities"]["path"])
    if (
        _sha256(manifest_path) != liquidity["source_manifest_sha256"]
        or _sha256(identity_path) != reference["files"]["identities"]["sha256"]
    ):
        raise ValueError("Manifeste/identités altérés")
    identities = {r["provider_symbol"]: r for r in _iter_manifest(identity_path)}
    base = pd.read_parquet(base_path)
    symbols = set(base["provider_symbol"])
    manifest = defaultdict(dict)
    for r in _iter_manifest(manifest_path):
        if r["symbol"] in symbols:
            if r["session_date"] in manifest[r["symbol"]]:
                raise ValueError("Barre manifeste dupliquée")
            manifest[r["symbol"]][r["session_date"]] = r
    cutoff = frozen["policy"]["end_date"]
    calendar = get_market_calendar("FR_EQ")
    sessions = [
        s.session_date.isoformat()
        for s in calendar.sessions(date.fromisoformat(base["decision_session_date"].min()), date.fromisoformat(cutoff))
        if s.is_open
    ]
    opens = {
        s.session_date.isoformat(): s.open_at_utc.isoformat()
        for s in calendar.sessions(date.fromisoformat(sessions[0]), date.fromisoformat(cutoff))
        if s.is_open
    }
    records, hashes, checks = [], {}, []
    checked_pairs = set()
    archive = Path(liquidity["archive_root"])
    for symbol, group in base.groupby("provider_symbol", sort=True):
        identity = identities[symbol]
        if not group["research_uid"].eq(identity["research_uid"]).all():
            raise ValueError("Identité panel divergente")
        bars = _load_symbol_bars(archive, symbol)
        metadata = json.loads(
            (archive / "symbols" / f"{hashlib.sha256(symbol.encode()).hexdigest()[:16]}.json").read_text(
                encoding="utf-8"
            )
        )
        hashes[symbol] = metadata["payloads"]["eod"]["sha256"]
        for r in group.itertuples():
            for horizon in cfg["horizons"]:
                label = path_label(
                    r.decision_session_date, horizon, sessions, bars, manifest[symbol], identity["isin"], cutoff
                )
                record = {
                    "provider_symbol": symbol,
                    "research_uid": r.research_uid,
                    "provider_status_current": identity["provider_status_current"],
                    "decision_session_date": r.decision_session_date,
                    "horizon": horizon,
                    "label_available_at": opens.get(label["label_available_session_date"]),
                    **label,
                }
                records.append(record)
                if label["path_state"] == "VALID" and (symbol, horizon) not in checked_pairs:
                    # Recalcul indépendant du ratio avec les prix archivés, sans réutiliser future_return.
                    expected = (
                        float(bars[label["exit_session_date"]]["close"]) / float(bars[r.decision_session_date]["open"])
                        - 1
                    )
                    if not np.isclose(expected, label["future_return"], rtol=0, atol=1e-12):
                        raise ValueError("Audit indépendant du rendement divergent")
                    checks.append(
                        {
                            "symbol": symbol,
                            "decision": r.decision_session_date,
                            "horizon": horizon,
                            "return": expected,
                            "entry": label["entry_price"],
                            "exit": label["exit_price"],
                        }
                    )
                    checked_pairs.add((symbol, horizon))
    labels = rank_labels(
        pd.DataFrame(records), cfg["min_cross_section"], cfg["min_label_coverage"], cfg["oracle_top_fraction"]
    )
    if labels.duplicated(["decision_session_date", "research_uid", "horizon"]).any():
        raise ValueError("Labels dupliqués")
    fingerprint = _fingerprint(
        {
            "config": cfg,
            "implementation": _sha256(Path(__file__)),
            "archives": hashes,
            "manifest": _sha256(manifest_path),
            "identities": _sha256(identity_path),
            "sessions": sessions,
        }
    )
    destination = output_root / f"fr-labels-v1-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=True)
    temp, final = destination / "labels.build.parquet", destination / "labels.parquet"
    labels.to_parquet(temp, engine="pyarrow", compression="zstd", index=False)
    digest = _sha256(temp)
    if final.exists():
        if _sha256(final) != digest:
            raise ValueError("Labels reconstruits divergents ; précédent conservé")
        temp.unlink()
    else:
        temp.replace(final)
    audit = []
    for (horizon, year, status), group in labels.groupby(
        ["horizon", labels["decision_session_date"].str[:4], "provider_status_current"], sort=True
    ):
        audit.append(
            {
                "horizon": int(horizon),
                "year": year,
                "provider_status_current": status,
                "rows": len(group),
                "path_states": dict(Counter(group["path_state"])),
                "oracle_known": int(group["oracle_extreme"].notna().sum()),
                "oracle_positive": int(group["oracle_extreme"].eq(1).sum()),
                "decile_counts": {str(k): int(v) for k, v in group["decile"].value_counts().sort_index().items()},
            }
        )
    semesters = []
    semester_keys = labels["decision_session_date"].map(lambda d: f"{d[:4]}H{1 if int(d[5:7]) <= 6 else 2}")
    for (horizon, semester), group in labels.groupby(["horizon", semester_keys], sort=True):
        semesters.append(
            {
                "horizon": int(horizon),
                "semester": semester,
                "candidate_rows": len(group),
                "path_states": dict(Counter(group["path_state"])),
                "qualified_cross_section_days": int(
                    group.loc[group["cross_section_state"].eq("QUALIFIED"), "decision_session_date"].nunique()
                ),
                "oracle_known": int(group["oracle_extreme"].notna().sum()),
                "d1": int(group["decile"].eq(1).sum()),
                "d10": int(group["decile"].eq(10).sum()),
            }
        )
    plan = make_fold_plan(sessions, cfg)
    for fold in plan:
        support = {}
        for horizon in cfg["horizons"]:
            h = labels.loc[labels["horizon"].eq(horizon)]
            train = h["decision_session_date"].between(fold["train_start"], fold["train_end"]) & h[
                "label_available_session_date"
            ].lt(fold["validation_start"])
            validation = h["decision_session_date"].between(fold["validation_start"], fold["validation_end"]) & h[
                "label_available_session_date"
            ].lt(fold["test_start"])
            test = h["decision_session_date"].between(fold["test_start"], fold["test_end"]) & h[
                "label_available_session_date"
            ].le(cfg["walk_forward"]["development_end"])
            support[str(horizon)] = {
                name: {
                    "oracle_known": int(h.loc[mask, "oracle_extreme"].notna().sum()),
                    "decile_known": int(h.loc[mask, "decile"].notna().sum()),
                }
                for name, mask in (("train", train), ("validation", validation), ("test", test))
            }
        fold["raw_label_support"] = support
    report = {
        "profile": cfg["profile"],
        "artifact_directory": str(destination),
        "config": cfg,
        "labels_sha256": digest,
        "rows": len(labels),
        "symbols": len(symbols),
        "path_states": dict(Counter(labels["path_state"])),
        "censor_reasons": dict(Counter(labels["censor_reason"])),
        "oracle_known": int(labels["oracle_extreme"].notna().sum()),
        "decile_known": int(labels["decile"].notna().sum()),
        "audit_by_horizon_year_provider_status": audit,
        "audit_by_horizon_semester": semesters,
        "independent_ratio_checks": checks,
        "fold_plan": plan,
        "reserved_confirmation_start": "2026-01-01",
        "source_hashes": {
            "panel": cfg["base_sha256"],
            "manifest": _sha256(manifest_path),
            "identities": _sha256(identity_path),
        },
        "archive_payload_hashes": hashes,
        "availability_basis": frozen["availability_basis"],
        "verdict": "GO_RAW_RESEARCH_LABELS_ONLY" if labels["oracle_extreme"].notna().any() else "BLOCKED_LABEL_SUPPORT",
        "economic_labels_validated": False,
        "training_performed": False,
        "sector_size_audit_state": "BLOCKED_NO_VALIDATED_HISTORICAL_MEMBERSHIPS_OR_SIZE",
        "human_review_state": "PENDING_REVIEW_OF_PRICE_PATHS_AND_CORPORATE_ACTIONS",
        "canonical_writes": False,
        "limitations": [
            "RAW_PRICE_NOT_TOTAL_RETURN",
            "NO_DELISTING_SETTLEMENT_IMPUTATION",
            "CENSORSHIP_SELECTION_BIAS",
            "NO_OFFICIAL_SUSPENSION_FEED",
            "RESEARCH_J1_NOT_VERIFIED_PUBLICATION",
        ],
    }
    _atomic_json(destination / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/labels_fr/fr_labels_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/labels/fr_labels_v1")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    report = run(args.profile, args.output_root)
    if args.verify_rebuild and report != run(args.profile, args.output_root):
        raise ValueError("Rapports labels reconstruits divergents")
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("artifact_directory", "rows", "path_states", "oracle_known", "decile_known", "verdict")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
