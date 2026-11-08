"""USD<=3 frozen TOP20 text embedding pilot; local artifacts only.

Historical, NOT PIT certified. Prepare never loads future price outcomes. Embed
only calls /v1/embeddings, no retries. Evaluate fits local small classifiers;
no SQL/broker calls, no Oracle retraining or changes to production.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_news_embedding_cache import (
    CAP, DIMENSIONS, MODEL, RATE, EmbeddingCache, exclusive, identity, sha,
)
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

SOURCE = Path('artifacts/research/us_news_gpt_top20_history/20261015-v1')
PRICES = Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1/prices.parquet')
REGISTRY = Path('config/data_quality/security_discontinuities.json')
HOME = Path('artifacts/research/us_news_embeddings')
ROOT = HOME/'20261102-v1'
NUMERIC = ['score', 'oracle_rank', 'news_count', 'return_1', 'momentum_5',
           'momentum_20', 'momentum_60', 'volatility_20', 'volume_ratio_20']
LOG = logging.getLogger(__name__)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify(root):
    protocol = read(root/'protocol.json')
    for name, checksum in protocol['sources'].items():
        if digest(name) != checksum:
            raise ValueError('Frozen input/code changed: '+name)
    for name, checksum in protocol['files'].items():
        if digest(root/name) != checksum:
            raise ValueError('Prepared material changed: '+name)
    return protocol


def prepare(root):
    if (root/'protocol.json').exists():
        return verify(root)
    root.mkdir(parents=True, exist_ok=True)
    os.environ['TIKTOKEN_CACHE_DIR'] = str((HOME/'tokenizer').resolve())
    import tiktoken
    encoder = tiktoken.get_encoding('cl100k_base')
    upstream = read(SOURCE/'protocol.json')
    sources = {str(SOURCE/n): digest(SOURCE/n) for n in ['protocol.json', 'report.json']}
    articles, panel, metadata = {}, [], []
    strict = truncated = 0
    for folder in sorted((SOURCE/'months').iterdir()):
        marker = read(folder/'prepared.json')
        for name, checksum in marker['files'].items():
            if digest(folder/name) != checksum:
                raise ValueError('Changed archived preparation: '+str(folder/name))
        for name in ['prepared.json', 'packets.json', 'candidates.parquet', 'news-metadata.parquet']:
            sources[str(folder/name)] = digest(folder/name)
        candidates = pd.read_parquet(folder/'candidates.parquet')
        annual = upstream['annual_models'][folder.name[:4]]
        if (candidates.duplicated(['date', 'symbol']).any()
                or not candidates.target_horizon.eq(20).all()
                or not candidates.target_name.eq('oracle_path_extreme20').all()
                or not candidates.model_sha256.eq(annual['model_sha256']).all()
                or not candidates.feature_profile_sha256.eq(annual['profile_sha256']).all()
                or not (pd.to_datetime(candidates.model_available_date) < pd.to_datetime(candidates.date)).all()):
            raise ValueError('Invalid annual causal Oracle lineage')
        scores = {(str(pd.Timestamp(v.date).date()), v.symbol): float(v.score)
                  for v in candidates.itertuples()}
        strict += marker['strict_historical_pit_mappings']
        for packet in read(folder/'packets.json'):
            cutoff = pd.Timestamp(packet['cutoff_utc'])
            keys, body_trunc = [], 0
            for article in packet['articles']:
                if pd.Timestamp(article['publication_utc']) >= cutoff:
                    raise ValueError('Article published at/after decision cutoff')
                text = ('Title: '+article['headline']+'\nSummary: '+article['summary']
                        +'\nArticle: '+article['body'])
                tokens = encoder.encode(text, disallowed_special=())
                if not tokens or len(tokens) > 8191:
                    raise ValueError('Input outside embedding contract')
                key = identity(text)
                articles.setdefault(key, dict(key=key, text=text, tokens=len(tokens)))
                keys.append(key)
                body_trunc += bool(article['body_truncated'])
                metadata.append(dict(date=packet['decision_date'], symbol=packet['symbol'],
                    article_id=article['article_id'], key=key,
                    body_truncated=article['body_truncated'], publication_utc=article['publication_utc']))
            truncated += body_trunc
            panel.append(dict(date=packet['decision_date'], symbol=packet['symbol'],
                oracle_rank=packet['oracle_rank'], score=scores[(packet['decision_date'], packet['symbol'])],
                news_count=len(set(keys)), keys=sorted(set(keys)), truncated_articles=body_trunc,
                batch_id=packet['batch_id']))
    frame = pd.DataFrame(panel)
    if frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate candidate')
    if not frame.groupby('date').size().eq(20).all():
        raise ValueError('Original TOP20 incomplete')
    rows = sorted(articles.values(), key=lambda x: x['key'])
    tokens = sum(a['tokens'] for a in rows)
    upper_tokens = (tokens*125+99)//100 + len(rows)*32
    if Decimal(upper_tokens)*RATE > CAP:
        raise ValueError('Entire fixed corpus exceeds approved USD3; no API called')
    frame.to_parquet(root/'population.parquet', index=False)
    pd.DataFrame(rows).to_parquet(root/'articles.parquet', index=False)
    pd.DataFrame(metadata).to_parquet(root/'article-uses.parquet', index=False)
    for name in [__file__, 'scripts/research/us_news_embedding_cache.py',
                 'tests/test_us_news_embeddings_pilot.py', str(PRICES), str(REGISTRY)]:
        sources[name] = digest(name)
    years = {str(y): dict(candidate_days=len(p), with_news=int(p.news_count.gt(0).sum()),
                sessions=int(p.loc[p.news_count.gt(0), 'date'].nunique()),
                symbols=int(p.loc[p.news_count.gt(0), 'symbol'].nunique()))
             for y,p in frame.groupby(frame.date.str[:4])}
    protocol = dict(experiment='TOP20_NEWS_EMBEDDING_PILOT', created_at_utc=datetime.now(timezone.utc).isoformat(),
        model=MODEL, dimensions=DIMENSIONS, cap_usd=str(CAP), rate_usd_per_million='0.13',
        planned_tokens=tokens, expected_usd=str(Decimal(tokens)*RATE),
        conservative_total_reserved_usd=str(Decimal(upper_tokens)*RATE),
        articles=len(rows), article_uses=len(metadata), candidate_days=len(frame), years=years,
        strict_pit_qualified_article_mappings=strict, historical_pit_certified=False,
        original_excerpt_truncated_associations=truncated, new_truncation=False,
        text='Frozen 500char headline/700char summary/2400char body excerpts; no new full-article claim',
        top=20, annual_models={y:{k:v for k,v in m.items() if k!='universe'}
                             for y,m in upstream['annual_models'].items()},
        primary_horizon=20, secondary_horizons=[5,10], primary_target='max_up_gt_abs_max_down_from_J1_open',
        secondary_target='first_touch_+10_-10_with_ambiguous_same_day_explicit',
        train_year=2024, validation_year=2025, test_year=2026, purge='full horizon label_end before split boundary',
        cross_split_article_policy='drop later rows sharing any exact normalized text key with earlier split',
        estimator='StandardScaler(train only) + L2 logistic; Cs .001,.01,.1; validation Brier minimum',
        arms=['NUMERIC', 'EMBEDDING', 'NUMERIC_EMBEDDING'], numeric_features=NUMERIC,
        primary_selection='probability>=0.5 fixed; no trading gate promotion',
        overlapping_events='all + deterministic nonoverlap horizon+1, then date/week cluster diagnostics',
        outcomes_accessed_during_prepare=False, tools=False, chat_calls=False, automatic_paid_retry=False,
        sql_writes=False, broker_orders=False, independent_holdout=False,
        sources=sources, files={n:digest(root/n) for n in ['population.parquet','articles.parquet','article-uses.parquet']})
    atomic_json(root/'protocol.json', protocol)
    atomic_json(root/'progress.json', dict(status='PREPARED', api_calls=0, **{k:protocol[k]
        for k in ['articles','planned_tokens','expected_usd','cap_usd','years']}))
    return protocol


def embed(root):
    protocol = verify(root)
    campaign = root.name
    cache = EmbeddingCache(HOME/'cache.sqlite')
    session = None
    try:
        cache.register(campaign, sha(protocol))
        rows = pd.read_parquet(root/'articles.parquet').to_dict('records')
        pending = [a for a in rows if cache.get(a['key']) is None]
        os.environ['TIKTOKEN_CACHE_DIR'] = str((HOME/'tokenizer').resolve())
        import tiktoken
        encoder = tiktoken.get_encoding('cl100k_base')
        from common.verified_http import verified_session
        session = verified_session()
        key = os.environ.get('OPENAI_API_KEY')
        if pending and not key:
            raise ValueError('OPENAI_API_KEY missing; no call made')
        for i in range(0, len(pending), 128):
            batch = pending[i:i+128]
            inputs = [encoder.encode(a['text'], disallowed_special=()) for a in batch]
            tokens = sum(map(len, inputs))
            if tokens > 300000 or tokens != sum(a['tokens'] for a in batch):
                raise ValueError('Tokenizer/request drift')
            request = dict(model=MODEL, dimensions=DIMENSIONS, input=inputs, encoding_format='float')
            call, _ = cache.reserve(campaign, request, tokens)
            requests = HOME/'requests'
            requests.mkdir(exist_ok=True)
            with (requests/f'{call}.json').open('x', encoding='utf-8') as stream:
                json.dump(dict(request=request, article_keys=[a['key'] for a in batch]), stream)
            atomic_json(root/'progress.json', dict(status='EMBEDDING', completed_articles=len(rows)-len(pending)+i,
                total_articles=len(rows), **cache.summary(campaign)))
            # No HTTP retry, redirects, implicit tools, or key material in logs/artifacts.
            response = session.post('https://api.openai.com/v1/embeddings', json=request,
                headers={'Authorization':'Bearer '+key}, timeout=(10,60), allow_redirects=False)
            if response.status_code != 200:
                raise RuntimeError('OpenAI embedding HTTP '+str(response.status_code)+'; no automatic retry')
            cache.complete(call, batch, response.json(), tokens)
            LOG.info('Embeddings %d/%d ; USD %s', min(i+len(batch),len(pending)),len(pending),
                     cache.summary(campaign)['committed_usd'])
        summary = dict(status='EMBEDDINGS_COMPLETE', total_articles=len(rows), **cache.summary(campaign))
        atomic_json(root/'embedding-completion.json', summary)
        atomic_json(root/'progress.json', summary)
        return summary
    except Exception as exc:
        atomic_json(root/'progress.json', dict(status='STOPPED', error_type=type(exc).__name__,
            message=str(exc)[:250], automatic_retry=False, **cache.summary(campaign)))
        raise
    finally:
        if session is not None:
            session.close()
        cache.close()


def path_outcome(window, horizon):
    """Outcome only, entry J+1 open. Missing/identity/dual touch never relabeled."""
    if len(window) != horizon or window[['open','high','low','close','volume']].isna().any().any():
        return dict(qualified=False, reason='MISSING_PRICE_SESSIONS')
    vals = window[['open','high','low','close','volume']].to_numpy(float)
    o,h,l,c,v = vals.T
    if (not np.isfinite(vals).all() or (vals <= 0).any() or (h < np.maximum(o,c)).any()
            or (l > np.minimum(o,c)).any() or (h < l).any()):
        return dict(qualified=False, reason='INVALID_OHLCV')
    ids = window.instrument_id.astype('string')
    if (not window.is_filled.eq(0).all() or ids.isna().any() or ids.str.strip().eq('').any()
            or ids.nunique() != 1 or not window.data_adjustment.eq('split').all()):
        return dict(qualified=False, reason='FILLED_OR_IDENTITY_OR_ADJUSTMENT')
    anchor = o[0]
    up, down = h/anchor-1, l/anchor-1
    up_i, down_i = int(np.argmax(up)), int(np.argmin(down))
    first, exit_price, exit_i = 'NONE', c[-1], horizon-1
    for i in range(horizon):
        if i > 0 and o[i] >= anchor*1.10:
            first,exit_price,exit_i='UP',anchor*1.10,i; break
        if i > 0 and o[i] <= anchor*.90:
            first,exit_price,exit_i='DOWN',o[i],i; break
        a,b = h[i] >= anchor*1.10,l[i] <= anchor*.90
        if a or b:
            first = 'AMBIGUOUS' if a and b else 'UP' if a else 'DOWN'
            exit_price,exit_i = (anchor*.90 if b else anchor*1.10),i
            break
    # 8 bps/leg, plus 5 bps/leg slippage, fixed ex ante; unit proxy, no portfolio.
    cost=.0013
    return dict(qualified=True, reason='', direction=int(up[up_i] > abs(down[down_i])),
        max_up_pct=float(100*up[up_i]), max_down_pct=float(100*down[down_i]),
        peak_order='UP_FIRST' if up_i<down_i else 'DOWN_FIRST' if down_i<up_i else 'SAME_DAY_UNKNOWN',
        up_date=str(window.index[up_i].date()), down_date=str(window.index[down_i].date()),
        first_touch=first, unit_net_pct=float(100*(exit_price/anchor*(1-cost)-(1+cost))),
        unit_holding_sessions=exit_i+1, label_end=str(window.index[-1].date()),
        terminal_pct=float(100*(c[-1]/anchor-1)))


def prepare_evaluation(root):
    """First point where outcomes can be loaded; requires sealed paid completion."""
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import load_security_discontinuities, path_crosses_known_discontinuity
    if not (root/'embedding-completion.json').exists():
        raise ValueError('Embeddings must be complete before opening price outcomes')
    panel = pd.read_parquet(root/'population.parquet')
    panel['date'] = pd.to_datetime(panel.date)
    bars = pd.read_parquet(PRICES)
    bars['date'] = pd.to_datetime(bars.date)
    if bars.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate frozen price providers; no arbitrary deduplication')
    days = nyse_sessions(str(bars.date.min().date()), str(bars.date.max().date()))
    registry = load_security_discontinuities(REGISTRY)
    group = {}
    for symbol,p in bars.groupby('symbol'):
        p = p.set_index('date').sort_index().reindex(days)
        close = p.close.astype(float)
        returns = close.pct_change(fill_method=None)
        p['return_1'] = returns
        for n in [5,20,60]:
            p[f'momentum_{n}'] = close/close.shift(n)-1
        p['volatility_20'] = returns.rolling(20).std()
        p['volume_ratio_20'] = p.volume/p.volume.rolling(20).mean()
        values=p[['open','high','low','close','volume']].to_numpy(float)
        good=(np.isfinite(values).all(axis=1)&(values>0).all(axis=1)&p.is_filled.eq(0).to_numpy()
              &p.data_adjustment.eq('split').to_numpy()
              &p.high.ge(p[['open','close']].max(axis=1)).to_numpy()
              &p.low.le(p[['open','close']].min(axis=1)).to_numpy())
        ids=p.instrument_id.astype('string')
        codes=pd.Series(pd.factorize(ids)[0],index=days).where(ids.notna()&ids.str.strip().ne(''))
        history_ok=(pd.Series(good,index=days).rolling(61).sum().eq(61)
                    &codes.rolling(61).max().eq(codes.rolling(61).min()))
        for event in registry.get(symbol,()):
            history_ok &= ~((days-pd.Timedelta(days=110)<=event.last_predecessor_date)
                           &(days>=event.first_successor_date))
        p.loc[~history_ok,NUMERIC[3:]]=np.nan
        group[symbol] = p
    features, outcomes = [], []
    for row in panel.itertuples():
        p = group.get(row.symbol)
        base = dict(date=row.date, symbol=row.symbol)
        if p is None or row.date not in days:
            continue
        j = days.get_loc(row.date)
        feature = {name:p.loc[row.date,name] for name in NUMERIC[3:]}
        feature.update(base)
        features.append(feature)
        for horizon in [5,10,20]:
            dates = days[j+1:j+1+horizon]
            if len(dates) != horizon:
                result=dict(qualified=False, reason='IMMATURE_WINDOW')
            elif path_crosses_known_discontinuity(row.symbol, dates[0], dates[-1],registry):
                result=dict(qualified=False, reason='KNOWN_IDENTITY_BREAK')
            else:
                result=path_outcome(p.loc[dates],horizon)
            outcomes.append(dict(**base,horizon=horizon,**result))
    panel = panel.merge(pd.DataFrame(features),on=['date','symbol'],how='left',validate='one_to_one')
    outcomes = pd.DataFrame(outcomes)
    outcomes.to_parquet(root/'outcomes.parquet', index=False)
    panel.to_parquet(root/'features.parquet', index=False)
    return panel, outcomes, days


def split_rows(panel):
    """No exact text can appear in an earlier and later retained split."""
    assigned = np.full(len(panel), '', dtype=object)
    seen = set()
    for year,name in [(2024,'TRAIN'),(2025,'VALIDATION'),(2026,'TEST')]:
        within = panel.date.dt.year.eq(year)
        ids = set()
        for i,row in panel[within].iterrows():
            if row.news_count and not seen.intersection(row['keys']):
                assigned[i] = name
            ids.update(row['keys'])
        seen.update(ids)
    return assigned


def metrics(frame, column):
    from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
    y=frame.direction.to_numpy(int); p=frame[column].to_numpy(float)
    long=p>=.5
    return dict(n=len(y), dates=int(frame.date.nunique()), symbols=int(frame.symbol.nunique()),
        auc=float(roc_auc_score(y,p)) if len(set(y))==2 else None,
        brier=float(brier_score_loss(y,p)), log_loss=float(log_loss(y,p,labels=[0,1])),
        accuracy=float(np.mean((p>=.5)==y)), long_selected=int(long.sum()),
        long_precision=float(y[long].mean()) if long.any() else None,
        long_coverage=float(long.mean()), all_long_precision=float(y.mean()),
        selected_unit_mean_net_pct=float(frame.loc[long,'unit_net_pct'].mean()) if long.any() else None,
        all_unit_mean_net_pct=float(frame.unit_net_pct.mean()),
        first_touch_selected=dict(Counter(frame.loc[long,'first_touch'])))


def nonoverlap(frame, days, horizon):
    keep=[]
    for symbol,p in frame.sort_values('date').groupby('symbol'):
        after=-1
        for i,row in p.iterrows():
            j=days.get_loc(row.date)
            if j>after:
                keep.append(i); after=j+horizon
    return frame.loc[keep].copy()


def evaluate(root):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import brier_score_loss
    import joblib
    protocol=verify(root)
    if (root/'report.json').exists():
        raise ValueError('Evaluation already published; do not overwrite outcomes')
    panel, outcomes, days = prepare_evaluation(root)
    panel['split'] = split_rows(panel)
    cache=EmbeddingCache(HOME/'cache.sqlite')
    try:
        vectors={key:cache.get(key) for keys in panel['keys'] for key in keys}
        if any(v is None for v in vectors.values()):
            raise ValueError('Incomplete vector cache')
        embedding=np.zeros((len(panel),DIMENSIONS),dtype=float)
        for i,row in panel.iterrows():
            if len(row['keys']):
                v=np.stack([vectors[k] for k in row['keys']]).mean(axis=0)
                embedding[i]=v/max(np.linalg.norm(v),1e-12)
    finally:
        cache.close()
    all_predictions=[]; summaries=[]; exclusions=[]
    root.joinpath('models').mkdir(exist_ok=True)
    for horizon in [20,5,10]:
        labels=outcomes[outcomes.horizon.eq(horizon)]
        frame=panel.reset_index(names='row_id').merge(labels,on=['date','symbol'],how='left',validate='one_to_one')
        frame['features_valid']=np.isfinite(frame[NUMERIC]).all(axis=1)
        usable=frame.qualified.eq(True)&frame.features_valid&frame.split.ne('')
        frame=frame[usable].copy()
        frame['label_end']=pd.to_datetime(frame.label_end)
        frame=frame[~((frame.split.eq('TRAIN')&frame.label_end.ge('2025-01-01'))
                    |(frame.split.eq('VALIDATION')&frame.label_end.ge('2026-01-01')))].copy()
        train=frame[frame.split.eq('TRAIN')];val=frame[frame.split.eq('VALIDATION')];test=frame[frame.split.eq('TEST')]
        counts={name:dict(rows=len(part), dates=int(part.date.nunique()),symbols=int(part.symbol.nunique()))
                for name,part in [('TRAIN',train),('VALIDATION',val),('TEST',test)]}
        exclusions.append(dict(horizon=horizon,split_counts=counts,
            raw_outcome_reasons=dict(Counter(labels.loc[~labels.qualified.eq(True),'reason'])),
            missing_features=int((~panel[NUMERIC].apply(np.isfinite).all(axis=1)).sum()),
            no_text_or_cross_split_duplicate=int(panel.split.eq('').sum())))
        if any(len(p)<100 or p.date.nunique()<30 or p.direction.nunique()!=2 for p in [train,val,test]):
            raise ValueError('Insufficient class/date support; no interpretive model result')
        ytrain=train.direction.to_numpy(int)
        for arm in ['NUMERIC','EMBEDDING','NUMERIC_EMBEDDING']:
            numeric=panel[NUMERIC].to_numpy(float)
            x=numeric if arm=='NUMERIC' else embedding if arm=='EMBEDDING' else np.column_stack([numeric,embedding])
            scaler=StandardScaler().fit(x[train.row_id])
            trials=[]
            # Equal date weights prevent a news-heavy session dominating fitting.
            weights=train.date.map(1/train.groupby('date').size()).to_numpy(float)
            weights=weights/weights.mean()
            for C in [.001,.01,.1]:
                model=LogisticRegression(C=C,max_iter=1500,solver='lbfgs',random_state=0)
                model.fit(scaler.transform(x[train.row_id]),ytrain,sample_weight=weights)
                loss=brier_score_loss(val.direction,model.predict_proba(scaler.transform(x[val.row_id]))[:,1])
                trials.append((float(loss),C))
            loss,C=min(trials)
            # Freeze selected regularization before accessing TEST labels for metrics.
            choice=dict(horizon=horizon,arm=arm,C=C,validation_brier=loss,grid=trials,
                        train_end=str(train.date.max().date()),validation_end=str(val.date.max().date()))
            atomic_json(root/'models'/f'H{horizon}-{arm}-selection.json',choice)
            fit=frame[frame.split.isin(['TRAIN','VALIDATION'])]
            final_scaler=StandardScaler().fit(x[fit.row_id])
            weights=fit.date.map(1/fit.groupby('date').size()).to_numpy(float); weights/=weights.mean()
            final_model=LogisticRegression(C=C,max_iter=1500,solver='lbfgs',random_state=0)
            final_model.fit(final_scaler.transform(x[fit.row_id]),fit.direction.astype(int),sample_weight=weights)
            joblib.dump(dict(scaler=final_scaler,model=final_model,choice=choice),root/'models'/f'H{horizon}-{arm}.joblib')
            test.loc[:,'probability']=final_model.predict_proba(final_scaler.transform(x[test.row_id]))[:,1]
            pred=test[['date','symbol','oracle_rank','direction','probability','max_up_pct','max_down_pct',
                       'peak_order','first_touch','unit_net_pct','label_end','unit_holding_sessions']].copy()
            pred['arm']=arm; pred['horizon']=horizon
            all_predictions.append(pred)
            for scope in ['ALL','NONOVERLAP']:
                part=pred if scope=='ALL' else nonoverlap(pred,days,horizon)
                summaries.append(dict(horizon=horizon,arm=arm,scope=scope,C=C,**metrics(part,'probability')))
    predictions=pd.concat(all_predictions,ignore_index=True)
    predictions.to_parquet(root/'predictions.parquet',index=False)
    pd.DataFrame(summaries).to_csv(root/'summary.csv',index=False)
    comparisons=compare_arms(predictions)
    atomic_json(root/'comparisons.json',comparisons)
    atomic_json(root/'coverage.json',exclusions)
    result=dict(status='COMPLETED_EXPLORATORY_NOT_PIT',protocol_sha256=sha(protocol),
        embedding=read(root/'embedding-completion.json'),results=summaries,
        comparisons=comparisons,
        primary_horizon=20,primary_comparison='NUMERIC_EMBEDDING versus NUMERIC, 2026',
        unit_returns_not_portfolio=True,unit_cost_per_leg_bps=13,
        historical_pit_certified=False,independent_holdout=False,production_promotion=False,
        files={n:digest(root/n) for n in ['predictions.parquet','summary.csv','coverage.json','outcomes.parquet','features.parquet','comparisons.json']})
    atomic_json(root/'report.json',result)
    atomic_json(root/'progress.json',{**result['embedding'],'status':result['status']})
    return result


def compare_arms(predictions):
    """Paired bootstrap by calendar week, never by individual repeated trades."""
    from sklearn.metrics import roc_auc_score
    rng=np.random.default_rng(20261102)
    results=[]
    for horizon,p in predictions.groupby('horizon'):
        base=p[p.arm.eq('NUMERIC')].set_index(['date','symbol'])
        enriched=p[p.arm.eq('NUMERIC_EMBEDDING')].set_index(['date','symbol'])
        if not base.index.equals(enriched.index):
            raise ValueError('Arms compared on different events')
        y=base.direction.to_numpy(int)
        a,b=base.probability.to_numpy(),enriched.probability.to_numpy()
        weeks=base.index.get_level_values('date').to_period('W').astype(str)
        clusters=[np.flatnonzero(weeks==w) for w in sorted(set(weeks))]
        deltas=[]
        for _ in range(400):
            ix=np.concatenate([clusters[i] for i in rng.integers(0,len(clusters),size=len(clusters))])
            if len(set(y[ix]))==2:
                deltas.append(roc_auc_score(y[ix],b[ix])-roc_auc_score(y[ix],a[ix]))
        monthly=[]
        months=base.index.get_level_values('date').to_period('M').astype(str)
        for month in sorted(set(months)):
            ix=np.flatnonzero(months==month)
            monthly.append(dict(month=month,n=len(ix),delta_auc=float(roc_auc_score(y[ix],b[ix])
                -roc_auc_score(y[ix],a[ix])) if len(set(y[ix]))==2 else None))
        results.append(dict(horizon=int(horizon),n=len(y),weeks=len(clusters),
            delta_auc=float(roc_auc_score(y,b)-roc_auc_score(y,a)),
            delta_auc_week_block_ci95=list(map(float,np.quantile(deltas,[.025,.975]))),
            bootstrap_repetitions=len(deltas),monthly=monthly))
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','embed','evaluate'],required=True)
    parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive(HOME/'pilot.lock'):
        result={'prepare':prepare,'embed':embed,'evaluate':evaluate}[args.phase](args.output)
        print(json.dumps({k:v for k,v in result.items() if k not in ['sources','files','results','annual_models']},default=str))


if __name__=='__main__':
    main()
