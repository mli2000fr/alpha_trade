"""Sprint 18-C : pilote Oracle CN → shadow, strictement lecture seule.

La sélection est figée avant le cutoff Oracle ; une tentative ne lit la
barre que post-clôture. Aucune règle/coût 2025 n'est prolongée en 2026.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import bindparam, text

from database.router import get_market_engine
from service.market.cn_execution_contract import (
    CNExecutionContractError, CostBreakdown, resolve_cost_profile, resolve_rule,
)
from service.market.cn_oracle_daily_15d9 import verify_published
from service.market.cn_shadow_execution_18b import (
    ShadowAttempt, ShadowBar, ShadowIntent, ShadowPlan, SHANGHAI,
    assess_shadow_attempt, mark_shadow_attempt, plan_shadow_intent,
    write_shadow_audit,
)

DEFAULT_ORACLE_ROOT = Path("artifacts/research/cn_oracle_prospective_15d8")
DEFAULT_OUTPUT_ROOT = Path("artifacts/research/cn_shadow_18c")
PROFILE_KEY = "cn_a_research"


def _iso(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Horodatage shadow sans fuseau horaire")
    return parsed


def _utc_from_db(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _date_from_db(value: date | str | None) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) else value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _engine(engine):
    owned = engine is None
    engine = engine or get_market_engine("CN_A", database_alias="cn_primary")
    if engine.url.database != "alpha_trade_cn":
        if owned:
            engine.dispose()
        raise RuntimeError("Shadow CN refusé hors alpha_trade_cn")
    return engine, owned


def _write_new(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        stream.write("\n")


def _symbol(exchange: str, code: str) -> tuple[str, str]:
    if exchange not in {"SSE", "SZSE"} or not code.isdigit() or len(code) != 6:
        raise ValueError("Identité Oracle CN invalide")
    return ("sh." if exchange == "SSE" else "sz.") + code, (
        "XSHG" if exchange == "SSE" else "XSHE")


def _validate_export(folder: Path, decision: date, now: datetime) -> tuple[dict, pd.DataFrame]:
    report = verify_published(folder, decision=decision)
    published = _iso(report["export_published_at_utc"])
    cutoff = _iso(report["decision_cutoff_utc"])
    if not published <= now < cutoff:
        raise RuntimeError("Plan shadow impossible hors fenêtre prospective pré-cutoff")
    frame = pd.read_parquet(folder / "oracle_top20.parquet")
    required = {"decision_date", "exchange", "code", "board_code", "oracle_top20",
                "oracle_oos", "score_available_at_utc", "model_trained_through"}
    if (not required.issubset(frame.columns) or frame.empty
            or frame.duplicated(["decision_date", "exchange", "code"]).any()
            or not frame["oracle_top20"].eq(True).all()
            or not frame["oracle_oos"].eq(True).all()
            or not frame["decision_date"].eq(decision.isoformat()).all()
            or int(report["quality"]["top20"]) != len(frame)):
        raise RuntimeError("Population Oracle prospective invalide ou altérée")
    if any(_iso(value) > published for value in frame["score_available_at_utc"]):
        raise RuntimeError("Score Oracle postérieur à la publication")
    if any(date.fromisoformat(str(value)) >= decision for value in frame["model_trained_through"]):
        raise RuntimeError("Modèle Oracle non OOS")
    return report, frame


def _mapping(conn, symbols: list[str], decision: date, cutoff: datetime) -> dict[str, dict]:
    statement = text("""
        SELECT ips.provider_symbol,ips.created_at,i.instrument_id,i.market_code,
               i.exchange_mic,i.instrument_type,i.currency,i.listing_date,i.delisting_date
        FROM instrument_provider_symbols ips JOIN instruments i
          ON i.instrument_id=ips.instrument_id
        WHERE ips.provider='baostock' AND ips.provider_symbol IN :symbols
          AND ips.valid_from<=:day AND (ips.valid_to IS NULL OR ips.valid_to>=:day)
    """).bindparams(bindparam("symbols", expanding=True))
    rows = conn.execute(statement, {"symbols": symbols, "day": decision}).mappings().all()
    result: dict[str, dict] = {}
    for row in rows:
        symbol = str(row["provider_symbol"])
        if (symbol in result or row["market_code"] != "CN_A"
                or row["instrument_type"] != "equity" or row["currency"] != "CNY"
                or _utc_from_db(row["created_at"]) > cutoff):
            raise RuntimeError(f"Mapping CN ambigu, étranger ou tardif : {symbol}")
        result[symbol] = dict(row)
    if set(result) != set(symbols):
        raise RuntimeError(f"Mapping CN manquant : {sorted(set(symbols) - set(result))}")
    return result


def prepare_plan(
    *, decision: date, output_path: Path, oracle_root: Path = DEFAULT_ORACLE_ROOT,
    now: datetime | None = None, sample_size: int = 12,
    selection_seed: str = "CN_SHADOW_18C_V1", budget_cny: Decimal = Decimal("10000"),
    engine=None,
) -> dict:
    """Fige un échantillon LONG diagnostic sans sélectionner sur le rendement."""
    now = _iso(now or datetime.now(UTC))
    if output_path.exists() or not 1 <= sample_size <= 100 or not selection_seed:
        raise ValueError("Plan déjà présent ou protocole d'échantillonnage invalide")
    if not budget_cny.is_finite() or budget_cny <= 0:
        raise ValueError("Budget notionnel shadow invalide")
    folder = oracle_root / decision.isoformat()
    report, frame = _validate_export(folder, decision, now)
    frame = frame.copy()
    frame["provider_symbol"] = [
        _symbol(str(exchange), str(code))[0]
        for exchange, code in zip(frame["exchange"], frame["code"], strict=True)
    ]
    frame["selection_key"] = frame["provider_symbol"].map(
        lambda symbol: hashlib.sha256(
            f"{selection_seed}|{decision.isoformat()}|{symbol}".encode("ascii")
        ).hexdigest()
    )
    chosen = frame.sort_values(["selection_key", "provider_symbol"]).head(sample_size)
    if len(chosen) != sample_size:
        raise RuntimeError("Échantillon Oracle insuffisant")
    published = _iso(report["export_published_at_utc"])
    source = f"CN_D8:{report['candidate_export_sha256']}"
    db, owned = _engine(engine)
    try:
        with db.connect() as conn:
            mapped = _mapping(conn, chosen["provider_symbol"].tolist(), decision, published)
    finally:
        if owned:
            db.dispose()
    plans = []
    for item in chosen.to_dict("records"):
        symbol = item["provider_symbol"]
        row = mapped[symbol]
        _, mic = _symbol(str(item["exchange"]), str(item["code"]))
        if row["exchange_mic"] != mic:
            raise RuntimeError(f"MIC Oracle/mapping incohérent : {symbol}")
        delisting = _date_from_db(row["delisting_date"])
        # Une radiation connue aujourd'hui mais postérieure au signal ne doit
        # pas être injectée rétroactivement dans la décision pré-cutoff.
        known_delisting = delisting if delisting is not None and delisting < published.astimezone(SHANGHAI).date() else None
        intent = ShadowIntent(
            intent_id=f"cn18c-{decision.isoformat()}-{row['instrument_id']}",
            instrument_id=int(row["instrument_id"]), symbol=symbol,
            market_code="CN_A", exchange_mic=mic, board_code=str(item["board_code"]),
            signal_at=published, execution_session=decision, side="BUY",
            budget_cny=budget_cny, source_ref=source,
        )
        plans.append(asdict(plan_shadow_intent(
            intent, listing_date=_date_from_db(row["listing_date"]),
            delisting_date=known_delisting,
        )))
    payload = {
        "schema_version": "cn_shadow_18c_plan_v1", "status": "FROZEN_RESEARCH_ONLY",
        "market_code": "CN_A", "decision_date": decision.isoformat(),
        "created_at_utc": now.astimezone(UTC).isoformat(),
        "decision_cutoff_utc": report["decision_cutoff_utc"],
        "oracle_report_path": str(folder / "report.json"),
        "oracle_export_sha256": report["candidate_export_sha256"],
        "selection_seed": selection_seed, "sample_size": sample_size,
        "selection_method": "SHA256_WITHIN_ORACLE_TOP20_NOT_SCORE_RANKED",
        "purpose": "NON_DIRECTIONAL_LONG_DIAGNOSTIC_NOT_A_TRADING_POLICY",
        "budget_per_intent_cny": str(budget_cny), "plans": plans,
        "database_modified": False, "broker_called": False,
    }
    _write_new(output_path, payload)
    return payload


def contract_readiness(*, decision: date, boards: list[tuple[str, str]],
                       profile_key: str = PROFILE_KEY, engine=None) -> dict:
    """Préflight agrégé en lecture seule ; aucune règle 2026 inventée."""
    db, owned = _engine(engine)
    missing = []
    try:
        with db.connect() as conn:
            for mic, board in sorted(set(boards)):
                count = conn.execute(text("""
                    SELECT COUNT(*) FROM market_execution_rules
                    WHERE market_code='CN_A' AND exchange_mic=:mic AND board_code=:board
                      AND valid_from<=:day AND (valid_to IS NULL OR valid_to>=:day)
                """), {"mic": mic, "board": board, "day": decision}).scalar_one()
                if count != 1:
                    missing.append(f"RULE_{mic}_{board}_COUNT_{count}")
            costs = conn.execute(text("""
                SELECT COUNT(*) FROM cn_execution_cost_profiles
                WHERE market_code='CN_A' AND profile_key=:key
                  AND valid_from<=:day AND (valid_to IS NULL OR valid_to>=:day)
            """), {"key": profile_key, "day": decision}).scalar_one()
            if costs != 1:
                missing.append(f"COST_{profile_key}_COUNT_{costs}")
    finally:
        if owned:
            db.dispose()
    return {"status": "READY_FOR_RESEARCH_ATTEMPT" if not missing else "BLOCKED_CONTRACT",
            "decision_date": decision.isoformat(), "market_code": "CN_A",
            "profile_key": profile_key, "blocking_reasons": missing,
            "database_modified": False, "broker_called": False}


def _decode_plan(raw: dict) -> ShadowPlan:
    item = raw["intent"]
    intent = ShadowIntent(
        intent_id=item["intent_id"], instrument_id=int(item["instrument_id"]),
        symbol=item["symbol"], market_code=item["market_code"],
        exchange_mic=item["exchange_mic"], board_code=item["board_code"],
        signal_at=_iso(item["signal_at"]),
        execution_session=date.fromisoformat(item["execution_session"]),
        side=item["side"],
        budget_cny=Decimal(item["budget_cny"]) if item["budget_cny"] is not None else None,
        requested_shares=item["requested_shares"], source_ref=item["source_ref"],
    )
    return ShadowPlan(intent, raw["state"], raw["reason"], raw["decision_fingerprint"])


def load_frozen_plan(path: Path, *, now: datetime | None = None) -> dict:
    """Refuse une décision écrite après cutoff ou un export modifié."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "cn_shadow_18c_plan_v1" or raw.get("market_code") != "CN_A":
        raise RuntimeError("Plan 18-C non conforme")
    decision = date.fromisoformat(raw["decision_date"])
    created, cutoff = _iso(raw["created_at_utc"]), _iso(raw["decision_cutoff_utc"])
    if not created < cutoff or (now is not None and _iso(now) < created):
        raise RuntimeError("Plan shadow rétroactif ou horloge incohérente")
    report_path = Path(raw["oracle_report_path"])
    report = verify_published(report_path.parent, decision=decision)
    if (report["candidate_export_sha256"] != raw["oracle_export_sha256"]
            or report["decision_cutoff_utc"] != raw["decision_cutoff_utc"]
            or created < _iso(report["export_published_at_utc"])):
        raise RuntimeError("Provenance Oracle du plan altérée")
    plans = [_decode_plan(item) for item in raw["plans"]]
    if len(plans) != int(raw["sample_size"]) or len({p.intent.intent_id for p in plans}) != len(plans):
        raise RuntimeError("Échantillon du plan altéré")
    frame = pd.read_parquet(report_path.parent / "oracle_top20.parquet")
    expected = sorted(
        (_symbol(str(item["exchange"]), str(item["code"]))[0] for item in frame.to_dict("records")),
        key=lambda symbol: (
            hashlib.sha256(
                f"{raw['selection_seed']}|{decision.isoformat()}|{symbol}".encode("ascii")
            ).hexdigest(), symbol,
        ),
    )[:len(plans)]
    if [p.intent.symbol for p in plans] != expected:
        raise RuntimeError("Échantillon déterministe du plan altéré")
    # Vérification des empreintes à partir des dataclasses reconstituées.
    from service.market.cn_shadow_execution_18b import _fingerprint
    if any(p.decision_fingerprint != _fingerprint(p.intent)
           or p.intent.execution_session != decision for p in plans):
        raise RuntimeError("Intention shadow du plan altérée")
    return {"raw": raw, "plans": plans, "decision": decision}


def _session_close(conn, day: date) -> datetime:
    rows = conn.execute(text("""
        SELECT close_at_utc FROM market_sessions
        WHERE market_code='CN_A' AND session_date=:day
          AND session_status IN ('open','half_day','special')
    """), {"day": day}).all()
    if len(rows) != 1 or rows[0][0] is None:
        raise RuntimeError(f"Séance CN sans clôture canonique : {day}")
    return _utc_from_db(rows[0][0])


def _observed_bar(conn, *, instrument_id: int, day: date,
                  now: datetime) -> ShadowBar | None:
    known = now.astimezone(UTC).replace(tzinfo=None)
    bars = conn.execute(text("""
        SELECT market_code,`date`,instrument_id,`open`,`close`,volume,
               trading_status,data_adjustment,data_source,source_payload_hash,
               available_at FROM stock_bars_daily
        WHERE instrument_id=:id AND market_code='CN_A' AND `date`=:day
          AND available_at<=:known
    """), {"id": instrument_id, "day": day, "known": known}).mappings().all()
    if not bars:
        return None
    if len(bars) != 1 or bars[0]["data_adjustment"] != "raw":
        raise RuntimeError("Barre CN ambiguë ou ajustée dans le shadow")
    bar = bars[0]
    limits = conn.execute(text("""
        SELECT policy_code,locked_up,locked_down,source,available_at
        FROM cn_daily_price_limits
        WHERE instrument_id=:id AND session_date=:day AND available_at<=:known
    """), {"id": instrument_id, "day": day, "known": known}).mappings().all()
    if len(limits) > 1:
        raise RuntimeError("Limites CN ambiguës")
    limit = limits[0] if limits else None
    unresolved = conn.execute(text("""
        SELECT COUNT(*) FROM cn_corporate_actions
        WHERE instrument_id=:id AND ex_date=:day
          AND classification_status='UNCLASSIFIED_FACTOR_EVENT'
          AND available_at<=:known
    """), {"id": instrument_id, "day": day, "known": known}).scalar_one()
    observed = max(_utc_from_db(bar["available_at"]),
                   _utc_from_db(limit["available_at"]) if limit else _utc_from_db(bar["available_at"]))
    return ShadowBar(
        session_date=day, instrument_id=instrument_id, market_code="CN_A",
        observed_at=observed, open_cny=Decimal(str(bar["open"])),
        close_cny=Decimal(str(bar["close"])),
        volume_shares=Decimal(str(bar["volume"])) if bar["volume"] is not None else None,
        trading_status=bar["trading_status"],
        limit_policy=limit["policy_code"] if limit else None,
        locked_up=bool(limit["locked_up"]) if limit and limit["locked_up"] is not None else None,
        locked_down=bool(limit["locked_down"]) if limit and limit["locked_down"] is not None else None,
        source_ref=f"{bar['data_source']}:{bar['source_payload_hash']}"
                   + (f"|limits:{limit['source']}" if limit else "|limits:missing"),
        factor_event_unresolved=bool(unresolved),
    )


def _decode_bar(raw: dict | None) -> ShadowBar | None:
    if raw is None:
        return None
    return ShadowBar(
        session_date=date.fromisoformat(raw["session_date"]),
        instrument_id=int(raw["instrument_id"]), market_code=raw["market_code"],
        observed_at=_iso(raw["observed_at"]),
        open_cny=Decimal(raw["open_cny"]) if raw["open_cny"] is not None else None,
        close_cny=Decimal(raw["close_cny"]) if raw["close_cny"] is not None else None,
        volume_shares=Decimal(raw["volume_shares"]) if raw["volume_shares"] is not None else None,
        trading_status=raw["trading_status"], limit_policy=raw["limit_policy"],
        locked_up=raw["locked_up"], locked_down=raw["locked_down"],
        source_ref=raw["source_ref"],
        factor_event_unresolved=bool(raw["factor_event_unresolved"]),
    )


def _decode_attempt(raw: dict) -> ShadowAttempt:
    item = raw["attempt"]
    breakdown = item["hypothetical_cost_breakdown"]
    return ShadowAttempt(
        intent_id=item["intent_id"], instrument_id=int(item["instrument_id"]),
        market_code=item["market_code"], side=item["side"],
        session_date=date.fromisoformat(item["session_date"]),
        observed_at=_iso(item["observed_at"]) if item["observed_at"] else None,
        state=item["state"], reason=item["reason"], shares=int(item["shares"]),
        hypothetical_price_cny=Decimal(item["hypothetical_price_cny"])
        if item["hypothetical_price_cny"] is not None else None,
        hypothetical_notional_cny=Decimal(item["hypothetical_notional_cny"])
        if item["hypothetical_notional_cny"] is not None else None,
        hypothetical_cost_cny=Decimal(item["hypothetical_cost_cny"])
        if item["hypothetical_cost_cny"] is not None else None,
        hypothetical_cost_breakdown=CostBreakdown(**{
            key: Decimal(str(value)) for key, value in breakdown.items()
        }) if breakdown else None,
        decision_fingerprint=item["decision_fingerprint"],
        observation_fingerprint=item["observation_fingerprint"],
        observed_bar=_decode_bar(item["observed_bar"]),
        rule_id=item["rule_id"], rule_version=item["rule_version"],
        cost_profile_id=item["cost_profile_id"],
        cost_profile_key=item["cost_profile_key"],
        cost_source_type=item["cost_source_type"],
        scenario=item["scenario"], evidence=item["evidence"],
    )


def assess_frozen_session(
    *, plan_path: Path, output_root: Path = DEFAULT_OUTPUT_ROOT,
    now: datetime | None = None, scenario: str = "base",
    profile_key: str = PROFILE_KEY, allow_research_rules: bool = False,
    allow_research_proxy: bool = False, engine=None,
) -> dict:
    """Tentatives post-clôture ; refuse tous les fills si contrats incomplets."""
    now = _iso(now or datetime.now(UTC))
    loaded = load_frozen_plan(plan_path, now=now)
    day, plans = loaded["decision"], loaded["plans"]
    boards = [(p.intent.exchange_mic, p.intent.board_code) for p in plans]
    readiness = contract_readiness(decision=day, boards=boards,
                                   profile_key=profile_key, engine=engine)
    if readiness["status"] != "READY_FOR_RESEARCH_ATTEMPT":
        return {"status": "BLOCKED_CONTRACT", "decision_date": day.isoformat(),
                "blocking_reasons": readiness["blocking_reasons"],
                "database_modified": False, "broker_called": False}
    db, owned = _engine(engine)
    try:
        with db.connect() as conn:
            if now < _session_close(conn, day):
                raise RuntimeError("Tentative shadow interdite avant la clôture CN")
            prepared = []
            for plan in plans:
                intent = plan.intent
                rule = resolve_rule(
                    conn, exchange_mic=intent.exchange_mic,
                    board_code=intent.board_code, session_date=day,
                    allow_research_rules=allow_research_rules,
                )
                profile = resolve_cost_profile(
                    conn, profile_key=profile_key, session_date=day,
                    allow_research_proxy=allow_research_proxy,
                )
                bar = _observed_bar(conn, instrument_id=intent.instrument_id,
                                    day=day, now=now)
                attempt = assess_shadow_attempt(
                    plan, bar=bar, rule=rule, profile=profile,
                    cash_available_cny=intent.budget_cny or Decimal(0),
                    scenario=scenario, allow_research_rules=allow_research_rules,
                    allow_research_proxy=allow_research_proxy,
                )
                prepared.append((plan, attempt))
    finally:
        if owned:
            db.dispose()
    folder = output_root / "attempts" / day.isoformat()
    counts = Counter()
    for plan, attempt in prepared:
        path = folder / f"{attempt.intent_id}.json"
        if path.exists():
            prior = _decode_attempt(json.loads(path.read_text(encoding="utf-8")))
            if prior != attempt:
                raise RuntimeError(f"Tentative shadow déjà publiée avec un autre état : {path}")
        else:
            write_shadow_audit(path, plan=plan, attempt=attempt)
        counts[attempt.state] += 1
    report = {"status": "COMPLETED_SHADOW_ONLY", "decision_date": day.isoformat(),
              "attempts": len(prepared), "states": dict(sorted(counts.items())),
              "plan_path": str(plan_path), "scenario": scenario,
              "database_modified": False, "broker_called": False}
    report_path = output_root / "reports" / f"attempt-{day.isoformat()}.json"
    if report_path.exists():
        if json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise RuntimeError("Rapport shadow déjà publié avec un autre état")
    else:
        _write_new(report_path, report)
    return report


def mark_frozen_session(
    *, plan_path: Path, mark_session: date,
    output_root: Path = DEFAULT_OUTPUT_ROOT, now: datetime | None = None,
    engine=None,
) -> dict:
    """Compare le close ultérieur ; aucun rendement réalisé n'est inféré."""
    now = _iso(now or datetime.now(UTC))
    loaded = load_frozen_plan(plan_path, now=now)
    day, plans = loaded["decision"], loaded["plans"]
    if mark_session <= day:
        raise ValueError("La marque doit suivre la séance de tentative")
    folder = output_root / "attempts" / day.isoformat()
    attempts = []
    for plan in plans:
        path = folder / f"{plan.intent.intent_id}.json"
        proof = json.loads(path.read_text(encoding="utf-8"))
        if proof.get("schema_version") != "cn_shadow_18b_v1":
            raise RuntimeError("Preuve de tentative absente ou invalide")
        attempt = _decode_attempt(proof)
        if attempt.decision_fingerprint != plan.decision_fingerprint:
            raise RuntimeError("Intention de tentative différente du plan figé")
        attempts.append((plan, attempt))
    db, owned = _engine(engine)
    try:
        with db.connect() as conn:
            if now < _session_close(conn, mark_session):
                raise RuntimeError("Marque shadow interdite avant clôture")
            marked = []
            for plan, attempt in attempts:
                if attempt.state != "HYPOTHETICAL_FILL":
                    continue
                bar = _observed_bar(conn, instrument_id=attempt.instrument_id,
                                    day=mark_session, now=now)
                if bar is None:
                    marked.append((plan, attempt, None, "MARK_BAR_MISSING"))
                    continue
                try:
                    mark = mark_shadow_attempt(attempt, next_bar=bar)
                except CNExecutionContractError as exc:
                    marked.append((plan, attempt, None, str(exc)))
                else:
                    marked.append((plan, attempt, mark, None))
    finally:
        if owned:
            db.dispose()
    counts = Counter()
    for plan, attempt, mark, reason in marked:
        if mark is None:
            counts["UNVERIFIABLE_MARK"] += 1
            continue
        path = output_root / "marks" / day.isoformat() / mark_session.isoformat() / f"{attempt.intent_id}.json"
        if path.exists():
            raise FileExistsError(f"Marque shadow déjà publiée : {path}")
        write_shadow_audit(path, plan=plan, attempt=attempt, mark=mark)
        counts["MARKED_PRICE_ONLY"] += 1
    report = {"status": "COMPLETED_SHADOW_MARK_ONLY", "decision_date": day.isoformat(),
              "mark_session": mark_session.isoformat(), "states": dict(sorted(counts.items())),
              "hypothetical_fills": len(marked),
              "unverifiable": [attempt.intent_id for _, attempt, mark, _ in marked if mark is None],
              "database_modified": False, "broker_called": False}
    report_path = output_root / "reports" / f"mark-{day.isoformat()}-{mark_session.isoformat()}.json"
    _write_new(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("plan", "preflight", "attempt", "mark"))
    parser.add_argument("--decision-date", required=True, type=date.fromisoformat)
    parser.add_argument("--oracle-root", type=Path, default=DEFAULT_ORACLE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--seed", default="CN_SHADOW_18C_V1")
    parser.add_argument("--budget-cny", type=Decimal, default=Decimal("10000"))
    parser.add_argument("--scenario", choices=("conservative", "base", "permissive"), default="base")
    parser.add_argument("--mark-session", type=date.fromisoformat)
    parser.add_argument("--allow-research-rules", action="store_true")
    parser.add_argument("--allow-research-proxy", action="store_true")
    args = parser.parse_args()
    if args.phase == "plan":
        path = args.output_root / "plans" / f"{args.decision_date.isoformat()}.json"
        result = prepare_plan(
            decision=args.decision_date, output_path=path,
            oracle_root=args.oracle_root, sample_size=args.sample_size,
            selection_seed=args.seed, budget_cny=args.budget_cny,
        )
        print(json.dumps({"status": result["status"], "plan": str(path),
                          "sample_size": result["sample_size"]}, ensure_ascii=False))
    elif args.phase == "preflight":
        path = args.output_root / "plans" / f"{args.decision_date.isoformat()}.json"
        loaded = load_frozen_plan(path)
        boards = [(p.intent.exchange_mic, p.intent.board_code) for p in loaded["plans"]]
        print(json.dumps(contract_readiness(decision=args.decision_date, boards=boards),
                         ensure_ascii=False))
    elif args.phase == "attempt":
        path = args.output_root / "plans" / f"{args.decision_date.isoformat()}.json"
        result = assess_frozen_session(
            plan_path=path, output_root=args.output_root, scenario=args.scenario,
            allow_research_rules=args.allow_research_rules,
            allow_research_proxy=args.allow_research_proxy,
        )
        print(json.dumps(result, ensure_ascii=False))
    else:
        if args.mark_session is None:
            parser.error("--phase mark exige --mark-session")
        path = args.output_root / "plans" / f"{args.decision_date.isoformat()}.json"
        print(json.dumps(mark_frozen_session(
            plan_path=path, mark_session=args.mark_session,
            output_root=args.output_root,
        ), ensure_ascii=False))


if __name__ == "__main__":
    main()
