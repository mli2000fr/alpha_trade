"""Portable directories for ticker-specific artifacts, without changing tickers."""
from pathlib import Path
import re


def symbol_directory(parent, symbol):
    """Keep ordinary names; prefix Windows device names with ``symbol=``.

    The accepted ticker alphabet excludes '=', making the prefix unambiguous.
    No truncation or character stripping may merge two distinct tickers.
    """
    if (not isinstance(symbol, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', symbol)
            or symbol.endswith('.') or len(symbol) > 128):
        raise ValueError('Invalid symbol for an artifact directory')
    reserved = re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', symbol, re.I)
    component = 'symbol=' + symbol if reserved else symbol
    return Path(parent) / component
