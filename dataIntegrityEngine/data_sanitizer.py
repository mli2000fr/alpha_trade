import os
import logging
import math
import gc
from datetime import datetime, timedelta, date
from typing import Optional

import pytz
import polars as pl
from dateutil import parser as dtparser

from sqlalchemy import create_engine, MetaData, Table, select, func, update, insert, and_
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.dialects.mysql import insert as mysql_insert

from service.alpaca.client import fetch_bars
from database.bar_metadata import TimeFrame
from database.sanitizer_db_ops import (
    get_last_sync_date, get_prev_close_before,
    upsert_stock_bars_daily, upsert_audit, get_symbols
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
        user = os.getenv(db_user_env)
        pwd = os.getenv(db_pass_env)
        if not user or not pwd:
            raise RuntimeError("Variables d'environnement DB manquantes (LOGIN_DB/PASSWORD_DB)")
        uri = f"mysql+pymysql://{user}:{pwd}@{db_host}/{db_name}?charset=utf8mb4"
        self.engine: Engine = create_engine(uri, pool_pre_ping=True)
        self.tz_ny = pytz.timezone('America/New_York')
        self.metadata = MetaData()
        self._reflect_tables()
        self._spy_calendar_cache: Optional[pl.DataFrame] = None

    def _reflect_tables(self):
        self.stock_bars_daily = Table('stock_bars_daily', self.metadata, autoload_with=self.engine)
        self.cleaning_audit_log = Table('cleaning_audit_log', self.metadata, autoload_with=self.engine)
        self.stock_metadata = Table('stock_metadata', self.metadata, autoload_with=self.engine)

    # ---------- Calendrier SPY ----------
    def _to_ny_date(self, ts_str: str) -> date:
        dt_utc = dtparser.isoparse(ts_str)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
        dt_ny = dt_utc.astimezone(self.tz_ny)
        return dt_ny.date()

    def load_spy_calendar(self, start: date, end: date) -> pl.DataFrame:
        """Construit le calendrier RTH via SPY pour [start, end]. Mis en cache au sein de l'instance."""
        # Si cache existant couvre la plage demandée, tronquer
        if self._spy_calendar_cache is not None:
            if (self._spy_calendar_cache['date'].min() <= start) and (self._spy_calendar_cache['date'].max() >= end):
                return self._spy_calendar_cache.filter((pl.col('date') >= pl.lit(start)) & (pl.col('date') <= pl.lit(end)))
        # Toujours reculer de quelques jours pour s'assurer d'inclure 'start' dans la plage renvoyée par l'API
        fetch_start = (start - timedelta(days=10)).isoformat()
        bars = fetch_bars('SPY', TimeFrame.ONE_DAY.api_value, fetch_start)
        dates = [self._to_ny_date(b['t']) for b in bars]
        # Fallback si la couverture est insuffisante
        if not dates or max(dates) < end or min(dates) > start:
            bars2 = fetch_bars('SPY', TimeFrame.ONE_DAY.api_value, None)
            dates = [self._to_ny_date(b['t']) for b in bars2]
        cal_df = pl.DataFrame({'date': sorted([d for d in dates if start <= d <= end])})
        self._spy_calendar_cache = cal_df
        return cal_df

    # ---------- Fetch Alpaca 1D ----------
    def fetch_symbol_bars_1d(self, symbol: str, start: Optional[date]) -> pl.DataFrame:
        start_str = start.isoformat() if start else None
        bars = fetch_bars(symbol, TimeFrame.ONE_DAY.api_value, start_str)
        if not bars:
            return pl.DataFrame({'date': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'adj_close': [], 'vwap': [], 'is_filled': []})
        df = pl.DataFrame({
            'date': [self._to_ny_date(b['t']) for b in bars],
            'open': [b['o'] for b in bars],
            'high': [b['h'] for b in bars],
            'low': [b['l'] for b in bars],
            'close': [b['c'] for b in bars],
            'volume': [b['v'] for b in bars],
            'adj_close': [b.get('c', None) for b in bars],  # approximation: adjusted close non distinct
            'vwap': [b.get('vw', None) for b in bars],
            'is_filled': [False] * len(bars)
        }).sort('date').unique(subset=['date'], keep='last')
        return df

    # ---------- Alignement & features ----------
    def sanitize_and_align(self, df: pl.DataFrame, calendar: pl.DataFrame, prev_close: Optional[float]) -> tuple[pl.DataFrame, int]:
        """Retourne df aligné sur le calendrier avec forward-fill; renvoie aussi le nombre de jours remplis."""
        if df.is_empty():
            return df, 0
        # Join sur calendrier (gauche)
        base = calendar.join(df, on='date', how='left')
        # Identifier les lignes manquantes d'origine (pas de close réelle)
        base = base.with_columns([
            pl.col('close').is_null().alias('orig_missing')
        ])
        # Forward-fill close en option avec seed prev_close via shift-fill plus tard
        # Remplacer open/high/low/adj_close manquants par close après FF
        tmp = base.with_columns([
            pl.col('close').forward_fill().alias('close')
        ])
        tmp = tmp.with_columns([
            pl.when(pl.col('open').is_null()).then(pl.col('close')).otherwise(pl.col('open')).alias('open'),
            pl.when(pl.col('high').is_null()).then(pl.col('close')).otherwise(pl.col('high')).alias('high'),
            pl.when(pl.col('low').is_null()).then(pl.col('close')).otherwise(pl.col('low')).alias('low'),
            pl.when(pl.col('adj_close').is_null()).then(pl.col('close')).otherwise(pl.col('adj_close')).alias('adj_close'),
        ])
        # Volume: 0 si manquant d'origine
        tmp = tmp.with_columns([
            pl.when(pl.col('orig_missing')).then(pl.lit(0)).otherwise(pl.col('volume').fill_null(0)).alias('volume'),
            pl.col('vwap')
        ])
        # is_filled basé sur orig_missing
        tmp = tmp.with_columns([
            pl.col('orig_missing').alias('is_filled')
        ])
        # Calcul daily_return avec prev_close externe pour la 1ère ligne
        prevc = pl.col('close').shift(1)
        if prev_close is not None:
            prevc = prevc.fill_null(prev_close)
        tmp = tmp.with_columns([
            prevc.alias('prev_close')
        ])
        tmp = tmp.with_columns([
            ((pl.col('close') / pl.col('prev_close')) - 1.0).alias('daily_return')
        ])
        # Parkinson, Overnight Gap, RVOL20 (non persistés)
        ln2 = math.log(2.0)
        parkinson = ((pl.col('high') / pl.col('low')).log().abs() / (4 * ln2)).sqrt().alias('parkinson_vol')
        overnight_gap = ((pl.col('open') / pl.col('prev_close')) - 1.0).alias('overnight_gap')
        rvol20 = (pl.col('volume') / pl.col('volume').rolling_mean(window_size=20, min_periods=1).shift(1)).alias('rvol20')
        tmp = tmp.with_columns([parkinson, overnight_gap, rvol20])
        # Nettoyage final
        tmp = tmp.drop(['prev_close'])
        filled_count = int(tmp['is_filled'].sum())
        return tmp, filled_count

    def detect_anomalies(self, df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
        if df.is_empty():
            return df, 0
        med = pl.col('daily_return').rolling_median(window_size=20, min_periods=5).alias('ret_med')
        df2 = df.with_columns([med])
        df2 = df2.with_columns([
            (pl.col('daily_return') - pl.col('ret_med')).abs().alias('abs_dev')
        ])
        df2 = df2.with_columns([
            pl.col('abs_dev').rolling_median(window_size=20, min_periods=5).alias('mad')
        ])
        is_anom = ((pl.col('abs_dev') > 5.0 * pl.col('mad')) & (pl.col('daily_return').abs() > 0.02)).alias('is_anomaly')
        df2 = df2.with_columns([is_anom])
        count = int(df2['is_anomaly'].sum())
        return df2.drop(['ret_med', 'abs_dev', 'mad']), count

    # ---------- Orchestration ----------
   
    def run_pipeline(self, symbols: Optional[list[str]] = None, commit_every: int = 50):
        processed = 0
        with self.engine.connect() as conn:
            outer_trans = conn.begin()
            try:
                if symbols is None:
                    symbols = get_symbols(conn, self.stock_metadata)
                for idx, symbol in enumerate(symbols, 1):
                    logging.info(f"Traitement {idx}/{len(symbols)}: {symbol}")
                    try:
                        last_sync = get_last_sync_date(conn, self.cleaning_audit_log, symbol)
                        start_date = (last_sync + timedelta(days=1)) if last_sync else None
                        df_raw = self.fetch_symbol_bars_1d(symbol, start_date)
                        if df_raw.is_empty():
                            logging.info(f"Aucune donnée pour {symbol} après {start_date}")
                            upsert_audit(conn, self.cleaning_audit_log, symbol, last_sync, 0, 0, 'success', None)
                            continue
                        window_start = df_raw['date'][0]
                        window_end = df_raw['date'][-1]
                        cal = self.load_spy_calendar(window_start, window_end)
                        prev_close = get_prev_close_before(conn, self.stock_bars_daily, symbol, window_start)
                        df_aligned, missing_cnt = self.sanitize_and_align(df_raw, cal, prev_close)
                        df_features, anom_cnt = self.detect_anomalies(df_aligned)
                        upsert_stock_bars_daily(conn, self.stock_bars_daily, symbol, df_features)
                        upsert_audit(conn, self.cleaning_audit_log, symbol, df_features['date'][-1] if df_features.height > 0 else last_sync, missing_cnt, anom_cnt, 'success', None)
                        processed += 1
                    except Exception as e:
                        logging.exception(f"Echec traitement {symbol}")
                        upsert_audit(conn, self.cleaning_audit_log, symbol, last_sync if 'last_sync' in locals() else None, 0, 0, 'failed', str(e))
                    if processed % commit_every == 0:
                        outer_trans.commit()
                        outer_trans = conn.begin()
                        gc.collect()
                outer_trans.commit()
            finally:
                gc.collect()


def main():
    sanitizer = DataSanitizer()
    sanitizer.run_pipeline(commit_every=50)


if __name__ == '__main__':
    main()

