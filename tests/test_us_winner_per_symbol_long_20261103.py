import numpy as np
import pandas as pd

from scripts.research.us_winner_per_symbol_long_20261103 import choose, long_labels, splits


def bars():
    days = pd.bdate_range('2023-01-02',periods=16)
    frame = pd.DataFrame(dict(date=days,open=100.,high=102.,low=99.,close=101.,
        adj_close=101.,volume=1000.,is_filled=0,instrument_id=1,data_source='eodhd_eod'))
    return days,frame


def test_proxy_counts_entry_day_and_exits_at_next_open_after_horizon():
    days,frame=bars();frame.loc[11,['open','high','close','adj_close']]=[110.,111.,110.,110.]
    labels=long_labels(frame,days,horizon=10,stop=.05,fee=0)
    assert labels.iloc[0].label_net_return == .1 or np.isclose(labels.iloc[0].label_net_return,.1)
    assert labels.iloc[0].label_available_date == days[11]
    assert labels.iloc[0].label_exit == 'TIME_OPEN'


def test_gap_stop_is_worse_than_the_nominal_five_percent():
    days,frame=bars();frame.loc[3,['open','high','low','close','adj_close']]=[90.,92.,89.,91.,91.]
    labels=long_labels(frame,days,horizon=10,stop=.05,fee=0)
    assert np.isclose(labels.iloc[0].label_net_return,-.1)
    assert labels.iloc[0].label_exit == 'SL_GAP'
    assert labels.iloc[0].label_available_date == days[11]


def test_unknown_future_path_never_becomes_a_negative_training_label():
    days,frame=bars();frame.loc[5,'is_filled']=1
    labels=long_labels(frame,days,horizon=10,stop=.05,fee=0)
    assert not labels.date.eq(days[0]).any()


def test_identity_change_excludes_only_training_label_crossing_it():
    days,frame=bars();frame.loc[4:,'instrument_id']=2
    labels=long_labels(frame,days,horizon=10,stop=.05,fee=0)
    assert not labels.date.eq(days[0]).any()


def test_fit_calibration_and_test_boundaries_are_all_purged():
    panel=pd.DataFrame(dict(date=pd.to_datetime(['2022-12-01','2022-12-23','2023-06-01','2023-12-20']),
        label_available_date=pd.to_datetime(['2022-12-19','2023-01-10','2023-06-19','2024-01-09']),
        label=[1.,0.,1.,0.]))
    fit,cal=splits(panel,year=2024,cutoff=pd.Timestamp('2023-12-29'))
    assert fit.date.tolist()==[pd.Timestamp('2022-12-01')]
    assert cal.date.tolist()==[pd.Timestamp('2023-06-01')]


def test_models_for_2025_and_2026_use_updated_calibration_years():
    panel=pd.DataFrame(dict(date=pd.to_datetime(['2023-06-01','2024-06-01','2025-06-02']),
        label_available_date=pd.to_datetime(['2023-06-20','2024-06-20','2025-06-20']),label=[1.,0.,1.]))
    fit25,cal25=splits(panel,year=2025,cutoff=pd.Timestamp('2024-12-31'))
    fit26,cal26=splits(panel,year=2026,cutoff=pd.Timestamp('2025-12-31'))
    assert cal25.date.dt.year.tolist()==[2024]
    assert cal26.date.dt.year.tolist()==[2025]
    assert len(fit26)>len(fit25)


def candidates():
    return pd.DataFrame(dict(trade_date=[pd.Timestamp('2024-01-02')]*20,
        symbol=[f'S{i:02}' for i in range(20)],rank=np.arange(1,21),proba_extreme=np.linspace(1,.5,20),
        long_probability=np.linspace(.1,.9,20),future_pnl=np.arange(20)))


def test_long_selector_is_only_inside_original_top20_and_uses_no_outcome():
    a=candidates();chosen=choose(a,'PER_SYMBOL_TOP10')
    assert set(chosen.symbol)==set(a.iloc[10:].symbol)
    assert 'future_pnl' not in chosen
    a['future_pnl']=-1e9
    pd.testing.assert_frame_equal(chosen,choose(a,'PER_SYMBOL_TOP10'))


def test_unknown_model_scores_do_not_receive_neutral_or_nplus1_fallbacks():
    a=candidates();a.loc[:13,'long_probability']=np.nan
    assert len(choose(a,'PER_SYMBOL_TOP10'))==6
    assert len(choose(a,'ORACLE_TOP20'))==20
    assert choose(a,'ORACLE_TOP10')['rank'].tolist()==list(range(1,11))
