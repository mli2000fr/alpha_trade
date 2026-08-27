Chantier 1 — GlobalDirection avec persistance TOP10 + confirmation prix

Nom de branche / expérience

GlobalDirectionPersistenceFeatures

Objectif

Ajouter au modèle GlobalDirection des features qui décrivent :

la persistance du symbole dans le TOP10% Oracle Extreme ;
la confirmation directionnelle par le prix ;
leur interaction.

Hypothèse :

Oracle Extreme élevé plusieurs jours
+
prix qui progresse pendant cette période
=>
probabilité plus élevée d'être un bon LONG futur.

Ne PAS changer :

horizon = H20
target_mode = rank
modèle = LightGBM actuel
folds WF
hyperparamètres
loss

On teste uniquement une nouvelle famille de features.

1. Source TOP10

Utiliser :

Oracle Extreme

avec percentile cross-sectionnel calculé chaque jour :

extreme_pct >= 0.90

= TOP10% Oracle du jour.

Tout doit être strictement PIT.

2. Construire les features pour N = 2,3,4,5

Pour chaque (date J, symbol) :

top10_streak_2
top10_streak_3
top10_streak_4
top10_streak_5

définition :

top10_streak_N = 1
si le symbole appartient au TOP10% Oracle
pendant N séances consécutives jusqu'à J inclus.

Ajouter :

top10_count_2
top10_count_3
top10_count_4
top10_count_5

= nombre de séances TOP10 dans les N dernières séances.

Ajouter également :

extreme_pct_mean_2
extreme_pct_mean_3
extreme_pct_mean_4
extreme_pct_mean_5

extreme_pct_min_2
extreme_pct_min_3
extreme_pct_min_4
extreme_pct_min_5

3. Confirmation prix

Pour N = 2,3,4,5 :

price_return_N =
close[J] / close[J-N] - 1

puis :

price_up_N = 1 si price_return_N > 0

Ajouter également :

price_return_2
price_return_3
price_return_4
price_return_5

comme variables continues.

4. Interaction principale

Créer :

top10_price_up_2
top10_price_up_3
top10_price_up_4
top10_price_up_5

avec :

top10_price_up_N =
top10_streak_N AND price_up_N

C'est la feature centrale du test.

5. Ne PAS modifier le target

Ne surtout pas faire :

top10_price_up_N = 1
=> target = UP

Le target reste le futur réellement observé :

target = percentile cross-sectionnel future_return H20

Le modèle doit apprendre lui-même si la condition apporte réellement de la direction.

6. Diagnostic avant entraînement

Avant d'ajouter les features au modèle, mesurer individuellement :

top10_streak_N
price_return_N
price_up_N
top10_price_up_N
extreme_pct_mean_N
extreme_pct_min_N

contre :

future_decile
BAD5 = D1-D5
GOOD5 = D6-D10
D1-D3 vs D8-D10
D1 vs D10

Calculer :

IC Spearman
AUC BAD5 vs GOOD5
AUC D1-D3 vs D8-D10
AUC D1 vs D10
coverage
stabilité par fold

7. Si diagnostic intéressant

Entraîner :

GlobalDirection H20
target_mode=rank

avec :

features baseline actuelles
+
persistence/price features validées

Ne pas injecter automatiquement toutes les variantes si certaines sont clairement bruitées.

8. Comparaison

Comparer :

B1 = Oracle + B25 H20
C3 = GlobalDirection rank actuel
C6 = GlobalDirection + persistence features

Dans Oracle TOP20%, puis TOP24.

Produire :

D1...D10
BAD5
GOOD5
VERY_BAD
VERY_GOOD
mean H20
median H20
P(return > 0)
gradient Q1→Q5
résultats par fold

9. Critère GO

C6 doit montrer simultanément :

BAD5 ↓
GOOD5 ↑
D1/D2 ↓
D8/D9/D10 ↑
mean return ↑

et être stable sur la majorité des folds.

Une simple baisse de D1 accompagnée d'une forte perte de D9/D10 = NO-GO.

Aucun changement PROD dans ce chantier.