"""Explanatory regime audit, no tuning, no fit, no SQL writes."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.features import _build_adjusted_price_frame
from scripts.research.us_intersection_sentiment_deciles import ROOT

DEST=ROOT/"combination-regime-review-20261004-v1"


def spy_context(bars):
    data=bars.sort_values("date").reset_index(drop=True).copy()
    if data.duplicated("date").any():
        raise ValueError("Multiple SPY bars per date")
    close=_build_adjusted_price_frame(data).close
    returns=close.pct_change(fill_method=None)
    for period in [5,20,60]:
        data[f"spy_ret{period}"]=close/close.shift(period)-1
    data["spy_dist200"]=close/close.rolling(200,min_periods=200).mean()-1
    data["spy_vol20"]=returns.rolling(20,min_periods=20).std()
    data["spy_dd252"]=close/close.rolling(252,min_periods=252).max()-1
    data["spy_future_h20_expost"]=close.shift(-20)/close-1
    return data[["date"]+[c for c in data if c.startswith("spy_")]]


def associations(monthly, keys, scope):
    output=[]
    for feature in keys:
        valid=monthly.dropna(subset=[feature,"d10_pct","mean_return_pct"])
        if len(valid)<6 or valid[feature].nunique()<2:
            continue
        output.append({"feature":feature,"months":len(valid),
                       "rho_d10":float(spearmanr(valid[feature],valid.d10_pct).statistic),
                       "rho_return":float(spearmanr(valid[feature],valid.mean_return_pct).statistic),
                       "scope":scope})
    return sorted(output,key=lambda x:abs(x["rho_return"]),reverse=True)


def main():
    histories=[ROOT/"combination-history-2019-2025-20261004-v1",ROOT/"combination-history-2026q1-20261004-v1"]
    reports=[json.loads((root/"report.json").read_text()) for root in histories]
    selected=pd.concat([pd.read_parquet(root/"mv_top10_all_years.parquet") for root in histories],ignore_index=True)
    if selected.duplicated(["symbol","date"]).any():
        raise ValueError("Duplicate historical selection")
    engine=get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT DATABASE()")).scalar()!="alpha_trade":
            raise ValueError("US database required")
        spy=pd.read_sql(text("SELECT date,close,adj_close,data_source FROM stock_bars_daily "
                             "WHERE symbol='SPY' AND date BETWEEN '2017-01-01' AND '2026-05-15'"),conn)
        macro=pd.read_sql(text("SELECT trade_date AS date,vix,vxn,vix3m,move,ten_y,mode,created_at,updated_at "
                               "FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2018-01-01' AND '2026-03-31'"),conn)
    spy["date"]=pd.to_datetime(spy.date)
    macro["date"]=pd.to_datetime(macro.date)
    if macro.duplicated("date").any():
        raise ValueError("Duplicate macro dates")
    if set(spy.data_source.unique())!={"eodhd_eod"}:
        raise ValueError("Unexpected SPY source")
    context=spy_context(spy).merge(macro,on="date",how="left",validate="one_to_one").sort_values("date")
    context["vix_curve_ratio"]=context.vix/context.vix3m.replace(0,np.nan)
    context["ten_y_change20"]=context.ten_y-context.ten_y.shift(20)
    selected=selected.merge(context,on="date",how="left",validate="many_to_one")
    selected["month"]=selected.date.dt.to_period("M").astype(str)
    selected=selected[selected.target_quality_valid.eq(1)&selected.future_return.notna()].copy()
    keys=["spy_ret5","spy_ret20","spy_ret60","spy_dist200","spy_vol20","spy_dd252", "vix","vxn","vix3m","move","ten_y","ten_y_change20","vix_curve_ratio",
          "momentum_120","rolling_volatility_60","atr20_pct","top5_share"]
    month_rows=[]
    sector_tables={}
    for month, group in selected.groupby("month"):
        year=month[:4]
        report=reports[0] if year!="2026" else reports[1]
        result=report["yearly"][year]["MV_TOP10"]["months"][month]
        row={"month":month,**result,
             "pool_return":report["yearly"][year]["POOL"]["months"][month]["mean_return_pct"],
             "top5_share":float(group.symbol.value_counts().head(5).sum()/len(group)),
             "spy_future_h20_expost":float(group.groupby("date").spy_future_h20_expost.mean().mean())}
        for feature in keys:
            if feature in group:
                row[feature]=float(group.groupby("date")[feature].mean().mean())
        for col in ["vix","vxn","vix3m","move","ten_y"]:
            row[f"{col}_coverage"]=float(group.groupby("date")[col].first().notna().mean())
        row["native_beta_unique"]=int(group.beta_252.nunique())
        month_rows.append(row)
        sector=group.groupby(group.sector.fillna("UNKNOWN")).agg(n=("future_return","size"),mean_return=("future_return","mean"))
        sector["d10_pct"]=group.oracle_decile.eq(10).groupby(group.sector.fillna("UNKNOWN")).mean()*100
        sector["d1_pct"]=group.oracle_decile.eq(1).groupby(group.sector.fillna("UNKNOWN")).mean()*100
        sector["share"]=sector.n/len(group)
        sector["contribution_mean_return_pct"]=sector.share*sector.mean_return*100
        sector_tables[month]=sector.reset_index().sort_values("contribution_mean_return_pct").to_dict("records")
    monthly=pd.DataFrame(month_rows).sort_values("month")
    # Simple fixed observable states: descriptive stratifications, NOT calibrated vetoes.
    daily=selected.groupby("date").agg(n=("future_return","size"),ret=("future_return","mean"))
    daily["d10"]=selected.oracle_decile.eq(10).groupby(selected.date).mean()
    daily["d1"]=selected.oracle_decile.eq(1).groupby(selected.date).mean()
    daily=daily.merge(context,on="date",how="left",validate="one_to_one")
    states={"SPY_BELOW_SMA200":daily.spy_dist200.lt(0),"SPY_ABOVE_SMA200":daily.spy_dist200.gt(0),
            "SPY_RET20_NEGATIVE":daily.spy_ret20.lt(0),"SPY_RET20_POSITIVE":daily.spy_ret20.gt(0),
            "VIX_GE20":daily.vix.ge(20),"VIX_LT20":daily.vix.lt(20)}
    state_stats={}
    for name,mask in states.items():
        data=daily[mask]
        state_stats[name]={"days":len(data),"mean_return_daily_pct":float(data.ret.mean()*100),
                           "d10_daily_pct":float(data.d10.mean()*100),"d1_daily_pct":float(data.d1.mean()*100)}
    assoc={scope:associations(monthly[mask],keys,scope) for scope,mask in
           [("2019_2023",monthly.month.lt("2024")),("2024_2025",monthly.month.ge("2024")&monthly.month.lt("2026")),
            ("2026Q1",monthly.month.ge("2026")),("ALL_EXPLORATORY",pd.Series(True,index=monthly.index))]}
    coverage={str(year):{col:float(group.groupby("date")[col].first().notna().mean()) for col in
                        ["vix","vxn","vix3m","move","ten_y"]} for year,group in selected.groupby(selected.date.dt.year)}
    result={"status":"COMPLETED_EXPLANATORY_NOT_PREDICTIVE_VETO","years":{year:rows for report in reports for year,rows in report["yearly"].items()},
            "months":monthly.replace({np.nan:None}).to_dict("records"),"negative_months":monthly[monthly.mean_return_pct.lt(0)].month.tolist(),
            "macro_coverage":coverage,"associations":assoc,"states":state_stats,"sectors_current_non_pit":sector_tables,
            "notes":["Regime features at J only; future SPY return labeled ex-post and excluded from predictive correlations",
                     "Pooled monthly correlations explanatory, post-hoc multiple comparisons, no significance claim",
                     "Monthly averages contain information from later days in month: not available at first day of month",
                     "Macro current table created_at/updated_at not reliable economic publication timestamps or vintages",
                     "2026 vix missing: no zero/forward-fill substituted; VIX states exclude absent observations",
                     "Native beta often constant/default=1; do not infer measured market exposure from those years",
                     "Current sector tags descriptive only, no historical taxonomy certification",
                     "Static current universe, selection and overlapping returns; no fit/SQL/portfolio/costs",
                     "2019-2024 retrospective extension; 2025 feature-selection period, 2026 already inspected"]}
    DEST.mkdir(parents=True,exist_ok=False)
    monthly.to_parquet(DEST/"monthly_diagnostics.parquet",index=False)
    daily.to_parquet(DEST/"daily_regimes.parquet",index=False)
    context.to_parquet(DEST/"market_macro_context.parquet",index=False)
    (DEST/"report.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    print("NEGATIVE",len(result["negative_months"]),"TOTAL",len(monthly))
    print("CORRELATIONS",json.dumps({k:v[:6] for k,v in assoc.items()}))
    print("STATES",json.dumps(state_stats))
    print("WORST",monthly.sort_values("mean_return_pct").head(12)[["month","d10_pct","d1_pct","mean_return_pct","spy_ret20","spy_dist200","vix","spy_future_h20_expost"]].to_string(index=False))
    for month in ["2025-02","2026-01","2026-02","2026-03","2024-07","2021-11"]:
        print("SECTORS",month,sector_tables[month][:4])


if __name__=="__main__":
    main()
