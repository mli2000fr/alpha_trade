# Bundle Oracle Extreme + Per-Symbol LONG/SHORT

## Objectif et responsabilités

Ce mode sépare explicitement amplitude et direction dans une seule campagne ML. Chacune des trois branches possède un profil de features indépendant :

```text
                          batch_id unique
                                │
                     Oracle Extreme O0
                  Walk-Forward → scores OOF
                                │
                     TOP20 de chaque date
                                │
                population directionnelle PIT
                         ┌──────┴──────┐
                         │             │
                  branche LONG   branche SHORT
                  profil LONG    profil SHORT
                         └──────┬──────┘
                                │
                    arbitrage / abstention
                                │
                       candidats de backtest
```

- l'Oracle Extreme détecte les mouvements d'amplitude inhabituelle sans imposer leur sens ;
- le champion LONG estime la probabilité haussière, uniquement sur la population d'événements que l'Oracle aurait effectivement proposée hors échantillon ;
- le champion SHORT estime la probabilité baissière sur cette même population conditionnelle, avec un autre contrat de features ;
- les trois composants portent le même `batch_id`.

Le mode est activé par `--directional-feature-profiles`. Sans ce drapeau, le contrat historique — un champion ternaire Per-Symbol par symbole — reste inchangé.

## Contrat des cibles : binaire pour l'Oracle, ternaire pour la direction

Le bundle n'utilise volontairement pas la même cible pour ses trois composants :

| Composant | Type de cible | Classes / sortie | Rôle |
|---|---|---|---|
| Oracle O0 | classification binaire interne | `extreme` / `non-extreme`, avec `proba_extreme` | détecter l'amplitude extrême |
| branche LONG | classification ternaire | SHORT / FLAT / LONG | fournir `proba_long` |
| branche SHORT | classification ternaire | SHORT / FLAT / LONG | fournir `proba_short` |

L'Oracle O0 **n'est donc pas un modèle de régression**. Il construit sa cible `oracle_extreme10` à partir des extrêmes cross-sectionnels et entraîne son classifieur binaire indépendamment du champ global `target_mode`.

En mode bundle, le backend impose désormais un contrat directionnel unique aux deux branches, même si une ancienne commande, une session IHM ou une API transmet des valeurs contradictoires :

```text
rendement absolu H20 = AdjClose(t + 20 séances) / AdjClose(t) - 1

SHORT : rendement < -3 %
FLAT  : -3 % <= rendement <= +3 %
LONG  : rendement > +3 %
```

Les branches sont donc toujours en `target_mode=ternary`, `num_classes=3`, `label_method=fixed_horizon`, horizon unique H20 et seuils absolus `-0.03/+0.03`. Le multi-horizon, l'excès relatif à SPY, les cibles intra-secteur, la normalisation optionnelle de cible et l'optimisation automatique de cible sont neutralisés. Ces options répondent à d'autres missions ML et rendraient la signification de `proba_long` et `proba_short` ambiguë dans ce bundle.

Le verrouillage existe à trois niveaux : formulaire IHM, génération de commande et configuration effective de chaque profil. Il ne repose donc pas uniquement sur l'état visible d'une case à cocher. Le manifeste et chaque configuration de branche permettent d'auditer le contrat réellement exécuté.

Le modèle Global Ranking n'appartient pas à ce bundle et n'est requis ni à l'entraînement O0 ni à la prédiction. Le préremplissage `global_rank_20` est donc désactivé pour ce parcours. Les autres campagnes Global Ranking demeurent inchangées.

## Population d'entraînement conditionnelle — étape 3

Les branches directionnelles ne sont plus entraînées comme des classifieurs génériques sur toutes les journées. Leur mission est maintenant exactement celle du serving : répondre à la question « parmi les candidats retenus par l'Oracle Extreme, quel est le sens probable du mouvement ? ».

L'ordre d'entraînement est bloquant :

```text
1. entraîner Oracle O0 sur ses folds causaux
2. collecter uniquement les prédictions des fenêtres TEST de chaque fold
3. calculer le percentile de proba_extreme séparément pour chaque date
4. marquer éligibles les rangs >= 0,80, soit la convention TOP20 du moteur
5. entraîner LONG et SHORT en n'autorisant que ces lignes comme endpoints
```

Un score recalculé avec le champion Oracle final sur sa propre période d'apprentissage n'est jamais accepté pour construire cette population. Chaque ligne du cache doit posséder un `fold_start`, qui trace son origine Walk-Forward. Les colonnes futures de l'Oracle (`future_return`, label réalisé) ne sont pas copiées dans le cache directionnel.

À l'intérieur de chaque fold Oracle, les trois partitions ont des fonctions distinctes : `train` ajuste LightGBM, `validation` pilote son early stopping et `test` produit le score OOF. Les labels de validation doivent être disponibles avant le début du test ; le test n'est passé à aucune API d'entraînement. Cette séparation est indispensable puisque ses scores deviennent ensuite des données d'entrée pour l'apprentissage directionnel.

Le cache `<batch_id>/_oracle_oof_gate.parquet` contient uniquement : date, symbole, probabilité Oracle OOF, percentile du jour, décision de gate et fold d'origine. Son fichier compagnon `_oracle_oof_gate.json` donne la couverture, la période, le nombre de symboles et la fraction retenue. Le manifeste expose la même synthèse sous `directional_conditioning`.

### Continuité des séquences LSTM

Filtrer physiquement les journées TOP20 avant de construire les séquences créerait un faux calendrier : deux observations consécutives pourraient être séparées de plusieurs semaines. Le pipeline conserve donc toutes les journées et toutes les features dans la fenêtre de 40 séances, mais limite les fins de séquence portant une cible :

```text
J-39 ─────────────────────────────────────────────── J
        historique quotidien complet                 │
                                                     └─ exemple appris
                                                        seulement si Oracle OOF TOP20 à J
```

LightGBM et CatBoost ne consomment pas de séquences. Pour eux, les frontières train/validation/test sont d'abord calculées sur le calendrier complet, avec purge H20, puis seules les lignes éligibles sont gardées dans chaque partition. Les trois architectures évaluent ainsi la même mission conditionnelle sans déplacer rétroactivement les frontières temporelles.

`proba_extreme` et son percentile sont conservés pour l'audit du gate, mais ne sont pas ajoutés aux features LONG/SHORT dans cette première version. Cela isole l'effet « population conditionnelle » et évite d'introduire une dépendance supplémentaire dans le serving. Leur ajout comme features devra faire l'objet d'une expérience séparée.

Si l'Oracle échoue, ne produit aucun fold OOF, ne produit aucun candidat ou si le cache est absent, le bundle s'arrête avant le premier entraînement directionnel. Il n'existe aucun fallback vers un entraînement générique, car celui-ci changerait silencieusement la mission du modèle.

### Taille minimale de l'univers Oracle

Les labels O0 sont des rangs cross-sectionnels TOP/BOTTOM 10 %. Ils exigent au moins **20 symboles disposant d'un rendement futur exploitable pour une même date**. Un bundle dont l'univers total contient moins de 20 symboles est maintenant refusé avant tout entraînement avec `insufficient_oracle_universe`, afin de ne pas dépenser du temps sur les branches LONG/SHORT d'un batch qui ne pourra jamais être servi.

Le seuil de 20 est un minimum technique, pas une recommandation de campagne. Pour un smoke test, prévoir au moins 25 à 30 titres avec suffisamment d'historique pour absorber les exclusions et les données manquantes. Après construction, les lignes sans cible binaire sont retirées du dataset Oracle. Si aucune cible ne reste, le batch échoue explicitement avec `no_labeled_oracle_targets` ; aucune conversion de valeur `NULL` en entier n'est tentée.

## Contrat et découverte des profils

Les profils sont découverts dynamiquement dans `config/features/oracle/*.json`, `config/features/long/*.json` et `config/features/short/*.json`. L'IHM choisit `oracle.json`, `long.json` et `short.json` par défaut lorsqu'ils existent.

Un profil contient obligatoirement `schema_version: 1`, une `direction` cohérente avec son répertoire, `feature_set`, une liste `feature_columns` ordonnée, non vide et sans doublon, les `generator_options` nécessaires au calcul des colonnes, et une provenance expérimentale.

Le chargeur refuse les chemins relatifs ou traversants, une mauvaise direction, un schéma inconnu, une liste vide et les doublons. Le contenu brut reçoit une empreinte SHA-256. Une copie résolue est figée dans les artefacts du batch : modifier plus tard le fichier de configuration ne change pas le contrat historique du modèle.

### Profils livrés

- `oracle/oracle.json` : contrat canonique O0 dédupliqué, 124 features EXPERT et 44 rangs cross-sectionnels, sans `global_rank_20` ni les deux extras O1, soit 168 colonnes ordonnées. Les cinq alias bruts `distance_ema20`, `distance_ema50`, `return_5d`, `return_10d`, `return_20d` et le rang redondant `log_return_xs_rank` sont exclus ;
- `long/long.json` : contrat LONG confirmé du batch `model-factory-20260902052533-998d3a`, 84 features EXPERT, après ablation et confirmation sur 300 symboles.
- `short/short.json` : contrat SHORT confirmé du batch `model-factory-20260901180312-2d74f9`, 130 features EXPERT avec MOVE. `include_macro_move=true` est indispensable : mettre `move_close` dans une whitelist ne calcule pas sa source à lui seul.

En prédiction historique, les sorties Oracle sont persistées par défaut tous les 20 jours de marché. Chaque lot possède sa propre transaction et devient immédiatement visible dans la page Diagnostic ML. Une interruption conserve donc les lots déjà écrits et une relance les met à jour sans doublon grâce à la clé `(prediction_date, symbol, batch_id)`. Le tableau des périodes Oracle exécute son agrégation à chaque clic afin d'afficher cette progression sans le délai du cache général.

Les performances historiques constituent la provenance du profil, pas une garantie. Une modification d'univers, d'horizon, de seuil de label ou de période exige une nouvelle validation OOS.

## Comportement de l'IHM

La case « Bundle Oracle + deux modèles Per-Symbol LONG/SHORT » :

1. affiche les profils Oracle, LONG et SHORT détectés sur disque ;
2. désactive les cases manuelles de features afin d'éviter deux sources de vérité ;
3. verrouille visuellement la cible sur **Ternaire — SHORT / FLAT / LONG**, le rendement absolu H20 et les seuils `-3 %/+3 %` ; walk-forward, epochs, patience, challengers et sélection du champion restent réglables ;
4. émet `--directional-feature-profiles`, `--long-feature-profile` et `--short-feature-profile` ;
5. active l'Oracle et force le mode Per-Symbol côté backend ;
6. neutralise `oracle_model_only` et `exclude_per_symbol_per_sector`.

Le profil Oracle est appliqué à la liste finale des colonnes O0 après calcul des features EXPERT et des rangs cross-sectionnels. Une feature demandée mais absente provoque l'échec explicite du batch : aucune réduction silencieuse du contrat n'est autorisée.

Les cases de features désactivées peuvent conserver leur valeur en session, mais elles ne sont pas ajoutées à la commande. Les profils sont les seules sources de vérité effectives des deux branches. L'Oracle conserve son propre contrat et n'hérite pas des whitelists directionnelles. La commande générée contient explicitement `--target-mode ternary --num-classes 3` en mode bundle, quelle que soit l'ancienne valeur de session.

## Entraînement et champions

Pour chaque symbole, deux entraînements indépendants utilisent les mêmes cibles et fenêtres de validation mais des datasets de features distincts :

```text
AAPL
  ├─ role=direction_long  → LSTM + challengers optionnels → champion LONG
  └─ role=direction_short → LSTM + challengers optionnels → champion SHORT
```

LSTM reste obligatoire ; LightGBM et CatBoost restent optionnels. Avec la sélection automatique, chaque branche choisit son propre backend éligible. Le champion LONG et le champion SHORT peuvent donc utiliser des architectures différentes.

Les `run_id` distincts contiennent `direction_long` ou `direction_short`, tout en partageant le même `batch_id`. Chaque `config.json` persiste `model_role` et la table `model_training_run` le stocke explicitement. L'index `(batch_id, model_role, symbol)` permet aux diagnostics de séparer les branches sans déduire le rôle depuis le nom du run. Les anciens runs restent compatibles avec un rôle nullable ; la migration `0070_training_run_role` reprend automatiquement les premiers runs bundle reconnaissables.

L'Oracle est entraîné une seule fois sur l'univers global et obligatoirement avant les branches. Les branches peuvent utiliser un sous-univers limité par `per_symbol_max_symbols`, mais le percentile Oracle est toujours calculé sur l'univers global disponible de la date, jamais uniquement sur les quelques symboles du smoke test directionnel après troncature.

## Artefacts et manifeste

```text
artifacts/models/<batch_id>/
  ├─ cascade_manifest.json
  ├─ _oracle_oof_gate.parquet
  ├─ _oracle_oof_gate.json
  ├─ oracle/
  │   └─ feature_profile.json
  ├─ directions/
  │   ├─ long/
  │   │   ├─ feature_profile.json
  │   │   ├─ _per_symbol_features.json
  │   │   └─ <SYMBOL>/config.json, metrics.json, modèles, signatures…
  │   └─ short/
  │       ├─ feature_profile.json
  │       ├─ _per_symbol_features.json
  │       └─ <SYMBOL>/config.json, metrics.json, modèles, signatures…
  └─ artefacts communs et référence vers artifacts/models/oracle/champions/<batch_id>
```

`cascade_manifest.json` est le point d'entrée du serving. Il déclare le type du bundle, les racines relatives, les profils complets et leurs empreintes, puis le statut et le résultat terminal de l'Oracle. Il distingue aussi explicitement les cibles : `oracle.target_contract` décrit la classification binaire d'extrêmes cross-sectionnels H20, tandis que `directional_target_contract` décrit la cible ternaire absolue H20 à ±3 %. Cette séparation évite de déduire à tort la cible Oracle depuis les options générales du batch.

Le manifeste suit maintenant un cycle de vie explicite :

```text
training / serving_ready=false
              │
              ├─ Oracle absent, branche manquante ou zéro paire ──> failed
              │                                                  serving_ready=false
              └─ Oracle terminé + au moins une paire LONG∩SHORT ─> completed
                                                                 serving_ready=true
```

La section `coverage` expose le nombre de symboles demandés, terminés en LONG, terminés en SHORT, présents dans l'intersection LONG ∩ SHORT, ainsi que les symboles exclus. Le batch n'est marqué `completed` dans la base que si le manifeste est réellement servable. Une fin de processus sans Oracle ou sans paire directionnelle ne constitue plus un succès.

Chaque `config.json` stocke un `feature_contract` complet et son `feature_fingerprint`. L'empreinte au niveau supérieur doit être strictement identique à celle du contrat. Les modèles LightGBM sont persistés au format natif texte et les modèles CatBoost au format natif CBM ; une extension `.cbm` ne peut plus contenir un objet Python sérialisé.

## Prédiction et arbitrage

`predict_batch` détecte automatiquement le manifeste et charge les deux champions :

```text
P_long  = proba_long du champion de la branche LONG
P_short = proba_short du champion de la branche SHORT
P_flat  = max(proba_flat LONG, proba_flat SHORT)
```

La classe consolidée est LONG si `P_long` est strictement supérieure aux deux autres, SHORT si `P_short` l'est, et FLAT sinon. Une seule ligne est produite pour la cascade ; elle conserve `direction_long_run_id`, `direction_short_run_id` et `model_role=directional_bundle`.

La table `model_predictions` persiste également `direction_long_model` et `direction_short_model`. Ainsi, `proba_long` est traçable jusqu'au run et au champion LONG, tandis que `proba_short` est traçable jusqu'au run et au champion SHORT. Le champ historique `run_id` reste renseigné avec le run LONG pour conserver sa contrainte et la compatibilité des jointures existantes ; la double filiation complète se lit dans les nouvelles colonnes.

### Calibration multiclasse au serving

Les calibrateurs directionnels sont distincts de `oracle.calibration`. Pour une branche ternaire, la calibration doit traiter simultanément `[P(SHORT), P(FLAT), P(LONG)]` : elle ne peut pas être appliquée à la seule marge binaire de `P(LONG)`.

- LSTM utilise `TemperatureScaler` sur les logits natifs `[N,3]` ;
- LightGBM et CatBoost utilisent `VectorScaler` ; leurs probabilités sont normalisées puis transformées en pseudo-logits `log(P)` exactement comme pendant le fit ;
- la sortie calibrée doit conserver la forme `[N,3]`, contenir uniquement des valeurs finies et sommer à 1 par ligne ;
- `calibration_method` vaut `temperature` ou `vector` seulement lorsque cette sortie est effectivement utilisée ;
- en cas d'artefact incompatible, le fallback vers les probabilités brutes reste non bloquant mais il est comptabilisé dans `prediction_calibration_fallback_count` et journalisé explicitement.

Le chemin scalaire `_apply_optional_calibration` est réservé à Platt/binaire. Les méthodes `temperature` et `vector` en sont exclues pour éviter l'erreur de conversion d'un vecteur de trois classes vers un seul `float`.

L'absence d'une branche invalide la prédiction du symbole. Aucun fallback silencieux vers le modèle legacy n'est fait, car mélanger un champion récent avec un modèle unique historique serait difficile à auditer. L'univers réellement prédit est donc l'intersection des symboles servables `LONG ∩ SHORT`, pas l'union des deux répertoires.

### Préflight obligatoire avant toute prédiction

Avant de calculer la première date, la CLI valide une seule fois l'ensemble du bundle :

1. manifeste de type `oracle_per_symbol_directional_bundle`, statut `completed` et `serving_ready=true` ;
2. Oracle déclaré `completed` et champions Oracle présents ;
3. deux `config.json` par symbole, avec les rôles `direction_long` et `direction_short` ;
4. cible `ternary` et `num_classes=3` dans les deux branches ;
5. concordance stricte de chaque empreinte de features ;
6. route du champion sélectionné et fichier modèle présents ;
7. format natif cohérent pour LightGBM et CatBoost.

Les symboles incomplets sont retirés avec une raison explicite. Si aucun symbole ne reste, ou si le manifeste/Oracle est invalide, la commande s'arrête immédiatement avec un code d'erreur au lieu de parcourir toutes les dates en produisant uniquement des `skipped`. Après le préflight, l'échec de la prédiction Oracle est également bloquant pour le bundle.

## Oracle, cascade et backtest

Dans « Oracle amplitude + Per-Symbol direction LONG/SHORT » :

1. l'Oracle fournit l'éligibilité ou le percentile d'amplitude ;
2. la ligne consolidée fournit `proba_long`, `proba_short` et `predicted_side` ;
3. le gate rejette une direction qui ne domine pas strictement `proba_flat`, puis applique la marge directionnelle configurée ;
4. Long only et Short only restent des restrictions de portefeuille en aval et ne modifient pas les modèles.

Le mode « Oracle seul, LONG-only » demeure disponible pour la compatibilité historique.

## CLI et contrôles de promotion

```text
python -m modelFactory --mode train --training-mode per_symbol --directional-feature-profiles --oracle-feature-profile oracle.json --long-feature-profile long.json --short-feature-profile short.json --enable-oracle-model [paramètres WF et challengers]
```

Le backend active aussi automatiquement l'Oracle lorsque le bundle est demandé. Il n'est pas nécessaire d'ajouter les paramètres de cible à cette commande : H20, ternaire et ±3 % sont le contrat du mode. S'ils sont tout de même fournis avec d'autres valeurs, ils sont remplacés avant la construction de `TrainingConfig`, puis de nouveau au moment d'appliquer les profils LONG et SHORT.

### Portée réelle de cette correction

Cette évolution rend la mission des modèles directionnels explicite et reproductible, mais elle ne garantit pas à elle seule une meilleure précision. L'audit du batch `model-factory-20260902192105-b5317c` a montré une nuance importante : `target_excess_vs_spy=true` figurait dans la configuration enregistrée, mais l'implémentation de la cible ne l'appliquait qu'à la régression. Les labels ternaires de ce batch étaient donc déjà fondés sur les rendements absolus. Son horizon H20 faisait toutefois partie d'un entraînement multi-horizons et non d'un contrat directionnel H20 isolé.

Il ne faut donc pas attribuer les mauvaises performances de ce batch au seul excès relatif à SPY. Le nouveau contrat supprime l'ambiguïté et fournit une baseline propre pour les expériences suivantes. Sa promotion exige toujours un diagnostic OOS conditionnel au gate Oracle, avec précision LONG/SHORT, abstention, couverture et stabilité temporelle.

Avant un backtest, vérifier : manifeste et `batch_id`, statut Oracle `completed`, copies et SHA-256 des profils, deux champions servables pour chaque symbole, plusieurs folds Walk-Forward valides par rôle, stabilité de `f1_long` côté LONG et `f1_short` côté SHORT, couverture et abstention, puis sélection du mode de gate directionnel symétrique.

> Les batches bundle entraînés avant ce contrat de validation peuvent être refusés s'ils contiennent des branches en régression, un Oracle manquant, des empreintes incohérentes ou de faux artefacts natifs. Ils doivent être réentraînés ; les déclarer manuellement servables masquerait une incompatibilité réelle.

## Diagnostic ML du bundle

La page **Diagnostic ML** détecte `cascade_manifest.json` et affiche une synthèse des trois composants. Un sélecteur LONG/SHORT borne ensuite toutes les requêtes de métriques, de gouvernance, d'horizons, de régimes et de détail symbole au `model_role` choisi.

- LONG classe et sélectionne sur `f1_long` ; les autres F1 restent informatifs ;
- SHORT classe et sélectionne sur `f1_short` ;
- Oracle conserve ses métriques binaires d'amplitude et n'est jamais agrégé aux modèles ternaires ;
- le volet de couplage contrôle la présence des deux run ids dans `model_predictions` ;
- le téléchargement des candidats lit les artefacts sous `directions/long` et `directions/short`, puis applique les gates indépendamment.

La compatibilité historique est conservée : en l'absence de manifeste bundle, la page utilise le parcours direct `<batch>/<SYMBOL>` et l'affichage per-symbol/per-sector précédent.

### Performance réalisée des prédictions directionnelles

Pour un bundle, le bouton **« Calculer / actualiser la performance réalisée »** confronte les probabilités effectivement persistées dans `model_predictions` aux clôtures ajustées futures de `stock_bars_daily`. Il mesure séparément la branche LONG et la branche SHORT : il ne remplace ni leurs probabilités ni leurs métriques par la classe consolidée `predicted_side`.

Deux périmètres permettent de localiser un éventuel défaut :

1. **Oracle TOP20 — mission réelle**, utilisé par défaut : pour chaque date, le percentile de `proba_extreme` est calculé sur l'univers Oracle complet, avant son intersection avec les symboles directionnels. Le filtre reprend exactement la règle du moteur, `rank(pct=True) >= 0,80`. On évalue ensuite séparément le top 10 % de `proba_long` et le top 10 % de `proba_short` dans les candidats Oracle encore servables ;
2. **Tout l'univers directionnel** : le top 10 % est pris parmi toutes les prédictions bundle de la date. Cette vue mesure plus directement la branche directionnelle, sans la composition d'univers imposée par l'Oracle.

Les pourcentages sont recalculés **date par date**, jamais globalement sur toute la période. Cette règle évite qu'une date ou un régime dont les probabilités sont globalement plus hautes monopolise l'échantillon. Pour les branches directionnelles, un groupe non vide conserve au moins un titre par l'arrondi supérieur. Le pool Oracle conserve volontairement la convention percentile inclusive du moteur ; sur un très petit univers, son effectif peut donc être légèrement supérieur à 20 %.

Les résultats sont mesurés à H3, H5, H10 et H20 **séances de cotation** :

```text
r_H(symbol, t) = AdjClose(symbol, t + H séances) / AdjClose(symbol, t) - 1

rendement_signé_LONG  =  r_H
rendement_signé_SHORT = -r_H

excès_H = r_H(symbol) - r_H(SPY)
excès_signé_LONG  =  excès_H
excès_signé_SHORT = -excès_H
```

Ainsi, un rendement signé positif désigne toujours une prédiction correcte : hausse pour LONG, baisse pour SHORT. Le **taux bon sens** est la fréquence `rendement_signé > 0`. Le **taux mouvement ≥ 3 %** exige `rendement_signé >= 3 %`. Le **lift** est exprimé en points de pourcentage et compare le taux bon sens du top 10 % à celui de toutes les prédictions arrivées à maturité dans le même périmètre.

Le tableau multi-horizons affiche aussi le rendement signé moyen et médian, l'excès signé moyen contre SPY et la proportion de dates dont la moyenne des sélections est positive. Le détail d'un horizon fournit :

- les KPI propres à chaque côté ;
- la stabilité par symbole avec nombre d'observations, hit rates et probabilité moyenne ;
- les 250 sélections réalisées les plus récentes avec date, champion, rendement du titre, rendement signé, rendement SPY et excès signé.

Lorsque la prédiction Oracle est encore en cours ou incomplète, l'écran affiche explicitement le rapport `dates Oracle / dates directionnelles`. Le périmètre TOP20 ne calcule alors que les dates Oracle déjà persistées ; le bouton **Actualiser** recharge les tables sans intervenir sur le processus de prédiction.

#### Maturité, PIT et interprétation

Le classement top 10 % est figé avec les seules probabilités disponibles à la date de prédiction. Une sélection récente qui ne possède pas encore H séances futures reste comptée comme **sélectionnée**, mais elle est exclue des métriques jusqu'à sa maturité. Elle n'est surtout pas remplacée a posteriori par le titre suivant du classement : ce remplacement introduirait un biais de disponibilité du label.

Les clôtures futures servent uniquement à l'évaluation ex post. Elles ne participent ni au gate Oracle, ni au classement directionnel. La double filiation LONG/SHORT est exigée dans la requête afin de ne pas mélanger les anciennes prédictions legacy ou `oracle_synth` avec les deux modèles spécialisés. Le diagnostic relit aussi `train_end_date` des deux runs et impose `train_end_date(LONG) < prediction_date` et `train_end_date(SHORT) < prediction_date`. Toute ligne in-sample, sans filiation ou sans date vérifiable est comptée dans l'alerte PIT puis exclue des statistiques.

Ces rendements ne constituent pas un backtest : les observations H3/H5/H10/H20 se chevauchent, aucune capacité de portefeuille, abstention finale, exécution, spread, slippage, stop ou TP n'est simulé. Le diagnostic répond à la question « les plus fortes probabilités de cette branche anticipent-elles le bon sens et une amplitude utile ? ». Seul le moteur de backtest mesure ensuite la stratégie tradable complète.

## Contrôle PIT des prédictions directionnelles en backtest

La présence d'une ligne historique dans `model_predictions` ne prouve pas qu'elle était disponible à la date simulée. Une commande de prédiction lancée après l'entraînement final peut recalculer 2024 avec un modèle dont `train_end_date` est en juin 2024 : ces lignes sont techniquement historiques, mais elles utilisent du futur pour janvier-mai 2024.

En mode backtest `pipeline`, le contrôle est bloquant pour un bundle directionnel. Pour chaque ligne, le chargeur relie `direction_long_run_id` et `direction_short_run_id` à leurs lignes `model_training_run`. Le contrat exigé est :

```text
train_end_date(LONG)  < trade_date
ET
train_end_date(SHORT) < trade_date
```

L'égalité est refusée : avec des barres daily, un modèle entraîné jusqu'au close du jour ne peut pas être considéré disponible avant la décision du même jour sans contrat intraday plus précis. Une filiation absente, un run inconnu ou une date de fin d'entraînement absente sont également refusés ; le moteur ne remplace pas une preuve PIT manquante par une hypothèse favorable.

Pour tester une période incluse dans la fenêtre d'entraînement finale, il faut donc persister des prédictions issues de vrais folds walk-forward et leur propre filiation de modèle as-of. Sinon, le backtest doit commencer après la fin d'entraînement des deux branches. Les backtests directionnels antérieurs à ce contrôle sont non conclusifs lorsque leurs prédictions précèdent la fin d'entraînement de leur run.
