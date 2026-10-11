"""Frozen exploratory analyst signals; SELECT only, no model or trading changes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from common.market_calendar import get_market_calendar, get_nyse_session_bounds
from database.connection import get_sqlalchemy_engine
from scripts.research.restore_analyst_archive import TABLES, save
from scripts.research.us_prospective_directional_check import directional_metrics
from scripts.research.us_prospective_directional_collection_audit import query

FEATURES = ["eps_revision_net_7d", "eps_revision_net_30d", "target_upside", "recommendation_balance"]


def balance(up, down):
    total = up + down
    result = (up-down) / total.replace(0, np.nan)
    return result.mask(total.eq(0), 0).where(up.ge(0) & down.ge(0))


def qualify_snapshots(frame):
    for column in ("observed_at", "available_at"):
        frame[column] = pd.to_datetime(frame[column])
    calendar = get_market_calendar("US_EQ", allow_us_weekday_fallback=False)
    days = calendar.session_dates(frame.observed_at.min().date()-timedelta(days=1), frame.observed_at.max().date()+timedelta(days=15))
    closes = pd.DatetimeIndex([get_nyse_session_bounds(day)[1] for day in days]).tz_convert("UTC").tz_localize(None)
    indices = closes.searchsorted(frame.observed_at, side="right")
    expected = pd.Series(closes.take(indices),index=frame.index)
    valid = frame.observed_at.notna() & frame.available_at.eq(expected) & frame.available_at.gt(frame.observed_at)
    return frame.loc[valid].copy(), int((~valid).sum())


def run(output, universe):
    output.mkdir(parents=True, exist_ok=True)
    source = universe.read_bytes()
    symbols = sorted({s.upper() for s in re.split(r"[,;\s]+", source.decode("utf-8-sig").strip()) if s})
    protocol = {"universe": str(universe), "universe_sha256": hashlib.sha256(source).hexdigest(),
        "universe_count": len(symbols), "data_end_inclusive": "2026-10-09",
        "features": FEATURES, "horizons": [3,5,10,20], "expected_direction": "larger feature -> D10",
        "eps_revision_horizon": "CURRENT_QUARTER", "recommendation_period": "0m",
        "decision": "close of stored available_at, validated against next NYSE close after observed_at",
        "entry": "following session open", "exit": "close of Hth session including entry",
        "deciles": "signed return over full current universe with qualified complete split-adjusted paths, stable symbol ties",
        "minimum_price_coverage": .90, "models_trained": False, "sql_writes": False,
        "limitations": ["Short prospective sample; no stable edge or economic promotion possible",
                        "Current universe, survivorship bias; dates and overlapping returns are not independent",
                        "Relative fiscal horizons lack validated fiscal identity: no time-series EPS delta is constructed",
                        "Canonical prices are screened but not independently requalified for every path",
                        "Yahoo permission remains unconfirmed; restored records do not establish collection rights"]}
    save(output / "protocol.json", protocol)
    engine = get_sqlalchemy_engine(db_name="alpha_trade")
    inventory, frames, rejected = {}, [], {}
    with engine.connect() as conn:
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        for table in TABLES:
            if table == "analyst_snapshot_collection_run":
                sql = f"SELECT COUNT(*) n,MIN(started_at) first_date,MAX(started_at) last_date FROM {table}"
            else:
                sql = f"SELECT COUNT(*) n,COUNT(DISTINCT snapshot_date) dates,COUNT(DISTINCT symbol) symbols,MIN(snapshot_date) first_date,MAX(snapshot_date) last_date FROM {table}"
            inventory[table] = dict(conn.execute(text(sql)).mappings().one())
        definitions = {
            "revision": "SELECT symbol,observed_at,available_at,up_last_7_days,down_last_7_days,up_last_30_days,down_last_30_days FROM stock_analyst_eps_revision_history WHERE symbol IN :symbols AND horizon_normalized='CURRENT_QUARTER'",
            "target": "SELECT symbol,observed_at,available_at,target_mean FROM stock_analyst_target_history WHERE symbol IN :symbols",
            "recommendation": "SELECT symbol,observed_at,available_at,strong_buy,buy,hold,sell,strong_sell FROM stock_analyst_recommendation_history WHERE symbol IN :symbols AND period_raw='0m'",
        }
        for name, sql in definitions.items():
            print("Loading", name, flush=True)
            frame = pd.DataFrame(query(conn, sql, symbols))
            frame, rejected[name] = qualify_snapshots(frame)
            frame["decision_date"] = frame.available_at.dt.normalize()
            frame = frame[frame.decision_date.le(pd.Timestamp("2026-10-09"))]
            frame = frame.sort_values(["available_at", "observed_at"]).drop_duplicates(["decision_date","symbol"], keep="last")
            for col in frame.columns.difference(["symbol","observed_at","available_at","decision_date"]):
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
            if name == "revision":
                frame["eps_revision_net_7d"] = balance(frame.up_last_7_days, frame.down_last_7_days)
                frame["eps_revision_net_30d"] = balance(frame.up_last_30_days, frame.down_last_30_days)
                frame = frame[["decision_date","symbol","eps_revision_net_7d","eps_revision_net_30d"]]
            elif name == "recommendation":
                total = frame[["strong_buy","buy","hold","sell","strong_sell"]].sum(axis=1, min_count=5)
                frame["recommendation_balance"] = (2*frame.strong_buy+frame.buy-frame.sell-2*frame.strong_sell)/total.where(total.gt(0))
                frame = frame[["decision_date","symbol","recommendation_balance"]]
            else:
                frame = frame[["decision_date","symbol","target_mean"]]
            frames.append(frame)
        features = frames[0]
        for frame in frames[1:]:
            features = features.merge(frame, on=["decision_date","symbol"],how="outer",validate="one_to_one")
        start = features.decision_date.min().date()
        print("Loading price paths", start, flush=True)
        bars = pd.DataFrame(query(conn, "SELECT date,symbol,instrument_id,open,high,low,close,volume,is_filled,data_adjustment FROM stock_bars_daily WHERE symbol IN :symbols AND date>=:start AND date<=:end", symbols, start=start,end="2026-10-09"))
    bars["date"] = pd.to_datetime(bars.date)
    for column in ("open","high","low","close","volume"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    if bars.duplicated(["date","symbol"]).any():
        raise ValueError("Duplicate canonical price dates")
    bars["valid"] = bars.is_filled.eq(0) & bars.open.gt(0) & bars.close.gt(0) & bars.volume.gt(0) & bars.data_adjustment.eq("split") & bars.high.ge(bars[["open","close"]].max(axis=1)) & bars.low.le(bars[["open","close"]].min(axis=1)) & bars.instrument_id.notna()
    spot = bars[["date","symbol","close","valid"]].rename(columns={"date":"decision_date"})
    features = features.merge(spot,on=["decision_date","symbol"],how="left",validate="one_to_one")
    features["target_upside"] = (features.target_mean/features.close-1).where(features.target_mean.gt(0) & features.valid.eq(True))
    features.to_parquet(output / "features.parquet",index=False)
    calendar = get_market_calendar("US_EQ",allow_us_weekday_fallback=False)
    sessions = pd.DatetimeIndex(calendar.session_dates(start, date(2026,11,30)))
    opens = bars.pivot(index="date",columns="symbol",values="open").reindex(index=sessions,columns=symbols)
    closes = bars.pivot(index="date",columns="symbol",values="close").reindex(index=sessions,columns=symbols)
    valid = bars.pivot(index="date",columns="symbol",values="valid").reindex(index=sessions,columns=symbols).eq(True)
    ids = bars.pivot(index="date",columns="symbol",values="instrument_id").reindex(index=sessions,columns=symbols)
    report = {"status":"COMPLETED_EXPLORATORY_NO_PROMOTION", "inventory":inventory,"protocol":protocol,
        "invalid_pit_rows_excluded":rejected,"feature_coverage":{f:int(features[f].notna().sum()) for f in FEATURES},"horizons":{}}
    for horizon in protocol["horizons"]:
        print("Evaluating H", horizon, flush=True)
        labels, excluded = [], []
        for day in sorted(features.decision_date.unique()):
            entry = sessions.searchsorted(day,side="right")
            end = entry+horizon-1
            if end>=len(sessions) or sessions[end]>pd.Timestamp("2026-10-09"):
                excluded.append({"decision_date":str(pd.Timestamp(day).date()),"reason":"IMMATURE"})
                continue
            path = valid.iloc[entry:end+1].all()
            same_id = ids.iloc[entry:end+1].nunique().eq(1)
            returns = (closes.iloc[end]/opens.iloc[entry]-1).where(path & same_id).dropna()
            if len(returns)<.90*len(symbols):
                excluded.append({"decision_date":str(pd.Timestamp(day).date()),"reason":"PRICE_COVERAGE_LT_90", "valid_symbols":len(returns)})
                continue
            ordered = returns.rename("future_return").rename_axis("symbol").reset_index().sort_values(["future_return","symbol"])
            ordered["decile"] = np.minimum(10, np.floor(np.arange(len(ordered))*10/len(ordered)).astype(int)+1)
            ordered["decision_date"], ordered["entry_date"] = pd.Timestamp(day),sessions[entry]
            labels.append(ordered)
        if labels:
            panel = features.merge(pd.concat(labels),on=["decision_date","symbol"],how="inner",validate="one_to_one")
            panel.to_parquet(output/f"panel_h{horizon}.parquet",index=False)
            metrics = {f:directional_metrics(panel,f) for f in FEATURES}
            for feature in FEATURES:
                part = panel.dropna(subset=[feature])
                selected = []
                for day, group in part.groupby("entry_date"):
                    top = group.sort_values([feature,"symbol"],ascending=[False,True]).head(max(1,int(np.ceil(.20*len(group)))))
                    selected.append({"entry_date":str(day.date()),"selected":len(top),"d10_pct":100*float(top.decile.eq(10).mean()),"d1_pct":100*float(top.decile.eq(1).mean()),"mean_return_pct":100*float(top.future_return.mean()),"baseline_d10_pct":100*float(group.decile.eq(10).mean()),"baseline_d1_pct":100*float(group.decile.eq(1).mean())})
                metrics[feature]["top20_daily"] = selected
            report["horizons"][str(horizon)] = {"metrics":metrics,"excluded_dates":excluded,"qualified_decision_dates":len(labels)}
        else:
            report["horizons"][str(horizon)] = {"metrics":{},"excluded_dates":excluded,"qualified_decision_dates":0}
        save(output / "report.json",report)
    save(output / "report.json",report)
    print("Finished:",output / "report.json",flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("artifacts/research/analyst_archive_restore/20261010/directional"))
    parser.add_argument("--universe",type=Path,default=Path("config/univers_batch/univers_filtred_tradable.txt"))
    args = parser.parse_args()
    run(args.output,args.universe)
