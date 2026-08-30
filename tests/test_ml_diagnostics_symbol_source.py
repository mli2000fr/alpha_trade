from ihm.pages.ml_diagnostics import _format_symbol_source


def test_dynamic_universe_source_displays_filename_only() -> None:
    assert (
        _format_symbol_source("universe-file:univers_filtred_2016.txt")
        == "univers_filtred_2016.txt"
    )


def test_native_and_empty_sources_remain_readable() -> None:
    assert _format_symbol_source("tradable-universe") == "tradable-universe"
    assert _format_symbol_source(None) == "—"
