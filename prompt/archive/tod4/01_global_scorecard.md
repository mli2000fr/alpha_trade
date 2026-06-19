# 01 — Tableau global des notes

**Application** : Alpha Trade v0.3.0  
**Date d'audit** : mai 2026  
**Échelle** : 0-10 (10 = niveau institutionnel mature)

---

## Notes par module/domaine

| # | Module / Domaine | Note /10 | Niveau | Tendance |
|---|---|---|---|---|
| 1 | Documentation | 7.0 | Solide | ↑ (améliorations continues) |
| 2 | Configuration | 6.5 | Prometteur | → (stable) |
| 3 | DataIntegrityEngine | 8.0 | Solide | ↑ (provider switch maîtrisé) |
| 4 | Database | 7.5 | Solide | ↑ (multi-comptes, migrations) |
| 5 | Service / Providers | 7.0 | Solide | ↑ (EODHD intégré) |
| 6 | Screener | 7.5 | Solide | → (profil strict aligné) |
| 7 | Selector (AlphaScanner) | 8.0 | Solide | ↑ (profil partagé, PIT) |
| 8 | Event Sentiment | 7.0 | Prometteur | → (scope mixte, N4 optionnel) |
| 9 | ModelFactory | 6.5 | Prometteur | ↑ (gouvernance multi-modèles) |
| 10 | Risk Management | 8.0 | Solide | ↑ (circuit breaker, régime) |
| 11 | Execution Engine | 8.5 | Solide → Pro | ↑ (chaîne canonique, TCA) |
| 12 | Corporate Actions | 7.5 | Solide | ↑ (idempotence, ledger) |
| 13 | Backtesting | 8.0 | Solide | ↑ (PIT, contraintes, phases) |
| 14 | IHM | 7.5 | Solide | ↑ (workflow, supervision) |
| 15 | Observabilité / Run Summaries / Logs | 7.0 | Prometteur | → (hétérogénéité) |
| 16 | Sécurité / Readiness Production | 7.0 | Prometteur | ↑ (secrets scannés, préflight) |
| 17 | Qualité Logicielle Globale | 7.5 | Solide | ↑ (lint, mypy, tests) |

---

## Note globale

| Métrique | Valeur |
|---|---|
| **Note globale** | **7,3 / 10** |
| Niveau de confiance | Élevé (80%) |
| Positionnement | **Prometteur → Solide** |
| Verdict | **Exploitable en paper, préparation live en cours** |

---

## Comparaison explicite

| Niveau de référence | Note typique | Alpha Trade |
|---|---|---|
| Application amateur sérieuse | 3-5 / 10 | **Au-dessus** |
| Application indépendante avancée | 5-7 / 10 | **Dans la fourchette haute** |
| Application pro buy-side / prop desk swing | 7-9 / 10 | **Atteint le bas de cette fourchette** |
| Application institutionnelle très mature | 9-10 / 10 | **Encore en dessous** |

---

## Répartition des notes

```
10.0 ┤
 9.0 ┤
 8.0 ┤     ▄▄▄▄▄▄▄▄
 7.0 ┤ ▄▄▄▄▄▄▄▄▄▄▄▄▄▄
 6.0 ┤ ▄▄▄▄▄▄
 5.0 ┤
 4.0 ┤
 3.0 ┤
 2.0 ┤
 1.0 ┤
 0.0 ┤
     1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17
```

Modules les mieux notés : Execution Engine (8.5), DataIntegrityEngine (8.0), Selector (8.0), Risk Management (8.0), Backtesting (8.0).

Modules les moins bien notés : ModelFactory (6.5), Configuration (6.5).

---

## Notes des principales familles fonctionnelles

| Famille | Modules | Note moyenne |
|---|---|---|
| **Ingestion & Qualité données** | DataIntegrityEngine, Database, Service/Providers | 7.5 / 10 |
| **Sélection & Alpha** | Screener, Selector, Event Sentiment, ModelFactory | 7.3 / 10 |
| **Risk & Exécution** | Risk Management, Execution Engine, Corporate Actions | 8.0 / 10 |
| **Recherche & Validation** | Backtesting | 8.0 / 10 |
| **Opérations & Supervision** | IHM, Observabilité, Sécurité | 7.2 / 10 |
| **Socle transverse** | Documentation, Configuration, Qualité Logicielle | 7.0 / 10 |

---

## Évolution depuis l'audit précédent (tod2)

L'application a progressé significativement depuis l'audit tod2 (mai 2026) :
- Provider switch EODHD finalisé et documenté
- Profil strict partagé centralisé dans `core/filter_profiles.py`
- Chaîne d'exécution canonique complétée (reconciliation, TCA)
- Multi-comptes généralisé
- Gouvernance ML multi-modèles
- Backtesting PIT avec contraintes de compte
- Couche Market-Aware (régimes, trailing ATR)
- Presets de capital par tranche

Les zones qui restent à améliorer sont principalement : l'industrialisation (orchestration, monitoring), l'uniformisation des résumés, et quelques incohérences documentaires résiduelles.