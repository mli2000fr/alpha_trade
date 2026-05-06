"""Sprint S24.3 — Tests du wrapper TLAPS / TLC.

Vérifie le comportement de ``scripts/run_tlaps.py`` :

* fallback vers TLC quand ``tlapm`` est absent ;
* écriture correcte de ``tlaps.json`` (n_specs, n_ok, n_failed, tool) ;
* mode ``--strict`` retourne ``1`` si une preuve échoue.

Les binaires ``tlapm`` / ``java`` ne sont pas requis : on monkeypatche
``shutil.which`` et ``subprocess.run`` pour simuler chaque cas.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_tlaps


def _fake_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def patch_no_tlapm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_tlaps.shutil, "which", lambda name: None)


def test_run_all_fallback_tlc_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_no_tlapm: None
) -> None:
    """tlapm absent → fallback TLC, toutes les specs OK."""
    monkeypatch.setattr(
        run_tlaps.subprocess,
        "run",
        lambda *a, **kw: _fake_proc(returncode=0, stdout="MODEL CHECK OK"),
    )
    payload = run_tlaps.run_all(tmp_path)
    assert payload["tool"] == "tlc-fallback"
    assert payload["n_specs"] == len(run_tlaps.SPECS) == 3
    assert payload["n_ok"] == 3
    assert payload["n_failed"] == 0
    out_files = list(tmp_path.rglob("tlaps.json"))
    assert len(out_files) == 1
    on_disk = json.loads(out_files[0].read_text("utf-8"))
    assert on_disk["n_ok"] == 3


def test_run_all_records_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_no_tlapm: None
) -> None:
    """Si tlc retourne != 0, n_failed est non-nul."""
    monkeypatch.setattr(
        run_tlaps.subprocess,
        "run",
        lambda *a, **kw: _fake_proc(returncode=1, stderr="counterexample"),
    )
    payload = run_tlaps.run_all(tmp_path)
    assert payload["n_failed"] == 3
    assert payload["n_ok"] == 0
    assert all(not r["ok"] for r in payload["results"])


def test_main_strict_exit_1_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_no_tlapm: None
) -> None:
    monkeypatch.setattr(
        run_tlaps.subprocess,
        "run",
        lambda *a, **kw: _fake_proc(returncode=1, stderr="counterexample"),
    )
    rc = run_tlaps.main(["--out", str(tmp_path), "--strict"])
    assert rc == 1


def test_main_non_strict_exit_0_even_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_no_tlapm: None
) -> None:
    monkeypatch.setattr(
        run_tlaps.subprocess,
        "run",
        lambda *a, **kw: _fake_proc(returncode=1),
    )
    rc = run_tlaps.main(["--out", str(tmp_path)])
    assert rc == 0


def test_run_all_uses_tlapm_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quand tlapm est dispo, le tool est marqué 'tlaps'."""
    monkeypatch.setattr(run_tlaps.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        run_tlaps.subprocess,
        "run",
        lambda *a, **kw: _fake_proc(returncode=0, stdout="proven"),
    )
    payload = run_tlaps.run_all(tmp_path)
    assert payload["tool"] == "tlaps"
    assert payload["n_ok"] == 3


def test_specs_are_the_three_documented_invariants() -> None:
    """Garde-fou : on prouve bien Idempotence, OCO, NoDoubleExec."""
    assert set(run_tlaps.SPECS) == {
        "IdempotenceCA.tla",
        "OCOBracket.tla",
        "NoDoubleExec.tla",
    }


def test_subprocess_timeout_is_handled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_no_tlapm: None
) -> None:
    def _raise(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="tlc", timeout=600)

    monkeypatch.setattr(run_tlaps.subprocess, "run", _raise)
    payload = run_tlaps.run_all(tmp_path)
    assert payload["n_failed"] == 3
    assert all(r.get("stderr") == "timeout" for r in payload["results"])

