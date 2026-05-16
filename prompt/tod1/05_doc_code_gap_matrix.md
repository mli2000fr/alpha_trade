# 05 — Matrice des Écarts Doc ↔ Code ↔ Config — Alpha Trade

> **Date** : mai 2026 | Convention : le **code courant est la source de vérité prioritaire**

---

## Légende

- ✅ **Cohérent** : doc et code alignés
- ⚠️ **Écart mineur** : différence de formulation ou omission non bloquante
- ❌ **Écart majeur** : information fausse ou obsolète pouvant induire en erreur
- ❓ **À confirmer** : ambiguïté nécessitant vérification plus profonde dans le code

---

## 1. Provider OHLCV (critique)

| Point | DOC_FONCTIONNELLE | DOC_TECHNIQUE | data_lineage_matrix | config.yaml | Code réel | Verdict |
|---|---|---|---|---|---|---|
| Provider primaire OHLCV | EODHD ✅ (encart) | EODHD ✅ (encart) | EODHD ✅ | `bars_provider: eodhd` ✅ | `import_eodhd_bar.py` actif | ✅ |
| Provider rétrocompat | Alpaca ✅ | Alpaca ✅ | Alpaca ✅ | — | `import_alpaca_bar.py` (no-op si eodhd) | ✅ |
| `data_adjustment='split'` | ✅ | ✅ | ✅ | — | `eodhd_to_split_only()`, CHECK SQL | ✅ |
| Step 1 pipeline §1.3 | "import_alpaca_bar" ❌ | "import_eodhd_bar (primaire)" ✅ | EODHD ✅ | — | `import_eodhd_bar.py` | ❌ Doc fonctionnelle step 1 |
| Provider quotes | Alpaca IEX ✅ | Alpaca IEX ✅ | Alpaca IEX ✅ | — | `sync_latest_quotes.py` Alpaca | ✅ |

**Écart majorité** : `DOC_FONCTIONNELLE.md §1.3` nomme encore `import_alpaca_bar` pour l'étape 1. Le code réel utilise `import_eodhd_bar` quand `bars_provider=eodhd`. Correction requise.

---

## 2. Corporate Actions — Provider

| Point | DOC_FONCTIONNELLE §2.9 | data_lineage_matrix §5/§7 | Code réel | Verdict |
|---|---|---|---|---|
| Provider CA primaire | ✅ `EodhdCorporateActionProvider` si `bars_provider=eodhd` (DOC_FONCTIONNELLE.md:246) | ✅ Règle de sélection documentée §7:109-111 | Factory conditionnelle (`corporate_actions/provider.py:402-432`) | ✅ **RÉSOLU** (A-005) |
| Switch provider CA | ✅ Documenté dans §2.9 | ✅ Documenté dans §7 | `build_corporate_action_provider()` correctement implémentée | ✅ |
| Yahoo cross-check | Non mentionné | Mentionné | `test_corporate_actions_cross_check_yahoo.py` suggère implémenté | ✅ (cohérent code ↔ lineage) |


---

## 3. Tables SQL — Noms canoniques

| Table logique | data_lineage_matrix §4 | Tables réelles | Verdict |
|---|---|---|---|
| Ordres d'exécution | `execution_orders` ❌ | `execution_order_requests` + `execution_broker_orders` | ❌ |
| Événements audit exec | `execution_audit_events` ❌ | `execution_events` | ❌ |
| Données scoring | `selector_alpha_candidates` | `stock_scores` (update via AlphaScanner) | ⚠️ Sémantique différente |
| ML drift | `ml_drift_runs` | `ml_drift_runs` (Phase 7.4 + S4 gate) | ✅ |
| Watcher heartbeats | `watcher_heartbeats` | `run_business_summaries` (watcher section) | ⚠️ Ambiguïté |

**Écart majeur** : `execution_orders` et `execution_audit_events` sont des noms obsolètes. Ces tables n'existent plus dans le schéma canonique depuis le refactoring exécution. La lineage doit être régénérée.

---

## 4. Backtesting — Framework

| Point | DOC_TECHNIQUE §9 | Code réel | Verdict |
|---|---|---|---|
| Framework backtest | ✅ "simulateur custom PIT — aucune dépendance vectorbt" (`DOC_TECHNIQUE.md:497`) | `backtesting/simulator.py` custom | ✅ **RÉSOLU** (A-004) |
| Moteur backtesting | "BacktestEngine" | `BacktestEngine` (`backtesting/simulator.py`) | ✅ |
| Résidu argparse | `backtesting/cli/_impl.py:67` : `description="Backtest intégré Alpha Trade (vectorbt)"` | Non corrigé | ⚠️ Résidu cosmétique (A-004 résidu) |
| ParquetCache branché | "pas encore branché par défaut" | Non branché dans CLI `run` | ✅ (doc exacte) |
| Walk-forward | Documenté | `backtesting/walk_forward.py` | ✅ |

---

## 5. Scoring / Conviction Weights

| Point | DOC_FONCTIONNELLE §3.3 | config.yaml | Code réel | Verdict |
|---|---|---|---|---|
| Fusion signal | 75% quant + 15% sentiment + 10% macro | `quant_weight: 0.75, sentiment_weight: 0.15, macro_weight: 0.10` | `SentimentSignalAggregator` utilise ces poids | ✅ |
| Conviction risk | 40% quant + 60% ML | (`risk_score_weight: 0.40, risk_prediction_weight: 0.60` dans presets) | `compute_conviction()` | ✅ |
| DOC_FONCTIONNELLE §2.4 | "40% quant + 60% ML" | Presets 10k+ | Code | ✅ |
| DOC_FONCTIONNELLE §2.4 | "40% quant + 60% ML" | Preset micro-compte : `0.45/0.55` ⚠️ | Capital preset `capital_0_2000_eur` différent | ⚠️ Légère incohérence preset vs doc |

**Écart mineur** : La doc cite "40%/60%" comme défaut mais les présets petits comptes utilisent "45%/55%". C'est intentionnel (plus de poids quant car ML moins fiable sur micro-compte) mais non documenté.

---

## 6. AlphaScanner — Filtres stricts

| Point | DOC_FONCTIONNELLE §2.3 | core/filter_profiles.py | config/capital_presets.yaml | Verdict |
|---|---|---|---|---|
| `min_close` | 10 $ | 10 $ | Variable (5–12 $) | ⚠️ Divergence presets petits comptes |
| `avg_dollar_volume_20d` | 30 M$ | 30 M$ | Variable (2M–40M$) | ⚠️ Presets petits comptes relâchés (justifié) |
| `volatility_ratio` | ≤ 0.90 | 0.90 | Variable (0.85–1.0) | ⚠️ Cohérent sauf micro-compte (1.0) |
| `min_market_cap` | 2 Md$ | 2 Md$ | Variable (500M–3Md$) | ⚠️ Micro-compte à 500M$ sous-optimal |
| `max_spread_bps` | 25 bps (doc) vs 40 bps (code) | 40 bps | Variable (35–80 bps) | ⚠️ Doc cite 25 bps, code est 40 bps |
| `beta_126` | ≥ 1.0 (doc) | ≥ 0.8 (code) | Variable (0.65–0.9) | ❌ Divergence doc (1.0) vs code (0.8) |
| `earnings_blackout` | 3 jours | 3 jours | Variable (2–4 jours) | ✅ |

**Écart** : `DOC_FONCTIONNELLE.md §2.3` cite `beta_126 >= 1.0` mais `core/filter_profiles.py:STRICT_SWING_CASH_FILTERS.min_beta_126 = 0.8`. La valeur dans le code (0.8) est la source de vérité. La doc est en retard. Idem pour `max_spread_bps` (doc dit 25 bps, code dit 40 bps).

---

## 7. model_predictions — Champs DB

| Point | DOC_TECHNIQUE §5.5 | Schéma DB réel | Verdict |
|---|---|---|---|
| `selected_model` | ✅ Présent | `model_predictions.sql:8` — `selected_model VARCHAR(32)` | ✅ **RÉSOLU** (A-003) |
| `decision_threshold` | ✅ Présent | `model_predictions.sql:9` — `decision_threshold DOUBLE` | ✅ **RÉSOLU** (A-003) |
| `calibration_method` | ✅ Présent | `model_predictions.sql:10` — `calibration_method VARCHAR(32)` | ✅ **RÉSOLU** (A-003) |
| `signal_label` | ✅ Présent | `model_predictions.sql:11` — `signal_label VARCHAR(32)` | ✅ **RÉSOLU** (A-003) |
| Idempotence `model_predictions` | `ON DUPLICATE KEY UPDATE` dans `db_registry.py:342-348` | `UNIQUE KEY uq_symbol_date_run` présent | ✅ **RÉSOLU** (A-009) |

---

## 8. IHM — Cohérence pipeline GUI vs backend CLI

| Étape IHM | Commande backend réelle | Options IHM exposées | Options backend disponibles | Verdict |
|---|---|---|---|---|
| Step 1 - Import bars | `python -m dataIntegrityEngine.import_eodhd_bar` (si eodhd) | Paramètre `bars_provider` dans settings | Options CLI complètes | ✅ |
| Step 6 - Alpha Scanner | `python -m selector.alpha_scanner` | Pas de toggle preset (profil strict implicite) | `--strict-swing-cash` | ✅ |
| Step 9 - ML Train | `python -m modelFactory --mode train` | Sous-ensemble cohérent documenté | Flags avancés non exposés | ⚠️ Flags avancés absents IHM |
| Step 10 - ML Predict | `python -m modelFactory --mode predict` | Pas de choix backend manuel | `--symbol-override` etc. | ✅ (correct : backend auto-sélectionné) |
| Step 12 - Execution | `python run_execution.py` | paper/live/simulate, account selector | `--dry-run`, `--account` | ✅ |

---

## 9. Matrice de résolution des contradictions

| Contradiction | Version doc | Version code | Verdict (source de vérité) | Statut |
|---|---|---|---|---|
| Step 1 pipeline = `import_alpaca_bar` | DOC_FONCTIONNELLE §1.3 | `import_eodhd_bar.py` actif | **Code** — la doc doit être corrigée | ✅ RÉSOLU (A-018) |
| CA provider = Alpaca vs EODHD | DOC_FONCTIONNELLE §2.9 vs lineage matrix | Factory conditionnelle | **Code (factory)** — les deux docs doivent préciser la règle | ✅ RÉSOLU (A-005) |
| `max_spread_bps` = 25 bps | DOC_FONCTIONNELLE §2.3 | `STRICT_SWING_CASH_FILTERS.max_spread_bps = 40` | **Code (40 bps)** — doc à corriger | 🔴 Actif |
| `beta_126 >= 1.0` | DOC_FONCTIONNELLE §2.3 | `STRICT_SWING_CASH_FILTERS.min_beta_126 = 0.8` | **Code (0.8)** — doc à corriger | 🔴 Actif |
| Backtest framework = vectorbt | DOC_TECHNIQUE §9 | Simulateur custom | **Code** — mention vectorbt supprimée dans §9 | ✅ RÉSOLU (A-004 principal) ; résidu argparse |
| Noms tables execution | data_lineage_matrix §4 | Schéma réel | **Code/schéma** — régénérer la lineage matrix | 🔴 Actif (A-002) |
| `model_predictions` sans gouvernance ML | DOC_TECHNIQUE §5.5 | Colonnes présentes dans SQL | **Code** — gouvernance ML en DB complète | ✅ RÉSOLU (A-003) |

