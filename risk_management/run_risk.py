"""
risk_management/run_risk.py
===========================
Point d'entrée script du module de gestion de risque.

Usage :
    python -m risk_management.run_risk
    python -m risk_management.run_risk --account-equity 100000 --max-positions 10 --dry-run
    python -m risk_management.run_risk --trade-date 2026-04-18 --log-level DEBUG
"""
from __future__ import annotations

import sys

from risk_management.cli import main

if __name__ == "__main__":
    sys.exit(main())

