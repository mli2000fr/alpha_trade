from __future__ import annotations

import logging
from datetime import date
from typing import Any, cast

import pandas as pd
import pytest

from event_sentiment.config import EventSentimentConfig
from event_sentiment.history_backfill import EventSentimentHistoryBackfillService


class _FakeRepository:
    def __init__(self) -> None:
        self.scored_dates = [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)]
        self.feature_frame_calls: list[dict[str, object]] = []
        self.ticker_upserts: list[list[dict[str, object]]] = []
        self.sector_upserts: list[list[dict[str, object]]] = []

    def list_scored_trade_dates(self, start_date=None, end_date=None, ingestion_source=None):
        dates = list(self.scored_dates)
        if start_date is not None:
            dates = [value for value in dates if value >= start_date]
        if end_date is not None:
            dates = [value for value in dates if value <= end_date]
        return dates

    def load_feature_frames(self, start_date=None, end_date=None, trade_dates=None, ingestion_source=None, ticker_symbols=None):
        self.feature_frame_calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "trade_dates": trade_dates,
                "ingestion_source": ingestion_source,
                "ticker_symbols": ticker_symbols,
            }
        )
        ticker_df = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "effective_trade_date": date(2026, 1, 2),
                    "event_timestamp_ny": "2026-01-02 10:00:00",
                    "market_session_tag": "regular",
                    "source": "Reuters",
                    "is_major_event": 0,
                    "symbol": "AAPL",
                    "sector": "Technology",
                    "positive_score": 0.8,
                    "neutral_score": 0.1,
                    "negative_score": 0.1,
                    "sentiment_confidence": 0.8,
                    "sentiment_net_score": 0.7,
                },
                {
                    "article_id": "a1",
                    "effective_trade_date": date(2026, 1, 2),
                    "event_timestamp_ny": "2026-01-02 10:30:00",
                    "market_session_tag": "regular",
                    "source": "Reuters",
                    "is_major_event": 0,
                    "symbol": "MSFT",
                    "sector": "Technology",
                    "positive_score": 0.7,
                    "neutral_score": 0.2,
                    "negative_score": 0.1,
                    "sentiment_confidence": 0.7,
                    "sentiment_net_score": 0.6,
                },
                {
                    "article_id": "a2",
                    "effective_trade_date": date(2026, 1, 5),
                    "event_timestamp_ny": "2026-01-05 10:00:00",
                    "market_session_tag": "regular",
                    "source": "Reuters",
                    "is_major_event": 1,
                    "symbol": "AAPL",
                    "sector": "Technology",
                    "positive_score": 0.9,
                    "neutral_score": 0.05,
                    "negative_score": 0.05,
                    "sentiment_confidence": 0.9,
                    "sentiment_net_score": 0.8,
                },
            ]
        )
        sector_df = ticker_df[[
            "article_id",
            "effective_trade_date",
            "event_timestamp_ny",
            "market_session_tag",
            "source",
            "is_major_event",
            "sector",
            "sentiment_confidence",
            "sentiment_net_score",
        ]].assign(sentiment_label="positive")
        macro_df = pd.DataFrame(
            [
                {
                    "article_id": "a2",
                    "trade_date": date(2026, 1, 5),
                    "sector": "Technology",
                    "macro_event_type": "monetary_policy",
                    "impact_direction": "positive",
                    "impact_score": 0.4,
                    "macro_event_intensity": 0.4,
                }
            ]
        )
        return ticker_df, sector_df, macro_df

    def upsert_ticker_daily_features(self, records):
        self.ticker_upserts.append(list(records))
        return len(records)

    def upsert_sector_daily_features(self, records):
        self.sector_upserts.append(list(records))
        return len(records)


def _build_service(repository: _FakeRepository, config: EventSentimentConfig) -> EventSentimentHistoryBackfillService:
    return EventSentimentHistoryBackfillService(repository=cast(Any, repository), config=config)


def test_history_backfill_resolve_bounds_uses_available_scored_dates() -> None:
    repository = _FakeRepository()
    service = _build_service(repository, EventSentimentConfig(bootstrap_default_years=10))

    start_date, end_date = service.resolve_bounds(end_date=date(2026, 1, 6), years=1)

    assert start_date == date(2026, 1, 2)
    assert end_date == date(2026, 1, 6)


def test_history_backfill_rebuilds_by_batches_and_filters_target_dates() -> None:
    repository = _FakeRepository()
    config = EventSentimentConfig(feature_history_buffer_days=20, bootstrap_batch_days=2)
    service = _build_service(repository, config)

    result = service.backfill(start_date=date(2026, 1, 2), end_date=date(2026, 1, 6), batch_days=2)

    assert result.trade_dates_processed == 3
    assert result.batches_processed == 2
    assert repository.feature_frame_calls[0]["start_date"] == date(2025, 12, 13)
    assert repository.feature_frame_calls[0]["end_date"] == date(2026, 1, 5)
    first_batch_dates = {row["trade_date"] for row in repository.ticker_upserts[0]}
    second_batch_dates = {row["trade_date"] for row in repository.ticker_upserts[1]}
    assert first_batch_dates == {date(2026, 1, 2), date(2026, 1, 5)}


def test_history_backfill_can_filter_ticker_scope_and_provider() -> None:
    repository = _FakeRepository()
    config = EventSentimentConfig(feature_history_buffer_days=20, bootstrap_batch_days=2)
    service = _build_service(repository, config)

    result = service.backfill(
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 6),
        batch_days=2,
        ingestion_source="eodhd",
        ticker_symbols=["AAPL"],
    )

    assert result.trade_dates_processed == 3
    assert repository.feature_frame_calls[0]["ingestion_source"] == "eodhd"
    assert repository.feature_frame_calls[0]["ticker_symbols"] == ["AAPL"]
    assert all(row["symbol"] == "AAPL" for batch in repository.ticker_upserts for row in batch)


def test_history_backfill_emits_phase_logs(caplog) -> None:
    repository = _FakeRepository()
    config = EventSentimentConfig(feature_history_buffer_days=20, bootstrap_batch_days=2)
    service = _build_service(repository, config)

    with caplog.at_level(logging.INFO):
        service.backfill(start_date=date(2026, 1, 2), end_date=date(2026, 1, 6), batch_days=2)

    messages = [record.getMessage() for record in caplog.records]
    assert any("Event sentiment history backfill started" in message for message in messages)
    assert any("history_backfill.resolve_bounds.scored_dates started" in message for message in messages)
    assert any("history_backfill.list_trade_dates completed" in message for message in messages)
    assert any("history_backfill.load_feature_frames result" in message for message in messages)
    assert any("history_backfill.aggregate_features completed" in message for message in messages)
    assert any("history_backfill.upsert_features completed" in message for message in messages)
    assert any("history_backfill.batch_completed" in message for message in messages)


def test_recent_mode_bounds_the_date_query_before_reading_history() -> None:
    class Repository(_FakeRepository):
        def __init__(self):
            super().__init__(); self.calls=[]
            self.scored_dates=[date(2016,1,1),date(2026,1,2),date(2026,1,5),date(2026,1,6),date(2026,1,12)]
        def list_scored_trade_dates(self,**kwargs):
            self.calls.append(kwargs);return super().list_scored_trade_dates(**kwargs)
    repo=Repository();service=_build_service(repo,EventSentimentConfig())
    assert service.resolve_bounds(end_date=date(2026,1,6),recent_days=2,ingestion_source='eodhd')==(date(2026,1,5),date(2026,1,6))
    assert repo.calls==[dict(start_date=date(2026,1,5),end_date=date(2026,1,6),ingestion_source='eodhd')]


def test_recent_mode_keeps_warmup_but_only_persists_target_dates() -> None:
    recent_repo=_FakeRepository();full_repo=_FakeRepository()
    recent=_build_service(recent_repo,EventSentimentConfig())
    full=_build_service(full_repo,EventSentimentConfig())
    recent.backfill(end_date=date(2026,1,6),recent_days=2,ticker_symbols=['AAPL'],ingestion_source='eodhd')
    full.backfill(start_date=date(2026,1,2),end_date=date(2026,1,6),ticker_symbols=['AAPL'],ingestion_source='eodhd')
    assert recent_repo.feature_frame_calls[0]['start_date']==date(2025,11,21)  # Jan 5 minus the unchanged 45-day buffer.
    targets={date(2026,1,5),date(2026,1,6)}
    got=[x for batch in recent_repo.ticker_upserts for x in batch]
    expected=[x for batch in full_repo.ticker_upserts for x in batch if x['trade_date'] in targets]
    pd.testing.assert_frame_equal(pd.DataFrame(got),pd.DataFrame(expected))
    assert all(x['trade_date'] in targets for x in got)
    assert all(x['trade_date'] in targets for batch in recent_repo.sector_upserts for x in batch)


@pytest.mark.parametrize('value',[0,-1,366,True])
def test_recent_window_rejects_invalid_lengths(value):
    from event_sentiment.history_backfill import _recent_window
    with pytest.raises(ValueError):_recent_window(value,date(2026,1,6))


def test_recent_window_is_inclusive_across_new_year():
    from event_sentiment.history_backfill import _recent_window
    assert _recent_window(7,date(2026,1,3))==(date(2025,12,28),date(2026,1,3))
    assert _recent_window(1,date(2026,1,3))==(date(2026,1,3),date(2026,1,3))


def test_unpinned_recent_window_uses_new_york_date_not_utc(monkeypatch):
    from datetime import datetime,timezone
    import event_sentiment.history_backfill as cli
    class Clock:
        @classmethod
        def now(cls,tz):return datetime(2026,1,7,2,0,tzinfo=timezone.utc)
    monkeypatch.setattr(cli,'datetime',Clock)
    assert cli._recent_window(7)==(date(2025,12,31),date(2026,1,6))


@pytest.mark.parametrize('kwargs',[dict(start_date=date(2026,1,2)),dict(years=1)])
def test_recent_mode_does_not_silently_override_historical_scope(kwargs):
    service=_build_service(_FakeRepository(),EventSentimentConfig())
    with pytest.raises(ValueError,match='cannot be combined'):service.resolve_bounds(recent_days=7,**kwargs)


def test_cli_recent_checkpoint_is_limited_to_actual_output_dates(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import event_sentiment.history_backfill as cli
    repo=MagicMock();repo.list_ticker_map_symbols.return_value=['AAPL'];calls=[]
    result=cli.EventSentimentHistoryBackfillResult(date(2026,1,5),date(2026,1,6),2,2,1,2,1)
    def backfill(**kwargs):calls.append(kwargs);return result
    monkeypatch.setattr(cli,'EventSentimentHistoryBackfillService',lambda:SimpleNamespace(repository=repo,backfill=backfill))
    monkeypatch.setattr(cli,'configure_root_logging',lambda **_:None)
    monkeypatch.setattr(cli,'_emit_run_summary',lambda _:None)
    assert cli.main(['--recent-days','2','--end-date','2026-01-06','--ingestion-source','eodhd'])==0
    assert calls[0]['recent_days']==2
    repo.list_ticker_map_symbols.assert_called_once_with(start_date=date(2026,1,5),end_date=date(2026,1,6),ingestion_source='eodhd',symbols=None)


@pytest.mark.parametrize('arguments',[
    ['--recent-days','7','--start-date','2025-01-01'],['--recent-days','7','--years','1'],['--recent-days','0']])
def test_cli_rejects_conflicting_or_unbounded_daily_scope_before_database(arguments):
    import event_sentiment.history_backfill as cli
    with pytest.raises(SystemExit) as exc:cli.main(arguments)
    assert exc.value.code==2


def test_recent_resume_compares_each_ticker_and_sector_without_skipping_holes():
    # A prior full build; one old hole and one stale value must still be fixed.
    initial = _FakeRepository()
    _build_service(initial, EventSentimentConfig()).backfill(
        end_date=date(2026, 1, 6), recent_days=21)
    ticker = pd.DataFrame(initial.ticker_upserts[0])
    sector = pd.DataFrame(initial.sector_upserts[0])
    ticker = ticker[~((ticker.symbol == 'MSFT') & (ticker.trade_date == date(2026, 1, 2)))].copy()
    ticker.loc[(ticker.symbol == 'AAPL') & (ticker.trade_date == date(2026, 1, 2)), 'news_count_1d'] = 99
    # SQL administrative fields are not business differences.
    ticker['updated_at'] = '2026-01-06T12:00:00'
    repo = _FakeRepository()
    calls = []
    def load_existing(start, end, **kwargs):
        calls.append((start, end, kwargs))
        return ticker, sector
    repo.load_existing_daily_features = load_existing
    result = _build_service(repo, EventSentimentConfig()).backfill(
        end_date=date(2026, 1, 6), recent_days=21, resume_features=True)
    assert result.ticker_rows_upserted == 2
    assert result.sector_rows_upserted == 0
    assert {(x['symbol'], x['trade_date']) for x in repo.ticker_upserts[0]} == {
        ('MSFT', date(2026, 1, 2)), ('AAPL', date(2026, 1, 2))}
    assert calls == [(date(2026, 1, 2), date(2026, 1, 6), {'ticker_symbols': None})]


def test_recent_resume_first_run_then_unchanged_run_keeps_warmup_and_writes_nothing(caplog):
    first = _FakeRepository()
    first.load_existing_daily_features = lambda *_args, **_kwargs: (pd.DataFrame(), pd.DataFrame())
    _build_service(first, EventSentimentConfig()).backfill(
        end_date=date(2026, 1, 6), recent_days=21, resume_features=True)
    second = _FakeRepository()
    second.load_existing_daily_features = lambda *_args, **_kwargs: (
        pd.DataFrame(first.ticker_upserts[0]), pd.DataFrame(first.sector_upserts[0]))
    with caplog.at_level(logging.INFO):
        result = _build_service(second, EventSentimentConfig()).backfill(
            end_date=date(2026, 1, 6), recent_days=21, resume_features=True)
    assert result.ticker_rows_upserted == result.sector_rows_upserted == 0
    assert second.feature_frame_calls == first.feature_frame_calls
    assert not any('completed with zero inserted rows' in r.message for r in caplog.records)


def test_pending_feature_rows_detects_version_nulls_dates_and_new_entities():
    from event_sentiment.history_backfill import _pending_feature_rows
    common = dict(trade_date=date(2026, 1, 5), latest_event_timestamp_ny=pd.Timestamp('2026-01-05 10:00'),
                  value=.3, nullable=None, feature_version='v2')
    new = pd.DataFrame([dict(symbol=s, **common) for s in ('A', 'B', 'C', 'D', 'E')])
    old = new[new.symbol != 'E'].copy()
    old.loc[old.symbol == 'A', 'value'] = .30000000000000004
    old.loc[old.symbol == 'B', 'feature_version'] = 'v1'
    old.loc[old.symbol == 'C', 'nullable'] = 1
    old.loc[old.symbol == 'D', 'latest_event_timestamp_ny'] = pd.NaT
    assert _pending_feature_rows(new, old, 'symbol').symbol.tolist() == ['B', 'C', 'D', 'E']


def test_fifty_two_calendar_days_recalculates_older_features_with_original_context():
    from event_sentiment.history_backfill import _recent_window
    assert _recent_window(52, date(2026, 10, 24)) == (date(2026, 9, 3), date(2026, 10, 24))
    class Repository(_FakeRepository):
        def __init__(self):
            super().__init__()
            self.scored_dates = [date(2026, 9, 2), date(2026, 9, 3), date(2026, 10, 24)]
        def load_feature_frames(self, **kwargs):
            ticker, sector, macro = super().load_feature_frames(**kwargs)
            mapping = {date(2026, 1, 2): date(2026, 9, 3), date(2026, 1, 5): date(2026, 10, 24)}
            ticker['effective_trade_date'] = ticker['effective_trade_date'].map(mapping)
            sector['effective_trade_date'] = sector['effective_trade_date'].map(mapping)
            macro['trade_date'] = macro['trade_date'].map(mapping)
            return ticker, sector, macro
        def load_existing_daily_features(self, *_args, **_kwargs):
            return pd.DataFrame(), pd.DataFrame()
    repo = Repository()
    result = _build_service(repo, EventSentimentConfig()).backfill(
        end_date=date(2026, 10, 24), recent_days=52, resume_features=True)
    assert result.start_date == date(2026, 9, 3) and result.end_date == date(2026, 10, 24)
    assert repo.feature_frame_calls[0]['start_date'] == date(2026, 7, 20)  # Additional read-only rolling warmup.
    assert {x['trade_date'] for x in repo.ticker_upserts[0]} == {date(2026, 9, 3), date(2026, 10, 24)}
    assert {x['trade_date'] for x in repo.sector_upserts[0]} == {date(2026, 9, 3), date(2026, 10, 24)}


def test_resume_features_requires_recent_window():
    service = _build_service(_FakeRepository(), EventSentimentConfig())
    with pytest.raises(ValueError, match='requires recent_days'):
        service.backfill(resume_features=True)


def test_cli_resume_features_forwards_flag_and_rejects_unbounded_resume(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import event_sentiment.history_backfill as cli
    repo = MagicMock(); repo.list_ticker_map_symbols.return_value = []
    calls = []
    result = cli.EventSentimentHistoryBackfillResult(date(2026, 1, 5), date(2026, 1, 6), 2, 2, 1, 0, 0)
    def backfill(**kwargs):
        calls.append(kwargs)
        return result
    monkeypatch.setattr(cli, 'EventSentimentHistoryBackfillService', lambda: SimpleNamespace(repository=repo, backfill=backfill))
    monkeypatch.setattr(cli, 'configure_root_logging', lambda **_: None)
    monkeypatch.setattr(cli, '_emit_run_summary', lambda _: None)
    assert cli.main(['--recent-days', '21', '--resume-features']) == 0
    assert calls[0]['recent_days'] == 21 and calls[0]['resume_features'] is True
    with pytest.raises(SystemExit) as exc:
        cli.main(['--resume-features'])
    assert exc.value.code == 2


