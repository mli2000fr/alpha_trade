# Architecture de replay broker-like

Retour : [références Backtesting](README.md)

Le replay reproduit les couches, pas seulement les rendements. `signal_replay` produit les candidats ; `risk_bridge` appelle le contrat portefeuille ; `execution_replay` simule tentatives/fills ; `execution_lifecycle_replay` crée les protections ; `protection_watcher_replay` déclenche leurs transitions ; `exit_lifecycle_replay` produit les sorties.

Chaque phase normalise ses frames et sauvegarde des artefacts. Pour diagnostiquer une divergence, comparer : candidats, entries, intents, fills, enfants, triggers, exits, puis positions. Le premier écart est la cause probable ; le PnL n'est que la conséquence.

La date de décision et la date d'exécution sont séparées. Les barres utilisées pour les features s'arrêtent au cutoff. Les positions initiales, cash, corporate actions et régime doivent être identiques au scénario comparé.

`execution_broker_like.py` calcule des compteurs d'états/événements par séance. Un fill synthétique doit respecter quantité, liquidité, gap et prix définis par microstructure.

## Données requises

Barres OHLCV split-adjusted, univers/scores/prédictions historiques PIT, secteurs, quotes si coûts réels, corporate actions, benchmark/macro et configuration. Chaque frame est normalisée sur symbol/date. L'absence d'une source doit produire un preflight/fallback explicite.

## Phase signal

Le signal replay reconstruit la sélection de la date D avec le batch et l'univers correspondants. Il ne doit pas utiliser le classement recalculé sur l'univers actuel. La sortie conserve score, côté, décision date, entry date et raisons des gates.

## Phase risque

`risk_bridge` prépare `SelectionScore`/prédictions, calcule ATR sur le passé, matrice de rendements et snapshots de régime, puis appelle la construction portefeuille partagée. Il exporte entries, rejets, régime et diagnostics. L'equity/positions initiales font partie des inputs.

## Phase exécution

`execution_replay` convertit entries en targets puis tentatives synthétiques à la séance d'exécution. Il applique gap, liquidité, prix et état terminal. Les fills sont dérivés des tentatives ; le prix moyen est pondéré. Les ordres non fillés restent visibles.

## Phase protections

`execution_lifecycle_replay` regroupe enfants par parent et agrège les fills d'entrée. Il construit stop/TP pour la quantité remplie. `protection_watcher_replay` recherche les triggers sur les séances futures selon activation. `exit_lifecycle_replay` traduit le motif de sortie en rôle d'intention.

## États broker-like

Les frames normalisées doivent distinguer request, submitted/accepted, partial/filled, cancelled/rejected et événements. Les summaries comptent états, raisons et séances. Cela permet une comparaison avec les tables execution réelles.

## Artefacts

Chaque fonction `save_phase*_artifacts` écrit CSV/JSON sous le dossier du run. Conserver aussi metadata git/config/dataset hash. Ne pas écraser un run antérieur avec le même nom sans version/run id.

## Diagnostic par première divergence

1. univers et prédictions ;
2. candidats/côtés/rangs ;
3. taille et régime ;
4. date/target/delta ;
5. tentative/gap ;
6. fill ;
7. enfants ;
8. trigger/exit ;
9. position/equity.

Comparer directement l'equity finale masque la cause. Une divergence d'un jour d'entrée peut modifier toutes les phases suivantes.

## Résilience et reconstruction

`resilience.py` peut reconstruire prédictions manquantes ou appliquer overlay walk-forward. Le résultat indique reconstructed et cause. Une reconstruction actuelle n'est pas une prédiction historiquement émise ; le rapport doit les distinguer.

## Tests

Date prochaine séance, univers changeant, aucune prédiction, partial fill, ordre rejeté, stop/TP, watcher activation, force close, corporate action, données manquantes et artefacts schema.
