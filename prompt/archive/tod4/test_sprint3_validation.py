#!/usr/bin/env python3
"""Sprint 3 — Validation et exécution des tests.

Ce script valide et exécute les tests créés pour le Sprint 3.

Usage:
  python test_sprint3_validation.py [unit|e2e|integration|all]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent


def run_cmd(cmd: list[str], description: str = "") -> int:
    """Exécute une commande et retourne le code de sortie."""
    if description:
        print(f"\n{'='*70}")
        print(f"▶ {description}")
        print('='*70)
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def validate_files() -> bool:
    """Valide que tous les fichiers du Sprint 3 existent."""
    files = [
        "tests/test_pipeline_e2e.py",
        "tests/test_backtest_live_parity.py",
        "tests/test_integration_mysql.py",
        "tests/test_sprint3_coverage.py",
        "docker-compose.test.yml",
        "prompt/tod4/SPRINT3_NOTES.md",
        "prompt/tod4/08_sprint_plan.md",
    ]

    print("\n📋 Vérification des fichiers Sprint 3…\n")
    all_exist = True
    for f in files:
        path = PROJECT_ROOT / f
        exists = path.exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {f}")
        all_exist = all_exist and exists

    return all_exist


def run_unit_tests() -> int:
    """Exécute les tests unitaires Sprint 3."""
    return run_cmd(
        [
            sys.executable, "-m", "pytest",
            "tests/test_sprint3_coverage.py",
            "-v", "--tb=short",
            "-m", "unit",
        ],
        "▶ Tests unitaires Sprint 3 (event_sentiment, modelFactory, execution_engine)"
    )


def run_e2e_tests() -> int:
    """Exécute les tests E2E."""
    return run_cmd(
        [
            sys.executable, "-m", "pytest",
            "tests/test_pipeline_e2e.py",
            "tests/test_backtest_live_parity.py",
            "-v", "--tb=short",
            "-m", "e2e",
        ],
        "▶ Tests E2E (pipeline complet, parité backtest)"
    )


def run_integration_tests() -> int:
    """Exécute les tests d'intégration MySQL."""
    import os

    env = os.environ.copy()
    env["TEST_MYSQL_URL"] = (
        "mysql+pymysql://testuser:testpass@localhost:3307/test_alpha_trade"
    )

    return subprocess.call(
        [
            sys.executable, "-m", "pytest",
            "tests/test_integration_mysql.py",
            "-v", "--tb=short",
            "-m", "integration",
        ],
        cwd=PROJECT_ROOT,
        env=env,
    )


def run_all_tests() -> int:
    """Exécute tous les tests Sprint 3."""
    return run_cmd(
        [
            sys.executable, "-m", "pytest",
            "tests/test_pipeline_e2e.py",
            "tests/test_backtest_live_parity.py",
            "tests/test_integration_mysql.py",
            "tests/test_sprint3_coverage.py",
            "-v", "--tb=short",
            "--cov=.",
            "--cov-report=term-missing:skip-covered",
            "--cov-fail-under=70",  # Cible progressive
        ],
        "▶ Tous les tests Sprint 3 (couverture globale)"
    )


def main():
    """Point d'entrée principal."""
    if not validate_files():
        print("\n❌ Certains fichiers manquent. Création annulée.")
        return 1

    print("\n✅ Tous les fichiers Sprint 3 sont présents.\n")

    test_type = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    match test_type:
        case "unit":
            exit_code = run_unit_tests()
        case "e2e":
            exit_code = run_e2e_tests()
        case "integration":
            print("\n⚠️  Les tests d'intégration MySQL nécessitent :")
            print("   docker-compose -f docker-compose.test.yml up -d")
            print("   (Attendre 10s que MySQL soit prêt)\n")
            exit_code = run_integration_tests()
        case "all":
            exit_code = run_all_tests()
        case _:
            print(f"Usage: {sys.argv[0]} [unit|e2e|integration|all]")
            return 1

    if exit_code == 0:
        print("\n" + "="*70)
        print("✅ Tous les tests Sprint 3 ont réussi !")
        print("="*70)
    else:
        print("\n" + "="*70)
        print(f"❌ Tests échoués (code {exit_code})")
        print("="*70)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

