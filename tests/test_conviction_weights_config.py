"""Sprint S8 — Tests de calibration formelle des poids de conviction.

Vérifie :

- la section ``conviction:`` est bien présente dans ``config.yaml`` ;
- :meth:`SentimentBoostConfig.from_global_config` applique les poids YAML ;
- les overrides programmatiques priment sur YAML ;
- la validation somme = 1.0 reste appliquée ;
- :class:`core.conviction.SentimentFusionWeights` reflète bien les valeurs.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_config_yaml_contains_conviction_weights():
    """La section ``conviction:`` doit être présente avec les 3 poids."""
    repo_root = Path(__file__).resolve().parents[1]
    raw = (repo_root / "config.yaml").read_text(encoding="utf-8")
    assert "conviction:" in raw
    assert "quant_weight" in raw
    assert "sentiment_weight" in raw
    assert "macro_weight" in raw


def test_sentiment_boost_config_reads_global_yaml():
    """Charge la config YAML réelle et vérifie que les poids sont appliqués."""
    from event_sentiment.signal_aggregator import SentimentBoostConfig
    from common.config_loader import load_config

    cfg = load_config() or {}
    expected = cfg.get("conviction") or {}
    boost = SentimentBoostConfig.from_global_config(cfg)

    if "quant_weight" in expected:
        assert boost.quant_weight == pytest.approx(float(expected["quant_weight"]))
    if "sentiment_weight" in expected:
        assert boost.sentiment_weight == pytest.approx(float(expected["sentiment_weight"]))
    if "macro_weight" in expected:
        assert boost.macro_sector_weight == pytest.approx(float(expected["macro_weight"]))


def test_from_global_config_overrides_take_precedence():
    from event_sentiment.signal_aggregator import SentimentBoostConfig

    cfg = {"conviction": {"quant_weight": 0.5, "sentiment_weight": 0.3, "macro_weight": 0.2}}
    boost = SentimentBoostConfig.from_global_config(
        cfg, quant_weight=0.6, sentiment_weight=0.3, macro_sector_weight=0.1
    )
    assert boost.quant_weight == pytest.approx(0.6)
    assert boost.sentiment_weight == pytest.approx(0.3)
    assert boost.macro_sector_weight == pytest.approx(0.1)


def test_from_global_config_uses_defaults_when_section_missing():
    from event_sentiment.signal_aggregator import SentimentBoostConfig

    boost = SentimentBoostConfig.from_global_config({})
    # Défauts historiques 75 / 15 / 10
    assert boost.quant_weight == pytest.approx(0.75)
    assert boost.sentiment_weight == pytest.approx(0.15)
    assert boost.macro_sector_weight == pytest.approx(0.10)


def test_from_global_config_rejects_non_unit_sum():
    from event_sentiment.signal_aggregator import SentimentBoostConfig

    cfg = {"conviction": {"quant_weight": 0.5, "sentiment_weight": 0.5, "macro_weight": 0.5}}
    with pytest.raises(ValueError, match="égal à 1.0"):
        SentimentBoostConfig.from_global_config(cfg)


def test_to_fusion_weights_round_trip():
    from event_sentiment.signal_aggregator import SentimentBoostConfig
    from core.conviction import SentimentFusionWeights

    boost = SentimentBoostConfig.from_global_config(
        {"conviction": {"quant_weight": 0.7, "sentiment_weight": 0.2, "macro_weight": 0.1}}
    )
    fusion = boost.to_fusion_weights()
    assert isinstance(fusion, SentimentFusionWeights)
    assert fusion.quant_weight == pytest.approx(0.7)
    assert fusion.sentiment_weight == pytest.approx(0.2)
    assert fusion.macro_weight == pytest.approx(0.1)

