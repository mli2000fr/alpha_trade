"""Offline descriptive attribution: regimes/sectors/symbols/folds, no tuning."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def group_metrics(frame,keys):
    rows = []
    for group,part in frame.groupby(keys,dropna=False):
        values = group if isinstance(group,tuple) else (group,)
        row = dict(zip(keys,map(str,values)))
        valid = part.loc[part.target_quality_valid.eq(1) & part.local_endpoint_ok.eq(True)
                         & np.isfinite(part.future_return)]
        row.update(count=len(part),qualified=len(valid),days=int(part.date.nunique()))
        if len(valid):
            row.update(d1_pct=100*float(valid.oracle_decile.eq(1).mean()),
                       d10_pct=100*float(valid.oracle_decile.eq(10).mean()),
                       positive_pct=100*float(valid.future_return.gt(0).mean()),
                       mean_return_pct=100*float(valid.future_return.mean()),
                       mean_abs_return_pct=100*float(valid.future_return.abs().mean()))
        rows.append(row)
    return rows


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    atomic_json(output/'progress.json',dict(status='RUNNING'))
    root = Path('artifacts/research/us_extreme50_capture/audit-20261006-v1')
    panels = [root/str(y)/'panel.parquet' for y in (2023,2024)]
    sector_path = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
    champions = Path('artifacts/models/oracle/champions/model-factory-20261003082853-e98332/oracle_champions.json')
    files = panels+[sector_path,champions]+[source/p for p in ['bars.parquet','macro.parquet',
         'baseline/regimes.json','baseline/trades.parquet','baseline/daily.parquet']]
    atomic_json(output/'protocol.json',dict(sources={str(p):digest(p) for p in files},
        sql_reads=False,sql_writes=False,training=False,threshold_search=False,
        caveats=['Regime/fold/sector comparisons are observational, not causal',
            'Current sectors and universe NON-PIT','Overlapping H20 labels, not independent observations',
            'Macro values not publication-vintage certified',
            'fold_start not full train/validation/calibration lineage',
            'No veto promoted and no economic replay of hypothetical exclusions']))
    data = pd.concat([pd.read_parquet(p) for p in panels],ignore_index=True)
    data = data.loc[data.ORACLE_TOP10].copy()
    data['date'] = pd.to_datetime(data.date)
    data['year'] = data.date.dt.year
    data['month'] = data.date.dt.to_period('M').astype(str)
    data['semester'] = data.year.astype(str)+'H'+np.where(data.date.dt.month.le(6),'1','2')
    sectors = pd.read_parquet(sector_path)[['symbol','sector']]
    data = data.merge(sectors,on='symbol',how='left',validate='many_to_one')
    data['sector'] = data.sector.fillna('UNKNOWN_NON_PIT')
    regimes = pd.DataFrame(json.loads((source/'baseline/regimes.json').read_text()))
    regimes['date'] = pd.to_datetime(regimes.date)
    data = data.merge(regimes[['date','mode','allow_long','spy_regime']],on='date',validate='many_to_one')
    macro = pd.read_parquet(source/'macro.parquet')
    macro['date'] = pd.to_datetime(macro.trade_date)
    columns = ['vix','vix9d','vxn','vix3m','move','ten_y','yield_10y_5d_pct','sentiment_score']
    data = data.merge(macro[['date']+columns],on='date',how='left',validate='many_to_one')
    data['fold_age_calendar_days'] = (data.date-pd.to_datetime(data.fold_start)).dt.days
    data.to_parquet(output/'context-panel.parquet',index=False)
    groups = {}
    for keys in [['year'],['month'],['semester'],['year','sector'],['year','spy_regime'],
                 ['year','mode'],['fold_start'],['fold_start','semester']]:
        groups['_'.join(keys)] = group_metrics(data,keys)
    atomic_json(output/'candidate-groups.json',groups)
    concentrations = []
    for year,part in data.groupby('year'):
        weights = part.symbol.value_counts(normalize=True)
        concentrations.append(dict(year=int(year),unique_symbols=int(part.symbol.nunique()),
            top10_occurrence_share_pct=100*float(weights.head(10).sum()),
            hhi=float((weights**2).sum()),top_symbols=part.symbol.value_counts().head(15).to_dict()))
    atomic_json(output/'concentration.json',concentrations)
    # Reweight within-sector rates to 2023 composition on common sectors only.
    sg = pd.DataFrame(groups['year_sector'])
    common = set(sg.loc[sg.year.eq('2023'),'sector']) & set(sg.loc[sg.year.eq('2024'),'sector'])
    s23 = sg.loc[sg.year.eq('2023') & sg.sector.isin(common)].set_index('sector')
    s24 = sg.loc[sg.year.eq('2024') & sg.sector.isin(common)].set_index('sector').reindex(s23.index)
    weights = s23['qualified']/s23['qualified'].sum()
    standardized = {key:dict(reference_2023=float((weights*s23[key]).sum()),
        standardized_2024=float((weights*s24[key]).sum())) for key in ['d1_pct','d10_pct','mean_return_pct']}
    standardized['common_sector_counts'] = {y:int(sg.loc[sg.year.eq(y) & sg.sector.isin(common),'count'].sum()) for y in ['2023','2024']}
    atomic_json(output/'sector-standardization.json',standardized)
    coverage = []
    for year,part in data.drop_duplicates('date').groupby('year'):
        coverage.append(dict(year=int(year),days=len(part),fields={c:dict(known=int(part[c].notna().sum()),
            median=float(part[c].median()) if part[c].notna().any() else None) for c in columns}))
    atomic_json(output/'macro-coverage.json',coverage)
    trades = pd.read_parquet(source/'baseline/trades.parquet')
    trades['date'] = pd.to_datetime(trades.signal_date)
    trades = trades.merge(regimes[['date','mode','spy_regime']],on='date',how='left',validate='many_to_one')
    trades['exit_year'] = pd.to_datetime(trades.exit_date).dt.year
    attribution = {}
    for keys in [['exit_year','sector'],['exit_year','spy_regime'],['exit_year','mode'],['exit_year','symbol']]:
        rows = []
        for group,part in trades.groupby(keys,dropna=False):
            values = group if isinstance(group,tuple) else (group,)
            rows.append(dict(zip(keys,map(str,values))) | dict(count=len(part),pnl=float(part.pnl.sum()),
                win_rate_pct=100*float(part.pnl.gt(0).mean())))
        attribution['_'.join(keys)] = rows
    atomic_json(output/'trade-attribution.json',attribution)
    champion_dates = [x['t_start'] for x in json.loads(champions.read_text())]
    atomic_json(output/'report.json',dict(status='COMPLETED_DESCRIPTIVE_ONLY',
        years=groups['year'],semesters=groups['semester'],sector_standardization=standardized,
        concentration=concentrations,champion_start_dates=champion_dates,
        last_champion=champion_dates[-1],no_champion_refresh_in_2024_h2=not any(d>='2024-07-01' for d in champion_dates),
        conclusion='No causal or predictive regime veto established; OOF/provenance and macro PIT reserves remain'))
    atomic_json(output/'progress.json',dict(status='COMPLETED'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('artifacts/research/us_concentrated_replay/top10-early-weakness-2023-2024-20261007-v1'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    run(args.source,args.output)
