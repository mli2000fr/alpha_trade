"""Contrat immuable de marché et registre de contextes configurés.

Sprint 1 introduit le scope marché sans modifier le comportement US. Aucun
état global mutable n'est utilisé : un contexte résolu est passé explicitement
aux traitements qui l'adopteront dans les sprints suivants.
"""

from __future__ import annotations

import hashlib
import json
import logging
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

LOGGER = logging.getLogger(__name__)


class MarketCompatibilityError(ValueError):
    """Le marché demandé est inconnu ou incompatible avec sa configuration."""


class MarketCode(StrEnum):
    US_EQ = "US_EQ"
    CN_A = "CN_A"
    CN_BJ = "CN_BJ"


_DATABASE_ALLOWLIST: Mapping[MarketCode, frozenset[str]] = MappingProxyType(
    {
        MarketCode.US_EQ: frozenset({"us_primary"}),
        MarketCode.CN_A: frozenset({"cn_primary"}),
        MarketCode.CN_BJ: frozenset({"cn_primary"}),
    }
)
_EXPECTED_COUNTRY: Mapping[MarketCode, str] = MappingProxyType(
    {
        MarketCode.US_EQ: "US",
        MarketCode.CN_A: "CN",
        MarketCode.CN_BJ: "CN",
    }
)
_EXPECTED_CURRENCY: Mapping[MarketCode, str] = MappingProxyType(
    {
        MarketCode.US_EQ: "USD",
        MarketCode.CN_A: "CNY",
        MarketCode.CN_BJ: "CNY",
    }
)
_EXPECTED_TIMEZONE: Mapping[MarketCode, str] = MappingProxyType(
    {
        MarketCode.US_EQ: "America/New_York",
        MarketCode.CN_A: "Asia/Shanghai",
        MarketCode.CN_BJ: "Asia/Shanghai",
    }
)
_EXPECTED_CALENDAR: Mapping[MarketCode, str] = MappingProxyType(
    {
        MarketCode.US_EQ: "NYSE",
        MarketCode.CN_A: "CN_A",
        MarketCode.CN_BJ: "CN_BJ",
    }
)


def _required_text(payload: Mapping[str, Any], name: str) -> str:
    value = str(payload.get(name) or "").strip()
    if not value:
        raise MarketCompatibilityError(f"Champ marché obligatoire absent ou vide : {name}")
    return value


def _required_bool(payload: Mapping[str, Any], name: str) -> bool:
    value = payload.get(name)
    if not isinstance(value, bool):
        raise MarketCompatibilityError(f"{name} doit être un booléen YAML")
    return value


def _string_set(values: Any, name: str) -> frozenset[str]:
    if values is None:
        return frozenset()
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise MarketCompatibilityError(f"{name} doit être une liste de chaînes")
    normalized = frozenset(str(value).strip() for value in values if str(value).strip())
    if len(normalized) != len(values):
        raise MarketCompatibilityError(f"{name} contient une valeur vide ou dupliquée")
    return normalized


@dataclass(frozen=True, slots=True)
class MarketContext:
    market_code: MarketCode
    database_alias: str
    country_code: str
    currency: str
    timezone: str
    calendar_id: str
    benchmark_instrument: str
    sector_taxonomy: str
    cost_profile: str
    execution_rules_profile: str
    feature_profile_root: str
    enabled: bool
    live_enabled: bool
    short_execution_enabled: bool
    capabilities: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        for name in (
            "database_alias",
            "country_code",
            "currency",
            "timezone",
            "calendar_id",
            "benchmark_instrument",
            "sector_taxonomy",
            "cost_profile",
            "execution_rules_profile",
            "feature_profile_root",
        ):
            if not str(getattr(self, name)).strip():
                raise MarketCompatibilityError(f"Champ marché vide : {name}")

        if self.database_alias not in _DATABASE_ALLOWLIST[self.market_code]:
            raise MarketCompatibilityError(
                f"{self.market_code.value} incompatible avec database_alias={self.database_alias!r}"
            )
        if self.country_code != _EXPECTED_COUNTRY[self.market_code]:
            raise MarketCompatibilityError(
                f"{self.market_code.value} requiert country_code={_EXPECTED_COUNTRY[self.market_code]}"
            )
        if self.currency != _EXPECTED_CURRENCY[self.market_code]:
            raise MarketCompatibilityError(
                f"{self.market_code.value} requiert currency={_EXPECTED_CURRENCY[self.market_code]}"
            )
        if self.timezone != _EXPECTED_TIMEZONE[self.market_code]:
            raise MarketCompatibilityError(
                f"{self.market_code.value} requiert timezone={_EXPECTED_TIMEZONE[self.market_code]}"
            )
        if self.calendar_id != _EXPECTED_CALENDAR[self.market_code]:
            raise MarketCompatibilityError(
                f"{self.market_code.value} requiert calendar_id={_EXPECTED_CALENDAR[self.market_code]}"
            )
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise MarketCompatibilityError(f"Timezone IANA inconnue : {self.timezone}") from exc
        if self.live_enabled and not self.enabled:
            raise MarketCompatibilityError("live_enabled ne peut pas être vrai pour un marché désactivé")
        if self.short_execution_enabled and "short_execution" not in self.capabilities:
            raise MarketCompatibilityError("short_execution_enabled requiert la capacité short_execution")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> MarketContext:
        schema_version = payload.get("schema_version")
        if schema_version != 1:
            raise MarketCompatibilityError(f"schema_version marché incompatible : {schema_version!r}; attendu=1")
        try:
            market_code = MarketCode(_required_text(payload, "market_code").upper())
        except ValueError as exc:
            raise MarketCompatibilityError(f"market_code inconnu : {payload.get('market_code')!r}") from exc
        return cls(
            market_code=market_code,
            database_alias=_required_text(payload, "database_alias"),
            country_code=_required_text(payload, "country_code").upper(),
            currency=_required_text(payload, "currency").upper(),
            timezone=_required_text(payload, "timezone"),
            calendar_id=_required_text(payload, "calendar_id"),
            benchmark_instrument=_required_text(payload, "benchmark_instrument"),
            sector_taxonomy=_required_text(payload, "sector_taxonomy"),
            cost_profile=_required_text(payload, "cost_profile"),
            execution_rules_profile=_required_text(payload, "execution_rules_profile"),
            feature_profile_root=_required_text(payload, "feature_profile_root"),
            enabled=_required_bool(payload, "enabled"),
            live_enabled=_required_bool(payload, "live_enabled"),
            short_execution_enabled=_required_bool(payload, "short_execution_enabled"),
            capabilities=_string_set(payload.get("capabilities"), "capabilities"),
        )

    def _manifest_payload(self) -> dict[str, Any]:
        return {
            "market_code": self.market_code.value,
            "database_alias": self.database_alias,
            "country_code": self.country_code,
            "currency": self.currency,
            "timezone": self.timezone,
            "calendar_id": self.calendar_id,
            "benchmark_instrument": self.benchmark_instrument,
            "sector_taxonomy": self.sector_taxonomy,
            "cost_profile": self.cost_profile,
            "execution_rules_profile": self.execution_rules_profile,
            "feature_profile_root": self.feature_profile_root,
            "enabled": self.enabled,
            "live_enabled": self.live_enabled,
            "short_execution_enabled": self.short_execution_enabled,
            "capabilities": sorted(self.capabilities),
        }

    def to_manifest(self) -> dict[str, Any]:
        return {**self._manifest_payload(), "fingerprint": self.fingerprint}

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            self._manifest_payload(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def assert_database_alias(self, database_alias: str) -> None:
        if database_alias != self.database_alias:
            raise MarketCompatibilityError(
                f"Contexte {self.market_code.value} lié à {self.database_alias!r}, pas à {database_alias!r}"
            )


@dataclass(frozen=True, slots=True)
class MarketRegistry:
    _contexts: Mapping[MarketCode, MarketContext]

    def __post_init__(self) -> None:
        copied = dict(self._contexts)
        if not copied:
            raise MarketCompatibilityError("Le registre de marchés est vide")
        if MarketCode.US_EQ not in copied:
            raise MarketCompatibilityError("Le registre doit contenir US_EQ")
        for code, context in copied.items():
            if code != context.market_code:
                raise MarketCompatibilityError(
                    f"Clé registre {code.value} incohérente avec {context.market_code.value}"
                )
        object.__setattr__(self, "_contexts", MappingProxyType(copied))

    @classmethod
    def from_contexts(cls, contexts: Iterable[MarketContext]) -> MarketRegistry:
        indexed: dict[MarketCode, MarketContext] = {}
        for context in contexts:
            if context.market_code in indexed:
                raise MarketCompatibilityError(f"Contexte dupliqué : {context.market_code.value}")
            indexed[context.market_code] = context
        return cls(indexed)

    @classmethod
    def from_directory(cls, directory: str | Path) -> MarketRegistry:
        root = Path(directory)
        if not root.is_dir():
            raise MarketCompatibilityError(f"Répertoire de marchés introuvable : {root}")
        contexts: list[MarketContext] = []
        for path in sorted(root.glob("market_*.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, dict):
                raise MarketCompatibilityError(f"Configuration marché invalide : {path}")
            contexts.append(MarketContext.from_mapping(payload))
        return cls.from_contexts(contexts)

    @property
    def market_codes(self) -> tuple[MarketCode, ...]:
        return tuple(sorted(self._contexts, key=lambda code: code.value))

    def resolve(
        self,
        market_code: MarketCode | str | None = None,
        *,
        require_enabled: bool = False,
    ) -> MarketContext:
        if market_code is None or not str(market_code).strip():
            warnings.warn(
                "market_code absent : résolution legacy vers US_EQ. "
                "Ce fallback sera retiré après la migration multi-marchés.",
                FutureWarning,
                stacklevel=2,
            )
            LOGGER.warning("market_code absent : fallback legacy US_EQ")
            code = MarketCode.US_EQ
        else:
            try:
                code = (
                    market_code if isinstance(market_code, MarketCode) else MarketCode(str(market_code).strip().upper())
                )
            except ValueError as exc:
                raise MarketCompatibilityError(f"market_code inconnu : {market_code!r}") from exc
        try:
            context = self._contexts[code]
        except KeyError as exc:
            raise MarketCompatibilityError(f"Contexte non configuré : {code.value}") from exc
        if require_enabled and not context.enabled:
            raise MarketCompatibilityError(f"Marché configuré mais désactivé : {code.value}")
        return context

    def assert_compatible(self, market_code: MarketCode | str, database_alias: str) -> MarketContext:
        context = self.resolve(market_code)
        context.assert_database_alias(database_alias)
        return context


__all__ = [
    "MarketCode",
    "MarketCompatibilityError",
    "MarketContext",
    "MarketRegistry",
]
