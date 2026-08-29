# Validation statistique et promotion

Retour : [références Backtesting](README.md)

`bootstrap_trades` rééchantillonne les trades ; le block bootstrap préserve des blocs temporels. `parameter_sensitivity` vérifie la stabilité autour du paramètre choisi. `deflated_sharpe_ratio` tient compte de non-normalité/essais ; `multiple_testing_correction` ajuste les tests ; `compute_promotion_score` agrège des gates.

Protocole : hypothèse préfixée, baseline, période de développement, walk-forward, holdout final, seeds, sensibilité, coûts/capacité, attribution et stress. Compter toutes les variantes tentées. Le choix après inspection ne peut être validé sur la même période.

Gates recommandés : performance nette positive multi-périodes, drawdown acceptable, absence de concentration extrême, stabilité folds/seeds, gradient cohérent, parité PROD, robustesse coûts, capacité et rollback. Une moyenne positive avec un semestre catastrophique doit être explicitement arbitrée.

Archiver commande, commit, dirty state, environnement, config, dataset hash, univers, batch ML et tous les artefacts. Sans ces éléments, un résultat n'est pas reproductible.

