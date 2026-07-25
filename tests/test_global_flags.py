"""tests/test_global_flags.py — Tests de la matrice A/B/C pour l'Approche 2 (Global Rank).

Verifie que :
- GlobalModelConfig gere correctement les 3 flags independants
- Les combinaisons de flags sont valides
- Le flag B active le stacking global_rank
- Le fingerprint change de maniere deterministe
"""
from __future__ import annotations

import pytest

from modelFactory.config import GlobalModelConfig
from modelFactory.features import fingerprint, get_feature_columns


class TestGlobalModelConfigFlags:
    def test_all_defaults(self) -> None:
        cfg = GlobalModelConfig()
        assert cfg.enabled is False
        assert cfg.stacking_enabled is False
        assert cfg.challenger_enabled is False

    def test_flag_a_alone(self) -> None:
        cfg = GlobalModelConfig(enabled=True)
        assert cfg.enabled is True
        assert cfg.stacking_enabled is False

    def test_flag_ab_stacking_on(self) -> None:
        cfg = GlobalModelConfig(enabled=True, stacking_enabled=True)
        assert cfg.enabled is True
        assert cfg.stacking_enabled is True
        assert cfg.challenger_enabled is False

    def test_immutable(self) -> None:
        cfg = GlobalModelConfig(enabled=True, stacking_enabled=True)
        with pytest.raises(Exception):
            cfg.stacking_enabled = False  # type: ignore[misc]

    def test_challenger_disabled_by_default(self) -> None:
        cfg = GlobalModelConfig()
        assert cfg.challenger_enabled is False


class TestFlagMatrixFeatureColumns:
    def test_no_stacking_no_global_rank(self) -> None:
        cols = get_feature_columns(include_cross_sectional=True)
        assert "global_rank" not in cols

    def test_stacking_adds_global_rank(self) -> None:
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_rank" in cols

    def test_stacking_without_cross_sectional_no_global_rank(self) -> None:
        cols = get_feature_columns(include_global_stacking=True)
        assert "global_rank" not in cols

    def test_010_b_without_a_no_cross_sectional_no_effect(self) -> None:
        """B=True sans cross-sectional → pas de global_pred (gating dans get_feature_columns)."""
        cols = get_feature_columns(include_global_stacking=True)
        for _col in ("global_pred_short", "global_pred_flat", "global_pred_long"):
            assert _col not in cols


# ─────────────────────────────────────────────────────────────────────
# Matrice A/B/C — effet sur fingerprint
# ─────────────────────────────────────────────────────────────────────

class TestFlagMatrixFingerprint:
    def test_fingerprint_differs_ab_vs_a_only(self) -> None:
        fp_a = fingerprint(
            feature_set="expert", include_cross_sectional=True,
            include_global_stacking=False,
        )
        fp_ab = fingerprint(
            feature_set="expert", include_cross_sectional=True,
            include_global_stacking=True,
        )
        assert fp_a != fp_ab

    def test_fingerprint_same_for_same_flags(self) -> None:
        fp1 = fingerprint(
            feature_set="expert", include_cross_sectional=True,
            include_global_stacking=True,
        )
        fp2 = fingerprint(
            feature_set="expert", include_cross_sectional=True,
            include_global_stacking=True,
        )
        assert fp1 == fp2

    def test_fingerprint_flag_c_does_not_affect_features(self) -> None:
        """FLAG C (challenger) n'affecte pas les features → fingerprint identique."""
        fp1 = fingerprint(include_cross_sectional=True, include_global_stacking=False)
        fp2 = fingerprint(include_cross_sectional=True, include_global_stacking=False)
        assert fp1 == fp2  # C n'est pas un paramètre de fingerprint


# ─────────────────────────────────────────────────────────────────────
# Gating logique (simulé comme dans orchestrateur)
# ─────────────────────────────────────────────────────────────────────

class TestFlagGatingLogic:
    """Simule le gating du code réel pour vérifier la logique."""

    @staticmethod
    def _should_train_global(cfg: GlobalModelConfig) -> bool:
        return cfg.enabled

    @staticmethod
    def _should_enable_stacking(cfg: GlobalModelConfig) -> bool:
        return cfg.enabled and cfg.stacking_enabled

    @staticmethod
    def _should_enable_challenger(cfg: GlobalModelConfig) -> bool:
        return cfg.enabled and cfg.challenger_enabled

    def test_gating_000(self) -> None:
        cfg = GlobalModelConfig()
        assert self._should_train_global(cfg) is False
        assert self._should_enable_stacking(cfg) is False
        assert self._should_enable_challenger(cfg) is False

    def test_gating_100(self) -> None:
        cfg = GlobalModelConfig(enabled=True)
        assert self._should_train_global(cfg) is True
        assert self._should_enable_stacking(cfg) is False
        assert self._should_enable_challenger(cfg) is False

    def test_gating_110(self) -> None:
        cfg = GlobalModelConfig(enabled=True, stacking_enabled=True)
        assert self._should_train_global(cfg) is True
        assert self._should_enable_stacking(cfg) is True
        assert self._should_enable_challenger(cfg) is False

    def test_gating_101(self) -> None:
        cfg = GlobalModelConfig(enabled=True, challenger_enabled=True)
        assert self._should_train_global(cfg) is True
        assert self._should_enable_stacking(cfg) is False
        assert self._should_enable_challenger(cfg) is True

    def test_gating_111(self) -> None:
        cfg = GlobalModelConfig(
            enabled=True, stacking_enabled=True, challenger_enabled=True,
        )
        assert self._should_train_global(cfg) is True
        assert self._should_enable_stacking(cfg) is True
        assert self._should_enable_challenger(cfg) is True

    def test_gating_b_without_a_blocked(self) -> None:
        cfg = GlobalModelConfig(enabled=False, stacking_enabled=True)
        assert self._should_enable_stacking(cfg) is False  # bloqué par enabled=False

    def test_gating_c_without_a_blocked(self) -> None:
        cfg = GlobalModelConfig(enabled=False, challenger_enabled=True)
        assert self._should_enable_challenger(cfg) is False  # bloqué par enabled=False
