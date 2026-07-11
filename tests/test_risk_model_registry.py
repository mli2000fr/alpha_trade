"""Tests unitaires — risk_management/model_registry.py (Sprint Maître 13)."""
from __future__ import annotations

import pytest

from risk_management.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    ModelStatus,
    create_model_entry,
)


# ── ModelStatus ─────────────────────────────────────────────────────────────


class TestModelStatus:
    def test_candidate_not_active(self) -> None:
        assert ModelStatus.CANDIDATE.is_active is False
        assert ModelStatus.CANDIDATE.is_production is False

    def test_champion_is_active_and_production(self) -> None:
        assert ModelStatus.CHAMPION.is_active is True
        assert ModelStatus.CHAMPION.is_production is True

    def test_paper_is_active_not_production(self) -> None:
        assert ModelStatus.PAPER.is_active is True
        assert ModelStatus.PAPER.is_production is False

    def test_can_be_promoted(self) -> None:
        assert ModelStatus.CANDIDATE.can_be_promoted is True
        assert ModelStatus.SHADOW.can_be_promoted is True
        assert ModelStatus.PAPER.can_be_promoted is True
        assert ModelStatus.CHAMPION.can_be_promoted is False

    def test_can_be_demoted(self) -> None:
        assert ModelStatus.CHAMPION.can_be_demoted is True
        assert ModelStatus.DEGRADED.can_be_demoted is True
        assert ModelStatus.CANDIDATE.can_be_demoted is False

    def test_next_in_cycle(self) -> None:
        assert ModelStatus.CANDIDATE.next_in_cycle() == ModelStatus.SHADOW
        assert ModelStatus.SHADOW.next_in_cycle() == ModelStatus.PAPER
        assert ModelStatus.PAPER.next_in_cycle() == ModelStatus.CHAMPION
        assert ModelStatus.CHAMPION.next_in_cycle() == ModelStatus.CHAMPION


# ── ModelRegistryEntry ──────────────────────────────────────────────────────


class TestModelRegistryEntry:
    def test_valid_entry(self) -> None:
        entry = ModelRegistryEntry(
            model_id="model_001", symbol="AAPL", status=ModelStatus.CANDIDATE, version=1,
        )
        assert entry.status == ModelStatus.CANDIDATE

    def test_rejects_empty_model_id(self) -> None:
        with pytest.raises(ValueError, match="model_id"):
            ModelRegistryEntry(model_id="", symbol="AAPL")

    def test_rejects_empty_symbol(self) -> None:
        with pytest.raises(ValueError, match="symbol"):
            ModelRegistryEntry(model_id="m1", symbol="")

    def test_rejects_version_zero(self) -> None:
        with pytest.raises(ValueError, match="version"):
            ModelRegistryEntry(model_id="m1", symbol="AAPL", version=0)

    def test_to_dict(self) -> None:
        entry = ModelRegistryEntry(model_id="m1", symbol="AAPL", status=ModelStatus.SHADOW, version=2)
        d = entry.to_dict()
        assert d["status"] == "shadow"
        assert d["version"] == 2


# ── ModelRegistry ───────────────────────────────────────────────────────────


class TestModelRegistry:
    def test_register(self) -> None:
        reg = ModelRegistry()
        entry = create_model_entry("m1", "AAPL")
        reg.register(entry)
        assert reg.get_champion("AAPL") is None

    def test_register_duplicate_raises(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        with pytest.raises(ValueError, match="enregistré"):
            reg.register(create_model_entry("m1", "AAPL"))

    def test_full_promotion_cycle(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        # CANDIDATE → SHADOW
        entry = reg.promote("m1", "evaluation OK")
        assert entry.status == ModelStatus.SHADOW
        # SHADOW → PAPER
        entry = reg.promote("m1", "shadow OK")
        assert entry.status == ModelStatus.PAPER
        # PAPER → CHAMPION
        entry = reg.promote("m1", "paper OK")
        assert entry.status == ModelStatus.CHAMPION
        assert reg.get_champion("AAPL") is not None
        assert reg.get_champion("AAPL").model_id == "m1"  # type: ignore[union-attr]

    def test_champion_replaces_old(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        reg.register(create_model_entry("m2", "AAPL"))
        # Promote m1
        for _ in range(3):
            reg.promote("m1", "ok")
        assert reg.get_champion("AAPL").model_id == "m1"  # type: ignore[union-attr]
        # Promote m2 → m1 dégradé
        for _ in range(3):
            reg.promote("m2", "better")
        assert reg.get_champion("AAPL").model_id == "m2"  # type: ignore[union-attr]
        # m1 is now DEGRADED
        m1 = reg._entries["m1"]
        assert m1.status == ModelStatus.DEGRADED

    def test_degrade(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        for _ in range(3):
            reg.promote("m1", "ok")
        reg.degrade("m1", "drift détecté")
        entry = reg._entries["m1"]
        assert entry.status == ModelStatus.DEGRADED
        assert reg.get_champion("AAPL") is None

    def test_retire(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        for _ in range(3):
            reg.promote("m1", "ok")
        reg.retire("m1", "obsolète")
        assert reg._entries["m1"].status == ModelStatus.RETIRED

    def test_rollback(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        reg.register(create_model_entry("m2", "AAPL"))
        # m1 champion
        for _ in range(3):
            reg.promote("m1", "ok")
        # m2 champion
        for _ in range(3):
            reg.promote("m2", "better")
        # Rollback → m1 restauré
        restored = reg.rollback("AAPL", "m2 drift")
        assert restored is not None
        assert restored.model_id == "m1"
        assert restored.status == ModelStatus.CHAMPION
        # m2 dégradé
        assert reg._entries["m2"].status == ModelStatus.DEGRADED

    def test_rollback_no_previous(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        for _ in range(3):
            reg.promote("m1", "ok")
        result = reg.rollback("AAPL", "no previous")
        assert result is None

    def test_get_by_status(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        reg.promote("m1", "ok")  # → SHADOW
        candidates = reg.get_by_status("AAPL", ModelStatus.CANDIDATE)
        assert len(candidates) == 0
        shadows = reg.get_by_status("AAPL", ModelStatus.SHADOW)
        assert len(shadows) == 1

    def test_count_by_status(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        reg.register(create_model_entry("m2", "MSFT"))
        counts = reg.count_by_status()
        assert counts.get("candidate", 0) == 2

    def test_cannot_promote_champion(self) -> None:
        reg = ModelRegistry()
        reg.register(create_model_entry("m1", "AAPL"))
        for _ in range(3):
            reg.promote("m1", "ok")
        with pytest.raises(ValueError, match="peut pas"):
            reg.promote("m1", "déjà champion")


# ── create_model_entry ──────────────────────────────────────────────────────


class TestCreateModelEntry:
    def test_helper(self) -> None:
        entry = create_model_entry("m1", "AAPL", architecture="catboost", version=3)
        assert entry.model_id == "m1"
        assert entry.architecture == "catboost"
        assert entry.version == 3
        assert entry.status == ModelStatus.CANDIDATE
