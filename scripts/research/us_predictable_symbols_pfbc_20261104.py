"""Documented, identity-only input correction: Preferred Bank is common stock.

Extend the frozen per-symbol audit by this one title; never refit or retune the
other stocks, overwrite their models, or change the two empty intersections.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import time

import pandas as pd
from sqlalchemy import text

import scripts.research.us_predictable_symbols_20261103 as m
from scripts.research.us_predictable_symbols_review_20261104 import check_2026,summarize
from scripts.operations import build_ordinary_shares_inventory_20261103 as ordinary


def main():
    started=time.monotonic();out=m.OUT;before=out/'before-pfbc-correction'
    integrity=json.loads((out/'integrity-review.json').read_text())
    assert integrity['status']=='PASS'
    assert not (out/'scope-amendment-pfbc.json').exists()
    protocol=json.loads((out/'protocol.json').read_text())
    source_key=next(k for k in protocol['source_hashes'] if k.replace('\\','/')=='config/univers_batch/action_ordinaire.txt')
    oldsymbols=sorted(set(m.SOURCE.read_text().strip().split(',')))
    assert m.digest(m.SOURCE)==protocol['source_hashes'][source_key]
    before.mkdir(exist_ok=False);(before/'action_ordinaire.txt').write_bytes(m.SOURCE.read_bytes())
    old_report=json.loads((out/'report.json').read_text())
    for name in ['report.json','progress.json','check-2026-summary.json','check-2026-per-symbol.csv','source-reliability-gates.parquet']:
        (before/name).write_bytes((out/name).read_bytes())
    classification_backup=ordinary.AUDIT/'before-pfbc-correction';classification_backup.mkdir(exist_ok=False)
    for name in ['classification.json','report.json','verification.json','README.md']:
        (classification_backup/name).write_bytes((ordinary.AUDIT/name).read_bytes())
    ordinary.main(write=False)
    decisions=json.loads((ordinary.AUDIT/'classification.json').read_text(encoding='utf-8'))
    proposed={x['symbol'] for x in decisions if x['status']=='INCLUDE_ORDINARY'}
    assert proposed==set(oldsymbols)|{'PFBC'},'Only the proven issuer-name false positive may change'
    m.save(out/'pfbc-amendment-plan.json',dict(at_utc=datetime.now(timezone.utc).isoformat(),symbol='PFBC',
        reason='Preferred Bank is issuer name; Finnhub and Nasdaq describe Common Stock, not Preferred Stock',
        old_count=len(oldsymbols),new_count=len(proposed),metrics_used_for_inclusion=False,
        original_protocol_sha256=m.digest(out/'protocol.json'),code_sha256=m.digest(__file__)))
    ordinary.main(write=True)
    symbols=sorted(proposed)
    engine=m.get_sqlalchemy_engine(db_name='alpha_trade')
    calendar=pd.DatetimeIndex(m.get_market_calendar('US_EQ',allow_us_weekday_fallback=False).session_dates(date(2016,1,1),m.ASOF.date()))
    data=m.load_bars(engine,['SPY','PFBC']);data['date']=pd.to_datetime(data.date)
    bench=m.select_daily_bars(data[data.symbol.eq('SPY')]).sort_values('date')
    raw=data[data.symbol.eq('PFBC')].copy()
    result=m.stock('PFBC',raw,bench,calendar,m.load_security_discontinuities().get('PFBC',()))
    assert result['status']=='PROCESSED' and raw.instrument_id.dropna().nunique()==1
    for target,t in result['targets'].items():
        for fit in t['fits']:
            if fit['status']!='FITTED':continue
            year=fit['year'];file=out/'symbols/PFBC'/f'{target}-{year}.joblib'
            assert m.digest(file)==fit['model_sha256']
            assert pd.Timestamp(fit['fit_label_available_max'])<pd.Timestamp(f'{year-1}-01-01')
            assert pd.Timestamp(fit['calibration_label_available_max'])<pd.Timestamp(f'{year}-01-01')
    receipts={}
    with engine.connect() as conn:
        conn.execute(text('START TRANSACTION READ ONLY'));conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
        for name,sql in {
            'oi':"SELECT MIN(GREATEST(observed_at,available_at)) first_receipt FROM stock_option_snapshots WHERE underlying_symbol='PFBC'",
            'volume':"SELECT MIN(GREATEST(observed_at,available_at)) first_receipt FROM stock_option_bars_delayed WHERE underlying_symbol='PFBC' AND timeframe='30Min'",
            'consensus':"SELECT MIN(GREATEST(observed_at,available_at)) first_receipt FROM stock_analyst_consensus_eodhd_history WHERE symbol='PFBC'"}.items():
            receipts[name]=conn.execute(text(sql)).scalar_one()
        conn.rollback()
    gates=pd.read_parquet(out/'source-reliability-gates.parquet');extra=[]
    for target in m.TARGETS:
        h=10 if target=='winner_h10' else 20
        options=max(receipts['oi'],receipts['volume']) if all(receipts[k] is not None for k in ('oi','volume')) else None
        for source,stamp in [('options',options),('consensus',receipts['consensus'])]:
            n=0 if stamp is None else int((calendar>=pd.Timestamp(stamp).normalize()-pd.Timedelta(days=1)).sum())
            matured=max(0,n-h);independent=int(m.math.ceil(matured/h));assert independent<20
            extra.append(dict(symbol='PFBC',target=target,source=source,first_receipt=None if stamp is None else str(stamp),
                optimistic_matured_sessions=matured,optimistic_independent_upper_bound=independent,
                minimum_independent_required=20,status='SOURCE_ABSENT' if stamp is None else 'INSUFFICIENT_HISTORY'))
    gates=pd.concat([gates,pd.DataFrame(extra)],ignore_index=True);gates.to_parquet(out/'source-reliability-gates.parquet',index=False)
    validation=pd.read_csv(out/'check-2026-per-symbol.csv',keep_default_na=False)
    extra_validation=[];report=dict(old_report);summaries={}
    for target in m.TARGETS:
        t=result['targets'][target];s=t.get('sparse',{})
        row=dict(symbol='PFBC',status=result['status'],qualified_history=t.get('qualified_history',False),
            reliability_confirmed=t.get('reliability_confirmed',False),long_lift_conservative_bound=t.get('long_lift_conservative_bound'),
            worst_annual_auc=t.get('worst_annual_auc'),auc_nonoverlap=s.get('auc'),independent_observations=t.get('n_independent',0),
            precision_lift=t.get('long_precision_lift'),check_2026_auc=t.get('check_2026',{}).get('auc'),identity_history_qualified=True)
        file=out/(target+'-per-symbol-audit.csv');(before/file.name).write_bytes(file.read_bytes())
        allrows=pd.concat([pd.read_csv(file,keep_default_na=False),pd.DataFrame([row])],ignore_index=True)
        assert set(allrows.symbol)==set(symbols) and not allrows.symbol.duplicated().any()
        for col in ['long_lift_conservative_bound','worst_annual_auc','auc_nonoverlap','precision_lift','check_2026_auc']:
            allrows[col]=pd.to_numeric(allrows[col],errors='coerce')
        allrows.to_csv(file,index=False)
        a=allrows[allrows.qualified_history].sort_values(['long_lift_conservative_bound','worst_annual_auc','auc_nonoverlap','symbol'],ascending=[False,False,False,True]).copy()
        a['rank']=range(1,len(a)+1)
        ranking=out/(target+'-per-symbol-ranking.csv');(before/ranking.name).write_bytes(ranking.read_bytes());a.to_csv(ranking,index=False)
        for suffix,values in [('model-top1500',a.head(1500).symbol),('model-confirmed',a[a.reliability_confirmed].symbol)]:
            file=out/(target+'-'+suffix+'.txt');(before/file.name).write_bytes(file.read_bytes());file.write_text(','.join(values)+'\n',encoding='utf-8')
        f=out/'symbols/PFBC'/(target+'-predictions.parquet')
        if f.exists():extra_validation.append(dict(symbol='PFBC',target=target,**check_2026(pd.read_parquet(f),target)))
        report['cases'][target].update(model_history_qualified=len(a),model_top1500=min(1500,len(a)),
            model_exploratory_confirmed=int(a.reliability_confirmed.sum()),source_gate_counts={f'{x}/{y}':int(n) for (x,y),n in gates[gates.target.eq(target)].groupby(['source','status']).size().items()})
    validation=pd.concat([validation,pd.DataFrame(extra_validation)],ignore_index=True)
    for col in ['auc','long_lift','long_precision','base_rate','observations','long_observations']:
        validation[col]=pd.to_numeric(validation[col],errors='coerce')
    validation.to_csv(out/'check-2026-per-symbol.csv',index=False)
    for target in m.TARGETS:
        a=pd.read_csv(out/(target+'-per-symbol-ranking.csv'),keep_default_na=False)
        eligible=set(a.symbol);top=set(a.head(1500).symbol);v=validation[validation.target.eq(target)&validation.symbol.isin(eligible)]
        summaries[target]=dict(top1500=summarize(v[v.symbol.isin(top)]),other_history_qualified=summarize(v[~v.symbol.isin(top)]),
            no_reranking=True,portfolio_return=False,independent_of_2023_2025_ranking=True,previously_explored_calendar_period_not_virgin_holdout=True)
    m.save(out/'check-2026-summary.json',summaries)
    report.update(symbols_requested=len(symbols),processed=len(symbols),models_fitted=old_report['models_fitted']+result['models'],scope_amendment='scope-amendment-pfbc.json')
    m.save(out/'report.json',report)
    amendment=dict(status='PASS',symbol='PFBC',source_count=len(symbols),source_sha256=m.digest(m.SOURCE),
        models_added=result['models'],old_models_refitted=False,model_code_unchanged=True,
        receipts=receipts,classification_code_sha256=m.digest(Path(ordinary.__file__)),
        reason='Verified issuer-name/type confusion, not performance-based inclusion',
        original_source_sha256=protocol['source_hashes'][source_key],
        original_source_preserved=str(before/'action_ordinaire.txt'),final_intersections_still_empty=True,
        elapsed_seconds=time.monotonic()-started,sql_writes=False,provider_calls=0)
    m.save(out/'scope-amendment-pfbc.json',amendment)
    progress=json.loads((out/'progress.json').read_text());progress.update(completed=len(symbols),total=len(symbols),models_fitted=report['models_fitted'])
    m.save(out/'progress.json',progress)
    assert len(set(m.SOURCE.read_text().strip().split(',')))==5254
    verification=json.loads((ordinary.AUDIT/'verification.json').read_text());verification.update(output_count=5254,issuer_name_correction='PFBC',duplicates=0,outside_source=0)
    m.save(ordinary.AUDIT/'verification.json',verification)
    readme=ordinary.AUDIT/'README.md';body=readme.read_text(encoding='utf-8').replace('5,253','5,254').replace('| INCLUDE_ORDINARY | 5253 |','| INCLUDE_ORDINARY | 5254 |').replace('| EXCLUDE_PREFERRED | 146 |','| EXCLUDE_PREFERRED | 145 |')
    readme.write_text(body+'\nCorrection du4novembre2026 : PFBC Preferred Bank est une action ordinaire ; le nom de société ne définit pas le type de titre.\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','source_count':len(symbols),'models_added':result['models'],'models_total':report['models_fitted']}))


if __name__=='__main__':main()
