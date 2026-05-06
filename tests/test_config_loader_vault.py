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


