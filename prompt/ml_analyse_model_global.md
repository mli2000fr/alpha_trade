# Analyse Global Ranking - amelioration pour swing trading

**Date :** 2026-08-06  
**Objet :** ameliorer le Global Ranking pour une strategie de swing trading, sans confondre un IC de modele avec une performance de portefeuille.  
**Statut :** signal historique positif, mais performance actuelle insuffisamment stable/reproductible pour une promotion sans nouvelle validation.

---

## 1. Diagnostic actuel

Le Global Ranking est le meilleur candidat comme signal de selection cross-sectionnelle : il classe les titres d'un univers a une date selon un rendement futur attendu. Il est plus adapte que onze modeles per-sector isoles pour exploiter un grand panel et construire un portefeuille diversifie.

Deux niveaux historiques doivent etre expliques avant toute optimisation :

| Batch | IC global moyen | Splits effectifs | Symboles | Lecture |
|---|---:|---:|---:|---|
| `7e4cf8` | environ 0.0190 | 8 | 928 | Reference historique prometteuse. |
| `f82ab5` | environ 0.0115 | 6 | 939 | Signal positif mais faible; baisse importante a expliquer. |

Un IC proche de $0.011$ n'est pas nul. Il peut etre exploitable en portefeuille diversifie si le spread top-bottom est stable, si le turnover est faible et si les couts restent inferieurs au rendement attendu. Il est toutefois insuffisant pour declarer une strategie production sans preuve economique hors echantillon.

L'ecart entre les batchs ne doit pas etre attribue spontanement a une feature ou un hyperparametre : le nombre de folds, l'univers, le filtre de liquidite, les dates, les versions de code, les disponibilites fondamentales/macro et les corrections de pipeline peuvent tous modifier le resultat.

---

## 2. Objectif swing trading

Pour un swing trade, le modele ne doit pas predire exactement chaque rendement. Il doit classer de maniere stable les titres les plus prometteurs et les moins prometteurs a un horizon suffisamment long pour absorber les couts et limiter le turnover.

Les horizons H10, H15 et H20 sont les candidats principaux. H5 peut servir de signal auxiliaire de timing ou de sortie, mais ne doit pas automatiquement devenir l'horizon principal sur son IC ponctuel.

Le critere de choix est economique :

$$
score_{portfolio} = spread_{net} - \lambda_{turn} \cdot turnover - \gamma_{dd} \cdot drawdown
$$

avec :

$$
spread_{net} = R_{top} - R_{bottom} - couts - slippage - impact
$$

Un IC plus haut mais tres instable, couteux ou concentre dans un secteur est moins interessant qu'un IC plus faible mais stable et peu tournant.

---

## 3. Premiere priorite : baseline reproductible

Avant de chercher un nouveau signal, reconstruire une base comparable.

### 3.1 Manifest obligatoire par run

Persister dans les artefacts/metadata :

* code SHA, versions Python, CatBoost et LightGBM;
* configuration resolue complete;
* seeds et parametres de reproductibilite;
* dates reelles, tailles et raisons de rejet de chaque fold;
* nombre de splits demandes et nombre de splits effectivement produits;
* hash/liste de l'univers et des symboles eligibles par fold;
* filtres de liquidite/volume appliques dans le train et test;
* feature fingerprint, taux de valeurs manquantes/defaults et schema final passe a `fit`;
* statistiques de target par horizon/fold;
* couts, slippage, regles de portefeuille et mapping secteur.

### 3.2 Trois replays necessaires

| ID | Configuration | Question |
|---|---|---|
| G0 | Reproduction exacte de `7e4cf8` sur code actuel si le manifeste le permet | Le niveau proche de 0.019 est-il toujours reproductible ? |
| G1 | Reproduction exacte de `f82ab5` | Le niveau proche de 0.0115 est-il stable ? |
| G2 | Meme univers et folds, mais une seule difference documentee | Quelle hypothese explique l'ecart ? |

Ne jamais comparer deux IC issus de dates, univers ou folds differents comme si une feature etait la seule variable.

---

## 4. Cibles et transformations a revalider

Les resultats historiques suggerent que les transformations suivantes meritent une reproduction, pas une adoption automatique :

| Hypothese | Test controle | Condition de maintien |
|---|---|---|
| Fenetre train 756 jours | 504 versus 756 jours | Gain IC/spread stable sur la majorite des folds. |
| Splits espaces | 8 x 252 versus protocole actuel | Pas de chevauchement excessif ni de folds artificiellement courts. |
| Smoothing H10/H15/H20 | on/off avec les memes splits | Gain confirme par horizon et sur holdout. |
| Vol scaling | on/off | Conserver seulement si rendement net et stabilite progressent. |
| Target sector-neutral | on/off | Distinguer stock-picking de sector-riding. |
| Target factor-neutral | on/off | Conserver si l'alpha reste apres facteurs. |

La winsorisation et la standardisation doivent rester fit uniquement sur le train de chaque fold. Les calculs cross-sectionnels ou sectoriels par date sont admissibles seulement avec un univers point-in-time et des donnees connues a la date de decision.

---

## 5. Features : chercher l'incremental, pas le volume

Le Global Ranking utilise deja un schema riche. Le bon test est une ablation par famille, pas l'ajout simultane de toutes les sources.

| ID | Variante | Hypothese |
|---|---|---|
| F0 | Base/expert actuel sans additions recentes | Reference. |
| F1 | F0 + cross-sectionnelles/sectorielles PIT | Le contexte relatif entre titres ajoute-t-il du ranking ? |
| F2 | F0 + fondamentales PIT | Les variables lentes stabilisent-elles H15/H20 ? |
| F3 | F0 + facteurs/neutralisations | Le signal est-il different des expositions connues ? |
| F4 | F0 + regime et interactions locales | Le regime change-t-il l'efficacite du momentum/volatilite ? |
| F5 | Meilleure famille + une seule seconde preregistree | Complementarite hors echantillon. |

VIX, VXN, VIX9D, VIX3M et MOVE sont communs a tous les titres le meme jour. Ils ne peuvent pas classer seuls le panel a cette date. Leur usage rationnel est une interaction telle que :

$$
momentum_{i,t} \times regime_t
$$

ou une adaptation du portefeuille/execution, pas une simple colonne macro ajoutee a toutes les lignes.

Pour chaque feature/famille, rapporter : presence dans la matrice, missing/default rate, variance, importance moyenne, stabilite entre folds et disponibilite PIT. Une feature importante une seule fois n'est pas une preuve d'alpha.

---

## 6. Modele et tuning

CatBoost RMSE est le candidat principal selon les resultats historiques. LightGBM LambdaRank est un challenger possible, mais ne doit pas etre privilegie sans reproduction de son gain net.

Le tuning est autorise apres les baselines/cibles/features, avec une grille courte predefinie :

| Modele | Variantes limitees | Regle |
|---|---|---|
| CatBoost | depth `5/7`, iterations `300/500`, `l2_leaf_reg` `3/10` | Garder le modele le plus simple a performance equivalente. |
| LightGBM RMSE | depth `5/7`, feuilles coherentes, `min_child_samples` `150/300` | Regularisation avant profondeur. |
| LambdaRank | une configuration historique controlee | Challenger, pas remplacement par defaut. |
| Ridge/ElasticNet | petite grille | Controle lineaire et diagnostic de complexite. |

Le vainqueur de developpement est choisi uniquement avec les folds de developpement; il est execute une fois sur le holdout final. Chaque configuration supplementaire augmente le risque de multiple testing.

---

## 7. Du score au portefeuille swing

Le Global Ranking selectionne les candidats. Il ne doit pas etre confondu avec une instruction de poids ou une permission de risque.

### 7.1 Politiques de portefeuille a comparer

| Politique | Description | Question |
|---|---|---|
| P0 | Selection top/bottom avec caps risque existants | Reference economique. |
| P1 | P0 + caps secteur/industrie/HHI plus stricts | Le gain depend-il d'une concentration cachee ? |
| P2 | Neutralite sectorielle souple versus benchmark | Le ranking garde-t-il un alpha apres retrait du sector-riding ? |
| P3 | Neutralite sectorielle stricte long/short | Diagnostic de stock-picking pur, pas choix de production initial. |

Mesurer distinctement :

$$
net_s = \sum_{i \in s} w_i,
\qquad
gross_s = \sum_{i \in s} |w_i|
$$

Une exposition nette nulle ne garantit pas une faible exposition au risque : long 10 % et short 10 % dans le meme secteur donne un gross de 20 %.

### 7.2 Metriques obligatoires

* IC Spearman par date, moyenne, ecart-type et intervalle de confiance;
* spread top-bottom, long-only et long-short, avant/apres couts;
* turnover, slippage, impact, capacite ADV et nombre de positions;
* rendement annualise, volatilite, Sharpe, Sortino, Calmar et max drawdown;
* exposition nette/gross par secteur, industrie, theme et facteur;
* contribution PnL par horizon, secteur et sens long/short;
* attribution Brinson-Fachler : allocation, selection et interaction;
* stabilite par fold, regime et holdout final.

Interpretation :

* selection positive apres neutralisation, allocation faible : stock-picking credible;
* allocation dominante : bet sectoriel a encadrer ou assumer explicitement;
* interaction dominante : le constructeur de portefeuille est le levier principal;
* spread faible apres couts : ne pas promouvoir, meme si IC positif.

---

## 8. Plan d'action priorise

1. **G0/G1 :** reproduire les deux baselines historiques avec manifests et expliquer les 6 versus 8 splits.
2. **Cible :** tournoi court 504/756, splits, smoothing, neutralisations, une variable a la fois.
3. **Features :** F0-F5 par familles et interactions regime, avec audit d'activite par fold.
4. **Tuning :** petite grille CatBoost/LightGBM sur le schema gagnant seulement.
5. **Portefeuille :** comparer P0-P3 avec memes candidats, couts et risque; calculer attribution Brinson-Fachler.
6. **Holdout :** geler le vainqueur, l'executer une fois sur une periode jamais consultee.

---

## 9. Criteres stop/go

**Go Global Ranking :** IC par date positif et stable, spread net positif apres couts sur la majorite des folds, diversification acceptable, drawdown/turnover compatibles avec le swing, puis confirmation holdout.

**Stop ou reduction :** IC positif mais spread net nul apres couts, performance dependante d'un seul secteur/regime, ou ecart non reproductible entre runs identiques. Dans ce cas, conserver le modele comme diagnostic et chercher d'abord les causes de donnees/protocole avant de complexifier le modele.

**Conclusion :** il existe des voies realistes pour ameliorer le Global Ranking. Pour du swing trading, la priorite est la reproductibilite du baseline, puis les cibles/neutralisations et les interactions de regime, enfin la construction de portefeuille sectoriellement controlee. Un IC modeste mais stable et rentable apres couts vaut plus qu'un IC eleve obtenu par tuning ou concentration non reproductible.
