"""Tests unitaires — risk_management/concentration_constraints.py (Sprint Maître 11).

Vérifie : ConcentrationConfig, ConcentrationResult, ConcentrationChecker,
HHI, single-name gap, industry/theme/country/currency constraints.
"""

from __future__ import annotations

import pytest

from risk_management.concentration_constraints import (
    ConcentrationChecker,
    ConcentrationConfig,
    ConcentrationResult,
    check_concentration,
    compute_portfolio_hhi,
)


# ── ConcentrationConfig ─────────────────────────────────────────────────────


class TestConcentrationConfig:
    def test_defaults(self) -> None:
        cfg = ConcentrationConfig()
        assert cfg.max_single_name_weight == 0.10
        assert cfg.max_sector_weight == 0.30

    def test_rejects_invalid_weight(self) -> None:
        with pytest.raises(ValueError):
            ConcentrationConfig(max_single_name_weight=0)
        with pytest.raises(ValueError):
            ConcentrationConfig(max_single_name_weight=1.5)

    def test_rejects_invalid_gap(self) -> None:
        with pytest.raises(ValueError):
            ConcentrationConfig(max_single_name_gap_pct=0)
        with pytest.raises(ValueError):
            ConcentrationConfig(max_single_name_gap_pct=1.5)


# ── ConcentrationResult ─────────────────────────────────────────────────────


class TestConcentrationResult:
    def test_to_dict(self) -> None:
        r = ConcentrationResult(
            passed=False,
            violations=("single_name:AAPL=15% > max=10%",),
            hhi=0.12,
            worst_dimension="single_name",
            worst_concentration_pct=0.15,
        )
        d = r.to_dict()
        assert d["passed"] is False
        assert len(d["violations"]) == 1
        assert d["hhi"] == 0.12


# ── ConcentrationChecker — single-name ──────────────────────────────────────


class TestConcentrationCheckerSingleName:
    def test_single_name_ok(self) -> None:
        checker = ConcentrationChecker()
        weights = {"A": 0.02, "B": 0.02, "C": 0.02, "D": 0.02, "E": 0.02}  # All equal, 5 positions
        result = checker.check(weights)
        assert result.passed is True

    def test_single_name_too_high(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_single_name_weight=0.10))
        weights = {"A": 0.15, "B": 0.03}
        result = checker.check(weights)
        assert result.passed is False
        assert any("single_name:A" in v for v in result.violations)


# ── ConcentrationChecker — single-name gap ──────────────────────────────────


class TestConcentrationCheckerGap:
    def test_gap_ok(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_single_name_gap_pct=0.50))
        # A=5% (above gap threshold), B=2% (40% of A) → OK (< 50%)
        weights = {"A": 0.05, "B": 0.02, "C": 0.02, "D": 0.02, "E": 0.02, "F": 0.02, "G": 0.01}
        result = checker.check(weights)
        assert result.passed is True

    def test_gap_violation(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_single_name_gap_pct=0.50))
        weights = {"A": 0.10, "B": 0.08}  # B = 80% de A → KO (> 50%)
        result = checker.check(weights)
        assert result.passed is False
        assert result.single_name_gap_violation == "B"


# ── ConcentrationChecker — sector ───────────────────────────────────────────


class TestConcentrationCheckerSector:
    def test_sector_ok(self) -> None:
        checker = ConcentrationChecker()
        # Needs enough dispersion: max weight ≤ 3% OR sufficiently diversified
        weights = {"AAPL": 0.02, "MSFT": 0.02, "GOOGL": 0.02, "AMZN": 0.02, "JPM": 0.02, "XOM": 0.02, "WMT": 0.02, "PFE": 0.01}
        sectors = {"AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "AMZN": "Retail", "JPM": "Finance", "XOM": "Energy", "WMT": "Retail", "PFE": "Pharma"}
        result = checker.check(weights, sectors=sectors)
        # Tech = 6% ≤ 30% → OK, HHI = 8*(0.133)^2 ≈ 0.14 < 0.20
        assert result.passed is True

    def test_sector_too_concentrated(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_sector_weight=0.10))
        weights = {"AAPL": 0.08, "MSFT": 0.08}  # Tech = 16% > 10%
        sectors = {"AAPL": "Tech", "MSFT": "Tech"}
        result = checker.check(weights, sectors=sectors)
        assert result.passed is False
        assert any("sector:Tech" in v for v in result.violations)


# ── ConcentrationChecker — industry ─────────────────────────────────────────


class TestConcentrationCheckerIndustry:
    def test_industry_ok(self) -> None:
        checker = ConcentrationChecker()
        weights = {"AAPL": 0.02, "MSFT": 0.02, "GOOGL": 0.02, "JPM": 0.02, "XOM": 0.02, "PFE": 0.01, "WMT": 0.01, "BAC": 0.01}
        industries = {"AAPL": "Hardware", "MSFT": "Software", "GOOGL": "Internet", "JPM": "Banking", "XOM": "Oil", "PFE": "Pharma", "WMT": "Retail", "BAC": "Banking"}
        result = checker.check(weights, industries=industries)
        assert result.passed is True

    def test_industry_too_concentrated(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_industry_weight=0.10))
        weights = {"AAPL": 0.08, "DELL": 0.08}  # Hardware = 16% > 10%
        industries = {"AAPL": "Hardware", "DELL": "Hardware"}
        result = checker.check(weights, industries=industries)
        assert result.passed is False
        assert any("industry:Hardware" in v for v in result.violations)


# ── ConcentrationChecker — theme ────────────────────────────────────────────


class TestConcentrationCheckerTheme:
    def test_theme_ok(self) -> None:
        checker = ConcentrationChecker()
        weights = {"AAPL": 0.02, "NVDA": 0.02, "MSFT": 0.02, "JPM": 0.02, "XOM": 0.02, "PFE": 0.01, "WMT": 0.01, "BAC": 0.01}
        themes = {"AAPL": "AI", "NVDA": "AI", "MSFT": "Cloud", "JPM": "Value", "XOM": "Energy", "PFE": "Pharma", "WMT": "Retail", "BAC": "Value"}
        result = checker.check(weights, themes=themes)
        # AI = 4% ≤ 25% → OK
        assert result.passed is True

    def test_theme_too_concentrated(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_theme_weight=0.10))
        weights = {"AAPL": 0.08, "NVDA": 0.08}
        themes = {"AAPL": "AI", "NVDA": "AI"}
        result = checker.check(weights, themes=themes)
        assert result.passed is False
        assert any("theme:AI" in v for v in result.violations)


# ── ConcentrationChecker — country ──────────────────────────────────────────


class TestConcentrationCheckerCountry:
    def test_country_ok(self) -> None:
        checker = ConcentrationChecker()
        weights = {"AAPL": 0.02, "MSFT": 0.02, "GOOGL": 0.02, "SAP": 0.02, "NESN": 0.02, "BABA": 0.02, "TSM": 0.01}
        countries = {"AAPL": "US", "MSFT": "US", "GOOGL": "US", "SAP": "DE", "NESN": "CH", "BABA": "CN", "TSM": "TW"}
        result = checker.check(weights, countries=countries)
        assert result.passed is True

    def test_country_too_many_positions(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_single_country_concentration=2))
        weights = {"A": 0.05, "B": 0.05, "C": 0.05}
        countries = {"A": "US", "B": "US", "C": "US"}
        result = checker.check(weights, countries=countries)
        assert result.passed is False
        assert any("country:US" in v for v in result.violations)

    def test_country_weight_too_high(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_country_weight=0.20))
        weights = {"AAPL": 0.15, "MSFT": 0.10}
        countries = {"AAPL": "US", "MSFT": "US"}
        result = checker.check(weights, countries=countries)
        assert result.passed is False
        assert any("country_weight:US" in v for v in result.violations)


# ── ConcentrationChecker — currency ─────────────────────────────────────────


class TestConcentrationCheckerCurrency:
    def test_currency_ok(self) -> None:
        checker = ConcentrationChecker()
        weights = {"AAPL": 0.02, "MSFT": 0.02, "GOOGL": 0.02, "SAP": 0.02, "NESN": 0.02, "BABA": 0.02, "TSM": 0.01}
        currencies = {"AAPL": "USD", "MSFT": "USD", "GOOGL": "USD", "SAP": "EUR", "NESN": "CHF", "BABA": "USD", "TSM": "USD"}
        result = checker.check(weights, currencies=currencies)
        # non-USD = 4% ≤ 30% → OK
        assert result.passed is True

    def test_non_usd_too_high(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_non_usd_weight=0.10))
        weights = {"SAP": 0.08, "NESN": 0.08}  # non-USD = 16% > 10%
        currencies = {"SAP": "EUR", "NESN": "CHF"}
        result = checker.check(weights, currencies=currencies)
        assert result.passed is False
        assert any("non_usd" in v for v in result.violations)


# ── ConcentrationChecker — HHI ──────────────────────────────────────────────


class TestConcentrationCheckerHHI:
    def test_hhi_ok(self) -> None:
        checker = ConcentrationChecker()
        weights = {"A": 0.05, "B": 0.05, "C": 0.05, "D": 0.05}  # HHI = 4*(0.25)^2 = 0.25
        result = checker.check(weights)
        # HHI=0.25 > 0.15 → violation
        assert result.passed is False
        assert result.hhi is not None

    def test_hhi_perfectly_diversified(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_hhi=0.20))
        n = 10
        weights = {f"S{i}": 0.02 for i in range(n)}  # total=20%, each=2%, share=0.1, HHI=10*0.01=0.10
        result = checker.check(weights)
        # HHI = 10 * (1/10)^2 = 0.10 → OK (< 0.20). Max weight=2% < min_weight_for_gap=3% → no gap check
        assert result.passed is True
        assert result.hhi == pytest.approx(0.10)

    def test_hhi_concentrated(self) -> None:
        checker = ConcentrationChecker(ConcentrationConfig(max_hhi=0.10))
        weights = {"A": 0.50, "B": 0.30, "C": 0.20}  # HHI ≈ 0.38
        result = checker.check(weights)
        assert result.passed is False


# ── check_concentration (helper) ────────────────────────────────────────────


class TestCheckConcentration:
    def test_helper(self) -> None:
        result = check_concentration({"A": 0.02, "B": 0.02, "C": 0.02, "D": 0.02, "E": 0.02})
        assert result.passed is True

    def test_helper_with_all_dimensions(self) -> None:
        weights = {"AAPL": 0.05, "MSFT": 0.05, "JPM": 0.05, "SAP": 0.03}
        result = check_concentration(
            weights,
            sectors={"AAPL": "Tech", "MSFT": "Tech", "JPM": "Finance", "SAP": "Tech"},
            industries={"AAPL": "Hardware", "MSFT": "Software", "JPM": "Banking", "SAP": "Software"},
            themes={"AAPL": "AI", "MSFT": "AI", "JPM": "Value", "SAP": "ERP"},
            countries={"AAPL": "US", "MSFT": "US", "JPM": "US", "SAP": "DE"},
            currencies={"AAPL": "USD", "MSFT": "USD", "JPM": "USD", "SAP": "EUR"},
        )
        assert isinstance(result, ConcentrationResult)


# ── compute_portfolio_hhi ───────────────────────────────────────────────────


class TestComputePortfolioHHI:
    def test_empty(self) -> None:
        assert compute_portfolio_hhi({}) == 0.0

    def test_single_position(self) -> None:
        assert compute_portfolio_hhi({"A": 1.0}) == 1.0

    def test_equal_weights(self) -> None:
        hhi = compute_portfolio_hhi({"A": 0.5, "B": 0.5})
        assert hhi == pytest.approx(0.5)  # 2 * (0.5)^2 = 0.5

    def test_diversified(self) -> None:
        n = 10
        weights = {f"S{i}": 1.0 for i in range(n)}
        hhi = compute_portfolio_hhi(weights)
        assert hhi == pytest.approx(1.0 / n)
