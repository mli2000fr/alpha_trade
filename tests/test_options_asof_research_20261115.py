from datetime import date
import pandas as pd
from service.options_directional import features as native
from scripts.research.options_asof_rows_20261115 import build_features_asof,rows_asof


def sample(received='2026-10-13T21:00Z'):
    rows=[]
    for side,letter,value in [('CALL','C',100),('PUT','P',20)]:
        rows.append(dict(symbol='AAA',contract_symbol='AAA261102'+letter+'00100000',expiration_date='2026-11-02',
            strike=100.,option_type=side,observed_at=received,available_at=received,provider_timestamp=None,
            open_interest=value,volume=value,bar_timestamp='2026-10-13T19:30Z',payload_hash=letter))
    return pd.DataFrame(rows)


def test_same_receipt_day_same_native_features_and_no_module_patch():
    before=native._rows;f=sample();day=date(2026,10,13);cutoff=pd.Timestamp('2026-10-14T13:25Z')
    assert build_features_asof(f,f,{'AAA':100.},day,cutoff)==native.build_features(f,f,{'AAA':100.},day,cutoff)
    assert native._rows is before


def test_after_midnight_receipt_is_usable_only_before_actual_decision():
    f=sample('2026-10-14T05:00Z');day=date(2026,10,13);cutoff=pd.Timestamp('2026-10-14T13:25Z')
    assert native.build_features(f,f,{'AAA':100.},day,cutoff)=={}
    assert 'AAA' in build_features_asof(f,f,{'AAA':100.},day,cutoff)
    assert build_features_asof(f,f,{'AAA':100.},day,pd.Timestamp('2026-10-14T04:59Z'))=={}


def test_expired_receipts_provider_future_and_wrong_bar_day_rejected():
    day=date(2026,10,13);cutoff=pd.Timestamp('2026-10-14T13:25Z')
    old=sample('2026-10-10T05:00Z');assert rows_asof(old,day,cutoff).empty
    future=sample();future['provider_timestamp']='2026-10-14T14:00Z';assert rows_asof(future,day,cutoff).empty
    wrong=sample();wrong['bar_timestamp']='2026-10-12T19:30Z';assert rows_asof(wrong,day,cutoff,volume=True).empty


def test_fixed_oracle_pool_and_no_forced_selection_among_per_symbol_five():
    from types import SimpleNamespace
    oracle=[dict(symbol=f'S{i:03}',proba_extreme=1-i/201.) for i in range(1,201)]
    evidence={f'S{i:03}':dict(volume_feature=float(i),oi_feature=float(i)) for i in range(1,201)}
    rows=native.select_top(oracle,evidence,
        SimpleNamespace(oracle_top_n=179,min_covered=4,min_combined_score=.5))
    selected={r['symbol'] for r in rows if r['selected']}
    assert len(rows)==179 and 'S180' not in {r['symbol'] for r in rows}
    assert len(selected)==89
    assert not selected & {f'S{i:03}' for i in range(1,6)}
