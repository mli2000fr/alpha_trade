# Direction D1/D10 — apprentissage exclusivement TOP10 Oracle

## GO et différence avec l'expérience précédente

L'utilisateur précise le 18 octobre 2026 : cible = **les dix premiers titres
prédits par Oracle**, pas TOP10 %, TOP20 % ni TOP50. La campagne précédente
apprenait sur TOP20 % puis évaluait aussi TOP10. Celle-ci filtre **train et
test aux seuls rangs Oracle 1 à 10**. Aucun spécialiste ne reçoit les autres
rangs pour son apprentissage.

Le groupe TOP10 est défini par les scores Oracle OOF historiques et la
confirmation causale de 2024–2026. Ce ne sont jamais les dix plus grands
mouvements réellement connus a posteriori. Un résultat futur inconnu ne
provoque pas de remplacement par le rang 11.

## Protocole figé avant calcul

Configuration : `config/research/us_top10_directional_20261018.json`.
Code : `scripts/research/us_top10_directional_diagnostic.py`.

On réutilise les sources et trajectoires déjà archivées, avec vérification
des empreintes du dossier antérieur. Aucun nouveau téléchargement, SQL,
appel LLM/courtier, PnL ou modèle servi modifié. Les petits modèles ajustés
sont des sondes de recherche conservées hors répertoires de serving.

- Huit features de J et leurs variations sur cinq/dix séances consécutives,
  calculées sur calendrier complet avant le gate Oracle. Même jeu figé que
  la campagne précédente : pas de recherche de fenêtre ou de nouvelles features.
- Six bras : GLOBAL/SECTOR/HIERARCHY × J/PATH. Régression logistique commune,
  correction ridge sectorielle, puis intercept titre régularisé. Paramètres et
  minimums de support conservés, même si le TOP10 laisse peu de titres admissibles.
- Ajustement annuel croissant sur TOP10 à partir de juillet 2018 ; seuls les
  labels disponibles strictement avant l'année test sont appris. Prétraitements
  appris sur le train uniquement. Validation 2022, confirmations 2023 partiel,
  2024, 2025, 2026 partiel jusqu'au 2 septembre.
- D1/D10 restent les déciles **terminaux H20 de l'univers global** déjà figés,
  pas les déciles calculés à l'intérieur des dix, et pas la direction du maximum
  de parcours. Inconnus conservés. Les vingt dates 2026 de couverture globale
  insuffisante de la campagne source ne sont pas réhabilitées artificiellement.
- Tâches pratiques primaires : D10 contre tous les autres déciles et D1 contre
  tous les autres. **Tous les dix titres, y compris D2–D9**, reçoivent un score
  en évaluation. D1 contre D10 seulement reste un diagnostic théorique secondaire.
- Shortlist primaire : **TOP3 parmi les dix**, seuil de recherche fixe pour
  rendre la sélection mesurable. TOP5 et conservation des dix sont des
  sensibilités publiées, jamais un choix rétrospectif du meilleur portefeuille.
  Ce choix n'est pas un nouveau réglage de la production.
- Référence de sélection : les trois premiers dans l'ordre Oracle original.
  Les bras globaux sont comparés à la prévalence constante apprise sur le train
  pour Brier/AUC ; les bras spécialisés au global de la même famille J ou PATH.

## Gates, support et comparaisons multiples

AUC moyenne quotidienne, couverture des dates discriminantes, Brier quotidien,
proportions D1/D10 dans la shortlist avant exclusion des rendements inconnus,
support réel de chaque correction. L'AUC exige deux positifs et deux négatifs
par séance ; les autres dates restent dans les mesures de sélection/Brier et
leur nombre est publié. Ce n'est pas un taux de trades gagnants.

Gate par tâche pratique et bras : validation AUC>=0,53 et gain>=0,01,
Brier amélioré, au moins trente dates, gain de la queue ciblée >=3 points
par rapport aux trois premiers Oracle, **sans augmenter la queue opposée**.
Au moins trois des quatre confirmations doivent passer ces mêmes conditions.
Différences Brier et lift comparées par blocs de 63 séances, au moins vingt
dates/bloc et huit blocs ; 999 sign-flips, correction Holm sur **24 comparaisons**.
Les deux différences doivent être favorables et significatives. Les tests sont
bilatéraux : une dégradation significative n'est pas une preuve d'alpha.

Le minimum de support titre/secteur n'est pas abaissé pour fabriquer des
spécialistes. Un groupe insuffisant revient à la référence ; le rapport donne
les fractions de corrections effectivement appliquées.

## Limites maintenues

Hypothèse TOP10 retenue **après examen de l'expérience TOP20 %** : mêmes
périodes déjà observées, pas nouvelle confirmation indépendante. Secteurs
actuels non PIT, univers courant et prix ajustés non certifiés en vintages.
Peu d'événements indépendants, chemins H20 chevauchants, 2023/2026 partiels.
Même un résultat positif n'autorise pas automatiquement le live ou un PnL.

## Lancement et résultats

```powershell
python -u -m scripts.research.us_top10_directional_diagnostic --output artifacts/research/us_top10_directional/20261018-v1
```

Dossier neuf, protocole et empreintes avant calcul ; `progress.json`,
`top10-population.parquet`, couverture, quinze fichiers de prédictions,
`daily-metrics.parquet`, `daily-selections.parquet`, `training-support.csv`,
`group-evidence.csv`, `summary.csv`, `selection-summary.csv`, `report.json`.
Les sources sont revérifiées en fin de calcul. Archives précédentes intactes.

## Résultat : terminé, pas de filtre promu

Calcul terminé le **18 octobre 2026 à 13:21 Paris**, dossier
`artifacts/research/us_top10_directional/20261018-v1`.
Verdict : **`NO_STABLE_TOP10_DIRECTION`**. Zéro des douze bras/tâches pratiques
franchit les gates fixés. Tous échouent dès la validation 2022. Les paramètres
et fenêtres ne sont pas réoptimisés après ces observations.

### Vérification du périmètre et des protections contre les fuites

- **19 300 couples titre/date, 1 930 séances, 317 titres** ayant été TOP10 ;
  19 051 labels connus. Univers de départ inchangé, 1 790 titres.
- Évaluation 2022–2026 : **10 490 candidats, 1 049 séances, 210 titres**,
  dont 10 288 labels connus. Toutes les séances gardent exactement les
  dix rangs originaux. Aucun apprentissage de rang 11 ou au-delà.
- Quinze fichiers de prédictions contrôlés : clés uniques, dix candidats
  par date, probabilités finies entre zéro et un. Disponibilité maximale des
  labels d'apprentissage strictement antérieure à chaque année test.
- Les vingt journées 2026 avec déciles inconnus restent présentes dans les
  sélections, sans être assimilées à des échecs ni remplacées par d'autres jours.
- Les AUC quotidiennes utilisent 771 séances pour D10/rest, 684 pour D1/rest,
  **465 pour D1/D10** : au moins deux exemples de chaque classe sont requis.
  Brier et proportions de sélection utilisent aussi les autres dates avec
  labels connus. Ne pas annoncer une précision couvrant toutes les séances.
- **51 tests ciblés passent**, dont contrôles du périmètre TOP10, des trous de
  trajectoire, de la causalité et de l'absence de remplacement. Un avertissement
  NumPy connu reste dans l'ancien test synthétique à trop peu de blocs.
- Toutes les empreintes sont revérifiées après calcul. Archives antérieures,
  production, bases, batchs, comptes et fournisseurs inchangés ; aucun PnL.

### AUC moyennes quotidiennes, six bras figés

| Tâche | Global J | Global PATH | Secteur J | Secteur PATH | Hiérarchie J | Hiérarchie PATH |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| D10 contre reste | 0,4957 | 0,5072 | 0,5033 | 0,5125 | 0,5007 | 0,5102 |
| D1 contre reste | 0,5321 | 0,5255 | 0,4983 | 0,5128 | 0,4953 | 0,5093 |
| D1 contre D10, théorique | 0,5059 | 0,5212 | 0,5046 | 0,5260 | 0,5019 | 0,5237 |

Le petit effet D1/rest observé précédemment avec une hiérarchie apprise sur le
TOP20 % ne se renforce pas dans ce test TOP10-only. Les trajectoires améliorent
certains classements moyens, mais la spécialisation et la qualité des
probabilités ne passent pas les critères de stabilité. Une AUC n'est pas un
taux de trades gagnants, ni un rendement de portefeuille.

### Sélection de trois candidats LONG : résultat par année

Présentation du bras **GLOBAL_PATH**, prédéfini avec les autres et non promu.
Ce n'est pas un champion choisi à partir de 2025. Les douze autres colonnes
par année et les sensibilités TOP5/TOP10 restent dans les CSV.

| Année | D10 des trois premiers Oracle | D10 après filtre | D1 des trois premiers Oracle | D1 après filtre |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 30,28 % | 24,17 % | 31,74 % | 35,72 % |
| 2023 partiel | 41,93 % | 42,71 % | 15,62 % | 20,05 % |
| 2024 | 22,22 % | 24,21 % | 25,26 % | 19,18 % |
| 2025 | 29,47 % | 37,87 % | 23,33 % | 14,93 % |
| 2026 partiel | 27,25 % | 29,05 % | 28,15 % | 29,95 % |
| Moyenne par date connue | 29,12 % | 30,52 % | 25,59 % | 23,84 % |

Le gain moyen **+1,40 point de D10** masque un effet surtout favorable en 2025.
2022 se dégrade nettement ; en 2026 la part de D1 augmente également.
Les taux sont des proportions de déciles, pas des probabilités de gain
TP20/SL10. D2–D9 ne sont ni gagnants ni perdants par définition.

### Pourquoi ne pas simplement entraîner des centaines de modèles par titre ?

Le TOP10 limite fortement l'effectif : 8 553 exemples matures pour la référence
pratique testée en 2022, 17 361 pour celle de 2026. Pour D10/rest, seulement
sept titres en 2022 puis vingt en 2026 disposent du support minimal permettant
une correction individuelle lors du test. Les corrections titre concernent
respectivement **2,23 % et 24,17 %** des candidats, sans abaisser les minimums.
La majorité reste donc mutualisée ; démultiplier les modèles ne crée pas de
nouvelles informations et augmenterait le risque de faux champions.

### Décision

Pas de filtre sectoriel/per-symbol ajouté au pipeline, pas de backtest économique
déduit de cette étude, pas de recherche des meilleurs seuils sur 2024–2026.
Cette formulation linéaire régularisée **n'apporte pas de direction TOP10 stable**.
Cela ne démontre pas l'impossibilité de toute méthode ou d'un nouveau corpus
PIT, mais ne justifie pas maintenant d'industrialiser ce filtre.
