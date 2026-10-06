"""Sprint 8-B : revue hors ligne des chemins et du support des folds FR, sans modèle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256
from service.fr.universe_liquidity_6b import _load_symbol_bars


def join_panels(labels: pd.DataFrame, price: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    keys = ["decision_session_date", "research_uid"]
    if labels.duplicated(keys + ["horizon"]).any() or price.duplicated(keys).any() or benchmark.duplicated(keys).any():
        raise ValueError("Clés labels/panels dupliquées")
    if set(map(tuple, price[keys].to_numpy())) != set(map(tuple, benchmark[keys].to_numpy())):
        raise ValueError("Univers prix/benchmark divergent")
    for frame in (price, benchmark):
        if (
            pd.to_datetime(frame["max_input_available_at"], utc=True) > pd.to_datetime(frame["decision_at"], utc=True)
        ).any():
            raise ValueError("Feature disponible après décision")
    merged = labels.merge(
        price[keys + ["profile_row_ready"]], on=keys, how="left", validate="many_to_one", indicator=True
    )
    if not merged["_merge"].eq("both").all():
        raise ValueError("Label sans candidat prix")
    merged = merged.drop(columns="_merge").merge(
        benchmark[keys + ["common_row_ready"]], on=keys, validate="many_to_one"
    )
    if (merged["common_row_ready"] & ~merged["profile_row_ready"]).any():
        raise ValueError("Le support commun doit être inclus dans le prix-only")
    return merged


def phase_mask(frame: pd.DataFrame, fold: dict, phase: str, development_end: str) -> pd.Series:
    bounded = frame["decision_session_date"].between(fold[f"{phase}_start"], fold[f"{phase}_end"])
    available = frame["label_available_session_date"]
    if phase == "train":
        mature = available.lt(fold["validation_start"])
    elif phase == "validation":
        mature = available.lt(fold["test_start"])
    elif phase == "test":
        mature = available.le(development_end)
    else:
        raise ValueError("Phase inconnue")
    return bounded & mature & frame["path_state"].eq("VALID")


def fold_support(frame: pd.DataFrame, folds: list[dict], sessions: list[str], cfg: dict) -> list[dict]:
    output = []
    for fold in folds:
        for horizon, h in frame.groupby("horizon", sort=True):
            for phase in ("train", "validation", "test"):
                expected = [s for s in sessions if fold[f"{phase}_start"] <= s <= fold[f"{phase}_end"]]
                mature = phase_mask(h, fold, phase, cfg["development_end"])
                for profile, column in (
                    ("price_only", "profile_row_ready"),
                    ("common_price_benchmark", "common_row_ready"),
                ):
                    selected = h.loc[mature & h[column] & h["oracle_extreme"].notna()]
                    daily = selected.groupby("decision_session_date").size()
                    usable_days = daily.index[daily.ge(cfg["min_cross_section"])]
                    selected = selected.loc[selected["decision_session_date"].isin(usable_days)]
                    coverage = len(usable_days) / len(expected) if expected else 0.0
                    positives = int(selected["oracle_extreme"].eq(1).sum())
                    negatives = int(selected["oracle_extreme"].eq(0).sum())
                    reasons = []
                    if coverage < cfg["min_session_coverage"]:
                        reasons.append("SESSION_COVERAGE_BELOW_80PCT")
                    if len(usable_days) < cfg["min_usable_sessions"]:
                        reasons.append("USABLE_SESSIONS_BELOW_40")
                    if not positives or not negatives:
                        reasons.append("ORACLE_CLASS_MISSING")
                    output.append(
                        {
                            "fold": fold["fold"],
                            "horizon": int(horizon),
                            "phase": phase,
                            "profile": profile,
                            "expected_sessions": len(expected),
                            "usable_sessions": len(usable_days),
                            "session_coverage": coverage,
                            "oracle_rows": len(selected),
                            "oracle_positive": positives,
                            "oracle_negative": negatives,
                            "d1": int(selected["decile"].eq(1).sum()),
                            "d10": int(selected["decile"].eq(10).sum()),
                            "symbols": int(selected["research_uid"].nunique()),
                            "delisted_rows": int(selected["provider_status_current"].eq("delisted").sum()),
                            "state": "GO_DATA_SUPPORT_ONLY" if not reasons else "BLOCKED_DATA_SUPPORT",
                            "reasons": reasons,
                        }
                    )
    return output


def choose_cases(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    # Aucun rendement de confirmation 2026 n'est inspecté pour choisir les cas.
    development = frame.loc[
        frame["path_state"].eq("VALID") & frame["label_available_session_date"].le(cfg["development_end"])
    ].copy()
    development["semester"] = development["decision_session_date"].map(
        lambda d: f"{d[:4]}H{1 if int(d[5:7]) <= 6 else 2}"
    )
    selected = []
    for _, group in development.groupby(["horizon", "semester"], sort=True):
        ordered = group.sort_values(["future_return", "decision_session_date", "research_uid"], kind="stable")
        n = cfg["extreme_cases_per_side_horizon_semester"]
        selected.extend([ordered.head(n), ordered.tail(n)])
    selected.append(development.loc[development["provider_status_current"].eq("delisted")])
    return (
        pd.concat(selected)
        .drop_duplicates(["decision_session_date", "research_uid", "horizon"])
        .sort_values(["provider_symbol", "decision_session_date", "horizon"], kind="stable")
    )


def read_payload(archive: Path, metadata: dict, kind: str) -> tuple[list, str]:
    meta = metadata["payloads"][kind]
    with gzip.open(archive / meta["file"], "rb") as stream:
        payload = stream.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != meta["sha256"]:
        raise ValueError(f"Payload {kind} altéré")
    return json.loads(payload), digest


def review_cases(selected: pd.DataFrame, archive: Path, sessions: list[str], cfg: dict) -> tuple[list, dict]:
    cases, hashes = [], {}
    for symbol, group in selected.groupby("provider_symbol", sort=True):
        bars = _load_symbol_bars(archive, symbol)
        key = hashlib.sha256(symbol.encode()).hexdigest()[:16]
        metadata = json.loads((archive / "symbols" / f"{key}.json").read_text(encoding="utf-8"))
        dividends, div_hash = read_payload(archive, metadata, "div")
        splits, split_hash = read_payload(archive, metadata, "splits")
        hashes[symbol] = {"eod": metadata["payloads"]["eod"]["sha256"], "div": div_hash, "splits": split_hash}
        for r in group.itertuples():
            i, j = sessions.index(r.entry_session_date), sessions.index(r.exit_session_date)
            path = [
                {"date": day, **{k: bars[day][k] for k in ("open", "high", "low", "close", "volume")}}
                for day in sessions[i : j + 1]
            ]
            value = path[-1]["close"] / path[0]["open"] - 1
            if not np.isclose(value, r.future_return, rtol=0, atol=1e-12):
                raise ValueError("Recalcul du chemin divergent")
            events = {
                "dividends": [d for d in dividends if r.entry_session_date <= d["date"] <= r.exit_session_date],
                "splits": [d for d in splits if r.entry_session_date <= d["date"] <= r.exit_session_date],
            }
            daily = [abs(path[k]["close"] / path[k - 1]["close"] - 1) for k in range(1, len(path))]
            flags = []
            if events["splits"]:
                flags.append("PROVIDER_SPLIT_IN_VALID_PATH")
            if events["dividends"]:
                flags.append("DIVIDEND_RAW_RETURN_NOT_TOTAL_RETURN")
            if daily and max(daily) > cfg["large_daily_move_alert"]:
                flags.append("LARGE_MOVE_REQUIRES_DOCUMENTARY_REVIEW")
            cases.append(
                {
                    "symbol": symbol,
                    "decision": r.decision_session_date,
                    "horizon": r.horizon,
                    "return": value,
                    "provider_status_current": r.provider_status_current,
                    "flags": flags,
                    "events": events,
                    "path": path,
                    "review_state": "SOURCE_RATIO_CHECKED_NOT_OFFICIAL_EVENT_VALIDATION",
                }
            )
    return cases, hashes


def run(config_path: Path, output_root: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if (cfg.get("schema_version"), cfg.get("profile"), cfg.get("canonical_writes_enabled")) != (
        1,
        "fr_labels_review_v1",
        False,
    ):
        raise ValueError("Revue France incompatible")
    if (cfg["development_end"], cfg["min_cross_section"], cfg["min_session_coverage"], cfg["min_usable_sessions"]) != (
        "2025-12-31",
        20,
        0.8,
        40,
    ):
        raise ValueError("Règles de revue figées")
    label_report_path = ROOT / cfg["labels_report"]
    label_report = json.loads(label_report_path.read_text(encoding="utf-8"))
    sources = {
        "labels": label_report_path.with_name("labels.parquet"),
        "price": ROOT / cfg["price_panel"],
        "benchmark": ROOT / cfg["benchmark_panel"],
    }
    expected = {"labels": cfg["labels_sha256"], "price": cfg["price_sha256"], "benchmark": cfg["benchmark_sha256"]}
    if (
        any(_sha256(p) != expected[k] for k, p in sources.items())
        or label_report["labels_sha256"] != cfg["labels_sha256"]
    ):
        raise ValueError("Sources divergentes du gel")
    frame = join_panels(*(pd.read_parquet(sources[k]) for k in ("labels", "price", "benchmark")))
    calendar = get_market_calendar("FR_EQ")
    sessions = [
        s.session_date.isoformat()
        for s in calendar.sessions(date.fromisoformat(frame["decision_session_date"].min()), date(2026, 10, 2))
        if s.is_open
    ]
    support = fold_support(frame, label_report["fold_plan"], sessions, cfg)
    liquidity = json.loads((ROOT / cfg["liquidity_report"]).read_text(encoding="utf-8"))
    selected = choose_cases(frame, cfg)
    cases, hashes = review_cases(selected, Path(liquidity["archive_root"]), sessions, cfg)
    fingerprint = _fingerprint(
        {
            "cfg": cfg,
            "sources": expected,
            "labels_report": _sha256(label_report_path),
            "code": _sha256(Path(__file__)),
            "case_archives": hashes,
        }
    )
    destination = output_root / f"fr-label-review-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=True)
    complete_folds = {}
    for profile in ("price_only", "common_price_benchmark"):
        complete_folds[profile] = {
            str(h): [
                f["fold"]
                for f in label_report["fold_plan"]
                if all(
                    r["state"] == "GO_DATA_SUPPORT_ONLY"
                    for r in support
                    if r["profile"] == profile and r["horizon"] == h and r["fold"] == f["fold"]
                )
            ]
            for h in (5, 10, 20)
        }
    report = {
        "profile": cfg["profile"],
        "artifact_directory": str(destination),
        "config": cfg,
        "source_hashes": expected,
        "fold_support": support,
        "complete_data_support_folds": complete_folds,
        "review_cases": len(cases),
        "cases_with_splits": sum(bool(c["events"]["splits"]) for c in cases),
        "cases_with_dividends": sum(bool(c["events"]["dividends"]) for c in cases),
        "cases_with_large_move": sum("LARGE_MOVE_REQUIRES_DOCUMENTARY_REVIEW" in c["flags"] for c in cases),
        "case_archive_hashes": hashes,
        "confirmation_returns_inspected": False,
        "human_official_event_validation": "PENDING",
        "training_performed": False,
        "verdict": "REVIEW_COMPLETE_RESEARCH_ONLY_RESERVES_REMAIN",
    }
    _atomic_json(destination / "cases.json", cases)
    report["cases_sha256"] = _sha256(destination / "cases.json")
    _atomic_json(destination / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/labels_fr/fr_labels_review_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/labels/review")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    report = run(args.profile, args.output_root)
    if args.verify_rebuild and report != run(args.profile, args.output_root):
        raise ValueError("Revue reconstruite divergente")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("fold_support", "case_archive_hashes", "config")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
