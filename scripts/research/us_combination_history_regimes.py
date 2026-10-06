"""Frozen M/V/MV across 2019-2025; research only, no SQL writes or training."""
import argparse
import gc
import hashlib
import json
import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.build_labels import build_labels
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.extreme_gate import compute_extreme_gate
from scripts.research.us_feature_combination_d10 import metrics, pick
from scripts.research.us_intersection_sentiment_deciles import ROOT

BATCH = "model-factory-20261003082853-e98332"
DEST = ROOT / "combination-history-2019-2025-20261004-v1"
CHAMP = Path("artifacts/models/oracle/champions") / BATCH


def historical_scores(frame, champions, model_root=CHAMP):
    data = frame.copy()
    data["proba_extreme"] = np.nan
    data["fold_used"] = None
    evidence = []
    dates = pd.to_datetime(data.date)
    ordered = sorted(champions, key=lambda x:x["t_start"])
    for i, item in enumerate(ordered):
        start = pd.Timestamp(item["t_start"])
        end = pd.Timestamp(ordered[i+1]["t_start"]) if i+1<len(ordered) else pd.Timestamp.max
        mask = dates.ge(start) & dates.lt(end)
        if not mask.any():
            continue
        model = lgb.Booster(model_file=str(model_root / item["model_file"]))
        cols = item["feature_columns"]
        if set(cols)-set(data):
            raise ValueError("Missing trained columns")
        data.loc[mask,"proba_extreme"] = model.predict(data.loc[mask,cols].astype(float), num_threads=4)
        data.loc[mask,"fold_used"] = item["t_start"]
        evidence.append({"fold":item["t_start"],"first":str(dates[mask].min().date()),
                         "last":str(dates[mask].max().date()),"rows":int(mask.sum()),
                         "model_sha256":hashlib.sha256((model_root/item["model_file"]).read_bytes()).hexdigest()})
        logging.info("PREDICT fold=%s rows=%d",item["t_start"],mask.sum())
    return data, evidence


def scores(pool):
    data = pool.copy()
    ranks = data[["momentum_120","rolling_volatility_60","atr20_pct"]].groupby(data.date).rank(pct=True)
    data["M"] = ranks.momentum_120.fillna(.5)
    data["V"] = (ranks.rolling_volatility_60.fillna(.5)+ranks.atr20_pct.fillna(.5))/2
    data["MV"] = (data.M+data.V)/2
    return data


def evaluate(data):
    return {"overall":metrics(data),
            "months":{str(month):metrics(group) for month,group in data.groupby(data.date.dt.to_period("M"))},
            "semesters":{str(half):metrics(group) for half,group in data.groupby(
                data.date.dt.year.astype(str)+"H"+np.where(data.date.dt.month.le(6),"1","2"))}}


def main():
    global DEST
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year",type=int,default=2019)
    parser.add_argument("--end-year",type=int,default=2025)
    parser.add_argument("--end-date",default=None)
    parser.add_argument("--output",type=Path,default=DEST)
    args=parser.parse_args()
    DEST=args.output
    if args.start_year>args.end_year:
        parser.error("Invalid year range")
    final_date=args.end_date or f"{args.end_year}-12-31"
    if pd.Timestamp(final_date).year!=args.end_year:
        parser.error("End date must belong to end-year")
    DEST.mkdir(parents=True,exist_ok=True)
    def progress(phase,**values):
        logging.info("PHASE=%s %s",phase,values)
        (DEST/"progress.json").write_text(json.dumps({"phase":phase,**values}),encoding="utf-8")
    champions = json.loads((CHAMP/"oracle_champions.json").read_text())
    options = json.loads((CHAMP/"feature_profile.json").read_text())["generator_options"]
    windows = pd.read_parquet(ROOT/"audit-20261004-v1/symbol_day_windows.parquet")
    symbols = sorted(windows.symbol.unique())
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT DATABASE()")).scalar()!="alpha_trade":
            raise ValueError("US database required")
        # Modern sector snapshot used for descriptive context ONLY.
        sectors = pd.read_sql(text("SELECT symbol,sector FROM stock_metadata"),conn).drop_duplicates("symbol")
    yearly = {}
    all_selected = []
    keep = ["date","symbol","proba_extreme","fold_used","atr20_pct","momentum_120",
            "rolling_volatility_60","market_return_20","market_volatility_20",
            "market_trend_strength_50","regime_bull_market","regime_risk_off","beta_252"]
    for year in range(args.start_year,args.end_year+1):
        year_end=final_date if year==args.end_year else f"{year}-12-31"
        folder = DEST/str(year)
        folder.mkdir(exist_ok=True)
        panel_path=folder/"panel.parquet"
        labels_path=folder/"labels.parquet"
        if panel_path.exists():
            frame=pd.read_parquet(panel_path)
        elif year==2025:
            progress("REUSE_2025",year=year)
            feats=pd.read_parquet(ROOT/"feature-separation-20261004-v1/features.parquet")
            orig=pd.read_parquet(ROOT/"audit-20261004-v1/oracle_atr_panel.parquet")
            frame=orig[["date","symbol","proba_extreme"]].merge(feats,on=["date","symbol"],validate="one_to_one")
            frame["fold_used"]="2024-01-08"
            frame=frame[keep]
            frame.to_parquet(panel_path,index=False)
        else:
            progress("BUILD_FEATURES",year=year,symbols=len(symbols))
            frame=build_feature_matrix(engine,symbols,start_date=f"{year}-01-01",end_date=year_end,generator_options=options)
            frame["date"]=pd.to_datetime(frame.date)
            frame=frame[frame.date.between(f"{year}-01-01",year_end)].copy()
            if frame.duplicated(["date","symbol"]).any():
                raise ValueError("Duplicate features")
            progress("PREDICT_CAUSAL_FOLDS",year=year,rows=len(frame))
            frame,evidence=historical_scores(frame,champions)
            (folder/"fold_evidence.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
            frame=frame[keep]
            frame.to_parquet(panel_path,index=False)
            gc.collect()
        if not labels_path.exists():
            if year==2025:
                labels=pd.read_parquet(ROOT/"intersection-realized-20261004-v1/native_realized_labels.parquet")
                labels.to_parquet(labels_path,index=False)
            else:
                progress("NATIVE_LABELS_READ_ONLY",year=year)
                status=build_labels(BATCH,horizon=20,start_date=f"{year}-01-01",end_date=year_end,engine=engine,
                                    dry_run=True,symbols=symbols,output_parquet=str(labels_path),
                                    progress_callback=lambda n,total,message:logging.info("LABELS %s %d/%d",message,n,total))
                if status.get("status")!="dry_run":
                    raise ValueError(f"Label build failed {status}")
        labels=pd.read_parquet(labels_path).rename(columns={"prediction_date":"date"})
        labels["date"]=pd.to_datetime(labels.date)
        progress("COMBINATION",year=year)
        gate=compute_extreme_gate(frame.dropna(subset=["proba_extreme","atr20_pct"]))
        gate["atr_top20"]=gate.groupby("date").atr20_pct.rank(pct=True).ge(.8)
        pool=scores(gate[gate.extreme_gate & gate.atr_top20])
        policies={"POOL":pool,"ORACLE":gate[gate.extreme_gate],
                  **{f"{name}_TOP{int(f*100)}":pick(pool,name,f) for name in ["M","V","MV"] for f in [.1,.2]}}
        results={}
        for name,selected in policies.items():
            selected=selected.merge(labels[["date","symbol","oracle_decile","future_return","target_quality_valid"]],
                                    on=["date","symbol"],how="left",validate="one_to_one")
            results[name]=evaluate(selected)
            if name=="MV_TOP10":
                all_selected.append(selected)
        yearly[str(year)]=results
        (folder/"report.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
        progress("YEAR_COMPLETED",year=year,mean_return=results["MV_TOP10"]["overall"]["mean_return_pct"])
        del frame,gate,pool,labels
        gc.collect()
    selected=pd.concat(all_selected,ignore_index=True).merge(sectors,on="symbol",how="left",validate="many_to_one")
    selected.to_parquet(DEST/"mv_top10_all_years.parquet",index=False)
    diagnostics={}
    for month,group in selected.groupby(selected.date.dt.to_period("M")):
        valid=group[group.target_quality_valid.eq(1)&group.future_return.notna()]
        if valid.empty:
            continue
        contributions=valid.groupby("symbol").agg(count=("future_return","size"),mean_return=("future_return","mean"),sum_return=("future_return","sum"))
        diagnostics[str(month)]={"metrics":metrics(group),
            "context_means":{c:float(valid.groupby("date")[c].mean().mean()) for c in
                             ["market_return_20","market_volatility_20","market_trend_strength_50","regime_bull_market","regime_risk_off","momentum_120","rolling_volatility_60","atr20_pct","beta_252"]},
            "top5_symbol_share":float(valid.symbol.value_counts().head(5).sum()/len(valid)),
            "worst10_symbols":contributions.sort_values("sum_return").head(10).reset_index().to_dict("records"),
            "sectors_current_non_pit":valid.groupby(valid.sector.fillna("UNKNOWN")).agg(count=("future_return","size"),mean_return=("future_return","mean")).reset_index().to_dict("records")}
    report={"status":"COMPLETED_DESCRIPTIVE_HISTORICAL","start_year":args.start_year,
            "end_date":final_date,"batch":BATCH,"yearly":yearly,
            "monthly_diagnostics":diagnostics,
            "notes":["2019-2024 last champion with fold_start <= date; native labels dry-run",
                     "2025 already explored; static current universe survivorship reserve",
                     "No fit/tuning/SQL writes, cost or portfolio simulation",
                     "Monthly regimes are explanatory associations, not validated predictive vetoes",
                     "Current sector metadata non-PIT; missing macro cannot be inferred neutral",
                     "closeJ-closeJ+20 overlapping observations; no independent statistical confirmation"]}
    (DEST/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    progress("COMPLETED",years=args.end_year-args.start_year+1)
    print("COMPLETED",DEST)


if __name__=="__main__":
    logging.basicConfig(level=logging.INFO)
    main()
