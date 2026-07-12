# Plan d'action pour obtenir un GO live

Date de préparation : 2026-07-12  
Application : Alpha Trade, swing trading US long/short ML-first  
Document fonctionnel de référence : `doc/synthese_long_short.md`

## 1. Objet et décision recherchée

Ce document décrit le chemin permettant de passer progressivement de l'état actuel à un **GO live gouverné**. Il ne cherche pas à démontrer que la stratégie est rentable par une affirmation ou par quelques tests unitaires. Il exige des preuves séparées sur trois sujets :

1. **La stratégie possède-t-elle un avantage économique hors échantillon ?**
2. **L'application exécute-t-elle fidèlement et sans danger ce que la stratégie demande ?**
3. **L'exploitation quotidienne sait-elle détecter une anomalie, arrêter le système et revenir en arrière ?**

Le GO n'est pas une décision binaire unique. Il existe plusieurs niveaux :

| Niveau | Capital réel | Ce que le niveau autorise |
|---|---:|---|
| GO recherche | Non | Continuer les expériences offline |
| GO shadow | Non | Produire les décisions quotidiennes sans ordre broker |
| GO paper | Non | Envoyer les ordres à un compte broker paper |
| GO live 5 % | Oui | Engager 5 % du budget de risque nominal |
| GO live 10/25/50 % | Oui | Augmenter progressivement le budget après observation |
| GO live 100 % | Oui | Utiliser le budget de risque nominal complet |

**État actuel vérifié :** GO recherche et préparation shadow. Le live reste **NO-GO** tant que les blockers de code, les preuves quantitatives et les campagnes opérationnelles décrites ci-dessous ne sont pas terminés.

Ce plan est une procédure d'ingénierie et de contrôle du risque, pas un conseil financier ni une garantie de rendement.

## 2. Comprendre les notions essentielles

### 2.1 Une bonne application ne garantit pas une bonne stratégie

L'application sait déjà construire des targets, limiter les expositions, envoyer des ordres, protéger les fills et réconcilier le broker. Cela réduit le risque opérationnel. Cela ne prouve pas que les prédictions gagnent de l'argent après les coûts.

Une stratégie peut être :

- bien codée mais non rentable ;
- rentable dans un backtest biaisé mais non rentable dans le futur ;
- rentable avant frais mais non rentable après spread, slippage et borrow ;
- rentable en moyenne mais exposée à un drawdown trop important ;
- rentable offline mais mal exécutée par le broker.

Le plan traite séparément chacune de ces possibilités.

### 2.2 Définition simple des principales métriques

| Métrique | Explication simple | Pourquoi elle compte |
|---|---|---|
| Rendement net | Gain ou perte après tous les coûts | Un rendement brut ne paie pas les frais réels |
| Sharpe | Rendement obtenu par unité de variabilité | Évite de préférer un gain obtenu avec un risque excessif |
| Sortino | Similaire au Sharpe, mais pénalise surtout les baisses | Plus proche de la perception réelle du risque |
| Drawdown maximal | Plus forte baisse depuis un sommet du portefeuille | Mesure la perte qu'il faut psychologiquement et financièrement supporter |
| Profit factor | Gains bruts divisés par pertes brutes | Au-dessus de 1, la somme des gains dépasse la somme des pertes |
| Win rate | Pourcentage de trades gagnants | Ne suffit jamais seul : un système peut gagner souvent et perdre énormément rarement |
| Payoff | Gain moyen divisé par perte moyenne | Complète le win rate |
| Stabilité des folds | Proportion de périodes OOS positives | Détecte une performance concentrée sur une seule période favorable |
| Deflated Sharpe | Sharpe corrigé du nombre d'essais réalisés | Réduit le risque d'avoir trouvé un bon résultat par hasard |
| Coûts/alpha | Part de l'avantage brut consommée par les coûts | Un ratio trop élevé rend l'avantage fragile |
| Slippage | Écart défavorable entre prix de décision et prix réellement exécuté | Mesure la différence entre théorie et broker |

### 2.3 Le budget de risque n'est pas le capital investi

Le `base_risk_budget` de campagne représente le **montant de perte accepté par position au stop**, pas la valeur totale du compte et pas le notionnel acheté.

Exemple pédagogique :

- equity du compte : 100 000 USD ;
- budget nominal de risque par position : 1 000 USD ;
- palier live 5 % : budget effectif de 50 USD par position ;
- distance entre entrée et stop : 2 USD par action ;
- quantité théorique limitée par le risque : $50 / 2 = 25$ actions.

Les plafonds de poids, secteur, ADV, cash et buying power peuvent encore réduire cette quantité.

## 3. Règle de gouvernance générale

Une phase est terminée uniquement si les trois éléments suivants existent :

1. **Code raccordé** : le chemin runtime utilise réellement le contrôle.
2. **Test exécutable** : un test peut falsifier le comportement attendu.
3. **Preuve archivée** : un artefact daté montre que le contrôle a fonctionné sur le run concerné.

Une case verte dans l'IHM, un test unitaire ou l'existence d'un fichier Python ne remplace pas une preuve de campagne.

Principes obligatoires :

- aucune modification de modèle, features, labels, seuils ou coûts pendant une campagne ;
- aucun ajustement après lecture du holdout final ;
- aucune promotion automatique vers du capital réel ;
- aucun `--skip-preflight` en paper de validation ou en live ;
- aucun fallback score-only si le ML est absent ;
- aucune donnée actuelle utilisée pour réparer silencieusement une date historique ;
- aucun secret, token ou clé copié dans ce document, Git ou un artefact de commande ;
- toute anomalie non expliquée produit un NO-GO ou prolonge la phase.

## 4. Blockers de code à fermer avant la campagne officielle

Ces points viennent du code source actuel et doivent être corrigés avant de démarrer le chronomètre des quatre semaines shadow.

### 4.1 Compatibilité ML complète et fail-closed

**État actuel :** `modelFactory/predictor.py` valide déjà la signature des artefacts et le contrat de features. En revanche, `risk_management.cli._check_model_compatibility()` considère encore un registre absent ou illisible comme compatible.

**Action :** construire un contrat unique de publication vérifiant au minimum :

- identité et statut du champion ;
- modèle et hash du modèle ;
- calibrateur attendu, présent et signé ;
- version et fingerprint de la policy ternaire ;
- feature schema et ordre des colonnes ;
- scaler et feature fingerprint ;
- fingerprint ou lineage des données d'entraînement ;
- architecture et route d'inférence sélectionnées ;
- absence de statut `DEGRADED` ou `RETIRED` ;
- cohérence entre `model_run_id` de la prédiction et champion publié.

**Comportement requis :** toute preuve absente, illisible ou incohérente bloque les nouvelles entrées. Les positions déjà ouvertes continuent d'être protégées et peuvent être clôturées.

**Tests requis :** modèle absent, calibrateur absent, policy différente, feature déplacée, fingerprint différent, registre corrompu, modèle retired et cas nominal complet.

### 4.2 Raccorder le shadow compare à la campagne

**État actuel :** le résumé produit par `risk_management.cli` contient `shadow_compare`, mais `CampaignOrchestrator` attend séparément `daily/<date>/shadow_compare.json` et ne l'extrait pas du résumé.

**Action :** après lecture de `risk_run_summary.json`, valider le bloc `shadow_compare`, le normaliser puis l'écrire atomiquement sous `shadow_compare.json`. Refuser les statuts `missing_reference` et `unavailable` pour une journée déclarée complète.

**Test requis :** un cycle shadow réel simulé par fixtures doit produire le fichier, son hash dans `evidence_manifest.json`, puis être correctement rechargé par une nouvelle instance de l'orchestrateur.

### 4.3 Alimenter le rollback avec le drawdown réel

**État actuel :** `_maybe_auto_rollback()` appelle `check_drawdown_breach(0.0)` et n'est pas appelé dans le cycle quotidien. Le rollback de drawdown est donc présent comme primitive, mais pas comme protection runtime démontrée.

**Action :**

- ajouter au résumé d'exécution/campagne l'equity courante et le high-water mark ;
- calculer le drawdown :

$$
drawdown = \frac{high\ water\ mark-equity\ courante}{high\ water\ mark}
$$

- appeler `_maybe_auto_rollback(result)` après la persistance des métriques quotidiennes ;
- passer le drawdown réel à `check_drawdown_breach()` ;
- journaliser valeur, seuil, source broker et transition ;
- bloquer toute promotion si le drawdown est inconnu.

**Tests requis :** absence de breach, breach au seuil, rollback d'un palier live, incident ouvert, échec de journalisation.

### 4.4 Faire suivre le mode d'exécution lors d'une promotion live

**État actuel :** la transition change `CampaignConfig.run_mode` vers `live`, mais la commande d'exécution est une liste figée. Une commande initialisée avec `run_execution.py paper` reste paper après la promotion.

**Action :** supporter un placeholder explicite `{run_mode}` dans la commande d'exécution, ou construire le mode depuis la phase dans l'orchestrateur. Refuser une journée si le reçu d'entrypoint indique un mode différent du palier attendu.

Exemple de contrat cible :

```json
[".venv\\Scripts\\python.exe", "run_execution.py", "{run_mode}", "--account", "account-id", "--auto-watcher"]
```

**Sécurité supplémentaire :** le passage à `{run_mode}=live` doit encore exiger le preflight, le run plan immuable et l'approbation opérateur. Le token ne doit pas être persisté dans `campaign_config.json` ni dans le reçu de commande.

### 4.5 Prouver le side flip broker de bout en bout

Le code classe maintenant un changement long vers short, ou short vers long, en `side_flip` et soumet d'abord la clôture. Il reste à prouver sur paper :

1. ordre de clôture soumis ;
2. fill de clôture observé ;
3. position broker égale à zéro ;
4. protections anciennes annulées ;
5. nouvel ordre opposé seulement au cycle suivant ;
6. nouvelles protections liées au nouveau fill.

Un ordre net unique de 200 actions pour passer de +100 à -100 est interdit.

### 4.6 Produire automatiquement les métriques de baseline

`scripts/produce_baseline_artifact.py` refuse correctement les placeholders et exige un fichier de métriques réel. Il manque encore un export canonique qui transforme un rapport OOS approuvé en `metrics_by_side.json` sans copie manuelle.

**Action :** ajouter un export signé depuis le rapport walk-forward comprenant au minimum long, short et flat, le nombre d'observations, la période, le modèle, le seed et le fingerprint des données.

### 4.7 Critère de sortie de la phase code

La phase est terminée si :

- tous les tests ciblés passent ;
- les tests risque/exécution/backtesting existants ne régressent pas ;
- une répétition locale complète produit les artefacts attendus ;
- aucun blocker ci-dessus n'est seulement documenté sans raccordement runtime.

## 5. Phase A - Geler la stratégie candidate

### 5.1 But

Empêcher la cible de changer pendant qu'on essaie de la mesurer. Si les règles changent à chaque mauvais résultat, le test final devient une nouvelle phase d'optimisation et perd sa valeur.

### 5.2 Éléments à geler

- commit Git ;
- `config.yaml` et son SHA-256 ;
- univers/preset capital ;
- période de données et fingerprint ;
- feature set et feature schema ;
- label `triple_barrier` et ses trois paramètres ;
- architecture(s) candidate(s) ;
- seeds de reproductibilité ;
- calibrateur ;
- policy ternaire et seuils ;
- capacités long/short ;
- vetos post-ML ;
- sizing et budget de risque ;
- modèle de coûts ;
- TP, stop, trailing et priorité intrabar ;
- règles de borrow et de dividendes short ;
- configuration régime ;
- type de compte et fractionnement.

### 5.3 Découpage temporel recommandé

Choisir des dates adaptées à la profondeur réelle des données. Le principe est plus important que les dates exactes :

| Zone | Usage autorisé | Usage interdit |
|---|---|---|
| Train | Apprentissage des modèles | Mesure finale annoncée |
| Validation | Calibration, seuils, sélection champion | Réentraînement après lecture du test |
| Walk-forward OOS | Mesure répétée dans plusieurs régimes | Optimisation sur les folds futurs |
| Holdout final | Une seule décision finale | Choix de paramètres |

Le holdout doit rester intact jusqu'à ce que toutes les décisions soient gelées.

### 5.4 Artefact de gel

Créer un manifeste sous une arborescence dédiée, par exemple :

```text
artifacts/go_live/<candidate_id>/
    frozen_manifest.json
    commands/
    data_quality/
    training/
    benchmarks/
    walk_forward/
    holdout/
    shadow/
    paper/
    live/
    decisions/
```

`frozen_manifest.json` doit contenir les chemins et hashes, pas les secrets.

## 6. Phase B - Certifier les données PIT

### 6.1 Pourquoi

Le look-ahead est l'utilisation involontaire d'une information future. Il peut rendre un backtest excellent alors que la décision était impossible à prendre à l'époque.

Exemples : composition actuelle de l'univers appliquée à 2022, earnings corrigés après publication, news arrivée après le cutoff ou modèle entraîné avec la période test.

### 6.2 Préparation

1. Importer et nettoyer les barres historiques avec le provider configuré.
2. Backfiller métadonnées, quotes, earnings et données macro nécessaires.
3. Publier les univers historiques `full` pour chaque séance et preset utilisé.
4. Construire les features et scores avec leurs dates `as_of`.
5. Vérifier la couverture des prédictions persistées.

Commande supportée pour reconstruire les scores et univers depuis les barres déjà présentes :

```powershell
python -m backtesting backfill-scores-history `
  --start <YYYY-MM-DD> `
  --end <YYYY-MM-DD> `
  --capital-preset-key <PRESET> `
  --chunk-size 1000 `
  --screener-workers 4
```

Commencer avec `--limit-days 5`, contrôler le résultat, puis élargir. Ne pas utiliser `--overwrite-existing` sans sauvegarde et décision explicite.

### 6.3 Gates de données

Pour chaque séance évaluée :

- univers canonique présent ;
- statut `completed` ;
- qualité `full` ;
- `rows_written == rows_expected` ;
- aucune date as-of postérieure au cutoff ;
- couverture prix/ATR suffisante ;
- couverture ML au moins égale au seuil gelé ;
- macro conforme à la policy PIT ;
- quotes et market cap manquantes explicitement comptées ;
- aucune réparation avec une valeur future.

Les jours non comparables sont exclus avec un motif. Ils ne sont pas remplacés par les données du jour suivant.

## 7. Phase C - Entraîner et challenger le ML

### 7.1 Ce que je ferais maintenant : version concrète

1. Geler une seule définition de stratégie.
2. Entraîner le ternaire triple-barrier sur plusieurs seeds.
3. Comparer LSTM, LightGBM, CatBoost et modèle global quand disponible.
4. Conserver un benchmark simple qui ne dépend pas du ML complexe.
5. Choisir le champion uniquement sur validation et walk-forward.
6. Ne regarder le holdout final qu'après le gel complet.

### 7.2 Commande d'entraînement supportée

Les symboles après `--symbols` sont séparés par des espaces, pas par des virgules. Pour utiliser l'univers canonique, omettre `--symbols`.

```powershell
python -m modelFactory `
  --mode train `
  --symbol-source tradable-universe `
  --universe-date <YYYY-MM-DD> `
  --training-start-date <YYYY-MM-DD> `
  --training-end-date <YYYY-MM-DD> `
  --target-mode ternary `
  --num-classes 3 `
  --label-method triple_barrier `
  --triple-barrier-stop-atr-mult 2.0 `
  --triple-barrier-tp-atr-mult 3.0 `
  --triple-barrier-max-sessions 20 `
  --feature-set expert `
  --walkforward `
  --wf-min-train-size 504 `
  --wf-val-size 126 `
  --wf-test-size 126 `
  --wf-step-size 126 `
  --wf-max-splits 3 `
  --compare-lightgbm `
  --enable-catboost `
  --enable-global-model `
  --select-champion `
  --champion-min-runs <N> `
  --champion-min-days <N> `
  --seed <SEED> `
  --deterministic `
  --artifacts-dir artifacts/go_live/<candidate_id>/training/seed_<SEED>
```

Utiliser au moins cinq seeds prédéclarés, par exemple `11, 23, 42, 71, 101`. Ce choix doit être fait avant lecture des résultats.

### 7.3 Attention à l'optimisation

`--optimize-target` et `--optimize-thresholds` utilisent les données d'entraînement/validation. Ils ne doivent jamais être relancés après observation du holdout final.

Pour une première certification, il est plus simple de :

- sélectionner les barrières sur les folds train/validation ;
- geler les valeurs gagnantes ;
- réentraîner chaque seed avec ces valeurs ;
- évaluer le holdout une seule fois.

### 7.4 Benchmarks obligatoires

Comparer le champion à des règles compréhensibles :

- toujours flat ;
- momentum simple ;
- breakout simple ;
- LightGBM ;
- CatBoost ;
- LSTM ;
- éventuellement buy-and-hold SPY comme contexte, sans prétendre qu'il a le même risque.

Le modèle le plus complexe ne gagne pas par défaut. S'il ne dépasse pas durablement une baseline simple après coûts, préférer la baseline ou rester en recherche.

### 7.5 Analyse par sous-population

Rapporter séparément :

- long et short ;
- années ;
- régimes normal, préservation du capital et cash-only ;
- secteurs ;
- déciles de conviction ;
- petites, moyennes et grandes liquidités ;
- périodes de forte volatilité ;
- modèle et seed.

Un bon résultat global ne doit pas masquer une jambe short durablement déficiente. Si le short échoue, le désactiver (`max_short_positions=0`) sans retarder nécessairement la validation du long.

## 8. Phase D - Walk-forward financier et holdout

### 8.1 Deux validations complémentaires

1. Le walk-forward du trainer teste la stabilité de l'apprentissage.
2. `walk-forward-financial` teste le portefeuille et le risque à partir des scores, prédictions et OHLCV persistés.

Le second ne réentraîne pas automatiquement le modèle à chaque fold. Il faut donc préparer des prédictions strictement PIT avant de présenter son rapport comme une preuve ML hors échantillon.

### 8.2 Commande walk-forward financier

```powershell
python -m backtesting walk-forward-financial `
  --start <YYYY-MM-DD> `
  --end <YYYY-MM-DD> `
  --equity <EQUITY> `
  --commission-bps 5 `
  --slippage-bps 5 `
  --train-days 504 `
  --val-days 126 `
  --test-days 126 `
  --step-days 126 `
  --purge-days 20 `
  --embargo-days 10 `
  --max-positions <MAX_POSITIONS> `
  --n-trials <NOMBRE_TOTAL_ESSAIS> `
  --output artifacts/go_live/<candidate_id>/walk_forward/report.json
```

Pour un label triple-barrier de 20 séances, utiliser une purge au moins égale à l'horizon maximal effectivement servi. `--n-trials` doit refléter le nombre d'essais réellement réalisés, pas une valeur artificiellement basse.

### 8.3 Backtest de parité production

Après le walk-forward financier, exécuter le pipeline complet avec les phases risk/exécution/protection :

```powershell
python -m backtesting run `
  --start <YYYY-MM-DD> `
  --end <YYYY-MM-DD> `
  --equity <EQUITY> `
  --capital-preset-key <PRESET> `
  --profile production-parity `
  --engine-mode pipeline `
  --scores-pit-mode exact `
  --macro-pit-mode j_minus_1_strict `
  --ml-pit-strategy use-persisted `
  --phase2-mode risk_execution `
  --phase3-mode execution_replay `
  --phase4-mode protection_replay `
  --phase5-mode watcher_replay `
  --phase7-mode exit_lifecycle_replay `
  --min-ml-coverage-ratio 0.80 `
  --swing-only `
  --intrabar-priority conservative `
  --bootstrap-samples 1000 `
  --sensitivity-analysis `
  --output-dir artifacts/go_live/<candidate_id>/holdout/production_parity
```

Les coûts explicites doivent correspondre au compte et au segment réellement tradés. Ne pas désactiver le spread réel pour améliorer le résultat.

### 8.4 Gates quantitatifs obligatoires déjà codés

Le rapport `walk-forward-financial` calcule les gates suivants :

| Gate | Seuil minimal |
|---|---:|
| Folds OOS positifs nets de coûts | ≥ 70 % |
| Sharpe OOS médian | ≥ 1,0 |
| 25e percentile du Sharpe | > 0 |
| Profit factor médian | ≥ 1,20 |
| Coûts / alpha brut | ≤ 35 % |
| Deflated Sharpe | significatif, p < 0,05 |
| Score composite de promotion | ≥ 0,60 |

Tous doivent passer. Il ne faut pas compenser un gate rouge par une moyenne subjective.

### 8.5 Gates supplémentaires recommandés

- intervalle bootstrap bas du Sharpe supérieur à 0 ;
- drawdown compatible avec le capital et la tolérance définie avant le test ;
- aucune année ou régime représentant seul l'essentiel du profit ;
- aucun trade unique représentant plus de 10 % du PnL total ;
- long et short analysés séparément ;
- performance encore acceptable avec coûts augmentés de 50 % ;
- performance encore acceptable avec entrée retardée d'une séance ou slippage dégradé ;
- absence de fuite détectée par les audits PIT ;
- couverture ML suffisante sur chaque fold, pas seulement en moyenne.

### 8.6 Baseline réelle

Une fois les métriques OOS approuvées exportées :

```powershell
python scripts/produce_baseline_artifact.py `
  --start <YYYY-MM-DD> `
  --end <YYYY-MM-DD> `
  --symbols SPY,XLF,XLK,XLE,XLV,XLI,XLY,XLP,XLU,XLB,XLRE,XLC `
  --seed <SEED> `
  --metrics-json artifacts/go_live/<candidate_id>/benchmarks/metrics_by_side.json `
  --data-fingerprint <DATA_FINGERPRINT>
```

Le fichier de métriques doit être généré depuis le rapport, pas saisi à la main.

### 8.7 Décision à la fin de la phase D

- Un seul gate obligatoire rouge : **NO-GO**, retour en recherche avec un nouveau `candidate_id`.
- Tous les gates verts mais résultat fragile aux coûts : **NO-GO live**, shadow possible pour collecte.
- Tous les gates verts et robustesse acceptable : **GO shadow**.

## 9. Phase E - Campagne shadow de quatre semaines

### 9.1 But

Le shadow vérifie les décisions quotidiennes sur des données arrivant réellement, sans envoyer d'ordre. Il ne sert pas à prouver la rentabilité à lui seul. Il détecte surtout : données en retard, modèle indisponible, différences de configuration, erreurs de calendrier et dérive entre le replay attendu et le runtime.

### 9.2 Configuration préalable

- modèle, calibrateur et config gelés ;
- commandes campagne validées ;
- `ALPHA_TRADE_CAMPAIGN_SIGNING_KEY` configurée hors Git ;
- compte paper configuré pour la phase suivante ;
- scheduler supervisé ;
- stockage des artefacts sauvegardé ;
- personne responsable identifiée ;
- auto-promotion désactivée.

Exemple PowerShell après correction des blockers de campagne :

```powershell
$riskCommand = '[".venv\\Scripts\\python.exe","-m","risk_management","--account","default"]'
$executionCommand = '[".venv\\Scripts\\python.exe","run_execution.py","{run_mode}","--account","paper-account","--auto-watcher"]'

python scripts/run_campaign.py init `
  --campaign-id <CANDIDATE_ID>_shadow `
  --phase shadow `
  --model-run-id <MODEL_RUN_ID> `
  --policy-version <POLICY_VERSION> `
  --config-fingerprint <CONFIG_FINGERPRINT> `
  --approved-by <OPERATEUR> `
  --base-risk-budget <BUDGET_RISQUE_NOMINAL_USD> `
  --risk-command-json $riskCommand `
  --execution-command-json $executionCommand `
  --frozen-model-path <MODEL_PATH> `
  --frozen-calibrator-path <CALIBRATOR_PATH> `
  --frozen-config-path <CONFIG_PATH>
```

Ne pas ajouter `--auto-promote`.

### 9.3 Cycle quotidien

Après clôture et disponibilité de toutes les données :

```powershell
python scripts/run_campaign.py daily `
  --campaign-id <CANDIDATE_ID>_shadow `
  --trade-date <YYYY-MM-DD>
```

Contrôler chaque jour :

- résultat `completed` ;
- univers `full` ;
- couverture ML ;
- compatibilité modèle ;
- fraîcheur prix/news/macro ;
- distribution long/flat/short ;
- nombre de targets ;
- absence de fallback ;
- `shadow_compare.status == compared` ;
- divergence expliquée ;
- signature HMAC et hashes du manifeste ;
- absence d'incident ouvert.

### 9.4 Revue hebdomadaire

Le code génère une revue tous les cinq jours de campagne. Ajouter une revue humaine qui répond :

1. Le système a-t-il tourné chaque séance prévue ?
2. Les jours manquants sont-ils expliqués ?
3. La distribution des classes est-elle plausible ?
4. Les changements de régime sont-ils cohérents ?
5. Les nouvelles données ont-elles modifié le taux de couverture ?
6. Les décisions seraient-elles exécutables en pratique ?
7. Un changement de code/config a-t-il eu lieu ?

Tout changement de stratégie redémarre les quatre semaines, sauf correction opérationnelle sans impact décisionnel démontré.

### 9.5 Gate GO paper

- au moins 28 jours calendaires et quatre semaines complètes ;
- aucun artefact quotidien requis manquant ;
- aucune violation du gel ;
- aucune divergence de côté inexpliquée ;
- couverture de protection théorique complète ;
- aucune incompatibilité modèle ;
- réconciliation logique propre ;
- revue humaine signée ;
- rapport campagne `can_promote=true`.

Rapport et promotion :

```powershell
python scripts/run_campaign.py report `
  --campaign-id <CANDIDATE_ID>_shadow `
  --output artifacts/go_live/<candidate_id>/shadow/campaign_report.json

python scripts/run_campaign.py promote `
  --campaign-id <CANDIDATE_ID>_shadow `
  --approved-by <REVIEWER> `
  --reason "Quatre semaines shadow complètes, gates documentés"
```

## 10. Phase F - Campagne paper de huit à douze semaines

### 10.1 But

Le paper vérifie le comportement avec un broker : acceptation des ordres, fills partiels, horaires, buying power, protections, side flips, watcher et réconciliation. Il ne remplace toujours pas la preuve statistique OOS.

### 10.2 Préflight paper

```powershell
python scripts/run_pre_live_checklist.py `
  --account <PAPER_ACCOUNT> `
  --broker-mode paper
```

Un `warn` ou `skip` doit être lu et accepté explicitement ; le simple booléen `passed` n'est pas suffisant pour une campagne de certification.

### 10.3 Exécution quotidienne

La commande `daily` réutilise la campagne promue. Vérifier dans le reçu que l'exécution est réellement `paper`.

Chaque jour, contrôler dans cet ordre :

1. target risk ;
2. intent local ;
3. ordre broker ;
4. fill ou rejet ;
5. position/lots ;
6. protections ouvertes ;
7. watcher ;
8. cash et PnL internes ;
9. positions/cash/PnL broker ;
10. réconciliation.

### 10.4 Réconciliation J+1

Utiliser le module canonique. Le wrapper `scripts/run_broker_reconciliation.py` ne résout actuellement pas correctement la racine du dépôt lorsqu'il est lancé directement et doit être corrigé séparément.

```powershell
python -m execution_engine.reconcile_statement `
  --account <PAPER_ACCOUNT> `
  --broker-mode paper `
  --trade-date <YYYY-MM-DD> `
  --report-out artifacts/go_live/<candidate_id>/paper/reconciliation_<YYYY-MM-DD>.json
```

Le rapport doit rapprocher intentions, soumissions, fills, positions, protections, cash et PnL. Une différence non expliquée bloque la promotion.

### 10.5 Critères opérationnels paper

Obligatoires :

- durée minimale : 56 jours, prolongation possible jusqu'à 12 semaines ;
- 100 % des fills exposés couverts par une protection broker valide ;
- aucune position orpheline ;
- aucun ordre dupliqué ;
- aucun fill absent du ledger ;
- aucune divergence cash/position non expliquée à J+1 ;
- aucun side flip net ambigu ;
- force-close testé volontairement sur compte paper ;
- kill switch testé ;
- rollback modèle testé ;
- relance après interruption testée ;
- alertes réellement reçues par l'opérateur ;
- slippage paper comparé au modèle par liquidité et par côté ;
- incidents clôturés avec cause racine.

Recommandation de volume d'observation : obtenir au moins 20 fills protégés et plusieurs sorties complètes. Si la stratégie trade moins, prolonger le paper ; ne pas abaisser les seuils pour fabriquer des trades.

### 10.6 Gate GO live 5 %

Le GO live 5 % exige simultanément :

- tous les gates quantitatifs toujours verts ;
- campagne shadow acceptée ;
- campagne paper acceptée ;
- preflight live complet avec réseau ;
- zéro incident critique ouvert ;
- dernier rapprochement J+1 propre ;
- modèle et config toujours gelés ;
- rapport de compatibilité ML complet ;
- revue humaine signée par au moins une personne autre que l'auteur du dernier changement quand cela est possible ;
- procédure d'arrêt répétée en paper ;
- perte maximale quotidienne et drawdown acceptés par écrit.

## 11. Phase G - GO live 5 %

### 11.1 Préparation le jour du lancement

1. Vérifier calendrier marché, earnings et événements exceptionnels.
2. Vérifier le compte et le mode `live`.
3. Exécuter un paper/dry-run récent, requis par le preflight.
4. Exécuter le preflight sans `--skip-network`.
5. Lire chaque check, y compris `warn` et `skip`.
6. Vérifier le run plan immuable.
7. Vérifier le palier et le budget effectif.
8. Faire approuver humainement.

```powershell
python scripts/run_pre_live_checklist.py `
  --account <LIVE_ACCOUNT> `
  --broker-mode live `
  --max-dry-run-age-hours 24
```

### 11.2 Lancement recommandé

Pour le premier lancement, préférer le menu interactif afin que le token ne soit pas placé dans l'historique shell :

```powershell
python run_execution.py
```

Choisir live, ressaisir le label exact du compte, répondre `oui`, puis saisir le token lorsqu'il est demandé. Ne jamais utiliser `--skip-preflight`.

Le `run-plan-file` doit figer les paramètres du run. Une modification du plan existant doit être refusée par le runtime.

### 11.3 Surveillance immédiate

Pendant et après le run :

- vérifier chaque ordre soumis ;
- confirmer les fills ;
- confirmer les protections sur la quantité réellement remplie ;
- vérifier le heartbeat du watcher ;
- surveiller cash, buying power et positions broker ;
- vérifier les alertes ;
- produire la réconciliation le jour même puis J+1 ;
- consigner toute intervention manuelle.

### 11.4 Arrêt immédiat obligatoire

Déclencher le kill switch et ne pas relancer si :

- protection absente ou invalide ;
- position broker inconnue de l'OMS ;
- ordre dupliqué ;
- mauvais côté ou mauvaise quantité ;
- divergence cash/position inexpliquée ;
- donnée future ou modèle incompatible détecté ;
- watcher sans heartbeat ;
- perte journalière ou drawdown au-delà du seuil ;
- clé, compte ou mode douteux ;
- comportement non couvert par la procédure.

La priorité est : empêcher de nouvelles entrées, protéger ou clôturer les positions existantes, réconcilier, puis comprendre.

## 12. Phase H - Ramp-up 5 % vers 100 %

Le code définit les paliers et durées minimales suivants :

| Palier | Budget effectif | Durée minimale | Drawdown maximal codé |
|---|---:|---:|---:|
| Shadow | 0 % | 28 jours | non applicable |
| Paper | 0 % | 56 jours | non applicable |
| Live 5 % | 5 % | 14 jours | 5 % |
| Live 10 % | 10 % | 21 jours | 5 % |
| Live 25 % | 25 % | 30 jours | 10 % |
| Live 50 % | 50 % | 45 jours | 10 % |
| Live 100 % | 100 % | maintien | 15 % |

Ces seuils de drawdown sont des plafonds techniques, pas des objectifs. Une perte inférieure peut justifier un rollback si elle révèle un défaut structurel.

Avant chaque promotion :

- durée minimale atteinte ;
- checklist verte ;
- aucune divergence de réconciliation ;
- aucune protection manquante ;
- aucun incident critique ouvert ;
- métriques live compatibles avec les bandes prévues par l'OOS et le paper ;
- slippage et coûts acceptables ;
- modèle sans drift bloquant ;
- revue humaine documentée ;
- transition écrite dans `ramp_up_journal.json`.

Ne jamais sauter un palier. Une promotion augmente le budget de risque, pas la confiance dans le modèle.

Durée minimale théorique jusqu'au live 100 %, sans incident ni prolongation :

$$
28+56+14+21+30+45=194\ jours
$$

Soit environ 28 semaines avant l'entrée au palier 100 %. Cette lenteur est volontaire.

## 13. Rollback et reprise

### 13.1 Rollback modèle

```powershell
python scripts/rollback_model_registry.py `
  --symbol <SYMBOL> `
  --reason "<CAUSE_DOCUMENTEE>" `
  --operator <OPERATEUR>
```

Après rollback : bloquer les nouvelles entrées du symbole, vérifier le journal, refaire une prédiction shadow et ne reprendre qu'après compatibilité complète.

### 13.2 Rollback de palier

Un breach de drawdown ou un incident critique doit ramener au palier précédent. Selon la cause, revenir directement à paper ou shadow est préférable à une simple réduction de 50 % vers 25 %.

### 13.3 Reprise après incident

Exiger :

1. cause racine identifiée ;
2. positions et cash réconciliés ;
3. correctif testé ;
4. replay de l'incident ;
5. paper de non-régression ;
6. approbation humaine ;
7. nouveau manifeste de campagne si le comportement décisionnel change.

## 14. Contenu minimal du dossier de preuve

Pour chaque candidat ou campagne, conserver :

- manifeste gelé et hashes ;
- commit Git et diff propre ;
- rapport qualité et couverture PIT ;
- commandes exactes sans secrets ;
- rapports d'entraînement par seed ;
- classement champion/challengers ;
- baseline réelle ;
- walk-forward financier ;
- bootstrap et sensibilité ;
- rapport holdout ;
- résultats par côté/régime/année ;
- configuration de coûts ;
- rapports shadow quotidiens et hebdomadaires ;
- reçus d'entrypoints et manifests signés ;
- rapports paper et réconciliations J+1 ;
- tests de kill switch, force-close, side flip et rollback ;
- preflight live ;
- journal de ramp-up ;
- incidents et postmortems ;
- décision humaine GO/NO-GO datée.

Les secrets ne doivent jamais apparaître dans ces artefacts.

## 15. Matrice finale GO/NO-GO

| Domaine | Condition GO | Sinon |
|---|---|---|
| Code | Blockers section 4 fermés et testés | NO-GO shadow officiel |
| Données | PIT complet, frais, cutoff et fingerprints prouvés | NO-GO quantitatif |
| ML | Champion compatible, calibré, stable multi-seeds | Retour recherche |
| OOS | Tous les gates walk-forward verts | Retour recherche |
| Robustesse | Coûts dégradés et sensibilité acceptables | NO-GO live |
| Shadow | 4 semaines complètes sans divergence inexpliquée | Prolonger/recommencer |
| Paper | 8 à 12 semaines, protections et réconciliation propres | Prolonger/rollback |
| Preflight | Aucun fail, warns/skips acceptés explicitement | NO-GO live |
| Incidents | Aucun incident critique ouvert | NO-GO promotion |
| Approbation | Revue humaine et journal présents | NO-GO promotion |
| Live | Palier courant et budget effectif vérifiés | Arrêt immédiat |

## 16. Ordre prioritaire des actions

### Maintenant

1. Fermer les blockers de code de la section 4.
2. Geler une stratégie candidate et créer son manifeste.
3. Auditer puis compléter les données PIT.
4. Entraîner les seeds et challengers sans toucher au holdout.
5. Produire le walk-forward financier et le backtest production-parity.
6. Générer la baseline réelle depuis les métriques OOS.

### Après preuve quantitative

7. Lancer quatre semaines shadow.
8. Revoir les résultats chaque semaine sans modifier la stratégie.
9. Promouvoir vers huit à douze semaines paper.
10. Tester volontairement les scénarios opérationnels dangereux.

### Après preuve paper

11. Exécuter le preflight live complet.
12. Obtenir une approbation humaine documentée.
13. Lancer live 5 % avec surveillance renforcée.
14. Respecter chaque durée de palier et rollback au premier breach.

## 17. Définition finale du GO live

Le **GO live 5 %** peut être prononcé uniquement lorsque :

- la stratégie gelée est promotable selon le rapport OOS ;
- le holdout reste intact et réussi ;
- le modèle est compatible et servi en échec fermé ;
- la campagne shadow est complète ;
- la campagne paper est complète ;
- OMS, protections, watcher, ledger et broker convergent ;
- les procédures d'arrêt et de rollback ont été réellement testées ;
- le preflight live est vert ;
- aucun incident critique n'est ouvert ;
- un humain accepte explicitement le risque résiduel ;
- le premier budget effectif correspond exactement au palier 5 %.

Le **GO live 100 %** n'est pas obtenu au premier ordre réel. Il est obtenu seulement après le passage documenté de tous les paliers et la stabilité des preuves live.

La question finale n'est donc pas « l'application peut-elle envoyer un ordre ? », mais :

> La stratégie a-t-elle démontré un avantage net hors échantillon, et l'organisation a-t-elle démontré qu'elle peut exécuter, surveiller, arrêter et expliquer chaque position sans perdre le contrôle ?

Si la réponse n'est pas prouvée par les artefacts, la décision reste NO-GO.