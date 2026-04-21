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

### Taille de chunk et sélection finale

```powershell
python -m selector.alpha_scanner --chunk-size 500 --selection-size 50
```

### Paramètres de filtrage personnalisés

```powershell
python -m selector.alpha_scanner --liquidity-threshold 20000000 --min-close 5 --max-anomaly-count 20 --sector-cap-ratio 0.30
```

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

### 4.2 Chargement et calcul des facteurs

Pour chaque chunk, le scanner charge :

- les prix depuis `stock_bars_daily`,
- les scores auxiliaires depuis `stock_scores`,
- les métadonnées instrument depuis `stock_metadata`.

Il calcule ensuite des facteurs comme :

- `trend_score`
- `vcp_score`
- moyennes mobiles 50 / 150 / 200 jours
- `high_52w` / `low_52w`
- `volatility_ratio`

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
