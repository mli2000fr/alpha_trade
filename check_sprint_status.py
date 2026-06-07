#!/usr/bin/env python
"""Évaluation du statut des Sprints pour continuation du projet.

Sprint 1-2 : ✓ Clos (mai 2026)
Sprint 3-5 : ? À évaluer et compléter (juin 2026)
Sprint 6-8 : ? À planifier
"""
import subprocess
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class Status(Enum):
    NOT_STARTED = "❌"
    IN_PROGRESS = "🔄"
    COMPLETE = "✓"
    PARTIAL = "⚠"

@dataclass
class TaskStatus:
    sprint: str
    task_id: str
    title: str
    status: Status
    notes: str = ""

# Vérifications rapides basées sur les fichiers
checks = [
    # Sprint 3
    TaskStatus("S3", "T3.1", "Test E2E pipeline", Status.COMPLETE,
               "test_ihm_pipeline_e2e.py + test_parity_* existent"),
    TaskStatus("S3", "T3.2", "Docker Compose MySQL", Status.COMPLETE,
               "testcontainers intégré dans tests/integration/"),
    TaskStatus("S3", "T3.3", "Tests d'intégration MySQL", Status.COMPLETE,
               "test_mysql_*.py existent"),
    TaskStatus("S3", "T3.4", "Parité backtest/live", Status.COMPLETE,
               "test_parity_backtest_live.py existe"),
    TaskStatus("S3", "T3.5", "Couverture >= 75%", Status.IN_PROGRESS,
               "Besoin de vérifier - actuellement ~70% nominal"),

    # Sprint 4
    TaskStatus("S4", "T4.1", "Choisir orchestrateur", Status.COMPLETE,
               "Prefect retenu dans flows/daily_pipeline.py"),
    TaskStatus("S4", "T4.2", "Flow Prefect pipeline", Status.PARTIAL,
               "flows/daily_pipeline.py implémenté (S5)"),
    TaskStatus("S4", "T4.3", "Reprise sur erreur", Status.PARTIAL,
               "Logique d'erreur présente, à intégrer Prefect"),
    TaskStatus("S4", "T4.4", "Scheduling automatique", Status.PARTIAL,
               "Skeleton présent, à configurer"),
    TaskStatus("S4", "T4.5", "Pool DB production", Status.NOT_STARTED,
               "À configurer pour la production"),

    # Sprint 5
    TaskStatus("S5", "T5.1", "Notifications extendues", Status.PARTIAL,
               "ihm/services/notifications.py existe"),
    TaskStatus("S5", "T5.2", "Webhook Slack", Status.NOT_STARTED,
               "À implémenter"),
    TaskStatus("S5", "T5.3", "Métriques Prometheus", Status.PARTIAL,
               "core/metrics.py existe, à élargir"),
    TaskStatus("S5", "T5.4", "Dashboard Grafana", Status.NOT_STARTED,
               "À créer"),
    TaskStatus("S5", "T5.5", "Alertes Grafana", Status.NOT_STARTED,
               "À configurer"),
]

# Affichage
print("=" * 80)
print("STATUT DES SPRINTS — Alpha Trade (juin 2026)")
print("=" * 80)

for sprint_num in ["S3", "S4", "S5"]:
    sprint_tasks = [t for t in checks if t.sprint == sprint_num]
    completed = sum(1 for t in sprint_tasks if t.status == Status.COMPLETE)
    total = len(sprint_tasks)

    print(f"\n{sprint_num} — {completed}/{total} tâches complétées")
    print("-" * 80)

    for task in sprint_tasks:
        print(f"  {task.status.value} {task.task_id:<7} {task.title:<35} # {task.notes}")

print("\n" + "=" * 80)
print("RECOMMANDATIONS")
print("=" * 80)
print("""
1. URGENT (cette session) :
   - T3.5 : Vérifier couverture >= 75% (actuellement ~70%)
   - T4.5 : Configurer pool DB production
   - T5.2 : Webhook Slack pour circuit breaker
   
2. IMPORTANT (cette semaine) :
   - T5.3 : Élargir métriques Prometheus
   - T5.4 : Créer dashboard Grafana basique
   - T4.3 : Intégrer gestion d'erreur Prefect
   
3. CAN WAIT (prochain sprint) :
   - T5.5 : Alertes Grafana détaillées
   - T6-8 : Sprints 6-8 (backtesting, ML, Docker)
""")

