# ML Hybride — Features Cross-Sectionnelles & Sectorielles

## 📌 Pourquoi ce changement ?

L'application `modelFactory` est une architecture **per-symbol** : un modèle indépendant (LSTM / LightGBM / CatBoost) est entraîné par titre. Le secteur GICS (Technology, Financials, Healthcare…) est une information disponible dans `stock_metadata` mais n'était **jamais injectée** dans les features ML.

Or, le comportement agrégé d'un secteur (momentum sectoriel, volatilité intra-secteur, alpha titre vs secteur) est une information **émergente** — elle n'existe pas au niveau du titre individuel et n'est pas redondante avec les features OHLCV. C'est la brique manquante de l'approche **hybride** utilisée par les fonds professionnels : modèle per-symbol enrichi de features cross-sectionnelles ET sectorielles.

Les tests précédents ont montré que :
- Les scores screener n'apportent rien car redondants avec les features OHLCV
- Les features cross-sectionnelles (rangs percentiles) améliorent les métriques
- La **dimension sectorielle** est complémentaire et indissociable du cross-sectional

**→ Refactor Sprint 2026-07** : fusion des flags `--enable-cross-sectional` et `--include-sector-features` en un seul. Activer le cross-sectional active automatiquement les features sectorielles (même raw_panel, coût marginal nul).

## 🎯 Avantages attendus

| Avantage | Détail |
|---|---|
| **Information non redondante** | Le momentum d'un secteur n'est pas déductible des seuls prix du titre |
| **Signal macro indirect** | Un secteur qui décroche = signal bear ; un secteur qui accélère = signal bull |
| **Aide à la classe `flat`** | Les titres sont souvent flat quand leur secteur est flat → meilleure calibration |
| **Coût minimal** | Les features sont calculées en O(n) sur le raw_panel déjà existant |
| **Un seul flag** | `--enable-cross-sectional` active tout : percentiles + secteur |

## 📁 État du code

### `modelFactory/cross_sectional.py`

- `SECTOR_FEATURE_COLUMNS` : 8 colonnes
  - `sector_ret_20`, `sector_ret_60` — momentum moyen du secteur
  - `sector_vol_20` — volatilité moyenne du secteur
  - `sector_relative_strength_20` — surperformance du secteur vs benchmark
  - `sector_dollar_volume_20` — liquidité agrégée du secteur
  - `sector_symbol_count` — nombre de titres dans le secteur à cette date
  - `stock_vs_sector_ret_20`, `stock_vs_sector_ret_60` — alpha du titre vs son secteur
- `_load_sector_mapping(engine)` → `dict[str, str]` : charge le mapping `symbol → sector` depuis `stock_metadata`
- `_compute_sector_features(raw_panel, sector_map)` : agrège par `(date, secteur)` puis réinjecte
- `build_cross_sectional_features_from_db()` : paramètre `sector_map` toujours fourni quand cross-sectional activé

### `modelFactory/config.py`

```python
enable_cross_sectional_features: bool = False  # percentiles + secteur (fusionné)
```
Le champ `include_sector_features` a été **supprimé** — le cross-sectional inclut désormais systématiquement les features sectorielles.

### `modelFactory/features.py`

- `get_feature_columns(include_cross_sectional=True)` → inclut automatiquement `CROSS_SECTIONAL_FEATURE_COLUMNS` + `SECTOR_FEATURE_COLUMNS`
- `fingerprint()`, `build_feature_contract()`, `validate_feature_contract()` : idem, un seul paramètre `include_cross_sectional`
- Le paramètre `include_sector_features` a été **supprimé** de toutes les signatures

### `modelFactory/cli.py`

```bash
--enable-cross-sectional    # Active rangs percentiles + features sectorielles
```
Le flag `--include-sector-features` a été **supprimé**. `--enable-cross-sectional` fait tout.

### `modelFactory/orchestrator.py`

- `_needs_cross_sectional = cfg.data.enable_cross_sectional_features` (plus de `or include_sector_features`)
- Le mapping sectoriel est **toujours** chargé quand cross-sectional est activé : `_load_sector_mapping(engine)`
- Passé systématiquement à `build_cross_sectional_features_from_db(sector_map=sector_map)`

### IHM

- **Un seul checkbox** : "🌐 Features cross-sectionnelles & sectorielles (rangs percentiles + momentum intra-secteur)"
- `pipeline_ml_enable_cross_sectional` → `True` active les deux
- `DEFAULT_ML_INCLUDE_SECTOR_FEATURES` supprimé de `pipeline_ml_defaults.py`
- `ml_include_sector_features` supprimé de `PipelineLaunchOptions`
- `--include-sector-features` n'est plus passé dans la commande

## 🚀 Comment activer ?

### Via CLI
```powershell
python -m modelFactory --mode train \
    --enable-cross-sectional \
    ...autres flags...
```

**Plus besoin** de `--include-sector-features` : un seul flag active tout.

### Via IHM
Cocher **"🌐 Features cross-sectionnelles & sectorielles"** dans les options ML du Pipeline.

### Vérification
Dans les logs, chercher :
```
run_training_batch sector features enabled: 487 symbols mapped to 11 sectors
```

## 🔬 Détails techniques

### Algorithme de calcul

1. **Chargement du mapping secteur** : `SELECT symbol, provider_sector FROM stock_metadata` — exécuté une seule fois par batch
2. **raw_panel** : déjà calculé par `build_cross_sectional_features_from_db` (rendements, volatilité, dollar volume par symbole et date)
3. **Agrégation sectorielle** : `raw_panel.groupby(["date", "sector"]).agg({"ret_20": "mean", ...})`
4. **Réinjection** : merge sur `(symbol, date)` → chaque titre reçoit les agrégats de son secteur
5. **Gestion des données manquantes** :
   - Secteurs avec < 3 titres → NaN → forward-fill → 0
   - Titres sans secteur → toutes les colonnes sectorielles à 0

### Performance

- **Coût** : ~0.5s supplémentaire pour 500 titres (l'agrégation par secteur est triviale)
- **Mémoire** : +8 colonnes float64 par ligne → négligeable
- **Pas de re-chargement** des barres : le raw_panel est réutilisé

## 📋 Fichiers modifiés

| Fichier | Changement |
|---|---|
| `modelFactory/cross_sectional.py` | +SECTOR_FEATURE_COLUMNS, +_load_sector_mapping, +_compute_sector_features |
| `modelFactory/config.py` | +enable_cross_sectional_features (inclut secteur), -include_sector_features |
| `modelFactory/features.py` | include_cross_sectional inclut automatiquement SECTOR_FEATURE_COLUMNS |
| `modelFactory/cli.py` | --enable-cross-sectional fait tout, --include-sector-features supprimé |
| `modelFactory/dataset.py` | propagation simplifiée |
| `modelFactory/trainer.py` | propagation simplifiée |
| `modelFactory/predictor.py` | propagation simplifiée |
| `modelFactory/orchestrator.py` | sector_map toujours chargé avec cross-sectional |
| `modelFactory/tabular_baseline.py` | propagation simplifiée |
| `modelFactory/global_model.py` | propagation simplifiée |
| `modelFactory/lstm_benchmark_adapter.py` | propagation simplifiée |
| `modelFactory/model_benchmark.py` | propagation simplifiée |
| `ihm/services/pipeline_ml_defaults.py` | -DEFAULT_ML_INCLUDE_SECTOR_FEATURES |
| `ihm/services/pipeline_runner.py` | -ml_include_sector_features, ---include-sector-features |
| `ihm/pages/_execution_center/__init__.py` | 1 checkbox fusionné "cross-sectional & sectoriel" |
