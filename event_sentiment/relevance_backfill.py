"""Script de backfill batch : ``relevance_score`` (Niveau 2/3) + scoring
contextualisé (Niveau 4) sur les lignes ``news_ticker_map`` historiques.

Exécutable :

.. code-block:: bash

   python -m event_sentiment.relevance_backfill --batch-size 500 \
       --start-date 2025-01-01 --end-date 2026-05-01 --rescore-contextual

Usage typique :

* Premier passage : ``--dry-run`` pour évaluer le volume sans rien écrire.
* Backfill ``relevance_score`` uniquement : laisser ``--rescore-contextual``
  désactivé (rapide, pure-Python).
* Backfill complet Niveau 4 : activer ``--rescore-contextual`` (charge
  FinBERT, peut être long).
* Purge optionnelle des paires bruyantes : ``--purge-below 0.2``.

Le script émet un summary JSON sur ``stdout`` préfixé par
``::alpha_trade_run_summary::`` consommable par l'IHM (parser commun).
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Literal, cast
from uuid import uuid4

import dateutil.parser

from common.utils import configure_root_logging
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.importe_news import resolve_symbols_from_inputs
from event_sentiment.models import NormalizedNewsArticle
from event_sentiment.relevance import (
    DEFAULT_WEIGHTS,
    RelevanceWeights,
    score_article_symbol,
)
from event_sentiment.scoring import ContextualFinBERTScorer

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _emit_run_summary(summary: dict[str, Any]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _build_run_id(prefix: str = "relevance-backfill") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return dateutil.parser.isoparse(value).date()


def _parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return sorted({s.strip().upper() for s in value.split(",") if s.strip()})


class RelevanceBackfillService:
    """Orchestre le backfill du ``relevance_score`` et (optionnel) du
    re-scoring FinBERT contextuel sur ``news_ticker_map``.

    Les deux phases sont indépendantes : on peut backfiller uniquement les
    scores Niveau 2/3 (rapide, pure-Python) puis lancer le Niveau 4
    séparément, ou enchaîner les deux dans un même run.
    """

    def __init__(
        self,
        repository: EventSentimentRepository,
        config: EventSentimentConfig,
        weights: RelevanceWeights | None = None,
    ) -> None:
        self.repository = repository
        self.config = config
        self.weights = weights or DEFAULT_WEIGHTS

    # ------------------------------------------------------------------
    # Phase 1 — backfill ``relevance_score`` (Niveau 2/3, sans FinBERT).
    # ------------------------------------------------------------------
    def backfill_relevance(
        self,
        *,
        batch_size: int = 500,
        start_date: date | None = None,
        end_date: date | None = None,
        symbols: list[str] | None = None,
        ingestion_source: str | None = None,
        dry_run: bool = False,
        rescore_all: bool = False,
    ) -> dict[str, int]:
        scanned = 0
        rescored = 0
        for batch in self.repository.iter_ticker_map_for_relevance_backfill(
            batch_size=batch_size,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            ingestion_source=ingestion_source,
            rescore_all=rescore_all,
        ):
            scanned += len(batch)
            updates: list[dict[str, Any]] = []
            for row in batch:
                result = score_article_symbol(
                    symbol=str(row["symbol"]),
                    headline=row.get("headline") or "",
                    summary=row.get("summary"),
                    content=row.get("content"),
                    is_primary=bool(row.get("is_primary_ticker")),
                    company_name=row.get("company_name"),
                    ticker_count=int(row.get("ticker_count") or 1),
                    weights=self.weights,
                )
                updates.append(
                    {
                        "article_id": row["article_id"],
                        "symbol": row["symbol"],
                        "relevance_score": result.score,
                        "relevance_components": result.components,
                    }
                )
            if updates and not dry_run:
                rescored += self.repository.upsert_news_ticker_map(updates)
            elif updates:
                rescored += len(updates)  # dry-run : compteur informatif
            LOGGER.info(
                "Relevance backfill batch | scanned=%s rescored_total=%s dry_run=%s",
                scanned,
                rescored,
                dry_run,
            )
        return {"relevance_scanned": scanned, "relevance_rescored": rescored}

    def purge_below(
        self,
        *,
        threshold: float,
        start_date: date | None = None,
        end_date: date | None = None,
        symbols: list[str] | None = None,
        ingestion_source: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, int | float]:
        if dry_run:
            LOGGER.info(
                "Purge dry-run (no DELETE) | threshold=%.3f start=%s end=%s symbols=%s",
                threshold,
                start_date,
                end_date,
                symbols,
            )
            return {"relevance_purged": 0, "relevance_purge_threshold": threshold}
        deleted = self.repository.delete_ticker_map_below_score(
            threshold=threshold,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            ingestion_source=ingestion_source,
        )
        return {"relevance_purged": deleted, "relevance_purge_threshold": threshold}

    # ------------------------------------------------------------------
    # Backfill contextualisé FinBERT (Niveau 4).
    # ------------------------------------------------------------------
    def backfill_contextual(
        self,
        *,
        batch_size: int = 500,
        min_relevance: float = 0.0,
        max_pairs: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        symbols: list[str] | None = None,
        ingestion_source: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, int]:
        cap = int(max_pairs or self.config.contextual_scoring_max_pairs_per_run)
        pending = self.repository.load_pending_contextual_pairs(
            limit=cap,
            min_relevance=min_relevance,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            ingestion_source=ingestion_source,
        )
        if not pending:
            return {"contextual_pairs_loaded": 0, "contextual_scored": 0}

        if dry_run:
            LOGGER.info(
                "Contextual backfill dry-run | pending=%s (no FinBERT call)",
                len(pending),
            )
            return {"contextual_pairs_loaded": len(pending), "contextual_scored": 0}

        scorer = ContextualFinBERTScorer(
            model_name=self.config.finbert_model_name,
            model_version=self.config.finbert_model_version,
            batch_size=self.config.finbert_batch_size,
            max_length=self.config.finbert_max_length,
            model_revision=getattr(self.config, "finbert_model_revision", None),
        )
        total_scored = 0
        for offset in range(0, len(pending), batch_size):
            chunk = pending[offset : offset + batch_size]
            pairs: list[tuple[NormalizedNewsArticle, str, str | None]] = []
            for row in chunk:
                article = NormalizedNewsArticle(
                    article_id=row["article_id"],
                    headline=row.get("headline") or "",
                    summary=row.get("summary"),
                    content=row.get("content"),
                    source=row.get("source") or "",
                    author=None,
                    url=None,
                    published_at_utc=row["published_at_utc"],
                    event_timestamp_utc=row["event_timestamp_utc"],
                    event_timestamp_ny=row["event_timestamp_ny"],
                    effective_trade_date=row["effective_trade_date"],
                    market_session_tag=row.get("market_session_tag") or "regular",
                    tickers=[],
                    raw_payload={},
                    is_major_event=int(row.get("is_major_event") or 0),
                )
                pairs.append((article, str(row["symbol"]), row.get("company_name")))
            records = scorer.score_pairs(pairs)
            total_scored += self.repository.upsert_news_ticker_sentiment(
                [asdict(r) for r in records]
            )
        return {"contextual_pairs_loaded": len(pending), "contextual_scored": total_scored}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill batch des scores de pertinence ``relevance_score`` "
            "(Niveau 2/3) et, optionnellement, du re-scoring FinBERT "
            "contextualisé (Niveau 4) sur ``news_ticker_map``."
        )
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--news-provider",
        type=str,
        choices=("alpaca", "finnhub", "eodhd"),
        default="eodhd",
        help=(
            "Provider news du scope visé. Utilisé pour aligner la config provider et filtrer "
            "`news_raw.ingestion_source` / `news_ticker_map` sur le même périmètre que l'étape 7."
        ),
    )
    parser.add_argument("--start-date", type=str, default=None, help="ISO date (effective_trade_date)")
    parser.add_argument("--end-date", type=str, default=None, help="ISO date (effective_trade_date)")
    parser.add_argument("--symbols", type=str, default=None, help="Liste CSV de symboles à filtrer")
    parser.add_argument(
        "--symbol-source",
        type=str,
        choices=("stock_scores", "stock_scores_history", "stock_scores_all", "candidates", "stock_bars_daily"),
        default=None,
        help="Source optionnelle des symboles quand --symbols est absent.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Garde-fou sécurité : refuse le run si l'univers résolu dépasse cette limite.",
    )
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument(
        "--rescore-all",
        action="store_true",
        default=False,
        help=(
            "Recalcule relevance_score même pour les lignes déjà scorées "
            "(utile après évolution des poids/heuristique). Défaut : NULL only."
        ),
    )
    parser.add_argument(
        "--purge-below",
        type=float,
        default=None,
        help=(
            "Si fourni, supprime les lignes news_ticker_map dont relevance_score "
            "< seuil (FK CASCADE supprime aussi news_ticker_sentiment associé)."
        ),
    )
    parser.add_argument(
        "--rescore-contextual",
        action="store_true",
        default=False,
        help=(
            "Phase 2 — lance également le scoring FinBERT contextuel sur les "
            "paires (article, symbole) sans entrée news_ticker_sentiment."
        ),
    )
    parser.add_argument(
        "--contextual-only",
        action="store_true",
        default=False,
        help=(
            "Exécute uniquement le scoring FinBERT contextuel (Niveau 4), sans recalculer "
            "relevance_score. Utile pour la maintenance ciblée d'un scope déjà scoré en standard."
        ),
    )
    parser.add_argument(
        "--contextual-min-relevance",
        type=float,
        default=0.0,
        help="Seuil min de relevance_score pour activer le scoring contextuel.",
    )
    parser.add_argument(
        "--contextual-max-pairs",
        type=int,
        default=None,
        help="Cap dur sur le nombre de paires scorées en contextuel (défaut config).",
    )
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/event_sentiment_backfill.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = build_arg_parser().parse_args()
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    repository = EventSentimentRepository()
    news_provider = cast(Literal["alpaca", "finnhub", "eodhd"], str(args.news_provider or "eodhd"))
    config = EventSentimentConfig.for_provider(news_provider)
    service = RelevanceBackfillService(repository=repository, config=config)
    if args.symbols or args.symbol_source:
        symbols, _effective_symbol_source = resolve_symbols_from_inputs(
            symbols_csv=args.symbols,
            symbol_source=str(args.symbol_source or "stock_scores_all"),
            repository=repository,
            logger=LOGGER,
        )
        if args.max_symbols is not None and args.max_symbols > 0 and len(symbols) > int(args.max_symbols):
            raise SystemExit(
                "Le nombre de symboles résolus ({0}) dépasse --max-symbols={1}. "
                "Réduisez l'univers (--symbol-source / --symbols) ou augmentez explicitement la limite.".format(
                    len(symbols),
                    int(args.max_symbols),
                )
            )
    else:
        symbols = _parse_symbols(args.symbols)

    summary: dict[str, Any] = {
        "run_id": _build_run_id(),
        "started_at": started_at.isoformat(timespec="seconds"),
        "news_provider": news_provider,
        "source_name": getattr(config, "source_name", None),
        "dry_run": bool(args.dry_run),
        "rescore_all": bool(args.rescore_all),
        "rescore_contextual": bool(args.rescore_contextual),
        "contextual_only": bool(args.contextual_only),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "symbols": args.symbols,
        "symbol_source": args.symbol_source,
        "max_symbols": args.max_symbols,
    }

    if not args.contextual_only:
        relevance_stats = service.backfill_relevance(
            batch_size=int(args.batch_size),
            start_date=_parse_date(args.start_date),
            end_date=_parse_date(args.end_date),
            symbols=symbols,
            ingestion_source=news_provider,
            dry_run=bool(args.dry_run),
            rescore_all=bool(args.rescore_all),
        )
        summary.update(relevance_stats)

        if args.purge_below is not None:
            purge_stats = service.purge_below(
                threshold=float(args.purge_below),
                start_date=_parse_date(args.start_date),
                end_date=_parse_date(args.end_date),
                symbols=symbols,
                ingestion_source=news_provider,
                dry_run=bool(args.dry_run),
            )
            summary.update(purge_stats)
    else:
        summary.setdefault("relevance_scanned", 0)
        summary.setdefault("relevance_rescored", 0)
        LOGGER.info(
            "Calcul relevance_score désactivé (--contextual-only) : scoring FinBERT contextuel uniquement."
        )

    if args.rescore_contextual:
        ctx_stats = service.backfill_contextual(
            batch_size=int(args.batch_size),
            min_relevance=float(args.contextual_min_relevance),
            max_pairs=args.contextual_max_pairs,
            start_date=_parse_date(args.start_date),
            end_date=_parse_date(args.end_date),
            symbols=symbols,
            ingestion_source=news_provider,
            dry_run=bool(args.dry_run),
        )
        summary.update(ctx_stats)

    finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    summary["finished_at"] = finished_at.isoformat(timespec="seconds")
    summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 2)
    _emit_run_summary(summary)


if __name__ == "__main__":
    main()

