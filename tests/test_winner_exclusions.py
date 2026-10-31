"""Exclusions are declared for a whole replay, never applied to held lots after a gap."""
from dataclasses import replace

import pandas as pd
import pytest

from backtesting.winner_exclusions import excluded_symbols,apply_exclusions


def test_parse_and_reject_invalid_exclusions():
    assert excluded_symbols(' sdgr, APP; sdgr\nKSS ')==['APP','KSS','SDGR']
    assert excluded_symbols('')==[]
    for value in ('../SDGR','SDGR/APP','SDGR*',None):
        with pytest.raises(ValueError):excluded_symbols(value)


def test_original_ranks_are_preserved_without_a_replacement_from_below_top_n():
    from backtesting.winner_campaign_replay import validate_scores
    dates=['2025-01-02','2025-01-03']
    rows=pd.DataFrame([dict(trade_date=day,symbol=s,proba_extreme=score,
        fold_start='2024-01-01',lineage_fold_start='2024-01-01',model_available_date='2024-12-31',
        target_name='oracle_path_extreme10',target_horizon=10,feature_profile_sha256='profile',model_sha256='weights')
        for day in dates for s,score in [('SDGR',.9),('AAA',.8),('BBB',.7)]])
    folds={'2024-01-01':dict(model_sha256='weights',metrics=dict(train_available_max='2024-12-30',val_available_max='2024-12-31'))}
    selected=validate_scores(rows,profile_hash='profile',folds=folds,
        expected_days=[pd.Timestamp(d).date() for d in dates],top_n=2,horizon=10)
    before=selected.copy(deep=True)
    kept,removed=apply_exclusions(selected,['SDGR'])
    assert kept.symbol.tolist()==['AAA','AAA']
    assert kept['rank'].tolist()==[2,2] and len(removed)==2
    assert not removed.selected.any()
    pd.testing.assert_frame_equal(selected,before)


@pytest.mark.usefixtures('isolated_winner_config')
def test_run_wide_exclusion_never_stages_the_bad_ticker_or_drops_a_held_position():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=fixture(symbols=('AAA','BBB'))
    raw[(cfg.end_date,'AAA')]=raw[(cfg.end_date,'AAA')].iloc[1:]
    with pytest.raises(ValueError,match='Missing held-position'):
        BacktestEngine(cfg).run(**args)
    args['signals_df'],removed=apply_exclusions(args['signals_df'],['AAA'])
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert buys.symbol.tolist()==['BBB'] and len(removed)==1


def test_command_passes_normalized_exclusions_to_the_actual_parser():
    from tests.test_winner_backtest_wiring import options
    from ihm.services.backtesting_runner import build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    args=build_parser().parse_args(build_backtesting_command('run',options(winner_excluded_symbols='sdgr, APP'))[4:])
    assert args.exclude_symbols=='APP,SDGR'
