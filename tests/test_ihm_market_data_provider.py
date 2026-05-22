"""Tests du service ``ihm.services.market_data_provider``.

Couvre la lecture, l'écriture round-trip et la préservation des autres
lignes de ``config.yaml`` lors d'une bascule ``alpaca``/``eodhd``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ihm.services import market_data_provider as mdp


YAML_TEMPLATE = """\
foo:
  bar: 1

# Commentaire avant la section
market_data:
  bars_provider: alpaca   # alpaca | eodhd

eodhd:
  enabled: false
"""


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(YAML_TEMPLATE, encoding="utf-8")
    return path


def test_default_constants():
    assert mdp.DEFAULT_BARS_PROVIDER == "eodhd"
    assert set(mdp.ALLOWED_BARS_PROVIDERS) == {"alpaca", "eodhd"}


def test_get_bars_provider_reads_value(tmp_config: Path):
    assert mdp.get_bars_provider(tmp_config) == "alpaca"


def test_get_bars_provider_missing_file_returns_default(tmp_path: Path):
    assert mdp.get_bars_provider(tmp_path / "absent.yaml") == mdp.DEFAULT_BARS_PROVIDER


def test_get_bars_provider_invalid_value_returns_default(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("market_data:\n  bars_provider: garbage\n", encoding="utf-8")
    assert mdp.get_bars_provider(path) == mdp.DEFAULT_BARS_PROVIDER


def test_set_bars_provider_round_trip(tmp_config: Path):
    assert mdp.set_bars_provider("eodhd", tmp_config) == "eodhd"
    assert mdp.get_bars_provider(tmp_config) == "eodhd"
    assert mdp.set_bars_provider("ALPACA", tmp_config) == "alpaca"
    assert mdp.get_bars_provider(tmp_config) == "alpaca"


def test_set_bars_provider_preserves_other_lines(tmp_config: Path):
    mdp.set_bars_provider("eodhd", tmp_config)
    text = tmp_config.read_text(encoding="utf-8")
    assert "foo:" in text
    assert "bar: 1" in text
    assert "eodhd:" in text
    assert "enabled: false" in text
    # La ligne bars_provider doit refléter la nouvelle valeur.
    assert "bars_provider: eodhd" in text


def test_set_bars_provider_rejects_invalid(tmp_config: Path):
    with pytest.raises(ValueError):
        mdp.set_bars_provider("yahoo", tmp_config)


def test_set_bars_provider_missing_key_raises(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("foo: 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        mdp.set_bars_provider("eodhd", path)

