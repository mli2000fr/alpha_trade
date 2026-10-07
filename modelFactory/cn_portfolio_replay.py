"""CLI de recherche du replay CN_A, lecture seule de alpha_trade_cn.

Entrée : signaux après clôture dans un JSON explicite. Sortie : artefacts
reproductibles, jamais une publication de signaux ou des fills live.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from database.router import get_market_engine
from service.market import cn_execution_contract, cn_portfolio_replay
from service.market.cn_execution_contract import resolve_cost_profile, resolve_rule
from service.market.cn_portfolio_replay import (
    CNAction,
    CNBar,
    CNInstrument,
    CNIntent,
    CNPortfolioReplay,
    ReplayConfig,
)


def load_verified_action_evidence(path: Path) -> dict[int, dict[str, Any]]:
    """Accepte uniquement le dossier complet A2, hashé et sans doublon."""
    from modelFactory.cn_corporate_action_a2 import _sha_json

    report_path = path.parent / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = json.loads(path.read_text(encoding="utf-8"))
    if (not report.get("complete") or report.get("groups_cached") != report.get("groups_total")
            or report.get("event_count") != len(rows)
            or report.get("evidence_sha256") != _sha_json(rows)
            or not report.get("preflight", {}).get("all_policies_pass")):
        raise RuntimeError("Preuve A2 incomplète, modifiée ou gate non passé")
    mapped = {int(row["corporate_action_id"]): row for row in rows}
    if len(mapped) != len(rows):
        raise RuntimeError("Preuve A2 à identifiants dupliqués")
    return mapped


def convert_verified_actions(
    action_rows: list[Any], evidence: dict[int, dict[str, Any]] | None,
) -> tuple[list[CNAction], set[tuple[date, int]]]:
    """Conserve les événements non prouvés comme UNRESOLVED, sans inférer."""
    actions: list[CNAction] = []
    unresolved_dates: set[tuple[date, int]] = set()
    for row in action_rows:
        identifier = int(row["corporate_action_id"])
        instrument_id = int(row["instrument_id"])
        day = row["ex_date"]
        prefix = f"{identifier}:{row['source_payload_hash']}"
        item = evidence.get(identifier) if evidence is not None else None
        corrected_ex_date = (
            identifier == 19141 and item is not None
            and item.get("remediation_kind") == "SOURCE_EX_DATE_ONE_SESSION_EARLIER"
            and item.get("canonical_ex_date") == day.isoformat()
            and item.get("ex_date") == "2022-03-29"
            and day.isoformat() == "2022-03-30"
        )
        if item is not None and (int(item["instrument_id"]) != instrument_id
                                 or (item["ex_date"] != day.isoformat() and not corrected_ex_date)
                                 or item["source_payload_hash"] != row["source_payload_hash"]):
            raise RuntimeError(f"Preuve A2 incompatible avec la ligne canonique {identifier}")
        # B5: a vendor factor reset after the officially documented
        # 300114 -> 302132 code change did not give holders cash or shares.
        # It must neither block the raw-price replay nor create a fake right.
        if (identifier == 316 and item is not None
                and item["status"] == "EVIDENCED_NON_DISTRIBUTION"
                and item.get("remediation_kind") == "OFFICIAL_TICKER_CHANGE_SAME_HOLDINGS"
                and item.get("official_previous_symbol") == "sz.300114"
                and item.get("official_effective_date") == "2025-02-17"
                and day.isoformat() == "2025-02-18"):
            continue
        if item is None or item["status"] != "EVIDENCED_DISTRIBUTION":
            actions.append(CNAction(prefix, instrument_id, day, "UNRESOLVED"))
            unresolved_dates.add((day, instrument_id))
            continue
        cash = Decimal(item["cash_per_share_before_tax"])
        ratio = Decimal(item["share_ratio"])
        if cash < 0 or ratio < 0 or (cash == 0 and ratio == 0) or not cash.is_finite() or not ratio.is_finite():
            raise RuntimeError(f"Termes A2 invalides pour {identifier}")
        effective_day = date.fromisoformat(item["ex_date"])
        if ratio > 0:
            actions.append(CNAction(prefix + ":shares", instrument_id, effective_day, "SPLIT",
                                    share_multiplier=Decimal(1) + ratio))
        if cash > 0:
            payment = date.fromisoformat(item["payment_date"])
            if payment < effective_day:
                raise RuntimeError(f"Paiement A2 avant ex-date pour {identifier}")
            actions.append(CNAction(prefix + ":cash", instrument_id, effective_day, "CASH_DIVIDEND",
                                    cash_per_share_cny=cash, payment_date=payment))
    return actions, unresolved_dates


def _digest_rows(*groups: list[Any]) -> str:
    digest = hashlib.sha256()
    for group in groups:
        digest.update(f"[{len(group)}]".encode())
        for item in group:
            payload = asdict(item) if hasattr(item, "__dataclass_fields__") else item
            digest.update(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode())
    return digest.hexdigest()


def _query_ids(conn: Connection, sql: str, ids: list[int], **params: Any):
    statement = text(sql).bindparams(bindparam("ids", expanding=True))
    return conn.execute(statement, {"ids": ids, **params}).mappings().all()


def load_inputs(path: Path) -> tuple[dict[str, Any], list[CNIntent]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (raw.get("market_code") != "CN_A" or raw.get("signal_timing") != "after_close"
            or not isinstance(raw.get("signals"), list)):
        raise ValueError("Entrée CN_A invalide : signaux after_close requis")
    start, end = date.fromisoformat(raw["start_date"]), date.fromisoformat(raw["end_date"])
    if start > end or (end - start).days > 730:
        raise ValueError("Fenêtre CN vide ou supérieure à deux ans")
    allowed = {"intent_id", "signal_date", "instrument_id", "side",
               "budget_cny", "shares", "reason", "priority"}
    if any(not isinstance(item, dict) or set(item) - allowed for item in raw["signals"]):
        raise ValueError("Champs de signal CN non autorisés (labels futurs interdits)")
    signals = [CNIntent(
        intent_id=str(item["intent_id"]), signal_date=date.fromisoformat(item["signal_date"]),
        instrument_id=int(item["instrument_id"]), side=item["side"],
        budget_cny=Decimal(str(item["budget_cny"])) if item.get("budget_cny") is not None else None,
        shares=int(item["shares"]) if item.get("shares") is not None else None,
        reason=str(item.get("reason") or "SIGNAL"),
        priority=Decimal(str(item.get("priority", 0))),
    ) for item in raw["signals"]]
    if not signals or len(signals) > 100_000:
        raise ValueError("Le replay CN nécessite 1 à 100 000 signaux explicites")
    if any(intent.signal_date < start or intent.signal_date > end for intent in signals):
        raise ValueError("Signal hors fenêtre CN")
    return raw, signals


def load_cn_market(conn: Connection, *, start: date, end: date,
                   instrument_ids: list[int],
                   evidence: dict[int, dict[str, Any]] | None = None) -> tuple[list[date], list[CNInstrument], list[CNBar], list[CNAction]]:
    """Lit les données canoniques révisées ; pas une preuve PIT de fill."""
    if not instrument_ids or len(instrument_ids) != len(set(instrument_ids)):
        raise ValueError("IDs CN vides ou dupliqués")
    days = list(conn.execute(text(
        "SELECT session_date FROM market_sessions WHERE market_code='CN_A' "
        "AND session_status IN ('open','half_day','special') "
        "AND open_at_utc IS NOT NULL AND close_at_utc IS NOT NULL "
        "AND session_date BETWEEN :start AND :end ORDER BY session_date"
    ), {"start": start, "end": end}).scalars())
    if not days:
        raise ValueError("Aucune séance CN_A datée dans la fenêtre")
    rows = _query_ids(conn, """
        SELECT instrument_id,market_code,exchange_mic,instrument_type,currency,
               listing_date,delisting_date
        FROM instruments WHERE instrument_id IN :ids
    """, instrument_ids)
    if len(rows) != len(instrument_ids) or any(
        row["market_code"] != "CN_A" or row["instrument_type"] != "equity"
        or row["currency"] != "CNY" for row in rows
    ):
        raise ValueError("Instrument absent ou étranger à CN_A/equity/CNY")
    status_rows = _query_ids(conn, """
        SELECT instrument_id,board_code,valid_from,valid_to
        FROM instrument_status_history WHERE instrument_id IN :ids
          AND valid_from<=:end AND (valid_to IS NULL OR valid_to>=:start)
    """, instrument_ids, start=start, end=end)
    histories: dict[int, list[Any]] = defaultdict(list)
    for row in status_rows:
        histories[int(row["instrument_id"])].append(row)
    bar_rows = _query_ids(conn, """
        SELECT b.instrument_id,b.`date` session_date,b.`open`,b.`close`,b.volume,
               b.trading_status,l.policy_code,l.locked_up,l.locked_down
        FROM stock_bars_daily b
        LEFT JOIN cn_daily_price_limits l
          ON l.instrument_id=b.instrument_id AND l.session_date=b.`date`
        WHERE b.market_code='CN_A' AND b.instrument_id IN :ids
          AND b.`date` BETWEEN :start AND :end
    """, instrument_ids, start=start, end=end)
    bar_keys = {(int(item["instrument_id"]), item["session_date"]) for item in bar_rows}
    instruments = []
    for row in rows:
        identifier = int(row["instrument_id"])
        boards = {item["board_code"] for item in histories[identifier] if item["board_code"]}
        if len(boards) != 1:
            raise ValueError(f"Board historique CN manquant ou changeant : {identifier}")
        # Un trou de statut à une date active interdit une règle de board implicite.
        for day in days:
            if row["listing_date"] and day < row["listing_date"]:
                continue
            if row["delisting_date"] and day > row["delisting_date"]:
                continue
            matching = [item for item in histories[identifier] if item["valid_from"] <= day
                        and (item["valid_to"] is None or item["valid_to"] >= day)]
            # Le dernier jour de radiation peut être une séance de marché sans
            # barre ni statut pour ce titre. Sans barre, aucun fill n'est possible;
            # une position détenue aura une valorisation stale/invalide.
            if not matching and (identifier, day) not in bar_keys:
                continue
            if not matching or {item["board_code"] for item in matching} != boards:
                raise ValueError(f"Statut/board CN ambigu ou absent {identifier}/{day}")
        instruments.append(CNInstrument(
            identifier, row["exchange_mic"], boards.pop(),
            row["listing_date"], row["delisting_date"],
        ))
    action_rows = _query_ids(conn, """
        SELECT corporate_action_id,instrument_id,ex_date,action_type,
               classification_status,source_payload_hash
        FROM cn_corporate_actions WHERE instrument_id IN :ids
          AND ex_date BETWEEN :start AND :end
    """, instrument_ids, start=start, end=end)
    actions, action_keys = convert_verified_actions(action_rows, evidence)
    bars = [CNBar(
        session_date=row["session_date"], instrument_id=int(row["instrument_id"]),
        open_cny=Decimal(str(row["open"])) if row["open"] is not None else None,
        close_cny=Decimal(str(row["close"])) if row["close"] is not None else None,
        trading_status=row["trading_status"], limit_policy=row["policy_code"],
        locked_up=bool(row["locked_up"]) if row["locked_up"] is not None else None,
        locked_down=bool(row["locked_down"]) if row["locked_down"] is not None else None,
        volume_shares=Decimal(str(row["volume"])) if row["volume"] is not None else None,
        factor_event_unresolved=(row["session_date"], int(row["instrument_id"])) in action_keys,
    ) for row in bar_rows]
    return days, instruments, bars, actions


def run(*, intent_path: Path, output_dir: Path, scenario: str, cost_profile_key: str,
        initial_cash_cny: Decimal, allow_research_proxy: bool,
        pending_policy: str = "carry", max_wait_sessions: int = 3,
        max_positions: int = 8, evidence_path: Path | None = None,
        auto_exit_after_full_sessions: int | None = None) -> dict[str, Any]:
    input_sha256 = hashlib.sha256(intent_path.read_bytes()).hexdigest()
    raw, intents = load_inputs(intent_path)
    evidence = load_verified_action_evidence(evidence_path) if evidence_path else None
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE() ")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Replay CN interdit hors alpha_trade_cn")
            days, instruments, bars, actions = load_cn_market(
                conn, start=date.fromisoformat(raw["start_date"]),
                end=date.fromisoformat(raw["end_date"]),
                instrument_ids=sorted({item.instrument_id for item in intents}),
                evidence=evidence,
            )
            canonical_data_sha256 = _digest_rows(
                days, sorted(instruments, key=lambda item: item.instrument_id),
                sorted(bars, key=lambda item: (item.session_date, item.instrument_id)),
                sorted(actions, key=lambda item: item.action_id),
            )
            config = ReplayConfig(
                initial_cash_cny=initial_cash_cny, cost_profile_key=cost_profile_key,
                scenario=scenario, pending_policy=pending_policy,
                max_wait_sessions=max_wait_sessions, max_positions=max_positions,
                allow_research_rules=allow_research_proxy,
                allow_research_proxy=allow_research_proxy,
                auto_exit_after_full_sessions=auto_exit_after_full_sessions,
            )
            cost_snapshot = resolve_cost_profile(
                conn, profile_key=cost_profile_key, session_date=days[0],
                allow_research_proxy=allow_research_proxy,
            )
            rule_snapshots = [resolve_rule(
                conn, exchange_mic=item.exchange_mic, board_code=item.board_code,
                session_date=next((day for day in days if item.listing_date and day >= item.listing_date), days[-1]),
                allow_research_rules=allow_research_proxy,
            ) for item in instruments if item.listing_date is not None and item.listing_date <= days[-1]]
            contract_sha256 = _digest_rows([cost_snapshot], sorted(rule_snapshots, key=lambda item: item.rule_id))
            result = CNPortfolioReplay(conn, config).run(
                sessions=days, instruments=instruments, bars=bars, intents=intents, actions=actions,
            )
    finally:
        engine.dispose()
    if output_dir.exists():
        raise FileExistsError(f"Rapport de replay CN existant, écrasement interdit : {output_dir}")
    if hashlib.sha256(intent_path.read_bytes()).hexdigest() != input_sha256:
        raise RuntimeError("Le fichier de signaux CN a changé pendant le replay")
    output_dir.mkdir(parents=True)
    for name, rows in (("journal.jsonl", result.journal), ("daily.jsonl", result.daily)):
        (output_dir / name).write_text(
            "".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in rows),
            encoding="utf-8",
        )
    counts: dict[str, int] = defaultdict(int)
    reasons: dict[str, int] = defaultdict(int)
    for event in result.journal:
        counts[event["event"]] += 1
        if event.get("reason"):
            reasons[f"{event['event']}:{event['reason']}"] += 1
    summary = {
        "market_code": "CN_A", "database_alias": "cn_primary",
        "evidence_level": "RESEARCH_DAILY_BAR_HYPOTHETICAL_FILLS_NOT_LIVE_OR_OBSERVED",
        "data_revision": "HISTORICAL_CANONICAL_REVISED_NOT_ORIGINAL_PIT_SNAPSHOT",
        "signal_timing": "after_close_next_session_open_earliest",
        "scenario": scenario, "cost_profile_key": cost_profile_key,
        "config": {key: str(value) if isinstance(value, Decimal) else value
                   for key, value in asdict(config).items()},
        "input_sha256": input_sha256,
        "canonical_data_sha256": canonical_data_sha256,
        "contract_sha256": contract_sha256,
        "code_sha256": _digest_rows([
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            hashlib.sha256(Path(cn_portfolio_replay.__file__).read_bytes()).hexdigest(),
            hashlib.sha256(Path(cn_execution_contract.__file__).read_bytes()).hexdigest(),
        ]),
        "sessions": len(days), "instruments": len(instruments),
        "intent_count": len(intents),
        "corporate_action_rows_unresolved": sum(item.kind == "UNRESOLVED" for item in actions),
        "corporate_action_evidence_sha256": (
            hashlib.sha256(evidence_path.read_bytes()).hexdigest() if evidence_path else None
        ),
        "event_counts": dict(sorted(counts.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "economic_result_valid": result.economic_result_valid,
        "marked_return_proxy": (
            str(Decimal(result.daily[-1]["equity_mark_cny"]) / initial_cash_cny - 1)
            if result.economic_result_valid else None
        ),
        "marked_return_is_executable_liquidation": False,
        "last_mark": result.daily[-1],
        "final_cash_cny": str(result.cash_cny),
        "open_lots": {str(key): [{"shares": lot.shares, "acquired_session": lot.acquired_session.isoformat()}
                                 for lot in lots] for key, lots in result.lots.items()},
        "unresolved": result.unresolved,
        "pending_intents": result.pending_intents,
    }
    (output_dir / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 12-B : replay de recherche CN_A, pas de serving")
    parser.add_argument("--intent-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scenario", choices=["permissive", "base", "conservative"], default="base")
    parser.add_argument("--cost-profile-key", default="cn_a_research")
    parser.add_argument("--initial-cash-cny", type=Decimal, required=True)
    parser.add_argument("--pending-policy", choices=["carry", "cancel_day"], default="carry")
    parser.add_argument("--max-wait-sessions", type=int, default=3)
    parser.add_argument("--max-positions", type=int, default=8)
    parser.add_argument("--allow-research-proxy", action="store_true")
    parser.add_argument("--corporate-action-evidence", type=Path)
    parser.add_argument("--auto-exit-after-full-sessions", type=int)
    args = parser.parse_args()
    report = run(
        intent_path=args.intent_file, output_dir=args.output_dir,
        scenario=args.scenario, cost_profile_key=args.cost_profile_key,
        initial_cash_cny=args.initial_cash_cny,
        allow_research_proxy=args.allow_research_proxy,
        pending_policy=args.pending_policy, max_wait_sessions=args.max_wait_sessions,
        max_positions=args.max_positions,
        evidence_path=args.corporate_action_evidence,
        auto_exit_after_full_sessions=args.auto_exit_after_full_sessions,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
