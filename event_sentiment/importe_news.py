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


def main():
    parser = argparse.ArgumentParser(description="Importe les news pour tous les symbols présents dans stock_bars_daily sur une période donnée.")
    parser.add_argument("--start-date", type=str, required=True, help="Date de début au format YYYY-MM-DD (ex: 2024-05-06)")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
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
    config = EventSentimentConfig()
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

