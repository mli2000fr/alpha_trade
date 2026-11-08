from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_news_embedding_cache import (
    DIMENSIONS, MODEL, EmbeddingCache, identity, sha,
)
from scripts.research.us_news_embeddings_pilot import path_outcome, split_rows, nonoverlap


def item(text='Article', tokens=1):
    return dict(key=identity(text),text=text,tokens=tokens)


def response(tokens=1, indices=(0,)):
    return dict(model=MODEL,usage={'total_tokens':tokens},
                data=[dict(index=i,embedding=[1.]*DIMENSIONS) for i in indices])


def cache(tmp_path):
    c=EmbeddingCache(tmp_path/'cache.sqlite')
    c.register('pilot',sha({'frozen':True}))
    return c


def test_reservation_is_durable_and_unknown_call_cannot_be_retried(tmp_path):
    c=cache(tmp_path)
    c.reserve('pilot',dict(input=[[1]],model=MODEL),1)
    c.close()
    c=EmbeddingCache(tmp_path/'cache.sqlite')
    assert c.summary('pilot')['unresolved_calls']==1
    with pytest.raises(ValueError,match='Unresolved'):
        c.reserve('pilot',dict(input=[[2]],model=MODEL),1)
    c.close()


def test_cap_checked_before_second_request_and_cache_is_reusable(tmp_path):
    c=cache(tmp_path)
    req=dict(input=[[1]],model=MODEL)
    call,_=c.reserve('pilot',req,10_000_000)
    a=item(tokens=10_000_000)
    c.complete(call,[a],response(tokens=10_000_000),10_000_000)
    assert c.get(a['key']).shape==(DIMENSIONS,)
    assert Decimal(c.summary('pilot')['committed_usd'])==Decimal('1.3')
    with pytest.raises(ValueError,match='ceiling'):
        c.reserve('pilot',dict(input=[[2]],model=MODEL),11_000_000)
    with pytest.raises(ValueError,match='already paid'):
        c.reserve('pilot',req,10_000_000)
    assert c.summary('pilot')['api_calls']==1
    c.close()


def test_bad_response_does_not_release_reserved_money(tmp_path):
    c=cache(tmp_path)
    call,_=c.reserve('pilot',dict(input=[[1],[2]],model=MODEL),2)
    with pytest.raises(ValueError,match='indexes'):
        c.complete(call,[item('A'),item('B')],response(tokens=2,indices=(0,0)),2)
    assert c.summary('pilot')['unresolved_calls']==1
    assert c.get(identity('A')) is None
    c.close()


def test_provider_token_mismatch_stops_before_next_request(tmp_path):
    c=cache(tmp_path)
    call,_=c.reserve('pilot',dict(input=[[1]],model=MODEL),1)
    with pytest.raises(ValueError,match='token mismatch'):
        c.complete(call,[item()],response(tokens=2),1)
    assert c.summary('pilot')['unresolved_calls']==1
    c.close()


def test_campaign_cannot_reset_its_protocol_or_budget(tmp_path):
    c=cache(tmp_path)
    with pytest.raises(ValueError,match='changed'):
        c.register('pilot','different')
    c.close()


def window():
    return pd.DataFrame(dict(open=[100.,102.],high=[112.,103.],low=[98.,83.],
        close=[109.,85.],volume=[1000.,1000.],instrument_id=['issuer','issuer'],
        is_filled=[0,0],data_adjustment=['split','split']),index=pd.bdate_range('2024-01-02',periods=2))


def test_maximum_direction_differs_from_first_barrier_and_terminal_sign():
    r=path_outcome(window(),2)
    assert r['qualified'] and r['direction']==0
    assert r['first_touch']=='UP' and r['peak_order']=='UP_FIRST'
    assert r['unit_net_pct']>0 and r['terminal_pct']<0


def test_same_day_dual_barrier_is_explicit_and_conservative():
    w=window();w.loc[w.index[0],'low']=88.
    r=path_outcome(w,2)
    assert r['first_touch']=='AMBIGUOUS' and r['unit_net_pct']<0


def test_gap_through_stop_uses_open_and_identity_break_is_not_a_label():
    w=window();w.loc[w.index[0],['high','close']]=[105.,104.];w.loc[w.index[1],['open','high']]=[85.,90.]
    r=path_outcome(w,2)
    assert r['first_touch']=='DOWN' and r['unit_net_pct']<-15
    w.loc[w.index[1],'instrument_id']='different'
    r=path_outcome(w,2)
    assert not r['qualified'] and 'direction' not in r


def test_missing_sessions_no_forward_fill():
    w=window().iloc[:1]
    assert not path_outcome(w,2)['qualified']


def test_exact_text_cannot_cross_training_validation_and_test():
    f=pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02','2025-01-02','2025-01-03','2026-01-02','2026-01-03']),
        news_count=[1]*5,keys=[['a'],['a'],['b'],['b'],['c']]))
    assert list(split_rows(f))==['TRAIN','','VALIDATION','','TEST']


def test_nonoverlap_preserves_first_signal_without_reading_outcomes():
    days=pd.bdate_range('2026-01-01',periods=25)
    f=pd.DataFrame(dict(date=days[[0,2,6,7]],symbol=['A']*4,direction=[0,1,1,0]))
    kept=nonoverlap(f,days,5)
    assert list(kept.index)==[0,2]
