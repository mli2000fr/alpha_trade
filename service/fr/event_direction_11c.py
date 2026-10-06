"""Frozen exploratory FR event ablation; reconstructed publication proxies only."""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from modelFactory.fr_direction_h5_audit import evaluate
from modelFactory.fr_direction_h5_shared import probability_score, ternary_target
from modelFactory.fr_feature_profile_freeze import FEATURES
from modelFactory.fr_labels_review import phase_mask
from service.fr.event_data_qualification_11b import digest, parse_positions, public_day

AMF_FEATURES = [f"amf_{name}_{window}" for window in (7, 30) for name in ("publications", "increase", "decrease", "threshold_exit")]
DILA_FEATURES = [f"dila_documents_{window}" for window in (7, 30)]


def available_day(day: str, lag: int) -> str:
    if lag not in (1, 2):
        raise ValueError("Frozen publication lag must be 1 or 2 calendar days")
    return (date.fromisoformat(day) + timedelta(days=lag)).isoformat()


def amf_events(records: list[dict]) -> tuple[list[dict], dict]:
    grouped = defaultdict(list)
    for row in records:
        if row["publication_date"] <= "2025-12-31":
            grouped[(row["isin"], row["holder"], row["publication_date"])].append(row)
    holders = defaultdict(list)
    ambiguous = 0
    for (isin, holder, day), rows in grouped.items():
        values = {(r["position_date"], r["ratio_percent"]) for r in rows}
        if len(values) != 1:
            ambiguous += 1
            # Ambiguity interrupts previous-state continuity rather than carry-forward.
            holders[(isin, holder)].append({"day": day, "ratio": None})
        else:
            holders[(isin, holder)].append({"day": day, "ratio": rows[0]["ratio_percent"]})
    events = []
    for (isin, _), rows in holders.items():
        previous = None
        for row in sorted(rows, key=lambda r: r["day"]):
            ratio = row["ratio"]
            if ratio is None:
                previous = None
                continue
            comparable = previous is not None and min(previous, ratio) >= 0.5
            events.append({"isin": isin, "day": row["day"], "publications": 1,
                           "increase": int(comparable and ratio > previous),
                           "decrease": int(comparable and ratio < previous),
                           "threshold_exit": int(previous is not None and previous >= 0.5 > ratio)})
            previous = ratio
    return events, {"ambiguous_holder_isin_day_groups_excluded": ambiguous,
                    "below_threshold_not_carried_as_current_position": True}


def dila_events(metadata: list[dict]) -> tuple[list[dict], dict]:
    grouped = defaultdict(list)
    for row in metadata:
        isin, identifier = row.get("identificationsociete_iso_cd_isi"), row.get("uin_idt_uin")
        if isin and identifier:
            grouped[(isin, identifier)].append(row)
    events, rejected = [], Counter()
    for (isin, identifier), rows in grouped.items():
        days = {public_day(row) for row in rows}
        if None in days or len(days) != 1:
            rejected["MISSING_OR_CONFLICTING_PUBLICATION_DAY"] += 1
            continue
        day = next(iter(days))
        if day <= "2025-12-31":
            events.append({"isin": isin, "id": identifier, "day": day})
    return events, {"unique_documents": len(events), "rejected_groups": dict(rejected),
                    "semantic_direction": "NOT_INFERRED_FROM_TITLES"}


def event_features(pool: pd.DataFrame, identity: dict, amf: list[dict], dila: list[dict],
                   collected: set[str], lag: int) -> pd.DataFrame:
    amf_by_isin, dila_by_isin = defaultdict(list), defaultdict(list)
    for row in amf:
        amf_by_isin[row["isin"]].append(row)
    for row in dila:
        dila_by_isin[row["isin"]].append(row)
    rows = []
    for item in pool.to_dict("records"):
        day = item["decision_session_date"]
        isin = identity[item["research_uid"]]
        row = {"dila_archive_collected": int(isin in collected)}
        for window in (7, 30):
            lower = (date.fromisoformat(day) - timedelta(days=window)).isoformat()
            candidates = [r for r in amf_by_isin[isin] if lower <= r["day"] and available_day(r["day"], lag) <= day]
            for name in ("publications", "increase", "decrease", "threshold_exit"):
                row[f"amf_{name}_{window}"] = np.log1p(sum(r[name] for r in candidates))
            candidates = [r for r in dila_by_isin[isin] if lower <= r["day"] and available_day(r["day"], lag) <= day]
            # Missing archive must not be labelled as no announcement.
            # All paired controls also include the collection flag.
            row[f"dila_documents_{window}"] = np.log1p(len(candidates)) if isin in collected else 0.0
        rows.append(row)
    return pd.DataFrame(rows, index=pool.index)


def validate_review(review: dict, audit: list[dict]) -> list[dict]:
    mapping = {Path(r["pdf_path"]).stem: r for r in audit if r.get("pdf_path")}
    validated = []
    for item in review["records"]:
        evidence = mapping[item["id"]]
        path = Path(evidence["pdf_path"])
        if digest(path.read_bytes()) != evidence["sha256"] or item["isin"] != evidence["isin"]:
            raise ValueError("Guidance PDF hash/identity mismatch")
        validated.append({**item, "pdf_path": str(path), "sha256": evidence["sha256"],
                          "url": evidence["url"], "transmission_at": evidence["published_at"],
                          "availability": "NEXT_LOCAL_DAY_PROXY_NOT_WEB_PROOF"})
    return validated


def run(profile: Path, output: Path) -> dict:
    cfg = yaml.safe_load(profile.read_text(encoding="utf-8"))
    if (cfg["profile"], cfg["market_code"], cfg["horizon"], cfg["outer_folds"], cfg["publication_lags_calendar_days"]) != (
        "fr_event_direction_11c_v1", "FR_EQ", 5, [6, 7], [1, 2]
    ) or cfg["serving_enabled"] or cfg["canonical_writes_enabled"] or cfg["confirmation_2026_enabled"]:
        raise ValueError("Frozen research scope changed")
    if output.exists():
        raise ValueError("Output already exists")
    source, direction = Path(cfg["source_dir"]), Path(cfg["direction_dir"])
    source_report = json.loads((source / "report.json").read_text(encoding="utf-8"))
    protocol_path = direction / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    pool_path = direction / "oracle_oof_pool.parquet"
    if digest(pool_path.read_bytes()) != cfg["pool_sha256"]:
        raise ValueError("OOF pool hash mismatch")
    raw = (source / "amf_positions.csv").read_bytes()
    if digest(raw) != source_report["amf"]["sha256"]:
        raise ValueError("AMF source hash mismatch")
    identity_path = Path(source_report["reference"]["path"])
    if digest(identity_path.read_bytes()) != source_report["reference"]["sha256"]:
        raise ValueError("Identity hash mismatch")
    with gzip.open(identity_path, "rt", encoding="utf-8") as handle:
        identity = {r["research_uid"]: r["isin"] for r in map(json.loads, handle)}
    metadata, collected = [], set()
    for path_str, sha in source_report["dila"]["source_hashes"].items():
        path = Path(path_str)
        raw_metadata = path.read_bytes()
        if digest(raw_metadata) != sha:
            raise ValueError("DILA source hash mismatch")
        metadata.extend(json.loads(raw_metadata))
        collected.add(path.stem)
    amf, amf_review = amf_events(parse_positions(raw)[0])
    dila, dila_review = dila_events(metadata)
    pool = pd.read_parquet(pool_path)
    if pool.decision_session_date.gt(cfg["development_end"]).any():
        raise ValueError("Reserved 2026 data in pool")
    if pool.duplicated(["research_uid", "decision_session_date"]).any():
        raise ValueError("Duplicate OOF decisions")
    guidance_path = Path(cfg["guidance_review"])
    review = yaml.safe_load(guidance_path.read_text(encoding="utf-8"))
    audit = json.loads((Path(cfg["guidance_dir"]) / "pdf_audit.json").read_text(encoding="utf-8"))
    validated = validate_review(review, audit)
    output.mkdir(parents=True)
    hashes = {"profile": digest(profile.read_bytes()), "oracle_pool": cfg["pool_sha256"],
              "outer_protocol": digest(protocol_path.read_bytes()),
              "source_report": digest((source / "report.json").read_bytes()),
              "guidance_review": digest(guidance_path.read_bytes()),
              "code": digest(Path(__file__).read_bytes())}
    # Protocol is written before fitting or reading performance metrics.
    (output / "protocol.json").write_text(json.dumps({"config": cfg, "hashes": hashes,
        "variants": ["price_control", "price_amf", "price_dila", "price_amf_dila"],
        "no_test_selection": True, "exploratory_publication_proxy_only": True}, indent=2), encoding="utf-8")
    (output / "guidance_validated.json").write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")
    folds, prediction_parts = [], []
    metrics_cfg = {"side_fraction": cfg["side_fraction"], "seed": cfg["seed"],
                   "support": {"min_dates": cfg["min_evaluation_dates"], "min_tail_per_class": cfg["min_evaluation_tail_per_class"]}}
    with threadpool_limits(limits=cfg["threads"]):
        for lag in cfg["publication_lags_calendar_days"]:
            features = event_features(pool, identity, amf, dila, collected, lag)
            work = pd.concat([pool, features], axis=1)
            work.to_parquet(output / f"feature_proxy_lag{lag}.parquet", index=False)
            variants = {"price_control": list(FEATURES) + ["dila_archive_collected"],
                        "price_amf": list(FEATURES) + ["dila_archive_collected"] + AMF_FEATURES,
                        "price_dila": list(FEATURES) + ["dila_archive_collected"] + DILA_FEATURES,
                        "price_amf_dila": list(FEATURES) + ["dila_archive_collected"] + AMF_FEATURES + DILA_FEATURES}
            for plan in protocol["plans"]:
                if plan["fold"] not in cfg["outer_folds"] or plan["status"] != "ADMITTED":
                    continue
                phases = {p: work[phase_mask(work, plan["dates"], p, cfg["development_end"])].copy() for p in ("train", "validation", "test")}
                target = ternary_target(phases["train"].decile)
                known = target.notna()
                if phases["train"].decision_session_date.nunique() < cfg["min_train_dates"] or min(target[known].value_counts().reindex([0, 1, 2], fill_value=0)) < cfg["min_train_per_class"]:
                    raise ValueError("Train support gate failed")
                for name, columns in variants.items():
                    model = make_pipeline(StandardScaler(), LogisticRegression(C=cfg["logistic_C"], max_iter=cfg["logistic_max_iter"], random_state=cfg["seed"]))
                    model.fit(phases["train"].loc[known, columns], target[known].astype(int))
                    record = {"fold": plan["fold"], "lag": lag, "variant": name, "metrics": {}}
                    for phase in ("validation", "test"):
                        frame = phases[phase].copy()
                        probs, score = probability_score(model, frame[columns])
                        frame["event_score"] = score
                        frame["p_d1"], frame["p_d10"] = probs[:, 0], probs[:, 2]
                        metric, daily, _ = evaluate(frame, "event_score", metrics_cfg)
                        if not metric["support_admitted"]:
                            raise ValueError("Evaluation support gate failed")
                        record["metrics"][phase] = metric
                        if phase == "test":
                            frame["outer_fold"], frame["lag"], frame["variant"] = plan["fold"], lag, name
                            prediction_parts.append(frame[["research_uid", "decision_session_date", "outer_fold", "lag", "variant", "event_score", "p_d1", "p_d10", "future_return", "decile"]])
                            daily.to_parquet(output / f"fold{plan['fold']}_{name}_lag{lag}_daily.parquet", index=False)
                    folds.append(record)
                    print(f"fold={plan['fold']} lag={lag} variant={name} test_auc={record['metrics']['test']['tail_auc']:.4f}", flush=True)
    pd.concat(prediction_parts, ignore_index=True).to_parquet(output / "oos_predictions.parquet", index=False)
    summary = []
    for lag in cfg["publication_lags_calendar_days"]:
        controls = {r["fold"]: r for r in folds if r["lag"] == lag and r["variant"] == "price_control"}
        for name in ("price_amf", "price_dila", "price_amf_dila"):
            rows = [r for r in folds if r["lag"] == lag and r["variant"] == name]
            delta = [r["metrics"]["test"]["tail_auc"] - controls[r["fold"]]["metrics"]["test"]["tail_auc"] for r in rows]
            auc = float(np.mean([r["metrics"]["test"]["tail_auc"] for r in rows]))
            ic = float(np.mean([r["metrics"]["test"]["means"]["ic"] for r in rows]))
            spread = float(np.mean([r["metrics"]["test"]["means"]["spread"] for r in rows]))
            passed = len(rows) >= cfg["min_oos_folds"] and auc >= cfg["min_mean_tail_auc"] and np.mean(delta) >= cfg["min_auc_delta_vs_same_control"] and min(delta) > 0 and ic >= cfg["min_mean_daily_ic"] and spread >= cfg["min_mean_daily_spread"]
            summary.append({"lag": lag, "variant": name, "folds": len(rows), "mean_tail_auc": auc,
                            "mean_auc_delta": float(np.mean(delta)), "fold_auc_deltas": delta,
                            "mean_daily_ic": ic, "mean_daily_spread": spread,
                            "statistical_verdict": "EXPLORATORY_SIGNAL_REQUIRES_STRICT_PIT_CONFIRMATION" if passed else "NO_GO_INCREMENTAL_PROXY_PILOT"})
    forward = [r for r in validated if r["type"] == "FORWARD_GUIDANCE_REVISION"]
    report = {"config": cfg, "hashes": hashes, "amf_review": amf_review, "dila_review": dila_review,
              "folds": folds, "summary": summary,
              "guidance": {"reviewed_documents": len(validated), "forward_pairs": len(forward),
                           "up": sum(r["direction"] == "UP" for r in forward), "down": sum(r["direction"] == "DOWN" for r in forward),
                           "verdict": "BLOCKED_INSUFFICIENT_VALIDATED_GUIDANCE_AND_NO_INDEPENDENT_REVIEW"},
              "strict_pit_verdict": "NOT_QUALIFIED_NO_HISTORICAL_VINTAGE_OR_WEB_AVAILABILITY_PROOF",
              "canonical_writes": False, "serving_enabled": False, "economic_backtest": False,
              "confirmation_2026_used": False}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
