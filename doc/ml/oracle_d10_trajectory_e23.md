# E23 — D10 one-vs-rest après Oracle avec trajectoires J−10 à J

## Statut

**TERMINÉ / NO_GO.** Le run complet pré-enregistré rejette la baseline D10-only
et toutes les trajectoires testées. Ce harnais reste exclusivement destiné à la
recherche. Il n'écrit ni modèle de serving, ni prédiction SQL et ne modifie
aucune cascade.

## Question

Parmi les candidats sélectionnés à J dans le TOP20 de l'Oracle OOF, peut-on
identifier ceux qui appartiendront au D10 transversal réel à J+20 ?

La cible conserve tous les candidats Oracle : `D10=1`, `D1..D9=0`. Elle diffère
du classifieur D1/D10, qui retirait le milieu, du dual-threshold absolu et du
ranker conditionnel décile 0..9.

## Variantes gelées

| Variante | Entrées |
|---|---|
| E23-A | état canonique à J |
| E23-B | état J + price/volume ordonné J−10 à J |
| E23-C | état J + sentiment quotidien ordonné J−10 à J |
| E23-D | état J + deux trajectoires |

Les modèles pré-enregistrés sont Logistic, LightGBM et CatBoost. CatBoost est
primaire ; les deux autres servent de contrôles d'architecture.

## Contrat temporel du sentiment

Les observations viennent de `news_ticker_sentiment`, joint à
`news_raw.effective_trade_date`. Chaque lag correspond à une séance globale
exacte et non à la dernière apparition du symbole dans le pool Oracle.

Pour chacune des onze séances J−10...J, le modèle reçoit : score net total,
score net moyen, nombre d'articles, ratios positif/négatif et indicateur de
présence de news. Une séance sans article vaut zéro avec `has_news=0`; elle ne
se confond donc pas avec une vraie nouvelle neutre (`score=0`, `has_news=1`).

Une publication après clôture n'est utilisable que lorsque son
`effective_trade_date` devient la séance suivante. Les agrégats et leurs
résumés sont strictement antérieurs ou égaux à la date de décision.

## Trajectoire prix

Les sept séries ordonnées sont : rendement quotidien, gap overnight, position
de clôture, volume relatif 20 jours, rendement moyen cinq jours, force relative
cinq jours et position dans le range 20 jours. Les dix lags précédents sont
ajoutés à la valeur de J, puis résumés par moyenne, dispersion, somme, delta et
pente. Les lags sont cherchés dans le panel quotidien complet avant application
du gate Oracle : une absence du pool à J−k ne transforme donc jamais J−k en une
ancienne date arbitraire.

Le panel historique des lags est chargé sans exiger de cible future à J−k.
Seul l'événement final du pool doit posséder son label H20 valide. Cette
séparation empêche l'absence d'un lag de révéler indirectement qu'un label futur
avait été invalidé par une discontinuité ou une indisponibilité ultérieure.

## Walk-Forward et évaluation

Le protocole utilise les douze folds H20 les plus récents : 504 séances de
train minimal, 126 de validation, 126 de test, pas de 126 et purge H20. La
calibration Platt est ajustée uniquement sur la validation. Les sélections
TOP5/TOP10/TOP20 sont faites quotidiennement avec le score brut, car une
calibration monotone ne doit pas modifier le classement.

Les comparaisons portent sur AUC, average precision, précision D10, rendement
H20, hit rate et fréquence de rendement supérieur à 3 %. Chaque sélection est
comparée au pool Oracle complet, au score d'amplitude Oracle et à E23-A.

Les gates absolus et incrémentaux sont enregistrés dans
`config/research/e23_oracle_d10_trajectory.json`. Une variante temporelle doit
à la fois être exploitable contre le pool et battre E23-A ; un gain uniquement
global ou un seul semestre positif ne suffit pas.

## Commandes

Smoke technique CatBoost, deux folds et 50 symboles :

    python -u -m modelFactory.oracle_d10_trajectory_e23 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --models catboost --max-symbols 50 --max-folds 2 --threads 4 --log-level INFO

Run complet pré-enregistré :

    python -u -m modelFactory.oracle_d10_trajectory_e23 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --threads 4 --log-level INFO

Les artefacts sont créés sous
`artifacts/research/oracle_d10_trajectory/e23-d10-*`. Un résultat positif
n'autorise qu'une confirmation ultérieure ; jamais une promotion directe.

## Smoke technique du 15 septembre 2026

Le smoke final utilise 50 symboles demandés, dont 33 présents dans le pool
Oracle, 12 537 événements et les deux folds récents de juillet 2024 à juillet
2025. Les quatre variantes CatBoost terminent et produisent 2 534 prédictions
OOS chacune. La couverture du sentiment est de 24,04 % à J et 67,58 % sur au
moins une séance de J−10 à J.

Le panel de lags price est chargé sans condition sur les labels futurs. Le
rapport confirme `serving_changed=false` et `database_writes=false`. Les
résultats du smoke ne sont pas interprétés : l'échantillon est alphabétique,
petit et limité à deux folds. Artefact :
`artifacts/research/oracle_d10_trajectory/e23-smoke50-20260915-v2`.

## Résultat complet du 15 septembre 2026

Artefact autoritatif :
`artifacts/research/oracle_d10_trajectory/e23-d10-20260915203334`.

Le pool contient 582 700 événements, 1 764 séances et 1 472 symboles du
5 juillet 2018 au 11 juillet 2025. La prévalence D10 vaut 21,95 % dans le pool
Oracle TOP20. L'évaluation OOS couvre neuf folds du 5 janvier 2021 au
11 juillet 2025. Le sentiment est présent à J pour 13,12 % des événements et
sur au moins une séance de J−10 à J pour 48,54 %.

### Synthèse OOS TOP10 quotidien

| Modèle | Variante | AUC | AP | Précision D10 | Lift précision | Rendement H20 | Lift rendement/pool | Verdict absolu |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Logistic | A état J | 0,5111 | 0,2333 | **25,22 %** | **+3,47 pts** | **+1,019 %** | **+0,232 pt** | FAIL |
| Logistic | B prix | 0,5113 | 0,2307 | 24,68 % | +2,94 pts | +0,707 % | −0,080 pt | FAIL |
| Logistic | C sentiment | 0,5110 | 0,2304 | 24,52 % | +2,78 pts | +0,967 % | +0,179 pt | FAIL |
| Logistic | D prix + sentiment | 0,5109 | 0,2284 | 24,22 % | +2,48 pts | +0,586 % | −0,201 pt | FAIL |
| LightGBM | A état J | 0,5171 | 0,2282 | 24,22 % | +2,47 pts | +0,794 % | +0,007 pt | FAIL |
| LightGBM | B prix | 0,5221 | 0,2302 | 23,56 % | +1,82 pt | +0,411 % | −0,377 pt | FAIL |
| LightGBM | C sentiment | 0,5139 | 0,2256 | 23,39 % | +1,64 pt | +0,505 % | −0,282 pt | FAIL |
| LightGBM | D prix + sentiment | **0,5250** | **0,2340** | 24,33 % | +2,58 pts | +0,727 % | −0,061 pt | FAIL |
| CatBoost | A état J | 0,4968 | 0,2169 | 23,22 % | +1,48 pt | +0,781 % | −0,006 pt | FAIL |
| CatBoost | B prix | 0,4980 | 0,2142 | 24,28 % | +2,54 pts | +0,651 % | −0,137 pt | FAIL |
| CatBoost | C sentiment | 0,5066 | 0,2286 | 24,22 % | +2,48 pts | +0,784 % | −0,004 pt | FAIL |
| CatBoost | D prix + sentiment | 0,4956 | 0,2157 | 23,89 % | +2,15 pts | +0,543 % | −0,244 pt | FAIL |

Le pool OOS a une prévalence D10 de 21,74 % et un rendement H20 moyen de
+0,787 %. La meilleure politique économique est la baseline Logistic à J :
elle atteint +1,019 %, soit seulement +0,232 point contre le pool. Elle passe
le gate de précision TOP10, mais échoue sur l'AUC, l'average precision, le
rendement minimal, la stabilité par fold et la sûreté semestrielle. Son lift
de rendement est positif dans 6 folds sur 9, mais varie de −1,21 à +2,49 points
selon le semestre.

Le score d'amplitude Oracle seul est aussi un benchmark supérieur : sur la
même taille TOP10, il atteint 28,62 % de D10 et +1,198 % de rendement, contre
25,22 % et +1,019 % pour la meilleure baseline apprise.

### Apport incrémental des trajectoires

Aucune variante temporelle ne franchit les gates contre A, pour aucun des
trois modèles. Le signal partiel le plus proche est CatBoost C sentiment :
AUC +0,0098, AP +0,0117, précision TOP10 +1,00 point, mais rendement seulement
+0,002 point et 6 folds positifs sur 9. Il ne satisfait donc ni le seuil AUC
incrémental de +0,01, ni les exigences de précision, de rendement et de
stabilité.

Le prix seul dégrade le rendement TOP10 dans les trois architectures. La
combinaison prix + sentiment dégrade également le rendement face à A dans les
trois cas. La meilleure AUC, LightGBM D à 0,5250, reste économiquement sous le
pool et ne constitue pas un signal tradable.

## Décision

E23 est fermé en `NO_GO`. Les trajectoires J−10 à J de prix/volume et de
sentiment ne permettent pas d'isoler de façon robuste les futurs D10 à
l'intérieur du TOP20 Oracle. Aucun artefact ne doit être promu, aucun seuil ne
doit être optimisé sur ces résultats et aucune modification de serving ou de
cascade n'est autorisée.
