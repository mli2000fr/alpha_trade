"""Web-backed probability proposals. No automatic authorization to buy."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import uuid

from common.q051_paper import reference
from service.llm_directional.prompts import PROBABILITY_VERSION
from service.llm_directional.repository import Repository
from service.llm_directional.runner import analyze, qualified_selection
from .llm_filter import manual_config, contexts


def config(horizon, count):
    cfg=manual_config(horizon,count)
    if cfg.analysis_mode!='web_search':
        raise ValueError('Probabilité sans SL : config.yaml → llm_directional_filter.analysis_mode: web_search requis')
    return replace(cfg,scoring_mode='long_without_stop_probability',separate_trend_evidence=False,
                   min_confidence=0.,max_selected=count)


def apply(engine, ranked, *, run_id, batch, day, horizon):
    frame=ranked.copy();frame['selected_before_llm']=frame.selected.astype(bool)
    candidates=frame[frame.selected].sort_values('rank')
    cfg=config(horizon,len(candidates))
    contract=dict(event='POSITIVE_EXIT_AND_NO_STOP_TOUCH',horizon_sessions=horizon,
                  stop_loss_pct=reference()['winner']['stop_loss_pct'],exit_session=horizon+1,
                  entry='ACTUAL_REGULAR_HOURS_J1_FILL',entry_day_counts_as_one=True,
                  take_profit_pct=None,trailing_stop_pct=None,return_basis='GROSS_PRICE')
    if not candidates.empty:
        packets=contexts(engine,candidates,day=day,horizon=horizon,config=cfg,parent_run_id=run_id)
        if len(packets)!=len(candidates) or {p['symbol'] for p in packets}!=set(candidates.symbol):
            raise ValueError('Candidats de probabilité différents du classement LONG')
        for packet in packets:
            packet['analysis_protocol']=PROBABILITY_VERSION
            packet['long_without_stop_contract']=contract
            source=candidates[candidates.symbol==packet['symbol']].iloc[0]
            packet['per_symbol_long_context']={k:float(source[k]) for k in ['long_probability','long_auc']
                                               if k in source and source[k] is not None}
        llm_id='llm-'+uuid.uuid4().hex
        from service.llm_directional.repository import utcnow
        from service.pipeline_telegram import notify_llm
        attempted=utcnow()
        try:
            analyze(engine=engine,batch_id=batch,trade_date=day,symbol_source='q051-selection:'+run_id,
                    capital_preset_key='q051_frozen_profile',config=cfg,run_id=llm_id,inputs=packets)
        finally:
            notify_llm(engine,llm_id,attempted_at=attempted,trade_date=str(day),provider_label=cfg.provider_label)
        run,eligible=qualified_selection(engine,llm_id,day,'default')
        _,items=Repository(engine).get(llm_id)
        assessments={i['symbol']:json.loads(i['assessment_json']) for i in items}
        allowed={i['symbol'] for i in eligible}
        if not allowed.issubset(set(candidates.symbol)):
            raise ValueError('La probabilité ne peut ajouter de nouveaux candidats')
        completed=run['completed_at'].replace(tzinfo=UTC) if run['completed_at'].tzinfo is None else run['completed_at']
        expiry=(completed+timedelta(hours=cfg.max_run_age_hours)).isoformat()
        input_hash=run['input_sha256']
    else:
        llm_id=None;assessments={};allowed=set();input_hash=None
        expiry=(datetime.now(UTC)+timedelta(hours=cfg.max_run_age_hours)).isoformat()
    frame['llm_probability_up_without_stop']=frame.symbol.map(lambda s:assessments.get(s,{}).get('probability_up_without_stop'))
    frame['llm_explanation']=frame.symbol.map(lambda s:assessments.get(s,{}).get('probability_explanation'))
    frame['llm_evidence_quality']=frame.symbol.map(lambda s:assessments.get(s,{}).get('evidence_quality'))
    frame['llm_blockers']=frame.symbol.map(lambda s:', '.join(assessments.get(s,{}).get('selection_blockers',[])))
    frame['selected']=frame.selected & frame.symbol.isin(allowed)
    receipt=dict(enabled=True,protocol=PROBABILITY_VERSION,approval_required=bool(len(candidates)),
                 run_id=llm_id,requested=len(candidates),selected=sorted(allowed),input_sha256=input_hash,
                 horizon=horizon,contract=contract,approval_expires_at=expiry,
                 provider=cfg.provider_label,analysis_mode='web_search',probability_is_calibrated=False)
    return frame,receipt


def validate(engine,report,ranked,day):
    r=report['llm_filter'];prior=set(ranked.loc[ranked.selected_before_llm,'symbol'])
    current=set(ranked.loc[ranked.selected,'symbol'])
    if not prior:
        if r['run_id'] or current or r['requested']!=0:raise ValueError('Proposition vide incohérente')
        return
    run,eligible=qualified_selection(engine,r['run_id'],day,'default')
    snapshot=json.loads(run['input_json'])
    expected=dict(event='POSITIVE_EXIT_AND_NO_STOP_TOUCH',horizon_sessions=r['horizon'],
                  stop_loss_pct=report['profile']['winner']['stop_loss_pct'],exit_session=r['horizon']+1,
                  entry='ACTUAL_REGULAR_HOURS_J1_FILL',entry_day_counts_as_one=True,
                  take_profit_pct=None,trailing_stop_pct=None,return_basis='GROSS_PRICE')
    if (run['protocol_version']!=PROBABILITY_VERSION or run['batch_id']!=report['batch_id']
            or run['input_sha256']!=r['input_sha256'] or r['contract']!=expected
            or r['horizon']!=report['profile']['winner']['horizon_sessions']
            or snapshot['symbol_source']!='q051-selection:'+report['run_id']
            or {p['symbol'] for p in snapshot['candidates']}!=prior
            or any(p.get('parent_q051_run_id')!=report['run_id'] or p.get('long_without_stop_contract')!=expected
                   for p in snapshot['candidates'])
            or current!={i['symbol'] for i in eligible} or current!=set(r['selected'])):
        raise ValueError('Proposition de probabilité altérée ou autre contrat')
