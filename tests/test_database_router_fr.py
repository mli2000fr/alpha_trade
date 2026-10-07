from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from common.market_context import MarketCompatibilityError
from database.router import (
    build_database_url,
    get_market_engine,
    load_database_routes,
    resolve_database_route,
)


@pytest.fixture(autouse=True)
def clear_route_cache() -> None:
    load_database_routes.cache_clear()
    yield
    load_database_routes.cache_clear()


def test_fr_route_is_fixed_to_its_own_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_DB_FR", "fr-user")
    monkeypatch.setenv("PASSWORD_DB_FR", "fr-pass")
    monkeypatch.setenv("DB_NAME_FR", "alpha_trade")  # Ignoré intentionnellement.
    route = resolve_database_route("fr_primary", "FR_EQ")
    assert route.database == "alpha_trade_fr"
    assert route.allowed_markets == frozenset({"FR_EQ"})
    assert "/alpha_trade_fr?" in build_database_url("fr_primary", "FR_EQ")


@pytest.mark.parametrize(
    ("alias", "market"),
    [("fr_primary", "US_EQ"), ("fr_primary", "CN_A"),
     ("us_primary", "FR_EQ"), ("cn_primary", "FR_EQ")],
)
def test_cross_market_routes_are_rejected(alias: str, market: str) -> None:
    with pytest.raises(MarketCompatibilityError, match="incompatible"):
        resolve_database_route(alias, market)


def test_fr_explicit_shared_credentials_keep_database_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGIN_DB_FR", raising=False)
    monkeypatch.delenv("PASSWORD_DB_FR", raising=False)
    monkeypatch.setenv("LOGIN_DB", "us-user")
    monkeypatch.setenv("PASSWORD_DB", "us-pass")
    url = build_database_url("fr_primary", "FR_EQ")
    assert 'us-user:us-pass@' in url
    assert '/alpha_trade_fr?' in url


def test_fr_credentials_fail_closed_without_configured_fallback(tmp_path, monkeypatch):
    import yaml
    from database.router import DEFAULT_ROUTING_CONFIG
    payload = yaml.safe_load(DEFAULT_ROUTING_CONFIG.read_text(encoding='utf-8'))
    payload['databases']['fr_primary'].pop('fallback_user_env')
    payload['databases']['fr_primary'].pop('fallback_password_env')
    path = tmp_path/'routes.yaml'
    path.write_text(yaml.safe_dump(payload),encoding='utf-8')
    monkeypatch.delenv('LOGIN_DB_FR',raising=False)
    monkeypatch.setenv('LOGIN_DB','shared-user')
    with pytest.raises(RuntimeError,match='LOGIN_DB_FR'):
        build_database_url('fr_primary','FR_EQ',config_path=path)


def test_fr_database_override_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_DB_FR", "fr-user")
    monkeypatch.setenv("PASSWORD_DB_FR", "fr-pass")
    with pytest.raises(MarketCompatibilityError, match="database_override"):
        build_database_url("fr_primary", "FR_EQ", database_override="alpha_trade")


def test_altered_fr_route_cannot_point_to_us(tmp_path: Path) -> None:
    config = tmp_path / "databases.yaml"
    config.write_text(
        "schema_version: 1\ndatabases:\n  fr_primary:\n"
        "    database: alpha_trade\n    allowed_markets: [FR_EQ]\n",
        encoding="utf-8",
    )
    with pytest.raises(MarketCompatibilityError, match="alpha_trade_fr"):
        resolve_database_route("fr_primary", "FR_EQ", config_path=config)


def test_fr_schema_verification_cannot_be_disabled() -> None:
    with pytest.raises(MarketCompatibilityError, match="verify_schema"):
        get_market_engine("FR_EQ", database_alias="fr_primary", verify_schema=False)


def test_fr_custom_url_cannot_point_to_us() -> None:
    with pytest.raises(MarketCompatibilityError, match="URL FR_EQ"):
        get_market_engine(
            "FR_EQ", database_alias="fr_primary",
            url="mysql+pymysql://user:pass@localhost/alpha_trade",
        )


def test_fr_custom_url_cannot_change_host() -> None:
    with pytest.raises(MarketCompatibilityError, match="URL FR_EQ"):
        get_market_engine(
            "FR_EQ", database_alias="fr_primary",
            url="mysql+pymysql://user:pass@other-host/alpha_trade_fr",
        )


def test_fr_actual_schema_is_verified_before_engine_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        def execute(self, _statement):
            return self

        def scalar(self):
            return "alpha_trade"

    class Engine:
        disposed = False

        @contextmanager
        def connect(self):
            yield Connection()

        def dispose(self):
            self.disposed = True

    engine = Engine()
    monkeypatch.setattr("database.router.create_engine", lambda *_args, **_kwargs: engine)
    with pytest.raises(MarketCompatibilityError, match="connexion réelle"):
        get_market_engine(
            "FR_EQ", database_alias="fr_primary",
            url="mysql+pymysql://user:pass@localhost/alpha_trade_fr",
        )
    assert engine.disposed
