import argparse
import logging
from datetime import datetime, timezone

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


def get_all_symbols_from_stock_scores(*, candidates_only: bool = False) -> list[str]:
    """Retourne les symboles distincts présents dans stock_scores."""
    where_clause = "WHERE is_candidate = 1" if candidates_only else ""
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


def resolve_symbols_from_inputs(
    *,
    symbols_csv: str | None,
    symbol_source: str,
    repository: EventSentimentRepository,
    logger: logging.Logger | None = None,
) -> tuple[list[str], str]:
    if symbols_csv:
        return _normalize_symbols(symbols_csv.split(",")), "explicit"

    if symbol_source == "candidates":
        return _normalize_symbols(repository.load_candidate_symbols()), "candidates"

    if symbol_source == "stock_bars_daily":
        return _normalize_symbols(get_all_symbols_from_stock_bars_daily()), "stock_bars_daily"

    if symbol_source == "stock_scores_history":
        return _normalize_symbols(get_all_symbols_from_stock_scores_history()), "stock_scores_history"

    if symbol_source == "stock_scores_all":
        return _normalize_symbols(get_all_symbols_from_stock_scores_all()), "stock_scores_all"

    if symbol_source != "stock_scores" and logger is not None:
        logger.warning("Source de symboles inconnue '%s' ; fallback stock_scores.", symbol_source)
    return _normalize_symbols(get_all_symbols_from_stock_scores(candidates_only=False)), "stock_scores"


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
            "Préférez --symbol-source stock_scores / candidates, une shortlist --symbols ou un cap --max-symbols.",
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

# python ./event_sentiment/importe_news.py --start-date 2025-01-01 --end-date 2025-04-20

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Importe les news sur une période donnée pour un univers de symboles ciblé. "
            "Par défaut, l'univers provient de stock_scores pour éviter les imports trop larges."
        )
    )
    parser.add_argument("--start-date", type=str, required=True, help="Date de début au format YYYY-MM-DD (ex: 2024-05-06)")
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
        choices=("stock_scores", "stock_scores_history", "stock_scores_all", "candidates", "stock_bars_daily"),
        default="stock_scores",
        help=(
            "Source des symboles à importer. 'stock_scores' (défaut) limite l'univers aux symboles suivis "
            "par le screener ; 'stock_scores_history' cible les symboles déjà présents dans l'historique PIT ; "
            "'stock_scores_all' cible l'union dédupliquée des symboles présents dans stock_scores ou stock_scores_history ; "
            "'candidates' limite à stock_scores.is_candidate=1 ; 'stock_bars_daily' conserve l'ancien comportement large."
        ),
    )
    parser.add_argument(
        "--news-provider",
        type=str,
        choices=("alpaca", "finnhub"),
        default="alpaca",
        help="Source de news utilisée pour l'ingestion brute.",
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
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
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
    ingestion = NewsIngestionService(repository=repository, config=config)

    batch_size = max(1, int(args.batch_size))
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        logger.info(f"Traitement batch {i//batch_size+1} ({len(batch)} symbols): {batch}")
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

