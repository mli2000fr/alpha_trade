from ihm.components import status_badges

from datetime import datetime

def test_status_badges_importable():
    assert hasattr(status_badges, "__doc__")


def test_classify_heartbeat_freshness_returns_green_for_fresh_heartbeat() -> None:
    level, label, age_seconds = status_badges.classify_heartbeat_freshness(
        "2026-04-26T10:00:00",
        60,
        service_status="RUNNING",
        now=datetime.fromisoformat("2026-04-26T10:00:30"),
    )

    assert level == "ok"
    assert label == "FRAIS"
    assert age_seconds == 30


def test_classify_heartbeat_freshness_returns_orange_for_slow_heartbeat() -> None:
    level, label, age_seconds = status_badges.classify_heartbeat_freshness(
        "2026-04-26T10:00:00",
        60,
        service_status="RUNNING",
        now=datetime.fromisoformat("2026-04-26T10:01:50"),
    )

    assert level == "warn"
    assert label == "À SURVEILLER"
    assert age_seconds == 110


def test_classify_heartbeat_freshness_returns_red_for_stale_or_failed_service() -> None:
    stale_level, stale_label, stale_age = status_badges.classify_heartbeat_freshness(
        "2026-04-26T10:00:00",
        60,
        service_status="RUNNING",
        now=datetime.fromisoformat("2026-04-26T10:03:00"),
    )
    failed_level, failed_label, failed_age = status_badges.classify_heartbeat_freshness(
        "2026-04-26T10:00:00",
        60,
        service_status="FAILED",
        now=datetime.fromisoformat("2026-04-26T10:00:10"),
    )

    assert stale_level == "error"
    assert stale_label == "STALE"
    assert stale_age == 180
    assert failed_level == "error"
    assert failed_label == "KO"
    assert failed_age is None


def test_heartbeat_badge_formats_badge_text() -> None:
    badge = status_badges.heartbeat_badge(
        "2026-04-26T10:00:00",
        60,
        service_status="RUNNING",
        now=datetime.fromisoformat("2026-04-26T10:00:15"),
    )

    assert badge == "🟢 Heartbeat FRAIS (15s)"


