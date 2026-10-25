import pandas as pd

from scripts.research.us_winner_gpt_veto_1_5_august_2026 import apply_cutoff, previous, trade_differences


def test_inclusive_five_preserves_unknown_invalid_and_original_rows():
    scores = [1,2,3,4,5,6,7,10,None,5]
    frame = pd.DataFrame(dict(gpt_score=scores,gpt_status=['VALID']*9+['INVALID']))
    result = apply_cutoff(frame)
    assert result.gpt_veto.tolist() == [True]*5+[False]*5
    assert 'gpt_veto' not in frame
    pd.testing.assert_frame_equal(result.drop(columns='gpt_veto'),frame)


def test_no_replacement_reranking_or_short_and_common_eligibility_is_preserved():
    cohort = pd.DataFrame(dict(date=[pd.Timestamp('2026-08-03')]*5,symbol=list('ABCDE'),oracle_rank=range(1,6),
        gpt_status=['VALID']*4+['INVALID'],gpt_score=[5,6,7,None,5],selected=[True,False,True,True,True]))
    cohort = apply_cutoff(cohort)
    selected = previous.filtered_signals(cohort)
    assert selected.symbol.tolist() == list('ABCDE')
    assert selected['rank'].tolist() == list(range(1,6))
    assert selected.selected.tolist() == [False,False,True,True,True]
    assert selected.side.eq('long').all()


def test_comparison_separates_removed_and_added_closures_not_causal_attribution():
    control = pd.DataFrame(dict(symbol=['A','B'],entry_date=['x','y'],pnl=[10.,-20.]))
    filtered = pd.DataFrame(dict(symbol=['A','C'],entry_date=['x','z'],pnl=[12.,-5.]))
    result = trade_differences(control,filtered)
    assert result['control_only_closed_trades'] == 1
    assert result['control_only_losers'] == 1 and result['control_only_pnl'] == -20.
    assert result['filtered_only_losers'] == 1 and result['filtered_only_pnl'] == -5.
    assert result['not_a_causal_per_trade_loss_estimate']
