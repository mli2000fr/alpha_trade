from __future__ import annotations

from ihm.pages import alpaca_accounts


def test_pages_alpaca_accounts_importable() -> None:
    assert hasattr(alpaca_accounts, "__doc__")


def test_format_currency_handles_invalid_values() -> None:
    assert alpaca_accounts._format_currency("1234.5") == "$1,234.50"
    assert alpaca_accounts._format_currency(None) == "—"


def test_ihm_brokers_page_failover_doctrine() -> None:
    summary = {
        "primary_broker": "alpaca",
        "secondary_broker": "ibkr",
        "circuit_breaker_threshold": 3,
        "mode_when_tripped": "secondary_read_only",
        "writes_suspended": True,
        "resume_flag_path": "F:/projets/artifacts/failover/RESUME",
        "resume_flag_present": False,
    }

    frame = alpaca_accounts._build_failover_doctrine_dataframe(summary)

    assert not frame.empty
    values = frame.set_index("Champ")["Valeur"].to_dict()
    assert values["Broker primaire"] == "alpaca"
    assert values["Broker secondaire"] == "ibkr"
    assert values["Écritures suspendues"] == "Oui"


