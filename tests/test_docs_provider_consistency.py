"""Sprint S0 — cohérence provider-aware des runbooks docs."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_TO_CHECK = (
    REPO_ROOT / "doc" / "dataIntegrityEngine.md",
    REPO_ROOT / "doc" / "screener.md",
    REPO_ROOT / "doc" / "runbook_24_7.md",
    REPO_ROOT / "doc" / "DOC_TECHNIQUE.md",
)

_ALLOWED_CONTEXT_MARKERS = (
    "bars_provider=alpaca",
    "rétrocompat",
    "retrocompat",
)


def test_no_unqualified_import_alpaca_bar_runbook() -> None:
    failures: list[str] = []
    needle = "python -m dataIntegrityEngine.import_alpaca_bar"
    for doc in DOCS_TO_CHECK:
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
        for idx, line in enumerate(lines):
            if needle not in line:
                continue
            window = "\n".join(lines[max(0, idx - 2): min(len(lines), idx + 3)]).lower()
            if not any(marker in window for marker in _ALLOWED_CONTEXT_MARKERS):
                failures.append(
                    f"{doc.name}:{idx + 1} — commande Alpaca daily non qualifiée par un contexte rétrocompat/provider-aware"
                )
    assert not failures, "\n".join(failures)

