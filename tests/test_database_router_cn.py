from __future__ import annotations

from pathlib import Path

import pytest

from common.market_context import MarketCompatibilityError
from database.router import build_database_url, load_database_routes, resolve_database_route


@pytest.fixture(autouse=True)
def clear_route_cache() -> None:
    load_database_routes.cache_clear()
    yield
    load_database_routes.cache_clear()


def test_cn_route_is_physically_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_DB", "user")
    monkeypatch.setenv("PASSWORD_DB", "secret")
    route = resolve_database_route("cn_primary", "CN_A")
    assert route.database == "alpha_trade_cn"
    assert route.allowed_markets == frozenset({"CN_A", "CN_BJ"})
    assert "/alpha_trade_cn?" in build_database_url("cn_primary", "CN_A")


def test_us_market_cannot_use_cn_route() -> None:
    with pytest.raises(MarketCompatibilityError, match="incompatible"):
        resolve_database_route("cn_primary", "US_EQ")


def test_cn_route_falls_back_to_existing_db_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGIN_DB_CN", raising=False)
    monkeypatch.delenv("PASSWORD_DB_CN", raising=False)
    monkeypatch.setenv("LOGIN_DB", "legacy-user")
    monkeypatch.setenv("PASSWORD_DB", "legacy-pass")
    url = build_database_url("cn_primary", "CN_A")
    assert "legacy-user:legacy-pass" in url


def test_unknown_database_alias_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "databases.yaml"
    config.write_text("schema_version: 1\ndatabases: {}\n", encoding="utf-8")
    with pytest.raises(MarketCompatibilityError, match="non autorisé"):
        resolve_database_route("free_text", "CN_A", config_path=config)
