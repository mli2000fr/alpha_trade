# Plan d'action ML 1 - Recuperer le signal Global Ranking et per-sector

**Date :** 2026-08-04  
**Contexte analyse :** batch `f82ab5`, documentation de resultat, code de `trainer_sector.py`, `global_ranking.py`, `dataset.py`, `features.py`, `tabular_baseline.py` et `orchestrator.py`.  
**Objectif :** etablir si la baisse Global Ranking et l'effondrement per-sector sont des regressions de donnees/contrat, de cible, ou un vrai manque d'alpha. Ne pas ajouter des modeles au hasard avant d'avoir un baseline comparable et des metriques economiques correctes.

## 1. Diagnostic de depart

### 1.0 Decision de recherche : suspendre le per-sector comme signal de trading (2026-08-05)

La campagne controlee comporte huit batchs sur le meme probleme per-sector, dont une baseline sans familles optionnelles (`S0`), les corrections de contrat XS/fondamentales, H20 seul, trois formulations de cible et le score short. Elle donne un resultat coherent : **aucun alpha per-sector tradable n'est demontre par les configurations et le dataset testes**.

| Experience | Hypothese testee | Resultat WF H20 | Lecture |
|---|---|---:|---|
| `S0` `799d9e` | Baseline sans flag optionnel | F1 0.330, DA 50.0 %, MSE 1.01 | Niveau nul. |
| `S0+short` `57461f` | Score short incremental | F1 0.330, DA 50.0 %, MSE 1.01 | Aucun effet mesure. |
| `d21cb1` | XS/fondamentales effectivement presentes | F1 0.325, DA 49.8 %, MSE 1.09 | Le correctif de contrat est valide, sans gain economique. |
| `T0` `a3aaa3` | H20 seul, cible continue actuelle | F1 0.330, DA 50.0 %, MSE 1.01 | Multi-horizon non responsable. |
| `T1` `1b2059` | Cible sans vol scaling | F1 0.330, DA 50.0 %, MSE 1.24 | Degradation nette de l'erreur. |
| `T2` `054378` | Rang percentile intra-secteur | F1 0.330, DA 49.9 %, MSE 1.07 | Pas de signal de ranking exploitable. |
| `T3` `5b6760` | Classes intra-secteur long/flat/short | F1 0.331, DA 39.3 %, MSE 0.23 | Surapprentissage temporel severe. |

`T3` ne constitue pas une exception positive : CatBoost et LightGBM affichent environ `69.3 %` de directional accuracy en validation, `71.3 %` en test interne, puis respectivement `39.6 %` et `39.0 %` en walk-forward. Le gain apparent vient donc d'un protocole de selection/calibration qui ne se generalise pas aux six periodes OOS, et non d'un signal utilisable.

**Decision operationnelle :** le per-sector passe en statut **research-only**. Il ne doit ni etre champion de production, ni entrer dans la cascade, ni servir de veto ou de ponderation du capital. Les artefacts et rapports sont conserves pour audit, mais aucune nouvelle campagne de tuning, de flags ou d'hyperparametres n'est justifiee.

**Regle de re-entree :** ne le reconsiderer que pour une hypothese materiallement nouvelle, avec une information nouvelle et PIT (revisions de resultats/estimations, flux ETF sectoriels, evenements sectoriels), ou un objectif de portefeuille relatif entierement redesigne. Une promotion requerra avant tout tuning une preregistration, un IC relatif positif par date, un spread long-short net de couts stable sur la majorite des folds et une confirmation sur holdout gele.

La priorite experimentale est maintenant le **Global Ranking**. Son IC positif historique ne suffit pas encore a une promotion automatique, mais justifie un baseline fige et reproductible : manifeste de run, univers PIT par fold, nombre reel de splits explique, IC par date avec intervalle de confiance, spread decile net, turnover et capacite. Le per-sector ne doit pas etre une condition de confirmation de ce signal global.

### 1.0 Comparaison per-sector : `f82ab5` versus `d21cb1` (2026-08-05)

Le batch `d21cb1` est le premier rerun apres les corrections de merge XS/fondamentales. Il est bien termine (`11/11` secteurs, stacking desactive), avec six splits WF OOS de 2019-07 a 2025-03. Il active simultanement cross-sectionnelles, fondamentales, facteurs, macro-regime, MOVE et short score.

| Horizon | F1 macro f82ab5 | F1 macro d21cb1 | Delta | Dir. acc. f82ab5 | Dir. acc. d21cb1 | Delta |
|---|---:|---:|---:|---:|---:|---:|
| H3 | 0.330 | 0.328 | -0.002 | 0.5033 | 0.5007 | -0.0026 |
| H5 | 0.331 | 0.326 | -0.005 | 0.5019 | 0.5003 | -0.0016 |
| H10 | 0.332 | 0.329 | -0.003 | 0.5038 | 0.5037 | -0.0001 |
| H15 | 0.332 | 0.326 | -0.006 | 0.5041 | 0.4994 | -0.0047 |
| H20 | 0.331 | 0.325 | -0.006 | 0.5019 | 0.4979 | -0.0040 |

`d21cb1` est donc legerement moins bon sur tous les horizons, sans changement qualitativement positif : F1 macro reste voisin de `0.33`, directional accuracy de `0.50`, et F1 flat est nul. Le MSE WF de `d21cb1` est `1.089` CatBoost et `1.118` LightGBM, toujours au voisinage ou au-dessus du modele nul standardise.

La dispersion sectorielle existe mais n'est pas suffisamment robuste pour une promotion : meilleur point Utilities/CatBoost (`dir_acc=0.5346`) mais MSE `1.3431`, et plusieurs secteurs/backend sont sous `0.48` de directional accuracy. Par regime, les F1 WF vont de `0.305` a `0.345`, sans relation convaincante avec bull/range/high-vol. Ce n'est pas une preuve d'alpha sectoriel exploitable.

**Interpretation correcte :** les corrections XS/fondamentales ont retire un bug de contrat reel, mais elles n'ont pas automatiquement cree du signal sur ce rerun. Il serait incorrect de les annuler : le nouveau batch active plusieurs sources a la fois (`short_score`, MOVE, fondamentales, facteurs, macro-regime, XS) et le rapport precedent ne fournit pas la commande complete de `f82ab5`. La comparaison ne constitue donc pas une ablation causalement propre.

**Decision historique remplacee par la campagne S0/T0-T3 :** les ablations prevues ont maintenant ete testees a un niveau suffisant pour interrompre la recherche incrementaliste. Ne pas lancer de tuning hyperparametrique, de nouvelles combinaisons de flags, ni promouvoir le per-sector.

### 1.1 Global Ranking : signal faible mais pas nul

Le batch `f82ab5` donne un IC moyen global de `0.0115`, contre `0.0190` sur le batch de reference `7e4cf8`. C'est une chute importante, mais pas une absence de signal :

| Horizon | IC moyen f82ab5 | IC IR f82ab5 | Lecture |
|---|---:|---:|---|
| H3 | 0.0091 | 0.69 | Faible et instable. |
| H5 | 0.0139 | 0.85 | Meilleure moyenne ponctuelle, stabilite insuffisante. |
| H10 | 0.0128 | 1.15 | Faible mais relativement stable. |
| H15 | 0.0117 | 1.43 | Meilleur compromis de stabilite du batch. |
| H20 | 0.0102 | 1.47 | Stabilite correcte, moyenne faible. |

Ne pas conclure que H15 est automatiquement le nouvel horizon principal, ni que H20 doit etre abandonne. H15 a le meilleur IR dans **ce** batch, H5 la meilleure moyenne, tandis que le backtest documentaire prefere H20. Les comparer exige le meme univers, les memes folds, les memes couts et une periode holdout gelee.

### 1.2 Per-sector : signal probablement reellement absent sur ce batch

Les metriques per-sector sont environ : `directional_accuracy = 0.50`, `F1 macro = 0.33`, `MSE ~= 1.0` sur tous les horizons et secteurs.

La lecture est importante : en regression signee sans classe flat effectivement predite, `F1 macro ~= 0.33` correspond a deux classes aleatoires et une F1 flat nulle. Avec `directional_accuracy ~= 0.50`, ce n'est pas un modele directionnel exploitable.

L'hypothese de Gemini selon laquelle le rapport comparerait la prediction sector-neutre au rendement absolu est **ecartee par le code actuel** :

* `_compute_regression_metrics` compare `sign(prediction)` a `sign(target)` ;
* pour le per-sector, `target` est neutralisee par la mediane sectorielle de la meme date ;
* l'IC est volontairement calcule sur `future_return` brut, pour conserver une lecture economique distincte.

Le resultat faible est donc une alerte de signal ou de dataset, pas un simple artefact de metrique.

### 1.3 Deux defects de contrat doivent etre traites avant toute conclusion economique

#### A. Features cross-sectionnelles non fusionnees dans le per-sector

`run_per_sector_batch` charge un `universe_df`, puis `_prepare_sector_data` prepare chaque symbole avec `universe_df=None`. Le commentaire indique une fusion apres concatenation, mais elle n'est pas implementée. Si `enable_cross_sectional_features=True`, `get_feature_columns` demande donc les familles XS/sectorielles/global-rank alors que le per-sector ne recupere pas le cache de l'univers entier. La fonction de merge sait explicitement remplir ces colonnes avec des valeurs neutres : `0.5` pour les rangs et `0.0` pour d'autres features.

**Impact probable :** une partie du schema peut etre neutre, constante ou absente du signal de ranking intra-secteur. Ce n'est pas une fuite, mais cela peut degrader directement la performance ou rendre un A/B trompeur.

#### B. Fondamentales calculees mais exclues de la liste de features sectorielle

`prepare_symbol_frame` peut merger les fondamentales lorsque le flag est actif. Pourtant `_prepare_sector_data` appelle `get_feature_columns(... include_factors=..., include_macro_regime=...)` sans transmettre `include_fundamentals=cfg.data.include_fundamentals_features`.

**Impact probable :** les fondamentales peuvent etre chargees et calculees sans etre donnees aux estimateurs per-sector. Il faut verifier le schema artefact du batch avant d'affirmer qu'elles ont participe. Les tableaux documentaires sont egalement contradictoires : une section indique que le per-sector n'a pas de fondamentales, une autre suggere des tests avec elles.

**Conclusion :** ne pas attribuer l'echec per-sector a l'absence de pouvoir predictif des fondamentales ou des facteurs avant d'avoir trace les colonnes reellement entrainees.

## 2. Principes de travail

1. **Un changement par experience.** Ne pas activer screener, VIX, VXN, VIX3M, cross-sectional et modifier la cible dans le meme batch.
2. **Baseline immuable.** Toute experience part du meme code hash, univers, dates, calendar de sessions, folds, seed, couts et artefact de features.
3. **Pas de selection sur le holdout.** Choisir les options sur les folds WF/validation, garder une periode finale gelee pour confirmer une seule configuration.
4. **PIT par construction.** Les scores screener, fondamentales et macro doivent avoir une date de disponibilite `<= date de decision`, pas uniquement une date de valeur economique.
5. **La metrique suit la decision.** Un modele sector-neutre doit etre juge sur ranking intra-secteur et PnL long-short neutralise, pas seulement sur direction absolue.
6. **Stop conditions explicites.** Une idee sans gain hors-echantillon ou sans cohérence par regimes est abandonnee, meme si un secteur isole s'ameliore.

## 3. Phase 0 - Gel du baseline et reproductibilite (P0)

### Action 0.1 - Creer un manifest de comparaison

Pour `f82ab5`, `7e4cf8` et tous les nouveaux runs, persister dans `metadata_json` ou un artefact versionne :

* git SHA et versions Python/LightGBM/CatBoost ;
* configuration resolue complete ;
* dates reelles de chaque fold, nombre de jours et nombre de symboles apres filtres ;
* hash/liste de l'univers par fold ;
* nombre de lignes et colonnes effectivement passees a chaque estimateur ;
* fingerprint de features, valeurs par defaut et taux de valeurs neutres ;
* quantiles/moyenne/ecart-type de target par horizon et par split ;
* seed par horizon/split.

**Pourquoi :** `f82ab5` a 6 splits et 939 symboles, alors que la reference a 8 splits et 928 symboles. Sans manifest, la difference d'IC ne peut pas etre attribuee a une seule modification.

**Acceptation :** deux runs du meme manifest donnent le meme nombre de folds, les memes schemas et des resultats identiques a la tolerance numerique definie.

### Action 0.2 - Rejouer un baseline sain, pas les 16 A/B en bloc

Rejouer d'abord trois baselines sur le code actuel, sans changer de features :

| ID | Mode | Configuration | Question |
|---|---|---|---|
| G0 | Global | configuration de reference `7e4cf8`, meme univers/folds si disponible | Le niveau `~0.019` est-il reproductible apres les 25 fixes ? |
| G1 | Global | configuration exacte `f82ab5` | Le resultat `0.0115` est-il reproductible ? |
| S0 | Per-sector | flags du batch `f82ab5`, mais avec schema de features trace | Le mauvais signal est-il stable et sur quelles families de features ? |

**Pourquoi :** les anciens A/B ont ete conduits avant plusieurs corrections de leakage, de split, de target, de categories et d'univers. Ils sont utiles comme hypotheses, pas comme verdicts definitifs. Relancer les 16 simultanement ferait exploser le risque de multiple testing et masquerait l'origine d'une regression.

**Decision :** si G0 et G1 convergent, l'ecart historique est probablement du au protocole/univers precedent. S'ils divergent fortement a seed et manifest egaux, investiguer data version, disponibilite fundamentals/macro, et code path avant toute optimisation.

## 4. Phase 1 - Corriger et auditer le dataset per-sector (P0)

### Etat au 2026-08-04 - Actions 1.1 et 1.2 corrigees et validees au niveau preparation

La lecture du code confirme les deux changements de structure :

* `run_per_sector_batch` construit une fois `cross_sectional_cache` avec `build_cross_sectional_features_from_db`, sur l'univers complet et le cutoff de training ; il le transmet a chaque `_train_sector_models`, puis a `_prepare_sector_data`.
* `_prepare_sector_data` concatene d'abord les frames preparees symbole par symbole, puis appelle `merge_cross_sectional_features(prepared, cross_sectional_df)` avant la neutralisation de target et le split par dates. L'isolation rolling/forward par symbole reste donc intacte.
* `get_feature_columns` recoit maintenant `include_fundamentals=cfg.data.include_fundamentals_features`. Les fondamentales demandees rejoignent donc le feature contract et peuvent etre donnees aux estimateurs.

Une regression silencieuse supplementaire a ete identifiee puis corrigee dans `merge_cross_sectional_features` : les frames individuelles per-sector recevaient d'abord les defaults XS lors de `prepare_symbol_frame` (cache absent), puis `_prepare_sector_data` tentait de merger le cache reel. Sans suppression prealable des colonnes XS existantes, `pandas.merge` creait des suffixes `_x/_y`; les features consommees par le contrat restaient les defaults et les valeurs reelles pouvaient etre ignorees.

Le helper supprime maintenant les colonnes XS deja presentes avant le merge, puis ajoute les valeurs du cache reel. C'est un correctif qui peut affecter directement la performance per-sector : les rangs cross-sectionnels n'etaient pas seulement non observes, ils pouvaient etre effectivement neutralises dans la matrice d'entrainement.

Les validations executees dans le venv du projet sont vertes : **`36 passed in 4.82s`** pour le test d'integration per-sector, les tests cross-sectionnels et les tests stacking concernes. Aucun diagnostic statique n'est remonte dans `cross_sectional.py`, `trainer_sector.py` et les tests modifies.

Les deux tests unitaires dedies sont inclus dans cette validation :

* `test_per_sector_xs_merge_uses_global_universe` construit un cache XS sur trois symboles, le merge sur deux symboles sectoriels, puis verifie les colonnes, leur variance et l'absence de fallback uniforme a `0.5`.
* `test_per_sector_feature_contract_includes_fundamentals_when_enabled` verifie que toutes les colonnes fondamentales sont ajoutees/enlevees par `get_feature_columns` selon le flag.

Un test d'integration `_prepare_sector_data` est aussi vert : il simule deux symboles, cache XS global et fondamentales, puis verifie les colonnes demandees, leur presence dans `train_df`, la variance XS, les fondamentales non-nulles/non constantes et l'absence de colonne fantome.

Ces changements corrigent le contrat de donnees que ce plan avait identifie. Ils ne prouvent pas encore un gain d'alpha : il faut relancer le baseline per-sector comparable. Il reste un test d'integration desirable qui entraine puis persiste un artefact per-sector et compare son `feature_contract` a la matrice passee a `fit` ; le test actuel valide le contrat renvoye par `_prepare_sector_data`, pas le fichier d'artefact final.

**Diagnostic XS corrige :** le log n'utilise plus `mean() != 0.5`. Il compte les colonnes dont la variance est `> 1e-9`, avec identification des rangs et des colonnes sectorielles. Une colonne constante au default `0.0` ou `0.5` n'est donc plus qualifiee a tort de feature alimentee.

**Validation executable :** les tests concernes ont ete executes avec l'interpreteur du venv du projet et passent. Le terminal systeme peut ne pas resoudre `python`; utiliser explicitement l'interpreteur du venv pour les prochaines validations.

### Action 1.1 - Rendre les cross-sectionnelles reellement disponibles au per-sector - IMPLEMENTEE ET TESTEE

**Correction implementée :** les features cross-sectionnelles sont construites une fois sur l'univers global PIT, transmises a `run_per_sector_batch`/`_train_sector_models`/`_prepare_sector_data`, puis mergees sur `(symbol, date)` via `merge_cross_sectional_features` avant la neutralisation target et avant les splits. Le helper supprime les colonnes XS deja presentes avant le merge afin que le cache reel remplace necessairement les defaults, sans suffixe `_x/_y`.

Les rangs de date et les medianes sectorielles sont licites s'ils n'emploient que les barres connues a la cloture de cette date et un univers PIT. Le merge doit donc conserver le cutoff de training, la liste de symboles et l'empreinte du cache.

**A/B :**

* `S1a` : per-sector local seulement, flags XS off ;
* `S1b` : meme baseline avec XS reellement fusionnees ;
* `S1c` : XS reellement fusionnees mais global stacking off ;
* `S1d` : XS + `global_rank` uniquement si la couverture OOF passe les gates deja implementees.

**Mesures :** fraction de valeurs `0.5/0.0`, variance par colonne, taux de lignes sans univers minimum, IC intra-secteur et spread top-bottom. Une colonne demandee mais 99 % neutre doit etre retiree ou corrigee, jamais laissee silencieusement.

### Action 1.2 - Inclure les fondamentales quand le flag le demande - IMPLEMENTEE ET TESTEE AU NIVEAU PREPARATION

**Correction implementée :** `include_fundamentals=cfg.data.include_fundamentals_features` est maintenant passe a `get_feature_columns` dans `trainer_sector._prepare_sector_data`.

**Test d'integration restant :** avec le flag actif, verifier que les colonnes fondamentales sont dans `feature_cols` renvoye par `_prepare_sector_data`, le feature contract persiste et la matrice passee a `fit`, puis qu'elles ne sont pas constantes apres merge. Avec le flag inactif, elles doivent etre absentes.

**Pourquoi :** le code prepare deja `fundamental_df`, mais la matrice per-sector peut l'ignorer. Tester « les fondamentales n'ont pas de signal » avant cette correction serait une conclusion invalide.

**A/B :** seulement apres S1b :

* `S2a` : XS corrigees, sans fondamentales ;
* `S2b` : XS corrigees, fondamentales PIT ;
* `S2c` : fondamentales sector-neutralisees seulement, si les fondamentales brutes ajoutent surtout une exposition de taille/valorisation.

### Action 1.3 - Audit d'activite des features par fold

Ajouter pour chaque secteur/horizon/fold :

* `n_features_requested`, `n_features_present`, `n_features_non_constant` ;
* missing rate avant imputation, neutral/default rate apres imputation ;
* importance moyenne et importance stable par split ;
* correlation avec la target et avec le symbole/secteur ;
* liste des colonnes automatiquement exclues si variance quasi nulle.

**Pourquoi :** un arbre avec 177 features dont une fraction importante est neutre ne gagne pas un signal gratuit ; il gagne de la variance et rend les importances illisibles.

## 5. Phase 2 - Mesurer correctement le probleme per-sector (P0)

### Action 2.1 - Preserver une target economique relative explicite

Conserver trois objets distincts dans le frame, par horizon :

* `future_return_h` : rendement absolu, utile au PnL absolu ;
* `relative_return_h = future_return_h - median_sector(future_return_h, date)` : performance economique intra-secteur ;
* `target_h` : version transformee seulement pour le fit (vol scaling, clip, standardisation train-only selon l'experience).

Aujourd'hui la neutralisation est appliquee directement sur `target_h`. C'est coherent pour apprendre, mais ne permet pas toujours de separer dans les rapports l'alpha economique relatif de la transformation statistique utilisee pour l'estimateur.

### Action 2.2 - Ajouter les bonnes metriques par secteur et par date

Pour chaque fold et horizon, rapporter :

* IC Spearman **par date**, prediction vs `relative_return_h`, puis moyenne/IR ;
* IC prediction vs rendement absolu, explicitement etiquete « beta/PnL absolu » ;
* long-short intra-secteur top quintile moins bottom quintile, avant et apres couts ;
* hit rate du top tercile, turnover, nombre de titres par cote et concentration ;
* baseline zero, baseline mediane sectorielle et baseline rang aleatoire, avec intervalle de confiance bootstrap bloc par date ;
* metriques par secteur, horizon et regime.

**Pourquoi :** MSE `~1` sur target standardisee et directional accuracy `~50 %` suffisent pour signaler l'echec actuel, mais ne disent pas si un faible pouvoir de ranking est exploitable en portefeuille long-short. A l'inverse, un IC brut positif ne prouve pas une surperformance relative.

### Action 2.3 - Revoir la regle de champion

Le per-sector choisit actuellement le champion par `selection_score`, largement lie au F1 WF. Pour une target relative de regression, remplacer ou completer par une metrique alignee :

$$
score = IC_{relative} + \lambda \times spread_{net} - \gamma \times turnover
$$

Selectionner uniquement sur validations/WF, jamais sur le test final. Une variante simple est de faire choisir CatBoost/LightGBM par IC relatif moyen, avec un minimum de dates et une stabilite IR.

**Stop/go :** ne promouvoir aucun secteur dont l'IC relatif n'est pas positivement stable ou dont le spread net n'est pas significatif apres couts. Ne pas appliquer une exclusion Energy/Materials sur un unique batch : imposer au moins plusieurs folds et une periode holdout.

## 6. Phase 3 - Tester la cible per-sector, pas seulement les hyperparametres (P1)

La recommendation Deepseek « signal plutot que bug » est partiellement juste, mais il faut tester cela apres les corrections de contrat des sections 4 et 5.

### Action 3.1 - Comparer trois cibles relatives simples

Toutes les transformations statistiques doivent etre fitees sur le train de chaque fold. La mediane sectorielle de la date est autorisee car elle est contemporaine et ne consulte pas le futur.

| ID | Cible | Hypothese | Decision |
|---|---|---|---|
| T0 | Cible actuelle : target vol-scalee puis mediane sectorielle | Baseline code actuelle | Reference. |
| T1 | `relative_return_h` brut, puis clip/standardisation train-only | Le vol scaling peut amplifier le bruit court terme | Garder si IC relatif/spread net progressent de facon stable. |
| T2 | Rang percentile intra-secteur de `relative_return_h` | Le secteur fournit surtout un classement, pas une magnitude precise | Evaluer IC/ranking et top-bottom spread. |
| T3 | Classification ternaire intra-secteur | Les arbres peuvent mieux apprendre les extremes que la valeur continue | Classe long/short definie par quantiles train-only, zone flat centrale. |

Pour T3, ne pas reutiliser aveuglement `target_up_threshold=0.03` et `target_down_threshold=-0.03` : ces seuils sont des niveaux absolus et ne correspondent pas necessairement a la dispersion intra-secteur. Definir les seuils sur des quantiles de la cible relative **du train du fold**, puis les figer pour validation/test.

### Action 3.2 - Tester H20 seul, mais comme experience de diagnostic

La proposition de tester H20 seul est bonne : une cible a 20 jours peut avoir un meilleur ratio signal/bruit que H3/H5. Elle ne doit cependant pas etre comparee a un run multi-horizon dont les donnees, splits ou feature flags changent.

Executer `S-H20` avec exactement le baseline S0 puis comparer T0/T1/T2/T3 seulement sur H20. Si H20 ne depasse pas les baselines aleatoires/zero en IC relatif et spread net, ne pas multiplier les horizons ou les hyperparametres : le per-sector doit rester un filtre passif ou etre suspendu.

### Action 3.3 - Ajouter un modele de controle volontairement simple

Comparer CatBoost et LightGBM a :

* prediction zero sur target standardisee ;
* score momentum 20/60 intra-secteur ;
* ridge/elastic net sur features standardisees ;
* rank de momentum simple dans le secteur.

**Pourquoi :** si les arbres ne battent pas momentum intra-secteur ou ridge, le probleme est probablement la cible/features ; s'ils battent les baselines seulement en train, il est probablement du surapprentissage.

## 7. Phase 4 - Architecture per-sector : choisir la bonne granularite (P1)

### Action 4.1 - Ablation de `symbol`

Le `symbol` categoriel donne au modele une identite propre pour chaque titre. Il peut capturer des effets structurels utiles, mais aussi memoriser des comportements historiques qui ne se generalisent pas entre regimes.

Comparer, sur le meme protocole :

* `A0` : sans `symbol` ;
* `A1` : `symbol` categoriel actuel ;
* `A2` : `symbol` + features XS/fondamentales reellement disponibles.

Lire les performances par nouveau symbole, ancien symbole et regime. Garder `symbol` uniquement s'il augmente le holdout et le spread net, pas seulement la validation.

### Action 4.2 - Tester une structure hierarchique avant 11 modeles isoles

Un secteur moyen de 85 titres peut avoir beaucoup de lignes, mais relativement peu de cross-sections utiles par date. Tester :

* un modele global de rendement relatif avec `sector` categoriel et interactions ;
* un modele global, puis un residuel sectoriel leger ;
* groupes larges cyclique/defensif/tech-finance, seulement si la stabilite est meilleure.

**Pourquoi :** le Global Ranking dispose de plus de diversite cross-sectionnelle. Le per-sector ne doit pas necessairement recreer 11 alpha models independants ; il peut devenir une couche de calibration ou de residualisation.

### Action 4.3 - Usage de production prudent tant que S0-S3 sont faibles

L'avis GPT est raisonnable : ne pas utiliser actuellement le per-sector comme moteur principal. Tant qu'il n'a pas de score relatif OOS stable, l'utiliser seulement comme :

* filtre de veto faible ;
* pondération de taille bornee ;
* diagnostic de dispersion intra-secteur.

Le Global Ranking reste le moteur principal, avec le per-sector desactive si son signal est statistiquement nul. Un veto doit etre teste en backtest avec couts : il peut facilement retirer les meilleurs trades par hasard.

## 8. Phase 5 - Recuperer le Global Ranking (P1)

### Action 5.1 - Expliquer 6 splits au lieu de 8

Le rapport annonce `--wf-max-splits=8` mais seulement 6 splits effectifs. Avant toute optimisation :

* logguer la raison exacte de chaque split non produit (`historique insuffisant`, purge, min universe, filtre liquidite) ;
* calculer le nombre theoretique de splits a partir des dates distinctes ;
* verifier les bornes de `training_start_date`, `training_end_date`, `min_train_size`, `val_size`, `test_size`, `step_size` et la purge ;
* comparer G0/G1 avec le meme nombre de splits effectifs.

Forcer artificiellement 8 splits sans assez d'historique cree des folds courts ou chevauchants et peut rendre le resultat moins, non plus, fiable.

### Action 5.2 - Rejouer les anciens A/B sous forme de tournoi court

Ne pas relancer les 16 anciennes pistes. Rejouer seulement les hypotheses qui etaient gagnantes et qui peuvent avoir change apres les correctifs :

| Rang | Experience | Raison |
|---|---|---|
| G2 | 504 vs 756 jours | Le changement de splits/univers peut inverser le sweet spot. |
| G3 | 8 splits x 252 vs protocole actuel | L'ancien gain de 40 % doit etre reproduit sur le pipeline corrige. |
| G4 | smoothing on/off pour H10/H15/H20 | L'effet depend explicitement du nombre de splits. |
| G5 | sector-neutral on/off et factor-neutral on/off | Ce sont les deux transformations qui portaient le gain historique le plus grand. |
| G6 | feature families ablation | OHLCV/expert, XS, fondamentales, facteurs, regimes, puis combinaison gagnante. |

Utiliser une correction de multiple testing ou, au minimum, confirmer le vainqueur sur un holdout final jamais consulte durant G2-G6.

### Action 5.3 - VIX, VXN, VIX3M, MOVE et screener : hypotheses encadrees

Activer ces flags n'est pas une amelioration par defaut.

* Pour le **Global Ranking**, VIX/VXN/VIX3M/MOVE sont identiques pour tous les symboles une meme date. Une valeur macro brute ne peut pas, seule, classer les titres intra-date. Elle peut etre utile dans des **interactions regime x feature locale** ou pour changer la politique d'execution, mais ne doit pas gonfler le schema sans ablation.
* Pour le **per-sector**, ces variables peuvent conditionner le comportement d'un secteur a travers le temps. Tester d'abord les interactions explicites `macro_regime x momentum`, `macro_regime x volatility`, `macro_regime x sector`, plutot que des niveaux bruts seulement.
* Les **scores screener** ne doivent etre actives que s'ils ont un timestamp de disponibilite PIT. Tester leur incremental IC relatif par rapport au baseline corrige, puis verifier le taux de valeurs stale/missing et la stabilite par periode.

Ordre conseille : `screener seul`, `macro regime seul`, `screener + macro` seulement si les deux premiers sont positifs OOS. Aucun ajout ne passe si l'IC/spread ne s'ameliore que sur un secteur ou un split.

### Action 5.4 - Ne pas confondre IC et strategie H20

Comparer H5/H10/H15/H20 avec :

* IC par date et IR ;
* decile/quintile spread net de couts ;
* turnover, capacity et drawdown ;
* stabilite par regimes ;
* holdout final.

Choisir l'horizon d'execution sur le rendement net et la robustesse, pas seulement sur l'IC moyen d'un batch. Conserver H5 comme monitoring est acceptable seulement si une analyse hors echantillon confirme son utilite predictive pour le risque ou la sortie.

## 9. Matrice d'execution recommandee

### Vague A - Contrats et diagnostics, obligatoire

1. Implementer fusion XS per-sector et inclusion conditionnelle des fondamentales.
2. Ajouter tests de schema, variance, neutral defaults et PIT du merge.
3. Ajouter target economique relative et metriques IC relatif/spread net.
4. Rejouer G0, G1, S0 avec manifests comparables.

**Go vers Vague B seulement si :** les artefacts prouvent quelles colonnes sont reelles, les metriques par date existent, et les 3 runs sont reproductibles.

### Vague B - Diagnostic cible per-sector

1. `S1a/S1b` : local versus XS fusionnees.
2. `S2a/S2b/S2c` : fondamentales off/on/neutralisees.
3. `T0/T1/T2/T3` sur H20 seulement.
4. Ablation `symbol` et comparaison aux modeles simples.

**Criteres de poursuite :** amelioration coherentement positive sur la majorite des folds, IC relatif stable, spread net positif apres couts et confirmation sur holdout. Un gain de F1 macro seul n'est pas suffisant.

### Vague C - Global Ranking

1. Diagnostiquer les 6 versus 8 splits.
2. Tournoi G2-G6, un changement a la fois.
3. Tester screener et macro en incremental, avec interactions regime si necessaire.
4. Geler le vainqueur et l'evaluer sur le holdout de portefeuille.

### Vague D - Exploitation

1. Global Ranking comme signal principal uniquement s'il conserve IC/spread net sur holdout.
2. Per-sector comme veto/pondération seulement si S0-S3 prouvent un alpha relatif stable ; sinon desactiver son influence sur le capital.
3. Promotion d'un batch seulement si tests de leakage, manifests, gates de stacking, artefacts et backtest couts sont tous verts.

## 10. Tests a ajouter avant les prochains runs

| Test | But |
|---|---|
| `per_sector_xs_merge_uses_global_universe` | Les lignes sectorielles recoivent les valeurs XS du cache global, pas les defaults. **Ajoute et vert.** |
| `per_sector_feature_contract_includes_fundamentals_when_enabled` | Le helper ajoute/enleve les fondamentales selon le flag. **Ajoute et vert.** |
| `prepare_sector_data_delivers_xs_and_fundamentals_to_feature_contract` | Deux symboles, cache XS, fondamentales et `_prepare_sector_data` : contrat, matrice, variance et absence de colonnes fantomes. **Ajoute et vert.** |
| `merge_cross_sectional_features_overwrites_existing_defaults` | Defaults XS deja presents puis cache reel : verifier l'absence de suffixes `_x/_y` et l'ecrasement par les valeurs reelles. **Recommande comme test unitaire explicite du bug corrige.** |
| `per_sector_features_non_constant` | Toute feature active a une variance/missing rate acceptable par fold. |
| `per_sector_relative_metrics_align_target` | Direction/F1 utilisent la target relative ; IC relatif et IC brut sont distincts. |
| `per_sector_quantile_labels_fit_train_only` | Seuils ternaires relatifs ne consultent ni val ni test. |
| `global_wf_split_count_explained` | Chaque split perdu a une raison loggee et testable. |
| `stacking_global_gate_under_10_percent` | La gate globale ne merge ni ne persiste un cache invalide. |
| `stacking_symbol_gates` | Les branches `<10 %` et `[10 %,30 %[` neutralisent/alertent exactement les bons symboles. |
| `screener_features_point_in_time` | Un score publie apres la date de decision ne peut pas entrer dans le frame. |

## 11. Priorites finales

| Priorite | Action | Impact attendu |
|---|---|---|
| P0 | Corriger la disponibilite reelle XS/fondamentales du per-sector et tracer le schema | Peut modifier directement les performances et evite les faux A/B. |
| P0 | Ajouter IC relatif + spread net + baselines simples | Distingue absence d'alpha, mauvais objectif et mauvaise metrique. |
| P0 | Rejouer G0/G1/S0 avec manifest identique | Permet d'expliquer la regression plutot que d'optimiser du bruit. |
| P1 | Tester T0-T3 sur H20 | Decide si la regression de magnitude est le mauvais probleme. |
| P1 | Diagnostiquer 6 vs 8 splits puis rejouer G2-G6 | Peut recuperer une partie de l'IC Global avec une preuve actualisee. |
| P1 | Ablation `symbol` et architecture hierarchique | Reduit le risque de memorisation et de faible taille effective par secteur. |
| P2 | Screener et macro regime en incremental PIT | Source potentielle de signal, mais seulement apres baseline saine. |
| P2 | Tuning fin CatBoost/LightGBM | A faire seulement apres cible/dataset ; le tuning ne cree pas un alpha absent. |

## 12. Position sur les avis externes

* **Deepseek :** juste sur la necessite de tester H20 seul et de ne pas confondre infrastructure saine avec signal. Incomplet : il faut d'abord prouver que les features activees sont reellement fusionnees dans la matrice per-sector.
* **Gemini :** l'explication « evaluation sur rendement brut » est invalidee par le code actuel, qui evalue direction/F1 sur la target neutralisee. La conclusion de signal faible reste donc serieuse.
* **GPT :** juste sur le role prudent du per-sector tant qu'il est faible et sur l'interet des XS. Les XS doivent etre fusionnees correctement et evaluees par ablation, pas seulement activees dans un flag.
* **Qwen :** juste sur l'importance de comprendre les 6 splits et de tester une cible classification. Trop assertif sur l'exclusion de secteurs : aucune decision de capital ne doit etre prise sur un seul batch. Le ternary doit employer des seuils relatifs fit train-only, pas les seuils absolus proposes.
* **Votre avis :** reprendre des A/B est la bonne direction, mais comme une campagne de reproduction courte et controlee, pas comme une repetition des 16 tests historiques. Les flags screener/VIX/VXN/VIX3M sont de bonnes hypotheses seulement avec tests PIT incrementaux et interactions de regime pour le ranking cross-sectionnel.

## Conclusion

Le prochain gain ne viendra vraisemblablement pas d'un changement de profondeur CatBoost ou d'une nouvelle famille de 50 features. Il faut d'abord rendre visible la matrice reellement entrainee par le per-sector, mettre ses features XS/fondamentales en coherence avec les flags, puis tester une cible economique relative et un benchmark long-short net. Si le per-sector ne bat toujours pas un simple ranking momentum intra-secteur sur un holdout, il faudra assumer qu'il n'a pas d'alpha propre et l'utiliser seulement comme diagnostic, voire le retirer de la cascade. Le Global Ranking garde un signal positif ; il merite une campagne A/B reproduisible pour determiner si l'IC `0.019` historique survit aux corrections de protocole.

---

## 13. Avis Copilot (DeepSeek V4 Pro) — 2026-08-04

### Accord global : ~90%

L'audit GPT est rigoureux, bien séquencé, et identifie correctement les deux défauts de contrat P0 (XS non fusionnées, fondamentales exclues). Les phases sont logiquement ordonnées : d'abord rendre le dataset visible et correct, ensuite mesurer, puis tester des hypothèses, enfin optimiser.

### Points d'accord fort

1. **P0 : XS + fondamentales** — ces deux bugs de contrat rendent tout A/B sur le per-sector invalide. À fixer avant toute expérience.
2. **Reproductibilité avant optimisation** — relancer G0/G1/S0 avec manifest est la seule façon d'expliquer la baisse d'IC.
3. **Métriques relatives** — F1=0.33 et DirAcc=50% disent « ça ne marche pas » mais pas pourquoi. L'IC relatif par date + spread net long-short sont nécessaires.
4. **H20 seul comme diagnostic** — tester la cible la plus stable avant de jeter le per-sector.
5. **Ne pas relancer les 16 A/B** — reproduire 3-6 expériences clés, pas le historique complet.
6. **Screener/VIX en PIT incrémental** — pas de activation massive sans ablation.

### Nuances

1. **Ablation `symbol` (§4.1)** — test scientifiquement valide, mais pas prioritaire. Si le per-sector reste à F1=0.33 après corrections XS + fondamentales, retirer `symbol` ne changera rien. À faire en Phase 4, pas avant.
2. **Architecture hiérarchique (§4.2)** — intéressant mais prématuré. Un modèle global avec `sector` catégoriel est du design exploratoire. À réserver pour quand les baselines corrigées seront stabilisées.

### Ajouts suggérés

1. **Vérifier la target post-split dans le per-sector** — après les 25 fixes post-leakage, vérifier que `run_tabular_baseline` / `run_tabular_walk_forward` appliquent bien la winsorization train-only et que le `shift(-h)` ne traverse pas les frontières dans le chemin per-sector.
2. **Tracer le nombre de symboles par secteur par date** — un secteur annoncé à 85 symboles peut avoir des dates à 20 symboles. Si `cross_sectional_min_universe=20` filtre beaucoup de dates, le per-sector tourne sur très peu de données effectives.

---

## 14. Résumé exécutif — Copilot

| Priorité | Action | Effort | Impact |
|----------|--------|--------|--------|
| **P0** | Fix XS merge + fundamentals dans per-sector | 2h | Direct sur le signal |
| **P0** | Relancer G0/G1/S0 avec manifest | 1 run | Explique la régression |
| **P0** | Ajouter feature audit par fold | 3h | Visibilité sur la matrice réelle |
| **P1** | Ajouter IC relatif + spread net + baselines simples | 4h | Distingue absence d'alpha vs mauvaise métrique |
| **P1** | Diagnostiquer 6 vs 8 splits | 1h | Peut récupérer l'IC perdu |
| **P1** | Tester T0-T3 sur H20 | 4 runs | Décide si la cible est le problème |
| **P2** | Tournoi Global Ranking G2-G6 | 6 runs | Optimisation avec preuve |
| **P2** | Ablation symbol + architectures | 4 runs | Design exploratoire |

**Recommandation** : commencer par les Actions 1.1 (fusion XS) et 1.2 (fondamentales) immédiatement — ce sont des bugs de code, pas des hypothèses à tester. Ensuite relancer S0 pour voir si le per-sector récupère un signal une fois les features correctement alimentées.