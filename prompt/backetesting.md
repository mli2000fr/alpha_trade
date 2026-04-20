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

Le backtest et le backfill supposent que la base MySQL contient déjà :

- `stock_bars_daily`
- `model_predictions`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`
- `stock_metadata`

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

### Sans sauvegarde des artefacts

```powershell
python -m backtesting run --start 2023-01-01 --no-save
```

### Artefacts générés

Dans `artifacts/backtesting/` :

- `equity_curve.png` — courbe de valeur du portefeuille
- `trades.csv` — liste détaillée des trades

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

---

## 11. État validé

Validation réelle effectuée :

- backfill exécuté avec succès sur `2026-04-17`
- snapshot inséré en base :
  - `snapshot_date = 2026-04-17`
  - `n = 1957`
  - `candidates = 100`
- tests passés : `24 passed`

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
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000
```

