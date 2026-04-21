# Backtesting & Backfill — Guide d'usage

## Objectif

Ce document résume l'intégration du module `backtesting/` et les commandes utiles pour :

- lancer un backtest vectorbt,
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
| `backtesting/simulator.py` | Moteur vectorbt avec TP + trailing stop |
| `backtesting/trading_constraints.py` | Contraintes de compte petit capital / PDT (`standard`, `pdt`, `swing`, `cash`) |
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
- `--swing-only` : interdit toute sortie le jour même de l'entrée ;
- `--account-type cash` : désactive de facto la règle PDT et n'autorise que le cash settled, avec settlement simplifié en `T+1`.

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
- `--swing-only` correspond bien à l'idée « achat aujourd'hui, vente demain ou plus tard » ;
- l'ancien flag `--account-constraint-mode` reste accepté temporairement comme alias legacy, mais il est déprécié.

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

## 11. État validé

Validation réelle effectuée :

- backfill exécuté avec succès sur `2026-04-17`
- snapshot inséré en base :
  - `snapshot_date = 2026-04-17`
  - `n = 1957`
  - `candidates = 100`
- validation runtime supplémentaire : `python -m backtesting run --start 2026-04-17 --end 2026-04-20 --equity 100000 --no-save --ml-mode off --sentiment-mode off`
- tests passés : `31 passed`

---

## 12. Recommandation pratique

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

