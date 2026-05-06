"""Phase C / S16.1 — Schéma JSON versionné du rapport mensuel."""
from __future__ import annotations

SCHEMA_VERSION = "monthly_report.v1"

JSON_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_VERSION,
    "type": "object",
    "required": [
        "schema_version",
        "account_id",
        "period_start",
        "period_end",
        "realized_pnl",
        "dividends",
        "withholding_tax",
        "fees",
        "average_slippage_bps",
        "fills_count",
        "trades_count",
        "signature",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "account_id": {"type": "string"},
        "period_start": {"type": "string", "format": "date"},
        "period_end": {"type": "string", "format": "date"},
        "realized_pnl": {"type": "number"},
        "dividends": {"type": "number"},
        "withholding_tax": {"type": "number"},
        "fees": {"type": "number"},
        "average_slippage_bps": {"type": "number"},
        "fills_count": {"type": "integer", "minimum": 0},
        "trades_count": {"type": "integer", "minimum": 0},
        "signature": {
            "type": "object",
            "required": ["algorithm", "value"],
            "properties": {
                "algorithm": {"type": "string"},
                "value": {"type": "string"},
            },
        },
    },
}

