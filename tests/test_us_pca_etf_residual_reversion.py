import numpy as np
import pandas as pd
import pytest

from scripts.research import us_pca_etf_residual_reversion as study
from scripts.research import us_professional_residual_reversion as base


def panel(n=370, m=11):
    rng = np.random.default_rng(333)
    common = rng.normal(0, .009, (n-1, 3))
    loadings = rng.normal(0, .7, (3, m))
    r = common @ loadings + rng.normal(0, .003, (n-1, m))
    etf = 100*np.vstack([np.ones(m), np.cumprod(1+r, axis=0)])
    state = np.zeros(n)
    for i in range(1, n):
        state[i] = .8*state[i-1]+rng.normal(0, .004)
    stockret = .8*r[:, 0]+.2*r[:, 1]+np.diff(state)
    stock = 100*np.r_[1, np.cumprod(1+stockret)]
    return stock, etf


def scalar(close, etfs, pos):
    raw = etfs[pos-251:pos+1]/etfs[pos-252:pos]-1
    sd = raw.std(axis=0, ddof=1)
    z = (raw-raw.mean(axis=0))/sd
    _, _, vh = np.linalg.svd(z, full_matrices=False)
    vectors = vh[:3].T
    x = z[-60:] @ vectors
    y = close[pos-59:pos+1]/close[pos-60:pos]-1
    fit = np.linalg.lstsq(np.column_stack([np.ones(60), x]), y, rcond=None)[0]
    hedge = (vectors/sd[:, None]) @ fit[1:]
    residual = y-fit[0]-x @ fit[1:]
    state = np.cumsum(residual)
    a, b = np.linalg.lstsq(np.column_stack([np.ones(59), state[:-1]]), state[1:], rcond=None)[0]
    error = state[1:]-a-b*state[:-1]
    with np.errstate(invalid='ignore', divide='ignore'):
        score = (state[-1]-a/(1-b))/np.sqrt((error@error)/57/(1-b*b))
    return hedge, b, score


def test_svd_scalar_matches_eigh_vector_ols_and_ou():
    c, etf = panel(); b = study.rolling_basis(etf, np.ones_like(etf, bool))
    f, h = study.pca_signals(c, np.ones(len(c), bool), b)
    assert f.model_valid.sum() > 5
    assert not b['ready'][:252].any()
    for pos in range(252, len(c), 9):
        hedge, ar, score = scalar(c, etf, pos)
        np.testing.assert_allclose(h[pos], hedge, rtol=0, atol=1e-9)
        assert f.ar_b.iloc[pos] == pytest.approx(ar, abs=1e-9)
        assert f.s_score.iloc[pos] == pytest.approx(score, abs=1e-7, nan_ok=True)


def test_future_prices_do_not_change_pca_or_signals():
    c, etf = panel(); good = np.ones_like(etf, bool)
    a = study.rolling_basis(etf, good); f, h = study.pca_signals(c, np.ones(len(c), bool), a)
    changed = etf.copy(); changed[310:] *= 1.3
    c2 = c.copy(); c2[310:] *= .7
    b = study.rolling_basis(changed, good); g, j = study.pca_signals(c2, np.ones(len(c), bool), b)
    pd.testing.assert_frame_equal(f.iloc[:310], g.iloc[:310])
    np.testing.assert_allclose(h[:310], j[:310], equal_nan=True)
    prefix = study.rolling_basis(etf[:310], good[:310])
    pf, ph = study.pca_signals(c[:310], np.ones(310, bool), prefix)
    pd.testing.assert_frame_equal(f.iloc[:310], pf)
    np.testing.assert_allclose(h[:310], ph, equal_nan=True)


def test_sign_flip_of_eigenvectors_does_not_change_hedge_or_score():
    c, etf = panel(); a = study.rolling_basis(etf, np.ones_like(etf, bool))
    f, h = study.pca_signals(c, np.ones(len(c), bool), a)
    b = {k: v.copy() for k, v in a.items()}
    b['loading'][:, :, 1] *= -1; b['design'][:, :, 1] *= -1; b['operator'][:, 1, :] *= -1
    g, j = study.pca_signals(c, np.ones(len(c), bool), b)
    pd.testing.assert_frame_equal(f, g)
    np.testing.assert_allclose(h, j, equal_nan=True)


def test_etf_permutation_changes_only_hedge_coordinate_order():
    c, etf = panel(); perm = np.random.default_rng(4).permutation(etf.shape[1])
    a = study.rolling_basis(etf, np.ones_like(etf, bool))
    b = study.rolling_basis(etf[:, perm], np.ones_like(etf, bool))
    f, h = study.pca_signals(c, np.ones(len(c), bool), a)
    g, j = study.pca_signals(c, np.ones(len(c), bool), b)
    np.testing.assert_allclose(f.s_score, g.s_score, atol=1e-7, equal_nan=True)
    np.testing.assert_allclose(h[:, perm], j, atol=1e-9, equal_nan=True)


def test_one_missing_etf_point_blocks_full_253_price_window():
    _, etf = panel(n=600); good = np.ones_like(etf, bool); good[300, 2] = False
    basis = study.rolling_basis(etf, good)
    assert basis['ready'][299]
    assert not basis['ready'][300:553].any()
    assert basis['ready'][553]


def test_constant_or_degenerate_etf_no_invented_basis():
    _, etf = panel(); etf[:, 3] = 100
    assert not study.rolling_basis(etf, np.ones_like(etf, bool))['ready'].any()
    with pytest.raises(ValueError):
        study.rolling_basis(etf, np.ones_like(etf, bool), components=11)


def test_stock_missing_point_blocks_61_prices_only():
    c, etf = panel(n=450); good = np.ones(len(c), bool); good[320] = False
    b = study.rolling_basis(etf, np.ones_like(etf, bool)); f, h = study.pca_signals(c, good, b)
    assert not f.model_valid.iloc[320:381].any()
    assert f.s_score.iloc[320:381].isna().all()
    assert np.isnan(h[320:381]).all()


def grid():
    days = pd.bdate_range('2024-01-01', periods=110)
    bars = pd.DataFrame(dict(date=days, open=100., high=101., low=99., close=100., adj_close=100.,
        volume=100000., is_filled=0, instrument_id=1, data_source='alpaca_sip', data_adjustment='split'))
    return days, bars


@pytest.mark.parametrize('mode', ['plain', 'missing', 'identity', 'source', 'unknown', 'filled', 'break', 'reserve', 'events'])
def test_vector_path_reasons_match_parent_all_dates(mode):
    days, bars = grid(); reserve = None; events = []
    if mode == 'missing': bars = bars.drop(index=50)
    if mode == 'identity': bars.loc[65:, 'instrument_id'] = 2
    if mode == 'source': bars.loc[55:, 'data_source'] = 'eodhd_eod'
    if mode == 'unknown': bars.loc[60, 'data_source'] = 'UNKNOWN'
    if mode == 'filled': bars.loc[51, 'is_filled'] = 1
    if mode == 'break': bars.loc[45:, ['open', 'high', 'low', 'close', 'adj_close']] *= 25
    if mode == 'reserve': reserve = {'start': str(days[65].date())}
    if mode == 'events': events = [dict(last_predecessor_date=str(days[59].date()), first_successor_date=str(days[62].date()))]
    g = base.valid_grid(bars, days, reserve, events)
    actual = study.path_reasons(g, reserve, events)
    expected = [base.window_reason(g, i, reserve, events) for i in range(len(days))]
    assert actual.tolist() == expected


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_basket_matches_parent_single_factor(side):
    h = np.array([1.2, 0., 0.])
    w = study.weights_for(h, side)
    ret = study.basket_returns([100, 100, 50, 40], [110, 102, 60, 50], w, 4)
    ref = base.returns_for(100, 110, 100, 102, 1.2, side, 4, 'OU_DYNAMIC')
    for key in ref:
        assert ret[key] == pytest.approx(ref[key], abs=1e-12)


def test_signed_multiple_hedges_all_charged_and_short_borrow_accounted():
    h = [.8, -.4]
    w = study.weights_for(h, 'LONG')
    assert np.abs(w).sum() == pytest.approx(1)
    assert w.tolist() == pytest.approx([1/2.2, -.8/2.2, .4/2.2])
    r = study.basket_returns([100, 100, 100], [110, 102, 95], w, 365)
    assert r['gross'] == pytest.approx((.1-.8*.02-.4*.05)/2.2)
    assert r['borrow'] == pytest.approx(.8/2.2*.003)
    assert r['costs'] == pytest.approx(.0008*(2.1+.8*2.02+.4*1.95)/2.2)
    assert r['net_stress'] < r['net']


@pytest.mark.parametrize('hedge,side', [([0, 0], 'LONG'), ([3, .1], 'LONG'), ([np.nan], 'LONG'), ([1], 'X')])
def test_invalid_exposure_rejected(hedge, side):
    with pytest.raises(ValueError): study.weights_for(hedge, side)


def test_gap_loss_is_not_capped_by_daily_risk_threshold():
    op = np.full((25, 3), 100.); cl = op.copy(); z = np.full(25, -2.); valid = np.ones(25, bool)
    cl[1, 0] = 85; op[2, 0] = 60
    end, why, age = study.basket_exit(op, cl, z, valid, 0, 'LONG', [.8, -.2])
    assert (end, why, age) == (2, 'DAILY_RISK_NEXT_OPEN', 1)
    assert study.basket_returns(op[1], op[end], study.weights_for([.8, -.2], 'LONG'), 1)['net'] < -.20


def test_exit_uses_fixed_entry_hedge_and_next_open():
    op = np.full((25, 3), 100.); cl = op.copy(); z = np.full(25, -2.); valid = np.ones(25, bool)
    z[3] = -.5
    assert study.basket_exit(op, cl, z, valid, 0, 'LONG', [.8, -.2]) == (4, 'REVERSION_NEXT_OPEN', 3)
    z[4:] = -200; cl[4:] = 500
    assert study.basket_exit(op, cl, z, valid, 0, 'LONG', [.8, -.2]) == (4, 'REVERSION_NEXT_OPEN', 3)


def test_invalid_model_and_timeout():
    op = np.full((25, 3), 100.); cl = op.copy(); z = np.full(25, 2.); valid = np.ones(25, bool)
    assert study.basket_exit(op, cl, z, valid, 0, 'SHORT', [1, .2])[1] == 'TIMEOUT_NEXT_OPEN'
    valid[2] = False
    assert study.basket_exit(op, cl, z, valid, 0, 'SHORT', [1, .2]) == (3, 'INVALID_MODEL_NEXT_OPEN', 2)


def test_compare_common_dates_without_zero_filling_or_causal_pair_claim():
    days = pd.bdate_range('2024-01-01', periods=100)
    rows = pd.DataFrame(dict(date=[days[0], days[0], days[1]], arm=['PCA3_ETF', 'SPY', 'PCA3_ETF'],
        net=[.03, .01, .99], scope='FULL_TRADABLE', year=2024, policy='OU_DYNAMIC'))
    r = study.compare_dates(rows, days)
    assert len(r) == 1 and r[0]['common_dates'] == 1
    assert r[0]['delta'] == pytest.approx(.02)
