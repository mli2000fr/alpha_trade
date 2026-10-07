"""Research-only, genuinely prospective CN Oracle H20 TOP20 candidate export.

No training, database writes, serving registration, or historical score backfill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_feature_panel import (
    CNFeatureProfile, assemble_candidate_panel, compute_symbol_features,
)
from modelFactory.cn_oracle_walk_forward import Protocol, _matrix
from service.market.cn_dragon_tiger_schedule_15d6 import (
    adjacent_open, is_open, load_calendar,
)
from service.market.cn_universe_pit import CNUniversePolicy, decide_member

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "research_cn" / "sprint15d8_oracle_prospective.yaml"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_contract(path: Path = DEFAULT_CONFIG) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if (raw.get("protocol_id") != "CN_ORACLE_PROSPECTIVE_15D8_V1"
            or raw.get("market_code") != "CN_A"
            or raw.get("database_alias") != "cn_primary"
            or raw.get("status") != "RESEARCH_ONLY"
            or raw.get("horizon") != 20
            or float(raw.get("top_pct", 0)) != 0.20
            or raw.get("decision_time_shanghai") != "09:15:00"):
        raise ValueError("Invalid CN 15-D8 research contract")
    for key in ("model_file", "model_report"):
        file = _path(raw[key])
        if not file.is_file() or _sha(file).lower() != str(raw[f"{key}_sha256"]).lower():
            raise RuntimeError(f"Frozen Oracle artifact changed or missing: {key}")
    protocol = Protocol.load(_path(raw["oracle_protocol"]))
    matched = yaml.safe_load(_path(raw["dragon_tiger_protocol"]).read_text(encoding="utf-8")) or {}
    if (matched.get("protocol_id") != "CN_DRAGON_TIGER_15D7_V1"
            or int(matched["candidate_contract"]["oracle_horizon"]) != 20
            or float(matched["candidate_contract"]["oracle_top_pct"]) != float(raw["top_pct"])
            or matched.get("decision_time") != raw["decision_time_shanghai"]):
        raise RuntimeError("D8 Oracle contract differs from D7 candidate contract")
    report = json.loads(_path(raw["model_report"]).read_text(encoding="utf-8"))
    through = date.fromisoformat(str(raw["trained_through"]))
    if (report.get("status") != "OOS_RESEARCH_ONLY"
            or report.get("horizon") != 20
            or report.get("test_semester") != "2025H2"
            or report.get("model_name") != "lightgbm"
            or report.get("protocol_sha256") != _sha(_path(raw["oracle_protocol"]))
            or date.fromisoformat(report["split"]["validation_label_max_available_at"][:10]) != through
            or through >= date(2026, 1, 1)):
        raise RuntimeError("Frozen model provenance or label maturity invalid")
    if not 0 < float(raw["minimum_feature_coverage"]) <= 1:
        raise ValueError("Invalid feature coverage gate")
    if int(raw["minimum_candidate_count"]) < 20:
        raise ValueError("Too few candidates for Oracle cross-section")
    if float(protocol.raw["evaluation"]["top_pct"]) != float(raw["top_pct"]):
        raise RuntimeError("Oracle TOP fraction differs from frozen protocol")
    return {"raw": raw, "protocol": protocol, "report": report,
            "config_sha256": _sha(path), "trained_through": through}


def decision_window(decision_day: date, *, now: datetime, calendar: dict) -> dict:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if not is_open(decision_day, calendar):
        raise ValueError("Decision day is not a verified open CN session")
    previous = adjacent_open(decision_day, calendar, -1)
    cutoff = datetime.combine(decision_day, time(9, 15), SHANGHAI).astimezone(UTC)
    if now.astimezone(UTC) >= cutoff:
        raise RuntimeError("Oracle CN cutoff 09:15 Shanghai already passed; retroactive export forbidden")
    if now.astimezone(SHANGHAI).date() < previous:
        raise RuntimeError("Previous CN market session has not finished")
    return {"decision_day": decision_day, "previous_day": previous,
            "cutoff_utc": cutoff, "now_utc": now.astimezone(UTC)}


def _load_market(engine, *, previous: date, now: datetime, profile: CNFeatureProfile,
                 policy: CNUniversePolicy) -> dict:
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("CN prospective Oracle refused outside alpha_trade_cn")
    known = now.astimezone(UTC).replace(tzinfo=None)
    with engine.connect() as conn:
        sessions = conn.execute(text(
            "SELECT session_date,close_at_utc FROM market_sessions WHERE market_code='CN_A' "
            "AND session_status='open' AND session_date<=:previous "
            "ORDER BY session_date DESC LIMIT :count"
        ), {"previous": previous, "count": max(300, profile.warmup_sessions + 1)}).mappings().all()
        if not sessions or sessions[0]["session_date"] != previous:
            raise RuntimeError("Last completed CN session missing from canonical calendar")
        if not sessions[0]["close_at_utc"] or sessions[0]["close_at_utc"] >= known:
            raise RuntimeError("Last CN session has not closed at the observation time")
        if len(sessions) < profile.warmup_sessions + 1:
            raise RuntimeError("Insufficient CN feature warmup history")
        history_start = sessions[-1]["session_date"]
        universe_start = sessions[min(len(sessions), policy.history_lookback_sessions) - 1]["session_date"]
        liquidity_start = sessions[min(len(sessions), policy.liquidity_lookback_sessions) - 1]["session_date"]
        instruments = [dict(row) for row in conn.execute(text(
            "SELECT i.instrument_id,i.instrument_type,i.exchange_mic,i.listing_date,i.delisting_date,"
            "ips.provider_symbol FROM instruments i JOIN instrument_provider_symbols ips "
            "ON ips.instrument_id=i.instrument_id AND ips.provider='baostock' AND ips.is_primary=1 "
            "WHERE i.market_code='CN_A' AND i.instrument_type='equity' ORDER BY i.instrument_id"
        )).mappings()]
        if len({row["instrument_id"] for row in instruments}) != len(instruments):
            raise RuntimeError("Ambiguous primary BaoStock mapping")
        bars = pd.read_sql(text(
            "SELECT b.instrument_id,b.date,CAST(b.open AS DOUBLE) open,CAST(b.high AS DOUBLE) high,"
            "CAST(b.low AS DOUBLE) low,CAST(b.close AS DOUBLE) close,"
            "CAST(b.pre_close AS DOUBLE) pre_close,CAST(b.volume AS DOUBLE) volume,"
            "CAST(b.amount AS DOUBLE) amount,CAST(b.daily_return AS DOUBLE) daily_return,"
            "b.trading_status,b.is_special_treatment,b.available_at "
            "FROM stock_bars_daily b JOIN instruments i ON i.instrument_id=b.instrument_id "
            "WHERE b.market_code='CN_A' AND i.instrument_type='equity' "
            "AND b.date BETWEEN :start AND :previous AND b.available_at<=:known "
            "ORDER BY b.instrument_id,b.date"
        ), conn, params={"start": history_start, "previous": previous, "known": known})
        benchmark = pd.read_sql(text(
            "SELECT date,CAST(open AS DOUBLE) open,CAST(high AS DOUBLE) high,"
            "CAST(low AS DOUBLE) low,CAST(close AS DOUBLE) close,"
            "CAST(pre_close AS DOUBLE) pre_close,CAST(volume AS DOUBLE) volume,"
            "CAST(amount AS DOUBLE) amount,CAST(daily_return AS DOUBLE) daily_return,"
            "trading_status,is_special_treatment,available_at "
            "FROM stock_bars_daily WHERE market_code='CN_A' AND symbol=:symbol "
            "AND date BETWEEN :start AND :previous AND available_at<=:known ORDER BY date"
        ), conn, params={"symbol": profile.benchmark_provider_symbol,
                         "start": history_start, "previous": previous, "known": known})
        factors = pd.read_sql(text(
            "SELECT instrument_id,ex_date date,available_at FROM cn_corporate_actions "
            "WHERE ex_date BETWEEN :start AND :previous AND available_at<=:known "
            "AND classification_status='UNCLASSIFIED_FACTOR_EVENT'"
        ), conn, params={"start": history_start, "previous": previous, "known": known})
        limits = pd.read_sql(text(
            "SELECT instrument_id,session_date,policy_code limit_policy,locked_up limit_locked_up,"
            "locked_down limit_locked_down,available_at limit_available_at "
            "FROM cn_daily_price_limits WHERE session_date=:previous AND available_at<=:known"
        ), conn, params={"previous": previous, "known": known})
    if bars.empty or benchmark.empty or pd.to_datetime(benchmark["date"]).max().date() != previous:
        raise RuntimeError("CN equity or CSI300 inputs missing through previous session")
    benchmark["instrument_id"] = -1
    return {"sessions": sessions, "instruments": instruments, "bars": bars,
            "benchmark": benchmark, "factors": factors, "limits": limits,
            "universe_start": universe_start, "liquidity_start": liquidity_start}


def _preopen_members(inputs: dict, *, decision_day: date, previous: date,
                     cutoff: datetime, policy: CNUniversePolicy) -> tuple[pd.DataFrame, dict]:
    bars = inputs["bars"].copy()
    bars["date"] = pd.to_datetime(bars["date"]).dt.date
    bars["available_at"] = pd.to_datetime(bars["available_at"])
    valid = (bars["trading_status"].astype(str).str.startswith("TRADE")
             & pd.to_numeric(bars["close"], errors="coerce").gt(0))
    bars["valid_trade"] = valid
    recent = bars.loc[bars["date"] >= inputs["universe_start"]]
    liquidity = bars.loc[bars["date"] >= inputs["liquidity_start"]]
    history_counts = recent.groupby("instrument_id")["valid_trade"].sum().to_dict()
    recent_counts = liquidity.groupby("instrument_id")["valid_trade"].sum().to_dict()
    amounts = (liquidity.loc[liquidity["valid_trade"]]
               .groupby("instrument_id")["amount"].mean().to_dict())
    last = bars.loc[bars["date"] == previous].set_index("instrument_id").to_dict("index")
    members = []
    decision_at = cutoff.replace(tzinfo=None)
    for instrument in inputs["instruments"]:
        identifier = int(instrument["instrument_id"])
        bar = last.get(identifier)
        observation = {
            "history_bars": int(history_counts.get(identifier, 0)),
            "recent_bars": int(recent_counts.get(identifier, 0)),
            "avg_amount_cny": amounts.get(identifier),
            "last_bar_date": previous if bar else None,
            "last_close": bar["close"] if bar else None,
            "last_status": bar["trading_status"] if bar else None,
            "source_available_at": bar["available_at"].to_pydatetime() if bar else None,
        }
        members.append(decide_member(instrument, observation, session_date=decision_day,
                                     decision_at=decision_at, previous_session=previous,
                                     policy=policy))
    eligible = [row for row in members if row["decision_state"] == "CANDIDATE"]
    frame = pd.DataFrame({
        "instrument_id": [row["instrument_id"] for row in eligible],
        "provider_symbol": [row["provider_symbol"] for row in eligible],
        "source_available_at": [row["source_available_at"] for row in eligible],
    })
    if frame.empty:
        raise RuntimeError("No CN pre-open tradable candidates")
    frame["session_date"] = pd.Timestamp(decision_day)
    frame["asof_date"] = pd.Timestamp(previous)
    frame["decision_at"] = pd.Timestamp(decision_at)
    reasons = {}
    for row in members:
        for reason in row["reasons"]:
            reasons[reason] = reasons.get(reason, 0) + 1
    return frame, {"instruments": len(members), "candidates": len(eligible),
                   "exclusion_reasons": reasons}


def _known_factors_for_future(factors: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Mark events known *now*, never rewrite their stored PIT timestamps."""
    if factors.empty:
        return factors, 0
    known = factors.copy()
    date_plus_day = pd.to_datetime(known["date"]) + pd.Timedelta(days=1)
    actual = pd.to_datetime(known["available_at"])
    late = int(actual.gt(date_plus_day).sum())
    # The frozen historical feature code masks events only if known by event+1.
    # This in-memory adaptation is used solely for a future decision after receipt.
    known["available_at"] = actual.where(actual.le(date_plus_day), date_plus_day)
    return known, late


def top20_candidates(panel: pd.DataFrame, scores: np.ndarray, *, top_pct: float,
                     minimum_count: int, minimum_coverage: float) -> tuple[pd.DataFrame, dict]:
    if len(panel) != len(scores) or panel["instrument_id"].duplicated().any():
        raise ValueError("Oracle score population mismatch or duplicate instrument")
    valid = (panel["mask_price20"].eq(1) & panel["mask_benchmark"].eq(1)
             & pd.to_numeric(panel["return_5"], errors="coerce").map(math.isfinite)
             & np.isfinite(scores))
    coverage = float(valid.mean()) if len(panel) else 0.0
    if coverage < minimum_coverage or int(valid.sum()) < minimum_count:
        raise RuntimeError(f"CN Oracle eligible feature coverage insufficient: {coverage:.3f}")
    ranked = panel.loc[valid, ["instrument_id", "provider_symbol", "board_code", "return_5",
                               "max_input_available_at"]].copy()
    ranked["oracle_score"] = np.asarray(scores)[valid.to_numpy()]
    ranked = ranked.sort_values(["oracle_score", "instrument_id"],
                                ascending=[False, True], kind="stable")
    count = max(1, math.ceil(len(ranked) * top_pct))
    return ranked.head(count).copy(), {"scored": len(panel), "eligible": len(ranked),
                                       "feature_coverage": coverage, "top20": count}


def check(*, decision_day: date, contract_path: Path = DEFAULT_CONFIG,
          now: datetime | None = None, engine=None) -> dict:
    """Cheap read-only preflight; it does not score or create an export."""
    now = now or datetime.now(UTC)
    contract = load_contract(contract_path)
    raw = contract["raw"]
    window = decision_window(decision_day, now=now,
                             calendar=load_calendar(_path(raw["calendar"])))
    owned = engine is None
    engine = engine or get_market_engine("CN_A", database_alias="cn_primary")
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("CN preflight refused outside alpha_trade_cn")
    try:
        with engine.connect() as conn:
            session = conn.execute(text(
                "SELECT close_at_utc FROM market_sessions WHERE market_code='CN_A' "
                "AND session_date=:day AND session_status='open'"
            ), {"day": window["previous_day"]}).scalar()
            bars = conn.execute(text(
                "SELECT COUNT(*) FROM stock_bars_daily WHERE market_code='CN_A' "
                "AND date=:day AND available_at<=:known"
            ), {"day": window["previous_day"],
                "known": now.astimezone(UTC).replace(tzinfo=None)}).scalar()
            benchmark = conn.execute(text(
                "SELECT COUNT(*) FROM stock_bars_daily WHERE market_code='CN_A' "
                "AND date=:day AND symbol='sh.000300' AND available_at<=:known"
            ), {"day": window["previous_day"],
                "known": now.astimezone(UTC).replace(tzinfo=None)}).scalar()
    finally:
        if owned:
            engine.dispose()
    reasons = []
    if session is None or session >= now.astimezone(UTC).replace(tzinfo=None):
        reasons.append("PREVIOUS_CN_SESSION_NOT_CLOSED_OR_MISSING")
    if not bars:
        reasons.append("PREVIOUS_CN_EQUITY_BARS_MISSING")
    if not benchmark:
        reasons.append("PREVIOUS_CSI300_BAR_MISSING")
    if (_path(raw["output_root"]) / decision_day.isoformat()).exists():
        reasons.append("CANDIDATE_EXPORT_ALREADY_EXISTS")
    return {"status": "READY_TO_SCORE" if not reasons else "BLOCKED",
            "reasons": reasons, "decision_date": decision_day.isoformat(),
            "previous_session": window["previous_day"].isoformat(),
            "cutoff_utc": window["cutoff_utc"].isoformat(),
            "known_bar_rows": int(bars or 0), "benchmark_present": bool(benchmark),
            "database_modified": False, "training_performed": False}


def run(*, decision_day: date, contract_path: Path = DEFAULT_CONFIG,
        now: datetime | None = None, engine=None, output_root: Path | None = None) -> dict:
    now = now or datetime.now(UTC)
    contract = load_contract(contract_path)
    raw = contract["raw"]
    window = decision_window(decision_day, now=now,
                             calendar=load_calendar(_path(raw["calendar"])))
    if contract["trained_through"] >= decision_day:
        raise RuntimeError("Oracle model is not out-of-time for this decision")
    root = output_root or _path(raw["output_root"])
    folder = root / decision_day.isoformat()
    if folder.exists():
        raise FileExistsError(f"Prospective Oracle output already exists: {folder}")
    owned = engine is None
    engine = engine or get_market_engine("CN_A", database_alias="cn_primary")
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("Oracle CN prospective prediction refused outside alpha_trade_cn")
    try:
        profile = CNFeatureProfile.from_yaml(_path(raw["feature_profile"]))
        policy = CNUniversePolicy.from_yaml(_path(raw["universe_policy"]))
        inputs = _load_market(engine, previous=window["previous_day"], now=now,
                              profile=profile, policy=policy)
        candidates, universe = _preopen_members(
            inputs, decision_day=decision_day, previous=window["previous_day"],
            cutoff=window["cutoff_utc"], policy=policy,
        )
        known_factors, late_factors = _known_factors_for_future(inputs["factors"])
        features = compute_symbol_features(inputs["bars"], known_factors)
        benchmark = compute_symbol_features(inputs["benchmark"])
        panel = assemble_candidate_panel(candidates, features, benchmark,
                                         inputs["limits"], profile=profile)
        columns = contract["protocol"].raw["features"]
        import lightgbm as lgb
        model = lgb.Booster(model_file=str(_path(raw["model_file"])))
        if list(model.feature_name()) != columns:
            raise RuntimeError("Frozen Oracle feature order differs from model")
        scores = np.asarray(model.predict(_matrix(panel, columns)), dtype=float)
        selected, quality = top20_candidates(
            panel, scores, top_pct=float(raw["top_pct"]),
            minimum_count=int(raw["minimum_candidate_count"]),
            minimum_coverage=float(raw["minimum_feature_coverage"]),
        )
        scored_at = datetime.now(UTC)
        if scored_at >= window["cutoff_utc"]:
            raise RuntimeError("Oracle scoring finished after 09:15 Shanghai; export forbidden")
        if scored_at < now.astimezone(UTC):
            raise RuntimeError("Scoring clock moved backwards")
        provider = selected["provider_symbol"].astype(str)
        result = pd.DataFrame({
            "decision_date": decision_day.isoformat(),
            "exchange": np.where(provider.str.startswith("sh."), "SSE", "SZSE"),
            "code": provider.str.split(".", regex=False).str[-1].to_numpy(),
            "board_code": selected["board_code"].to_numpy(),
            "oracle_score": selected["oracle_score"].to_numpy(),
            "oracle_top20": True, "oracle_oos": True,
            "score_available_at_utc": scored_at.isoformat(),
            "prior_return_5d": selected["return_5"].to_numpy(),
            "prior_return_available_at_utc": pd.to_datetime(
                selected["max_input_available_at"]
            ).dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00").to_numpy(),
            "model_trained_through": contract["trained_through"].isoformat(),
        })
        if result.duplicated(["decision_date", "exchange", "code"]).any():
            raise RuntimeError("Duplicate Oracle candidate identity")
        if selected["max_input_available_at"].max() > pd.Timestamp(now.astimezone(UTC).replace(tzinfo=None)):
            raise RuntimeError("An Oracle feature arrived after the score started")
        root.mkdir(parents=True, exist_ok=True)
        temporary = root / f".{decision_day.isoformat()}-{uuid.uuid4().hex}.partial"
        temporary.mkdir()
        temporary_export = temporary / "oracle_top20.parquet"
        result.to_parquet(temporary_export, index=False)
        export = folder / "oracle_top20.parquet"
        report = {
            "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": decision_day.isoformat(),
            "previous_session": window["previous_day"].isoformat(),
            "decision_cutoff_utc": window["cutoff_utc"].isoformat(),
            "score_available_at_utc": scored_at.isoformat(),
            "model_trained_through": contract["trained_through"].isoformat(),
            "model_file_sha256": raw["model_file_sha256"],
            "model_report_sha256": raw["model_report_sha256"],
            "contract_sha256": contract["config_sha256"],
            "oracle_protocol_sha256": _sha(_path(raw["oracle_protocol"])),
            "feature_profile_sha256": _sha(_path(raw["feature_profile"])),
            "universe_policy_sha256": _sha(_path(raw["universe_policy"])),
            "calendar_sha256": _sha(_path(raw["calendar"])),
            "candidate_export_sha256": _sha(temporary_export), "candidate_export": str(export),
            "population": universe, "quality": quality,
            "late_factor_events_masked_for_future_only": late_factors,
            "database_modified": False, "training_performed": False,
            "serving_changed": False, "trading_enabled": False,
            "historical_pit_certified": False,
        }
        publishing_at = datetime.now(UTC)
        if publishing_at >= window["cutoff_utc"]:
            raise RuntimeError("Oracle export would be published after 09:15 Shanghai")
        report["export_published_at_utc"] = publishing_at.isoformat()
        (temporary / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                 encoding="utf-8")
        if folder.exists():
            raise FileExistsError(f"Prospective Oracle output already exists: {folder}")
        if datetime.now(UTC) >= window["cutoff_utc"]:
            raise RuntimeError("Oracle export missed 09:15 Shanghai before publication")
        temporary.replace(folder)
        if datetime.now(UTC) >= window["cutoff_utc"]:
            quarantine = root / f".{decision_day.isoformat()}-{uuid.uuid4().hex}.late"
            folder.replace(quarantine)
            raise RuntimeError("Oracle export crossed 09:15 Shanghai; quarantined")
        return report
    finally:
        if owned:
            engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-date", type=date.fromisoformat, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check", action="store_true", help="Read-only input preflight; no prediction")
    args = parser.parse_args()
    if args.check:
        if args.output_root is not None:
            parser.error("--check does not accept --output-root")
        print(json.dumps(check(decision_day=args.decision_date,
                               contract_path=args.config), ensure_ascii=False))
        return
    report = run(decision_day=args.decision_date, contract_path=args.config,
                 output_root=args.output_root)
    print(json.dumps({"status": report["status"], "date": report["decision_date"],
                      "candidates": report["quality"]["top20"],
                      "export": report["candidate_export"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
