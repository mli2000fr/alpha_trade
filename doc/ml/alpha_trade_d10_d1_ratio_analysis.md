# Analyse du ratio `d10_d1_ratio` — Alpha Trade

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## 1. Objectif

Cette analyse porte sur le fichier extrait de l'application **Alpha Trade** et vise à étudier le comportement du ratio :

`d10_d1_ratio`

L'objectif principal est de déterminer :

- s'il existe des corrélations avec les autres variables du fichier ;
- quelles relations sont simplement mécaniques ;
- quelles variables de marché semblent réellement associées au ratio ;
- si certaines variables peuvent avoir un intérêt prédictif pour les jours suivants ;
- comment exploiter ces observations dans la logique de `market_regime` d'Alpha Trade.

---

## 2. Taille de l'échantillon

Le fichier contient :

- **1 695 lignes**
- **1 676 valeurs exploitables** pour `d10_d1_ratio`

---

## 3. Définition du ratio

Un point important ressort de l'analyse :

> `d10_d1_ratio = d10_pct / d1_pct`

Le ratio est donc directement construit à partir de `d10_pct` et `d1_pct`.

Cela signifie que les très fortes corrélations avec les variables directement liées à D10 et D1 ne doivent pas être interprétées comme des découvertes statistiques indépendantes.

En particulier, les relations avec :

- `d10_pct`
- `d1_pct`
- `d10_count`
- `d1_count`

sont en grande partie **mécaniques**.

L'analyse la plus intéressante consiste donc à regarder les relations avec les variables externes décrivant l'état du marché.

---

# 4. Corrélations avec les principales variables de marché

Les corrélations de Pearson observées avec `d10_d1_ratio` sont les suivantes :

| Variable | Corrélation avec `d10_d1_ratio` | Interprétation |
|---|---:|---|
| `vix3m` | **+0,329** | Relation positive modérée |
| `vix` | **+0,318** | Relation positive modérée |
| `vix9d` | **+0,281** | Relation positive |
| `vxn` | **+0,278** | Relation positive |
| `sentiment_score` | **-0,151** | Sentiment élevé associé à un ratio plus faible |
| `ten_y` | **-0,164** | Relation faible |
| `move` | **-0,067** | Quasiment aucune relation |
| `yield_10y_5d_pct` | **-0,017** | Aucune relation claire |

---

# 5. Relation entre volatilité et `d10_d1_ratio`

Le résultat principal est relativement clair :

> **Plus la volatilité implicite du marché est élevée, plus `d10_d1_ratio` tend à être élevé.**

Les variables les plus intéressantes sont notamment :

- VIX
- VIX3M
- VIX9D
- VXN

Le VIX et le VIX3M montrent les relations les plus fortes parmi les variables de marché analysées.

---

## 5.1 Analyse par niveau de VIX

Pour aller plus loin qu'une simple corrélation linéaire, les observations ont été réparties en cinq groupes en fonction du niveau du VIX.

| Niveau moyen du VIX | `d10_d1_ratio` moyen | `d10_d1_ratio` médian |
|---:|---:|---:|
| 13,8 | **1,11** | 0,93 |
| 16,4 | **1,13** | 0,96 |
| 18,8 | **1,21** | 1,06 |
| 22,6 | **1,61** | 1,26 |
| 32,1 | **2,02** | 1,28 |

Le phénomène est très visible.

Lorsque le VIX est faible, le ratio moyen est proche de :

`1,1`

Lorsque le VIX atteint les niveaux les plus élevés de l'échantillon, le ratio moyen monte autour de :

`2,0`

Autrement dit, dans les phases de forte volatilité, D10 devient relativement beaucoup plus important par rapport à D1.

---

# 6. Relation avec VIX3M

Le même phénomène apparaît avec `vix3m`.

| Niveau moyen du VIX3M | `d10_d1_ratio` moyen |
|---:|---:|
| ~16 | **1,07** |
| ~19 | **1,15** |
| ~21 | **1,27** |
| ~25 | **1,62** |
| ~33 | **1,97** |

La progression est très nette.

Cela confirme que le phénomène observé n'est pas spécifique au VIX spot.

Il semble davantage associé au **régime général de volatilité du marché**.

---

# 7. Relation avec le sentiment de marché

Le `sentiment_score` présente une relation inverse avec le ratio.

La corrélation de Pearson est d'environ :

`-0,151`

Cette relation est relativement faible en valeur absolue, mais l'analyse par groupes montre une tendance intéressante.

| Sentiment moyen | `d10_d1_ratio` moyen |
|---:|---:|
| 0,015 | **1,68** |
| 0,069 | **1,47** |
| 0,101 | **1,38** |
| 0,131 | **1,35** |
| 0,179 | **1,20** |

On observe donc que :

> **Plus le sentiment est positif, plus `d10_d1_ratio` tend à diminuer.**

Et inversement :

> **Lorsque le sentiment est faible ou négatif, `d10_d1_ratio` tend à augmenter.**

---

# 8. Hypothèse de régime de marché

Les résultats suggèrent l'hypothèse suivante :

```text
Stress / peur du marché ↑
        ↓
Volatilité implicite ↑
        ↓
d10_d1_ratio ↑
```

En parallèle :

```text
Sentiment positif ↑
        ↓
d10_d1_ratio ↓
```

Cela signifie que `d10_d1_ratio` pourrait être utilisé comme une mesure indirecte de la structure des opportunités de marché selon le régime de volatilité.

---

# 9. Analyse temporelle : VIX et ratio futur

Une analyse supplémentaire a été réalisée en comparant le VIX du jour avec la valeur future de `d10_d1_ratio`.

Résultats :

| Horizon du ratio | Corrélation avec VIX | Corrélation avec VIX3M |
|---|---:|---:|
| Même jour | 0,318 | 0,329 |
| J+1 | 0,328 | 0,334 |
| J+2 | 0,342 | 0,341 |
| J+5 | **0,364** | **0,345** |
| J+10 | **0,385** | **0,387** |

Ce résultat est particulièrement intéressant.

La relation ne disparaît pas lorsque l'on regarde le ratio futur.

Elle semble même augmenter progressivement jusqu'à J+10.

Le VIX et le VIX3M pourraient donc contenir une information utile sur le comportement futur de `d10_d1_ratio`.

---

# 10. Attention : corrélation ne signifie pas prédiction

Il ne faut toutefois pas conclure immédiatement que :

> « le VIX prédit directement `d10_d1_ratio` ».

Les marchés financiers présentent une forte persistance des régimes.

Par exemple :

- un régime de volatilité élevée peut durer plusieurs jours ou plusieurs semaines ;
- le VIX est lui-même autocorrélé ;
- `d10_d1_ratio` peut également présenter une autocorrélation ;
- plusieurs variables peuvent être liées à une même cause sous-jacente.

Une corrélation avec le ratio à J+10 peut donc venir en partie de la persistance du régime de marché.

Pour parler réellement de capacité prédictive, il faudrait compléter l'analyse avec des tests supplémentaires.

---

# 11. Interprétation pour Alpha Trade

Une interprétation possible est que `d10_d1_ratio` mesure en partie :

> **la domination relative des mouvements ou opportunités D10 par rapport aux mouvements D1 dans les périodes de stress de marché.**

Dans les marchés calmes :

```text
D10 / D1 ≈ faible à modéré
```

Dans les marchés fortement volatils :

```text
D10 / D1 ≈ nettement plus élevé
```

Autrement dit, les mouvements ou signaux observés sur l'horizon D10 prennent davantage d'importance relative lorsque le marché entre dans un régime de stress.

---

# 12. Utilisation possible dans `market_regime`

Une première logique de régime pourrait combiner :

```text
VIX / VIX3M élevé
+
sentiment faible
=
probabilité plus importante d'un d10_d1_ratio > 1
```

Cela pourrait permettre de distinguer plusieurs états de marché.

Exemple conceptuel :

```text
REGIME CALME
- VIX faible
- VIX3M faible
- sentiment correct
- d10_d1_ratio proche ou inférieur à 1

REGIME INTERMEDIAIRE
- volatilité en hausse
- sentiment qui se dégrade
- d10_d1_ratio entre environ 1 et 1,5

REGIME STRESS
- VIX élevé
- VIX3M élevé
- sentiment faible
- d10_d1_ratio nettement supérieur à 1
```

Les seuils exacts doivent évidemment être calibrés statistiquement sur l'historique.

---

# 13. Variables dérivées à tester

Le VIX brut est utile, mais des variables dérivées pourraient être encore plus informatives.

## 13.1 Structure temporelle du VIX

### Ratio VIX9D / VIX

```text
vix9d / vix
```

Permet de comparer la volatilité très court terme avec la volatilité à environ un mois.

Une forte hausse de ce ratio peut signaler un stress immédiat.

---

### Ratio VIX / VIX3M

```text
vix / vix3m
```

Cette variable est particulièrement intéressante pour identifier la structure de volatilité.

Situation normale :

```text
VIX < VIX3M
```

Stress important :

```text
VIX > VIX3M
```

Le passage en inversion de la courbe de volatilité peut être un indicateur de stress très pertinent.

---

## 13.2 Pente de la term structure VIX

Exemple :

```text
vix3m - vix
```

ou :

```text
(vix3m - vix) / vix
```

Cette variable permet de distinguer :

- contango ;
- courbe plate ;
- backwardation.

Elle pourrait être plus informative que le niveau absolu du VIX.

---

## 13.3 Variation du VIX

Tester par exemple :

```text
VIX variation 1 jour
VIX variation 3 jours
VIX variation 5 jours
VIX variation 10 jours
```

Exemple :

```text
vix_change_5d = vix(t) / vix(t-5) - 1
```

Il est possible que la **vitesse de montée du VIX** soit plus informative que son niveau absolu.

---

# 14. Combinaison VIX + sentiment

Une piste intéressante consiste à construire une variable composite.

Par exemple :

```text
stress_score = VIX × (1 - sentiment_score)
```

ou après normalisation :

```text
stress_score =
zscore(VIX)
-
zscore(sentiment_score)
```

L'idée est de détecter les situations dans lesquelles :

```text
volatilité élevée
+
sentiment faible
```

se produisent simultanément.

Ces situations pourraient correspondre aux niveaux les plus élevés de `d10_d1_ratio`.

---

# 15. Autres analyses recommandées

Pour déterminer si `d10_d1_ratio` peut devenir une véritable variable exploitable dans Alpha Trade, plusieurs analyses complémentaires sont recommandées.

## 15.1 Corrélation de Spearman

Pearson mesure principalement les relations linéaires.

La corrélation de Spearman permettrait de détecter des relations monotones mais non nécessairement linéaires.

Particulièrement intéressant pour :

- VIX ;
- VIX3M ;
- sentiment ;
- MOVE ;
- taux.

---

## 15.2 Analyse des seuils

Tester par exemple :

```text
P(d10_d1_ratio > 1 | VIX < 15)
P(d10_d1_ratio > 1 | VIX 15-20)
P(d10_d1_ratio > 1 | VIX 20-25)
P(d10_d1_ratio > 1 | VIX 25-30)
P(d10_d1_ratio > 1 | VIX > 30)
```

Puis la même chose pour :

```text
d10_d1_ratio > 1.2
d10_d1_ratio > 1.5
d10_d1_ratio > 2
```

Cela permettrait de produire des règles directement exploitables par le moteur Alpha Trade.

---

## 15.3 Analyse conditionnelle VIX + sentiment

Exemple :

```text
VIX > 25
AND
sentiment_score < 0.08
```

Comparer ensuite :

```text
moyenne d10_d1_ratio
médiane d10_d1_ratio
probabilité ratio > 1
probabilité ratio > 1.5
probabilité ratio > 2
```

Cette analyse pourrait révéler des combinaisons beaucoup plus fortes que les variables prises séparément.

---

# 16. Modèles prédictifs possibles

Une étape suivante pourrait consister à construire un modèle dont la cible est :

```text
d10_d1_ratio(t + N)
```

avec par exemple :

```text
N = 1
N = 5
N = 10
```

Variables explicatives potentielles :

```text
VIX
VIX9D
VIX3M
VXN
MOVE
sentiment_score
10Y yield
variation du 10Y
VIX/VIX3M
VIX9D/VIX
variation VIX 5 jours
variation VIX 10 jours
```

Des modèles relativement simples suffisent au départ :

- régression linéaire ;
- Random Forest ;
- XGBoost ;
- Gradient Boosting.

L'objectif principal serait alors de mesurer l'importance réelle des variables.

---

# 17. Classification plutôt que régression

Pour Alpha Trade, il pourrait être encore plus intéressant de transformer le problème en classification.

Exemple :

```text
TARGET = 1 si d10_d1_ratio > 1.5
TARGET = 0 sinon
```

Le modèle chercherait alors à répondre à la question :

> « Quelle est la probabilité que D10 devienne significativement dominant par rapport à D1 dans les prochains jours ? »

Cela peut être plus directement exploitable pour le moteur de décision qu'une estimation exacte du ratio.

---

# 18. Conclusion

L'analyse du fichier met en évidence plusieurs éléments importants.

### 1. Les variables D1/D10

Les corrélations fortes avec les variables directement liées à D1 et D10 sont principalement dues à la construction mathématique de `d10_d1_ratio`.

Elles ne constituent donc pas des signaux indépendants.

### 2. Volatilité

Le résultat externe le plus clair concerne la volatilité.

Les variables :

```text
VIX
VIX3M
VIX9D
VXN
```

présentent toutes une relation positive avec `d10_d1_ratio`.

Le VIX et le VIX3M ressortent particulièrement.

### 3. Sentiment

Le sentiment présente une relation inverse :

```text
sentiment positif ↑
→
d10_d1_ratio ↓
```

### 4. Régime de stress

Les résultats semblent indiquer :

```text
volatilité élevée
+
sentiment faible
→
d10_d1_ratio élevé
```

Cela peut être particulièrement pertinent pour identifier un **régime de marché stressé** dans Alpha Trade.

### 5. Dimension prédictive potentielle

Le fait que les corrélations avec VIX et VIX3M restent présentes, et même augmentent jusqu'à J+10, mérite une investigation plus poussée.

Ce résultat est prometteur, mais doit être validé en contrôlant :

- l'autocorrélation ;
- la persistance des régimes ;
- les effets temporels ;
- la performance hors échantillon.

---

# 19. Prochaine étape recommandée

La suite la plus utile pour Alpha Trade serait de chercher automatiquement :

1. les variables les plus prédictives de `d10_d1_ratio` ;
2. les meilleurs seuils de VIX et de sentiment ;
3. les meilleures combinaisons de variables ;
4. les probabilités conditionnelles de `d10_d1_ratio > 1`, `> 1.5` et `> 2` ;
5. les performances prédictives à J+1, J+5 et J+10 ;
6. les règles pouvant être directement intégrées au `market_regime`.

L'objectif final serait de transformer l'observation statistique :

```text
VIX élevé → d10_d1_ratio élevé
```

en une règle quantitative exploitable, par exemple :

```text
IF
    vix > seuil_1
    AND vix/vix3m > seuil_2
    AND sentiment_score < seuil_3
THEN
    probability(d10_d1_ratio > 1.5 dans les 5 prochains jours)
    = XX %
```

Cette approche permettrait d'intégrer le ratio dans Alpha Trade non seulement comme une métrique descriptive, mais comme un véritable **signal de régime et d'aide à la décision**.
