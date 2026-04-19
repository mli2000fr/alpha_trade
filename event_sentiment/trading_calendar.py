import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pytz

LOGGER = logging.getLogger(__name__)
TZ_UTC = pytz.UTC
TZ_NY = pytz.timezone("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


@dataclass(frozen=True, slots=True)
class TemporalAlignmentResult:
    event_timestamp_utc: datetime
    event_timestamp_ny: datetime
    effective_trade_date: date
    market_session_tag: str


class TradingCalendarAligner:
    def __init__(self, regular_session_maps_to_same_day: bool = False) -> None:
        self.regular_session_maps_to_same_day = regular_session_maps_to_same_day
        self._calendar = self._load_calendar()

    @staticmethod
    def _load_calendar():
        try:
            import pandas_market_calendars as mcal

            return mcal.get_calendar("NYSE")
        except Exception:
            LOGGER.warning(
                "pandas_market_calendars indisponible: fallback weekday-only active, precision calendrier reduite."
            )
            return None

    def _is_trading_day(self, value: date) -> bool:
        if self._calendar is None:
            return value.weekday() < 5
        return not self._calendar.schedule(start_date=value, end_date=value).empty

    def _next_trading_day(self, value: date) -> date:
        probe = value
        if self._calendar is None:
            while probe.weekday() >= 5:
                probe += timedelta(days=1)
            return probe

        valid = self._calendar.valid_days(start_date=probe, end_date=probe + timedelta(days=14))
        if len(valid) == 0:
            raise RuntimeError(f"Aucune prochaine séance NYSE trouvée après {value}.")
        first_valid = valid[0]
        # pandas_market_calendars retourne des Timestamps tz-aware à minuit UTC.
        # Un tz_convert(TZ_NY) ferait reculer la date civile d'un jour (ex: 2026-01-06 00:00Z
        # -> 2026-01-05 19:00-05:00), ce qui casse l'alignement métier attendu.
        # Ici on veut la DATE DE SÉANCE NYSE, donc on prend directement la date civile.
        if hasattr(first_valid, "to_pydatetime"):
            return first_valid.to_pydatetime().date()
        return date(first_valid.year, first_valid.month, first_valid.day)

    def align(self, published_at_utc: datetime) -> TemporalAlignmentResult:
        if published_at_utc.tzinfo is None:
            published_at_utc = TZ_UTC.localize(published_at_utc)
        event_utc = published_at_utc.astimezone(TZ_UTC)
        event_ny = event_utc.astimezone(TZ_NY)

        local_date = event_ny.date()
        local_time = event_ny.time()

        if not self._is_trading_day(local_date):
            return TemporalAlignmentResult(
                event_timestamp_utc=event_utc,
                event_timestamp_ny=event_ny,
                effective_trade_date=self._next_trading_day(local_date + timedelta(days=1)),
                market_session_tag="non_trading_day",
            )

        if local_time < MARKET_OPEN:
            effective_trade_date = local_date
            tag = "pre_market"
        elif local_time < MARKET_CLOSE:
            tag = "regular"
            effective_trade_date = (
                local_date
                if self.regular_session_maps_to_same_day
                else self._next_trading_day(local_date + timedelta(days=1))
            )
        else:
            effective_trade_date = self._next_trading_day(local_date + timedelta(days=1))
            tag = "post_market"

        return TemporalAlignmentResult(
            event_timestamp_utc=event_utc,
            event_timestamp_ny=event_ny,
            effective_trade_date=effective_trade_date,
            market_session_tag=tag,
        )

