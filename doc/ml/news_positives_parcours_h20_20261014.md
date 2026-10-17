# News très positives à J, J−1/J−2 : hausse pendant H0…H20

Étude achevée le **14 octobre 2026**. Rapport canonique :
`artifacts/research/us_news_positive_path/20261014-v2/report.json`.
V1 demeure un premier calcul limité aux fenêtres cumulées ; V2 ajoute J−1 et
J−2 pris séparément. Pas de changement de seuil après les résultats.

## Conclusion

Une petite hausse à un instant du parcours se produit dans environ **99 %**
des cas, avec ou sans sentiment fort : ce n'est pas une précision LONG de 99 %.
Les écarts pour atteindre +20 % sont faibles ; les retards et la répétition
quotidienne ne montrent pas d'avantage stable confirmé entre 2025 et 2026.
Pas de filtre promu, nouveau modèle ou calcul économique dans ce test.

## Données et règle figée

1 790 titres de `config/univers/univers_filtred_tradable.txt`, univers actuel
identique à celui des archives news du fichier batch. 367 851 observations
article/titre dédupliquées de `news_raw`/`news_ticker_sentiment`. Prix split-adjusted
du tape `us_oracle_tp20_sl10_new/20261012-v6`, source locale qualifiée conservée.
Aucun téléchargement, API, SQL ou entraînement dans ce calcul.

**Tous les articles scorés du jour** doivent avoir `positive_score > 0,9`,
avec au moins un article. Un maximum quotidien >0,9 ne suffit pas. Score 0,9,
manquant ou invalide : échec de la règle. Cela ne garantit pas que toutes les
news publiées ont été collectées et scorées.

Cinq vues : J seul, J−1 seul, J−2 seul, chaque jour J−1/J, chaque jour J−2/J.
Les fenêtres cumulées exigent un article chaque jour ; les retards seuls n'exigent
pas de news à J. J−1/J−2 sont les **séances NYSE**, vendredi étant J−1 de lundi.
Les 41 159 publications hors séances sont comptées sans redistribution arbitraire.

2025 : 250 séances. 2026 : 194 dates jusqu'au 9 octobre, mais seulement
174 dates avec H20 mature, **jusqu'au 11 septembre**. Pas de rendement nul pour
les vingt dernières dates. Les premières dates 2025 sont tronquées pour les
retards : pas d'invention de news de décembre 2024.

## Définition du parcours et qualité

**H0…H20** : départ à l'open J, maximum HIGH/minimum LOW de J à J+20,
soit **21 séances incluses**. Open 100, high 125 à J9, clôture 95 à J20 :
hausse maximale +25 %, terminal −5 %. Les deux résultats sont conservés.
Le high de J peut avoir précédé la news : cette vue est rétrospective.

**H1…H20** : départ à l'open J+1, vingt séances J+1…J20, sans high de J.
Cette vue reste descriptive faute de preuve de disponibilité du scoring.
Pour J−1/J−2 seuls, elle conserve également ce départ à J+1 : un délai supplémentaire.

Qualité complète du chemin : toutes les barres présentes, OHLC positifs et
cohérents, volume positif, aucune barre remplie, ajustement split, instrument_id
connu et constant, aucune discontinuité du registre. Aucune imputation ou
resélection selon la qualité future. Les chemins exclus/immatures sont comptés.

## H0…H20 : atteindre +20 % à un moment

Les N représentent des **couples titre/date**, pas des trades indépendants.

| Signal | N 2025 | Atteint +20 %, 2025 | N 2026 | Atteint +20 %, 2026 |
| --- | ---: | ---: | ---: | ---: |
| Univers sans filtre news | 447 479 | 7,78 % | 305 695 | 10,88 % |
| J seul | 10 919 | 8,65 % | 8 811 | 11,33 % |
| J−1 seul | 10 908 | 8,14 % | 8 801 | 10,56 % |
| J−2 seul | 10 884 | 7,80 % | 8 791 | 10,11 % |
| Chaque jour J−1/J | 669 | 9,57 % | 604 | 10,60 % |
| Chaque jour J−2/J | 41 | 7,32 % | 45 | 11,11 % |

Une hausse strictement positive vaut, pour J seul, **99,16 % / 99,25 %**, contre
**98,93 % / 99,02 %** dans l'univers (2025/2026). Un high légèrement supérieur
à l'open est extrêmement fréquent. La règle trois jours ne fournit que 41/45
cas qualifiés et chevauchants : aucune efficacité démontrée.

## H1…H20 : exclure le high du jour de publication

| Année | Signal | N | Atteint +5 % | Atteint +10 % | Atteint +20 % |
| --- | --- | ---: | ---: | ---: | ---: |
| 2025 | Univers | 447 480 | 56,34 % | 28,07 % | 7,29 % |
| 2025 | J seul | 10 919 | 55,92 % | 27,47 % | 7,50 % |
| 2025 | J−1 seul | 10 908 | 55,41 % | 27,05 % | 7,19 % |
| 2025 | J−2 seul | 10 885 | 55,05 % | 27,19 % | 7,29 % |
| 2025 | Chaque jour J−1/J | 669 | 54,86 % | 26,16 % | 8,22 % |
| 2025 | Chaque jour J−2/J | 41 | 48,78 % | 21,95 % | 4,88 % |
| 2026 | Univers | 305 826 | 58,94 % | 33,20 % | 10,15 % |
| 2026 | J seul | 8 814 | 57,41 % | 32,20 % | 10,01 % |
| 2026 | J−1 seul | 8 804 | 56,79 % | 31,64 % | 9,47 % |
| 2026 | J−2 seul | 8 796 | 56,95 % | 31,22 % | 9,38 % |
| 2026 | Chaque jour J−1/J | 604 | 56,13 % | 29,47 % | 8,44 % |
| 2026 | Chaque jour J−2/J | 45 | 44,44 % | 22,22 % | 6,67 % |

Le signal J seul termine positif à J20 dans **55,18 % / 47,59 %** des cas.
Les cas +20 % atteints puis clôture non positive représentent **0,22 % / 0,58 %**
de ces cohortes. Ce n'est pas le nombre de TP exécutables : un SL a pu précéder
la hausse. Le maximum n'est pas une performance réalisable.

## Témoins et incertitude

Le rapport contient des témoins avec news non fortes et une comparaison
**date × quintile volatilité60 × quintile momentum20**, au moins cinq témoins
non forts par cellule. Covariables calculées jusqu'à J−1, bins avant qualification
du futur ; aucun contrôle sur la réaction de J. Les cas sans covariables/témoins
restent dans les chiffres bruts mais sont exclus de cette comparaison.
`matched.total_strong_qualified` signifie ici les cas qualifiés **ayant ces deux
covariables**, avant le filtre des cinq témoins, pas tout le groupe `strong`.

H1/J seul : écart +20 % équipondéré par blocs **+0,32 point** en 2025, IC95
descriptif [−0,16 ; +0,81], et **+1,36 point** en 2026, IC [−0,001 ; +2,71].
J−2 seul : petit effet 2025, mais intervalle 2026 incluant zéro. J−1 seul ne
fournit pas de confirmation stable non plus. 999 bootstrap de blocs de 21 séances,
au moins huit blocs ; J−2/J 2026 n'en a que sept, pas d'intervalle inventé.
Intervalles descriptifs **sans correction des comparaisons multiples** ; années
déjà étudiées, pas de holdout vierge ni de preuve causale.

## PIT et périmètre

Le diagnostic utilise le maximum des dernières mises à jour news/sentiment,
pas une version immuable de la première disponibilité. **Zéro cas fort qualifié**
avec tous ces horodatages antérieurs à l'open J+1. Cela ne prouve pas que les
articles n'existaient pas à l'époque ; les archives présentes ne prouvent pas
que ce score précis était connu alors. 688 heures minuit ambiguës sont tracées
et exclues du diagnostic temporel. Aucun horaire n'est inventé.

Univers actuel/survivorship, couverture des seuls articles scorés, réaction
prix→news et chemins chevauchants limitent les conclusions. Pas de cible décile
D1/D10, seulement une excursion absolue ; **pas de condition Oracle TOP10/20/50**.
Ne pas attribuer ces pourcentages à ce pool. Aucun sizing/coûts/PnL dans ce test.

## Livrables et reproduction

`protocol.json` contient les hashes des sources, du registre, du script et les
règles ; `observations.parquet` contient sélections, qualité, covariables et
excursions ; `report.json` fournit années/mois/témoins/compteurs ; `progress.json`
est `COMPLETED`. V2 est la référence pour les retards seuls.

```powershell
python -u -m scripts.research.us_news_positive_path_audit --output artifacts/research/us_news_positive_path/NOUVEL-ID
```

Refus d'écraser un protocole existant, vérification des sources au début/à la fin.
Tests : tous-articles, journées manquantes, retards séparés, fenêtres exactes,
pic puis baisse, high pré-news, barres remplies, identités/discontinuités, seuil
strict, timezone NY, vendredi/lundi et absence de résultats sans observations.
