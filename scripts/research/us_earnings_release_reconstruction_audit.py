"""Audit source receipts, source-only feature arithmetic and re-timed selection bias."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json

import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def selection_known_at_decision(old_reaction,new_reaction):
    if pd.isna(old_reaction) or pd.isna(new_reaction):return False
    return pd.Timestamp(old_reaction)<=pd.Timestamp(new_reaction)


def audit(root):
    if (root/'final-audit.json').exists():raise ValueError('Immutable audit')
    for folder in (root,root/'table-review-v1',root/'recalage-v1'):
        verify_hashes(Path('.'),READ(folder/'protocol.json')['sources'])
        verify_hashes(folder,READ(folder/'report.json')['files'])
    docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    for doc in docs['documents']:
        assert doc['receipt']['status']=='OK'
        assert digest(root/doc['receipt']['file'])==doc['receipt']['sha256']
    metadata=READ(root/'discovery.json');assert len(metadata['issuers'])==68
    assert all(x['complete'] for x in metadata['issuers'])
    cases=pd.read_parquet(root/'cases.parquet');retimed=pd.read_parquet(root/'recalage-v1/retimed-features.parquet')
    assert len(cases)==len(retimed)==93
    assert set(cases.accession_number)==set(retimed.case_accession)
    assert retimed.qualified_direction.eq('ABSTAIN').all() and not retimed.fully_qualified.any()
    meta=pd.read_parquet(root/'reconstructed-cases.parquet')
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2023-01-01',end_date='2026-10-20')
    for x in meta[meta.public_sec_acceptance.notna()].itertuples():
        expected=schedule[schedule.market_open.gt(x.public_sec_acceptance)].index[0]
        assert expected==x.corrected_reaction
    bars=pd.read_parquet(root/'recalage-v1/reaction-price-inputs.parquet')
    price={(x.symbol,x.date):x.adj_close for x in bars.itertuples()};verified=0;needed=set()
    for r in retimed[retimed.release_values.notna()].itertuples():
        rev,previous,op,oldop=r.release_values
        g=(rev-previous)/previous;m=op/rev-oldop/previous
        assert abs(r.source_revenue_growth-g)<1e-12 and abs(r.source_margin_change-m)<1e-12
        if r.price_pattern=='UNKNOWN':continue
        day=r.corrected_reaction;j=schedule.index.get_loc(day);before=schedule.index[j-1]
        needed.update((s,d) for s in (r.symbol,'SPY') for d in (before,day))
        relative=price[(r.symbol,day)]/price[(r.symbol,before)]-price[('SPY',day)]/price[('SPY',before)]
        assert abs(relative-r.relative_reaction)<1e-12
        assert r.potential_entry_date==schedule.index[j+1]
        verified+=1
    assert set(price)==needed
    selection=[]
    for row in retimed.itertuples():
        selection.append(dict(symbol=row.symbol,case_accession=row.case_accession,
            original_reaction=str(row.original_reaction),corrected_reaction=str(row.corrected_reaction),
            old_selection_known_at_corrected_decision=selection_known_at_decision(row.original_reaction,row.corrected_reaction),
            provisional_agreement=row.provisional_agreement,
            historical_backtest_authorized=False))
    atomic_json(root/'selection-causality.json',dict(rows=selection,
        verdict='NOT_ENTRY_CAUSAL_FULL_EVENT_SAMPLE',
        explanation='Original93 cases were selected on TOP10 at later10-Q observation. Rechecking TOP10 at earlier release does not remove conditioning on future membership. Rebuild full event population before any re-timed performance test.'))
    provisional=[x for x in selection if x['provisional_agreement'] in ('LONG','SHORT')]
    result=dict(status='PASS_EVIDENCE_AND_FEATURE_ARITHMETIC_NOT_BACKTEST_ADMISSION',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),source_documents=154,issuers=68,cases=93,
        source_values_and_reactions_verified=verified,
        provisional_agreements=len(provisional),provisional_with_future_original_selection=sum(not x['old_selection_known_at_corrected_decision'] for x in provisional),
        sample_is_full_entry_causal_population=False,performance_authorized=False,
        first_worldwide_release_certified=False,independent_human_review=False,
        code_sha256=digest(Path(__file__)),files={'selection-causality.json':digest(root/'selection-causality.json')},
        sql=False,api_calls=0,training=False,price_outcomes=False,orders=False)
    atomic_json(root/'final-audit.json',result);print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);audit(p.parse_args().output)
