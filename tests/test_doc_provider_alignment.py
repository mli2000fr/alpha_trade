"""Sprint S1 / Anomalies A-004 et A-005 — Cohérence doc ↔ provider OHLCV.

Empêche la dérive entre `config.yaml › market_data.bars_provider` et les
documents structurants (`doc/dataIntegrityEngine.md`,
`doc/data_lineage_matrix.md`, `doc/DOC_FONCTIONNELLE.md`,
`doc/DOC_TECHNIQUE.md`). Chaque document est marqué par un commentaire
HTML invariant `<!-- primary_provider: <name> -->` ; ce test vérifie que
la valeur du marqueur correspond bien au provider effectivement
configuré.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"

DOCS_WITH_MARKER = [
    REPO_ROOT / "doc" / "dataIntegrityEngine.md",
    REPO_ROOT / "doc" / "data_lineage_matrix.md",
    REPO_ROOT / "doc" / "DOC_FONCTIONNELLE.md",
    REPO_ROOT / "doc" / "DOC_TECHNIQUE.md",
]

MARKER_RE = re.compile(r"<!--\s*primary_provider:\s*(?P<value>\w+)\s*-->")


def _configured_provider() -> str:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return (cfg.get("market_data") or {}).get("bars_provider", "alpaca")


def test_each_doc_has_provider_marker() -> None:
    expected = _configured_provider()
    failures: list[str] = []
    for doc in DOCS_WITH_MARKER:
        text = doc.read_text(encoding="utf-8", errors="replace")
        match = MARKER_RE.search(text)
        if match is None:
            failures.append(f"{doc.name} : marqueur primary_provider absent")
            continue
        value = match.group("value")
        if value != expected:
            failures.append(
                f"{doc.name} : marqueur '{value}' != bars_provider '{expected}'"
            )
    assert not failures, "\n".join(failures)

