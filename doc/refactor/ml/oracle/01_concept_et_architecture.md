# Oracle Extreme — concept, sémantique et architecture

Retour : [dossier Oracle](README.md)

## Question modélisée

Pour chaque date D, l’application dispose d’un univers de symboles et de features PIT. Après H séances, certains titres appartiendront aux queues haute ou basse des rendements futurs cross-sectionnels. Oracle apprend à reconnaître les configurations associées à ces mouvements extrêmes.

La sortie `proba_extreme` signifie :

> probabilité estimée qu’un symbole appartienne à l’une des deux queues extrêmes définies par le label Oracle.

Elle ne signifie pas :

- probabilité de hausse ;
- probabilité de baisse ;
- rendement futur attendu ;
- rang directionnel du Global Ranking ;
- ordre d’achat.

## Évolution depuis la spécification historique

La première spécification envisageait deux modèles : Oracle TOP et Oracle BOTTOM, éventuellement superposés au Global Model B25. Les expériences et le code ont montré que les deux apprenaient largement le même signal d’amplitude et distinguaient mal le signe.

Le contrat actuel a donc fusionné les cibles :

`oracle_extreme10 = oracle_top10 OR oracle_bottom10`.

Les noms `oracle_top10` peuvent encore apparaître dans des commentaires, compatibilités ou archives. Le champ canonique des labels et prédictions est `oracle_extreme10`. Toute nouvelle intégration doit utiliser cette sémantique.

## Place par rapport au Global Ranking

Global Ranking répond : « comment ordonner les rendements relatifs attendus ? ». Oracle Extreme répond : « quelles observations ressemblent à de futurs mouvements de queue ? ».

Les architectures possibles ne sont pas équivalentes :

| Architecture | Sens |
|---|---|
| Global Rank seul | classement directionnel relatif |
| Global Rank + Oracle | filtre ou second signal de magnitude |
| Oracle O0 seul | univers d’opportunités extrêmes sans direction |
| Oracle utilisé comme rang long | hypothèse empirique, pas sémantique native |

Le gate officiel `extreme_gate.py` est indépendant du ranking B25. Il transforme les probabilités Oracle en percentile quotidien et sélectionne une fraction de l’univers. Une couche aval doit encore décider le côté.

## Configuration dédiée

`OracleConfig` est séparée de `TrainingConfig` pour éviter de modifier implicitement le champion Global Model. Ses champs sont :

| Champ | Défaut | Rôle |
|---|---:|---|
| `horizon` | 20 | horizon du label |
| `top_pct` | 0,10 | taille de chaque queue lors de la construction conceptuelle |
| `raw_target` | true | rendement futur brut avant rang |
| `batch_id` | absent | override du batch source |
| `available_date_offset_days` | 1 | décalage après l’exit date |

`resolve_oracle_batch_id()` donne priorité à `oracle.batch_id`, puis à `batch_diagnostics.backtest_batch_id`. Le batch effectif doit toujours être publié dans les rapports.

Attention : le constructeur de labels actuel utilise explicitement H et `top_pct=0.10` dans son calcul. Toute modification de la config doit être vérifiée jusqu’au call site ; la présence d’un champ YAML ne garantit pas qu’il pilote chaque chemin historique.

## Composants

| Fichier | Responsabilité |
|---|---|
| `config.py` | paramètres et résolution du batch |
| `build_labels.py` | univers, rendements futurs, rangs et persistance |
| `dataset.py` | features PIT, targets et ablations |
| `leakage.py` | assertions bloquantes T1–T5 |
| `train.py` | modèles et métriques d’ablation |
| `walk_forward.py` | folds causaux, OOS et champions |
| `combine.py` | combinaison/calibration expérimentale |
| `predict_history.py` | inférence sans retrain sur une période |
| `predictions_store.py` | table des probabilités |
| `extreme_gate.py` | percentile quotidien et gate |
| `audit.py` | capture, déciles et comparaison golden |

Les autres fichiers de diagnostic testent séparabilité, hard negatives, sévérité, fondamentaux, direction et confounders. Ils ne deviennent pas automatiquement des gates de production.

## Invariants

1. Oracle est un target historique, jamais une feature future.
2. Les probabilités sont produites à D avec des features disponibles à D.
3. Le label ne devient utilisable pour le train qu’à `oracle_available_date`.
4. L’univers quotidien du label correspond au scope que le modèle pouvait voir.
5. Les probabilités sont toujours filtrées par batch.
6. Le percentile du gate est calculé à l’intérieur de chaque date.
7. Oracle ne décide pas la direction.
8. Recherche et production utilisent un lifecycle explicitement identifié.

## Exemple

À D, quatre cents symboles sont observés. À D+20, les 10 % meilleurs et 10 % pires rendements sont marqués extrêmes. Le modèle apprend à D les caractéristiques de ces observations, mais n’utilise le label que lorsque D+20 et son délai de disponibilité sont passés.

Si un symbole obtient `proba_extreme=0.92`, cela signifie forte ressemblance avec une future queue, sans indiquer s’il se trouvera dans la queue haute ou basse.

