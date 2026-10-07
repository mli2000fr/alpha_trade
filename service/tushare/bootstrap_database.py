from __future__ import annotations

import argparse
import json
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from database.router import build_database_url, get_market_engine, resolve_database_route

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "cn_ingestion_runs",
    "cn_raw_payloads",
    "cn_staging_rows",
    "cn_staging_quality_metrics",
    "markets",
    "instruments",
    "instrument_provider_symbols",
    "instrument_status_history",
    "market_sessions",
    "stock_bars_daily",
    "instrument_adjustment_factors",
    "cn_canonicalization_runs",
    "cn_daily_price_limits",
    "cn_corporate_actions",
    "cn_canonical_coverage_metrics",
}
EXPECTED_REVISION = "0005_canonical_full_coverage"
CANONICAL_DIAGNOSTIC_TABLES = {
    "instruments",
    "stock_bars_daily",
    "model_predictions",
    "global_oracle_labels",
    "oracle_extreme_predictions",
}


def create_database() -> None:
    route = resolve_database_route("cn_primary", "CN_A")
    server_url = build_database_url("cn_primary", "CN_A", database_override="mysql")
    engine = create_engine(server_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE DATABASE IF NOT EXISTS alpha_trade_cn "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        if route.database != "alpha_trade_cn":
            raise RuntimeError(f"Route CN inattendue après création : {route.database}")
    finally:
        engine.dispose()


def upgrade_database() -> None:
    cfg = Config(str(ROOT / "alembic_cn.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic_cn"))
    command.upgrade(cfg, "head")


def audit_database() -> dict[str, object]:
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            canonical_rows = 0
            for table in sorted(CANONICAL_DIAGNOSTIC_TABLES & tables):
                canonical_rows += int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
        return {
            "database": "alpha_trade_cn",
            "alembic_version": version,
            "expected_tables": sorted(EXPECTED_TABLES),
            "missing_tables": sorted(EXPECTED_TABLES - tables),
            "canonical_tables_present": sorted(CANONICAL_DIAGNOSTIC_TABLES & tables),
            "canonical_rows": canonical_rows,
            "status": "PASS" if tables >= EXPECTED_TABLES and version == EXPECTED_REVISION else "FAIL",
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap et audit de la base Chine")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    if not any((args.create, args.upgrade, args.audit)):
        parser.error("Choisir --create, --upgrade et/ou --audit")
    if args.create:
        create_database()
    if args.upgrade:
        upgrade_database()
    if args.audit:
        print(json.dumps(audit_database(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
