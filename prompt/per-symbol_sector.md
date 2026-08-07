# Synthese - per-symbol et per-sector : regression, ternaire et equilibre long/short/flat

**Date :** 2026-08-07  
**Objet :** determiner si les poids de classes, les penalites ou les seuils peuvent corriger des predictions long/short faibles ou dominees par la classe `flat`.

---

## 1. Reponse courte

Oui, les poids de classes et les seuils peuvent etre ajustes. Mais ils ne resolvent pas le meme probleme :

1. **Le modele ne distingue pas long et short.** Modifier les poids ne cree pas d'information predictive; cela deplace seulement la frequence des predictions.
2. **Le modele possede un signal mais sa decision est mal calibree ou trop prudente.** La calibration et les seuils peuvent alors augmenter le rendement net en changeant le compromis entre couverture, faux positifs et turnover.

Un meilleur F1, davantage de longs/shorts, ou un taux d'action plus eleve ne sont pas des preuves d'alpha. La decision doit etre prise avec IC par date, spread net, PnL apres couts, turnover, drawdown et holdout OOS.

---

## 2. Etat actuel du code

Le code distingue deja le fit du modele et la decision long/short/flat.

### 2.1 Arbres tabulaires

| Backend | Mode ternaire | Equilibrage actuel |
|---|---|---|
| LightGBM | `LGBMClassifier(objective="multiclass")` | `class_weight="balanced"` |
| CatBoost | `CatBoostClassifier(loss_function="MultiClass")` | `auto_class_weights="Balanced"` |

Les arbres compensent donc deja le desequilibre de classes pendant l'entrainement. Ajouter sans analyse une ponderation manuelle supplementaire risque de surcompenser une classe et de degrader la calibration des probabilites.

### 2.2 LSTM

Le LSTM accepte des poids explicites dans `ModelConfig` :

| Parametre | Defaut |
|---|---:|
| `ternary_weight_short` | 1.0 |
| `ternary_weight_flat` | 1.5 |
| `ternary_weight_long` | 1.0 |

Ils alimentent `CrossEntropyLoss(weight=...)`. Ils sont donc utiles pour une experience controlee LSTM, mais le LSTM reste en quarantaine tant que ses predictions de regression ont une echelle/MSE incoherente avec les arbres.

### 2.3 Decision ternaire partagee

La politique `TernaryDecisionPolicy` est utilisee par l'entrainement, l'evaluation, la prediction et le replay. Elle prend les probabilites calibrees et decide :

| Parametre | Defaut | Role |
|---|---:|---|
| `ternary_threshold_short` | 0.45 | Probabilite minimale pour autoriser un short. |
| `ternary_threshold_long` | 0.45 | Probabilite minimale pour autoriser un long. |
| `ternary_top2_margin` | 0.05 | Ecart minimal entre meilleure et deuxieme classe. |

Regle :

$$
p_{long} \geq \theta_{long}, \quad p_{long} - p_{second} \geq m \Rightarrow long
$$

$$
p_{short} \geq \theta_{short}, \quad p_{short} - p_{second} \geq m \Rightarrow short
$$

Sinon la decision est `flat`, c'est-a-dire une abstention. Cela est preferable a une prise de position forcee lorsque le modele est incertain.

### 2.4 Calibration et selection

Pour le ternaire, les baselines tabulaires calibrent les trois probabilites par un `TemperatureScaler` sur la validation. La decision et les seuils doivent etre selectionnes sur la validation du fold, puis controles une seule fois sur le test/WF du fold.

Le principe est :

$$
\max_{\theta_{long},\theta_{short},m}
spread_{net} - \lambda_{turn} \cdot turnover
$$

sous contraintes de taux d'action et de nombre minimal de trades :

$$
rate_{min} \leq action\_rate \leq rate_{max},
\qquad n_{long}, n_{short} \geq n_{min}.
$$

Les seuils ne doivent jamais etre choisis apres lecture des resultats OOS ou du holdout final.

---

## 3. Diagnostic per-sector

### 3.1 Resultat de T3

Le test per-sector ternaire T3 avait approximativement :

* classes vraies : $30\%$ short, $39\%$ flat, $30\%$ long;
* predictions WF : environ $70\%$ flat;
* directional accuracy WF : environ $39\%$;
* direction accuracy validation/test interne : environ $69\%-71\%$.

La degradation validation vers walk-forward indique un probleme de generalisation temporelle, pas simplement un biais de decision `flat`.

Baisser le poids de `flat` ou diminuer les seuils ferait probablement apparaitre plus de longs/shorts. Mais sans IC relatif et spread net OOS positif, cela ne ferait qu'augmenter le taux d'action et les faux positifs. Les couts et drawdowns peuvent alors empirer.

### 3.2 Decision per-sector

Ne pas commencer par les poids des classes. Le per-sector ternaire est une recherche secondaire tant que la regression relative ne bat pas les controles simples.

Ordre impose :

1. Regression H20 avec cible relative explicite;
2. IC relatif par date, top-bottom intra-secteur et spread net de couts;
3. comparaison a zero predictor et momentum intra-secteur;
4. seulement si ces metriques sont positives et stables : classification ternaire, calibration et grille de seuils;
5. poids de classes manuels seulement si une classe est systematiquement ignoree malgre un signal OOS deja etabli.

Une reprise per-sector durable requiert une hypothese economique nouvelle et, idealement, des donnees sectorielles specialisees PIT : courbe energie/stocks, taux/spreads credit pour Financials, commandes/capex pour Semiconductors, taux reels/refinancement pour Real Estate, etc.

---

## 4. Diagnostic per-symbol

Le per-symbol est plus prometteur mais non valide. Le pilote `71ad0b` sur dix titres donne environ :

| Backend | Directional accuracy WF | MSE WF | Lecture |
|---|---:|---:|---|
| CatBoost | 57.24 % | 1.1503 | Signal a repliquer. |
| LightGBM | 54.61 % | 1.1685 | Signal faible a verifier. |
| LSTM | 56.96 % | 39.9255 | Echelle/calibration a diagnostiquer. |

Le pilote ne suffit pas : dix titres de `ticket-recherche` ne constituent pas un univers liquide, PIT et representatif. La prochaine etape est une replication sur `50-100` titres eligibles par ADV, spread, historique et disponibilite des donnees, avec comparaison appariée au Global Ranking.

### 4.1 Regression per-symbol : mode principal

La regression conserve la magnitude du score. Au lieu de forcer un long/short a chaque observation, construire une zone d'abstention :

$$
score > \tau_{long} \Rightarrow long,
$$

$$
score < -\tau_{short} \Rightarrow short,
$$

$$
-\tau_{short} \leq score \leq \tau_{long} \Rightarrow flat.
$$

Les seuils $\tau_{long}$ et $\tau_{short}$ sont selectionnes uniquement sur la validation de chaque fold, selon le spread net, les couts et le taux d'action. Ils ne modifient pas l'entrainement; ils transforment un score continu en decisions de portefeuille.

### 4.2 Ternaire per-symbol : challenger utile

Le ternaire est pertinent comme challenger si l'objectif est une probabilite explicite `long/flat/short`, mais il ne doit pas remplacer la regression sans une preuve economique.

Pour CatBoost/LightGBM :

1. conserver `Balanced`/`auto_class_weights="Balanced"` au premier essai;
2. calibrer les probabilites sur validation;
3. effectuer une petite grille sur les seuils et marges;
4. evaluer le test/WF une fois;
5. comparer aux scores continus avec les memes couts et meme univers.

Mini-grille raisonnable, preregistree :

| Parametre | Valeurs |
|---|---|
| `threshold_long` | 0.45, 0.50, 0.55 |
| `threshold_short` | 0.45, 0.50, 0.55 |
| `top2_margin` | 0.03, 0.05, 0.10 |

Une asymetrie des seuils est possible, mais seulement si elle est expliquee par les couts et la distribution/qualite OOS des shorts versus longs. Par exemple, un short plus couteux ou plus risqué peut exiger $	heta_{short} > \theta_{long}$.

### 4.3 Quand ponderer explicitement les classes

Tester des poids manuels seulement si les trois conditions sont reunies :

1. la distribution vraie est durablement desequilibree dans le train;
2. le modele bat deja les controles en IC/spread OOS, mais ignore systematiquement une classe;
3. les probabilites restent calibrees apres ponderation et le gain subsiste sur WF/holdout.

Pour LightGBM/CatBoost, ne pas cumuler des poids manuels avec `balanced`/`auto_class_weights` sans desactiver explicitement l'automatisme et tracer la ponderation effective. Sinon, le resultat ne sera pas interpretable.

Pour le LSTM, tester `flat=1.0`, `1.25`, `1.5` est possible apres correction de l'echelle de prediction, avec les memes folds et seeds. Ne pas utiliser le F1 de validation seul pour choisir.

---

## 5. Matrice de decision

| Situation diagnostique | Action appropriee | Action a eviter |
|---|---|---|
| Probas calibrees, IC/spread OOS positifs, trop de flat | Diminuer progressivement seuils/marge sur validation | Reponderer les classes au hasard |
| Probas calibrees, longs corrects mais shorts insuffisants et cout short plus haut | Seuil short plus exigeant ou politique short specifique | Forcer autant de shorts que de longs |
| Une classe rare, mais signal OOS positif | Tester ponderation unique et tracée | Cumul `Balanced` + poids manuels |
| DA/F1 au hasard, IC/spread OOS nul | Revoir univers, cible/donnees/features | Augmenter action rate avec seuils bas |
| Bonne validation, mauvais WF | Geler les hyperparametres et analyser derives/overfit | Choisir les seuils sur test/WF |
| LSTM MSE hors echelle | Diagnostiquer scaler, target, checkpoint, inversion de transform | Tuner poids de classe/architecture |

---

## 6. Protocole recommande

### Per-symbol

1. Baseline H20 regression CatBoost/LightGBM sur 50-100 titres liquides, avec controls zero/momentum/ElasticNet.
2. Evaluer IC par date, spread net, PnL, turnover, drawdown et exposition, pas seulement F1/DA.
3. Optimiser des seuils d'abstention de regression sur validation seulement.
4. Tester le ternaire avec arbres deja balances et la mini-grille de policy.
5. Ne tester une ponderation manuelle qu'apres diagnostic et avec une seule variante.
6. Confirmer la meilleure configuration une fois sur holdout final, puis comparer Global Ranking seul, per-symbol seul et combinaison OOF bornée.

### Per-sector

1. Conserver le mode en shadow research.
2. Valider d'abord une regression relative H20 contre zero et momentum intra-secteur.
3. Mesurer IC relatif, top-bottom, couts et taille effective par secteur/date.
4. Reprendre le ternaire uniquement si la regression a un signal relatif OOS stable.
5. Ne modifier poids/seuils qu'apres une calibration et une preuve de signal; sinon fermer la branche generique.

---

## 7. Conclusion

Les poids de classe, les probabilites et les seuils sont des outils de calibration et de construction de decision. Ils peuvent ameliorer une strategie qui possede deja une information predictive, en reduisant les positions ambiguës et en ajustant le cout relatif des longs et shorts. Ils ne peuvent pas transformer des predictions aleatoires en alpha.

La priorite est donc : preuve de signal economique OOS, calibration sur validation, policy de decision prudente, puis ponderation seulement lorsque le diagnostic justifie une asymetrie. Le per-symbol peut meriter cette sequence; le per-sector doit d'abord demontrer une regression relative stable avant toute correction de classes.
