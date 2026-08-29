# Référence de configuration

`config.yaml` est la configuration principale, complétée par les defaults des dataclasses, les flags CLI et les préférences IHM. Toujours journaliser la configuration effective d'un run.

## Sections racine actuelles

| Section | Objet |
|---|---|
| `database` | hôte, port, nom et placeholders credentials |
| `alpaca` | comptes, labels, modes et restrictions |
| `risk` | pertes et drawdown PROD/backtest |
| `leverage` | politique Reg-T, plafond, equity, buying power |
| `market_regimes` | providers, signaux, hystérésis, CP-V2 |
| `fred` | séries et cache FRED |
| `selector` | facteurs, filtres et ranking selector |
| `risk_management` | sizing, contraintes, stops, corrélations |
| `screener` | fenêtres et seuils objectifs |
| `market_data` | provider bars et convention de données |
| `eodhd` | endpoints, quotas, batch/backfill |
| `batch_diagnostics` | batch/horizon production et diagnostics |
| `global_ranking` | activation et paramètres ranking |
| `cascade` | mode de sélection/ranking aval |
| `persistent_dip_filter_long` | gate dip long et profils prod/backtest |
| `extreme_gate` | gate Oracle par percentile |
| `oracle` | batch et paramètres Oracle |
| `conviction` | transformation probabilités/score en conviction |
| `backtest` | lifecycle, coûts, limites et reporting |

## Priorités

En général : flag CLI explicite > option IHM transmise en CLI > `config.yaml` > default Python. Certains résolveurs ont un ordre spécialisé. Exemple pour l'horizon de synthèse ML : `--synth-best-h`, puis `batch_diagnostics.live_horizon`, puis metadata du batch, puis 10.

## Paramètres sensibles

- batch id et horizon live ;
- source de symboles ;
- provider et `data_adjustment` ;
- dates de train et folds ;
- feature whitelist/feature set ;
- targets et labels ;
- stop/TP/trailing/time-stop/gap filter ;
- limites gross/net, sleeves et levier ;
- mode régime et hystérésis ;
- account id et mode paper/live.

Tout changement de ces paramètres doit produire un nouveau fingerprint ou une metadata de run différente. Ne pas comparer des performances sans diff de configuration.

## Environnements et secrets

Les `${VAR}` sont résolus par `core.secrets` et les registries de comptes. Les clés manquantes peuvent être acceptables pour un provider optionnel, mais jamais pour DB ou broker lorsqu'une étape en dépend. Les valeurs `pass`, `user`, `changeme` et secrets littéraux sont rejetés selon le scanner.

## Ajouter une option

Définir le default dans la dataclass responsable, valider type/plage, charger depuis YAML, exposer éventuellement en CLI/IHM, inclure dans metadata/fingerprint, tester priorité et erreur, puis documenter l'impact live/backtest.

