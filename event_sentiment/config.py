from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EventSentimentConfig:
    source_name: str = "alpaca_news"
    provider_name: str = "alpaca"
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    page_limit: int = 50
    sleep_between_requests: float = 0.35
    regular_session_maps_to_same_day: bool = False
    checkpoint_overlap_minutes: int = 60
    initial_backfill_days: int = 7

    finbert_model_name: str = "ProsusAI/finbert"
    finbert_model_version: str = "finbert_v1"
    finbert_batch_size: int = 16
    finbert_max_length: int = 256

    allow_sector_fallback: bool = True
    sentiment_pending_limit: int = 1000
    feature_version: str = "v1"
    macro_rule_version: str = "macro_rules_v1"

    def __post_init__(self) -> None:
        if self.page_limit < 1:
            raise ValueError("page_limit doit être >= 1.")
        if self.sleep_between_requests < 0:
            raise ValueError("sleep_between_requests doit être >= 0.")
        if self.checkpoint_overlap_minutes < 0:
            raise ValueError("checkpoint_overlap_minutes doit être >= 0.")
        if self.initial_backfill_days < 1:
            raise ValueError("initial_backfill_days doit être >= 1.")
        if self.finbert_batch_size < 1:
            raise ValueError("finbert_batch_size doit être >= 1.")
        if self.finbert_max_length < 32:
            raise ValueError("finbert_max_length doit être >= 32.")
        if self.sentiment_pending_limit < 1:
            raise ValueError("sentiment_pending_limit doit être >= 1.")

