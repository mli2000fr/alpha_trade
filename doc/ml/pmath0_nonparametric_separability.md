# P-MATH-0 — Audit non paramétrique de séparabilité D1/D10

## Statut

**TERMINÉ / NO_STABLE_SEPARATION.** Recherche uniquement : aucune écriture SQL,
aucun modèle de serving et aucune cascade n'ont été modifiés.

## Question

Les informations PIT disponibles à J contiennent-elles une différence
mathématique stable entre les distributions directionnelles, même lorsque les
classifieurs habituels restent proches du hasard ?

Trois problèmes sont volontairement séparés :

1. `D1_VS_D10`, diagnostic théorique limité aux deux queues réelles ;
2. `D10_VS_REST`, sélection LONG exploitable dans tout le pool Oracle ;
3. `D1_VS_REST`, sélection SHORT exploitable dans tout le pool Oracle.

Une séparation D1/D10 qui disparaît face aux déciles intermédiaires ne suffit
pas à autoriser une évolution de production.

## Population et horloge

Le pool est celui du gate Oracle OOF TOP20 du batch sélectionné. Les features
proviennent du profil directionnel partagé et sont disponibles à J. Les labels
D1–D10 H20 et le garde de continuité existants sont autoritatifs.

Les folds sont chronologiques : 504 séances minimales d'entraînement, 126 de
validation, 126 de test, pas de 126 et purge H20. Les folds les plus récents
sont retenus, au maximum douze selon l'historique réellement disponible.

Dans chaque fold, médianes, winsorisation et standardisation sont apprises
uniquement sur le train. Les échantillons statistiques sont équilibrés à
l'intérieur de chaque date afin d'empêcher les régimes ou les tailles
quotidiennes du pool de fabriquer une différence artificielle.

## Statistiques

### MMD-RBF scalable

Le MMD utilise une approximation Random Fourier Features du noyau RBF. La
bande passante est estimée par la médiane des distances du train. Cette version
évite une matrice quadratique sur plusieurs centaines de milliers de lignes.

### Energy Distance projetée

Les données standardisées sont projetées sur seize directions aléatoires
gelées. La moyenne des Energy Distances unidimensionnelles mesure des
différences de distribution qui ne se limitent pas à la moyenne.

### Henze–Penrose / Friedman–Rafsky

Un arbre couvrant minimal est construit sur l'échantillon de test. Le nombre
d'arêtes reliant les deux classes estime la divergence HP sous priors
équilibrés. Le rapport publie aussi les bornes correspondantes de l'erreur de
Bayes ; elles restent des bornes asymptotiques et non une précision promise.

### Classifier two-sample test

Une Logistic L2 apprise sur le train mesure si la différence se généralise dans
le fold suivant. Elle sert de garde opérationnel : une p-value minuscule sur
une distance, rendue possible par un grand échantillon, ne suffit pas si l'AUC
chronologique reste inexploitable.

## Null, multiplicité et verdict

Les 99 permutations sont effectuées séparément dans chaque date du test. Elles
préservent donc le nombre quotidien de D1/D10. Les p-values des folds sont
combinées par Fisher puis corrigées par Holm sur les trois tâches et les quatre
familles de statistiques.

Le verdict distingue :

- `STABLE_OPERATIONAL_SEPARATION` : différence non paramétrique stable et AUC
  chronologique exploitable ;
- `WEAK_DISTRIBUTION_SHIFT_ONLY` : différence statistique détectable sans
  séparabilité opérationnelle ;
- `NO_STABLE_SEPARATION` : aucune différence robuste selon les gates gelés.

Les seuils sont dans
`config/research/pmath0_separability.json`. Ils ne doivent pas être ajustés
après lecture du run complet.

## Commandes

Smoke technique, 50 symboles, deux folds et 19 permutations :

    python -u -m modelFactory.oracle_separability_pmath0 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --max-symbols 50 --max-folds 2 --permutations 19 --log-level INFO

Run complet pré-enregistré :

    python -u -m modelFactory.oracle_separability_pmath0 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --log-level INFO

Les sorties sont placées dans
`artifacts/research/pmath0_separability/pmath0-*` :

- `report.json` : contrat, agrégats, gates et détails par fold ;
- `fold_metrics.csv` : métriques et nulls par tâche, fold et méthode.

Un résultat positif autorise seulement P-MATH-1. Il n'autorise aucune promotion
directe vers le serving.

## Smoke technique du 16 septembre 2026

Le smoke utilise 50 symboles demandés, dont 33 présents dans le pool Oracle,
12 537 événements, 1 764 dates et 84 features. Les deux folds récents couvrent
du 10 juillet 2024 au 11 juillet 2025. Les trois tâches terminent et les sorties
confirment `serving_changed=false` et `database_writes=false`.

Les résultats prédictifs du smoke ne sont pas interprétés : l'univers est un
petit sous-ensemble alphabétique et les 19 permutations ne donnent qu'une
résolution minimale de 0,05. Son rôle est uniquement de valider le contrat,
l'usage mémoire, les folds, les permutations et les artefacts. Cinq tests
unitaires ciblés passent. Artefact :
`artifacts/research/pmath0_separability/pmath0-smoke50-20260916-v2`.

## Run complet du 15 septembre 2026

Artefact autoritatif :
`artifacts/research/pmath0_separability/pmath0-20260915232426`.

Le pool contient 582 700 événements, 1 764 séances et 1 472 symboles du
5 juillet 2018 au 11 juillet 2025. Les 84 features demandées sont auditées sur
neuf folds OOS du 5 janvier 2021 au 11 juillet 2025. Chaque test contient
3 000 observations équilibrées, soit 1 500 par classe.

| Tâche | AUC Logistic médiane | Folds AUC >= 0,53 | MMD stable | Energy stable | HP stable | Verdict |
|---|---:|---:|---|---|---|---|
| D1 vs D10 | 0,5077 | 1/9 | non | non | oui | `NO_STABLE_SEPARATION` |
| D10 vs reste | 0,5096 | 2/9 | non | non | oui | `NO_STABLE_SEPARATION` |
| D1 vs reste | **0,5380** | **5/9** | non | non | oui | `NO_STABLE_SEPARATION` |

Les p-values Fisher corrigées de HP sont très faibles sur les trois tâches et
les bornes HP sont informatives selon le gate. Cela prouve qu'il existe des
différences locales dans l'espace multivarié. Cela ne prouve pas qu'une règle
stable et apprenable existe : les relations peuvent être non linéaires,
spécifiques aux symboles ou variables dans le temps.

Pour D1 contre le reste, le classifier two-sample est significatif dans sept
folds sur neuf et son AUC médiane vaut 0,5380. Cependant, cinq folds seulement
atteignent le niveau opérationnel de 0,53. Le seuil gelé de 67 % exige
arithmétiquement au moins sept folds sur neuf. Les AUC vont notamment de 0,5026
à 0,5565. Les deux derniers folds valent
0,5431 et 0,5565, mais cette récence ne doit pas être utilisée pour modifier le
gate après observation.

La séparation non paramétrique échoue également au contrat : HP passe, mais
MMD ne rejette que six folds sur neuf et Energy cinq sur neuf. Le seuil gelé
est 67 %, donc six sur neuf, soit 66,67 %, ne franchit pas le gate. Deux
méthodes non paramétriques stables étaient nécessaires.

## Décision finale

P-MATH-0 ferme la recherche d'une nouvelle formule utilisant uniquement le
même espace canonique à J pour D1/D10 et D10/reste. Le côté D1/reste reste un
signal exploratoire asymétrique, pas un candidat de serving. Aucun seuil ne
doit être relâché et aucun modèle ne doit être promu à partir de ce run.

La suite légitime n'est pas un nouveau réglage des 84 features : elle doit
ajouter une information réellement différente, notamment le graphe cross-asset
lead-lag prévu par P-MATH-1. Le résultat D1/reste pourra servir de benchmark
secondaire pré-enregistré, sans devenir la cible primaire a posteriori.
