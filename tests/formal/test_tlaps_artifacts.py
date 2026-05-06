"""Sprint S24.3 — Tests artefact TLAPS."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_tlaps import SPECS, TLA_DIR, run_all


def test_specs_files_exist() -> None:
    for s in SPECS:
        assert (TLA_DIR / s).exists(), f"Spec manquante : {s}"


def test_run_all_writes_json_even_without_tools(tmp_path: Path) -> None:
    """Sans tlapm/java installé, doit produire un rapport (n_failed > 0)."""
    payload = run_all(tmp_path)
    assert "results" in payload
    assert payload["n_specs"] == len(SPECS)
    files = list(tmp_path.rglob("tlaps.json"))
    assert len(files) == 1
    on_disk = json.loads(files[0].read_text("utf-8"))
    assert on_disk == payload

