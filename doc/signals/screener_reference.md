# Stock Screener — référence

Retour : [vue signaux](../13_screener_selector_sentiment.md)

`stock_screener.py` orchestre le traitement par chunks/processus ; `pipeline.py` contient les calculs purs ; `db_io.py` charge et persiste ; `models.py` définit config, métriques chunk et rapport.

La passe 1 charge une fenêtre récente et évalue tradabilité objective. La passe 2 charge l'historique long seulement pour les candidats nécessaires au range. Les scores incluent liquidité/dollar volume, force relative 6 mois vs SPY et position dans le range historique. Les percentiles sont calculés dans la population du run.

`run_screener_with_report` crée run id, estime les rows, soumet chunks, agrège succès/erreurs, archive le snapshot puis upsert le latest. Les erreurs sont échantillonnées et comptées ; un chunk échoué ne doit pas disparaître du denominator.

Options : chunk size, workers, benchmark, seuil liquidité, RS min, fenêtre/range min, fenêtre première passe, désactivation two-pass et date PIT selon CLI courant. Le snapshot historique est indispensable à la publication d'univers d'une date passée.

Tables : lectures daily/metadata/audits ; écritures `stock_scores` et historique. Une purge de scores manquants ne doit être lancée que sur le scope explicitement prévu.

Diagnostics : candidats zéro (barres/source/seuils), RS aberrante (SPY/date), range faux (split/historique), mémoire élevée (two-pass off/chunk), run incomplet (chunk failures). Le screener produit contexte et admissibilité objective, jamais le côté final.

## Configuration

`ScreenerConfig` valide chunk, fenêtres, liquidité, benchmark, range et two-pass. Les defaults stricts sont construits avant le parser ; les overrides CLI deviennent la configuration effective du run. Archiver cette configuration avec le snapshot.

## Tradabilité objective

`evaluate_objective_tradability` évalue les critères disponibles sans ML. Une raison de rejet doit être conservée. La présence d'un score ne signifie pas que le symbole passe tous les critères.

## Préparation des prix

`_prepare_prices` normalise symbol/date, trie et borne à `as_of_date`. Les calculs roulants se font par symbole. Le benchmark 6 mois est chargé séparément ; sa date doit correspondre au cutoff.

## Scores

Les scores de percentile comparent la population du snapshot. Liquidité s'appuie sur dollar volume ; relative strength compare le rendement au SPY ; historical range positionne le close entre bas/haut de la fenêtre. Les composants et score final restent diagnostiques.

## Deux passes

La première fenêtre réduit le scope et le volume mémoire. La seconde charge l'historique long pour le range des candidats. Désactiver le two-pass peut changer performance et consommation, mais ne doit pas changer les résultats à données identiques ; un test de parité est requis.

## Chunks et workers

Chaque chunk retourne frame et `ScreenerChunkMetrics`. Le parent fusionne, compte erreurs et samples. `max_workers` est borné/résolu selon machine. Le traitement doit rester déterministe malgré ordre de futures.

## Persistance

`archive_scores_snapshot` écrit l'historique daté avant/avec l'upsert latest selon orchestration. `_normalize_scores_snapshot` homogénéise colonnes/nulls. Les valeurs NaN sont converties pour MySQL. Le snapshot historique conserve l'identité du run/source nécessaire à l'univers PIT.

## Run summary

Ciblés, processed, scores, chunks success/failed, estimated rows, timings, error samples et compteurs qualité. Une exécution avec chunk failures ne doit pas être publiée comme source complète sans politique explicite.

## Commandes

```powershell
python -m screener.stock_screener --help
python -m screener.stock_screener --chunk-size 500 --max-workers 8
```

Pour une date historique, utiliser l'option trade/as-of réellement exposée par le CLI courant et vérifier le snapshot archivé.

## Tests de modification

Série courte, NaN/volume nul, benchmark manquant, égalités percentile, cutoff, two-pass parity, chunk exception, multiprocessing determinism, archive/upsert et sérialisation MySQL.
