import json
import pandas as pd

from scripts.research.us_extreme50_price_qualification import (
    compare_vendor_paths, crosses, qualify_path, reservations,
)


def test_crossing_excludes_start_close_and_includes_end_close():
    assert not crosses('2022-10-11', '2022-11-01', '2022-10-11')
    assert crosses('2022-10-10', '2022-10-11', '2022-10-11')


def test_single_independent_point_does_not_certify_path():
    case = qualify_path(dict(symbol='CLDX', future_return_pct=60, bars=[
        dict(date='2020-06-09', adj_close=2.99, close=2.99, volume=100),
        dict(date='2020-06-10', adj_close=4.8, close=4.8, volume=100)]))
    assert case['independent_price_points'][0]['matches']
    assert not case['economic_path_certified']
    assert len(case['jumps']) == 1


def test_reservations_do_not_exclude_entire_symbols_or_all_reverse_splits():
    data = pd.DataFrame(dict(symbol=['INDV', 'INDV', 'GRND', 'GRND', 'NBR'],
        date=['2022-11-23', '2023-06-12', '2022-11-17', '2022-11-18', '2020-04-28'],
        oracle_exit_date=['2022-12-22', '2023-07-12', '2022-12-16', '2022-12-19', '2020-05-26']))
    assert reservations(data).tolist() == [True, False, True, False, False]


def test_zero_volume_is_reserved_not_silent_price_repair():
    path = dict(symbol='INDV', future_return_pct=400, bars=[
        dict(date='2022-10-10', adj_close=3.13, close=3.13, volume=0),
        dict(date='2022-10-11', adj_close=15.65, close=15.65, volume=0)])
    result = qualify_path(path)
    assert 'FIVEFOLD_JUMP_NEAR_OFFICIAL_CONSOLIDATION' in result['flags']
    assert 'ZERO_VOLUME_PATH' in result['flags']
    assert result['jumps'][0]['return_pct'] == 400
    assert path['bars'][0]['adj_close'] == 3.13


def test_vendor_scale_difference_is_not_automatically_a_false_return(tmp_path):
    (tmp_path / 'KNTK_eod.json').write_text(json.dumps([
        dict(date='2020-11-04', close=10, adjusted_close=3),
        dict(date='2020-11-05', close=30, adjusted_close=9)]), encoding='utf-8')
    rows = compare_vendor_paths([dict(symbol='KNTK', future_return_pct=200, bars=[
        dict(date='2020-11-04', close=5), dict(date='2020-11-05', close=15)])], tmp_path)
    assert rows[0]['fresh_vendor_raw_return_pct'] == 200
    assert rows[0]['fresh_vendor_total_adjusted_return_pct'] == 200
    assert not rows[0]['independent_source']
