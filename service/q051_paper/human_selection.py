"""One immutable human subset per sealed probability proposal; no broker calls."""
from copy import deepcopy
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import tempfile
import time

LOG=logging.getLogger(__name__)


def required(report):
    return report.get('llm_filter',{}).get('approval_required') is True


def check_expiry(report,now=None):
    stamp=datetime.fromisoformat(report['llm_filter']['approval_expires_at'])
    if stamp.tzinfo is None or (now or datetime.now(UTC))>=stamp:
        raise ValueError('Analyse expirée : lancer un nouveau batch ou pipeline avec une nouvelle étape 10 ; '
                         'ne pas reprendre les étapes 11/12 avec cette ancienne sélection')


def approval_path(folder):
    return Path(folder)/'human_selection.json'


def read(folder,report,frame,*,now=None):
    from .pipeline import digest
    if not required(report):return None
    path=approval_path(folder)
    if not path.is_file():raise ValueError('Validation manuelle requise : cocher les titres puis Valider la sélection dans Pipeline')
    check_expiry(report,now)
    value=json.loads(path.read_text(encoding='utf-8'))
    try:
        approved=datetime.fromisoformat(value['approved_at'])
        if approved.tzinfo is None or approved>(now or datetime.now(UTC)):
            raise ValueError('Horodatage de validation humain futur ou sans fuseau')
    except (KeyError,TypeError):
        raise ValueError('Horodatage de validation humaine absent ou invalide') from None
    selected=value.get('selected_symbols')
    eligible=set(frame.loc[frame.selected,'symbol'])
    if (value.get('schema_version')!=1 or value.get('action')!='EXPLICIT_UI_VALIDATION'
            or value.get('account_scope')!='SHARED_PAPER_SELECTION' or value.get('run_id')!=report['run_id']
            or value.get('report_sha256')!=digest(Path(folder)/'selection.json')
            or value.get('selection_sha256')!=digest(Path(folder)/'selection.parquet')
            or value.get('llm_input_sha256')!=report['llm_filter']['input_sha256']
            or not isinstance(selected,list) or any(not isinstance(s,str) for s in selected)
            or len(set(selected))!=len(selected)
            or not set(selected).issubset(eligible)):
        raise ValueError('Validation humaine incompatible avec la proposition scellée')
    return value


def effective(folder,report,frame):
    from .pipeline import digest
    value=read(folder,report,frame)
    if value is None:return report,frame
    updated=deepcopy(report);ranked=frame.copy()
    symbols=value['selected_symbols']
    ranked['selected']=ranked.symbol.isin(symbols)
    ranked['per_symbol_selection_rank']=ranked['rank']
    order={s:i+1 for i,s in enumerate(symbols)}
    ranked.loc[ranked.selected,'rank']=ranked.loc[ranked.selected,'symbol'].map(order)
    updated['selected']=symbols
    updated['human_selection_sha256']=digest(approval_path(folder))
    updated['llm_filter']['eligible_before_human']=report['llm_filter']['selected']
    updated['llm_filter']['selected']=symbols
    return updated,ranked


def approve(engine,run_id,symbols):
    from common.q051_paper import profile_scope,settings
    from .pipeline import directory,qualified,digest
    folder=directory(run_id)
    saved=json.loads((folder/'selection.json').read_text(encoding='utf-8'))
    from datetime import date
    import pandas as pd
    with profile_scope(saved['strategy_profile']):
        _,report=qualified(run_id,batch=saved['batch_id'],day=date.fromisoformat(saved['trade_date']),
                           artifacts_dir=settings()['artifacts_dir'],engine=engine,require_human=False)
    if not required(report):raise ValueError('Cette sélection ne demande pas de validation humaine')
    check_expiry(report)
    frame=pd.read_parquet(folder/'selection.parquet')
    if (not isinstance(symbols,list) or any(not isinstance(s,str) for s in symbols)
            or len(set(symbols))!=len(symbols) or not set(symbols).issubset(set(frame.loc[frame.selected,'symbol']))):
        raise ValueError('Choisir uniquement des candidats dont la probabilité et les preuves sont qualifiées')
    ordered=frame[frame.symbol.isin(symbols)].sort_values(['llm_probability_up_without_stop','oracle_rank'],ascending=[False,True]).symbol.tolist()
    value=dict(schema_version=1,run_id=run_id,selected_symbols=ordered,
               report_sha256=digest(folder/'selection.json'),selection_sha256=digest(folder/'selection.parquet'),
               llm_input_sha256=report['llm_filter']['input_sha256'],approved_at=datetime.now(UTC).isoformat(),
               action='EXPLICIT_UI_VALIDATION',account_scope='SHARED_PAPER_SELECTION')
    target=approval_path(folder)
    if target.exists():
        existing=read(folder,report,frame)
        if existing['selected_symbols']==ordered:return existing
        raise ValueError('Une sélection a déjà été validée ; elle ne peut pas être remplacée après reprise du risque')
    descriptor,temp=tempfile.mkstemp(prefix='.human-selection-',suffix='.tmp',dir=folder)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        if os.name=='nt':
            os.rename(temp,target)  # Windows rename is atomic and refuses an existing target.
        else:
            os.link(temp,target)  # POSIX rename would overwrite; use no-replace link instead.
    finally:
        Path(temp).unlink(missing_ok=True)
    return value


def wait_for_selection(options,stop_event):
    from .pipeline import directory,digest
    folder=directory(options.q051_run_id)
    report=json.loads((folder/'selection.json').read_text(encoding='utf-8'))
    if not required(report):return None
    seal=json.loads((folder/'seal.json').read_text(encoding='utf-8'))
    if (seal['report_sha256']!=digest(folder/'selection.json') or report['run_id']!=options.q051_run_id
            or report['batch_id']!=options.ml_predict_batch_id or report['trade_date']!=options.trade_date
            or report['selection_sha256']!=digest(folder/'selection.parquet')):
        raise ValueError('Proposition en attente incompatible avec ce workflow')
    import pandas as pd
    frame=pd.read_parquet(folder/'selection.parquet')
    last_log=None
    while not stop_event.is_set():
        check_expiry(report)
        if approval_path(folder).is_file():
            selection=read(folder,report,frame)
            return dict(status='HUMAN_SELECTION_VALIDATED',run_id=options.q051_run_id,count=len(selection['selected_symbols']))
        if last_log is None or time.monotonic()-last_log>=30:
            LOG.info('Validation manuelle attendue pour %s : choisir les titres dans Pipeline ; étape11 bloquée.',options.q051_run_id)
            last_log=time.monotonic()
        stop_event.wait(1.)
    return dict(status='STOPPED_WAITING_HUMAN_SELECTION')
