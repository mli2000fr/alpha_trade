import argparse
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import dateutil.parser

from common.utils import configure_root_logging
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.pipeline import EventSentimentPipeline

RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _build_cli_run_summary(
    *,
    stats: dict[str, object],
    started_at: datetime,
    finished_at: datetime,
    config: EventSentimentConfig | None = None,
) -> dict[str, object]:
    ingestion = stats.get("ingestion") if isinstance(stats.get("ingestion"), dict) else {}
    summary: dict[str, object] = {
        "run_id": _build_run_id("event-sentiment"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "resolved_symbols": int(stats.get("resolved_symbols") or 0),
        "window_start_utc": stats.get("start_utc"),
        "window_end_utc": stats.get("end_utc"),
        "fetched_articles": int(ingestion.get("fetched") or 0),
        "deduped_articles": int(ingestion.get("deduped") or 0),
        "landed_articles": int(ingestion.get("landed") or 0),
        "ticker_maps": int(ingestion.get("ticker_maps") or 0),
        "filtered_too_many_tickers": int(ingestion.get("filtered_too_many_tickers") or 0),
        "strict_dropped_tickers": int(ingestion.get("strict_dropped_tickers") or 0),
        "relevance_scored": int(ingestion.get("relevance_scored") or 0),
        "relevance_filtered": int(ingestion.get("relevance_filtered") or 0),
        "sentiment_inferred": int(stats.get("sentiment_inferred") or 0),
        "contextual_pairs_loaded": int(stats.get("contextual_pairs_loaded") or 0),
        "contextual_scored": int(stats.get("contextual_scored") or 0),
        "macro_rows": int(stats.get("macro_rows") or 0),
        "ticker_day_rows": int(stats.get("ticker_day_rows") or 0),
        "sector_day_rows": int(stats.get("sector_day_rows") or 0),
        "finbert_model_fingerprint": stats.get("finbert_model_fingerprint"),
    }
    if config is not None:
        summary["news_provider"] = getattr(config, "news_provider", None)
        summary["source_name"] = getattr(config, "source_name", None)
        summary["provider_ticker_relevance_mode"] = getattr(
            config, "provider_ticker_relevance_mode", None
        )
        summary["min_relevance_score"] = getattr(config, "min_relevance_score", None)
        summary["enable_contextual_scoring"] = bool(
            getattr(config, "enable_contextual_scoring", False)
        )
        summary["contextual_scoring_min_relevance"] = getattr(
            config, "contextual_scoring_min_relevance", None
        )
        summary["contextual_scoring_max_pairs_per_run"] = getattr(
            config, "contextual_scoring_max_pairs_per_run", None
        )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline Event Sentiment basée sur FinBERT")
    parser.add_argument("--start-utc", type=str, default=None, help="Fenêtre UTC de début, ex: 2026-01-01T00:00:00Z")
    parser.add_argument("--end-utc", type=str, default=None, help="Fenêtre UTC de fin, ex: 2026-01-31T23:59:59Z")
    parser.add_argument("--symbols", type=str, default=None, help="Liste optionnelle de symboles, séparés par des virgules")
    parser.add_argument(
        "--finbert-revision",
        type=str,
        default=None,
        help="Revision Hugging Face épinglée (commit SHA / tag) pour FinBERT (Phase 4.1.c)",
    )
    parser.add_argument(
        "--news-provider",
        type=str,
        choices=("alpaca", "finnhub", "eodhd"),
        default="eodhd",
        help=(
            "Source de news utilisée pour l'ingestion. Par défaut 'eodhd' "
            "(EODHD Financial News Feed — provider recommandé). Bascule "
            "possible vers 'alpaca' ou 'finnhub' sans migration DB ; les "
            "checkpoints sont séparés par source_name."
        ),
    )
    parser.add_argument(
        "--ticker-relevance-mode",
        type=str,
        choices=("provider_default", "strict", "scored"),
        default="provider_default",
        help=(
            "Mode de mapping article → ticker. 'provider_default' garde le "
            "comportement historique (tous les tickers fournis par le "
            "provider). 'strict' ne conserve que le 1er ticker (~= primary). "
            "'scored' calcule un score de pertinence (Niveau 2/3) stocké "
            "dans news_ticker_map.relevance_score et utilisé comme poids "
            "downstream dans build_ticker_daily_features."
        ),
    )
    parser.add_argument(
        "--max-tickers-per-article",
        type=int,
        default=None,
        help=(
            "Garde-fou : ignore les articles dont le provider tagge plus de N "
            "tickers (par défaut : valeur de EventSentimentConfig)."
        ),
    )
    parser.add_argument(
        "--min-relevance-score",
        type=float,
        default=None,
        help=(
            "Mode 'scored' : seuil [0,1] de pertinence en dessous duquel "
            "une paire (article, symbole) est filtrée avant insertion dans "
            "news_ticker_map. 0.0 = aucun filtrage (défaut)."
        ),
    )
    parser.add_argument(
        "--enable-contextual-scoring",
        action="store_true",
        default=False,
        help=(
            "Niveau 4 — active le re-scoring FinBERT contextualisé par couple "
            "(article, symbole). Persisté dans news_ticker_sentiment. "
            "Désactivé par défaut (rétro-compat)."
        ),
    )
    parser.add_argument(
        "--contextual-min-relevance",
        type=float,
        default=None,
        help=(
            "Niveau 4 — seuil [0,1] : ne tokenise FinBERT contextuel que pour "
            "les paires (article, symbole) dont relevance_score >= seuil "
            "(perf garde-fou)."
        ),
    )
    parser.add_argument(
        "--contextual-max-pairs",
        type=int,
        default=None,
        help=(
            "Niveau 4 — cap dur sur le nombre de paires (article, symbole) "
            "scorées par run (défaut config : 5000)."
        ),
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        default=False,
        help=(
            "N'exécute pas l'ingestion news : score uniquement le backlog pending "
            "déjà présent dans news_raw, borné par la fenêtre/provider du run."
        ),
    )
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/event_sentiment.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = build_arg_parser().parse_args()

    start_utc = dateutil.parser.isoparse(args.start_utc) if args.start_utc else None
    end_utc = dateutil.parser.isoparse(args.end_utc) if args.end_utc else None
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",")] if args.symbols else None

    repository = EventSentimentRepository()
    config_overrides: dict[str, object] = {}
    if args.finbert_revision:
        config_overrides["finbert_model_revision"] = args.finbert_revision
    if args.ticker_relevance_mode:
        config_overrides["provider_ticker_relevance_mode"] = args.ticker_relevance_mode
    if args.max_tickers_per_article is not None:
        config_overrides["max_tickers_per_article"] = int(args.max_tickers_per_article)
    if args.min_relevance_score is not None:
        config_overrides["min_relevance_score"] = float(args.min_relevance_score)
    if args.enable_contextual_scoring:
        config_overrides["enable_contextual_scoring"] = True
    if args.contextual_min_relevance is not None:
        config_overrides["contextual_scoring_min_relevance"] = float(args.contextual_min_relevance)
    if args.contextual_max_pairs is not None:
        config_overrides["contextual_scoring_max_pairs_per_run"] = int(args.contextual_max_pairs)
    config = EventSentimentConfig.for_provider(args.news_provider, **config_overrides)
    pipeline = EventSentimentPipeline(
        repository=repository,
        config=config,
        progress_callback=lambda payload: _emit_run_summary(payload),
    )
    started_at = _utc_now_naive()
    stats = pipeline.run(
        start_utc=start_utc,
        end_utc=end_utc,
        symbols=symbols,
        skip_ingestion=bool(args.skip_ingestion),
    )
    finished_at = _utc_now_naive()
    _emit_run_summary(
        _build_cli_run_summary(
            stats=stats,
            started_at=started_at,
            finished_at=finished_at,
            config=config,
        )
    )
