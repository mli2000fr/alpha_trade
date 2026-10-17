"""Matched LONG TP10/SL10: GPT BEARISH, GPT BULLISH, unfiltered TOP20.

Three verified BEARISH cases reused, six controls computed. No SQL/API/training.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout,redirect_stderr
from functools import partial
import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from scripts.research import us_news_gpt_bearish_long as base
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

SOURCE=Path('artifacts/research/us_news_gpt_bearish_long/20261015-v1')
ARMS=('GPT_BEARISH_AS_LONG','GPT_BULLISH_AS_LONG','ORACLE_TOP20_ALL_LONG')


def verify_original_sources(mapping):
    """Allow only proven Python CRLF/LF equivalence; never rewrite old manifests.

    Data, config and changed Python content remain strict failures. New manifests
    bind current raw bytes and archive the exact old-to-new source attestation.
    """
    current={};equivalent=[]
    for name,expected in mapping.items():
        path=Path(name);raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
        current[name]=actual
        if actual==expected:continue
        if path.suffix!='.py' or hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('Source content changed: '+name)
        equivalent.append(dict(path=name,original_sha256=expected,current_sha256=actual,
            normalized_lf_sha256=expected,change='PYTHON_CRLF_ONLY_NO_CONTENT_CHANGE'))
    return current,equivalent


def add_policies(panel):
    if panel.duplicated(['date','symbol']).any():raise ValueError('Duplicate candidate key')
    result=panel.copy()
    for arm,decision in [('GPT_BEARISH_AS_LONG','BEARISH'),('GPT_BULLISH_AS_LONG','BULLISH')]:
        result[arm]=result.selected & result.decision.eq(decision) & result.technical_status.eq('VALID')
    # Includes no-news, abstention and technical unknowns, as an unfiltered control must.
    result['ORACLE_TOP20_ALL_LONG']=result.selected
    return result


def prepare(root):
    marker=root/'ready.json'
    if marker.exists():
        p=base.native.read(marker)
        if p['experiment']!='MATCHED_GPT_LONG_TP10_SL10':raise ValueError('Wrong output contract')
        verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files']);return p
    if (root/'protocol.json').exists():raise ValueError('Incomplete preparation: use fresh output ID')
    old=base.native.read(SOURCE/'ready.json');audit=base.native.read(SOURCE/'audit.json')
    current_sources,newline_equivalence=verify_original_sources(old['sources'])
    verify_hashes(SOURCE,old['files']);verify_hashes(SOURCE,audit['files'])
    report=base.native.read(SOURCE/'report.json')
    if report['status']!='COMPLETED' or not audit['status'].startswith('AUDITED'):raise ValueError('Audited source required')
    if old['tp']!=.1 or old['sl']!=.1 or old['side']!='LONG':raise ValueError('Unmatched protections/direction')
    panel=add_policies(pd.read_parquet(SOURCE/'candidates.parquet'))
    if len(panel)!=13780 or not panel.groupby('date').size().eq(20).all():raise ValueError('Original TOP20 changed')
    for decision,count in [('BEARISH',734),('BULLISH',913)]:
        if int((panel.decision.eq(decision)&panel.technical_status.eq('VALID')).sum())!=count:
            raise ValueError('Original opinion membership changed')
    if int(panel.GPT_BEARISH_AS_LONG.sum())!=732 or int(panel.GPT_BULLISH_AS_LONG.sum())!=911:
        raise ValueError('Original J admission changed')
    panel.to_parquet(root/'candidates.parquet',index=False)
    sources=current_sources
    for path in [SOURCE/name for name in ['ready.json','report.json','audit.json','candidates.parquet']]+[
            Path(__file__),Path('tests/test_us_news_gpt_long_comparison.py')]:sources[str(path)]=digest(path)
    for case in report['reports']:
        folder=SOURCE/str(case['year']);verify_hashes(folder,case['files'])
        sources[str(folder/'case-report.json')]=digest(folder/'case-report.json')
        sources.update({str(folder/name):checksum for name,checksum in case['files'].items()})
    atomic_json(root/'source-line-endings.json',dict(status='VERIFIED',equivalent_python_paths=newline_equivalence,
        legacy_manifest=str(SOURCE/'ready.json'),legacy_manifest_sha256=digest(SOURCE/'ready.json'),
        data_and_config_strict=True,old_manifests_modified=False))
    p=dict(old,experiment='MATCHED_GPT_LONG_TP10_SL10',arms=ARMS,bearish_source=str(SOURCE),
        selection_only_difference=True,reused_bearish_cases=3,new_control_cases=6,
        primary_comparisons=['BEARISH_LONG minus ALL_LONG','BEARISH_LONG minus BULLISH_LONG'],
        control_caveat='ALL includes missing/invalid/abstain opinions; opinion availability itself can select a different population',
        exposure_matched=False,comparison_warning='Same rules/capital, not same exposure or realized risk; periods already explored, not a fresh holdout',
        sources=sources,legacy_source_newline_equivalence=newline_equivalence,
        files={name:digest(root/name) for name in ['candidates.parquet','source-line-endings.json']})
    atomic_json(root/'protocol.json',p);atomic_json(marker,p);return p


def make_ledger(cfg,p,quality,refs,*,terminal,**kwargs):
    value=base.native.ExpiryMarkLedger(cfg,quality=quality,sl=.1,trail=None,tp=.1,study_end=terminal,events=p['events'],**kwargs)
    refs.append(value);return value


def run_case(root,p,panel,prices,year,arm):
    if arm not in ARMS:raise ValueError('Unknown frozen arm')
    if arm==ARMS[0]:
        folder=SOURCE/str(year);saved=base.native.read(folder/'case-report.json')
        verify_hashes(folder,saved['files'])
        return dict(saved,arm=arm,source_folder=str(folder),reused=True,raw_candidate_days=saved['raw_bearish_days'])
    folder=root/f'{year}-{arm}';folder.mkdir(exist_ok=True);marker=folder/'case-report.json'
    if marker.exists():
        saved=base.native.read(marker)
        if saved['status'].startswith('COMPLETED'):verify_hashes(folder,saved['files']);return saved
    spec=p['years'][str(year)];subset=panel[panel.date.dt.year.eq(year)].copy()
    bars=prices[prices.date.le(spec['terminal'])].copy();days=base.native.grid.nyse_sessions('2023-01-01',spec['terminal'])
    frames={key:bars.pivot(index='date',columns='symbol',values=field).reindex(days)
        for key,field in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    quality=bars[['date','symbol','is_filled','instrument_id']]
    sectors=pd.read_parquet(p['sectors']).set_index('symbol').sector.to_dict()
    sectors['VMRK']=sectors['EQR'];sectors['TELWY']=sectors.get('TOELY',sectors.get('TELWY','Unknown'))
    refs=[]
    factory=partial(make_ledger,p=p,quality=quality,refs=refs,terminal=spec['terminal'])
    try:
        with (folder/'research.log').open('a',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            logging.basicConfig(level=logging.WARNING,stream=stream,force=True)
            result=base.native.run_portfolio(frames=frames,scores=subset,sectors=sectors,
                macro=base.native.ArchivedMacro(pd.read_parquet(p['macro'])),market_config=base.native.grid.parse_market_regimes(p['market']),
                policy=arm,variant='CURRENT_NO_EXPIRY',output=folder,start_date=f'{year}-01-01',end_date=spec['terminal'],
                decision_end_date=spec['decision_end'],quality=quality,ledger_factory=factory,
                session_factory=partial(base.native.grid.MarginAwareSession,ledger_ref=refs),reject_constrained_entries=True,
                protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=base.native.grid.margin_policy)
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        result=base.summarize(result,refs[0],daily,trades,year,spec['terminal'])
        opened=[(pd.Timestamp(e['date']),s) for e in base.native.read(folder/'executions.json') for s in e['opened']]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in subset[subset[arm]].itertuples()
                 if days.get_loc(r.date)+1<len(days)}
        if any(pair not in allowed for pair in opened):raise ValueError('Entry outside frozen next-open arm')
        if year<2026 and result['open_positions']:raise ValueError('Incomplete old-year expiry tail')
        raw=(subset.decision.eq('BULLISH')&subset.technical_status.eq('VALID')) if arm==ARMS[1] else pd.Series(True,index=subset.index)
        result.update(arm=arm,source_folder=str(folder),reused=False,batch_id=p['models'][str(year)],
            actual_entries=len(opened),candidate_days=int(subset[arm].sum()),raw_candidate_days=int(raw.sum()))
        atomic_json(folder/'open-positions.json',result['open_positions']);atomic_json(folder/'expiry-audit.json',refs[0].expiry_audits)
        atomic_json(folder/'maintenance.json',refs[0].margin_audits)
        result['files']={name:digest(folder/name) for name in ['daily.parquet','trades.parquet','executions.json','decisions.json',
            'regimes.json','open-positions.json','expiry-audit.json','maintenance.json','corporate-actions.json']}
    except Exception as exc:result=dict(status='FAILED',year=year,arm=arm,error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result);return result


def run(root,phase):
    root.mkdir(parents=True,exist_ok=True);p=prepare(root)
    if phase=='prepare':return dict(status='READY',new_cases=6,reused_cases=3,api_calls=0)
    panel=pd.read_parquet(root/'candidates.parquet');prices=pd.read_parquet(p['prices']);reports=[]
    for arm in ARMS:
        for year in (2024,2025,2026):
            atomic_json(root/'progress.json',dict(status='RUNNING',year=year,arm=arm,completed=len(reports),total=9,api_calls=0))
            reports.append(run_case(root,p,panel,prices,year,arm))
            atomic_json(root/'report.json',dict(status='RUNNING',completed=len(reports),total=9,reports=reports))
    result=dict(status='COMPLETED' if all(r['status'].startswith('COMPLETED') for r in reports) else 'PARTIAL_FAILED',
        completed=len(reports),total=9,reports=reports,api_calls=0,sql_writes=False,training=False,
        new_cases=6,reused_cases=3,exposure_matched=False)
    atomic_json(root/'report.json',result);atomic_json(root/'progress.json',{k:v for k,v in result.items() if k!='reports'});return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','run'],default='run');args=parser.parse_args()
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('HTTP forbidden in matched offline LONG comparison')
    requests.Session.request=forbidden
    with exclusive_run(args.output):
        try:print(json.dumps(run(args.output,args.phase),default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
