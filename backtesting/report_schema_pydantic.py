"""
backtesting/report_schema_pydantic.py
=====================================
Phase D.5b (refactor) — adaptateur **Pydantic optionnel** pour le schéma
``report.json`` de backtesting.

Ce module ne s'active que si Pydantic v2 est installé (présent dans
``requirements.txt``). Sinon il définit ``PydanticBacktestReport = None`` et
``HAS_PYDANTIC = False`` afin que les call-sites puissent retomber proprement
sur les dataclasses de ``backtesting.report_schema``.

Pourquoi un adaptateur séparé plutôt que de migrer ``report_schema.py`` :

- Les dataclasses sont consommées par ``tests/test_pages_backtesting.py`` et
  par l'IHM via JSON brut. Migrer en Pydantic risquerait de casser
  l'introspection (ex : ``dataclasses.asdict``).
- Pydantic v2 apporte une **validation cross-IHM** plus stricte (coercion
  numérique automatique, sentinels ``"inf"`` typés, ``model_validate_json``
  one-shot).
- Cet adaptateur expose ``model_validate_json(text)`` qui peut être appelé
  par un futur endpoint API ou un tableau de bord externe.

Usage :

>>> from backtesting.report_schema_pydantic import HAS_PYDANTIC, PydanticBacktestReport
>>> if HAS_PYDANTIC:
...     report = PydanticBacktestReport.model_validate_json(open("report.json").read())
...     print(report.summary.sharpe_ratio)
"""
from __future__ import annotations

import math
import importlib
from typing import Any

BaseModel = object  # type: ignore[assignment,misc]
ConfigDict = dict  # type: ignore[assignment,misc]
Field = lambda *args, **kwargs: None  # type: ignore[assignment]
field_validator = lambda *args, **kwargs: (lambda func: func)  # type: ignore[assignment]

try:
    _pydantic = importlib.import_module("pydantic")
    BaseModel = _pydantic.BaseModel
    ConfigDict = _pydantic.ConfigDict
    Field = _pydantic.Field
    field_validator = _pydantic.field_validator

    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover — chemin sans dépendance.
    HAS_PYDANTIC = False
    BaseModel = object  # type: ignore[assignment,misc]
    ConfigDict = dict  # type: ignore[assignment,misc]
    Field = lambda *args, **kwargs: None  # type: ignore[assignment]
    field_validator = lambda *args, **kwargs: (lambda func: func)  # type: ignore[assignment]
    PydanticBacktestReport = None  # type: ignore[assignment]
    PydanticSummary = None  # type: ignore[assignment]


if HAS_PYDANTIC:

    def _coerce_inf(value: Any) -> float:
        """Convertit les sentinels JSON ``"inf"`` / ``"-inf"`` en floats Python.

        Le ``BacktestReport.to_serializable_dict`` utilise ces sentinels pour
        rester JSON-friendly (Phase A.7) ; on rétablit le float ici pour que
        les consommateurs Pydantic puissent comparer comme des nombres.
        """
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"inf", "+inf", "infinity"}:
                return math.inf
            if lowered in {"-inf", "-infinity"}:
                return -math.inf
        return value

    class PydanticSummary(BaseModel):  # type: ignore[no-redef]
        """Miroir Pydantic de ``BacktestReport.to_serializable_dict()``."""

        model_config = ConfigDict(extra="allow")  # forward compatibility

        initial_equity: float
        final_value: float
        total_return_pct: float
        cagr_pct: float = 0.0
        sharpe_ratio: float = 0.0
        sortino_ratio: float = 0.0
        max_drawdown_pct: float = 0.0
        total_trades: int = 0
        win_rate_pct: float = 0.0
        avg_trade_duration_days: float = 0.0
        # Phase A.5/A.6 — champs avec sentinels potentiels.
        profit_factor: float = 0.0
        calmar_ratio: float = 0.0
        ulcer_index: float = 0.0
        risk_free_rate: float = 0.0
        # Phase 6.1.c — dividendes.
        dividends_received: float = 0.0
        total_return_with_dividends_pct: float = 0.0

        @field_validator("profit_factor", "calmar_ratio", mode="before")
        @classmethod
        def _accept_inf_sentinel(cls, value: Any) -> Any:
            return _coerce_inf(value)

    class PydanticRunMetadata(BaseModel):
        """Miroir de ``backtesting.run_metadata.RunMetadata.to_dict()``."""

        model_config = ConfigDict(extra="allow")

        git_sha: str | None = None
        python_version: str | None = None
        platform: str | None = None
        dataset_hash: str | None = None
        seed: int | None = None
        timestamp_utc: str | None = None

    class PydanticBacktestReport(BaseModel):  # type: ignore[no-redef]
        """Façade Pydantic du payload ``report.json`` complet."""

        model_config = ConfigDict(extra="allow")

        summary: PydanticSummary
        params: dict[str, Any] = Field(default_factory=dict)
        artifacts: dict[str, Any] = Field(default_factory=dict)
        diagnostics: dict[str, Any] = Field(default_factory=dict)
        run_metadata: PydanticRunMetadata | None = None
        fidelity: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "HAS_PYDANTIC",
    "PydanticBacktestReport",
    "PydanticSummary",
]

