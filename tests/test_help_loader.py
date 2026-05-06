"""Sprint S20 — Tests du chargeur YAML d'aide contextuelle."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ihm.services import help_loader


@pytest.fixture(autouse=True)
def _reset_cache():
    help_loader.reset_cache()
    yield
    help_loader.reset_cache()


def test_load_help_returns_only_common_for_unknown_page() -> None:
    """Page inexistante ⇒ seules les entrées de _common.yaml sont renvoyées."""
    common_only = dict(help_loader.load_help("page_inexistante_xyz"))
    common_keys = dict(help_loader.load_help("__no_match__")).keys()
    assert set(common_only.keys()) == set(common_keys)
    # _common.yaml contient au moins ``account``.
    assert "account" in common_only


def test_load_help_returns_dict_for_known_page() -> None:
    entries = help_loader.load_help("risk")
    assert isinstance(entries, dict)
    assert "risk_per_trade_pct" in entries


def test_load_help_merges_common_into_each_page(monkeypatch, tmp_path: Path) -> None:
    common = tmp_path / "_common.yaml"
    common.write_text(
        textwrap.dedent(
            """
            broker:
              title: Broker
              description: Compte broker
              impact: routage
              example: paper
              default: paper
              range: '{paper, live}'
              doc_ref: doc/x.md
            """
        ),
        encoding="utf-8",
    )
    page = tmp_path / "demo.yaml"
    page.write_text(
        textwrap.dedent(
            """
            specific_key:
              title: Spécifique
              description: ok
              impact: ok
              example: ok
              default: ok
              range: ok
              doc_ref: ok
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(help_loader, "_HELP_DIR", tmp_path)
    help_loader.reset_cache()
    merged = help_loader.load_help("demo")
    assert "broker" in merged
    assert "specific_key" in merged


def test_bom_is_rejected(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_bytes(b"\xef\xbb\xbfk: v\n")
    monkeypatch.setattr(help_loader, "_HELP_DIR", tmp_path)
    help_loader.reset_cache()
    # Ne plante pas la page : retourne dict vide en logguant un warning.
    result = help_loader.load_help("bad")
    assert dict(result) == {}


def test_lru_cache_avoids_redundant_disk_reads(monkeypatch) -> None:
    calls: list[str] = []
    original = help_loader._read_yaml

    def _spy(path: Path):
        calls.append(str(path))
        return original(path)

    monkeypatch.setattr(help_loader, "_read_yaml", _spy)
    help_loader.reset_cache()
    help_loader.load_help("risk")
    help_loader.load_help("risk")
    help_loader.load_help("risk")
    # Deuxième et troisième appels servis par lru_cache.
    assert len([c for c in calls if "risk.yaml" in c]) == 1


