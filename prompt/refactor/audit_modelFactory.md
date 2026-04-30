# Audit — `modelFactory`

> Périmètre : `modelFactory/` (orchestrateur, trainer, predictor, modèle LSTM+Attention,
> challengers LightGBM/CatBoost, modèle global, gouvernance champion, calibration,
> évaluation, optimisation cible/seuil, db_registry).
> Sources : `doc/modelFactory.md` (référence très détaillée — 824 lignes), code listé,
> tests `tests/test_model_factory_*`.

---

## 1. Résumé exécutif

`modelFactory/` est le module ML opérationnel : entraînement par symbole d'un modèle
séquentiel `LSTM + Attention`, challengers tabulaires locaux (LightGBM, CatBoost),
modèle global multi-symboles optionnel, calibration Platt, optimisation seuil,
optimisation target swing, **gouvernance multi-modèles** avec sélection automatique du
champion servi, prédiction batch quotidienne.

État global : **module le plus mature et le plus sophistiqué du projet**. Architecture
en couches propre (`orchestrator` → `trainer` / `predictor` → `model`/`dataset`),
artefacts disque cohérents (`config.json`, `metrics.json`, scaler, ckpt), persistance
DB de synthèse (`model_training_run`, `model_metrics`, `model_governance`,
`model_predictions`). Très bonne couverture de tests.

Principaux risques :

1. **Pickle des modèles tabulaires** : `lightgbm_model.pkl`, `catboost_model.pkl` sauvés
   en `pickle` au lieu de format natif (`booster.save_model()`) → fragilité aux upgrades
   de version + risque de désérialisation arbitraire si artefacts non maîtrisés.
2. **`model_metrics`, `model_governance`, `model_predictions` sont des résumés** : la
   richesse vit dans `metrics.json` disque. Si on perd `artifacts/models/` (ex: rebuild
   container), on perd la justification complète des champions.
3. **Pas de versioning fort des features** : `feature_columns` est dans `config.json`
   mais aucune CI ne vérifie qu'un nouveau code ne change pas les features sans
   ré-entraînement.
4. **Walk-forward optionnel** (`--walkforward`) : pas activé par défaut → risque de
   leak de validation sur split aléatoire si pas configuré explicitement.
5. **Sélection champion basée sur `selection_score`** (combinaison AUC val + business)
   → métrique composite à valider empiriquement (overfit possible sur la métrique
   elle-même).
6. **`predict_symbol` charge data + modèle à chaque appel** : performance batch OK pour
   100-200 symboles, mais pas optimisé pour 1000+.
7. **GPU forcé `effective_workers=1`** : conservateur, mais peut sous-utiliser un GPU
   capable de batcher plusieurs symboles.

Priorités immédiates :
- Migrer la persistance des challengers tabulaires vers les formats natifs
  (`booster.save_model('lgb.txt')`).
- Activer `--walkforward` par défaut en production.
- Ajouter un fingerprint de features (SHA256 de `feature_columns + ordre`) dans
  `config.json` pour détecter les divergences.

---

## 2. Constat détaillé

### 2.1 Orchestration `orchestrator.py`

| Item | Détail |
|---|---|
| Constat | `run_training_batch()` parallélise par symbole. `effective_workers=1` si GPU. Réinjection des routes `global_model` dans les artefacts symboles. |
| Force | Bonne séparation. Tolérance aux skips. |
| Risque | **Performance / scalabilité** : sur GPU, training séquentiel par symbole gaspille la capacité (batch multi-symbole pas exploitée). |
| Recommandation | Évaluer un `BatchSymbolDataModule` qui batch plusieurs symboles ensemble côté GPU. |

### 2.2 Entraînement `trainer.py`

| Item | Détail |
|---|---|
| Constat | 17 étapes documentées (cf. doc §6.3) : data → optim target → walk-forward → train LSTM → calibration → optim seuil → challengers → routes → champion → persist. |
| Force | Discipline impeccable, tout est tracé. |
| Risque | **Maintenabilité** : `train_symbol()` trop long (probablement >300 lignes). |
| Risque 2 | **Performance** : `min_history_days` non documenté chiffré (probable ~252 d). À valider que les skips `history_too_short` ne sont pas trop nombreux sur l'univers réel. |
| Recommandation | (a) Découper `train_symbol()` en sous-fonctions composables ; (b) exposer `min_history_days` en CLI ; (c) reporter dans `run_summary` la distribution des skips. |

### 2.3 Prédiction `predictor.py`

| Constat | Route via `_resolve_selected_model_route()` selon `config.json`. PIT-safe (`cutoff_date`). Recharge artefacts à chaque appel. |
| Risque | **Performance** : pour batch 200 symboles sur disque NTFS Windows, lecture pickle/ckpt = goulot. |
| Risque 2 | **Maintenabilité** : 4 chemins de backend (`lstm_attention`, `lightgbm_tabular`, `catboost_tabular`, `global_tabular`) → branches multiples, risque de dérive. |
| Recommandation | (a) Cache LRU des modèles chargés ; (b) refactor en `Strategy` pattern : un objet par backend avec interface `BackendPredictor`. |

### 2.4 Modèle `model.py` — `LSTMAttentionModule`

| Constat | Implémentation Lightning. |
| Risque | Pas de mention de la profondeur, du hidden_size, du dropout, de l'attention type → à vérifier dans le code. |
| Recommandation | Documenter les hyperparamètres défaut + leur justification empirique (ablation). |

### 2.5 Dataset `dataset.py` + `data_loader.py` + `features.py` + `cross_sectional.py`

| Constat | `SymbolDataModule`, scaling, séquences, features locales + cross-sectionnelles PIT-safe. `cross_sectional_min_universe` configurable. |
| Force | Bonne discipline PIT, paramètre `min_universe` évite le data leakage early-stage. |
| Risque | **Cohérence** : la liste des features est dispersée entre `features.py`, `cross_sectional.py`, `tabular_baseline.py`. Pas de fingerprint unique. |
| Recommandation | (a) `features.fingerprint(feature_set, include_sentiment, enable_cross_sectional) -> str` (SHA256) ; persisté dans `config.json` ; ré-entraînement obligé si fingerprint change ; (b) test que `features_v1` est strictement immuable. |

### 2.6 Challengers `lightgbm_baseline.py`, `catboost_baseline.py`

| Constat | Pickle pour persistance. Hyperparamètres CLI exposés. |
| Risque critique | **Format pickle** : (a) lié à la version exacte du paquet (LightGBM 4.x ne lit pas forcément un pickle 3.x) ; (b) désérialisation arbitraire = vecteur sécurité si artefacts viennent d'une source externe. |
| Recommandation | Migrer vers `booster.save_model('lgb.txt')` pour LightGBM (format texte stable) et `model.save_model('cb.cbm')` pour CatBoost. Conserver le scaler/calibrateur en pickle (acceptable car internes). |

### 2.7 Modèle global `global_model.py`

| Constat | Backend `lightgbm` ou `catboost`, dossier `__GLOBAL__`. |
| Risque | **Cohérence** : pas de garantie de cohérence des features entre symboles individuels et global → le fingerprint feature recommandé doit aussi inclure la dimension cross-sectionnelle. |
| Recommandation | Inclure un test "cohérence features local vs global". |

### 2.8 Gouvernance `champion_selection.py`

| Constat | Modes : `default_champion` / `fallback_default_champion` / `auto_selected_champion`. Métriques : `selection_score` (composite) / `business_score` / `auc`. |
| Risque | **Modèle / métrique** : `selection_score` composite peut être overfit. |
| Risque 2 | Pas de "période de quarantaine" : un nouveau champion devient servi immédiatement, sans validation production observée. |
| Recommandation | Ajouter un mode `--champion-min-out-of-sample-runs N` qui empêche un champion d'être servi avant N runs walk-forward consécutifs. |

### 2.9 Calibration `calibration.py`

| Constat | Platt uniquement. `--calibration-min-samples` configurable. |
| Risque | Platt = LR univariée → fragile si la distribution change. |
| Recommandation | Évaluer `IsotonicRegression` (sklearn) comme alternative. Exposer `--calibration-method none|platt|isotonic`. |

### 2.10 Évaluation `evaluation.py`, optim `target_optimization.py`

| Constat | Métriques classiques + business. `--optimize-target` / `--optimize-thresholds` exposés. |
| Risque | Optimisation conjointe target + seuil + calibration → **multiple comparison** problem (overfit). |
| Recommandation | Documenter la nested-CV utilisée (si présente), sinon ajouter une nested-CV par défaut quand walk-forward activé. |

### 2.11 Persistance `db_registry.py`

| Constat | Tables `model_training_run`, `model_metrics`, `model_governance`, `model_predictions`. Riches mais **résumées**. |
| Risque | Si `artifacts/` est perdu, la justification complète disparaît. |
| Recommandation | (a) Sauvegarder `metrics.json` complet en BLOB DB (`model_metrics_full BLOB`) au moins pour les champions ; (b) backup régulier `artifacts/models/` (script `scripts/backup_artifacts.ps1`). |

---

## 3. Risques prioritaires

### Critique
- Persistance challengers en `pickle` → fragilité version + sécurité.

### Élevé
- `model_metrics.json` non répliqué en DB → perte d'historique si artefacts perdus.
- Pas de fingerprint features → risque de divergence silencieuse.
- Walk-forward non activé par défaut → risque de validation optimiste.
- Champion immédiatement servi sans quarantaine.
- `train_symbol()` monolithique → maintenabilité.

### Modéré
- GPU sous-utilisé (séquentiel par symbole).
- Predictor recharge tout à chaque symbole (pas de cache).
- `selection_score` composite sans validation empirique.

### Faible
- Calibration Platt seule (alternative Isotonic disponible).

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Impact indirect : les features ML s'appuient sur `stock_bars_daily` (volume IEX
sous-évalué). Conséquence :

- les features `volume_*` (s'il y en a — features expert) sont biaisées de manière
  homogène cross-sectionnelle → ranking préservé ;
- les features `volatility_*` calculées sur `daily_return` ne sont pas affectées
  (returns OK) ;
- les features `liquidity_*` héritent du biais IEX → impact mineur si le modèle apprend
  à les pondérer empiriquement ;
- les features `cross_sectional` (rank percentile sur l'univers) sont robustes au biais
  d'échelle.

**Recommandation** : auditer les features dans `features.py` / `cross_sectional.py` →
identifier celles qui dépendent du *niveau absolu* de volume (problématiques) vs ratio /
rank (robustes).

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct (toutes les features sont calculées de manière relative).
Conservation `split_adjusted` recommandée et cohérente avec le reste du projet.

Note : `daily_return` est consommé tel quel — sain.

---

## 6. Quick wins

1. **Migrer LightGBM/CatBoost vers format natif** (`save_model`).
2. **Fingerprint features** SHA256 dans `config.json`.
3. **Activer `--walkforward` par défaut** en production (CLI `train`).
4. **`--calibration-method none|platt|isotonic`** étendu.
5. **Cache LRU des modèles chargés** dans `predictor.py`.
6. **Documenter `min_history_days`** + l'exposer CLI.
7. **Persister `metrics.json` en BLOB DB** pour les champions.
8. **Test "fingerprint features doit être stable"** (CI-bloquant).

## 7. Recommandations structurelles

1. **Découper `train_symbol`** en sous-fonctions testables (`_prepare_data`,
   `_train_lstm`, `_train_challengers`, `_select_champion`, `_persist`).
2. **Strategy pattern pour backends** : interface `BackendPredictor` avec 4
   implémentations (`LSTMBackend`, `LightGBMBackend`, `CatBoostBackend`, `GlobalBackend`).
3. **Quarantaine champion** : `--champion-min-runs N`, `--champion-min-days N`.
4. **Backup artefacts** automatisé (script + cron / Task Scheduler).
5. **Évaluation feature importance cross-modèle** : exposer `feature_importance.json`
   par symbole pour audit.
6. **Évaluer XGBoost** comme 3e challenger tabulaire (souvent compétitif sur volumes ML).

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 6, 8.
- Documentation : `metrics.json` schéma versionné.

### Moyen terme
- Quick wins 4, 5, 7.
- Découpage `train_symbol`.
- Backup artefacts.
- Quarantaine champion.

### Long terme
- Strategy pattern backends.
- BatchSymbolDataModule GPU.
- Évaluation XGBoost.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Excellente couverture (`tests/test_model_factory_*`). **Manque** :
  - test "fingerprint features stable".
  - test "champion quarantaine".
  - test "format natif LightGBM/CatBoost" round-trip.
  - test PIT au niveau predict (pas de leak).

### Monitoring
- DB et artefacts riches. **Manque** :
  - dashboard IHM "drift" : distribution des `predicted_proba` jour-à-jour.
  - alarm si > X % de symboles changent de champion d'un run train à l'autre.

### Documentation
- Excellente (`doc/modelFactory.md` 824 lignes). **Manque** :
  - section "comment migrer un format pickle vers natif".
  - section "que faire si on perd `artifacts/models/`".
  - section "comment ajouter un nouveau backend".

