from functools import partial

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_protection_selector as selector
from scripts.research.us_oracle_path_top5_leverage_grid import UnlimitedLedger, MarginAwareSession, margin_policy
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def test_frozen_profile_choice_not_a_probability():
    assert selector.choose_profiles([2., -2., 1., 0.], [1., 3., 1., 0.]).tolist() == [
        'COURT', 'LARGE', 'COURT', 'REFERENCE']
    assert selector.choose_profiles([1e-11], [0.]).tolist() == ['REFERENCE']
    assert selector.PROFILES == {'COURT': (.1, .1), 'REFERENCE': (.15, .2), 'LARGE': (.2, .3)}


def test_invalid_predicted_advantage_fails_closed():
    with pytest.raises(ValueError):
        selector.choose_profiles([np.nan], [0.])


def test_equal_date_weights_and_validation_only_constant():
    f = pd.DataFrame(dict(date=pd.to_datetime(['2021-01-01', '2021-01-01', '2021-01-04'])))
    weights = selector.equal_date_weights(f)
    assert weights.mean() == 1
    assert weights[0]+weights[1] == weights[2]
    val = pd.DataFrame({'REFERENCE_net_pct': [1., 1.], 'COURT_net_pct': [2., 0.], 'LARGE_net_pct': [0., 0.]})
    assert selector.constant_on_validation(val) == 'REFERENCE'


def simulation(output, arm, *, profile='REFERENCE', native=False, moving=False):
    frames, scores, macro, days = fixture_data()
    contexts = pd.DataFrame([dict(date=d, symbol='FIXTURE', chosen_profile=profile,
        court_advantage_pct=1., large_advantage_pct=2.) for d in days])
    contexts.loc[contexts.date.gt(days[0]), 'chosen_profile'] = 'COURT'
    if moving:
        frames['high'].loc[days[1], 'FIXTURE'] = 125.
        for col, price in [('opens', 122.), ('high', 131.), ('low', 121.), ('close', 125.)]:
            frames[col].loc[days[2], 'FIXTURE'] = price
    ref = []
    def factory(cfg, **kwargs):
        if native:
            trail, tp = selector.PROFILES[arm.removeprefix('FIXED_')]
            ledger = UnlimitedLedger(cfg, sl=.05, trail=trail, tp=tp, study_end=days[-1], events=(), **kwargs)
        else:
            ledger = selector.SelectorLedger(cfg, profile_decisions=contexts, arm=arm, study_end=days[-1], events=(), **kwargs)
        ref.append(ledger); return ledger
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'}, macro=macro,
        market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY',
        output=output, ledger_factory=factory,
        session_factory=partial(MarginAwareSession if native else selector.SelectorSession, ledger_ref=ref),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=True),
        daily_exit_policy=margin_policy, reject_constrained_entries=True)
    return result, ref[0], pd.read_parquet(output/'trades.parquet'), days


@pytest.mark.parametrize('profile', ['COURT', 'REFERENCE', 'LARGE'])
def test_each_fixed_wrapper_exact_native_parity(tmp_path, profile):
    a, _, _, _ = simulation(tmp_path/'wrapped', f'FIXED_{profile}')
    b, _, _, _ = simulation(tmp_path/'native', f'FIXED_{profile}', native=True)
    assert a['return_pct'] == b['return_pct']
    for name in ['daily.parquet', 'trades.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'wrapped'/name), pd.read_parquet(tmp_path/'native'/name))


def test_learned_profile_stays_locked_and_hard_stop_unchanged(tmp_path):
    result, ledger, trades, days = simulation(tmp_path, 'LEARNED', profile='LARGE', moving=True)
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade.entry_date == days[1] and trade.exit_date == days[2]
    assert trade.exit_price == 130.
    assert trade.replay_initial_stop_price == 95.
    assert trade.replay_take_profit_price == 130.
    assert trade.replay_trailing_stop_pct == .20
    assert ledger.fill_profile_audits[0]['profile'] == 'LARGE'
    assert result['cash_reconciliation_error'] == pytest.approx(0., abs=1e-8)


def test_learned_reference_exact_fixed_reference(tmp_path):
    simulation(tmp_path/'learned', 'LEARNED')
    simulation(tmp_path/'fixed', 'FIXED_REFERENCE')
    for name in ['daily.parquet', 'trades.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'learned'/name), pd.read_parquet(tmp_path/'fixed'/name))


def test_small_fit_ignores_control_labels_and_uses_feature_rank(tmp_path, monkeypatch):
    from scripts.research.us_oracle_path_protection_dataset import FEATURES
    rng = np.random.default_rng(731)
    dates = pd.bdate_range('2019-01-01', periods=400).append(pd.bdate_range('2022-01-03', periods=180)).append(
        pd.bdate_range('2023-01-03', periods=20))
    x = pd.DataFrame(rng.normal(size=(len(dates), len(FEATURES))), columns=FEATURES)
    x['date'] = dates; x['symbol'] = 'FIXTURE'; x['oracle_rank'] = 1
    labels = x[['date', 'symbol']].copy()
    labels['oracle_rank'] = 99  # Label-side metadata must not overwrite decision X.
    labels['label_available'] = dates+pd.Timedelta(days=1)
    labels['split'] = ['FIT_2018_2021']*400+['VALIDATION_2022']*180+['CONTROL_2023']*20
    labels['REFERENCE_net_pct'] = 0.
    labels['COURT_net_pct'] = x.momentum_20.to_numpy()*2
    labels['LARGE_net_pct'] = -x.momentum_20.to_numpy()*2
    labels['target_court_advantage_pct'] = labels.COURT_net_pct
    labels['target_large_advantage_pct'] = labels.LARGE_net_pct
    data = tmp_path/'data'; data.mkdir()
    monkeypatch.setattr(selector, 'DATA', data)
    x.to_parquet(data/'decision-features.parquet', index=False)
    labels.to_parquet(data/'outcomes.parquet', index=False)
    a = tmp_path/'a'; a.mkdir()
    fitted = selector.fit_selector(a, {})
    assert fitted['fit_rows'] == 400 and fitted['validation_rows'] == 180
    assert not fitted['trained_on_control_or_annual_results']
    labels.loc[labels.split.eq('CONTROL_2023'), ['target_court_advantage_pct', 'target_large_advantage_pct']] = 1e6
    labels.to_parquet(data/'outcomes.parquet', index=False)
    b = tmp_path/'b'; b.mkdir()
    changed = selector.fit_selector(b, {})
    assert fitted['files'] == changed['files']  # Future control labels never affect weights.
    decision = selector.predict_profiles(a/'selector', x[['date', 'symbol', *FEATURES]])
    assert len(decision) == len(x)
