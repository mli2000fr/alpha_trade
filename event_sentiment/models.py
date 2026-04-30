from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedNewsArticle:
    article_id: str
    headline: str
    summary: str | None
    content: str | None
    source: str
    author: str | None
    url: str | None
    published_at_utc: datetime
    event_timestamp_utc: datetime
    event_timestamp_ny: datetime
    effective_trade_date: date
    market_session_tag: str
    tickers: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    is_major_event: int = 0


@dataclass(frozen=True, slots=True)
class SentimentRecord:
    article_id: str
    model_name: str
    model_version: str
    text_strategy: str
    text_hash: str
    truncated: int
    max_length_tokens: int
    sentiment_label: str
    positive_score: float
    neutral_score: float
    negative_score: float
    sentiment_confidence: float
    sentiment_net_score: float
    inference_status: str = "success"
    error_message: str | None = None
    model_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class MacroImpactRecord:
    article_id: str
    trade_date: date
    sector: str
    macro_event_type: str
    impact_direction: str
    impact_score: float
    macro_event_intensity: float
    rule_version: str
    rule_hits: dict[str, Any]
    explanation_text: str

