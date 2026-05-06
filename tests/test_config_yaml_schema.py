"""Sprint S1 / Anomalie A-002 — Empêcher la résurrection de paramètres
fantômes dans `config.yaml`.

L'audit a révélé que la clé `eodhd.enabled` était présente dans
`config.yaml` mais **jamais lue par le code applicatif** (faux levier
opérateur). Elle a été supprimée en S1 ; ce test garantit qu'elle ne
revient pas par mégarde et liste les clés autorisées sous `eodhd:` /
`market_data:`.
"""
from __future__ import annotations

import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"

#: Clés explicitement reconnues par le code sous chaque section auditée.
ALLOWED_EODHD_KEYS = {
    "api_token_env",
    "exchange",
    "cache_dir",
    "daily_quota",
    "soft_quota_warn",
    "bulk_publish_offset_hours",
    "splits_cache_ttl_days",
    "circuit_breaker",
}

ALLOWED_MARKET_DATA_KEYS = {
    "bars_provider",
    "fallback_on_failure",
}


def _load() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_config_yaml_loads() -> None:
    cfg = _load()
    assert isinstance(cfg, dict)


def test_eodhd_enabled_key_is_absent() -> None:
    cfg = _load()
    eodhd = cfg.get("eodhd", {}) or {}
    assert "enabled" not in eodhd, (
        "eodhd.enabled est un paramètre fantôme (audit S1 / A-002). "
        "L'activation runtime se fait via market_data.bars_provider."
    )


def test_eodhd_section_has_only_known_keys() -> None:
    cfg = _load()
    eodhd = cfg.get("eodhd", {}) or {}
    unknown = set(eodhd) - ALLOWED_EODHD_KEYS
    assert not unknown, (
        f"Clés inconnues sous eodhd: {sorted(unknown)}. "
        f"Si elles sont légitimes, ajoute-les explicitement à "
        f"ALLOWED_EODHD_KEYS dans tests/test_config_yaml_schema.py "
        f"après avoir branché leur lecture dans le code."
    )


def test_market_data_section_has_only_known_keys() -> None:
    cfg = _load()
    md = cfg.get("market_data", {}) or {}
    unknown = set(md) - ALLOWED_MARKET_DATA_KEYS
    assert not unknown, (
        f"Clés inconnues sous market_data: {sorted(unknown)}."
    )


def test_bars_provider_value_is_supported() -> None:
    cfg = _load()
    md = cfg.get("market_data", {}) or {}
    assert md.get("bars_provider") in {"alpaca", "eodhd"}

