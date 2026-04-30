import gc
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import pytz
import polars as pl
from dateutil import parser as dtparser

from sqlalchemy import MetaData, Table
from sqlalchemy.engine import Engine, Connection

from common.utils import configure_root_logging
from common.market_calendar import nyse_session_dates
from database.connection import get_sqlalchemy_engine
from database.bar_metadata import TimeFrame
from database.sanitizer_db_ops import (
    get_failed_audits,
    get_last_actual_daily_date,
    get_stock_bars,
    get_last_sync_date,
    get_prev_close_before,
    get_symbols,
    sync_audit_to_stock_scores,
    upsert_audit,
    upsert_stock_bars_daily,
)


LOGGER = logging.getLogger(__name__)
SPY_SYMBOL = "SPY"
SPY_FETCH_PADDING_DAYS = 10
REBUILD_LOOKBACK_CALENDAR_DAYS = 400
ROLLING_WINDOW_DAYS = 20
ROLLING_MIN_PERIODS = 5
ANOMALY_MAD_THRESHOLD = 5.0
ANOMALY_RETURN_THRESHOLD = 0.02
DEFAULT_COMMIT_EVERY = 50
MAX_CONSECUTIVE_FILLED_DAYS = 3
DATA_ADJUSTMENT = "split"
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
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


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f'{prefix}-{_utc_now_naive().strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:6]}'


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


class DataQualityError(RuntimeError):
    """Erreur de qualité bloquante sur une série daily nettoyée."""


class DataSanitizer:
    """
    Pipeline de nettoyage et d'alignement des données Daily (RTH) avec Polars, et upsert MySQL via SQLAlchemy.
    - Forward-fill des jours manquants (volume=0, is_filled=True) basé sur le calendrier SPY
    - Détection d'anomalies via Rolling MAD (fenêtre 20, seuil 5*MAD et |ret|>2%)
    - Calcul et persistance de `daily_return` uniquement (les autres features restent recalculées à l'aval)
    - Incrémental via cleaning_audit_latest.last_sync_date
    - Résumé run-level (run_id, volumes traités, succès/échecs/skips, lignes upsertées)
    """

    def __init__(self,
                 engine: Engine | None = None,
                 db_user_env: str = 'LOGIN_DB',
                 db_pass_env: str = 'PASSWORD_DB',
                 db_host: str = 'localhost',
                 db_name: str = 'alpha_trade'):
        # NOTE: La configuration du logging appartient au point d'entrée (main()).
        # Ne pas appeler logging.basicConfig() ici pour ne pas écraser la config appelante.
        if engine is not None:
            self.engine: Engine = engine
        else:
            self.engine = get_sqlalchemy_engine(
                db_host=db_host,
                db_name=db_name,
                db_user_env=db_user_env,
                db_password_env=db_pass_env,
            )
        self.tz_ny = pytz.timezone('America/New_York')
        # Les tables sont réfléchies paresseusement au premier appel à run_pipeline().
        # Cela évite un overhead DDL (autoload_with) à chaque instanciation.
        self._db_metadata = MetaData()
        self._tables_reflected: bool = False
        self._spy_calendar_cache: Optional[pl.DataFrame] = None

    def _ensure_tables_reflected(self) -> None:
        """Réflexion DDL paresseuse : exécutée une seule fois par instance."""
        if self._tables_reflected:
            return
        self._reflect_tables()
        self._tables_reflected = True

    def _reflect_tables(self) -> None:
        self.stock_bars = Table('stock_bars', self._db_metadata, autoload_with=self.engine)
        self.stock_bars_daily = Table('stock_bars_daily', self._db_metadata, autoload_with=self.engine)
        self.cleaning_audit_latest = Table('cleaning_audit_latest', self._db_metadata, autoload_with=self.engine)
        self.cleaning_audit_runs = Table('cleaning_audit_runs', self._db_metadata, autoload_with=self.engine)
        self.stock_metadata = Table('stock_metadata', self._db_metadata, autoload_with=self.engine)
        self.stock_scores = Table('stock_scores', self._db_metadata, autoload_with=self.engine)

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

    def _ensure_spy_1d_available(self, conn: Connection) -> None:
        """Conservé pour compatibilité ascendante.

        Depuis le découplage du calendrier (Phase 3.1.b), le calendrier de
        sessions NYSE est fourni par ``common.market_calendar.nyse_session_dates``
        (``pandas_market_calendars``). SPY n'est plus consulté pour la
        construction du calendrier ; cette méthode devient un no-op explicite.
        Elle reste appelée par ``run_pipeline`` pour préserver les hooks de tests
        existants et permettre une éventuelle ré-activation locale.
        """
        return None

    def _fetch_calendar_dates_from_spy(self, conn: Connection, start: Optional[date]) -> list[date]:
        """Fallback historique : reconstruit le calendrier depuis SPY (stock_bars 1D).

        Utilisé uniquement si ``nyse_session_dates`` ne retourne rien (cas
        extrême : dépendance pmc absente *et* fenêtre d'historique antérieure à
        l'energie weekday-only). Préserve la robustesse du pipeline.
        """
        bars = get_stock_bars(conn, self.stock_bars, SPY_SYMBOL, TimeFrame.ONE_DAY.db_value, start)
        return [self._to_ny_date(bar['t']) for bar in bars]


    def _build_symbol_frame(self, bars: list[dict]) -> pl.DataFrame:
        if not bars:
            return self._empty_bar_frame()

        # Note sur adj_close : l'API Alpaca est appelée avec adjustment="split",
        # ce qui signifie que les champs OHLCV retournés (bar['c']) sont déjà
        # ajustés des splits. Par conséquent,
        #   close     = prix split-adjusted (utilisé pour les calculs de rendements)
        #   adj_close = identique à close (convention maintenue pour compatibilité schema)
        # Si un prix RAW ou total-return est nécessaire ultérieurement, il faudra
        # l'ingérer explicitement dans une autre série/version, pas ici.
        return pl.DataFrame(
            {
                'date': [self._to_ny_date(bar['t']) for bar in bars],
                'open': [bar['o'] for bar in bars],
                'high': [bar['h'] for bar in bars],
                'low': [bar['l'] for bar in bars],
                'close': [bar['c'] for bar in bars],
                'volume': [bar['v'] for bar in bars],
                'adj_close': [bar['c'] for bar in bars],  # = close car adjustment=split
                'vwap': [bar.get('vw') for bar in bars],
                'is_filled': [False] * len(bars),
            }
        ).sort('date').unique(subset=['date'], keep='last')

    @staticmethod
    def _build_audit_payload(
        last_sync: Optional[date],
        missing_days: Optional[int],
        anomaly_count: Optional[int],
        status: str,
        error_message: Optional[str] = None,
    ) -> dict:
        return {
            'last_sync': last_sync,
            'missing_days': missing_days,
            'anomaly_count': anomaly_count,
            'status': status,
            'error_message': error_message,
        }

    @staticmethod
    def _compute_fill_streaks(missing_flags: list[bool]) -> list[int]:
        streaks: list[int] = []
        current = 0
        for is_missing in missing_flags:
            if is_missing:
                current += 1
            else:
                current = 0
            streaks.append(current)
        return streaks

    @staticmethod
    def _compute_rebuild_start_date(last_sync: Optional[date]) -> Optional[date]:
        if last_sync is None:
            return None
        return last_sync - timedelta(days=REBUILD_LOOKBACK_CALENDAR_DAYS)

    @staticmethod
    def _compute_resume_anchor(*dates: Optional[date]) -> Optional[date]:
        candidates = [value for value in dates if value is not None]
        if not candidates:
            return None
        return max(candidates)

    @staticmethod
    def _last_frame_date(df: pl.DataFrame) -> Optional[date]:
        if df.is_empty():
            return None
        return df['date'][-1]

    @staticmethod
    def _should_commit(processed_count: int, commit_every: int) -> bool:
        return processed_count > 0 and processed_count % commit_every == 0

    @staticmethod
    def _format_exception_message(exc: Exception) -> str:
        orig = getattr(exc, 'orig', None)
        if orig is not None:
            orig_message = str(orig).strip()
            if orig_message:
                return f'{exc.__class__.__name__}: {orig_message}'
        message = str(exc).strip()
        if message:
            return f'{exc.__class__.__name__}: {message}'
        return exc.__class__.__name__

    def _commit_batch(self, transaction, conn: Connection):
        transaction.commit()
        gc.collect()
        return conn.begin()

    def _log_failed_audit_summary(self, conn: Connection, limit: int = 20) -> None:
        failed_audits = get_failed_audits(conn, self.cleaning_audit_latest, limit=limit)
        if not failed_audits:
            LOGGER.info('Aucun audit en echec detecte dans cleaning_audit_latest.')
            return

        LOGGER.warning(
            'Audits en echec detectes dans cleaning_audit_latest | count=%s limit=%s',
            len(failed_audits),
            limit,
        )
        for audit in failed_audits:
            LOGGER.error(
                'Audit failed summary | symbol=%s latest_run_at=%s last_sync=%s error=%s',
                audit.get('symbol'),
                audit.get('latest_run_at'),
                audit.get('last_sync_date'),
                audit.get('error_message'),
            )

    def _process_symbol(self, conn: Connection, symbol: str) -> tuple[bool, dict, int]:
        last_sync = get_last_sync_date(conn, self.cleaning_audit_latest, symbol)
        last_daily_date = get_last_actual_daily_date(conn, self.stock_bars_daily, symbol)
        resume_anchor = self._compute_resume_anchor(last_sync, last_daily_date)
        rebuild_start = self._compute_rebuild_start_date(resume_anchor)
        df_raw = self.fetch_symbol_bars_1d(conn, symbol, rebuild_start)

        if df_raw.is_empty():
            LOGGER.info("Aucune donnee brute pour %s a partir de %s", symbol, rebuild_start)
            return False, self._build_audit_payload(last_sync, None, None, 'success'), 0

        window_start = df_raw['date'][0]
        window_end = df_raw['date'][-1]
        calendar = self.load_spy_calendar(conn, window_start, window_end)
        prev_close = get_prev_close_before(conn, self.stock_bars_daily, symbol, window_start)
        df_aligned, missing_count = self.sanitize_and_align(df_raw, calendar, prev_close)
        df_features, anomaly_count = self.detect_anomalies(df_aligned)

        rows_upserted = upsert_stock_bars_daily(conn, self.stock_bars_daily, symbol, df_features, data_adjustment=DATA_ADJUSTMENT)
        return True, self._build_audit_payload(
            self._last_frame_date(df_features) or resume_anchor,
            missing_count,
            anomaly_count,
            'success',
        ), rows_upserted

    # ---------- Calendrier SPY ----------
    def _to_ny_date(self, ts_value: date | datetime | str) -> date:
        if isinstance(ts_value, date) and not isinstance(ts_value, datetime):
            return ts_value

        dt_value = ts_value if isinstance(ts_value, datetime) else dtparser.isoparse(ts_value)
        if dt_value.tzinfo is None:
            dt_ny = self.tz_ny.localize(dt_value)
        else:
            dt_ny = dt_value.astimezone(self.tz_ny)
        return dt_ny.date()

    def load_spy_calendar(self, conn: Connection, start: date, end: date) -> pl.DataFrame:
        """Construit le calendrier de sessions NYSE pour ``[start, end]``.

        - Source primaire : ``common.market_calendar.nyse_session_dates``
          (``pandas_market_calendars``), totalement indépendant de SPY.
        - Fallback : reconstruction depuis SPY/stock_bars (legacy) si pmc et le
          fallback weekday-only ne donnent rien.
        - Cache à l'instance pour éviter les recomputes inter-symboles.

        Le nom historique ``load_spy_calendar`` est conservé pour ne pas casser
        les appelants ; le contenu n'a plus de dépendance directe à SPY.
        """
        if self._spy_calendar_cache is not None:
            if self._covers_date_range(self._spy_calendar_cache, start, end):
                return self._slice_cached_calendar(self._spy_calendar_cache, start, end)

        dates = nyse_session_dates(start, end)
        if not dates:
            # Fallback ultime : la table SPY locale.
            LOGGER.warning(
                "Calendrier NYSE vide via pandas_market_calendars sur [%s, %s] | bascule sur SPY/stock_bars.",
                start, end,
            )
            fetch_start = start - timedelta(days=SPY_FETCH_PADDING_DAYS)
            spy_dates = self._fetch_calendar_dates_from_spy(conn, fetch_start)
            if not spy_dates or max(spy_dates) < end or min(spy_dates) > start:
                spy_dates = self._fetch_calendar_dates_from_spy(conn, None)
            dates = sorted([d for d in spy_dates if start <= d <= end])

        cal_df = pl.DataFrame({
            'date': pl.Series('date', dates, dtype=pl.Date),
        })
        self._spy_calendar_cache = cal_df
        return cal_df

    # ---------- Fetch DB 1D ----------
    def fetch_symbol_bars_1d(self, conn: Connection, symbol: str, start: Optional[date]) -> pl.DataFrame:
        bars = get_stock_bars(conn, self.stock_bars, symbol, TimeFrame.ONE_DAY.db_value, start)
        return self._build_symbol_frame(bars)

    # ---------- Alignement & features ----------
    def sanitize_and_align(self, df: pl.DataFrame, calendar: pl.DataFrame, prev_close: Optional[float]) -> tuple[pl.DataFrame, int]:
        """Retourne df aligné sur le calendrier avec forward-fill; renvoie aussi le nombre de jours remplis."""
        if df.is_empty():
            return df, 0
        if calendar.is_empty():
            start = df['date'][0]
            end = df['date'][-1]
            raise RuntimeError(
                f'Calendrier NYSE introuvable pour la plage {start} -> {end}. '
                'Verifier l\'installation de pandas_market_calendars (et, en dernier recours, '
                'que SPY est bien importe dans stock_bars en 1D).'
            )

        base = calendar.join(df, on='date', how='left')
        base = base.with_columns([
            pl.col('close').is_null().alias('orig_missing')
        ])
        missing_flags = [bool(flag) for flag in base['orig_missing'].to_list()]
        fill_streaks = self._compute_fill_streaks(missing_flags)

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
        tmp = tmp.with_columns([
            pl.Series('fill_streak', fill_streaks, dtype=pl.Int64)
        ])

        prevc = pl.col('close').shift(1)
        if prev_close is not None:
            prevc = prevc.fill_null(prev_close)
        tmp = tmp.with_columns([
            prevc.alias('prev_close')
        ])
        daily_return = (
            pl.when(pl.col('prev_close').is_null() | (pl.col('prev_close') <= 0))
            .then(pl.lit(None, dtype=pl.Float64))
            .otherwise((pl.col('close') / pl.col('prev_close')) - 1.0)
            .alias('daily_return')
        )
        tmp = tmp.with_columns([
            daily_return
        ])


        tmp = tmp.drop(['prev_close'])
        filled_count = int(tmp['is_filled'].sum())
        max_fill_streak = max(fill_streaks, default=0)
        if max_fill_streak > MAX_CONSECUTIVE_FILLED_DAYS:
            bad_index = next(index for index, streak in enumerate(fill_streaks) if streak > MAX_CONSECUTIVE_FILLED_DAYS)
            bad_date = tmp['date'][bad_index]
            raise DataQualityError(
                f'Serie degradee: fill streak={max_fill_streak} > {MAX_CONSECUTIVE_FILLED_DAYS} pour la date {bad_date}.'
            )
        tmp = tmp.drop(['fill_streak'])
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

    def run_pipeline(self, symbols: Optional[list[str]] = None, commit_every: int = DEFAULT_COMMIT_EVERY) -> dict[str, object]:
        if commit_every < 1:
            raise ValueError('commit_every doit être supérieur ou égal à 1.')

        self._ensure_tables_reflected()
        with self.engine.connect() as bootstrap_conn:
            self._ensure_spy_1d_available(bootstrap_conn)

        started_at = _utc_now_naive()
        summary: dict[str, object] = {
            'run_id': _build_run_id('sanitize-daily'),
            'started_at': started_at.isoformat(timespec='seconds'),
            'finished_at': None,
            'duration_seconds': 0.0,
            'targeted_symbols': 0,
            'successful_symbols': 0,
            'failed_symbols': 0,
            'skipped_symbols': 0,
            'degraded_symbols': 0,
            'upserted_rows': 0,
            'audit_rows_written': 0,
            'batch_commits': 0,
            'status_breakdown': {
                'success': 0,
                'failed': 0,
                'skipped': 0,
            },
        }

        processed = 0
        with self.engine.connect() as conn:
            outer_trans = conn.begin()
            try:
                if symbols is None:
                    symbols = get_symbols(conn, self.stock_metadata)
                summary['targeted_symbols'] = len(symbols)
                LOGGER.info(
                    'Demarrage sanitizeur daily | run_id=%s targeted_symbols=%s commit_every=%s adjustment=%s',
                    summary['run_id'],
                    summary['targeted_symbols'],
                    commit_every,
                    DATA_ADJUSTMENT,
                )

                for idx, symbol in enumerate(symbols, 1):
                    LOGGER.info("Traitement %s/%s: %s", idx, len(symbols), symbol)
                    try:
                        was_processed, audit_payload, rows_upserted = self._process_symbol(conn, symbol)
                        upsert_audit(
                            conn,
                            self.cleaning_audit_latest,
                            self.cleaning_audit_runs,
                            symbol,
                            **audit_payload,
                        )
                        summary['audit_rows_written'] = int(summary['audit_rows_written']) + 1
                        # sync_audit_to_stock_scores uniquement si de nouvelles barres ont été traitées.
                        # Si was_processed=False (aucune nouvelle barre), on conserve les valeurs
                        # existantes dans stock_scores pour ne pas écraser avec 0.
                        if was_processed:
                            sync_audit_to_stock_scores(
                                conn,
                                self.stock_scores,
                                symbol,
                                audit_payload['missing_days'],
                                audit_payload['anomaly_count'],
                                audit_payload['status'],
                            )
                        if was_processed:
                            processed += 1
                            summary['successful_symbols'] = int(summary['successful_symbols']) + 1
                            summary['upserted_rows'] = int(summary['upserted_rows']) + rows_upserted
                            summary['status_breakdown']['success'] = int(summary['status_breakdown']['success']) + 1
                        else:
                            summary['skipped_symbols'] = int(summary['skipped_symbols']) + 1
                            summary['status_breakdown']['skipped'] = int(summary['status_breakdown']['skipped']) + 1
                    except Exception as e:
                        error_message = self._format_exception_message(e)
                        LOGGER.exception("Echec traitement %s | error_detail=%s", symbol, error_message)
                        fallback_last_sync = get_last_sync_date(conn, self.cleaning_audit_latest, symbol)
                        failed_payload = self._build_audit_payload(fallback_last_sync, None, None, 'failed', error_message)
                        LOGGER.error("Persistance audit echec | symbol=%s payload=%s", symbol, failed_payload)
                        upsert_audit(
                            conn,
                            self.cleaning_audit_latest,
                            self.cleaning_audit_runs,
                            symbol,
                            **failed_payload,
                        )
                        summary['audit_rows_written'] = int(summary['audit_rows_written']) + 1
                        sync_audit_to_stock_scores(
                            conn,
                            self.stock_scores,
                            symbol,
                            failed_payload['missing_days'],
                            failed_payload['anomaly_count'],
                            failed_payload['status'],
                        )
                        summary['failed_symbols'] = int(summary['failed_symbols']) + 1
                        summary['status_breakdown']['failed'] = int(summary['status_breakdown']['failed']) + 1
                        if isinstance(e, DataQualityError):
                            summary['degraded_symbols'] = int(summary['degraded_symbols']) + 1

                    if self._should_commit(processed, commit_every):
                        outer_trans = self._commit_batch(outer_trans, conn)
                        summary['batch_commits'] = int(summary['batch_commits']) + 1

                outer_trans.commit()
                summary['batch_commits'] = int(summary['batch_commits']) + 1
                self._log_failed_audit_summary(conn)
            finally:
                gc.collect()

        finished_at = _utc_now_naive()
        summary['finished_at'] = finished_at.isoformat(timespec='seconds')
        summary['duration_seconds'] = round((finished_at - started_at).total_seconds(), 2)
        LOGGER.info(
            'Resume sanitizeur daily | run_id=%s targeted=%s success=%s failed=%s skipped=%s degraded=%s upserted_rows=%s audit_rows=%s batch_commits=%s status_breakdown=%s duration_s=%s',
            summary['run_id'],
            summary['targeted_symbols'],
            summary['successful_symbols'],
            summary['failed_symbols'],
            summary['skipped_symbols'],
            summary['degraded_symbols'],
            summary['upserted_rows'],
            summary['audit_rows_written'],
            summary['batch_commits'],
            summary['status_breakdown'],
            summary['duration_seconds'],
        )
        return summary


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/data_sanitizer_daily.log",
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    sanitizer = DataSanitizer()
    summary = sanitizer.run_pipeline(commit_every=DEFAULT_COMMIT_EVERY)
    _emit_run_summary(summary)


if __name__ == '__main__':
    main()

