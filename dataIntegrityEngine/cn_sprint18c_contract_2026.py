"""Installe ou audite les contrats CN 2026 pour le shadow 18-C uniquement."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from dataIntegrityEngine.cn_sprint12a_migrate import _statements
from service.market.cn_execution_contract import resolve_cost_profile, resolve_rule

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "database/sql/cn/migration_cn_0009_execution_contract_2026_shadow.sql"
START = date(2026, 7, 6)
END = date(2026, 12, 31)
PILOT = date(2026, 10, 8)
VERSION = "cn_a_2026_07_shadow_v1"
SPECS = (
    ("XSHG", "SH_MAIN", 100, 100),
    ("XSHE", "SZ_MAIN", 100, 100),
    ("XSHE", "CHINEXT", 100, 100),
    ("XSHG", "STAR", 1, 200),
)
RULE_SOURCES = {
    ("XSHG", "SH_MAIN"): "https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml",
    ("XSHE", "SZ_MAIN"): "https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html",
    ("XSHE", "CHINEXT"): "https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf",
    ("XSHG", "STAR"): "https://english.sse.com.cn/start/trading/mechanism/",
}
FEE_SOURCE_SSE = "https://one.sse.com.cn/onething/gptz/"
FEE_SOURCE_SZSE = "https://investor.szse.cn/marketServices/deal/payFees/index.html"


def _metadata(value: object) -> dict:
    decoded = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, dict):
        raise RuntimeError("Métadonnées de contrat CN 2026 absentes")
    return decoded


def _database_guard(conn) -> None:
    database = conn.execute(text("SELECT DATABASE() ")).scalar_one()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Contrat CN 2026 interdit sur {database!r}")
    market = conn.execute(text(
        "SELECT live_enabled FROM markets WHERE market_code='CN_A'"
    )).one_or_none()
    if market is None or bool(market[0]):
        raise RuntimeError("CN_A absent ou live_enabled : installation interdite")


def audit(conn) -> dict:
    """Contrôle l'unicité, la période, la provenance et l'opt-in recherche."""
    _database_guard(conn)
    rules = {}
    for mic, board, increment, minimum in SPECS:
        rule = resolve_rule(
            conn, exchange_mic=mic, board_code=board,
            session_date=PILOT, allow_research_rules=True,
        )
        row = conn.execute(text("""
            SELECT metadata_json FROM market_execution_rules WHERE rule_id=:id
        """), {"id": rule.rule_id}).scalar_one()
        meta = _metadata(row)
        if (
            rule.valid_from != START or rule.valid_to != END
            or rule.buy_increment != increment
            or rule.minimum_buy_shares != minimum
            or rule.minimum_sell_shares != minimum
            or rule.tick_size != Decimal("0.01")
            or rule.settlement_cycle_days != 1
            or rule.same_day_sell_allowed or rule.short_selling_allowed
            or rule.rule_version != VERSION or not rule.research_only
            or meta.get("source_type") != "OFFICIAL_RULES_RESEARCH_EXECUTION"
            or meta.get("source_ref") != RULE_SOURCES[(mic, board)]
            or meta.get("limits") != "instrument_session_only"
            or meta.get("not_broker_verified") is not True
        ):
            raise RuntimeError(f"Règle CN 2026 divergente : {mic}/{board}")
        rules[f"{mic}/{board}"] = rule.rule_id
    profile = resolve_cost_profile(
        conn, profile_key="cn_a_research", session_date=PILOT,
        allow_research_proxy=True,
    )
    row = conn.execute(text("""
        SELECT metadata_json FROM cn_execution_cost_profiles WHERE profile_id=:id
    """), {"id": profile.profile_id}).scalar_one()
    meta = _metadata(row)
    expected = {
        "commission_bps_buy": "10", "commission_bps_sell": "10",
        "commission_min_cny": "5", "transfer_fee_bps_buy": "0.1",
        "transfer_fee_bps_sell": "0.1", "stamp_duty_bps_sell": "5",
        "slippage_bps_buy": "2", "slippage_bps_sell": "2",
    }
    if (
        profile.valid_from != START or profile.valid_to != END
        or profile.source_type != "RESEARCH_PROXY"
        or any(getattr(profile, key) != Decimal(value) for key, value in expected.items())
        or meta.get("version") != "cn_a_research_2026_shadow_v1"
        or meta.get("not_verified_broker") is not True
        or meta.get("exchange_handling_in_commission_not_added_twice") is not True
        or meta.get("public_fees_ref") != FEE_SOURCE_SSE
        or meta.get("szse_fees_ref") != FEE_SOURCE_SZSE
        or meta.get("commission_assumption") != "Sprint 11-B 10bps/min5"
        or meta.get("slippage_assumption_bps_per_side") != 2
    ):
        raise RuntimeError("Profil CN 2026 de recherche divergent")
    return {
        "status": "CN_2026_SHADOW_RESEARCH_CONTRACT_READY_NOT_LIVE",
        "database": "alpha_trade_cn", "market_live_enabled": False,
        "valid_from": START.isoformat(), "valid_to": END.isoformat(),
        "pilot_date": PILOT.isoformat(), "rules": rules,
        "cost_profile": {"key": profile.profile_key, "id": profile.profile_id,
                         "source_type": profile.source_type},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Insérer les règles/coûts CN 2026 puis auditer la transaction")
    args = parser.parse_args()
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.begin() as conn:
            _database_guard(conn)
            if args.apply:
                for statement in _statements(MIGRATION.read_text(encoding="utf-8")):
                    conn.exec_driver_sql(statement)
            result = audit(conn)
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
