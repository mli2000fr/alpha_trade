"""Tests unitaires pour le filtrage liquidité (Sprint 2026-07-24).

Vérifie que :
- filter_symbols_by_liquidity() retourne la bonne structure
- Les symboles sans données suffisantes sont filtrés
- La fonction est robuste aux entrées vides
- Les seuils sont respectés
- Le filtre spread bid-ask (stock_quote_snapshots) fonctionne avec les 3 fallback modes
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


def _disable_spread(kwargs: dict) -> dict:
    """Désactive le filtre spread pour les tests qui ne le concernent pas."""
    kwargs.setdefault("max_spread_bps", 0.0)
    return kwargs


class TestFilterSymbolsByLiquidity:
    """Tests unitaires de filter_symbols_by_liquidity()."""

    def test_empty_symbols_returns_empty(self) -> None:
        """Une liste vide en entrée donne une liste vide en sortie."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        excluded, diag = filter_symbols_by_liquidity(engine, [], **_disable_spread({}))
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
            engine, ["AAPL", "MSFT", "GOOGL"], **_disable_spread({}),
        )
        assert excluded == []
        assert diag["filtered_count"] == 0
        assert diag["details"] == {}

    def test_symbols_filtered_when_below_threshold(self) -> None:
        """Les symboles sous les seuils sont correctement filtrés."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class FakeRow:
            def __init__(self, symbol, reason, avg_volume_20d=100000, avg_dollar_volume_20d=5000000,
                         avg_high_low_range_pct=1.5, nb_days=20):
                self.symbol = symbol
                self.reason = reason
                self.avg_volume_20d = avg_volume_20d
                self.avg_dollar_volume_20d = avg_dollar_volume_20d
                self.avg_high_low_range_pct = avg_high_low_range_pct
                self.nb_days = nb_days

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            FakeRow("PENNY", "volume_insuffisant"),
            FakeRow("ILLIQ", "range_eleve"),
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "PENNY", "ILLIQ", "MSFT"],
            **_disable_spread({
                "min_avg_volume_20d": 500_000,
                "min_market_cap": 500_000_000,
                "max_avg_high_low_range_pct": 0.5,
            }),
        )
        assert set(excluded) == {"PENNY", "ILLIQ"}
        assert diag["filtered_count"] == 2
        assert diag["kept_count"] == 2
        assert "PENNY" in diag["details"]
        assert diag["details"]["PENNY"] == "volume_insuffisant"
        assert diag["details"]["ILLIQ"] == "range_eleve"
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
            engine, ["AAPL", "MSFT"], **_disable_spread({}),
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
            **_disable_spread({}),
        )
        # Vérifie que execute a été appelé avec les bons paramètres
        call_args = conn.execute.call_args
        assert call_args is not None

    def test_diagnostics_structure(self) -> None:
        """Le dictionnaire de diagnostic a la structure attendue."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class FakeRow:
            def __init__(self, symbol, reason, avg_volume_20d=100000, avg_dollar_volume_20d=5000000,
                         avg_high_low_range_pct=1.5, nb_days=20):
                self.symbol = symbol
                self.reason = reason
                self.avg_volume_20d = avg_volume_20d
                self.avg_dollar_volume_20d = avg_dollar_volume_20d
                self.avg_high_low_range_pct = avg_high_low_range_pct
                self.nb_days = nb_days

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            FakeRow("T1", "volume_insuffisant"),
            FakeRow("T2", "market_cap_insuffisant"),
            FakeRow("T3", "range_eleve"),
            FakeRow("T4", "historique_insuffisant"),
        ]
        engine.connect.return_value.__enter__.return_value = conn

        _, diag = filter_symbols_by_liquidity(
            engine, ["T1", "T2", "T3", "T4", "OK1", "OK2"],
            **_disable_spread({
                "min_avg_volume_20d": 1_000_000,
                "min_market_cap": 1_000_000_000,
                "max_avg_high_low_range_pct": 0.3,
            }),
        )
        assert diag["filtered_count"] == 4
        assert diag["kept_count"] == 2
        assert diag["total_requested"] == 6
        assert len(diag["details"]) == 4
        # Vérifie les 4 raisons possibles
        reasons = set(diag["details"].values())
        assert "volume_insuffisant" in reasons
        assert "market_cap_insuffisant" in reasons
        assert "range_eleve" in reasons
        assert "historique_insuffisant" in reasons

    # ── Tests du filtre spread bid-ask réel ─────────────────────────────

    def test_spread_filter_disabled_when_max_zero(self) -> None:
        """max_spread_bps=0 désactive complètement le filtre spread."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        engine.connect.return_value.__enter__.return_value = conn

        _, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "MSFT"],
            max_spread_bps=0.0,
        )
        assert diag["spread_diagnostics"]["enabled"] is False

    def test_spread_filter_pass_mode_ignores_missing(self) -> None:
        """Mode 'pass' : si spread_bps absent, le symbole n'est PAS filtré."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class QuoteRow:
            def __init__(self, symbol, spread_bps, quote_date):
                self.symbol = symbol
                self.spread_bps = spread_bps
                self.quote_date = quote_date

        engine = MagicMock()
        conn = MagicMock()
        # 1er appel (range/volume) : aucun filtré
        # 2e appel (spread) : seulement MSFT a une quote (spread correct)
        conn.execute.return_value.fetchall.side_effect = [
            [],  # pas de filtrés range/volume
            [QuoteRow("MSFT", 15.0, date(2026, 7, 30))],  # 15 bps OK
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "MSFT", "NODATA"],
            max_spread_bps=40.0,
            spread_fallback_mode="pass",
        )
        assert excluded == []
        assert diag["spread_diagnostics"]["enabled"] is True
        assert diag["spread_diagnostics"]["spread_available"] == 1  # MSFT
        assert diag["spread_diagnostics"]["spread_missing"] == 2   # AAPL, NODATA
        assert diag["spread_diagnostics"]["spread_ok"] == 1

    def test_spread_filter_reject_mode_filters_missing(self) -> None:
        """Mode 'reject' : si spread_bps absent, le symbole EST filtré."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class QuoteRow:
            def __init__(self, symbol, spread_bps, quote_date):
                self.symbol = symbol
                self.spread_bps = spread_bps
                self.quote_date = quote_date

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [
            [],
            [QuoteRow("MSFT", 15.0, date(2026, 7, 30))],
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "MSFT", "NODATA"],
            max_spread_bps=40.0,
            spread_fallback_mode="reject",
        )
        assert set(excluded) == {"AAPL", "NODATA"}  # pas de quote → rejetés
        assert diag["details"]["AAPL"] == "spread_inconnu"
        assert diag["details"]["NODATA"] == "spread_inconnu"

    def test_spread_filter_rejects_high_spread(self) -> None:
        """Un spread > seuil est filtré quel que soit le fallback mode."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class QuoteRow:
            def __init__(self, symbol, spread_bps, quote_date):
                self.symbol = symbol
                self.spread_bps = spread_bps
                self.quote_date = quote_date

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [
            [],
            [QuoteRow("WIDE", 85.0, date(2026, 7, 30)), QuoteRow("TIGHT", 12.0, date(2026, 7, 30))],
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["WIDE", "TIGHT"],
            max_spread_bps=40.0,
            spread_fallback_mode="pass",
        )
        assert excluded == ["WIDE"]
        assert diag["details"]["WIDE"] == "spread_eleve"
        assert diag["spread_diagnostics"]["spread_high"] == 1
        assert diag["spread_diagnostics"]["spread_ok"] == 1

    def test_spread_filter_sql_error_graceful(self) -> None:
        """Si la requête spread échoue, on skip sans filtrer."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        engine = MagicMock()
        conn = MagicMock()
        # 1er appel OK, 2e (spread) lève une erreur
        conn.execute.side_effect = [
            MagicMock(fetchall=lambda: []),
            RuntimeError("stock_quote_snapshots not found"),
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["AAPL", "MSFT"],
            max_spread_bps=40.0,
        )
        assert excluded == []
        assert "error" in diag["spread_diagnostics"]
        assert diag["spread_diagnostics"]["newly_filtered"] == {}

    def test_spread_filter_already_filtered_skipped(self) -> None:
        """Les symboles déjà filtrés par range/volume ne sont pas ré-évalués."""
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        class FakeRow:
            def __init__(self, symbol, reason, avg_volume_20d=100000, avg_dollar_volume_20d=5000000,
                         avg_high_low_range_pct=1.5, nb_days=20):
                self.symbol = symbol
                self.reason = reason
                self.avg_volume_20d = avg_volume_20d
                self.avg_dollar_volume_20d = avg_dollar_volume_20d
                self.avg_high_low_range_pct = avg_high_low_range_pct
                self.nb_days = nb_days

        class QuoteRow:
            def __init__(self, symbol, spread_bps, quote_date):
                self.symbol = symbol
                self.spread_bps = spread_bps
                self.quote_date = quote_date

        engine = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [
            [FakeRow("PENNY", "volume_insuffisant")],
            [QuoteRow("PENNY", 5.0, date(2026, 7, 30)), QuoteRow("AAPL", 15.0, date(2026, 7, 30))],
        ]
        engine.connect.return_value.__enter__.return_value = conn

        excluded, diag = filter_symbols_by_liquidity(
            engine, ["PENNY", "AAPL"],
            max_spread_bps=40.0,
        )
        assert excluded == ["PENNY"]  # PENNY déjà filtré volume, pas ré-évalué spread
        assert diag["details"]["PENNY"] == "volume_insuffisant"  # raison originale préservée
        assert "AAPL" not in diag["details"]
