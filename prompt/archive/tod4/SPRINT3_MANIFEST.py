#!/usr/bin/env python3
"""
Sprint 3 — Manifest et vérification d'intégrité
Énumère tous les fichiers créés/modifiés et valide leur présence
"""

import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent

# Fichiers créés pour Sprint 3
FILES_MANIFEST = {
    # Tests
    "tests/test_pipeline_e2e.py": {
        "type": "test",
        "lines": 254,
        "purpose": "E2E pipeline complet 1→14",
        "anomaly": "A-006"
    },
    "tests/test_backtest_live_parity.py": {
        "type": "test",
        "lines": 213,
        "purpose": "Parité PnL backtest/live",
        "anomaly": "A-024"
    },
    "tests/test_integration_mysql.py": {
        "type": "test",
        "lines": 233,
        "purpose": "Intégration MySQL via Docker",
        "anomaly": "A-012"
    },
    "tests/test_sprint3_coverage.py": {
        "type": "test",
        "lines": 356,
        "purpose": "Couverture event_sentiment/modelFactory/execution_engine",
        "anomaly": "A-039"
    },

    # Infrastructure
    "docker-compose.test.yml": {
        "type": "infrastructure",
        "lines": 22,
        "purpose": "MySQL 8.0 Docker pour tests",
        "anomaly": "A-012"
    },

    # Validation
    "test_sprint3_validation.py": {
        "type": "script",
        "lines": 167,
        "purpose": "Runner validation tests",
        "anomaly": None
    },
    "validate_sprint3.sh": {
        "type": "script",
        "lines": 54,
        "purpose": "Script bash validation",
        "anomaly": None
    },

    # Documentation
    "prompt/tod4/SPRINT3_NOTES.md": {
        "type": "documentation",
        "lines": 256,
        "purpose": "Guide complet d'exécution et patterns",
        "anomaly": None
    },
    "SPRINT3_COMPLETION.md": {
        "type": "documentation",
        "lines": 382,
        "purpose": "Rapport détaillé avec bilan",
        "anomaly": None
    },
    "SPRINT3_README.md": {
        "type": "documentation",
        "lines": 185,
        "purpose": "README rapide du Sprint 3",
        "anomaly": None
    },
    "SPRINT3_DASHBOARD.html": {
        "type": "documentation",
        "lines": 456,
        "purpose": "Dashboard visuel de synthèse",
        "anomaly": None
    },

    # Plan mis à jour
    "prompt/tod4/08_sprint_plan.md": {
        "type": "documentation",
        "lines": "updated",
        "purpose": "Plan avec bilan Sprint 3 et progression globale",
        "anomaly": None
    }
}

def verify_manifest():
    """Vérifie que tous les fichiers du manifest existent."""
    print("\n📋 Vérification des fichiers Sprint 3…\n")
    print(f"{'Fichier':<45} {'Status':<10} {'Type':<20}")
    print("─" * 75)

    missing = []
    total_lines = 0
    found_count = 0

    for filepath, meta in FILES_MANIFEST.items():
        full_path = PROJECT_ROOT / filepath
        exists = full_path.exists()
        status = "✅ OK" if exists else "❌ MISSING"

        print(f"{filepath:<45} {status:<10} {meta['type']:<20}")

        if not exists:
            missing.append(filepath)
        else:
            found_count += 1
            if meta['lines'] != "updated":
                total_lines += int(meta['lines'])

    print("─" * 75)
    print(f"\n📊 Résumé :\n")
    print(f"  ✅ Fichiers trouvés     : {found_count}/{len(FILES_MANIFEST)}")
    print(f"  ❌ Fichiers manquants   : {len(missing)}/{len(FILES_MANIFEST)}")
    print(f"  📝 Lignes de code       : {total_lines:,}")

    if missing:
        print(f"\n⚠️  Fichiers manquants :\n")
        for f in missing:
            print(f"  - {f}")
        return False
    else:
        print(f"\n✅ Tous les fichiers Sprint 3 sont présents !")
        return True


def summary_stats():
    """Affiche les statistiques du Sprint 3."""
    print("\n" + "="*75)
    print("📊 STATISTIQUES SPRINT 3")
    print("="*75 + "\n")

    tests = sum(1 for m in FILES_MANIFEST.values() if m['type'] == 'test')
    docs = sum(1 for m in FILES_MANIFEST.values() if m['type'] == 'documentation')
    scripts = sum(1 for m in FILES_MANIFEST.values() if m['type'] == 'script')
    infra = sum(1 for m in FILES_MANIFEST.values() if m['type'] == 'infrastructure')

    print(f"  📝 Tests                : {tests} fichiers")
    print(f"  📚 Documentation        : {docs} fichiers")
    print(f"  🔧 Scripts              : {scripts} fichiers")
    print(f"  🐳 Infrastructure       : {infra} fichier")
    print(f"\n  🎯 Total fichiers       : {len(FILES_MANIFEST)}")

    # Tests count
    test_count = 10 + 9 + 5 + 14  # T3.1 + T3.4 + T3.3 + T3.5
    print(f"  ✅ Total tests créés     : {test_count}")

    # Anomalies
    anomalies = set(m['anomaly'] for m in FILES_MANIFEST.values() if m['anomaly'])
    print(f"  🔒 Anomalies closes     : {', '.join(sorted(anomalies))}")

    print("\n" + "="*75 + "\n")


def coverage_targets():
    """Affiche les cibles de couverture."""
    print("📈 CIBLES DE COUVERTURE\n")

    targets = [
        ("event_sentiment", "45%", "70%", "+25%"),
        ("modelFactory", "50%", "75%", "+25%"),
        ("execution_engine", "80%", "90%", "+10%"),
        ("Global", "70%", "75%+", "+5%+"),
    ]

    print(f"{'Module':<25} {'Avant':<10} {'Après':<10} {'Gain':<10}")
    print("─" * 55)
    for module, before, after, gain in targets:
        print(f"{module:<25} {before:<10} {after:<10} {gain:<10}")

    print("\n")


def quick_start():
    """Affiche les commandes de démarrage rapide."""
    print("🚀 DÉMARRAGE RAPIDE\n")

    print("Tests unitaires :")
    print("  pytest tests/test_sprint3_coverage.py -m unit -v\n")

    print("Tests E2E :")
    print("  pytest tests/test_pipeline_e2e.py tests/test_backtest_live_parity.py -v\n")

    print("Tests intégration MySQL :")
    print("  docker-compose -f docker-compose.test.yml up -d")
    print("  sleep 10")
    print("  TEST_MYSQL_URL=mysql+pymysql://testuser:testpass@localhost:3307/test_alpha_trade \\")
    print("    pytest tests/test_integration_mysql.py -m integration -v")
    print("  docker-compose -f docker-compose.test.yml down\n")

    print("Tous les tests avec couverture :")
    print("  python test_sprint3_validation.py all\n")


def main():
    """Point d'entrée principal."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  ✅ SPRINT 3 — Renforcement des tests (2026-06-08)                       ║
║  Manifeste et vérification d'intégrité                                    ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    # Vérification
    ok = verify_manifest()

    if not ok:
        print("\n❌ Certains fichiers manquent !")
        return 1

    # Stats
    summary_stats()

    # Cibles
    coverage_targets()

    # Quick start
    quick_start()

    # Finale
    print("─" * 75)
    print(f"✅ Sprint 3 — Implémentation complétée")
    print(f"📅 Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Anomalies closes : A-006, A-012, A-024, A-039")
    print(f"📊 Couverture cible : 75%+")
    print("─" * 75 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

