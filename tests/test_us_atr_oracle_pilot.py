import pandas as pd
import pytest

from modelFactory.us_atr_oracle_pilot import daily_metrics, summarize, validate_oof


def panel():
    return pd.DataFrame({'date': pd.Timestamp('2020-01-01'),
                         'fold_start': pd.Timestamp('2020-01-01'),
                         'symbol': [f'S{i:02}' for i in range(20)],
                         'proba_extreme': [i/20 for i in range(20)],
                         'atr20_pct': list(range(20)),
                         'oracle_extreme10': [0]*16+[1]*4,
                         'target': [0]*16+[1]*4})


def test_identical_rankings_and_metrics():
    frame = panel()
    validate_oof(frame)
    daily = daily_metrics(frame)
    oracle = daily[daily.policy.eq('ORACLE')].iloc[0]
    assert oracle.precision == 1
    assert oracle.recall == 1
    assert oracle.lift == 5
    assert oracle.overlap_fraction == oracle.jaccard == 1
    assert summarize(daily)['paired']['mean_daily_precision_delta_oracle_minus_atr'] == 0


def test_unknown_label_does_not_change_selection():
    frame = panel()
    frame.loc[19, 'target'] = float('nan')
    row = daily_metrics(frame).query("policy == 'ORACLE'").iloc[0]
    assert row.selected == 4
    assert row.evaluated_selected == 3
    assert row.precision == 1


def test_ties_are_order_independent():
    frame = panel()
    frame['proba_extreme'] = .5
    pd.testing.assert_frame_equal(daily_metrics(frame), daily_metrics(frame.sample(frac=1, random_state=3)))


def test_duplicate_or_untraceable_oof_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        validate_oof(pd.concat([panel(), panel()]))
    frame = panel()
    frame['fold_start'] = pd.Timestamp('2020-01-02')
    with pytest.raises(ValueError, match='provenance'):
        validate_oof(frame)


def test_no_small_universe():
    with pytest.raises(ValueError, match='No eligible'):
        daily_metrics(panel().head(10))


def test_atr_is_adjusted_and_causal(monkeypatch):
    from modelFactory.us_atr_oracle_pilot import atr_panel
    from modelFactory.oracle import security_continuity
    monkeypatch.setattr(security_continuity, 'load_security_discontinuities', lambda: {})
    bars = pd.DataFrame({'date': pd.date_range('2020-01-01', periods=25),
                         'symbol': 'TEST', 'open': 100., 'high': 102.,
                         'low': 98., 'close': 100., 'adj_close': 50.})
    first = atr_panel(bars)
    assert first.atr20_pct.iloc[:19].isna().all()
    assert first.atr20_pct.iloc[19] == pytest.approx(.04)
    bars.loc[24, ['high', 'close', 'adj_close']] = [1000., 900., 450.]
    second = atr_panel(bars)
    pd.testing.assert_frame_equal(first.iloc[:24], second.iloc[:24])
