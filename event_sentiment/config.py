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
    initial_backfill_days: int = 365
    candidate_reactivation_backfill_days: int = 365

    finbert_model_name: str = "ProsusAI/finbert"
    finbert_model_version: str = "finbert_v1"
    finbert_model_revision: str | None = None
    finbert_batch_size: int = 16
    finbert_max_length: int = 256

    allow_sector_fallback: bool = True
    sentiment_pending_limit: int = 1000
    feature_version: str = "v2"
    macro_rule_version: str = "macro_rules_v1"
    feature_rolling_windows: tuple[int, ...] = (3, 5, 10, 20)
    feature_history_buffer_days: int = 45
    bootstrap_default_years: int = 10
    bootstrap_batch_days: int = 63

    def __post_init__(self) -> None:
        if self.page_limit < 1:
            raise ValueError("page_limit doit être >= 1.")
        if self.sleep_between_requests < 0:
            raise ValueError("sleep_between_requests doit être >= 0.")
        if self.checkpoint_overlap_minutes < 0:
            raise ValueError("checkpoint_overlap_minutes doit être >= 0.")
        if self.initial_backfill_days < 1:
            raise ValueError("initial_backfill_days doit être >= 1.")
        if self.candidate_reactivation_backfill_days < 1:
            raise ValueError("candidate_reactivation_backfill_days doit être >= 1.")
        if self.finbert_batch_size < 1:
            raise ValueError("finbert_batch_size doit être >= 1.")
        if self.finbert_max_length < 32:
            raise ValueError("finbert_max_length doit être >= 32.")
        if self.sentiment_pending_limit < 1:
            raise ValueError("sentiment_pending_limit doit être >= 1.")
        if not self.feature_rolling_windows:
            raise ValueError("feature_rolling_windows ne doit pas être vide.")
        if any(window < 2 for window in self.feature_rolling_windows):
            raise ValueError("feature_rolling_windows doit contenir des fenêtres >= 2.")
        if tuple(sorted(set(self.feature_rolling_windows))) != self.feature_rolling_windows:
            raise ValueError("feature_rolling_windows doit être trié, sans doublons.")
        if self.feature_history_buffer_days < max(self.feature_rolling_windows):
            raise ValueError("feature_history_buffer_days doit couvrir au moins la plus grande fenêtre rolling.")
        if self.bootstrap_default_years < 1:
            raise ValueError("bootstrap_default_years doit être >= 1.")
        if self.bootstrap_batch_days < 1:
            raise ValueError("bootstrap_batch_days doit être >= 1.")

