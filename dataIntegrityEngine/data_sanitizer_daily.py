import gc
import logging
import math
from datetime import date, timedelta
from typing import Optional

import pytz
import polars as pl
from dateutil import parser as dtparser

from sqlalchemy import MetaData, Table
from sqlalchemy.engine import Engine, Connection

from database.connection import get_sqlalchemy_engine
from service.alpaca.client import fetch_bars
from database.bar_metadata import TimeFrame
from database.sanitizer_db_ops import (
    get_last_sync_date,
    get_prev_close_before,
    get_symbols,
    upsert_audit,
    upsert_stock_bars_daily,
)


LOGGER = logging.getLogger(__name__)
SPY_SYMBOL = "SPY"
SPY_FETCH_PADDING_DAYS = 10
ROLLING_WINDOW_DAYS = 20
ROLLING_MIN_PERIODS = 5
ANOMALY_MAD_THRESHOLD = 5.0
ANOMALY_RETURN_THRESHOLD = 0.02
DEFAULT_COMMIT_EVERY = 50
EMPTY_BAR_FRAME = pl.DataFrame(
    {
        "date": [],
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": [],
        "adj_close": [],
        "vwap": [],
        "is_filled": [],
    }
)


class DataSanitizer:
    """
    Pipeline de nettoyage et d'alignement des données Daily (RTH) avec Polars, et upsert MySQL via SQLAlchemy.
    - Forward-fill des jours manquants (volume=0, is_filled=True) basé sur le calendrier SPY
    - Détection d'anomalies via Rolling MAD (fenêtre 20, seuil 5*MAD et |ret|>2%)
    - Calcul des features: daily_return (persisté), Parkinson, Overnight Gap, RVOL20 (calculés mais non persistés ici)
    - Incrémental via cleaning_audit_log.last_sync_date
    """

    def __init__(self,
                 db_user_env: str = 'LOGIN_DB',
                 db_pass_env: str = 'PASSWORD_DB',
                 db_host: str = 'localhost',
                 db_name: str = 'alpha_trade',
                 log_level: int = logging.INFO):
        logging.basicConfig(level=log_level,
                            format='%(asctime)s %(levelname)s %(message)s')
        self.engine: Engine = get_sqlalchemy_engine(
            db_host=db_host,
            db_name=db_name,
            db_user_env=db_user_env,
            db_password_env=db_pass_env,
        )
        self.tz_ny = pytz.timezone('America/New_York')
        self.metadata = MetaData()
        self._reflect_tables()
        self._spy_calendar_cache: Optional[pl.DataFrame] = None

    def _reflect_tables(self) -> None:
        self.stock_bars_daily = Table('stock_bars_daily', self.metadata, autoload_with=self.engine)
        self.cleaning_audit_log = Table('cleaning_audit_log', self.metadata, autoload_with=self.engine)
        self.stock_metadata = Table('stock_metadata', self.metadata, autoload_with=self.engine)

    @staticmethod
    def _empty_bar_frame() -> pl.DataFrame:
        return EMPTY_BAR_FRAME.clone()

    @staticmethod
    def _slice_cached_calendar(calendar: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
        return calendar.filter((pl.col('date') >= pl.lit(start)) & (pl.col('date') <= pl.lit(end)))

    @staticmethod
    def _covers_date_range(calendar: pl.DataFrame, start: date, end: date) -> bool:
        if calendar.is_empty():
            return False
        return (calendar['date'].min() <= start) and (calendar['date'].max() >= end)

    def _fetch_calendar_dates(self, start: Optional[date]) -> list[date]:
        start_str = start.isoformat() if start else None
        bars = fetch_bars(SPY_SYMBOL, TimeFrame.ONE_DAY.api_value, start_str)
        return [self._to_ny_date(bar['t']) for bar in bars]

    def _build_symbol_frame(self, bars: list[dict]) -> pl.DataFrame:
        if not bars:
            return self._empty_bar_frame()

        return pl.DataFrame(
            {
                'date': [self._to_ny_date(bar['t']) for bar in bars],
                'open': [bar['o'] for bar in bars],
                'high': [bar['h'] for bar in bars],
                'low': [bar['l'] for bar in bars],
                'close': [bar['c'] for bar in bars],
                'volume': [bar['v'] for bar in bars],
                'adj_close': [bar.get('c') for bar in bars],
                'vwap': [bar.get('vw') for bar in bars],
                'is_filled': [False] * len(bars),
            }
        ).sort('date').unique(subset=['date'], keep='last')

    @staticmethod
    def _build_audit_payload(last_sync: Optional[date], missing_days: int, anomaly_count: int, status: str, error_msg: Optional[str]) -> dict:
        return {
            'last_sync': last_sync,
            'missing_days': missing_days,
            'anomaly_count': anomaly_count,
            'status': status,
            'error_msg': error_msg,
        }

    @staticmethod
    def _last_frame_date(df: pl.DataFrame) -> Optional[date]:
        if df.is_empty():
            return None
        return df['date'][-1]

    @staticmethod
    def _should_commit(processed_count: int, commit_every: int) -> bool:
        return processed_count > 0 and processed_count % commit_every == 0

    def _commit_batch(self, transaction, conn: Connection):
        transaction.commit()
        gc.collect()
        return conn.begin()

    def _process_symbol(self, conn: Connection, symbol: str) -> tuple[bool, dict]:
        last_sync = get_last_sync_date(conn, self.cleaning_audit_log, symbol)
        start_date = (last_sync + timedelta(days=1)) if last_sync else None
        df_raw = self.fetch_symbol_bars_1d(symbol, start_date)

        if df_raw.is_empty():
            LOGGER.info("Aucune donnée pour %s après %s", symbol, start_date)
            return False, self._build_audit_payload(last_sync, 0, 0, 'success', None)

        window_start = df_raw['date'][0]
        window_end = df_raw['date'][-1]
        calendar = self.load_spy_calendar(window_start, window_end)
        prev_close = get_prev_close_before(conn, self.stock_bars_daily, symbol, window_start)
        df_aligned, missing_count = self.sanitize_and_align(df_raw, calendar, prev_close)
        df_features, anomaly_count = self.detect_anomalies(df_aligned)

        upsert_stock_bars_daily(conn, self.stock_bars_daily, symbol, df_features)
        return True, self._build_audit_payload(
            self._last_frame_date(df_features) or last_sync,
            missing_count,
            anomaly_count,
            'success',
            None,
        )

    # ---------- Calendrier SPY ----------
    def _to_ny_date(self, ts_str: str) -> date:
        dt_utc = dtparser.isoparse(ts_str)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
        dt_ny = dt_utc.astimezone(self.tz_ny)
        return dt_ny.date()

    def load_spy_calendar(self, start: date, end: date) -> pl.DataFrame:
        """Construit le calendrier RTH via SPY pour [start, end]. Mis en cache au sein de l'instance."""
        if self._spy_calendar_cache is not None:
            if self._covers_date_range(self._spy_calendar_cache, start, end):
                return self._slice_cached_calendar(self._spy_calendar_cache, start, end)

        fetch_start = start - timedelta(days=SPY_FETCH_PADDING_DAYS)
        dates = self._fetch_calendar_dates(fetch_start)
        if not dates or max(dates) < end or min(dates) > start:
            dates = self._fetch_calendar_dates(None)

        cal_df = pl.DataFrame({'date': sorted([d for d in dates if start <= d <= end])})
        self._spy_calendar_cache = cal_df
        return cal_df

    # ---------- Fetch Alpaca 1D ----------
    def fetch_symbol_bars_1d(self, symbol: str, start: Optional[date]) -> pl.DataFrame:
        start_str = start.isoformat() if start else None
        bars = fetch_bars(symbol, TimeFrame.ONE_DAY.api_value, start_str)
        return self._build_symbol_frame(bars)

    # ---------- Alignement & features ----------
    def sanitize_and_align(self, df: pl.DataFrame, calendar: pl.DataFrame, prev_close: Optional[float]) -> tuple[pl.DataFrame, int]:
        """Retourne df aligné sur le calendrier avec forward-fill; renvoie aussi le nombre de jours remplis."""
        if df.is_empty():
            return df, 0

        base = calendar.join(df, on='date', how='left')
        base = base.with_columns([
            pl.col('close').is_null().alias('orig_missing')
        ])

        tmp = base.with_columns([
            pl.col('close').forward_fill().alias('close')
        ])
        tmp = tmp.with_columns([
            pl.when(pl.col('open').is_null()).then(pl.col('close')).otherwise(pl.col('open')).alias('open'),
            pl.when(pl.col('high').is_null()).then(pl.col('close')).otherwise(pl.col('high')).alias('high'),
            pl.when(pl.col('low').is_null()).then(pl.col('close')).otherwise(pl.col('low')).alias('low'),
            pl.when(pl.col('adj_close').is_null()).then(pl.col('close')).otherwise(pl.col('adj_close')).alias('adj_close'),
        ])
        tmp = tmp.with_columns([
            pl.when(pl.col('orig_missing')).then(pl.lit(0)).otherwise(pl.col('volume').fill_null(0)).alias('volume'),
            pl.col('vwap')
        ])

        tmp = tmp.with_columns([
            pl.col('orig_missing').alias('is_filled')
        ])

        prevc = pl.col('close').shift(1)
        if prev_close is not None:
            prevc = prevc.fill_null(prev_close)
        tmp = tmp.with_columns([
            prevc.alias('prev_close')
        ])
        tmp = tmp.with_columns([
            ((pl.col('close') / pl.col('prev_close')) - 1.0).alias('daily_return')
        ])

        ln2 = math.log(2.0)
        parkinson = ((pl.col('high') / pl.col('low')).log().abs() / (4 * ln2)).sqrt().alias('parkinson_vol')
        overnight_gap = ((pl.col('open') / pl.col('prev_close')) - 1.0).alias('overnight_gap')
        rvol20 = (pl.col('volume') / pl.col('volume').rolling_mean(window_size=20, min_samples=1).shift(1)).alias('rvol20')
        tmp = tmp.with_columns([parkinson, overnight_gap, rvol20])

        tmp = tmp.drop(['prev_close'])
        filled_count = int(tmp['is_filled'].sum())
        return tmp, filled_count

    def detect_anomalies(self, df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
        if df.is_empty():
            return df, 0

        med = pl.col('daily_return').rolling_median(window_size=ROLLING_WINDOW_DAYS, min_samples=ROLLING_MIN_PERIODS).alias('ret_med')
        df2 = df.with_columns([med])
        df2 = df2.with_columns([
            (pl.col('daily_return') - pl.col('ret_med')).abs().alias('abs_dev')
        ])
        df2 = df2.with_columns([
            pl.col('abs_dev').rolling_median(window_size=ROLLING_WINDOW_DAYS, min_samples=ROLLING_MIN_PERIODS).alias('mad')
        ])
        is_anom = (
            ((pl.col('abs_dev') > ANOMALY_MAD_THRESHOLD * pl.col('mad')) & (pl.col('daily_return').abs() > ANOMALY_RETURN_THRESHOLD))
            .fill_null(False)
            .alias('is_anomaly')
        )
        df2 = df2.with_columns([is_anom])
        count = int(df2['is_anomaly'].sum())
        return df2.drop(['ret_med', 'abs_dev', 'mad']), count

    # ---------- Orchestration ----------

    def run_pipeline(self, symbols: Optional[list[str]] = None, commit_every: int = DEFAULT_COMMIT_EVERY) -> None:
        if commit_every < 1:
            raise ValueError('commit_every doit être supérieur ou égal à 1.')

        processed = 0
        with self.engine.connect() as conn:
            outer_trans = conn.begin()
            try:
                if symbols is None:
                    symbols = get_symbols(conn, self.stock_metadata)

                for idx, symbol in enumerate(symbols, 1):
                    LOGGER.info("Traitement %s/%s: %s", idx, len(symbols), symbol)
                    try:
                        was_processed, audit_payload = self._process_symbol(conn, symbol)
                        upsert_audit(conn, self.cleaning_audit_log, symbol, **audit_payload)
                        if was_processed:
                            processed += 1
                    except Exception as e:
                        LOGGER.exception("Echec traitement %s", symbol)
                        fallback_last_sync = get_last_sync_date(conn, self.cleaning_audit_log, symbol)
                        upsert_audit(
                            conn,
                            self.cleaning_audit_log,
                            symbol,
                            **self._build_audit_payload(fallback_last_sync, 0, 0, 'failed', str(e)),
                        )

                    if self._should_commit(processed, commit_every):
                        outer_trans = self._commit_batch(outer_trans, conn)

                outer_trans.commit()
            finally:
                gc.collect()


def main() -> None:
    sanitizer = DataSanitizer()
    sanitizer.run_pipeline(commit_every=DEFAULT_COMMIT_EVERY)


if __name__ == '__main__':
    main()

