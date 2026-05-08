import argparse
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from common.utils import configure_root_logging
from database.connection import get_sqlalchemy_engine
from event_sentiment.ingestion import NewsIngestionService
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository


def get_all_symbols_from_stock_bars_daily():
    """Retourne tous les symboles distincts présents dans stock_bars_daily."""
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT symbol FROM stock_bars_daily")).fetchall()
        return [row[0] for row in result]

# python ./event_sentiment/importe_news.py --start-date 2025-01-01 --end-date 2025-04-20

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importe les news pour tous les symbols présents dans stock_bars_daily sur une période donnée."
    )
    parser.add_argument("--start-date", type=str, required=True, help="Date de début au format YYYY-MM-DD (ex: 2024-05-06)")
    parser.add_argument("--end-date", type=str, required=False, help="Date de fin au format YYYY-MM-DD (ex: 2024-05-10). Par défaut: aujourd'hui.")
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
        help="Mode de mapping article → ticker réutilisé lors de l'import brut.",
    )
    parser.add_argument(
        "--min-relevance-score",
        type=float,
        default=None,
        help="Seuil minimum de pertinence [0,1] quand le mode 'scored' est actif.",
    )
    return parser


def main():

    args = build_arg_parser().parse_args()

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

    logger.info(f"Récupération des symbols depuis stock_bars_daily ...")
    symbols = get_all_symbols_from_stock_bars_daily()
    logger.info(f"{len(symbols)} symbols trouvés.")

    repository = EventSentimentRepository()
    config_overrides: dict[str, object] = {
        "provider_ticker_relevance_mode": args.ticker_relevance_mode,
    }
    if args.min_relevance_score is not None:
        config_overrides["min_relevance_score"] = float(args.min_relevance_score)
    config = EventSentimentConfig.for_provider(args.news_provider, **config_overrides)
    ingestion = NewsIngestionService(repository=repository, config=config)

    batch_size = 20
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

