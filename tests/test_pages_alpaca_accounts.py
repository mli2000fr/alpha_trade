from __future__ import annotations

from ihm.pages import alpaca_accounts


def test_pages_alpaca_accounts_importable() -> None:
    assert hasattr(alpaca_accounts, "__doc__")


def test_format_currency_handles_invalid_values() -> None:
    assert alpaca_accounts._format_currency("1234.5") == "$1,234.50"
    assert alpaca_accounts._format_currency(None) == "—"


def test_sync_page_account_selector_state_adopts_sidebar_selection_when_page_widget_is_stale(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_accounts, "resolve_selected_account_id", lambda preferred_account_id=None: str(preferred_account_id or "acct-1"))
    session_state: dict[str, object] = {
        "selected_account_id": "acct-2",
        alpaca_accounts._PAGE_ACCOUNT_SELECT_KEY: "acct-1",
        alpaca_accounts._PAGE_ACCOUNT_LAST_SYNC_KEY: "acct-1",
    }

    selected_account_id = alpaca_accounts._sync_page_account_selector_state(session_state, ["acct-1", "acct-2"])

    assert selected_account_id == "acct-2"
    assert session_state[alpaca_accounts._PAGE_ACCOUNT_SELECT_KEY] == "acct-2"
    assert session_state[alpaca_accounts._PAGE_ACCOUNT_LAST_SYNC_KEY] == "acct-2"


def test_sync_page_account_selector_state_promotes_page_selection_to_global_state(monkeypatch) -> None:
    monkeypatch.setattr(alpaca_accounts, "resolve_selected_account_id", lambda preferred_account_id=None: str(preferred_account_id or "acct-1"))
    session_state: dict[str, object] = {
        "selected_account_id": "acct-1",
        alpaca_accounts._PAGE_ACCOUNT_SELECT_KEY: "acct-2",
        alpaca_accounts._PAGE_ACCOUNT_LAST_SYNC_KEY: "acct-1",
    }

    selected_account_id = alpaca_accounts._sync_page_account_selector_state(session_state, ["acct-1", "acct-2"])

    assert selected_account_id == "acct-2"
    assert session_state["selected_account_id"] == "acct-2"
    assert session_state[alpaca_accounts._PAGE_ACCOUNT_LAST_SYNC_KEY] == "acct-2"


