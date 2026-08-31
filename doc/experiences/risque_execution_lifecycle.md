# Expériences risque, exécution et lifecycle — synthèse

Retour : [exécution](../11_execution_et_protections.md) · [backtesting](../12_backtesting_validation.md)

## Sources regroupées

`recherche_vs_pipeline.md`, `backtest_audit.md`, documents time-stop/parity, rebench post-fix TP, drawdown/reprise, B4/C2, force-close, airbag, exposition, go-live et synthèses TP/risk/execution.

## Enseignement central

Plusieurs écarts spectaculaires venaient de contrats d’exécution différents : stop, TP, trailing, time-stop, gap filter, ordre d’activation et résolution intrabar. Une conclusion obtenue sous un lifecycle de recherche ne se transpose pas au contrat PROD.

Le recheck E12 sous PROD a notamment invalidé une narrative de stops prématurés spécifique à 2026H1 et réorienté le diagnostic vers les entrées. Cet exemple impose un audit du contrat avant toute optimisation.

## Drawdown et reprise

Les campagnes breaker/force-close ont exploré réduction, fermeture et reprise progressive. Les enseignements durables sont : état de drawdown persistant, hystérésis/release, séparation catastrophe versus bruit, reprise par étapes et analyse side-aware.

## Exposition

Une faible exposition peut venir du sizing, du nombre de slots, de la corrélation, du régime ou du circuit breaker. Attribuer le PnL au seul modèle sans décomposer le funnel risque→targets→fills est incorrect.

## Statut

Les paramètres chiffrés et verdicts go-live historiques ne sont pas des defaults. Le contrat actuel vient de `execution_engine/config.py`, du watcher, de `config.yaml` et des options du run.

