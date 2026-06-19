# 00 — Audit Executive Summary

> **Synthèse dirigeant — Vue d'ensemble de l'état de l'application Alpha Trade**

---

## 1. Positionnement actuel

**Alpha Trade** est une plateforme Python de swing trading US actions qui couvre l'intégralité de la chaîne : ingestion marché → screening → sélection alpha → sentiment NLP → ML → risk management → exécution → corporate actions → backtesting → supervision IHM.

L'application est **fonctionnellement très riche** et témoigne d'un **investissement de conception considérable**. Elle se situe à un niveau **nettement supérieur à un projet amateur**, avec des préoccupations de production visibles partout : idempotence, audit trail, multi-comptes, secrets management, circuit breakers, réconciliation, etc.

**Cependant**, la richesse fonctionnelle s'est construite par vagues successives (sprints S1→S7, plan v2 short selling, plan ML v2 ternaire) et montre des **signes de complexité accumulée** : documentation partiellement désynchronisée, paramétrages dont la cohérence inter-tranches est discutable, et certaines incohérences entre IHM et backend.

---

## 2. Forces majeures

1. **Architecture modulaire bien découpée** : séparation claire entre ingestion, scoring, risk, exécution, backtesting, IHM.
2. **Convention de prix solide** : `data_adjustment='split'` avec dividendes via `portfolio_cash_ledger`, matérialisée par des contraintes SQL CHECK.
3. **Provider switch OHLCV propre** : EODHD primaire, Alpaca rétrocompatibilité, no-op explicite quand le mauvais provider est appelé, pas de fallback automatique dangereux.
4. **Idempotence** : clés SHA-256 sur les intentions d'ordres, les événements corporate actions, les signaux sentiment.
5. **Multi-comptes** : `AccountRegistry` bien conçu, propagation cohérente de `account_id` dans les tables d'exécution et de risque.
6. **Test suite extensive** : ~230 fichiers de test couvrant la plupart des modules, avec des tests de parité backtest/live, des tests de cohérence IHM/CLI, et des property-based tests.
7. **Garde-fous live** : circuit breaker, kill switch, preflight checks, vérification des credentials au démarrage.

---

## 3. Faiblesses critiques

1. **Documentation partiellement obsolète** : `DOC_FONCTIONNELLE.md` et `DOC_TECHNIQUE.md` mentionnent des versions de sprints (S1-S7) mais ne reflètent pas toujours les plans v2 (short selling, ML ternaire) en cours d'implémentation. Plusieurs documents de `doc/` contiennent des références croisées qui peuvent être périmées.
2. **Presets de capital inconsistants entre tranches** : le preset micro-compte (0-2000€) utilise `execution_swing_only: false` alors que les petits comptes cash devraient être swing-only. Les paramètres de drawdown breaker (`degraded_entry_allocation_pct=0.025`, `ramp_up_max_pct=0.8`) sont identiques pour TOUTES les tranches, ce qui n'a pas de sens métier.
3. **Défaut IHM vs preset divergence** : l'IHM utilise `execution_account_type='cash'` et `execution_swing_only=True` comme défauts, mais les presets capital pour les tranches ≥25k$ utilisent `margin` et `swing_only=false`. L'opérateur peut facilement se tromper.
4. **Complexité ML élevée** : le plan ML v2 ternaire (long/flat/short) et le plan v2 short selling s'ajoutent à une gouvernance ML déjà complexe (LSTM + LightGBM + CatBoost + global model + cross-sectional). Le risque d'overfitting et de fragilité opérationnelle est réel.
5. **Pas de sandbox de pré-production** : pas de mode "paper strict" simulant exactement les contraintes live avant de passer en live.

---

## 4. Risques majeurs identifiés

| Risque | Sévérité | Probabilité |
|---|---|---|
| Univers vide sur micro-comptes avec les filtres stricts actuels | **P0** | Élevée |
| Incohérence IHM/presets pouvant causer une mauvaise config d'exécution | **P0** | Moyenne |
| Double-ajustement corporate actions si provider switch mal maîtrisé | **P1** | Faible |
| Backtest trompeur dû à une fidélité PIT insuffisante sur les données exotiques | **P1** | Moyenne |
| Fragilité du pipeline si un module ML échoue silencieusement | **P1** | Faible |
| Sur-confiance dans les scores ML sans validation out-of-sample suffisante | **P2** | Moyenne |

---

## 5. Recommandations immédiates (quick wins)

1. **Harmoniser `execution_swing_only` dans tous les presets** : tous les comptes ≤25k$ en cash devraient être `swing_only=true`.
2. **Réviser les paramètres de drawdown breaker par tranche** : un micro-compte ne devrait pas avoir le même `ramp_up_max_pct=0.8` qu'un compte 100k$+.
3. **Mettre à jour `DOC_FONCTIONNELLE.md` et `DOC_TECHNIQUE.md`** pour refléter les plans v2 en cours.
4. **Ajouter un test E2E IHM → backend** qui vérifie que tous les paramètres exposés dans l'IHM sont bien transmis et acceptés par les modules backend.

---

## 6. Verdict

**Note globale : 6.2/10** — Application **solide** pour un projet indépendant avancé. La base architecturale est saine, la couverture de tests est impressionnante pour un projet de cette taille, et les préoccupations de production sont réelles. Cependant, l'accumulation rapide de fonctionnalités a créé une dette de cohérence (documentation, paramétrages, IHM/backend) qui doit être résorbée avant de pouvoir prétendre à un niveau professionnel.

**Avec le plan de sprints proposé, l'application peut atteindre ~8.5/10 en 6 mois.**
