"""Installe/audite le contrat CN Sprint 12-A dans alpha_trade_cn seulement."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_execution_contract import resolve_cost_profile, resolve_rule

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "database" / "sql" / "cn" / "migration_cn_0008_execution_contract.sql"


def _statements(source: str) -> list[str]:
    # Le fichier 0008 ne contient ni routine ni littéral avec point-virgule.
    return [part.strip() for part in re.split(r";\s*(?:\r?\n|$)", source) if part.strip()]


def audit(conn) -> dict[str, object]:
    database = conn.execute(text("SELECT DATABASE()")).scalar_one()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN interdite sur {database!r}")
    market = conn.execute(text(
        "SELECT enabled,live_enabled FROM markets WHERE market_code='CN_A'"
    )).one_or_none()
    if market is None or bool(market[1]):
        raise RuntimeError("Marché CN_A absent ou live déjà actif")
    rules = {}
    expected_rules = (
        ("XSHG", "SH_MAIN", 100, 100, date(2018, 1, 1)),
        ("XSHE", "SZ_MAIN", 100, 100, date(2018, 1, 1)),
        ("XSHE", "CHINEXT", 100, 100, date(2018, 1, 1)),
        ("XSHG", "STAR", 1, 200, date(2019, 7, 22)),
    )
    for mic, board, increment, minimum, start in expected_rules:
        rule = resolve_rule(
            conn, exchange_mic=mic, board_code=board,
            session_date=date(2024, 6, 3), allow_research_rules=True,
        )
        if (rule.valid_from != start or rule.valid_to != date(2025, 12, 31)
                or rule.buy_increment != increment
                or rule.minimum_buy_shares != minimum
                or rule.minimum_sell_shares != minimum
                or not rule.research_only):
            raise RuntimeError(f"Règle CN historique divergente : {board}")
        rules[board] = {
            "rule_id": rule.rule_id, "valid_from": str(rule.valid_from),
            "valid_to": str(rule.valid_to), "buy_increment": rule.buy_increment,
            "minimum_buy_shares": rule.minimum_buy_shares,
            "minimum_sell_shares": rule.minimum_sell_shares,
            "t1": not rule.same_day_sell_allowed,
        }
    profiles = {}
    for name, bps in (("cn_a_research", 10), ("cn_a_research_stress", 25)):
        profile = resolve_cost_profile(
            conn, profile_key=name, session_date=date(2024, 6, 3),
            allow_research_proxy=True,
        )
        if (profile.source_type != "RESEARCH_PROXY"
                or profile.valid_from != date(2018, 1, 1)
                or profile.valid_to != date(2025, 12, 31)
                or profile.commission_bps_buy != bps
                or profile.commission_bps_sell != bps
                or profile.commission_min_cny != 5
                or any(value != 0 for value in (
                    profile.transfer_fee_bps_buy, profile.transfer_fee_bps_sell,
                    profile.stamp_duty_bps_sell, profile.slippage_bps_buy,
                    profile.slippage_bps_sell,
                ))):
            raise RuntimeError(f"Profil de coûts CN historique divergent : {name}")
        profiles[name] = {
            "profile_id": profile.profile_id, "source_type": profile.source_type,
            "valid_from": str(profile.valid_from), "valid_to": str(profile.valid_to),
        }
    return {
        "database": database, "market_live_enabled": bool(market[1]),
        "rules": rules, "cost_profiles": profiles,
        "status": "CN_2018_2025_RESEARCH_RULES_READY_NOT_LIVE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Créer/amorcer les deux tables CN")
    args = parser.parse_args()
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.begin() as conn:
            database = conn.execute(text("SELECT DATABASE()")).scalar_one()
            if database != "alpha_trade_cn":
                raise RuntimeError(f"Migration CN interdite sur {database!r}")
            if args.apply:
                for statement in _statements(MIGRATION.read_text(encoding="utf-8")):
                    conn.exec_driver_sql(statement)
            result = audit(conn)
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
