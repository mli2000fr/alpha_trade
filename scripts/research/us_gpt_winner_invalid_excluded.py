"""2025 frozen replay: validated GPT vetoes plus explicit invalid-answer exclusions.

User-authorized policy change; original paid receipts and protocol stay untouched.
No inference, provider download, shared SQL write or broker order.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import json

import numpy as np
import pandas as pd

from scripts.research import us_gpt_winner_ab as source
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from service.local_ai.research_veto import validate_response

ROOT = Path('artifacts/research/us_gpt_winner_invalid_excluded/20261108-v2')
METRICS = ('initial_equity','final_equity','return_pct','max_drawdown_pct',
    'closed_lot_trades','winners','losers','win_pct','gross_winning_pnl',
    'gross_losing_pnl','average_winning_pnl','average_losing_pnl',
    'average_winning_holding_days','average_losing_holding_days',
    'average_gross_capital','maximum_gross_capital','costs','margin_interest')


def decisions_for(packets, records):
    rows=[]; identities=set()
    for packet in packets:
        identity=(packet['signal_date'],packet['symbol'])
        if identity in identities:
            raise ValueError('Candidature dupliquée')
        identities.add(identity)
        saved=records.get(packet['key'])
        if saved is None:
            raise ValueError('Réponse absente : ne pas assimiler un dossier non traité aux onze invalides')
        validation=saved['validation']
        if not packet['context']['news']:
            if saved['response'] is not None or not validation.get('valid') or validation.get('veto'):
                raise ValueError('Dossier sans news incohérent')
            reason='NO_NEWS_KEEP_BASELINE';excluded=False
        elif not validation.get('valid'):
            if saved['response'] is None:
                raise ValueError('Réponse invalide sans reçu : qualification nécessaire')
            reason='INVALID_RESPONSE_EXCLUDED';excluded=True
        else:
            checked=validate_response(saved['response'],packet)
            excluded=checked['veto']
            reason='VALIDATED_GPT_VETO' if excluded else 'VALID_RESPONSE_KEEP_BASELINE'
        rows.append(dict(signal_date=identity[0],symbol=identity[1],request_key=packet['key'],
            excluded=excluded,reason=reason,original_valid=validation['valid'],
            original_error=validation.get('error')))
    return rows


def frozen_decisions():
    source.verify(source.ROOT)
    dbpath=source.ROOT/'analyses.sqlite3'
    db=sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        records={key:dict(validation=json.loads(v),response=json.loads(r) if r else None)
            for key,v,r in db.execute('SELECT a.request_key,a.validation_json,a.response_json '
                'FROM attempts a WHERE a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.request_key=a.request_key)')}
    finally:db.close()
    return decisions_for(source.read(source.ROOT/'requests.json'),records)


def run(root):
    from collections import Counter
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid

    root.mkdir(parents=True,exist_ok=False)
    try:
        rows=frozen_decisions();counts=dict(Counter(r['reason'] for r in rows))
        if counts.get('INVALID_RESPONSE_EXCLUDED')!=11 or counts.get('VALIDATED_GPT_VETO')!=34:
            raise ValueError('La cohorte ne correspond plus aux onze invalides et 34 vetoes autorisés')
        base=pd.read_parquet(source.ROOT/'signals.parquet')
        keys={(str(r.trade_date)[:10],r.symbol) for r in base.itertuples()}
        if len(base)!=len(rows) or keys!={(r['signal_date'],r['symbol']) for r in rows}:
            raise ValueError('Décisions et signaux ne correspondent pas exactement')
        excluded={(r['signal_date'],r['symbol']) for r in rows if r['excluded']}
        selected=base.loc[[(str(r.trade_date)[:10],r.symbol) not in excluded for r in base.itertuples()]]
        pd.DataFrame(rows).to_csv(root/'decisions.csv',index=False)
        selected.to_parquet(root/'selected-signals.parquet',index=False)
        protocol=dict(policy='INVALID_RESPONSE_EXCLUDED_NO_REFILL',source=str(source.ROOT),
            authorized_at_utc=datetime.now(timezone.utc).isoformat(),year=2025,
            selection_counts=counts,baseline_candidates=len(base),filtered_candidates=len(selected),
            source_hashes={n:digest(source.ROOT/n) for n in ('protocol.json','requests.json','signals.parquet','analyses.sqlite3')},
            files={n:digest(root/n) for n in ('decisions.csv','selected-signals.parquet')},
            script_sha256=digest(Path(__file__)),api_calls=0,broker_calls=0,shared_sql_writes=0,
            strict_pit=False,independent_holdout=False,
            limitation='Rétrospectif ; versions des news et mémoire LLM non PIT ; décision modifiée après validation technique.')
        atomic_json(root/'protocol.json',protocol)
        grid.verify_inputs(grid.ROOT);grid.initialize_worker(grid.ROOT)
        reference=source.read(grid.REFERENCE/'report.json');reports=[]
        for arm,signals in [('A_REFERENCE',base),('B_GPT_INVALID_EXCLUDED',selected)]:
            out=root/arm;out.mkdir()
            with ReadOnlyReplay(root).install():
                def progress(done,total,day):
                    atomic_json(root/'progress.json',dict(status='REPLAYING',arm=arm,
                        completed=done,total=total,last_date=str(day)))
                cfg=grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
                result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
                    high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
                    signals_df=signals,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
                    winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
                report=metrics(result,4000.)
                if arm=='A_REFERENCE':
                    for key in METRICS:
                        if not np.isclose(report[key],reference[key],rtol=1e-10,atol=1e-6):
                            raise ValueError('Référence non reproduite : '+key)
                report.update(arm=arm,selected_signals=len(signals),excluded_signals=len(base)-len(signals),
                    invalid_exclusions=11 if arm!='A_REFERENCE' else 0,
                    validated_veto_exclusions=34 if arm!='A_REFERENCE' else 0,strict_pit=False)
                atomic_json(out/'report.json',report)
                result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
                result.closed_trades_df.to_csv(out/'trades.csv',index=False)
                result.trade_events_df.to_csv(out/'events.csv',index=False)
                signals.to_csv(out/'signals.csv',index=False)
                reports.append(report)
        table=pd.DataFrame([{k:r[k] for k in ('arm',)+METRICS+('selected_signals','excluded_signals',
            'invalid_exclusions','validated_veto_exclusions')} for r in reports])
        table.to_csv(root/'comparison.csv',index=False)
        report=dict(status='COMPLETED_EXPLORATORY',reference_reproduction='PASS',arms=reports,
            api_calls=0,broker_calls=0,shared_sql_writes=0,strict_pit=False,selection_counts=counts)
        atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],arms=2))
        return table.to_dict('records')
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    args=parser.parse_args()
    print(json.dumps(run(args.output_dir),ensure_ascii=False))


if __name__=='__main__':main()
