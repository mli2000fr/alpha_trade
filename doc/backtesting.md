# Backtesting & Backfill — Guide d'usage

## Objectif

Ce document résume l'intégration du module `backtesting/` et les commandes utiles pour :

- lancer un backtest journalier cohérent avec exécution au prochain `open`,
- reconstruire l'historique de `stock_scores_history`,
- comprendre pourquoi un backtest peut produire `0 trade`,
- exécuter un vrai backtest exploitable sur une période longue.

---

## 1. Ce qui a été ajouté

### Fichiers créés

| Fichier | Rôle |
|---|---|
| `backtesting/__init__.py` | Package Python |
| `backtesting/__main__.py` | Point d'entrée `python -m backtesting` |
| `backtesting/cli.py` | CLI argparse : parsing, orchestration |
| `backtesting/data_loader.py` | Chargement OHLCV, scores, sentiment, prédictions ML |
| `backtesting/signal_replay.py` | Reconstruction des signaux de conviction jour par jour |
| `backtesting/simulator.py` | Moteur de backtest journalier avec TP + trailing stop |
| `backtesting/trading_constraints.py` | Contraintes de compte composables : `account_type`, `pdt_rule`, `swing_only` |
| `backtesting/report.py` | Rapport : Sharpe, Sortino, CAGR, drawdown, win rate, profit factor |
| `backtesting/backfill_scores_history.py` | Backfill point-in-time de `stock_scores_history` |
| `tests/test_backtesting.py` | Tests unitaires backtesting |
| `tests/test_backfill_scores_history.py` | Tests du backfill historique |

### Fichiers modifiés

- `requirements.txt` → ajout `vectorbt`, `plotly`, `kaleido`, `matplotlib`
- `pyproject.toml` → ajout dépendances + `backtesting*` dans les packages
- `DOC_FONCTIONNELLE.md` → backtesting marqué implémenté
- `DOC_TECHNIQUE.md` → doc module + commandes de backtest et backfill

---

## 2. Prérequis

Les tables réellement nécessaires ne sont pas les mêmes selon l'usage.

### 2.1 Pour le backfill de `stock_scores_history`

#### Obligatoires

- `stock_bars_daily`
- `stock_metadata`

#### Optionnelles mais recommandées

- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

Si les tables sentiment ne sont pas présentes, le backfill fonctionne quand même,
mais la composante sentiment est neutralisée / dégradée vers un comportement plus quantitatif.

#### Non nécessaires

- `model_predictions`

Le backfill de `stock_scores_history` n'utilise pas `model_predictions`.

### 2.2 Pour lancer un backtest

#### Obligatoires

- `stock_bars_daily`
- `stock_scores_history` (ou à défaut `stock_scores`, mais ce n'est pas un vrai backtest PIT)

#### Optionnelles mais utiles

- `model_predictions`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

Le code est tolérant :

- si `model_predictions` est absente ou trop courte, le backtest continue sans composante ML ;
- si les tables sentiment sont absentes ou incomplètes, le backtest continue avec un signal sentiment neutre / réduit ;
- plus ces tables sont riches historiquement, plus le backtest se rapproche du pipeline production complet.

### 2.3 Modes `ML` et `sentiment`

Le backtest supporte désormais trois politiques explicites pour le ML et le sentiment.

#### `--ml-mode`

- `auto` : utilise les prédictions disponibles ; si certaines manquent, le backtest continue sans ML pour ces lignes ;
- `off` : ignore complètement `model_predictions` ;
- `rebuild-missing` : tente de reconstruire les prédictions manquantes via les artefacts modèles, en mode point-in-time.

#### `--sentiment-mode`

- `auto` : utilise `final_score_sentiment` si présent, sinon fallback sur `final_score` ;
- `off` : désactive complètement le boost sentiment (`final_score_sentiment = final_score`) ;
- `rebuild-missing` : tente de reconstruire les snapshots sentiment manquants dans `stock_scores_history`, puis fallback sur `final_score` pour les lignes restant incomplètes.

#### Remarques pratiques

- `rebuild-missing` est plus fidèle mais plus coûteux en temps ;
- `--ml-mode rebuild-missing` nécessite les checkpoints/scalers/configs modèles dans `artifacts/models/` ;
- `--sentiment-mode rebuild-missing` peut reconstruire les snapshots PIT quand c'est possible, sinon retombe sur un signal neutre/réduit.

### 2.4 Ce qu'il faut idéalement pour un backtest "research-grade"

Pour un backtest 10 ans vraiment fidèle au pipeline cible, il faudrait idéalement :

- 10 ans de `stock_bars_daily`
- 10 ans de `stock_scores_history`
- 365 jours glissants (ou plus) de `ticker_daily_sentiment_features`
- 365 jours glissants (ou plus) de `sector_daily_sentiment_features`
- un historique aussi long que possible de `model_predictions`

Mais en pratique :

- **les bars + l'historique des snapshots de scores sont le socle indispensable** ;
- **les prédictions ML et le sentiment améliorent la fidélité**, mais ne bloquent pas l'exécution du moteur.

Variables d'environnement minimales :

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

---

## 3. Lancer un backtest

### Backtest complet

```powershell
python -m backtesting run --start 2016-01-01 --end 2026-04-20 --equity 100000
```

### Backtest personnalisé

```powershell
python -m backtesting run --start 2020-01-01 --end 2026-04-20 --equity 50000 --tp 0.10 --ts 0.04 --max-positions 15
```

### Contraintes de compte petit capital / PDT

Le backtest expose désormais une API plus propre pour simuler les contraintes de compte :

- `--account-type margin|cash`
- `--pdt-rule auto|off`
- `--swing-only`

Cette séparation permet de distinguer :

- le **type de compte** (`margin` vs `cash`) ;
- la **règle réglementaire PDT** (`auto` vs `off`) ;
- le **style de trading** (`--swing-only`).

Comportements principaux :

- `--account-type margin --pdt-rule auto` : applique la règle PDT si l'equity initiale est `< 25 000 $` ;
- `--account-type margin --pdt-rule off` : baseline non contraint côté PDT ;
- `--swing-only` : interdit toute sortie le jour même de l'entrée, sans modifier le prix d'entrée ;
- `--account-type cash` : désactive de facto la règle PDT et n'autorise que le cash settled, avec settlement simplifié en `T+1`.

Convention d'exécution du moteur :

- le signal est daté en `J` ;
- l'entrée est exécutée au **vrai `open` de la séance suivante (`J+1`)** ;
- les TP / trailing stops sont évalués à partir de cette séance d'exécution ;
- `--swing-only` bloque uniquement les sorties same-day sur cette séance d'entrée.

Combinaisons utiles :

- `margin + auto + no swing` : simulation la plus proche d'un petit compte margin soumis à PDT ;
- `margin + off + swing_only` : swing strict sans règle PDT ;
- `cash + off + swing_only` : petit compte cash conservateur ;
- `cash + off + no swing` : cash account sans PDT, mais avec réutilisation différée du capital après vente.

Exemples :

```powershell
# Compte < 25k avec règle PDT : max 3 day trades / 5 séances
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type margin --pdt-rule auto

# Mode swing strict : jamais de revente le jour même
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type margin --pdt-rule off --swing-only

# Cash account : pas de PDT, mais réutilisation du capital seulement après settlement T+1
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type cash

# Cash + swing : combine cash settled T+1 et interdiction des sorties same-day
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type cash --swing-only
```

Remarques pratiques :

- `--account-type cash` neutralise la règle PDT, même si `--pdt-rule auto` est laissé par défaut ;
- `--swing-only` correspond bien à l'idée « signal aujourd'hui, achat à la prochaine ouverture, vente le lendemain ou plus tard ».

### Sans sauvegarde des artefacts

```powershell
python -m backtesting run --start 2023-01-01 --no-save
```

### Modes de résilience ML / sentiment

```powershell
# Désactiver complètement ML et sentiment
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode off --sentiment-mode off

# Mode tolérant (défaut)
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode auto --sentiment-mode auto

# Reconstruction des prédictions ML manquantes
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode rebuild-missing --artifacts-dir artifacts/models

# Reconstruction des snapshots sentiment manquants
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --sentiment-mode rebuild-missing

# Reconstruction des prédictions ML manquantes ET des snapshots sentiment manquants en même temps
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode rebuild-missing --sentiment-mode rebuild-missing --artifacts-dir artifacts/models
```

### Artefacts générés

Dans `artifacts/backtesting/` :

- `equity_curve.png` — courbe de valeur du portefeuille
- `trades.csv` — liste détaillée des trades
- `report.json` — résumé structuré incluant désormais les diagnostics de contraintes (`blocked_pdt_day_trades`, `blocked_same_day_exits`, `blocked_cash_entries`, `executed_day_trades`)

---

## 4. Pourquoi un backtest peut afficher `0 trade`

Si le rapport affiche :

- `Nombre de trades = 0`
- `Valeur finale = capital initial`
- `Rendement total = 0%`

alors les causes les plus probables sont :

1. `stock_scores_history` ne contient pas encore d'historique quotidien exploitable ;
2. il n'existe qu'un snapshot unique ;
3. ce snapshot tombe un jour non tradé ;
4. les signaux sont donc reconstruits sur une seule date non exécutable.

### Exemple observé

Dans la base actuelle, on a constaté :

- `stock_scores_history` initialement rempli seulement au `2026-04-19`
- `stock_bars_daily` disponible jusqu'au `2026-04-17`

Résultat :
- le backtest trouvait des candidats,
- mais aucune entrée n'était réellement exécutable,
- donc `0 trade`.

---

## 5. Backfill de `stock_scores_history`

Le module ajouté permet maintenant de reconstruire l'historique PIT (point-in-time) de `stock_scores_history` directement depuis les bars et les features sentiment déjà en base.

### Ce que fait le backfill

Pour chaque séance de trading manquante :

1. recalcule le screener à date,
2. recalcule le selector / AlphaScanner à date,
3. applique la fusion sentiment,
4. insère un snapshot complet dans `stock_scores_history`.

Important :

- le backfill **n'écrit pas** dans `stock_scores` courant ;
- il **saute automatiquement** les dates déjà historisées ;
- il peut **recalculer** avec `--overwrite-existing`.

---

## 6. Commandes de backfill

### Test rapide sur 1 séance

```powershell
python -m backtesting backfill-scores-history --start 2026-04-17 --limit-days 1 --screener-workers 1
```

### Backfill automatique depuis une date de départ

Cette commande reconstruit les séances manquantes depuis `--start` jusqu'à la dernière séance disponible avant le premier snapshot déjà présent dans `stock_scores_history`.

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 1
```

### Backfill avec borne explicite

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --end 2026-04-16 --screener-workers 1
```

### Recalcul forcé d'une journée déjà historisée

```powershell
python -m backtesting backfill-scores-history --start 2026-04-17 --end 2026-04-17 --overwrite-existing --screener-workers 1
```

### Validation progressive

Commencer petit :

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --limit-days 1 --screener-workers 1
python -m backtesting backfill-scores-history --start 2025-01-01 --limit-days 5 --screener-workers 1
```

Puis lancer le backfill complet.

---

## 7. Commande recommandée pour ton cas

Comme `2026-04-17` est désormais historisé, la commande suivante reconstruira automatiquement de `2025-01-01` jusqu'à `2026-04-16` :

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 2
```

Variante stricte avec borne explicite :

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --end 2026-04-16 --screener-workers 2
```

---

## 8. Après le backfill : lancer un vrai backtest utile

Une fois `stock_scores_history` correctement rempli :

```powershell
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000
```

### Commande si tu veux reconstruire ML + sentiment en même temps

```powershell
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode rebuild-missing --sentiment-mode rebuild-missing --artifacts-dir artifacts/models
```

Cette commande :

- tente de reconstruire les `model_predictions` manquantes à partir des artefacts de `artifacts/models/` ;
- tente de reconstruire les snapshots sentiment manquants dans `stock_scores_history` ;
- continue quand même avec fallback si certaines données restent indisponibles.

Exemple robuste sans dépendre d'un historique ML complet :

```powershell
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode off --sentiment-mode auto
```

Exemple avec reconstruction automatique des données manquantes :

```powershell
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode rebuild-missing --sentiment-mode rebuild-missing --artifacts-dir artifacts/models
```

Exemple optimal pour une période cible :

```powershell
python -m backtesting run --start 2025-04-21 --end 2026-04-20 --equity 100000 --ml-mode off --sentiment-mode auto
python -u -m backtesting backfill-scores-history --start 2025-04-21 --end 2026-04-16 --screener-workers 4 --chunk-size 2000
```

---

## 9. Vérifications utiles en base

### Vérifier la plage de `stock_scores_history`

```powershell
python - <<'PY'
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

engine = get_sqlalchemy_engine()
with engine.connect() as conn:
    row = conn.execute(text("""
        SELECT COUNT(*) AS n,
               MIN(snapshot_date) AS dmin,
               MAX(snapshot_date) AS dmax
        FROM stock_scores_history
    """)).mappings().one()
    print(dict(row))
PY
```

### Vérifier un snapshot précis

```powershell
python - <<'PY'
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

engine = get_sqlalchemy_engine()
with engine.connect() as conn:
    row = conn.execute(text("""
        SELECT snapshot_date,
               COUNT(*) AS n,
               SUM(CASE WHEN is_candidate = 1 THEN 1 ELSE 0 END) AS candidates
        FROM stock_scores_history
        WHERE snapshot_date = :d
        GROUP BY snapshot_date
    """), {"d": "2026-04-17"}).mappings().one()
    print(dict(row))
PY
```

---

## 10. Tests

### Tests ciblés backtesting + backfill

```powershell
python -m pytest tests/test_backtesting.py tests/test_backfill_scores_history.py -q -o addopts=""
```

Les tests backtesting couvrent désormais aussi :

- le blocage du 4e day trade avec `account_type=margin` et `pdt_rule=auto` ;
- l'interdiction de sortie le jour même avec `--swing-only` ;
- la consommation de cash settled uniquement avec `account_type=cash`.

---

## 11. Diagnostic screener phase 4 + recommandation phase 5

Le diagnostic screener exporte maintenant non seulement les artefacts PIT :

- `daily_metrics.csv`
- `summary_metrics.csv`
- `scenarios.csv`
- `metadata.json`

mais aussi les artefacts d'analyse phase 5 :

- `scenario_recommendations.csv`
- `recommendation_summary.json`

### Lancer un diagnostic avec recommandation automatique

```powershell
python -m backtesting diagnose-screener --start 2024-01-01 --end 2024-12-31 --mode oat --limit-days 60
```

À la fin du run, la CLI affiche désormais :

- le **meilleur compromis** automatique ;
- ses scores de **robustesse / survie / qualité forward** ;
- un aperçu du classement `scenario_recommendations.csv`.

### Réanalyser un `summary_metrics.csv` existant

```powershell
python -m backtesting recommend-screener --input-dir artifacts/screener_diagnostics
```

Variante avec chemins explicites :

```powershell
python -m backtesting recommend-screener \
  --summary-csv artifacts/screener_diagnostics/summary_metrics.csv \
  --daily-csv artifacts/screener_diagnostics/daily_metrics.csv \
  --target-horizon 20
```

### Comment le classement phase 5 est calculé

Le classement automatique s'appuie sur trois piliers :

1. **Robustesse**
   - taux de succès du scénario (`days_failed` vs `days_evaluated`) ;
   - couverture forward disponible ;
   - stabilité journalière quand `daily_metrics.csv` est présent.

2. **Survie**
   - `portfolio_survival_ratio_mean` ;
   - `selector_to_portfolio_survival_ratio_mean` ;
   - `portfolio_target_count_mean`.

3. **Qualité forward**
   - priorité à `portfolio_excess_return_20d_mean`, sinon fallback sur `portfolio_forward_return_20d_mean` ;
   - support de `selector_excess_return_20d_mean` / `selector_forward_return_20d_mean` en backup ;
   - part de cas positifs (`portfolio_positive_share_20d_mean`).

Le score final est un **compromis pondéré** entre ces trois piliers, avec pénalisation légère des scénarios trop incomplets en métriques.

### Colonnes clés de `scenario_recommendations.csv`

- `rank`
- `scenario_name`
- `overall_score`
- `robustness_score`
- `survival_score`
- `forward_quality_score`
- `confidence_score`
- `recommendation_label`
- `recommendation_reason`
- `recommendation_warnings`

### Lecture pratique

Un scénario recommandé automatiquement n'est pas forcément :

- celui qui a le meilleur forward absolu ;
- ni celui qui garde le plus gros univers.

L'objectif est plutôt d'identifier le **meilleur équilibre exploitable** entre :

- stabilité du run,
- conversion jusqu'au portefeuille cible,
- qualité forward moyenne.

### Phase 6 — robustesse par régime de marché

Le diagnostic phase 6 enrichit automatiquement `daily_metrics.csv` avec un label `market_regime` dérivé du benchmark (par défaut `SPY`) :

- `bull`
- `bear`
- `range`
- `vol`

La priorité est donnée à `vol` quand la volatilité réalisée explose, puis la tendance / momentum détermine `bull` ou `bear`, sinon le jour est classé `range`.

### Artefacts supplémentaires phase 6

Quand `daily_metrics.csv` contient les régimes, le diagnostic exporte aussi :

- `market_regimes.csv`
- `summary_metrics_by_regime.csv`
- `scenario_recommendations_by_regime.csv`
- `recommendation_summary_by_regime.json`
- `cross_regime_recommendations.csv`
- `cross_regime_recommendation_summary.json`

### À quoi servent ces artefacts

- `summary_metrics_by_regime.csv` : comparer un même scénario en marché haussier, baissier, latéral ou très volatil ;
- `scenario_recommendations_by_regime.csv` : meilleur compromis **à l'intérieur de chaque régime** ;
- `cross_regime_recommendations.csv` : classement de robustesse **entre régimes**, pour éviter de sur-optimiser un scénario valable seulement en bull market.

### Lecture pratique du score cross-régimes

Le classement cross-régimes favorise les scénarios qui combinent :

- une bonne moyenne de score par régime ;
- un bon pire cas (`worst_regime_overall_score`) ;
- une couverture large des régimes observés ;
- une variabilité réduite entre régimes.

En pratique, le meilleur scénario cross-régimes n'est pas forcément :

- celui qui gagne le plus fort en `bull` ;
- ni celui qui résiste le mieux seulement en `bear`.

L'objectif est de trouver le scénario **le plus robuste selon le contexte de marché**.

### Réanalyse d'un run existant

La commande suivante relit toujours le `summary_metrics.csv`, mais si le `daily_metrics.csv` associé contient `market_regime`, elle produit aussi automatiquement l'analyse phase 6 :

```powershell
python -m backtesting recommend-screener --input-dir artifacts/screener_diagnostics
```

### Phase 7 — recommandation adaptative par objectif

La phase 7 ajoute une lecture plus opérationnelle des scénarios selon l'objectif recherché.

Au lieu de ne sortir qu'un unique “meilleur compromis”, le pipeline produit désormais aussi quatre recommandations dédiées :

- `robuste`
- `offensif`
- `défensif bear-market`
- `meilleur compromis exécutable`

### Logique des 4 profils

#### `robuste`
- privilégie la stabilité globale ;
- exploite en priorité la lecture `cross_regime` si elle est disponible ;
- favorise les scénarios qui gardent un pire cas acceptable quand le contexte de marché change.

#### `offensif`
- surpondère la qualité forward ;
- valorise davantage le potentiel d'upside que la simple largeur d'exécution ;
- reste utile pour identifier les réglages plus agressifs quand l'objectif n'est pas la robustesse maximale.

#### `défensif bear-market`
- bascule sur le sous-ensemble `bear` dès qu'il existe ;
- met davantage l'accent sur survie + robustesse ;
- retombe proprement sur une lecture globale si aucun régime `bear` n'est disponible.

#### `meilleur compromis exécutable`
- priorise la conversion jusqu'au portefeuille cible ;
- valorise `portfolio_survival_ratio_mean`, `selector_to_portfolio_survival_ratio_mean` et `portfolio_target_count_mean` ;
- correspond au meilleur candidat quand le besoin principal est un réglage réellement déployable.

### Nouveaux artefacts phase 7

Quand une recommandation est calculée, le pipeline exporte aussi :

- `scenario_recommendations_by_objective.csv`
- `recommendation_summary_by_objective.json`

### Phase 8 — exposition directe côté IHM / dashboard

La phase 8 ne change pas le moteur de recommandation :
elle réutilise les artefacts phases 5→7 pour les rendre visibles directement dans l'interface Streamlit.

Concrètement, quand le répertoire `artifacts/screener_diagnostics/` contient :

- `scenario_recommendations_by_objective.csv`
- `recommendation_summary_by_objective.json`
- `metadata.json`

l'IHM affiche désormais :

- sur **🏠 Vue d'ensemble** : un résumé compact des leaders `robuste / offensif / bear / exécutable` ;
- sur **📊 Screening** : un bloc détaillé avec les leaders par objectif, la période analysée et le leaderboard phase 7.

Cette intégration est volontairement **read-only** :
elle permet de consommer les recommandations sans rajouter une nouvelle couche de calcul dans l'IHM.

### Phase 9 — lancement / recalcul directement depuis l'IHM

La page `ihm/pages/backtesting.py` permet maintenant aussi de déclencher depuis Streamlit :

- `python -m backtesting diagnose-screener`
- `python -m backtesting recommend-screener`

L'intégration réutilise le même registre de runs IHM que les autres commandes backtesting :

- lancement en arrière-plan ;
- historique centralisé ;
- logs `stdout` / `stderr` téléchargeables ;
- sélection du run courant dans le centre d'exécution.

En pratique :

- `diagnose-screener` sert à **rejouer le diagnostic PIT complet** et régénérer `summary_metrics.csv`, `daily_metrics.csv` et toutes les recommandations ;
- `recommend-screener` sert à **recalculer rapidement la couche de recommandation** à partir d'artefacts existants.

Si le répertoire cible reste `artifacts/screener_diagnostics`, la page **📊 Screening** relira automatiquement les artefacts mis à jour au prochain rafraîchissement.

### Lecture pratique

Cette phase 7 répond à des questions concrètes du type :

- si je cherche avant tout un paramétrage robuste, lequel choisir ?
- si je veux maximiser l'offensive forward, quel scénario ressort ?
- quel réglage tient le mieux en bear market ?
- quel scénario garde le meilleur compromis réellement exécutable ?

Les commandes existantes restent inchangées :

```powershell
python -m backtesting diagnose-screener --start 2024-01-01 --end 2024-12-31 --mode oat --limit-days 60
python -m backtesting recommend-screener --input-dir artifacts/screener_diagnostics
```

La différence est qu'elles produisent maintenant automatiquement aussi l'analyse par objectif, en plus des sorties phases 5 et 6.

---

## 12. État validé

Validation réelle effectuée :

- backfill exécuté avec succès sur `2026-04-17`
- snapshot inséré en base :
  - `snapshot_date = 2026-04-17`
  - `n = 1957`
  - `candidates = 100`
- validation runtime supplémentaire : `python -m backtesting run --start 2026-04-17 --end 2026-04-20 --equity 100000 --no-save --ml-mode off --sentiment-mode off`
- tests passés : `31 passed`

---

## 13. Recommandation pratique

Ordre conseillé :

1. tester sur 1 jour,
2. tester sur 5 jours,
3. lancer le backfill complet,
4. lancer ensuite le backtest.

### Séquence recommandée

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --limit-days 1 --screener-workers 2
python -m backtesting backfill-scores-history --start 2025-01-01 --limit-days 5 --screener-workers 2
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 2
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode auto --sentiment-mode auto
```


---

## 11. Phase 6.1 (refactor) — coûts explicites, dividendes, hold-out, profils

### 11.1 Commission & slippage en bps (Phase 6.1.b)

Les frais sont désormais paramétrés en **basis points** (bps) au lieu d'un
unique taux `--fees`. Défauts : `5 bps` de commission + `5 bps` de slippage
(soit `10 bps` aller-retour, ≈ `0.10%` par trade).

```powershell
python -m backtesting run --start 2024-01-01 --end 2025-01-01 `
  --commission-bps 5 --slippage-bps 5
```

`--fees` reste accepté pour la rétro-compatibilité mais émet un
`DeprecationWarning` et écrase `commission_bps`/`slippage_bps`.

Le `report.json` et l'IHM exposent `commission_bps`, `slippage_bps`, `fees_pct`
(somme convertie) ainsi que `fees` (legacy) dans `params`.

### 11.2 Dividendes encaissés (Phase 6.1.c)

`generate_report` accepte un argument `dividends_received` (somme des
dividendes touchés sur la période backtestée, lus best-effort depuis
`corporate_actions_events`). Deux nouveaux champs dans le rapport :

- `dividends_received` (USD)
- `total_return_with_dividends_pct` = `(equity_final + dividends) / equity_initial − 1`

Si la table `corporate_actions_events` est indisponible (env de test, DB non
provisionnée), on retombe à `0.0` sans bloquer le run.

### 11.3 Validation hold-out du diagnostic screener (Phase 6.1.d)

Les commandes `screener-diagnostics` et `recommend-screener` acceptent les
deux nouveaux flags :

```powershell
python -m backtesting screener-diagnostics `
  --start 2023-01-01 --end 2025-06-30 `
  --holdout-train-end 2024-12-31 --holdout-test-end 2025-06-30
```

Cela calcule, pour chaque scénario screener, le **rang train vs rang test**
sur le `metric_column` choisi (par défaut
`portfolio_forward_return_20d`) et émet :

- `holdout_validation_recommendations.csv`
  (`scenario_name, score_train, score_test, rank_train, rank_test, rank_delta, score_delta`)
- `holdout_summary.json` (`scenarios_evaluated, stable_top_k_ratio, avg_rank_delta`)

`stable_top_k_ratio = 1.0` ⇒ le top-K est identique entre train et test
(robuste). `avg_rank_delta` proche de 0 ⇒ classement cohérent. Voir
`backtesting/screener_diagnostics.py::validate_recommendations_holdout`.

### 11.4 Profils CLI consolidés (Phase 6.1.e)

Trois profils stables exposés via `--profile` :

| Profil | tp | ts | max_positions | commission_bps | slippage_bps | account_type | swing_only |
|---|---|---|---|---|---|---|---|
| `strict_swing_cash` | 0.08 | 0.05 | 20 | 5 | 5 | cash | ✅ |
| `swing_cash_aggressive` | 0.12 | 0.06 | 25 | 5 | 8 | cash | ✅ |
| `custom` (défaut) | — | — | — | — | — | — | — |

Les flags CLI explicites **prioritent toujours** sur le profil :

```powershell
python -m backtesting run --start 2024-01-01 --end 2025-01-01 `
  --profile strict_swing_cash --tp 0.10
# → tp=0.10 (explicite), ts=0.05 (profil), account_type=cash (profil)
```

Définition unique : `backtesting/profiles.py::BACKTEST_PROFILES`. Aligne
`risk/execution` pour ne pas dériver entre live et backtest.

### 11.5 `signal_replay` ↔ `core.conviction` (Phase 6.1.a)

`backtesting/signal_replay.py` consomme désormais
`core.conviction.fuse(...)` au lieu d'une formule locale. Le payload
`report.json["params"]["conviction_weights"]` documente la provenance
(`source = "core.conviction"`, `score_weight = 0.40`,
`prediction_weight = 0.60`). Cohérent avec `risk_management` (Phase 5.1.b)
et `event_sentiment.signal_aggregator` (Phase 4.1.a/b).

### 11.6 Tests Phase 6.1

```powershell
python -m pytest `
  tests/test_backtesting.py `
  tests/test_backtesting_profiles.py `
  tests/test_screener_diagnostics_holdout.py `
  tests/test_screener_diagnostics.py `
  tests/test_backfill_scores_history.py --no-cov -q
```
