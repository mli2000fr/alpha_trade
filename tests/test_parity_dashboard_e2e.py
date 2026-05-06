"""S11.5 — Tests du dashboard parité IHM (rolling 30 j + agrégats).

Couvre les helpers purs ``load_rolling_summaries`` et
``aggregate_top_divergent_symbols`` (le rendu Streamlit lui-même est testé
indirectement par les imports). Un test E2E AppTest peut être ajouté quand le
runtime Streamlit est disponible.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ihm.pages.parity import (
    aggregate_top_divergent_symbols,
    load_rolling_summaries,
)


def _write_summary(root: Path, trade_date: str, *, score: float, rows: list[dict]) -> None:
    d = root / trade_date
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "trade_date": trade_date,
        "divergence_score": score,
        "n_matched": sum(1 for r in rows if r.get("divergence_kind") == "match"),
        "n_divergent": sum(1 for r in rows if r.get("divergence_kind") not in (None, "match")),
        "n_symbols_live": len(rows),
        "n_symbols_replay": len(rows),
        "rows": rows,
    }
    (d / "parity_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_rolling_summaries_picks_window_most_recent(tmp_path: Path):
    for i, trade_date in enumerate(["2026-04-01", "2026-04-02", "2026-04-03"]):
        _write_summary(tmp_path, trade_date, score=0.05 * i, rows=[])

    out = load_rolling_summaries(root=tmp_path, window=2)
    assert len(out) == 2
    # ordre chronologique décroissant
    assert out[0]["trade_date"] == "2026-04-03"
    assert out[1]["trade_date"] == "2026-04-02"


def test_load_rolling_summaries_skips_missing_or_corrupt(tmp_path: Path):
    _write_summary(tmp_path, "2026-04-01", score=0.05, rows=[])
    # créer un dossier sans summary
    (tmp_path / "2026-04-02").mkdir()
    # corrupted summary
    bad = tmp_path / "2026-04-03"
    bad.mkdir()
    (bad / "parity_summary.json").write_text("{not-json", encoding="utf-8")
    _write_summary(tmp_path, "2026-04-04", score=0.10, rows=[])

    out = load_rolling_summaries(root=tmp_path, window=10)
    dates = {s["trade_date"] for s in out}
    assert dates == {"2026-04-01", "2026-04-04"}


def test_aggregate_top_divergent_symbols_counts_distinct_days_and_kinds():
    summaries = [
        {
            "trade_date": "2026-04-01",
            "rows": [
                {"symbol": "AAPL", "divergence_kind": "qty_mismatch"},
                {"symbol": "AAPL", "divergence_kind": "price_drift"},  # même jour, 2 kinds
                {"symbol": "MSFT", "divergence_kind": "qty_mismatch"},
                {"symbol": "TSLA", "divergence_kind": "match"},  # ignoré
            ],
        },
        {
            "trade_date": "2026-04-02",
            "rows": [
                {"symbol": "AAPL", "divergence_kind": "qty_mismatch"},
            ],
        },
        {
            "trade_date": "2026-04-03",
            "rows": [
                {"symbol": "MSFT", "divergence_kind": "side_mismatch"},
            ],
        },
    ]
    top = aggregate_top_divergent_symbols(summaries, top_n=10)
    by_symbol = {row["symbol"]: row for row in top}

    assert by_symbol["AAPL"]["divergent_days"] == 2  # 04-01 + 04-02
    assert by_symbol["AAPL"]["total_days"] == 3
    assert by_symbol["AAPL"]["kinds"]["qty_mismatch"] == 2
    assert by_symbol["AAPL"]["kinds"]["price_drift"] == 1

    assert by_symbol["MSFT"]["divergent_days"] == 2
    assert "TSLA" not in by_symbol  # match seul → ignoré

    # Ordre : AAPL et MSFT à 2 jours, AAPL avant car alpha à égalité.
    assert top[0]["symbol"] == "AAPL"
    assert top[1]["symbol"] == "MSFT"


def test_aggregate_top_divergent_symbols_respects_top_n():
    summaries = [
        {
            "trade_date": "2026-04-01",
            "rows": [{"symbol": s, "divergence_kind": "qty_mismatch"} for s in "ABCDE"],
        }
    ]
    top = aggregate_top_divergent_symbols(summaries, top_n=3)
    assert len(top) == 3

