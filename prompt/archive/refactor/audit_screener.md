# Audit — `screener`

> Périmètre : `screener/stock_screener.py`, `screener/pipeline.py`, `screener/db_io.py`,
> `screener/models.py`.
> Sources : `doc/screener.md`, code listé, tests `tests/test_screener_*`, `tests/test_stock_screener.py`.

---

## 1. Résumé exécutif

`screener/` calcule les **scores quantitatifs de base** (liquidité, force relative vs SPY,
position dans le range historique) sur l'univers actions et alimente `stock_scores`.
Architecture en chunks parallèles (`ProcessPoolExecutor`), chargement en 2 passes
(récente bornée + historique réduit aux agrégats), `total_score` calculé en percentiles
cross-sectionnels (poids défaut : liquidité 15 %, RS 55 %, range 30 %).

État global : **module fonctionnel, bien testé, optimisé**. La passe 2 sur agrégats est
un bon choix de design pour la volumétrie 10 ans × ~5000 symboles. Tests nombreux.

Principaux risques :

1. **`liquidity_val` repose sur le volume IEX** sous-évalué → biais absolu présent, mais
   atténué par le passage au **percentile cross-sectionnel** dans `total_score`. Risque
   réel surtout pour les petits / mid caps illiquides où IEX peut renvoyer 0 sur certaines
   séances.
2. **`min_close_price = 5$` par défaut** très permissif (le selector durcit ensuite à 10$),
   incohérence implicite entre les deux modules.
3. **`ProcessPoolExecutor` partage des engines DB recréés par worker** → pas de pool
   global, plusieurs sessions concurrentes peuvent saturer MySQL si `max-workers` est
   élevé (8 par défaut configurable).
4. **`compute_scores_from_prices` dans un sous-process** → tout objet non picklable
   (lambda, connexion ouverte) crashe silencieusement le worker. À vérifier.
5. **`historical_range_score`** dépend de `MIN(low)`/`MAX(high)` sur 504 jours : sur des
   séries avec `is_filled` (forward-fill du sanitizer), les `low`/`high` artificiels
   égaux au close passent à travers — risque de sur-évaluer la position de range pour
   des titres dégradés.
6. **Pas de mode point-in-time exposé en CLI** : `as_of_date` est uniquement utilisable
   en code (backtest/backfill) → donc l'opérateur ne peut pas rejouer manuellement le
   screener sur une date précise sans passer par `backtesting.backfill-scores-history`.

Priorités immédiates :
- Documenter et instrumenter le biais IEX dans le résumé du run (`liquidity_iex_warning`
  si médiane volume × close < seuil).
- Aligner les défauts `min_close` entre screener (5$) et selector (10$).
- Exclure les jours `is_filled` du calcul `historical_range_score`.

---

## 2. Constat détaillé

### 2.1 `stock_screener.py` — orchestration

| Item | Détail |
|---|---|
| Constat | `ProcessPoolExecutor`, chunks de 500 symboles par défaut, `max_workers=8`. Émet `run_summary` avec `recent_rows_loaded`, `range_rows_loaded`, `pass1/2/upsert seconds`. |
| Risque | **Performance** : pas de mesure publiée du `wall_clock` total sur un univers complet 5000 symboles × 10 ans. Risque de dérive silencieuse. |
| Risque 2 | **Cohérence** : un chunk en erreur ne bloque pas les autres (correct), mais aucune métrique n'agrège le `chunk_error_count` dans le résumé. |
| Recommandation | (a) Exposer `chunk_failures` dans `run_summary` ; (b) test de charge documenté avec ordre de grandeur attendu sur la machine de référence. |

### 2.2 `pipeline.py` — calcul des scores

| Item | Détail |
|---|---|
| Constat | `compute_scores_from_prices()` produit `liquidity_val`, `relative_strength_index`, `historical_range_score`, `total_score`. `total_score` = combinaison pondérée de **percentiles cross-sectionnels** (15 / 55 / 30). |
| Force | Le passage en percentiles atténue le biais d'échelle entre facteurs. Bonne décision. |
| Risque | **Cohérence des données** : `historical_range_score = (close - low_504) / (high_504 - low_504)` n'est pas robuste aux outliers ; un seul `high` aberrant fausse le calcul. |
| Risque 2 | Les jours `is_filled` (forward-fill par le sanitizer, jusqu'à 3 consécutifs) entrent dans le calcul du range. Si plusieurs trous, `low_504` et `high_504` sont basés sur des prix de clôture répétés. |
| Risque 3 | La force relative est calculée vs SPY uniquement ; pas de configuration possible "vs sector ETF" qui serait métier-pertinente. |
| Recommandation | (a) Filtrer `WHERE is_filled = 0` quand on calcule `MIN(low)`/`MAX(high)` ; (b) winsoriser `historical_range_score` aux 1/99 percentiles ; (c) exposer benchmark configurable au niveau du `compute_scores_from_prices`. |

### 2.3 `db_io.py` — chargement

| Item | Détail |
|---|---|
| Constat | 2 passes : (1) fenêtre récente bornée par `first_pass_window_days` (≈400j) ; (2) agrégats historiques `MIN(low)/MAX(high)/MIN(date)/MAX(date)` pour les survivants. Très bon design. |
| Risque | **Performance / cohérence** : la passe 1 charge `recent_rows = symbols × 400` ; pour 5000 symboles, ~2M lignes via pandas → mémoire. Pas de streaming. |
| Risque 2 | Pas de chargement par `polars` malgré la présence de la dépendance dans `requirements.txt`. |
| Recommandation | (a) Évaluer le passage à `polars` pour le chargement de la passe 1 (vraisemblablement 3-5× plus rapide et moins gourmand en RAM) ; (b) ajouter un `LIMIT` de sécurité (ex. 10M lignes) avec exit warning si dépassé. |

### 2.4 `models.py` — `ScreenerConfig`

| Constat | Configuration immuable. Pas commentée en détail dans la doc. |
| Recommandation | Ajouter docstrings sur chaque champ + valeurs par défaut justifiées (pourquoi 504 jours, pourquoi 252 min_history, etc.). |

### 2.5 Couplage avec `selector` et incohérences de défauts

| Constat | Le screener filtre `min_close_price=5$`, le selector durcit ensuite à `min_close=10$` (profil strict). |
| Risque | **Maintenabilité** : deux sources de vérité pour des défauts qui devraient être alignés. |
| Recommandation | Centraliser dans `core/eligibility.py` ou `core/filter_profiles.py` avec usage partagé screener + selector. |

### 2.6 Mode point-in-time

| Constat | `run_screener(as_of_date=...)` existe en code. Pas exposé via CLI standard. |
| Risque | **Fiabilité du backtest** : le seul appel PIT passe par `backtesting.backfill-scores-history`, qui orchestre screener + selector + sentiment ensemble. Pas de moyen d'isoler un rerun screener seul. |
| Recommandation | Exposer `--as-of-date YYYY-MM-DD` en CLI (utile pour debug PIT). |

---

## 3. Risques prioritaires

### Critique
- Aucun.

### Élevé
- Biais IEX sur `liquidity_val` non instrumenté.
- Jours `is_filled` polluent `historical_range_score`.
- Défauts `min_close` désalignés avec selector.
- Performance non instrumentée à grande échelle (univers 10 ans).

### Modéré
- `compute_scores_from_prices` non test-friendly en sub-process (objets non picklables).
- Pas de fallback vers `polars` malgré la dépendance.
- Mode PIT non exposé CLI.

### Faible
- Benchmark codé pour SPY uniquement (par défaut, `--benchmark` existe).
- `max-workers` 0 = auto = `os.cpu_count()` peut sur-souscrire le CPU.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

`liquidity_val` = `mean(close * volume, 30j)`. Avec IEX :

- `volume` ≈ 2-3 % du consolidé → `liquidity_val` absolu sous-évalué d'un facteur ~30-50.
- Conséquence directe sur le seuil `liquidity_threshold_usd` : la valeur "métier" 20 M$
  doit être abaissée à ~600 K$ - 1 M$ pour rester équivalente, OU rester "20 M$ en
  équivalent IEX" qui correspond ≈ 1 Md$ de liquidité réelle (acceptable car le projet
  vise les large/mid caps swing).
- **Ranking percentile mitige le biais** : tant que tous les symboles sont mesurés sur
  la même base IEX, le ranking reste comparable.

**Cas pathologique** : un symbole à très faible flotte ou à listing récent peut avoir
des séances avec `volume = 0` côté IEX alors qu'il est tradable. `liquidity_val`
devient mécaniquement faible et le titre est exclu à tort.

### Recommandation
- Logger explicitement dans `run_summary` un compteur `symbols_zero_volume_30d` —
  alerte opérateur si > 5 % de l'univers.
- Documenter dans `doc/screener.md` la convention "20 M$ = équivalent IEX, environ
  1 Md$ consolidated".

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct sur le screener — `compute_scores_from_prices` consomme `close` et
`volume`, les deux sont split-adjusted dans la convention actuelle.

Note : `relative_strength_index` (vs SPY) n'est *pas* le RSI Wilder, mais une force
relative en ratio `(close_t / close_t-N) / (spy_close_t / spy_close_t-N)`. Le naming est
trompeur — voir documentation.

---

## 6. Quick wins

1. **Filtrer `is_filled = 0`** dans le calcul `historical_range_score` (one-liner SQL).
2. **Aligner les défauts `min_close`** avec le selector (10$ partout, ou centraliser).
3. **Exposer `--as-of-date` en CLI** pour debug PIT.
4. **Renommer `relative_strength_index`** → `relative_strength_ratio` (le RSI canonique
   est une autre indicateur).
5. **Ajouter `chunk_failures` et `symbols_zero_volume_30d`** dans `run_summary`.
6. **Docstrings sur `ScreenerConfig`** justifiant chaque défaut.
7. **Documenter la convention de seuil liquidité IEX** (`20 M$ ≈ 1 Md$ consolidated`).

## 7. Recommandations structurelles

1. **Migrer la passe 1 vers `polars`** pour gagner mémoire et CPU (dépendance déjà là).
2. **Centraliser `core/filter_profiles.py`** consommé par screener + selector + backtest.
3. **Ajouter une variante "sector relative strength"** (force relative vs ETF sectoriel)
   complémentaire au calcul vs SPY.
4. **Découpler `compute_scores_from_prices` du DB I/O** : actuellement `db_io.py` charge
   et `pipeline.py` calcule, mais l'orchestration cross-fichiers reste enchevêtrée.
5. **Test de charge documenté** : sur l'univers complet, mesurer `wall_clock` cible et
   alerter en CI/CD si régression > 30 %.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 5, 6, 7.
- Renommage `relative_strength_index` (avec rétrocompatibilité — alias colonne SQL).

### Moyen terme
- Centralisation `core/filter_profiles.py`.
- Migration `polars` pour la passe 1.
- Test de charge / benchmark publié.

### Long terme
- Variante sectorielle de la force relative.
- Refactor `pipeline` ↔ `db_io` plus pur.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Bons tests unitaires. **Manque** :
  - test sur séries avec `is_filled=1` (vérifier le bon comportement de
    `historical_range_score` après quick win 1).
  - test de non-régression sur le calcul `total_score` (fixtures déterministes).
  - test charge sur univers simulé large.

### Monitoring
- `run_summary` riche. **Manque** :
  - distribution des `total_score` (p10/p50/p90) pour suivre la dérive du scoring.

### Documentation
- `doc/screener.md` clair. **Manque** :
  - convention seuil liquidité IEX vs consolidated.
  - explication détaillée du calcul de `historical_range_score`.
  - tableau de mapping des poids défaut + justification.

