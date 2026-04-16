from datetime import datetime
import pytz
from event_sentiment.trading_calendar import TradingCalendarAligner
def test_pre_market_maps_to_same_trade_date() -> None:
    aligner = TradingCalendarAligner()
    ts = datetime(2026, 1, 5, 13, 0, tzinfo=pytz.UTC)
    result = aligner.align(ts)
    assert result.market_session_tag == "pre_market"
    assert str(result.effective_trade_date) == "2026-01-05"
def test_regular_session_maps_to_next_trade_date() -> None:
    aligner = TradingCalendarAligner()
    ts = datetime(2026, 1, 5, 16, 0, tzinfo=pytz.UTC)
    result = aligner.align(ts)
    assert result.market_session_tag == "regular"
    assert str(result.effective_trade_date) == "2026-01-06"
def test_weekend_maps_to_next_trade_date() -> None:
    aligner = TradingCalendarAligner()
    ts = datetime(2026, 1, 10, 15, 0, tzinfo=pytz.UTC)
    result = aligner.align(ts)
    assert result.market_session_tag == "non_trading_day"
    assert str(result.effective_trade_date) == "2026-01-12"
