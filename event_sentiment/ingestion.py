import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any
import dateutil.parser
import requests
from event_sentiment.trading_calendar import TradingCalendarAligner
from event_sentiment.mapping import EntitySectorMapper
from event_sentiment.models import NormalizedNewsArticle
from service.alpaca.clientNewsAlpaca import iter_news_pages
LOGGER = logging.getLogger(__name__)
class NewsIngestionService:
    def __init__(self, repository, config) -> None:
        self.repository = repository
        self.config = config
        self.aligner = TradingCalendarAligner(
            regular_session_maps_to_same_day=config.regular_session_maps_to_same_day
        )
        self.mapper = EntitySectorMapper()
    def _normalize_article(self, payload: dict[str, Any]) -> NormalizedNewsArticle:
        raw_id = str(payload.get("id") or payload.get("article_id") or "").strip()
        if not raw_id:
            raise ValueError("Article sans identifiant fournisseur.")
        published_at_raw = payload.get("created_at") or payload.get("published_at") or payload.get("updated_at")
        published_at_utc = dateutil.parser.isoparse(str(published_at_raw))
        if published_at_utc.tzinfo is None:
            published_at_utc = published_at_utc.replace(tzinfo=timezone.utc)
        alignment = self.aligner.align(published_at_utc)
        tickers = [
            str(symbol).strip().upper()
            for symbol in (payload.get("symbols") or payload.get("tickers") or [])
            if symbol
        ]
        headline = str(payload.get("headline") or "").strip()
        summary = str(payload.get("summary") or "").strip() or None
        content = str(payload.get("content") or payload.get("body") or "").strip() or None
        source = str(payload.get("source") or payload.get("source_name") or "unknown").strip()
        author = str(payload.get("author") or "").strip() or None
        url = str(payload.get("url") or "").strip() or None
        major_flag = int(len(tickers) >= 3 or source.lower() in {"reuters", "bloomberg", "dow jones"})
        return NormalizedNewsArticle(
            article_id=f"{self.config.provider_name}:{raw_id}",
            headline=headline,
            summary=summary,
            content=content,
            source=source,
            author=author,
            url=url,
            published_at_utc=alignment.event_timestamp_utc,
            event_timestamp_utc=alignment.event_timestamp_utc,
            event_timestamp_ny=alignment.event_timestamp_ny,
            effective_trade_date=alignment.effective_trade_date,
            market_session_tag=alignment.market_session_tag,
            tickers=tickers,
            raw_payload=payload,
            is_major_event=major_flag,
        )
    def run(self, start_utc: datetime, end_utc: datetime, symbols: list[str] | None = None) -> dict[str, int]:
        summary = {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}
        checkpoint = self.repository.get_checkpoint(self.config.source_name)
        page_token = checkpoint["next_page_token"] if checkpoint else None
        previous_watermark = checkpoint["watermark_published_at_utc"] if checkpoint else None
        self.repository.upsert_checkpoint(
            self.config.source_name,
            previous_watermark,
            page_token,
            "running",
        )
        with requests.Session() as session:
            for articles, next_token in iter_news_pages(
                start_utc=start_utc,
                end_utc=end_utc,
                symbols=symbols,
                limit=self.config.page_limit,
                page_token=page_token,
                session=session,
            ):
                if not articles:
                    break
                normalized = [self._normalize_article(payload) for payload in articles]
                summary["fetched"] += len(normalized)
                existing = self.repository.get_existing_article_ids([article.article_id for article in normalized])
                summary["deduped"] += len(existing)
                raw_rows: list[dict[str, Any]] = []
                ticker_rows: list[dict[str, Any]] = []
                ticker_union = sorted({ticker for article in normalized for ticker in article.tickers})
                sector_lookup = self.mapper.resolve(ticker_union, allow_fallback=self.config.allow_sector_fallback)
                for article in normalized:
                    dedupe_key = "|".join([
                        article.headline,
                        article.source,
                        article.url or "",
                        article.published_at_utc.isoformat(),
                    ])
                    dedupe_hash = hashlib.sha256(dedupe_key.encode("utf-8")).hexdigest()
                    raw_rows.append({
                        "article_id": article.article_id,
                        "headline": article.headline,
                        "summary": article.summary,
                        "content": article.content,
                        "source": article.source,
                        "author": article.author,
                        "published_at_utc": article.published_at_utc.replace(tzinfo=None),
                        "event_timestamp_utc": article.event_timestamp_utc.replace(tzinfo=None),
                        "event_timestamp_ny": article.event_timestamp_ny.replace(tzinfo=None),
                        "effective_trade_date": article.effective_trade_date,
                        "market_session_tag": article.market_session_tag,
                        "url": article.url,
                        "ingestion_source": self.config.provider_name,
                        "dedupe_hash": dedupe_hash,
                        "is_major_event": article.is_major_event,
                        "raw_payload": article.raw_payload,
                    })
                    for idx, symbol in enumerate(article.tickers):
                        sector_info = sector_lookup.get(symbol, {})
                        ticker_rows.append({
                            "article_id": article.article_id,
                            "symbol": symbol,
                            "sector": sector_info.get("sector"),
                            "sector_source": sector_info.get("sector_source"),
                            "sector_updated_at": sector_info.get("sector_updated_at"),
                            "is_primary_ticker": int(idx == 0),
                        })
                summary["landed"] += self.repository.upsert_news_raw(raw_rows)
                summary["ticker_maps"] += self.repository.upsert_news_ticker_map(ticker_rows)
                watermark = max(article.published_at_utc for article in normalized).replace(tzinfo=None)
                self.repository.upsert_checkpoint(self.config.source_name, watermark, next_token, "running")
                page_token = next_token
                LOGGER.info(
                    "News ingestion page | fetched=%s deduped=%s landed=%s ticker_maps=%s next_token=%s",
                    len(normalized),
                    len(existing),
                    len(raw_rows),
                    len(ticker_rows),
                    next_token,
                )
                if not next_token:
                    break
                time.sleep(self.config.sleep_between_requests)
        self.repository.upsert_checkpoint(
            self.config.source_name,
            end_utc.replace(tzinfo=None),
            None,
            "success",
        )
        return summary
