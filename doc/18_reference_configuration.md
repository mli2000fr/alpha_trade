# Référence de configuration

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

`config.yaml` porte le profil US et les options communes, complétés par les
defaults des dataclasses, flags CLI et préférences IHM. Toujours journaliser
la configuration effective ; ni un défaut Python ni un YAML isolé ne la décrivent seul.

## Fichiers et propriétaires — 10 octobre 2026

| Fichier | Fonction |
| --- | --- |
| config.yaml | Options métier US ; us_pipeline.steps/steps_friday et filtre GPT |
| config_cn.yaml / config_fr.yaml | Profils de recherche propres aux marchés, serving fermé |
| config/markets/market_us.yaml, market_cn.yaml, market_fr.yaml | Identité marché, capacités, calendrier, devise, alias DB |
| config/databases.yaml | Bases distinctes, credentials et allowlists du router |
| batch.yaml | Catalogue US et quatre entrées de recherche CN legacy |
| batch_cn.yaml / batch_fr.yaml | Catalogues propres CN/FR |
| config/research_cn / config/research_fr | Protocoles et preuves de recherche, pas paramètres LIVE |

Les catalogues ne sont pas déplacés automatiquement par un changement d'IHM.
Un nom dupliqué entre les catalogues CN est refusé. La page Batch résout le
marché et les fichiers concernés. [Inventaire courant](operations/catalogue_batchs_actuel.md).

## Chargement du fichier

`common/config_loader.py` fournit le chargement YAML commun. Un chemin explicite
**autre que le `config.yaml` racine** a priorité ; pour le chemin par défaut
(y compris ce `config.yaml` explicite), `ALPHA_TRADE_CONFIG_PATH` peut le remplacer.
Le même principe s'applique au catalogue via `ALPHA_TRADE_BATCH_CONFIG_PATH`.
Les context managers d'override restaurent l'environnement après utilisation.
Ne pas supposer qu'un appel passant le chemin racine neutralise l'override.

L'[inventaire de toutes les clés présentes](reference/configuration_generee.md)
est généré sans valeurs ni secrets. Il complète cette explication, sans déduire
qu'une clé déclarée est consommée partout.

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
| `us_pipeline` | listes d'étapes 1–14 lundi–jeudi/vendredi, mode et compte du batch |
| `llm_directional_filter` | défauts IHM/CLI du filtre Oracle → Web → GPT PAPER, SHORT et protections |
| `market_cap` | filtre de capitalisation, indépendamment de la collecte market_cap_sync |
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
| `ALPHA_TRADE_BATCH_CONFIG_PATH` | autre catalogue de batchs pour les consommateurs compatibles |
| `ALPHA_TRADE_MARKETS_CONFIG_DIR` | répertoire des contextes de marchés |
| `ALPHA_TRADE_VAULT_ADDR` | active la résolution Vault |
| `LOGIN_DB`, `PASSWORD_DB` | credentials MySQL |
| `LOGIN_DB_CN`, `PASSWORD_DB_CN`, `LOGIN_DB_FR`, `PASSWORD_DB_FR` | credentials par marché ; fallback partagé configuré dans le router, sans partage des données |
| `DB_HOST`, `DB_NAME` | overrides DB ciblés |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | capacité du pool |
| `DB_POOL_RECYCLE_SECONDS` | recyclage, minimum 60 s |
| `DB_SSL_CA_PATH` | CA TLS, fichier requis |
| `ALPACA_<ID>_*` | comptes broker multiples |
| `ALPHA_TRADE_CACHE_URL` | Redis ou fallback mémoire |
| `IHM_AUTH_TOKEN`, `IHM_REQUIRE_LOCALHOST` | accès IHM |

## Valeurs locales à ne pas confondre avec les defaults Python

Au 10/10/2026 : filtre GPT enabled=true pour le défaut IHM, modèle demandé
gpt-6.1-sol, univers universe-file:univers_filtred_tradable.txt, batch
model-factory-20261003082853-e98332 ; N=20, K=3, SHORT autorisé. SL=7 %, sortie
à l'ouverture séance 21 (entrée=1), trailing=15 %. Sans option YAML,
FilterConfig reste désactivé, N=10/K=5/SHORT=false ; ProtectionProfile a
un trailing par défaut de 20 %. Le profil d'un run est figé, pas rechargé
rétroactivement pour ses lots.

Le batch US utilise des options fraîches dont llm_filter_enabled=false :
enabled=true dans le défaut IHM ne suffit pas à lui ajouter GPT. Son mode
configuré est PAPER/default, ses listes actuelles sont 1–7,9–14 lundi–jeudi
et 1–14 vendredi. Les étapes omises ne sont pas rajoutées.

Oracle × ATR : cascade.oracle_atr_enabled=true, mais politique Oracle live
off et extreme_gate.enabled=false. Ne pas déduire « serving Oracle activé »
du seul booléen ATR. Le filtre market_cap est liquidity_only actuellement,
même si le batch de collecte SEC/Yahoo/Finnhub est actif.

Voir [état actuel](ETAT_ACTUEL_IMPLEMENTATION.md) pour les contrats, restrictions
et différences entre configuration et autorisation effective.

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
