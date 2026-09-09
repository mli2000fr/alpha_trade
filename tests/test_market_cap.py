from __future__ import annotations

import pytest

from common.market_cap import compute_sec_market_cap, load_market_cap_config


def test_market_cap_config_defaults_to_sec_edgar() -> None:
    cfg = load_market_cap_config(config={})
    assert cfg.provider == "sec_edgar"
    assert cfg.max_age_days == 365
    assert cfg.missing_policy == "reject"


def test_market_cap_config_supports_explicit_eodhd_switch() -> None:
    cfg = load_market_cap_config(
        config={
            "market_cap": {
                "provider": "eodhd",
                "max_age_days": 45,
                "missing_policy": "reject",
            }
        }
    )
    assert cfg.provider == "eodhd"
    assert cfg.max_age_days == 45


def test_market_cap_config_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError, match="provider"):
        load_market_cap_config(config={"market_cap": {"provider": "auto"}})
    with pytest.raises(ValueError, match="max_age_days"):
        load_market_cap_config(config={"market_cap": {"max_age_days": -1}})
    with pytest.raises(ValueError, match="missing_policy"):
        load_market_cap_config(config={"market_cap": {"missing_policy": "allow"}})


def test_compute_sec_market_cap() -> None:
    assert compute_sec_market_cap(20.0, 50_000_000) == pytest.approx(1_000_000_000.0)
    assert compute_sec_market_cap(None, 50_000_000) is None
    assert compute_sec_market_cap(20.0, 0) is None
