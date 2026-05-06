"""Sprint S12.5 — Tests EnvFallbackVault."""
from __future__ import annotations

import pytest

from common.config_vault import EnvFallbackVault


def test_put_creates_versions(tmp_path):
    v = EnvFallbackVault(root=tmp_path)
    assert v.put("MY_KEY", "v1") == 1
    assert v.put("MY_KEY", "v2") == 2
    assert v.list_versions("MY_KEY") == [1, 2]


def test_get_specific_version(tmp_path):
    v = EnvFallbackVault(root=tmp_path)
    v.put("K", "first")
    v.put("K", "second")
    assert v.get("K", version=1) == "first"
    assert v.get("K", version=2) == "second"


def test_get_without_version_prefers_env(tmp_path, monkeypatch):
    v = EnvFallbackVault(root=tmp_path)
    v.put("K", "from-disk")
    monkeypatch.setenv("K", "from-env")
    assert v.get("K") == "from-env"
    monkeypatch.delenv("K")
    assert v.get("K") == "from-disk"


def test_rotate_creates_new_version(tmp_path):
    v = EnvFallbackVault(root=tmp_path)
    v.put("K", "old")
    new = v.rotate("K", "new")
    assert new == 2
    assert v.get("K", version=2) == "new"


def test_get_unknown_returns_none(tmp_path):
    v = EnvFallbackVault(root=tmp_path)
    assert v.get("UNKNOWN") is None
    assert v.list_versions("UNKNOWN") == []

