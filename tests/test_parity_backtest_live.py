"""Sprint S9 — Tests du module de parité backtest ↔ live.

Couvre :

- :func:`backtesting.parity.compare_decisions` (match, action_mismatch,
  qty_mismatch, missing_live, missing_replay, tolérance qty),
- :func:`backtesting.parity.run_daily_parity` end-to-end avec loaders
  injectables (artefacts + déclenchement alerte conditionné au seuil),
- :func:`backtesting.parity.write_parity_artifacts` (JSON + CSV),
- :mod:`service.alerting` (priorité du factory + non-blocking fallback),
- IHM : navigation contient bien la page parité ; helpers de lecture
  d'artefacts.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backtesting.parity import (
    DEFAULT_DIVERGENCE_THRESHOLD,
    ParityReport,
    compare_decisions,
    run_daily_parity,
    write_parity_artifacts,
)
from service import alerting
from service.alerting import (
    EmailNotifier,
    LogNotifier,
    SlackNotifier,
    build_notifier_from_env,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(symbol: str, decision: str, qty: float = 0.0, weight: float = 0.0,
         conviction: float | None = None, run_id: str = "live-1") -> dict:
    return {
        "symbol": symbol,
        "decision": decision,
        "approved_shares": qty,
        "target_weight": weight,
        "conviction_score": conviction,
        "run_id": run_id,
    }


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# compare_decisions — cas unitaires
# ---------------------------------------------------------------------------


def test_compare_decisions_perfect_match() -> None:
    live = _df([_row("AAPL", "BUY", 10), _row("MSFT", "HOLD", 0)])
    replay = _df([_row("AAPL", "BUY", 10, run_id="rep-1"), _row("MSFT", "HOLD", 0, run_id="rep-1")])
    rep = compare_decisions(live, replay, trade_date=date(2026, 5, 5))
    assert rep.n_matched == 2
    assert rep.n_divergent == 0
    assert rep.divergence_score == 0.0
    assert {r.divergence_kind for r in rep.rows} == {"match"}
    assert rep.live_run_id == "live-1"
    assert rep.replay_run_id == "rep-1"


def test_compare_decisions_action_mismatch() -> None:
    live = _df([_row("AAPL", "BUY", 10)])
    replay = _df([_row("AAPL", "HOLD", 0, run_id="rep")])
    rep = compare_decisions(live, replay)
    assert rep.n_divergent == 1
    assert rep.rows[0].divergence_kind == "action_mismatch"


def test_compare_decisions_qty_within_tolerance_is_match() -> None:
    # Différence de 1 part absolue tolérée par défaut (abs=1.0).
    live = _df([_row("AAPL", "BUY", 100)])
    replay = _df([_row("AAPL", "BUY", 101, run_id="rep")])
    rep = compare_decisions(live, replay)
    assert rep.rows[0].divergence_kind == "match"


def test_compare_decisions_qty_outside_tolerance_is_qty_mismatch() -> None:
    live = _df([_row("AAPL", "BUY", 100)])
    replay = _df([_row("AAPL", "BUY", 130, run_id="rep")])  # 30% > 5% + > 1
    rep = compare_decisions(live, replay)
    assert rep.rows[0].divergence_kind == "qty_mismatch"


def test_compare_decisions_missing_sides() -> None:
    live = _df([_row("AAPL", "BUY", 10)])
    replay = _df([_row("MSFT", "BUY", 5, run_id="rep")])
    rep = compare_decisions(live, replay)
    kinds = {r.symbol: r.divergence_kind for r in rep.rows}
    assert kinds == {"AAPL": "missing_replay", "MSFT": "missing_live"}
    assert rep.divergence_score == 1.0


def test_compare_decisions_handles_empty_inputs() -> None:
    rep = compare_decisions(pd.DataFrame(), pd.DataFrame(), trade_date=date(2026, 5, 5))
    assert rep.n_symbols_live == rep.n_symbols_replay == 0
    assert rep.divergence_score == 0.0
    assert rep.rows == []


def test_compare_decisions_normalizes_symbols_case() -> None:
    live = _df([_row("aapl", "BUY", 10)])
    replay = _df([_row("AAPL", "BUY", 10, run_id="rep")])
    rep = compare_decisions(live, replay)
    assert rep.rows[0].symbol == "AAPL"
    assert rep.rows[0].divergence_kind == "match"


# ---------------------------------------------------------------------------
# run_daily_parity — orchestration
# ---------------------------------------------------------------------------


class _RecordingNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def send(self, subject: str, body: str, *, severity: str = "warning") -> None:
        self.calls.append((subject, body, severity))


def test_run_daily_parity_writes_artifacts_and_no_alert_below_threshold(tmp_path: Path) -> None:
    live = _df([_row("AAPL", "BUY", 10)])
    replay = _df([_row("AAPL", "BUY", 10, run_id="rep")])
    notifier = _RecordingNotifier()

    rep = run_daily_parity(
        date(2026, 5, 5),
        live_loader=lambda d, a: live,
        replay_loader=lambda d, a: replay,
        artifacts_dir=tmp_path,
        notifier=notifier,
    )
    out_dir = tmp_path / "2026-05-05"
    assert (out_dir / "parity_summary.json").exists()
    assert (out_dir / "rows.csv").exists()
    summary = json.loads((out_dir / "parity_summary.json").read_text(encoding="utf-8"))
    assert summary["n_matched"] == 1
    assert summary["divergence_score"] == 0.0
    assert notifier.calls == []
    assert isinstance(rep, ParityReport)


def test_run_daily_parity_triggers_alert_above_threshold(tmp_path: Path) -> None:
    live = _df([_row(f"S{i}", "BUY", 10) for i in range(5)])
    # Replay : 3 actions divergentes / 5 -> score 0.6 > 0.10
    replay = _df([
        _row("S0", "HOLD", 0, run_id="rep"),
        _row("S1", "HOLD", 0, run_id="rep"),
        _row("S2", "HOLD", 0, run_id="rep"),
        _row("S3", "BUY", 10, run_id="rep"),
        _row("S4", "BUY", 10, run_id="rep"),
    ])
    notifier = _RecordingNotifier()
    run_daily_parity(
        date(2026, 5, 5),
        live_loader=lambda d, a: live,
        replay_loader=lambda d, a: replay,
        artifacts_dir=tmp_path,
        notifier=notifier,
        divergence_threshold=DEFAULT_DIVERGENCE_THRESHOLD,
    )
    assert len(notifier.calls) == 1
    subject, body, severity = notifier.calls[0]
    assert "Parité" in subject
    assert "action_mismatch" in body
    assert severity == "warning"


def test_run_daily_parity_swallows_notifier_errors(tmp_path: Path) -> None:
    class _Boom:
        def send(self, *a, **kw):  # noqa: D401, ANN001
            raise RuntimeError("network down")

    live = _df([_row("S0", "BUY", 10)])
    replay = _df([_row("S0", "HOLD", 0, run_id="rep")])
    # Doit NE PAS lever malgré l'erreur du notifier.
    rep = run_daily_parity(
        date(2026, 5, 5),
        live_loader=lambda d, a: live,
        replay_loader=lambda d, a: replay,
        artifacts_dir=tmp_path,
        notifier=_Boom(),
        divergence_threshold=0.0,
    )
    assert rep.n_divergent == 1


def test_write_parity_artifacts_dataframe_columns_when_empty(tmp_path: Path) -> None:
    rep = compare_decisions(pd.DataFrame(), pd.DataFrame(), trade_date=date(2026, 5, 5))
    paths = write_parity_artifacts(rep, tmp_path)
    df = pd.read_csv(paths["rows_csv"])
    assert list(df.columns) == [
        "symbol", "live_decision", "replay_decision", "live_qty", "replay_qty",
        "live_weight", "replay_weight", "live_conviction", "replay_conviction",
        "divergence_kind",
    ]


# ---------------------------------------------------------------------------
# service.alerting
# ---------------------------------------------------------------------------


def test_build_notifier_from_env_priority_slack(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        alerting.ENV_SLACK_WEBHOOK: "https://hooks.example.com/abc",
        alerting.ENV_SMTP_HOST: "smtp.example.com",
        alerting.ENV_SMTP_TO: "ops@example.com",
        alerting.ENV_SMTP_FROM: "bot@example.com",
    }
    notifier = build_notifier_from_env(env=env)
    assert isinstance(notifier, SlackNotifier)


def test_build_notifier_from_env_smtp_when_no_slack() -> None:
    env = {
        alerting.ENV_SMTP_HOST: "smtp.example.com",
        alerting.ENV_SMTP_TO: "ops@example.com,ops2@example.com",
        alerting.ENV_SMTP_FROM: "bot@example.com",
    }
    notifier = build_notifier_from_env(env=env)
    assert isinstance(notifier, EmailNotifier)
    assert notifier.to_addrs == ("ops@example.com", "ops2@example.com")


def test_build_notifier_from_env_log_fallback() -> None:
    notifier = build_notifier_from_env(env={})
    assert isinstance(notifier, LogNotifier)


def test_log_notifier_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    notifier = LogNotifier()
    with caplog.at_level("WARNING", logger="service.alerting"):
        notifier.send("subject", "body", severity="warning")
    assert any("subject" in rec.message for rec in caplog.records)


def test_slack_notifier_falls_back_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str]] = []

    class _FB:
        def send(self, subject, body, *, severity="warning"):  # noqa: ANN001
            captured.append((subject, body))

    notifier = SlackNotifier(webhook_url="https://nope.invalid/x", fallback=_FB())

    # Force ImportError pour requests pour exercer la branche d'erreur.
    import sys
    monkeypatch.setitem(sys.modules, "requests", None)  # type: ignore[arg-type]
    notifier.send("subj", "body", severity="critical")
    assert captured == [("subj", "body")]


# ---------------------------------------------------------------------------
# IHM
# ---------------------------------------------------------------------------


def test_navigation_contains_parity_page() -> None:
    from ihm.services.navigation import NAVIGATION_PAGES
    keys = [p.key for p in NAVIGATION_PAGES]
    assert "parity" in keys
    parity_page = next(p for p in NAVIGATION_PAGES if p.key == "parity")
    assert parity_page.module_name == "ihm.pages.parity"
    assert parity_page.group == "support"


def test_parity_page_helpers_list_and_load(tmp_path: Path) -> None:
    from ihm.pages import parity as parity_page

    # Aucun run -> liste vide
    empty_root = tmp_path / "empty"
    assert parity_page._list_available_dates(empty_root) == []

    # Crée un run valide
    run_dir = tmp_path / "2026-05-05"
    run_dir.mkdir()
    payload = {"divergence_score": 0.0, "n_matched": 1, "n_divergent": 0, "rows": []}
    (run_dir / "parity_summary.json").write_text(json.dumps(payload), encoding="utf-8")
    assert parity_page._list_available_dates(tmp_path) == ["2026-05-05"]
    loaded = parity_page._load_summary("2026-05-05", tmp_path)
    assert loaded == payload

    # Date inexistante -> None
    assert parity_page._load_summary("1999-01-01", tmp_path) is None


def test_parity_page_badge_color_thresholds() -> None:
    from ihm.pages.parity import _badge_color
    assert _badge_color(0.0) == "🟢"
    assert _badge_color(0.08) == "🟡"
    assert _badge_color(0.5) == "🔴"

