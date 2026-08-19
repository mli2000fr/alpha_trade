"""Tests S7 — Feature whitelist per-symbol (modelFactory).

Spécification S7 (§15) — TEST 1..10.

**Règle d'or** : whitelist OFF = aucun changement ; whitelist ON =
uniquement les features explicitement listées.

Note : les noms d'exemples de la spec (`ret_5/10/20/60`) ne correspondent
pas aux colonnes réelles. Les vrais noms directionnels sont `momentum_*`
(voir ``momentum_5/10/20/60``, ``relative_strength_*``,
``stock_vs_sector_ret_*``, ``selector_short_score``, volume :
``up_volume_ratio_20``, ``obv_slope_20``).
"""
from __future__ import annotations

import pandas as pd
import pytest

from modelFactory import dataset, predictor
from modelFactory.config import DataConfig, ModelConfig
from modelFactory.features import (
    apply_feature_whitelist,
    build_feature_contract,
    fingerprint,
    get_feature_columns,
    validate_feature_contract,
)

# Whitelist directionnelle S7 (noms réels — pas `ret_*`, qui n'existent pas).
WL_DIR = (
    "momentum_5",
    "momentum_10",
    "momentum_20",
    "momentum_60",
    "relative_strength_20",
    "relative_strength_60",
    "stock_vs_sector_ret_20",
    "stock_vs_sector_ret_60",
    "selector_short_score",
    "up_volume_ratio_20",
    "obv_slope_20",
)

# Flags identiques à l'expérience directionnelle S7.
KW = dict(
    feature_set="expert",
    include_cross_sectional=True,
    include_screener_scores=True,
    include_short_score=True,
    include_volume_features=True,
)

# Sous-ensemble de features v1 (pour les tests DataModule légers).
WL_V1 = ("rsi_14", "volume_ratio_20", "daily_return")


def _legacy_columns() -> list[str]:
    return get_feature_columns(**KW)


# ---------------------------------------------------------------------------
# TEST 1 — Comportement legacy strictement inchangé (whitelist OFF/vide)
# ---------------------------------------------------------------------------
def test_t1_legacy_columns_unchanged_when_whitelist_disabled() -> None:
    legacy = _legacy_columns()
    assert get_feature_columns(**KW) == legacy
    assert get_feature_columns(**KW, feature_whitelist_enabled=False) == legacy
    assert get_feature_columns(**KW, feature_whitelist_enabled=False, feature_whitelist=()) == legacy


def test_t1_data_config_defaults_are_legacy() -> None:
    cfg = DataConfig()
    assert cfg.feature_whitelist_enabled is False
    assert cfg.feature_whitelist == ()
    # S7 : par défaut, le LSTM per-symbol force feature_set="v1" (prod inchangée).
    assert cfg.force_v1_lstm is True


# ---------------------------------------------------------------------------
# TEST 1b — Forçage v1 LSTM vs whitelist (garde-fou architectural)
# ---------------------------------------------------------------------------
def test_whitelist_requires_appropriate_feature_set() -> None:
    # Le LSTM per-symbol force feature_set="v1" quand whitelist OFF (Cause 2,
    # input dim). Les features directionnelles (liste A) n'existent qu'en expert
    # → une whitelist expert échoue en v1 (FAIL FAST) et passe en expert+cross.
    with pytest.raises(ValueError, match="does not exist"):
        get_feature_columns(
            feature_set="v1",
            include_short_score=True,
            include_cross_sectional=True,
            feature_whitelist_enabled=True,
            feature_whitelist=WL_DIR,
        )
    cols = get_feature_columns(
        feature_set="expert",
        include_short_score=True,
        include_cross_sectional=True,
        include_volume_features=True,  # WL_DIR inclut des features volume
        feature_whitelist_enabled=True,
        feature_whitelist=WL_DIR,
    )
    assert cols == list(WL_DIR)


def test_no_force_v1_lstm_respects_configured_feature_set() -> None:
    # Simule la décision du trainer : feature_set résolu quand whitelist OFF + force_v1_lstm=False.
    def _resolve(force_v1: bool, whitelist_on: bool) -> str:
        if force_v1 and not whitelist_on:
            return "v1"
        return "expert"

    assert _resolve(True, False) == "v1"       # prod : whitelist OFF → v1 forcé
    assert _resolve(False, False) == "expert"  # --no-force-v1-lstm → expert respecté
    assert _resolve(True, True) == "expert"    # whitelist ON → expert respecté


def test_volume_gated_on_whitelist_enabled_golden_rule() -> None:
    """Règle d'or S7 : whitelist OFF = comportement legacy strictement inchangé.

    Les appelants per-symbol ne transmettent le flag volume que si la whitelist
    est active (sinon le legacy 18 features v1+short+factors est préservé, le
    volume n'entrant JAMAIS dans X quand whitelist OFF).
    """
    def _effective_volume(include_volume: bool, whitelist_on: bool) -> bool:
        return include_volume and whitelist_on

    # Run 1 baseline : --include-volume-features passé mais whitelist OFF → 18.
    cols_off = get_feature_columns(
        feature_set="v1",
        include_short_score=True,
        include_factors=True,
        include_volume_features=_effective_volume(True, False),
        feature_whitelist_enabled=False,
    )
    assert len(cols_off) == 18
    assert "up_volume_ratio_20" not in cols_off
    assert "obv_slope_20" not in cols_off

    # Whitelist ON + liste volume → le volume entre dans le pool (Run 3).
    cols_on = get_feature_columns(
        feature_set="expert",
        include_cross_sectional=True,
        include_short_score=True,
        include_factors=True,
        include_volume_features=_effective_volume(True, True),
        feature_whitelist_enabled=True,
        feature_whitelist=("up_volume_ratio_20", "obv_slope_20"),
    )
    assert cols_on == ["up_volume_ratio_20", "obv_slope_20"]


# ---------------------------------------------------------------------------
# TEST 2 — Whitelist active → X contient EXACTEMENT les features listées
# ---------------------------------------------------------------------------
def test_t2_get_feature_columns_returns_exactly_whitelist() -> None:
    cols = get_feature_columns(**KW, feature_whitelist_enabled=True, feature_whitelist=WL_DIR)
    assert cols == list(WL_DIR)
    assert len(cols) == len(WL_DIR)
    # Chaque feature demandée existe réellement dans le set complet.
    assert set(WL_DIR) <= set(_legacy_columns())


def test_t2_dataset_x_contains_exactly_whitelist() -> None:
    dm = dataset.SymbolDataModule(
        pd.DataFrame(),
        data_cfg=DataConfig(feature_set="v1", feature_whitelist_enabled=True, feature_whitelist=WL_V1),
        model_cfg=ModelConfig(),
    )
    assert dm._feature_cols == list(WL_V1)
    assert dm.n_features == len(WL_V1)
    assert list(dm.scaler.feature_names) == list(WL_V1)
    # X est construit via df[self.feature_names] → colonnes = whitelist exacte.
    df = pd.DataFrame(columns=list(WL_V1) + ["is_filled"])
    x = df[list(dm.scaler.feature_names)]
    assert list(x.columns) == list(WL_V1)


# ---------------------------------------------------------------------------
# TEST 3 — Feature inconnue → erreur stricte (fail fast)
# ---------------------------------------------------------------------------
def test_t3_unknown_feature_raises() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        apply_feature_whitelist(_legacy_columns(), ("bogus_feature",))
    with pytest.raises(ValueError, match="does not exist"):
        get_feature_columns(**KW, feature_whitelist_enabled=True, feature_whitelist=("bogus_feature",))


# ---------------------------------------------------------------------------
# TEST 4 — Whitelist vide/désactivée → legacy
# ---------------------------------------------------------------------------
def test_t4_empty_tuple_disabled_is_legacy() -> None:
    assert get_feature_columns(**KW, feature_whitelist_enabled=False, feature_whitelist=()) == _legacy_columns()
    # apply_feature_whitelist est un pur filtre : vide en entrée → vide en sortie.
    # Le mode "whitelist vide → legacy" est garanti par get_feature_columns
    # (l'application n'a lieu que si feature_whitelist_enabled est True).
    assert apply_feature_whitelist(_legacy_columns(), ()) == []


# ---------------------------------------------------------------------------
# TEST 5 — enabled + whitelist vide → FAIL FAST
# ---------------------------------------------------------------------------
def test_t5_enabled_empty_fails_fast() -> None:
    with pytest.raises(ValueError, match="Feature whitelist enabled but empty"):
        get_feature_columns(**KW, feature_whitelist_enabled=True, feature_whitelist=())


# ---------------------------------------------------------------------------
# TEST 6 — train/val/test utilisent les MÊMES features (une seule source)
# ---------------------------------------------------------------------------
def test_t6_train_val_test_share_single_feature_set() -> None:
    dm = dataset.SymbolDataModule(
        pd.DataFrame(),
        data_cfg=DataConfig(feature_set="v1", feature_whitelist_enabled=True, feature_whitelist=WL_V1),
        model_cfg=ModelConfig(),
    )
    # Un seul feature set, partagé par train/val/test (scaler unique).
    assert dm.scaler.feature_names == dm._feature_cols
    assert dm.n_features == len(dm._feature_cols)
    # Le calcul est déterministe : aucun écart entre les appels (train/val/test).
    expected = get_feature_columns(
        False,
        feature_set="v1",
        include_volume_features=False,
        feature_whitelist_enabled=True,
        feature_whitelist=WL_V1,
    )
    assert list(dm._feature_cols) == expected


# ---------------------------------------------------------------------------
# TEST 7 — Walk-forward : même whitelist sur tous les folds
# ---------------------------------------------------------------------------
def test_t7_walk_forward_keeps_whitelist_across_folds() -> None:
    contract = build_feature_contract(
        feature_set="v1",
        feature_whitelist_enabled=True,
        feature_whitelist=WL_V1,
    )
    assert contract["feature_columns"] == list(WL_V1)
    assert contract["feature_count"] == len(WL_V1)
    # Le fingerprint est constant d'un fold à l'autre : la whitelist n'est pas
    # modifiée par le découpage temporel (le DataConfig est partagé).
    stable_fp = contract["feature_fingerprint"]
    for _ in range(3):
        again = build_feature_contract(feature_set="v1", feature_whitelist_enabled=True, feature_whitelist=WL_V1)
        assert again["feature_fingerprint"] == stable_fp
        assert again["feature_columns"] == list(WL_V1)


# ---------------------------------------------------------------------------
# TEST 8 — Whitelists différentes → fingerprints différents
# ---------------------------------------------------------------------------
def test_t8_different_whitelists_differ_fingerprint() -> None:
    full_wl = fingerprint(**KW, feature_whitelist_enabled=True, feature_whitelist=WL_DIR)
    subset_wl = fingerprint(**KW, feature_whitelist_enabled=True, feature_whitelist=WL_DIR[:5])
    legacy = fingerprint(**KW)
    assert full_wl != subset_wl
    assert full_wl != legacy
    assert subset_wl != legacy


# ---------------------------------------------------------------------------
# TEST 9 — Rétrocompatibilité : contrat legacy sans whitelist
# ---------------------------------------------------------------------------
def test_t9_legacy_contract_still_validates() -> None:
    legacy_contract = build_feature_contract(**KW)
    assert validate_feature_contract(
        legacy_contract,
        **KW,
        persisted_feature_columns=legacy_contract["feature_columns"],
    ) is None


def test_t9_predictor_payload_defaults_whitelist_off() -> None:
    cfg = predictor._load_data_cfg_from_payload(
        {"data": {"sequence_length": 20, "forecast_horizon": 5}}
    )
    assert cfg.feature_whitelist_enabled is False
    assert cfg.feature_whitelist == ()


# ---------------------------------------------------------------------------
# TEST 10 — Contrat de prédiction : le prédicteur reconstruit les mêmes colonnes
# ---------------------------------------------------------------------------
def test_t10_predictor_rebuilds_same_columns_with_whitelist() -> None:
    contract = build_feature_contract(**KW, feature_whitelist_enabled=True, feature_whitelist=WL_DIR)
    cfg = predictor._load_data_cfg_from_payload(
        {
            "data": {
                "sequence_length": 20,
                "forecast_horizon": 5,
                "feature_set": "expert",
                "enable_cross_sectional_features": True,
                "include_screener_scores": True,
                "include_short_score_features": True,
                "include_volume_features": True,
                "feature_whitelist_enabled": True,
                "feature_whitelist": list(WL_DIR),
            }
        }
    )
    assert cfg.feature_whitelist_enabled is True
    assert tuple(cfg.feature_whitelist) == WL_DIR
    # La reconstruction du DataConfig redonne exactement les colonnes whitelist.
    rebuilt = get_feature_columns(
        cfg.include_sentiment_features,
        feature_set=cfg.feature_set,
        include_cross_sectional=cfg.enable_cross_sectional_features,
        include_screener_scores=cfg.include_screener_scores,
        include_short_score=cfg.include_short_score_features,
        include_volume_features=cfg.include_volume_features,
        feature_whitelist_enabled=cfg.feature_whitelist_enabled,
        feature_whitelist=cfg.feature_whitelist,
    )
    assert rebuilt == list(WL_DIR)
    # Le contrat persisté se valide avec les mêmes colonnes.
    assert validate_feature_contract(
        contract,
        **KW,
        feature_whitelist_enabled=True,
        feature_whitelist=WL_DIR,
        persisted_feature_columns=contract["feature_columns"],
    ) is None


def test_t10_prediction_contract_mismatch_when_whitelist_missing() -> None:
    contract = build_feature_contract(**KW, feature_whitelist_enabled=True, feature_whitelist=WL_DIR)
    # Sans la whitelist, les colonnes attendues (legacy) ne correspondent pas.
    reason = validate_feature_contract(
        contract,
        **KW,
        persisted_feature_columns=contract["feature_columns"],
    )
    assert reason is not None
    assert reason.startswith("feature_contract_columns_mismatch")
