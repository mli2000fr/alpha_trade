# Roadmap des méthodes quant professionnelles applicables à α-Trade

## 0. Objectif de ce document

Ce document rassemble, dans une seule roadmap, les principales méthodes quantitatives professionnelles pertinentes pour l’architecture actuelle de **α-Trade**.

L’objectif est d’éviter de devoir “réinventer” une idée à chaque étape.

Le principe de travail devient :

```text
1. identifier les méthodes professionnelles déjà connues
2. sélectionner celles adaptées à l’architecture actuelle
3. les tester dans un ordre rationnel
4. éviter les méthodes prématurées ou inutilement complexes
5. garder un protocole PIT / OOF / walk-forward strict
```

Architecture actuelle de référence :

```text
                    Oracle Extreme
                          │
                "extrême probable"
                          │
                          ▼
              Temporal D1/D10 Classifier
                          │
              ┌───────────┴───────────┐
              │                       │
      p_d10_given_tail         p_d1_given_tail
              │                       │
              ▼                       ▼
       Per-Symbol LONG         Per-Symbol SHORT
              │                       │
              ▼                       ▼
         LONG candidate          SHORT candidate
              │                       │
              └───────────┬───────────┘
                          ▼
                     Risk / Execution
```

Sémantique :

```text
Oracle Extreme
= détecte l’amplitude / la probabilité de tail

Temporal D1/D10
= estime la polarité probable de l’extrême

Per-Symbol LONG
= spécialiste haussier du ticker

Per-Symbol SHORT
= spécialiste baissier du ticker

Risk / Execution
= décide si et comment trader
```

---

# 1. Classification générale des méthodes

Les méthodes sont classées en quatre catégories :

```text
STANDARD_PRO
ADAPTÉ_À_ALPHA_TRADE
EXPÉRIMENTAL
À_ÉVITER_POUR_L_INSTANT
```

## 1.1 STANDARD_PRO

Méthodes courantes en recherche quant :

```text
walk-forward
PIT data
purge / embargo
cross-sectional ranking
meta-labeling
temporal feature engineering
factor neutralization
regime conditioning
feature ablation
ensemble models
calibration
risk overlays
portfolio constraints
```

## 1.2 ADAPTÉ_À_ALPHA_TRADE

Méthodes particulièrement pertinentes ici :

```text
tail classification D1 vs D10
temporal trajectories J-N → J
meta-labeling après Oracle
cross-feature divergence
relative trajectory
multi-horizon agreement
mixture of experts
specialized LONG/SHORT models
```

## 1.3 EXPÉRIMENTAL

À tester seulement après baseline solide :

```text
TCN
1D-CNN
LSTM
contrastive learning
trajectory clustering
representation learning
mixture of experts dynamique
change-point detection avancé
```

## 1.4 À_ÉVITER_POUR_L_INSTANT

```text
Transformer temporel lourd
reinforcement learning
full end-to-end portfolio neural network
huge feature mining
Optuna massif
threshold search post-hoc
dynamic symbol-specific optimization
```

---

# 2. Méthode n°1 — Tail Classification

## Statut

```text
STANDARD_PRO
TRÈS_ADAPTÉ
PRIORITÉ MAXIMALE
```

## Idée

Au lieu de prédire :

```text
hausse ou baisse sur toutes les observations
```

on conditionne sur les tails :

```text
D1 vs D10
```

Target :

```text
D1  = 0
D10 = 1
```

Les observations :

```text
D2-D9
```

sont exclues de la première expérience.

Question :

```text
"parmi les vrais extrêmes,
les futurs D1 et D10 sont-ils séparables ?"
```

## Pourquoi c’est adapté

Oracle sait déjà détecter :

```text
les mouvements extrêmes
```

Il est donc logique de spécialiser un modèle pour :

```text
la polarité de l’extrême
```

## Verdict

```text
À TESTER MAINTENANT
```

---

# 3. Méthode n°2 — Temporal Feature Engineering

## Statut

```text
STANDARD_PRO
TRÈS_ADAPTÉ
PRIORITÉ MAXIMALE
```

## Idée

Ne pas utiliser uniquement :

```text
X(J)
```

mais :

```text
X(J-N) ... X(J)
```

Exemples :

```text
delta
slope
acceleration
persistence
positive days
negative days
rolling mean
rolling std
range
time since update
```

## Fenêtres recommandées

Pré-enregistrer :

```text
N=3
N=5
N=10
```

Puis éventuellement :

```text
N=20
```

uniquement si :

```text
N=10 > N=5 > N=3
```

de façon stable.

## Règle professionnelle

Choisir :

```text
le plus petit N presque aussi bon que le meilleur
```

Pas forcément :

```text
le N avec AUC maximale de 0.001
```

## Verdict

```text
À TESTER MAINTENANT
```

---

# 4. Méthode n°3 — Meta-Labeling

## Statut

```text
STANDARD_PRO
TRÈS_ADAPTÉ
PRIORITÉ MAXIMALE
```

## Idée

Un modèle ne fait pas tout.

Architecture :

```text
Primary model
→ Oracle Extreme

Secondary model
→ D1/D10 polarity

Tertiary model
→ Per-Symbol LONG / SHORT confirmation
```

C’est proche du principe :

```text
candidate generation
→ meta model
→ specialist model
→ execution
```

## Application à α-Trade

```text
Oracle
→ "quelque chose d’important peut arriver"

Temporal D1/D10
→ "plutôt positif ou négatif"

Per-Symbol
→ "ce ticker mérite-t-il vraiment un trade ?"
```

## Verdict

```text
À GARDER COMME ARCHITECTURE CIBLE
```

---

# 5. Méthode n°4 — Cross-Sectional Ranking

## Statut

```text
STANDARD_PRO
ADAPTÉ
```

## Idée

Au lieu de prédire parfaitement une classe, classer les candidats.

Exemple :

```text
p_d10_given_tail
```

permet de ranker les Oracle candidates.

Utilisation :

```text
top score
→ candidats LONG prioritaires

bottom score
→ candidats SHORT prioritaires
```

## Métrique importante

```text
same-date AUC
```

Question :

```text
"le même jour,
les futurs D10 sont-ils mieux classés que les futurs D1 ?"
```

## Verdict

```text
À TESTER MAINTENANT
```

---

# 6. Méthode n°5 — Cross-Feature Divergence

## Statut

```text
STANDARD/PRO-INSPIRED
TRÈS ADAPTÉ
```

## Idée

Le signal peut ne pas être dans une seule feature mais dans la contradiction entre plusieurs.

Exemples :

```text
prix ↑
mais
money flow ↓
```

```text
relative strength élevé
mais
momentum ralentit fortement
```

```text
short interest ↑
et
borrow fee ↑
et
shares available ↓
```

```text
prix stable
mais
analyst revisions ↓
```

## Features candidates

```text
price_return - flow_change
relative_strength_change - momentum_change
price_change - analyst_revision_change
price_change - options_skew_change
short_interest_change + borrow_fee_change
```

Ou laisser LightGBM/CatBoost apprendre les interactions.

## Règle

Ne pas générer 500 divergences artificielles.

Créer uniquement des divergences économiquement motivées.

## Verdict

```text
À TESTER APRÈS LES DELTAS/SLOPES DE BASE
```

---

# 7. Méthode n°6 — Relative Trajectory

## Statut

```text
STANDARD_PRO
TRÈS ADAPTÉ
```

## Idée

Comparer la trajectoire du symbole à celle de :

```text
SPY
secteur
industrie
univers cross-sectionnel
```

Exemple :

```text
stock momentum slope
-
sector momentum slope
```

```text
stock flow
-
sector flow
```

```text
stock return_5d
-
sector return_5d
```

## Pourquoi

Un titre peut être :

```text
+3%
```

mais si son secteur fait :

```text
+8%
```

il est en réalité relativement faible.

## Verdict

```text
À TESTER TÔT
```

---

# 8. Méthode n°7 — Multi-Horizon Agreement

## Statut

```text
STANDARD_PRO
ADAPTÉ
```

## Idée

Vérifier si plusieurs horizons donnent la même direction.

Exemple :

```text
delta_3 > 0
delta_5 > 0
delta_10 > 0
```

peut être différent de :

```text
delta_3 > 0
delta_5 > 0
delta_10 < 0
```

Features possibles :

```text
trend_agreement_count
trend_sign_consistency
short_vs_medium_divergence
```

## Verdict

```text
À TESTER APRÈS LE CHOIX DE N
```

---

# 9. Méthode n°8 — Persistence

## Statut

```text
STANDARD_PRO
TRÈS ADAPTÉ
```

## Idée

La même variation totale peut avoir une structure différente.

Exemple :

```text
+10% en une séance
```

vs :

```text
+10% sur 8 séances positives
```

Features :

```text
positive_days_N
negative_days_N
consecutive_positive_days
consecutive_negative_days
sign_consistency
```

## Verdict

```text
À TESTER TÔT
```

---

# 10. Méthode n°9 — Velocity / Acceleration

## Statut

```text
STANDARD_PRO
TRÈS ADAPTÉ
```

## Idée

Ne pas seulement mesurer :

```text
où est la feature
```

mais :

```text
à quelle vitesse elle bouge
et si cette vitesse augmente ou diminue
```

Exemples :

```text
momentum_slope
momentum_acceleration

flow_slope
flow_acceleration

options_skew_slope
options_skew_acceleration
```

## Verdict

```text
À TESTER TÔT
```

---

# 11. Méthode n°10 — Change-Point Detection

## Statut

```text
PRO
EXPÉRIMENTAL ADAPTÉ
```

## Idée

Détecter un changement brutal de comportement.

Exemples :

```text
volume regime change
volatility jump
flow sign reversal
momentum break
borrow fee shock
```

Méthodes possibles :

```text
CUSUM
rolling z-score break
Bayesian change point
PELT
```

## Utilité

Un futur D1/D10 peut être précédé non pas par une tendance lisse mais par :

```text
un changement structurel soudain
```

## Verdict

```text
PLUS TARD
```

---

# 12. Méthode n°11 — Event-Conditioned Models

## Statut

```text
STANDARD_PRO
ADAPTÉ
```

## Idée

Certains patterns n’ont de sens que près d’un événement.

Exemples :

```text
earnings
guidance
analyst revision
target revision
Form 4
13F
short-interest publication
options event
```

On peut ajouter :

```text
days_to_event
days_since_event
event_type
event_direction
```

## Verdict

```text
À TESTER QUAND LES DONNÉES ÉVÉNEMENTIELLES SONT DISPONIBLES
```

---

# 13. Méthode n°12 — Regime-Conditioned Models

## Statut

```text
STANDARD_PRO
ADAPTÉ
```

## Idée

Un même pattern peut changer de sens selon le régime.

Exemples :

```text
bull
bear
stress
rebound
high volatility
low volatility
```

Approche prudente :

```text
ajouter régime comme feature
```

avant de créer :

```text
un modèle séparé par régime
```

## Danger

Trop peu d’observations par régime.

## Verdict

```text
À TESTER APRÈS BASELINE GLOBAL STABLE
```

---

# 14. Méthode n°13 — Mixture of Experts

## Statut

```text
PRO
EXPÉRIMENTAL
```

## Idée

Plusieurs modèles spécialisés :

```text
expert momentum
expert flow
expert options
expert short squeeze
expert analyst revision
```

Un gating model choisit quel expert écouter.

## Quand

Seulement si l’analyse montre plusieurs familles de patterns réellement distinctes.

## Verdict

```text
PLUS TARD
```

---

# 15. Méthode n°14 — Trajectory Clustering

## Statut

```text
EXPÉRIMENTAL
UTILE EN DIAGNOSTIC
```

## Idée

Clusteriser les trajectoires des D1 et D10.

Objectif :

```text
existe-t-il plusieurs types de D10 ?
existe-t-il plusieurs types de D1 ?
```

Exemples potentiels :

```text
D10 momentum breakout
D10 short squeeze
D10 analyst revision
D10 flow accumulation

D1 momentum collapse
D1 negative revision
D1 distribution
D1 liquidity stress
```

## Verdict

```text
PLUS TARD
```

---

# 16. Méthode n°15 — Contrastive Learning

## Statut

```text
EXPÉRIMENTAL
```

## Idée

Apprendre une représentation où :

```text
D10 similaires
→ proches

D1 similaires
→ proches

D1 vs D10
→ éloignés
```

Possible avec :

```text
Siamese network
triplet loss
contrastive loss
```

## Verdict

```text
TRÈS PLUS TARD
```

---

# 17. Méthode n°16 — 1D-CNN / TCN

## Statut

```text
PRO
EXPÉRIMENTAL ADAPTÉ
```

## Idée

Donner directement :

```text
[J-N ... J]
```

au modèle.

Avantage :

```text
détecter des formes temporelles locales
```

TCN/1D-CNN est souvent plus simple qu’un LSTM.

## Ordre conseillé

```text
tabulaire temporal
→ flattened sequence
→ 1D-CNN / TCN
```

## Verdict

```text
APRÈS QUE LES FEATURES TEMPORELLES TABULAIRES PASSENT
```

---

# 18. Méthode n°17 — LSTM

## Statut

```text
STANDARD ML TIME SERIES
MAIS PAS PREMIER CHOIX
```

## Idée

Apprendre une séquence :

```text
X(J-N) ... X(J)
```

avec mémoire interne.

## Risques

```text
overfitting
instabilité
plus difficile à auditer
dataset limité par symbole
```

## Verdict

```text
CHALLENGER, PAS BASELINE
```

---

# 19. Méthode n°18 — Transformer temporel

## Statut

```text
PRO/RESEARCH
PRÉMATURÉ ICI
```

## Pourquoi pas maintenant

Pour :

```text
N=3,5,10
```

les séquences sont très courtes.

Un Transformer ajoute :

```text
beaucoup de paramètres
complexité
risque d’overfit
```

sans garantie de gain.

## Verdict

```text
À ÉVITER POUR L’INSTANT
```

---

# 20. Méthode n°19 — Calibration

## Statut

```text
STANDARD_PRO
```

Mesures :

```text
Brier score
log loss
reliability curve
```

Ne pas calibrer avant de vérifier que le ranking fonctionne.

## Verdict

```text
APRÈS SIGNAL STABLE
```

---

# 21. Méthode n°20 — Feature Ablation

## Statut

```text
STANDARD_PRO
OBLIGATOIRE
```

Tester les familles séparément :

```text
price/momentum
volume/liquidity
relative strength
options
short/borrow
flow
analyst
insider
institutional
macro
```

Comparer sur :

```text
exactement les mêmes lignes
```

## Verdict

```text
À FAIRE SYSTÉMATIQUEMENT
```

---

# 22. Méthode n°21 — Direction vs Amplitude Audit

## Statut

```text
TRÈS IMPORTANT POUR α-TRADE
```

Mesurer séparément :

```text
tail vs middle
D1 vs D10
```

Verdicts :

```text
DIRECTIONAL
AMPLITUDE_ONLY
BOTH
NO_SIGNAL
```

## Verdict

```text
OBLIGATOIRE
```

---

# 23. Méthode n°22 — Same-Date Evaluation

## Statut

```text
STANDARD CROSS-SECTIONAL
CRITIQUE POUR α-TRADE
```

Calculer :

```text
AUC par date
```

puis agréger :

```text
mean daily AUC
median daily AUC
% dates > .50
% dates > .55
```

Objectif :

```text
distinguer D1 de D10 le même jour
```

et non apprendre un simple effet de régime temporel.

## Verdict

```text
MÉTRIQUE PRINCIPALE
```

---

# 24. Méthode n°23 — Pairwise Ranking

Pour chaque date :

```text
P(score_D10 > score_D1)
```

## Verdict

```text
À UTILISER EN COMPLÉMENT DE SAME-DATE AUC
```

---

# 25. Méthode n°24 — Purged Walk-Forward

## Statut

```text
STANDARD_PRO
OBLIGATOIRE
```

Exemple :

```text
train 2020-2021 → test 2022
train 2020-2022 → test 2023
train 2020-2023 → test 2024
train 2020-2024 → test 2025
```

Avec H20 :

```text
aucun target train ne doit chevaucher le test
```

---

# 26. Méthode n°25 — Embargo / Leakage Controls

Audit :

```text
feature PIT
target availability
preprocessing train-only
OOF Oracle
no future fill
```

## Verdict

```text
OBLIGATOIRE
```

---

# 27. Méthode n°26 — Missingness as Information

Features possibles :

```text
is_missing
days_since_update
days_since_last_event
```

Particulièrement utile pour :

```text
analyst revisions
short interest
insiders
institutional
```

---

# 28. Méthode n°27 — Event Recency

Exemples :

```text
days_since_last_upgrade
days_since_last_downgrade
days_since_insider_buy
days_since_target_revision
```

---

# 29. Méthode n°28 — Ensemble Models

Combiner seulement des modèles complémentaires :

```text
LR
LightGBM
CatBoost
```

Ne pas faire d’ensemble si leurs prédictions sont quasi identiques.

---

# 30. Méthode n°29 — Feature Neutralization

Retirer éventuellement :

```text
market
sector
beta
size
```

pour isoler un signal plus pur.

À tester comme ablation, pas automatiquement.

---

# 31. Méthode n°30 — Risk Overlay

Séparer :

```text
alpha
risk
execution
```

Le modèle directionnel ne doit pas remplacer le moteur de risque.

---

# 32. Méthode n°31 — Portfolio Constraints

Exemples :

```text
sector cap
gross exposure
net exposure
max positions
liquidity cap
symbol concentration
```

Valider d’abord le signal, puis l’effet portefeuille.

---

# 33. Méthode n°32 — Transaction Cost Awareness

Après GO scientifique :

```text
net alpha
turnover
spread cost
slippage
margin cost
```

---

# 34. Méthode n°33 — Probability Thresholding

Ne pas tester en boucle :

```text
0.51, 0.52, 0.53...
```

D’abord analyser :

```text
deciles
top10
top20
bottom10
bottom20
```

Thresholds seulement dans une campagne ultérieure.

---

# 35. Méthode n°34 — Symbol-Specific Thresholds

Avec peu de tails par symbole :

```text
risque élevé d’overfit
```

## Verdict

```text
À ÉVITER POUR L’INSTANT
```

---

# 36. Méthode n°35 — Per-Symbol Fine-Tuning

Architecture possible :

```text
global/shared temporal model
        ↓
per-symbol specialist
```

À tester seulement après validation du modèle partagé.

---

# 37. Méthode n°36 — Hierarchical Models

Hiérarchie potentielle :

```text
market
→ sector
→ symbol
```

Intéressant plus tard.

---

# 38. Méthode n°37 — Survival / Time-to-Event

Question :

```text
combien de temps avant le mouvement extrême ?
```

Non prioritaire tant que l’architecture travaille principalement en H20.

---

# 39. Méthode n°38 — Régression directe des rendements

Cible :

```text
future return
```

plus bruitée que :

```text
D1 vs D10
```

## Verdict

```text
NE PAS REVENIR EN PRIORITÉ
```

---

# 40. Méthode n°39 — Ordinal Classification

Target possible :

```text
D1 ... D10
```

ou groupes ordonnés.

À envisager seulement après validation D1/D10.

---

# 41. Méthode n°40 — Multitask Learning

Prédire simultanément :

```text
extreme probability
direction
return magnitude
```

Mélange les rôles actuellement bien séparés.

## Verdict

```text
À ÉVITER POUR L’INSTANT
```

---

# 42. Méthode n°41 — Reinforcement Learning

RL ne résout pas un manque d’information directionnelle.

## Verdict

```text
À ÉVITER
```

---

# 43. Méthode n°42 — Genetic Programming / Symbolic Search

Risque massif de data mining.

## Verdict

```text
À ÉVITER POUR L’INSTANT
```

---

# 44. Méthode n°43 — SHAP Pattern Discovery

Utiliser après OOF pour comprendre :

```text
quelles trajectoires poussent vers D10
quelles trajectoires poussent vers D1
```

Mais :

```text
SHAP ≠ preuve d’alpha
```

---

# 45. Méthode n°44 — Counterfactual Analysis

Exemple :

```text
si flow avait été neutre au lieu de négatif,
le score aurait-il changé ?
```

Intéressant pour compréhension, plus tard.

---

# 46. Méthode n°45 — Placebo Tests

Faire :

```text
shuffle labels
```

Résultat attendu :

```text
AUC ≈ 0.50
```

Si non :

```text
suspect leakage
```

## Verdict

```text
À FAIRE
```

---

# 47. Méthode n°46 — Bootstrap par Date

Pour comparer :

```text
N=5
vs
N=10
```

ne pas conclure sur une différence minuscule sans incertitude.

Bootstrap :

```text
par date
```

plutôt que par ligne.

---

# 48. Méthode n°47 — Stability Selection

Une feature/famille utile doit être stable dans plusieurs folds.

Mesurer :

```text
importance rank
AUC contribution
sign stability
```

par fold.

---

# 49. Méthode n°48 — Data Source Incrementality

Pour chaque nouvelle source :

```text
BASE
vs
BASE + SOURCE
```

sur :

```text
mêmes lignes
```

Question :

```text
apporte-t-elle réellement de l’information nouvelle ?
```

---

# 50. Méthode n°49 — Alternative Data Families prioritaires

## Priorité 1

```text
capital flow
order flow
options skew
options flow
analyst revisions
target revisions
guidance
```

## Priorité 2

```text
short interest changes
borrow fee
utilization
insider activity
```

## Priorité 3

```text
institutional ownership
13F
fund flow
```

## Plus amplitude que direction

```text
IV brute
ATR
VIX
volume absolu
```

---

# 51. Roadmap opérationnelle recommandée

## PHASE 1 — maintenant

```text
1. D1 vs D10 classification
2. baseline X(J)
3. temporal N=3
4. temporal N=5
5. temporal N=10
6. delta / slope / acceleration / persistence
7. same-date AUC
8. pairwise ranking
9. LightGBM / CatBoost
10. Dataset B Oracle OOF
11. Dataset C avec D2-D9
```

Verdict :

```text
GO / NO_GO temporal direction
```

---

# 52. PHASE 2 — enrichissement des features actuelles

Ajouter :

```text
cross-feature divergence
relative trajectory
multi-horizon agreement
event recency
missingness age
```

sans changer :

```text
labels
WF
N
hyperparameters
```

---

# 53. PHASE 3 — nouvelles données

Tester une famille à la fois :

```text
Eroya Short/Borrow
Eroya Options
Eroya Flow
Eroya Analyst
Eroya Insiders
Eroya Institutional
```

Toujours :

```text
BASE
vs
BASE + family
```

sur mêmes lignes.

---

# 54. PHASE 4 — séquence brute

Seulement si temporal tabulaire :

```text
GO
```

Tester :

```text
flattened raw sequence
1D-CNN
TCN
LSTM
```

Pas de Transformer au départ.

---

# 55. PHASE 5 — spécialistes

Si plusieurs patterns distincts sont identifiés :

```text
momentum pattern
flow pattern
short squeeze pattern
analyst revision pattern
```

alors tester :

```text
Mixture of Experts
```

---

# 56. PHASE 6 — intégration LONG

Si classifier stable :

```text
LONG baseline
vs
LONG + p_d10_given_tail
```

Tout le reste figé.

Mesurer :

```text
D10 enrichment
D8-D10
D1-D3 contamination
AUC
PR-AUC
% symbols improved
```

---

# 57. PHASE 7 — intégration SHORT

Séparément :

```text
SHORT baseline
vs
SHORT + p_d1_given_tail
```

Mesurer :

```text
D1 enrichment
D1-D3
D8-D10 contamination
AUC
PR-AUC
% symbols improved
```

---

# 58. PHASE 8 — portfolio

Seulement après validation des modèles :

```text
portfolio backtest
costs
turnover
gross exposure
net exposure
drawdown
capacity
```

Ne pas faire l’inverse.

---

# 59. Priorités globales

## PRIORITÉ 5/5

```text
D1 vs D10
temporal features
same-date AUC
meta-labeling
relative trajectory
feature ablations
PIT
purged WF
```

## PRIORITÉ 4/5

```text
cross-feature divergence
multi-horizon agreement
event conditioning
regime interaction
Eroya flow/options/analyst
```

## PRIORITÉ 3/5

```text
TCN
1D-CNN
LSTM
mixture of experts
trajectory clustering
```

## PRIORITÉ 1-2/5

```text
Transformer
contrastive learning
hierarchical neural models
RL
genetic programming
```

---

# 60. Méthodes à ne pas oublier automatiquement à l’avenir

Pour chaque nouveau problème quant, vérifier systématiquement :

```text
1. cross-sectional ou time-series ?
2. classification, ranking ou regression ?
3. état J ou trajectoire J-N ?
4. signal absolu ou relatif au secteur ?
5. interaction de features ?
6. conditionnement par événement ?
7. conditionnement par régime ?
8. modèle unique ou meta-model ?
9. shared model ou specialist ?
10. tabulaire ou sequence ?
11. signal directionnel ou amplitude ?
12. OOF/PIT propre ?
13. coût de transaction ?
14. stabilité multi-fold ?
15. placebo / leakage test ?
```

---

# 61. Architecture cible de recherche

```text
                          DATA PIT
                             │
                    ┌────────┴────────┐
                    │                 │
               Market data       Alternative data
                    │                 │
                    └────────┬────────┘
                             ▼
                     Temporal Features
                             │
                  J-N → ... → J
                             │
                             ▼
                     Oracle Extreme
                             │
                  extreme probability
                             │
                             ▼
                 Temporal D1/D10 Model
                             │
                  polarity / ranking
                             │
             ┌───────────────┴───────────────┐
             │                               │
             ▼                               ▼
      Per-Symbol LONG                 Per-Symbol SHORT
             │                               │
             └───────────────┬───────────────┘
                             ▼
                       Risk Overlay
                             │
                             ▼
                         Execution
```

---

# 62. Philosophie générale

Le système ne doit pas chercher à faire :

```text
un seul modèle magique
```

mais à séparer les problèmes :

```text
AMPLITUDE
DIRECTION
SYMBOL-SPECIFIC CONFIRMATION
RISK
EXECUTION
```

Chaque composant doit être jugé séparément.

---

# 63. Règle d’arrêt

Si une famille ou méthode échoue :

```text
documenter
NO_GO
freeze
passer à la suivante
```

Ne pas immédiatement :

```text
changer les fenêtres
changer les labels
tuner les seuils
ajouter 100 features
```

Le but est d’éviter :

```text
research overfitting
```

---

# 64. Règle de simplicité

Toujours préférer :

```text
le modèle le plus simple
qui capte presque tout le signal
```

Exemple :

```text
LightGBM same-date AUC = 0.580
TCN same-date AUC      = 0.582
```

Préférer probablement :

```text
LightGBM
```

si le gain TCN n’est pas robuste.

---

# 65. Règle de preuve

Un gain n’est crédible que s’il est :

```text
OOF
PIT
stable
same-date
multi-fold
non expliqué par coverage change
non expliqué par régime unique
```

---

# 66. Résultat attendu à moyen terme

Architecture potentiellement robuste :

```text
Oracle Extreme
    ↓
Temporal D1/D10
    ↓
LONG / SHORT specialist
    ↓
Risk
    ↓
Execution
```

avec nouvelles données directionnelles :

```text
flow
options
analyst
short/borrow
insider
institutional
```

et trajectoires :

```text
J-3
J-5
J-10
```

plutôt que simple photographie :

```text
J
```

---

# 67. Résumé exécutif — quoi tester maintenant

Ordre recommandé :

```text
1. Tail D1 vs D10
2. X(J) baseline
3. N=3
4. N=5
5. N=10
6. delta
7. slope
8. acceleration
9. persistence
10. relative trajectory
11. cross-feature divergence
12. LightGBM / CatBoost
13. Oracle OOF population
14. Dataset C D2-D9
15. Eroya flow
16. Eroya options
17. Eroya analyst
18. Eroya short/borrow
19. TCN / LSTM seulement si justifié
20. Per-Symbol LONG/SHORT integration
```

Le principe directeur est :

> **Ne plus attendre qu’une nouvelle idée soit découverte au hasard : partir systématiquement des méthodes quant professionnelles adaptées au problème, puis les tester dans un ordre contrôlé.**
