from __future__ import annotations

from pathlib import Path

import pytest

from service.alpaca import accounts as accounts_module
from service.alpaca.accounts import AccountRegistry, DEFAULT_ACCOUNT_ID


@pytest.fixture(autouse=True)
def reset_registry(request: pytest.FixtureRequest) -> None:
    AccountRegistry.reset()
    request.addfinalizer(AccountRegistry.reset)


@pytest.fixture(autouse=True)
def clean_alpaca_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "ALPACA_LIVE1_API_KEY",
        "ALPACA_LIVE1_SECRET_KEY",
        "ALPACA_LIVE1_MODE",
        "ALPACA_LIVE1_LABEL",
        "ALPACA_LIVE2_API_KEY",
        "ALPACA_LIVE2_SECRET_KEY",
        "ALPACA_LIVE2_MODE",
        "ALPACA_LIVE2_LABEL",
        "LIVE1_API_KEY",
        "LIVE1_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def empty_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(accounts_module, "_CONFIG_PATH", config_path)
    return config_path


def test_loads_accounts_from_yaml_with_env_placeholders(
    empty_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_config_path.write_text(
        """
 alpaca:
   accounts:
     - id: live1
       label: Compte live
       api_key: ${LIVE1_API_KEY}
       secret_key: ${LIVE1_SECRET_KEY}
       mode: live
 """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("LIVE1_API_KEY", "key-live")
    monkeypatch.setenv("LIVE1_SECRET_KEY", "secret-live")

    registry = AccountRegistry()

    account = registry.resolve("live1")
    assert account.label == "Compte live"
    assert account.api_key == "key-live"
    assert account.secret_key == "secret-live"
    assert account.mode == "live"


def test_loads_prefixed_env_accounts_when_yaml_missing(
    empty_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_LIVE2_API_KEY", "api-live2")
    monkeypatch.setenv("ALPACA_LIVE2_SECRET_KEY", "secret-live2")
    monkeypatch.setenv("ALPACA_LIVE2_MODE", "live")
    monkeypatch.setenv("ALPACA_LIVE2_LABEL", "Secondaire")

    registry = AccountRegistry()

    assert registry.list_account_ids() == ["live2"]
    account = registry.resolve("live2")
    assert account.label == "Secondaire"
    assert account.mode == "live"


def test_fallback_default_account_uses_classic_env_vars(
    empty_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "api-default")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret-default")

    registry = AccountRegistry()

    account = registry.resolve()
    assert account.account_id == DEFAULT_ACCOUNT_ID
    assert registry.get_credentials() == ("api-default", "secret-default")


def test_yaml_account_takes_precedence_over_env_account_with_same_id(
    empty_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_config_path.write_text(
        """
 alpaca:
   accounts:
     - id: live1
       label: YAML First
       api_key: yaml-key
       secret_key: yaml-secret
       mode: paper
 """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALPACA_LIVE1_API_KEY", "env-key")
    monkeypatch.setenv("ALPACA_LIVE1_SECRET_KEY", "env-secret")
    monkeypatch.setenv("ALPACA_LIVE1_MODE", "live")

    registry = AccountRegistry()

    account = registry.resolve("live1")
    assert account.label == "YAML First"
    assert account.api_key == "yaml-key"
    assert account.mode == "paper"


def test_resolve_raises_when_no_accounts_configured(
    empty_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    registry = AccountRegistry()

    with pytest.raises(RuntimeError, match="Aucun compte Alpaca configuré"):
        registry.resolve()

    with pytest.raises(KeyError, match="introuvable"):
        registry.resolve("missing")

