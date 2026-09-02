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
3. conserve les réglages indépendants des features : cibles, horizons, walk-forward, epochs, patience, challengers et sélection du champion ;
4. émet `--directional-feature-profiles`, `--long-feature-profile` et `--short-feature-profile` ;
5. active l'Oracle et force le mode Per-Symbol côté backend ;
6. neutralise `oracle_model_only` et `exclude_per_symbol_per_sector`.

Le profil Oracle est appliqué à la liste finale des colonnes O0 après calcul des features EXPERT et des rangs cross-sectionnels. Une feature demandée mais absente provoque l'échec explicite du batch : aucune réduction silencieuse du contrat n'est autorisée.

Les cases de features désactivées peuvent conserver leur valeur en session, mais elles ne sont pas ajoutées à la commande. Les profils sont les seules sources de vérité effectives des deux branches. L'Oracle conserve son propre contrat et n'hérite pas des whitelists directionnelles.

## Entraînement et champions

Pour chaque symbole, deux entraînements indépendants utilisent les mêmes cibles et fenêtres de validation mais des datasets de features distincts :

```text
AAPL
  ├─ role=direction_long  → LSTM + challengers optionnels → champion LONG
  └─ role=direction_short → LSTM + challengers optionnels → champion SHORT
```

LSTM reste obligatoire ; LightGBM et CatBoost restent optionnels. Avec la sélection automatique, chaque branche choisit son propre backend éligible. Le champion LONG et le champion SHORT peuvent donc utiliser des architectures différentes.

Les `run_id` distincts contiennent `direction_long` ou `direction_short`, tout en partageant le même `batch_id`. Les métriques et la gouvernance ne se remplacent donc pas. Chaque `config.json` persiste aussi `model_role`.

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

## Prédiction et arbitrage

`predict_batch` détecte automatiquement le manifeste et charge les deux champions :

```text
P_long  = proba_long du champion de la branche LONG
P_short = proba_short du champion de la branche SHORT
P_flat  = max(proba_flat LONG, proba_flat SHORT)
```

La classe consolidée est LONG si `P_long` est strictement supérieure aux deux autres, SHORT si `P_short` l'est, et FLAT sinon. Une seule ligne est produite pour la cascade ; elle conserve `direction_long_run_id`, `direction_short_run_id` et `model_role=directional_bundle`.

La table `model_predictions` persiste également `direction_long_model` et `direction_short_model`. Ainsi, `proba_long` est traçable jusqu'au run et au champion LONG, tandis que `proba_short` est traçable jusqu'au run et au champion SHORT. Le champ historique `run_id` reste renseigné avec le run LONG pour conserver sa contrainte et la compatibilité des jointures existantes ; la double filiation complète se lit dans les nouvelles colonnes.

L'absence d'une branche invalide la prédiction du symbole. Aucun fallback silencieux vers le modèle legacy n'est fait, car mélanger un champion récent avec un modèle unique historique serait difficile à auditer.

## Oracle, cascade et backtest

Dans « Oracle amplitude + Per-Symbol direction LONG/SHORT » :

1. l'Oracle fournit l'éligibilité ou le percentile d'amplitude ;
2. la ligne consolidée fournit `proba_long`, `proba_short` et `predicted_side` ;
3. le gate applique la marge directionnelle configurée ;
4. Long only et Short only restent des restrictions de portefeuille en aval et ne modifient pas les modèles.

Le mode « Oracle seul, LONG-only » demeure disponible pour la compatibilité historique.

## CLI et contrôles de promotion

```text
python -m modelFactory --mode train --training-mode per_symbol --directional-feature-profiles --oracle-feature-profile oracle.json --long-feature-profile long.json --short-feature-profile short.json --enable-oracle-model [paramètres de cible, WF et challengers]
```

Le backend active aussi automatiquement l'Oracle lorsque le bundle est demandé.

Avant un backtest, vérifier : manifeste et `batch_id`, statut Oracle `completed`, copies et SHA-256 des profils, deux champions servables pour chaque symbole, plusieurs folds Walk-Forward valides par rôle, stabilité de `f1_long` côté LONG et `f1_short` côté SHORT, couverture et abstention, puis sélection du mode de gate directionnel symétrique.
