"""Patterns calendaires : Tax Day, Sept Slump, Santa, January, OpEx, Month-End."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from service.market.config import CalendarPatternConfig, MarketRegimesConfig


@dataclass(frozen=True, slots=True)
class CalendarPatternHit:
    name: str
    risk_mult: float
    screener_expansion_pct: float
    sentiment_threshold_addon: float
    block_new_entries: bool


def _in_md_window(d: date, start_md: str, end_md: str) -> bool:
    """Test "MM-DD" inclusif (gère les fenêtres traversant l'année)."""
    try:
        sm, sd = (int(x) for x in start_md.split("-"))
        em, ed = (int(x) for x in end_md.split("-"))
    except ValueError:
        return False
    cur = (d.month, d.day)
    a = (sm, sd)
    b = (em, ed)
    if a <= b:
        return a <= cur <= b
    # fenêtre traversant l'année (ex 12-20 → 01-05)
    return cur >= a or cur <= b


def is_third_friday(d: date) -> bool:
    """Retourne True si ``d`` est le 3e vendredi du mois (OpEx US classique)."""
    if d.weekday() != 4:  # Friday
        return False
    # 3e vendredi = jour entre 15 et 21 inclus
    return 15 <= d.day <= 21


def is_month_end_window(d: date, business_days_from_end: int) -> bool:
    """True si ``d`` est dans les ``N`` derniers jours ouvrés du mois."""
    last_day = calendar.monthrange(d.year, d.month)[1]
    end = date(d.year, d.month, last_day)
    # reculer en sautant les week-ends
    bd_remaining = business_days_from_end
    cursor = end
    while cursor.weekday() >= 5:  # 5=Sat, 6=Sun
        cursor -= timedelta(days=1)
    while bd_remaining > 0:
        cursor -= timedelta(days=1)
        while cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
        bd_remaining -= 1
    return cursor <= d <= end


def evaluate_pattern(name: str, cfg: CalendarPatternConfig, d: date) -> CalendarPatternHit | None:
    """Retourne un hit si le pattern est actif au ``trade_date`` ``d``."""
    if not cfg.enabled:
        return None
    active = False
    if cfg.rule == "3rd_friday":
        active = is_third_friday(d)
    elif cfg.business_days_from_month_end is not None:
        active = is_month_end_window(d, cfg.business_days_from_month_end)
    else:
        active = _in_md_window(d, cfg.start, cfg.end)
    if not active:
        return None
    block = cfg.block_new_entries or (cfg.mode == "block_entries")
    return CalendarPatternHit(
        name=name,
        risk_mult=cfg.risk_mult,
        screener_expansion_pct=cfg.screener_expansion_pct,
        sentiment_threshold_addon=cfg.sentiment_threshold_addon,
        block_new_entries=block,
    )


def evaluate_calendar_patterns(
    cfg: MarketRegimesConfig, trade_date: date
) -> list[CalendarPatternHit]:
    hits: list[CalendarPatternHit] = []
    for name, pattern in cfg.patterns.items():
        hit = evaluate_pattern(name, pattern, trade_date)
        if hit is not None:
            hits.append(hit)
    return hits


__all__ = [
    "CalendarPatternHit",
    "evaluate_pattern",
    "evaluate_calendar_patterns",
    "is_third_friday",
    "is_month_end_window",
]

