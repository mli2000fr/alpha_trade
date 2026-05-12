import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import dateutil.parser
import requests
from event_sentiment.trading_calendar import TradingCalendarAligner
from event_sentiment.mapping import EntitySectorMapper
from event_sentiment.models import NormalizedNewsArticle
from event_sentiment.relevance import (
    DEFAULT_WEIGHTS,
    RelevanceWeights,
    score_article_symbol,
)
from service.alpaca.clientNewsAlpaca import iter_news_pages as _alpaca_iter_news_pages
from service.eodhd.news_client import iter_news_pages as _eodhd_iter_news_pages
from service.finnhub.news_client import iter_news_pages as _finnhub_iter_news_pages
LOGGER = logging.getLogger(__name__)

#: Dispatch provider news → callable ``iter_news_pages`` (contrat Alpaca).
#:
#: Tout nouveau provider doit exposer la même signature
#: ``iter_news_pages(start_utc, end_utc, symbols=, limit=, page_token=, session=)``
#: et yield des tuples ``(articles, next_token)`` consommables par
#: :meth:`NewsIngestionService._normalize_article`.
NEWS_PROVIDERS: dict[str, Callable[..., Any]] = {
    "alpaca": _alpaca_iter_news_pages,
    "finnhub": _finnhub_iter_news_pages,
    "eodhd": _eodhd_iter_news_pages,
}


def _resolve_iter_news_pages(provider: str) -> Callable[..., Any]:
    try:
        return NEWS_PROVIDERS[provider]
    except KeyError as exc:
        raise ValueError(
            f"news_provider inconnu: {provider!r} (attendu: {sorted(NEWS_PROVIDERS)})."
        ) from exc


class NewsIngestionService:
    def __init__(self, repository, config) -> None:
        self.repository = repository
        self.config = config
        self.aligner = TradingCalendarAligner(
            regular_session_maps_to_same_day=config.regular_session_maps_to_same_day
        )
        self.mapper = EntitySectorMapper()
        # Dispatch provider news : on accepte qu'un ``DummyConfig`` de test
        # ne porte pas ``news_provider`` et on retombe alors sur Alpaca
        # (comportement historique).
        provider = getattr(config, "news_provider", "alpaca")
        self._iter_news_pages: Callable[..., Any] = _resolve_iter_news_pages(provider)
        self._ticker_relevance_mode = getattr(
            config, "provider_ticker_relevance_mode", "provider_default"
        )
        self._max_tickers_per_article = int(
            getattr(config, "max_tickers_per_article", 25)
        )
        self._min_relevance_score = float(
            getattr(config, "min_relevance_score", 0.0)
        )
        # ``relevance_weights`` peut être surchargé pour tests / tuning ;
        # par défaut on utilise les poids documentés dans relevance.py.
        custom_weights = getattr(config, "relevance_weights", None)
        if isinstance(custom_weights, RelevanceWeights):
            self._relevance_weights: RelevanceWeights = custom_weights
        elif isinstance(custom_weights, dict):
            self._relevance_weights = RelevanceWeights(**custom_weights)
        else:
            self._relevance_weights = DEFAULT_WEIGHTS
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

    @staticmethod
    def _normalize_symbol_list(symbols: list[str] | None) -> list[str]:
        if not symbols:
            return []
        return sorted({str(symbol).strip().upper() for symbol in symbols if symbol and str(symbol).strip()})

    def _resolve_symbol_start(self, symbol: str, start_utc: datetime | None, end_utc: datetime) -> datetime:
        if start_utc is not None:
            return start_utc
        checkpoint = self.repository.get_checkpoint(self.config.source_name, symbol)
        watermark = checkpoint.get("watermark_published_at_utc") if checkpoint else None
        if watermark is not None:
            return watermark.replace(tzinfo=timezone.utc) - timedelta(minutes=self.config.checkpoint_overlap_minutes)
        return end_utc - timedelta(days=self.config.initial_backfill_days)

    def _resolve_persisted_article_ids(
        self,
        raw_rows: list[dict[str, Any]],
    ) -> dict[str, str]:
        resolver = getattr(self.repository, "get_article_ids_by_dedupe_hashes", None)
        if not callable(resolver) or not raw_rows:
            return {
                str(row["article_id"]): str(row["article_id"])
                for row in raw_rows
                if row.get("article_id")
            }
        dedupe_hashes = [str(row["dedupe_hash"]) for row in raw_rows if row.get("dedupe_hash")]
        raw_canonical_by_hash = resolver(self.config.provider_name, dedupe_hashes)
        canonical_by_hash = raw_canonical_by_hash if isinstance(raw_canonical_by_hash, dict) else {}
        resolved: dict[str, str] = {}
        for row in raw_rows:
            article_id = str(row["article_id"])
            dedupe_hash = str(row.get("dedupe_hash") or "")
            resolved[article_id] = canonical_by_hash.get(dedupe_hash, article_id)
        return resolved

    def _run_symbol(
        self,
        symbol: str,
        start_utc: datetime,
        end_utc: datetime,
        resume_checkpoint: bool,
    ) -> dict[str, int]:
        summary = {
            "fetched": 0,
            "deduped": 0,
            "landed": 0,
            "ticker_maps": 0,
            "filtered_too_many_tickers": 0,
            "strict_dropped_tickers": 0,
            "relevance_filtered": 0,
            "relevance_scored": 0,
        }
        checkpoint = self.repository.get_checkpoint(self.config.source_name, symbol)
        page_token = checkpoint["next_page_token"] if checkpoint and resume_checkpoint else None
        previous_watermark = checkpoint["watermark_published_at_utc"] if checkpoint else None

        self.repository.upsert_checkpoint(
            self.config.source_name,
            symbol,
            previous_watermark,
            page_token,
            "running",
        )

        try:
            with requests.Session() as session:
                for articles, next_token in self._iter_news_pages(
                    start_utc=start_utc,
                    end_utc=end_utc,
                    symbols=[symbol],
                    limit=self.config.page_limit,
                    page_token=page_token,
                    session=session,
                ):
                    if not articles:
                        break
                    normalized = [self._normalize_article(payload) for payload in articles]
                    summary["fetched"] += len(normalized)
                    # Garde-fou Niveau 1 : on filtre les articles « bruyants »
                    # (provider qui tagge trop de tickers) avant tout autre
                    # traitement, pour rester conservateur sur le mapping
                    # article → ticker. Voir prompt/add_Finnhub.md addendum.
                    filtered: list[NormalizedNewsArticle] = []
                    for article in normalized:
                        if len(article.tickers) > self._max_tickers_per_article:
                            summary["filtered_too_many_tickers"] += 1
                            LOGGER.info(
                                "Article ignoré (trop de tickers) | id=%s tickers=%s seuil=%s",
                                article.article_id,
                                len(article.tickers),
                                self._max_tickers_per_article,
                            )
                            continue
                        filtered.append(article)
                    normalized = filtered
                    if not normalized:
                        page_token = next_token
                        if not next_token:
                            break
                        continue
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
                        for idx, article_symbol in enumerate(article.tickers):
                            # Mode ``strict`` : on ne conserve que le 1er
                            # ticker fourni par le provider (~= primary
                            # ticker). Le score article reste calculé une
                            # fois côté FinBERT, mais on ne le propage qu'au
                            # ticker principal pour limiter les faux
                            # positifs en cas de tag provider bruyant.
                            if self._ticker_relevance_mode == "strict" and idx > 0:
                                summary["strict_dropped_tickers"] += 1
                                continue
                            sector_info = sector_lookup.get(article_symbol, {})
                            row: dict[str, Any] = {
                                "article_id": article.article_id,
                                "symbol": article_symbol,
                                "sector": sector_info.get("sector"),
                                "sector_source": sector_info.get("sector_source"),
                                "sector_updated_at": sector_info.get("sector_updated_at"),
                                "is_primary_ticker": int(idx == 0),
                            }
                            # Mode ``scored`` : calcule un poids de
                            # pertinence article→symbol et l'ajoute à la
                            # ligne. Filtrage optionnel via
                            # ``min_relevance_score``.
                            if self._ticker_relevance_mode == "scored":
                                relevance = score_article_symbol(
                                    symbol=article_symbol,
                                    headline=article.headline,
                                    summary=article.summary,
                                    content=article.content,
                                    is_primary=(idx == 0),
                                    company_name=sector_info.get("company_name"),
                                    ticker_count=len(article.tickers),
                                    weights=self._relevance_weights,
                                )
                                summary["relevance_scored"] += 1
                                if relevance.score < self._min_relevance_score:
                                    summary["relevance_filtered"] += 1
                                    LOGGER.info(
                                        "Mapping article->ticker filtré (relevance) | "
                                        "article_id=%s symbol=%s score=%.3f seuil=%.3f",
                                        article.article_id,
                                        article_symbol,
                                        relevance.score,
                                        self._min_relevance_score,
                                    )
                                    continue
                                row["relevance_score"] = relevance.score
                                row["relevance_components"] = relevance.components
                            ticker_rows.append(row)
                    summary["landed"] += self.repository.upsert_news_raw(raw_rows)
                    persisted_article_ids = self._resolve_persisted_article_ids(raw_rows)
                    remapped_ticker_rows: list[dict[str, Any]] = []
                    remapped_pairs = 0
                    for row in ticker_rows:
                        payload = dict(row)
                        canonical_article_id = persisted_article_ids.get(payload["article_id"], payload["article_id"])
                        if canonical_article_id != payload["article_id"]:
                            remapped_pairs += 1
                            payload["article_id"] = canonical_article_id
                        remapped_ticker_rows.append(payload)
                    if remapped_pairs:
                        LOGGER.info(
                            "Remap article_id appliqué avant news_ticker_map | provider=%s symbol=%s remapped_pairs=%s",
                            self.config.provider_name,
                            symbol,
                            remapped_pairs,
                        )
                    existing_parent_ids: set[str] = set()
                    if remapped_ticker_rows:
                        existing_parent_ids = set(
                            self.repository.get_existing_article_ids(
                                sorted(
                                    {
                                        str(row["article_id"])
                                        for row in remapped_ticker_rows
                                        if row.get("article_id")
                                    }
                                )
                            )
                        )
                    persistable_ticker_rows = [
                        row
                        for row in remapped_ticker_rows
                        if str(row.get("article_id") or "") in existing_parent_ids
                    ]
                    orphan_ticker_rows = len(remapped_ticker_rows) - len(persistable_ticker_rows)
                    if orphan_ticker_rows:
                        missing_article_ids = sorted(
                            {
                                str(row["article_id"])
                                for row in remapped_ticker_rows
                                if str(row.get("article_id") or "") not in existing_parent_ids
                            }
                        )
                        LOGGER.warning(
                            "Lignes news_ticker_map ignorées faute de parent news_raw | provider=%s symbol=%s orphan_rows=%s missing_article_ids=%s",
                            self.config.provider_name,
                            symbol,
                            orphan_ticker_rows,
                            missing_article_ids[:5],
                        )
                    summary["ticker_maps"] += self.repository.upsert_news_ticker_map(persistable_ticker_rows)
                    watermark = max(article.published_at_utc for article in normalized).replace(tzinfo=None)
                    self.repository.upsert_checkpoint(self.config.source_name, symbol, watermark, next_token, "running")
                    page_token = next_token
                    LOGGER.info(
                        "News ingestion page | symbol=%s fetched=%s deduped=%s landed=%s ticker_maps=%s next_token=%s",
                        symbol,
                        len(normalized),
                        len(existing),
                        len(raw_rows),
                        len(persistable_ticker_rows),
                        next_token,
                    )
                    if not next_token:
                        break
                    time.sleep(self.config.sleep_between_requests)
            self.repository.upsert_checkpoint(
                self.config.source_name,
                symbol,
                end_utc.replace(tzinfo=None),
                None,
                "success",
            )
            return summary
        except Exception as exc:
            self.repository.upsert_checkpoint(
                self.config.source_name,
                symbol,
                previous_watermark,
                page_token,
                "failed",
                last_error=str(exc),
            )
            raise

    def run(
        self,
        start_utc: datetime | None,
        end_utc: datetime,
        symbols: list[str] | None = None,
        symbol_start_overrides: dict[str, datetime] | None = None,
        symbol_resume_overrides: dict[str, bool] | None = None,
        resume_checkpoints: bool = True,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, int]:
        summary = {
            "fetched": 0,
            "deduped": 0,
            "landed": 0,
            "ticker_maps": 0,
            "filtered_too_many_tickers": 0,
            "strict_dropped_tickers": 0,
            "relevance_filtered": 0,
            "relevance_scored": 0,
        }
        normalized_symbols = self._normalize_symbol_list(symbols)
        total_symbols = len(normalized_symbols)
        for index, symbol in enumerate(normalized_symbols, start=1):
            effective_start = (
                symbol_start_overrides.get(symbol)
                if symbol_start_overrides and symbol in symbol_start_overrides
                else self._resolve_symbol_start(symbol, start_utc=start_utc, end_utc=end_utc)
            )
            symbol_summary = self._run_symbol(
                symbol=symbol,
                start_utc=effective_start,
                end_utc=end_utc,
                resume_checkpoint=(
                    symbol_resume_overrides.get(symbol)
                    if symbol_resume_overrides and symbol in symbol_resume_overrides
                    else resume_checkpoints and start_utc is None
                ),
            )
            for key in summary:
                summary[key] += symbol_summary[key]
            if progress_callback is not None:
                progress_callback(
                    {
                        "ingestion": dict(summary),
                        "current_symbol": symbol,
                        "current_symbol_index": index,
                        "current_symbol_total": total_symbols,
                    }
                )
        return summary
