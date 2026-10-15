from functools import partial
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_challengers import (
    FEATURES, SCORE_FEATURES, CausalDailyExit, DailyExitLedger,
    LifecyclePersonalizedLedger, label_availability, build_training_chunk,
)
from scripts.research.us_oracle_tp20_sl10_models import SizedSession
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from service.market import parse_market_regimes


def test_expiry_open_is_included_in_label_availability():
    days = pd.bdate_range('2021-12-06', periods=21)
    available = label_availability('2021-12-27', days, [(1,110.,'tp'), (20,100.,'expiry')])
    assert available == days[-1]
    assert available >= pd.Timestamp('2022-01-01')


def test_declared_available_date_is_never_shortened():
    days = pd.bdate_range('2021-01-01', periods=21)
    assert label_availability('2021-02-20', days, [(1,120.,'tp')]) == pd.Timestamp('2021-02-20')


def training_fixture():
    from modelFactory.oracle_barrier import SCORES
    days = pd.bdate_range('2020-01-01', periods=30)
    bars = pd.DataFrame(dict(date=days, symbol='A', open=100., high=101., low=99., close=100.,
        adj_close=100., volume=1000., is_filled=0, instrument_id='1'))
    raw = pd.DataFrame(dict(date=days, symbol='A', **{f: .1 for f in FEATURES}))
    selected = pd.DataFrame([dict(date=days[0], symbol='A', path_qualified=True, long_gross_return=0.,
        selection_rank=1, oracle_available_date=days[21], **{f:.1 for f in FEATURES},
        **{f:.6 for f in SCORES.values()})])
    return selected, raw, bars, days


def test_state_stops_at_hard_barrier_and_never_uses_future_features():
    selected, raw, bars, days = training_fixture()
    bars.loc[3,'high'] = 125.
    raw.loc[raw.date.gt(days[3]), FEATURES] = 999.
    entries, states, _ = build_training_chunk(selected, raw, bars, days)
    assert len(entries) == 1 and len(states) == 2
    assert states.date.max() == days[2]
    assert not states[FEATURES].eq(999).any().any()
    assert states.weight.sum() == pytest.approx(1.)


@pytest.mark.parametrize('column,value,reason',[
    ('volume',0.,'missing_or_nonpositive_volume'),
    ('is_filled',1,'filled_or_changed_identity'),
    ('instrument_id','2','filled_or_changed_identity'),
])
def test_unknown_training_path_is_excluded_not_marked_loser(column,value,reason):
    selected, raw, bars, days = training_fixture()
    bars.loc[4,column] = value
    entries, states, excluded = build_training_chunk(selected, raw, bars, days)
    assert entries.empty and states.empty and excluded[reason] == 1


class FixedHead:
    def __init__(self,value=-.1): self.value=value; self.seen=[]
    def feature_name(self): return SCORE_FEATURES+['age','pnl','mfe','mae','distance_stop','distance_tp']
    def predict(self,frame,**kwargs): self.seen.append(frame.copy()); return [self.value]


def test_daily_exit_uses_original_entry_scores_after_conversion():
    days = pd.bdate_range('2026-01-01', periods=6)
    head = FixedHead()
    features = pd.DataFrame([dict(date=days[0],symbol='OLD',**{f:.7 for f in SCORE_FEATURES}),
        dict(date=days[4],symbol='NEW',**{f:9. for f in SCORE_FEATURES})])
    position = SimpleNamespace(signal_context={'entry_symbol':'OLD'}, entry_idx=1,
        entry_date=days[1],entry_price=50.,replay_initial_stop_price=45.,replay_take_profit_price=60.)
    frame = pd.DataFrame({'NEW':[50.]*6},index=days)
    ledger = SimpleNamespace(state=SimpleNamespace(positions={'NEW':position}),days=days,
        close=frame,high=frame+1,low=frame-1)
    policy = CausalDailyExit(head,features)
    orders = policy(days[4],ledger,{'close':frame.loc[:days[4]]})
    assert orders[0]['entry_symbol'] == 'OLD'
    assert head.seen[0][SCORE_FEATURES].eq(np.float32(.7)).all().all()
    assert head.seen[0].age.iloc[0] == 3


def test_daily_exit_refuses_future_observed_history():
    days=pd.bdate_range('2026-01-01',periods=2)
    policy=CausalDailyExit(FixedHead(),pd.DataFrame(dict(date=days,symbol='A')))
    with pytest.raises(ValueError,match='future prices'):
        policy(days[0],None,{'close':pd.DataFrame({'A':[1.,1.]},index=days)})


def test_queued_exit_is_remapped_in_place():
    policy=CausalDailyExit(FixedHead(),pd.DataFrame(dict(date=[],symbol=[])))
    order=dict(symbol='OLD',entry_date='2026-01-01')
    policy.orders=[order]
    policy.remap_pending([('OLD','NEW',1.)])
    assert order['symbol']=='NEW' and order['converted_from']=='OLD'


def test_offline_tail_features_ignore_sparse_benchmark_index_and_future():
    from scripts.research.us_oracle_challengers_v2 import causal_features
    days=pd.bdate_range('2023-01-01',periods=720)
    close=100+np.arange(len(days))*.04+np.sin(np.arange(len(days))*.5)
    bars=pd.DataFrame(dict(date=days,symbol='A',open=close,high=close+2,low=close-2,close=close,
        adj_close=close,volume=1000+np.arange(len(days))%31,is_filled=0))
    benchmark=bars.copy();benchmark['symbol']='SPY';benchmark.index=np.arange(len(days))*100+5000
    full=causal_features(bars,benchmark)
    past=causal_features(bars.iloc[:650],benchmark.iloc[:650])
    assert len(full)>0 and len(past)>0
    a=full.loc[full.date.isin(past.date),['date',*FEATURES]].reset_index(drop=True)
    pd.testing.assert_frame_equal(a,past[['date',*FEATURES]].reset_index(drop=True))


@pytest.mark.parametrize('ratio',[1.,2.])
def test_personalized_profile_survives_name_or_share_conversion(tmp_path,ratio):
    from tests.test_us_oracle_merger_ledger import converted_fixture
    frames,scores,macro,days,event=converted_fixture()
    if ratio==1:
        for f in frames.values(): f['NEW']=f.FIXTURE
    event=dict(event,ratio=str(ratio),event_type='NAME_CHANGE' if ratio==1 else 'MERGER')
    profiles={(days[0],'FIXTURE'):(.25,.1)}
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology','NEW':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        session_factory=partial(SizedSession,profiles=profiles),
        ledger_factory=partial(LifecyclePersonalizedLedger,profiles=profiles,events=(event,),cash_policy='STRICT'),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.symbol=='NEW' and trade.entry_symbol=='FIXTURE'
    assert trade.replay_initial_stop_price==pytest.approx(90./ratio)
    assert trade.replay_take_profit_price==pytest.approx(125./ratio)
    assert result['personalized_protection_audit']['verified']
    assert abs(result['cash_reconciliation_error'])<1e-8


def test_learned_order_executes_next_open_after_ticker_change(tmp_path):
    from tests.test_us_oracle_merger_ledger import converted_fixture
    frames,scores,macro,days,event=converted_fixture()
    for f in frames.values(): f['NEW']=f.FIXTURE
    event=dict(event,ratio='1',event_type='NAME_CHANGE')
    class ExitOnEve:
        orders=[]
        audit=[]
        def __call__(self,day,ledger,frames):
            self.orders=[dict(symbol=s,entry_date=p.entry_date,decision_date=day)
                for s,p in ledger.state.positions.items()] if day==days[3] else []
            return self.orders
        def remap_pending(self,conversions):
            for source,target,_ in conversions:
                for order in self.orders:
                    if order['symbol']==source: order['symbol']=target
    policy=ExitOnEve()
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology','NEW':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        daily_exit_policy=policy,ledger_factory=partial(DailyExitLedger,daily_policy=policy,events=(event,),cash_policy='STRICT'),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.exit_reason=='learned_exit_next_open' and trade.symbol=='NEW'
    assert trade.exit_date==days[4]
    assert abs(result['cash_reconciliation_error'])<1e-8
