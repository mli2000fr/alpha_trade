#!/usr/bin/env python
"""Évaluation de la couverture par module pour Sprint 3.

Identifie les modules avec couverture < 75% pour cibler les tests manquants.
"""
import json
from pathlib import Path
from collections import defaultdict

# Charger le coverage.json
with open('coverage.json') as f:
    data = json.load(f)

module_coverage = defaultdict(lambda: {'covered': 0, 'total': 0})

# Analyser les fichiers
for file_path, file_data in data.get('files', {}).items():
    # Extraire le module principal (premier répertoire)
    parts = file_path.replace('\\', '/').split('/')
    if parts[0].startswith('.'):
        parts = parts[1:]

    if not parts or parts[0].startswith('test'):
        continue

    module = parts[0]

    summary = file_data.get('summary', {})
    module_coverage[module]['covered'] += summary.get('covered_lines', 0)
    module_coverage[module]['total'] += summary.get('num_statements', 0)

# Trier par couverture croissante
sorted_modules = sorted(
    module_coverage.items(),
    key=lambda x: (x[1]['covered'] / max(1, x[1]['total'])) if x[1]['total'] > 0 else 0
)

print("=" * 60)
print("COUVERTURE PAR MODULE (Sprint 3 - Renforcement tests)")
print("=" * 60)
print(f"{'Module':<25} {'Coverage':<12} {'Lines':<20}")
print("-" * 60)

critical = []
for module, stats in sorted_modules:
    if stats['total'] == 0:
        continue
    coverage_pct = (stats['covered'] / stats['total']) * 100
    status = '✗ CRITIQUE' if coverage_pct < 50 else '⚠ À TESTER' if coverage_pct < 75 else '✓'

    print(f"{module:<25} {coverage_pct:>6.1f}%  {status:<15} {stats['covered']}/{stats['total']}")

    if coverage_pct < 75:
        critical.append((module, coverage_pct))

print("=" * 60)
print(f"\nModules critiques (< 75%) : {len(critical)}")
for module, pct in critical[:10]:
    print(f"  - {module:<25} {pct:>6.1f}%")

total_coverage = data['totals']['percent_covered']
print(f"\nCouverture globale : {total_coverage:.1f}%")
print(f"Seuil Sprint 3 : 75%")
print(f"STATUS: {'✓ PASS' if total_coverage >= 75 else '✗ À AMÉLIORER'}")

