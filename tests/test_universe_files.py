from __future__ import annotations

from pathlib import Path

import pytest

from common.universe_files import (
    default_universe_file_source,
    list_universe_file_sources,
    load_universe_file_symbols,
    normalize_universe_file_source,
    replace_legacy_ticket_option,
    universe_file_source,
)


def _write(path: Path, content: str = "AAPL,MSFT") -> None:
    path.write_text(content, encoding="utf-8")


def test_universe_files_are_discovered_and_sorted(tmp_path: Path) -> None:
    _write(tmp_path / "zeta.txt")
    _write(tmp_path / "Alpha.TXT")
    _write(tmp_path / "ignored.csv")
    (tmp_path / "folder.txt").mkdir()

    assert list_universe_file_sources(tmp_path) == (
        "universe-file:Alpha.TXT",
        "universe-file:zeta.txt",
    )
    assert default_universe_file_source(tmp_path) == "universe-file:Alpha.TXT"


def test_loader_supports_commas_lines_comments_and_deduplication(tmp_path: Path) -> None:
    _write(
        tmp_path / "universe.txt",
        "# commentaire\naapl, msft\nNVDA # commentaire final\nAAPL,,\n",
    )

    assert load_universe_file_symbols("universe-file:universe.txt", tmp_path) == [
        "AAPL",
        "MSFT",
        "NVDA",
    ]


def test_legacy_ticket_source_resolves_first_file(tmp_path: Path) -> None:
    _write(tmp_path / "b.txt", "B")
    _write(tmp_path / "a.txt", "A")

    assert normalize_universe_file_source("ticket-recherche", tmp_path) == "universe-file:a.txt"
    assert load_universe_file_symbols("ticket-recherche", tmp_path) == ["A"]


def test_legacy_option_is_replaced_without_removing_native_sources(tmp_path: Path) -> None:
    _write(tmp_path / "alpha.txt")

    assert replace_legacy_ticket_option(
        ("stock-bars-daily", "tradable-universe", "ticket-recherche"),
        tmp_path,
    ) == ("stock-bars-daily", "tradable-universe", "universe-file:alpha.txt")


@pytest.mark.parametrize(
    "filename",
    ("../secret.txt", "folder/secret.txt", r"folder\secret.txt", "not-text.csv", ""),
)
def test_source_rejects_unsafe_or_non_text_names(filename: str) -> None:
    with pytest.raises(ValueError):
        universe_file_source(filename)


def test_missing_selected_file_is_explicit(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_universe_file_symbols("universe-file:missing.txt", tmp_path)
