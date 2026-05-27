# 05 — Matrice des écarts doc ↔ code ↔ config

Date : mai 2026

---

## Légende

- ✅ Cohérent — doc, code et config sont alignés
- ⚠️ Écart mineur — divergence sans impact critique
- ❌ Écart majeur — divergence avec impact opérationnel
- 🔍 Non vérifié — nécessite investigation complémentaire

---

## 1. Matrice principale

| # | Sujet | Doc | Code | Config | Statut | Détail |
|---|---|---|---|---|---|---|
| 1 | Convention `data_adjustment = 'split'` | CONVENTIONS.md, DOC_FONCTIONNELLE.md, DOC_TECHNIQUE.md, dataIntegrityEngine.md | `import_alpaca_bar.py: DATA_ADJUSTMENT = "split"` | Contrainte SQL CHECK | ✅ | Cohérent de bout en bout |
| 2 | Provider OHLCV primaire = EODHD | CONVENTIONS.md, data_lineage_matrix.md, README.md, DOC_FONCTIONNELLE.md, DOC_TECHNIQUE.md, dataIntegrityEngine.md | `resolve_bars_provider()` garde un fallback technique `"alpaca"` si config absente ; runtime nominal piloté par `config.yaml` | `market_data.bars_provider: eodhd` | ⚠️ | Le dépôt versionné est aligné sur `eodhd`, mais le fallback interne sans config reste `alpaca` |
| 3 | Provider news par défaut | CONVENTIONS.md, DOC_FONCTIONNELLE.md, DOC_TECHNIQUE.md → `alpaca` ; README.md → `eodhd` | `event_sentiment/cli.py` + `event_sentiment/config.py` → défaut `eodhd` | N/A (CLI `--news-provider`) | ❌ | Incohérence doc/doc confirmée ; le code est bien `eodhd` |
| 4 | Quotes = Alpaca IEX | CONVENTIONS.md §1, dataIntegrityEngine.md | `sync_latest_quotes.py` utilise Alpaca | N/A | ✅ | Cohérent |
| 5 | Profil strict = `STRICT_SWING_CASH_FILTERS` | DOC_FONCTIONNELLE.md §2.3, DOC_TECHNIQUE.md §2.1 | `core/filter_profiles.py` | `capital_presets.yaml` overrides | ⚠️ | Profil cohérent, mais presets peuvent diverger sans garde-fou |
| 6 | `adj_close = close` dans `stock_bars_daily` | dataIntegrityEngine.md §8.2 | `data_sanitizer_daily.py` | N/A | ✅ | Documenté et cohérent |
| 7 | Provider CA aligné sur provider OHLCV | data_lineage_matrix.md §5 | `corporate_actions/provider.py:build_corporate_action_provider()` | `market_data.bars_provider` | ✅ | Cohérent |
| 8 | `stock_assets` vs `stock_metadata` | data_lineage_matrix.md §1 | Code et SQL | Tables SQL → les deux existent conceptuellement dans la doc métier | ✅ | `stock_assets` et `stock_metadata` sont deux objets distincts, pas un renommage erroné |
| 9 | Tables ML listées dans lineage | data_lineage_matrix.md §3 | `database/sql/ml/` + `database/sql/risk/` | SQL versionné présent | ✅ | `model_governance`, `model_metrics_full`, `ml_drift_runs`, `shadow_drift_runs` existent bien |
| 10 | Entrée canonique exécution = `run_execution.py` | CONVENTIONS.md §4, README.md §8, DOC_TECHNIQUE.md §5 | `run_execution.py` + `execution_engine/__main__.py` (déprécié) | N/A | ✅ | Cohérent |
| 11 | Cash ledger pour dividendes | DOC_FONCTIONNELLE.md §2.9, corporate_actions.md | `corporate_actions/engine.py`, `corporate_actions/processors.py` | `portfolio_cash_ledger` | ✅ | Cohérent |
| 12 | Pipeline quotidien 1→14 | README.md §6, DOC_FONCTIONNELLE.md §3.1, DOC_TECHNIQUE.md §10 | `ihm/pages/pipeline.py` (workflow IHM) | N/A | ⚠️ | README liste `import_alpaca_bar` comme étape 1, puis `import_eodhd_bar` ; ordre clarifié mais peut prêter à confusion |
| 13 | `execution_pdt_rule: "off"` sur comptes cash | capital_presets.yaml (commentaires) | `execution_engine/config.py:effective_pdt_rule` → PDT désactivée si cash | N/A | ✅ | Cohérent |
| 14 | `scores_pit_mode` en backtesting | DOC_FONCTIONNELLE.md §9 | `backtesting/simulator.py` | CLI `--scores-pit-mode exact/asof_latest` | ✅ | Cohérent |
| 15 | Market-Aware preflight | DOC_FONCTIONNELLE.md §8, DOC_TECHNIQUE.md §11 | `execution_engine/market_regime_preflight.py`, `run_execution.py` | `config.yaml > market_regimes` | ✅ | Cohérent |
| 16 | Fallback inter-provider OHLCV inexistant | dataIntegrityEngine.md (« Pas de fallback automatique ») | `import_alpaca_bar.py` et `import_eodhd_bar.py` : no-op explicite, pas de fallback | Pas de clé `fallback_on_failure` | ✅ | Cohérent |
| 17 | Biais IEX documenté et mesuré | dataIntegrityEngine.md, DATA_LINEAGE | `sync_latest_quotes.py` → `quote_iex_vs_consolidated_bps` | N/A | ✅ | Cohérent |
| 18 | `max_positions` par défaut | DOC_FONCTIONNELLE.md §2.5 → 20 | `risk_management/` → dépend du preset | Override par preset | ⚠️ | La doc donne 20 comme défaut, mais les presets varient de 3 à 18 |
| 19 | `correlation_threshold` par défaut | DOC_FONCTIONNELLE.md §2.5 → 0.80 | `risk_management/` → dépend du preset | 0.78 à 0.92 selon le preset | ⚠️ | La doc donne 0.80, mais les presets ajustent |
| 20 | Docs POC sans bandeau | CONVENTIONS.md §6 | Fichiers dans `doc/` (à revalider fichier par fichier) | N/A | 🔍 | Constat plausible mais non revalidé exhaustivement dans cette contre-revue |

---

## 2. Synthèse des écarts

| Statut | Nombre |
|---|---|
| ✅ Cohérent | 14 |
| ⚠️ Écart mineur | 4 |
| ❌ Écart majeur | 1 |
| 🔍 Non vérifié | 1 |

---

## 3. Corrections recommandées (ordre de priorité)

1. **A-001** : Aligner le provider news par défaut dans toute la documentation sur `eodhd` (P1)
2. **A-002** : Décider et documenter explicitement le fallback interne `bars_provider` en absence de config (P2)
3. **A-027** : Revalider puis ajouter les bandeaux POC aux documents concernés (P2)
4. Mettre à jour `DOC_FONCTIONNELLE.md` pour préciser que `max_positions` et `correlation_threshold` varient selon le preset de capital (P3)
