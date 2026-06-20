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
2. **Presets de capital inconsistants entre tranches** : les paramètres de drawdown breaker (`degraded_entry_allocation_pct=0.025`, `ramp_up_max_pct=0.8`) sont identiques pour TOUTES les tranches, ce qui n'a pas de sens métier. En revanche, `execution_swing_only=false` sur tous les presets est désormais **correct** depuis la suppression de la règle PDT par la FINRA le 4 juin 2026 : le day trading (achat/vente intraday) est autorisé sans restriction, y compris sur les petits comptes.
3. **Défaut IHM vs preset divergence** : l'IHM utilise `execution_swing_only=True` comme défaut, mais les presets capital utilisent `swing_only=false` — ce qui est désormais le bon choix post-PDT. C'est l'IHM qui doit être mise à jour pour refléter la nouvelle réalité réglementaire (swing_only=false par défaut). L'opérateur peut se tromper s'il se fie aux défauts IHM sans vérifier.
4. **Complexité ML élevée** : le plan ML v2 ternaire (long/flat/short) et le plan v2 short selling s'ajoutent à une gouvernance ML déjà complexe (LSTM + LightGBM + CatBoost + global model + cross-sectional). Le risque d'overfitting et de fragilité opérationnelle est réel.
5. **Pas de sandbox de pré-production** : pas de mode "paper strict" simulant exactement les contraintes live avant de passer en live.

---

## 4. Risques majeurs identifiés

| Risque | Sévérité | Probabilité |
|---|---|---|
| Univers vide sur micro-comptes avec les filtres stricts actuels | **P0** | Élevée |
| IHM par défaut `swing_only=True` en contradiction avec les presets (post-PDT, swing_only=false est correct) | **P1** | Moyenne |
| Double-ajustement corporate actions si provider switch mal maîtrisé | **P1** | Faible |
| Backtest trompeur dû à une fidélité PIT insuffisante sur les données exotiques | **P1** | Moyenne |
| Fragilité du pipeline si un module ML échoue silencieusement | **P1** | Faible |
| Sur-confiance dans les scores ML sans validation out-of-sample suffisante | **P2** | Moyenne |

---

## 5. Recommandations immédiates (quick wins)

1. **Mettre à jour le défaut `execution_swing_only` dans l'IHM** : depuis la suppression de la règle PDT par la FINRA (4 juin 2026), `swing_only=false` est le bon choix pour tous les comptes. L'IHM doit refléter ce nouveau défaut.
2. **Réviser les paramètres de drawdown breaker par tranche** : un micro-compte ne devrait pas avoir le même `ramp_up_max_pct=0.8` qu'un compte 100k$+.
3. **Mettre à jour `DOC_FONCTIONNELLE.md` et `DOC_TECHNIQUE.md`** pour refléter les plans v2 en cours.
4. **Ajouter un test E2E IHM → backend** qui vérifie que tous les paramètres exposés dans l'IHM sont bien transmis et acceptés par les modules backend.

---

## 6. Verdict

**Note globale : 7.8/10** — Application **quasi-professionnelle**. Les sprints S8 à S14 ont résolu toutes les anomalies P0, aligné l'IHM sur la réalité post-PDT, rendu le backtesting réaliste, mis à jour la documentation, activé le cross-check corporate actions, et amélioré l'observabilité. La base architecturale est saine, la couverture de tests est impressionnante, et les préoccupations de production sont réelles.

**Avec les sprints S15-S17 restants (sécurité, polish, validation paper), l'application peut atteindre ~8.5/10 et être prête pour le live discipliné.**
