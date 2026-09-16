Oui. Et après avoir regardé ton registre, je pense qu’il reste encore **des pistes mathématiques réellement différentes** de ce que tu as déjà testé.

Mais il faut distinguer deux choses. D’un côté, il n’existe probablement pas une « formule secrète » qui transforme mécaniquement D1/D10 en 80–90 % de précision. De l’autre, tes expériences ont surtout testé des **classifieurs/rankers sur des représentations assez classiques**. Ton registre montre que l’Oracle d’amplitude est solide, alors que le signe reste proche du hasard ; P0g donne par exemple AUC `0,4904` sur 179 605 D1/D10. Mais E20-B est très important : lorsqu’on introduit une information réellement nouvelle après l’ouverture, la précision D1/D10 monte à `56,91 %`. Donc je ne conclurais pas « D1/D10 est imprévisible ». Je conclurais plutôt : **le signe est mal observable dans la représentation actuelle à J**.

Je partirais maintenant sur une campagne beaucoup plus mathématique.

## 1. Avant de chercher une formule : mesurer si une formule peut exister

C’est la première expérience que je ferais.

Jusqu’à présent tu demandes essentiellement :

```text
features X
→ modèle
→ D1 ou D10
```

Quand le modèle fait 0,50, on ne sait pas si :

```text
A. l'information n'existe pas dans X

ou

B. l'information existe,
   mais Logistic / CatBoost / LGBM ne la trouvent pas.
```

Il existe des outils statistiques précisément pour ça.

Le **Maximum Mean Discrepancy (MMD)** teste si deux ensembles suivent réellement des distributions différentes dans un espace éventuellement non linéaire, via des noyaux RKHS.

On ferait :

```text
X | D1
versus
X | D10
```

avec les features PIT à J.

Et pas seulement MMD :

```text
MMD-RBF
Energy Distance
Henze-Penrose divergence
classifier two-sample test
```

La divergence Henze-Penrose est particulièrement intéressante parce qu’elle peut être reliée à des **bornes du taux d’erreur Bayesien**, c’est-à-dire l’erreur minimale théorique d’un classifieur pour ces distributions.

C’est exactement la question que tu poses :

> « Il existe peut-être une fonction mathématique que mes modèles n’ont pas découverte. »

Cette expérience essaie de répondre :

```text
avec X actuel,
D1 et D10 sont-ils mathématiquement séparables ?
```

Si résultat :

```text
MMD ≈ placebo
HP divergence ≈ 0
Bayes-error bound ≈ 48-50 %
```

alors je fermerais presque définitivement la chasse aux nouvelles formules utilisant **les mêmes 168 features**.

D’autant que ton Meta-Oracle F1 vient justement de montrer que les 168 features historiques n’améliorent même pas le veto Oracle : `47,01 %` baseline contre `46,97 %` CatBoost.

En revanche, si :

```text
D1 ≠ D10 statistiquement
de façon stable OOF
```

mais CatBoost reste à 0,50, alors là :

> **oui, il existe probablement une structure que ta représentation/modélisation actuelle ne capture pas.**

Je mettrais cette expérience en **priorité 0**.

---

# 2. La piste que je trouve la plus prometteuse : les relations lead-lag entre actions

C’est probablement la plus grosse famille mathématique que je ne vois pas réellement testée dans ton registre.

Tu as énormément étudié :

```text
le titre lui-même
SPY
secteur
macro
volume
intraday
fundamentaux
```

Mais pas vraiment :

```text
"quelles autres actions ont tendance
à bouger AVANT celle-ci ?"
```

C’est différent d’une corrélation sectorielle.

Exemple :

```text
NVDA bouge aujourd'hui
      ↓
SMCI réagit ensuite

TSM bouge
      ↓
semi US réagit

matière première bouge
      ↓
producteur/utilisateur réagit
```

C’est un problème de **graphe orienté temporel**.

Et il y a justement de la recherche très récente sur ce sujet. Un article 2026 de *Machine Learning* représente les actifs comme un graphe dynamique où les arêtes représentent des relations lead→lag ; il souligne que ces dépendances changent dans le temps et peuvent être utilisées pour prévoir les mouvements.

Une autre recherche 2026 sur les rendements idiosyncratiques étudie explicitement les dépendances lead-lag après retrait des facteurs communs.

Je commencerais **sans GNN**.

Pour chaque action `i`, on calcule d’abord son rendement résiduel :


```text
epsilon(i,t) = r(i,t)
             - beta(i,m) * r(SPY,t)
             - beta(i,s) * r(sector,t)
```


Puis, uniquement sur le TRAIN :


```text
C(j -> i, k) = Corr(
    epsilon(j, t-k),
    epsilon(i, t)
)
```


pour :

```text
k = 1, 2, 3, 5 jours
```

On retient quelques leaders stables.

Et à J :


```text
L_i(J) = Σ_j Σ_k [ w(j,i,k) * epsilon(j, J-k) ]
```


`L_i` devient une sorte de **pression directionnelle externe**.

Ton système actuel regarde essentiellement :

```text
état de i
→ futur de i
```

On testerait :

```text
état des leaders de i
→ futur de i
```

Ça change réellement l’ensemble d’information.

Je classerais :

```text
Lead-Lag Graph
→ STANDARD_PRO / GO_RESEARCH
```

avant un nouveau CatBoost sur les features existantes.

---

# 3. Une vraie méthode mathématique que tu n’as apparemment pas testée : les Path Signatures

Celle-ci est particulièrement intéressante par rapport à Temporal V2.

Temporal V2 a testé :

```text
niveau
delta
pente
accélération
dispersion
persistance
```

et ça a échoué.

Mais une **signature de chemin** n’est pas juste une autre pente.

Elle vient de la théorie des *rough paths*.

Pour un chemin multidimensionnel :


```text
X(t) = ( x1(t), x2(t), ... )
```


la signature contient notamment :


```text
∫ dX_i
```


puis :


```text
∫[t1 < t2] dX_i(t1) * dX_j(t2)
```


puis des intégrales d’ordre supérieur.

Le deuxième ordre capture notamment :

```text
A bouge puis B
```

différemment de :

```text
B bouge puis A
```

C’est exactement ce que tes pentes/deltas classiques perdent.

Il existe maintenant un ouvrage entier, open access, consacré aux **Signature Methods in Finance**, et un papier 2026 applique spécifiquement des *lead-lag signatures* aux séries financières.

Le papier explique notamment que la transformation lead-lag permet de récupérer des propriétés de variation quadratique via les aires de Lévy.

Je construirais par exemple le chemin :

```text
J-20 ... J

[
  residual_return_stock,
  leader_pressure,
  sector_residual,
  SPY_residual,
  volume_zscore
]
```

puis :

```text
log-signature depth 2
```

et seulement ensuite :

```text
Logistic L2
```

Pas de deep learning.

Pourquoi Logistic ?

Parce que si une transformation mathématique intéressante existe, je préfère qu’elle soit démontrée par :

```text
bonne représentation
+
modèle très simple
```

plutôt que masquée dans un Transformer.

Petite réserve importante : le papier 2026 trouve peu de gain des signatures sur les actions en moyenne, où le momentum classique reste fort. Donc ce n’est absolument pas une garantie.

Mais dans **ton problème conditionnel très particulier Oracle→D1/D10**, ça reste une expérience légitime et véritablement nouvelle.

Je classerais :

```text
Rough Path / Signature
→ EXPÉRIMENTAL SÉRIEUX
```

---

# 4. Une autre route : arrêter de prédire une classe et prédire toute la distribution future

C’est probablement la deuxième expérience que je testerais après lead-lag.

Aujourd’hui, beaucoup de tes formulations demandent :

```text
P(D10)
P(D1)

ou

return H20
```

On peut changer complètement le problème.

On cherche :


```text
F_i(r | X_J) = P( R_i,H20 <= r | X_J )
```


c’est-à-dire **la distribution conditionnelle complète du rendement futur**.

Ensuite seulement on en déduit les queues.

La littérature utilise notamment :

```text
quantile regression
expectile regression
skewed Student-t
distributional regression
conditional EVT
```

Une étude sur des actions européennes a par exemple montré que les quantiles faibles et élevés du rendement peuvent avoir des dynamiques différentes.

Les expectiles sont également étudiés spécifiquement pour les risques de queue et peuvent être plus sensibles à l'amplitude des observations extrêmes que les quantiles classiques.

Je commencerais très simplement :

```text
q05(X)
q10(X)
q25(X)
q50(X)
q75(X)
q90(X)
q95(X)
```

avec sept LightGBM quantile fixes.

Pas d’optimisation massive.

Puis on définit une asymétrie :


```text
A(X) = (q90 - q50) - (q50 - q10)
```


Si :

```text
A > 0
→ queue supérieure plus étendue

A < 0
→ queue inférieure plus étendue
```

Mais je ferais encore mieux.

---

# 5. La formule que je proposerais spécifiquement pour α-Trade

C’est celle-ci que je trouve la plus élégante pour ton architecture.

Ton Oracle estime déjà :


```text
P(E | X)
```


où :

```text
E = futur extrême
  = D1 ∪ D10
```

Appelons cette probabilité :


```text
A(X)
```


Ensuite la seule quantité qui nous manque réellement est :


```text
P(D10 | E, X)
```


Par identité de probabilité :


```text
P(D10 | E, X)
= P(D10 | X) / [ P(D10 | X) + P(D1 | X) ]
```


Je définirais alors le **Tail Polarity Score** :


```text
S(X)
= log(
    [P(D10 | X) + epsilon]
    /
    [P(D1 | X) + epsilon]
  )
```


Donc :

```text
S >> 0  → D10
S << 0  → D1
S ≈ 0   → aucune information directionnelle
```

Et l’architecture devient :


```text
P(D10 | X) = A(X) * sigma(S(X))
```



```text
P(D1 | X) = A(X) * [1 - sigma(S(X))]
```


Conceptuellement :

```text
Oracle A(X)
=
combien il va probablement bouger

S(X)
=
de quel côté penche la queue
```

C’est exactement la séparation que ton système cherche depuis le début.

Mais la différence fondamentale serait :

**je n’entraînerais pas `S(X)` avec les 168 features actuelles uniquement.**

Je l’entraînerais à partir de :

```text
Lead-Lag network
+
Path Signatures
+
éventuellement quantiles conditionnels
```

Donc :

```text
          ┌────────────────────────────┐
          │ Oracle Extreme            │
          │ A(X) = amplitude          │
          └─────────────┬──────────────┘
                        │
                        │
   ┌────────────────────▼────────────────────┐
   │ Direction information                   │
   │                                         │
   │ cross-asset lead/lag                    │
   │ residual peer moves                     │
   │ rough-path signature                    │
   │ conditional upper/lower tails           │
   └────────────────────┬────────────────────┘
                        │
                        ▼
                 Tail Polarity
                     S(X)
                        │
             ┌──────────┴─────────┐
             ▼                    ▼
          D10 prob             D1 prob
```

Je donnerais à cette expérience un nom du genre :

```text
P-MATH-TAIL-POLARITY
```

---

# 6. Et surtout : ne plus forcer une décision sur 100 % des Oracle

Tu as dit quelque chose d’important :

> je ne cherche pas 100 %.

Alors mathématiquement, ton problème peut être reformulé.

Tu ne veux peut-être pas maximiser :

```text
accuracy sur tous les candidats
```

mais :

```text
accuracy élevée
sur une fraction seulement des candidats.
```

C’est le domaine de la **selective classification / classification avec abstention**.

La littérature formalise explicitement le compromis :


```text
coverage <-> error
```


et permet au modèle de répondre :

```text
LONG
SHORT
JE NE SAIS PAS
```

plutôt que d’être obligé de choisir D1/D10.

Par exemple :

```text
|S| < 0.2
→ ABSTAIN

S > 0.8
→ D10

S < -0.8
→ D1
```

Les seuils seraient évidemment appris uniquement sur train.

On mesurerait :

| Coverage | Precision D1/D10 |
|---:|---:|
| 100 % | 51 % |
| 50 % | ? |
| 30 % | ? |
| 20 % | ? |
| 10 % | ? |

Si tu trouves :

```text
100% → 51%
50%  → 53%
30%  → 56%
20%  → 59%
10%  → 63%
```

ça pourrait être beaucoup plus utile pour toi qu’un modèle à :

```text
53% sur 100% des candidats.
```

Mais attention : **l’abstention ne crée pas d’information**. Elle ne vaut la peine que si le nouveau score possède déjà un minimum de pouvoir prédictif.

---

# 7. Une autre petite famille mathématique à tester : semivariances signées

Tu as testé volatilité et intraday, mais je ne vois pas de test explicite de **realized semivariance**.

Au lieu de :


```text
RV = Σ r_t²
```


on décompose :


```text
RS+ = Σ [ r_t² * 1(r_t > 0) ]
```


et :


```text
RS- = Σ [ r_t² * 1(r_t < 0) ]
```


Puis :


```text
B = (RS+ - RS-) / (RS+ + RS-)
```


La littérature de Barndorff-Nielsen, Kinnebrock et Shephard a précisément développé cette décomposition positive/négative de la variation réalisée.

Tu pourrais faire :

```text
RS+_5m
RS-_5m

jump+
jump-

overnight+
overnight-

opening_RS_balance
full_session_RS_balance
```

Je la classe cependant moins haut, parce que cette littérature est surtout très forte pour la **prévision de volatilité**, donc elle risque encore une fois d’améliorer ton Oracle d’amplitude plutôt que le signe.

---

# 8. Conditional Extreme Value Theory : scientifiquement intéressant, mais pas ma première expérience

Il existe aussi toute une littérature de **multivariate/conditional extreme value theory**.

Le modèle de Heffernan–Tawn, par exemple, cherche précisément à modéliser la distribution d’autres variables **conditionnellement au fait qu’une composante soit extrême**.

Ça ressemble beaucoup à ton problème conceptuel :

```text
Oracle dit :
"nous sommes dans une situation d'extrême"

puis :
quelle est la distribution conditionnelle
du signe et des autres variables ?
```

On pourrait étudier :

```text
stock future tail
conditionné par
sector/market/peer state
```

Mais D1/D10 = 10 % de chaque côté n’est pas extrêmement profond dans la queue au sens EVT. Je la mettrais donc :

```text
EVT / Conditional Extremes
→ EXPÉRIMENTAL
```

et pas en premier.

---

# Ma hiérarchie maintenant

| Priorité | Expérience | Pourquoi |
|---|---|---|
| **0** | **MMD + Energy + HP Bayes-error audit** | savoir si une séparation mathématique existe dans les données actuelles |
| **1** | **Lead-Lag graph sur résidus** | apporte une information cross-asset réellement nouvelle |
| **2** | **Lead-Lag + Path Signature** | représentation mathématique non testée de l'ordre des mouvements |
| **3** | **Distributional / Quantile tail model** | prédire toute la distribution au lieu d'une classe |
| **4** | **Tail Polarity Score + abstention** | architecture que je construirais pour α-Trade |
| 5 | Semivariance / signed jumps | faible coût, mais risque de n'expliquer que l'amplitude |
| 6 | Conditional EVT | scientifique mais plus expérimental |
| 7 | HMM/Change-point/TDA/etc. | seulement si les étapes précédentes montrent quelque chose |

Je **ne partirais pas maintenant vers HMM, Transformer, RL, genetic programming ou encore 200 nouvelles features**. Ton registre montre déjà que les variations de modèle sur le même espace d'information ne résolvent pas le problème.

Le chemin qui me paraît réellement nouveau est donc :

```text
P-MATH-0
NONPARAMETRIC SEPARABILITY AUDIT
        ↓
si aucune séparation
        ↓
arrêt features actuelles

si séparation ou après ajout d'information :
        ↓
P-MATH-1
CROSS-ASSET LEAD-LAG GRAPH
        ↓
P-MATH-2
ROUGH-PATH / SIGNATURE
        ↓
P-MATH-3
CONDITIONAL TAIL DISTRIBUTION
        ↓
Tail Polarity Score
S = log(P(D10) / P(D1))
        ↓
SELECTIVE CLASSIFICATION
        ↓
D10 / D1 / ABSTAIN
```

C’est la route que je tenterais maintenant. Elle ne repose pas sur l’espoir qu’un CatBoost mieux réglé trouve miraculeusement le signe : **elle change successivement la question statistique, la source d’information, la représentation mathématique et enfin la règle de décision.**
