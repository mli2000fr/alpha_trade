"""Exploratory frozen-feature check of prospective collections (SELECT only)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from scripts.research.us_prospective_directional_collection_audit import query

OUTPUT = Path("artifacts/research/us_prospective_directional_audit/20261010-v1")
START, END = "2026-09-10", "2026-10-10"
FEATURES = ["iv_call_minus_put", "oi_call_minus_put_log", "volume_call_minus_put_log",
            "news_net_mean", "news_count", "borrow_easy", "borrow_shortable"]


def local_day(series):
    return pd.to_datetime(series, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()


def directional_metrics(frame, feature):
    frame = frame.dropna(subset=[feature, "future_return"]).copy()
    extreme = frame[frame.decile.isin([1, 10])]
    daily = []
    for day, part in extreme.groupby("entry_date"):
        if part.decile.nunique() < 2 or part[feature].nunique() < 2 or len(part) < 20:
            continue
        daily.append({"entry_date": str(day.date()), "samples": len(part),
                      "auc": float(roc_auc_score(part.decile.eq(10), part[feature]))})
    auc = None
    if extreme.decile.nunique() == 2 and extreme[feature].nunique() > 1:
        auc = float(roc_auc_score(extreme.decile.eq(10), extreme[feature]))
    days = sorted(extreme.entry_date.unique())
    halves = []
    if len(days) >= 2:
        for name, subset_days in [("first_half", days[:len(days)//2]),
                                  ("second_half", days[len(days)//2:])]:
            part = extreme[extreme.entry_date.isin(subset_days)]
            value = float(roc_auc_score(part.decile.eq(10), part[feature])) if part.decile.nunique()==2 and part[feature].nunique()>1 else None
            halves.append({"name":name,"entry_dates":len(subset_days),"samples":len(part),"auc":value})
    return {
        "samples": len(frame), "symbols": int(frame.symbol.nunique()),
        "entry_dates": int(frame.entry_date.nunique()), "extreme_samples": len(extreme),
        "d10_count": int(extreme.decile.eq(10).sum()), "d1_count": int(extreme.decile.eq(1).sum()),
        "d10_mean_feature": float(extreme.loc[extreme.decile.eq(10), feature].mean()) if (extreme.decile == 10).any() else None,
        "d1_mean_feature": float(extreme.loc[extreme.decile.eq(1), feature].mean()) if (extreme.decile == 1).any() else None,
        "auc_pooled_exploratory": auc,
        "mean_daily_auc": float(np.mean([row["auc"] for row in daily])) if daily else None,
        "daily_auc": daily,
        "chronological_halves": halves,
        "verdict": "INSUFFICIENT_PROSPECTIVE_HISTORY_NO_PROMOTION",
    }


def run():
    inventory = json.loads((OUTPUT / "inventory.json").read_text(encoding="utf-8"))
    symbols = sorted(set(Path(inventory["universe"]).read_text(encoding="utf-8-sig").strip().split(",")))
    calendar = get_market_calendar("US_EQ", allow_us_weekday_fallback=False)
    session_dates = calendar.session_dates(date(2026, 9, 10), date(2026, 11, 10))
    sessions = pd.DatetimeIndex(session_dates)
    next_entry = {}
    for day in pd.date_range(START, END):
        candidates = sessions[sessions > day]
        if len(candidates):
            next_entry[day] = candidates[0]
    engine = get_sqlalchemy_engine()
    frames = []
    with engine.connect() as conn:
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        print("Loading qualified canonical daily bars", flush=True)
        bars = pd.DataFrame(query(conn, """SELECT symbol,date,open,high,low,close,volume,
            is_filled,data_source,data_adjustment FROM alpha_trade.stock_bars_daily
            WHERE symbol IN :symbols AND date>=:start AND date<:end""", symbols, start=START,end=END))
        bars["date"] = pd.to_datetime(bars.date)
        for col in ["open", "high", "low", "close", "volume"]:
            bars[col] = pd.to_numeric(bars[col],errors="coerce")
        qualified = (bars.is_filled.eq(0) & bars.open.gt(0) & bars.close.gt(0) & bars.volume.gt(0)
                     & bars.high.ge(bars[["open","close"]].max(axis=1))
                     & bars.low.le(bars[["open","close"]].min(axis=1))
                     & bars.data_adjustment.eq("split"))
        bars["valid"] = qualified
        closes = bars.pivot(index="date", columns="symbol", values="close")
        opens = bars.pivot(index="date", columns="symbol", values="open")
        valid = bars.pivot(index="date", columns="symbol", values="valid")
        print("Loading indicative options; pairing identical strike/expiry", flush=True)
        option = pd.DataFrame(query(conn, """SELECT underlying_symbol AS symbol, contract_symbol,
            expiration_date,strike,option_type,available_at,implied_volatility,open_interest
            FROM alpha_trade.stock_option_snapshots WHERE underlying_symbol IN :symbols
            AND available_at>=:start AND available_at<:end AND feed='indicative'""", symbols,start=START,end=END))
        option["day"] = local_day(option.available_at)
        option["expiration_date"] = pd.to_datetime(option.expiration_date)
        option["option_type"] = option.option_type.str.upper().replace({"C":"CALL","P":"PUT"})
        root = option.contract_symbol.str.replace(r"\d{6}[CP]\d{8}$", "", regex=True)
        option = option[root.eq(option.symbol.str.replace(".","",regex=False))]
        option = option.sort_values("available_at").drop_duplicates(["day","symbol","contract_symbol"],keep="last")
        daily_price = bars[["date","symbol","close"]].rename(columns={"date":"day","close":"spot"})
        option = option.merge(daily_price,on=["day","symbol"],how="inner")
        option["dte"] = (option.expiration_date-option.day).dt.days
        option["moneyness_distance"] = (option.strike/option.spot-1).abs()
        option = option[option.dte.between(15,25) & option.moneyness_distance.le(.05)]
        keys = ["day","symbol","expiration_date","strike"]
        pairs = option[option.option_type.eq("CALL")].merge(option[option.option_type.eq("PUT")],on=keys,suffixes=("_call","_put"))
        pairs["tenor_distance"] = (pairs.dte_call-20).abs()
        pairs = pairs.sort_values(["day","symbol","tenor_distance","moneyness_distance_call","strike"]).drop_duplicates(["day","symbol"])
        pairs["available_at"] = pairs[["available_at_call","available_at_put"]].max(axis=1)
        pairs["iv_call_minus_put"] = pairs.implied_volatility_call.where(pairs.implied_volatility_call.gt(0)) - pairs.implied_volatility_put.where(pairs.implied_volatility_put.gt(0))
        pairs["oi_call_minus_put_log"] = np.log1p(pairs.open_interest_call.where(pairs.open_interest_call.ge(0))) - np.log1p(pairs.open_interest_put.where(pairs.open_interest_put.ge(0)))
        frames.append(pairs[["day","symbol","available_at","iv_call_minus_put","oi_call_minus_put_log"]])
        print("Loading delayed option volumes",flush=True)
        flow = pd.DataFrame(query(conn,"""SELECT underlying_symbol AS symbol,contract_symbol,
            expiration_date,option_type,bar_timestamp,available_at,volume
            FROM alpha_trade.stock_option_bars_delayed WHERE underlying_symbol IN :symbols
            AND available_at>=:start AND available_at<:end""",symbols,start=START,end=END))
        flow["day"] = local_day(flow.bar_timestamp)
        root = flow.contract_symbol.str.replace(r"\d{6}[CP]\d{8}$", "", regex=True)
        flow = flow[root.eq(flow.symbol.str.replace(".","",regex=False))]
        flow["available_day"] = local_day(flow.available_at)
        flow = flow[flow.day.eq(flow.available_day)].sort_values("available_at").drop_duplicates(["contract_symbol","bar_timestamp"],keep="last")
        flow["expiration_date"] = pd.to_datetime(flow.expiration_date)
        flow["tenor_distance"] = ((flow.expiration_date-flow.day).dt.days-20).abs()
        flow = flow[flow.tenor_distance.le(5)]
        flow["option_type"] = flow.option_type.str.upper().replace({"C":"CALL","P":"PUT"})
        flow = flow.groupby(["day","symbol","expiration_date","option_type"],as_index=False).agg(volume=("volume","sum"),available_at=("available_at","max"),tenor_distance=("tenor_distance","first"))
        fpair = flow[flow.option_type.eq("CALL")].merge(flow[flow.option_type.eq("PUT")],on=["day","symbol","expiration_date"],suffixes=("_call","_put"))
        fpair = fpair.sort_values(["day","symbol","tenor_distance_call","expiration_date"]).drop_duplicates(["day","symbol"])
        fpair["available_at"] = fpair[["available_at_call","available_at_put"]].max(axis=1)
        fpair["volume_call_minus_put_log"] = np.log1p(fpair.volume_call)-np.log1p(fpair.volume_put)
        frames.append(fpair[["day","symbol","available_at","volume_call_minus_put_log"]])
        print("Loading actual news sentiment timestamps",flush=True)
        news = pd.DataFrame(query(conn,"""SELECT nts.symbol,nr.effective_trade_date AS day,
            nts.sentiment_net_score,nr.published_at_utc,
            GREATEST(nr.updated_at,nts.updated_at) AS available_at
            FROM alpha_trade.news_ticker_sentiment nts JOIN alpha_trade.news_raw nr ON nr.article_id=nts.article_id
            WHERE nts.symbol IN :symbols AND nr.effective_trade_date>=:start
            AND nr.effective_trade_date<:end AND nts.inference_status='success'""",symbols,start=START,end=END))
        news["day"] = pd.to_datetime(news.day)
        news["entry_date"] = news.day.map(next_entry)
        cutoff = {day:pd.Timestamp(calendar.session_bounds(day.date())[0])-pd.Timedelta(minutes=5) for day in news.entry_date.dropna().unique()}
        news["cutoff"] = pd.to_datetime(news.entry_date.map(cutoff),utc=True)
        news = news[pd.to_datetime(news.available_at,utc=True).lt(news.cutoff) & pd.to_datetime(news.published_at_utc,utc=True).lt(news.cutoff)]
        nday = news.groupby(["day","symbol"],as_index=False).agg(news_net_mean=("sentiment_net_score","mean"),news_count=("sentiment_net_score","size"),available_at=("available_at","max"))
        frames.append(nday)
        print("Loading borrow availability (not lending fees)",flush=True)
        borrow = pd.DataFrame(query(conn,"""SELECT symbol,available_at,easy_to_borrow,shortable
            FROM alpha_trade.stock_borrow_status_snapshots WHERE symbol IN :symbols
            AND available_at>=:start AND available_at<:end""",symbols,start=START,end=END))
        borrow["day"] = local_day(borrow.available_at)
        borrow = borrow.sort_values("available_at").drop_duplicates(["day","symbol"],keep="last")
        borrow = borrow.rename(columns={"easy_to_borrow":"borrow_easy","shortable":"borrow_shortable"})
        frames.append(borrow[["day","symbol","available_at","borrow_easy","borrow_shortable"]])
        conn.rollback()
    engine.dispose()
    all_features = []
    for frame in frames:
        frame=frame.copy()
        frame["entry_date"] = frame.day.map(next_entry)
        frame["available_at"] = pd.to_datetime(frame.available_at,utc=True)
        cutoff = {day:pd.Timestamp(calendar.session_bounds(day.date())[0])-pd.Timedelta(minutes=5) for day in frame.entry_date.dropna().unique()}
        frame = frame[frame.available_at.lt(pd.to_datetime(frame.entry_date.map(cutoff),utc=True))]
        all_features.append(frame)
    features = all_features[0].drop(columns=["available_at"])
    for frame in all_features[1:]:
        features=features.merge(frame.drop(columns=["available_at"]),on=["day","symbol","entry_date"],how="outer",validate="one_to_one")
    features.to_parquet(OUTPUT / "prospective_features.parquet",index=False)
    report = {
        "status":"COMPLETED_EXPLORATORY_ONLY", "universe_count":len(symbols),
        "protocol":{"decision":"09:25 NY next session after local observation day", "entry":"next-session open", "exit":"close of Hth session including entry session",
            "options_pair":"same strike and expiration; |moneyness-1|<=5%; nearest 20 calendar DTE within 15..25",
            "features":FEATURES,"horizons":[3,5,10,20],"label_deciles":"full price-qualified current file universe, signed realized return; stable symbol tie-break",
            "minimum_price_coverage":.90,"models_trained":False,"sql_writes":False},
        "field_coverage":{feature:{"symbol_days":int(features[feature].notna().sum()),"symbols":int(features.loc[features[feature].notna(),"symbol"].nunique())} for feature in FEATURES},
        "news_articles_before_conservative_cutoff":len(news),
        "horizons":{},"last_bar_date":str(bars.date.max().date()),
        "limitations":["Current universe, not historical survivorship-free universe",
            "Canonical split-adjusted prices, not independently qualified total returns; no corporate-action cash or execution costs",
            "Overlapping short horizons and few independent dates: no validated directional advantage, no threshold fitting or strategy promotion",
            "No sector/size neutralization; availability timestamp does not independently certify provider freshness, IV or open interest accuracy",
            "Indicative quotes and unverified OPRA bars are research data only; call/put volume is not signed order flow",
            "Latest-update cutoff excludes overwritten historical news scores conservatively; no reconstruction of unavailable earlier versions",
            "No analysis of families currently suspended for rights/prudence", "Borrow status is primarily execution feasibility, not short interest or borrow fees"],
    }
    for horizon in [3,5,10,20]:
        targets=[]
        eligible_dates=[]
        for entry in sorted(features.entry_date.dropna().unique()):
            start=sessions.get_loc(entry)
            exit_date=sessions[start+horizon-1]
            if exit_date>bars.date.max():continue
            path=sessions[start:start+horizon]
            good=valid.reindex(path).eq(True).all(axis=0)
            returns=closes.reindex([exit_date]).iloc[0]/opens.reindex([entry]).iloc[0]-1
            returns=returns[good & np.isfinite(returns)]
            if len(returns)<len(symbols)*.90:continue
            target=returns.rename("future_return").reset_index()
            target=target.sort_values(["future_return","symbol"],kind="stable")
            target["decile"]=(np.floor(np.arange(len(target))*10/len(target))+1).astype(int)
            target["entry_date"]=entry
            targets.append(target)
            eligible_dates.append(str(entry.date()))
        if not targets:
            report["horizons"][str(horizon)]={"mature_entry_dates":0,"verdict":"NO_MATURE_PROSPECTIVE_LABELS"}
            continue
        target=pd.concat(targets,ignore_index=True)
        joined=features.merge(target,on=["entry_date","symbol"],how="inner",validate="many_to_one")
        joined.to_parquet(OUTPUT/f"feature_outcome_pairs_h{horizon}.parquet",index=False)
        report["horizons"][str(horizon)]={"mature_entry_dates":len(eligible_dates),"entry_dates":eligible_dates,
            "features":{feature:directional_metrics(joined,feature) for feature in FEATURES}}
    (OUTPUT/"directional_report.json").write_text(json.dumps(report,indent=2,allow_nan=False,default=str),encoding="utf-8")
    print(json.dumps({"status":report["status"],"output":str(OUTPUT),
        "horizons":{h:{f:{k:value.get(k) for k in ["samples","entry_dates","auc_pooled_exploratory","mean_daily_auc"]}
        for f,value in result.get("features",{}).items()} for h,result in report["horizons"].items()}},default=str),flush=True)
    return report


if __name__=="__main__":
    run()
