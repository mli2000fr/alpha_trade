"""Confidence bins on already executed LONG/SHORT TP20/SL5 positions, offline.

Descriptive attribution, not newly rebalanced threshold portfolios or independent
calibration. Position PnL includes trade fees/SHORT borrow, not allocated funding.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

LONG = Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1')
SHORT = Path('artifacts/research/us_news_gpt_bearish_portfolio/20261015-v1')
LABELS = ('<0.70','0.70-<0.80','0.80-<0.90','0.90-<0.95','0.95-1.00')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def confidence_bins(scores):
    scores = pd.to_numeric(scores,errors='raise')
    if not np.isfinite(scores).all() or not scores.between(0,1).all():
        raise ValueError('Invalid confidence score')
    return pd.cut(scores,[0,.70,.80,.90,.95,1.0000001],right=False,labels=LABELS).astype(str)


def position_rows(trades, panel, opened, *, year, side):
    if trades.empty:
        return pd.DataFrame()
    expected_side = 'buy' if side=='LONG' else 'sell'
    expected_decision = 'BULLISH' if side=='LONG' else 'BEARISH'
    if not trades.side.eq(expected_side).all():
        raise ValueError('Unexpected trade direction')
    open_keys={(p['symbol'],pd.Timestamp(p['entry_date'])) for p in opened}
    lookup=panel.set_index(['date','symbol'])
    if not lookup.index.is_unique:
        raise ValueError('Duplicate GPT candidate key')
    records=[]
    for (symbol,entry),part in trades.groupby(['symbol','entry_date']):
        dates=pd.to_datetime(part.signal_date).unique()
        if len(dates)!=1:
            raise ValueError('One initial signal required per position')
        signal=pd.Timestamp(dates[0]); candidate=lookup.loc[(signal,symbol)]
        if candidate.decision!=expected_decision or candidate.technical_status!='VALID':
            raise ValueError('Position not mapped to valid original GPT decision')
        nominal=float((part.quantity*part.entry_price).sum())
        pnl=float(part.pnl.sum())
        records.append(dict(year=year,side=side,symbol=symbol,signal_date=signal,entry_date=entry,
            last_exit_date=part.exit_date.max(),confidence=float(candidate.confidence),cache_key=candidate.cache_key,
            oracle_rank=int(candidate.oracle_rank),closed=(symbol,pd.Timestamp(entry)) not in open_keys,
            pnl_usd=pnl,entry_notional_usd=nominal,net_trade_return_pct=100*pnl/nominal,
            exit_legs=len(part),borrow_usd=float(part.borrow_cost.sum()) if 'borrow_cost' in part else 0.))
    result=pd.DataFrame(records)
    result['confidence_bin']=confidence_bins(result.confidence)
    return result


def metrics(group):
    pnl=group.pnl_usd
    wins,losses=int(pnl.gt(0).sum()),int(pnl.lt(0).sum())
    positive=float(pnl[pnl.gt(0)].sum()); negative=float(pnl[pnl.lt(0)].sum())
    return dict(n=len(group),distinct_symbols=int(group.symbol.nunique()),
        distinct_signal_dates=int(group.signal_date.nunique()),wins=wins,losses=losses,flat=int(pnl.eq(0).sum()),
        winning_pct=100*wins/len(group) if len(group) else None,
        losing_pct=100*losses/len(group) if len(group) else None,
        positive_pnl_usd=positive,negative_pnl_usd=negative,net_pnl_usd=float(pnl.sum()),
        mean_net_trade_return_pct=float(group.net_trade_return_pct.mean()) if len(group) else None,
        median_net_trade_return_pct=float(group.net_trade_return_pct.median()) if len(group) else None,
        profit_factor=positive/-negative if negative<0 else None,
        winner_pnl_concentration=(float(pnl.max())/positive if positive>0 else None),
        borrow_usd=float(group.borrow_usd.sum()))


def run(root):
    root.mkdir(parents=True,exist_ok=True)
    sources={}; reports={}; panels={}
    for side,base in [('LONG',LONG),('SHORT',SHORT)]:
        ready=read(base/'ready.json')
        verify_hashes(Path('.'),ready['sources']); verify_hashes(base,ready['files'])
        source_report=read(base/'report.json'); audit=read(base/'audit.json')
        if source_report['status']!='COMPLETED' or not audit['status'].startswith('AUDITED'):
            raise ValueError('Completed audited source required')
        if audit['files']['report.json']!=digest(base/'report.json'):
            raise ValueError('Source audit/report changed')
        for name in ['ready.json','report.json','audit.json','candidates.parquet']:
            sources[str(base/name)]=digest(base/name)
        reports[side]=source_report; panels[side]=pd.read_parquet(base/'candidates.parquet')
    protocol=dict(experiment='CACHED_GPT_CONFIDENCE_ATTRIBUTION_TP20_SL5',sides=['LONG','SHORT'],tp=.20,sl=.05,
        bins=LABELS,boundary='left inclusive, right exclusive except final includes1',
        long_policy='GPT_BULLISH_ONLY',short_policy='GPT_BEARISH_ONLY RESEARCH_SHORT_NORMAL',
        raw_candidates={'LONG':913,'SHORT':734},closed_expected={'LONG':335,'SHORT':167},
        population='actual executed and fully closed positions only; open lots excluded including partial closed legs',
        annual_cohort='decision year; includes prescribed expiry tail after2024/2025, 2026 cut atSep30',
        money='closed position PnL net trade fees and SHORT borrow; portfolio funding interest not allocated',
        comparison='descriptive bin/year attribution, not a replay of independently capitalized bin portfolios',
        threshold_comparison='>=0.90 versus<0.90, fixed before calculation; no threshold search',
        reserves=['non-PIT historical news/LLM knowledge; current sectors; SHORT availability/cost assumptions',
                  'repeated symbols/dates, capacity and sizing selection; pooled yearly mix; not independent holdout',
                  'confidence self-reported, not probability of profitable trade; posthoc selection cannot prove calibration'],
        api_calls=0,sql_writes=False,training=False,production_changes=False,
        sources=sources,analysis_script_sha256=digest(Path(__file__)))
    # Seal the descriptive procedure before reading executed outcomes into bins.
    atomic_json(root/'protocol.json',protocol)
    rows=[]
    for side,base in [('LONG',LONG),('SHORT',SHORT)]:
        for item in reports[side]['reports']:
            if item['arm']!=('GPT_BULLISH_ONLY' if side=='LONG' else 'GPT_BEARISH_ONLY'):
                continue
            if side=='SHORT' and item['profile']!='RESEARCH_SHORT_NORMAL':
                continue
            year=item['year']
            folder=base/(f'{year}-{item["arm"]}' if side=='LONG' else f'{year}-{item["profile"]}-{item["arm"]}')
            verify_hashes(folder,item['files'])
            for name in item['files']:sources[str(folder/name)]=item['files'][name]
            trades=pd.read_parquet(folder/'trades.parquet')
            rows.append(position_rows(trades,panels[side],item['open_positions'],year=year,side=side))
    positions=pd.concat(rows,ignore_index=True)
    closed=positions[positions.closed].copy()
    for side,expected in protocol['closed_expected'].items():
        if len(closed[closed.side.eq(side)])!=expected:
            raise ValueError('Closed position population differs')
    positions.to_parquet(root/'position-attribution.parquet',index=False)
    summaries=[]; thresholds=[]
    for side in ('LONG','SHORT'):
        for year in (2024,2025,2026,'ALL'):
            selected=closed[closed.side.eq(side)]
            if year!='ALL':selected=selected[selected.year.eq(year)]
            for label in LABELS:
                group=selected[selected.confidence_bin.eq(label)]
                summaries.append(dict(side=side,year=year,confidence_bin=label,**metrics(group)))
            for label,mask in [('below_090',selected.confidence.lt(.90)),('at_least_090',selected.confidence.ge(.90))]:
                thresholds.append(dict(side=side,year=year,confidence_group=label,**metrics(selected[mask])))
    distributions=[]
    for side,decision in [('LONG','BULLISH'),('SHORT','BEARISH')]:
        panel=panels[side]
        valid=panel[panel.decision.eq(decision)&panel.technical_status.eq('VALID')].copy()
        valid['confidence_bin']=confidence_bins(valid.confidence)
        if len(valid)!=protocol['raw_candidates'][side]:raise ValueError('Raw population changed')
        for label in LABELS:
            distributions.append(dict(side=side,confidence_bin=label,n=int(valid.confidence_bin.eq(label).sum())))
    # Partition must preserve exact PnL and counts; no repeated exit legs counted as trades.
    for side in ('LONG','SHORT'):
        bins=[r for r in summaries if r['side']==side and r['year']=='ALL']
        selected=closed[closed.side.eq(side)]
        if sum(r['n'] for r in bins)!=len(selected) or not np.isclose(sum(r['net_pnl_usd'] for r in bins),selected.pnl_usd.sum()):
            raise ValueError('Bin partition failed')
    result=dict(status='COMPLETED_DESCRIPTIVE_NOT_CALIBRATED',bins=summaries,thresholds=thresholds,
        raw_distributions=distributions,fully_closed_positions=len(closed),
        partially_closed_open_positions_excluded=int((~positions.closed).sum()),
        source_final_open_positions={'LONG':4,'SHORT':2},sources=sources,
        files={'position-attribution.parquet':digest(root/'position-attribution.parquet')},
        api_calls=0,sql_writes=False,training=False,not_independent_holdout=True)
    atomic_json(root/'report.json',result)
    atomic_json(root/'progress.json',dict(status=result['status'],positions=len(closed),api_calls=0))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    result=run(parser.parse_args().output)
    print(json.dumps({key:result[key] for key in ('status','fully_closed_positions','bins','thresholds')},default=str))
