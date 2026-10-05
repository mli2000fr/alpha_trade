"""Compatibility entrypoint; all markets share the same Batch UI."""


def render_fr_batches():
    from ihm.pages.batches import render_market_batches
    render_market_batches('FR_EQ')
