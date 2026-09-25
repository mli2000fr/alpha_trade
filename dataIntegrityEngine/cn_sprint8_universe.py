"""CLI Sprint 8 : univers CN_A quotidien PIT, sans accès aux tables US."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_universe_pit import CNUniversePolicy, build_snapshot, candidate_symbols

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "universe_cn.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "universe"


def main() -> None:
    parser = argparse.ArgumentParser(description="Publier l'univers quotidien CN_A point-in-time")
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-sessions", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(message)s")
    if args.end_date < args.start_date or (args.max_sessions is not None and args.max_sessions < 1):
        parser.error("Plage de dates ou max-sessions invalide")
    policy = CNUniversePolicy.from_yaml(args.config)
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    with engine.connect() as conn:
        dates = list(conn.execute(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' AND session_status='open' "
            "AND session_date BETWEEN :start AND :end ORDER BY session_date"
        ), {"start": args.start_date, "end": args.end_date}).scalars())
    if args.max_sessions is not None:
        dates = dates[:args.max_sessions]
    if not dates:
        raise RuntimeError("Aucune séance CN_A ouverte dans la période demandée")
    for session_date in dates:
        summary = build_snapshot(engine, session_date=session_date, policy=policy, persist=not args.dry_run)
        if not args.dry_run:
            directory = args.output_dir / summary["universe_run_id"]
            directory.mkdir(parents=True, exist_ok=True)
            symbols = candidate_symbols(engine, summary["universe_run_id"])
            (directory / "universe.txt").write_text(",".join(symbols) + "\n", encoding="utf-8")
            (directory / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info("CN universe %s: candidates=%s/%s audits=%s run=%s", session_date,
                     summary["candidates"], summary["instruments"], summary["audit_counts"],
                     summary["universe_run_id"])
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
