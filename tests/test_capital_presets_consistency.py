"""A-005 — cohérence documentée entre presets de capital et profil strict.

Le chargeur doit désormais refuser :
- tout écart selector vs ``STRICT_SWING_CASH_FILTERS`` sans justification dédiée ;
- toute justification devenue obsolète ;
- tout désalignement entre les deux alias RS.
"""
from __future__ import annotations

import textwrap

import pytest

from common.capital_presets import collect_strict_profile_deviations, load_capital_presets


@pytest.fixture(scope="module")
def presets():
    return list(load_capital_presets())


def test_all_default_presets_document_current_strict_profile_deviations(presets):
    assert presets, "Aucun preset chargé"
    assert any(preset.strict_profile_justifications for preset in presets)

    for preset in presets:
        deviations = collect_strict_profile_deviations(preset)
        documented_keys = set(preset.strict_profile_justifications.keys())
        assert documented_keys == set(deviations.keys()), (
            f"{preset.key}: divergences={sorted(deviations.keys())}, "
            f"justifications={sorted(documented_keys)}"
        )
        for selector_key, reason in preset.strict_profile_justifications.items():
            assert reason.strip(), f"{preset.key}: justification vide pour {selector_key}"


def test_loading_yaml_with_undocumented_strict_profile_divergence_fails(tmp_path):
    config_path = tmp_path / "capital_presets_invalid.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            presets:
              - key: invalid_micro
                label: "Invalid"
                min_equity: 0
                max_equity: 1000
                description: "Preset volontairement invalide"
                values:
                  selector_min_beta_126: 0.7
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sans justification"):
        load_capital_presets(config_path)


def test_loading_yaml_with_stale_justification_fails(tmp_path):
    config_path = tmp_path / "capital_presets_stale.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            presets:
              - key: stale_doc
                label: "Stale"
                min_equity: 0
                max_equity: 1000
                description: "Justification devenue inutile"
                strict_profile_justifications:
                  selector_min_close: "Commentaire obsolète"
                values:
                  selector_min_close: 10.0
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="justifications devenues inutiles"):
        load_capital_presets(config_path)


def test_loading_yaml_with_rs_alias_mismatch_fails(tmp_path):
    config_path = tmp_path / "capital_presets_alias_mismatch.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            presets:
              - key: alias_mismatch
                label: "Alias mismatch"
                min_equity: 0
                max_equity: 1000
                description: "Alias RS incohérents"
                strict_profile_justifications:
                  selector_min_ibd_rs_rank: "Divergence voulue pour le test"
                values:
                  selector_min_ibd_rs_rank: 95.0
                  selector_min_relative_strength_index: 96.0
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="doivent rester identiques"):
        load_capital_presets(config_path)

