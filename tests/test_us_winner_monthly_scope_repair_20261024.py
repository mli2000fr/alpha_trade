from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
from tests import test_us_winner_monthly_selector_20261024 as prior

study = repair.study


def subset_fixture(monkeypatch, adapter, empty=False):
    rows = [dict(version=1, state=dict(campaign_id=name, symbol=name, lots=[{'remaining': 1}],
            due=name == 'DUE', status='OPEN')) for name in ['DUE', 'ZS', 'NTNX']]
    class Store:
        def rows(self, **kwargs):
            return deepcopy(rows)
        def get(self, key):
            return deepcopy(next(r for r in rows if r['state']['campaign_id'] == key))
    class Parent:
        def __init__(self):
            self.store = Store()
            self.now = pd.Timestamp('2020-11-02T14:25Z')
        def run(self, records):
            visited = []
            for record in records:
                if not record['state']['due']:
                    {}['bars']  # Exactly the deliberately barless pre-open port.
                visited.append(record['state']['symbol'])
            return visited
    monkeypatch.setattr(study.native, 'WinnerCampaignRuntime', Parent)
    with adapter(None, lambda _d: study.REFERENCE) as metadata:
        runtime = study.native.WinnerCampaignRuntime()
        return runtime.run([] if empty else [rows[0]])


def test_original_bug_is_reproduced(monkeypatch):
    with pytest.raises(KeyError, match='bars'):
        subset_fixture(monkeypatch, study.campaign_adapter)


@pytest.mark.parametrize('empty', [False, True])
def test_fixed_scope_never_expands_due_only_or_empty_call(monkeypatch, empty):
    assert subset_fixture(monkeypatch, repair.campaign_adapter, empty) == ([] if empty else ['DUE'])


@pytest.mark.parametrize('pending', [False, True])
def test_repaired_real_month_boundary_and_policy_freeze(monkeypatch, pending):
    monkeypatch.setattr(study, 'campaign_adapter', repair.campaign_adapter)
    prior.test_real_native_runtime_preserves_held_policy_and_rearms_only_pending(pending)


def test_repaired_actual_selected_horizon(monkeypatch):
    monkeypatch.setattr(study, 'campaign_adapter', repair.campaign_adapter)
    prior.test_real_entry_uses_selected_horizon_not_outer_admission_h20()


def test_native_distinct_due_dates_preserves_other_held_position():
    cfg, _ = prior.replay_fixture()
    end = date(2020, 11, 20)
    cfg = replace(cfg, end_date=end, risk_config=replace(cfg.risk_config, max_position_weight=.4))
    schedule = [s for s in study.capacity.grid.calendar().sessions(cfg.start_date-timedelta(days=10), end) if s.is_open]
    history = pd.bdate_range('2019-01-01', end)
    daily = pd.DataFrame({s: 100.+np.sin(np.arange(len(history))) for s in ['AAA', 'BBB']}, index=history)
    actual = [s for s in schedule if s.session_date >= cfg.start_date]
    entry_days = {'AAA': actual[0].session_date, 'BBB': actual[1].session_date}
    raw = {}
    for session in schedule:
        stamps = pd.date_range(session.open_at_utc, session.close_at_utc, freq='5min', inclusive='left')
        parts = []
        for symbol in entry_days:
            values = np.full(len(stamps), 100.)
            if session.session_date == entry_days[symbol]:
                values[1:] = 102.
            elif session.session_date > entry_days[symbol]:
                values[:] = 102.
            parts.append(pd.DataFrame(dict(symbol=symbol, timestamp=stamps, open=values,
                close=values, high=values+.1, low=values-.1, volume=100000.)))
        raw[session.session_date] = pd.concat(parts, ignore_index=True)
    previous = max(s.session_date for s in schedule if s.session_date < cfg.start_date)
    signals = pd.DataFrame([dict(trade_date=previous, symbol='AAA', rank=1, selected=True),
                           dict(trade_date=cfg.start_date, symbol='BBB', rank=2, selected=True)])
    def source(day, symbols):
        return raw[day][raw[day].symbol.isin(symbols)].copy()
    with study.capacity.corrected_runtime(), repair.campaign_adapter(cfg.exec_config, lambda _d: study.PROFILES[3]['name']) as metadata:
        result = prior.BacktestEngine(cfg).run(open_df=daily, close=daily, high=daily+1, low=daily-1,
            volume=daily*100000., signals_df=signals, sector_map={'AAA': 'S', 'BBB': 'S'},
            intraday_source=source, winner_research_assumptions=True, winner_corporate_actions=[])
    trades = result.closed_trades_df
    assert set(trades.symbol) == {'AAA', 'BBB'}
    assert set(trades.exit_reason) == {'HORIZON_OPEN'}
    assert trades.exit_date.nunique() == 2
    assert len([m for m in metadata.values() if m.get('first_fill_at')]) == 2
    assert result.tracker_snapshot['winner_replay']['status'] == 'COMPLETED_EXPLORATORY'
