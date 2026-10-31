"""Retire les anciennes estimations de date, sans effacer leur preuve.

Seule une réponse d'annonce Finnhub avec un réalisé, une année et un trimestre
permet ce rapprochement. Un réalisé SEC daté du dépôt ne le permet pas.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Index, MetaData, String, Table, Text, and_, select

LOGGER = logging.getLogger(__name__)


def correction_table() -> Table:
    table = Table(
        "stock_earnings_calendar_date_corrections", MetaData(),
        Column("correction_id", String(32), primary_key=True),
        Column("symbol", String(20), nullable=False),
        Column("old_earnings_date", Date, nullable=False),
        Column("replacement_earnings_date", Date, nullable=False),
        Column("observed_at", DateTime, nullable=False),
        Column("provider", String(32), nullable=False),
        Column("original_row_json", Text, nullable=False),
        Column("replacement_evidence_json", Text, nullable=False),
    )
    Index("ix_earnings_date_correction_symbol", table.c.symbol, table.c.old_earnings_date)
    return table


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _actual(row):
    for key in ("eps_actual", "revenue_actual"):
        value = row.get(key)
        try:
            if value is not None and math.isfinite(float(value)):
                return True
        except (ValueError, TypeError):
            continue
    return False


def filter_superseded_forecasts(connection, calendar, archive, rows):
    """Une répétition de l'ancienne prévision ne ressuscite pas sa fausse date."""
    symbols = {row["symbol"] for row in rows if row.get("_calendar_evidence")}
    if not symbols:
        return rows
    corrections = list(connection.execute(select(archive).where(archive.c.symbol.in_(symbols))).mappings())
    retained = []
    for row in rows:
        proof = row.get("_calendar_evidence") or {}
        blocked = False
        if proof.get("provider") == "finnhub" and not _actual(row):
            for correction in corrections:
                if correction["symbol"] != row["symbol"] or _day(correction["old_earnings_date"]) != _day(row["earnings_date"]):
                    continue
                old_proof = json.loads(correction["replacement_evidence_json"])
                if (str(proof.get("fiscal_year")) != str(old_proof["_calendar_evidence"].get("fiscal_year"))
                        or str(row.get("fiscal_period")) != str(old_proof.get("fiscal_period"))):
                    continue
                target = connection.execute(select(calendar).where(and_(
                    calendar.c.symbol == row["symbol"],
                    calendar.c.earnings_date == correction["replacement_earnings_date"],
                    calendar.c.fiscal_period == str(row["fiscal_period"]),
                )).with_for_update()).mappings().first()
                if target is not None and _actual(target):
                    blocked = True
                    LOGGER.info("Earnings: estimation de date déjà remplacée ignorée | symbol=%s date=%s", row["symbol"], row["earnings_date"])
                    break
        if not blocked:
            retained.append(row)
    return retained


def reconcile_confirmed_dates(connection, calendar, archive, evidence_rows):
    """Archive + suppression atomiques, sous le verrou des lignes du calendrier.

Une période '3' héritée n'identifie pas une année : le rapprochement est donc
limité à 30 jours autour de l'annonce et refusé en présence de deux réalisés.
Les snapshots d'univers déjà publiés ne sont jamais modifiés.
"""
    corrected = 0
    for evidence in evidence_rows:
        proof = evidence.get("_calendar_evidence") or {}
        if proof.get("provider") != "finnhub" or not _actual(evidence):
            continue
        try:
            quarter = str(int(evidence.get("fiscal_period")))
            fiscal_year = int(proof["fiscal_year"])
            target_date = _day(evidence["earnings_date"])
            stamp = datetime.fromisoformat(proof["observed_at"])
            if stamp.tzinfo is None:
                continue
            observed = stamp.astimezone(timezone.utc).replace(tzinfo=None)
        except (ValueError, TypeError, KeyError):
            continue
        if quarter not in {"1", "2", "3", "4"} or not 1900 <= fiscal_year <= 2200:
            continue
        if target_date > observed.date():
            continue
        scope = and_(
            calendar.c.symbol == evidence["symbol"],
            calendar.c.fiscal_period == quarter,
            calendar.c.earnings_date.between(target_date-timedelta(days=30), target_date+timedelta(days=30)),
        )
        nearby = list(connection.execute(select(calendar).where(scope).with_for_update()).mappings())
        actuals = [row for row in nearby if _actual(row)]
        if len(actuals) != 1 or _day(actuals[0]["earnings_date"]) != target_date:
            continue
        canonical = actuals[0]
        for row in nearby:
            old_date = _day(row["earnings_date"])
            if old_date == target_date or _actual(row):
                continue
            updated = row.get("last_updated")
            if updated is None or datetime.fromisoformat(str(updated)) >= observed:
                continue
            if "instrument_id" in calendar.c and (
                not row.get("instrument_id") or row["instrument_id"] != canonical["instrument_id"]
            ):
                continue
            connection.execute(archive.insert().values(
                correction_id=uuid4().hex, symbol=row["symbol"], old_earnings_date=old_date,
                replacement_earnings_date=target_date, observed_at=observed, provider="finnhub",
                original_row_json=json.dumps(dict(row), default=str, sort_keys=True),
                replacement_evidence_json=json.dumps(evidence, default=str, sort_keys=True),
            ))
            connection.execute(calendar.delete().where(and_(scope, calendar.c.earnings_date == old_date)))
            LOGGER.info("Earnings: ancienne date archivée et remplacée | symbol=%s ancienne=%s confirmée=%s", row["symbol"], old_date, target_date)
            corrected += 1
    return corrected
