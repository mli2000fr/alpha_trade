# E21-B3 — Lecture des tableaux et de leurs en-têtes

## Implémentation

`service/forward_pit/guidance_tables.py` lit les tableaux HTML et conserve la
provenance de chaque fourchette : tableau, ligne, cellule, label, en-tête et
position dans le texte visible. Une fourchette n'est associée à une cellule
que si ses deux bornes y sont contenues ; une valeur traversant plusieurs
cellules reste ambiguë.

Le rôle est proposé uniquement à partir d'indices explicites :

- colonne `prior/previous guidance` : `PRIOR_FORECAST` ;
- colonne `current/new/updated guidance` : `NEW_FORECAST` ;
- en-tête `following table summarizes ... targets` : `NEW_FORECAST` ;
- en-tête explicite de résultats : `REALIZED_RESULT` ;
- absence d'indice, tableau imbriqué ou `rowspan` : `AMBIGUOUS`.

Une cellule contenant `respectively` est rejetée comme intervalle : par
exemple `$17 and $23, respectively` représente deux valeurs distinctes. Les
en-têtes ne se propagent pas au tableau suivant.

## Informations extraites

Le service ajoute `table_context` et `table_suggestions` : mesure issue du
label de ligne, base GAAP/non-GAAP issue de la cellule, année fiscale et
trimestre issus de l'en-tête, unité explicite, et scope segment conservant le
label exact. Ces champs restent des suggestions : `validated` demeure vide et
`eligible_for_comparison=false` jusqu'à revue.

L'année fiscale ne suffit pas à déterminer la date de clôture. Les unités
présentes seulement dans des en-têtes complexes, la définition non-GAAP
complète, le scope groupe et la disponibilité PIT nécessitent encore une
validation.

## Résultat de développement Adobe/Agilent

Le corpus avait déjà été lu pour développer cette évolution : il ne constitue
donc pas une confirmation indépendante. Il comprend huit annexes et 71
candidats, dont 66 prévisions actuelles et cinq faux intervalles selon la
référence assistant.

Après lecture des tableaux :

- 63 prévisions classées `NEW_FORECAST` ;
- trois prévisions laissées ambiguës ;
- cinq faux intervalles laissés ambigus ;
- couverture des prévisions détectées : **63/66 = 95,5 %**, contre 25/66 ;
- abstention : 8/71 = 11,3 %.

Aucun faux intervalle de ce petit corpus n'est transformé en prévision. Cela
ne prouve pas une précision généralisable : les répétitions titre/corps ne
sont pas indépendantes, le rappel documentaire complet n'est pas mesuré, et
les classes ancienne prévision et réalisé ne sont pas représentées dans la
référence.

Artefacts :
`artifacts/research/guidance_structured/e21b-tables-adbe-development-v2/`.
Le corpus est lié à son SHA256 exact. Les tests couvrent les offsets, en-têtes,
colonnes ancien/actuel, GAAP/non-GAAP, segments, non-propagation et abstention.

## Verdict et suite

Le problème des tableaux Adobe est techniquement corrigé, mais E21 reste
`DATA_NOT_READY`. Il faut maintenant geler ces règles et constituer un corpus
réellement nouveau comprenant les trois rôles. Tous les candidats et toutes
les prévisions manquées devront être annotés avant d'adapter de nouveau les
règles. Aucun rendement, entraînement ou backtest ne doit être consulté avant
cette validation.

Voir [validation des rôles](guidance_role_validation_e21b.md) et
[socle E21-B](guidance_structured_e21b.md).

La confirmation indépendante suivante échoue : voir
[E21-B4, matrice et causes](guidance_table_validation_protocol_e21b4.md).

E21-B5 est documenté dans le même rapport : la couverture NEW progresse, mais
les relations `from OLD to NEW` font échouer la distinction des anciennes
prévisions. Ne pas utiliser V2 pour créer des labels.
