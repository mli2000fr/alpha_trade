# Backtests US : isolation des écritures et coexistence avec le pipeline

Évolution du 1er novembre 2026. Les nouveaux backtests US ordinaires et Winner
qualifiés utilisent automatiquement `READ_ONLY_ISOLATED` depuis l'IHM. Ils
peuvent tourner pendant le pipeline ; les calculs du pipeline conservent leurs
verrous et contrôles habituels. Aucun ordre réel ou PAPER n'est passé par un replay.

## Audit des écritures avant modification du verrou

| Chemin | Constat et traitement |
| --- | --- |
| CLI `backtesting run`, chargement OHLCV/scores/prédictions, cascade Oracle | Lectures SQL historiques. Le cache Parquet était partagé ; il est maintenant propre au run isolé. |
| `backtesting.resilience`, reconstruction ML/sentiment | Peut publier dans certains modes de recherche. `rebuild-missing` et les stratégies non qualifiées restent exclusifs. Une écriture indirecte imprévue est bloquée dans le mode isolé. |
| Bridges risque, exécution, protections, watcher et sorties | Objets et écritures simulés en mémoire ; exports dans `output_dir`. Ils n'appellent pas le CLI risque/exécution de production. |
| Trackers de concentration/pertes | Chargement éventuellement demandé en lecture ; sauvegarde du résultat dans le dossier du run. Aucun état live n'est remplacé. |
| Winner | `MemoryCampaignStore` et `ReplayBroker` en mémoire ; données/facteurs/options lus, reçus de reconstruction locaux. |
| Rattrapage intraday Winner | Réponses fournisseurs et cache désormais dans le dossier du run isolé ; jamais dans les tables de cours ou le cache commun. GET historiques qualifiés seulement. |
| Rapports, courbes, diagnostics | Fichiers propres au run ; PNG produit avec Matplotlib dans le processus, sans lancer Chrome/Kaleido. |
| Backfills, calibrations, walk-forward, replays FR/CN non qualifiés ici | Verrou exclusif conservé. Aucun élargissement implicite à ces tâches. |

Les défauts `auto` ML/sentiment lisent les données disponibles. Ils ne sont pas
assimilés à une reconstruction. Les configurations inconnues restent exclusives.
La classification n'autorise jamais à elle seule les écritures : le processus
est protégé avant l'import du moteur de simulation.

## Protections du processus

L'IHM lance `backtesting.isolated_run`, qui n'accepte que `backtesting run` ou
`backtesting.winner_campaign_replay`, avec un `output_dir` sous l'espace du run.

- MySQL : `SET SESSION TRANSACTION READ ONLY` dès la création de connexion.
  Une garde SQL supplémentaire contrôle SQLAlchemy et le chemin DBAPI PyMySQL,
  y compris les connexions recréées par les helpers. DDL/DML, procédures,
  requêtes empilées, sorties fichier SQL et verrous applicatifs SQL sont refusés.
  Les lectures de schéma `SHOW CREATE TABLE` restent autorisées.
- SQLite : les bases de simulation en mémoire ou locales au run peuvent être
  écrites ; les fichiers SQLite partagés restent en lecture seule à la frontière SQL.
- Fichiers : les écritures Python applicatives, suppressions et renommages sont
  limités à l'espace du run. Les liens et sous-processus non qualifiés sont
  refusés. TEMP, caches Numba/Torch/Matplotlib/Parquet et rattrapage intraday y
  sont redirigés ; les `.pyc` sont désactivés. Les lectures Git `rev-parse`
  servent uniquement aux métadonnées ; `git status` n'est pas lancé.
- HTTP : GET/HEAD limités aux fournisseurs historiques raccordés. Les requêtes
  d'ordre ou LLM, et les hôtes non qualifiés, sont refusés.
- Une violation reste fatale même si une bibliothèque la capture : sortie en
  échec, `isolation.json` en échec, rapport éventuel marqué `FAILED_ISOLATION`.
  L'application ne transforme pas ce cas en résultat silencieusement dégradé.

Le canal nommé Windows de télémétrie TLS déjà hérité du poste est conservé :
ce n'est pas un fichier applicatif. Cela n'autorise pas un fichier de keylog
arbitraire et ne désactive ni TLS ni ses certificats.

Il s'agit de protections applicatives pour les chemins audités, pas d'une
isolation OS contre du code hostile ou des écritures natives arbitraires.
Les connexions utilisent des lectures indépendantes : **ce mode ne constitue
pas un instantané global figé de toutes les tables**. Un pipeline peut publier
de nouvelles données pendant la simulation ; les contrats de dates, disponibilité
et provenance du moteur restent nécessaires. Il ne corrige pas le biais de
survivance, les secteurs actuels ni les limites de reproduction OHLC.

## Verrous et suivi

| Activité | Scope | Coexistence avec pipeline |
| --- | --- | --- |
| Simulation US protégée | `backtesting_readonly` | Oui |
| Backtest ancien ou susceptible d'écrire | `backtesting` | Non |
| Workflow pipeline | `pipeline` | Un workflow à la fois |

Les vérifications/créations des fichiers de verrou sont sérialisées par un
verrou OS, en plus du verrou local des threads. Le PID réel de l'enfant et son
heure de création restent associés au verrou. La récupération et l'arrêt
après redémarrage de l'IHM reconnaissent les deux scopes de backtest. Un arrêt
d'un replay isolé ne supprime pas le verrou d'un pipeline parallèle.

Le registre conserve `isolation_mode` et la commande exacte. `isolation.json`
dans le dossier du run passe de RUNNING à COMPLETED/FAILED, puis son reçu est
joint au `run_metadata` du rapport. Les logs restent dans le dossier du run.

**Les processus déjà démarrés ne sont jamais convertis à chaud.** Le backtest
`20261101_104459_51fd640e`, lancé avant cette évolution, conserve son verrou
exclusif jusqu'à sa fin ou son arrêt demandé par l'utilisateur. Il n'a pas été
arrêté, relancé ni déverrouillé par cette intervention.

## Commande directe

Depuis la racine du projet, pour un nouveau dossier :

```powershell
python -B -u -m backtesting.isolated_run `
  --workspace artifacts/replays/mon-run `
  --module backtesting -- run `
  --start 2025-01-02 --end 2025-03-31 `
  --ml-mode off --sentiment-mode auto --no-winner-pyramiding `
  --output-dir artifacts/replays/mon-run/artifacts
```

Cette commande directe bénéficie des protections ; le suivi/arrêt dans l'IHM
nécessite un lancement par son registre. Le CLI historique sans cette enveloppe
ne doit pas être présenté comme protégé par ce nouveau contrat.

## Vérifications réelles bornées

Preuves sous `artifacts/operations/backtest_isolation_20261101` :

- `mysql-readonly-proof/server-proof.json` : `alpha_trade`,
  `@@session.transaction_read_only = 1`, vérifié par SELECT.
- `daily-smoke-v4/isolation.json` : replay standard des 29–30 octobre 2026,
  phases risque/exécution/protections/watcher/sorties appelées, exports réalisés,
  **zéro violation**, sortie 0. Cache propre au dossier, aucun ordre broker.
- Le contrôle borné n'est pas une mesure de performance ni une certification
  des phases métier : sa couverture ML est incomplète et le replay watcher
  existant rapporte des items en échec. Ces limites sont dans ses diagnostics ;
  elles ne sont pas neutralisées pour qualifier l'isolation des écritures.

Les essais préparatoires `daily-smoke` à `daily-smoke-v3` conservent leurs
échecs : canal TLS hérité, lecture de métadonnées SQL puis lectures Git non
encore qualifiées. Le blocage des écritures/effets non qualifiés a bien empêché
leur poursuite silencieuse ; les protections ont ensuite été corrigées sur
ces opérations précises, sans autoriser une classe générale d'écritures.

Validation automatisée : **117 tests ciblés réussis** sur isolation, registre,
Winner, rapports et commandes, puis **64 tests réussis** sur le sous-ensemble
isolation/verrous/registre après les derniers ajustements. Ces suites se
recouvrent. Le second passage comprend une course réelle entre deux processus,
la coexistence pipeline/replay dans les deux ordres de lancement, la reprise
du suivi et le maintien des exclusions entre travaux susceptibles d'écrire.
