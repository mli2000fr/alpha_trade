"""Configuration transverse de la capitalisation boursiere PIT.

sec_edgar calcule la capitalisation a la date demandee avec le dernier nombre
d'actions publie avant cette date et le cours du jour. Les autres providers
lisent une capitalisation positive persistee avant la date demandee.
yahoo_then_finnhub choisit Yahoo en priorite, puis Finnhub si Yahoo est absent
ou perime selon le TTL configure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.config_loader import load_config


SUPPORTED_MARKET_CAP_PROVIDERS = frozenset(
    {"sec_edgar", "eodhd", "yahoo_then_finnhub"}
)
SUPPORTED_MARKET_CAP_POLICIES = frozenset({"strict", "liquidity_only"})


@dataclass(frozen=True)
class MarketCapConfig:
    provider: str = "sec_edgar"
    max_age_days: int = 365
    missing_policy: str = "reject"
    policy: str = "strict"


def _normalize_provider(value: Any) -> str:
    provider = str(value or "sec_edgar").strip().lower()
    aliases = {
        "sec": "sec_edgar",
        "edgar": "sec_edgar",
        "sec_edgar": "sec_edgar",
        "eodhd": "eodhd",
        "yahoo_then_finnhub": "yahoo_then_finnhub",
        "yahoo-finnhub": "yahoo_then_finnhub",
        "yahoo_finnhub": "yahoo_then_finnhub",
    }
    normalized = aliases.get(provider, provider)
    if normalized not in SUPPORTED_MARKET_CAP_PROVIDERS:
        raise ValueError(
            "market_cap.provider doit etre 'sec_edgar', 'eodhd' "
            "ou 'yahoo_then_finnhub' "
            f"(recu: {provider!r})."
        )
    return normalized


def load_market_cap_config(
    *,
    provider_override: str | None = None,
    max_age_days_override: int | None = None,
    policy_override: str | None = None,
    config: dict[str, Any] | None = None,
) -> MarketCapConfig:
    """Charge et valide la section market_cap de config.yaml."""
    root = config if config is not None else load_config()
    raw = root.get("market_cap") or {}
    if not isinstance(raw, dict):
        raise ValueError("La section config.yaml -> market_cap doit etre un mapping YAML.")
    provider = _normalize_provider(provider_override or raw.get("provider"))
    age = (
        max_age_days_override
        if max_age_days_override is not None
        else raw.get("max_age_days", 365)
    )
    max_age_days = int(age)
    if max_age_days < 0:
        raise ValueError("market_cap.max_age_days doit etre positif ou nul.")
    missing_policy = str(raw.get("missing_policy") or "reject").strip().lower()
    if missing_policy != "reject":
        raise ValueError(
            "Seule market_cap.missing_policy='reject' est supportee (fail-closed)."
        )
    policy = str(policy_override or raw.get("policy") or "strict").strip().lower()
    if policy not in SUPPORTED_MARKET_CAP_POLICIES:
        raise ValueError(
            "market_cap.policy doit etre 'strict' ou 'liquidity_only' "
            f"(recu: {policy!r})."
        )
    return MarketCapConfig(
        provider=provider,
        max_age_days=max_age_days,
        missing_policy=missing_policy,
        policy=policy,
    )


def compute_sec_market_cap(close_price: Any, shares_outstanding: Any) -> float | None:
    """Retourne close x shares apres validation stricte des deux termes."""
    try:
        close = float(close_price)
        shares = float(shares_outstanding)
    except (TypeError, ValueError):
        return None
    if close <= 0 or shares <= 0:
        return None
    return close * shares


__all__ = [
    "MarketCapConfig",
    "SUPPORTED_MARKET_CAP_POLICIES",
    "SUPPORTED_MARKET_CAP_PROVIDERS",
    "compute_sec_market_cap",
    "load_market_cap_config",
]
