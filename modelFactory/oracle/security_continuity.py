"""Security-continuity rules used by Oracle labels and feature construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "data_quality"
    / "security_discontinuities.json"
)


@dataclass(frozen=True, slots=True)
class SecurityDiscontinuity:
    symbol: str
    last_predecessor_date: pd.Timestamp
    first_successor_date: pd.Timestamp
    reason: str

    def crosses(self, start: pd.Timestamp, end: pd.Timestamp) -> bool:
        """Return True when a target path joins predecessor and successor."""
        return start <= self.last_predecessor_date and end >= self.first_successor_date


def load_security_discontinuities(
    path: str | Path | None = None,
) -> dict[str, tuple[SecurityDiscontinuity, ...]]:
    """Load the reviewed security-identity breaks, grouped by upper-case symbol."""
    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        return {}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[SecurityDiscontinuity]] = {}
    for raw in payload.get("discontinuities", []):
        symbol = str(raw["symbol"]).strip().upper()
        event = SecurityDiscontinuity(
            symbol=symbol,
            last_predecessor_date=pd.Timestamp(raw["last_predecessor_date"]).normalize(),
            first_successor_date=pd.Timestamp(raw["first_successor_date"]).normalize(),
            reason=str(raw.get("reason") or "known_security_discontinuity"),
        )
        if event.first_successor_date <= event.last_predecessor_date:
            raise ValueError(f"Invalid security discontinuity for {symbol}: {raw}")
        grouped.setdefault(symbol, []).append(event)
    return {
        symbol: tuple(sorted(events, key=lambda event: event.first_successor_date))
        for symbol, events in grouped.items()
    }


def path_crosses_known_discontinuity(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    registry: dict[str, tuple[SecurityDiscontinuity, ...]],
) -> bool:
    return any(
        event.crosses(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())
        for event in registry.get(str(symbol).strip().upper(), ())
    )


def split_frame_on_discontinuities(
    frame: pd.DataFrame,
    symbol: str,
    registry: dict[str, tuple[SecurityDiscontinuity, ...]],
) -> Iterable[pd.DataFrame]:
    """Yield independent price-history segments; rolling features cannot cross a break."""
    ordered = frame.sort_values("date").copy()
    if ordered.empty:
        return
    dates = pd.to_datetime(ordered["date"]).dt.normalize()
    segment = pd.Series(0, index=ordered.index, dtype=int)
    for event in registry.get(str(symbol).strip().upper(), ()):
        segment = segment + dates.ge(event.first_successor_date).astype(int)
    for _, part in ordered.groupby(segment, sort=True):
        if not part.empty:
            yield part.copy()


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "SecurityDiscontinuity",
    "load_security_discontinuities",
    "path_crosses_known_discontinuity",
    "split_frame_on_discontinuities",
]
