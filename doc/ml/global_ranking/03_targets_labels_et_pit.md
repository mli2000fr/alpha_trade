# 3 — Targets, labels et étanchéité temporelle

## Calcul dans les folds isolés

La fonction `_compute_ranking_targets` est appelée séparément sur le DataFrame
train et le DataFrame validation de chaque split. Le `shift(-horizon)` ne peut
donc pas aller chercher un cours dans le fold voisin. Les lignes de fin dont le
futur sort du fold deviennent `NaN`, puis sont éliminées avant le fit.

Cette isolation est le principal garde-fou PIT du label. Calculer la target sur
le dataset complet puis découper les folds créerait une fuite à leurs frontières.

## Étape 1 — rendement futur et rang

Pour chaque horizon `h` :

```text
future_return_h = close[t+h] / close[t] - 1
```

À partir de H5, ce rendement est divisé par
`rolling_volatility_20.clip(lower=0.001)`. La cible classe donc une performance
ajustée de volatilité, pas le rendement brut. Pour chaque date, les valeurs sont
winsorisées aux quantiles 1 % et 99 %, puis transformées en percentile.

Le label discret vaut :

```text
label_h = floor(percentile_h × 10), borné entre 0 et 9
```

Ces déciles alimentent les rankers. La version continue du percentile reste
utilisée pour l’IC et les diagnostics.

## Étape 2 — lissage multi-horizons

Seulement pour H10/H15/H20, si au moins deux horizons sont disponibles :

```text
target_lissée_h = 50 % target_h + 50 % moyenne(H10,H15,H20)
```

Le résultat est re-ranké par date et reconverti en décile. H3 et H5 ne sont pas
lissés, car le code les considère trop bruités pour cette opération.

## Étape 3 — neutralisation secteur

Lorsque le mapping existe, la médiane de target du secteur à la date est
soustraite, puis le résultat est à nouveau classé par date. Les titres sans
secteur conservent leur target avant cette soustraction.

## Étape 4 — neutralisation facteurs

Si au moins deux facteurs sont présents, le code ajuste pour chaque date une
régression OLS avec constante sur les colonnes de facteurs (taille, value,
momentum selon les colonnes disponibles). Les résidus deviennent la nouvelle
target, puis sont re-rankés et remis en déciles. Si le groupe contient moins de
20 observations, la target existante est conservée pour ce groupe.

## Mode `ranking_raw_target`

Lorsque ce flag vaut vrai, la fonction s’arrête après l’étape 1. Elle conserve
le rang percentile brut, sans lissage, neutralisation secteur ni neutralisation
facteurs. Ce mode change substantiellement le contrat du modèle et doit figurer
dans toute comparaison.

## Ce que le label ne signifie pas

- le décile 9 ne garantit pas un rendement positif ;
- deux titres de dates différentes ne partagent pas la même population ;
- les horizons ≥5 optimisent une performance ajustée de volatilité ;
- la neutralisation peut privilégier le meilleur titre relatif d’un secteur
  même si tout le secteur baisse ;
- le label n’est pas la classe long/flat/short persistée par la synthèse aval.

## Audit anti-fuite

Vérifier que splits sont construits par dates, que les targets sont calculées
après le split, que toutes les données de features respectent leur date de
disponibilité, que l’univers est résolu PIT et que le modèle/feature selection
ne consulte pas les métriques de la période finale de test.

