"""Frozen-archive consensus TOP10/20/50 audit; no SQL/API/model fitting or orders."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from scripts.research import us_options_equal_mix_20261026 as b
from scripts.research import us_options_equal_mix_amended_20261026 as paths
from scripts.research import us_consensus_reliability_20261022 as consensus

ORACLE=Path('artifacts/research/us_options_oracle_topn/20261026-v1')
CONSENSUS=Path('artifacts/research/us_consensus_reliability/20261022-v1/sip-only-v2')
OUTPUT=Path('artifacts/research/us_consensus_options_topn/20261027-v1')
DOC=Path('doc/ml/consensus_options_topn_protocole_20261027.md')
TEST=Path('tests/test_us_consensus_options_topn_20261027.py')
FEATURES=['revisions30','eps30','revenue_observed']


def verify_archives():
    sources={};reserves=[]
    for root,seal_names in [(ORACLE,['seal.json']), (CONSENSUS,['snapshot-ready.json','features-ready.json'])]:
        for seal_name in seal_names:
            seal=b.read(root/seal_name)
            for name,expected in seal['files'].items():
                if Path(name).name!=name or b.digest(root/name)!=expected:
                    raise ValueError('Parent archive modified: '+str(root/name))
                sources[str(root/name)]=expected
            sources[str(root/seal_name)]=b.digest(root/seal_name)
        protocol=b.read(root/'protocol.json')
        for name,expected in protocol['sources'].items():
            current=b.digest(name) if Path(name).is_file() else None
            if current!=expected:
                # Frozen data hashes remain mandatory. Historical code/docs may
                # evolve: reserve reproducibility, never rewrite their seals or
                # claim the parent generator has been reproduced unchanged.
                if 'artifacts' in Path(name).parts and 'models' in Path(name).parts:
                    raise ValueError('Model artifact modified: '+name)
                reserves.append(dict(path=name,archived_sha256=expected,current_sha256=current))
        sources[str(root/'protocol.json')]=b.digest(root/'protocol.json')
    # Verify the price/options parent too, including the separate price-source outputs.
    parent=Path(b.read(ORACLE/'protocol.json')['parent'])
    seal=b.read(parent/'seal.json')
    for name,expected in seal['files'].items():
        if b.digest(parent/name)!=expected:raise ValueError('Options parent modified: '+name)
        sources[str(parent/name)]=expected
    sources[str(parent/'seal.json')]=b.digest(parent/'seal.json')
    return sources,parent,reserves


def verify_ranks(ranked, raw, protocol, symbols):
    """Independently reproduce ranks from sealed raw scores, without outcomes."""
    f=raw.copy();f['signal_day']=pd.to_datetime(f.signal_day)
    f=f[f.symbol.isin(symbols)]
    f=f[f.signal_day.dt.strftime('%Y-%m').map(protocol['batch_policy']).eq(f.batch_id)]
    if f.duplicated(['signal_day','symbol']).any():raise ValueError('Duplicate raw scores')
    counts=f.groupby('signal_day').symbol.transform('size')
    f=f[counts.ge(protocol['minimum_daily_coverage']*len(symbols))]
    f=f.sort_values(['signal_day','proba_extreme','symbol'],ascending=[True,False,True])
    f['oracle_rank']=f.groupby('signal_day').cumcount()+1
    columns=['signal_day','symbol','batch_id','proba_extreme','oracle_rank']
    expected=f[columns].sort_values(['signal_day','symbol']).reset_index(drop=True)
    got=ranked[columns].sort_values(['signal_day','symbol']).reset_index(drop=True)
    pd.testing.assert_frame_equal(got,expected,check_dtype=False)
    return len(got)


def consensus_features(pairs, raw, runs, top):
    """Select on identities/known clocks only, never on a future outcome."""
    pairs=pairs.copy();pairs['entry_day']=pd.to_datetime(pairs.entry_date).dt.strftime('%Y-%m-%d')
    pairs=pairs.merge(top[b.KEY+['decision_at']],on=b.KEY,how='inner',validate='one_to_one')
    rows={int(r['id']):r for r in raw.to_dict('records')}
    quality={}
    output=[]
    for f in pairs.to_dict('records'):
        ids=[int(f['old_id']),int(f['new_id'])]
        for i in ids:
            if i not in quality:quality[i]=consensus.row_quality(rows[i],runs)
        old,new=[rows[i] for i in ids];a,z=[quality[i] for i in ids]
        decision=pd.Timestamp(f['decision_at']);available=pd.Timestamp(z['conservative_available'])
        valid=(a['raw_normalization_ok'] and z['raw_normalization_ok']
            and a['run_receipt_ok'] and z['run_receipt_ok']
            and old['symbol']==new['symbol']==f['symbol']
            and str(old['fiscal_period_end'])==str(new['fiscal_period_end'])
            and old['horizon_raw']==new['horizon_raw']=='0q'
            and pd.notna(available) and available<decision
            and available>=decision-pd.Timedelta(days=4)
            and pd.Timestamp(a['conservative_available'])<pd.Timestamp(f['prior_open']))
        item={k:f[k] for k in b.KEY}
        item.update(old_id=ids[0],new_id=ids[1],consensus_available=available,
                    consensus_receipts_qualified=bool(valid),production_qualified=False)
        for name in FEATURES:item[name]=np.nan
        count=new.get('eps_analyst_count')
        eps_ok=(valid and z['eps_range_ok'] and pd.notna(count) and count>=3)
        up,down=new.get('revisions_up_30d'),new.get('revisions_down_30d')
        if eps_ok and all(pd.notna(x) and np.isfinite(float(x)) and x>=0 for x in (up,down)):
            item['revisions30']=(float(up)-float(down))/(float(up)+float(down)) if up+down else 0.
        current,prior=new.get('eps_current'),new.get('eps_30d_ago')
        if eps_ok and all(pd.notna(x) and np.isfinite(float(x)) for x in (current,prior)) and prior!=0:
            item['eps30']=(float(current)-float(prior))/abs(float(prior))
        if (valid and a['revenue_range_ok'] and z['revenue_range_ok']
                and f['revenue_count_group']=='UNCHANGED_COUNT'
                and all(pd.notna(x) and float(x)>0 for x in (f['old_revenue'],f['new_revenue']))):
            item['revenue_observed']=(float(f['new_revenue'])-float(f['old_revenue']))/float(f['old_revenue'])
        output.append(item)
    return pd.DataFrame(output,columns=b.KEY+['old_id','new_id','consensus_available',
        'consensus_receipts_qualified','production_qualified']+FEATURES)


def ranks(frame):
    result=frame.copy()
    for name in FEATURES:
        result[name+'_score']=result.groupby('entry_day')[name].transform(
            lambda s:(s.rank(method='average')-.5)/s.notna().sum() if s.notna().any() else s)
    return result


def metrics(frame, scores):
    result=dict(rows=len(frame),symbols=int(frame.symbol.nunique()),dates=int(frame.entry_day.nunique()),
                status_counts=frame.status.value_counts().to_dict(),scores={})
    valid=frame[frame.status.eq('LABEL')].copy()
    if scores:valid=valid[np.isfinite(valid[scores].to_numpy(float)).all(axis=1)]
    result.update(valid_n=len(valid),valid_symbols=int(valid.symbol.nunique()),valid_dates=int(valid.entry_day.nunique()),
                  long_n=int(valid.dominant_direction.eq('LONG').sum()))
    for score in scores:
        daily=[]
        for day,g in valid.groupby('entry_day'):
            if g.dominant_direction.nunique()==2:
                daily.append(dict(day=day,n=len(g),auc=float(roc_auc_score(g.dominant_direction.eq('LONG'),g[score]))))
        result['scores'][score]=dict(daily=daily,informative_dates=len(daily),
            mean_daily_auc=float(np.mean([d['auc'] for d in daily])) if daily else None,
            pooled_auc=float(roc_auc_score(valid.dominant_direction.eq('LONG'),valid[score]))
            if len(valid) and valid.dominant_direction.nunique()==2 else None)
    return result


def run(output):
    sources,parent,reserves=verify_archives()
    output.mkdir(parents=True,exist_ok=False)
    sources.update({str(p):b.digest(p) for p in [Path(__file__),DOC,TEST,Path(consensus.__file__),Path(paths.__file__)]})
    b.write(output/'protocol.json',dict(created_at_utc=pd.Timestamp.now(tz='UTC'),sources=sources,
        protocol=str(DOC),consensus_parent=str(CONSENSUS),oracle_parent=str(ORACLE),
        SQL_reads=0,SQL_writes=0,provider_calls=0,LLM_calls=0,training=False,
        oracle_top_n=[10,20,50],weights=dict(options=.5,revisions30=.5),independent_holdout=False,
        parent_generator_source_reserves=reserves))
    top=pd.read_parquet(ORACLE/'oracle-ranked.parquet')
    rank_rows=verify_ranks(top,pd.read_parquet(ORACLE/'oracle-scores.parquet'),
        b.read(ORACLE/'protocol.json'),b.read(parent/'protocol.json')['symbols'])
    top=top[top.oracle_rank.le(50)].copy()
    pairs=pd.read_parquet(CONSENSUS/'features.parquet')
    raw=pd.read_parquet(CONSENSUS/'consensus.parquet')
    runs={r['run_id']:r for r in pd.read_parquet(CONSENSUS/'runs.parquet').to_dict('records')}
    features=consensus_features(pairs,raw,runs,top)
    features.to_parquet(output/'consensus-asof-features.parquet',index=False)
    cal=pd.read_parquet(parent/'calendar.parquet');cutoff=pd.Timestamp(b.read(parent/'protocol.json')['cutoff'])
    report=dict(status='COMPLETED_EXPLORATORY_SINGLE_DATE_NO_PROMOTION',sources={},
        consensus_data_cutoff=b.read(CONSENSUS/'protocol.json')['cutoff_utc'],price_cutoff=str(cutoff),
        data_qualification='RESEARCH_ONLY; provider EPS/fiscal/currency and ingestion-clock reserves retained',
        no_economic_backtest=True,no_independent_validation=True,raw_rank_rows_reproduced=rank_rows,
        parent_generator_source_reserves=reserves)
    for source in ['eodhd_eod','alpaca_sip']:
        prices=pd.read_parquet(parent/'prices.parquet');prices=prices[prices.data_source.eq(source)].copy()
        report['sources'][source]={}
        for n in [10,20,50]:
            selected=top[top.oracle_rank.le(n)].copy()
            candidate=selected.merge(features,on=b.KEY,how='left',validate='one_to_one')
            scored=ranks(candidate)
            scored.to_parquet(output/f'{source}-top{n}-asof-scores.parquet',index=False)
            # Freeze observable signals before opening outcome prices.
            labels=paths.make_labels(selected,prices,cal,cutoff,source)
            panel=labels.merge(scored[b.KEY+[s+'_score' for s in FEATURES]],on=b.KEY,validate='many_to_one')
            options=pd.read_parquet(ORACLE/f'{source}-top{n}-asof-scores.parquet')
            panel=panel.merge(options[b.KEY+b.SCORES],on=b.KEY,how='left',validate='many_to_one')
            panel['options_consensus_score']=.5*panel.combined_score+.5*panel.revisions30_score
            panel.to_parquet(output/f'{source}-top{n}-protected-paths.parquet',index=False)
            item=dict(oracle_candidates=len(selected),oracle_dates=int(selected.entry_day.nunique()),
                feature_coverage={s:int(scored[s].notna().sum()) for s in FEATURES},
                consensus_dates=sorted(scored.loc[scored.revisions30.notna(),'entry_day'].unique()),horizons={})
            for h in [5,10,20]:
                f=panel[panel.horizon.eq(h)].copy()
                common_scores=b.SCORES+['revisions30_score','options_consensus_score']
                common=f[np.isfinite(f[common_scores].to_numpy(float)).all(axis=1)]
                spaced=b.spaced_dates(scored.loc[scored.revisions30.notna(),'entry_day'],h,cal)
                first=scored[scored.revisions30.notna()].sort_values(b.KEY).drop_duplicates('symbol')[b.KEY]
                item['horizons'][str(h)]=dict(
                    individual={s:metrics(f[f[s+'_score'].notna()],[s+'_score']) for s in FEATURES},
                    common=metrics(common,common_scores),
                    physically_observed=metrics(common[common.physically_observed_before_decision],common_scores),
                    nonoverlap_dates=spaced,
                    nonoverlap=metrics(common[common.entry_day.isin(spaced)],common_scores),
                    first_per_symbol=metrics(common.merge(first,on=b.KEY,validate='many_to_one'),common_scores))
            report['sources'][source][str(n)]=item
    b.write(output/'report.json',report)
    b.write(output/'seal.json',dict(files={p.name:b.digest(p) for p in output.iterdir() if p.is_file() and p.name!='seal.json'},sources=sources))
    print(report['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    run(parser.parse_args().output)
