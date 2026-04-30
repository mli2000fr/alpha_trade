"""Tests Phase D.5b — adaptateur Pydantic optionnel pour `report.json`."""
from __future__ import annotations

import math

import pytest

from backtesting.report_schema_pydantic import HAS_PYDANTIC

if not HAS_PYDANTIC:
    pytest.skip("pydantic non installé", allow_module_level=True)

from backtesting.report_schema_pydantic import PydanticBacktestReport, PydanticSummary  # noqa: E402


class TestPydanticReportSchema:
    def _minimal_payload(self) -> dict:
        return {
            "summary": {
                "initial_equity": 100_000.0,
                "final_value": 110_000.0,
                "total_return_pct": 10.0,
                "sharpe_ratio": 1.25,
            },
        }

    def test_accepts_minimal_payload_and_defaults_missing_fields(self):
        report = PydanticBacktestReport.model_validate(self._minimal_payload())
        assert report.summary.initial_equity == 100_000.0
        assert report.summary.cagr_pct == 0.0  # défaut
        assert report.params == {}
        assert report.run_metadata is None

    def test_accepts_inf_sentinel_for_profit_factor_and_calmar(self):
        payload = self._minimal_payload()
        payload["summary"]["profit_factor"] = "inf"
        payload["summary"]["calmar_ratio"] = "+inf"
        report = PydanticBacktestReport.model_validate(payload)
        assert math.isinf(report.summary.profit_factor)
        assert math.isinf(report.summary.calmar_ratio)

    def test_accepts_negative_inf_sentinel(self):
        payload = self._minimal_payload()
        payload["summary"]["calmar_ratio"] = "-inf"
        report = PydanticBacktestReport.model_validate(payload)
        assert math.isinf(report.summary.calmar_ratio) and report.summary.calmar_ratio < 0

    def test_extra_fields_are_tolerated_forward_compat(self):
        payload = self._minimal_payload()
        payload["summary"]["future_metric"] = 42.0
        payload["future_section"] = {"foo": "bar"}
        # Ne lève pas grâce à `extra="allow"`.
        report = PydanticBacktestReport.model_validate(payload)
        assert report.summary.model_extra["future_metric"] == 42.0

    def test_run_metadata_parsed_when_present(self):
        payload = self._minimal_payload()
        payload["run_metadata"] = {
            "git_sha": "abc123",
            "python_version": "3.12.7",
            "seed": 42,
        }
        report = PydanticBacktestReport.model_validate(payload)
        assert report.run_metadata is not None
        assert report.run_metadata.git_sha == "abc123"
        assert report.run_metadata.seed == 42

    def test_summary_must_be_present(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PydanticBacktestReport.model_validate({"params": {}})

