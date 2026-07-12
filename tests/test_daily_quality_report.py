"""Tests du rapport quotidien automatisé (Section 17 Point 2.4)."""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone as _tz
from pathlib import Path

import pytest

from common.data_availability import (
    DailyQualityReport,
    DataAvailabilityInfo,
    QualityState,
    build_daily_quality_report,
)
from common.daily_quality_report import (
    CombinedDailyReport,
    UniverseAnomalyReport,
    build_and_persist_daily_report,
    detect_universe_anomalies,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_avail(
    source: str = "eodhd",
    event_time: datetime | None = None,
    available_at: datetime | None = None,
    quality: QualityState = QualityState.PRESENT,
) -> DataAvailabilityInfo:
    """Construit un DataAvailabilityInfo minimal pour les tests."""
    now = datetime(2026, 7, 12, 20, 0, 0, tzinfo=_tz.utc)
    return DataAvailabilityInfo(
        event_time=event_time or now,
        available_at=available_at or now,
        source=source,
        source_revision="v1",
        ingested_at=now,
        timezone="America/New_York",
        quality=quality,
    )


# ── detect_universe_anomalies ────────────────────────────────────────────────

class TestDetectUniverseAnomalies:
    def test_no_previous_returns_informative(self):
        r = detect_universe_anomalies(
            current_symbols=["AAPL", "MSFT"],
            previous_symbols=None,
            current_date="2026-07-12",
        )
        assert not r.is_anomalous
        assert r.previous_count == 0
        assert r.current_count == 2
        assert len(r.symbols_added) == 2
        assert r.symbols_removed == []
        assert r.count_change_pct == 1.0

    def test_identical_universe_no_anomaly(self):
        r = detect_universe_anomalies(
            current_symbols=["AAPL", "MSFT", "GOOGL"],
            previous_symbols=["MSFT", "AAPL", "GOOGL"],  # ordre différent
            current_date="2026-07-12",
            previous_date="2026-07-11",
        )
        assert not r.is_anomalous
        assert r.current_count == 3
        assert r.previous_count == 3
        assert r.symbols_added == []
        assert r.symbols_removed == []
        assert r.count_change_pct == 0.0

    def test_normal_churn_below_threshold(self):
        """1 symbole retiré sur 20 = 5% → pas d'anomalie."""
        prev = [f"TICKER{i:03d}" for i in range(20)]
        curr = prev[:-1]  # 19 symboles, 1 retiré
        r = detect_universe_anomalies(
            current_symbols=curr,
            previous_symbols=prev,
            current_date="2026-07-12",
            previous_date="2026-07-11",
        )
        assert not r.is_anomalous

    def test_massive_change_above_threshold(self):
        """30% de changement → anomalie."""
        prev = [f"TICKER{i:03d}" for i in range(10)]
        curr = [f"TICKER{i:03d}" for i in range(3, 10)]  # 3 retirés, 0 ajoutés = 30%
        r = detect_universe_anomalies(
            current_symbols=curr,
            previous_symbols=prev,
            current_date="2026-07-12",
            previous_date="2026-07-11",
            max_count_change_pct=0.20,
        )
        assert r.is_anomalous
        assert any("count_change" in reason for reason in r.anomaly_reasons)

    def test_only_added_no_removed_anomalous(self):
        """Ajouts sans retraits → anomalie."""
        r = detect_universe_anomalies(
            current_symbols=["A", "B", "C", "D", "E"],
            previous_symbols=["A", "B", "C"],
            current_date="2026-07-12",
            previous_date="2026-07-11",
            max_added_without_removed=1,  # seuil bas pour le test
        )
        assert r.is_anomalous
        assert any("only_added" in reason for reason in r.anomaly_reasons)

    def test_only_removed_no_added_anomalous(self):
        """Retraits sans ajouts → anomalie."""
        r = detect_universe_anomalies(
            current_symbols=["A"],
            previous_symbols=["A", "B", "C", "D"],
            current_date="2026-07-12",
            previous_date="2026-07-11",
            max_removed_without_added=1,
        )
        assert r.is_anomalous
        assert any("only_removed" in reason for reason in r.anomaly_reasons)

    def test_normal_replacement_not_anomalous(self):
        """1 ajout + 1 retrait = rotation normale."""
        r = detect_universe_anomalies(
            current_symbols=["A", "B", "D"],
            previous_symbols=["A", "B", "C"],
            current_date="2026-07-12",
            previous_date="2026-07-11",
        )
        assert not r.is_anomalous

    def test_case_insensitive_dedup(self):
        """Les symboles sont normalisés (upper, strip)."""
        r = detect_universe_anomalies(
            current_symbols=[" aapl ", "MSFT"],
            previous_symbols=["AAPL", "msft"],
            current_date="2026-07-12",
            previous_date="2026-07-11",
        )
        assert not r.is_anomalous
        assert r.symbols_added == []
        assert r.symbols_removed == []

    def test_empty_previous(self):
        r = detect_universe_anomalies(
            current_symbols=["AAPL"],
            previous_symbols=[],
            current_date="2026-07-12",
            previous_date="2026-07-11",
        )
        assert r.is_anomalous  # 100% change
        assert r.previous_count == 0
        assert r.current_count == 1

    def test_to_dict(self):
        r = detect_universe_anomalies(
            current_symbols=["AAPL", "MSFT"],
            previous_symbols=["AAPL", "GOOGL"],
            current_date="2026-07-12",
            previous_date="2026-07-11",
        )
        d = r.to_dict()
        assert d["current_date"] == "2026-07-12"
        assert "MSFT" in d["symbols_added"]
        assert "GOOGL" in d["symbols_removed"]


# ── build_and_persist_daily_report ───────────────────────────────────────────

class TestBuildAndPersistDailyReport:
    def test_full_report_all_present(self):
        """Univers complet, toutes les données présentes."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        avail_map = {s: _make_avail(source="eodhd") for s in symbols}
        trade_date = date(2026, 7, 12)

        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=trade_date,
                symbols=symbols,
                availability_map=avail_map,
                artifact_dir=tmp,
            )
            assert report.quality.coverage_ratio == 1.0
            assert report.quality.symbols_with_future_data == 0
            assert report.quality.symbols_stale_data == 0
            assert report.report_path is not None

            # Vérifie que le fichier a été écrit
            path = Path(report.report_path)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["quality"]["coverage_ratio"] == 1.0
            assert "universe_symbols" in data

    def test_report_with_future_data(self):
        """Détecte les données futures."""
        now = datetime(2026, 7, 12, 20, 0, 0, tzinfo=_tz.utc)
        future = datetime(2026, 7, 13, 21, 0, 0, tzinfo=_tz.utc)
        symbols = ["AAPL", "MSFT"]
        avail_map = {
            "AAPL": _make_avail(available_at=now),
            "MSFT": _make_avail(available_at=future),  # future!
        }

        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=symbols,
                availability_map=avail_map,
                artifact_dir=tmp,
                max_age_hours=24.0,
            )
            assert report.quality.symbols_with_future_data == 1
            assert report.quality.coverage_ratio < 1.0
            assert any("FUTURE_DATA" in a for a in report.quality.alerts)

    def test_report_with_stale_data(self):
        """Détecte les données stale (>24h)."""
        now = datetime(2026, 7, 12, 20, 0, 0, tzinfo=_tz.utc)
        # event_time et available_at sont cohérents : le 2026-07-10 à 21h UTC
        event = datetime(2026, 7, 10, 20, 0, 0, tzinfo=_tz.utc)
        stale = datetime(2026, 7, 10, 21, 0, 0, tzinfo=_tz.utc)  # ~48h avant le cutoff
        symbols = ["AAPL"]
        avail_map = {"AAPL": _make_avail(event_time=event, available_at=stale)}

        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=symbols,
                availability_map=avail_map,
                artifact_dir=tmp,
                max_age_hours=24.0,
            )
            assert report.quality.symbols_stale_data == 1
            assert any("stale_data" in a for a in report.quality.alerts)

    def test_report_with_missing_data(self):
        """Symbole sans DataAvailabilityInfo."""
        symbols = ["AAPL", "MSFT"]
        avail_map = {"AAPL": _make_avail()}  # MSFT manquant

        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=symbols,
                availability_map=avail_map,
                artifact_dir=tmp,
            )
            assert report.quality.symbols_missing_data == 1
            assert report.quality.coverage_ratio == 0.5
            assert any("missing_data:MSFT" in a for a in report.quality.alerts)

    def test_report_low_coverage_alert(self):
        """Couverture < 90% → alerte."""
        symbols = [f"T{i:03d}" for i in range(10)]
        avail_map = {f"T{i:03d}": _make_avail() for i in range(5)}  # 50%
        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=symbols,
                availability_map=avail_map,
                artifact_dir=tmp,
            )
            assert any("low_coverage" in a for a in report.quality.alerts)

    def test_empty_universe(self):
        """Univers vide → couverture 0, pas d'erreur."""
        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=[],
                availability_map={},
                artifact_dir=tmp,
            )
            assert report.quality.coverage_ratio == 0.0
            assert report.quality.total_symbols == 0

    def test_universe_anomalies_in_combined_report(self):
        """Le rapport combiné inclut les anomalies d'univers."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        avail_map = {s: _make_avail() for s in symbols}
        prev_symbols = ["AAPL", "MSFT", "TSLA"]  # TSLA retiré, GOOGL ajouté

        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=symbols,
                availability_map=avail_map,
                artifact_dir=tmp,
                previous_symbols=prev_symbols,
                previous_date="2026-07-11",
            )
            assert report.universe_anomalies is not None
            assert "GOOGL" in report.universe_anomalies.symbols_added
            assert "TSLA" in report.universe_anomalies.symbols_removed

    def test_report_loads_previous_from_disk(self):
        """Le rapport précédent est chargé depuis le disque si previous_symbols=None."""
        symbols_today = ["AAPL", "MSFT", "GOOGL"]
        symbols_yesterday = ["AAPL", "MSFT"]
        avail_map = {s: _make_avail() for s in symbols_today}

        with tempfile.TemporaryDirectory() as tmp:
            # Écrit un rapport de la veille
            from common.daily_quality_report import _persist_report
            from common.data_availability import DailyQualityReport

            prev_quality = DailyQualityReport(
                report_date="2026-07-11",
                total_symbols=2,
                symbols_with_data=2,
                symbols_missing_data=0,
                symbols_stale_data=0,
                symbols_with_future_data=0,
                coverage_ratio=1.0,
                quality_by_source={},
                alerts=[],
            )
            prev_report = CombinedDailyReport(quality=prev_quality, universe_anomalies=None)
            _persist_report(prev_report, Path(tmp), symbols_yesterday)

            # Construit le rapport du jour AVEC previous_date
            report = build_and_persist_daily_report(
                trade_date=date(2026, 7, 12),
                symbols=symbols_today,
                availability_map=avail_map,
                artifact_dir=tmp,
                previous_date="2026-07-11",
                # previous_symbols=None → doit charger depuis le disque
            )
            assert report.universe_anomalies is not None
            # GOOGL devrait apparaître comme ajouté
            assert "GOOGL" in report.universe_anomalies.symbols_added


# ── DailyQualityReport (existant, vérifié ici par cohérence) ────────────────

class TestDailyQualityReportContract:
    def test_build_report_all_present(self):
        symbols = ["AAPL", "MSFT", "GOOGL"]
        now = datetime(2026, 7, 12, 20, 0, 0, tzinfo=_tz.utc)
        avail_map = {s: _make_avail(available_at=now) for s in symbols}
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)

        report = build_daily_quality_report(symbols, avail_map, cutoff)
        assert report.coverage_ratio == 1.0
        assert report.symbols_with_future_data == 0
        assert report.alerts == []

    def test_to_dict_roundtrip(self):
        symbols = ["AAPL"]
        avail_map = {"AAPL": _make_avail()}
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        report = build_daily_quality_report(symbols, avail_map, cutoff)
        d = report.to_dict()
        assert d["report_date"] == "2026-07-12"
        assert d["coverage_ratio"] == 1.0
        assert "alerts" in d
