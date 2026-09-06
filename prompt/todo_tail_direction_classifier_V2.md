# EXPÉRIENCE V2 — Temporal D1/D10 Tail Direction Classifier

## 0. Objectif général

Cette campagne remplace complètement l’ancienne approche centrée principalement sur les features observées au seul jour `J`.

L’hypothèse centrale est désormais :

> **La différence entre un futur D1 et un futur D10 n’est probablement pas contenue uniquement dans l’état des features au jour J, mais dans leur trajectoire récente entre J-N et J.**

Autrement dit :

```text
ancienne approche :
X(J) → D1 ou D10

nouvelle approche :
[X(J-N), ..., X(J-2), X(J-1), X(J)] → D1 ou D10
```

Deux symboles peuvent avoir exactement la même valeur d’une feature au jour `J`, tout en ayant suivi des trajectoires opposées.

Exemple :

```text
                J-5   J-4   J-3   J-2   J-1    J

Symbol A RSI     32    35    40    45    50    55
Symbol B RSI     72    68    64    61    58    55
```

Au jour `J` :

```text
RSI_A(J) = RSI_B(J) = 55
```

Mais :

```text
Symbol A :
RSI en forte remontée

Symbol B :
RSI en forte détérioration
```

La valeur finale masque donc une information potentiellement directionnelle.

Cette campagne doit rechercher des **patterns temporels précurseurs** qui distinguent les futurs :

```text
D1  = extrême négatif
D10 = extrême positif
```

---

# 1. Architecture actuelle à respecter

L’architecture actuelle de l’application est :

```text
                     Oracle Extreme
                           │
                  "extrême probable"
                           │
              ┌────────────┴────────────┐
              │                         │
      Per-Symbol LONG           Per-Symbol SHORT
              │                         │
         LONG candidate             SHORT candidate
```

Oracle Extreme sert à détecter :

```text
AMPLITUDE / TAIL PROBABILITY
```

Oracle Extreme ne doit PAS être transformé en modèle directionnel.

Les deux modèles actuels restent séparés :

```text
Per-Symbol LONG
Per-Symbol SHORT
```

Cette campagne ajoute un composant de recherche supplémentaire :

```text
TEMPORAL D1/D10 CLASSIFIER
```

dont le rôle est :

```text
parmi les mouvements extrêmes,
estimer si la trajectoire récente ressemble davantage
à un futur D1 ou à un futur D10
```

Architecture cible potentielle :

```text
                       Oracle Extreme
                             │
                    "extrême probable"
                             │
                             ▼
                Temporal D1/D10 Classifier
                             │
                  ┌──────────┴──────────┐
                  │                     │
          p_d10_given_tail      p_d1_given_tail
                  │                     │
                  ▼                     ▼
         Per-Symbol LONG       Per-Symbol SHORT
                  │                     │
                  ▼                     ▼
             LONG trade            SHORT trade
```

Sémantique :

```text
Oracle Extreme
= amplitude / probabilité d'extrême

Temporal D1/D10 classifier
= polarité probable de l'extrême

Per-Symbol LONG / SHORT
= confirmation spécifique au ticker
```

---

# 2. Question scientifique principale

Nous connaissons historiquement, pour l’univers de recherche d’environ 400 symboles, les déciles réalisés :

```text
D1 ... D10
```

sur une période approximative :

```text
2020 → 2025
```

La question principale est :

> **Les trajectoires temporelles des features disponibles avant J permettent-elles de distinguer les futurs D1 des futurs D10 ?**

Target :

```text
y = 0 → D1 réel
y = 1 → D10 réel
```

Pour la première expérience scientifique :

```text
D2-D9 sont exclus
```

afin d’étudier la séparabilité pure entre les deux tails.

---

# 3. Ne pas confondre classification D1/D10 et direction universelle

Ce modèle ne doit PAS répondre à :

```text
"cette action va-t-elle monter ou baisser ?"
```

sur toutes les observations.

Il répond à une question conditionnelle :

```text
"sachant que cette observation appartient à un tail,
ressemble-t-elle davantage à un futur D1 ou D10 ?"
```

Pendant Dataset A/B, la sortie brute doit être nommée :

```text
tail_polarity_score
```

Elle représente un classement relatif appris sur la population D1/D10. Elle ne
doit pas encore être présentée comme une probabilité calibrée sur le pool Oracle
complet. La notation suivante n'est autorisée qu'après validation et calibration
sur Dataset C, où D2-D9 sont réintroduits :

```text
p_d10_given_tail
p_d1_given_tail = 1 - p_d10_given_tail
```

Ne pas appeler cette sortie simplement :

```text
p_up
p_long
p_short
```

car cela serait conceptuellement incorrect.

Une valeur élevée signifie d'abord « ressemble davantage à un futur D10 qu'à
un futur D1 ». Elle ne garantit ni un rendement absolu positif, ni que
l'observation réalisera effectivement un tail.

---

# 4. Réutiliser exactement le contrat de labels Oracle

Ne pas reconstruire une nouvelle définition de D1/D10.

Réutiliser la logique autoritative existante qui construit les labels Oracle.

Le contrat doit conserver exactement :

```text
horizon
forward return definition
cross-sectional universe
percentile computation
D1 boundary
D10 boundary
session calendar
missing data handling
```

Si le contrat Oracle actuel est H20 :

```text
D1  = bottom 10% realized H20 intra-date
D10 = top 10% realized H20 intra-date
```

alors utiliser exactement cela.

## 4.1 Audit obligatoire : rang relatif vs signe absolu

Les déciles Oracle sont cross-sectionnels. D1 signifie « parmi les moins bons
rendements du jour » et D10 « parmi les meilleurs » ; D1 ne signifie pas
nécessairement rendement négatif et D10 ne signifie pas nécessairement rendement
positif.

Avant tout fit, produire globalement, par année, semestre et régime :

```text
P(future_return < 0 | D1)
P(future_return > 0 | D10)
P(future_return <= -3% | D1)
P(future_return >= +3% | D10)
mean/median future_return de D1 et D10
part des dates où les deux tails ont le même signe absolu
```

Le rapport doit séparer deux verdicts :

```text
RELATIVE_TAIL_RANKING_VERDICT
ABSOLUTE_LONG_SHORT_VERDICT
```

Un bon classement D1/D10 avec une mauvaise cohérence de signe peut rester utile
pour un portefeuille long/short relatif, mais ne valide pas les décisions
LONG/SHORT absolues de l'application.

Produire en début de rapport :

```text
LABEL_CONTRACT
```

avec :

```text
target_horizon
forward_return_definition
D1_definition
D10_definition
universe_definition
signal_date_definition
target_available_at_rule
```

---

# 5. Grain du dataset

Grain obligatoire :

```text
1 ligne = 1 symbol × 1 signal_date J
```

Pour cette ligne, les inputs temporels utilisent uniquement :

```text
J-N ... J
```

Le target utilise uniquement :

```text
future realized return
```

selon le contrat Oracle.

Ne pas utiliser :

```text
trade events
partial exits
lifecycle events
backtest positions
duplicated executions
```

Le dataset est un dataset de signal/recherche, pas un dataset de trades.

---

# 6. Question critique : quelle valeur de N ?

Ne PAS choisir arbitrairement :

```text
N = 5
```

ou :

```text
N = 10
```

après avoir vu les résultats.

Le choix de `N` fait partie de l’expérience scientifique.

Pré-enregistrer exactement trois fenêtres principales :

```text
N = 3 sessions
N = 5 sessions
N = 10 sessions
```

Interprétation :

```text
N=3
→ dynamique très récente
→ environ 3 séances

N=5
→ dynamique courte
→ environ 1 semaine de bourse

N=10
→ dynamique intermédiaire
→ environ 2 semaines de bourse
```

Ne pas ajouter d’autres valeurs de N pendant la campagne principale.

Interdit dans cette première campagne :

```text
N=2
N=4
N=6
N=7
N=8
N=9
N=12
N=15
N=20
N=30
...
```

afin d’éviter un sweep massif de fenêtres.

---

# 7. N=20 : uniquement comme test secondaire conditionnel

Une fenêtre :

```text
N = 20
```

peut être pertinente pour environ un mois de marché.

Mais ne pas l’inclure immédiatement.

Autoriser `N=20` uniquement si les résultats montrent une progression cohérente :

```text
N=3 < N=5 < N=10
```

sur les métriques OOF principales.

Exemple :

```text
same-date AUC

N=3  = 0.535
N=5  = 0.552
N=10 = 0.571
```

Dans ce cas seulement :

```text
tester N=20
```

comme expérience secondaire pré-déclarée.

Si :

```text
N=5 > N=10
```

ne pas essayer N=20 pour sauver artificiellement l’hypothèse.

---

# 8. Comment sélectionner le N final

Le meilleur N ne doit PAS être choisi sur :

```text
training AUC
in-sample accuracy
une seule année
un seul fold
portfolio return
```

Le choix doit être basé en priorité sur :

```text
1. same-date AUC OOF moyenne
2. same-date AUC OOF médiane
3. stabilité par fold
4. % dates AUC > 0.50
5. % dates AUC > 0.55
6. enrichissement D10 dans les scores hauts
7. enrichissement D1 dans les scores bas
8. monotonicité des buckets de score
9. stabilité annuelle
```

Règle de sélection :

```text
choisir le plus petit N
dont la performance est économiquement
et statistiquement proche du meilleur N
```

Exemple :

```text
N=5  same-date AUC = 0.567
N=10 same-date AUC = 0.569
```

Préférer :

```text
N=5
```

car :

```text
plus simple
moins de missing
plus réactif
moins de dépendance historique
moins de risque d’overfitting
```

---

# 9. Pourquoi ne pas choisir directement N=5 ?

`N=5` est une hypothèse raisonnable, mais il ne faut pas la considérer comme vraie avant test.

Il est possible que :

```text
N=3
```

capture mieux un signal extrêmement récent.

Il est possible que :

```text
N=10
```

capture mieux une construction progressive de pression directionnelle.

Le protocole doit donc répondre empiriquement à :

```text
3 jours ?
5 jours ?
10 jours ?
```

sans utiliser le futur pour décider.

---

# 10. Trois niveaux d’information temporelle

Ne pas partir directement vers un LSTM.

Tester trois niveaux progressivement.

```text
T0 = état au jour J

T1 = état J + variations temporelles résumées

T2 = état J + variations + forme/statistiques de trajectoire

T3 = séquence brute J-N → J
```

La complexité n’est ajoutée que si le niveau précédent montre que la dynamique temporelle apporte réellement de l’information.

---

# 11. Phase T0 — baseline jour J uniquement

Construire :

```text
T0 = X(J)
```

avec les features PIT disponibles au jour `J`.

Exemples :

```text
RSI_J
momentum_J
relative_strength_J
volume_ratio_J
ATR_J
short_interest_J
options_skew_J
money_flow_J
eps_revision_J
```

Cette baseline est obligatoire.

Elle permet de répondre à :

```text
"combien apporte réellement la trajectoire
par rapport à la photographie de J ?"
```

---

# 12. Phase T1 — deltas temporels

Pour chaque fenêtre `N ∈ {3,5,10}`, construire des changements signés.

Forme générale :

```text
delta_N = X(J) - X(J-N)
```

Pour les features où un ratio est économiquement pertinent :

```text
pct_change_N = X(J) / X(J-N) - 1
```

Exemples :

```text
rsi_delta_3
rsi_delta_5
rsi_delta_10

momentum_delta_3
momentum_delta_5
momentum_delta_10

relative_strength_delta_3
relative_strength_delta_5
relative_strength_delta_10

options_skew_delta_3
options_skew_delta_5
options_skew_delta_10
```

Ne jamais convertir automatiquement les deltas en valeur absolue.

Le signe est précisément l’information recherchée.

---

# 13. Phase T2 — pente de trajectoire

Pour chaque feature quotidienne suffisamment dense, calculer une pente sur :

```text
J-N ... J
```

Exemple :

```text
slope_N
```

à partir d’une régression linéaire :

```text
feature ~ session_index
```

Exemples :

```text
rsi_slope_5
rsi_slope_10
money_flow_slope_5
relative_strength_slope_10
options_skew_slope_5
```

Le but est de différencier :

```text
niveau identique mais tendance montante
vs
niveau identique mais tendance descendante
```

---

# 14. Phase T2 — accélération

Quand économiquement pertinente, construire une accélération simple.

Exemple :

```text
recent_slope - older_slope
```

ou :

```text
delta_recent - delta_previous
```

Exemples :

```text
momentum_acceleration
money_flow_acceleration
relative_strength_acceleration
options_skew_acceleration
```

Limiter les variantes.

Ne pas faire des dizaines de définitions d’accélération.

Une seule définition canonique par type de feature.

---

# 15. Phase T2 — dispersion et stabilité de trajectoire

Pour les features quotidiennes, considérer :

```text
mean_N
std_N
min_N
max_N
range_N
```

uniquement si économiquement justifié.

Exemple :

```text
rsi_mean_5
rsi_std_5
rsi_range_5

money_flow_mean_10
money_flow_std_10
```

Ne pas générer mécaniquement toutes les statistiques pour toutes les features.

Créer uniquement les transformations pertinentes par famille.

---

# 16. Phase T2 — nombre de jours positifs/négatifs

Pour certaines features signées :

```text
positive_days_N
negative_days_N
```

Exemple :

```text
money_flow_positive_days_5
money_flow_negative_days_5

relative_strength_positive_days_10
```

Cela permet de distinguer :

```text
+10 obtenu en une seule séance
```

de :

```text
+10 obtenu progressivement sur 8 séances
```

---

# 17. Prix et rendement : patterns temporels

Pour les prix, tester quelques features canoniques :

```text
ret_1d
ret_3d
ret_5d
ret_10d

positive_return_days_N
negative_return_days_N

close_slope_N

distance_high_N
distance_low_N
```

Éviter un énorme catalogue de patterns candlestick.

L’objectif est de tester la dynamique, pas de faire du pattern mining non contrôlé.

---

# 18. Momentum et relative strength

Priorité élevée.

Construire par exemple :

```text
momentum_J
momentum_delta_N
momentum_slope_N
momentum_acceleration_N

relative_strength_J
relative_strength_delta_N
relative_strength_slope_N
```

Le signal recherché peut être :

```text
un leader relatif dont la dynamique s’améliore
→ D10

un leader apparent dont la dynamique se dégrade
→ D1
```

Ne pas imposer le signe a priori.

Le modèle doit apprendre.

---

# 19. Volume et liquidité

Pour les données quotidiennes :

```text
volume_ratio_J
volume_ratio_delta_N
volume_slope_N

turnover_J
turnover_delta_N

spread_J
spread_delta_N
```

si disponible.

Tester également :

```text
price_direction × volume_direction
```

avec une définition simple et pré-enregistrée.

---

# 20. Volatilité

La volatilité est souvent une information d’amplitude plutôt que de direction.

Tester néanmoins :

```text
ATR_J
ATR_delta_N
realized_vol_J
realized_vol_delta_N
```

mais classer ensuite la famille via :

```text
direction_vs_amplitude
```

Une amélioration d’Oracle Extreme ne signifie pas une amélioration D1/D10.

---

# 21. Cross-sectional et sector-relative

Pour chaque jour `t` dans la fenêtre :

les transformations cross-sectionnelles doivent être calculées uniquement avec les données disponibles à `t`.

Exemples :

```text
xs_rank_J
xs_rank_delta_N

sector_rank_J
sector_rank_delta_N

relative_strength_sector_delta_N
```

Ne jamais calculer les ranks historiques avec une information disponible après `t`.

---

# 22. Macro et régime

Les features macro peuvent être utilisées :

```text
VIX
VXN
MOVE
SPY trend
market regime
breadth
```

mais attention :

elles sont souvent identiques pour tous les symboles d’une même date.

Elles peuvent être utiles en interaction :

```text
symbol trajectory × market regime
```

mais ne doivent pas créer artificiellement une séparation D1/D10 uniquement par effet de date.

C’est pourquoi :

```text
SAME-DATE AUC
```

est une métrique centrale.

---

# 23. Nouvelles données Eroya : priorité aux trajectoires

Pour les nouvelles données Eroya, ne pas se limiter à la valeur à `J`.

Tester en priorité :

```text
niveau
variation
pente
accélération
persistance
```

car la direction peut être contenue davantage dans l’évolution que dans le niveau absolu.

---

# 24. Short interest

Exemple important :

```text
Symbol A :
10% → 11% → 12% → 13% → 15%

Symbol B :
22% → 20% → 18% → 17% → 15%
```

Au jour J :

```text
short_interest = 15%
```

dans les deux cas.

Mais :

```text
A = pression short en augmentation
B = short covering
```

Construire si disponible PIT :

```text
short_interest_J
short_interest_delta_5
short_interest_delta_10
short_interest_slope_5
short_interest_slope_10
days_since_short_interest_update
```

Attention à la fréquence réelle de publication.

---

# 25. Short volume

Si disponible quotidiennement :

```text
short_volume_ratio_J
short_volume_ratio_delta_3
short_volume_ratio_delta_5
short_volume_ratio_delta_10
short_volume_ratio_slope_N
```

Ne pas supposer automatiquement :

```text
short volume élevé = futur D1
```

Cela peut aussi être lié à :

```text
hedging
market making
liquidity
amplitude
```

Le harnais décide.

---

# 26. Borrow fee / utilization / shares available

Si disponibles :

```text
borrow_fee_J
borrow_fee_delta_N
borrow_fee_slope_N

utilization_J
utilization_delta_N

shares_available_J
shares_available_delta_N
```

Une hausse rapide peut être différente d’un niveau déjà élevé mais stable.

Tester séparément :

```text
direction
vs
amplitude/squeeze risk
```

---

# 27. Options skew

Priorité élevée si historique PIT disponible.

Construire :

```text
put_call_volume_ratio_J
put_call_volume_ratio_delta_N

put_call_oi_ratio_J
put_call_oi_ratio_delta_N

put_iv_minus_call_iv_J
put_iv_minus_call_iv_delta_N

downside_skew_J
downside_skew_delta_N
downside_skew_slope_N
```

Ne pas considérer :

```text
IV brute
```

comme directionnelle par défaut.

---

# 28. Options flow

Si trades / premium flow réellement disponibles :

```text
bullish_premium_N
bearish_premium_N
net_options_premium_N

net_options_premium_delta
net_options_premium_slope
```

Ne jamais inventer :

```text
aggressor side
```

si le provider ne le fournit pas.

Si une heuristique est utilisée, la documenter exactement.

---

# 29. Capital flow / money flow

Pour un flux signé :

```text
flow_J
flow_sum_3
flow_sum_5
flow_sum_10

flow_delta_N
flow_slope_N

positive_flow_days_N
negative_flow_days_N
```

C’est une famille particulièrement intéressante pour cette campagne.

---

# 30. Analyst revisions

Ces données ne changent pas nécessairement tous les jours.

Construire plutôt :

```text
eps_revision_latest
eps_revision_sum_N
positive_eps_revisions_N
negative_eps_revisions_N
net_eps_revisions_N

revenue_revision_latest
net_revenue_revisions_N

target_revision_latest
net_target_revisions_N

days_since_last_revision
```

Ne jamais reconstruire artificiellement un historique à partir d’un snapshot actuel.

---

# 31. Features événementielles

Pour :

```text
upgrade/downgrade
insider trade
earnings guidance
Form 4
institutional event
```

ne pas forward-fill naïvement un événement.

Construire plutôt :

```text
event_today
event_count_N
positive_event_count_N
negative_event_count_N
net_event_count_N
days_since_last_event
event_value_sum_N
```

---

# 32. Forward-fill : règle stricte

Pour une feature de type état/consensus :

```text
feature(t) =
dernière valeur réellement connue à t
```

avec :

```text
available_at <= decision_cutoff(t)
```

Le forward-fill est autorisé uniquement :

```text
après la date réelle de disponibilité
```

et jamais vers le passé.

---

# 33. PIT obligatoire sur chaque point de la séquence

Pour une observation finale à `J`, il ne suffit pas que la feature soit PIT au jour `J`.

Chaque point :

```text
X(J-N)
X(J-N+1)
...
X(J)
```

doit être causal.

Assertion :

```text
available_at(feature at t) <= cutoff(t)
```

pour tout :

```text
t ∈ [J-N, J]
```

Si une violation est détectée :

```text
FAIL_PIT
```

et stopper l’expérience concernée.

---

# 34. Pas de backward-fill

Interdiction absolue :

```text
utiliser une valeur publiée à J
pour remplir J-1, J-2, J-3
```

Exemple :

```text
consensus EPS observé pour la première fois le 10 juin
```

ne peut jamais être utilisé :

```text
le 9 juin
le 8 juin
...
```

---

# 35. Age de l’information

Pour les features irrégulières, ajouter :

```text
days_since_last_update
```

Exemple :

```text
analyst_target = 120
days_since_last_target_update = 2
```

est différent de :

```text
analyst_target = 120
days_since_last_target_update = 90
```

L’âge de l’information peut être lui-même directionnel.

---

# 36. Phase T3 — séquence brute

Seulement après T0/T1/T2.

Construire :

```text
X_sequence =
[
  X(J-N),
  X(J-N+1),
  ...
  X(J)
]
```

Shape conceptuel :

```text
[n_sessions, n_features]
```

---

# 37. Convention N obligatoire

Adopter explicitement :

```text
window N = [J-N, ..., J]
```

Donc :

```text
N=3  → 4 observations
N=5  → 6 observations
N=10 → 11 observations
```

Ne pas mélanger :

```text
"N jours incluant J"
```

et :

```text
"J-N à J"
```

Le rapport doit toujours indiquer cette convention.

---

# 38. Modèles à tester

Ordre obligatoire :

```text
M0 = Logistic Regression sur T0
M1 = Logistic Regression sur T1/T2
M2 = LightGBM
M3 = CatBoost
M4 = modèle séquentiel simple uniquement si justifié
```

Ne pas commencer par un Transformer.

---

# 39. Modèle séquentiel recommandé

Si la séquence brute apporte un intérêt potentiel, tester en priorité :

```text
1D-CNN ou TCN
```

avant :

```text
LSTM
Transformer
```

Raison :

```text
séquences courtes
dataset limité
moins de paramètres
audit plus facile
moins de risque d’overfitting
```

LSTM peut ensuite être un challenger.

Transformer uniquement si les modèles plus simples montrent clairement une information temporelle non capturée.

---

# 40. Baseline flattened sequence

Avant un réseau neuronal, faire un contrôle simple :

```text
flatten [
X(J-N),
...
X(J)
]
```

puis :

```text
Logistic Regression
LightGBM
```

Cela permet de savoir si la raw sequence contient de l’information sans attribuer automatiquement le gain à une architecture deep learning.

---

# 41. Dataset A — séparabilité fondamentale

Construire :

```text
univers recherche ~400 symboles
```

Pour chaque date :

```text
garder uniquement D1 + D10 réels
```

Target :

```text
D1  = 0
D10 = 1
```

Inputs :

```text
J-N → J
```

Dataset A répond :

> Les vrais tails sont-ils intrinsèquement séparables par leurs trajectoires préalables ?

---

# 42. Dataset B — population Oracle réelle

Après Dataset A :

utiliser les candidats :

```text
Oracle TOP20% prédit à J
```

Mais uniquement avec prédictions :

```text
OOF
WF
PIT
```

Puis garder pour l’entraînement initial :

```text
D1 + D10
```

Dataset B répond :

> Parmi les candidats qu’Oracle aurait réellement sélectionnés, les trajectoires permettent-elles de distinguer D1 de D10 ?

Dataset B est plus proche du problème production.

---

# 43. Dataset C — production-like avec D2-D9 réintroduits

Si le classifier passe A et B :

prendre :

```text
TOUS les candidats Oracle TOP20
```

y compris ceux qui réalisent :

```text
D2-D9
```

Scorer chaque candidat avec :

```text
tail_polarity_score
```

Ne renommer ce score `p_d10_given_tail` qu'après calibration OOF sur cette
population complète et vérification de la fiabilité par buckets.

Puis mesurer par bucket de score :

```text
D1%
D2%
...
D10%

BAD = D1-D3
MID = D4-D7
GOOD = D8-D10

mean forward return
median forward return
```

C’est une étape obligatoire avant intégration.

---

# 44. Pourquoi Dataset C est essentiel

Le classifier est entraîné sur :

```text
D1 vs D10
```

mais en production Oracle lui présentera aussi :

```text
D2-D9
```

Il faut donc vérifier que :

```text
scores élevés
→ GOOD et D10 augmentent

scores faibles
→ BAD et D1 augmentent
```

Si cette propriété disparaît :

```text
classifier scientifiquement intéressant
mais non exploitable en production
```

---

# 45. Walk-forward obligatoire

Aucun random split.

Exemple conceptuel :

```text
train 2020-2021 → test 2022
train 2020-2022 → test 2023
train 2020-2023 → test 2024
train 2020-2024 → test 2025
```

Adapter aux données réelles.

Utiliser si possible le framework WF existant.

---

# 46. Purge selon l’horizon Oracle

Pour H20 :

aucune ligne de train ne doit avoir un target dont la réalisation chevauche le test.

Condition conceptuelle :

```text
target_available_at < test_fold_start
```

ou contrat causal Oracle équivalent.

---

# 47. Oracle OOF obligatoire pour Dataset B/C

Si l’Oracle utilisé pour sélectionner historiquement les candidats a été entraîné jusqu’en 2025 :

```text
ne pas utiliser ses prédictions in-sample 2020-2025
comme si elles étaient OOF
```

Utiliser :

```text
Oracle OOF historique
```

ou reconstruire un vrai :

```text
walk-forward Oracle
```

avant Dataset B/C.

## 47.1 Sélection du modèle et confirmation séparée

Les prédictions OOF utilisées pour choisir N, la représentation et le modèle
servent au développement. Elles ne constituent pas une confirmation intacte.

Le protocole doit distinguer :

```text
DEVELOPMENT_WF
→ choix figé de N / représentation / modèle
→ TEMPORAL_CONFIRMATION_BLOCK non utilisé pour ce choix
```

Si aucune période réellement intacte n'existe parce que ses résultats ont déjà
guidé les expériences précédentes, le rapport doit déclarer :

```text
FINAL_CONFIRMATION_STATUS = UNAVAILABLE_ALREADY_OBSERVED
serving_ready = false
research_only = true
```

Dans ce cas, un nested walk-forward et un bootstrap par date mesurent la
robustesse interne, mais ne doivent jamais être présentés comme une validation
finale indépendante.

---

# 48. Preprocessing train-only

Dans chaque fold :

```text
imputation
scaling
winsorization
normalization
feature selection
categorical encoding
```

doivent être appris uniquement sur :

```text
TRAIN
```

puis appliqués à :

```text
TEST
```

---

# 49. Aucun symbol ID dans le classifier partagé initial

Ne pas utiliser :

```text
symbol
ticker ID
```

comme feature dans le premier classifier partagé.

On veut apprendre :

```text
des patterns de trajectoire
```

et non mémoriser :

```text
quels symboles ont historiquement plus de D1/D10
```

---

# 50. Dates non prédictives directement

Ne pas utiliser directement :

```text
signal_date ordinal
year encoded as integer
timestamp numeric
```

comme feature brute.

Le régime peut être représenté par des features économiques PIT, mais pas par un raccourci temporel arbitraire.

---

# 51. Equal-date weighting

Les targets D1/D10 sont cross-sectionnels par date.

Une date avec plus de lignes ne doit pas dominer excessivement.

Tester :

```text
weight(row at J) = 1 / number_of_rows_at_J
```

avec normalisation si nécessaire.

Documenter :

```text
weighted
vs
unweighted
```

comme contrôle.

---

# 52. Métrique principale : SAME-DATE AUC OOF

Calculer pour chaque date J :

```text
AUC entre D1 et D10
```

uniquement si les deux classes sont présentes.

Puis :

```text
mean_same_date_auc
median_same_date_auc
std_same_date_auc

% dates AUC > 0.50
% dates AUC > 0.55
% dates AUC > 0.60
```

Cette métrique est prioritaire.

Elle répond précisément à :

> Le même jour, le modèle classe-t-il correctement les futurs D10 au-dessus des futurs D1 ?

---

# 53. AUC OOF globale

Produire également :

```text
global_oof_auc
AUC par fold
AUC par année
```

Mais ne pas utiliser la seule AUC globale pour conclure.

---

# 54. Pairwise accuracy

Pour chaque date :

comparer chaque score D10 avec chaque score D1.

Mesurer :

```text
P(score_D10 > score_D1)
```

Puis agréger par date.

---

# 55. Score buckets

Sur les scores OOF :

```text
p_d10_given_tail
```

créer :

```text
10 déciles
```

Pour chaque bucket :

```text
n
D1%
D10%
mean forward return
median forward return
```

On cherche :

```text
score bas → D1 enrichi
score haut → D10 enrichi
```

et idéalement une relation monotone.

---

# 56. Extrêmes du score

Mesurer particulièrement :

```text
bottom10 score
bottom20 score
top20 score
top10 score
```

Fournir :

```text
P(D1 | bottom10 score)
P(D1 | bottom20 score)

P(D10 | top20 score)
P(D10 | top10 score)
```

---

# 57. Métriques secondaires

Produire :

```text
ROC-AUC
PR-AUC
accuracy
balanced_accuracy
precision_D10
recall_D10
precision_D1
recall_D1
F1
log_loss
Brier score
```

Ne pas sélectionner le modèle uniquement sur F1 ou accuracy.

---

# 58. Stabilité annuelle

Pour chaque année OOF :

```text
AUC
same-date AUC
top10 D10 enrichment
bottom10 D1 enrichment
```

On cherche :

```text
stabilité du signe
```

plus qu’un pic sur une seule année.

---

# 59. Stabilité sectorielle

Calculer si échantillon suffisant :

```text
AUC by sector
same-date AUC by sector
```

Identifier :

```text
universel
sector-dependent
```

sans créer immédiatement des modèles sectoriels.

---

# 60. Stabilité par symbole

Calculer si échantillon suffisant :

```text
AUC par symbol
n_D1
n_D10
```

Puis :

```text
median_symbol_auc
% symbols > 0.50
% symbols > 0.55
```

Ne pas conclure pour les symboles avec trop peu de tails.

---

# 61. Comparaison directe des N

Pour chaque représentation temporelle et modèle, produire :

| N | OOF AUC | Mean same-date AUC | Median same-date AUC | % dates > .50 | % dates > .55 | Top10 D10% | Bottom10 D1% |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3 | | | | | | | |
| 5 | | | | | | | |
| 10 | | | | | | | |

Puis indiquer :

```text
BEST_N_RAW
BEST_N_STABLE
SELECTED_N
```

avec justification.

---

# 62. Test de significativité du choix N

Ne pas considérer une différence minuscule comme réelle.

Exemple :

```text
N=5  AUC = 0.566
N=10 AUC = 0.568
```

Ne pas conclure :

```text
N=10 meilleur
```

automatiquement.

Utiliser un bootstrap par date ou méthode équivalente sur les prédictions OOF pour estimer l’incertitude de :

```text
Δ same-date AUC
```

Favoriser le N plus court si la différence n’est pas convaincante.

---

# 63. Ablation valeur J vs évolution

Comparer explicitement :

```text
A = niveau J uniquement
B = trajectoire uniquement
C = niveau J + trajectoire
```

Exemple :

```text
A : X(J)
B : delta/slope/acceleration
C : A+B
```

Question :

> L’alpha directionnel vient-il de l’état actuel, de la dynamique, ou de leur combinaison ?

---

# 64. Ablation feature families

## 64.1 Budget de features pour la campagne principale

Ne pas appliquer mécaniquement toutes les transformations aux quelque 129
features EXPERT. La phase principale est limitée à environ 20-30 features de
base denses et économiquement directionnelles, avec une définition canonique
des transformations par famille.

Produire avant fit :

```text
n_base_features
n_generated_features_by_N
duplicate_or_equivalent_features
correlation_clusters
coverage_by_feature
```

Les features déjà équivalentes à une trajectoire (`momentum_3/5/10`,
`rsi_slope`, pentes EMA, `accel_3_5`, `decay_5_10`, etc.) doivent être signalées
pour éviter de compter deux fois la même information.

Comparer quelques familles principales :

```text
PRICE_MOMENTUM_TEMPORAL
VOLUME_LIQUIDITY_TEMPORAL
RELATIVE_STRENGTH_TEMPORAL
FUNDAMENTALS_TEMPORAL
SENTIMENT_TEMPORAL
CAPM_TEMPORAL
CROSS_SECTIONAL_TEMPORAL
```

Ne pas faire toutes les combinaisons possibles.

---

# 65. Eroya — ablation incrémentale par famille

Cette section est différée. Ne pas engager un nouveau backfill Eroya ni tester
T3 tant que la baseline locale T0/T1/T2 n'a pas franchi le gate de poursuite.
Les expériences Eroya déjà réalisées constituent un prior défavorable ; seules
des séries historiques PIT suffisamment denses justifient une nouvelle ablation.

Après baseline actuelle :

```text
BASE = existing PIT temporal features
```

tester séparément :

```text
BASE + EROYA_SHORT_TEMPORAL
BASE + EROYA_OPTIONS_TEMPORAL
BASE + EROYA_FLOW_TEMPORAL
BASE + EROYA_INSIDERS_TEMPORAL
BASE + EROYA_INSTITUTIONAL_TEMPORAL
BASE + EROYA_ANALYST_TEMPORAL
```

Une famille à la fois.

---

# 66. Comparaison sur mêmes lignes

Pour chaque ablation Eroya :

```text
baseline
vs
baseline + Eroya family
```

doivent utiliser exactement :

```text
les mêmes symbol × dates
```

sur l’intersection de coverage.

Produire :

```text
baseline_same_rows_auc
enriched_same_rows_auc
delta_auc

baseline_same_rows_same_date_auc
enriched_same_rows_same_date_auc
delta_same_date_auc
```

---

# 67. Direction vs amplitude

Pour chaque famille, mesurer séparément :

```text
D1 vs D10 predictability
```

et :

```text
tail vs middle predictability
```

Définition obligatoire :

```text
DIRECTION = D1 vs D10
AMPLITUDE = (D1 ∪ D10) vs D2-D9
```

Ne pas réutiliser aveuglément l'ancien champ `dir_vs_amp` de
`modelFactory/global_direction/temporal.py` : son implémentation historique
`_auc_amplitude()` compare D1 à D10 au lieu de comparer tails à middle. Les AUC
directionnelles historiques restent informatives, mais ce champ amplitude doit
être recalculé correctement dans V2.

Verdicts possibles :

```text
DIRECTIONAL
AMPLITUDE_ONLY
BOTH
NO_SIGNAL
```

Une feature très bonne pour Oracle mais neutre D1/D10 est :

```text
AMPLITUDE_ONLY
```

Elle ne doit pas être présentée comme nouvelle information directionnelle, mais
elle constitue un résultat potentiellement utile. Elle doit alors être évaluée
comme candidate incrémentale pour Oracle Extreme.

L'évaluation amplitude doit comparer, sur exactement les mêmes lignes OOF :

```text
ORACLE_BASE
vs
ORACLE_BASE + CANDIDATE_FEATURE_OR_FAMILY
```

Produire au minimum :

```text
tail_vs_middle_auc
average_precision_extreme
precision_at_top_10pct
precision_at_top_20pct
lift_at_top_10pct
lift_at_top_20pct
mean/median realized_absolute_return par bucket
monotonicity des buckets
delta vs Oracle seul
stabilité par fold, semestre, symbole et régime
```

Une forte AUC amplitude autonome ne suffit pas : la famille doit apporter une
information incrémentale au score Oracle existant. Si elle ne fait que reproduire
`proba_extreme`, son verdict est `REDUNDANT_WITH_ORACLE`.

Verdicts amplitude autorisés :

```text
AMPLITUDE_INCREMENTAL_GO_RESEARCH
AMPLITUDE_ONLY_WEAK_SIGNAL
REDUNDANT_WITH_ORACLE
NO_AMPLITUDE_SIGNAL
```

Une candidate amplitude validée doit être dirigée vers une ablation du profil
Oracle, pas vers les modèles Per-Symbol LONG/SHORT. Elle peut ensuite servir à
mieux prioriser les événements, calibrer le gate ou prévoir l'amplitude attendue.
Elle ne doit pas augmenter mécaniquement la taille des positions : une amplitude
élevée représente aussi davantage de risque.

---

# 68. Missing data temporels

Ne jamais remplir aveuglément :

```text
missing = 0
```

sauf signification économique réelle.

Pour les séquences :

```text
missingness
```

peut elle-même être informative.

Ajouter éventuellement :

```text
is_missing
days_since_update
```

mais éviter une explosion du nombre de variables.

---

# 69. Coverage minimum

Pour chaque feature/famille :

produire :

```text
coverage overall
coverage by year
coverage by symbol
coverage by date
```

Une famille avec un excellent AUC sur 8% du dataset doit être marquée :

```text
INCONCLUSIVE_COVERAGE
```

tant que la couverture n’est pas suffisante.

---

# 70. Source/PIT audit Eroya

Avant backfill complet, tester quelques symboles pour chaque endpoint.

Produire :

```text
SOURCE_ACCESS_REPORT
```

avec :

```text
endpoint
ACCESS_OK / FAIL
historical depth
frequency
published timestamp
available timestamp
PIT usable YES/NO
coverage
```

Ne pas supposer qu’un endpoint documenté est utilisable historiquement.

---

# 71. Raw provider storage

Si de nouvelles données sont collectées :

```text
MySQL = source de vérité
```

Stockage append-only recommandé :

```text
symbol
provider
metric_type
observed_at
published_at
available_at
ingested_at
value
raw_payload_json
raw_hash
schema_version
```

Ne pas écraser les observations historiques.

---

# 72. Temporal feature computation

Toutes les features temporelles doivent être reconstruites à partir des observations PIT historiques.

Pour chaque signal J :

```text
window = market sessions [J-N, ..., J]
```

et non :

```text
calendar days arbitraires
```

Utiliser le calendrier NYSE existant pour le marché US.

Pour le marché chinois, utiliser ultérieurement le calendrier de marché chinois approprié.

---

# 73. Pas de look-ahead via rolling

Attention aux implémentations pandas.

Les rolling doivent être :

```text
groupby(symbol)
sort by date
rolling uniquement vers le passé
```

Ne jamais faire de rolling entre symboles.

Ajouter un test automatique :

```text
aucune valeur à t ne dépend d’une ligne > t
```

---

# 74. Aucun tuning massif

Pendant cette campagne :

```text
N figés = 3,5,10
features transforms limitées
seeds fixes
hyperparamètres fixes
```

Pas de :

```text
Optuna
grid search massif
hundreds of windows
feature mining après résultat
symbol-specific thresholds
```

---

# 75. Logistic Regression comme contrôle

Toujours commencer par Logistic Regression.

Pourquoi :

```text
si les trajectoires contiennent une séparation simple,
LR doit en capturer une partie
```

Si :

```text
LR ≈ 0.50
LGBM ≈ 0.50
CatBoost ≈ 0.50
```

cela suggère surtout un manque d’information.

---

# 76. LightGBM / CatBoost

Tester ensuite les interactions non linéaires.

Exemples :

```text
RSI slope positif
+
options skew amélioration
+
money flow positif
+
relative strength stable
```

peuvent être plus informatifs conjointement qu’individuellement.

Pas de tuning spécifique par N.

Ajouter un challenger de ranking pairwise groupé strictement par `signal_date` :

```text
CatBoost PairLogit ou ranker équivalent
group_id = signal_date
```

La classification binaire et le ranker doivent partager exactement les mêmes
lignes et folds. Le ranker optimise directement l'ordre D10 > D1 le même jour.
Son score brut ne doit pas être appelé probabilité sans calibration OOF séparée.

---

# 77. Modèles séquentiels

Tester uniquement si les modèles tabulaires temporels montrent déjà :

```text
un signal stable
```

ou si la raw flattened sequence montre un gain.

Ordre conseillé :

```text
1. TCN / 1D-CNN
2. LSTM
3. Transformer seulement si justification forte
```

---

# 78. Pourquoi ne pas commencer par LSTM

Le but de la campagne est d’identifier :

```text
si l’information temporelle existe
```

avant de tester :

```text
quel modèle complexe peut l’extraire
```

Un deep model puissant peut facilement :

```text
surapprendre les dates
surapprendre les symboles
surapprendre les régimes
```

et donner une illusion de signal.

---

# 79. Feature importance

Après OOF :

```text
permutation importance
```

par famille ou feature.

SHAP autorisé pour compréhension.

Interdit :

```text
regarder SHAP sur tout 2020-2025
supprimer les faibles
réentraîner
puis appeler le résultat OOS
```

Toute sélection post-hoc doit être déclarée comme nouvelle campagne.

---

# 80. Analyse de patterns concrets

Si un modèle passe :

identifier quelques patterns fréquents.

Exemples à rechercher sans les imposer :

```text
D10 :
relative strength ↑
money flow ↑
options skew bullish
short pressure ↓
analyst revisions ↑

D1 :
relative strength ↓
money flow ↓
options skew bearish
short pressure ↑
analyst revisions ↓
```

Mais ces patterns doivent provenir du modèle/OOF.

Ne pas les coder manuellement dans le target.

---

# 81. Cluster de trajectoires — exploration secondaire

Optionnel après le test principal :

sur les seuls D1/D10 de train, explorer des clusters de trajectoires.

Objectif :

```text
existe-t-il plusieurs types de D10 ?
existe-t-il plusieurs types de D1 ?
```

Exemples :

```text
D10 momentum breakout
D10 short squeeze
D10 analyst revision

D1 momentum collapse
D1 negative revision
D1 flow distribution
```

Cette exploration est diagnostique.

Ne pas utiliser les clusters du test pour optimiser le modèle principal dans la même campagne.

---

# 82. Tests placebo / sanity checks

Inclure :

```text
randomized labels
```

sur au moins un run de contrôle.

Résultat attendu :

```text
AUC ≈ 0.50
same-date AUC ≈ 0.50
```

Si le placebo donne un AUC élevé :

```text
STOP
```

il existe probablement un leakage.

---

# 83. Reverse-time sanity check

Optionnel mais utile :

vérifier qu’une transformation accidentellement future ne donne pas un score anormal.

L’audit PIT reste la protection principale.

## 83.1 Corporate actions, qualité des prix et biais d'univers

Réutiliser les contrôles découverts pendant E6 : cours ajustés, détection des
ruptures de ticker/corporate actions et exclusion des ratios de prix aberrants.
Une trajectoire contaminée par un split ou un changement de ticker ne doit
jamais devenir un pattern directionnel.

Documenter également si l'univers historique est un univers fixe de survivants
actuels ou un univers réellement PIT. Un univers fixe est acceptable pour un
diagnostic initial, mais impose la mention :

```text
SURVIVORSHIP_BIAS_RISK = true
```

---

# 84. Critères de verdict

### NO_GO

```text
same-date AUC ≈ 0.50
folds instables
aucun enrichissement cohérent
trajectoire n’améliore pas T0
```

### WEAK_SIGNAL

```text
same-date AUC ~0.52-0.54
amélioration temporelle cohérente
mais faible
```

### GO_RESEARCH

```text
same-date AUC ~0.55+
majorité des folds > 0.50
stabilité annuelle acceptable
score buckets cohérents
D10 enrichment en haut
D1 enrichment en bas
Dataset C confirme l’effet
```

Gate quantitatif minimal pré-enregistré pour poursuivre au-delà de T2 :

```text
delta_mean_same_date_auc_vs_T0 >= +0.01
majorité nette des folds avec same-date AUC > 0.50
enrichissement monotone des buckets
gain non concentré sur un symbole, une année ou un régime
cohérence économique LONG et SHORT évaluée séparément
```

Une AUC élevée sans cohérence du rendement signé ne valide que le classement
relatif, pas l'intégration au bundle de trading.

### STRONG_GO

Signal sensiblement plus fort, stable, monotone et robuste.

Ces valeurs sont des guides de lecture, pas des seuils à optimiser.

---

# 85. Verdict spécifique sur N

Le rapport final doit obligatoirement répondre :

```text
N=3 : GO / NO_GO
N=5 : GO / NO_GO
N=10: GO / NO_GO
```

Puis :

```text
SELECTED_N = ?
```

avec justification.

Exemple :

```text
SELECTED_N = 5

Reason:
N=5 apporte pratiquement le même same-date AUC que N=10,
avec moins de missing, plus de réactivité et moins de complexité.
```

---

# 86. Rapport comparatif T0/T1/T2/T3

Produire :

| Representation | N | Model | OOF AUC | Same-date AUC | Top10 D10% | Bottom10 D1% | Verdict |
|---|---:|---|---:|---:|---:|---:|---|
| T0 J-only | — | LR | | | | | |
| T1 delta | 3 | LR/LGBM | | | | | |
| T1 delta | 5 | LR/LGBM | | | | | |
| T1 delta | 10 | LR/LGBM | | | | | |
| T2 trajectory | 3 | LGBM/CB | | | | | |
| T2 trajectory | 5 | LGBM/CB | | | | | |
| T2 trajectory | 10 | LGBM/CB | | | | | |
| T3 raw sequence | selected | TCN/LSTM | | | | | |

---

# 87. Eroya temporal comparison

Produire :

| Feature family | Selected N | Base same-date AUC | +Family same-date AUC | Δ | Coverage | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Short/Borrow | | | | | | |
| Options | | | | | | |
| Flow | | | | | | |
| Insiders | | | | | | |
| Institutional | | | | | | |
| Analyst | | | | | | |

---

# 88. Relation future avec Per-Symbol LONG

Seulement si classifier :

```text
GO_RESEARCH
```

tester plus tard :

```text
LONG_BASELINE
vs
LONG_BASELINE + p_d10_given_tail
```

Tout le reste figé.

Mesurer :

```text
D10 enrichment
D8-D10 enrichment
D1-D3 contamination
AUC
PR-AUC
% symbols improved
```

---

# 89. Relation future avec Per-Symbol SHORT

Séparément :

```text
SHORT_BASELINE
vs
SHORT_BASELINE + p_d1_given_tail
```

Tout le reste figé.

Mesurer :

```text
D1 enrichment
D1-D3 enrichment
D8-D10 contamination
AUC
PR-AUC
% symbols improved
```

Ne pas supposer que le gain LONG et SHORT sera symétrique.

---

# 90. Ne pas remplacer immédiatement les modèles actuels

Même si le Temporal D1/D10 classifier est excellent :

```text
ne pas supprimer immédiatement
Per-Symbol LONG / SHORT
```

Première utilisation :

```text
feature supplémentaire
ou
confirmation
```

Seulement après ablation causale.

---

# 91. Freeze de campagne

Une fois la campagne lancée, figer :

```text
labels D1/D10
horizon Oracle
N candidates = 3,5,10
feature transform definitions
model hyperparameters
seeds
WF protocol
purge
metrics
GO/NO_GO rules
feature budget
development period
confirmation period/status
pairwise objective contract
```

Ne pas modifier après observation des premiers résultats.

---

# 92. Ordre d’exécution demandé

Exécuter exactement dans cet ordre :

```text
STEP 0
Attendre la clôture et le verdict de la piste E6-B2 en cours

STEP 1
Auditer le contrat D1/D10, le signe absolu, le PIT, les corporate actions et le biais d'univers

STEP 2
Construire Dataset A

STEP 3
T0 : baseline X(J)

STEP 4
T1 : deltas pour N=3,5,10

STEP 5
T2 : slopes / acceleration / persistence pour N=3,5,10

STEP 6
Comparer N=3 vs N=5 vs N=10 en OOF sur Logistic Regression, CatBoost classification et ranker pairwise

STEP 7
Sélectionner le plus petit N équivalent au meilleur

STEP 8
Figer le budget de features, le N, la représentation et le modèle retenus

STEP 9
Construire Dataset B Oracle OOF

STEP 10
Répéter le test avec le N sélectionné

STEP 11
Construire Dataset C avec D2-D9 réintroduits

STEP 12
Émettre le verdict RELATIVE_TAIL_RANKING et ABSOLUTE_LONG_SHORT

STEP 13
Exécuter la confirmation séparée si une période réellement intacte existe

STEP 14
Seulement si le gate T2 passe, auditer les séries Eroya temporelles réellement PIT et denses

STEP 15
Ajouter les familles Eroya une à une sur les mêmes lignes ; ne pas changer le N principal

STEP 16
Si justifié, tester T3 raw sequence avec TCN/1D-CNN puis LSTM

STEP 17
Verdict final
```

---

# 93. Questions auxquelles le rapport final doit répondre

```text
Q1
Les trajectoires J-N → J sont-elles plus prédictives
que les features observées uniquement à J ?

Q2
Quel N est le plus pertinent parmi 3,5,10 ?

Q3
Le gain de N=10 est-il réellement supérieur à N=5
ou simplement marginal ?

Q4
Quelles familles de features bénéficient le plus
de l’information temporelle ?

Q5
Les patterns sont-ils stables same-date et en OOF ?

Q6
Le signal reste-t-il présent dans le pool Oracle OOF ?

Q7
Le score reste-t-il utile lorsque D2-D9 sont réintroduits ?

Q8
Les données Eroya ajoutent-elles une trajectoire directionnelle
non présente dans les features actuelles ?

Q9
Quelle famille Eroya apporte le plus :
short/borrow, options, flow, insiders,
institutional ou analyst ?

Q10
Un modèle séquentiel apporte-t-il réellement plus
qu’un modèle tabulaire avec deltas/slopes ?

Q11
Le classifier mérite-t-il d’être ajouté
au Per-Symbol LONG ?

Q12
Le classifier mérite-t-il d’être ajouté
au Per-Symbol SHORT ?

Q13
Une famille sans signal directionnel améliore-t-elle néanmoins l'amplitude
de façon incrémentale par rapport à Oracle seul ?

Q14
Si oui, doit-elle être testée dans le profil Oracle comme feature, gate,
priorité de classement ou estimation de risque ?
```

---

# 94. Rapport final attendu

Créer :

```text
TEMPORAL_D1D10_CLASSIFIER_REPORT.md
```

Sections :

```text
1. Executive summary
2. Label contract
3. PIT / leakage audit
4. Dataset A statistics
5. T0 J-only baseline
6. N=3 temporal results
7. N=5 temporal results
8. N=10 temporal results
9. N selection
10. Temporal feature family ablations
11. Logistic Regression
12. LightGBM
13. CatBoost
14. Same-date analysis
15. Annual stability
16. Sector stability
17. Symbol stability
18. Score bucket analysis
19. Dataset B Oracle OOF
20. Dataset C production-like
21. Eroya source/PIT audit
22. Eroya temporal ablations
23. Raw sequence / TCN / LSTM if executed
24. Final architecture recommendation
25. Final verdict
```

---

# 95. Verdict final obligatoire

Choisir exactement un verdict principal :

```text
STRONG_GO
GO_RESEARCH
WEAK_SIGNAL
NO_GO
EXPERIMENT_INVALID
```

Et produire séparément :

```text
TEMPORAL_SIGNAL_VERDICT
SELECTED_N
EROYA_INCREMENTAL_VERDICT
AMPLITUDE_INCREMENTAL_VERDICT
LONG_INTEGRATION_VERDICT
SHORT_INTEGRATION_VERDICT
```

---

# 96. Principe final

Cette campagne ne cherche pas seulement :

```text
"quelle est la valeur d'une feature à J ?"
```

Elle cherche surtout :

```text
"d'où vient cette feature ?"
"comment a-t-elle évolué ?"
"avec quelle vitesse ?"
"avec quelle persistance ?"
"est-elle en accélération ou en décélération ?"
```

L’hypothèse est que la direction future peut être contenue dans :

```text
la trajectoire
```

bien davantage que dans :

```text
la photographie finale.
```

Le test doit donc comparer proprement :

```text
STATE
vs
TRAJECTORY
vs
STATE + TRAJECTORY
vs
RAW SEQUENCE
```

sans tuning post-hoc et avec validation temporelle stricte.
