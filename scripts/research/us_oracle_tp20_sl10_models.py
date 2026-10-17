"""Three sequential, preregistered offline challengers; original Oracle untouched.

Fit: honest Oracle OOF candidates up to 2021, validation in 2022. External
2024-2026 outcomes never enter fit, thresholds, profile choice or exit decisions.
Unit trade training targets approximate costs; only portfolio replay measures PnL.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from functools import partial
import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import event

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from common.trading_costs import DEFAULT_COST_MODEL
from database.connection import get_sqlalchemy_engine
from execution_engine.models import IntentRole
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle_barrier import SCORES
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_exit_grid import GridLedger, parametric_protections
from scripts.research.us_oracle_barrier_comparison import freeze_candidates,readonly_statement
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
from scripts.research.us_oracle_tp20_sl10_campaign import (
    YEARS,COUNTS,AS_OF,code_hashes,checkpoint,model_contract,read,run_case)

LOG=logging.getLogger(__name__)
FEATURES=['momentum_20','momentum_60','momentum_120','relative_strength_20',
    'relative_strength_60','rolling_volatility_20','rolling_volatility_60','atr20_pct',
    'drawdown_20','high_low_position_20','market_return_20','market_volatility_20',
    'market_trend_strength_50','rsi_14','volume_ratio_20']
SCORE_FEATURES=[SCORES['long'],SCORES['short'],'score_difference']
STATE_FEATURES=['age','pnl','mfe','mae','distance_stop','distance_tp','relative_since_entry']
PROFILES=((.10,.07),(.20,.10),(.25,.10))


def input_matrix(frame,columns):
    if not set(columns)<=set(frame):raise ValueError(f'Missing causal features {set(columns)-set(frame)}')
    return frame[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32)


def unit_path(opens,high,low,entry,*,tp=.2,sl=.1):
    """One LONG path: SL-first collisions, adverse stop gaps, conservative TP gaps.

    Twenty holding sessions plus expiry OPEN. Entry is a realised open proxy,
    not a preview of J+1 used by decision features. Unit labels are not ledger PnL.
    """
    arrays=np.array([opens,high,low],dtype=float)
    if arrays.shape!=(3,21) or not np.isfinite(arrays).all() or (arrays<=0).any() or entry<=0:
        return None
    stop,target=entry*(1-sl),entry*(1+tp)
    for k in range(20):
        if opens[k]<=stop:return k,float(opens[k]),'stop_gap'
        if opens[k]>=target:return k,float(target),'tp_gap'
        if low[k]<=stop:return k,float(stop),'stop'
        if high[k]>=target:return k,float(target),'tp'
    return 20,float(opens[20]),'expiry'


def split_fit_validation(frame):
    # Purge all future label availability, not only decision timestamps.
    available=pd.to_datetime(frame.label_available)
    fit=frame.loc[frame.date.lt('2022-01-01') & available.lt('2022-01-01')]
    val=frame.loc[frame.date.between('2022-01-01','2022-12-31') & available.lt('2023-01-01')]
    if len(fit)<1000 or len(val)<500:raise ValueError('Insufficient purged training/validation sample')
    return fit,val


def train_head(frame,columns,target,*,binary,output):
    fit,val=split_fit_validation(frame)
    if fit[target].nunique()<2 or val[target].nunique()<2:
        raise ValueError('Insufficient target variation')
    params=dict(objective='binary' if binary else 'huber',metric='binary_logloss' if binary else 'l1',
        num_leaves=7,max_depth=3,min_data_in_leaf=200,learning_rate=.03,
        lambda_l1=.1,lambda_l2=1.,feature_fraction=1.,num_threads=3,seed=731,
        deterministic=True,force_col_wise=True,verbosity=-1)
    weights=fit.get('weight',pd.Series(1.,index=fit.index))
    model=lgb.train(params,lgb.Dataset(input_matrix(fit,columns),label=fit[target],weight=weights),
        num_boost_round=150,valid_sets=[lgb.Dataset(input_matrix(val,columns),label=val[target])],
        callbacks=[lgb.early_stopping(15,verbose=False)])
    model.save_model(str(output))
    predictions=model.predict(input_matrix(val,columns),num_threads=3)
    metrics=dict(fit_rows=len(fit),validation_rows=len(val),fit_available_max=str(fit.label_available.max()),
        validation_available_max=str(val.label_available.max()),columns=columns,
        best_iteration=model.best_iteration,validation_target_mean=float(val[target].mean()),
        validation_prediction_mean=float(np.mean(predictions)),
        validation_auc=float(roc_auc_score(val[target],predictions)) if binary else None,
        threshold=.5 if binary else 0.,validation_mae=float(np.mean(abs(predictions-val[target]))),
        model_sha256=digest(output),no_external_labels_used=True)
    atomic_json(output.with_suffix('.json'),metrics)
    return model


def training_data(root,model_root):
    """All-day rank first; keep TOP50 OOF, then annotate label coverage.

    Future path validity is for training labels ONLY. External ranking does not
    use these guards, and unknown held paths remain failures in replay.
    """
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    _,profile,_=model_contract(model_root)
    features=[f for f in FEATURES if f in profile['feature_columns']]
    if len(features)<12:raise ValueError('Causal feature coverage insufficient')
    oof=[]
    source_hashes={}
    for fold in sorted((model_root/'folds').iterdir()):
        done=read(fold/'done.json');verify_hashes(fold,done['files'])
        source_hashes[str(fold/'done.json')]=digest(fold/'done.json')
        f=pd.read_parquet(fold/'oof.parquet')
        f=f.sort_values(['date',SCORES['long'],'symbol'],ascending=[True,False,True])
        f['selection_rank']=f.groupby('date').cumcount()+1
        oof.append(f.loc[f.selection_rank.le(50)&f.date.lt('2023-01-01')])
    candidates=pd.concat(oof,ignore_index=True)
    if candidates.duplicated(['date','symbol']).any():raise ValueError('Overlapping OOF keys')
    parts,states,excluded=[],[],{}
    calendar=nyse_sessions(pd.Timestamp('2016-01-01').date(),pd.Timestamp('2023-12-31').date())
    cost=DEFAULT_COST_MODEL.round_trip_cost_pct
    # Static existing model chunks contain original training features and bars.
    for i,chunk in enumerate(sorted((model_root/'chunks').iterdir())):
        done=read(chunk/'done.json');verify_hashes(chunk,done['files'])
        source_hashes[str(chunk/'done.json')]=digest(chunk/'done.json')
        raw=pd.read_parquet(chunk/'features.parquet',columns=['date','symbol',*features])
        raw=raw.replace([np.inf,-np.inf],np.nan)
        bars=pd.read_parquet(chunk/'bars.parquet')
        selected=candidates.loc[candidates.symbol.isin(done['symbols'])].merge(raw,
            on=['date','symbol'],how='left',validate='one_to_one')
        for symbol,group in selected.groupby('symbol'):
            b=bars.loc[bars.symbol.eq(symbol)].set_index('date').reindex(calendar)
            factor=b.adj_close.where(b.adj_close.notna(),b.close)/b.close
            b[['open','high','low','close']]=b[['open','high','low','close']].mul(factor,axis=0)
            f=raw.loc[raw.symbol.eq(symbol)].set_index('date')
            for row in group.itertuples(index=False):
                if not row.path_qualified or pd.isna(row.long_gross_return):
                    excluded['unknown_or_ambiguous']=excluded.get('unknown_or_ambiguous',0)+1
                    continue
                j=calendar.get_indexer([pd.Timestamp(row.date)])[0]
                path=b.iloc[j+1:j+22]
                if len(path)!=21 or path.volume.isna().any() or path.volume.le(0).any():continue
                entry=float(path.open.iloc[0])
                # Same entry gap gate as portfolio; filter based on J+1 only for
                # labels of actually fillable training orders, never test ranking.
                if not np.isfinite(entry) or not np.isfinite(b.close.iloc[j]) or abs(entry/b.close.iloc[j]-1)>.03:continue
                exits=[unit_path(path.open.to_numpy(),path.high.to_numpy(),path.low.to_numpy(),entry,tp=tp,sl=sl)
                       for tp,sl in PROFILES]
                if any(x is None for x in exits):continue
                base=exits[1]
                record={k:getattr(row,k) for k in features+list(SCORES.values())}
                record.update(date=row.date,symbol=symbol,selection_rank=int(row.selection_rank),
                    score_difference=getattr(row,SCORES['long'])-getattr(row,SCORES['short']),
                    label_available=row.oracle_available_date,
                    unit_net_return=base[1]/entry-1-cost,
                    label_win=float(base[1]/entry-1-cost>0))
                for k,exit_ in enumerate(exits):record[f'profile_target_{k}']=(exit_[1]/entry-1-cost)/PROFILES[k][1]
                parts.append(record)
                # States exist only AFTER surviving intraday protections.
                for k in range(min(base[0],20)):
                    day=path.index[k]
                    if day not in f.index:continue
                    closed=float(path.close.iloc[k]);history=path.iloc[:k+1]
                    if not np.isfinite(closed) or closed<=0:continue
                    state={x:float(f.at[day,x]) for x in features}
                    state.update({x:getattr(row,x) for x in SCORES.values()})
                    state['score_difference']=record['score_difference']
                    state.update(state_values(k,entry,closed,float(history.high.max()),float(history.low.min()),0.))
                    state.update(date=day,symbol=symbol,entry_date=path.index[0],trade_id=f'{symbol}/{row.date}',
                        label_available=row.oracle_available_date,
                        keep_advantage=(base[1]-float(path.open.iloc[k+1]))/closed,
                        weight=1./max(1,min(base[0],20)))
                    # Relative since entry omitted in training/runtime (no
                    # same-chunk SPY available); no synthetic zero macro signal.
                    state.pop('relative_since_entry')
                    states.append(state)
        atomic_json(root/'progress.json',dict(status='RUNNING',phase='OOF_training_dataset',
            completed_chunks=i+1,total_chunks=72,entry_rows=len(parts),state_rows=len(states)))
    entries,pd_states=pd.DataFrame(parts),pd.DataFrame(states)
    entries.to_parquet(root/'entry-training.parquet',index=False)
    pd_states.to_parquet(root/'exit-training.parquet',index=False)
    atomic_json(root/'training-source-manifest.json',dict(files=source_hashes,features=features,
        dataset_hashes={n:digest(root/n) for n in ('entry-training.parquet','exit-training.parquet')},
        excluded=excluded,labels_cost_basis='canonical flat unit approximation; portfolio costs only in replay',
        entry_rows=len(entries),daily_state_rows=len(pd_states),fold_weights_equal=False,
        labels_not_used_for_external_ranking=True))
    return entries,pd_states,features


def state_values(age,entry,close,mfe_price,mae_price,relative):
    return dict(age=float(age),pnl=close/entry-1,mfe=mfe_price/entry-1,mae=mae_price/entry-1,
                distance_stop=(close-entry*.9)/close,distance_tp=(entry*1.2-close)/close,
                relative_since_entry=relative)


def daily_tail(root,model_root,features):
    """Daily exit features continue past the last date permitting NEW entries.

    No future daily Oracle scores are needed: the daily policy uses entry scores.
    This is another SELECT-only snapshot; no filling absent daily observations.
    """
    scores=pd.read_parquet(root/'scores.parquet')
    candidates=freeze_candidates(scores,50,'NEW_BARRIER_LONG')
    symbols=sorted(candidates.symbol.unique())
    _,profile,_=model_contract(model_root)
    tail_root=root/'daily-tail';tail_root.mkdir(parents=True,exist_ok=True)
    if (tail_root/'ready.json').exists():
        verify_hashes(tail_root,read(tail_root/'ready.json')['files'])
        return pd.read_parquet(tail_root/'features.parquet')
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':raise ValueError('US database required')
    event.listen(engine,'begin',readonly_begin);event.listen(engine,'before_cursor_execute',readonly_statement)
    parts=[]
    try:
        for i,offset in enumerate(range(0,len(symbols),25)):
            chunk=symbols[offset:offset+25]
            def builder():
                frame=build_feature_matrix(engine,chunk,start_date='2016-01-01',end_date=AS_OF,
                    generator_options={**profile['generator_options'],'enable_cross_sectional_ranks':False})
                return frame.loc[frame.date.gt('2026-09-03'),['date','symbol',*features]]
            parts.append(checkpoint(tail_root,f'chunk-{i:03d}.parquet',builder))
            atomic_json(tail_root/'progress.json',dict(status='RUNNING',completed=i+1,total=(len(symbols)+24)//25))
    finally:engine.dispose()
    tail=pd.concat(parts,ignore_index=True)
    if tail.duplicated(['date','symbol']).any():raise ValueError('Duplicate daily tail feature keys')
    tail.to_parquet(tail_root/'features.parquet',index=False)
    atomic_json(tail_root/'ready.json',dict(files={'features.parquet':digest(tail_root/'features.parquet')},
        rows=len(tail),symbols=len(symbols),daily_score_source='entry scores; no post-decision inference'))
    atomic_json(tail_root/'progress.json',dict(status='COMPLETED',rows=len(tail)))
    return tail


class DailyExit:
    def __init__(self,model,features):
        self.model=model;self.features=features.set_index(['date','symbol'])
        self.columns=model.feature_name()

    def __call__(self,day,ledger,frames):
        rows=[]
        for symbol,pos in ledger.state.positions.items():
            key=(pd.Timestamp(day),symbol)
            if key not in self.features.index:
                raise ValueError(f'Missing close-known exit features {symbol}/{day.date()}')
            row=self.features.loc[key].to_dict()
            entry_key=(ledger.days[pos.entry_idx-1],symbol)
            if entry_key not in self.features.index:
                raise ValueError(f'Missing archived entry scores for learned exit {symbol}/{entry_key[0]}')
            entry_features=self.features.loc[entry_key]
            for c in SCORE_FEATURES:row[c]=entry_features[c]
            path=frames['close'].loc[pos.entry_date:day,symbol]
            row.update(state_values(ledger.days.get_loc(day)-pos.entry_idx,pos.entry_price,float(path.iloc[-1]),
                float(frames['high'].loc[pos.entry_date:day,symbol].max()),
                float(frames['low'].loc[pos.entry_date:day,symbol].min()),0.))
            prediction=float(self.model.predict(input_matrix(pd.DataFrame([row]),self.columns),num_threads=1)[0])
            if prediction<0:
                rows.append(dict(symbol=symbol,entry_date=pos.entry_date,decision_date=day,
                                 predicted_keep_advantage=prediction))
        return rows


class SizedSession(OraclePortfolioSession):
    def __init__(self,*args,profiles,**kwargs):
        self.profile_choices=profiles;self.sizing_audits=[]
        super().__init__(*args,**kwargs)

    def decide(self,day,**kwargs):
        entries=super().decide(day,**kwargs)
        output=[]
        equity=kwargs['snapshot'].account.equity
        for e in entries:
            key=(pd.Timestamp(day),e.symbol)
            tp,sl=self.profile_choices[key]
            budget=min(float(e.risk_budget_dollars or equity*self.resolved_config.risk_per_trade_pct),
                       float(equity*self.resolved_config.risk_per_trade_pct))
            # No increase beyond the native approved cash/sector/correlation cap.
            # 3% permitted adverse entry gap also fits in the stop-risk budget.
            q=min(float(e.approved_shares),budget/(float(e.entry_price)*sl*1.03))
            if not np.isfinite(q) or q<=0:continue
            output.append(replace(e,approved_shares=q,proposed_shares=min(e.proposed_shares,q),
                target_notional=q*e.entry_price,target_weight=q*e.entry_price/equity,
                risk_per_share=e.entry_price*sl*1.03,risk_budget_dollars=budget,
                initial_risk_dollars=q*e.entry_price*sl*1.03))
            self.sizing_audits.append(dict(date=str(day),symbol=e.symbol,tp=tp,sl=sl,native_quantity=e.approved_shares,
                quantity=q,stop_risk_budget=budget,maximum_gap_stop_risk=q*e.entry_price*sl*1.03))
        return output


class PersonalizedLedger(GridLedger):
    def __init__(self,*args,profiles,**kwargs):
        self.profile_choices=profiles;self.active_profiles={};self.profile_audits=[]
        super().__init__(*args,tp_pct=.2,sl_pct=.1,**kwargs)

    def execute_approved(self,entries,**kwargs):
        for e in entries:
            choice=self.profile_choices[(pd.Timestamp(e.score_snapshot_date or e.price_asof_date),e.symbol)]
            self.active_profiles[e.symbol]=choice
            self.profile_audits.append(dict(symbol=e.symbol,entry_date=str(self.current_day.date()),
                decision_date=str(e.score_snapshot_date or e.price_asof_date),tp=choice[0],sl=choice[1],
                approved_quantity=e.approved_shares,risk_budget=e.risk_budget_dollars,
                entry_price_at_decision=e.entry_price))
        result=super().execute_approved(entries,**kwargs)
        opened=set(result[1])
        for audit in self.profile_audits:
            if audit['entry_date']==str(self.current_day.date()) and audit['symbol'] in opened:
                p=self.state.positions[audit['symbol']]
                risk=p.quantity*p.entry_price*audit['sl']
                if risk>float(audit['risk_budget'])+1e-6:
                    raise ValueError('Actual fill stop risk exceeds personalized risk budget')
                audit.update(booked_quantity=p.quantity,actual_fill=p.entry_price,booked_stop_risk=risk)
        return result

    def _build_entry_protections(self,phase3,*,execution_config):
        native=OraclePortfolioLedger._build_entry_protections(self,phase3,execution_config=execution_config)
        result=parametric_protections(native,tp_pct=.2,sl_pct=.1)
        signals,frame,orders=result.signals_df.copy(),result.protection_frame.copy(),result.order_lifecycle_frame.copy()
        if signals.empty:return result
        fills=signals.set_index('symbol').fill_price.to_dict()
        stop={s:p*(1-self.active_profiles[s][1]) for s,p in fills.items()}
        tp={s:p*(1+self.active_profiles[s][0]) for s,p in fills.items()}
        for f in (signals,frame):
            if len(f):
                f['replay_initial_stop_price']=f.symbol.map(stop)
                f['replay_take_profit_price']=f.symbol.map(tp)
        if len(orders):
            mask=orders.intent_role.eq(IntentRole.INITIAL_STOP)
            orders.loc[mask,'stop_price']=orders.loc[mask,'symbol'].map(stop)
            mask=orders.intent_role.eq(IntentRole.TAKE_PROFIT)
            orders.loc[mask,'limit_price']=orders.loc[mask,'symbol'].map(tp)
        return replace(result,signals_df=signals,protection_frame=frame,order_lifecycle_frame=orders)

    def corporate_action_report(self):
        report=super().corporate_action_report()
        report['profile_choices']=self.profile_audits
        # Reconciliation against the actually booked fill anchors, not J close.
        choices={(r['symbol'],pd.Timestamp(r['entry_date'])):(r['tp'],r['sl']) for r in self.profile_audits}
        for t in self.state.closed_trades:
            key=(t['symbol'],pd.Timestamp(t['entry_date']))
            if key not in choices:
                raise ValueError('Personalized trade identity changed without profile qualification')
            tp,sl=choices[key]
            if not np.isclose(t['replay_initial_stop_price'],t['entry_price']*(1-sl),rtol=1e-8,atol=1e-7):
                raise ValueError('Personalized SL anchor differs from booked fill')
            if not np.isclose(t['replay_take_profit_price'],t['entry_price']*(1+tp),rtol=1e-8,atol=1e-7):
                raise ValueError('Personalized TP anchor differs from booked fill')
            duration=self.days.get_loc(pd.Timestamp(t['exit_date']))-self.days.get_loc(pd.Timestamp(t['entry_date']))
            if not 0<=duration<=20 or t['exit_reason']=='expiry_open' and duration!=20:
                raise ValueError('Personalized expiry chronology differs')
        report['personalized_protection_audit']=dict(trades=len(self.state.closed_trades),verified=True)
        return report


def experiments(root,model_root):
    root,model_root=Path(root),Path(model_root)
    baseline=read(root/'baseline-report.json')
    if baseline['status']!='COMPLETED_EXPLORATORY':raise ValueError('Baseline must complete before experiments')
    manifest_path=root/'experiments-protocol.json'
    manifest=dict(fit_start='2018-07-05',fit_end='2021-12-31',validation_year=2022,
        entry_filter='binary win probability >= .5; no replacement below TOPN',
        daily_exit='negative predicted KEEP minus next-open EXIT, stop10 and TP20 remain hard',
        profiles=PROFILES,sizing='cap native quantity by equity risk budget / (SL * J close * 1.03)',
        profile_objective='highest predicted canonical-unit net return / SL; not highest realised return',
        primary_count=10,counts=COUNTS,years=YEARS,sql_writes=False,production_changes=False,
        source_hashes=code_hashes(),original_model_unchanged=True)
    if manifest_path.exists():verify_hashes(Path('.'),read(manifest_path)['source_hashes'])
    else:atomic_json(manifest_path,manifest)
    fit_root=root/'fit-data'
    if (fit_root/'entry-training.parquet').exists() and (fit_root/'training-source-manifest.json').exists():
        saved=read(fit_root/'training-source-manifest.json');verify_hashes(Path('.'),saved['files'])
        verify_hashes(fit_root,saved['dataset_hashes'])
        entries,states=pd.read_parquet(fit_root/'entry-training.parquet'),pd.read_parquet(fit_root/'exit-training.parquet')
        features=saved['features']
    else:entries,states,features=training_data(fit_root,model_root)
    columns=features+SCORE_FEATURES
    external=pd.read_parquet(root/'features.parquet',columns=['date','symbol',*features]).merge(
        pd.read_parquet(root/'scores.parquet'),on=['date','symbol'],validate='one_to_one')
    external['score_difference']=external[SCORES['long']]-external[SCORES['short']]
    reports=[]
    for number,name in enumerate(('ENTRY_FILTER','DAILY_EXIT','PERSONAL_TP_SL'),1):
        atomic_json(root/'progress.json',dict(status='RUNNING',phase=name,experiment_number=number))
        models_dir=root/name/'models';models_dir.mkdir(parents=True,exist_ok=True)
        def head(frame,cols,target,binary):
            path=models_dir/f'{target}.txt'
            if path.exists() and path.with_suffix('.json').exists():
                if digest(path)!=read(path.with_suffix('.json'))['model_sha256']:raise ValueError('Changed challenger')
                return lgb.Booster(model_file=str(path))
            return train_head(frame,cols,target,binary=binary,output=path)
        overrides={}
        if name=='ENTRY_FILTER':
            model=head(entries,columns,'label_win',True)
            scored=external.copy()
            scored['entry_filter_probability']=model.predict(input_matrix(scored,columns),num_threads=3)
            scored['entry_allowed']=scored.entry_filter_probability.ge(.5)
            overrides['scores_override']=scored
        elif name=='DAILY_EXIT':
            state_cols=columns+[c for c in STATE_FEATURES if c!='relative_since_entry']
            model=head(states,state_cols,'keep_advantage',False)
            observed=pd.concat([external,daily_tail(root,model_root,features)],ignore_index=True)
            overrides['daily_exit_policy']=DailyExit(model,observed)
        else:
            predictions=[]
            for k in range(len(PROFILES)):
                model=head(entries,columns,f'profile_target_{k}',False)
                predictions.append(model.predict(input_matrix(external,columns),num_threads=3))
            choice=np.stack(predictions,axis=1).argmax(axis=1)
            profiles={(pd.Timestamp(d),s):PROFILES[int(k)] for d,s,k in zip(external.date,external.symbol,choice)}
            overrides.update(session_factory=partial(SizedSession,profiles=profiles),
                ledger_factory=partial(PersonalizedLedger,profiles=profiles,cash_policy='STRICT'))
            # Same-sizing fixed-profile control is needed to separate adaptive
            # barriers from the effect of reducing native ATR-sized quantities.
            fixed={key:(.2,.1) for key in profiles}
            control=[]
            for year in YEARS:
                for count in COUNTS:
                    control.append(run_case(root,year,count,experiment='FIXED_SL10_SIZING_CONTROL',
                        session_factory=partial(SizedSession,profiles=fixed)))
            atomic_json(root/'FIXED_SL10_SIZING_CONTROL'/'report.json',dict(portfolios=control))
            if any(r['status']=='FAILED' for r in control):raise RuntimeError('Same-sizing control failed')
        external.to_parquet(models_dir/'external-decision-features.parquet',index=False)
        if name=='ENTRY_FILTER':scored.to_parquet(models_dir/'filter-decisions.parquet',index=False)
        elif name=='PERSONAL_TP_SL':
            pd.DataFrame([dict(date=d,symbol=s,tp=p[0],sl=p[1]) for (d,s),p in profiles.items()]).to_parquet(
                models_dir/'profile-decisions.parquet',index=False)
        stage=[]
        for year in YEARS:
            annual=[]
            for count in COUNTS:
                r=run_case(root,year,count,experiment=name,**overrides)
                stage.append(r);reports.append(r);annual.append(r)
                atomic_json(root/name/f'{year}.json',dict(portfolios=annual))
                LOG.info('%s %s TOP%s: %s',name,year,count,r['status'])
            if any(r['status']=='FAILED' for r in annual):break
        atomic_json(root/name/'report.json',dict(status='FAILED' if any(r['status']=='FAILED' for r in stage)
            else 'COMPLETED_EXPLORATORY',portfolios=stage,original_model_unchanged=True))
        if any(r['status']=='FAILED' for r in stage):raise RuntimeError(f'{name} replay failed; subsequent experiments not started')
        verify_hashes(Path('.'),read(manifest_path)['source_hashes'])
    rows=[]
    base={(r['year'],r['count']):r for r in baseline['portfolios']}
    for r in reports:
        reference=base[(r['year'],r['count'])]['annual_metrics'];m=r['annual_metrics']
        rows.append(dict(experiment=r['experiment'],year=r['year'],count=r['count'],**m,
            delta_return_points=m['return_pct']-reference['return_pct'],
            delta_dd_points=m['max_drawdown_pct']-reference['max_drawdown_pct'],
            delta_winrate_points=m['winning_pct']-reference['winning_pct'] if m['winning_pct'] is not None else None))
    atomic_json(root/'experiments-report.json',dict(status='COMPLETED_EXPLORATORY',comparisons=rows,
        holdout_is_virgin=False,no_automatic_promotion=True))


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_tp20_sl10_campaign import MODEL
    parser=argparse.ArgumentParser(description='Prepare historical OOF labels only; no fitting or external evaluation')
    parser.add_argument('--fit-data',type=Path,required=True)
    parser.add_argument('--model',type=Path,default=MODEL)
    args=parser.parse_args()
    try:
        training_data(args.fit_data,args.model)
        atomic_json(args.fit_data/'progress.json',dict(status='COMPLETED',phase='OOF_training_dataset'))
    except Exception as exc:
        atomic_json(args.fit_data/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
