"""Sprint S21.2 — Tests vault overrides + verify_vault_rotation."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from common import config_loader
from common.config_vault import EnvFallbackVault
from scripts import verify_vault_rotation as vvr


@pytest.fixture()
def yaml_with_placeholders(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(
        "broker:\n"
        "  api_key: ${vault:UT_S21_KEY1}\n"
        "  api_secret: ${vault:UT_S21_KEY2}\n"
        "  base_url: https://paper-api.alpaca.markets\n"
        "nested:\n"
        "  list:\n"
        "    - ${vault:UT_S21_KEY3}\n"
        "    - literal\n",
        encoding="utf-8",
    )
    return p


def test_load_config_no_vault_keeps_placeholders(yaml_with_placeholders, monkeypatch):
    monkeypatch.delenv("ALPHA_TRADE_VAULT_ADDR", raising=False)
    cfg = config_loader.load_config(str(yaml_with_placeholders))
    assert cfg["broker"]["api_key"] == "${vault:UT_S21_KEY1}"


def test_load_config_with_explicit_vault_substitutes(yaml_with_placeholders, tmp_path, monkeypatch):
    # garantir absence de collision avec l'env système
    for k in ("UT_S21_KEY1", "UT_S21_KEY2", "UT_S21_KEY3"):
        monkeypatch.delenv(k, raising=False)
    vault = EnvFallbackVault(root=tmp_path / "vault")
    vault.put("UT_S21_KEY1", "ak-secret")
    vault.put("UT_S21_KEY2", "as-secret")
    vault.put("UT_S21_KEY3", "p@ss")
    cfg = config_loader.load_config(str(yaml_with_placeholders), vault=vault)
    assert cfg["broker"]["api_key"] == "ak-secret"
    assert cfg["broker"]["api_secret"] == "as-secret"
    assert cfg["broker"]["base_url"] == "https://paper-api.alpaca.markets"
    assert cfg["nested"]["list"] == ["p@ss", "literal"]


def test_load_config_missing_key_keeps_placeholder(yaml_with_placeholders, tmp_path, monkeypatch):
    for k in ("UT_S21_KEY1", "UT_S21_KEY2", "UT_S21_KEY3"):
        monkeypatch.delenv(k, raising=False)
    vault = EnvFallbackVault(root=tmp_path / "vault")
    # Aucune clé n'est ajoutée — placeholders conservés
    cfg = config_loader.load_config(str(yaml_with_placeholders), vault=vault)
    assert cfg["broker"]["api_key"] == "${vault:UT_S21_KEY1}"


def test_load_config_env_triggers_vault_build(yaml_with_placeholders, tmp_path, monkeypatch):
    """Quand ALPHA_TRADE_VAULT_ADDR est défini, build_vault_from_env est invoqué."""
    monkeypatch.setenv("ALPHA_TRADE_VAULT_ADDR", "http://127.0.0.1:8200")
    monkeypatch.delenv("ALPHA_TRADE_VAULT_TOKEN", raising=False)
    for k in ("UT_S21_KEY1", "UT_S21_KEY2", "UT_S21_KEY3"):
        monkeypatch.delenv(k, raising=False)

    fake_vault = EnvFallbackVault(root=tmp_path / "vault")
    fake_vault.put("UT_S21_KEY1", "from-env")
    fake_vault.put("UT_S21_KEY2", "x")
    fake_vault.put("UT_S21_KEY3", "y")

    monkeypatch.setattr(
        "common.config_vault.build_vault_from_env", lambda: fake_vault
    )
    cfg = config_loader.load_config(str(yaml_with_placeholders))
    assert cfg["broker"]["api_key"] == "from-env"


def test_load_config_uses_env_override_for_default_repo_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default_config = tmp_path / "config.yaml"
    override_config = tmp_path / "regime_r13a_final.yaml"
    default_config.write_text("value: default\n", encoding="utf-8")
    override_config.write_text("value: override\n", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_DEFAULT_CONFIG_PATH", default_config)
    monkeypatch.setenv(config_loader.CONFIG_PATH_ENV, str(override_config))

    cfg_default = config_loader.load_config()
    cfg_explicit_default = config_loader.load_config(str(default_config))

    assert cfg_default["value"] == "override"
    assert cfg_explicit_default["value"] == "override"


def test_load_config_keeps_explicit_non_default_path_even_with_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default_config = tmp_path / "config.yaml"
    explicit_config = tmp_path / "custom.yaml"
    override_config = tmp_path / "regime_r13a_final.yaml"
    default_config.write_text("value: default\n", encoding="utf-8")
    explicit_config.write_text("value: explicit\n", encoding="utf-8")
    override_config.write_text("value: override\n", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_DEFAULT_CONFIG_PATH", default_config)
    monkeypatch.setenv(config_loader.CONFIG_PATH_ENV, str(override_config))

    cfg = config_loader.load_config(str(explicit_config))

    assert cfg["value"] == "explicit"


def test_override_config_path_restores_previous_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    previous = tmp_path / "previous.yaml"
    current = tmp_path / "current.yaml"
    monkeypatch.setenv(config_loader.CONFIG_PATH_ENV, str(previous))

    with config_loader.override_config_path(current):
        assert os.environ.get(config_loader.CONFIG_PATH_ENV) == str(current)

    assert os.environ.get(config_loader.CONFIG_PATH_ENV) == str(previous)


def test_repo_default_config_promotes_r13a_market_regime_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config_loader.CONFIG_PATH_ENV, raising=False)

    cfg = config_loader.load_config()
    market_regimes = cfg["market_regimes"]
    yields_cfg = market_regimes["yields"]
    sentiment_cb = market_regimes["sentiment_circuit_breaker"]

    assert market_regimes["macro_provider"] == "eodhd"
    assert market_regimes["capital_preservation_max_gross_exposure"] == pytest.approx(0.65)
    assert market_regimes["vix"]["high_threshold"] == pytest.approx(30.0)
    assert yields_cfg["relative_spike_threshold"] == pytest.approx(0.07)
    assert yields_cfg["risk_mult"] == pytest.approx(0.85)
    assert yields_cfg["soft_max_positions"] == 3
    assert yields_cfg["soft_max_position_weight"] == pytest.approx(0.25)
    assert yields_cfg["soft_max_sector_weight"] == pytest.approx(0.30)
    assert yields_cfg["soft_max_gross_exposure"] == pytest.approx(0.65)
    assert yields_cfg["hard_mode_backtest"] == "capital_preservation"
    assert sentiment_cb["warning_threshold"] == pytest.approx(-0.20)
    assert sentiment_cb["critical_threshold"] == pytest.approx(-0.40)
    assert sentiment_cb["warning_max_positions"] == 3
    assert sentiment_cb["critical_mode_backtest"] == "capital_preservation"


# ----------------------------- verify_vault_rotation ----------------------------


def test_verify_rotation_ok(tmp_path):
    vault = EnvFallbackVault(root=tmp_path / "vault")
    vault.put("KEY_OK", "v")
    report = vvr.verify(
        ["KEY_OK"], max_age_days=90, vault=vault, output_dir=tmp_path / "out",
    )
    assert report["status"] == "ok"
    assert report["keys"][0]["status"] == "ok"
    assert Path(report["report_path"]).exists()


def test_verify_rotation_missing(tmp_path):
    vault = EnvFallbackVault(root=tmp_path / "vault")
    report = vvr.verify(
        ["GHOST"], max_age_days=90, vault=vault, output_dir=tmp_path / "out",
    )
    assert report["status"] == "missing"
    assert report["keys"][0]["status"] == "missing"


def test_verify_rotation_expired_when_stored_at_old(tmp_path):
    vault = EnvFallbackVault(root=tmp_path / "vault")
    vault.put("OLD_KEY", "v")
    # Réécrit le fichier avec un stored_at périmé
    key_dir = vault.root / "OLD_KEY"
    files = list(key_dir.glob("v*.json"))
    assert files
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    payload["stored_at"] = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    files[0].write_text(json.dumps(payload), encoding="utf-8")

    report = vvr.verify(
        ["OLD_KEY"], max_age_days=90, vault=vault, output_dir=tmp_path / "out",
    )
    assert report["status"] == "expired"
    assert report["keys"][0]["status"] == "expired"


def test_main_exit_codes(tmp_path, monkeypatch, capsys):
    vault = EnvFallbackVault(root=tmp_path / "vault")
    vault.put("OK_KEY", "v")
    monkeypatch.setattr(vvr, "build_vault_from_env", lambda: vault)
    rc = vvr.main(["OK_KEY", "--output-dir", str(tmp_path / "out")])
    assert rc == 0
    rc = vvr.main(["MISSING_KEY", "--output-dir", str(tmp_path / "out")])
    assert rc == 3


