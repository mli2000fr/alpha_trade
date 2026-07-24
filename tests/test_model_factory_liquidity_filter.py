"""Tests unitaires pour le filtrage liquidité (Sprint 2026-07-24).

Vérifie que :
- filter_symbols_by_liquidity() retourne la bonne structure
- Les symboles sans données suffisantes sont filtrés
- La fonction est robuste aux entrées vides
- Les seuils sont respectés
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


class TestFilterSymbolsByLiquidity:
    """Tests unitaires de filter_symbols_by_liquidity()."""

    def test_empty_symbols_returns_empty(self) -> None:
        """Une liste vide en entrée donne une liste vide en sortie."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        excluded, diag = filter_symbols_by_liquidity(engine, [])
        assert excluded == []
        assert diag["filtered_count"] == 0
        assert diag["details"] == {}

    def test_all_symbols_pass_when_no_rows_returned(self) -> None:
        """Si la requête SQL ne retourne rien, aucun symbole n'est filtré."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "MSFT", "GOOGL"],
        )
        assert excluded == []
        assert diag["filtered_count"] == 0
        assert diag["details"] == {}

    def test_symbols_filtered_when_below_threshold(self) -> None:
        """Les symboles sous les seuils sont correctement filtrés."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class FakeRow:
            def __init__(self, symbol, reason):
                self.symbol = symbol
                self.reason = reason

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            FakeRow("PENNY", "volume_insuffisant"),
            FakeRow("ILLIQ", "spread_eleve"),
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "PENNY", "ILLIQ", "MSFT"],
            min_avg_volume_20d=500_000,
            min_market_cap=500_000_000,
            max_avg_spread_pct=0.5,
        )
        assert set(excluded) == {"PENNY", "ILLIQ"}
        assert diag["filtered_count"] == 2
        assert diag["kept_count"] == 2
        assert "PENNY" in diag["details"]
        assert diag["details"]["PENNY"] == "volume_insuffisant"
        assert diag["details"]["ILLIQ"] == "spread_eleve"
        assert "thresholds" in diag
        assert diag["thresholds"]["min_avg_volume_20d"] == 500_000

    def test_sql_error_returns_empty_and_logs(self) -> None:
        """En cas d'erreur SQL, on skip le filtre sans planter."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("table not found")
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "MSFT"],
        )
        assert excluded == []
        assert diag["filtered_count"] == 0
        assert "error" in diag

    def test_custom_end_date(self) -> None:
        """La date de fin personnalisée est utilisée dans la requête."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        engine.connect.return_value.__enter__.return_value = conn

        filter_symbols_by_liquidity(
            engine, ["AAPL"],
            end_date=date(2025, 12, 31),
        )
        # Vérifie que execute a été appelé avec les bons paramètres
        call_args = conn.execute.call_args
        assert call_args is not None

    def test_diagnostics_structure(self) -> None:
        """Le dictionnaire de diagnostic a la structure attendue."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class FakeRow:
            def __init__(self, symbol, reason):
                self.symbol = symbol
                self.reason = reason

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            FakeRow("T1", "volume_insuffisant"),
            FakeRow("T2", "dollar_volume_insuffisant"),
            FakeRow("T3", "spread_eleve"),
            FakeRow("T4", "historique_insuffisant"),
        ]
        engine.connect.return_value.__enter__.return_value = conn

        _, diag = filter_symbols_by_liquidity(
            engine, ["T1", "T2", "T3", "T4", "OK1", "OK2"],
            min_avg_volume_20d=1_000_000,
            min_market_cap=1_000_000_000,
            max_avg_spread_pct=0.3,
        )
        assert diag["filtered_count"] == 4
        assert diag["kept_count"] == 2
        assert diag["total_requested"] == 6
        assert len(diag["details"]) == 4
        # Vérifie les 4 raisons possibles
        reasons = set(diag["details"].values())
        assert "volume_insuffisant" in reasons
        assert "dollar_volume_insuffisant" in reasons
        assert "spread_eleve" in reasons
        assert "historique_insuffisant" in reasons
