from __future__ import annotations

from pathlib import Path

import pytest

from common.universe_files import (
    default_universe_file_source,
    list_universe_file_sources,
    load_universe_file_symbols,
    normalize_universe_file_source,
    replace_legacy_ticket_option,
    resolve_universe_file_path,
    universe_file_source,
    universe_file_source_from_path,
    validate_symbol_source,
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


def test_source_from_path_keeps_short_form_for_default_directory() -> None:
    assert universe_file_source_from_path(Path("config/univers/univers_filtred.txt")) == (
        "universe-file:univers_filtred.txt"
    )
    assert universe_file_source_from_path(Path("config/univers_batch/univers_filtred_tradable.txt")) == (
        "universe-file:config/univers_batch/univers_filtred_tradable.txt"
    )


def test_loader_supports_path_qualified_source(tmp_path: Path) -> None:
    batch_directory = tmp_path / "config" / "univers_batch"
    batch_directory.mkdir(parents=True)
    _write(batch_directory / "univers_filtred_tradable.txt", "aapl, msft")

    source = "universe-file:config/univers_batch/univers_filtred_tradable.txt"

    assert load_universe_file_symbols(source, root=tmp_path) == ["AAPL", "MSFT"]
    assert normalize_universe_file_source(source) == source
    assert resolve_universe_file_path(source, root=tmp_path) == (
        batch_directory / "univers_filtred_tradable.txt"
    )


@pytest.mark.parametrize(
    "path",
    ("config/../secret.txt", "artifacts/universe.txt", "config/univers_batch/universe.csv", ""),
)
def test_path_sources_reject_escape_and_non_text(path: str) -> None:
    with pytest.raises(ValueError):
        universe_file_source_from_path(Path(path))


def test_missing_path_qualified_file_is_explicit(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_universe_file_symbols("universe-file:config/univers_batch/absent.txt", root=tmp_path)


def test_validate_symbol_source_accepts_native_and_rejects_unknown() -> None:
    assert validate_symbol_source("stock-bars-daily", ("stock-bars-daily",)) == "stock-bars-daily"
    with pytest.raises(ValueError):
        validate_symbol_source("not-a-source", ("stock-bars-daily",))
    with pytest.raises(FileNotFoundError):
        validate_symbol_source("universe-file:absent.txt", ("stock-bars-daily",))
