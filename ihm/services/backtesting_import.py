"""Register completed research results for inspection, without running a simulation."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ihm.services import backtesting_registry as registry


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def import_continuous_winner(source, *, run_id, label='Continu 2021–2026 — modèles annuels',
                             result_subdir='continuous-uniform20pct'):
    source=Path(source).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('Identifiant de run invalide')
    if Path(result_subdir).name!=result_subdir or result_subdir in ('.','..'):
        raise ValueError('Répertoire de résultats invalide')
    output=source/result_subdir
    plan=read(source/'protocol.json');native=read(output/'report.json')
    if (read(source/'progress.json').get('status')!='COMPLETED_EXPLORATORY'
            or native.get('status') not in ('COMPLETED_EXPLORATORY','INCOMPLETE_COVERAGE')):
        raise ValueError('Importer uniquement un replay terminé avec un bilan qualifié')
    isolation=read(source/'isolation.json')
    if isolation.get('status')!='COMPLETED' or isolation.get('violations'):
        raise ValueError('Finalisation de l’isolation non validée')
    files=['report.json','annual-summary.csv','trades.csv','events.csv','equity-daily.csv',
           'equity-5m.parquet','risk-5m.csv','configuration.json']
    hashes={name:digest(output/name) for name in files}
    hashes['source-protocol.json']=digest(source/'protocol.json')
    folder=registry.RUNS_DIR/'run'/run_id
    with registry._REGISTRY_LOCK:
        prior=registry._read_history_index().get(run_id)
    if prior:
        receipt=read(folder/'import.json')
        if receipt['source_hashes']!=hashes or receipt['source']!=str(source):
            raise ValueError('Cet identifiant référence une autre archive ; import refusé')
        return prior
    folder.mkdir(parents=True,exist_ok=False);artifacts=folder/'artifacts';artifacts.mkdir()
    # Owned copies: deleting the IHM record must never delete the research source.
    for name in files:shutil.copyfile(output/name,artifacts/('source-report.json' if name=='report.json' else name))
    shutil.copyfile(source/'protocol.json',artifacts/'source-protocol.json')
    daily=pd.read_csv(artifacts/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0]
    trades=pd.read_csv(artifacts/'trades.csv')
    for name in ('entry_date','exit_date'):trades[name]=pd.to_datetime(trades[name],utc=True)
    intraday=pd.read_parquet(artifacts/'equity-5m.parquet')
    from backtesting.simulator import BacktestResult
    from backtesting.winner_campaign_replay import export_ui_report,atomic_json
    from backtesting.isolation import ReadOnlyReplay
    result=BacktestResult(equity_curve=daily,closed_trades_df=trades,intraday_equity_curve=intraday,
        trade_events_df=pd.read_csv(artifacts/'events.csv'),
        drawdown_breaker_df=pd.read_csv(artifacts/'risk-5m.csv'),tracker_snapshot={'winner_replay':native})
    report={**native,'limitations':[
        'Replay exploratoire ; couverture intraday partielle avec protections OHLC journalières.',
        'Secteurs actuels et prix révisables ; absence de certification PIT complète et de parité live.',
        'Portefeuille continu : positions, capital et état du risque transmis entre années.',
        'DD15 est un déclencheur de liquidation partielle, pas un plafond garanti.']}
    protocol={**plan['reference'],'observed_at_utc':native['finished_at_utc'],
        'start':plan['start'],'end':plan['end'],'annual_models':plan['annual_models'],
        'annual_reset':False,'source':str(source),'imported_result':True}
    with ReadOnlyReplay(folder).install():
        export_ui_report(result,report,protocol,artifacts,float(native['initial_equity']))
        for a,b in [('final_value','final_equity'),('total_return_pct','return_pct'),
                    ('win_rate_pct','win_pct'),('total_trades','closed_lot_trades')]:
            if not np.isclose(report['summary'][a],native[b],rtol=1e-10,atol=1e-6):
                raise ValueError('Conversion IHM incohérente : '+a)
        report['run_metadata'].update(imported_result=True,source=str(source),
            annual_models=plan['annual_models'],annual_reset=False)
        annual=pd.read_csv(artifacts/'annual-summary.csv').astype(object)
        report['annual_summary']=annual.where(pd.notna(annual),None).to_dict('records')
        atomic_json(artifacts/'report.json',report)
        atomic_json(artifacts/'progress.json',dict(status=native['status'],completed=len(daily),total=len(daily)))
    imported=datetime.now(timezone.utc).isoformat()
    atomic_json(folder/'import.json',dict(source=str(source),source_hashes=hashes,
        imported_at_utc=imported,simulation_replayed=False,source_untouched=True))
    # Preserve the original time of the simulation; importing is not a new run.
    tz=ZoneInfo('Europe/Paris')
    started=datetime.fromtimestamp((output/'configuration.json').stat().st_mtime,timezone.utc)
    finished=datetime.fromisoformat(native['finished_at_utc'])
    note=f'Résultat importé : {label}\nSource : {source}\nAucune simulation relancée.\n'
    (folder/'stdout.log').write_text(note,encoding='utf-8')
    (folder/'stderr.log').write_text('',encoding='utf-8')
    (folder/'combined.log').write_text(note,encoding='utf-8')
    command=plan.get('replay_command') or [sys.executable,'-m',
        'scripts.research.us_winner_continuous_registry_recovery_20261108','--output-dir',str(source)]
    if not isinstance(command,list) or not all(isinstance(x,str) for x in command):
        raise ValueError('Commande de provenance invalide')
    record=registry.BacktestingRunRecord(run_id=run_id,run_kind='run',run_label=label,
        command=command,command_display=registry.format_command_for_display(command),status='completed',
        executed_at=started.astimezone(tz).isoformat(),finished_at=finished.astimezone(tz).isoformat(),
        returncode=0,duration_seconds=max(0.,(finished-started).total_seconds()),
        stdout_path=str(folder/'stdout.log'),stderr_path=str(folder/'stderr.log'),
        combined_path=str(folder/'combined.log'),stdout_lines=3,isolation_mode='READ_ONLY_IMPORTED',
        log_capture='imported_report').to_state()
    record.update(imported_result=True,result_engine='winner_campaign_replay',source_artifacts_dir=str(source),
        start_date=plan['start'],end_date=plan['end'],imported_at_utc=imported)
    for name,sha in hashes.items():
        path=source/'protocol.json' if name=='source-protocol.json' else output/name
        if digest(path)!=sha:raise ValueError('Source modifiée pendant l’import : '+name)
    with registry._REGISTRY_LOCK:
        index=registry._read_history_index()
        if run_id in index:raise ValueError('Run enregistré pendant l’import ; vérifier avant reprise')
        index[run_id]=record;registry._write_history_index(index)
    return record
