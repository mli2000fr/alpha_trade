from __future__ import annotations

from typing import TYPE_CHECKING

from .config import EventSentimentConfig

if TYPE_CHECKING:
    from .pipeline import EventSentimentPipeline

__all__ = ["EventSentimentConfig", "EventSentimentPipeline"]


def __getattr__(name: str):
    if name == "EventSentimentPipeline":
        from .pipeline import EventSentimentPipeline

        return EventSentimentPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


