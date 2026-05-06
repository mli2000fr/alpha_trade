"""Phase C / S16.3 — Module conformité fiscale (US, équivalent 1099-B)."""
from tax.wash_sale import (  # noqa: F401
    Lot,
    WashSaleAdjustment,
    WashSaleReport,
    WASH_WINDOW_DAYS,
    detect_wash_sales,
)

__all__ = [
    "Lot",
    "WashSaleAdjustment",
    "WashSaleReport",
    "WASH_WINDOW_DAYS",
    "detect_wash_sales",
]

