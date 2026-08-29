# Orchestration ML : train, predict et artefacts

Retour : [références ML](README.md)

## Points d'entrée

`python -m modelFactory` appelle `modelFactory.cli`. Le CLI parse les options, construit `TrainingConfig`, applique les seeds, crée un batch et distribue vers `run_train` ou `run_predict`. `orchestrator.py` séquence les familles de modèles ; il ne faut pas inférer la séquence uniquement depuis les noms de flags.

## Matrice des branches

| Configuration | per-symbol | per-sector | global/ranking | Oracle |
|---|---:|---:|---:|---:|
| défaut selon CLI | selon options | selon options | oui selon config | opt-in |
| `exclude_per_symbol_per_sector` | non | non | conservé | conservé si activé |
| `global_model_only` | non | non | chemin global avec retour anticipé possible | peut être sauté |
| `oracle_model_only` | non | non | non | oui, activation implicite |

## Train

Le batch enregistre commande reconstruite, arguments JSON, configuration dataclass sérialisée et liste de features. Le chargement résout les dates disponibles et le scope. Les familles sont entraînées en walk-forward, évaluées, puis les champions admissibles sont inscrits au registry et leurs artefacts écrits sous `artifacts/`.

Un rapport est généré dans `artifacts/rapport_ml/<batch_id>.md`. Les logs contenant le batch id sont archivés à côté pour survivre à la rotation. Un échec de rapport est non bloquant pour le calcul, mais doit être visible.

## Predict : résolution du batch

Dans le chemin courant, `batch_diagnostics.backtest_batch_id` a priorité lorsqu'il est renseigné ; le nom du dossier d'artefacts sert de fallback dans le résolveur. Le batch effectif doit être publié dans le summary. Ne jamais prendre « dernier fichier modifié » comme champion implicite.

## Predict : détection des artefacts

Le CLI détecte modèles per-symbol, per-sector, historique Global Rank et champions Oracle. Un batch possédant un historique rank-driven n'est pas traité comme Oracle-only même s'il a aussi Oracle. Le combined path peut exécuter Oracle après la synthèse principale. L'Oracle-only remplit `oracle_extreme_predictions`, puis synthétise vers `model_predictions` si des rows valides existent.

## Horizon de synthèse

Priorité exacte : `--synth-best-h`, `batch_diagnostics.live_horizon`, best horizon metadata, puis 10. Cet horizon choisit la colonne Global Rank qui contribue au côté/rang synthétique. Un changement modifie le comportement live sans réentraîner : il doit donc être gouverné.

## Inférence historique

Le mode historique reçoit start/end et reconstruit les dates. Pour chaque date, utiliser univers et données as-of. Les résultats reconstruits ne remplacent pas les prédictions historiquement émises ; run id et batch les distinguent.

## États et erreurs

`runtime_status.py` publie progression/compteurs. `cleanup_incomplete_batches.py` cible les batches interrompus. `auto_rollback.py` restaure un champion connu selon politique. Une absence d'artefact, un contrat features incompatible ou une couverture nulle est une erreur explicite ; aucun fallback score-only.

