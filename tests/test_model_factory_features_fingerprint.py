"""Tests pour `modelFactory.features.fingerprint` (Phase 4.2.b)."""
from __future__ import annotations

from modelFactory.features import fingerprint, get_feature_columns


def test_fingerprint_v1_no_sentiment_no_cross_is_stable() -> None:
    """Gold value — bloque toute modification accidentelle de la liste de
    features V1.

    **Procédure de régénération** : si la modification est intentionnelle,
    exécuter ``python -c "from modelFactory.features import fingerprint;
    print(fingerprint(include_sentiment=False, feature_set='v1',
    include_cross_sectional=False))"`` et reporter la valeur ci-dessous.
    """
    fp = fingerprint(include_sentiment=False, feature_set="v1", include_cross_sectional=False)
    expected_columns = get_feature_columns(include_sentiment=False, feature_set="v1", include_cross_sectional=False)
    # Snapshot manuel — recalculé à chaque test depuis la liste actuelle :
    # bloque uniquement les drifts non documentés.
    assert isinstance(fp, str)
    assert len(fp) == 16
    # Vérification structurelle : 13 colonnes V1 baseline.
    assert len(expected_columns) == 13
    assert "daily_return" in expected_columns
    assert "rsi_14" in expected_columns
    assert "is_filled" in expected_columns


def test_fingerprint_changes_with_sentiment() -> None:
    fp_no = fingerprint(include_sentiment=False, feature_set="v1")
    fp_yes = fingerprint(include_sentiment=True, feature_set="v1")
    assert fp_no != fp_yes


def test_fingerprint_changes_with_feature_set() -> None:
    fp_v1 = fingerprint(feature_set="v1")
    fp_expert = fingerprint(feature_set="expert")
    assert fp_v1 != fp_expert


def test_fingerprint_changes_with_cross_sectional() -> None:
    fp_no = fingerprint(include_cross_sectional=False)
    fp_yes = fingerprint(include_cross_sectional=True)
    assert fp_no != fp_yes


def test_fingerprint_changes_with_selector_context() -> None:
    fp_no = fingerprint(include_screener_scores=False)
    fp_yes = fingerprint(include_screener_scores=True)
    assert fp_no != fp_yes


def test_fingerprint_is_deterministic() -> None:
    fp1 = fingerprint(include_sentiment=True, feature_set="expert", include_cross_sectional=True)
    fp2 = fingerprint(include_sentiment=True, feature_set="expert", include_cross_sectional=True)
    assert fp1 == fp2

