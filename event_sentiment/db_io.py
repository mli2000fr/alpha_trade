import json
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import MetaData, Table, bindparam, func, text
from sqlalchemy.dialects.mysql import insert as mysql_insert

from database.connection import get_sqlalchemy_engine
from database.stock_scores import list_candidate_symbols


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
        return list_candidate_symbols(engine=self.engine)

    def list_scored_trade_dates(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[date]:
        filters = ["ns.article_id = nr.article_id"]
        params: dict[str, Any] = {}
        if start_date is not None:
            filters.append("nr.effective_trade_date >= :start_date")
            params["start_date"] = start_date
        if end_date is not None:
            filters.append("nr.effective_trade_date <= :end_date")
            params["end_date"] = end_date
        stmt = text(
            f"""
            SELECT DISTINCT nr.effective_trade_date
            FROM news_raw nr
            JOIN news_sentiment ns ON {' AND '.join(filters)}
            ORDER BY nr.effective_trade_date
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, params).scalars().all()
        return [value for value in rows if isinstance(value, date)]

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
        # ``relevance_components`` est un dict côté ingestion (mode
        # ``scored``) ; MySQL JSON attend une chaîne JSON.
        serializable: list[dict[str, Any]] = []
        for row in records:
            payload = dict(row)
            components = payload.get("relevance_components")
            if isinstance(components, (dict, list)):
                payload["relevance_components"] = json.dumps(components, ensure_ascii=False)
            serializable.append(payload)
        return self._upsert("news_ticker_map", serializable, key_columns={"article_id", "symbol"})

    def upsert_news_sentiment(self, records: list[dict[str, Any]]) -> int:
        return self._upsert("news_sentiment", records, key_columns={"article_id"})

    def upsert_news_ticker_sentiment(self, records: list[dict[str, Any]]) -> int:
        """Niveau 4 — persistance des scores FinBERT contextualisés."""
        return self._upsert(
            "news_ticker_sentiment",
            records,
            key_columns={"article_id", "symbol"},
        )

    def load_pending_contextual_pairs(
        self,
        limit: int = 5000,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Liste les couples ``(article, symbol)`` à scorer en contextuel.

        Retourne les paires présentes dans ``news_ticker_map`` mais absentes
        de ``news_ticker_sentiment``. Filtre optionnel par ``relevance_score``
        (perf : ne tokenise pas les paires dont le Niveau 2/3 a déjà jugé la
        pertinence trop faible). Le ``company_name`` est résolu via
        ``stock_metadata`` (jointure LEFT, NULLable).
        """
        query = text(
            """
            SELECT
                nr.article_id,
                ntm.symbol,
                nr.headline,
                nr.summary,
                nr.content,
                nr.source,
                nr.published_at_utc,
                nr.event_timestamp_utc,
                nr.event_timestamp_ny,
                nr.effective_trade_date,
                nr.market_session_tag,
                nr.is_major_event,
                COALESCE(ntm.relevance_score, 1.0) AS relevance_score,
                sm.company_name AS company_name
            FROM news_ticker_map ntm
            JOIN news_raw nr ON nr.article_id = ntm.article_id
            LEFT JOIN news_ticker_sentiment nts
                ON nts.article_id = ntm.article_id AND nts.symbol = ntm.symbol
            LEFT JOIN stock_metadata sm ON sm.symbol = ntm.symbol
            WHERE nts.article_id IS NULL
              AND COALESCE(ntm.relevance_score, 1.0) >= :min_relevance
            ORDER BY nr.effective_trade_date ASC, nr.published_at_utc ASC,
                     ntm.article_id ASC, ntm.symbol ASC
            LIMIT :limit_rows
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(
                query,
                {"limit_rows": int(limit), "min_relevance": float(min_relevance)},
            ).mappings().all()
        return [dict(row) for row in rows]

    def iter_ticker_map_for_relevance_backfill(
        self,
        batch_size: int = 500,
        start_date: date | None = None,
        end_date: date | None = None,
        symbols: list[str] | None = None,
        rescore_all: bool = False,
    ):
        """Itère par batch les lignes ``news_ticker_map`` candidates au
        backfill du ``relevance_score`` (mode Niveau 2/3).

        Joint ``news_raw`` (headline/summary/content/...) + ``stock_metadata``
        (``company_name``). Filtre par date d'effet et liste de symboles
        optionnels. Par défaut : uniquement les lignes ``relevance_score IS NULL``.
        """
        filters: list[str] = []
        params: dict[str, Any] = {}
        if not rescore_all:
            filters.append("ntm.relevance_score IS NULL")
        if start_date is not None:
            filters.append("nr.effective_trade_date >= :start_date")
            params["start_date"] = start_date
        if end_date is not None:
            filters.append("nr.effective_trade_date <= :end_date")
            params["end_date"] = end_date
        if symbols:
            filters.append("ntm.symbol IN :symbols")
            params["symbols"] = list(symbols)
        where_clause = (" WHERE " + " AND ".join(filters)) if filters else ""
        query_sql = (
            """
            SELECT
                ntm.article_id,
                ntm.symbol,
                ntm.is_primary_ticker,
                nr.headline,
                nr.summary,
                nr.content,
                sm.company_name AS company_name,
                (
                    SELECT COUNT(*) FROM news_ticker_map ntm2
                    WHERE ntm2.article_id = ntm.article_id
                ) AS ticker_count
            FROM news_ticker_map ntm
            JOIN news_raw nr ON nr.article_id = ntm.article_id
            LEFT JOIN stock_metadata sm ON sm.symbol = ntm.symbol
            """
            + where_clause
            + """
            ORDER BY ntm.article_id ASC, ntm.symbol ASC
            LIMIT :limit_rows OFFSET :offset_rows
            """
        )
        stmt = text(query_sql)
        if symbols:
            stmt = stmt.bindparams(bindparam("symbols", expanding=True))

        offset = 0
        while True:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    stmt,
                    {**params, "limit_rows": int(batch_size), "offset_rows": int(offset)},
                ).mappings().all()
            if not rows:
                return
            yield [dict(row) for row in rows]
            if len(rows) < batch_size:
                return
            offset += len(rows)

    def delete_ticker_map_below_score(
        self,
        threshold: float,
        start_date: date | None = None,
        end_date: date | None = None,
        symbols: list[str] | None = None,
    ) -> int:
        """Purge optionnelle des lignes ``news_ticker_map.relevance_score < seuil``.

        Utilisé par le script de backfill quand l'opérateur souhaite réduire
        le bruit historique. La FK CASCADE supprime aussi les lignes
        ``news_ticker_sentiment`` associées.
        """
        filters = ["relevance_score IS NOT NULL", "relevance_score < :threshold"]
        params: dict[str, Any] = {"threshold": float(threshold)}
        if start_date is not None or end_date is not None or symbols:
            # On a besoin d'un sous-select sur news_raw pour les bornes de date.
            join_clause = "JOIN news_raw nr ON nr.article_id = ntm.article_id"
            if start_date is not None:
                filters.append("nr.effective_trade_date >= :start_date")
                params["start_date"] = start_date
            if end_date is not None:
                filters.append("nr.effective_trade_date <= :end_date")
                params["end_date"] = end_date
            if symbols:
                filters.append("ntm.symbol IN :symbols")
                params["symbols"] = list(symbols)
            stmt = text(
                f"""
                DELETE ntm FROM news_ticker_map ntm
                {join_clause}
                WHERE {' AND '.join(filters)}
                """
            )
            if symbols:
                stmt = stmt.bindparams(bindparam("symbols", expanding=True))
        else:
            stmt = text(
                f"DELETE FROM news_ticker_map WHERE {' AND '.join(filters)}"
            )
        with self.engine.begin() as conn:
            result = conn.execute(stmt, params)
        return int(result.rowcount or 0)

    def get_active_finbert_fingerprints(self, trade_date: date) -> list[str]:
        """Phase 4.1.c — fingerprints FinBERT actifs pour `trade_date`.

        Retourne les ``model_fingerprint`` distincts présents sur les
        sentiments rattachés à des articles dont ``effective_trade_date``
        ≤ `trade_date` ET strictement > `trade_date - 30 jours`.
        Trié par fréquence décroissante. Renvoie ``[]`` si la colonne
        n'existe pas encore (rétrocompat pré-migration 0015).
        """
        try:
            query = text(
                """
                SELECT ns.model_fingerprint AS fp, COUNT(*) AS occurrences
                FROM news_sentiment ns
                JOIN news_raw nr ON nr.article_id = ns.article_id
                WHERE ns.model_fingerprint IS NOT NULL
                  AND nr.effective_trade_date <= :trade_date
                  AND nr.effective_trade_date > DATE_SUB(:trade_date, INTERVAL 30 DAY)
                GROUP BY ns.model_fingerprint
                ORDER BY occurrences DESC
                LIMIT 8
                """
            )
            with self.engine.connect() as conn:
                rows = conn.execute(query, {"trade_date": trade_date}).mappings().all()
        except Exception:  # noqa: BLE001 — col absente / dialecte non MySQL
            return []
        return [str(row["fp"]) for row in rows if row.get("fp")]

    def upsert_macro_event_audit(self, records: list[dict[str, Any]]) -> int:
        serializable: list[dict[str, Any]] = []
        for row in records:
            payload = dict(row)
            payload["rule_hits"] = json.dumps(payload["rule_hits"], ensure_ascii=False)
            serializable.append(payload)
        return self._upsert(
            "macro_event_audit",
            serializable,
            key_columns={"article_id", "sector", "macro_event_type"},
        )

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
            ORDER BY nr.effective_trade_date ASC, nr.published_at_utc ASC, nr.article_id ASC
            LIMIT :limit_rows
            """
        )
        frame = pd.read_sql_query(query, self.engine, params={"limit_rows": limit})
        return [dict(row) for row in frame.to_dict(orient="records")]

    def load_feature_frames(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        trade_dates: list[date] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        normalized_trade_dates = sorted({value for value in (trade_dates or []) if value is not None})
        if normalized_trade_dates:
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
                    COALESCE(ntm.relevance_score, 1.0) AS relevance_score,
                    COALESCE(nts.sentiment_label, ns.sentiment_label) AS sentiment_label,
                    COALESCE(nts.positive_score, ns.positive_score) AS positive_score,
                    COALESCE(nts.neutral_score, ns.neutral_score) AS neutral_score,
                    COALESCE(nts.negative_score, ns.negative_score) AS negative_score,
                    COALESCE(nts.sentiment_confidence, ns.sentiment_confidence) AS sentiment_confidence,
                    COALESCE(nts.sentiment_net_score, ns.sentiment_net_score) AS sentiment_net_score
                FROM news_raw nr
                JOIN news_ticker_map ntm ON ntm.article_id = nr.article_id
                JOIN news_sentiment ns ON ns.article_id = nr.article_id
                LEFT JOIN news_ticker_sentiment nts
                    ON nts.article_id = nr.article_id AND nts.symbol = ntm.symbol
                WHERE nr.effective_trade_date IN :trade_dates
                """
            ).bindparams(bindparam("trade_dates", expanding=True))
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
                WHERE nr.effective_trade_date IN :trade_dates
                """
            ).bindparams(bindparam("trade_dates", expanding=True))
            macro_query = text(
                """
                SELECT article_id, trade_date, sector, macro_event_type, impact_direction, impact_score, macro_event_intensity
                FROM macro_event_audit
                WHERE trade_date IN :trade_dates
                """
            ).bindparams(bindparam("trade_dates", expanding=True))
            params: dict[str, Any] = {"trade_dates": normalized_trade_dates}
        else:
            if start_date is None or end_date is None:
                raise ValueError("load_feature_frames requiert start_date/end_date ou trade_dates.")
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
                    COALESCE(ntm.relevance_score, 1.0) AS relevance_score,
                    COALESCE(nts.sentiment_label, ns.sentiment_label) AS sentiment_label,
                    COALESCE(nts.positive_score, ns.positive_score) AS positive_score,
                    COALESCE(nts.neutral_score, ns.neutral_score) AS neutral_score,
                    COALESCE(nts.negative_score, ns.negative_score) AS negative_score,
                    COALESCE(nts.sentiment_confidence, ns.sentiment_confidence) AS sentiment_confidence,
                    COALESCE(nts.sentiment_net_score, ns.sentiment_net_score) AS sentiment_net_score
                FROM news_raw nr
                JOIN news_ticker_map ntm ON ntm.article_id = nr.article_id
                JOIN news_sentiment ns ON ns.article_id = nr.article_id
                LEFT JOIN news_ticker_sentiment nts
                    ON nts.article_id = nr.article_id AND nts.symbol = ntm.symbol
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
            params = {"start_date": start_date, "end_date": end_date}

        ticker_df = pd.read_sql_query(ticker_query, self.engine, params=params)
        sector_df = pd.read_sql_query(sector_query, self.engine, params=params)
        macro_df = pd.read_sql_query(macro_query, self.engine, params=params)
        return ticker_df, sector_df, macro_df


