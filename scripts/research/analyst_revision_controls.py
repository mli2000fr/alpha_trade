"""Descriptive sector/momentum controls for the frozen restored analyst audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from scripts.research.restore_analyst_archive import save
from scripts.research.us_prospective_directional_collection_audit import query
from scripts.research.us_prospective_directional_check import directional_metrics

SOURCE = Path("artifacts/research/analyst_archive_restore/20261010/directional")
OUTPUT = Path("artifacts/research/analyst_archive_restore/20261010/controls")
SECTORS = Path("artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet")


def rank_within(frame, feature, groups, min_size=20):
    part = frame.dropna(subset=[feature]+groups).copy()
    grouped = part.groupby(groups)[feature]
    ranks = grouped.rank(method="average", pct=True)
    return ranks.where(grouped.transform("size").ge(min_size)).reindex(frame.index)


def selected_summary(frame, feature, horizon):
    part = frame.dropna(subset=[feature]).copy()
    selections, daily = [], []
    for day, group in part.groupby("entry_date"):
        top = group.sort_values([feature,"symbol"],ascending=[False,True]).head(max(1,int(np.ceil(len(group)*.2))))
        selections.append(top)
        daily.append({"entry_date":str(day.date()),"selected":len(top),"d10_pct":100*float(top.decile.eq(10).mean()),"d1_pct":100*float(top.decile.eq(1).mean()),"baseline_d10_pct":100*float(group.decile.eq(10).mean()),"baseline_d1_pct":100*float(group.decile.eq(1).mean())})
    selected = pd.concat(selections) if selections else part.iloc[:0]
    counts = selected.symbol.value_counts()
    metrics = directional_metrics(part,feature)
    metrics["selection"] = {key:float(np.mean([d[key] for d in daily])) if daily else None for key in ("d10_pct","d1_pct","baseline_d10_pct","baseline_d1_pct")}
    metrics["selection"]["unique_symbols"] = len(counts)
    metrics["selection"]["top10_symbols_share_pct"] = 100*float(counts.head(10).sum()/len(selected)) if len(selected) else None
    metrics["selection"]["most_repeated_symbols"] = counts.head(10).to_dict()
    # First available entry and subsequent entries only after the previous H-session path.
    dates = sorted(part.entry_date.unique())
    nonoverlap = []
    if dates:
        calendar = get_market_calendar("US_EQ",allow_us_weekday_fallback=False)
        sessions = pd.DatetimeIndex(calendar.session_dates(pd.Timestamp(dates[0]).date(),pd.Timestamp(dates[-1]).date()))
        next_position = -1
        for day in dates:
            position = sessions.get_loc(day)
            if position>=next_position:
                nonoverlap.append(day)
                next_position = position+horizon
    metrics["nonoverlap"] = directional_metrics(part[part.entry_date.isin(nonoverlap)],feature)
    return metrics


def run():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    protocol = {"source":str(SOURCE),"sector_source":str(SECTORS),"sector_sha256":hashlib.sha256(SECTORS.read_bytes()).hexdigest(),
        "sectors_current_non_pit":True,"horizons":[3,5,10,20],"revision_scores":["eps_revision_net_7d","eps_revision_net_30d"],
        "momentum":"20-session close/close return ending at decision, all bars qualified",
        "neutralization":"within decision-date/sector/momentum-quintile percentile, min 20 covered symbols per stratum",
        "models_trained":False,"sql_writes":False,"threshold_optimized":False,
        "interpretation":"diagnostic controls, not independent confirmation or PIT-validated sector strategy"}
    save(OUTPUT/"protocol.json",protocol)
    features = pd.read_parquet(SOURCE/"features.parquet")
    sectors = pd.read_parquet(SECTORS)[["symbol","sector"]].drop_duplicates("symbol")
    symbols = sorted(features.symbol.unique())
    engine = get_sqlalchemy_engine(db_name="alpha_trade")
    with engine.connect() as conn:
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        bars = pd.DataFrame(query(conn,"SELECT date,symbol,close,volume,is_filled,data_adjustment,instrument_id FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN '2026-07-01' AND '2026-10-09'",symbols))
    bars["date"] = pd.to_datetime(bars.date)
    for col in ("close","volume"):
        bars[col] = pd.to_numeric(bars[col],errors="coerce")
    calendar = get_market_calendar("US_EQ",allow_us_weekday_fallback=False)
    sessions = pd.DatetimeIndex(calendar.session_dates(bars.date.min().date(),bars.date.max().date()))
    close = bars.pivot(index="date",columns="symbol",values="close").reindex(sessions)
    bars["valid"] = bars.close.gt(0)&bars.volume.gt(0)&bars.is_filled.eq(0)&bars.data_adjustment.eq("split")&bars.instrument_id.notna()
    valid = bars.pivot(index="date",columns="symbol",values="valid").reindex(sessions).eq(True)
    ids = bars.pivot(index="date",columns="symbol",values="instrument_id").reindex(sessions)
    qualified = valid.rolling(21).sum().eq(21)&ids.rolling(21).apply(lambda x:float(len(set(x))==1),raw=True).eq(1)
    momentum = (close/close.shift(20)-1).where(qualified).rename_axis(index="decision_date",columns="symbol").stack().rename("momentum20").reset_index()
    report = {"status":"COMPLETED_DIAGNOSTIC_NO_PROMOTION","protocol":protocol,"horizons":{}}
    for horizon in protocol["horizons"]:
        print("Controls H",horizon,flush=True)
        panel = pd.read_parquet(SOURCE/f"panel_h{horizon}.parquet").merge(momentum,on=["decision_date","symbol"],how="left",validate="one_to_one").merge(sectors,on="symbol",how="left",validate="many_to_one")
        # Equal-size quintiles with fixed symbol tie break. No labels used.
        rank = panel.groupby("decision_date").momentum20.rank(method="first",pct=True)
        panel["momentum_quintile"] = np.minimum(4,np.floor(rank*5))
        results = {"momentum20_baseline":selected_summary(panel,"momentum20",horizon)}
        for feature in protocol["revision_scores"]:
            matched = panel.dropna(subset=[feature,"momentum20","sector"]).copy()
            matched["neutral_revision"] = rank_within(matched,feature,["decision_date","sector","momentum_quintile"])
            results[feature] = {"raw_on_matched":selected_summary(matched,feature,horizon),
                "momentum_on_matched":selected_summary(matched,"momentum20",horizon),
                "raw_on_neutral_coverage":selected_summary(matched[matched.neutral_revision.notna()],feature,horizon),
                "sector_momentum_neutral":selected_summary(matched,"neutral_revision",horizon)}
        report["horizons"][str(horizon)] = results
        save(OUTPUT/"report.json",report)
    print("Finished",OUTPUT/"report.json",flush=True)


if __name__ == "__main__":
    run()
