# TOP10 Oracle — essai CatBoost trois classes, configuration unique

## Décision et différence réelle

GO utilisateur du 18 octobre 2026. Essai de recherche borné, sans modification
de l'Oracle ou du serving, sans SQL, fournisseur, LLM, ordre ou calcul de PnL.
Ce n'est pas une nouvelle information financière : CatBoost a déjà été essayé
ailleurs. Le contrat précis ici est **train et test exclusivement TOP10 causal,
trois déciles agrégés, classement P(D10)−P(D1)**.

Configuration figée : `config/research/us_top10_catboost_multiclass_20261018.json`.
Code : `scripts/research/us_top10_catboost_multiclass.py`.

## Données et cible

Archives de `us_top10_directional/20261018-v1`, sources et empreintes vérifiées
en chaîne jusqu'à l'Oracle d'origine. La population TOP10 archivée est confrontée
à sa reconstruction depuis le dossier parent. Ni nouveau prix ni nouveau
score Oracle ; les modèles et prédictions des campagnes précédentes restent intacts.

Trois classes : `0=D1`, `1=D2…D9`, `2=D10`. D1/D10 restent les déciles du
rendement **terminal H20 global**. Ni dix plus grands mouvements futurs, ni
déciles calculés parmi les dix, ni signe de l'excursion pendant vingt séances.
Tout candidat des déciles centraux est présent au train et au test. Un label
inconnu reste inconnu, jamais une perte ou un motif de remplacement par le rang 11.

Les huit features de J et leurs différences depuis J−5 et J−10 forment
**24 colonnes**, calculées sur calendrier complet avant sélection Oracle.
Pas d'identifiant ticker, de secteur ou de nouveau corpus pour mémoriser les titres.

## Un seul essai non linéaire, références équivalentes

- CatBoost : MultiClass, profondeur **3**, **200** itérations, learning rate
  **0,03**, L2 **10**, seed **20261018**, deux threads, pas d'early stopping,
  pas de grille de paramètres, pas de calibration ou refit sélectionné sur test.
- Régression logistique **également à trois classes**, mêmes données et
  prétraitements : elle isole l'effet non linéaire du changement de cible/score.
- Ancien filtre logistique binaire D10/rest PATH, dont chaque année est
  réajustée uniquement pour vérifier la reproduction des anciennes probabilités
  à 1e-10. Pas un candidat supplémentaire à optimiser.
- Ordre Oracle originel, sans filtre directionnel, conservé comme témoin.

Les deux nouveaux modèles utilisent le score **P(D10)−P(D1)**. Les probabilités
sont archivées séparément ; elles doivent être finies, dans [0,1], de somme un,
avec contrôle explicite de l'ordre des classes. Le score n'est ni une probabilité
de gain ni un rendement prévu.

## Horloge et sélection

Ajustement annuel croissant, à partir des observations OOF de juillet 2018,
avec tous les labels d'entraînement disponibles **strictement avant** janvier
de l'année évaluée. Validation 2022 ; confirmations 2023 partielle, 2024, 2025,
2026 partielle jusqu'au 2 septembre. La validation n'est passée à aucune API
de fit CatBoost. Prétraitements appris sur le train et sauvegardés.

Shortlist primaire : trois parmi les dix, score décroissant et rang Oracle
original en cas d'égalité ; cinq/dix sont des sensibilités, pas un choix après
observation. Toutes les shortlists sont fixées avant examen des résultats futurs.

**Comparaisons primaires sur les mêmes dates où les dix labels sont connus**,
pour ne pas comparer des sélections évaluées sur des dénominateurs différents.
Ce masque ne modifie ni scores, ni prédictions, ni shortlists ; toutes les dates
incomplètes sont archivées séparément. C'est une mesure conditionnelle à la
couverture future, pas une règle d'entrée live ni une réparation des trous.

## Mesures, gates et multiplicité

AUC quotidienne du score pour D10/rest, du score inversé pour D1/rest, et
théorique D1/D10 ; au moins deux exemples par classe/date, dates exclues publiées.
Proportions de D1/D10 des trois sélectionnés ; Brier **à trois classes**, somme
des trois erreurs quadratiques, et logloss/accuracy. Ne pas comparer directement
ce Brier3 au Brier binaire des anciennes expériences.

Gate CatBoost : validation AUC D10/rest >=0,53, gain >=0,01 contre logistique
trois classes, Brier3 amélioré, D10 +3 points contre ordre Oracle, D1 non augmenté,
gain D10 positif contre les deux références logistiques, au moins trente dates.
Au moins trois des quatre confirmations passent les mêmes conditions.
Quatre comparaisons par blocs (Brier3/linéaire, D10/Oracle, D10/ancienne logistique,
D10/logistique trois classes), 63 séances, au moins vingt dates/bloc et huit
blocs, 999 sign-flips, Holm sur les quatre, p<=0,05 et effet favorable requis.
Une différence défavorable significative ne constitue pas un avantage.

## Limites et non-promotion

Mêmes années déjà examinées après plusieurs choix de recherche : **pas de
holdout indépendant**. Univers actuel et prix ajustés non certifiés en vintages.
2023 s'arrête au 7 juillet ; 2026 au 2 septembre et comporte vingt dates sans
déciles qualifiés. Événements H20 chevauchants et titres répétés, blocs approximatifs.
Un résultat positif permettrait seulement une confirmation future, pas le live.

## Exécution

```powershell
python -u -m scripts.research.us_top10_catboost_multiclass --output artifacts/research/us_top10_catboost_multiclass/20261018-v1
```

Modèles et prédictions locaux par année dans un dossier de recherche, jamais
dans `artifacts/models`. Protocole, prétraitements, contrôles de reproduction,
mesures quotidiennes, résultats par année, empreintes avant/après et progression.

## Résultat : terminé, pas de filtre promu

Calcul terminé le **18 octobre 2026 à 14:44 Paris** :
`artifacts/research/us_top10_catboost_multiclass/20261018-v1`.
Verdict **`NO_STABLE_CATBOOST_TOP10_DIRECTION`**. Validation 2022 rejetée,
zéro confirmation franchissant tous les critères, gate statistique non franchi.
Pas de nouvel essai de paramètres, de choix de seuil, de backtest ou de promotion.

### Reproduction et audit des artefacts

- Exactement **dix candidats originaux par séance**, tous déciles inclus ;
  population totale 19 300 lignes / 1 930 séances, dont 10 490 lignes en test
  2022–2026. La comparaison primaire couvre **1 027 dates complètes**, soit
  **3 081 sélections** par bras pour la shortlist de trois.
- Deux dates 2022 partiellement inconnues et vingt dates 2026 entièrement
  inconnues ne participent pas aux comparaisons primaires. Toutes restent dans
  les prédictions/shortlists archivées. Pas de remplacement ni de zéro inventé.
- Cinq CatBoost, un par année d'ajustement causal, **200 arbres chacun** selon
  le même réglage. Pas de données test ou validation passées à `fit`.
- Cinq anciens filtres logistiques reproduits avec **écart maximal zéro**.
  Les cinq modèles CatBoost enregistrés ont été rechargés ; prétraitements et
  probabilités reproduits sur trente candidats de chaque année à 1e-12.
- Probabilités des trois classes finies, dans [0,1], de somme un ; ordre des
  classes explicitement contrôlé et score stocké égal à P(D10)−P(D1).
- **80 tests ciblés passent**, dont un petit fit CatBoost réel ; un avertissement
  connu du précédent test de blocs NumPy est conservé. Empreintes des sources
  et de tous les artefacts du manifeste revérifiées.
- Modèles enregistrés seulement sous `artifacts/research`, aucun artefact de
  serving, batch, table, compte ou protection modifié. Zéro coût API.

### D10 dans les trois titres sélectionnés, mêmes dates pour tous les bras

| Période | Ordre Oracle | Ancien filtre D10 | Logistique trois classes | CatBoost trois classes |
| --- | ---: | ---: | ---: | ---: |
| 2022, 249 dates complètes | 30,25 % | 24,36 % | 23,96 % | 24,50 % |
| 2023 partiel | 41,93 % | 42,71 % | 40,36 % | 39,84 % |
| 2024 | 22,22 % | 24,21 % | 23,15 % | 24,07 % |
| 2025 | 29,47 % | 37,87 % | 35,87 % | 35,47 % |
| 2026 partiel | 27,25 % | 29,05 % | 30,41 % | 28,83 % |
| Moyenne par date complète | **29,11 %** | **30,57 %** | **29,63 %** | **29,60 %** |

Les légères différences de moyenne avec le rapport précédent viennent des
**mêmes dates complètes imposées ici à tous les bras**, pas d'un recalcul ou
d'une modification des anciennes probabilités. En 2022, l'ancien rapport
utilisait aussi deux journées dont certaines issues étaient inconnues.

CatBoost ne dépasse pas la logistique équivalente en concentration moyenne de
D10, et reste derrière l'ancien filtre D10/rest. L'architecture non linéaire
ne valide donc pas l'avantage recherché sur ce périmètre.

### D1 dans ces mêmes sélections

| Période | Ordre Oracle | Ancien filtre D10 | Logistique trois classes | CatBoost trois classes |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 31,86 % | 35,61 % | 36,14 % | 32,00 % |
| 2023 partiel | 15,62 % | 20,05 % | 18,23 % | 21,88 % |
| 2024 | 25,26 % | 19,18 % | 22,35 % | 23,02 % |
| 2025 | 23,33 % | 14,93 % | 14,40 % | 16,00 % |
| 2026 partiel | 28,15 % | 29,95 % | 24,55 % | 23,87 % |
| Moyenne par date complète | **25,61 %** | **23,79 %** | **23,56 %** | **23,47 %** |

CatBoost réduit légèrement D1 en moyenne, et notamment en 2026. Mais il
ne domine pas uniformément les références : sélectionner moins de D1 et
moins de D10 simultanément ne prouve pas un portefeuille plus rentable.

Effectifs agrégés sur 3 081 sélections par bras : Oracle **897 D10 / 789 D1**,
ancien filtre **942 / 733**, logistique trois classes **913 / 726**, CatBoost
**912 / 723**. Le même titre peut être sélectionné plusieurs journées ; ces
effectifs ne sont ni des titres uniques ni des trades réellement exécutés.

### Probabilités et tests de confirmation

Brier3 moyen sur toutes les dates primaires : CatBoost **0,65485**, logistique
trois classes **0,65556**, prévalence constante apprise sur le train **0,65156**.
Plus faible = meilleur. CatBoost améliore modestement la logistique, mais pas
ce témoin constant agrégé, qui ne sait pourtant pas classer les titres.

Sur les confirmations 2023–2026, l'amélioration Brier3 contre la logistique est
significative dans ce test par blocs (p Holm **0,036**). Mais le gain de D10
contre Oracle n'est plus significatif après correction (**0,126**) ; le gain
contre l'ancienne logistique est négatif (**−1,33 point**, p **0,382**) et celui
contre la logistique trois classes également (**−0,21 point**, p **0,818**).
Ces moyennes de confirmation ne sont pas les moyennes incluant la validation 2022.

La meilleure AUC conditionnelle D1/D10 de CatBoost en 2025 (**0,6072**) ne
constitue pas une précision de 60,72 %, et ne suffit pas : elle ne considère
que les deux queues réelles et ne résout pas la sélection parmi D2–D9.
L'AUC D10/rest de CatBoost reste **0,4219 / 0,5323 / 0,4804 / 0,5372 /
0,5144** sur 2022/2023/2024/2025/2026, respectivement.

### Conclusion bornée

Essai clos : ce CatBoost trois classes sur ces 24 features n'apporte pas de
gain TOP10 stable justifiant une intégration ou un replay économique.
Ne pas choisir uniquement 2025, optimiser le nombre de titres, chercher une
autre profondeur ou inverser le score après observation. Le résultat ne prouve
pas l'impossibilité d'un signal avec de nouvelles données PIT ; il ferme
seulement cette formulation et cette configuration.
