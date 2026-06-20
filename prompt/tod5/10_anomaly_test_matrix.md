# 10 — Anomaly Test Matrix

> **Matrice traçable : Anomalie → Correctif → Test(s) → Sprint**

---

## Tableau de traçabilité

| ID Anomalie | Sévérité | Correctif | Test(s) associé(s) | Sprint |
|---|---|---|---|---|
| A-CAP-001 | ~~P0~~ → **RÉSOLU** | ~~Activer swing_only~~ → Résolu par FINRA 2026-06-04 | ~~T-CAP-001~~ | ~~S8~~ |
| A-CAP-002 | ~~P0~~ → **RÉSOLU S8** | Drawdown breaker différencié | T-CAP-002 ✅ | S8 ✅ |
| A-CAP-003 | ~~P0~~ → **RÉSOLU S8** | min_notional ≥ 155 $ | T-CAP-003 ✅ | S8 ✅ |
| A-IHM-001 | ~~P1~~ → **RÉSOLU S8-bis** | swing_only=False IHM | T-IHM-001 ✅ | S8-bis ✅ |
| A-DOC-001 | ~~P1~~ → **RÉSOLU S10** | Nettoyage doc | T-DOC-001 | S10 ✅ |
| A-CA-001 | ~~P1~~ → **RÉSOLU S13** | Cross-check Yahoo par défaut | T-CA-001 ✅ | S13 ✅ |
| A-BACK-001 | ~~P1~~ → **RÉSOLU S11** | Cache Parquet + microstructure | T-BACK-001 ⏳ | S11 ✅ |
| A-RISK-001 | P1 | Justifier poids de conviction | T-RISK-001 ⏳ | S11 (ablation différée) |
| A-IHM-002 | P1 | Validation croisée IHM/preset | T-IHM-002 (intégration IHM) | S9 |
| A-DOC-001 | P1 | Nettoyer valeurs obsolètes doc | T-DOC-001 (non-régression doc) | S10 |
| A-ML-001 | P1 | Mode Expert ML dans l'IHM | T-ML-001 (E2E IHM) | S12 |
| A-EXE-001 | P1 | Documenter/supprimer __main__.py | T-EXE-001 (intégration CLI) | S10 |
| A-CA-001 | P1 | Activer cross-check Yahoo | T-CA-001 (intégration) | S13 |
| A-BACK-001 | P1 | Activer cache Parquet | T-BACK-001 (performance) | S11 |
| A-RISK-001 | P1 | Justifier poids de conviction | T-RISK-001 (non-régression) | S11 |
| A-CONV-001 | P1 | Documenter calibration poids fusion | T-CONV-001 (non-régression) | S11 |
| A-DATA-001 | P1 | Documenter invariant source unique | T-DATA-001 (SQL/intégration) | S16 |

---

## Catalogue des tests par catégorie

### Tests de configuration
| ID Test | Fichier probable | Sprint |
|---|---|---|
| T-CAP-001 : ~~swing_only sur presets cash~~ → **RÉSOLU** (FINRA 2026-06-04) | — | — |
| T-CAP-002 : drawdown breaker croissant | `tests/test_capital_presets_consistency.py` | S8 |
| T-CAP-003 : min_notional ≥ enforce_min | `tests/test_capital_presets_consistency.py` | S8 |

### Tests d'intégration IHM / CLI
| ID Test | Fichier probable | Sprint |
|---|---|---|
| T-IHM-001 : défaut swing_only=False (post-PDT) | `tests/test_ihm_cli_contract.py` | S8-bis |
| T-IHM-002 : validation rejette combinaisons incohérentes | `tests/test_ihm_pipeline_runner.py` | S9 |
| T-EXE-001 : équivalence run_execution / __main__ | `tests/test_execution_cli_cancel_all.py` | S10 |

### Tests E2E IHM
| ID Test | Fichier probable | Sprint |
|---|---|---|
| T-ML-001 : nombre de paramètres ML exposés | `tests/test_ihm_pipeline_runner.py` | S12 |
| Test E2E workflow complet | `tests/test_ihm_pipeline_e2e.py` | S9 |

### Tests de non-régression documentation
| ID Test | Fichier probable | Sprint |
|---|---|---|
| T-DOC-001 : valeurs numériques doc = code | `tests/test_docs_provider_consistency.py` | S10 |
| T-CONV-001 : poids de conviction justifiés | `tests/test_conviction_weights_config.py` | S11 |
| T-RISK-001 : ablation des poids documentée | `tests/test_conviction_weights_config.py` | S11 |

### Tests d'intégration données
| ID Test | Fichier probable | Sprint |
|---|---|---|
| T-CA-001 : cross-check Yahoo fonctionnel | `tests/test_corporate_actions_cross_check_yahoo.py` | S13 |
| T-DATA-001 : pas de double écriture multi-provider | `tests/test_data_source_consistency_runtime.py` | S16 |

### Tests de performance
| ID Test | Fichier probable | Sprint |
|---|---|---|
| T-BACK-001 : cache Parquet accélère le chargement | `tests/test_backtesting.py` | S11 |

---

## Tests recommandés supplémentaires (non liés à des anomalies)

### Tests de résistance
| Test | Type | Fichier probable | Sprint |
|---|---|---|---|
| Circuit breaker sur scénarios de crise historiques | Backtest | `tests/test_circuit_breaker.py` | S11 |
| Résilience réseau (timeout, 429, 5xx) | Intégration | `tests/test_phase1_http_retry.py` | S15 |

### Tests de parité backtest/live
| Test | Type | Fichier probable | Sprint |
|---|---|---|---|
| Parité backtest/paper sur 20 jours | Parité | `tests/test_backtest_live_parity.py` | S17 |
| Écart slippage backtest vs réel | Parité | `tests/test_backtest_live_parity_golden.py` | S17 |

### Tests de qualité logicielle
| Test | Type | Fichier probable | Sprint |
|---|---|---|---|
| Tests de mutation (hebdomadaire) | CI | `.github/workflows/mutation.yml` | S14 |
| Benchmarks screener/selector/backtesting | Performance | `tests/benchmarks/` | S14 |
| Import-linter contracts | Qualité | `tests/test_import_linter_contracts.py` | S14 |

---

## Priorisation des tests par sprint

```
S8     : ██████ (2 tests config — T-CAP-002, T-CAP-003)
S8-bis : ████████████ (3 tests IHM — post-PDT)
S9     : ██████ (finalisation IHM)
S10 : ████████ (3 tests doc/CLI)
S11 : ████████████████ (5 tests backtest/conviction)
S12 : ████████ (2 tests ML)
S13 : ████████ (1 test CA)
S14 : ████████████ (4 tests qualité)
S15 : ████████ (2 tests sécurité)
S16 : ████████ (2 tests données)
S17 : ████████████ (4 tests validation)
```

---

## Règle de couverture post-sprints

Après exécution complète du plan :
- Chaque anomalie P0/P1 a **≥ 1 test automatisé** qui la couvre ✅
- Chaque sprint a **≥ 2 tests nouveaux ou étendus** ✅
- Les tests de non-régression couvrent les conventions critiques ✅
- La parité backtest/live est testée en continu ✅
