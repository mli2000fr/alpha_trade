import argparse
import logging

import dateutil.parser

from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.pipeline import EventSentimentPipeline


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline Event Sentiment basée sur FinBERT")
    parser.add_argument("--start-utc", type=str, default=None, help="Fenêtre UTC de début, ex: 2026-01-01T00:00:00Z")
    parser.add_argument("--end-utc", type=str, default=None, help="Fenêtre UTC de fin, ex: 2026-01-31T23:59:59Z")
    parser.add_argument("--symbols", type=str, default=None, help="Liste optionnelle de symboles, séparés par des virgules")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args()

    start_utc = dateutil.parser.isoparse(args.start_utc) if args.start_utc else None
    end_utc = dateutil.parser.isoparse(args.end_utc) if args.end_utc else None
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",")] if args.symbols else None

    repository = EventSentimentRepository()
    config = EventSentimentConfig()
    pipeline = EventSentimentPipeline(repository=repository, config=config)
    pipeline.run(start_utc=start_utc, end_utc=end_utc, symbols=symbols)

