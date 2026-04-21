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

### Lancement direct avec le preset strict swing cash

```powershell
python -m selector.alpha_scanner --preset strict
```

Ce preset applique automatiquement le profil partagé `STRICT_SWING_CASH_FILTERS`, c'est-à-dire :

- `min_close = 10`
- `avg_dollar_volume_20d >= 30_000_000`
- `max_volatility_ratio = 0.90`
- `relative_strength_index >= 100`
- `latest_close > ma200`
- `latest_close / high_52w >= 0.75`
- `weekly_trend_score >= 1.0`
- `atr_pct_20` dans `[1.5 %, 6 %]`

Depuis l'IHM (`Pipeline`), le même comportement peut être activé via la case **`Alpha Scanner — activer le preset strict`** dans les paramètres d'exécution.

### Taille de chunk et sélection finale

```powershell
python -m selector.alpha_scanner --chunk-size 500 --selection-size 50
```

Le preset strict peut être combiné avec les autres paramètres usuels :

```powershell
python -m selector.alpha_scanner --preset strict --selection-size 100 --chunk-size 1000
```

### Paramètres de filtrage personnalisés

```powershell
python -m selector.alpha_scanner --liquidity-threshold 20000000 --min-close 5 --max-volatility-ratio 0.90 --max-anomaly-count 20 --sector-cap-ratio 0.30
```

Les seuils explicites passés en CLI gardent la priorité sur le preset. Exemple :

```powershell
python -m selector.alpha_scanner --preset strict --min-close 12 --max-volatility-ratio 0.80
```

Ici, le preset strict est chargé, puis `min_close` et `max_volatility_ratio` sont surchargés avec les valeurs explicites.

### Logs détaillés

```powershell
python -m selector.alpha_scanner --log-level DEBUG
```

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
- les métadonnées instrument depuis `stock_metadata`.

Il calcule ensuite des facteurs comme :

- `trend_score`
- `vcp_score`
- `atr_20` et `atr_pct_20`
- moyennes mobiles 50 / 150 / 200 jours
- structure weekly (`weekly_close`, `weekly_ma10`, `weekly_ma30`, `weekly_trend_score`)
- `high_52w` / `low_52w`
- `high_52w_proximity`
- `volatility_ratio`

Quand `--max-volatility-ratio` (ou `AlphaScannerConfig.max_volatility_ratio`) est renseigné, le scanner exclut ensuite les symboles dont `volatility_ratio > seuil`. Exemple d'usage swing strict petit compte :

- `min_close >= 10`
- `avg_dollar_volume_20d >= 30_000_000`
- `volatility_ratio <= 0.90`
- `relative_strength_index >= 100`
- `latest_close > ma200`
- `high_52w_proximity >= 0.75`
- `weekly_trend_score >= 1.0`
- `0.015 <= atr_pct_20 <= 0.06`

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
- drapeaux / colonnes de sélection finale

Les facteurs `atr_pct_20`, `weekly_trend_score` et `high_52w_proximity` sont aujourd'hui utilisés dans le pipeline de sélection en mémoire et dans le résultat retourné par `AlphaScanner`, mais ne sont pas persistés tels quels dans `stock_scores` par défaut.

---

## 5. Pourquoi peu de titres peuvent être retenus

### Causes probables

1. données daily insuffisantes ;
2. trop de symboles exclus au filtre instrument ;
3. anomalies ou jours manquants au-delà des seuils tolérés ;
4. liquidité réelle inférieure au seuil ;
5. cap sectoriel trop strict.

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

## 7. Tests

### Tests ciblés selector

```powershell
python -m pytest tests/test_selector_alpha_scanner.py tests/test_alpha_scanner.py tests/test_selector_init.py -q -o addopts=""
```

---

## 8. Recommandation pratique

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
