"""Compat wrapper vers ``execution_engine.reconcile_statement``.

Le point d'entrée canonique Sprint S3 est désormais :

    python -m execution_engine.reconcile_statement ...
"""
from __future__ import annotations

import sys

from execution_engine.reconcile_statement import main


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

