# Oracle TOP20 % et univers tradable complet — TP10

Suite distincte : [mêmes candidats et filtres, détention H5/H10/H20 sans
réentraînement](oracle_comparaison_detention_h5_h10_h20_20261019.md).

## Périmètres demandés

Le TOP10 du rapport précédent n'était qu'un contrôle secondaire. Le test principal
portait déjà sur l'univers complet. Cette expérience ajoute explicitement le
**TOP20 % Oracle prédit**, et non vingt titres ni les plus grands mouvements réels.

- **TOP20 %** : à chaque séance, classement de tous les scores disponibles parmi
  les 1 790 titres de `config/univers_batch/univers_filtred_tradable.txt` ; score
  décroissant, symbole alphabétique en cas d'égalité, premiers `ceil(20 % × N)`.
- **Univers complet** : tous les titres du même fichier, sans restriction Oracle.
  Réutilisation exacte des résultats complets TP10 v2, contrôlés par empreintes.

Le classement est figé **avant** de joindre les parcours futurs. Une fenêtre
future manquante n'est jamais remplacée par le rang suivant. Ce fichier est un
univers courant survivant, pas une reconstruction de l'univers historique PIT.

## Prédictions et couverture

Sources des scores : `oracle_extreme_predictions` joint à
`oracle_path_prediction_lineage`, exportées dans une transaction SQL en lecture
seule, protégée par un garde SELECT-only. Aucun appel fournisseur ou LLM.

| Année | Modèle annuel Oracle parcours | Disponible avant le test |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-04 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-04 |
| 2026 | `model-factory-20261014113232-bc35a7` | 2025-12-09 |

Ce sont les mêmes modèles annuels CatBoost que les contrôles TOP10 précédents,
pas un changement de backend ni de nouveaux entraînements. Fold, poids, profil,
date de disponibilité, cible et horizon sont vérifiés ; les labels futurs sont
absents des prédictions. Les vingt premiers rangs reproduisent exactement les
archives de la campagne antérieure, sur les 689 séances, sans différence de score.
Cette traçabilité ne certifie pas indépendamment les versions PIT de toutes les
features historiques, notamment les fondamentaux et la macro.

| Année | Séances scorées | Scores disponibles | Titres scorés par séance | Retenus TOP20 % par séance | Couples retenus avant qualité future | Parcours qualifiés |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 252 | 451 073 | 1 789–1 790 | 358 | 90 216 | 90 216 |
| 2025 | 250 | 447 500 | 1 790 | 358 | 89 500 | 89 479 |
| 2026 jusqu'au 30 septembre | 187 | 332 219 | 1 748–1 790 | 350–358 | 66 476 | 58 926 |

Les 7 550 couples 2026 sans parcours qualifié comprennent les fenêtres non
encore matures à l'observation du 30 septembre ; **pas une omission de pertes**.
Les décisions évaluées vont jusqu'au **1er septembre 2026**. Les deux côtés de
chaque couple qualifié sont évalués, sur exactement les mêmes prix pour les deux
protections. 2024 sert d'historique initial ; résultats de test en 2025 et 2026.
Sept séances 2024 et 108 séances 2026 ont moins de 1 790 scores ; le dénominateur
est le nombre réellement scoré, sans score inventé. Les tests TOP20 % couvrent
148 405 couples qualifiés, sur 811 titres distincts ; le test univers complet
couvre bien tous les 1 790 titres, avec les réserves de qualité décrites dans
son rapport.

Un premier essai technique, conservé dans `20261019-v1`, recalculait les scores
depuis un autre snapshot ancien de features. Il n'a pas reproduit l'intégralité
des rangs enregistrés : **rejeté avant toute évaluation des résultats**. La v2
utilise les prédictions réellement enregistrées, pas un mélange de classements.
Une correction pré-résultats de comparaison de dictionnaires catégoriels est
tracée dans le protocole v2 avec sa version initiale et son empreinte ; aucune
règle de sélection ou de sortie n'a changé.

## Protections et filtre de fiabilité

1. **TP10/SL10** : TP ±10 % dans le sens de la position, SL opposé 10 %.
2. **TP10 sans SL** : même TP, aucun SL, ni perte artificiellement plafonnée.

Pour les deux : entrée open J+1, sortie close de la vingtième séance incluant
l'entrée si aucun seuil n'est touché, sans trailing. Gaps de stop à l'ouverture,
TP à sa limite, collision OHLC stop-first sauf ouverture résolvant l'ordre.
Tolérance relative 1e−12 pour les touches exactes, contrat TP10 v2 inchangé.
Frais hypothétiques : 8 bps par jambe, calculés sur leurs montants respectifs ;
SHORT : emprunt supposé 0,3 % annualisé, pas un coût réel de locate certifié.

Chaque périmètre a sa référence **tous LONG / tous SHORT** et son filtre causal
de fiabilité historique titre/sens : 504 séances passées, maturité intégrale
strictement antérieure à la sélection mensuelle, huit épisodes minimum sans
chevauchement, borne basse Wilson90 du TP supérieure au global passé du même
sens, net positif et supérieur au global, stabilité des deux moitiés historiques.

- Principal TOP20 % : historique et évaluation restreints au TOP20 % Oracle.
- Principal univers complet : historique et évaluation sur l'univers complet.
- Contrôle additionnel : filtre appris sur l'univers complet, évalué dans le
  TOP20 %. Il isole l'effet du périmètre de test de celui de l'historique appris.
- LONG et SHORT séparés ; le choix de sens combiné s'abstient si les deux côtés
  passent. Un titre inconnu ou sans assez d'historique n'est pas admis par défaut.

Les occasions quotidiennes peuvent se chevaucher : contrôles sans chevauchement
et semestriels fournis. Les moyennes sont **par occasion hypothétique après
frictions**, pas un rendement annuel de capital, ni un backtest portefeuille.

## Résultats

**DEUX PÉRIMÈTRES × DEUX PROTECTIONS TERMINÉS. EXPLORATOIRE, PAS DE PROMOTION.**
« Gagnant » ci-dessous signifie `net_outcome > 0`, pas nécessairement TP atteint.
Il s'agit d'une réussite du parcours avec ces sorties, **pas du taux de prédiction
des déciles D1/D10 du rendement final à H20**. Une hausse provisoire peut atteindre
le TP puis être suivie d'une baisse ; aucun classifieur directionnel n'a été ajouté.

### LONG avec filtre de fiabilité propre au périmètre

| Périmètre | Protection | Occasions 2025 / 2026 | Gagnantes 2025 / 2026 | Moyenne nette 2025 | Moyenne nette 2026 |
| --- | --- | ---: | ---: | ---: | ---: |
| TOP20 % Oracle | TP10/SL10 | 3 486 / 2 660 | 58,58 % / 50,30 % | +1,25 % | −0,26 % |
| Univers complet | TP10/SL10 | 22 614 / 19 883 | 52,56 % / 53,01 % | +0,30 % | +0,28 % |
| TOP20 % Oracle | TP10 sans SL | 3 640 / 3 388 | 71,76 % / 65,20 % | +3,11 % | +1,10 % |
| Univers complet | TP10 sans SL | 32 377 / 22 153 | 58,89 % / 61,18 % | +0,87 % | +0,92 % |

Le TOP20 % améliore le résultat apparent 2025, surtout sans SL. Il ne confirme
pas un avantage transversal : TP10/SL10 LONG est négatif en 2026 ; sans SL le
supplément du filtre n'est pas robuste en 2026.

### Références sans filtre de fiabilité : tous les candidats LONG

| Périmètre | Protection | Gagnantes 2025 / 2026 | Moyenne nette 2025 | Moyenne nette 2026 |
| --- | --- | ---: | ---: | ---: |
| TOP20 % Oracle | TP10/SL10 | 54,25 % / 51,98 % | +0,52 % | +0,06 % |
| Univers complet | TP10/SL10 | 52,76 % / 52,13 % | +0,25 % | +0,30 % |
| TOP20 % Oracle | TP10 sans SL | 61,41 % / 62,06 % | +1,01 % | +0,80 % |
| Univers complet | TP10 sans SL | 55,41 % / 55,48 % | +0,52 % | +0,50 % |

Dénominateurs : TOP20 % = 89 479 / 58 926 couples qualifiés en 2025/2026 ; univers
complet = 447 460 / 293 574. Une occasion LONG et une SHORT par couple, pas deux
ordres envoyés au courtier. Pas d'achats répétés simulés avec capital disponible.

### SHORT et choix du sens : pas d'avantage stable

| Périmètre | Protection | Moyenne SHORT filtrés 2025 / 2026 | Moyenne sens choisi 2025 / 2026 |
| --- | --- | ---: | ---: |
| TOP20 % Oracle | TP10/SL10 | −1,38 % / −1,38 % | −0,37 % / −0,83 % |
| Univers complet | TP10/SL10 | −1,33 % / −1,69 % | −0,69 % / −0,54 % |
| TOP20 % Oracle | TP10 sans SL | −2,64 % / −1,48 % | −0,13 % / +0,06 % |
| Univers complet | TP10 sans SL | −1,91 % / −2,22 % | −0,60 % / −0,28 % |

TOP20 % SHORT filtrés : 5 563/2 793 occasions avec SL10 ; 4 600/2 290 sans SL.
Sens choisi TOP20 % : 9 049/5 453 avec SL10 ; 8 120/5 678 sans SL. Certaines
occasions des deux côtés passent sans SL : le bras combiné s'y abstient, donc sa
taille n'est pas nécessairement la somme des deux bras séparés.

### Contrôles qui empêchent de conclure trop vite

Sans chevauchement par symbole/sens (fenêtre complète de vingt séances, pas
réentrée anticipée après un TP), TOP20 % :

| Protection | LONG filtrés 2025 : nombre / moyenne | LONG filtrés 2026 : nombre / moyenne | Tous LONG 2025 / 2026 | Sens choisi 2025 / 2026 |
| --- | ---: | ---: | ---: | ---: |
| TP10/SL10 | 217 / +1,78 % | 198 / +0,86 % | +0,68 % / +0,14 % | −0,73 % / −0,77 % |
| TP10 sans SL | 228 / +3,69 % | 226 / +0,36 % | +1,32 % / +1,29 % | −0,29 % / −1,42 % |

Le signe et l'avantage dépendent donc du traitement des occasions répétées.
En 2026, sans SL, le filtre LONG fait **moins bien** que tous TOP20 % LONG dans
ce contrôle (+0,36 % contre +1,29 %). Ce ne sont toujours pas des portefeuilles.

Différence de moyenne quotidienne appariée LONG filtrés contre tous TOP20 % LONG,
intervalle descriptif bootstrap par blocs de vingt séances :

- SL10 : IC95 inclut zéro en 2025 et 2026.
- Sans SL 2025 : +2,28 points, IC95 [+0,45 ; +3,91] points.
- Sans SL 2026 : +0,24 point, IC95 [−0,96 ; +1,57] points : non confirmé.

Ces intervalles ne corrigent pas les expériences et sélections multiples déjà
réalisées. Résultats semestriels LONG TOP20 % : SL10 +0,93/+1,53 % en 2025 puis
+0,48/−2,78 % en 2026 ; sans SL +1,81/+4,50 % puis +1,57/−0,11 %. Le second
semestre 2026 reste partiel, décisions matures jusqu'au 1er septembre.

Contrôle « même filtre appris sur tout l'univers, appliqué au TOP20 % » :

- SL10 LONG : +0,76/−0,11 % ; sens choisi −0,69/−0,73 %.
- Sans SL LONG : +1,39/+0,81 % ; sens choisi −0,74/−0,45 %.

Le résultat supérieur du filtre TOP20 % propre en 2025 n'est donc pas uniquement
un effet mécanique du sous-ensemble de test : les historiques d'admission sont
différents. Cela ne constitue pas une validation de paramètres optimisés.

### Risque de la variante sans SL

Pour les LONG filtrés TOP20 %, baisse contraire de plus de 10 % **avant la barre
de sortie** dans au moins 34,53 % des cas 2025 et 47,11 % en 2026. Le 95e centile
du mouvement adverse incluant la barre de sortie est 28,24 % / 29,68 %. L'ordre
intrabar étant inconnu, cette seconde mesure est une borne, pas un drawdown réel.

Gain moyen des occasions positives : +9,08 % / +9,36 % ; perte moyenne des autres :
−12,07 % / −14,37 %. Pire occasion dans l'archive : −45,65 % / −50,38 %, sous les
réserves de prix ci-dessous. Le taux gagnant supérieur ne supprime pas le risque.

**Conclusion : le périmètre TOP20 % demandé est désormais testé, mais ni le filtre
de titres ni le choix LONG/SHORT ne sont confirmés stables. Le résultat LONG sans
SL reste exploratoire et ne justifie pas de désactiver les protections en live.**

57 tests unitaires/régressions passent, dont vingt spécifiques au nouveau périmètre.
Audit offline des rangs, populations, maturités, coûts réutilisés, adhésions,
empreintes et références : `final-audit.json`. Les réserves de qualité prix ne
sont pas levées par ces contrôles techniques.

## Reproduction et limites

Script : `scripts/research/us_oracle_top20pct_tp10.py`, phases `prepare`, `score`
(lecture SQL uniquement), `run` (offline). Audit :
`scripts/research/us_oracle_top20pct_tp10_audit.py --output` suivi du dossier.

Dossier : `artifacts/research/us_oracle_top20pct_tp10/20261019-v2/`.
Il conserve les scores complets avec lineage, les TOP20 % figés par année,
la couverture quotidienne, les adhésions mensuelles, évaluations, trois contrôles
de périmètre/historique, coûts et risques, empreintes et protocole.

**Réserve prix/OST héritée** : certaines archives présentent des discontinuités
apparentes d'échelle, dont KLAC, DD, SBS ou TOELY. Les OHLC et identités sont
contrôlés, mais toutes les opérations sur titres ne sont pas indépendamment
qualifiées. Aucune correction, suppression, winsorisation ou exclusion ex post
n'a été appliquée. Sans SL, le risque de grosse perte augmente ; en SHORT les
pertes peuvent dépasser 100 %, sans vrai moteur de marge ni liquidation forcée.

Années déjà explorées, multiples sélections non corrigées et univers survivant :
aucun résultat n'est une confirmation prospective ou une permission de passer
en live sans protections. Aucun SQL écrit, modèle/batch de production modifié,
nouvel entraînement ou ordre.

Rapport antérieur univers complet :
[TP10/SL10 et TP10 sans SL](univers_tradable_tp10_sl10_et_sans_sl_20261019.md).
