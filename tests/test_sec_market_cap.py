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
    assert rows[0]["fiscal_period_end"].isoformat() == "2024-03-31"
    assert rows[0]["form"] == "10-Q"
    assert rows[0]["accession_number"] == "0000000000-24-000001"
    assert rows[0]["shares_outstanding"] == 50_000_000


def _usd_fact(tag_value: float) -> dict:
    return {
        "units": {"USD": [{
            "end": "2024-03-31", "val": tag_value,
            "accn": "0000000000-24-000002", "fy": 2024, "fp": "Q1",
            "form": "10-Q", "filed": "2024-05-03", "frame": "CY2024Q1",
        }]}
    }


def test_mapper_uses_financial_debt_and_keeps_dividend_unit_explicit() -> None:
    dividend = _usd_fact(0.5)
    dividend["units"] = {"USD/shares": dividend["units"]["USD"]}
    rows = extract_fundamentals_from_sec({
        "Assets": _usd_fact(1_000.0),
        "StockholdersEquity": _usd_fact(400.0),
        "Liabilities": _usd_fact(600.0),
        "LongTermDebt": _usd_fact(100.0),
        "OperatingIncomeLoss": _usd_fact(80.0),
        "CommonStockDividendsPerShareDeclared": dividend,
    }, "EXM")
    assert len(rows) == 1
    assert rows[0]["debt_to_equity"] == 0.25
    assert "ebitda" not in rows[0]
    assert rows[0]["dividend_per_share"] == 0.5
    assert "dividend_yield" not in rows[0]
