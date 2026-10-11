# Oracle Extreme — inférence, persistance et gate quotidien

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Retour : [dossier Oracle](README.md)

## Champions et sélection PIT

`has_oracle_champions()` vérifie `oracle_champions.json`. Le manifeste est trié par `t_start`. Pour une date D, `predict_oracle_extreme_history()` prend le plus grand `t_start <= D`.

Si D précède tous les folds, le code choisit le premier champion et suppose son entraînement antérieur. Cette hypothèse doit être vérifiée dans les métadonnées avant de revendiquer une prédiction causale antérieure.

Les features viennent du manifeste et sont intersectées avec le dataset. Si le contrat contient `global_rank_20`, les ranks sont requis ; O0 les ignore. Les labels sont optionnels en prédiction forward.

Les boosters sont chargés à la demande et cachés par fold. Une erreur sur une date est journalisée puis les autres dates continuent : rapprocher dates attendues et rows écrites.

L'horizon se lit dans le profil de l'artefact Oracle ; H20 n'est que le repli
legacy lorsque la metadata manque. Un horizon demandé incompatible est refusé.
Les profils de recherche `pit_dynamic_bars` ne deviennent pas des champions
serving ordinaires : ils passent par leur chemin shadow/recherche contrôlé.

## Date et échecs du CLI prospectif US — 10 octobre 2026

La date de signal est résolue par `common/us_signal_date.py`, puis figée pour
Oracle, GPT et les étapes aval. En mode prospectif, un lancement hors séance
(week-end, jour férié ou avant l'ouverture suivante) peut résoudre la dernière
séance US clôturée ; il ne doit pas scorer la date civile Paris par accident.
Le filtre GPT vérifie aussi sa fenêtre close → prochaine ouverture avant
l'inférence : aucune recherche Web historique ni Oracle shadow dans ce filtre.

Une sortie Oracle-only `no_predictions`, vide ou en erreur provoque désormais
un code retour non nul avant le GPT. « Predictions: 0 rows » n'est pas un succès
de l'étape 10. Inspecter le dataset, le contrat de features, l'artefact et les
erreurs par date ; ne pas lancer risque/exécution sur un autre batch/date en repli.
[Contrat du filtre](../oracle_llm_directional_filter.md) ·
[Pipeline planifié](../../operations/us_pipeline.md).

## Persistance

`write_oracle_predictions()` exige un batch, normalise date/symbole et upsert. La PK `date,symbol,batch` écrase l’ancienne valeur sans run id. Pour comparer deux artefacts, employer deux batch ids ; ne pas réutiliser un batch comme version générique.

`load_oracle_predictions()` exige un batch par défaut et filtre éventuellement start/end. Une table absente est créée puis relue. Une table présente mais sans rows du batch reste un résultat vide explicite.

## Gate

`compute_extreme_gate()` calcule :

`extreme_pct = groupby(date)[proba_extreme].rank(pct=True)`

`extreme_gate = extreme_pct >= 1-pool_pct`.

Avec 20 %, le seuil est 0,8. DataFrame vide ou proba absente donne false. NaN donne un rang NaN et false.

Le commentaire historique des cas `pool_pct<=0` et `>=1` est inversé par rapport à la formule : pool 0 tend à ne garder que le percentile 1 ; pool ≥1 tend à tout garder. Le calcul exécutable fait foi.

Les égalités suivent le rang pandas par défaut. La taille retenue peut différer exactement du pourcentage cible.

## Rank map et consumers

`build_oracle_rank_map()` retourne `{date:{symbol:proba_extreme}}`. Le consumer cascade recalcule son percentile selon son univers. Filtrer l’univers avant le rang change les membres ; conserver batch, pool, population, valeurs manquantes et couche directionnelle aval.

Le backtest offre deux consumers distincts : `extreme_gate` pour le chemin legacy LONG et
`extreme_gate_directional` pour la combinaison amplitude Oracle + direction Per-Symbol.
Le second exige une prédiction Per-Symbol, compare `proba_long` et `proba_short`, applique le
seuil de la cascade et une marge directionnelle, puis classe par
`percentile_oracle × probabilité_directionnelle`. Voir
[Mode cascade](../../mode_cascade.md).

## Contrôles

1. Batch et champions explicites.
2. Features strictement compatibles.
3. Couverture quotidienne publiée.
4. Aucun mélange de batch.
5. Population du percentile conservée.
6. Gate vide fail-closed.
7. Direction fournie ailleurs.
8. Risque/lifecycle identifiés.
9. Rows attendues/écrites rapprochées.
10. Rollback sans Oracle disponible.

## Diagnostic

| Symptôme | Vérification |
|---|---|
| no champions | manifeste et fichiers |
| dataset vide | fenêtre, barres, symboles, rank requis |
| aucune feature | manifeste contre colonnes courantes |
| dates manquantes | logs par date et fold |
| gate vide | batch, NaN, population, pool |
| trop de membres | égalités et univers |
| résultat écrasé | même batch réutilisé |
| mauvais côté | Oracle interprété comme direction |

