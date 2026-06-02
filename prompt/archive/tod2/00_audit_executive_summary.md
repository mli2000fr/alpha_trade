# 00 — Synthèse exécutive de l’audit Alpha Trade

## Verdict court

Alpha Trade est une application de trading indépendante avancée, avec une architecture riche, une vraie volonté d’auditabilité et des garde-fous sérieux sur l’exécution. Elle n’est pas encore au niveau d’un système buy-side/proprietary desk mature : le socle est prometteur, mais plusieurs incohérences de conventions, de documentation, de configuration et d’exploitation empêchent encore de parler de production quasi institutionnelle.

**Note globale proposée : 7,8 / 10.**

**Verdict : pro-grade partiel avancé, exploitable en paper/simulation et envisageable en live pilote très discipliné, taille réduite et supervision stricte.**

## Constats majeurs

| Axe | Constat | Impact |
|---|---|---|
| Architecture | Découpage riche (`dataIntegrityEngine`, `screener`, `selector`, `risk_management`, `execution_engine`, `corporate_actions`, `backtesting`, `ihm`) mais orchestration encore locale/processus. | Bonne base, mais risque d’états partiels sans scheduler transactionnel. |
| Provider OHLCV | Le code courant confirme `EODHD` comme provider daily primaire via `config.yaml:181-183`, IHM route vers `import_eodhd_bar --write` (`ihm/services/pipeline_runner.py:1494-1506`). | Choix cohérent pour corriger les limites IEX, mais la transition n’est pas entièrement purgée dans la doc et le schéma. |
| Conventions prix | `data_adjustment='split'` est imposé par les schémas SQL (`database/sql/stock/stock_bars.sql:15-20`, `stock_bars_daily.sql:20-27`). | Convention saine, mais nécessite discipline stricte entre EODHD, corporate actions et backtesting. |
| IHM → backend | L’IHM construit réellement les commandes principales (`build_pipeline_command`, `PipelineStepDefinition`). | Bon alignement global, mais certaines options/configs restent non effectives ou peu visibles. |
| Exécution | `run_execution.py` bloque le fallback d’equity broker à 100k en paper/live, impose un preflight live, exige un token d’approbation (`ALPHA_TRADE_LIVE_APPROVAL_TOKEN`) et fige un run plan immuable pour les runs live. | Très bon garde-fou opérateur ; encore dépendant d’un processus local et d’une discipline humaine forte. |
| Corporate actions | Factory provider sélectionne EODHD si `bars_provider=eodhd` (`corporate_actions/provider.py:402-432`). | Cohérent, mais l’apply dépend de snapshots broker disponibles (`corporate_actions/engine.py:202-213`). |
| Backtesting | Beaucoup de briques de fidélité PIT existent, mais le backtest force EODHD dans la doc et probablement dans le loader ; la parité live n’est pas totale. | Bon outil de recherche, pas encore preuve institutionnelle. |
| Tests | Environ 298 fichiers de tests détectés ; plusieurs tests ciblés existent. La couverture JSON disponible est non fiable/partielle. | Bon volume, mais la robustesse réelle doit être verrouillée par des tests de conventions et E2E plus stricts. |

## Risques prioritaires

1. **P1 — Aucun workflow CI sécurité versionné n’est encore présent dans le repo.** Les scans CVE/secrets/SBOM existent, mais ne sont pas imposés par un pipeline bloquant versionné.
2. **P1 — Les runbooks incidents exhaustifs restent incomplets côté dépôt.** Broker outage, provider outage, DB outage et partial fill ne sont pas encore couverts de façon homogène.
3. **P1 — L’orchestration reste majoritairement locale via l’IHM et des sous-processus.** La plateforme est robuste, mais pas encore opérée comme un orchestrateur transactionnel durable.
4. **P1 — Le versioning multi-source daily n’est pas natif dans `stock_bars_daily`.** Le choix de source unique active est désormais clarifié, mais limite la cohabitation simultanée auditée en base.
5. **P1 — La parité backtest/live a beaucoup progressé, sans être totalement automatique partout.** Elle reste dépendante des bons profils/presets et d’une discipline d’exploitation.
6. **P2 — L’observabilité est riche mais encore distribuée.** Il manque toujours un niveau de monitoring/alerting centralisé de type production durable.

## Ce qui est déjà fort

- Provider switch OHLCV explicite dans le code IHM et imports.
- Convention `split-only` matérialisée par CHECK SQL.
- Exécution avec preflight live, interdiction de fallback equity silencieux, modes `simulate/paper/live`, contraintes cash/PDT/swing.
- Token d’approbation live obligatoire + run plan immuable côté `run_execution.py`.
- Policy secrets live explicite : Vault requis par défaut, ou override assumé `ALPHA_TRADE_LIVE_SECRET_POLICY=env`.
- Scripts sécurité disponibles et testés (`generate_sbom.py`, `scan_cves.py`, `scan_repo_secrets.py`, `verify_vault_rotation.py`).
- Nombreux modules de run summaries, audit trail et tables canoniques.
- Corporate actions séparées des prix historiques : dividendes via ledger, splits sur positions.
- Profil strict swing centralisé dans `core/filter_profiles.py` et alias rétrocompatible `selector/strict_filter_profiles.py`.

## Ce qui empêche le niveau institutionnel

- Pas d’orchestrateur transactionnel de bout en bout ; l’IHM lance des sous-processus.
- Quelques sections documentaires historiques et certains runbooks restent à homogénéiser.
- La validation systématique des contrats config/code/CI n’est pas encore totalement centralisée.
- Parité backtest/live encore complexe, opt-in et difficile à garantir systématiquement.
- Observabilité riche mais distribuée : logs, artifacts, tables, run summaries ; manque une vue incident unique et des SLO/SLA opérationnels.
- Secrets et sécurité sensiblement renforcés au runtime, mais pas encore politique complète de rotation, séparation d’environnements, workflow CI sécurité versionné dans le repo, ni runbooks incident exhaustifs.

## Décision opérationnelle recommandée

- **Simulation/paper** : OK pour usage intensif avec monitoring.
- **Live réel très petit capital** : envisageable avec `simulate`/`paper` validés sur plusieurs cycles complets, preflight vert, token live actif, policy secrets live satisfaite (Vault ou override `env` assumé), run plan immuable et allocation pilote strictement plafonnée.
- **Production quasi pro** : le socle S0 à S8 runtime/IHM/tests est désormais largement en place ; l’absence de workflow CI sécurité versionné reste toutefois un verrou avant un go-live plus ambitieux.

