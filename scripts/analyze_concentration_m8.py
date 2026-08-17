# -*- coding: utf-8 -*-
"""Test 3 (2026-08-17) — Analyse de concentration du benchmark OOS 2026 (m8).

Questions : gross par jour ? exposition LONG vs SHORT ? poids max symbole/secteur ?
nb positions simultanées ? contribution top 1/2/3 trades au +27.09 % ?

Source : artifacts/backtesting/cmp_b25_h20_2026_prodparity_repro_h20cfg_m8/
         trade_audit_log.csv (le run == benchmark archivé bit-for-bit).

Sorties : logs/concentration_m8_report.txt
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "artifacts" / "backtesting" / "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8"
AUDIT = RUN_DIR / "trade_audit_log.csv"
OUT = ROOT / "logs" / "concentration_m8_report.txt"

sys.path.insert(0, str(ROOT))


def _load_sector_map() -> dict[str, str]:
    from sqlalchemy import MetaData, Table, create_engine, select

    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    try:
        meta = MetaData()
        stock_metadata = Table("stock_metadata", meta, autoload_with=engine)
        col = None
        for c in ("provider_sector", "sector"):
            if c in stock_metadata.c:
                col = stock_metadata.c[c]
                break
        if col is None:
            return {}
        stmt = select(stock_metadata.c.symbol, col).where(col.isnot(None), col != "")
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        m = {}
        for sym, sec in rows:
            m[str(sym).strip().upper()] = str(sec).strip()
        return m
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  sector map échec: {exc}")
        return {}


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}"


def main() -> None:
    df = pd.read_csv(AUDIT)
    snap = df[df["event_type"] == "daily_leverage_snapshot"].copy()
    entries = df[df["event_type"] == "entry_opened"].copy()
    exits = df[df["event_type"] == "exit_closed"].copy()

    secmap = _load_sector_map()
    lines: list[str] = []
    w = lines.append

    w("=" * 78)
    w("TEST 3 — CONCENTRATION m8 · benchmark OOS 2026 (B25 H20 top10 P14 m8)")
    w("=" * 78)

    # ── 1. Gross / exposition par jour ────────────────────────────────────
    w("\n## 1. GROSS PAR JOUR (daily_leverage_snapshot)")
    g = snap["gross_exposure_before_pct"].astype(float)
    n = snap["net_exposure_before_pct"].astype(float)
    w(f"  jours snapshot : {len(snap)}")
    w(f"  gross moyen     : {_fmt(g.mean()*100)} %")
    w(f"  gross médian    : {_fmt(g.median()*100)} %")
    w(f"  gross min/max   : {_fmt(g.min()*100)} % / {_fmt(g.max()*100)} %")
    w(f"  gross p90/p95   : {_fmt(g.quantile(0.90)*100)} % / {_fmt(g.quantile(0.95)*100)} %")
    w(f"  jours gross >100% : {(g > 1.0).sum()} / {len(g)}")
    w(f"  jours gross >150% : {(g > 1.5).sum()} / {len(g)}")
    w(f"  net moyen (signé): {_fmt(n.mean()*100)} %  (négatif = short net)")
    w(f"  net min/max      : {_fmt(n.min()*100)} % / {_fmt(n.max()*100)} %")

    # ── 2. Exposition LONG vs SHORT ───────────────────────────────────────
    w("\n## 2. EXPOSITION LONG vs SHORT (gross=long+short, net=long−short)")
    long_pct = (g + n) / 2.0
    short_pct = (g - n) / 2.0
    w(f"  LONG moyen  : {_fmt(long_pct.mean()*100)} %  |  max {_fmt(long_pct.max()*100)} %")
    w(f"  SHORT moyen : {_fmt(short_pct.mean()*100)} %  |  max {_fmt(short_pct.max()*100)} %")
    w(f"  jours net LONG  (>0) : {(n > 0).sum()} / {len(n)}")
    w(f"  jours net SHORT (<0) : {(n < 0).sum()} / {len(n)}")
    # notional total par côté
    long_not = long_pct * snap["current_equity"].astype(float)
    short_not = short_pct * snap["current_equity"].astype(float)
    w(f"  notional LONG  cumulé : ${_fmt(long_not.sum(), 0)}")
    w(f"  notional SHORT cumulé : ${_fmt(short_not.sum(), 0)}")

    # ── 3. Positions simultanées ─────────────────────────────────────────
    w("\n## 3. POSITIONS SIMULTANÉES (appariement FIFO entrée→sortie)")
    # Apparie chaque entrée à sa sortie (même symbol+side, ordre chronologique).
    # Le merge naïf sur symbol crée un produit cartésien (multi-trades/symbole).
    def _pair_fifo(entries_df, exits_df):
        paired = []
        for (sym, side), grp_in in entries_df.groupby(["symbol", "side"]):
            ins = grp_in.sort_values("execution_date")[["execution_date"]].reset_index(drop=True)
            grp_out = exits_df[(exits_df["symbol"] == sym) & (exits_df["side"] == side)]
            outs = grp_out.sort_values("event_date")[["event_date"]].reset_index(drop=True)
            n = min(len(ins), len(outs))
            for k in range(n):
                paired.append((sym, side, ins.iloc[k]["execution_date"], outs.iloc[k]["event_date"]))
        return paired

    paired = _pair_fifo(entries, exits)
    trades = pd.DataFrame(paired, columns=["symbol", "side", "d_in", "d_out"])
    trades["d_in"] = pd.to_datetime(trades["d_in"])
    trades["d_out"] = pd.to_datetime(trades["d_out"])
    all_days = pd.date_range(trades["d_in"].min(), max(snap["event_date"]), freq="B")
    counts, gross_d = [], []
    for d in all_days:
        open_mask = (trades["d_in"] <= d) & (trades["d_out"] >= d)
        counts.append(int(open_mask.sum()))
        s = snap[snap["event_date"] == d.strftime("%Y-%m-%d")]
        gross_d.append(float(s["gross_exposure_before_pct"].iloc[0]) if len(s) else float("nan"))
    cs = pd.Series(counts, index=all_days)
    gd = pd.Series(gross_d, index=all_days).dropna()
    w(f"  paires entrée→sortie appariées (FIFO) : {len(trades)} (77 exit_closed attendus)")
    w(f"  positions simultanées — min/moy/max : {cs.min()} / {_fmt(cs.mean(),1)} / {cs.max()}")
    w(f"  positions simultanées — p50/p90/p95 : {int(cs.median())} / {int(cs.quantile(0.90))} / {int(cs.quantile(0.95))}")
    w(f"  jours avec >6 positions : {(cs > 6).sum()} / {len(cs)}")
    w(f"  jours avec 8 positions (max_positions) : {(cs == 8).sum()} / {len(cs)}")
    w(f"  gross moyen (jours actifs) : {_fmt(gd.mean()*100)} %")
    w("  top 5 jours (nb positions) :")
    for d, c in cs.sort_values(ascending=False).head(5).items():
        w(f"     {d.date()}  → {c} positions | gross {_fmt(gd.get(d, float('nan'))*100)} %")

    # ── 4. Poids max symbole ─────────────────────────────────────────────
    w("\n## 4. POIDS MAX SYMBOLE (target_weight_pct à l'entrée)")
    tw = entries["target_weight_pct"].astype(float)
    w(f"  poids entrée — min/moy/max : {_fmt(tw.min()*100)} % / {_fmt(tw.mean()*100)} % / {_fmt(tw.max()*100)} %")
    w(f"  poids entrée — p90/p95     : {_fmt(tw.quantile(0.90)*100)} % / {_fmt(tw.quantile(0.95)*100)} %")
    top_sym = entries.loc[entries["target_weight_pct"].astype(float).nlargest(10).index,
                          ["symbol", "side", "execution_date", "target_weight_pct"]]
    w("  top 10 entrées par poids cible :")
    for _, r in top_sym.iterrows():
        w(f"     {r['symbol']:<8} {str(r['side']):<5} {r['execution_date']}  poids {_fmt(r['target_weight_pct']*100)} %")

    # ── 5. Concentration secteur ─────────────────────────────────────────
    w("\n## 5. POIDS MAX SECTEUR (joindre symbol → secteur GICS)")
    sec_of = entries["symbol"].map(lambda s: secmap.get(str(s).strip().upper(), "Unknown"))
    # poids par secteur au jour d'entrée (somme des poids ouverts)
    entries2 = entries.copy()
    entries2["sector"] = sec_of.values
    sector_weight_sum = entries2.groupby("sector")["target_weight_pct"].sum().astype(float)
    sector_weight_sum = sector_weight_sum.sort_values(ascending=False)
    w(f"  secteurs représentés : {len(sector_weight_sum)} (mapping {len(secmap)} symbols)")
    w("  poids cible cumulé par secteur (somme sur toutes les entrées) :")
    for sec, wgt in sector_weight_sum.head(12).items():
        w(f"     {sec:<28} {_fmt(wgt*100)} %  ({int((entries2['sector'] == sec).sum())} entrées)")
    unk = entries2["sector"].eq("Unknown").mean() * 100
    w(f"  entrées sans secteur (Unknown) : {_fmt(unk)} %")
    # exposition max par secteur sur un même jour
    w("  top 5 entrées par poids, avec secteur :")
    top_all = entries2.loc[entries2["target_weight_pct"].astype(float).nlargest(5).index,
                           ["symbol", "side", "execution_date", "target_weight_pct", "sector"]]
    for _, r in top_all.iterrows():
        w(f"     {r['symbol']:<8} {str(r['side']):<5} {r['execution_date']}  poids {_fmt(r['target_weight_pct']*100)} %  secteur {r['sector']}")

    # ── 5bis. Poids max secteur PAR JOUR (concentration réelle) ──────────
    w("\n## 5bis. POIDS MAX SECTEUR PAR JOUR (portefeuille reconstruit)")
    pf = pd.DataFrame(_pair_fifo(entries, exits), columns=["symbol", "side", "d_in", "d_out"])
    pf["d_in"] = pd.to_datetime(pf["d_in"])
    pf["d_out"] = pd.to_datetime(pf["d_out"])
    pf["sector"] = pf["symbol"].map(lambda s: secmap.get(str(s).strip().upper(), "Unknown"))
    sym_w = entries2.groupby("symbol")["target_weight_pct"].mean()
    pf["w"] = pf["symbol"].map(sym_w).fillna(0.1)
    days = pd.date_range(pf["d_in"].min(), max(snap["event_date"]), freq="B")
    rows = []
    for d in days:
        openm = (pf["d_in"] <= d) & (pf["d_out"] >= d)
        sub = pf[openm]
        if sub.empty:
            continue
        sec_sum = sub.groupby("sector")["w"].sum()
        rows.append((d, sec_sum.idxmax(), float(sec_sum.max()), int(len(sub))))
    mdf = pd.DataFrame(rows, columns=["day", "sector", "max_w", "npos"])
    w(f"  jours analysés : {len(mdf)}")
    w(f"  poids max secteur/jour — moy {_fmt(mdf['max_w'].mean()*100)} % | max {_fmt(mdf['max_w'].max()*100)} % | p95 {_fmt(mdf['max_w'].quantile(0.95)*100)} %")
    w(f"  jours secteur > 30 % : {(mdf['max_w'] > 0.30).sum()} | > 40 % : {(mdf['max_w'] > 0.40).sum()} | > 50 % : {(mdf['max_w'] > 0.50).sum()}")
    w("  top 5 jours (poids secteur max) :")
    for _, r in mdf.sort_values("max_w", ascending=False).head(5).iterrows():
        w(f"     {r['day'].date()}  → {r['sector']} {_fmt(r['max_w']*100)} % ({int(r['npos'])} positions)")
    dom = mdf.groupby("sector")["max_w"].mean().sort_values(ascending=False)
    w("  poids moyen du secteur dominant par jour, top 6 :")
    for sec, val in dom.head(6).items():
        w(f"     {sec:<28} {_fmt(val*100)} %")

    # ── 6. Contribution top trades ───────────────────────────────────────
    w("\n## 6. CONTRIBUTION TOP 1/2/3 TRADES (exit_closed)")
    pnl_net = exits["pnl"].astype(float).sum()
    w(f"  PnL net total (exits) : ${_fmt(pnl_net, 2)}")
    top = exits.reindex(exits["pnl"].astype(float).sort_values(ascending=False).index)[
        ["symbol", "side", "event_date", "pnl", "return_pct", "holding_days", "exit_reason"]].head(10)
    w("  top 10 trades par PnL :")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        w(f"     #{i:<2} {r['symbol']:<8} {str(r['side']):<5} {r['event_date']}  pnl ${_fmt(r['pnl'],0):>10}  ret {_fmt(r['return_pct'],2)} %  {int(r['holding_days'])}j  {r['exit_reason']}")
    t1 = top["pnl"].iloc[0] if len(top) >= 1 else 0
    t12 = top["pnl"].head(2).sum()
    t123 = top["pnl"].head(3).sum()
    t10 = top["pnl"].sum()
    w(f"  top1 seul  : ${_fmt(t1,0)} = {_fmt(t1/pnl_net*100,1)} % du PnL net")
    w(f"  top1+2     : ${_fmt(t12,0)} = {_fmt(t12/pnl_net*100,1)} %")
    w(f"  top1+2+3   : ${_fmt(t123,0)} = {_fmt(t123/pnl_net*100,1)} %")
    w(f"  top10      : ${_fmt(t10,0)} = {_fmt(t10/pnl_net*100,1)} %")
    # pire trades
    bot = exits.reindex(exits["pnl"].astype(float).sort_values().index)[
        ["symbol", "side", "event_date", "pnl", "return_pct", "exit_reason"]].head(5)
    w("  pires 5 trades :")
    for _, r in bot.iterrows():
        w(f"     {r['symbol']:<8} {str(r['side']):<5} {r['event_date']}  pnl ${_fmt(r['pnl'],0):>10}  ret {_fmt(r['return_pct'],2)} %  {r['exit_reason']}")

    # ── 7. Overlap top symbole ───────────────────────────────────────────
    w("\n## 7. TITRES RÉCURRENTS (nb trades par symbole)")
    sym_cnt = exits["symbol"].value_counts().head(10)
    for sym, c in sym_cnt.items():
        pnl_sym = exits[exits["symbol"] == sym]["pnl"].astype(float).sum()
        w(f"     {sym:<8} {int(c)} trades | PnL cumulé ${_fmt(pnl_sym, 0)}")

    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
