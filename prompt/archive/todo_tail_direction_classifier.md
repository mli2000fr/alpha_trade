# EXPÉRIENCE — `D1D10 Tail Direction Classifier`

## 0. Contexte et objectif

Architecture actuelle :

```text
                      Oracle Extreme
                            │
                "extrême probable à J"
                            │
                 ┌──────────┴──────────┐
                 │                     │
          Per-Symbol LONG       Per-Symbol SHORT
                 │                     │
             LONG trade            SHORT trade
```

Le problème observé jusqu’ici est :

```text
Oracle Extreme
→ sait identifier des mouvements extrêmes
→ concentre D1 et D10

MAIS

→ ne sait pas déterminer correctement
  si l'extrême futur sera D1 ou D10
```

Global Rank et plusieurs expériences directionnelles ont également montré que la direction est difficile à observer avec les données actuelles.

Nous disposons cependant d’un avantage important pour la recherche :

```text
pour les ~400 symboles de recherche,
nous connaissons historiquement les déciles réalisés
D1...D10
```

notamment sur environ :

```text
2020 → 2025
```

Nouvelle formulation du problème :

```text
Classe 0 = D1 réel
Classe 1 = D10 réel
```

On exclut volontairement :

```text
D2...D9
```

dans la première expérience de séparabilité.

La question scientifique devient :

```text
"Parmi les véritables extrêmes,
les informations disponibles à J permettent-elles
de distinguer un futur D1 d'un futur D10 ?"
```

Ceci est un problème de :

```text
classification binaire
```

et non un nouveau modèle de prédiction directe du rendement.

---

# 1. Hypothèse

Il est possible que :

```text
D1-D5 vs D6-D10
```

soit difficile à classifier à cause des observations centrales D4/D5/D6/D7 très ambiguës,

alors que :

```text
D1 vs D10
```

possède éventuellement une frontière plus claire.

Cette expérience doit tester cette hypothèse sans chercher à la confirmer artificiellement.

Verdict accepté :

```text
GO
WEAK
INCONCLUSIVE
NO_GO
```

Si le résultat est ≈ hasard :

```text
on l'accepte
```

sans tuning post-hoc.

---

# 2. Réutiliser exactement les labels Oracle existants

Ne pas reconstruire une nouvelle définition de D1/D10.

Réutiliser la fonction / logique autoritative existante qui construit le target Oracle.

Il faut conserver exactement :

```text
horizon
forward return
cross-sectional universe
percentile definition
D1/D10 boundaries
dates
traitement des valeurs manquantes
```

utilisées par Oracle.

Si Oracle utilise par exemple H20 :

```text
D1 = bottom 10% realized H20 intra-date
D10 = top 10% realized H20 intra-date
```

utiliser exactement cette définition.

Produire au début du rapport :

```text
LABEL_CONTRACT
```

indiquant :

```text
horizon
forward return definition
D1 definition
D10 definition
universe used
target availability rule
```

---

# 3. Dataset scientifique A — séparabilité fondamentale

Première expérience :

```text
univers ≈ 400 symboles
dates disponibles ≈ 2020→2025
```

Pour chaque date J :

conserver uniquement :

```text
D1
D10
```

Construire :

```text
y = 0 si D1
y = 1 si D10
```

Grain obligatoire :

```text
1 ligne = symbol × signal_date
```

Aucun événement de lifecycle.

Aucun trade.

Aucun partial exit.

Aucun duplicat.

Cette expérience répond uniquement :

```text
"D1 et D10 sont-ils intrinsèquement séparables
avec X(J) ?"
```

---

# 4. Dataset scientifique B — problème réel derrière Oracle

Faire ensuite une seconde expérience.

Utiliser uniquement les candidats :

```text
Oracle Extreme TOP20% prédit à J
```

IMPORTANT :

le TOP20 doit provenir de prédictions Oracle :

```text
OOF / WF / PIT
```

et jamais d’un modèle qui aurait été entraîné sur le futur du fold considéré.

Assertion obligatoire :

```text
champion_train_end < test_fold_start
```

ou contrat causal équivalent déjà utilisé par Oracle.

Parmi ces candidats Oracle, pour l’entraînement binaire initial :

```text
garder seulement les réalisations D1 et D10
```

avec :

```text
D1  = 0
D10 = 1
```

Cette expérience répond :

```text
"Une fois qu'Oracle dit EXTREME,
pouvons-nous déterminer le côté de l'extrême ?"
```

**Dataset B est plus important économiquement que Dataset A.**

---

# 5. Attention : le score n'est PAS une probabilité absolue D10

Puisque le modèle est entraîné uniquement sur :

```text
D1 + D10
```

sa sortie doit être nommée :

```text
p_d10_given_tail
```

et :

```text
p_d1_given_tail = 1 - p_d10_given_tail
```

Ne jamais appeler cette sortie :

```text
p_up
p_long
P(D10)
```

sans préciser la condition.

Elle signifie :

```text
P(D10 | observation réellement dans D1/D10)
```

Le modèle n’a pas encore appris à distinguer :

```text
tail vs middle
```

C’est Oracle qui joue ce rôle.

---

# 6. Features utilisées

Première baseline :

```text
toutes les features PIT actuelles disponibles à J
```

MAIS effectuer avant entraînement un audit anti-leakage.

Supprimer absolument :

```text
future_return*
forward_return*
realized_*
oracle_realized*
target*
label*
future_decile*
oracle_available_date utilisé comme information
toute valeur calculée après J
```

Le `symbol` ne doit PAS être utilisé comme feature catégorielle dans le premier modèle partagé.

`signal_date` ne doit PAS être utilisée comme valeur numérique prédictive.

---

# 7. Groupes de features

Identifier les groupes actuels, par exemple :

```text
PRICE_TECHNICAL
MOMENTUM
VOLUME_LIQUIDITY
CAPM
FUNDAMENTALS
SENTIMENT
MACRO_REGIME
CROSS_SECTIONAL
SECTOR_RELATIVE
SIGNED_DIRECTIONAL_EXISTING
```

Ne pas faire immédiatement une sélection feature par feature sur tout le dataset.

Le premier objectif est :

```text
BASELINE_ALL_EXISTING_PIT
```

Puis des ablations par **famille**, pas 150 sweeps individuels.

---

# 8. Données Eroya

Les données Eroya devront être traitées comme nouvelles familles indépendantes.

Exemples :

```text
EROYA_SHORT
EROYA_OPTIONS
EROYA_FLOW
EROYA_INSIDERS
EROYA_INSTITUTIONAL
EROYA_ANALYST
```

Mais une famille Eroya n’est autorisée dans 2020–2025 que si elle est réellement historique/PIT.

Vérifier pour chaque endpoint :

```text
historical timestamp
published_at
available_at
revision semantics
historical depth
```

Si Eroya fournit seulement l’état actuel :

```text
NOT_PIT
```

et exclure la famille.

Interdiction :

```text
snapshot actuel → dates historiques
```

---

# 9. Features Eroya candidates

Si disponibles PIT, construire seulement quelques features pré-enregistrées.

## SHORT / borrow

```text
short_interest_pct_float
short_interest_change_20d
short_interest_change_60d

borrow_fee
borrow_fee_change_5d
borrow_fee_change_20d

utilization
utilization_change_20d
```

## OPTIONS

```text
put_call_volume_ratio
put_call_oi_ratio
put_call_premium_ratio

put_iv_minus_call_iv
downside_skew
skew_change_5d
skew_change_20d

net_options_premium
```

Ne pas considérer :

```text
IV brute
```

comme directionnelle par défaut.

## FLOW

```text
net_money_flow
net_money_flow_5d
net_money_flow_20d
flow_acceleration
```

## INSIDERS

```text
insider_buy_value_20d
insider_sell_value_20d
insider_net_value_20d
insider_net_count_20d
```

## INSTITUTIONAL

```text
institutional_ownership_change
holder_count_change
```

## ANALYST / forecast si réellement disponible

```text
eps_revision
revenue_revision
target_revision
net_upgrades
```

---

# 10. Pour chaque feature signée, conserver le signe

Ne jamais convertir automatiquement :

```text
x → abs(x)
```

Exemple :

```text
revision +10%
```

doit être différente de :

```text
revision -10%
```

puisque précisément :

```text
le signe est l'information recherchée.
```

---

# 11. Raw + time change + cross-sectional

Pour les données pertinentes, créer au maximum :

```text
raw level
5d change
20d change
60d change
xs_rank
sector_rank
```

Ne pas créer immédiatement :

```text
3/4/6/7/8/9/12/15/30/45/90d
```

Aucun sweep massif.

Fenêtres figées :

```text
5
20
60
```

---

# 12. Premier modèle : Logistic Regression

Commencer impérativement par :

```text
LogisticRegression
```

avec preprocessing correct :

```text
imputation train-only
scaling train-only
```

Pipeline sklearn pour garantir qu’aucune statistique du test n’est utilisée.

Pourquoi :

```text
si une frontière directionnelle simple existe,
elle doit être visible ici.
```

---

# 13. Deux modèles non linéaires seulement ensuite

Tester ensuite :

```text
LightGBM
CatBoost
```

Utiliser :

```text
hyperparamètres fixes raisonnables
seeds fixes
```

Pas de :

```text
Optuna
grid search
Bayesian search
tuning par fold
```

Le test porte sur :

```text
l'information disponible
```

pas sur la capacité à optimiser le modèle.

---

# 14. Walk-forward obligatoire

Aucun random split.

Exemple conceptuel :

```text
train 2020-2021 → test 2022
train 2020-2022 → test 2023
train 2020-2023 → test 2024
train 2020-2024 → test 2025
```

Adapter aux dates réellement disponibles.

Utiliser le framework WF existant si possible.

---

# 15. Purge H20

Pour une observation J avec target H20 :

son label n’est disponible qu’après réalisation complète du H20.

Le training fold doit respecter :

```text
target_available_at < test_start
```

ou exactement le contrat causal déjà implémenté pour Oracle.

Aucun train row dont le futur chevauche le test.

---

# 16. Feature engineering strictement train-only

Dans chaque fold :

```text
imputation
scaling
winsorization
feature selection
categorical encoding
```

doivent être appris :

```text
uniquement sur train
```

puis appliqués à test.

Interdiction de faire :

```text
sélectionner les meilleures features sur 2020-2025 complet
puis lancer le WF
```

Ce serait du leakage de recherche.

---

# 17. Equal-date weighting

Les déciles sont cross-sectionnels par date.

Une date avec davantage de symboles ne doit pas dominer artificiellement l’apprentissage.

Tester/utiliser :

```text
weight(row on date J) = 1 / n_rows_on_date_J
```

puis normaliser si nécessaire.

Documenter la méthode.

Produire également le résultat sans pondération comme contrôle si facile.

---

# 18. Métrique principale : ROC-AUC OOF

Mesurer :

```text
ROC-AUC
```

sur toutes les prédictions OOF.

Mais ce n’est pas suffisant.

Produire :

```text
AUC OOF global
AUC par fold
AUC par année
```

---

# 19. Métrique cruciale : SAME-DATE AUC

D1 et D10 étant définis cross-sectionnellement chaque jour, calculer également :

```text
ROC-AUC séparément pour chaque date J
```

lorsqu’il y a les deux classes.

Puis :

```text
mean_daily_auc
median_daily_auc
% dates AUC > 0.50
% dates AUC > 0.55
```

Pondérer chaque date également.

Cette métrique est extrêmement importante.

On cherche :

```text
le même jour,
le modèle classe-t-il les D10 au-dessus des D1 ?
```

plutôt qu’un simple effet de régime entre différentes dates.

---

# 20. Pairwise D1 vs D10

Ajouter si faisable une métrique :

```text
pairwise_accuracy
```

Pour chaque date :

comparer les scores de chaque :

```text
D10
```

aux scores :

```text
D1
```

mesurer :

```text
P(score_D10 > score_D1)
```

C’est conceptuellement proche de l’AUC quotidienne.

---

# 21. Calibration

Mesurer :

```text
log_loss
Brier score
```

et reliability bins.

Ne pas calibrer Platt/isotonic dans la première campagne.

Observer seulement.

---

# 22. Déciles du score du classifier

Très important.

Sur les prédictions OOF :

trier :

```text
p_d10_given_tail
```

en déciles.

Pour chaque décile de score :

produire :

```text
n
% D1 réel
% D10 réel
mean realized H20
median realized H20
```

On cherche une relation monotone :

```text
score bas
→ D1 majoritaires

score haut
→ D10 majoritaires
```

---

# 23. Extrêmes du score

Mesurer particulièrement :

```text
bottom 10% score
top 10% score
```

Fournir :

```text
P(D1 | score bottom10)
P(D10 | score top10)
```

Puis :

```text
bottom20
top20
```

Ceci est plus important économiquement qu’une petite variation de l’accuracy globale.

---

# 24. Baseline naïve

D1/D10 devraient être proches de 50/50 dans le dataset pur.

Calculer :

```text
class balance
```

par :

```text
fold
year
date
```

Toute performance doit être comparée au baseline réel.

---

# 25. Metrics secondaires

Produire :

```text
accuracy
balanced_accuracy
precision D10
recall D10
precision D1
recall D1
F1
PR-AUC
```

Mais ne pas choisir le modèle sur F1 seul.

---

# 26. Stabilité temporelle

Pour chaque fold :

```text
AUC
same_date_auc
IC
top_score D10 enrichment
bottom_score D1 enrichment
```

Un résultat :

```text
0.58
0.59
0.57
0.60
```

est bien plus intéressant que :

```text
0.70
0.48
0.52
0.61
```

même si les moyennes sont proches.

---

# 27. Stabilité par symbole

Pour les prédictions OOF :

calculer si échantillon suffisant :

```text
AUC par symbol
n_D1
n_D10
```

Puis :

```text
% symbols AUC > 0.50
% symbols AUC > 0.55
median symbol AUC
```

Ne pas publier d’AUC pour un symbole avec échantillon trop faible sans avertissement.

---

# 28. Stabilité sectorielle

Même analyse :

```text
AUC by sector
same-date performance by sector
```

Objectif :

savoir si le signal est :

```text
universel
```

ou seulement :

```text
Tech / Biotech / etc.
```

---

# 29. Test des familles existantes

Pour comprendre d’où vient éventuellement le signal, faire des ablations :

```text
E0 = toutes features existantes PIT

E1 = price/technical only
E2 = fundamentals only
E3 = volume/liquidity
E4 = cross-sectional/sector
E5 = sentiment
E6 = CAPM/macro
```

Pas besoin de toutes les combinaisons.

On veut seulement déterminer :

```text
quelle famille contient la séparabilité.
```

---

# 30. Eroya : ablations incrémentales

Une fois E0 mesuré :

```text
E0 = current features

E0 + Eroya Short/Borrow
E0 + Eroya Options
E0 + Eroya Flow
E0 + Eroya Insiders
E0 + Eroya Institutional
E0 + Eroya Analyst
```

Ne pas commencer directement par :

```text
E0 + toutes les données Eroya
```

sinon on ne saura pas quelle famille apporte l’information.

---

# 31. Test sur EXACTEMENT les mêmes lignes

Pour comparer :

```text
E0
```

et :

```text
E0 + Eroya Options
```

utiliser strictement :

```text
mêmes symbol×dates
```

correspondant à l’intersection de coverage.

Sinon l’AUC peut changer uniquement parce que la population a changé.

Pour chaque ablation fournir :

```text
baseline_same_rows_auc
enriched_same_rows_auc
delta_auc
```

---

# 32. Missing data

Ne jamais :

```text
missing = 0
```

sauf si zéro a réellement une signification économique.

Ajouter éventuellement :

```text
feature_missing_flag
```

si pertinent.

L’imputation doit être apprise train-only.

---

# 33. Redondance avec Oracle

Pour chaque nouvelle famille :

mesurer corrélation avec :

```text
oracle_proba_extreme
```

et éventuellement Global Rank si disponible.

On cherche surtout :

```text
information orthogonale de direction
```

et pas :

```text
une deuxième mesure d'amplitude.
```

---

# 34. `direction_vs_amplitude`

Réutiliser la garde existante du harnais.

Pour chaque nouvelle feature/famille :

mesurer :

```text
direction predictability
```

versus :

```text
amplitude predictability
```

Si une feature améliore surtout :

```text
extreme vs middle
```

mais pas :

```text
D1 vs D10
```

verdict :

```text
AMPLITUDE_ONLY
```

Elle ne doit pas entrer dans le classifier de direction.

---

# 35. Feature importance

Pour LightGBM/CatBoost :

produire :

```text
permutation importance OOF
```

ou interprétation équivalente propre.

SHAP peut être utilisé pour compréhension après entraînement.

Mais :

```text
ne pas sélectionner rétroactivement les features
sur la base de SHAP du test complet.
```

---

# 36. Pas de symbol ID

Pour le premier classifier partagé :

ne pas permettre au modèle d’apprendre :

```text
AAPL est historiquement D10 plus souvent
X est historiquement D1 plus souvent
```

via un identifiant ticker.

Le modèle doit apprendre :

```text
un pattern de features
```

et non mémoriser les symboles.

---

# 37. Pas de régime/date comme raccourci

Une feature macro constante pour tous les symboles d’une date :

```text
VIX
SPY return
regime
```

ne peut pas, seule, distinguer D1 de D10 le même jour.

Elle peut être utile en interaction.

La mesure `same_date_auc` permet précisément de vérifier qu’on ne gagne pas seulement grâce à un effet temporel.

---

# 38. Expérience C — test production-like sur TOUS les candidats Oracle

Si le classifier D1/D10 passe, faire un test essentiel avant toute intégration.

Prendre :

```text
TOUS les candidats Oracle TOP20
```

y compris ceux qui réalisent :

```text
D2-D9
```

Calculer :

```text
p_d10_given_tail
```

pour chaque candidat.

Puis répartir le score en déciles.

Pour chaque score-decile, mesurer la distribution réelle :

```text
D1
D2
...
D10
```

ainsi que :

```text
BAD = D1-D3
MID = D4-D7
GOOD = D8-D10
mean H20
```

---

# 39. Pourquoi l'expérience C est obligatoire

Le classifier a appris seulement :

```text
D1 vs D10
```

mais en production Oracle lui fournira aussi :

```text
faux extrêmes / middles
```

Il faut donc vérifier que :

```text
score élevé
→ GOOD augmente réellement

score faible
→ BAD augmente réellement
```

même en présence de D2-D9.

Si ce comportement disparaît :

```text
classifier scientifique intéressant
mais non exploitable en production
```

---

# 40. Aucun threshold portfolio à ce stade

Ne pas choisir :

```text
p > 0.61
p > 0.67
p < 0.32
```

après observation.

Utiliser seulement :

```text
score deciles
top10
top20
bottom10
bottom20
```

pour analyser la monotonicité.

---

# 41. Critères pré-enregistrés de réussite

Ne pas exiger un chiffre arbitrairement énorme.

Classifier :

```text
NO_GO
```

si :

```text
AUC OOF ≈ 0.50
same-date AUC ≈ 0.50
folds instables
score buckets non monotones
```

`WEAK` si :

```text
AUC ~0.52-0.54
mais signe cohérent
et enrichissement tails visible
```

`GO_RESEARCH` si :

```text
AUC ~0.55+
same-date AUC > 0.50 de façon stable
majorité des folds positifs
score-deciles monotones
top score enrichit D10
bottom score enrichit D1
comportement production-like C confirmé
```

`STRONG_GO` si la séparation est sensiblement supérieure et stable.

Ces valeurs servent de guide de lecture, pas de seuil à tuner.

---

# 42. Comparaison des modèles

Produire :

| Model | Dataset | OOF AUC | Same-date AUC | LogLoss | Brier | Top10 D10% | Bottom10 D1% | Fold stability |
|---|---|---:|---:|---:|---:|---:|---:|---|
| LR | A | | | | | | | |
| LGBM | A | | | | | | | |
| CatBoost | A | | | | | | | |
| LR | B | | | | | | | |
| LGBM | B | | | | | | | |
| CatBoost | B | | | | | | | |

Puis Dataset C séparément.

---

# 43. Comparaison baseline vs Eroya

Produire :

| Feature set | AUC | Same-date AUC | Δ AUC | Top10 D10 | Bottom10 D1 | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Existing | | | — | | | |
| + Short/Borrow | | | | | | |
| + Options | | | | | | |
| + Flow | | | | | | |
| + Insiders | | | | | | |
| + Institutional | | | | | | |
| + Analyst | | | | | | |

Comparaison sur mêmes lignes obligatoire.

---

# 44. Si plusieurs familles Eroya passent

Seulement alors construire :

```text
EROYA_SIGNED_COMBINED
```

avec uniquement les familles ayant montré un signal OOF stable.

Puis :

```text
Existing
vs
Existing + EROYA_SIGNED_COMBINED
```

Pas de sélection feature individuelle à partir du test.

---

# 45. Relation avec les deux modèles per-symbol actuels

Ne pas remplacer immédiatement :

```text
Per-Symbol LONG
Per-Symbol SHORT
```

Même si le classifier fonctionne.

Première intégration future potentielle :

```text
Oracle Extreme
       ↓
D1/D10 classifier partagé
       ↓
p_d10_given_tail
p_d1_given_tail
       ↓
┌─────────────────────────────┐
│                             │
▼                             ▼
Per-Symbol LONG          Per-Symbol SHORT
+ p_d10_given_tail       + p_d1_given_tail
```

Ainsi :

```text
Oracle = amplitude
classifier = polarité de l'extrême
per-symbol = confirmation spécifique ticker
```

---

# 46. Ablation future LONG

Seulement après `GO_RESEARCH` du classifier :

```text
L0 = per-symbol LONG actuel
L1 = L0 + p_d10_given_tail
```

Tout le reste figé.

Tester :

```text
amélioration AUC
D10 enrichment
GOOD
BAD
% symbols improved
```

---

# 47. Ablation future SHORT

Séparément :

```text
S0 = per-symbol SHORT actuel
S1 = S0 + p_d1_given_tail
```

Ne pas supposer une symétrie.

Mesurer :

```text
D1 enrichment
BAD
GOOD
% symbols improved
```

---

# 48. Ne pas réintroduire le portfolio SHORT maintenant

Cette expérience peut utiliser :

```text
D1
```

pour apprendre la direction.

Cela ne signifie pas que le portfolio SHORT doit immédiatement être réactivé.

Le chantier actuel portfolio peut rester :

```text
LONG-only
```

pendant que la partie directionnelle SHORT reste en recherche.

---

# 49. Important concernant 2020-2025

Documenter clairement le statut des données/modèles.

Si certaines prédictions Oracle utilisées dans Dataset B viennent d’un modèle entraîné jusqu’en 2025, elles ne doivent PAS être présentées comme OOS 2020-2025.

Pour Dataset B :

utiliser uniquement :

```text
Oracle OOF / strict WF predictions
```

pour chaque date historique.

Si celles-ci n’existent pas :

```text
reconstruire le WF causal
```

ou :

```text
ne pas utiliser Dataset B
```

jusqu’à disponibilité.

Dataset A reste possible sans prédiction Oracle puisqu’il étudie directement la séparabilité des labels D1/D10.

---

# 50. Audit final leakage

Produire :

```text
LEAKAGE_AUDIT
```

avec :

```text
target construction PASS/FAIL
H20 purge PASS/FAIL
feature PIT PASS/FAIL
Oracle OOF selection PASS/FAIL
preprocessing train-only PASS/FAIL
same-row comparison PASS/FAIL
no-symbol-ID PASS/FAIL
```

Si un élément critique échoue :

```text
EXPERIMENT_INVALID
```

---

# 51. Rapport final

Produire :

```text
D1D10_CLASSIFIER_REPORT
```

avec sections :

```text
1. Label contract
2. Dataset A
3. Dataset B
4. Feature inventory
5. Leakage/PIT audit
6. Logistic Regression
7. LightGBM
8. CatBoost
9. Same-date analysis
10. Score-decile analysis
11. Per-year stability
12. Per-symbol stability
13. Per-sector stability
14. Existing feature-family ablations
15. Eroya incremental ablations
16. Dataset C production-like test
17. Final verdict
```

---

# 52. Verdict final obligatoire

Choisir :

```text
STRONG_GO
GO_RESEARCH
WEAK_SIGNAL
NO_GO
EXPERIMENT_INVALID
```

Puis répondre explicitement à :

```text
Q1:
Les vrais D1 et D10 sont-ils séparables
avec les features actuelles ?

Q2:
La séparation existe-t-elle encore
dans le pool Oracle OOF ?

Q3:
Les données Eroya ajoutent-elles
une information incrémentale ?

Q4:
Quelle famille Eroya apporte le plus ?

Q5:
Le score reste-t-il utile quand
D2-D9 sont réintroduits ?

Q6:
Le classifier mérite-t-il d'être testé
comme feature du per-symbol LONG ?

Q7:
Le classifier mérite-t-il d'être testé
comme feature du per-symbol SHORT ?
```

---

# 53. Freeze

Pendant toute cette campagne :

```text
aucune modification des labels
aucun changement H20
aucun changement D1/D10
aucun tuning post-hoc
aucun threshold portfolio
aucun changement Oracle
aucun changement per-symbol LONG/SHORT
```

Si une expérience échoue :

```text
documenter
NO_GO
passer à la famille suivante
```

Ne pas sauver artificiellement une hypothèse.

---

# 54. Ordre d'exécution demandé

Exécuter dans cet ordre :

```text
STEP 1
Audit labels/features/PIT

STEP 2
Construire Dataset A : vrais D1 vs D10

STEP 3
LR baseline

STEP 4
LightGBM + CatBoost

STEP 5
Same-date + score-deciles + stabilité

STEP 6
Ablations familles existantes

STEP 7
Construire Dataset B avec Oracle OOF

STEP 8
Répéter les tests dans le vrai pool Oracle

STEP 9
Audit Eroya PIT

STEP 10
Ajouter une famille Eroya à la fois

STEP 11
Combinaison des seules familles gagnantes

STEP 12
Dataset C : scorer tous les Oracle TOP20
y compris D2-D9

STEP 13
Verdict final
```

**Ne pas passer aux étapes Eroya si les features actuelles montrent déjà une erreur méthodologique/leakage.**

**Ne pas passer à l’intégration per-symbol avant le verdict Dataset C.**
