# P-PATH-0 — séparabilité du mouvement dominant pendant vingt séances

## Objectif et statut

GO utilisateur du 11 octobre 2026 : comparer les classes fondées sur le résultat
final H20 aux classes fondées sur le mouvement dominant **atteint pendant** les
vingt séances. Audit de recherche uniquement : pas d'entraînement, pas d'écriture
SQL, pas de changement de modèle, de batch, de sélection live ou d'ordre.

Le script de recherche est `scripts/research/us_oracle_dominant_path_audit.py`.
**Terminé** : les résultats sont archivés séparément sous
`artifacts/research/us_dominant_path/ppath0-20261011-v1`.

## Cible figée avant calcul

Depuis la clôture ajustée de J, observer exactement les séances NYSE J+1 à J+20.
J lui-même et J+21 ne participent pas aux extrema. Pour chaque titre :

- `up_excursion = max(0, max(high ajusté futur / clôture ajustée J − 1))` ;
- `down_excursion = max(0, max(1 − low ajusté futur / clôture ajustée J))` ;
- retenir `+up_excursion` si la hausse domine, sinon `−down_excursion` ;
- égalité à 1e−12 près : ambiguë, exclue, sans choix arbitraire.

Exemples : +25 % / −10 % → +25 % ; +25 % / −30 % → −30 %.
Ces valeurs sont des rendements, pas les prix bruts des pics. La conversion
high/low utilise le facteur `adj_close/close` de chaque barre, comme les labels
archivés. Cela neutralise les splits mais n'est pas une certification indépendante
des opérations sur titres ou de la disponibilité historique des ajustements.

Trois cibles sont comparées : rendement final H20, excursion dominante high/low,
et excursion dominante des **clôtures** (sensibilité indépendante des mèches).
Les déciles sont calculés sur le **même univers quotidien complet scoré**, qualifié
et non ambigu pour les trois cibles, avant l'étude dans Oracle × ATR. Le rang suit
la convention existante : `rank(method=max,pct=True)`, puis `ceil(10×rang)`.
Les nouveaux déciles ne sont pas injectés dans `global_oracle_labels`.

## Population et qualité

Archives corrigées et figées de l'expérience numérique Oracle H20 : univers
tradable nettoyé de 1 790 titres, empreinte
`d84c50d7b78a74b98c77431d0ab9b230b8e39e53fa703acdd722bfda8ca3290f`.
Le nombre présent/scoré dépend de la date. Historique OOF disponible de 2020 au
9 juillet 2024 ; confirmation déjà examinée du 2 janvier 2025 au 3 septembre 2026.
Pas de scores inventés pour le second semestre 2024. Le périmètre ne prétend pas
être un univers historique parfaitement PIT, radiés compris.

La sélection Oracle TOP20 % ∩ ATR TOP20 % est figée **avant** lecture des futurs.
Les dix premiers de cette intersection sont également décrits, dans l'ordre du
score Oracle. Aucun titre manquant n'est remplacé par un gagnant connu ensuite.

Qualification : 21 vraies barres J…J20, OHLC valides, volume positif, non remplies,
source/ajustement/identité stables, registre de ruptures respecté, absence de saut
ajusté inexpliqué ×20, rendement final cohérent avec l'archive et disponibilité du
label à la séance suivant J20. Journées exploitables si au moins 95 % de l'univers
scoré possède les trois cibles qualifiées, minimum 20 titres. Couverture et motifs
d'exclusion sont conservés ; un rang partiel n'est pas présenté comme exhaustif.

## Features et comparaison sans entraînement

Toutes les 129 features numériques stockées du profil corrigé sont examinées,
plus le score Oracle. Les 44 rangs cross-sectionnels du profil sont répertoriés
comme alias : pour une AUC calculée **dans chaque date**, un rang monotone conserve
exactement l'ordre et donc l'AUC de la feature source. Ce ne sont pas 44 sources
d'information indépendantes supplémentaires.

Familles : prix, momentum, volatilité, ATR, moyennes mobiles, volumes, régimes
SPY, force relative, CAPM, interactions, z-scores roulants et dynamiques.
`selector_short_score` reste un diagnostic réservé : disponibilité PIT non
certifiée, exclusion de la sélection des pistes. Les constantes sont conservées
avec AUC 0,50, pas transformées en signal artificiel.

News/sentiment, consensus, fondamentaux et VIX/VXN/VIX3M/MOVE ne sont **pas**
présents dans ces archives : aucun verdict sur ces familles n'est revendiqué ici.

Tâches : D1 contre D10 ; D10 contre le reste ; D1 contre le reste ; signe dominant
sur tout le pool. Mesure principale : moyenne des AUC **intra-date**, dates à poids
égal, minimum cinq observations par classe. Une feature macro identique pour tous
les titres à J ne peut pas discriminer les titres dans cette date ; une AUC groupée
sur plusieurs années risquerait de confondre régime de marché et choix du titre.

Développement 2020–2022, seulement les labels disponibles strictement avant le
3 janvier 2023 : figer le sens de chaque feature (+ ou −). Ne pas inverser son sens
après examen de 2025/2026. Confirmation par année 2023, 2024 partielle, 2025, 2026
partielle. Intervalles descriptifs par bootstrap en blocs de vingt séances, 500
répétitions seed 42, et sensibilité une date sur vingt-et-une. Ce ne sont pas des
preuves de significativité ajustées pour les comparaisons multiples.

Présélection de dix features **distinctes** uniquement sur le développement pour
D1/D10 parcours, excluant les alias et `selector_short_score`. Filtre descriptif
figé : AUC ≥0,53, borne basse >0,50, au moins 60 dates, dans chacune des quatre
périodes de confirmation. Un passage n'autorise ni production ni trading ; une
nouvelle confirmation et un protocole multivarié sont nécessaires.

Sensibilité supplémentaire : exclure les chemins comprenant `high/low >=1,5`,
recalculer tous les déciles sur le nouvel univers complet apparié, puis garder les
orientations déjà figées. Une grande plage n'est pas automatiquement un prix faux.

## Suivi et reprise

```powershell
python -u -m scripts.research.us_oracle_dominant_path_audit --output artifacts/research/us_dominant_path/ppath0-20261011-v1
Get-Content artifacts/research/us_dominant_path/ppath0-20261011-v1/progress.json
```

Les prix et chemins sont archivés par 25 symboles, les AUC par année, avec hashes.
Relancer la même commande reprend les fichiers validés ; un protocole ou code
différent exige un nouveau répertoire. `report.json` est produit uniquement une
fois les contrôles et sensibilités terminés. Les lectures SQL sont réalisées en
transactions READ ONLY. Aucun appel fournisseur ou LLM payant.

## Portée et suite

Un titre atteignant +25 % puis finissant −1 % peut changer de classe. Cela ne dit
pas si une feature disponible à J pouvait le prévoir, si un stop aurait été touché
avant, ou si le pic était vendable. Pas de TP/SL, sizing ou PnL dans cet audit.

Les gains en pourcentage peuvent dépasser +100 %, alors qu'une baisse depuis un
prix positif est bornée à −100 %. Cette asymétrie peut rapprocher certaines
features de volatilité de `D10_parcours` sans en faire un indicateur fiable du
signe sur tout le pool. C'est pourquoi la tâche de signe dominant est conservée
séparément de D1/D10. Une meilleure AUC entre deux queues n'implique pas que l'on
sache éviter les baisses parmi tous les candidats.

L'utilisateur a aussi soulevé l'idée d'entraîner un **Oracle parcours**. C'est une
expérience distincte : changer la cible de l'Oracle, garder features, folds et
algorithme comparables, puis mesurer la capture des amplitudes atteintes. Aucun
tel entraînement n'est lancé dans P-PATH-0. Les anciennes expériences H20 ne sont
ni invalidées ni automatiquement reproduites. 2025/2026 ne sont plus un holdout
vierge ; toute piste devra être confirmée prospectivement.

## Résultats terminés — 11 octobre 2026

Rapport : `artifacts/research/us_dominant_path/ppath0-20261011-v1/report.json`.
Verdict : **NO_STABLE_UNIVARIATE_DOMINANT_PATH_SEPARATION**. Ce verdict porte sur
les features individuelles archivées, **pas** sur un modèle multivarié nouvellement
entraîné, ni sur toutes les familles de données de l'application.

- 2 743 313 observations titre/date, 1 790 titres, 1 555 dates scorées ;
- 2 733 673 chemins qualifiés, soit 99,65 % ;
- 2 728 464 observations appariées non ambiguës pour les trois cibles ;
- 419 168 observations dans Oracle × ATR, sur 1 533 dates exploitables ;
- 174 entrées examinées : 129 features stockées + score Oracle + 44 alias de rang ;
- 41 tests ciblés passent ; 17 empreintes de sorties vérifiées ; 100 chemins réels
  comparés au calcul indépendant précédent ; unicité des clés et alias vérifiés.

### Changement des labels dans Oracle × ATR

Chaque ligne utilise les observations appariées de l'année. « D1/D10 conservé »
est calculé parmi les anciens D1/D10 H20, après recalcul de leur décile sur le même
univers qualifié que le parcours. Ce n'est pas la précision d'un modèle.

| Année | Observations évaluées | Signe changé | Anciens D1 restant D1 parcours | Anciens D10 restant D10 parcours |
|---|---:|---:|---:|---:|
| 2020 | 68 218 | 14,57 % | 81,35 % | 88,89 % |
| 2021 | 71 669 | 15,60 % | 87,81 % | 91,00 % |
| 2022 | 72 446 | 16,13 % | 87,53 % | 87,15 % |
| 2023 | 67 888 | 14,59 % | 83,43 % | 90,47 % |
| 2024 jusqu'au 09/07 | 34 549 | 15,72 % | 86,58 % | 89,42 % |
| 2025 | 65 921 | 14,61 % | 86,05 % | 90,04 % |
| 2026 partielle | 38 477 | 15,07 % | 88,46 % | 87,94 % |

La nouvelle cible change réellement le diagnostic, mais **la majorité des deux
queues reste la même** : on ne repart pas d'un problème totalement différent.

### Séparabilité : exemples et absence de stabilité

AUC D1 contre D10 du parcours, moyenne intra-date ; le sens de chaque feature est
figé sur le développement 2020–2022. 0,50 signifie aucune discrimination.

| Feature / sens figé | 2023 | 2024 partielle | 2025 | 2026 partielle |
|---|---:|---:|---:|---:|
| Score Oracle, élevé | 0,5360 | 0,4845 | 0,5321 | 0,4929 |
| ATR20 %, élevé | 0,5316 | 0,4997 | 0,5357 | 0,4996 |
| Volatilité 60 séances, élevée | 0,5307 | 0,4895 | 0,5360 | 0,4898 |
| R² CAPM 252, faible | 0,4934 | 0,5360 | 0,4886 | 0,4952 |
| Momentum 60 séances, faible | 0,5452 | 0,5268 | 0,4881 | 0,4736 |

Les dix pistes présélectionnées sans consulter 2023–2026 sont : R² CAPM,
momentum250 z-score, distance SMA250 z-score, écart SMA50/SMA200,
distance SMA200 z-score, alpha CAPM, momentum252 relatif au marché,
volatilité120 z-score, écart SMA20/SMA50, score Oracle. **Zéro sur dix** passe
le filtre de confirmation fixé. Les résultats de toutes les autres features
restent disponibles dans `feature_auc_annual.parquet` et `feature_auc_daily.parquet`.

Il existe des associations propres à une période : l'interaction
`relative_strength_20_times_market_trend` atteint 0,5539 en 2026, mais seulement
0,4985 / 0,4796 / 0,5147 en 2023 / 2024 / 2025. La choisir après lecture de 2026
serait une nouvelle hypothèse exploratoire, pas une confirmation réussie.

La tâche de **signe dominant sur tout le pool** ne résout pas davantage le
problème : ATR20 vaut 0,5231 en 2025 et 0,4935 en 2026 ; score Oracle
0,5171 puis 0,4925. Ce n'est pas un taux de réussite de trading.

### Sensibilités et réserves de couverture

Pour D1/D10 parcours, après exclusion des chemins contenant une plage high/low
≥1,5 et recalcul des déciles : score Oracle 0,5318 / 0,4932 en 2025 / 2026 ;
ATR 0,5347 / 0,5003 ; volatilité60 0,5356 / 0,4902. L'absence de stabilité de
ces repères n'est donc pas créée uniquement par quelques mèches extrêmes.

Avec les seuls extrema de **clôture**, les AUC D1/D10 restent instables : score
Oracle 0,5310 / 0,4897, ATR 0,5386 / 0,4945 en 2025 / 2026. Les résultats
une date sur vingt-et-une et les intervalles en blocs sont archivés ; leurs
effectifs sont plus faibles et ils ne constituent pas une nouvelle optimisation.

22 journées échouent au seuil de 95 % de couverture quotidienne : les 21 séances
du 20 mai au 18 juin 2026, puis le 3 septembre 2026. La qualification stricte des
barres futures rejette certains chemins ; les labels H20 archivés du 3 septembre
sont non qualifiés/manquants, **ce n'est pas une affirmation que cette date serait
encore immature au 11 octobre**. Aucun label ou prix n'a été réparé dans cet audit.
En 2026, seuls 86,22 % des candidats sélectionnés entrent donc dans le comparatif,
contre environ 99,8 % en 2021–2025 : ne pas présenter l'année comme exhaustive.

Les motifs de réservation sont stockés par observation et dans le rapport.
Les 2 446 égalités high/low et 2 849 égalités sur les clôtures sont exclues ; leurs
ensembles peuvent se recouper. Les anciennes classes archivées sont conservées,
et leur différence avec le recalcul apparié reste mesurable séparément.

### Décision et suite bornée

Pas de promotion directionnelle, pas de nouvelle sélection live, pas de backtest
économique. Ces résultats ne justifient pas de reproduire automatiquement toutes
les expériences mathématiques ou per-symbol sur cette cible.

La question de l'utilisateur sur un **Oracle entraîné pour le parcours** reste
pertinente et distincte : un détecteur d'amplitude H20 finale n'a pas été entraîné
explicitement pour capturer les maxima intermédiaires. La suite éventuelle doit
comparer les deux contrats sur les mêmes features/folds et mesurer leur capture
des grandes excursions, avant de confondre détection d'amplitude et direction.
Un modèle multivarié directionnel constituerait aussi un test distinct, pas un
résultat déjà obtenu ici. Aucun de ces entraînements n'a été lancé.

Suite autorisée le 11 octobre : [mode d'entraînement Oracle parcours H20](oracle_path_training.md)
implémenté avec checkbox Pipeline et artefacts séparés. Aucun entraînement de
campagne réelle lancé ; cela ne modifie pas le verdict directionnel ci-dessus.
