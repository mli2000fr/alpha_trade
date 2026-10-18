"""No real API, SQL or order: prior-session signals use a fresh PAPER account."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from risk_management import operational_data as op
from risk_management.config import RiskConfig
from risk_management.db_io import RiskRepository
from risk_management.models import PriceInfo
from risk_management.portfolio_builder import PortfolioBuilder
from service.market.models import neutral_snapshot

UTC = timezone.utc
DAY = date(2026, 10, 16)  # Friday -> Monday, no weekday-only inference.
NEXT_DAY = date(2026, 10, 19)
CLOSE = datetime(2026, 10, 16, 20, tzinfo=UTC)
NEXT_OPEN = datetime(2026, 10, 19, 13, 30, tzinfo=UTC)


class Calendar:
    def session_dates(self, first, last):
        assert first == last
        return [DAY] if first == DAY else []

    def next_session(self, day):
        assert day == DAY
        return NEXT_DAY

    def session_bounds(self, day):
        if day == DAY:
            return datetime(2026, 10, 16, 13, 30, tzinfo=UTC), CLOSE
        assert day == NEXT_DAY
        return NEXT_OPEN, datetime(2026, 10, 19, 20, tzinfo=UTC)


def snapshot(stamp, **kwargs):
    return op.OperationalDataSnapshot.from_raw(
        account_id=kwargs.get('account_id', 'default'),
        account={'equity':4000., 'cash':4000., 'buying_power':4000.},
        positions=[], orders=[], as_of=stamp,
        source=kwargs.get('source', 'broker:paper:llm'))


@pytest.mark.parametrize('now', [
    datetime(2026,10,16,22,tzinfo=UTC),
    datetime(2026,10,17,0,30,tzinfo=UTC),
    datetime(2026,10,18,6,53,tzinfo=UTC),
    datetime(2026,10,19,6,tzinfo=UTC),  # 08:00 Paris, still before US open.
])
def test_current_snapshot_can_fund_the_prior_session_without_backdating(now):
    stamp = now-timedelta(seconds=20)
    data = snapshot(stamp)
    op.validate_llm_paper_snapshot(data, DAY, now=now, calendar=Calendar())
    assert data.account.as_of == stamp and data.account.as_of is stamp


@pytest.mark.parametrize('day,instant', [
    ('2026-10-08','2026-10-09T08:00:00+02:00'),
    ('2026-10-16','2026-10-18T08:53:00+02:00'),
    ('2026-01-16','2026-01-20T08:00:00+01:00'),
    ('2026-10-30','2026-11-02T08:00:00+01:00'),
])
def test_real_us_calendar_supports_overnight_weekend_holiday_and_dst(day, instant):
    now = datetime.fromisoformat(instant)
    data = snapshot(now-timedelta(seconds=10))
    op.validate_llm_paper_snapshot(data,date.fromisoformat(day),now=now)
    assert data.account.as_of == now-timedelta(seconds=10)


@pytest.mark.parametrize('now,stamp,match', [
    (CLOSE-timedelta(seconds=1), CLOSE-timedelta(seconds=1), 'après clôture'),
    (CLOSE+timedelta(seconds=10), CLOSE-timedelta(seconds=1), 'après clôture'),
    (NEXT_OPEN, NEXT_OPEN-timedelta(seconds=1), 'avant ouverture'),
    (NEXT_OPEN+timedelta(seconds=1), NEXT_OPEN, 'avant ouverture'),
    (CLOSE+timedelta(minutes=10), CLOSE+timedelta(minutes=4,seconds=59), 'périmée'),
    (CLOSE+timedelta(minutes=1), CLOSE+timedelta(minutes=2), 'futur'),
])
def test_unsafe_capture_or_sizing_window_is_rejected(now, stamp, match):
    with pytest.raises(ValueError, match=match):
        op.validate_llm_paper_snapshot(snapshot(stamp), DAY, now=now, calendar=Calendar())


@pytest.mark.parametrize('kwargs', [
    {'account_id':'test1'}, {'source':'broker:live:llm'},
    {'source':'backtest_historical_snapshot'},
])
def test_live_or_other_account_cannot_use_this_exception(kwargs):
    now = CLOSE+timedelta(minutes=1)
    with pytest.raises(ValueError, match='principal PAPER'):
        op.validate_llm_paper_snapshot(snapshot(now, **kwargs), DAY, now=now, calendar=Calendar())


def test_naive_timestamp_and_non_session_signal_are_rejected():
    now = CLOSE+timedelta(minutes=1)
    with pytest.raises(ValueError, match='timezone-aware'):
        op.validate_llm_paper_snapshot(snapshot(now.replace(tzinfo=None)), DAY, now=now)
    with pytest.raises(ValueError, match='hors séance'):
        op.validate_llm_paper_snapshot(snapshot(now), date(2026,10,17), now=now, calendar=Calendar())


@pytest.mark.parametrize('has_candidate', [True, False])
def test_shared_builder_handles_current_paper_snapshot_and_empty_selection(monkeypatch, has_candidate):
    import pandas as pd
    from service.llm_directional.risk_adapter import build_entries
    from risk_management.selection_contract import MLRankedCandidate
    now = datetime(2026,10,18,6,53,tzinfo=UTC)
    data = snapshot(now-timedelta(seconds=15))
    validate = op.validate_llm_paper_snapshot
    monkeypatch.setattr(op, 'validate_llm_paper_snapshot',
        lambda data, day: validate(data, day, now=now, calendar=Calendar()))
    builder = PortfolioBuilder(RiskConfig(account_equity=4000, min_breakout_days=1,
        min_position_notional=0, max_positions=8, max_position_weight=.25, max_sector_weight=.5),
        regime_snapshot=neutral_snapshot(DAY), sector_map={'ABC':'Tech'})
    builder.set_operational_snapshot(data)
    candidates = [MLRankedCandidate('ABC', DAY, 'long', model_run_id='oracle', side_rank=1,
        lineage={'confidence_uncalibrated':.9,'llm_filter_run_id':'llm-test'})] if has_candidate else []
    prices = {'ABC':PriceInfo('ABC',100.,2.,DAY,DAY,1000000.)} if has_candidate else {}
    result = build_entries(builder, candidates, prices, {'ABC':'Tech'}, DAY, pd.DataFrame())
    assert bool(result) == has_candidate
    if has_candidate:
        assert result[0].approved_shares > 0
    else:
        assert result == []
    assert builder.operational_snapshot is data
    assert data.account.as_of == now-timedelta(seconds=15)


@pytest.mark.parametrize('policy,source', [
    ('oracle_pure_long','broker:paper:llm'),
    ('oracle_web_llm_directional','backtest_historical_snapshot'),
])
def test_historical_or_other_policy_still_requires_exact_snapshot_date(policy, source):
    builder = PortfolioBuilder(RiskConfig(account_equity=4000, min_position_notional=0))
    builder.set_operational_snapshot(snapshot(CLOSE+timedelta(days=1), source=source))
    with pytest.raises(ValueError, match='match decision date'):
        builder.build([],{},trade_date=DAY,selection_policy=policy)


def test_empty_factor_request_returns_dataframe_without_sql():
    import pandas as pd
    engine = MagicMock()
    repo = RiskRepository(engine=engine)
    result = repo.load_factor_columns_asof([],DAY)
    assert isinstance(result,pd.DataFrame) and result.empty
    engine.connect.assert_not_called()
