# Sprint 15-B6 — Calendrier réalisable et extension Oracle OOF

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

29 septembre 2026. Suite de [15-B5](./sprint_15b5_features_et_jointures_temporelles.md).

**État actualisé : audit terminé et nouvelle campagne pré-enregistrée. Les deux entraînements Oracle OOF 2021 sont terminés (`OOS_RESEARCH_ONLY`) ; leurs jointures et les gates réels sont audités en [15-B7](./sprint_15b7_jointures_2021_preflight_directionnel.md). Aucun entraînement directionnel, aucune modification de serving ou écriture en base.**

## 1. Pourquoi le protocole B4 ne peut pas être exécuté tel quel

B4 proposait huit semestres de test directionnel 2022H1–2025H2 avec 504 séances d'apprentissage et une fenêtre de validation de 126 séances. B5 a montré que les scores Oracle OOF existants commencent en 2022. Il manque donc l'historique directionnel préalable aux six folds 2022–2024.

Il serait incorrect de remplacer ces observations par les scores d'un Oracle final appliqué au passé : ce ne serait pas de l'OOF. Réduire les fenêtres ou choisir d'autres dates après avoir vu les performances serait également une autre expérience.

B6 est donc une **nouvelle campagne**, pas une modification silencieuse de B4 :

- les YAML et les artefacts B4/B5 restent inchangés ;
- le [protocole B6](../../config/research_cn/sprint15b6_margin_calendar.yaml) est enregistré avant les résultats directionnels de marge ;
- les sources amont sont verrouillées par leurs SHA-256 ;
- le [service dédié](../../modelFactory/cn_margin_calendar_15b6.py) ne modifie pas le runner Oracle 10-B, dont l'empreinte est utilisée par de nombreuses autres recherches.

## 2. Audit réel de la faisabilité Oracle

Rapport définitif : [audit.json](../../artifacts/research/cn_margin_lending/sprint15b6_calendar_v2/audit.json).

L'audit lit les panels prix CN et les labels H20 déjà qualifiés. Il vérifie leurs empreintes et jointures, applique l'échantillonnage annuel déterministe de 10-B puis la purge des labels indisponibles, et contrôle le nombre de séances **après** purge et plafonnement.

| Fold Oracle envisagé | Séances antérieures du panel | Séances train après purge/échantillonnage | Lignes train | Lignes validation | Séances validation après purge | Lignes test | Séances test | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2020H1 | 447 | — | — | — | — | — | — | Insuffisant pour 504 + 126 |
| 2020H2 | 564 | — | — | — | — | — | — | Insuffisant pour 504 + 126 |
| 2021H1 | 690 | 543 | 416 377 | 400 437 | 105 | 485 335 | 118 | Entraînement OOF réalisable |
| 2021H2 | 808 | 661 | 429 392 | 422 551 | 105 | 548 063 | 125 | Entraînement OOF réalisable |

Les séances du panel ne sont pas nécessairement toutes les séances du calendrier de marché : une journée sans candidats qualifiés n'est pas inventée comme journée d'apprentissage.

### Bornes vérifiées

Pour 2021H1 :

- validation commence le 1er juillet 2020 ;
- labels train disponibles au plus tard le 30 juin 2020 à 01:30 UTC ;
- labels validation disponibles au plus tard le 31 décembre 2020 à 01:30 UTC ;
- première décision test le 4 janvier 2021 à 01:30 UTC.

Pour 2021H2 :

- validation commence le 22 décembre 2020 ;
- labels train disponibles au plus tard le 21 décembre 2020 à 01:30 UTC ;
- labels validation disponibles au plus tard le 30 juin 2021 à 01:30 UTC ;
- première décision test le 1er juillet 2021 à 01:30 UTC.

Le code exige l'antériorité stricte des labels train face à la décision de validation et des labels validation face à la décision de test. Une fenêtre de validation de 126 séances ne signifie pas 126 séances conservées après purge : l'Oracle en conserve ici 105, comme la convention de 10-B.

## 3. Deux folds Oracle supplémentaires, pas un nouvel Oracle choisi après résultats

L'extension est limitée à :

- H20, LightGBM ;
- tests 2021H1 et 2021H2 ;
- mêmes 33 variables prix, paramètres LightGBM, seed 20260925 et early stopping de 30 itérations que le protocole Oracle 10-B ;
- apprentissage chronologique depuis 2018 ;
- plafonnement annuel préalable puis plafonnement global déterministe, au maximum 600 000 lignes train ;
- aucune réduction ni sélection de validation/test ;
- scores pour **tous les candidats CN du semestre**, pas seulement Shenzhen ou les titres éligibles à la marge.

Le TOP20 devra être calculé sur cette population CN complète, puis restreint à XSHE et aux observations de marge disponibles. Aucun futur décile ne participe à la sélection du TOP20.

Les performances d'amplitude des deux folds ne serviront pas à choisir un autre modèle, un autre horizon ou à supprimer un fold directionnel défavorable. Le modèle d'amplitude est fixé à l'avance. Les prédictions originales 2022–2025 ne sont pas recalculées ni écrasées.

Les commandes d'extension exigent l'audit réussi correspondant au **même code, protocole et fichiers sources**. Les sorties d'une exécution existante ne sont pas écrasées. Un run échoué reste marqué FAILED et nécessite un dossier/audit neuf après diagnostic.

## 4. Nouveau calendrier directionnel pré-enregistré

| Rôle | Semestres |
|---|---|
| Historique des événements Oracle OOF | Depuis 2021H1 |
| Développement directionnel | 2024H1, 2024H2 |
| Confirmation historique | 2025H1, 2025H2 |

2022–2023 deviennent de l'historique potentiel d'apprentissage, **pas des folds de test prétendument évaluables**. Les nouveaux critères de stabilité sont fixés pour quatre folds, et non renommés comme une réussite du protocole à huit folds B4.

Les dates 2025 ont déjà été consultées dans d'autres expériences CN. Il s'agit d'une confirmation historique, **pas d'un holdout global vierge ni d'une certification de généralisation future**.

### Séparation temporelle des modèles directionnels

Sur le calendrier des événements candidats :

1. vingt séances complètes sont laissées avant le début du test ;
2. les 126 séances précédentes constituent la fenêtre de validation ;
3. vingt autres séances sont laissées entre train et validation ;
4. les labels train doivent être disponibles strictement avant la première décision de validation ;
5. les labels validation doivent être disponibles strictement avant la première décision de test ;
6. après ces exclusions, il faut au moins 504 séances train et 100 séances de validation exploitables.

La règle explicite de 100 séances minimum concerne le résultat **après purge**, pas la taille de la fenêtre, qui reste 126. Ce contrôle est fixé avant toute performance.

Audit du calendrier, en supposant provisoirement une couverture des futurs scores 2021 :

| Test directionnel | Séances antérieures, borne haute | Train après les deux gaps, borne haute | Fenêtre validation | Dernière séance train | Fenêtre validation |
|---|---:|---:|---:|---|---|
| 2024H1 | 727 | 561 | 126 | 2023-04-26 | 2023-05-30 → 2023-12-01 |
| 2024H2 | 844 | 678 | 126 | 2023-10-23 | 2023-11-21 → 2024-05-30 |
| 2025H1 | 969 | 803 | 126 | 2024-04-26 | 2024-05-30 → 2024-12-03 |
| 2025H2 | 1 086 | 920 | 126 | 2024-10-23 | 2024-11-21 → 2025-05-30 |

**Ces chiffres étaient des bornes de calendrier, pas une preuve des populations train.** La preuve postérieure est dans [15-B7](./sprint_15b7_jointures_2021_preflight_directionnel.md) : après production des scores 2021 et application des quatre variables de marge, de la baseline complète, des labels valides et des deux classes, les huit gates tâche × fold passent. Ce constat ne prouve aucune performance directionnelle et ne change pas les exigences pré-enregistrées.

## 5. Modèles, variables et critères figés

Les tâches restent D1 versus D10 et D10 versus le reste, avec les vrais déciles CN H20 sans recalcul sur Shenzhen.

La baseline reprend les 33 variables prix et le contrôle logarithmique du montant historique moyen sur 20 séances. Les trois extensions restent flux, encours et combinaison des quatre variables de marge définies en B4. Aucun ajout de variable guidé par les futurs résultats.

Deux familles sont proposées :

- régression logistique L2 : C=1, solver lbfgs, max_iter=2000, aucune pondération de classe ; standardisation apprise uniquement sur train ;
- LightGBM : 300 estimateurs, profondeur 5, learning rate 0,03, 31 feuilles, min_child_samples=150 et reg_lambda=1 ; paramètres B4, sans early stopping ni calibration dans cette nouvelle campagne directionnelle.

Seed directionnel 20260928, plafond train 600 000, aucune sélection de seuil de probabilité. Ces modèles directionnels **ne sont pas implémentés/lancés par la tranche B6** ; les paramètres sont pré-enregistrés pour l'étape suivante.

Conditions de conclusion, toutes nécessaires :

- chaque tâche/fold dispose de 60 dates, 500 lignes, 20 symboles et des deux classes ;
- baseline et extensions comparées sur exactement les mêmes lignes ;
- gain d'AUC au moins +0,015 ;
- gain positif sur au moins trois des quatre folds, dont **les deux** confirmations 2025 ;
- uplift de précision au TOP20 directionnel au moins +0,02 ;
- ne pas retirer plus de 30 % des vrais positifs du TOP20 **de la baseline prix** : cette référence n'est pas l'ensemble des D10 de l'Oracle ;
- bootstrap par mois, 1 000 répétitions ; borne ajustée du gain d'AUC strictement positive ;
- famille principale de 12 hypothèses : deux tâches × deux modèles × trois extensions, au retard principal de deux séances ; correction Bonferroni bilatérale, alpha familial 5 % ;
- résumé pondéré également par date, pas dominé par les journées avec plus de titres ;
- retards 3/5 et séparation avant/après le 11 juillet 2024 descriptifs, sans choix du meilleur lag ni revendication GO supplémentaire ;
- aucun GO si un fold requis ne passe pas ses gates.

Pour éviter plusieurs lectures possibles des critères : le +0,015 s'applique au gain global des prédictions OOF des quatre folds, avec un poids individuel inverse du nombre de lignes de la date (chaque date totalise le même poids). Il s'agit d'une AUC pondérée sur les observations regroupées, pas d'une moyenne d'AUC quotidiennes parfois non définies. Les gains par fold sont calculés avec la même convention et doivent être strictement positifs pour les folds comptés. L'uplift de précision est la moyenne, à poids égal par date, des écarts de précision entre TOP20 directionnel augmenté et TOP20 directionnel de la baseline, sur la même tâche et population. Le bootstrap rééchantillonne les mois et conserve toutes leurs dates/lignes ; la borne Bonferroni est bilatérale pour chacune des douze comparaisons principales. Aucun seuil n'est retenu après lecture des quatre folds.

## 6. Limites de couverture et de PIT

B5 a montré une population commune représentant seulement 8,5–19,7 % du TOP20 XSHE suivant le semestre, du fait de l'éligibilité à la marge et des variables prix longues indisponibles.

B6 conserve cette baseline complète, sans imputation ni désactivation des protections contre les corporate actions. Toute conclusion sera limitée à cette sous-population. Un résultat ne pourra pas être extrapolé au TOP20 entier, aux actions Shanghai ou à un portefeuille live.

Les retards de disponibilité des archives SZSE restent des proxies. `historical_vintage_proven=false`, `strict_ml_allowed=false` et `production_decision=NEVER_FROM_PROXY_ALONE` sont inchangés.

## 7. Commandes déjà exécutées — historique de reproduction

L'audit et les deux runs sont terminés. **Ne pas relancer ces commandes dans le même dossier** : les artefacts existants sont protégés contre l'écrasement. Pour reproduire, utiliser un dossier de sortie neuf et réaliser d'abord son audit. Depuis `F:\projets`, environnement virtuel activé, les commandes historiques étaient :

2021H1 :

```powershell
python -u -m modelFactory.cn_margin_calendar_15b6 --mode train --test-semester 2021H1 --output artifacts/research/cn_margin_lending/sprint15b6_calendar_v2
```

2021H2 :

```powershell
python -u -m modelFactory.cn_margin_calendar_15b6 --mode train --test-semester 2021H2 --output artifacts/research/cn_margin_lending/sprint15b6_calendar_v2
```

Les deux folds étaient indépendants et ont écrit dans des sous-dossiers distincts, sans changer les tables ni les modèles servant l'application. Leurs rapports et empreintes de prédictions ont été vérifiés en B7.

Suivi de l'achèvement :

```powershell
Get-Content artifacts/research/cn_margin_lending/sprint15b6_calendar_v2/oracle_extension/2021H1/report.json -Raw
Get-Content artifacts/research/cn_margin_lending/sprint15b6_calendar_v2/oracle_extension/2021H2/report.json -Raw
```

Les deux rapports indiquent `OOS_RESEARCH_ONLY` et les fichiers `predictions.parquet` possèdent les empreintes déclarées. Un simple fichier présent n'aurait pas prouvé la fin : le statut et les empreintes ont été vérifiés.

Les modèles sont `model.txt`, les scores `predictions.parquet`, et les rapports `report.json`, sous `oracle_extension/2021H1` et `oracle_extension/2021H2`.

Reproduire l'audit dans un dossier neuf, sans entraînement :

```powershell
python -u -m modelFactory.cn_margin_calendar_15b6 --mode audit --output artifacts/research/cn_margin_lending/sprint15b6_calendar_reaudit
```

Le premier audit exploratoire dans `sprint15b6_calendar` est conservé. Il ne correspond pas à la version finale du service et ne doit pas servir de préflight d'entraînement ; utiliser le dossier `sprint15b6_calendar_v2` référencé ici.

## 8. Tests et suite

**57 tests ciblés passaient au jalon B6**, incluant B6, les non-régressions Oracle 10-B et B1–B5. Contrôle de style réussi. Les tests couvrent la purge, le refus d'un historique trop court ou d'un échantillonnage ayant perdu trop de séances, les doublons, les gaps calendaires, le caractère provisoire du gate de calendrier et le verrouillage du protocole. Avec B7, 62 tests ciblés passent.

Les hashes et bornes ont été vérifiés ; les jointures 2021 aux retards 2/3/5 et les splits directionnels réels ont été produits et audités en [B7](./sprint_15b7_jointures_2021_preflight_directionnel.md). Le constructeur B5 n'a pas été modifié. L'entraînement directionnel demeure une étape distincte.
