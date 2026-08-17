"""Inventaire des donnees Phase 6 (earnings PIT) et Phase 4 (fondamentaux relatifs).

Usage : python scripts/check_phase6_data.py [--universe config/ticket_mid_cap_400.txt]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def read_universe(path: str) -> list[str]:
    text_data = Path(path).read_text(encoding="utf-8", errors="ignore")
    syms = [s.strip().upper() for s in text_data.replace("\n", ",").split(",") if s.strip()]
    return list(dict.fromkeys(syms))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    args = ap.parse_args()

    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    syms = read_universe(args.universe)
    in_clause = ",".join(f"'{s}'" for s in syms)

    print(f"UNIVERS : {len(syms)} symboles\n")

    with engine.connect() as c:
        # 1. stock_earnings_calendar
        q = f"""
            SELECT COUNT(*) AS n_rows,
                   COUNT(DISTINCT symbol) AS n_symbols,
                   MIN(earnings_date) AS dmin,
                   MAX(earnings_date) AS dmax,
                   SUM(eps_estimate IS NOT NULL AND eps_actual IS NOT NULL) AS n_surprise_completes
            FROM stock_earnings_calendar
            WHERE symbol IN ({in_clause})
        """
        print("== stock_earnings_calendar (univers) ==")
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        # distribution par annee
        q = f"""
            SELECT YEAR(earnings_date) AS annee, COUNT(*) AS n_events,
                   COUNT(DISTINCT symbol) AS n_symbols,
                   SUM(eps_estimate IS NOT NULL AND eps_actual IS NOT NULL) AS n_eps_comp
            FROM stock_earnings_calendar
            WHERE symbol IN ({in_clause}) AND earnings_date >= '2016-01-01'
            GROUP BY YEAR(earnings_date) ORDER BY annee
        """
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        # nb d'evenements par symbole
        q = f"""
            SELECT COUNT(*) AS n_events, COUNT(DISTINCT symbol) AS n_symbols
            FROM (
                SELECT symbol FROM stock_earnings_calendar
                WHERE symbol IN ({in_clause}) AND earnings_date >= '2016-01-01'
                GROUP BY symbol HAVING COUNT(*) >= 2
            ) t
        """
        print("symboles avec >= 2 evenements depuis 2016 :")
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        # 2. stock_fundamentals_daily
        q = f"""
            SELECT COUNT(DISTINCT symbol) AS n_symbols,
                   MIN(trade_date) AS dmin, MAX(trade_date) AS dmax,
                   COUNT(*) AS n_rows
            FROM stock_fundamentals_daily WHERE symbol IN ({in_clause})
        """
        print("== stock_fundamentals_daily (univers) ==")
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        q = f"""
            SELECT COUNT(*) AS n_non_null,
                   ROUND(100 * SUM(pe_ratio IS NOT NULL) / COUNT(*), 1) AS pe_pct,
                   ROUND(100 * SUM(roe IS NOT NULL) / COUNT(*), 1) AS roe_pct,
                   ROUND(100 * SUM(eps_growth_yoy IS NOT NULL) / COUNT(*), 1) AS epsg_pct,
                   ROUND(100 * SUM(revenue_growth_yoy IS NOT NULL) / COUNT(*), 1) AS revg_pct,
                   ROUND(100 * SUM(eps_estimate_current IS NOT NULL) / COUNT(*), 1) AS epsest_pct
            FROM stock_fundamentals_daily WHERE symbol IN ({in_clause})
        """
        print("taux de non-null par colonne :")
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        # revisions possibles ? eps_estimate_current change-t-il dans le temps ?
        q = f"""
            SELECT symbol, COUNT(DISTINCT eps_estimate_current) AS n_distinct_est
            FROM stock_fundamentals_daily
            WHERE symbol IN ({in_clause}) AND eps_estimate_current IS NOT NULL
            GROUP BY symbol ORDER BY n_distinct_est DESC LIMIT 10
        """
        print("distincts eps_estimate_current par symbole (top 10) — une valeur = pas d'historique de revisions :")
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        # 3. tables news (sentiment) — couverture
        q = f"""
            SELECT COUNT(*) AS n_rows, COUNT(DISTINCT symbol) AS n_symbols,
                   MIN(trade_date) AS dmin, MAX(trade_date) AS dmax
            FROM ticker_daily_sentiment_features WHERE symbol IN ({in_clause})
        """
        print("== ticker_daily_sentiment_features (univers) ==")
        print(pd.read_sql(q, c).to_string(index=False), "\n")

        # 4. schemas utiles pour les baselines signaux
        for t in ("ticker_daily_sentiment_features", "stock_scores_history"):
            print(f"== schema {t} ==")
            cols = pd.read_sql(f"SHOW COLUMNS FROM {t}", c)
            print(cols[["Field", "Type"]].to_string(index=False), "\n")

        # 5. couverture stock_scores_history
        q = f"""
            SELECT COUNT(*) AS n_rows, COUNT(DISTINCT symbol) AS n_symbols,
                   MIN(snapshot_date) AS dmin, MAX(snapshot_date) AS dmax,
                   ROUND(100 * SUM(short_score IS NOT NULL) / COUNT(*), 1) AS short_pct,
                   ROUND(100 * SUM(normalized_total_score IS NOT NULL) / COUNT(*), 1) AS norm_pct
            FROM stock_scores_history WHERE symbol IN ({in_clause})
        """
        print("== stock_scores_history (univers) ==")
        print(pd.read_sql(q, c).to_string(index=False), "\n")


if __name__ == "__main__":
    main()
