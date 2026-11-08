"""Sequential local inference followed by the two frozen A/B replays only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def cache_counts(root):
    packets = read(root/'requests.json')
    path = root/'analyses.sqlite3'
    records = {}
    if path.exists():
        conn = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
        try:
            records = {key:json.loads(value) for key,value in conn.execute(
                'SELECT a.request_key,a.validation_json FROM attempts a JOIN '
                '(SELECT request_key,MAX(id) id FROM attempts GROUP BY request_key) b ON a.id=b.id')}
        finally:
            conn.close()
    values = [records.get(p['key']) for p in packets]
    return dict(total=len(packets),valid=sum(bool(v and v['valid']) for v in values),
        invalid=sum(bool(v and not v['valid']) for v in values),pending=sum(v is None for v in values),
        no_news=sum(not p['context']['news'] for p in packets),
        vetoes=sum(bool(v and v['valid'] and v['veto']) for v in values))


def launch(root,phase,monitor):
    command = [sys.executable,'-X','utf8','-u','-m','scripts.research.us_local_llm_winner_ab',
               phase,'--output-dir',str(root)]
    if phase=='analyze':
        command += ['--limit','204']
    with (root/'campaign'/f'{phase}.log').open('x',encoding='utf8') as log:
        process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        while process.poll() is None:
            state = dict(status='ANALYZING_LOCAL' if phase=='analyze' else 'REPLAYING_A_B',
                child_pid=process.pid,phase=phase,updated_at_utc=datetime.now(timezone.utc).isoformat())
            if phase=='analyze':
                state.update(cache_counts(root))
                progress_path = root/'progress.json'
                if progress_path.exists():
                    state['analysis_progress'] = read(progress_path)
            else:
                state['arms'] = {name:read(root/'replay'/name/'progress.json')
                    for name in ('A_REFERENCE','B_LOCAL_VETO') if (root/'replay'/name/'progress.json').exists()}
            atomic_json(monitor,state)
            time.sleep(10)
        return process.returncode


def run(root,runner=launch):
    folder = root/'campaign'
    folder.mkdir(exist_ok=True)
    with exclusive_run(folder):
        if (folder/'report.json').exists() or (folder/'analyze.log').exists():
            raise ValueError('Campagne déjà tentée : vérifier son bilan avant reprise, aucun écrasement')
        manifest = dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
            protocol_sha256=digest(root/'protocol.json'),coordinator_sha256=digest(Path(__file__)),
            tests=['A_REFERENCE','B_LOCAL_VETO'],test_c=False,cloud_calls=0,broker_calls=0,
            automatic_retries=False,before=cache_counts(root))
        atomic_json(folder/'launch.json',manifest)
        monitor = folder/'progress.json'
        atomic_json(monitor,dict(status='STARTING',**manifest['before']))
        code = runner(root,'analyze',monitor)
        counts = cache_counts(root)
        analysis = read(root/'analysis-report.json') if (root/'analysis-report.json').exists() else {}
        if code!=0 or counts['invalid'] or counts['pending'] or analysis.get('status')!='ANALYSIS_COMPLETE_RESEARCH_ONLY':
            report = dict(status='INCOMPLETE_ANALYSIS_NO_REPLAY',analysis_exit_code=code,
                          analysis=analysis,**counts,cloud_calls=0,broker_calls=0)
        else:
            code = runner(root,'replay',monitor)
            target = root/'replay/report.json'
            if code!=0 or not target.exists():
                report = dict(status='FAILED_REPLAY',replay_exit_code=code,**counts)
            else:
                report = dict(status='COMPLETED_EXPLORATORY',**counts,replay=read(target),
                              strict_pit=False,cloud_calls=0,broker_calls=0)
                arms = report['replay']['arms']
                keys = [('Capital final USD','final_equity'),('Rendement %','return_pct'),
                    ('DD maximal %','max_drawdown_pct'),('Trades clôturés','closed_lot_trades'),
                    ('Taux gagnant %','win_pct'),('Gain moyen USD','average_winning_pnl'),
                    ('Perte moyenne USD','average_losing_pnl'),('Capital moyen engagé USD','average_gross_capital'),
                    ('Capital maximal engagé USD','maximum_gross_capital')]
                lines = ['# Comparaison A/B 2025 — exploratoire', '',
                         '| Mesure | A référence | B veto Qwen |','|---|---:|---:|']
                for label,key in keys:
                    values = [f"{a[key]:.2f}" if a.get(key) is not None else '—' for a in arms]
                    lines.append(f'| {label} | {values[0]} | {values[1]} |')
                lines += ['', 'Sources rétrospectives et mémoire future du LLM non exclue ; '
                    'couverture intraday selon les réserves de la référence. Aucun avantage confirmé hors échantillon.']
                (folder/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_json(folder/'report.json',report);atomic_json(monitor,report)
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    a = p.parse_args()
    report = run(a.output_dir)
    print(json.dumps(report,ensure_ascii=False,default=str))
    if report['status']!='COMPLETED_EXPLORATORY':
        raise SystemExit(2)


if __name__=='__main__':main()
