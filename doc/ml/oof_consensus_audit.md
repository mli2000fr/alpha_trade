# Audit du consensus des modèles directionnels OOF

## Objectif

Cette expérience vérifie si plusieurs modèles directionnels déjà entraînés
contiennent une information complémentaire malgré leurs échecs individuels. Elle
ne réentraîne aucun modèle, ne modifie pas le serving et n’optimise aucun poids.

La question falsifiable est :

> Lorsque des familles de modèles conçues avec des cibles différentes classent
> les mêmes événements Oracle OOF dans le même sens, la direction réalisée
> devient-elle plus fiable que celle du meilleur modèle individuel ?

Un consensus positif ne serait qu’un `GO_RESEARCH`. Une confirmation sur une
période ultérieure, non utilisée ici, resterait obligatoire avant tout serving.

## Population et contrat PIT

Tous les composants proviennent du TOP20 Oracle calculé hors échantillon par le
batch `model-factory-20260904192500-0802c8`. La clé de jointure est strictement
`date + symbol`. Aucune prédiction manquante n’est reconstruite ou imputée :
chaque horizon utilise l’intersection stricte de ses familles.

Les anciens GlobalDirection, les prédictions de serving et le bundle Per-Symbol
ne sont pas mélangés à l’expérience lorsqu’ils ne fournissent pas une prédiction
OOF événementielle alignable sous le même contrat Oracle.

### Familles retenues

| Horizon | Familles |
|---:|---|
| H3 | rendement signé, dual-threshold, confirmation LONG calibrée, ranker conditionnel |
| H5 | rendement signé, dual-threshold |
| H10 | rendement signé, dual-threshold |
| H20 | classifieur D1/D10, PairLogit D1/D10, rendement signé, dual-threshold, ranker conditionnel, économie path-aware, first-touch |

Les deux variantes path-aware forment une seule famille. Les versions
multiclasse et binaire first-touch forment également une seule famille. Cette
agrégation empêche deux reformulations très proches de recevoir deux voix
entières dans le consensus.

## Normalisation et consensus

Les sorties brutes ne sont pas directement comparables : certaines sont des
probabilités, d’autres des marges, des rendements prédits ou des scores de rang.
Pour chaque date et chaque composant :

1. convertir le score en rang percentile cross-sectionnel ;
2. moyenner les rangs des composants appartenant à la même famille ;
3. recalculer le rang quotidien de la famille ;
4. moyenner à poids égaux les rangs des familles ;
5. classer les 20 % supérieurs comme candidats LONG et les 20 % inférieurs
   comme candidats SHORT.

La transformation n’utilise aucun rendement futur. Les poids égaux et la
fraction de 20 % sont fixés avant lecture des résultats. Aucun sweep de poids,
de seuil ou de sous-ensemble de modèles n’est autorisé dans cette expérience.

Deux politiques d’accord sont publiées uniquement comme diagnostics secondaires :

- `supermajority` : au moins deux tiers des familles votent dans le sens retenu ;
- `unanimous` : toutes les familles votent dans le même sens.

Elles ne remplacent pas le consensus primaire et ne peuvent pas être choisies a
posteriori parce que leur résultat serait meilleur.

## Mesures

Pour chaque famille et pour le consensus :

- IC de Spearman quotidien entre score et rendement futur ;
- taux de journées à IC positif ;
- rendement signé LONG et SHORT des queues de 20 % ;
- lift de chaque côté contre le pool Oracle complet ;
- spread brut entre queue haute et queue basse ;
- taux de réussite directionnelle ;
- amplitude terminale absolue sélectionnée contre le pool ;
- résultats par fold et par semestre ;
- corrélations quotidiennes entre familles ;
- couverture et résultat des politiques d’accord.

## Gates pré-enregistrés

Un horizon obtient `GO_RESEARCH` seulement si les six conditions suivantes sont
simultanément satisfaites :

1. IC quotidien moyen du consensus ≥ `0,02` ;
2. gain d’IC contre la meilleure famille individuelle ≥ `0,005` ;
3. spread haut-bas positif dans au moins 6 folds ;
4. spread haut-bas positif dans au moins 60 % des semestres ;
5. lift LONG contre le pool strictement positif ;
6. lift SHORT contre le pool strictement positif.

Sinon le verdict est `NO_GO` pour l’hypothèse « la moyenne équipondérée des
modèles existants résout la direction ». Un échec ne prouve pas qu’aucune future
méthode d’ensemble ne fonctionnera ; il interdit en revanche de rechercher des
poids optimaux sur ce même OOF sans nouveau protocole et nouvelle confirmation.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oof_consensus_audit --manifest config/research/oof_consensus_0802c8.json --output artifacts/models/shared_directional/oof-consensus-20260906-0802c8 --project-root F:\projets --log-level INFO
```

Le dossier produit contient :

- `report.json` : métriques, gates, corrélations et verdicts ;
- `consensus_predictions.parquet` : scores OOF et votes par événement.

## Résultat de la campagne du 6 septembre 2026

Artefact canonique :
[oof-consensus-20260906-0802c8](../../artifacts/models/shared_directional/oof-consensus-20260906-0802c8/report.json).

| Horizon | Familles | Lignes OOF communes | IC quotidien | LONG signé | SHORT signé | Spread haut-bas | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---|
| H3 | 4 | 86 256 | +0,0041 | +0,50 % | -0,26 % | +0,24 % | `NO_GO` |
| H5 | 2 | 86 256 | -0,0014 | +0,62 % | -0,46 % | +0,16 % | `NO_GO` |
| H10 | 2 | 86 256 | +0,0019 | +1,49 % | -0,95 % | +0,54 % | `NO_GO` |
| H20 | 7 | 78 538 | +0,0118 | +1,78 % | -1,44 % | +0,35 % | `NO_GO` |

Le rendement LONG positif ne suffit pas à conclure à une direction prédite : le
pool Oracle est structurellement haussier sur cette période. Le signal doit
également rendre la sélection SHORT profitable et battre le meilleur modèle
individuel. Or le SHORT signé est négatif à tous les horizons.

### Comparaison avec le meilleur composant

Le consensus ne franchit jamais le gate d’IC à `0,02` et ne bat jamais la
meilleure famille :

| Horizon | Meilleur IC individuel | IC consensus | Écart consensus - meilleur |
|---:|---:|---:|---:|
| H3 | +0,0136, ranker conditionnel | +0,0041 | -0,0095 |
| H5 | +0,0032, dual-threshold | -0,0014 | -0,0047 |
| H10 | +0,0041, rendement signé | +0,0019 | -0,0022 |
| H20 | +0,0251, ranker conditionnel | +0,0118 | -0,0134 |

Le consensus moyenne donc aussi les erreurs. Les corrélations quotidiennes entre
familles s’étendent approximativement de `0,12` à `0,72` selon l’horizon : les
modèles ne sont pas identiques, mais leur diversité ne contient pas assez
d’information directionnelle complémentaire.

### Accord renforcé

L’accord à deux tiers conserve presque toute la queue primaire et ne change pas
le verdict. À H20, l’unanimité réduit la couverture à `37,54 %` de la queue LONG
et `43,28 %` de la queue SHORT. Elle produit LONG `+1,52 %` et SHORT signé
`-1,07 %`. Une abstention beaucoup plus forte ne transforme donc pas le SHORT en
branche profitable.

À H3, l’unanimité conserve environ 65 % de chaque queue : LONG `+0,52 %`, SHORT
signé `-0,19 %`. H5 et H10 n’ont que deux familles ; leur règle supermajoritaire
équivaut mécaniquement à l’unanimité et n’apporte pas de preuve indépendante.

### Overlay de régime quotidien E5

Le score moyen Ridge/CatBoost E5 couvre `1 008 / 1 134` dates H20 (`88,89 %`).
Le veto ne conserve que `32,74 %` de la queue LONG et `67,45 %` de la queue
SHORT. Le rendement LONG tombe à `+0,55 %`, soit un lift de `-0,61` point contre
le pool des mêmes dates ; le SHORT signé reste négatif à `-0,92 %`. Le régime
quotidien ne sauve pas le consensus.

### Stabilité et amplitude

Le spread du consensus est positif dans 6 folds sur 9 à H3, H10 et H20, mais son
amplitude est faible et les semestres négatifs restent importants. À H20, le
spread devient notamment négatif en 2022H2, 2023H1 et 2025H1. Le dernier
`2025H2` est incomplet, car les OOF s’arrêtent au 11 juillet 2025 ; il ne doit pas
être interprété comme un semestre de confirmation complet.

La moyenne des rendements terminaux absolus des queues consensus dépasse le
pool de seulement environ `0,04` à `0,16` point selon l’horizon. L’ensemble ne
crée donc pas non plus une amélioration d’amplitude matériellement distincte de
l’Oracle déjà appliqué en amont.

## Verdict

**`NO_GO` pour le consensus équipondéré des modèles existants.** Aucun horizon
ne franchit les six gates pré-enregistrés. Les échecs les plus structurants sont
l’IC trop faible, l’absence de gain contre le meilleur composant et une branche
SHORT économiquement négative sur toute la grille H3/H5/H10/H20.

Il ne faut pas rechercher maintenant des poids, seuils ou sous-ensembles
optimaux sur ces mêmes OOF : ce serait transformer l’audit en optimisation
a posteriori. La prochaine hypothèse indépendante peut porter sur une nouvelle
représentation temporelle D1/D10 V2 ou sur de nouvelles données signées, avec un
nouveau protocole de validation.
