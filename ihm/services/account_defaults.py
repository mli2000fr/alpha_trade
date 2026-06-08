"""Aides de préremplissage IHM à partir du compte Alpaca sélectionné."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from service.alpaca.accounts import AccountRegistry
from service.alpaca.trading_client import AlpacaTradingClient


@dataclass(frozen=True, slots=True)
class PipelineExecutionDefaults:
    """Valeurs de préremplissage déduites du compte broker courant."""

    account_id: str
    broker_mode: str
    equity: float | None
    account_type: Literal["margin", "cash"] | None = None
    swing_only: bool | None = None


def _safe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _extract_equity(snapshot: dict[str, object]) -> float | None:
    return _safe_float(snapshot.get("equity") or snapshot.get("portfolio_value"))


def _infer_account_type(snapshot: dict[str, object]) -> Literal["margin", "cash"] | None:
    explicit_type = str(snapshot.get("account_type") or snapshot.get("type") or "").strip().lower()
    if explicit_type in {"margin", "cash"}:
        return explicit_type  # type: ignore[return-value]

    multiplier = _safe_float(snapshot.get("multiplier"))
    if multiplier is None:
        return None
    if multiplier <= 1.0:
        return "cash"
    return "margin"


def get_pipeline_execution_defaults(account_id: str | None) -> PipelineExecutionDefaults | None:
    """Retourne des valeurs par défaut si elles sont déductibles de manière fiable.

    Règles produit :
    - `account_type` est prérempli seulement si le broker le rend explicite ou déductible.
    - `swing_only` reste manuel : ce choix relève d'une préférence d'exécution, pas d'un simple montant.
    """

    cleaned_account_id = (account_id or "").strip()
    if not cleaned_account_id:
        return None

    broker_account = AccountRegistry.get().resolve(cleaned_account_id)
    snapshot = AlpacaTradingClient(
        broker_mode=broker_account.mode,
        account_id=cleaned_account_id,
    ).get_account()

    account_type = _infer_account_type(snapshot)
    equity = _extract_equity(snapshot)

    return PipelineExecutionDefaults(
        account_id=cleaned_account_id,
        broker_mode=broker_account.mode,
        equity=equity,
        account_type=account_type,
        swing_only=None,
    )
