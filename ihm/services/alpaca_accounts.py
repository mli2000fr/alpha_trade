"""Services IHM pour la consultation des comptes Alpaca."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from service.alpaca.accounts import AccountRegistry, BrokerAccount
from service.alpaca.trading_client import AlpacaTradingClient

_DEFAULT_ORDER_LIMIT = 200


def get_registered_accounts() -> list[BrokerAccount]:
    return AccountRegistry.get().list_accounts()


def resolve_selected_account_id(preferred_account_id: str | None = None) -> str | None:
    accounts = get_registered_accounts()
    if not accounts:
        return None
    available_ids = {account.account_id for account in accounts}
    cleaned_account_id = str(preferred_account_id or "").strip()
    if cleaned_account_id and cleaned_account_id in available_ids:
        return cleaned_account_id
    return accounts[0].account_id


def build_account_label(account: BrokerAccount) -> str:
    return f"{account.label} ({account.account_id}, {account.mode})"


def _build_client(account_id: str) -> AlpacaTradingClient:
    broker_account = AccountRegistry.get().resolve(account_id)
    return AlpacaTradingClient(
        broker_mode=broker_account.mode,
        account_id=account_id,
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_live_account(account_id: str) -> dict[str, Any]:
    payload = _build_client(account_id).get_account()
    return dict(payload) if isinstance(payload, dict) else {}


@st.cache_data(ttl=60, show_spinner=False)
def get_live_positions(account_id: str) -> pd.DataFrame:
    records = _build_client(account_id).get_positions()
    if not isinstance(records, list) or not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    preferred_columns = [
        column
        for column in [
            "symbol",
            "side",
            "qty",
            "avg_entry_price",
            "current_price",
            "market_value",
            "unrealized_pl",
            "unrealized_plpc",
            "asset_marginable",
            "asset_shortable",
        ]
        if column in df.columns
    ]
    prepared = df[preferred_columns].copy() if preferred_columns else df.copy()
    if "market_value" in prepared.columns:
        prepared["market_value"] = pd.to_numeric(prepared["market_value"], errors="coerce")
        prepared = prepared.sort_values("market_value", ascending=False, na_position="last")
    return prepared.reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def get_live_orders(account_id: str, limit: int = _DEFAULT_ORDER_LIMIT) -> pd.DataFrame:
    records = _build_client(account_id).list_orders(status="all", limit=limit)
    if not isinstance(records, list) or not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    for datetime_column in ("submitted_at", "updated_at", "filled_at", "expired_at", "canceled_at"):
        if datetime_column in df.columns:
            df[datetime_column] = pd.to_datetime(df[datetime_column], utc=True, errors="coerce")

    preferred_columns = [
        column
        for column in [
            "submitted_at",
            "updated_at",
            "filled_at",
            "symbol",
            "side",
            "type",
            "time_in_force",
            "qty",
            "filled_qty",
            "filled_avg_price",
            "limit_price",
            "stop_price",
            "status",
            "client_order_id",
            "id",
        ]
        if column in df.columns
    ]
    prepared = df[preferred_columns].copy() if preferred_columns else df.copy()
    if "submitted_at" in prepared.columns:
        prepared = prepared.sort_values("submitted_at", ascending=False, na_position="last")
    return prepared.reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def get_live_portfolio_history(
    account_id: str,
    *,
    period: str = "1M",
    timeframe: str = "1D",
) -> pd.DataFrame:
    payload = _build_client(account_id).get_portfolio_history(period=period, timeframe=timeframe)
    if not isinstance(payload, dict):
        return pd.DataFrame()

    timestamps = payload.get("timestamp")
    equity_values = payload.get("equity")
    profit_loss_values = payload.get("profit_loss")
    profit_loss_pct_values = payload.get("profit_loss_pct")
    if not isinstance(timestamps, list) or not isinstance(equity_values, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for index, raw_timestamp in enumerate(timestamps):
        if index >= len(equity_values):
            break
        timestamp = pd.to_datetime(raw_timestamp, unit="s", utc=True, errors="coerce")
        if pd.isna(timestamp):
            timestamp = pd.to_datetime(raw_timestamp, utc=True, errors="coerce")
        rows.append(
            {
                "timestamp": timestamp,
                "equity": pd.to_numeric(equity_values[index], errors="coerce"),
                "profit_loss": pd.to_numeric(
                    profit_loss_values[index] if isinstance(profit_loss_values, list) and index < len(profit_loss_values) else None,
                    errors="coerce",
                ),
                "profit_loss_pct": pd.to_numeric(
                    profit_loss_pct_values[index] if isinstance(profit_loss_pct_values, list) and index < len(profit_loss_pct_values) else None,
                    errors="coerce",
                ),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.dropna(subset=["timestamp", "equity"]).sort_values("timestamp", ascending=True)
    return df.reset_index(drop=True)

