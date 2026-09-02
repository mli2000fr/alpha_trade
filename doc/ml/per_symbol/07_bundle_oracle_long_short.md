# Bundle Oracle Extreme + Per-Symbol LONG/SHORT

## Objectif et responsabilités

Ce mode sépare explicitement amplitude et direction dans une seule campagne ML. Chacune des trois branches possède un profil de features indépendant :

```text
                          batch_id unique
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
     Oracle Extreme       branche LONG       branche SHORT
     modèle global O0     modèle / symbole   modèle / symbole
     amplitude extrême    profil LONG JSON   profil SHORT JSON
             │                  │                  │
             └──────────── gate + arbitrage LONG/SHORT ────────┘
                                │
                       candidats de backtest
```

- l'Oracle Extreme détecte les mouvements d'amplitude inhabituelle sans imposer leur sens ;
- le champion LONG estime la probabilité haussière avec un contrat de features spécialisé ;
- le champion SHORT estime la probabilité baissière avec un autre contrat ;
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

En mode bundle, le backend force systématiquement les deux branches directionnelles en `target_mode=ternary` et `num_classes=3`, même si une ancienne commande, une session IHM ou une API transmet `regression`. Les seuils ternaires configurés sont conservés ; s'ils sont invalides, les valeurs de repli sont `+3 %` et `-3 %`. Cette règle empêche qu'un choix destiné à l'Oracle transforme accidentellement les modèles LONG/SHORT en régresseurs.

Le modèle Global Ranking n'appartient pas à ce bundle et n'est requis ni à l'entraînement O0 ni à la prédiction. Le préremplissage `global_rank_20` est donc désactivé pour ce parcours. Les autres campagnes Global Ranking demeurent inchangées.

## Contrat et découverte des profils

Les profils sont découverts dynamiquement dans `config/features/oracle/*.json`, `config/features/long/*.json` et `config/features/short/*.json`. L'IHM choisit `oracle.json`, `long.json` et `short.json` par défaut lorsqu'ils existent.

Un profil contient obligatoirement `schema_version: 1`, une `direction` cohérente avec son répertoire, `feature_set`, une liste `feature_columns` ordonnée, non vide et sans doublon, les `generator_options` nécessaires au calcul des colonnes, et une provenance expérimentale.

Le chargeur refuse les chemins relatifs ou traversants, une mauvaise direction, un schéma inconnu, une liste vide et les doublons. Le contenu brut reçoit une empreinte SHA-256. Une copie résolue est figée dans les artefacts du batch : modifier plus tard le fichier de configuration ne change pas le contrat historique du modèle.

### Profils livrés

- `oracle/oracle.json` : contrat canonique O0, 129 features EXPERT et 45 rangs cross-sectionnels, sans `global_rank_20` ni les deux extras O1, soit 174 colonnes ordonnées ;
- `long/long.json` : contrat LONG confirmé du batch `model-factory-20260902052533-998d3a`, 84 features EXPERT, après ablation et confirmation sur 300 symboles.
- `short/short.json` : contrat SHORT confirmé du batch `model-factory-20260901180312-2d74f9`, 130 features EXPERT avec MOVE. `include_macro_move=true` est indispensable : mettre `move_close` dans une whitelist ne calcule pas sa source à lui seul.

Les performances historiques constituent la provenance du profil, pas une garantie. Une modification d'univers, d'horizon, de seuil de label ou de période exige une nouvelle validation OOS.

## Comportement de l'IHM

La case « Bundle Oracle + deux modèles Per-Symbol LONG/SHORT » :

1. affiche les profils Oracle, LONG et SHORT détectés sur disque ;
2. désactive les cases manuelles de features afin d'éviter deux sources de vérité ;
3. verrouille visuellement la cible sur **Ternaire — SHORT / FLAT / LONG** pour les deux branches ; horizons, walk-forward, epochs, patience, challengers et sélection du champion restent réglables ;
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

L'Oracle est entraîné une seule fois sur l'univers global. L'ordre d'exécution actuel l'entraîne après les branches ; cela ne change pas son rôle au serving, où il est le gate d'amplitude en amont de la décision directionnelle.

## Artefacts et manifeste

```text
artifacts/models/<batch_id>/
  ├─ cascade_manifest.json
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

`cascade_manifest.json` est le point d'entrée du serving. Il déclare le type du bundle, les racines relatives, les profils complets et leurs empreintes, puis le statut et le résultat terminal de l'Oracle.

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
python -m modelFactory --mode train --training-mode per_symbol --directional-feature-profiles --oracle-feature-profile oracle.json --long-feature-profile long.json --short-feature-profile short.json --enable-oracle-model [paramètres de cible, WF et challengers]
```

Le backend active aussi automatiquement l'Oracle lorsque le bundle est demandé.

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
