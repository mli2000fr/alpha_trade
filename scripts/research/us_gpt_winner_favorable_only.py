"""2025: buy only valid FAVORABLE GPT answers, using saved receipts exclusively."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import json

import numpy as np
import pandas as pd

from scripts.research import us_gpt_winner_ab as source
from scripts.research.us_gpt_winner_invalid_excluded import METRICS
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from service.local_ai.research_veto import validate_response

ROOT=Path('artifacts/research/us_gpt_winner_favorable_only/20261108-v1')
PREVIOUS=Path('artifacts/research/us_gpt_winner_invalid_excluded/20261108-v2')


def classify(packets,records):
    rows=[];identities=set()
    for p in packets:
        identity=(p['signal_date'],p['symbol'])
        if identity in identities:raise ValueError('Candidature dupliquée')
        identities.add(identity)
        saved=records.get(p['key'])
        if saved is None:raise ValueError('Réponse manquante')
        valid=saved['validation']['valid'];assessment=None;quality=None
        if valid and p['context']['news']:
            checked=validate_response(saved['response'],p)
            assessment=checked['analysis']['assessment'];quality=checked['analysis']['evidence_quality']
        favorable=valid and assessment=='FAVORABLE'
        rows.append(dict(signal_date=identity[0],symbol=identity[1],request_key=p['key'],
            original_valid=valid,has_news=bool(p['context']['news']),assessment=assessment,evidence_quality=quality,
            FAVORABLE_ONLY=favorable,FAVORABLE_SUFFICIENT_ONLY=favorable and quality=='SUFFICIENT'))
    return rows


def run(root):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid
    root.mkdir(parents=True,exist_ok=False)
    try:
        _,packets=source.verify(source.ROOT)
        db=sqlite3.connect((source.ROOT/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        try:
            records={key:dict(validation=json.loads(v),response=json.loads(raw) if raw else None)
                for key,v,raw in db.execute('SELECT a.request_key,a.validation_json,a.response_json '
                    'FROM attempts a WHERE a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.request_key=a.request_key)')}
        finally:db.close()
        rows=classify(packets,records);ledger=pd.DataFrame(rows)
        counts={arm:int(ledger[arm].sum()) for arm in ('FAVORABLE_ONLY','FAVORABLE_SUFFICIENT_ONLY')}
        if counts!={'FAVORABLE_ONLY':17,'FAVORABLE_SUFFICIENT_ONLY':16}:
            raise ValueError('Cohorte favorable différente de la source analysée')
        base=pd.read_parquet(source.ROOT/'signals.parquet')
        if len(base)!=len(rows) or {(str(r.trade_date)[:10],r.symbol) for r in base.itertuples()}!={(r['signal_date'],r['symbol']) for r in rows}:
            raise ValueError('Incohérence signaux / réponses')
        ledger.to_csv(root/'decisions.csv',index=False)
        previous=source.read(PREVIOUS/'report.json')
        if previous['reference_reproduction']!='PASS':raise ValueError('Témoin précédent non validé')
        reference=source.read(grid.REFERENCE/'report.json')
        reports=list(previous['arms'])
        for k in METRICS:
            if not np.isclose(reports[0][k],reference[k],rtol=1e-10,atol=1e-6):raise ValueError('Référence différente : '+k)
        protocol=dict(year=2025,source=str(source.ROOT),policy='PRIMARY_VALID_FAVORABLE_ONLY',
            secondary_policy='ALSO_REQUIRE_SUFFICIENT_EVIDENCE',selection_counts=counts,refill=False,
            no_news='EXCLUDE',invalid='EXCLUDE',indeterminable='EXCLUDE',
            source_hashes={n:digest(source.ROOT/n) for n in ('protocol.json','requests.json','signals.parquet','analyses.sqlite3')},
            baseline_report_sha256=digest(PREVIOUS/'report.json'),baseline_reused=True,
            baseline_previously_reproduced=True,script_sha256=digest(Path(__file__)),
            authorized_at_utc=datetime.now(timezone.utc).isoformat(),api_calls=0,broker_calls=0,shared_sql_writes=0,
            strict_pit=False,independent_holdout=False)
        atomic_json(root/'protocol.json',protocol)
        grid.verify_inputs(grid.ROOT);grid.initialize_worker(grid.ROOT)
        for arm in counts:
            out=root/arm;out.mkdir()
            retained={(r['signal_date'],r['symbol']) for r in rows if r[arm]}
            selected=base.loc[[(str(r.trade_date)[:10],r.symbol) in retained for r in base.itertuples()]]
            selected.to_csv(out/'signals.csv',index=False)
            with ReadOnlyReplay(root).install():
                def progress(done,total,day):
                    atomic_json(root/'progress.json',dict(status='REPLAYING',arm=arm,completed=done,total=total,last_date=str(day)))
                cfg=grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
                result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
                    high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
                    signals_df=selected,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
                    winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
                report=metrics(result,4000.)
                report.update(arm=arm,selected_signals=len(selected),excluded_signals=len(base)-len(selected),strict_pit=False)
                atomic_json(out/'report.json',report)
                result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
                result.closed_trades_df.to_csv(out/'trades.csv',index=False)
                result.trade_events_df.to_csv(out/'events.csv',index=False)
                reports.append(report)
        table=pd.DataFrame([{k:r.get(k) for k in ('arm',)+METRICS+('selected_signals','excluded_signals')} for r in reports])
        table.to_csv(root/'comparison.csv',index=False)
        atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY',arms=reports,api_calls=0,broker_calls=0,
            strict_pit=False,baseline_reused=True,selection_counts=counts))
        atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY',new_arms=2))
        return table.to_dict('records')
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT)
    args=parser.parse_args();print(json.dumps(run(args.output_dir),ensure_ascii=False))


if __name__=='__main__':main()
