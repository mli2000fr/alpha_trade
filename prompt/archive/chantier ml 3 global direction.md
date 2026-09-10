Chantier research-only — dip_feature_discovery_and_outcome_model
0. Objectif

On dispose déjà d’un setup LONG spécifique :

DIP N4/X2 =
global_rank_20 >= 0.90 pendant 4 séances consécutives
ET
adj_close[J] / adj_close[J-4] - 1 <= -0.02

Le problème n’est plus de détecter le DIP.

Le problème est :

parmi les événements DIP N4/X2, peut-on identifier à J lesquels vont rebondir et lesquels vont continuer à baisser ?

Le but est de construire un modèle spécialisé :

DipOutcomeClassifier

qui ne travaille que sur les événements DIP.

Aucun changement PROD.
Aucun changement risk.
Aucun changement du DIP N4/X2.
Aucun tuning de N/X.

1. Dataset conditionnel DIP uniquement

Construire un dataset où :

1 ligne = 1 événement (date J, symbol)

et où chaque ligne satisfait strictement :

global_rank_20[J]   >= 0.90
global_rank_20[J-1] >= 0.90
global_rank_20[J-2] >= 0.90
global_rank_20[J-3] >= 0.90

ET

adj_close[J] / adj_close[J-4] - 1 <= -0.02

Utiliser uniquement le batch Global Rank explicitement demandé.

Ne jamais mélanger plusieurs batch_id.

Ajouter des assertions :

unique(date, symbol)
1 seul global_rank_20 par date/symbol
aucun duplicate multi-batch
2. PIT / no-lookahead

Toutes les features d’une ligne (J, symbol) doivent être calculées uniquement avec des données disponibles au plus tard à J.

Interdictions absolues :

future_return
future_decile
oracle realized labels
future bars
future earnings revisions
features recalculées avec information > J

Toute feature issue d’un autre modèle doit être auditée :

OOF/PIT uniquement

Si la provenance d’une feature est ambiguë :

l’exclure du premier run
3. Targets

Construire deux problèmes séparés.

Target A — outcome binaire
y_binary = 1 si future_return_H20 > 0
y_binary = 0 si future_return_H20 <= 0

Objectif :

rebond/gagnant vs continuation/perdant
Target B — outcome extrême

Utiliser le décile réalisé H20 :

GOOD = D8, D9, D10
BAD  = D1, D2, D3

Exclure D4-D7 du training pour ce target.

Objectif :

très bon DIP vs très mauvais DIP

Ne pas mélanger les deux targets dans un même modèle.

4. Universe de features

Partir de toutes les features PIT disponibles, mais NE PAS les donner immédiatement au modèle.

Regrouper les features par familles :

momentum
trend
mean_reversion
relative_strength
sector_relative
market_relative
volatility
ATR/range
volume/liquidity
beta/risk
technical structure
moving-average distances
cross-sectional ranks
fundamentals
earnings/events
sentiment
company-idiosyncratic signals
macro/regime

Produire un inventaire :

feature_name
family
source_table
PIT provenance
coverage
dtype
5. Étape A — hygiene des features

Avant toute analyse prédictive, éliminer mécaniquement :

coverage < 80%
quasi-constant
variance quasi nulle
leakage/future
duplicates exacts
features ID/date/string non prédictives

Détecter aussi les corrélations extrêmes :

abs(corr) > 0.95

mais ne pas encore supprimer agressivement ici ; marquer les groupes redondants.

Produire :

n_features_initial
n_removed_coverage
n_removed_constant
n_removed_leakage
n_remaining
6. Étape B — analyse univariée

Pour chaque feature restante, calculer sur le pool DIP uniquement :

Pour Target A
AUC
directional_AUC = max(AUC, 1-AUC)
Spearman IC avec future_return_H20
mean(feature | winner)
mean(feature | loser)
median(feature | winner)
median(feature | loser)
standardized mean difference
Pour Target B
AUC GOOD vs BAD
directional_AUC
Spearman IC avec future_return_H20
GOOD/BAD lift

Reporter le sens :

high feature -> GOOD
ou
low feature -> GOOD

Ne jamais cacher le signe derrière directional_AUC.

7. Étape C — stabilité temporelle

Les statistiques doivent être calculées :

globalement
par année
par semestre si assez de n
par fold walk-forward

Pour chaque feature produire :

AUC_global
AUC_2022
AUC_2023
AUC_2024
...

IC_global
IC_par_année

sign_stability

Définir :

sign_stability =
fraction des périodes où le sens de la feature est identique

Une feature légèrement prédictive mais stable est préférable à une feature forte mais instable.

Exemple préféré :

AUC = 0.54 / 0.55 / 0.54

plutôt que :

AUC = 0.65 / 0.58 / 0.46
8. Étape D — analyse par quantiles

Pour chaque feature candidate :

découper le pool DIP en quintiles intra-train :

Q1 Q2 Q3 Q4 Q5

Produire pour chaque quintile :

n
mean H20
median H20
P(H20 > 0)
BAD5
GOOD5
D1
D10

Calculer un score de monotonie :

monotonicity_score

Favoriser les features où Q1→Q5 montre une progression cohérente.

Ne pas retenir une feature uniquement parce qu’un seul quintile est spectaculaire.

9. Étape E — contrôle multiple testing / data mining

On teste 150+ features, donc plusieurs faux positifs sont inévitables.

Faire un permutation test.

Préserver la structure temporelle/cross-sectionnelle autant que possible.

Par exemple :

permutation du target par date
ou permutation en blocs temporels compatibles

Répéter au moins :

500 permutations

Pour chaque permutation, calculer :

max directional_AUC parmi toutes les features
max abs(IC)

Construire la distribution du maximum sous H0.

Pour chaque vraie feature, produire :

empirical_pvalue_auc
empirical_pvalue_ic

Objectif :

distinguer :

AUC 0.54 réellement intéressant

de :

AUC 0.54 obtenu facilement par hasard quand on teste 150 variables
10. Étape F — réduction de redondance

Sur le pool DIP uniquement :

calculer la matrice de corrélation des features candidates.

Clusteriser les features avec :

abs(corr) >= 0.80

Pour chaque cluster, garder en priorité :

meilleure stabilité temporelle
meilleure couverture
meilleur comportement monotone
meilleure interprétabilité
meilleur score univarié corrigé du multiple testing

Garder idéalement :

1 à 2 features maximum par cluster

Objectif :

obtenir environ :

10 à 30 features

réellement différentes.

11. Règles de présélection

Ne pas appliquer une règle unique rigide, mais utiliser comme critères indicatifs :

coverage >= 0.80
sign stable dans majorité des folds
directional_AUC >= ~0.53
ou abs(IC) >= ~0.03
relation quantile raisonnablement monotone
empirical p-value acceptable
non redondante

Une feature peut être retenue même avec AUC <0.53 si :

très stable
complémentaire
économiquement cohérente

Inversement, une feature AUC=0.56 instable doit être rejetée.

12. Feature selection NESTED walk-forward

Point critique :

La sélection des features doit être faite uniquement dans le TRAIN de chaque fold.

Interdit :

sélectionner les features sur toute la période
puis prétendre que les prédictions sont OOF

Pour chaque fold :

TRAIN
  -> hygiene
  -> analyse univariée
  -> stabilité interne
  -> redondance
  -> shortlist
  -> fit modèle

VALIDATION
  -> prédiction uniquement

Aucun critère de sélection ne doit regarder le fold de validation.

À la fin produire :

selection_frequency par feature

Exemple :

feature_A : 5/5 folds
feature_B : 4/5
feature_C : 1/5

Les features sélectionnées fréquemment sont considérées plus robustes.

13. Modèles à tester

Garder les modèles simples.

M0 — baseline
tous les DIP

Aucun modèle.

M1 — logistic/simple model

Utiliser la shortlist stable avec :

LogisticRegression

pour avoir une baseline linéaire/interprétable.

M2 — LightGBM

Entraîner LightGBM sur la shortlist.

Ne pas faire de gros sweep hyperparamètres.

Utiliser des hyperparamètres conservateurs :

faible profondeur
régularisation
min_data_in_leaf élevé
learning_rate modéré
early stopping

L’objectif est d’éviter que LightGBM mémorise les événements DIP.

14. Output modèle

Produire :

dip_quality_score = P(good DIP)

exclusivement OOF pour les analyses historiques.

Pour Target A :

P(H20 > 0)

Pour Target B :

P(D8-D10 vs D1-D3)
15. Ne pas utiliser directement un threshold

Premier usage recommandé :

utiliser dip_quality_score comme ranking.

Comparer :

Q0 = tous les DIP
Q1 = DIP triés par dip_quality_score

Puis diagnostics :

top 50%
top 25%

uniquement comme analyse pré-spécifiée.

Ne pas tuner :

40%
45%
55%
60%
etc.
16. Diagnostics OOF

Sur les prédictions OOF, produire :

ROC AUC
PR AUC
Brier score
calibration curve
Spearman IC score vs H20

Puis par quintile de dip_quality_score :

n
mean H20
median H20
P>0
BAD5
GOOD5
D1
D10

L’objectif principal est de voir une vraie pente :

Q1 < Q2 < Q3 < Q4 < Q5

en qualité du DIP.

17. Stabilité du modèle

Produire les métriques :

par fold
par année
par régime

Vérifier :

AUC/IC même signe
top quintile meilleur que bottom quintile
BAD5 baisse dans les meilleurs scores
GOOD5 augmente

Une performance globale élevée mais inversée sur un fold = NO-GO.

18. Importance des features

Utiliser :

permutation importance sur validation OOF

comme importance principale.

SHAP peut être calculé ensuite comme diagnostic secondaire.

Ne pas utiliser :

LightGBM gain importance

seule pour sélectionner les features.

Produire :

feature
selection_frequency
permutation_importance_mean
permutation_importance_std
sign_univariate
family
19. Analyse économique des features

Pour les 10 features les plus robustes, expliquer leur interprétation.

Exemple :

GOOD DIP :
relative strength sectorielle reste forte
ATR ne s’emballe pas
tendance moyen terme intacte
volume vendeur non extrême

vs :

BAD DIP :
rank encore élevé mais volatilité explose
secteur se détériore
support/tendance casse
pression vendeuse augmente

Le but est de vérifier que le pattern appris a un sens économique plausible.

20. Backtest portfolio PROD-parity

Uniquement après validation OOF.

Comparer :

P0 = stratégie actuelle / baseline
P1 = DIP N4/X2 tous
P2 = DIP N4/X2 priorisés par dip_quality_score
P3 = top 50% dip_quality
P4 = top 25% dip_quality

Même :

batch
risk
sector cap
sizing
lifecycle
execution
costs
max_positions
regime

Aucun autre changement.

21. Métriques portefeuille

Produire :

total return
CAGR
Sharpe
Sortino
MaxDD
PF
win rate
avg trade
median trade
n trades
turnover
exposure
capital utilization
worst day
worst 5-day

Ajouter :

PnL marginal vs DIP all
trades rejetés
qualité des trades rejetés
22. Critères GO

Le modèle ne doit PAS être déclaré GO juste parce que :

AUC > 0.53

GO seulement si plusieurs éléments convergent :

score OOF stable
IC stable
gradient Q1→Q5
GOOD5 augmente
BAD5 diminue
D10 augmente ou se maintient
D1 diminue
PF portfolio augmente
Sharpe augmente
PnL/trade augmente
fréquence reste suffisante

Et surtout :

résultat stable sur majorité des folds/années
23. Critères NO-GO

Stopper le chantier si :

aucune feature ne dépasse le bruit après permutation
signes instables
LightGBM bat logistic uniquement in-sample
pas de gradient monotone du quality score
amélioration portfolio uniquement sur une année
top score supprime trop de trades

Ne pas continuer à ajouter des features ou tuner des seuils dans ce cas.

24. Livrables

Produire :

dip_dataset_summary.csv
dip_feature_inventory.csv
dip_feature_univariate.csv
dip_feature_stability.csv
dip_feature_quantiles.csv
dip_feature_clusters.csv
dip_feature_permutation_null.csv
dip_feature_selected_by_fold.csv
dip_oof_predictions.csv
dip_model_metrics.csv
dip_quality_quintiles.csv
dip_portfolio_comparison.csv

Et un rapport final :

artifacts/dip_outcome_learning_report.md

avec :

taille/coverage du dataset
features réellement utiles
features rejetées comme bruit
stabilité par fold
résultat Logistic vs LightGBM
gradient du dip_quality_score
résultats portfolio
verdict GO / NO-GO
25. Règle fondamentale

Ne pas essayer de faire apprendre au modèle :

"la direction générale des actions"

Le modèle doit apprendre uniquement :

P(gagnant | DIP N4/X2 déjà détecté)

C’est un meta-model conditionnel de qualité du DIP, pas un nouveau Global Rank.

J’ajouterais même une consigne finale à ton IA : si la feature discovery montre que les 150+ features n’apportent pratiquement rien après contrôle de stabilité/permutation, arrêter là. Ce serait un résultat utile en soi, et il vaut mieux garder le DIP simple que fabriquer artificiellement un modèle plus complexe.