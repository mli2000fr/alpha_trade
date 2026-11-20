"""One immutable human subset per sealed probability proposal; no broker calls."""
from copy import deepcopy
from datetime import UTC, datetime
import json
import logging
import math
import os
from pathlib import Path
import tempfile
import time

LOG=logging.getLogger(__name__)

EVIDENCE_BLOCKERS=frozenset({'insufficient_fresh_sources','excluded_untraceable_sources',
    'excluded_untraceable_local_sources','insufficient_qualified_local_sources',
    'evidence_partial','evidence_insufficient'})


def selection_policy():
    from common.config_loader import load_config
    value=(load_config().get('us_pipeline') or {}).get('gpt_require_qualified_evidence_for_manual_selection',True)
    if type(value) is not bool:raise ValueError('gpt_require_qualified_evidence_for_manual_selection : booléen requis')
    return dict(require_qualified_evidence=value)


def selectable_symbols(frame,policy):
    """Relax evidence only; unknown blockers and missing estimates remain blocked."""
    if set(policy)!={'require_qualified_evidence'} or type(policy['require_qualified_evidence']) is not bool:
        raise ValueError('Politique de sélection manuelle incompatible')
    if policy['require_qualified_evidence']:return set(frame.loc[frame.selected,'symbol'])
    allowed=set(frame.loc[frame.selected,'symbol'])
    for row in frame.loc[frame.selected_before_llm].to_dict('records'):
        p=row.get('llm_probability_up_without_stop')
        blockers=row.get('llm_blockers')
        if (type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1
                or not isinstance(blockers,str)):
            continue
        reasons={v.strip() for v in blockers.split(',') if v.strip()}
        if reasons<=EVIDENCE_BLOCKERS:allowed.add(row['symbol'])
    return allowed


def evidence_overrides(frame,symbols):
    return [dict(symbol=r['symbol'],evidence_quality=r.get('llm_evidence_quality'),
                 blockers=r.get('llm_blockers')) for r in frame.sort_values('symbol').to_dict('records')
            if r['symbol'] in symbols and not r['selected']]


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
    if not isinstance(selected,list) or any(not isinstance(s,str) for s in selected):
        raise ValueError('Liste de la validation humaine incompatible')
    version=value.get('schema_version')
    if version==1:
        if 'selection_policy' in value or 'evidence_overrides' in value:
            raise ValueError('Ancienne validation modifiée avec une nouvelle politique')
        policy=dict(require_qualified_evidence=True)
    elif version==2:
        policy=value.get('selection_policy')
        if not isinstance(policy,dict):raise ValueError('Politique de validation absente')
        if value.get('evidence_overrides')!=evidence_overrides(frame,selected or []):
            raise ValueError('Dérogations de la validation humaine incompatibles avec la proposition')
    else:raise ValueError('Version de validation humaine incompatible')
    eligible=selectable_symbols(frame,policy)
    if (value.get('action')!='EXPLICIT_UI_VALIDATION'
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
    updated['llm_filter']['manual_selection_policy']=value.get('selection_policy',dict(require_qualified_evidence=True))
    updated['llm_filter']['evidence_overrides']=value.get('evidence_overrides',[])
    return updated,ranked


def validate_choice(engine,run_id,symbols,*,policy=None):
    """Read-only qualification of a proposed subset; never publishes approval."""
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
    policy=selection_policy() if policy is None else policy
    if (not isinstance(symbols,list) or any(not isinstance(s,str) for s in symbols)
            or len(set(symbols))!=len(symbols) or not set(symbols).issubset(selectable_symbols(frame,policy))):
        raise ValueError('Choisir uniquement des candidats avec probabilité valide et contrôles requis qualifiés')
    ordered=frame[frame.symbol.isin(symbols)].sort_values(['llm_probability_up_without_stop','oracle_rank'],ascending=[False,True]).symbol.tolist()
    return folder,report,frame,ordered


def approve(engine,run_id,symbols):
    from .pipeline import digest
    policy=selection_policy()
    folder,report,frame,ordered=validate_choice(engine,run_id,symbols,policy=policy)
    value=dict(schema_version=2,run_id=run_id,selected_symbols=ordered,
               selection_policy=policy,evidence_overrides=evidence_overrides(frame,ordered),
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
