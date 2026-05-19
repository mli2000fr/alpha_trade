# Selector — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `selector/` et les commandes utiles pour :

- enrichir les scores du screener avec des facteurs avancés,
- appliquer un ranking type Minervini / VCP,
- neutraliser partiellement les biais sectoriels,
- sélectionner les meilleurs candidats finaux dans `stock_scores`.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `selector/__init__.py` | Package Python |
| `selector/alpha_scanner.py` | Scanner multi-facteurs principal |

Le module `selector/` est volontairement compact : l'essentiel de la logique est concentré dans `AlphaScanner`.
Les seuils stricts réutilisés par les reruns swing cash sont centralisés dans `selector/strict_filter_profiles.py` pour éviter toute divergence entre scanner, backfill et backtest PIT.

---

## 2. Prérequis

### 2.1 Tables et données requises

#### Obligatoires

- `stock_bars_daily`
- `stock_scores`
- `stock_metadata`

#### Recommandées

- données daily suffisamment longues pour calculer MA50 / MA150 / MA200 et range 52 semaines
- `stock_scores` pré-alimentée par `screener`
- `stock_quote_snapshots` pour alimenter le filtre de spread bid/ask
- `stock_earnings_calendar` pour alimenter le blackout résultats

Depuis l'IHM Streamlit, le workflow complet déclenche automatiquement `sync_latest_quotes` puis `sync_earnings_calendar` juste avant `Alpha Scanner`, de sorte que ces tables soient rafraîchies avant le scan live/opérationnel.

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

---

## 3. Commandes utiles

### Lancement standard

```powershell
python -m selector.alpha_scanner
```

Le lancement standard applique désormais automatiquement le profil partagé `STRICT_SWING_CASH_FILTERS`, c'est-à-dire :

- `min_close = 10`
- `avg_dollar_volume_20d >= 30_000_000`
- `max_volatility_ratio = 0.90`
- `relative_strength_index >= 100`
- `latest_close > ma200`
- `latest_close / high_52w >= 0.75`
- `weekly_trend_score >= 1.0`
- `atr_pct_20` dans `[1.5 %, 6 %]`
- `market_cap >= 2 Md$`
- `beta_126 >= 0.8`
- `spread_bps <= 40`
- relâchement IEX possible jusqu’à `65 bps` si `bid_size` / `ask_size >= 100`
- TTL `market_cap_refreshed_at <= 45 jours` (mode par défaut : `warn_skip_filter` si la fraîcheur n’est pas exploitable)
- exclusion si `earnings_date` tombe dans les `3` prochains jours

L'option legacy `--preset strict` reste tolérée comme alias de compatibilité, mais n'est plus nécessaire.

### Taille de chunk et sélection finale

```powershell
python -m selector.alpha_scanner --chunk-size 500 --selection-size 50
```

Le mode strict implicite peut être combiné avec les autres paramètres usuels :

```powershell
python -m selector.alpha_scanner --selection-size 100 --chunk-size 1000
```

### Paramètres de filtrage personnalisés

```powershell
python -m selector.alpha_scanner --liquidity-threshold 20000000 --min-close 5 --max-volatility-ratio 0.90 --max-anomaly-count 20 --sector-cap-ratio 0.30
```

Les seuils explicites passés en CLI gardent la priorité sur le profil strict implicite. Exemple :

```powershell
python -m selector.alpha_scanner --min-close 12 --max-volatility-ratio 0.80 --max-spread-bps 20
```

Ici, le profil strict est chargé, puis `min_close`, `max_volatility_ratio` et `max_spread_bps` sont surchargés avec les valeurs explicites.

### Logs détaillés

```powershell
python -m selector.alpha_scanner --log-level DEBUG
```

### Correspondance avec l'IHM

Depuis `ihm/pages/pipeline.py`, l'étape `6. alpha_scanner` du workflow quotidien 1→14 lance bien :

```powershell
python -m selector.alpha_scanner ...
```

L'IHM expose désormais les options CLI réellement supportées par ce point d'entrée :

- `chunk-size`
- `selection-size`
- `max-workers`
- `liquidity-threshold`
- `min-close`
- `max-volatility-ratio`
- `min-relative-strength-index`
- `min-high-52w-proximity`
- `min-weekly-trend-score`
- `min-atr-pct-20`
- `max-atr-pct-20`
- `min-market-cap`
- `min-beta-126`
- `max-spread-bps`
- `spread-data-quality-mode`
- `earnings-blackout-days`
- `earnings-data-quality-mode`
- `market-cap-data-quality-mode`
- `ablation-mode`
- `ablation-config`
- `max-anomaly-count`
- `sector-cap-ratio`
- `log-level`

Points importants :

- `0` sur `max workers` dans l'IHM signifie **auto** ;
- le profil partagé `STRICT_SWING_CASH_FILTERS` reste appliqué implicitement côté backend ;
- les valeurs affichées dans l'IHM sont transmises explicitement à la commande pour reproductibilité et audit des runs.

---

## 4. Ce que fait le module

### 4.1 Préselection SQL

`AlphaScanner` commence par présélectionner des symboles éligibles selon :

- historique minimal,
- prix minimal,
- liquidité minimale,
- statut actif / tradable,
- univers actions US.

Le filtre de **volatilité relative** n'est volontairement pas traité ici : il nécessite le calcul des fenêtres roulantes `vol_10` / `vol_60` et donc intervient plus loin, dans `apply_filters()`.

### 4.2 Chargement et calcul des facteurs

Pour chaque chunk, le scanner charge :

- les prix depuis `stock_bars_daily`,
- les scores auxiliaires depuis `stock_scores`,
- les métadonnées instrument depuis `stock_metadata`,
- le dernier snapshot de spread depuis `stock_quote_snapshots`,
- la prochaine date de résultats depuis `stock_earnings_calendar`.

Dans le workflow complet IHM, ces deux tables de référence sont maintenant alimentées automatiquement par les étapes `Sync Latest Quotes` et `Sync Earnings Calendar` avant le lancement de `Alpha Scanner`.

Il calcule ensuite des facteurs comme :

- `trend_score`
- `vcp_score`
- `atr_20` et `atr_pct_20`
- `beta_126` vs `SPY`
- moyennes mobiles 50 / 150 / 200 jours
- structure weekly (`weekly_close`, `weekly_ma10`, `weekly_ma30`, `weekly_trend_score`)
- `high_52w` / `low_52w`
- `high_52w_proximity`
- `volatility_ratio`
- `market_cap`
- `spread_bps`
- `earnings_date`, `days_to_earnings`, `earnings_blackout`

Quand `--max-volatility-ratio` (ou `AlphaScannerConfig.max_volatility_ratio`) est renseigné, le scanner exclut ensuite les symboles dont `volatility_ratio > seuil`. Exemple d'usage swing strict petit compte :

- `min_close >= 10`
- `avg_dollar_volume_20d >= 30_000_000`
- `volatility_ratio <= 0.90`
- `relative_strength_index >= 100`
- `latest_close > ma200`
- `high_52w_proximity >= 0.75`
- `weekly_trend_score >= 1.0`
- `0.015 <= atr_pct_20 <= 0.06`
- `market_cap >= 2_000_000_000`
- `beta_126 >= 1.0`
- `spread_bps <= 25`
- `earnings_blackout = 0`

Pour éviter la duplication, cet exemple correspond désormais au profil partagé `STRICT_SWING_CASH_FILTERS`, consommé via `AlphaScannerConfig.strict_swing_cash()` dans les flows stricts.

### 4.3 Composition du score final

Le score final repose sur trois familles de composantes configurables :

- moyenne `trend_score` + `vcp_score`
- `total_score` issu du screener
- composante force relative

La classe expose des poids configurables :

- `weight_trend_vcp`
- `weight_total_score`
- `weight_rsi`

### 4.4 Neutralisation sectorielle

Si `neutralize_by_sector=True`, une partie du score est neutralisée intra-secteur pour éviter une surreprésentation mécanique d'un seul segment de marché.

### 4.5 Persistance

Le module met à jour `stock_scores` avec les colonnes avancées comme :

- `trend_score`
- `vcp_score`
- `final_score`
- `sector`
- `market_cap`
- `beta_126`
- `spread_bps`
- `earnings_date`
- `days_to_earnings`
- `earnings_blackout`
- `candidate_rank`
- `raw_final_score`
- `normalized_total_score`
- `normalized_rsi`
- `total_score_neutralized`
- `relative_strength_index_neutralized`
- `trend_vcp_component`
- `total_score_component`
- `rsi_component`
- `atr_pct_20`
- `weekly_trend_score`
- `high_52w_proximity`
- `volatility_ratio`
- `selector_signal_mode`
- `selection_explanation`
- drapeaux / colonnes de sélection finale

Le `run_summary` persiste aussi désormais :

- `top_candidate_explanations`
- `preselection_rejections`
- `data_quality_gate`
- `skipped_filters`
- `ablation`

L’IHM peut donc relire à la fois :

- l’explicabilité des candidats retenus ;
- les raisons principales des rejets de pré-sélection SQL ;
- les filtres désactivés dynamiquement via fallback data-quality.
- les variantes shadow d’ablation comparées au primaire, avec overlap et chemins d’artefacts JSON.

---

## 5. Pourquoi peu de titres peuvent être retenus

### Causes probables

1. données daily insuffisantes ;
2. trop de symboles exclus au filtre instrument ;
3. anomalies ou jours manquants au-delà des seuils tolérés ;
4. liquidité réelle inférieure au seuil ;
5. cap sectoriel trop strict.

Le point d'entrée CLI émet aussi un `run_summary` structuré sur stdout avec le préfixe :

- `::alpha_trade_run_summary::`

Champs notables :

- `requested_selection_size`
- `selected_candidates`
- `selected_sectors`
- `selection_fill_ratio`
- `workers`
- `sector_cap_ratio`
- `sector_breakdown`
- `top_symbols`
- `max_final_score`
- `avg_final_score`

Ces résumés sont consommés côté IHM pour enrichir le centre d'exécution, `Overview` et `Screening`.

---

## 6. Vérifications utiles

### Vérifier les meilleurs scores finaux

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, sector, trend_score, vcp_score, final_score, is_candidate FROM stock_scores ORDER BY final_score DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier le nombre de candidats finaux

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    row = conn.execute(text("SELECT COUNT(*) AS n FROM stock_scores WHERE is_candidate = 1")).mappings().one();
    print(dict(row))'
```

---

## 7. Mode d’ablation / A-B des filtres

Le selector supporte maintenant un mode **shadow** d’ablation pour comparer proprement des variantes de filtres/profils sans casser la persistance live.

### 7.1 Principes

- le **primaire** reste le run métier de référence ;
- seules les sorties du primaire sont persistées dans `stock_scores` / `stock_scores_history` ;
- les variantes d’ablation sont exécutées **en shadow** sur le même univers présélectionné et les mêmes chunks préparés ;
- chaque variante produit un résumé compact dans `run_summary["ablation"]` ;
- un artefact JSON détaillé est écrit dans `artifacts/selector/ablation/` (ou dans le dossier configuré).

Conséquence importante : on obtient un vrai A/B de filtres/profils, mais **sans multiplier les écritures DB** ni perturber le contrat aval de `risk_management`.

### 7.2 Activation CLI

```powershell
python -m selector.alpha_scanner --ablation-mode shadow --ablation-config .\selector_ablation.json
```

### 7.3 Exemple de fichier JSON/YAML

```json
{
  "mode": "shadow",
  "artifact_dir": "artifacts/selector/ablation",
  "variants": [
    {
      "variant_id": "no_spread",
      "disabled_filters": ["spread"]
    },
    {
      "variant_id": "looser_rsi",
      "config_overrides": {
        "min_relative_strength_index": 95.0
      }
    }
  ]
}
```

### 7.4 Filtres désactivables nativement

Les clés `disabled_filters` supportées sont actuellement :

- `volatility`
- `atr`
- `relative_strength`
- `ma200`
- `high_52w`
- `weekly_trend`
- `market_cap`
- `market_cap_ttl`
- `beta`
- `spread`
- `earnings_blackout`

### 7.5 Overrides supportés

Les variantes peuvent aussi ajuster certains seuils via `config_overrides`, notamment :

- `selection_size`
- les seuils de filtres (`max_volatility_ratio`, `min_relative_strength_index`, `min_high_52w_proximity`, `min_weekly_trend_score`, `min_atr_pct_20`, `max_atr_pct_20`, `min_market_cap`, `min_beta_126`, `max_spread_bps`, `max_spread_bps_iex`, `min_quote_size`, `market_cap_max_age_days`, `earnings_blackout_days`)
- `require_above_ma200`
- `max_anomaly_count`, `max_missing_days_count`
- `sector_cap_ratio`, `neutralize_by_sector`
- les poids de score (`weight_trend_vcp`, `weight_total_score`, `weight_rsi`)

### 7.6 Contrat d’observabilité

Le bloc `run_summary["ablation"]` expose typiquement :

- `mode`
- `variant_count`
- `artifact_path`
- `primary`
- `variants[]` avec pour chaque variante :
  - `variant_id`
  - `disabled_filters`
  - `skipped_filters`
  - `config_diff`
  - `selected_candidates`
  - `top_symbols`
  - `overlap_with_primary`
  - `selection_diff`
  - `rejected_by_filter`

L’IHM `run_summary` affiche ensuite :

- le nombre de variantes shadow ;
- le chemin de l’artefact ;
- les principaux ajouts/retraits vs primaire ;
- l’overlap avec la sélection de référence.

### 7.7 Interaction avec le data quality gate

Le `data_quality_gate` du primaire reste **autoritaire** :

- si un filtre est désactivé par fallback data-quality sur le primaire, une variante shadow ne peut pas le réactiver ;
- cela évite de comparer des variantes sur une source explicitement jugée non exploitable.

---

## 8. Tests

### Tests ciblés selector

```powershell
python -m pytest tests/test_selector_alpha_scanner.py tests/test_alpha_scanner.py tests/test_selector_init.py tests/test_selector_run_summaries.py -q -o addopts=""
```

---

## 9. Recommandation pratique

Ordre conseillé :

1. lancer `screener` ;
2. lancer `selector` ;
3. vérifier la distribution sectorielle et le nombre de candidats ;
4. enchaîner ensuite vers `event_sentiment` puis `risk_management`.

### Séquence recommandée

```powershell
python -m screener.stock_screener
python -m selector.alpha_scanner --selection-size 100
```

---

## 10. Workflow standard — ajout d’un nouveau filtre

Checklist recommandée :

1. **Configuration**
   - ajouter le seuil / mode dans `selector/config.py` ;
   - si le filtre appartient au preset partagé, propager aussi via `core/filter_profiles.py`.
2. **Données d’entrée**
   - décider si le filtre vit en pré-sélection SQL, en filtrage pandas, ou dans un overlay optionnel (`quotes`, `earnings`, `metadata`) ;
   - si la source est externe et fragile, ajouter/étendre le check dans `selector/db_io.py::build_data_quality_gate()`.
3. **Filtrage métier**
   - implémenter la logique dans `selector/filters.py` ;
   - incrémenter un compteur dédié `rejected_<nom_du_filtre>` dans `apply_filters_with_stats()`.
4. **Observabilité**
   - exposer le nouveau compteur dans `_summarize_zero_candidate_filters()` si le filtre peut devenir un goulot d’étranglement ;
   - compléter le `run_summary` si le filtre produit un contexte spécifique (payload, fallback, samples, etc.).
5. **Persistance / IHM**
   - si le filtre génère une donnée utile au post-mortem, la persister via `selector/ranking.py` / `selector/db_io.py` ;
   - ajouter l’exposition IHM nécessaire dans `ihm/services/run_summary.py` ou `ihm/pages/screening.py`.
6. **Tests**
   - ajouter au minimum :
     - un test config/CLI,
     - un test unitaire de filtre,
     - un test run_summary/observabilité,
     - un test d’intégration scanner si le filtre dépend d’une source SQL.
7. **Validation finale**
   - lancer Ruff sur le périmètre modifié ;
   - relancer les tests selector + IHM touchés ;
   - mettre à jour `prompt/refactor_selector.md` et cette doc si le contrat change.

