from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from common.oracle_atr import atr20_percent_panel, filter_oracle_atr_percentiles, load_oracle_atr_by_date, resolve_oracle_atr_enabled
from modelFactory.predictor import CascadePrediction, cascade_select, apply_cascade_to_predictions, load_cascade_config


def test_percentiles_are_not_reranked_and_use_whole_population():
    pct={'A':1., 'B':.9, 'C':.8, 'D':.2, 'E':.1}
    kept,diag=filter_oracle_atr_percentiles(pct, {'A':1.,'B':2.,'C':3.,'D':4.,'E':5.})
    assert kept=={}  # ATR winners D/E are not in Oracle TOP20.
    assert diag['oracle_before']==3
    kept,_=filter_oracle_atr_percentiles(pct,{'A':5.,'B':4.,'C':3.,'D':2.,'E':1.})
    assert kept=={'A':1.,'B':.9}


def test_missing_atr_is_rejected_and_total_absence_is_blocking():
    pct={'A':1.,'B':.9,'C':.1}
    kept,diag=filter_oracle_atr_percentiles(pct,{'B':2.,'C':1.})
    assert kept=={'B':.9}
    assert diag['atr_missing']==1
    with pytest.raises(RuntimeError,match='aucun ATR'):
        filter_oracle_atr_percentiles(pct,{})


def test_atr_adjusted_formula_causality_and_exact_date_support():
    n=45
    bars=pd.DataFrame({'symbol':'A','date':pd.bdate_range('2025-01-01',periods=n),
                       'high':102.,'low':98.,'close':100.,'adj_close':50.})
    result=atr20_percent_panel(bars)
    assert result.atr20_pct.iloc[20]==pytest.approx(.04)
    assert result.atr20_pct.iloc[:20].isna().all()
    changed=bars.copy()
    changed.loc[30:,'high']=500.
    pd.testing.assert_frame_equal(result.iloc[:30],atr20_percent_panel(changed).iloc[:30])
    changed=bars.copy()
    changed.loc[18,'adj_close']=np.nan
    assert pd.isna(atr20_percent_panel(changed).atr20_pct.iloc[20])


def test_loader_bounded_at_j_and_rejects_stale_bars():
    bars=pd.DataFrame({'symbol':'A','date':pd.bdate_range(end='2025-01-30',periods=24),
                       'high':102.,'low':98.,'close':100.,'adj_close':100.})
    from unittest.mock import MagicMock
    engine=MagicMock()
    with patch('common.oracle_atr.pd.read_sql',return_value=bars) as read:
        result=load_oracle_atr_by_date(engine,['A'],['2025-01-31'])
    assert result=={'2025-01-31':{}}
    assert str(read.call_args.kwargs['params']['end'])=='2025-01-31'


def test_bool_config_and_default_enabled(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_cascade_config()['oracle_atr_enabled'] is True
    (tmp_path/'config.yaml').write_text('cascade:\n  oracle_atr_enabled: false\n')
    assert load_cascade_config()['oracle_atr_enabled'] is False
    (tmp_path/'config.yaml').write_text('cascade:\n  oracle_atr_enabled: "false"\n')
    with pytest.raises(ValueError):
        load_cascade_config()
    with pytest.raises(ValueError):
        resolve_oracle_atr_enabled('false')


@pytest.mark.parametrize('mode',['extreme_gate','extreme_gate_directional'])
def test_both_cascade_modes_and_rollback(mode):
    day='2025-01-02'
    scores={str(i):float(i) for i in range(10)}
    preds={s:CascadePrediction(symbol=s,long_prob=.8,short_prob=.1) for s in scores}
    # Oracle top: 7/8/9. ATR top: 0/1/9 -> intersect only9.
    atr={s:1. for s in scores}
    atr.update({'0':10.,'1':11.,'9':12.})
    cfg={'top_pct':.2,'min_prob_regression':.55,'oracle_atr_enabled':True}
    with patch('modelFactory.predictor.load_cascade_config',return_value=cfg):
        actual=cascade_select(day,'batch',preds,rank_mode=mode,oracle_rank_map={day:scores},
                              extreme_gate_pct=.2,oracle_atr_values=atr)
        with patch('common.oracle_atr.load_oracle_atr_by_date',side_effect=AssertionError('No DB on rollback')):
            legacy=cascade_select(day,'batch',preds,rank_mode=mode,oracle_rank_map={day:scores},
                                  extreme_gate_pct=.2,oracle_atr_enabled=False)
    assert [s for _,s,_ in actual]==['9']
    assert [s for _,s,_ in legacy]==['9','8','7']


def test_backtest_prefetch_once():
    day='2025-01-02'
    frame=pd.DataFrame({'trade_date':[day]*10,'symbol':[str(i) for i in range(10)],
                        'predicted_side':'long','proba_long':.8,'proba_short':.1,'proba_flat':.1})
    scores={str(i):float(i) for i in range(10)}
    atr={str(i):float(i+1) for i in range(10)}
    with patch('modelFactory.predictor.load_cascade_config',return_value={'top_pct':.2,'min_prob_classification':.55,'oracle_atr_enabled':True}), \
         patch('common.oracle_atr.load_oracle_atr_by_date',return_value={day:atr}) as load:
        out=apply_cascade_to_predictions(frame,'batch',rank_mode='extreme_gate',
                oracle_rank_map={day:scores},extreme_gate_pct=.2,extreme_gate_per_symbol='bypass')
    load.assert_called_once()
    assert set(out.loc[out.predicted_side.eq('long'),'symbol'])=={'7','8','9'}


def test_live_uses_same_helper_and_price_loader():
    import ast
    from pathlib import Path
    tree=ast.parse(Path('risk_management/cli.py').read_text(encoding='utf-8'))
    names=[node.func.id for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)]
    assert 'filter_oracle_atr_percentiles' in names
    assert 'load_oracle_atr_by_date' in names


def test_loader_empty_history():
    from unittest.mock import MagicMock
    with patch('common.oracle_atr.pd.read_sql',return_value=pd.DataFrame()):
        assert load_oracle_atr_by_date(MagicMock(),['A'],['2025-01-31'])=={'2025-01-31':{}}


def test_nonoracle_mode_does_not_load_atr():
    with patch('modelFactory.predictor.load_cascade_config',return_value={'top_pct':.2,'oracle_atr_enabled':True}), \
         patch('modelFactory.predictor.load_global_ranks_from_db',return_value=pd.DataFrame()), \
         patch('common.oracle_atr.load_oracle_atr_by_date',side_effect=AssertionError('Not an Oracle gate')):
        assert cascade_select('2025-01-02','batch',{},rank_mode='global_rank')==[]


def test_directional_short_is_preserved_after_amplitude_gate():
    day='2025-01-02'
    scores={str(i):float(i) for i in range(10)}
    preds={s:CascadePrediction(symbol=s,long_prob=.1,short_prob=.8,side='short') for s in scores}
    with patch('modelFactory.predictor.load_cascade_config',return_value={'top_pct':.2,'min_prob_regression':.55,'oracle_atr_enabled':True}):
        selected=cascade_select(day,'batch',preds,rank_mode='extreme_gate_directional',
            oracle_rank_map={day:scores},oracle_atr_values={s:float(int(s)+1) for s in scores})
    assert {side for side,_,_ in selected}=={'SHORT'}
    assert {symbol for _,symbol,_ in selected}=={'7','8','9'}
