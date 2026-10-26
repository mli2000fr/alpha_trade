"""Bounded read-only readiness gate before an Oracle Winner 2016-2026 grid."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import pandas as pd
from sqlalchemy import text

ROOT=Path('artifacts/research/us_winner_grid_history_readiness/20261023-v1')
MODEL_ROOT=Path('artifacts/models')


def receipt(path):
    raw=Path(path).read_bytes()
    return json.loads(raw),dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),
        read_at_utc=datetime.now(timezone.utc).isoformat())


def causal_fold(metrics):
    first=pd.Timestamp(metrics['test_start'])
    return all(pd.Timestamp(metrics[k])<first for k in ['train_available_max','val_available_max'])


def year_counts(dates):
    f=pd.DataFrame({'date':pd.to_datetime(dates)})
    return [dict(year=int(y),first=str(g.date.min().date()),last=str(g.date.max().date()),
        score_rows=len(g),dates=int(g.date.nunique())) for y,g in f.groupby(f.date.dt.year)]


def db_inventory():
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade');lineages=[];samples=[];calls=0
    try:
        with engine.connect() as c,c.begin():
            c.execute(text('SET SESSION MAX_EXECUTION_TIME=10000'))
            c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if c.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US only')
            for year in range(2016,2027):
                row=c.execute(text('SELECT prediction_date,batch_id,fold_start,model_available_date,target_name '
                    'FROM oracle_path_prediction_lineage FORCE INDEX(PRIMARY) '
                    'WHERE prediction_date>=:start AND prediction_date<:end '
                    'ORDER BY prediction_date,symbol,batch_id LIMIT 1'),
                    {'start':f'{year}-01-01','end':f'{year+1}-01-01'}).mappings().first();calls+=1
                lineages.append(dict(year=year,first_stored_lineage=dict(row) if row else None))
                for symbol in ['AA','ANF','HOV']:
                    row=c.execute(text("SELECT trade_date,bar_timestamp,data_source,session_tag FROM stock_bars_intraday FORCE INDEX(PRIMARY) "
                        "WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end AND provider='alpaca' "
                        "AND data_source='alpaca_sip' AND interval_code='5m' AND market_code='US_EQ' "
                        "AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 ORDER BY bar_timestamp LIMIT 1"),
                        {'symbol':symbol,'start':f'{year}-01-01','end':f'{year+1}-01-01'}).mappings().first();calls+=1
                    samples.append(dict(year=year,symbol=symbol,first_row=dict(row) if row else None))
    finally:engine.dispose()
    return dict(transaction_read_only=True,SQL_data_queries=calls,indexed_limits=True,
        stored_lineage=lineages,intraday_presence_samples=samples,full_symbol_session_coverage_certified=False)


def run(root=ROOT,*,database=True):
    if root.exists():raise FileExistsError('Fresh readiness snapshot required')
    root.mkdir(parents=True);runs=[];models=[];folds=[];inputs=[]
    for folder in sorted(Path('artifacts/intraday_backfill').iterdir()):
        planfile=folder/'plan.json'
        if not planfile.exists():continue
        plan,r=receipt(planfile);inputs.append(r)
        item={k:plan.get(k) for k in ['plan_id','start_date','end_date','provider','alpaca_feed','interval','symbol_source','universe_sha256']}
        item['symbols']=len(plan.get('symbols',[]));item['ranges']=len(plan.get('ranges',[]))
        for name in ['progress.json','report.json']:
            if (folder/name).exists():
                v,r=receipt(folder/name);inputs.append(r)
                item[name]={k:v.get(k) for k in ['status','total_tasks','completed_tasks','failed_tasks','empty_tasks','received','persisted','current','updated_at_utc']}
        item['process_liveness_verified']=False;runs.append(item)
    for protocol in sorted(MODEL_ROOT.glob('*/oracle_path/protocol.json')):
        p,r=receipt(protocol);inputs.append(r)
        if p.get('target')!='oracle_path_extreme20':continue
        scores=protocol.with_name('oof_predictions.parquet');reportfile=protocol.with_name('report.json')
        if not scores.exists() or not reportfile.exists():continue
        report,r=receipt(reportfile);inputs.append(r)
        dates=pd.read_parquet(scores,columns=['date']).date
        for fold in report.get('folds',[]):
            item={k:fold.get(k) for k in ['fold_start','train_available_max','val_available_max','test_start','test_end','selected_backend']}
            item.update(batch_id=p['batch_id'],temporally_causal=causal_fold(fold));folds.append(item)
        models.append(dict(batch_id=p['batch_id'],target=p['target'],backend=p.get('backend'),
            score_file=str(scores),first_oof=str(dates.min().date()),last_oof=str(dates.max().date()),
            rows=len(dates),by_year=year_counts(dates),all_folds_temporally_causal=all(causal_fold(x) for x in report['folds'])))
    earliest=min(x['first_oof'] for x in models)
    sql=db_inventory() if database else dict(executed=False)
    (root/'fold-inventory.csv').write_text(pd.DataFrame(folds).to_csv(index=False),encoding='utf-8')
    value=dict(status='NOT_READY_FOR_EXACT_2016_2026_GRID',observed_at_utc=datetime.now(timezone.utc).isoformat(),
        requested_first_date='2016-01-01',requested_last_date='2026-09-30',first_existing_causal_oof=earliest,
        missing_early_oracle_scores=['2016-01-01 through 2017-06-01'],backfills=runs,models=models,
        database=sql,input_metadata_receipts=inputs,
        limitations=['Presence samples are NOT full symbol-session coverage.',
            'COMPLETED tasks may be empty or have absent regular bars; IPO/delisting dates must be considered.',
            'RUNNING progress is not proof of a live process; BLOCKED 2018 report and unfinished overlapping plan require qualification.',
            '2016 needs a model trained on earlier data; never apply a later-trained model retrospectively as OOS.',
            'Annual capital resets and native risk contract must remain fixed before ranking profiles.'],
        grid_started=False,top3=None,training_performed=False,SQL_writes=False,provider_calls=0,
        scope_choice_required=True,proposed_earliest_test='2017-06-02')
    with (root/'report.json').open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,default=str,allow_nan=False)
    print(json.dumps({k:value[k] for k in ['status','first_existing_causal_oof','grid_started','scope_choice_required']},indent=2))


if __name__=='__main__':run()
