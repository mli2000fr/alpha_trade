"""Repository canonique des marchés, instruments et symboles fournisseurs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from common.config_loader import load_market_registry
from common.market_context import (
    MarketCode,
    MarketCompatibilityError,
    MarketRegistry,
)
from database.repositories._base import Repository

_INSTRUMENT_NAMESPACE = UUID("4d849de4-86ee-4d4d-a706-88d16baf7e88")

MARKET_MICS: Mapping[MarketCode, frozenset[str]] = {
    MarketCode.US_EQ: frozenset({"XNAS", "XNYS", "XASE", "ARCX", "BATS"}),
    MarketCode.CN_A: frozenset({"XSHG", "XSHE"}),
    MarketCode.CN_BJ: frozenset({"BJSE"}),
}

_LIST_FILTER_COLUMNS = {
    "exchange_mic": "i.exchange_mic",
    "currency": "i.currency",
    "instrument_type": "i.instrument_type",
    "mapping_status": "i.mapping_status",
    "is_active": "i.is_active",
}


class InstrumentIdentityError(ValueError):
    """Identité ou période instrument incohérente."""


class InstrumentAmbiguityError(LookupError):
    """Plusieurs instruments correspondent à une identité censée être unique."""


def _as_date(value: date | str, name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise InstrumentIdentityError(f"{name} doit être une date ISO") from exc


def _clean(value: str, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise InstrumentIdentityError(f"{name} est obligatoire")
    return normalized


def build_instrument_uid(
    market_code: MarketCode | str,
    exchange_mic: str,
    canonical_identity: str,
) -> str:
    """Construit un UUID stable depuis une identité contrôlée.

    canonical_identity doit être une identité durable validée lors de
    l'onboarding. Un changement futur de ticker ne doit jamais recalculer cet UID.
    """

    code = MarketCode(str(market_code).upper())
    mic = _clean(exchange_mic, "exchange_mic").upper()
    identity = _clean(canonical_identity, "canonical_identity")
    return str(uuid5(_INSTRUMENT_NAMESPACE, f"{code.value}|{mic}|{identity}"))


def assert_market_mic(market_code: MarketCode | str, exchange_mic: str) -> None:
    code = market_code if isinstance(market_code, MarketCode) else MarketCode(str(market_code).upper())
    mic = _clean(exchange_mic, "exchange_mic").upper()
    if mic not in MARKET_MICS[code]:
        raise MarketCompatibilityError(f"MIC {mic!r} incompatible avec le marché {code.value}")


class InstrumentRepository(Repository):
    """Accès au référentiel canonique sans modifier les tables historiques."""

    def __init__(
        self,
        *,
        engine=None,
        registry: MarketRegistry | None = None,
    ) -> None:
        super().__init__(engine=engine)
        self._registry = registry or load_market_registry()

    def resolve_instrument(
        self,
        market_code: MarketCode | str,
        mic: str,
        local_symbol: str,
    ) -> RowMapping[str, Any] | None:
        context = self._registry.resolve(market_code)
        normalized_mic = _clean(mic, "mic").upper()
        assert_market_mic(context.market_code, normalized_mic)
        params = {
            "market_code": context.market_code.value,
            "mic": normalized_mic,
            "local_symbol": _clean(local_symbol, "local_symbol").upper(),
        }
        statement = text(
            """
            SELECT i.*
            FROM instruments i
            WHERE i.market_code = :market_code
              AND i.exchange_mic = :mic
              AND i.local_symbol = :local_symbol
            """
        )
        with self.connect() as conn:
            rows = conn.execute(statement, params).mappings().all()
        return self._one_or_none(rows, "instrument")

    def resolve_local_symbol(
        self,
        market_code: MarketCode | str,
        local_symbol: str,
    ) -> RowMapping[str, Any] | None:
        """Résout un symbole canonique dans un marché.

        Cette méthode est le pont de compatibilité des appels historiques qui
        ne connaissent encore que ``symbol``. Une ambiguïté entre deux places
        du même marché est volontairement bloquante : le consommateur doit
        alors fournir le MIC ou directement ``instrument_id``.
        """
        context = self._registry.resolve(market_code)
        params = {
            "market_code": context.market_code.value,
            "local_symbol": _clean(local_symbol, "local_symbol").upper(),
        }
        statement = text(
            """
            SELECT i.*
            FROM instruments i
            WHERE i.market_code = :market_code
              AND i.local_symbol = :local_symbol
            ORDER BY i.is_active DESC, i.instrument_id
            """
        )
        with self.connect() as conn:
            rows = conn.execute(statement, params).mappings().all()
        return self._one_or_none(rows, "local symbol")

    def resolve_provider_symbol(
        self,
        provider: str,
        provider_symbol: str,
        as_of: date | str,
    ) -> RowMapping[str, Any] | None:
        params = {
            "provider": _clean(provider, "provider").lower(),
            "provider_symbol": _clean(provider_symbol, "provider_symbol"),
            "as_of": _as_date(as_of, "as_of"),
        }
        statement = text(
            """
            SELECT i.*, ips.mapping_id, ips.provider, ips.provider_symbol,
                   ips.provider_exchange, ips.valid_from AS mapping_valid_from,
                   ips.valid_to AS mapping_valid_to, ips.is_primary
            FROM instrument_provider_symbols ips
            JOIN instruments i ON i.instrument_id = ips.instrument_id
            WHERE ips.provider = :provider
              AND ips.provider_symbol = :provider_symbol
              AND ips.valid_from <= :as_of
              AND (ips.valid_to IS NULL OR ips.valid_to >= :as_of)
            ORDER BY ips.is_primary DESC, ips.valid_from DESC
            """
        )
        with self.connect() as conn:
            rows = conn.execute(statement, params).mappings().all()
        return self._one_or_none(rows, "provider symbol")

    def list_instruments(
        self,
        market_code: MarketCode | str,
        as_of: date | str,
        filters: Mapping[str, Any] | None = None,
    ) -> list[RowMapping[str, Any]]:
        context = self._registry.resolve(market_code)
        effective_date = _as_date(as_of, "as_of")
        filters = dict(filters or {})
        unknown = set(filters) - set(_LIST_FILTER_COLUMNS)
        if unknown:
            raise InstrumentIdentityError(f"Filtres instrument non supportés : {sorted(unknown)}")

        clauses = [
            "i.market_code = :market_code",
            "(i.listing_date IS NULL OR i.listing_date <= :as_of)",
            "(i.delisting_date IS NULL OR i.delisting_date >= :as_of)",
        ]
        params: dict[str, Any] = {
            "market_code": context.market_code.value,
            "as_of": effective_date,
        }
        for index, (name, value) in enumerate(filters.items()):
            parameter = f"filter_{index}"
            clauses.append(f"{_LIST_FILTER_COLUMNS[name]} = :{parameter}")
            params[parameter] = value

        statement = text(
            "SELECT i.* FROM instruments i WHERE " + " AND ".join(clauses) + " ORDER BY i.exchange_mic, i.local_symbol"
        )
        with self.connect() as conn:
            return list(conn.execute(statement, params).mappings().all())

    def load_status_asof(
        self,
        instrument_id: int,
        as_of: date | str,
    ) -> RowMapping[str, Any] | None:
        params = {
            "instrument_id": int(instrument_id),
            "as_of": _as_date(as_of, "as_of"),
        }
        statement = text(
            """
            SELECT ish.*
            FROM instrument_status_history ish
            WHERE ish.instrument_id = :instrument_id
              AND ish.valid_from <= :as_of
              AND (ish.valid_to IS NULL OR ish.valid_to >= :as_of)
            ORDER BY ish.available_at DESC, ish.status_id DESC
            """
        )
        with self.connect() as conn:
            rows = conn.execute(statement, params).mappings().all()
        return self._one_or_none(rows, "instrument status")

    def create_instrument(
        self,
        *,
        market_code: MarketCode | str,
        exchange_mic: str,
        local_symbol: str,
        canonical_identity: str,
        currency: str,
        display_name: str | None = None,
        instrument_type: str = "equity",
        listing_date: date | str | None = None,
        delisting_date: date | str | None = None,
    ) -> int:
        context = self._registry.resolve(market_code, require_enabled=True)
        mic = _clean(exchange_mic, "exchange_mic").upper()
        assert_market_mic(context.market_code, mic)
        normalized_currency = _clean(currency, "currency").upper()
        if normalized_currency != context.currency:
            raise MarketCompatibilityError(f"{context.market_code.value} requiert currency={context.currency}")
        start = _as_date(listing_date, "listing_date") if listing_date else None
        end = _as_date(delisting_date, "delisting_date") if delisting_date else None
        if start and end and end < start:
            raise InstrumentIdentityError("delisting_date précède listing_date")

        params = {
            "instrument_uid": build_instrument_uid(context.market_code, mic, canonical_identity),
            "market_code": context.market_code.value,
            "exchange_mic": mic,
            "local_symbol": _clean(local_symbol, "local_symbol").upper(),
            "display_name": display_name,
            "instrument_type": _clean(instrument_type, "instrument_type").lower(),
            "currency": normalized_currency,
            "listing_date": start,
            "delisting_date": end,
        }
        statement = text(
            """
            INSERT INTO instruments (
                instrument_uid, market_code, exchange_mic, local_symbol,
                display_name, instrument_type, currency, listing_date,
                delisting_date, mapping_status, is_active
            ) VALUES (
                :instrument_uid, :market_code, :exchange_mic, :local_symbol,
                :display_name, :instrument_type, :currency, :listing_date,
                :delisting_date, 'mapped', TRUE
            )
            """
        )
        with self.transaction() as conn:
            result = conn.execute(statement, params)
            return int(result.lastrowid)

    def add_provider_symbol(
        self,
        *,
        instrument_id: int,
        provider: str,
        provider_symbol: str,
        valid_from: date | str,
        valid_to: date | str | None = None,
        provider_exchange: str | None = None,
        is_primary: bool = True,
    ) -> int:
        start = _as_date(valid_from, "valid_from")
        end = _as_date(valid_to, "valid_to") if valid_to else None
        if end and end < start:
            raise InstrumentIdentityError("valid_to précède valid_from")
        params = {
            "instrument_id": int(instrument_id),
            "provider": _clean(provider, "provider").lower(),
            "provider_symbol": _clean(provider_symbol, "provider_symbol"),
            "provider_exchange": provider_exchange,
            "valid_from": start,
            "valid_to": end,
            "is_primary": bool(is_primary),
        }
        with self.transaction() as conn:
            suffix = " FOR UPDATE" if conn.dialect.name in {"mysql", "mariadb"} else ""
            overlap = conn.execute(
                text(
                    """
                    SELECT mapping_id
                    FROM instrument_provider_symbols
                    WHERE provider = :provider
                      AND provider_symbol = :provider_symbol
                      AND valid_from <= COALESCE(:valid_to, '9999-12-31')
                      AND COALESCE(valid_to, '9999-12-31') >= :valid_from
                    """
                    + suffix
                ),
                params,
            ).first()
            if overlap is not None:
                raise InstrumentIdentityError("Période chevauchante pour ce symbole fournisseur")
            if is_primary:
                primary = conn.execute(
                    text(
                        """
                        SELECT mapping_id
                        FROM instrument_provider_symbols
                        WHERE instrument_id = :instrument_id
                          AND provider = :provider
                          AND is_primary = TRUE
                          AND valid_from <= COALESCE(:valid_to, '9999-12-31')
                          AND COALESCE(valid_to, '9999-12-31') >= :valid_from
                        """
                        + suffix
                    ),
                    params,
                ).first()
                if primary is not None:
                    raise InstrumentIdentityError("Deux mappings primaires actifs pour instrument/provider")
            result = conn.execute(
                text(
                    """
                    INSERT INTO instrument_provider_symbols (
                        instrument_id, provider, provider_symbol,
                        provider_exchange, valid_from, valid_to, is_primary
                    ) VALUES (
                        :instrument_id, :provider, :provider_symbol,
                        :provider_exchange, :valid_from, :valid_to, :is_primary
                    )
                    """
                ),
                params,
            )
            return int(result.lastrowid)

    @staticmethod
    def _one_or_none(
        rows: list[RowMapping[str, Any]],
        identity_name: str,
    ) -> RowMapping[str, Any] | None:
        if not rows:
            return None
        if len(rows) > 1:
            raise InstrumentAmbiguityError(f"Résolution ambiguë pour {identity_name}: {len(rows)} lignes")
        return rows[0]


__all__ = [
    "InstrumentAmbiguityError",
    "InstrumentIdentityError",
    "InstrumentRepository",
    "MARKET_MICS",
    "assert_market_mic",
    "build_instrument_uid",
]
