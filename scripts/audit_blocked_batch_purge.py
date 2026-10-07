"""Read-only inventory before any purge of blocked collectors. No SQL writes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from database.router import get_market_engine

TABLES = {
    "US_EQ": ["analyst_snapshot_collection_run", "stock_analyst_estimate_history",
              "stock_analyst_eps_trend_history", "stock_analyst_eps_revision_history",
              "stock_analyst_target_history", "stock_analyst_recommendation_history",
              "stock_short_volume_daily", "macro_vintage_observations",
              "pit_collection_runs", "pit_raw_payloads"],
    "CN_A": ["cn_staging_rows", "cn_raw_payloads", "market_sessions",
             "stock_bars_daily", "instrument_adjustment_factors"],
    "FR_EQ": [],
}


def main():
    load_dotenv(ROOT / ".env")
    for market, tables in TABLES.items():
        alias = {"US_EQ": "us_primary", "CN_A": "cn_primary", "FR_EQ": "fr_primary"}[market]
        engine = get_market_engine(market, database_alias=alias)
        inspector = inspect(engine)
        with engine.connect() as conn:
            print(json.dumps({"market": market, "database": conn.execute(text("SELECT DATABASE()")).scalar()}))
            for table in tables:
                if not inspector.has_table(table):
                    print(json.dumps({"table": table, "absent": True}))
                    continue
                quote = engine.dialect.identifier_preparer.quote
                identifier = quote(table)
                columns = [column["name"] for column in inspector.get_columns(table)]
                result = {"table": table, "rows": conn.execute(text(f"SELECT COUNT(*) FROM {identifier}")).scalar(),
                          "columns": columns}
                for column in ("provider", "source", "batch_name"):
                    if column in columns:
                        qcol = quote(column)
                        result[column + "_counts"] = [dict(row) for row in conn.execute(text(
                            f"SELECT {qcol} AS value, COUNT(*) AS rows_count FROM {identifier} GROUP BY {qcol}"
                        )).mappings()]
                print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
