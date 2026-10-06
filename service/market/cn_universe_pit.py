"""Publication reproductible de l'univers CN_A avant séance (Sprint 8)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Engine, text

from service.market.cn_tradability_contract import assess_execution_data, assess_pretrade


@dataclass(frozen=True)
class CNUniversePolicy:
    history_lookback_sessions: int = 60
    min_history_bars: int = 40
    liquidity_lookback_sessions: int = 20
    min_liquidity_bars: int = 15
    min_close_cny: Decimal = Decimal("1")
    min_avg_amount_cny: Decimal = Decimal("5000000")
    require_previous_session_bar: bool = True

    @classmethod
    def from_yaml(cls, path: Path) -> CNUniversePolicy:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if raw.get("market_code") != "CN_A" or raw.get("database_alias") != "cn_primary":
            raise ValueError("La politique Sprint 8 doit cibler exclusivement CN_A/cn_primary")
        policy = cls(**{
            key: Decimal(str(value)) if key in {"min_close_cny", "min_avg_amount_cny"} else value
            for key, value in raw.items() if key not in {"market_code", "database_alias"}
        })
        if not (0 < policy.min_history_bars <= policy.history_lookback_sessions):
            raise ValueError("Historique CN incohérent")
        if not (0 < policy.min_liquidity_bars <= policy.liquidity_lookback_sessions <= policy.history_lookback_sessions):
            raise ValueError("Fenêtre de liquidité CN incohérente")
        if policy.min_close_cny < 0 or policy.min_avg_amount_cny < 0:
            raise ValueError("Seuils CN négatifs")
        return policy


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def decide_member(
    instrument: dict[str, Any], observation: dict[str, Any] | None, *,
    session_date: date, decision_at: datetime, previous_session: date | None, policy: CNUniversePolicy,
) -> dict[str, Any]:
    """Décision pure : aucune lecture de la barre de la séance à décider."""
    obs = observation or {}
    history = int(obs.get("history_bars") or 0)
    recent = int(obs.get("recent_bars") or 0)
    last_date = obs.get("last_bar_date")
    close = obs.get("last_close")
    amount = obs.get("avg_amount_cny")
    base = assess_pretrade(
        session_date=session_date, decision_at=decision_at,
        listing_date=instrument.get("listing_date"), delisting_date=instrument.get("delisting_date"),
        trading_status=obs.get("last_status"), status_available_at=obs.get("source_available_at"),
    )
    reasons: list[str] = []
    if base.state == "EXCLUDED":
        reasons.append(base.reason)
    if instrument.get("exchange_mic") not in {"XSHG", "XSHE"} or instrument.get("instrument_type") != "equity":
        reasons.append("NOT_CN_A_EQUITY")
    if history < policy.min_history_bars:
        reasons.append("INSUFFICIENT_HISTORY")
    if recent < policy.min_liquidity_bars:
        reasons.append("INSUFFICIENT_RECENT_BARS")
    if policy.require_previous_session_bar and (previous_session is None or last_date != previous_session):
        reasons.append("NO_PREVIOUS_SESSION_BAR")
    if close is None or Decimal(str(close)) < policy.min_close_cny:
        reasons.append("PRICE_BELOW_MINIMUM_OR_MISSING")
    if amount is None or Decimal(str(amount)) < policy.min_avg_amount_cny:
        reasons.append("LIQUIDITY_BELOW_MINIMUM_OR_MISSING")
    return {
        "instrument_id": int(instrument["instrument_id"]),
        "provider_symbol": str(instrument["provider_symbol"]),
        "decision_state": "EXCLUDED" if reasons else "CANDIDATE",
        "primary_reason": reasons[0] if reasons else "PRETRADE_PIT_CHECKS_PASSED",
        "reasons": reasons,
        "history_bars": history, "recent_bars": recent,
        "last_bar_date": last_date, "last_close": close,
        "avg_amount_cny": amount, "source_available_at": obs.get("source_available_at"),
    }


def _session_context(conn: Any, session_date: date, policy: CNUniversePolicy) -> tuple[datetime, date | None, date, date, datetime]:
    session = conn.execute(text(
        "SELECT open_at_utc,close_at_utc FROM market_sessions "
        "WHERE market_code='CN_A' AND session_date=:day AND session_status='open'"
    ), {"day": session_date}).mappings().first()
    if not session or not session["open_at_utc"] or not session["close_at_utc"]:
        raise ValueError(f"Séance CN_A ouverte sans horaires : {session_date}")
    previous = conn.execute(text(
        "SELECT session_date FROM market_sessions WHERE market_code='CN_A' AND session_status='open' "
        "AND session_date<:day ORDER BY session_date DESC LIMIT :count"
    ), {"day": session_date, "count": policy.history_lookback_sessions}).scalars().all()
    # Le début de l'historique est publié aussi : les seuils écartent naturellement
    # les titres sans assez de barres, sans inventer de séances antérieures.
    history_start = previous[-1] if previous else session_date
    liquidity_start = previous[min(len(previous), policy.liquidity_lookback_sessions) - 1] if previous else session_date
    return (
        session["open_at_utc"], previous[0] if previous else None, history_start,
        liquidity_start, session["close_at_utc"],
    )


def build_snapshot(engine: Engine, *, session_date: date, policy: CNUniversePolicy, persist: bool = True) -> dict[str, Any]:
    """Construit une séance, puis persiste chaque snapshot atomiquement et sans doublon."""
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError(f"Publication CN refusée sur {engine.url.database!r}")
    with engine.connect() as conn:
        decision_at, previous, history_start, liquidity_start, close_at = _session_context(conn, session_date, policy)
        if close_at > datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("Audit de séance refusé avant sa clôture")
        instruments = [dict(row) for row in conn.execute(text(
            "SELECT i.instrument_id,i.instrument_type,i.exchange_mic,i.listing_date,i.delisting_date,"
            "ips.provider_symbol FROM instruments i JOIN instrument_provider_symbols ips "
            "ON ips.instrument_id=i.instrument_id AND ips.provider='baostock' AND ips.is_primary=1 "
            "WHERE i.market_code='CN_A' AND i.instrument_type='equity' ORDER BY i.instrument_id"
        )).mappings()]
        if len({item["instrument_id"] for item in instruments}) != len(instruments):
            raise RuntimeError("Plusieurs mappings BaoStock primaires par instrument CN")
        observations = {int(row["instrument_id"]): dict(row) for row in conn.execute(text(
            "SELECT b.instrument_id,"
            "SUM(CASE WHEN b.trading_status LIKE 'TRADE%' AND b.close>0 THEN 1 ELSE 0 END) history_bars,"
            "SUM(CASE WHEN b.date>=:liquidity_start AND b.trading_status LIKE 'TRADE%' AND b.close>0 THEN 1 ELSE 0 END) recent_bars,"
            "AVG(CASE WHEN b.date>=:liquidity_start AND b.trading_status LIKE 'TRADE%' THEN b.amount END) avg_amount_cny,"
            "MAX(b.date) last_bar_date,"
            "MAX(CASE WHEN b.date=:previous THEN b.close END) last_close,"
            "MAX(CASE WHEN b.date=:previous THEN b.trading_status END) last_status,"
            "MAX(CASE WHEN b.date=:previous THEN b.available_at END) source_available_at "
            "FROM stock_bars_daily b WHERE b.market_code='CN_A' AND b.date BETWEEN :history_start AND :previous "
            "AND b.available_at<=:decision_at GROUP BY b.instrument_id"
        ), {"history_start": history_start, "liquidity_start": liquidity_start,
            "previous": previous, "decision_at": decision_at}).mappings()}
        current = {int(row["instrument_id"]): dict(row) for row in conn.execute(text(
            "SELECT b.instrument_id,b.trading_status,b.available_at bar_available_at,"
            "l.policy_code,l.available_at limit_available_at,l.locked_up,l.locked_down "
            "FROM stock_bars_daily b LEFT JOIN cn_daily_price_limits l "
            "ON l.instrument_id=b.instrument_id AND l.session_date=b.date "
            "WHERE b.market_code='CN_A' AND b.date=:day AND b.available_at<=:close_at"
        ), {"day": session_date, "close_at": close_at}).mappings()}
    members = [decide_member(item, observations.get(int(item["instrument_id"])), session_date=session_date,
                             decision_at=decision_at, previous_session=previous, policy=policy) for item in instruments]
    policy_fingerprint = _fingerprint(asdict(policy))
    fingerprint = _fingerprint({"market": "CN_A", "date": session_date, "decision_at": decision_at,
                                "policy": policy_fingerprint, "members": members})
    run_id = f"cn8-{session_date:%Y%m%d}-{fingerprint[:16]}"
    audits = []
    for member in members:
        if member["decision_state"] != "CANDIDATE":
            continue
        bar = current.get(member["instrument_id"])
        assessment = assess_execution_data(
            bar_present=bar is not None, trading_status=bar["trading_status"] if bar else None,
            limit_policy=bar["policy_code"] if bar else None,
            locked_up=bar["locked_up"] if bar else None,
            locked_down=bar["locked_down"] if bar else None,
        )
        audits.append({"run": run_id, "id": member["instrument_id"], "state": assessment.state,
                       "reason": assessment.reason, "bar_available": bar["bar_available_at"] if bar else None,
                       "limit_available": bar["limit_available_at"] if bar else None,
                       "audited": datetime.now(UTC).replace(tzinfo=None)})
    summary = {"universe_run_id": run_id, "session_date": session_date.isoformat(),
               "decision_at": decision_at.isoformat(), "policy_fingerprint": policy_fingerprint,
               "universe_fingerprint": fingerprint, "instruments": len(members),
               "candidates": sum(row["decision_state"] == "CANDIDATE" for row in members),
               "audited": len(audits), "audit_counts": {
                   state: sum(row["state"] == state for row in audits)
                   for state in ("DATA_CHECKS_PASSED", "EXCLUDED", "UNVERIFIABLE")},
               "reason_counts": {reason: sum(reason in row["reasons"] for row in members)
                                 for reason in sorted({reason for row in members for reason in row["reasons"]})}}
    if persist:
        _persist_snapshot(engine, summary, members, audits)
    return summary


def _persist_snapshot(engine: Engine, summary: dict[str, Any], members: list[dict[str, Any]], audits: list[dict[str, Any]]) -> None:
    run_id = summary["universe_run_id"]
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO cn_universe_runs(universe_run_id,market_code,session_date,decision_at,"
            "policy_fingerprint,universe_fingerprint,status,instrument_count,candidate_count,audited_count,details_json) "
            "VALUES (:run,'CN_A',:day,:decision,:policy,:fingerprint,'COMPLETED',:instruments,:candidates,:audited,:details) "
            "ON DUPLICATE KEY UPDATE audited_count=VALUES(audited_count),details_json=VALUES(details_json)"
        ), {"run": run_id, "day": summary["session_date"], "decision": summary["decision_at"],
            "policy": summary["policy_fingerprint"], "fingerprint": summary["universe_fingerprint"],
            "instruments": summary["instruments"], "candidates": summary["candidates"],
            "audited": summary["audited"], "details": json.dumps(summary, sort_keys=True)})
        if members:
            conn.execute(text(
                "INSERT INTO cn_universe_decisions(universe_run_id,instrument_id,provider_symbol,decision_state,"
                "primary_reason,reasons_json,history_bars,recent_bars,last_bar_date,last_close,avg_amount_cny,source_available_at) "
                "VALUES (:run,:id,:symbol,:state,:reason,:reasons,:history,:recent,:last_date,:close,:amount,:available) "
                "ON DUPLICATE KEY UPDATE universe_run_id=VALUES(universe_run_id)"
            ), [{"run": run_id, "id": row["instrument_id"], "symbol": row["provider_symbol"],
                 "state": row["decision_state"], "reason": row["primary_reason"],
                 "reasons": json.dumps(row["reasons"]), "history": row["history_bars"],
                 "recent": row["recent_bars"], "last_date": row["last_bar_date"],
                 "close": row["last_close"], "amount": row["avg_amount_cny"],
                 "available": row["source_available_at"]} for row in members])
        if audits:
            conn.execute(text(
                "INSERT INTO cn_universe_execution_audit(universe_run_id,instrument_id,audit_state,audit_reason,"
                "bar_available_at,limit_available_at,audited_at) "
                "VALUES (:run,:id,:state,:reason,:bar_available,:limit_available,:audited) "
                "ON DUPLICATE KEY UPDATE audit_state=VALUES(audit_state),audit_reason=VALUES(audit_reason),"
                "bar_available_at=VALUES(bar_available_at),limit_available_at=VALUES(limit_available_at),"
                "audited_at=VALUES(audited_at)"
            ), audits)


def candidate_symbols(engine: Engine, run_id: str) -> list[str]:
    with engine.connect() as conn:
        return list(conn.execute(text(
            "SELECT provider_symbol FROM cn_universe_decisions WHERE universe_run_id=:run "
            "AND decision_state='CANDIDATE' ORDER BY provider_symbol"
        ), {"run": run_id}).scalars())
