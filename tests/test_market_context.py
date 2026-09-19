from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from common.config_loader import load_market_registry, resolve_market_context
from common.market_context import (
    MarketCode,
    MarketCompatibilityError,
    MarketContext,
    MarketRegistry,
)

ROOT = Path(__file__).resolve().parents[1]
MARKETS_DIR = ROOT / "config" / "markets"


def _us_payload() -> dict:
    return yaml.safe_load((MARKETS_DIR / "market_us.yaml").read_text(encoding="utf-8"))


def test_registry_loads_all_declared_markets() -> None:
    registry = load_market_registry()
    assert registry.market_codes == (MarketCode.CN_A, MarketCode.CN_BJ, MarketCode.US_EQ)


def test_legacy_resolution_warns_and_falls_back_to_us() -> None:
    with pytest.warns(FutureWarning, match="US_EQ"):
        context = resolve_market_context()
    assert context.market_code is MarketCode.US_EQ
    assert context.enabled is True


def test_cn_contexts_are_visible_but_disabled() -> None:
    registry = load_market_registry()
    for code in (MarketCode.CN_A, MarketCode.CN_BJ):
        context = registry.resolve(code)
        assert context.country_code == "CN"
        assert context.enabled is False
        assert context.live_enabled is False
        with pytest.raises(MarketCompatibilityError, match="désactivé"):
            registry.resolve(code, require_enabled=True)


def test_context_and_registry_are_immutable() -> None:
    registry = load_market_registry()
    context = registry.resolve(MarketCode.US_EQ)
    with pytest.raises(FrozenInstanceError):
        context.currency = "EUR"
    with pytest.raises(TypeError):
        registry._contexts[MarketCode.CN_A] = context


def test_manifest_is_serializable_and_fingerprint_is_stable() -> None:
    first = load_market_registry().resolve(MarketCode.US_EQ)
    second = MarketContext.from_mapping(_us_payload())
    manifest = first.to_manifest()
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert json.loads(json.dumps(manifest))["fingerprint"] == first.fingerprint
    assert manifest["capabilities"] == sorted(manifest["capabilities"])


def test_unknown_market_is_blocked() -> None:
    with pytest.raises(MarketCompatibilityError, match="inconnu"):
        load_market_registry().resolve("FR_EQ")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("database_alias", "cn_primary", "database_alias"),
        ("country_code", "CN", "country_code"),
        ("currency", "CNY", "currency"),
        ("timezone", "Asia/Shanghai", "timezone"),
        ("calendar_id", "CN_A", "calendar_id"),
    ],
)
def test_us_contract_rejects_incoherent_market_identity(field: str, value: str, message: str) -> None:
    payload = _us_payload()
    payload[field] = value
    with pytest.raises(MarketCompatibilityError, match=message):
        MarketContext.from_mapping(payload)


def test_schema_version_is_mandatory_and_versioned() -> None:
    payload = _us_payload()
    payload["schema_version"] = 2
    with pytest.raises(MarketCompatibilityError, match="schema_version"):
        MarketContext.from_mapping(payload)


def test_boolean_fields_must_be_real_yaml_booleans() -> None:
    payload = _us_payload()
    payload["enabled"] = "true"
    with pytest.raises(MarketCompatibilityError, match="booléen"):
        MarketContext.from_mapping(payload)


def test_short_execution_requires_capability() -> None:
    payload = _us_payload()
    payload["capabilities"].remove("short_execution")
    with pytest.raises(MarketCompatibilityError, match="short_execution"):
        MarketContext.from_mapping(payload)


def test_live_cannot_be_enabled_for_disabled_market() -> None:
    payload = _us_payload()
    payload["enabled"] = False
    with pytest.raises(MarketCompatibilityError, match="live_enabled"):
        MarketContext.from_mapping(payload)


def test_duplicate_contexts_are_rejected() -> None:
    context = MarketContext.from_mapping(_us_payload())
    with pytest.raises(MarketCompatibilityError, match="dupliqué"):
        MarketRegistry.from_contexts([context, context])


def test_database_alias_compatibility_is_explicit() -> None:
    registry = load_market_registry()
    assert registry.assert_compatible("US_EQ", "us_primary").currency == "USD"
    with pytest.raises(MarketCompatibilityError, match="pas à"):
        registry.assert_compatible("US_EQ", "cn_primary")


def test_parallel_resolution_has_no_mutable_current_market() -> None:
    registry = load_market_registry()
    codes = ["US_EQ", "CN_A", "CN_BJ"] * 20
    with ThreadPoolExecutor(max_workers=6) as pool:
        resolved = list(pool.map(lambda code: registry.resolve(code).market_code.value, codes))
    assert resolved == codes
    assert registry.resolve("US_EQ").currency == "USD"


def test_market_config_directory_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for source in MARKETS_DIR.glob("market_*.yaml"):
        (tmp_path / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("ALPHA_TRADE_MARKETS_CONFIG_DIR", str(tmp_path))
    assert load_market_registry().resolve("US_EQ").database_alias == "us_primary"


def test_us_context_preserves_historical_constants() -> None:
    context = load_market_registry().resolve("US_EQ")
    assert context.timezone == "America/New_York"
    assert context.calendar_id == "NYSE"
    assert context.currency == "USD"
    assert context.benchmark_instrument == "SPY"
    assert context.sector_taxonomy == "GICS"
