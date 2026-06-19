# 05 — Doc / Code Gap Matrix

> **Écarts documentés entre la documentation, le code source et la configuration**

---

## Légende

| Statut | Signification |
|---|---|
| ✅ Aligné | La doc, le code et la config sont cohérents |
| ⚠️ Écart mineur | Divergence non critique, documentée |
| ❌ Écart majeur | Divergence pouvant induire en erreur |
| 🔄 En transition | Le code évolue, la doc suit avec retard |

---

## 1. Conventions OHLCV / Provider

| Point | Doc | Code | Config | Statut |
|---|---|---|---|---|
| Provider primaire | EODHD (`DOC_FONCTIONNELLE.md`, `DOC_TECHNIQUE.md`, `dataIntegrityEngine.md`) | `dataIntegrityEngine/import_eodhd_bar.py` actif | `config.yaml › market_data.bars_provider: eodhd` | ✅ Aligné |
| Provider rétrocompat | Alpaca IEX supporté | `import_alpaca_bar.py` avec no-op si `bars_provider!=alpaca` | `bars_provider: alpaca` possible | ✅ Aligné |
| `data_adjustment` | `'split'` canonique | `import_alpaca_bar.py:DATA_ADJUSTMENT='split'`, `adapters.py:DATA_ADJUSTMENT_SPLIT` | Contrainte SQL CHECK | ✅ Aligné |
| Fallback auto inter-provider | Documenté comme **absent** (S0) | Pas implémenté | `fallback_on_failure` retiré | ✅ Aligné |
| Provider CA lié au `bars_provider` | Documenté | `provider.py:build_corporate_action_provider()` | — | ✅ Aligné |

---

## 2. Filtres et seuils

| Point | Doc | Code (`core/filter_profiles.py`) | Statut |
|---|---|---|---|
| `max_spread_bps` | 40 bps (corrigé S4), mention historique 25 bps | 40.0 | ⚠️ Écart mineur (doc mentionne l'historique) |
| `min_beta_126` | 0.8 (corrigé S4), mention historique 1.0 | 0.8 | ⚠️ Écart mineur |
| `min_close` | 10$ | 10.0 | ✅ Aligné |
| `min_avg_dollar_volume_20d` | 30 M$ | 30_000_000.0 | ✅ Aligné |
| `max_volatility_ratio` | 0.90 | 0.9 | ✅ Aligné |
| `min_relative_strength_index` | 100 | 100.0 | ✅ Aligné |
| `min_high_52w_proximity` | 0.75 | 0.75 | ✅ Aligné |
| `min_weekly_trend_score` | 1.0 | 1.0 | ✅ Aligné |
| `min_atr_pct_20` | 1.5% | 0.015 | ✅ Aligné |
| `max_atr_pct_20` | 6% | 0.06 | ✅ Aligné |
| `min_market_cap` | 2 Md$ | 2_000_000_000.0 | ✅ Aligné |
| `earnings_blackout` | 0 (dans le profil strict) | 0 | ✅ Aligné |

---

## 3. Architecture et flux

| Point | Doc | Code | Statut |
|---|---|---|---|
| Launcher canonique exécution | `run_execution.py` | `run_execution.py` | ✅ Aligné |
| `python -m execution_engine` | Déprécié, façade de compatibilité | `__main__.py` émet DeprecationWarning | ✅ Aligné |
| `cancel-all` natif | `execution_engine` | `cli.py` conserve `cancel-all` | ✅ Aligné |
| Ordre du pipeline 1→14 | Documenté dans `DOC_FONCTIONNELLE.md` | IHM `pipeline.py` suit cet ordre | ⚠️ Le step 1 est `import_alpaca_bar` dans l'IHM mais devrait être `import_eodhd_bar` en mode EODHD |
| Watcher post-exécution | Étapes 12.bis | `protection_watcher.py` | ✅ Aligné |
| Profil strict partagé | `core/filter_profiles.py` canonique | `selector/strict_filter_profiles.py` alias | ✅ Aligné |

---

## 4. IHM ↔ Backend

| Point | IHM | Backend | Statut |
|---|---|---|---|
| Step 1 (barres) | `import_alpaca_bar` dans le workflow | `import_eodhd_bar` si `bars_provider=eodhd` | ⚠️ L'IHM devrait afficher le bon module selon le provider |
| `execution_account_type` défaut | `cash` | Preset ≥25k$ = `margin` | ❌ Divergence — cf. A-IHM-001 |
| `execution_swing_only` défaut | `True` | Presets = `false` | ❌ Divergence — cf. A-IHM-001 |
| Options screener | Exposées dans l'IHM | Supportées par `stock_screener` | ✅ Aligné |
| Options selector | Exposées dans l'IHM | Supportées par `alpha_scanner` | ✅ Aligné |
| Options ML | 30+ paramètres exposés | Supportés par `modelFactory` | ⚠️ Trop de paramètres — cf. A-ML-001 |

---

## 5. Schéma SQL

| Point | Doc (`database.md`) | Code (DDL) | Statut |
|---|---|---|---|
| `data_adjustment` CHECK | Documenté §9 | `chk_bars_adj`, `chk_daily_adj` | ✅ Aligné |
| `account_id` sur tables critiques | Documenté (`DOC_TECHNIQUE.md`) | Présent dans les DDL | ✅ Aligné |
| `data_source` dans `stock_bars_daily` | Documenté (lineage matrix) | Colonne présente | ✅ Aligné |
| PK `(symbol, date)` | Documenté | Implémenté | ✅ Aligné |
| Tables plan v2 | Non documenté | En cours d'implémentation | 🔄 En transition |

---

## 6. Plans v2 (Short Selling + ML Ternaire)

| Point | Doc (`DOC_TECHNIQUE.md`) | Code | Statut |
|---|---|---|---|
| Short selling support | Plan v2 Sprint 0-5 documenté | `core/direction.py`, `selector/short_score.py`, `risk_management/concentration.py`, `backtesting/simulator.py` | 🔄 En cours |
| ML ternaire long/flat/short | Plan ML v2 Sprint 1-7 documenté | `modelFactory/features.py`, `model.py`, `db_registry.py` | 🔄 En cours |
| Migration 0038/0039 | Mentionnée dans la doc | Alembic à vérifier | 🔄 Statut incertain |
| Statut global v2 | Non précisé | Code partiellement présent | ❌ La doc devrait indiquer le statut |

---

## 7. Synthèse des actions documentaires prioritaires

1. **Mettre à jour `DOC_FONCTIONNELLE.md`** : nettoyer les valeurs historiques, indiquer le statut des plans v2
2. **Mettre à jour `DOC_TECHNIQUE.md`** : clarifier le statut d'implémentation des plans v2
3. **Corriger le step 1 dans l'IHM** : afficher `import_eodhd_bar` quand `bars_provider=eodhd`
4. **Aligner les défauts IHM sur les presets** : `execution_account_type` et `execution_swing_only`
5. **Documenter les migrations Alembic** pour les plans v2
