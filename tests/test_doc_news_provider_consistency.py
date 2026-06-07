from __future__ import annotations

import re
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_TOKEN_PATTERN = re.compile(r"`(?P<provider>alpaca|eodhd|finnhub)`", re.IGNORECASE)


def _extract_default_news_provider(doc_path: Path) -> str:
    content = doc_path.read_text(encoding="utf-8")
    normalized = unicodedata.normalize("NFKD", content).encode("ascii", "ignore").decode("ascii")
    for line in normalized.splitlines():
        lowered = line.lower()
        if "provider news" not in lowered and "news provider" not in lowered:
            continue
        match = PROVIDER_TOKEN_PATTERN.search(line)
        if match is not None:
            return str(match.group("provider")).lower()
    raise AssertionError(f"Aucune mention du provider news par defaut dans {doc_path}")


def test_default_news_provider_is_consistent_across_core_docs() -> None:
    docs = (
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "doc" / "CONVENTIONS.md",
        PROJECT_ROOT / "doc" / "DOC_FONCTIONNELLE.md",
        PROJECT_ROOT / "doc" / "DOC_TECHNIQUE.md",
    )
    extracted = {str(doc): _extract_default_news_provider(doc) for doc in docs}
    values = set(extracted.values())
    assert values == {"eodhd"}, f"Incoherence detectee: {extracted}"





