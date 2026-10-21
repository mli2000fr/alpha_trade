import pytest
from scripts.research.multi_asset_trend_audit import near


def test_reconciliation_rejects_material_mismatch():
    near(4000,4000,'NAV')
    with pytest.raises(ValueError,match='NAV'):near(4001,4000,'NAV')


def test_reconciliation_rejects_nan():
    with pytest.raises(ValueError):near(float('nan'),0,'Invalid number')
