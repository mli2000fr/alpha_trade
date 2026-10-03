from datetime import date
from decimal import Decimal

import pytest
import yaml

from service.fr.execution_costs import execution_costs, load_cost_profile, resolve_liability
from service.fr.universe_contract_6a import ROOT


def profile():
    return load_cost_profile(ROOT / "config/markets/fr_execution_research_v1.yaml")


def test_separate_costs_buy_sell_and_historical_tax():
    cfg = profile()
    buy = execution_costs(cfg, side="BUY", quantity=5, reference_price=Decimal(100), settlement_date=date(2025, 4, 1), issuer_liability=True)
    assert buy["commission"] == Decimal(1)
    assert buy["spread"] == Decimal(".125")
    assert buy["slippage"] == Decimal(".25")
    assert buy["taxes"] == Decimal("2.00160")  # 5 * rounded executed price100.08 * .004
    assert buy["total"] == sum(buy[k] for k in ("commission", "spread", "slippage", "taxes"))
    old = execution_costs(cfg, side="BUY", quantity=5, reference_price=Decimal(100), settlement_date=date(2025, 3, 31), issuer_liability=True)
    assert old["taxes"] == Decimal("1.50120")
    sale = execution_costs(cfg, side="SELL", quantity=5, reference_price=Decimal(100))
    assert sale["taxes"] == 0
    assert sale["total"] == Decimal("1.375")


def test_configurable_fees_and_unknown_liability():
    cfg = profile()
    cfg["commission"]["fixed_eur_per_executed_order"] = 2
    cost = execution_costs(cfg, side="BUY", quantity=5, reference_price=Decimal(100), settlement_date=date(2024, 8, 1), issuer_liability=False)
    assert cost["commission"] == 2 and cost["taxes"] == 0
    with pytest.raises(ValueError, match="assujettissement"):
        execution_costs(cfg, side="BUY", quantity=5, reference_price=Decimal(100), settlement_date=date(2025, 4, 1))
    cancelled = execution_costs(cfg, side="BUY", quantity=5, reference_price=Decimal(100), executed=False)
    assert all(v == 0 for v in cancelled.values())


def test_stress_execution_costs_not_statutory_tax_rate():
    cost = execution_costs(profile(), side="BUY", quantity=5, reference_price=Decimal(100), settlement_date=date(2025, 4, 1), issuer_liability=True, stress_multiplier=Decimal(2))
    assert cost["commission"] == 2 and cost["spread"] == Decimal(".25") and cost["slippage"] == Decimal(".5")
    assert cost["taxes"] == Decimal("2.00300")  # acquisition price100.15; rate stays .004


def test_isin_scope_requires_unique_explicit_evidence(tmp_path):
    data = {"schema_version": 1, "market_code": "FR_EQ", "unknown_policy": "block", "instruments": []}
    path = tmp_path / "tax.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="inconnue"):
        resolve_liability(path, isin="FR_TEST", ticker="TEST.PA", settlement_date=date(2025, 4, 1))
    row = {"isin": "FR_TEST", "ticker": "TEST.PA", "from": "2025-01-01", "to": "2025-12-31", "liable": True, "evidence": "verified-reference"}
    data["instruments"] = [row]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert resolve_liability(path, isin="FR_TEST", ticker="TEST.PA", settlement_date=date(2025, 4, 1)) is True
    data["instruments"].append(row)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguë"):
        resolve_liability(path, isin="FR_TEST", ticker="TEST.PA", settlement_date=date(2025, 4, 1))
