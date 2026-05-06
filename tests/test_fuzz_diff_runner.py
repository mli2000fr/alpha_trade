"""Sprint S24.1 — Tests unitaires du runner de fuzz différentiel."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backtesting.fuzz_runner import (
    FuzzScenario,
    _run_engine,
    generate_scenarios,
    run_fuzz_diff,
)
from backtesting.fuzz_tolerance import FuzzTolerance


def test_generate_scenarios_is_deterministic() -> None:
    a = generate_scenarios(20, master_seed=42)
    b = generate_scenarios(20, master_seed=42)
    assert a == b
    c = generate_scenarios(20, master_seed=43)
    assert c != a  # seed différent ⇒ scénarios différents


def test_engine_is_deterministic() -> None:
    sc = FuzzScenario(
        seed=1, qty=10.0, entry_price=100.0, tp_price=110.0, sl_price=95.0,
        events=(("tick", 0.02), ("partial_fill", 0.1)),
    )
    a = _run_engine(sc, is_live=True)
    b = _run_engine(sc, is_live=False)
    assert a.audit_hash == b.audit_hash
    assert a.pnl == b.pnl


def test_run_fuzz_diff_smoke_no_divergence(tmp_path: Path) -> None:
    report = run_fuzz_diff(50, out_dir=tmp_path, master_seed=7)
    assert report.n_scenarios == 50
    assert report.n_diverged == 0
    # Fichier de sortie écrit
    files = list(tmp_path.rglob("diff.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["n_scenarios"] == 50
    assert payload["n_diverged"] == 0
    assert "tolerance" in payload
    assert "config_hash" in payload
    assert isinstance(payload["divergences"], list)


def test_run_fuzz_diff_detects_injected_divergence(tmp_path: Path) -> None:
    report = run_fuzz_diff(
        20, out_dir=tmp_path, master_seed=7, inject_divergence=True,
    )
    assert report.n_diverged == 20
    payload = json.loads(next(tmp_path.rglob("diff.json")).read_text("utf-8"))
    assert payload["n_diverged"] == 20
    assert payload["divergences"]  # au moins 1 enregistré


def test_tolerance_from_dict_round_trip() -> None:
    tol = FuzzTolerance(pnl_abs_usd=0.5, status_strict=False)
    d = tol.to_dict()
    assert FuzzTolerance.from_dict(d) == tol
    # Champs inconnus ignorés
    d2 = {**d, "unknown_key": 123}
    assert FuzzTolerance.from_dict(d2) == tol

