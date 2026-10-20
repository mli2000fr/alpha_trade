import pytest
from scripts.research import multi_asset_trend_data as s


def test_no_trading_or_iex_endpoint():
    with pytest.raises(ValueError, match='Endpoint'):
        s.fetch_kind(None, 'bad', '/v2/orders', {}, None, None, {}, [0])
    assert s.READ(s.CONFIG)['feed'] == 'sip'


def test_frozen_rules_are_one_primary_not_parameter_search():
    cfg = s.READ(s.CONFIG)
    assert cfg['lookbacks_sessions'] == [63,126,252]
    assert cfg['positive_votes_required'] == 2
    assert cfg['weight_per_active_asset'] * len(cfg['symbols']) == 1
    assert cfg['primary_cost_bps_per_traded_notional'] == 10
    assert not cfg['short'] and not cfg['leverage']
