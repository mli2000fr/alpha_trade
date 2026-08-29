# Validation statistique et promotion

Retour : [références Backtesting](README.md)

`bootstrap_trades` rééchantillonne les trades ; le block bootstrap préserve des blocs temporels. `parameter_sensitivity` vérifie la stabilité autour du paramètre choisi. `deflated_sharpe_ratio` tient compte de non-normalité/essais ; `multiple_testing_correction` ajuste les tests ; `compute_promotion_score` agrège des gates.

Protocole : hypothèse préfixée, baseline, période de développement, walk-forward, holdout final, seeds, sensibilité, coûts/capacité, attribution et stress. Compter toutes les variantes tentées. Le choix après inspection ne peut être validé sur la même période.

Gates recommandés : performance nette positive multi-périodes, drawdown acceptable, absence de concentration extrême, stabilité folds/seeds, gradient cohérent, parité PROD, robustesse coûts, capacité et rollback. Une moyenne positive avec un semestre catastrophique doit être explicitement arbitrée.

Archiver commande, commit, dirty state, environnement, config, dataset hash, univers, batch ML et tous les artefacts. Sans ces éléments, un résultat n'est pas reproductible.

## Bootstrap trades

Le bootstrap classique suppose des observations rééchantillonnables. Les trades d'un même régime/jour peuvent être dépendants ; le block bootstrap est préférable pour préserver des séquences. Rapporter intervalle, nombre de resamples, seed et statistique.

## Sensibilité paramètres

Tester un voisinage fixé avant inspection. Un optimum isolé entouré de résultats mauvais est fragile. La sensibilité couvre performance, drawdown, turnover et nombre de trades, pas seulement PnL.

## Deflated Sharpe

Le DSR corrige biais de sélection en tenant compte du nombre d'essais et moments de la distribution. Le nombre d'essais inclut variantes abandonnées, horizons et seeds consultés. Un DSR positif ne remplace pas la parité opérationnelle.

## Correction multiple

Appliquer la méthode prévue aux p-values d'une famille d'hypothèses. Définir la famille avant les tests. Changer de méthode après observation est une nouvelle décision de recherche.

## Promotion score

`compute_promotion_score` agrège des critères ; conserver composantes et gates, pas seulement le score total. Un gate dur (fuite, drawdown, parité) doit rester bloquant même si les autres composantes compensent.

## Découpage temporel

Development, validation et holdout final doivent être chronologiques. Walk-forward fournit plusieurs OOS, mais si leurs résultats servent à choisir la variante, un holdout supplémentaire reste nécessaire.

## Seeds

Rapporter médiane, dispersion, pire seed et concentration. Ne pas choisir la seed représentative après coup seulement parce qu'elle est proche du résultat souhaité.

## Attribution et concentration

Mesurer top1/top5/top10 contribution, secteurs, périodes, côtés et exit reasons. Une stratégie dépendante de quelques trades exige une incertitude plus large.

## Gate de suppression d'une idée

Abandonner ou maintenir research-only si signal instable, coût annule edge, capacité insuffisante, fuite non résolue, parité échoue ou holdout invalide l'hypothèse. Conserver une synthèse de verdict, pas tous les journaux dans la refonte.

## Checklist de rapport

Hypothèse, population, dates, PIT, target/lifecycle, paramètres préfixés, nombre d'essais, baselines, OOS, coûts, capacité, statistiques, breakdown, limitations, verdict et statut promotion.
