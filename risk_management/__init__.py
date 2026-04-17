"""
risk_management
===============
Module de gestion de risque pour Alpha Trade.

S'exécute après ``signal_aggregator.py`` : lit les candidats depuis
``stock_scores``, applique les règles de risque, calcule les tailles de
position, construit un portefeuille cible et journalise les décisions.
"""
from __future__ import annotations

