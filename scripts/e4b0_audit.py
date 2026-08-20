"""E4-B0 — Audit quantitatif des sources directionnelles orthogonales en base (v2).

Approche GROUP BY (une requête par table, pas de IN(400) par année) :
  SELECT symbol, YEAR(date_col) FROM table GROUP BY symbol, YEAR(date_col)
puis couverture calculée en pandas vs pool Oracle O1. Aucun modèle.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

OOS = "artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet"
OUT = "artifacts/models/oracle/e4b0_inventory.md"

# (table, date_col, symbol_col, mode, fréquence, timestamp_pit, risque_leakage, catégorie)
    # mode: "simple" (date+symbol), "market" (date seule), "news" (MIN/MAX via news_raw, pas de GROUP BY massif)
CANDIDATES = [
    ("stock_earnings_calendar", "earnings_date", "symbol", "simple", "par événement", "earnings_date (date annonce/dépôt)", "faible", "A"),
    ("stock_fundamentals_daily", "trade_date", "symbol", "simple", "quotidien", "trade_date (as-of EODHD)", "faible-moyen (ratios de niveau)", "A"),
    ("ticker_daily_sentiment_features", "trade_date", "symbol", "simple", "quotidien", "trade_date + latest_event_timestamp_ny", "moyen (sentiment_net_* déjà NO-GO)", "B"),
    ("sector_daily_sentiment_features", "trade_date", "sector", "sector", "quotidien", "trade_date", "faible", "E"),
    ("stock_macro_indicators_daily", "trade_date", None, "market", "quotidien", "trade_date (indices marché)", "faible (market-level, PIT)", "E"),
    ("global_rank_history", "date", "symbol", "simple", "quotidien", "date (rang cross-sectionnel)", "moyen (dérivé B25, pas orthogonal)", "E"),
    ("corporate_actions_events", "ex_date", "symbol", "simple", "par événement", "announcement_date", "faible (N très petit)", "A"),
    # tables news sans date directe : MIN/MAX via news_raw (léger, pas de GROUP BY annuel massif)
    ("news_ticker_sentiment", "effective_trade_date", "symbol", "news", "par article", "via news_raw.published_at_utc", "faible", "B"),
    ("news_ticker_map", "effective_trade_date", "symbol", "news", "par article", "via news_raw.published_at_utc", "faible", "B"),
]


def _load_coverage(c, table: str, date_col: str, sym_col: str | None, join_sql: str | None) -> pd.DataFrame:
    """Retourne DataFrame [symbol(optional), year] distincts présents dans la table."""
    if sym_col:
        q = f"SELECT {sym_col} AS symbol, YEAR({date_col}) AS y FROM {table} t {join_sql or ''} GROUP BY {sym_col}, YEAR({date_col})"
    else:
        q = f"SELECT YEAR({date_col}) AS y FROM {table} GROUP BY YEAR({date_col})"
    return pd.read_sql(text(q), c)


def main() -> None:
    oos = pd.read_parquet(OOS)
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    pool_year = oos[["symbol", "date"]].copy()
    pool_year["year"] = pool_year["date"].dt.year
    pool_by_year = pool_year.groupby("year")["symbol"].nunique()
    pool_syms_by_year = {y: set(g["symbol"]) for y, g in pool_year.groupby("year")}
    years = sorted(pool_by_year.index)
    print(f"Oracle pool: {pool_year['symbol'].nunique()} symboles | années: {years}")

    eng = get_sqlalchemy_engine()
    lines: list[str] = [
        "# E4-B0 — Audit des sources directionnelles orthogonales disponibles",
        "",
        f"Pool Oracle (O1 OOS) : {pool_year['symbol'].nunique()} symboles. "
        f"Années : {', '.join(f'{y} (N={pool_by_year[y]})' for y in years)}.",
        "Aucun modèle construit. Inventaire read-only PIT.",
        "",
        "| table | cat | 1ère date | dernière date | N | symboles distincts | couverture pool Oracle par année | fréquence | timestamp PIT | risque leakage | verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    with eng.connect() as c:
        # mapping secteur -> symboles du pool (pour sector_daily_sentiment_features)
        meta = pd.read_sql(text("SELECT symbol, sector FROM stock_metadata"), c)
        meta["symbol"] = meta["symbol"].astype(str)
        pool_sym_set = set(pool_year["symbol"])
        sector2pool: dict[str, set] = {}
        for sym, sec in zip(meta["symbol"], meta["sector"]):
            if sym in pool_sym_set and sec:
                sector2pool.setdefault(str(sec), set()).add(sym)
        for table, date_col, sym_col, mode, freq, pit, leak, cat in CANDIDATES:
            try:
                if mode == "simple":
                    q = f"SELECT COUNT(*) n, COUNT(DISTINCT {sym_col}) ns, MIN({date_col}) mn, MAX({date_col}) mx FROM {table}"
                    n, ns, mn, mx = tuple(c.execute(text(q)).fetchone())
                    cov = _load_coverage(c, table, date_col, sym_col, None)
                    cov_map = dict(zip(zip(cov["symbol"], cov["y"]), [1] * len(cov)))
                    parts = []
                    for y in years:
                        pool_s = pool_syms_by_year[y]
                        hit = sum(1 for s in pool_s if (s, y) in cov_map)
                        parts.append(f"{y}:{hit}/{len(pool_s)}")
                    cov_str = " ".join(parts)
                elif mode == "market":
                    q = f"SELECT COUNT(*) n, MIN({date_col}) mn, MAX({date_col}) mx FROM {table}"
                    n, mn, mx = tuple(c.execute(text(q)).fetchone())
                    ns = "-"
                    cov_str = "market-level (pas de symbol)"
                elif mode == "news":
                    # stats globales sur la table elle-même (compte lignes + symboles)
                    q = f"SELECT COUNT(*) n, COUNT(DISTINCT {sym_col}) ns FROM {table}"
                    n, ns = tuple(c.execute(text(q)).fetchone())
                    # MIN/MAX via news_raw (léger)
                    q2 = (f"SELECT MIN(nr.effective_trade_date), MAX(nr.effective_trade_date) "
                          f"FROM {table} t JOIN news_raw nr ON nr.article_id=t.article_id")
                    mn, mx = tuple(c.execute(text(q2)).fetchone())
                    # couverture annuelle approximée = ticker_daily_sentiment_features (même pipeline news)
                    cov2 = _load_coverage(c, "ticker_daily_sentiment_features", "trade_date", "symbol", None)
                    cov_map = dict(zip(zip(cov2["symbol"], cov2["y"]), [1] * len(cov2)))
                    parts = []
                    for y in years:
                        pool_s = pool_syms_by_year[y]
                        hit = sum(1 for s in pool_s if (s, y) in cov_map)
                        parts.append(f"{y}:{hit}/{len(pool_s)}")
                    cov_str = " ".join(parts) + " (≈ ticker_daily_sentiment_features)"
                elif mode == "sector":
                    q = f"SELECT COUNT(*) n, COUNT(DISTINCT {sym_col}) ns, MIN({date_col}) mn, MAX({date_col}) mx FROM {table}"
                    n, ns, mn, mx = tuple(c.execute(text(q)).fetchone())
                    cov = _load_coverage(c, table, date_col, sym_col, None)
                    sectors_by_year = {y: set(cov[cov["y"] == y]["symbol"]) for y in years}
                    parts = []
                    for y in years:
                        pool_s = pool_syms_by_year[y]
                        hit = sum(1 for s in pool_s if s in {sx for sec in sectors_by_year.get(y, set()) for sx in sector2pool.get(sec, set())})
                        parts.append(f"{y}:{hit}/{len(pool_s)}")
                    cov_str = " ".join(parts) + " (symboles du pool dont le secteur a des news)"
                lines.append(
                    f"| {table} | {cat} | {mn} | {mx} | {int(n):,} | {ns} | {cov_str} | "
                    f"{freq} | {pit} | {leak} | à qualifier |"
                )
                print(f"  OK {table}: N={int(n):,} sym={ns} [{mn} -> {mx}] | {cov_str}")
            except Exception as e:  # noqa: BLE001
                lines.append(f"| {table} | {cat} | ERREUR: {str(e)[:70]} | | | | | | | | |")
                print(f"  !! {table}: {e}")

    lines.append("")
    lines.append("## C — Options : AUCUNE table en base (IV, skew, put/call, term structure absents)")
    lines.append("## D — Positioning : AUCUNE table en base (short_interest, borrow, utilization absents —")
    lines.append("    recommandation `prompt/ml/ml_recommandations_todo.md` Action 11 non implémentée)")
    lines.append("")
    lines.append("(scans artefacts : aucune donnée options/positioning/analystes/insider en cache)")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\ninventaire:", OUT)


if __name__ == "__main__":
    main()
