from datetime import date
from decimal import Decimal

import pytest

from service.fr.economic_qualification_12a import dividend_check, ttf_accrual, ttf_rate


def test_historical_rate_and_pna_price_rounding():
    assert ttf_rate(date(2025, 3, 31)) == Decimal(".003")
    assert ttf_rate(date(2025, 4, 1)) == Decimal(".004")
    assert ttf_accrual(date(2025, 4, 1), 10, Decimal("49.666"), issuer_liability=True) == Decimal("1.9868")
    with pytest.raises(ValueError):
        ttf_accrual(date(2025, 4, 1), 10, Decimal(50), issuer_liability=None)
    with pytest.raises(ValueError):
        ttf_rate(date(2026, 1, 1))


def test_dividend_fields_not_invented():
    event = {"date": "2025-05-01", "unadjustedValue": 1, "currency": "EUR", "paymentDate": "2025-05-05"}
    assert dividend_check(event) == []  # no declaration date needed for realized accounting
    event["paymentDate"] = None
    assert "PAYMENT_DATE_MISSING_OR_BEFORE_EX_DATE" in dividend_check(event)
    event["currency"] = None
    event["unadjustedValue"] = None
    reasons = dividend_check(event)
    assert "CURRENCY_UNKNOWN_OR_FX_REQUIRED" in reasons
    assert "UNADJUSTED_AMOUNT_INVALID_OR_MISSING" in reasons
