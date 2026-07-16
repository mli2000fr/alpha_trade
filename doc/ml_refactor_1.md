# ML Refactor 1 - Plan concret d'amelioration de l'entrainement

## 1. Pourquoi ce travail est necessaire

La campagne du 2026-07-12 a entraine 2067 symboles. Les moyennes par symbole sont :

| Split | F1 macro | F1 short | F1 flat | F1 long |
| --- | ---: | ---: | ---: | ---: |
| `test` | 0.285 | 0.227 | 0.316 | 0.300 |
| `val` | 0.290 | 0.231 | 0.309 | 0.317 |
| `wf` | 0.216 | 0.099 | 0.373 | 0.177 |

Le modele apprend quelque chose sur `val` et `test`, mais sa performance se degrade
sur les periodes futures. La degradation est surtout visible sur les decisions `short`.
L'objectif n'est pas simplement d'augmenter le F1 de validation : il faut augmenter la
qualite `walk-forward` sans fuite temporelle et sans reduire le systeme a une prediction
quasi permanente de `flat`.

## 2. Regles avant toute modification

1. Ne modifier qu'un facteur principal par campagne. Ne pas changer simultanement les
   labels, les features et l'architecture.
2. Conserver les memes dates et le meme univers de symboles pour comparer deux campagnes.
3. Ne jamais choisir un parametre a partir de `test`. Les choix se font sur `train` et
   `val`; `test` et `wf` servent a mesurer la generalisation.
4. Donner un `batch_id` a chaque campagne. Il permet de comparer deux executions sans
   fenetre temporelle arbitraire.
5. Conserver le modele actuellement servi tant qu'une nouvelle campagne ne passe pas les
   criteres de promotion definis dans ce document.

### Isolation des campagnes et serving

Les artefacts d'une campagne sont isoles sous `artifacts/models/<batch_id>/`.
Le chemin configure reste la racine `artifacts/models`, jamais le sous-dossier
d'une campagne. La prediction et le backtesting `rebuild-missing` doivent
selectionner explicitement un `batch_id` termine.

Une campagne ne devient pas servie automatiquement : dans la page ML, promouvoir
une campagne terminee comme campagne de serving. Risk ne consomme alors que les
predictions dont les runs appartiennent a ce batch. Sans campagne promue, le
comportement historique reste actif temporairement; il doit etre traite comme un
etat de migration, pas comme une politique de production.

ML Train ne propose qu'un unique comportement : `rebuild-all`. Chaque lancement
cree une campagne complete et isolee; une mise a jour incrementale d'une campagne
precedente n'est pas supportee. Le `rebuild-missing` du backtesting reste un
comportement distinct, limite a la reconstruction de predictions historiques a
partir d'un batch explicitement choisi.

## 3. Etape zero - Etablir le diagnostic de reference

### 3.1 Executer une campagne de reference

Avant un refactor, executer une nouvelle campagne avec la configuration actuelle et noter
son `batch_id`. Cette campagne sert de point de comparaison reproductible.

Apres execution, analyser toutes les lignes de la campagne :

```sql
SELECT
    mm.split_name,
    COUNT(DISTINCT mm.symbol) AS nb_symbols,
    ROUND(AVG(mm.f1_macro), 3) AS avg_f1_macro,
    ROUND(AVG(mm.f1_short), 3) AS avg_f1_short,
    ROUND(AVG(mm.f1_flat), 3) AS avg_f1_flat,
    ROUND(AVG(mm.f1_long), 3) AS avg_f1_long
FROM alpha_trade.model_metrics AS mm
JOIN alpha_trade.model_training_run AS mtr
    ON mtr.run_id = mm.run_id
WHERE mtr.batch_id = :batch_id
  AND mtr.status = 'completed'
GROUP BY mm.split_name
ORDER BY FIELD(mm.split_name, 'train', 'val', 'test', 'wf');
```

Remplacer `:batch_id` par l'identifiant de la campagne. Exemple :
`model-factory-20260715123000-ab12cd`.

### 3.2 Mesurer la stabilite entre symboles

Une moyenne peut cacher quelques tres bons symboles et beaucoup de mauvais. Identifier la
distribution des performances walk-forward :

```sql
SELECT
    CASE
        WHEN mm.f1_macro < 0.10 THEN '0.00-0.09'
        WHEN mm.f1_macro < 0.20 THEN '0.10-0.19'
        WHEN mm.f1_macro < 0.30 THEN '0.20-0.29'
        WHEN mm.f1_macro < 0.40 THEN '0.30-0.39'
        ELSE '0.40+'
    END AS wf_f1_macro_bucket,
    COUNT(DISTINCT mm.symbol) AS nb_symbols
FROM alpha_trade.model_metrics AS mm
JOIN alpha_trade.model_training_run AS mtr
    ON mtr.run_id = mm.run_id
WHERE mtr.batch_id = :batch_id
  AND mtr.status = 'completed'
  AND mm.split_name = 'wf'
GROUP BY wf_f1_macro_bucket
ORDER BY wf_f1_macro_bucket;
```

### 3.3 Lire les artefacts de quelques symboles

Prendre au moins :

- 5 symboles avec le meilleur `wf.f1_macro`;
- 5 symboles avec le plus mauvais `wf.f1_macro`;
- 5 symboles dont `wf.f1_short = 0`.

Dans `artifacts/<SYMBOL>/metrics.json`, comparer par fold :

- `true_short_pct`, `true_flat_pct`, `true_long_pct`;
- `pred_short_pct`, `pred_flat_pct`, `pred_long_pct`;
- `f1_short`, `f1_flat`, `f1_long`;
- le nombre de splits walk-forward et leurs dates.

Interpretation :

- Peu de `true_short_pct` : le label est trop rare ou mal defini pour ce symbole.
- `true_short_pct` normal mais `pred_short_pct` proche de zero : le modele evite la
  classe `short`.
- `pred_short_pct` eleve mais `f1_short` faible : les signaux short sont bruyants ou
  les seuils de decision sont trop permissifs.

### 3.4 Diagnostiquer les regimes de marche avant de modifier le modele

La periode d'entrainement 2018-2025 contient des regimes de marche incompatibles :
correction de 2018, crash et rebond de 2020, marche haussier de 2021, bear market de 2022,
puis marche recent concentre sur certains secteurs. Un ecart entre `val`, `test` et `wf`
peut donc etre une vraie mesure de changement de regime, et non un bug du walk-forward.

Ne pas conclure que le modele est bon ou mauvais a partir de la seule moyenne `wf`.
Identifier les dates exactes de chaque fold, puis construire un tableau par periode :

| Periode OOS | Regime | F1 macro | F1 short | F1 long | Taux action | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2020-Q1 | crash | ... | ... | ... | ... | rechercher une protection / abstention |
| 2020-Q2 a Q4 | rebond | ... | ... | ... | ... | evaluer long et short separement |
| 2022 | bear / taux | ... | ... | ... | ... | tester la robustesse short |
| 2023-2024 | bull concentre | ... | ... | ... | ... | verifier le risque de short excessif |
| 2025 | holdout recent | ... | ... | ... | ... | reference de decision actuelle |

Pour chaque fold, conserver dans `metrics.json` :

- les bornes de dates `train`, `val` et `test`;
- `f1_macro`, `f1_short`, `f1_flat`, `f1_long`;
- les distributions vraies et predites des trois classes;
- le taux d'action global, long et short;
- hit-rate, payoff et perte maximale par cote, apres couts;
- rendement de SPY, niveau moyen de VIX et volatilite du fold.

Classification initiale simple des regimes :

- `bear_high_vol` : rendement SPY negatif et VIX au-dessus de son niveau median;
- `bull` : rendement SPY positif hors condition `bear_high_vol`;
- `range_high_vol` : rendement SPY faible et VIX eleve;
- `range_low_vol` : tous les autres cas.

Cette classification doit etre calculee exclusivement a partir des donnees observees dans
le fold OOS. Elle sert a interpreter les resultats et, plus tard, a conditionner la
politique de risque. Elle ne doit pas utiliser les rendements futurs pour choisir une
prediction au sein du fold.

### 3.5 Distinguer train, validation, test et holdout recent

Pour une etude allant de 2018 a 2025, utiliser quatre niveaux distincts :

1. `train` : ajuster les poids du modele.
2. `val` : choisir labels, seuils, calibrage et autres hyperparametres.
3. `walk-forward` : repeter train/val/OOS dans plusieurs periodes historiques pour
     mesurer la robustesse entre regimes.
4. `holdout recent` : reserver la derniere annee complete, par exemple 2025, et ne jamais
     l'utiliser pour choisir les parametres ni le champion.

Le `test` final et le holdout recent doivent etre definis avant de lancer les comparaisons.
Leur resultat est une mesure, pas une source de reglage. Si 2025 est deja inclus dans les
choix de configuration, le renommer `test recent` plutot que `holdout` et reserver une
periode plus recente pour une evaluation vraiment independante.

La question utile n'est pas "le modele gagne-t-il sur toutes les annees ?". Un objectif
plus realiste est de savoir :

- dans quels regimes il conserve une qualite directionnelle exploitable;
- dans quels regimes il doit etre bloque, limite a `flat`, ou associe a une taille de
    position reduite;
- s'il reste suffisamment performant sur le regime recent pour etre servi aujourd'hui.

### 3.6 Verifier puis comparer le contexte de regime deja disponible

Le projet possede deja un contexte de marche utilisable par le modele, mais il n'est pas
active dans la configuration standard. Le jeu de features `v1` est le defaut et ne contient
que les indicateurs derives du titre. Le jeu `expert`, active avec `--feature-set expert`,
ajoute les variables suivantes, calculees a partir de `SPY` :

```text
market_return_20
market_volatility_20
market_trend_strength_50
relative_strength_20
relative_strength_60
regime_bull_market
regime_risk_off
```

Il ne s'agit pas d'entrainer un modele distinct par regime. C'est un unique modele par
symbole, entraine sur tout l'historique, auquel le contexte courant de marche est fourni
a chaque pas de la sequence. Cette solution conserve les episodes rares comme COVID dans
le train global au lieu de tenter d'apprendre un reseau avec seulement un ou deux ans de
donnees de crise.

Avant toute campagne `expert`, effectuer ce controle :

1. Verifier que `stock_bars_daily` contient les barres ajustees de `SPY` sur toute la
    periode d'entrainement et les periodes OOS.
2. Verifier que la valeur de `benchmark_symbol` est bien `SPY` pour les deux campagnes.
3. Executer le test unitaire existant qui controle la creation des colonnes de marche :

```powershell
python -m pytest tests/test_model_factory_features.py -k expert -q
```

4. Lancer une campagne courte sur un echantillon fixe de symboles et lire
    `run_summary.json` ou `config.json`. La liste `feature_columns` doit contenir
    `regime_bull_market` et `regime_risk_off`. Si elles sont absentes, ne pas lancer la
    campagne complete : le contexte n'est pas entre dans le modele.

Ensuite, comparer deux campagnes strictement identiques :

```powershell
# A : reference sans contexte de marche explicite (jeu v1, defaut)
python -m modelFactory --feature-set v1 --training-start-date 2020-01-01 --walkforward

# B : meme configuration, avec les features marche/regime existantes
python -m modelFactory --feature-set expert --benchmark-symbol SPY --training-start-date 2020-01-01 --walkforward
```

Completer chaque commande avec le meme univers, les memes labels, le meme seed, les memes
dates de fin et les memes parametres walk-forward. Ne changer aucun autre flag entre A et
B. Noter les deux `batch_id` et verifier dans leurs artefacts que le nombre de colonnes de
features est different comme attendu.

Comparer ensuite, par regime et non uniquement en moyenne :

- la mediane et le pire `wf.f1_macro`;
- `wf.f1_short` dans `bear_high_vol`;
- `wf.f1_long` dans `bull`;
- le taux d'action long et short par regime;
- le holdout recent, qui reste hors de tout choix de configuration.

Garder `expert` seulement si son gain est stable sur plusieurs folds et n'empire pas un
regime critique. Si `expert` est neutre ou degrade le holdout, garder `v1` : davantage de
features ne constitue pas une amelioration en soi.

La couche `market_regimes` active dans `config.yaml` est distincte. Elle pilote le risque
et l'execution a l'execution; elle ne place pas automatiquement ses informations dans les
tenseurs d'entrainement. Les options macro (`--include-macro-vix`, `--include-macro-vxn`,
`--include-macro-vix3m`, `--include-macro-move`) forment une experience ulterieure : ne
les activer qu'apres avoir decide entre `v1` et `expert`, une famille de features a la fois.

## 4. Priorite 1 - Corriger et comparer les labels

### 4.1 Problematique

Les labels ternaires a horizon fixe sont construits dans
`modelFactory/features.py::build_target`. Avec des seuils `0.0` / `0.0`, presque chaque
variation negative devient `short` et presque chaque variation positive devient `long`.
Le signal est alors tres sensible au bruit quotidien et la classe `flat` est peu utile.

### 4.2 Premiere experience : une zone neutre explicite

Creer une configuration de test avec :

```python
DataConfig(
    target_mode="ternary",
    label_method="fixed_horizon",
    forecast_horizon=10,
    target_up_threshold=0.01,
    target_down_threshold=-0.01,
)
```

Ne modifier aucun autre parametre pour cette campagne. Comparer ensuite avec une seconde
campagne identique utilisant `0.02` et `-0.02`.

Resultat attendu : moins de trades labels, une classe `flat` plus pertinente et des labels
`short` / `long` moins ambigus. Ce n'est pas un succes si le F1 monte uniquement parce que
le modele predit plus souvent `flat`; verifier les trois F1 et le taux d'action.

### 4.3 Deuxieme experience : optimiser la target sur le train

Le projet contient deja `TargetOptimizationConfig` et
`modelFactory/target_optimization.py`. Activer l'optimisation et utiliser une grille
simple au depart :

```python
TargetOptimizationConfig(
    enabled=True,
    candidate_horizons=(5, 10, 15),
    candidate_up_thresholds=(0.01, 0.02, 0.03),
    candidate_down_thresholds=(-0.01, -0.02, -0.03),
    min_trades_fraction=0.10,
)
```

Le code selectionne la target a partir du fold `train`, puis evalue sur `val`, `test` et
`wf`. Ne pas etendre la grille avant d'avoir confirme que cette premiere grille apporte
une amelioration stable sur plusieurs campagnes.

### 4.4 Troisieme experience : comparer le triple barrier

Le triple barrier est disponible dans `modelFactory/labeling.py`. Il genere une classe
`long` ou `short` seulement quand une cible de gain ou une limite de perte est atteinte;
sinon l'observation reste `flat`. Il est donc souvent plus proche de la decision de
trading reelle qu'un rendement fixe a dix jours.

Configuration initiale recommandee :

```python
DataConfig(
    target_mode="ternary",
    label_method="triple_barrier",
    triple_barrier_stop_atr_mult=2.0,
    triple_barrier_tp_atr_mult=3.0,
    triple_barrier_max_sessions=20,
)
```

Puis activer `TargetOptimizationConfig` seulement sur les parametres suivants :

```python
candidate_stop_atr_mults=(1.5, 2.0, 2.5)
candidate_tp_atr_mults=(2.0, 3.0, 4.0)
candidate_max_sessions=(10, 20)
```

Ne pas lancer une grille plus grande lors du premier essai : elle multiplierait fortement
le temps de calcul sur 2067 symboles.

### 4.5 Critere de choix des labels

Choisir une variante seulement si, par rapport a la reference :

- `wf.f1_macro` augmente d'au moins `0.02`;
- `wf.f1_short` et `wf.f1_long` ne regressent pas;
- la degradation `val - wf` diminue;
- le nombre de symboles avec un F1 directionnel nul diminue;
- le taux de prediction non-flat reste utile pour la strategie.

## 5. Priorite 2 - Optimiser la decision ternaire

### 5.1 Problematique

`modelFactory/trainer.py::_evaluate_best_checkpoint` optimise actuellement le
`decision_threshold` seulement lorsque le modele est binaire. En mode ternaire, les
probabilites passent dans `decide_ternary_side_batch` avec une politique fixe. La
temperature peut etre calibree, mais la frontiere entre `short`, `flat` et `long` n'est
pas optimisee sur `val`.

### 5.2 Modification a implementer

Ajouter une configuration explicite, par exemple :

```python
@dataclass(frozen=True, slots=True)
class TernaryDecisionConfig:
    enabled: bool = False
    candidate_short_thresholds: tuple[float, ...] = (0.45, 0.50, 0.55, 0.60)
    candidate_long_thresholds: tuple[float, ...] = (0.45, 0.50, 0.55, 0.60)
    candidate_margin_thresholds: tuple[float, ...] = (0.00, 0.05, 0.10, 0.15)
    min_action_rate: float = 0.03
    max_action_rate: float = 0.35
    min_short_precision: float = 0.50
    min_long_precision: float = 0.52
```

Creer ensuite dans `modelFactory/evaluation.py` une fonction
`optimize_ternary_decision(...)` qui :

1. Recoit les probabilites calibrees et les labels de validation.
2. Teste chaque combinaison `short_threshold`, `long_threshold`, `margin_threshold`.
3. Predira `short` si `P(short)` est assez haute et depasse la seconde probabilite par la
   marge imposee.
4. Predira `long` avec la regle symetrique.
5. Predira `flat` dans tous les autres cas.
6. Rejette les combinaisons sans assez de trades ou avec une precision directionnelle trop
   faible.
7. Selectionne la meilleure combinaison selon une metrique explicite, par exemple
   `0.5 * f1_macro + 0.25 * f1_short + 0.25 * f1_long`, puis conserve tous les candidats
   et leurs contraintes dans les artefacts.

Dans `trainer.py`, appeler cette fonction apres la calibration sur `val`, puis reutiliser
la politique selectionnee sans changement sur `test` et sur chaque evaluation future.

### 5.3 Tests indispensables

Ajouter des tests unitaires pour :

- une probabilite `short` elevee qui produit bien `short`;
- une probabilite `long` elevee qui produit bien `long`;
- une probabilite ambigue qui produit `flat`;
- une combinaison rejetee quand son taux d'action est trop bas;
- l'absence d'acces a `test` dans l'optimiseur.

## 6. Priorite 3 - Remplacer les poids de classes fixes

### 6.1 Problematique

Dans `modelFactory/model.py`, la loss ternaire utilise actuellement :

```python
[1.5, 1.0, 1.5]  # short, flat, long
```

Ces valeurs sont identiques pour chaque symbole et chaque periode. Elles peuvent etre
inadequates si un fold contient tres peu de `short` ou, au contraire, beaucoup de `flat`.

### 6.2 Modification a implementer

Calculer les poids seulement a partir des labels du dataset train :

```python
raw_weight_c = n_train / (3 * n_train_class_c)
weight_c = clip(raw_weight_c, 0.5, 3.0)
weight_c = weight_c / mean(weight_c)
```

Etapes de code :

1. Dans le `DataModule`, compter les classes du seul fold train apres la creation des
   sequences.
2. Passer ces poids au constructeur de `LSTMAttentionModule`.
3. Remplacer la constante interne par le tenseur recu en parametre.
4. Ecrire les comptes et les poids selectionnes dans `config.json` et `metrics.json`.
5. Conserver un parametre de configuration permettant de revenir aux poids fixes pendant
   la comparaison.

Le plafonnement a `3.0` est important : sans lui, une classe extremement rare peut faire
apprendre au modele a surpredire des signaux peu fiables.

### 6.3 Critere de succes

Accepter cette modification seulement si elle augmente le rappel et le F1 `short` sans
faire s'effondrer la precision `short` ni le `F1_flat`.

## 7. Priorite 4 - Renforcer le walk-forward

### 7.1 Configuration de diagnostic

La configuration actuelle utilise typiquement :

```python
WalkForwardConfig(
    enabled=True,
    min_train_size=504,
    val_size=126,
    test_size=126,
    step_size=126,
    max_splits=3,
)
```

Pour comprendre la stabilite dans le temps, lancer une campagne d'evaluation avec :

```python
WalkForwardConfig(
    enabled=True,
    min_train_size=504,
    val_size=126,
    test_size=126,
    step_size=126,
    max_splits=11,
)
```

Cette etape ne vise pas encore a monter le score. Elle permet de voir si les performances
faibles sont concentrees dans certains regimes de marche. Les tests OOS ne se chevauchent
pas et les onze folds couvrent approximativement des semestres consecutifs de 2020 a 2025
pour un historique complet debutant en 2018.

Utiliser une fenetre d'entrainement expanding pour l'evaluation historique : chaque nouveau
fold ajoute le passe disponible au train et mesure la periode suivante hors echantillon.
Ne pas melanger les lignes d'un regime futur dans le train d'un fold plus ancien.

### 7.1.1 Comparer la longueur de l'historique d'entrainement

Un historique complet apporte des crises rares, mais peut diluer le regime actuel. Ne pas
choisir intuitivement entre ces deux options : executer les trois campagnes suivantes avec
les memes labels, hyperparametres, splits OOS et univers :

| Variante | Debut des donnees | Question posee |
| --- | --- | --- |
| longue | 2018 | Le modele apprend-il une robustesse utile aux crises ? |
| intermediaire | 2020 | Le modele garde-t-il le crash/rebond sans les regimes plus anciens ? |
| recente | 2022 | Le modele s'adapte-t-il mieux au regime actuel ? |

Comparer ces variantes sur la mediane des folds walk-forward, le pire fold, les regimes
`bear_high_vol` et la periode holdout recente. Ne pas choisir la variante qui maximise
seulement `val` ou la moyenne globale.

### 7.2 Rapport a produire par fold

Pour chaque fold, sauvegarder et comparer :

- les dates de debut et de fin de train, val et test;
- `f1_macro`, `f1_short`, `f1_flat`, `f1_long`;
- la distribution reelle et predite des classes;
- le taux d'action long et short;
- les retours directionnels, le hit-rate et le payoff apres couts;
- la volatilite et le rendement de SPY pendant le fold.

Un mauvais score concentre pendant les regimes de hausse forte peut expliquer une faiblesse
short. Dans ce cas, il faut ajouter des features de regime ou reduire l'exposition short
dans ce regime, pas forcer une hausse artificielle de son F1.

### 7.3 Criteres d'evaluation d'un modele entraine

Un candidat ne doit pas etre juge par un unique score moyen. Produire au minimum :

```text
median_wf_f1_macro
worst_wf_f1_macro
wf_f1_macro_par_regime
wf_f1_short_par_regime
wf_f1_long_par_regime
holdout_recent_f1_macro
holdout_recent_f1_short
holdout_recent_f1_long
action_rate_par_regime
```

Points de depart pour une gate de promotion :

```text
median_wf_f1_macro >= 0.25
holdout_recent_f1_macro >= 0.25
wf_f1_short en bear_high_vol >= 0.15
wf_f1_long en bull >= 0.20
action_rate entre 0.03 et 0.35
au moins 4 folds walk-forward exploitables
aucun fold critique faible sans une politique d'abstention explicite
```

Ces seuils sont des hypotheses initiales. Les reviser apres deux ou trois campagnes
strictement comparables, en tenant compte du rendement net et du risque reel de la
strategie. Une bonne moyenne ne compense pas un fold de crise qui produit des signaux
directionnels dangereux.

## 8. Priorite 5 - Comparer les modeles et changer la promotion

### 8.1 Lancer des challengers

Le CLI expose deja des options pour LightGBM, CatBoost et le modele global. Pour chaque
campagne de labels retenue, activer les challengers afin de comparer les modeles avec les
memes splits et les memes features.

Le modele global est particulierement interessant pour 2067 symboles : il peut apprendre
un contexte transversal qui manque a un modele LSTM entraine symbole par symbole.

### 8.2 Ne pas promouvoir sur la seule validation

La selection du champion est geree par `modelFactory/champion_selection.py`. La metrique de
selection autorise `val` et `walk_forward_oos`, mais la logique actuelle peut retourner la
premiere valeur disponible de validation. Avec l'ecart observe, modifier cette logique pour
preferer une metrique walk-forward quand elle existe.

Ajout recommande : une gate explicite avant promotion :

```text
wf_f1_macro >= 0.25
wf_f1_short >= 0.15
wf_f1_long >= 0.20
wf_action_rate >= 0.03
nombre_minimal_de_splits >= 4
```

Ces valeurs sont des points de depart, pas des verites universelles. Elles devront etre
ajustees apres deux ou trois campagnes comparables. Si la gate echoue, garder le champion
actuel et enregistrer la raison de rejet.

## 9. Ordre exact des campagnes

| Campagne | Seul changement majeur | Decision apres la campagne |
| --- | --- | --- |
| A | Reference actuelle, avec `batch_id` | Etablir la base de comparaison |
| B | `v1` contre `expert`, toutes choses egales | Garder seulement si le gain est stable par regime |
| C | Labels ternaires fixes a `+/-1%` | Garder seulement si WF progresse |
| D | Labels ternaires fixes a `+/-2%` | Comparer C, D et A |
| E | Triple barrier avec grille compacte | Retenir la meilleure famille de labels |
| F | Decision ternaire optimisee sur val | Verifier F1 short/long et taux d'action |
| G | Poids de classes dynamiques | Garder seulement si precision et WF restent stables |
| H | LightGBM, CatBoost et modele global | Promouvoir uniquement avec les gates WF |
| I | Comparaison des fenetres 2018, 2020 et 2022 | Retenir le meilleur compromis robustesse/regime recent |

Ne pas passer a la campagne suivante si les artefacts, le `batch_id` ou les metriques par
split ne sont pas disponibles. Une campagne non comparable ne fournit pas de signal utile.

## 10. Definition de fin du refactor 1

Le refactor est considere termine quand :

1. Chaque campagne est requetable avec un `batch_id`.
2. Les distributions de labels et predictions sont disponibles pour `val`, `test` et `wf`.
3. Les seuils ternaires sont selectionnes sur validation seulement.
4. Les poids de classes sont calcules sur train seulement ou les poids fixes sont justifies
   par les donnees observees.
5. Le champion est bloque quand ses criteres walk-forward ne sont pas satisfaits.
6. Une campagne candidate bat la reference sur le walk-forward de maniere stable, pas
   seulement sur la validation.
7. La decision de promotion est justifiee par les resultats par regime et par le holdout
    recent, pas par une moyenne agregee seule.