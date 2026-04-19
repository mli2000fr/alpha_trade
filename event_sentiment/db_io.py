import json
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import MetaData, Table, bindparam, func, text
from sqlalchemy.dialects.mysql import insert as mysql_insert

from database.connection import get_sqlalchemy_engine


class EventSentimentRepository:
    def __init__(self) -> None:
        self.engine = get_sqlalchemy_engine()
        self.metadata = MetaData()
        self._tables: dict[str, Table] = {}

    def _table(self, table_name: str) -> Table:
        if table_name not in self._tables:
            self._tables[table_name] = Table(table_name, self.metadata, autoload_with=self.engine)
        return self._tables[table_name]

    @staticmethod
    def _normalize_mysql_scalar(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            if pd.isna(value):
                return None
            return value.to_pydatetime()
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        return value

    def _normalize_mysql_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {key: self._normalize_mysql_scalar(value) for key, value in record.items()}
            for record in records
        ]

    def _upsert(self, table_name: str, records: list[dict[str, Any]], key_columns: set[str]) -> int:
        if not records:
            return 0
        records = self._normalize_mysql_records(records)
        table = self._table(table_name)
        stmt = mysql_insert(table).values(records)
        update_cols = {
            column.name: stmt.inserted[column.name]
            for column in table.c.values()
            if column.name in records[0] and column.name not in key_columns
        }
        if "updated_at" in table.c:
            update_cols["updated_at"] = func.current_timestamp()
        with self.engine.begin() as conn:
            conn.execute(stmt.on_duplicate_key_update(**update_cols))
        return len(records)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = str(symbol).strip().upper()
        if not normalized:
            raise ValueError("symbol checkpoint vide.")
        return normalized

    def get_checkpoint(self, source_name: str, symbol: str) -> dict[str, Any] | None:
        stmt = text(
            """
            SELECT source_name, symbol, watermark_published_at_utc, next_page_token, status, last_error, updated_at
            FROM news_ingestion_checkpoint
            WHERE source_name = :source_name AND symbol = :symbol
            """
        )
        with self.engine.connect() as conn:
            row = conn.execute(
                stmt,
                {"source_name": source_name, "symbol": self._normalize_symbol(symbol)},
            ).mappings().first()
        return dict(row) if row else None

    def get_checkpoints(self, source_name: str, symbols: list[str]) -> dict[str, dict[str, Any]]:
        normalized_symbols = [self._normalize_symbol(symbol) for symbol in symbols if symbol and str(symbol).strip()]
        if not normalized_symbols:
            return {}
        stmt = text(
            """
            SELECT source_name, symbol, watermark_published_at_utc, next_page_token, status, last_error, updated_at
            FROM news_ingestion_checkpoint
            WHERE source_name = :source_name
              AND symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"source_name": source_name, "symbols": normalized_symbols}).mappings().all()
        return {str(row["symbol"]): dict(row) for row in rows}

    def load_candidate_symbols(self) -> list[str]:
        stmt = text(
            """
            SELECT symbol
            FROM stock_scores
            WHERE is_candidate = 1
            ORDER BY total_score DESC, symbol ASC
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        return [str(row[0]).strip().upper() for row in rows if row and row[0]]

    def upsert_checkpoint(
        self,
        source_name: str,
        symbol: str,
        watermark_published_at_utc: datetime | None,
        next_page_token: str | None,
        status: str,
        last_error: str | None = None,
    ) -> None:
        self._upsert(
            "news_ingestion_checkpoint",
            [{
                "source_name": source_name,
                "symbol": self._normalize_symbol(symbol),
                "watermark_published_at_utc": watermark_published_at_utc,
                "next_page_token": next_page_token,
                "status": status,
                "last_error": last_error,
            }],
            key_columns={"source_name", "symbol"},
        )

    def get_existing_article_ids(self, article_ids: list[str]) -> set[str]:
        if not article_ids:
            return set()
        stmt = text("SELECT article_id FROM news_raw WHERE article_id IN :article_ids").bindparams(
            bindparam("article_ids", expanding=True)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"article_ids": article_ids}).fetchall()
        return {str(row[0]) for row in rows}

    def upsert_news_raw(self, records: list[dict[str, Any]]) -> int:
        serializable: list[dict[str, Any]] = []
        for row in records:
            payload = dict(row)
            payload["raw_payload"] = json.dumps(payload["raw_payload"], ensure_ascii=False)
            serializable.append(payload)
        return self._upsert("news_raw", serializable, key_columns={"article_id"})

    def upsert_news_ticker_map(self, records: list[dict[str, Any]]) -> int:
        return self._upsert("news_ticker_map", records, key_columns={"article_id", "symbol"})

    def upsert_news_sentiment(self, records: list[dict[str, Any]]) -> int:
        return self._upsert("news_sentiment", records, key_columns={"article_id"})

    def upsert_macro_event_audit(self, records: list[dict[str, Any]]) -> int:
        serializable: list[dict[str, Any]] = []
        for row in records:
            payload = dict(row)
            payload["rule_hits"] = json.dumps(payload["rule_hits"], ensure_ascii=False)
            serializable.append(payload)
        return self._upsert("macro_event_audit", serializable, key_columns={"article_id", "sector"})

    def upsert_ticker_daily_features(self, records: list[dict[str, Any]]) -> int:
        return self._upsert("ticker_daily_sentiment_features", records, key_columns={"symbol", "trade_date"})

    def upsert_sector_daily_features(self, records: list[dict[str, Any]]) -> int:
        return self._upsert("sector_daily_sentiment_features", records, key_columns={"sector", "trade_date"})

    def load_pending_articles(self, limit: int = 1000) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT
                nr.article_id,
                nr.headline,
                nr.summary,
                nr.content,
                nr.source,
                nr.author,
                nr.url,
                nr.published_at_utc,
                nr.event_timestamp_utc,
                nr.event_timestamp_ny,
                nr.effective_trade_date,
                nr.market_session_tag,
                nr.is_major_event
            FROM news_raw nr
            LEFT JOIN news_sentiment ns ON ns.article_id = nr.article_id
            WHERE ns.article_id IS NULL
            ORDER BY nr.published_at_utc ASC
            LIMIT :limit_rows
            """
        )
        return pd.read_sql_query(query, self.engine, params={"limit_rows": limit}).to_dict(orient="records")

    def load_feature_frames(self, start_date, end_date) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        ticker_query = text(
            """
            SELECT
                nr.article_id,
                nr.effective_trade_date,
                nr.event_timestamp_ny,
                nr.market_session_tag,
                nr.source,
                nr.is_major_event,
                ntm.symbol,
                COALESCE(ntm.sector, 'UNKNOWN') AS sector,
                ns.sentiment_label,
                ns.positive_score,
                ns.neutral_score,
                ns.negative_score,
                ns.sentiment_confidence,
                ns.sentiment_net_score
            FROM news_raw nr
            JOIN news_ticker_map ntm ON ntm.article_id = nr.article_id
            JOIN news_sentiment ns ON ns.article_id = nr.article_id
            WHERE nr.effective_trade_date BETWEEN :start_date AND :end_date
            """
        )
        sector_query = text(
            """
            SELECT
                nr.article_id,
                nr.effective_trade_date,
                nr.event_timestamp_ny,
                nr.market_session_tag,
                nr.source,
                nr.is_major_event,
                COALESCE(ntm.sector, 'UNKNOWN') AS sector,
                ns.sentiment_label,
                ns.sentiment_confidence,
                ns.sentiment_net_score
            FROM news_raw nr
            JOIN news_ticker_map ntm ON ntm.article_id = nr.article_id
            JOIN news_sentiment ns ON ns.article_id = nr.article_id
            WHERE nr.effective_trade_date BETWEEN :start_date AND :end_date
            """
        )
        macro_query = text(
            """
            SELECT article_id, trade_date, sector, macro_event_type, impact_direction, impact_score, macro_event_intensity
            FROM macro_event_audit
            WHERE trade_date BETWEEN :start_date AND :end_date
            """
        )
        ticker_df = pd.read_sql_query(ticker_query, self.engine, params={"start_date": start_date, "end_date": end_date})
        sector_df = pd.read_sql_query(sector_query, self.engine, params={"start_date": start_date, "end_date": end_date})
        macro_df = pd.read_sql_query(macro_query, self.engine, params={"start_date": start_date, "end_date": end_date})
        return ticker_df, sector_df, macro_df


