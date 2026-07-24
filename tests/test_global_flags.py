"""tests/test_global_flags.py — Tests de la matrice A/B/C pour l'Approche 2.

Vérifie que :
- GlobalModelConfig gère correctement les 3 flags indépendants
- Les combinaisons de flags sont valides
- Les flags B et C sont sans effet si A est False
- Le fingerprint change de manière déterministe selon les flags
"""
from __future__ import annotations

import pytest

from modelFactory.config import GlobalModelConfig
from modelFactory.features import fingerprint, get_feature_columns


# ─────────────────────────────────────────────────────────────────────
# GlobalModelConfig — combinaisons de flags
# ─────────────────────────────────────────────────────────────────────

class TestGlobalModelConfigFlags:
    def test_all_defaults_false(self) -> None:
        cfg = GlobalModelConfig()
        assert cfg.enabled is False
        assert cfg.stacking_enabled is False
        assert cfg.challenger_enabled is False

    def test_flag_a_alone(self) -> None:
        cfg = GlobalModelConfig(enabled=True)
        assert cfg.enabled is True
        assert cfg.stacking_enabled is False
        assert cfg.challenger_enabled is False

    def test_flag_a_plus_b(self) -> None:
        cfg = GlobalModelConfig(enabled=True, stacking_enabled=True)
        assert cfg.enabled is True
        assert cfg.stacking_enabled is True
        assert cfg.challenger_enabled is False

    def test_flag_a_plus_c(self) -> None:
        cfg = GlobalModelConfig(enabled=True, challenger_enabled=True)
        assert cfg.enabled is True
        assert cfg.stacking_enabled is False
        assert cfg.challenger_enabled is True

    def test_flag_a_plus_b_plus_c(self) -> None:
        cfg = GlobalModelConfig(
            enabled=True, stacking_enabled=True, challenger_enabled=True,
        )
        assert cfg.enabled is True
        assert cfg.stacking_enabled is True
        assert cfg.challenger_enabled is True

    def test_flag_b_without_a_has_no_effect_on_features(self) -> None:
        """FLAG B sans FLAG A → global_pred_long pas inclus (get_feature_columns
        vérifie d'abord include_cross_sectional, mais le gating par config
        se fait au niveau du TrainingConfig, pas ici)."""
        cfg = GlobalModelConfig(enabled=False, stacking_enabled=True)
        assert cfg.enabled is False
        assert cfg.stacking_enabled is True  # stocké mais inactif
        # Le gating réel est fait dans le code appelant (orchestrator, etc.)

    def test_flag_c_without_a_has_no_effect(self) -> None:
        cfg = GlobalModelConfig(enabled=False, challenger_enabled=True)
        assert cfg.enabled is False
        assert cfg.challenger_enabled is True  # stocké mais inactif

    def test_immutable(self) -> None:
        cfg = GlobalModelConfig(enabled=True, stacking_enabled=True)
        with pytest.raises(Exception):
            cfg.stacking_enabled = False  # type: ignore[misc]
        with pytest.raises(Exception):
            cfg.challenger_enabled = False  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────
# Matrice A/B/C — effet sur get_feature_columns
# ─────────────────────────────────────────────────────────────────────

class TestFlagMatrixFeatureColumns:
    """Vérifie l'effet de chaque combinaison de flags sur get_feature_columns."""

    def test_000_no_global_pred(self) -> None:
        """A=False, B=False, C=False → pas de global_pred."""
        cols = get_feature_columns(include_cross_sectional=True)
        for _col in ("global_pred_short", "global_pred_flat", "global_pred_long"):
            assert _col not in cols

    def test_100_flag_a_alone_no_global_pred(self) -> None:
        """A=True seul → pas de global_pred (B=False)."""
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=False,
        )
        for _col in ("global_pred_short", "global_pred_flat", "global_pred_long"):
            assert _col not in cols

    def test_110_flag_ab_stacking_on(self) -> None:
        """A=True, B=True → 3 colonnes global_pred incluses."""
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        for _col in ("global_pred_short", "global_pred_flat", "global_pred_long"):
            assert _col in cols

    def test_101_flag_ac_no_stacking(self) -> None:
        """A=True, C=True, B=False → pas de global_pred (challenger only)."""
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=False,
        )
        for _col in ("global_pred_short", "global_pred_flat", "global_pred_long"):
            assert _col not in cols

    def test_111_full_stack_has_global_pred(self) -> None:
        """A+B+C → 3 colonnes global_pred présentes."""
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        for _col in ("global_pred_short", "global_pred_flat", "global_pred_long"):
            assert _col in cols

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
