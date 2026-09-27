"""Suivi séparé d'une vente H20 suspendue après la fin de 2025H1.

Aucun nouveau signal après le 30/06. Ce résultat n'est pas un rendement
semestriel et n'entre pas dans le classement des politiques Sprint 13-B.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_economic_preflight import DEFAULT_CONFIG, SAFE_COLUMNS, load_protocol, select_policies
from modelFactory.cn_economic_replay_13b import _source, eligible_signal_dates, make_intents
from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_portfolio_replay import load_cn_market, load_verified_action_evidence
from service.market.cn_portfolio_replay import CNPortfolioReplay, ReplayConfig

EVIDENCE = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b2" / "evidence-afd10e157ff253b7" / "evidence.json"
ORIGINAL = (ROOT / "artifacts" / "cn" / "economic" / "sprint13b"
            / "sprint13b-e1982645b67400a2"
            / "2025H1__lightgbm_long_top20__seed0__base__cn_a_research")
OUTPUT = ROOT / "artifacts" / "cn" / "economic" / "sprint13b2" / "suspended-followthrough-2025h1"
HELD_ID = 5188
SEMESTER_END = date(2025, 6, 30)
FOLLOW_END = date(2025, 10, 13)


def run(*, evidence_path: Path = EVIDENCE, original: Path = ORIGINAL,
        output: Path = OUTPUT) -> dict:
    protocol = load_protocol(DEFAULT_CONFIG)
    evidence = load_verified_action_evidence(evidence_path)
    source_path, source = _source("2025H1")
    frame = pd.read_parquet(source_path, columns=SAFE_COLUMNS)
    pool, masks = select_policies(frame, minimum=protocol["portfolio"]["min_oracle_pool_per_session"])
    selected = pool.loc[masks["lightgbm_long_top20"]]
    required = sorted({int(value) for value in selected["instrument_id"]})
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Suivi B2 interdit hors alpha_trade_cn")
            days, instruments, bars, actions = load_cn_market(
                conn, start=date(2025, 1, 1), end=FOLLOW_END,
                instrument_ids=required, evidence=evidence,
            )
            semester_days = [day for day in days if day <= SEMESTER_END]
            intents = make_intents(
                selected, semester="2025H1", seed=0,
                valid_dates=eligible_signal_dates(semester_days),
                ticket=Decimal(protocol["portfolio"]["ticket_cny"]),
                policy="lightgbm_long_top20",
            )
            if any(intent.signal_date > SEMESTER_END for intent in intents):
                raise RuntimeError("Nouveau signal après la fenêtre 2025H1")
            config = ReplayConfig(
                initial_cash_cny=Decimal(protocol["portfolio"]["initial_cash_cny"]),
                cost_profile_key="cn_a_research", scenario="base",
                pending_policy="cancel_day", max_positions=8,
                allow_research_rules=True, allow_research_proxy=True,
                auto_exit_after_full_sessions=20,
                suppress_signals_during_open_position=True,
            )
            result = CNPortfolioReplay(conn, config).run(
                sessions=days, instruments=instruments, bars=bars,
                intents=intents, actions=actions,
            )
    finally:
        engine.dispose()
    old = pd.read_parquet(original / "daily.parquet")
    original_report = json.loads((original / "report.json").read_text(encoding="utf-8"))
    if original_report.get("open_lots", {}).get(str(HELD_ID)) != 800:
        raise RuntimeError("Position suspendue B2 différente du diagnostic initial")
    prefix = [row for row in result.daily if row["session_date"] <= SEMESTER_END.isoformat()]
    if len(prefix) != len(old) or any(
        row["session_date"] != str(old.iloc[index]["session_date"])
        or row["equity_mark_cny"] != str(old.iloc[index]["equity_mark_cny"])
        or row["cash_spendable_cny"] != str(old.iloc[index]["cash_spendable_cny"])
        for index, row in enumerate(prefix)
    ):
        raise RuntimeError("Le suivi B2 ne reproduit pas exactement le replay 2025H1")
    sells = [event for event in result.journal
             if event["event"] == "HYPOTHETICAL_FILL"
             and event.get("instrument_id") == HELD_ID
             and event.get("side") == "SELL"
             and event["session_date"] > SEMESTER_END.isoformat()]
    realized = [event for event in result.journal
                if event["event"] == "REALIZED_SALE"
                and event.get("instrument_id") == HELD_ID
                and event["session_date"] > SEMESTER_END.isoformat()]
    report = {
        "experiment": "cn_sprint13b2_suspension_followthrough",
        "not_a_semester_return": True,
        "serving_enabled": False,
        "source_predictions_sha256": source["predictions_sha256"],
        "evidence_sha256": json.loads((evidence_path.parent / "report.json").read_text(encoding="utf-8"))["evidence_sha256"],
        "h1_prefix_exactly_reproduced": True,
        "new_signals_after_2025h1": 0,
        "held_instrument_id": HELD_ID,
        "h1_end_position_shares": 800,
        "followthrough_end": FOLLOW_END.isoformat(),
        "sell_fills_after_h1": sells,
        "realized_sales_after_h1": realized,
        "end_open_lots": {str(key): sum(lot.shares for lot in lots)
                          for key, lots in result.lots.items() if lots},
        "economic_result_valid_after_followthrough": result.economic_result_valid,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Suivi post-2025H1 de la vente suspendue CN")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--original", type=Path, default=ORIGINAL)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(evidence_path=args.evidence, original=args.original, output=args.output)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
