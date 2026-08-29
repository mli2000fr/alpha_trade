# Référence de configuration

`config.yaml` est la configuration principale, complétée par les defaults des dataclasses, les flags CLI et les préférences IHM. Toujours journaliser la configuration effective d'un run.

## Chargement du fichier

`common/config_loader.py` fournit le chargement YAML commun. `ALPHA_TRADE_CONFIG_PATH` peut remplacer le chemin par défaut. Lorsqu’un chemin est passé explicitement au loader, le code applique ses règles de priorité et permet un override temporaire via context manager, notamment pour les tests.

Un fichier absent ou un YAML invalide doit être traité comme une erreur de configuration au point où sa présence est requise. Le loader ne valide pas à lui seul toutes les sections métier : chaque dataclass ou résolveur valide ensuite types, bornes, énumérations et combinaisons.

## Valeurs secrètes

Le loader reconnaît les placeholders Vault de forme exacte `${vault:KEY}`. Ils sont résolus seulement si un client Vault est fourni ou construit lorsque `ALPHA_TRADE_VAULT_ADDR` est configuré. Un placeholder Vault non résolu est conservé et journalisé, ce qui permet au module consommateur de refuser proprement la configuration.

Les placeholders d’environnement `${VAR}` sont aussi utilisés par des composants comme `core.secrets` et le registre Alpaca. Il ne faut pas confondre ces deux mécanismes ni supposer que chaque lecture YAML résout automatiquement tous les placeholders.

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

La priorité est locale à chaque option. Avant de modifier un paramètre sensible, rechercher son résolveur réel et ses tests. Une valeur IHM n’a d’effet que si elle est traduite dans la commande ou l’environnement du sous-processus.

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

Pour la connexion DB, le code actuel interdit plusieurs valeurs manifestement sentinelles comme `changeme` ou `todo`, mais reste volontairement permissif pour les valeurs historiques `user` et `pass`. Elles ne doivent pas être utilisées en production, même si ce contrôle précis ne les bloque pas. Le message d’erreur du module est plus général que la liste effectivement rejetée.

Variables structurantes :

| Variable | Effet |
|---|---|
| `ALPHA_TRADE_CONFIG_PATH` | autre fichier YAML |
| `ALPHA_TRADE_VAULT_ADDR` | active la résolution Vault |
| `LOGIN_DB`, `PASSWORD_DB` | credentials MySQL |
| `DB_HOST`, `DB_NAME` | overrides DB ciblés |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | capacité du pool |
| `DB_POOL_RECYCLE_SECONDS` | recyclage, minimum 60 s |
| `DB_SSL_CA_PATH` | CA TLS, fichier requis |
| `ALPACA_<ID>_*` | comptes broker multiples |
| `ALPHA_TRADE_CACHE_URL` | Redis ou fallback mémoire |
| `IHM_AUTH_TOKEN`, `IHM_REQUIRE_LOCALHOST` | accès IHM |

## Ajouter une option

Définir le default dans la dataclass responsable, valider type/plage, charger depuis YAML, exposer éventuellement en CLI/IHM, inclure dans metadata/fingerprint, tester priorité et erreur, puis documenter l'impact live/backtest.

## Procédure de changement

1. Localiser toutes les lectures de la clé et son default Python.
2. Identifier priorité CLI/YAML/env et profil PROD/backtest.
3. Vérifier que l’option est incluse dans le fingerprint ou la metadata.
4. Ajouter validation et tests des limites.
5. Vérifier la commande générée par l’IHM.
6. Comparer la configuration effective avant/après.
7. Si le contrat de décision change, produire un nouveau batch/modèle ou une nouvelle version de politique.

## Diagnostic

| Symptôme | Cause fréquente |
|---|---|
| modification YAML sans effet | flag CLI, variable env ou dataclass prioritaire |
| compte absent | placeholder non résolu ou paire API/secret incomplète |
| résultats non comparables | batch, horizon, features ou lifecycle différents |
| DB pointe ailleurs | `DB_HOST`, `DB_NAME` ou fichier alternatif |
| Vault visible littéralement | client/adresse Vault absent ou clé introuvable |
| IHM différente du CLI | option non transmise par le builder de commande |
