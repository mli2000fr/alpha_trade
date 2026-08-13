"""P1-5 (étape 2) — IC journalier de B25 par régime de marché.

Analyse de robustesse : le Spearman IC cross-sectionnel du rang global H10
(proba_long du run synthétique B25) est calculé jour par jour, puis agrégé
par régime de marché (bull/bear/range/vol via classify_market_regimes sur SPY)
et par niveau de dispersion cross-sectionnelle.

Cibles comparées :
- ic_raw        : forward return 10j brut
- ic_vs         : forward return 10j vol-scalé (vol 20j) + winsorisé 1%/99% par date
                  (miroir de l'étape 1 du pipeline de target, avant neutralisation)

Usage : python scripts/analyze_ic_by_regime_b25.py
"""
import sys
from datetime import date, timedelta

sys.path.insert(0, r"F:\projets")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from sqlalchemy import text

from backtesting.data_loader import get_required_bars_source_filter, load_predictions
from backtesting.screener_diagnostics._impl import classify_market_regimes
from modelFactory.cross_sectional import _load_sector_mapping

BID = "model-factory-20260811223551-ef2cd0"
START = date(2019, 1, 2)
END = date(2024, 6, 28)  # dernière date de prédiction du run synthétique
HORIZON = 10
OUT_DIR = r"F:\projets\artifacts\metrics"


def main() -> None:
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True, pool_pre_ping=True)

    # ── 1. Prédictions B25 (run synth : proba_long = rank global H10) ──
    print("Chargement des prédictions B25 …")
    preds = load_predictions(engine, START, END, batch_id=BID)
    print(f"  → {len(preds)} lignes, {preds['symbol'].nunique()} symboles")
    preds["d"] = pd.to_datetime(preds["trade_date"], utc=False).dt.date
    preds = preds[["symbol", "d", "proba_long"]].dropna(subset=["proba_long"])
    needed_symbols = sorted(set(preds["symbol"].astype(str)) | {"SPY"})

    # ── 2. Barres restreintes aux symboles du run + SPY (warmup 60j pour vol 20j) ──
    print("Chargement OHLCV (uniquement symboles du run + SPY) …")
    source_filter_sql, source_filter_params = get_required_bars_source_filter(engine)
    placeholders = ",".join(f":s{i}" for i in range(len(needed_symbols)))
    params = {
        "start": START - timedelta(days=60),
        "end": END,
        **source_filter_params,
        **{f"s{i}": s for i, s in enumerate(needed_symbols)},
    }
    bars = pd.read_sql(
        text(
            f"""
            SELECT symbol, `date` AS trade_date, COALESCE(adj_close, `close`) AS `close`
            FROM stock_bars_daily
            WHERE `date` BETWEEN :start AND :end
              AND symbol IN ({placeholders})
              {source_filter_sql}
            ORDER BY symbol, `date`
            """
        ),
        engine,
        params=params,
    )
    bars["d"] = pd.to_datetime(bars["trade_date"], utc=False).dt.date
    print(f"  → {len(bars)} lignes, {bars['symbol'].nunique()} symboles")

    print("Calcul forward returns H10 + vol scaling …")
    g = bars.groupby("symbol", sort=False)
    bars["fwd10"] = g["close"].shift(-HORIZON) / bars["close"] - 1.0
    bars["ret1"] = g["close"].pct_change(fill_method=None)
    bars["vol20"] = g["ret1"].transform(lambda x: x.rolling(20, min_periods=5).std(ddof=0))

    m = preds.merge(
        bars[["symbol", "d", "fwd10", "vol20", "close"]],
        on=["symbol", "d"],
        how="inner",
    )
    # vol-scalé + winsorize 1%/99% par date (miroir pipeline de target)
    m["fwd_vs"] = m["fwd10"] / m["vol20"].clip(lower=0.001)
    m["fwd_vs"] = m.groupby("d")["fwd_vs"].transform(
        lambda x: x.clip(lower=x.quantile(0.01), upper=x.quantile(0.99))
    )
    # neutralisation sectorielle (miroir étape 3 du pipeline de target)
    sector_map = _load_sector_mapping(engine)
    m["sector"] = m["symbol"].astype(str).str.upper().map(sector_map)
    for src, dst in [("fwd10", "fwd10_sn"), ("fwd_vs", "fwd_vs_sn")]:
        valid = m["sector"].notna()
        med = m.loc[valid].groupby(["d", "sector"])[src].transform("median")
        m[dst] = m[src].copy()
        m.loc[valid, dst] = m.loc[valid, src] - med
    m = m.dropna(subset=["fwd10", "fwd_vs", "fwd10_sn", "fwd_vs_sn"])
    print(f"  → {len(m)} lignes score×forward retour (secteurs mappés: {m['sector'].notna().mean():.0%})")

    # ── 3. IC journalier cross-sectionnel ──
    def _daily_ic(df: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "ic_raw": df["proba_long"].corr(df["fwd10"], method="spearman"),
                "ic_vs": df["proba_long"].corr(df["fwd_vs"], method="spearman"),
                "ic_sn": df["proba_long"].corr(df["fwd10_sn"], method="spearman"),
                "ic_vs_sn": df["proba_long"].corr(df["fwd_vs_sn"], method="spearman"),
                "n_sym": len(df),
                "dispersion": float(df["fwd10"].std(ddof=0)),
            }
        )

    daily = m.groupby("d").apply(_daily_ic, include_groups=False).reset_index()
    daily = daily[daily["n_sym"] >= 30].copy()
    print(f"  → {len(daily)} jours IC (≥30 symboles)")

    # ── 4. Régimes de marché sur SPY (warmup long pour SMA200/médiane 252j) ──
    print("Classification des régimes (SPY) …")
    spy_bars = pd.read_sql(
        text(
            f"""
            SELECT 'SPY' AS symbol, `date` AS trade_date, COALESCE(adj_close, `close`) AS `close`
            FROM stock_bars_daily
            WHERE `date` BETWEEN :start AND :end
              AND symbol = 'SPY'
              {source_filter_sql}
            ORDER BY `date`
            """
        ),
        engine,
        params={"start": date(2017, 1, 1), "end": END, **source_filter_params},
    )
    regime_df = classify_market_regimes(
        spy_bars,
        benchmark_symbol="SPY",
        trade_dates=[date.fromisoformat(str(x)) for x in daily["d"]],
    )
    daily = daily.merge(regime_df[["trade_date", "market_regime"]], left_on="d", right_on="trade_date", how="left")
    daily["market_regime"] = daily["market_regime"].fillna("range")

    # ── 5. Axe dispersion : médiane split sur la période ──
    med_disp = daily["dispersion"].median()
    daily["disp_regime"] = np.where(daily["dispersion"] >= med_disp, "high_disp", "low_disp")

    # ── 6. Agrégations ──
    print("\n" + "=" * 100)
    print("IC PAR RÉGIME DE MARCHÉ — B25 (rank global H10)")
    print("=" * 100)

    rows = []
    for ic_col, label in [
        ("ic_raw", "IC vs fwd10 brut"),
        ("ic_vs", "IC vs fwd10 vol-scalé+winsor"),
        ("ic_sn", "IC vs fwd10 sector-neutral"),
        ("ic_vs_sn", "IC vs fwd10 vol-scalé sector-neutral"),
    ]:
        for reg, sub in daily.groupby("market_regime", sort=False):
            n = len(sub)
            mean_ic = sub[ic_col].mean()
            std_ic = sub[ic_col].std(ddof=0)
            ir = mean_ic / std_ic if std_ic > 0 else np.nan
            tstat = mean_ic / (std_ic / np.sqrt(n)) if std_ic > 0 else np.nan
            rows.append(
                {
                    "metrique": label,
                    "regime": reg,
                    "jours": n,
                    "ic_moyen": round(float(mean_ic), 4),
                    "ic_ir": round(float(ir), 2),
                    "t_stat": round(float(tstat), 2),
                    "pct_jours_positifs": round(float((sub[ic_col] > 0).mean() * 100), 1),
                }
            )
        for reg, sub in daily.groupby("disp_regime", sort=False):
            n = len(sub)
            mean_ic = sub[ic_col].mean()
            std_ic = sub[ic_col].std(ddof=0)
            rows.append(
                {
                    "metrique": label,
                    "regime": reg,
                    "jours": n,
                    "ic_moyen": round(float(mean_ic), 4),
                    "ic_ir": round(float(mean_ic / std_ic), 2) if std_ic > 0 else np.nan,
                    "t_stat": round(float(mean_ic / (std_ic / np.sqrt(n))), 2) if std_ic > 0 else np.nan,
                    "pct_jours_positifs": round(float((sub[ic_col] > 0).mean() * 100), 1),
                }
            )
        # global
        n = len(daily)
        mean_ic = daily[ic_col].mean()
        std_ic = daily[ic_col].std(ddof=0)
        rows.append(
            {
                "metrique": label,
                "regime": "GLOBAL",
                "jours": n,
                "ic_moyen": round(float(mean_ic), 4),
                "ic_ir": round(float(mean_ic / std_ic), 2) if std_ic > 0 else np.nan,
                "t_stat": round(float(mean_ic / (std_ic / np.sqrt(n))), 2) if std_ic > 0 else np.nan,
                "pct_jours_positifs": round(float((daily[ic_col] > 0).mean() * 100), 1),
            }
        )

    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))

    # croisement régime × dispersion (ic_vs_sn)
    print("\nCROISEMENT régime × dispersion (IC vs vol-scalé sector-neutral) :")
    cross = daily.pivot_table(index="market_regime", columns="disp_regime", values="ic_vs_sn", aggfunc="mean")
    print(cross.round(4).to_string())

    print("\nIC MOYEN PAR ANNÉE (ic_vs_sn) :")
    daily["year"] = daily["d"].astype(str).str[:4]
    print(
        daily.groupby("year")["ic_vs_sn"]
        .agg(jours="count", ic_moyen="mean", pct_pos=lambda s: round(float((s > 0).mean() * 100), 1))
        .round(4)
        .to_string()
    )

    print("\nRépartition des jours par régime :")
    print(daily["market_regime"].value_counts().to_string())

    # ── 7. Sauvegarde ──
    import os

    os.makedirs(OUT_DIR, exist_ok=True)
    daily.to_csv(os.path.join(OUT_DIR, "ic_by_regime_b25_daily.csv"), index=False)
    summary.to_csv(os.path.join(OUT_DIR, "ic_by_regime_b25_summary.csv"), index=False)
    print(f"\nSauvegardé : {OUT_DIR}\\ic_by_regime_b25_daily.csv / _summary.csv")


if __name__ == "__main__":
    main()
