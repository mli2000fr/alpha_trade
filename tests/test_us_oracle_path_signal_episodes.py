from functools import partial

import pandas as pd
import pytest

from scripts.research.us_oracle_path_signal_episodes import build_episodes, EpisodeBook, EpisodeSession
from scripts.research.us_oracle_path_atr_stop import ATRStopLedger, ARMS as FIXED_ARMS
from scripts.research.us_oracle_path_top5_leverage_grid import UnlimitedLedger, MarginAwareSession, margin_policy
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def sample():
    days = pd.bdate_range('2025-01-02', periods=4)
    rows = []
    for i, d in enumerate(days):
        symbols = ['A', 'B', 'C', 'D', 'E'] if i != 2 else ['F', 'B', 'C', 'D', 'E']
        rows.extend(dict(date=d, symbol=s, year=2025, oracle_rank=k+1, selected=not (i == 1 and s == 'A'))
                    for k, s in enumerate(symbols))
    return pd.DataFrame(rows), days


def test_episode_requires_observed_absence_not_risk_quality_rejection():
    c, days = sample(); m = build_episodes(c, {2025: days}); book = EpisodeBook(m)
    assert book.token(days[0], 'A') == book.token(days[1], 'A')
    assert book.token(days[1], 'A') != book.token(days[3], 'A')
    assert m.loc[m.symbol.eq('A'), 'episode_age_sessions'].tolist() == [1, 2, 1]


def test_episode_metadata_is_prefix_invariant():
    c, days = sample(); full = build_episodes(c, {2025: days})
    prefix = build_episodes(c[c.date.le(days[1])], {2025: days[:2]})
    pd.testing.assert_frame_equal(full[full.date.le(days[1])].reset_index(drop=True), prefix)
    assert 'episode_end' not in full and 'episode_length' not in full


def test_missing_scoring_day_is_not_a_false_rearm():
    c, days = sample()
    with pytest.raises(ValueError, match='Complete original'):
        build_episodes(c[c.date.ne(days[1])], {2025: days})


def test_rank_change_does_not_create_a_new_episode():
    c, days = sample(); c.loc[c.date.eq(days[1]), 'oracle_rank'] = [5, 4, 3, 2, 1]
    b = EpisodeBook(build_episodes(c, {2025: days}))
    assert b.token(days[0], 'A') == b.token(days[1], 'A')


def test_only_recorded_actual_entry_consumes_an_episode():
    c, days = sample(); b = EpisodeBook(build_episodes(c, {2025: days}))
    assert not b.consumed(days[0], 'A')
    b.record_actual_entry(days[0], 'A', enforce=True)
    assert b.consumed(days[1], 'A') and not b.consumed(days[3], 'A')
    with pytest.raises(ValueError, match='Duplicate actual'):
        b.record_actual_entry(days[1], 'A', enforce=True)


def simulate(root, enforce, native=False, renewed=False, rejected_first=False):
    frames, scores, macro, days = fixture_data()
    scores = pd.concat([scores, scores.assign(date=days[2])], ignore_index=True)
    if rejected_first:
        frames['opens'].loc[days[1], 'FIXTURE'] = 110
        frames['high'].loc[days[1], 'FIXTURE'] = 112
    else:
        frames['low'].loc[days[2], 'FIXTURE'] = 94  # first lot stops before second decision
    membership = pd.DataFrame([dict(date=d, symbol='FIXTURE',
        episode_id='B' if renewed and d >= days[2] else 'A') for d in days])
    refs, sessions = [], []
    def factory(cfg, **kwargs):
        cls = UnlimitedLedger if native else ATRStopLedger
        extra = dict(sl=.05, trail=.15, tp=.20) if native else dict(arm=FIXED_ARMS[0])
        ledger = cls(cfg, study_end=days[-1], events=(), **kwargs, **extra); refs.append(ledger); return ledger
    def sf(*args, **kwargs):
        s = EpisodeSession(*args, membership=membership, enforce=enforce, ledger_ref=refs, **kwargs)
        sessions.append(s); return s
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'}, macro=macro,
        market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY',
        output=root, ledger_factory=factory,
        session_factory=partial(MarginAwareSession, ledger_ref=refs) if native else sf,
        protection_options=dict(take_profit_enabled=True, trailing_enabled=True), daily_exit_policy=margin_policy,
        reject_constrained_entries=True)
    return result, refs[0], sessions, days


def test_disabled_episode_filter_exactly_matches_native_reference(tmp_path):
    simulate(tmp_path/'reference', enforce=False)
    simulate(tmp_path/'native', enforce=False, native=True)
    for name in ['daily.parquet', 'trades.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'reference'/name),
            pd.read_parquet(tmp_path/'native'/name), check_exact=True)


def test_stop_then_same_episode_reentry_is_blocked(tmp_path):
    _, _, reference, _ = simulate(tmp_path/'reference', enforce=False)
    result, _, filtered, _ = simulate(tmp_path/'filtered', enforce=True)
    assert len(reference[0].episode_fill_audits) == 2
    assert len(filtered[0].episode_fill_audits) == 1
    assert any(a['blocked'] and not a['already_held'] for a in filtered[0].gate_audits)
    assert result['cash_reconciliation_error'] == pytest.approx(0, abs=1e-8)


def test_renewed_episode_allows_new_entry_after_actual_stop(tmp_path):
    _, _, sessions, _ = simulate(tmp_path, enforce=True, renewed=True)
    assert [a['episode_id'] for a in sessions[0].episode_fill_audits] == ['A', 'B']


def test_rejected_order_does_not_consume_episode_and_fill_retry_is_idempotent(tmp_path):
    _, _, sessions, _ = simulate(tmp_path, enforce=True, rejected_first=True)
    s = sessions[0]
    assert len(s.episode_fill_audits) == 1
    a = s.episode_fill_audits[0]
    s.record_fill(a['execution_event_id'], day=pd.Timestamp(a['fill_date']).date(), symbol=a['symbol'], entry=True)
    assert len(s.episode_fill_audits) == 1
    assert s.book.used['A'] == 1
