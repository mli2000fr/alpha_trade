# Trois expériences séparées — Oracle TP20/SL10

## Autorisation et limites

GO utilisateur du 13 octobre 2026, modèle
`model-factory-20261012183840-6d6569`. La piste de réduction progressive
d'exposition est rejetée : elle n'est pas appliquée ici.

La baseline `artifacts/research/us_oracle_tp20_sl10_new/20261012-v6` reste
immuable, neuf portefeuilles achevés et audités. La nouvelle campagne est
`artifacts/research/us_oracle_challengers/20261013-v2`.
Elle utilise exactement ses scores, prix corrigés, macro et lifecycle.
Seuls les modèles auxiliaires de recherche sont entraînés ; l'Oracle
original, le live, les batchs et les données SQL ne sont pas modifiés.
Aucun appel réseau ou ordre courtier n'est nécessaire.

## Protocole figé avant apprentissage

- Stratégie LONG de baseline, TOP10 primaire, TOP20 et TOP50 secondaires.
- Capital 4 000 USD réinitialisé pour chaque année et chaque cas.
- Tests 2024, 2025, 2026 jusqu'au 3 septembre avec queue de dénouement.
  2026 n'est pas une année complète ; ces tests ont déjà été observés.
- Exemples issus des TOP50 Oracle hors échantillon 2018–2022, classés
  avant examen du futur. Fit jusqu'en 2021, validation 2022.
- Purge selon disponibilité de **tous** les résultats nécessaires,
  y compris l'ouverture de la 21e séance détenue ; jamais selon la seule
  date de décision. Les résultats 2024–2026 n'entrent pas dans le training.
- Features fixées disponibles dans le contrat archivé : momentum20/60/120,
  force relative20/60, volatilité20/60, ATR20, RSI14, volume relatif20,
  rendement/volatilité/tendance SPY et scores LONG/SHORT d'entrée.
  Drawdown20 et position dans le range20 figuraient parmi les candidats du
  protocole préparatoire, mais sont absents du profil de serving de cette
  baseline ; ils sont écartés selon la règle de disponibilité préparée,
  avant tout entraînement ou résultat, sans inventer de données de test.
- Petits arbres LightGBM, seed731, profondeur3, 7 feuilles, learning rate0,03,
  maximum150 itérations, early stopping15 sur 2022 seulement.
- Labels de trades unitaires avec coûts plats approximés ; ce ne sont
  pas des PnL de portefeuille. Les comparaisons financières proviennent
  du moteur de replay avec capital, coûts, risques et positions.
- Les trois expériences sont **indépendantes** et lancées successivement.
  Un échec technique ou d'audit bloque la suivante ; un résultat négatif
  n'est pas corrigé en réglant les seuils sur les pertes de test.

### 1. Filtre d'entrée

Prédire la probabilité qu'un trade TP20/SL10 gagne net des coûts unitaires.
Seuil fixe0,50, appliqué après sélection TOPN. Aucun remplacement par le
rang N+1. TP20, SL10 dur, absence de trailing, durée20 séances et sizing
natif de baseline restent identiques.

### 2. Modèle quotidien de sortie

Après survie aux stops/TP intraday, prédire l'avantage de conserver la
position jusqu'à sa sortie de référence plutôt que vendre au prochain open.
Si cet avantage prédit est négatif : sortie **totale**, au prochain open.
Pas de réduction progressive. SL10 reste dur et TP20 reste actif.

État observé à la clôture : âge, PnL, MFE/MAE, distances SL/TP et features
du jour. Les scores Oracle sont ceux de l'entrée, pas des prédictions futures.
Une observation longue n'est pas artificiellement comptée comme vingt trades :
poids unitaires répartis sur ses états d'apprentissage.

Priorité de replay : événements et expiration, protections à l'open,
transitions natives de régime, puis sortie apprise. Un stop déjà touché
ne peut pas être annulé par le modèle. Les ordres différés et les scores
d'entrée suivent le lot d'origine à travers le changement de ticker.
Les features de la queue septembre/octobre sont calculées causalement sur
les archives locales corrigées ; le préfixe du prédécesseur n'est raccordé
au successeur que dans cette lignée qualifiée en mémoire, sans insertion SQL.

### 3. TP/SL personnalisés avec sizing

Trois couples figés : TP10/SL7, TP20/SL10, TP25/SL10. Choisir à J le profil
avec le meilleur rendement unitaire net/SL **prédit**, pas celui qui aurait
réellement gagné dans le futur. Profil conservé pendant toute la vie du lot.
Les barrières sont ancrées au fill J+1 puis suivent les conversions qualifiées.

Quantité plafonnée par le budget de risque natif divisé par
`close_J × SL × 1,03`, sans augmentation au-delà des approbations natives.
Risque au fill vérifié ; les gaps de sortie peuvent dépasser le SL.
Un contrôle supplémentaire TP20/SL10 avec la même règle de sizing est
calculé avant l'expérience pour distinguer sizing et personnalisation.

## Contrôles et résultats à remettre

59 tests ciblés passent après remédiation technique : chronologie, purge, absence de
future feature, SL d'abord sur collision/gap, conversion du ticker,
profil du lot conservé, quantité et cash. Les chemins d'apprentissage
non qualifiés sont exclus avec motifs ; les chemins détenus de test
inconnus font échouer le replay, jamais disparaître un perdant.

Neuf replays par expérience et neuf pour le contrôle de sizing :
36 au total, sans réexécuter les neuf baselines. Plusieurs cas peuvent
être calculés en parallèle **au sein** d'une expérience, jamais les
trois expériences simultanément. Progression et reprise par chunk/cas.

Après chaque étape : vérification des neuf cas, candidats d'origine,
protections, portefeuille entièrement clos, cash et empreintes. Comparer
capital final, gains/pertes, taux gagnant/perdant, DD maximal, rendement,
nombre de trades, activité sacrifiée et écarts à la baseline.
Les résultats sont dans `comparisons.json` et `comparisons.md`.
Un taux gagnant plus élevé avec presque aucune activité n'est pas une
preuve de meilleur rendement. Aucune promotion automatique.

Réserves inchangées : univers statique de survivants, secteurs actuels
non PIT acceptés, prix ajustés rétrospectifs fournisseur, vintages macro
non certifiés, protections/corporate actions simulées et exécutabilité
OTC historique non démontrée. Pas de certification de parité broker LIVE.

## Suivi

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_challengers\20261013-v2\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_challengers\20261013-v2\fit-data\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_challengers\20261013-v2\stderr.log -Tail 20
```

Lancement/reprise, uniquement si aucun autre writer n'utilise cette racine :

```powershell
python -u -m scripts.research.us_oracle_challengers_v2 --output artifacts/research/us_oracle_challengers/20261013-v2 --workers 3
```

Un changement de code, d'inputs, de configuration ou d'hypothèse exige une
version distincte, pas un écrasement des résultats déjà qualifiés.

Statut : filtre d'entrée v1 terminé, aucune entrée avec le seuil figé0,50 ;
pas un gain exploitable. Les neuf cas ont été audités. La sortie quotidienne
v1 a correctement bloqué la suite : les cas2026 TOP10 et TOP50 ne disposaient
pas des features de la queue après le3septembre ; le TOP20 ne détenait plus de
position nécessitant ces features. Une erreur d'alignement d'index
dates/prix SPY vidait cette queue dans le calcul offline. Les v1 et leurs
sources restent conservées ; aucune conclusion économique sur les cas2026
échoués et aucun entraînement de la troisième expérience en v1.

V2 ne modifie que cet alignement dans une fonction de recherche séparée et
rejette explicitement une queue vide. Un test par préfixe prouve que tronquer
le futur ne change pas les features ; des canaris avant la queue les comparent
aux archives de baseline. Les labels OOF de v1 sont repris avec empreintes,
les mêmes heads sont entraînés avec les mêmes paramètres et les replays
relancés séparément. Aucun seuil, profil, année ou objectif n'est modifié.

Le premier précontrôle a arrêté le lancement avant tout calcul pour les
deux extras absents ; le contrat est limité aux treize features disponibles.

## Résultats définitifs — 36 nouveaux replays terminés et audités

V2 : neuf cas par expérience et neuf contrôles de sizing, **zéro échec**.
Statut final `COMPLETED`, revue technique `THREE_CHALLENGERS_VERIFIED`.
Modèles d'apprentissage : 37 551 exemples d'entrée fit et9 617 validation ;
366 851 états quotidiens fit et74 074 validation. Labels disponibles au plus
tard le31décembre2021 /30décembre2022 respectivement. Aucun label2024–2026
utilisé pour l'apprentissage ou la sélection d'itération.

Le filtre refuse **tous** les candidats de test au seuil figé0,50 :
probabilités0,4121 à0,4286, AUC de validation2022 =0,50021, meilleure
itération1. Les neuf comptes restent à4 000USD, sans trade. Aucun signal
discriminant utile démontré ; les pertes évitées par inactivité ne prouvent
pas qu'il sait choisir les gagnants. V2 reproduit les mêmes poids que v1.

La sortie quotidienne est terminée et auditée sur neuf cas. TOP10 primaire :

| Année | Baseline rendement | Sortie quotidienne | DD baseline → sortie | Gagnants baseline → sortie | Positions baseline → sortie |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | −2,26 % | −2,01 % | −11,01 → −7,11 % | 37,97 → 45,87 % | 158 → 460 |
| 2025 | −12,01 % | +4,96 % | −17,45 → −6,74 % | 32,97 → 45,89 % | 91 → 353 |
| 2026 partiel | +28,71 % | +1,83 % | −8,66 → −6,44 % | 51,43 → 45,40 % | 140 → 337 |

Sorties anticipées effectivement exécutées442/334/309 sur ces TOP10,
sans annuler le SL10. L'activité change fortement : libérer un slot permet
d'autres entrées ; ce n'est pas le rendement des mêmes trades seulement
raccourcis. Les coûts des nouveaux allers-retours sont inclus.
Sur TOP20/TOP50, 2024 bascule respectivement de+16,44 % à−14,12/−13,09 %,
2025 de−7,03/−6,05 % à+4,91/+6,10 %, 2026 de+21,43 % à+7,14/+8,70 %.
Amélioration2025, mais gros gains sacrifiés ailleurs : pas de supériorité
robuste sur ces trois périodes, ni raison de promouvoir automatiquement.

Les poids du filtre et de la sortie sont identiques bit pour bit entre v1
et v2 : la réparation porte uniquement sur la queue de features externes.

### TP/SL personnalisés : résultat complet

| Année | TOP | Capital final $ | Gains $ | Pertes $ | Gagnants % | DD max % | Rendement % | Baseline % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 10 | 4568,93 | 3564,48 | −2995,55 | 49,44 | −8,06 | +14,22 | −2,26 |
| 2024 | 20 | 4568,29 | 3805,15 | −3236,87 | 48,24 | −6,17 | +14,21 | +16,44 |
| 2024 | 50 | 4568,29 | 3805,15 | −3236,87 | 48,24 | −6,17 | +14,21 | +16,44 |
| 2025 | 10 | 3510,71 | 1066,46 | −1555,75 | 35,97 | −16,55 | −12,23 | −12,01 |
| 2025 | 20 | 3513,03 | 1442,02 | −1928,99 | 38,14 | −19,25 | −12,17 | −7,03 |
| 2025 | 50 | 3594,32 | 1834,23 | −2239,91 | 40,16 | −17,92 | −10,14 | −6,05 |
| 2026 partiel | 10 | 4226,72 | 2723,67 | −2496,95 | 45,53 | −5,84 | +5,67 | +28,71 |
| 2026 partiel | 20 | 4090,73 | 2790,02 | −2699,29 | 43,58 | −12,38 | +2,27 | +21,43 |
| 2026 partiel | 50 | 4090,73 | 2790,02 | −2699,29 | 43,58 | −12,38 | +2,27 | +21,43 |

Les neuf contrôles TP20/SL10 avec sizing plafonné reproduisent exactement
les trades et métriques des neuf baselines. Le plafond supplémentaire ne
change donc pas leur quantité effectivement exécutée. Les différences des
cas personnalisés ne sont pas un simple gain causé par une réduction de
taille dans le témoin ; les profils modifient ensuite aussi les dates de
sortie, les réentrées, le capital disponible et l'état des garde-fous natifs.

La personnalisation choisit surtout **TP10/SL7** :98,10 % /91,28 % /96,80 %
des candidats TOP10 en2024/2025/2026. Ces proportions concernent les candidats,
pas le nombre de positions exécutées. L'avantage2024 ne suffit pas à prouver
un apport du modèle de choix plutôt que de barrières proches de TP10/SL7
fixes. Aucun contrôle supplémentaire TP10/SL7 n'est lancé a posteriori ici.

### Conclusion bornée

- Filtre0,50 : pas de signal exploitable, car aucune entrée.
- Sortie quotidienne : bénéfice2025 réel dans ce replay, mais gains2024/2026
  fortement sacrifiés ; aucun gain robuste sur toutes les périodes.
- TP/SL personnalisés : mieux sur TOP10 en2024, mais pas sur2025 et nette
  sous-performance2026. Les TOP20/50 ne sauvent pas cette conclusion.
- Pas d'empilement de ces méthodes, de nouveau seuil choisi sur les pertes
  ou de promotion en production. L'Oracle original reste inchangé.

L'audit recalcule les décisions du filtre et des trois heads TP/SL à partir
des features archivées et vérifie les profils réellement ancrés aux fills.
Les stops, échéances, décisions close/next-open, identités d'origine, cash,
portefeuilles entièrement clos et empreintes sont contrôlés. Tous les résultats
et diagnostics : `comparisons.json`, `comparisons.md`, `second-technical-review.json`.
Les modèles auxiliaires sont conservés dans les trois sous-répertoires `models`.

Le champ legacy `sizing_unchanged` du moteur commun décrit son défaut natif
et n'est pas autorité pour une session de recherche injectée. La revue précise
le contrat effectif du sizing personnalisé ; ce champ ne sert pas à attribuer
les performances. Les résultats bruts restent conservés sans réécriture.
