import argparse
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from common.utils import configure_root_logging
from database.connection import get_sqlalchemy_engine
from event_sentiment.ingestion import NewsIngestionService
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository

STOCK_BARS_DAILY_WARNING_THRESHOLD = 2000


def _normalize_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in symbols:
        symbol = str(value).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _load_distinct_symbols(query: str) -> list[str]:
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query)).fetchall()
    return _normalize_symbols([row[0] for row in result])


def get_all_symbols_from_stock_bars_daily():
    """Retourne tous les symboles distincts présents dans stock_bars_daily."""
    return _load_distinct_symbols("SELECT DISTINCT symbol FROM stock_bars_daily ORDER BY symbol ASC")


def get_all_symbols_from_stock_scores(*, selected_only: bool = False) -> list[str]:
    """Retourne les symboles distincts présents dans stock_scores."""
    where_clause = "WHERE selection_rank IS NOT NULL" if selected_only else ""
    return _load_distinct_symbols(
        f"""
        SELECT DISTINCT symbol
        FROM stock_scores
        {where_clause}
        ORDER BY symbol ASC
        """
    )


def get_all_symbols_from_stock_scores_history() -> list[str]:
    """Retourne les symboles distincts présents dans stock_scores_history."""
    return _load_distinct_symbols(
        """
        SELECT DISTINCT symbol
        FROM stock_scores_history
        ORDER BY symbol ASC
        """
    )


def get_all_symbols_from_stock_scores_all() -> list[str]:
    """Retourne l'union dédupliquée des symboles présents dans stock_scores ou stock_scores_history."""
    return _load_distinct_symbols(
        """
        SELECT DISTINCT symbol
        FROM (
            SELECT symbol FROM stock_scores
            UNION
            SELECT symbol FROM stock_scores_history
        ) AS combined_symbols
        ORDER BY symbol ASC
        """
    )


def get_all_symbols_from_tradable_universe() -> list[str]:
    """Charge le dernier univers tradable PIT canonique et complet."""
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        run = conn.execute(
            text(
                """
                SELECT universe_run_id
                FROM tradable_universe_runs
                WHERE snapshot_date <= :trade_date
                  AND status = 'completed'
                  AND is_canonical = 1
                  AND rows_written = rows_expected
                  AND data_quality_grade = 'full'
                ORDER BY snapshot_date DESC, finished_at DESC
                LIMIT 1
                """
            ),
            {"trade_date": date.today()},
        ).scalar_one_or_none()
        if run is None:
            raise RuntimeError("Aucun univers tradable PIT canonique complet disponible pour le sentiment.")
        rows = conn.execute(
            text(
                """
                SELECT symbol
                FROM tradable_universe_history
                WHERE universe_run_id = :universe_run_id
                  AND is_tradable = 1
                ORDER BY symbol ASC
                """
            ),
            {"universe_run_id": run},
        ).fetchall()
    return _normalize_symbols([row[0] for row in rows])


def resolve_symbols_from_inputs(
    *,
    symbols_csv: str | None,
    symbol_source: str,
    repository: EventSentimentRepository,
    logger: logging.Logger | None = None,
) -> tuple[list[str], str]:
    if symbols_csv:
        return _normalize_symbols(symbols_csv.split(",")), "explicit"

    if symbol_source == "stock_bars_daily":
        return _normalize_symbols(get_all_symbols_from_stock_bars_daily()), "stock_bars_daily"

    if symbol_source == "stock_scores":
        return _normalize_symbols(get_all_symbols_from_stock_scores()), "stock_scores"

    if symbol_source == "stock_scores_history":
        return _normalize_symbols(get_all_symbols_from_stock_scores_history()), "stock_scores_history"

    if symbol_source == "stock_scores_all":
        return _normalize_symbols(get_all_symbols_from_stock_scores_all()), "stock_scores_all"

    if symbol_source == "tradable-universe":
        return _normalize_symbols(get_all_symbols_from_tradable_universe()), "tradable-universe"

    if symbol_source != "stock_scores_all" and logger is not None:
        logger.warning("Source de symboles inconnue '%s' ; fallback stock_scores_all.", symbol_source)
    return _normalize_symbols(get_all_symbols_from_stock_scores_all()), "stock_scores_all"


def resolve_symbols(
    args: argparse.Namespace,
    repository: EventSentimentRepository,
    logger: logging.Logger,
) -> tuple[list[str], str]:
    return resolve_symbols_from_inputs(
        symbols_csv=args.symbols,
        symbol_source=str(args.symbol_source),
        repository=repository,
        logger=logger,
    )


def _apply_symbol_guardrails(
    *,
    symbol_source: str,
    symbols: list[str],
    max_symbols: int | None,
    logger: logging.Logger,
    parser: argparse.ArgumentParser,
) -> None:
    symbol_count = len(symbols)
    if symbol_source == "stock_bars_daily" and symbol_count > STOCK_BARS_DAILY_WARNING_THRESHOLD:
        logger.warning(
            "Univers d'import très large détecté | source=%s symbol_count=%s threshold=%s. "
            "Préférez --symbol-source tradable-universe, une shortlist --symbols ou un cap --max-symbols.",
            symbol_source,
            symbol_count,
            STOCK_BARS_DAILY_WARNING_THRESHOLD,
        )
    if max_symbols is not None and max_symbols > 0 and symbol_count > max_symbols:
        parser.error(
            "Le nombre de symboles résolus ({0}) dépasse --max-symbols={1}. "
            "Réduisez l'univers (--symbol-source / --symbols) ou augmentez explicitement la limite.".format(
                symbol_count,
                max_symbols,
            )
        )


def _warn_ignored_scoring_flags(args: argparse.Namespace, logger: logging.Logger) -> None:
    ignored_flags: list[str] = []
    if args.sentiment_pending_limit is not None:
        ignored_flags.append("--sentiment-pending-limit")
    if args.sentiment_pending_max_batches is not None:
        ignored_flags.append("--sentiment-pending-max-batches")
    if args.finbert_batch_size is not None:
        ignored_flags.append("--finbert-batch-size")
    if ignored_flags:
        logger.warning(
            "Flags de scoring ignorés par importe_news.py : %s. "
            "Utilisez `python -m event_sentiment --skip-ingestion ...` ou le wrapper auto pour le scoring FinBERT.",
            ", ".join(ignored_flags),
        )


def _coerce_utc_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_checkpoint_aware_import_scope(
    *,
    symbols: list[str],
    start_utc: datetime,
    end_utc: datetime,
    repository: EventSentimentRepository,
    config: EventSentimentConfig,
    logger: logging.Logger,
) -> tuple[list[str], dict[str, datetime], dict[str, bool], int]:
    checkpoints = repository.get_checkpoints(config.source_name, symbols)
    start_overrides: dict[str, datetime] = {}
    resume_overrides: dict[str, bool] = {}
    selected_symbols: list[str] = []
    skipped_symbols = 0

    overlap = getattr(config, "checkpoint_overlap_minutes", 0)

    for symbol in symbols:
        checkpoint = checkpoints.get(symbol) or {}
        watermark = _coerce_utc_datetime(checkpoint.get("watermark_published_at_utc"))
        updated_at = _coerce_utc_datetime(checkpoint.get("updated_at"))
        anchor = watermark or updated_at
        if anchor is None:
            selected_symbols.append(symbol)
            start_overrides[symbol] = start_utc
            resume_overrides[symbol] = False
            continue

        if anchor >= end_utc:
            skipped_symbols += 1
            logger.info(
                "Import ignoré (checkpoint déjà à jour) | symbol=%s checkpoint=%s end=%s",
                symbol,
                anchor,
                end_utc,
            )
            continue

        effective_start = start_utc
        if watermark is not None:
            effective_start = max(start_utc, watermark - timedelta(minutes=int(overlap)))
        elif updated_at is not None:
            effective_start = max(start_utc, updated_at)

        selected_symbols.append(symbol)
        start_overrides[symbol] = effective_start
        resume_overrides[symbol] = watermark is not None

    return selected_symbols, start_overrides, resume_overrides, skipped_symbols

# python ./event_sentiment/importe_news.py --start-date 2025-01-01 --end-date 2025-04-20

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Importe les news sur une période donnée pour un univers de symboles ciblé. "
            "Par défaut, l'univers provient de stock_scores_all pour couvrir l'union du snapshot courant et de l'historique PIT."
        )
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=False,
        help=(
            "Date de début au format YYYY-MM-DD (ex: 2024-05-06). Si absente, "
            "fallback sur `initial_backfill_days` du provider choisi."
        ),
    )
    parser.add_argument("--end-date", type=str, required=False, help="Date de fin au format YYYY-MM-DD (ex: 2024-05-10). Par défaut: aujourd'hui.")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Liste explicite de symboles séparés par des virgules. Prioritaire sur --symbol-source.",
    )
    parser.add_argument(
        "--symbol-source",
        type=str,
        choices=("tradable-universe", "stock_scores", "stock_scores_history", "stock_scores_all", "stock_bars_daily"),
        default="tradable-universe",
        help=(
            "Source des symboles à importer. 'tradable-universe' (défaut) cible le dernier univers PIT canonique complet ; "
            "'stock_scores_all' cible l'union dédupliquée des symboles présents dans stock_scores ou stock_scores_history ; "
            "'stock_scores' limite l'univers aux symboles suivis par le screener ; "
            "'stock_scores_history' cible les symboles déjà présents dans l'historique PIT ; "
            "'stock_bars_daily' conserve l'ancien comportement large."
        ),
    )
    parser.add_argument(
        "--news-provider",
        type=str,
        choices=("alpaca", "finnhub", "eodhd"),
        default="eodhd",
        help="Source de news utilisée pour l'ingestion brute (défaut : eodhd).",
    )
    parser.add_argument(
        "--ticker-relevance-mode",
        type=str,
        choices=("provider_default", "strict", "scored"),
        default="provider_default",
        help="Mode de mapping article -> ticker réutilisé lors de l'import brut.",
    )
    parser.add_argument(
        "--min-relevance-score",
        type=float,
        default=None,
        help="Seuil minimum de pertinence [0,1] quand le mode 'scored' est actif.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Nombre de symboles par batch d'import. Défaut 20.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help=(
            "Garde-fou sécurité : si > 0, refuse l'exécution quand l'univers résolu dépasse cette limite. "
            "Exemple : 500."
        ),
    )
    parser.add_argument(
        "--resume-checkpoints",
        action="store_true",
        default=False,
        help=(
            "Réutilise news_ingestion_checkpoint pour reprendre l'import par symbole depuis le watermark connu, "
            "et saute les symboles déjà à jour par rapport à --end-date."
        ),
    )
    parser.add_argument(
        "--sentiment-pending-limit",
        type=int,
        default=None,
        help="Compatibilité CLI : ignoré par l'import brut ; réservé au scoring pending.",
    )
    parser.add_argument(
        "--sentiment-pending-max-batches",
        type=int,
        default=None,
        help="Compatibilité CLI : ignoré par l'import brut ; réservé au scoring pending.",
    )
    parser.add_argument(
        "--finbert-batch-size",
        type=int,
        default=None,
        help="Compatibilité CLI : ignoré par l'import brut ; réservé au scoring FinBERT.",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_date = datetime.now(timezone.utc)

    configure_root_logging(
        level=logging.INFO,
        log_path="./log/importe_news.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("importe_news")

    repository = EventSentimentRepository()
    symbols, symbol_source = resolve_symbols(args, repository, logger)
    _apply_symbol_guardrails(
        symbol_source=symbol_source,
        symbols=symbols,
        max_symbols=(int(args.max_symbols) if args.max_symbols is not None else None),
        logger=logger,
        parser=parser,
    )
    _warn_ignored_scoring_flags(args, logger)
    logger.info("Source de symboles retenue: %s", symbol_source)
    logger.info("%s symbols trouvés.", len(symbols))
    if not symbols:
        logger.warning("Aucun symbole à importer ; exécution terminée sans appel provider.")
        return

    config_overrides: dict[str, object] = {
        "provider_ticker_relevance_mode": args.ticker_relevance_mode,
    }
    if args.min_relevance_score is not None:
        config_overrides["min_relevance_score"] = float(args.min_relevance_score)
    config = EventSentimentConfig.for_provider(args.news_provider, **config_overrides)
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        start_date = end_date - timedelta(days=int(config.initial_backfill_days))
        logger.info(
            "Date de debut implicite derivee du provider | initial_backfill_days=%s start=%s end=%s",
            config.initial_backfill_days,
            start_date,
            end_date,
        )
    ingestion = NewsIngestionService(repository=repository, config=config)

    symbol_start_overrides: dict[str, datetime] | None = None
    symbol_resume_overrides: dict[str, bool] | None = None
    if args.resume_checkpoints:
        symbols, resolved_start_overrides, resolved_resume_overrides, skipped_symbols = _resolve_checkpoint_aware_import_scope(
            symbols=symbols,
            start_utc=start_date,
            end_utc=end_date,
            repository=repository,
            config=config,
            logger=logger,
        )
        symbol_start_overrides = resolved_start_overrides
        symbol_resume_overrides = resolved_resume_overrides
        logger.info(
            "Import checkpoint-aware | selected_symbols=%s skipped_symbols=%s end=%s",
            len(symbols),
            skipped_symbols,
            end_date,
        )
        if not symbols:
            logger.warning("Tous les symboles sont déjà à jour d'après news_ingestion_checkpoint ; aucun import provider nécessaire.")
            return

    batch_size = max(1, int(args.batch_size))
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        logger.info(f"Traitement batch {i//batch_size+1} ({len(batch)} symbols): {batch}")
        if args.resume_checkpoints:
            batch_start_overrides = {symbol: symbol_start_overrides[symbol] for symbol in batch} if symbol_start_overrides else None
            batch_resume_overrides = {symbol: symbol_resume_overrides[symbol] for symbol in batch} if symbol_resume_overrides else None
            summary = ingestion.run(
                start_utc=start_date,
                end_utc=end_date,
                symbols=batch,
                symbol_start_overrides=batch_start_overrides,
                symbol_resume_overrides=batch_resume_overrides,
                resume_checkpoints=False,
            )
        else:
            summary = ingestion.run(
                start_utc=start_date,
                end_utc=end_date,
                symbols=batch,
                resume_checkpoints=False,
            )
        logger.info(f"Résultat batch {i//batch_size+1}: {summary}")

    logger.info("Import des news terminé.")

if __name__ == "__main__":
    main()

