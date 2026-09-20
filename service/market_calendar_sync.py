"""Charge un calendrier validé dans la table canonique ``market_sessions``."""

from __future__ import annotations

import argparse
from datetime import date

from common.config_loader import resolve_market_context
from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from database.repositories.market_sessions import upsert_market_sessions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-code", required=True, choices=("US_EQ", "CN_A", "CN_BJ"))
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    context = resolve_market_context(args.market_code)
    calendar = get_market_calendar(context, allow_us_weekday_fallback=False)
    sessions = calendar.sessions(args.start_date, args.end_date)
    if args.dry_run:
        print(f"{context.market_code.value}: {len(sessions)} séances validées (dry-run)")
        return
    count = upsert_market_sessions(get_sqlalchemy_engine(), sessions)
    print(f"{context.market_code.value}: {count} séances persistées")


if __name__ == "__main__":
    main()
