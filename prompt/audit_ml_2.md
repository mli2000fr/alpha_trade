# Audit ML ModelFactory 2 - Revalidation leakage, contrats et maturite production

**Date :** 2026-08-04  
**Perimetre :** `modelFactory/{config,features,dataset,cross_sectional,global_ranking,tabular_baseline,trainer,trainer_sector,orchestrator,predictor,db_registry}.py`, `common/tradable_universe.py`, documentation et tests ModelFactory.  
**Modes couverts :** Global Ranking, per-symbol LSTM/LightGBM/CatBoost, per-sector LightGBM/CatBoost, mono-horizon, multi-horizon, features cross-sectionnelles, stacking global rank, labels fixed-horizon et triple-barrier.  
**Methode :** lecture des chemins producteurs -> transformations -> splits -> entrainement -> artefacts -> inference, greps, tests cibles et sondes runtime minimales. Aucun backtest historique complet ni entrainement DB complet n'a ete execute dans cet audit.

## 1. Conclusion executive

Les correctifs successifs ont retire les fuites les plus graves qui invalidaient les entrainements per-sector et les targets de regression. A la date de cet audit, **aucune fuite temporelle de target confirmable n'a ete trouvee** dans les chemins de construction de target fixed-horizon examines, sous les hypotheses suivantes :

* les barres chargees par date sont exactes et disponibles a la cloture de la date consideree ;
* les snapshots d'univers canoniques dans `tradable_universe_history` sont complets ;
* les executeurs utilisent les helpers de split par dates lorsqu'ils operent sur un panel multi-symboles.

Le module n'est toutefois pas encore au niveau d'un systeme quantitatif production complet. Les sujets principaux ne sont plus des `shift(-h)` traversant les symboles, mais des **contrats de recherche et d'exploitation** : couverture OOF non bloquante du stacking, validation de purge formulee en jours calendaires, biais de selection d'univers/liquidite dans le walk-forward, et absence de test E2E sectoriel avec de vrais artefacts/backend.

**Decision recommandee :**

* `per_symbol` et Global Ranking peuvent etre utilises en recherche encadree, avec un rapport explicite de couverture OOF et un univers PIT versionne.
* `per_sector` est structurellement pret sur les chemins analyses, mais doit rester derriere une gate de promotion tant que le test E2E `registre -> route -> feature frame -> prediction` n'est pas vert pour LightGBM et CatBoost, par horizon.
* Ne pas qualifier le module de "sans leakage". Dire plutot quels invariants sont verifies, par quels tests, et sur quel univers/version de donnees.

## 2. Validations executees pendant cet audit

| Controle | Resultat | Interpretation |
|---|---|---|
| `test_per_sector_prepare_isolates_symbols` sans couverture | **Passe** | Le fixture `v1` exerce les trois assertions : forward return H3 du meme symbole, invariance a l'ordre de concatenation et rolling volatility non contaminee. |
| Sondes features cross-sectionnelles | **Passe** | Modifier les 10 dernieres observations d'un symbole ne modifie pas les 60 premieres valeurs `ret_20`, `ret_60`, `volatility_20`, `dollar_volume_20`, `momentum_20`. Les fenetres sont retrospectives. |
| Sonde target regression `skip_winsorize=True` | **Passe** | Une mutation future ne modifie pas le prefixe de target preparee. Les quantiles ne sont plus appliques pendant `prepare_symbol_frame`. |
| Sonde IC cross-sectionnel | **Passe dans l'audit precedent** | Deux dates avec IC +1 et -1 donnent `ic_mean=0`, confirmant l'agregation date par date. |
| Sonde route sectorielle | **Passe** | Un `artifact_routes.models.lightgbm` valide est resolu en backend `lightgbm_tabular` avec chemin `.txt`. |
| Sonde categories LightGBM | **Passe, avec limite** | Les categories connues gardent leur prediction quand une categorie additionnelle est presente. Une categorie inconnue est acceptee mais suit une branche existante, sans politique explicite. |
| Tests `dataset + cross_sectional + predictor` | **75 passes, 3 echecs** | Les echecs sont des tests devenus obsoletes apres evolution de configuration/multi-horizon, decrits en section 7. |
| `git diff --check` du rapport | **Passe** | Rapport sans erreur de whitespace. |

## 3. Invariants de leakage verifies

### 3.1 Targets et transformations - valide sous conditions

#### Per-symbol et per-sector, regression, mono/multi-horizon

`prepare_symbol_frame` appelle `build_target` et `build_multi_horizon_targets` avec `skip_winsorize=True`. Les rendements forward et le vol scaling sont construits avant split, mais les quantiles de winsorisation sont ensuite fites sur train seulement dans :

* `run_tabular_baseline` pour le split simple ;
* `run_tabular_walk_forward` pour chaque fold ;
* `SymbolDataModule.setup` pour le LSTM.

Cela elimine le leakage precedemment confirme ou une mutation future changeait les quantiles appliques aux observations de train. La target reste naturellement indisponible sur les dernieres `h` lignes ; les splits purgent ces observations de train/validation.

**Dette restante :** les bornes de winsorisation, moyenne et ecart-type ne sont pas un transformateur persiste unique dans les artefacts finaux. Cela ne constitue pas une fuite de WF, mais rend la reproductibilite des predictions de regression et du re-fit final moins traçable.

#### Global Ranking

`_compute_ranking_targets` est invoquee sur les partitions de fold, pas sur le panel complet. Le forward return utilise `groupby("symbol").shift(-horizon)` et les labels sont ensuite transformes intra-date. Cette structure empeche le retour forward d'un titre de traverser une frontiere train/validation ou un autre symbole.

Les winsorisations/rangs/neutralisations du ranking sont calcules a la date avec les symboles presents a cette date dans la partition. C'est valide pour une prediction produite apres la cloture de la date, mais depend de l'univers PIT (section 5).

### 3.2 Splits et purge - corrects pour les chemins productifs par dates

* `chrono_split_by_dates` et `generate_walk_forward_splits_by_dates` conservent une date atomique dans une seule partition.
* Les helpers retirent les dernieres **dates distinctes** de train et validation avec `_purge_by_dates(..., purge_tail_dates=forecast_horizon)`.
* Global Ranking et per-sector utilisent les splits par dates ; le per-symbol reste une serie unique et peut utiliser les splits par lignes, ce qui est coherent si les dates sont ordonnees et uniques pour le symbole.
* En multi-horizon, trainer et trainer_sector recreent les splits avec `forecast_horizon_override=h` pour chaque horizon. H3 n'utilise donc pas silencieusement la purge H20.

### 3.3 Per-sector - isolation des series validee

La preparation appelle `prepare_symbol_frame` par symbole avant concatenation. Ainsi les rolling, rendements forward et features locales sont calcules dans la serie propre a chaque titre. Le test P0 couvre le forward return, l'ordre de concatenation et la volatilite rolling. C'est une amelioration structurante et bien ciblee.

### 3.4 Features cross-sectionnelles - pas de fuite future observee

Les features brutes de `cross_sectional.py` (`ret_20`, `ret_60`, volatilite, dollar volume, RSI, SMA) ne font appel qu'a `shift` positif et `rolling` retrospectif. Elles peuvent etre calculees sur tout l'historique sans faire entrer de valeurs futures dans une date precedente. Les rangs sont calcules `groupby("date")`, ce qui est conforme a une decision cross-sectionnelle prise a la cloture de cette date.

Ce point ne dispense pas d'un univers PIT : la formule est temporalement saine, l'eligibilite des titres peut encore biaiser le panel.

## 4. Constats actifs, risques et corrections recommandees

### Verification des correctifs - round du 2026-08-04

| Sujet | Statut verifie | Evidence |
|---|---|---|
| Tests triple-barrier et colonnes globales | **Resolu** | Les deux fixtures triple-barrier ont des seuils valides et le test multi-horizon accepte les colonnes attendues. La suite ciblee est maintenant a **79 passes**. |
| P1-5 stacking | **Ameliore, tests de branches manquants** | `global_rank_available` separe correctement le fallback du score OOF. Une gate globale sous 10 % et une gate symboles sous 10 % sont implementees ; la couverture par symbole est loggee avec mediane/minimum et warning sous 30 %. Le merge/persistence est maintenant protege lorsque la gate globale desactive le stacking. |
| P2-5 invalidation cache | **Resolu au code** | `clear_prediction_data_cache` vide maintenant les caches global-rank et features per-symbol, en plus des caches benchmark/cross-sectionnel. Un test de non-regression reste souhaitable. |
| P2-6 symboles inconnus | **Resolu par politique documentee** | Le comportement LightGBM, CatBoost et le fallback per-symbol sont explicitement documentes. La performance hors univers reste non garantie, ce qui est correctement indique. |
| P2-3 purge en seances | **Stabilise, approximation documentee** | La tentative par positions a ete retiree car le validateur ne connait que les folds deja purges. Le controle revient a `.days`, approximation conservative, tandis que la purge productive reste correcte par construction. |
| P1-6 disponibilite/liquidite par fold | **Partiellement resolu** | Les symboles ayant moins de `min_train_size / 2` seances ou un volume moyen train inferieur au seuil sont ecartes de train/validation du fold et le nombre est trace. Le filtre est conditionne a `enable_liquidity_filter`, le message indique correctement le filtrage per-fold et les compteurs sont calcules apres exclusion. Top-N/autres criteres ne sont pas encore recalcules par fold. |
| E2E per-sector | **Test de route unitaire ajoute** | Le test valide `config.json -> _resolve_selected_model_route -> lightgbm_tabular`; il n'exerce ni registre DB, ni chargement LightGBM reel, ni feature frame, ni `predict_symbol`. |

### P2-3 - limite connue du validateur de purge

La tentative de validation par positions de seances a ete invalidee : la suite ciblee produisait **76 passes, 1 echec** sur `TestValidateFoldIsolation.test_valid_split_passes`. Elle a ete retiree et la suite est maintenant a **79 passes**.

La cause est precise : `validate_fold_isolation` reconstruisait `_all_dates` a partir des trois partitions deja purgées. Les cinq dates retirees entre train et validation n'appartenaient plus a cet index ; la distance de position etait donc artificiellement egale a 1. Comparer les positions reste la bonne direction, mais le validateur devrait recevoir le calendrier ou le frame complet **avant** purge, ou conserver les bornes/index de split dans `ChronoSplit`.

Le validateur utilise donc a nouveau `.days` pour purge et embargo. C'est une approximation conservative explicitement documentee : un week-end peut declencher un faux positif, mais le helper productif `_purge_by_dates` retire bien les dates distinctes requises. La correction complete doit couvrir purge **et** embargo avec le meme calendrier de seances fourni avant purge.

### Couverture de test restauree

`test_fold_isolation_report_to_dict` et `test_zero_horizon_split_still_disjoint` ont ete remontes au niveau module et sont maintenant collectes. La suite ciblee confirme `79 passed`.

### P0-2 - Per-sector : route coherente, preuve E2E d'integration manquante

**Statut : P0 gate de promotion production / preuve E2E manquante.**

Le contrat a fortement progresse : `trainer_sector` persiste `artifact_routes` avec les deux backends et `predictor._resolve_sector_run` joint `model_training_run` et `model_governance` pour retrouver le modele choisi. `_resolve_selected_model_route` accepte le format et route correctement vers LightGBM tabulaire lors de la sonde.

Il manque la preuve qui compte en production : un artefact sectoriel reel, une ligne de registre reelle, un symbole membre du secteur, une feature frame a la date de cutoff et une prediction persistable. Le code est structurellement en place ; ce point n'est pas un bug de logique demontre. Sans ce test, les incompatibilites de chemin, de schema DB, de config, de signature ou de format `.txt/.cbm` peuvent toutefois rendre le mode indisponible dans l'environnement reel.

**Correction prioritaire :** ajouter deux tests `pytest` E2E avec DB temporaire/mocks realistes :

1. LightGBM : entrainer un secteur minimal, persister modele/config/governance, resoudre un symbole, predire.
2. CatBoost : meme scenario, marque `integration` si le package doit etre optionnel.

Chaque test doit verifier le backend choisi, l'horizon, les colonnes de la matrice et le `run_id` en sortie.

### P1-5 - Stacking global rank : gate minimale ajoutee, gouvernance OOF incomplete

**Statut : P1 integrite de recherche.**

`global_rank_df` ne contient que les predictions de validation walk-forward. Lors du merge dans le cache cross-sectionnel, les dates/symboles absents sont remplaces par `0.5`. Le correctif ajoute `global_rank_available`, calcule la couverture par date, avertit sous 50 % et desactive le stacking sous 10 %. Apres merge, il calcule aussi `groupby("symbol")["global_rank_available"].mean()`, loggue mediane/minimum, avertit pour les symboles sous 30 % et neutralise les rangs/availability des symboles sous 10 %. C'est une protection reelle contre une couverture quasi nulle et une observabilite utile des symboles mal couverts.

Le bug de flux de la branche globale `<10 %` est corrige : merge, persistence parquet et logs dependants sont maintenant places sous `if global_rank_df is not None and not global_rank_df.empty`. La suite ciblee reste verte a `79 passed`.

**Dette de test :** aucun test orchestrateur ne couvre encore les branches globale `<10 %`, symbole `<10 %` et symbole `[10 %, 30 %[`. Ajouter ces trois cas est necessaire pour proteger les gates nouvellement introduites. Le doublon d'assignation `global_rank_df["global_rank_available"] = True` a ete retire.

Ce n'est pas une fuite si les valeurs presentes sont vraiment OOF. C'est un biais de comparabilite : deux splits per-symbol peuvent avoir des proportions tres differentes de vrai signal global et de valeur neutre. Une bonne metrique globale peut etre diluee ou artificiellement stabilisee selon le calendrier de couverture.

**Complement recommande :**

* conserver `global_rank_available` booleen, ne pas confondre `0.5` neutre et une prediction effectivement egale a 0.5 ;
* conserver la couverture par symbole maintenant ajoutee et la ventiler par partition train/val/test/WF ;
* rendre configurable le seuil global et ajouter un seuil/gate par symbole pour les symboles sous-couverts ;
* logguer et persister la couverture dans les metriques et l'artefact ;
* tester qu'aucune valeur non OOF ne rejoint une matrice d'entrainement.
* ajouter un test orchestrateur couvrant explicitement les branches globale `<10 %`, symbole `<10 %` et symbole `[10 %, 30 %[`.

### P1-6 - Disponibilite par fold filtree, liquidite/top-N encore globaux

**Statut : P1 partiellement corrige ; risque de selection temporelle residuel, pas une fuite de label directe.**

L'univers de base est une union de snapshots canoniques PIT entre `training_start_date` et `training_end_date`, ce qui est une bonne fondation. Dans chaque fold Global Ranking, les symboles ayant moins de `max(min_train_size / 2, 60)` seances dans le train ou un volume quotidien moyen train sous `liquidity_min_avg_volume_20d` sont maintenant exclus du train et de la validation, et le nombre d'exclusions est trace. Le calcul est bien effectue sur le `train_df` du fold, sans regarder les volumes de validation ; cela empeche un titre avec historique ou volume insuffisant de participer aux metriques de ce fold.

Le filtre ajoute est correctement conditionne par `cfg.data.enable_liquidity_filter`, coherent avec le contrat de configuration. Le warning indique que sessions+volume sont controles per-fold, tout en distinguant la selection initiale globale qui reste a ameliorer. Les compteurs `_train_syms`/`_val_syms` sont maintenant recalcules apres exclusion et refletent donc le panel effectivement entraine. `filter_symbols_by_liquidity` reste par ailleurs applique une seule fois avec `end_date=training_end_date`, avant le walk-forward ; les plafonds `global_ranking_max_symbols` et `per_symbol_max_symbols` utilisent aussi une moyenne de volume sur tout l'historique charge jusqu'a la fin. Enfin, le filtre derive l'eligibilite des symboles presents dans `train_df` : un symbole totalement absent du train est retire de la validation par la difference avec l'union train/val, mais ce cas merite un test explicite.

Une selection de titres liquides a la fin de periode peut influencer les folds anciens : un titre illiquide dans un ancien regime mais liquide a la fin entre dans l'etude, ou l'inverse. Les rendements/labels ne fuient pas, mais la selection de l'univers et les metriques WF deviennent conditionnelles a une information plus recente que le fold.

**Complement recommande :**

* definir explicitement le protocole : univers fixe a la date initiale, reconstitution par date, ou rebalancement periodique ;
* pour le WF, calculer la selection de liquidite et top-N uniquement sur le train disponible a chaque fold ;
* recalculer les compteurs de symboles apres exclusion et remplacer le warning legacy par un diagnostic de couverture post-filtre ;
* persister par fold `universe_snapshot_id`, liste/hash des symboles, criteres de liquidite et date de selection ;
* ajouter un test ou un symbole ne devient liquide qu'apres le premier fold et verifier qu'il n'est pas eligible avant sa date d'entree.

### P2-3 - `validate_fold_isolation` : tentative de comptage en seances non fonctionnelle

**Statut : P2 outillage de validation, regression de test.**

Le split productif par dates retire effectivement un nombre de dates uniques. La correction remplace le calcul calendrier par des positions, mais cree son index de seances a partir des partitions deja purgées. Elle perd donc les seances retirees et echoue sur un split valide. L'embargo compare encore `(first - last).days`.

**Correction :** injecter l'index ordonne des dates du dataset avant purge dans le validateur, ou conserver les bornes de split et le calendrier dans `ChronoSplit`, puis comparer les positions. Utiliser ce meme calendrier pour l'embargo. Ajouter des tests incluant week-end, jour ferie, date manquante et split purgé valide.

### P2-4 - Universe cross-sectionnel PIT : snapshot non persiste par feature date/fold

**Statut : P2 robustesse / auditabilite.**

Le module dispose de snapshots canoniques et sait charger un univers a une date en inference. Pendant l'entrainement, les features cross-sectionnelles sont toutefois calculees sur une liste de symboles globale, et aucun hash du sous-univers effectivement present par date/fold n'est persiste avec les metriques. Les dates avec titres manquants sont neutralisees si l'univers est trop petit, mais le chercheur ne peut pas reconstituer exactement les membres elegibles ayant participe au rang d'une date ancienne.

**Correction :** persister pour chaque fold une table ou un artefact compact `date -> universe_fingerprint, count, symbols_hash, snapshot_run_id`. Lier cette empreinte aux predictions OOF et aux rapports de performance par regime.

### P2-5 - Caches de prediction : corrige, test de non-regression recommande

**Statut : resolu au code.**

`clear_prediction_data_cache` vide maintenant aussi `_global_rank_prediction_cache` et `_per_symbol_features_cache`. Le risque de valeurs stale dans un processus long est ainsi traite au point d'invalidation expose.

**Test recommande :** `train/update artifact -> clear -> prediction reads new config`, avec assertion sur les quatre caches.

### P2-6 - Politique de categories inconnues documentee

**Statut : resolu par documentation ; risque de performance residuel connu.**

La documentation expose maintenant la politique : LightGBM ajoute le symbole aux categories, CatBoost gere nativement les valeurs non vues et le predicteur remonte vers le per-symbol si le modele sectoriel est indisponible. Elle indique aussi correctement l'absence de garantie de performance hors univers.

Le contrat CatBoost doit toutefois etre execute en CI optionnelle, pas seulement inspecte statiquement.

## 5. Faux positifs ecartes et nuances importantes

### Cross-sectional calcule sur toute la periode

Ce n'est pas une fuite future en soi. Les `rolling` utilises sont retrospectives et les rangs ne combinent que les titres de la meme date. Le correctif necessaire concerne l'univers PIT et son auditabilite, pas un recalcul artificiel de chaque rolling a chaque fold.

### Sector-neutral dans Global Ranking

Les targets de ranking sont calculees dans chaque fold isole avant le fit. La mediane sectorielle par date est une transformation contemporaines des titres disponibles a cette date ; elle ne consulte pas la validation/test depuis le train. L'alerte pertinente est le mapping secteur/univers PIT, pas la neutralisation elle-meme.

### Re-winsorisation post-split

Elle est maintenant pertinente parce que le clipping pre-split est desactive dans le chemin `prepare_symbol_frame`. Le fait que `build_target` conserve un parametre `skip_winsorize=False` ne reintroduit pas de fuite tant que les entrees d'entrainement passent par la preparation standard. Ajouter un test de contrat empechera une future regression d'appelant direct.

### Fallback de prediction

Le predictor verifie le contrat de features avant la resolution et de nouveau dans le chemin tabulaire ou LSTM final. Le fallback n'est donc pas une fuite identifiee. Il reste une surface a tester, surtout avec stacking, mais pas un P0 prouve dans cette lecture.

## 6. Bugs et dette de tests observes

Le lot cible `tests/test_model_factory_dataset.py`, `tests/test_model_factory_cross_sectional.py`, `tests/test_model_factory_predictor.py` donne **75 passes et 3 echecs** :

1. `test_prepare_symbol_frame_uses_triple_barrier_targets` instancie `DataConfig(target_mode="ternary", label_method="triple_barrier")` avec seuils ternaires par defaut nuls. La validation exige maintenant `target_up_threshold > 0` et `target_down_threshold < 0`.
2. `TestFoldIsolationEndToEnd.test_triple_barrier_optimization_train_only` a le meme contrat de configuration obsolete.
3. `test_global_pred_feature_columns_defined` attend une seule colonne globale alors que le contrat multi-horizon en expose maintenant quatre (`global_rank_3`, `_5`, `_10`, `global_rank`).

Ces echecs ne prouvent pas une fuite, mais ils cachent la couverture des labels triple-barrier et du stacking. Ils doivent etre corriges avant de faire confiance a la CI comme garde-fou anti-leakage.

**Correctifs minimaux :** donner des seuils valides aux fixtures triple-barrier et modifier le test de colonnes globales pour verifier l'ensemble multi-horizon attendu, pas une cardinalite historique.

## 7. Coherence par mode

| Mode | Labels/splits | Features | Inference | Avis |
|---|---|---|---|---|
| Per-symbol LSTM | Chronologique, purge horizon, standardisation train-only | Bon contrat local ; flags avances transmis a la preparation | Contrat verifie, tests nombreux | Le plus mature, mais persister le transformateur target final et remettre les tests triple-barrier au vert. |
| Per-symbol tabulaire | Split/WF horizon-specific | Feature contract et artefacts locaux presentes | Route LightGBM/CatBoost testee unitairement | Solide pour recherche. Stacking doit etre gouverne par couverture. |
| Per-sector | Preparation isolee par symbole et split par dates | `symbol` categoriel + target relative ; les XS globaux post-concat sont intentionnellement non requis | Route existe mais E2E absent | Structurellement pret ; promotion conditionnee par E2E et politique unknown explicite. |
| Global Ranking | Folds par dates, target fold-isolee, IC quotidien | Rangs/neutralisation intra-date coherents | Artefact global et fallback disponibles | Bon coeur quantitatif. Univers/liquidite et OOF coverage sont les vrais risques residuels. |
| Multi-horizon | Purge dynamique par horizon dans baselines/WF | Colonnes/horizons explicites | Champion primaire et routes a auditer par horizon | Architecture saine, mais necessite tests systematiques par horizon et artefacts de transformateurs. |

## 8. Avis sur le module

Le module a plusieurs qualites que l'on rencontre rarement ensemble dans un projet ML de trading en cours de construction :

* les problemes precedents ont ete corriges a la racine, notamment preparation per-symbol, dates atomiques et target regression ;
* les config dataclasses, feature fingerprints, contrats d'artefacts, seeds et diagnostics WF donnent une base de gouvernance serieuse ;
* l'approche Global Ranking cross-sectionnelle est plus alignee avec la construction de portefeuille qu'une simple collection de classifieurs independants ;
* la distinction entre IC, directional accuracy, F1 et decile spread est conceptuellement saine ;
* les snapshots d'univers canoniques montrent une vraie intention PIT.

Ses faiblesses sont celles d'un module qui est passe rapidement du prototype a la plateforme : plusieurs comportements importants sont encore encodes par des conventions de fichiers, des fallbacks neutres ou des flags booleens plutot que par des objets de contrat typables et testes de bout en bout.

Le risque principal n'est plus un bug trivial de `shift`, mais de publier des chiffres de recherche dont l'univers, la couverture OOF, les transformations de target et la route de serving ne sont pas assez materialises pour etre rejoues exactement.

## 9. Ecart vers un niveau professionnel

Un desk quantitatif ou une equipe ML mature ne se distingue pas seulement par un meilleur modele. Elle rend chaque resultat **reproductible, attribuable et refusable**.

### Niveau attendu

1. **Data versioning PIT** : chaque run stocke les barres, fondamentales, news, univers et taxonomie tels qu'ils etaient connus a la date du run.
2. **Experiment tracking immuable** : code hash, config resolue, seeds, feature schema, target transform, univers/fold fingerprints, artefacts et metriques sont lies dans un manifest unique.
3. **Validation purgee** : tests de disjonction par seances, embargo, overlap de labels, selection d'univers fit sur train et tests de mutation future dans CI.
4. **Separation recherche/production** : registry avec promotion explicite, signature, tests de compatibilite et rollback. Aucun fallback silencieux vers un modele different sans evenement de gouvernance.
5. **Evaluation portefeuille** : IC quotidien par univers, turnover, couts, impact, capacity, contraintes, exposition sectorielle/factorielle, stabilite par regime et analyse de degradations.
6. **Monitoring live** : freshness, missingness, drift de features/target proxy, couverture de prediction, latence, taux de fallback, distribution de signaux, performance realisee et alertes.

### Priorites concretes

**Sprint 1 - integrite des contrats**

1. E2E sectoriel LightGBM puis CatBoost.
2. Gate stacking par couverture OOF, avec `global_rank_available`.
3. Validation de purge par index de seances.
4. Reparer les trois tests rouges et ajouter mutation-future regression/LSTM/WF.

**Sprint 2 - reproductibilite**

1. `RunManifest` unique et versionne : config resolue, code SHA, univers par fold, schema features, target transform, artefacts.
2. Transformateurs `fit(train)/transform(frame)` explicites pour winsorisation/standardisation, serialisables par horizon.
3. Cache invalide par `run_id + artifact fingerprint + cutoff_date`.

**Sprint 3 - protocoles quantitatifs**

1. Selection liquidite/top-N dans chaque fold a partir de son train uniquement.
2. Evaluation OOS imbriquee : tuning -> validation -> holdout final totalement gele.
3. Backtest portefeuille avec couts realistes, capacity et contraintes de liquidite.

**Sprint 4 - exploitation**

1. Promotion gate : seulement un artefact ayant passe schema, E2E, OOS et controles de risque peut etre servi.
2. Tableau de bord de monitoring et kill switches par data freshness, taux de fallback, drift et couverture.
3. Runs de recalibration avec canary, comparaison contre champion et rollback automatique.

## 10. Matrice de tests recommandee

| Test | Priorite | Invariant |
|---|---|---|
| E2E per-sector LightGBM/CatBoost | P0 | DB registry -> route -> categories -> predict_symbol, pour chaque horizon. |
| OOF stacking coverage gate | P1 | Aucun split n'utilise un rank non OOF ; echec sous seuil. |
| Universe/liquidity fit par fold | P1 | Un symbole devenu eligible plus tard n'apparait pas dans un train ancien. |
| Regression target mutation | P1 | Modifier val/test ne change ni target train ni bornes fit train, pour baseline/WF/LSTM et multi-horizon. |
| Purge en seances | P1 | Week-end/jour ferie ne modifient pas la conclusion de purge. |
| Triple-barrier config/tests | P1 | Seuils valides, optimisation train-only, labels limites aux seances du fold. |
| Stacking fallback schema | P2 | Fallback global -> local/LSTM conserve ou desactive proprement les features attendues. |
| Unknown symbol policy | P2 | Rejet, categorie inconnue ou fallback explicite et trace. |
| Cache invalidation | P2 | Nouvel artefact/config est lu dans le meme processus apres invalidation. |
| Universe fingerprint replay | P2 | Meme fold/date/universe produit le meme hash et les memes rangs. |

## 11. Criteres avant mise en production

Le module peut pretendre a une mise en production controlee lorsque :

* tous les tests P0/P1 ci-dessus sont verts en CI avec les dependances actives ;
* chaque run de training persiste son manifest, son univers par fold et ses target transforms ;
* le stacking est soit correctement couvert OOF, soit desactive ;
* le per-sector passe les E2E de serving pour les deux backends ou est explicitement bloque ;
* les performances sont confirmees sur une periode holdout gelee, apres couts et contraintes de trading ;
* la prediction live fournit des indicateurs de freshness, fallback et couverture avec des seuils bloquants.

En l'etat, le module a une base technique prometteuse et une trajectoire claire. La prochaine valeur ne viendra probablement pas d'ajouter une quatrieme famille de modele, mais de verrouiller l'univers PIT, le protocole OOF, la promotion d'artefact et la mesure portefeuille OOS. C'est ce qui transforme de bons scores ML en systeme de decision defendable.