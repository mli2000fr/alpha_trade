"""Alias typés transverses partagés par tout le projet Alpha Trade.

Phase 2 du refactor (`prompt/refactor/plan.md` §2.1).

Évite la prolifération de `str` partout pour des identifiants métier
distincts (symbole boursier, identifiant compte, ID de run...) et
documente les conventions canoniques (adjustment, feed) au même endroit.
"""
from __future__ import annotations

from typing import Literal, NewType

# --- Identifiants métier (NewType pour distinguer en mypy) -----------------

Symbol = NewType("Symbol", str)
"""Symbole boursier normalisé (UPPER, sans espaces). Ex: ``AAPL``."""

AccountId = NewType("AccountId", str)
"""Identifiant de compte multi-broker (Alpaca paper / live). Ex: ``paper1``."""

RunId = NewType("RunId", str)
"""Identifiant unique d'un run pipeline (UUID4 en général)."""

RiskRunId = NewType("RiskRunId", str)
"""Identifiant d'un run risk_management (`risk_runs.run_id`)."""

ExecutionRunId = NewType("ExecutionRunId", str)
"""Identifiant d'un run execution_engine (`execution_runs.run_id`)."""


# --- Conventions canoniques (Literal pour validation statique) -------------

Adjustment = Literal["split", "all", "raw"]
"""Politique d'ajustement Alpaca data v2.

Convention projet : ``"split"`` partout (cf. CHECK SQL `chk_bars_adj`,
`README.md` §"Conventions clés", `doc/dataIntegrityEngine.md`).
"""

Feed = Literal["iex", "sip"]
"""Feed Alpaca data v2.

Convention projet : ``"iex"`` par défaut (offre gratuite, biais documenté
dans `audit_dataIntegrityEngine.md`).
"""

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
TimeInForce = Literal["day", "gtc", "ioc", "fok", "opg", "cls"]

AccountMode = Literal["paper", "live"]


__all__ = [
    "AccountId",
    "AccountMode",
    "Adjustment",
    "ExecutionRunId",
    "Feed",
    "OrderSide",
    "OrderType",
    "RiskRunId",
    "RunId",
    "Symbol",
    "TimeInForce",
]

