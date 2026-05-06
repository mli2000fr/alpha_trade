"""Sprint S3 / A-009 — `selector_min_weekly_trend_score` ne doit pas vider l'univers.

`weekly_trend_score` est borné dans [0, 1] (cf. ``core/filter_profiles.py``).
Imposer 1.0 strict-égal-au-max revient à exiger un score parfait, ce qui
vide l'univers en pratique. Garde-fou anti-régression : aucun preset ne
doit imposer 1.0.

On vérifie aussi qu'un échantillon synthétique réaliste de 200 symboles
laisse au moins 5 candidats par préset après application du seuil.
"""
from __future__ import annotations

import random

import pytest

from common.capital_presets import load_capital_presets


@pytest.fixture(scope="module")
def presets():
    return list(load_capital_presets())


def test_no_preset_imposes_strict_1_threshold(presets):
    """Aucun preset ne doit avoir min_weekly_trend_score >= 1.0 strict."""
    for preset in presets:
        score = float(preset.values.get("selector_min_weekly_trend_score", 0.0))
        assert score < 1.0, (
            f"Preset '{preset.key}' impose selector_min_weekly_trend_score={score} "
            f">= 1.0 — risque de vider l'univers (A-009)."
        )


def test_threshold_in_realistic_range(presets):
    """Plage réaliste : [0.5, 0.99]."""
    for preset in presets:
        score = float(preset.values.get("selector_min_weekly_trend_score", 0.0))
        assert 0.5 <= score <= 0.99, (
            f"Preset '{preset.key}' selector_min_weekly_trend_score={score} hors plage."
        )


def test_synthetic_universe_yields_at_least_5_candidates_per_preset(presets):
    """Distribution synthétique : 200 symboles, weekly_trend_score ~ Beta(2, 2)
    déplacée vers [0.4, 1.0]. Pour chaque preset, le seuil doit laisser ≥ 5 candidats."""
    rng = random.Random(42)
    # Distribution semi-réaliste : 50 % ∈ [0.7, 0.9], queue droite ∈ [0.9, 1.0].
    universe = []
    for _ in range(200):
        r = rng.random()
        if r < 0.5:
            universe.append(rng.uniform(0.7, 0.9))
        elif r < 0.85:
            universe.append(rng.uniform(0.9, 0.97))
        else:
            universe.append(rng.uniform(0.97, 1.0))

    for preset in presets:
        threshold = float(preset.values.get("selector_min_weekly_trend_score", 0.0))
        passing = [s for s in universe if s >= threshold]
        assert len(passing) >= 5, (
            f"Preset '{preset.key}' (seuil {threshold}) ne laisse que "
            f"{len(passing)} candidats sur 200 — risque univers vide."
        )


def test_thresholds_monotonic_with_account_size(presets):
    """Les seuils doivent rester monotones croissants par tranche d'equity."""
    scores = [float(p.values.get("selector_min_weekly_trend_score", 0.0)) for p in presets]
    assert scores == sorted(scores), (
        f"weekly_trend_score doit être croissant entre presets : {scores}"
    )

