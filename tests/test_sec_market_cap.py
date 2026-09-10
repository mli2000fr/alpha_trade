from __future__ import annotations

from service.sec import clientEdgar
from service.sec.xbrl_mapper import extract_fundamentals_from_sec


def _shares_fact(value: int) -> dict:
    return {
        "units": {
            "shares": [
                {
                    "end": "2024-03-31",
                    "val": value,
                    "accn": "0000000000-24-000001",
                    "fy": 2024,
                    "fp": "Q1",
                    "form": "10-Q",
                    "filed": "2024-05-02",
                    "frame": "CY2024Q1I",
                }
            ]
        }
    }


def test_client_merges_dei_entity_shares_into_mapper_payload(monkeypatch) -> None:
    monkeypatch.setattr(clientEdgar, "ticker_to_cik", lambda symbol: "0000000001")
    monkeypatch.setattr(
        clientEdgar,
        "fetch_company_facts",
        lambda cik: {
            "entityName": "Example Inc.",
            "facts": {
                "us-gaap": {},
                "dei": {"EntityCommonStockSharesOutstanding": _shares_fact(50_000_000)},
            },
        },
    )

    record = clientEdgar.fetch_symbol_fundamentals_record("EXM")

    assert "EntityCommonStockSharesOutstanding" in record["raw_facts"]


def test_mapper_extracts_dei_shares_at_filing_date() -> None:
    raw_facts = {
        "EntityCommonStockSharesOutstanding": _shares_fact(50_000_000),
        "Assets": {
            "units": {
                "USD": [
                    {
                        "end": "2024-03-31",
                        "val": 1_000_000_000,
                        "accn": "0000000000-24-000001",
                        "fy": 2024,
                        "fp": "Q1",
                        "form": "10-Q",
                        "filed": "2024-05-02",
                        "frame": "CY2024Q1I",
                    }
                ]
            }
        },
    }

    rows = extract_fundamentals_from_sec(raw_facts, "EXM")

    assert len(rows) == 1
    assert rows[0]["trade_date"].isoformat() == "2024-05-02"
    assert rows[0]["shares_outstanding"] == 50_000_000
