"""Offline completion checks only: saved replies/portfolios, no API or SQL."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_gpt_q1_2025_continue as collection
from scripts.research import us_news_gpt_q1_2025_evaluate as economic
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def run(root):
    root=Path(root);read=collection.pilot.read
    prepared,analysis,result=[read(root/name) for name in ('prepare.json','analysis.json','q1-results.json')]
    for value in (prepared,analysis,result):verify_hashes(root,value['files'])
    for name in ('protocol.json','analysis-protocol.json','analysis-continuation.json','economic-protocol.json'):
        value=read(root/name);verify_hashes(Path('.'),value['sources'])
    packets=read(root/'packets.json');assessments=read(root/'assessments.json')
    inventory=read(root/'analysis-protocol.json')['request_inventory']
    ids=set();cost=Decimal(0);valid=[]
    for item in inventory:
        packet=packets[item['packet']]
        prefix=root/'api'/f'{item["packet"]:03d}-{packet["decision_date"]}-{packet["symbol"]}'
        request=read(prefix.with_suffix('.request.json'));response=read(prefix.with_suffix('.response.json'))
        assert collection.initial.payload_hash(request)==item['request_sha256']
        assert request==collection.initial.paid_payload(packet,'gpt-6-luna')
        assert request.get('tools',[])==[] and request['service_tier']=='default'
        assert response['id'] not in ids;ids.add(response['id'])
        cost+=Decimal(str(collection.usage_with_cache(response)['gross_cost_estimate_usd']))
        qualified=collection.qualify_or_unknown(response,packet)
        assert qualified==assessments[item['packet']]
        valid.append(qualified)
        cutoff=pd.Timestamp(packet['cutoff_utc'])
        assert all(cutoff-pd.Timedelta(hours=24)<=pd.Timestamp(article['publication_utc'])<cutoff
                   for article in packet['articles'])
        reservation=prefix.with_suffix('.reservation.json')
        if reservation.exists():
            r=read(reservation)
            assert Decimal(str(r['spent_before_usd']))+Decimal(str(r['worst_next_call_usd']))<=Decimal('.50')
    assert len(ids)==len(inventory)==len(list((root/'api').glob('*.request.json')))==213
    assert len(list((root/'api').glob('*.response.json')))==213
    assert not list((root/'api').glob('*.error.json'))
    assert cost<=Decimal('.50')<Decimal('1')
    assert abs(float(cost)-analysis['gross_cost_estimate_usd'])<1e-12
    counts=dict(Counter(item['decision'] for item in assessments))
    assert counts==analysis['decisions'] and len(assessments)==600
    assert sum(item['veto_long'] for item in assessments)==26
    assert sum(item['technical_status']=='INVALID_PRESERVED' for item in assessments)==18
    assert all(not item['veto_long'] for item in assessments if item['technical_status']!='VALID')
    sealed=pd.Timestamp(analysis['completed_at_utc'])
    assert pd.Timestamp(read(root/'economic-protocol.json')['frozen_at_utc'])>sealed
    for name in ('q1-unit-outcomes.json','q1-results.json'):
        assert pd.Timestamp((root/name).stat().st_mtime,unit='s',tz='UTC')>sealed
    candidates=pd.read_parquet(root/'candidates.parquet')
    assert len(candidates)==600 and candidates.date.nunique()==60 and candidates.symbol.nunique()==35
    assert candidates.groupby('date').oracle_rank.apply(lambda ranks:set(ranks)==set(range(1,11))).all()
    economic.merge_decisions(candidates,assessments)
    arms=[]
    for report in result['portfolios']:
        folder=root/report['arm'];trades=pd.read_parquet(folder/'trades.parquet')
        daily=pd.read_parquet(folder/'daily.parquet')
        assert len(daily)==81 and daily.date.min()==pd.Timestamp('2025-01-02')
        assert daily.date.max()==pd.Timestamp('2025-04-30')
        assert trades.side.eq('buy').all() and not trades.exit_reason.str.contains('trailing').any()
        assert np.allclose(1-trades.replay_initial_stop_price/trades.entry_price,.05)
        assert np.allclose(trades.replay_take_profit_price/trades.entry_price-1,.20)
        for _,part in trades.groupby('symbol'):
            part=part.sort_values('entry_date')
            assert (part.entry_date.iloc[1:].to_numpy()>=part.exit_date.iloc[:-1].to_numpy()).all()
        assert daily.positions.iloc[-1]==0 and len(trades)==report['closed_positions']
        assert np.isclose(4000+trades.pnl.sum()-report['margin_interest'],report['capital_final_usd'],atol=1e-7)
        monthly=economic.monthly_curves(daily,trades)
        assert monthly==report['monthly']
        assert np.isclose(np.prod([1+row['return_pct']/100 for row in monthly]),report['capital_final_usd']/4000)
        arms.append(dict(arm=report['arm'],positions=len(trades),reconciliation_error=report['cash_reconciliation_error'],
            last_entry=str(trades.entry_date.max().date()),last_exit=str(trades.exit_date.max().date()),
            exit_reasons=dict(Counter(trades.exit_reason)),tp20_sl5_verified=True,no_trailing=True,
            no_held_symbol_reinforcement=True,continuous_monthly_compounding_verified=True))
    assert result['full_filter_qualified'] is False and result['production_promotion'] is False
    audit=dict(status='PASS_OFFLINE_COMPLETION_CHECKS_NOT_INDEPENDENT_SCIENTIFIC_REVIEW',
        validated_at_utc=datetime.now(timezone.utc).isoformat(),api_calls_in_this_audit=0,
        unique_paid_responses=213,no_paid_retry=True,web_calls=0,technical_unknowns=18,
        actual_cost_conservative_usd=float(cost),user_authorized_cap_usd=1.,stricter_collector_cap_usd=.50,
        raw_inputs_responses_and_sources_hash_verified=True,strict_reparse_exact=True,
        responses_sealed_before_first_economic_outputs=True,portfolios=arms,
        no_new_training=True,no_sql_writes=True,no_broker_orders=True,no_production_changes=True,
        pit_certified=False,llm_future_knowledge_excluded=False,
        files={name:digest(root/name) for name in ('q1-results.json','analysis.json','veto-impact.json')},
        audit_script_sha256=digest(Path(__file__)))
    atomic_json(root/'paid-completion-audit.json',audit)
    return audit


if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.output),default=str))
