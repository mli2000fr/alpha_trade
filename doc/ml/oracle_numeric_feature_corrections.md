# Correction des facteurs et ratios EXPERT — 7 octobre 2026

## Périmètre et décision

À la suite de [l'audit H20](us_oracle_h20_dataset_quality_audit.md), l'utilisateur
a demandé de corriger les calculs plutôt que de retirer davantage de titres.
Deux modules de calcul partagés sont corrigés :
`modelFactory/factor_features.py` et `modelFactory/features.py`.

Les 1 790 titres restants sont conservés. Aucune migration SQL, correction de
barre, réécriture de label, modification de modèle sauvegardé ou intervention
sur un batch métier en cours. Aucun entraînement ou calcul de PnL lancé.

## 1. Facteurs benchmark : prix ajustés comme source de rendement

### Cause

Les 3 023 rendements SPY persistés dans la fenêtre d'audit étaient NULL. L'ancien
module les remplissait avec zéro : variance marché nulle, valeurs par défaut
beta=1/alpha=0/R²=0 et momentum relatif amputé de sa composante marché.

### Contrat corrigé

- Si des prix `close` sont fournis, reconstruire la même clôture ajustée que le
  moteur partagé, puis calculer `pct_change(fill_method=None)`. La colonne
  persistée `daily_return` du benchmark n'est pas prioritaire, même si elle
  contient des zéros ou des valeurs obsolètes.
- Les prix non finis ou non positifs ne produisent pas de rendement estimable.
- Les entrées ne contenant que des dates et des rendements restent compatibles.
  Ce fallback ne réintroduit pas de zéro à la place d'une valeur manquante.
- Aligner exactement les dates ; ne pas propager le rendement de la veille.
- Pour les prix, insérer avant différenciation les dates observées sur le titre
  mais absentes du benchmark : ni la date absente ni la variation suivante
  couvrant plusieurs séances ne deviennent un faux rendement quotidien.
- Rejeter les dates benchmark nulles/dupliquées et les dates titre nulles,
  dupliquées ou non triées, plutôt que calculer sur une identité temporelle ambiguë.
- Calculer covariance, variances et moyennes sur les **mêmes paires finies**.
  Conserver la fenêtre de 252 lignes et le minimum de 126 paires observées.
- Avec une couverture insuffisante ou une variance marché non estimable,
  conserver les valeurs par défaut documentées. Le nombre de paires écartées
  est disponible en journal DEBUG ; aucun nouvel indicateur modèle n'est ajouté.
- Borner seulement R² à [0,1] pour les écarts d'arrondi numérique.

Le calcul de `momentum_252_vs_market` conserve la définition historique :
**somme glissante des rendements quotidiens titre moins somme glissante des
rendements benchmark**, sur les mêmes paires. Il ne devient pas implicitement
un rendement composé sur 252 séances. Le nom ne doit pas être interprété comme
une nouvelle définition de momentum cumulé.

Les OLS sont vectorisés par fenêtres pandas, sans changer la convention ddof=0.
Les DataFrames d'entrée ne sont pas modifiés.

## 2. Ratios : neutraliser l'indéfinissable, pas diviser par epsilon

L'ancien mécanisme `denominator.clip(lower=1e-8)` rendait les résultats finis,
mais pouvait produire des ratios de plusieurs milliards sur des séries plates.

Le helper `_positive_denominator_ratio` conserve le ratio exact uniquement si
numérateur et dénominateur sont finis et si le dénominateur est **strictement
supérieur à 1e−8**. Sinon il retourne **0**, valeur neutre explicite.

Le seuil est une frontière numérique fixée indépendamment des performances ;
il n'est ni appris ni choisi sur les pertes. **Aucun plafond de valeur de sortie**
n'est ajouté : un ratio élevé avec un dénominateur admissible reste élevé.
La neutralisation empêche les cas indéfinis identifiés, pas tous les extrêmes
possibles. Par exemple 100 / 1e−6 reste 100 millions.

Six interactions sont concernées :

1. `momentum_20_div_vol_20` ;
2. `momentum_60_div_vol_60` ;
3. `rsi_14_div_volatility_20` ;
4. `intraday_range_div_atr_14` ;
5. `log_return_div_intraday_range` ;
6. `relative_strength_60_div_market_volatility`.

La liste et l'ordre des features ne changent pas. Le zéro peut désormais
signifier ratio non estimable ; il ne faut pas l'interpréter comme preuve d'une
absence de mouvement. Aucun indicateur de qualité additionnel n'est ajouté
afin de ne pas étendre silencieusement le contrat des modèles existants.

Les ratios signés de dynamique temporelle, les z-scores et les autres formules
restent inchangés. Ce correctif ne prétend pas normaliser toutes les échelles
EXPERT ou certifier toutes les séries OTC. Aucune nouvelle exclusion de titre.

## 3. Compatibilité des modèles

La version numérique est
`2026-10-07-capm-safe-ratios-v2`. Elle entre dans `features.fingerprint` lorsque
EXPERT ou les facteurs sont actifs. Le fingerprint V1 sans facteurs ne change
pas au titre de ce correctif.

**Les anciennes colonnes identiques ne signifient pas anciennes valeurs
identiques.** Les modèles existants ne sont pas réentraînés ni transformés.
Les chemins qui contrôlent ce fingerprint peuvent signaler une incompatibilité.
Cette version n'ajoute pas à elle seule un blocage universel à tous les chemins
de serving Oracle ; ne pas supposer que tous refuseront automatiquement un
ancien modèle.

Avant production ou comparaison de performances corrigées : valider le nouvel
audit, réentraîner les modèles affectés, puis régénérer leurs prédictions. Une
simple nouvelle prédiction d'un ancien modèle ne corrige pas son entraînement.
L'impact dépasse Oracle : tout appel partagé avec EXPERT/facteurs reçoit ces
calculs, notamment les familles Per-Symbol/Ranking lorsqu'elles les activent.
Les anciens résultats d'expériences restent des résultats de l'ancien contrat.

## 4. Tests et contrôle sur données réelles

**224 tests ciblés passent**, couvrant les facteurs, features, profils Oracle,
rangs transversaux, contrats FR/CN et scripts d'audit. Un avertissement existant
de fallback `market_code` US reste présent dans un test ; il n'est pas un échec.

Nouveaux cas : benchmark NULL ou obsolète, splits, beta/alpha connus, index
non standard, dates manquantes et trous de prix, couverture insuffisante,
dates dupliquées, stabilité des résultats passés lorsque des prix futurs sont
modifiés, neutralisation des dénominateurs non admissibles, préservation des
ratios ordinaires et changement du fingerprint affecté.

Smoke sur 25 titres et 52 098 lignes : aucune perte supplémentaire de lignes ;
beta observé de −0,1336 à 2,7579, alpha de −2,3537 à 4,6432 et R² non constant.
Ce smoke provient du premier passage corrigé ; le dernier cas limite sur les
trous benchmark a ensuite été ajouté et testé avant le passage final v2.

### Audit complet avant/après

Le rapport initial reste conservé dans :
`artifacts/research/us_concentrated_replay/oracle-h20-dataset-audit-20261007-v1/`.

Le premier audit corrigé a été arrêté volontairement et marqué
`STOPPED_SUPERSEDED_BY_CORRECTED_V2` pour intégrer le dernier cas limite.
Seul ce processus de recherche créé pour le correctif a été arrêté.

L'audit final corrigé est **terminé** (`COMPLETED_READ_ONLY_AUDIT`) dans :
`artifacts/research/us_concentrated_replay/oracle-h20-dataset-audit-corrected-20261007-v2/`.
Même univers, même horizon H20 et même période 2016–2024. Il compare les données
produites, pas les scores d'un ancien modèle et encore moins sa performance.

Le protocole de reprise inclut désormais les empreintes des modules de features,
des facteurs et du registre de continuité, ainsi que la version numérique.
Ne pas reprendre le rapport initial avec le code corrigé : utiliser une nouvelle
racine pour ne pas mélanger deux contrats de calcul.

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-dataset-audit-corrected-20261007-v2\progress.json
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-dataset-audit-corrected-20261007-v2\stderr.log -Tail 20 -Wait
Test-Path F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-dataset-audit-corrected-20261007-v2\report.json
```

Les neuf années 2016–2024 sont consolidées. Aucune feature émise non finie,
aucun symbole entièrement perdu ; tous les contrôles de labels valides restent
à zéro violation, sur l'univers original comme sur le sous-ensemble conservé.
Les 1 759 labels invalides restent identifiés et exclus de l'apprentissage :
1 679 sorties sans barre et 80 sauts non ajustés invalidés. Ils ne sont pas
réparés artificiellement. Le probe SPY contre lui-même produit désormais
beta=1, alpha=0, R²=1 et momentum relatif=0, malgré les rendements persistés NULL.

### Comparaison complète des lignes de features déjà terminée

Le contrôle hors SQL de tous les 72 Parquet avant/après est terminé :

| Mesure | Avant | Après correction v2 |
|---|---:|---:|
| Lignes émises | 3 787 770 | 3 787 770 |
| Lots dont les clés `(date, symbol)` changent | — | 0 |
| RSI/volatilité de valeur absolue > 1 million | 870 | 0 |
| Log-return/range de valeur absolue > 1 million | 50 058 | 0 |
| Ratio RSI non neutre avec volatilité ≤ 1e−8 | — | 0 |
| Ratio log-return non neutre avec range ≤ 1e−8 | — | 0 |

Ces chiffres proviennent de `feature_comparison.json`, produit par
`scripts/research/us_oracle_numeric_correction_comparison.py`. Les dénominateurs
admissibles n'ont pas été plafonnés : la disparition des valeurs supérieures
au million est un **résultat observé** sur ce dataset, pas une borne imposée.

La comparaison des features et la consolidation annuelle des labels sont
terminées. Ce tableau ne démontre pas une amélioration des performances du
modèle. Le GO suivant autorise une [mesure appariée de l'effet H20](oracle_h20_numeric_effect.md),
lancée en recherche uniquement ; aucun ancien modèle de serving n'est remplacé.
