"""Sprint S1 / A-002,A-004 — alignement schéma SQL ↔ documentation lineage."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = REPO_ROOT / "database" / "sql" / "stock" / "stock_bars_daily.sql"
LINEAGE_DOC_PATH = REPO_ROOT / "doc" / "data_lineage_matrix.md"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_data_lineage.py"


def test_stock_bars_daily_sql_keeps_single_source_primary_key() -> None:
    text = SQL_PATH.read_text(encoding="utf-8", errors="replace")
    assert "PRIMARY KEY (`symbol`, `date`)" in text
    assert "source unique active" in text.lower()


def test_lineage_docs_do_not_claim_same_symbol_date_multi_source_cohabitation() -> None:
    lineage_text = LINEAGE_DOC_PATH.read_text(encoding="utf-8", errors="replace").lower()
    generator_text = GENERATOR_PATH.read_text(encoding="utf-8", errors="replace").lower()

    forbidden = "peut contenir\n  simultanément `alpaca_iex` et `eodhd_eod` sur la même `(symbol, date)`"
    assert forbidden not in lineage_text
    assert forbidden not in generator_text
    assert "source unique active" in lineage_text
    assert "source unique active" in generator_text

