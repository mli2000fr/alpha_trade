"""Sprint S28.4 / A10 — Benchmark async DB vs sync sur les 3 loaders chauds.

Compare le temps mur de :
  - ``fetch_market_data_async`` vs équivalent sync,
  - ``fetch_scores_async`` vs équivalent sync,
  - ``fetch_open_orders_async`` vs équivalent sync,

sur une base sqlite éphémère (tests reproductibles en CI). Pour le bench
prod (asyncpg / Postgres), passer ``--dsn postgresql+asyncpg://...`` et
fournir la même DSN sync via ``--sync-dsn``.

Usage::

    python scripts/bench_async_db.py --rows 5000 --runs 5
    python scripts/bench_async_db.py --rows 50000 --runs 3 \\
        --dsn postgresql+asyncpg://user:pwd@host/db \\
        --sync-dsn postgresql+psycopg2://user:pwd@host/db

Sortie : ``doc/async_db_benchmark.md`` (tableau comparatif + Δ %).
La cible institutionnelle est **≥ 30 %** de gain sur 3 loaders.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "doc" / "async_db_benchmark.md"
DEFAULT_SYNC_DSN = "sqlite:///:memory:"
DEFAULT_ASYNC_DSN = "sqlite+aiosqlite:///:memory:"


def _seed_sync(engine, rows: int) -> None:
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS bars_daily ("
            "symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS screener_scores ("
            "run_id TEXT, symbol TEXT, score REAL, rank INTEGER)"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS execution_broker_orders ("
            "broker_order_id TEXT, intent_id TEXT, symbol TEXT, "
            "status TEXT, qty REAL, account_id TEXT)"
        ))
        d0 = date(2024, 1, 1)
        for i in range(rows):
            sym = f"SYM{i % 50:03d}"
            conn.execute(text(
                "INSERT INTO bars_daily VALUES (:s,:d,:o,:h,:l,:c,:v)"
            ), {"s": sym, "d": (d0 + timedelta(days=i % 365)).isoformat(),
                 "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 10_000})
            if i % 5 == 0:
                conn.execute(text(
                    "INSERT INTO screener_scores VALUES (:r,:s,:sc,:rk)"
                ), {"r": "run_bench", "s": sym, "sc": 0.5 + (i % 10) / 100, "rk": i})
            if i % 7 == 0:
                conn.execute(text(
                    "INSERT INTO execution_broker_orders VALUES (:bo,:it,:sy,:st,:q,:a)"
                ), {"bo": f"o{i}", "it": f"i{i}", "sy": sym,
                     "st": "PENDING", "q": 10.0, "a": "acct_bench"})


def _bench(label: str, fn: Callable[[], object], runs: int) -> dict:
    samples: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return {
        "label": label,
        "runs": runs,
        "median_s": statistics.median(samples),
        "mean_s": statistics.mean(samples),
        "min_s": min(samples),
        "max_s": max(samples),
    }


def run_benchmark(rows: int, runs: int, sync_dsn: str, async_dsn: str) -> dict:
    from sqlalchemy import create_engine, text

    sync_engine = create_engine(sync_dsn, future=True)
    _seed_sync(sync_engine, rows)

    # --- Sync baseline ---------------------------------------------------
    def sync_market():
        with sync_engine.connect() as c:
            c.execute(text(
                "SELECT symbol, date, open, high, low, close, volume "
                "FROM bars_daily ORDER BY symbol, date"
            )).fetchall()

    def sync_scores():
        with sync_engine.connect() as c:
            c.execute(text(
                "SELECT symbol, score, rank FROM screener_scores "
                "WHERE run_id = :r ORDER BY rank"
            ), {"r": "run_bench"}).fetchall()

    def sync_orders():
        with sync_engine.connect() as c:
            c.execute(text(
                "SELECT broker_order_id, intent_id, symbol, status, qty "
                "FROM execution_broker_orders WHERE account_id = :a "
                "AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED','FAILED')"
            ), {"a": "acct_bench"}).fetchall()

    # --- Async (opt-in only if drivers available) ------------------------
    os.environ.setdefault("ALPHA_TRADE_ASYNC_DB", "1")
    os.environ.setdefault("ALPHA_TRADE_ASYNC_DSN", async_dsn)

    from database import async_engine as ae

    async def _async_loop():
        engine = ae.make_async_engine(async_dsn)
        if engine is None:
            return None
        from sqlalchemy import text as atxt

        # Re-seed sur l'engine async (db indépendante en sqlite memory)
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: _seed_sync(sync_conn.engine, rows))

        async def amarket():
            async with engine.connect() as conn:
                res = await conn.execute(atxt(
                    "SELECT symbol, date, open, high, low, close, volume "
                    "FROM bars_daily ORDER BY symbol, date"
                ))
                res.fetchall()

        async def ascores():
            async with engine.connect() as conn:
                res = await conn.execute(atxt(
                    "SELECT symbol, score, rank FROM screener_scores "
                    "WHERE run_id = :r ORDER BY rank"
                ), {"r": "run_bench"})
                res.fetchall()

        async def aorders():
            async with engine.connect() as conn:
                res = await conn.execute(atxt(
                    "SELECT broker_order_id, intent_id, symbol, status, qty "
                    "FROM execution_broker_orders WHERE account_id = :a "
                    "AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED','FAILED')"
                ), {"a": "acct_bench"})
                res.fetchall()

        async_results = {}
        for label, fn in (("market", amarket), ("scores", ascores), ("orders", aorders)):
            samples = []
            for _ in range(runs):
                t0 = time.perf_counter()
                await fn()
                samples.append(time.perf_counter() - t0)
            async_results[label] = {
                "runs": runs,
                "median_s": statistics.median(samples),
                "mean_s": statistics.mean(samples),
                "min_s": min(samples),
                "max_s": max(samples),
            }
        await engine.dispose()
        return async_results

    sync_results = {
        "market": _bench("sync.market", sync_market, runs),
        "scores": _bench("sync.scores", sync_scores, runs),
        "orders": _bench("sync.orders", sync_orders, runs),
    }
    async_results = asyncio.run(_async_loop())

    return {
        "rows": rows,
        "runs_per_loader": runs,
        "sync_dsn": sync_dsn,
        "async_dsn": async_dsn,
        "sync": sync_results,
        "async": async_results,
        "async_available": async_results is not None,
    }


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Async DB benchmark — Sprint S28.4 / A10\n")
    lines.append(f"- rows seeded : **{report['rows']}**")
    lines.append(f"- runs per loader : **{report['runs_per_loader']}**")
    lines.append(f"- sync DSN : `{report['sync_dsn']}`")
    lines.append(f"- async DSN : `{report['async_dsn']}`\n")
    lines.append("## Résultats (médiane, secondes)\n")
    lines.append("| Loader | Sync | Async | Δ % | Cible |")
    lines.append("|---|---:|---:|---:|---:|")
    if not report["async_available"]:
        lines.append("| _async indisponible_ | — | — | — | _drivers absents : `pip install aiosqlite asyncpg 'sqlalchemy[asyncio]'`_ |")
    else:
        for k in ("market", "scores", "orders"):
            s = report["sync"][k]["median_s"]
            a = report["async"][k]["median_s"]
            delta = ((s - a) / s) * 100 if s > 0 else 0.0
            target = "≥ 30 %"
            lines.append(f"| {k} | {s:.4f} | {a:.4f} | {delta:+.1f} % | {target} |")
    lines.append("")
    lines.append("> Méthodologie : sqlite in-memory (CI), même schéma seedé sur les 2 engines.")
    lines.append("> Pour reproduire en prod (asyncpg/Postgres) : passer `--dsn` et `--sync-dsn`.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5_000)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--sync-dsn", default=DEFAULT_SYNC_DSN)
    parser.add_argument("--dsn", dest="async_dsn", default=DEFAULT_ASYNC_DSN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    report = run_benchmark(args.rows, args.runs, args.sync_dsn, args.async_dsn)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(report), encoding="utf-8")
    print(f"[bench] report written: {args.out}")
    if report["async_available"]:
        for k in ("market", "scores", "orders"):
            s = report["sync"][k]["median_s"]
            a = report["async"][k]["median_s"]
            print(f"  · {k}: sync={s:.4f}s async={a:.4f}s  Δ={((s-a)/s)*100 if s>0 else 0:+.1f}%")
    else:
        print("  · async drivers manquants — fallback sync (cf. doc/async_db_benchmark.md)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

