# 00 — Synthèse exécutive de l’audit Alpha Trade

## Verdict court

Alpha Trade est une application de trading indépendante avancée, avec une architecture riche, une vraie volonté d’auditabilité et des garde-fous sérieux sur l’exécution. Elle n’est pas encore au niveau d’un système buy-side/proprietary desk mature : le socle est prometteur, mais plusieurs incohérences de conventions, de documentation, de configuration et d’exploitation empêchent de parler de production quasi institutionnelle.

**Note globale proposée : 6,8 / 10.**

**Verdict : pro-grade partiel, exploitable en paper/simulation et exploitable en réel uniquement après corrections P0/P1, taille réduite et supervision stricte.**

## Constats majeurs

| Axe | Constat | Impact |
|---|---|---|
| Architecture | Découpage riche (`dataIntegrityEngine`, `screener`, `selector`, `risk_management`, `execution_engine`, `corporate_actions`, `backtesting`, `ihm`) mais orchestration encore locale/processus. | Bonne base, mais risque d’états partiels sans scheduler transactionnel. |
| Provider OHLCV | Le code courant confirme `EODHD` comme provider daily primaire via `config.yaml:181-183`, IHM route vers `import_eodhd_bar --write` (`ihm/services/pipeline_runner.py:1494-1506`). | Choix cohérent pour corriger les limites IEX, mais la transition n’est pas entièrement purgée dans la doc et le schéma. |
| Conventions prix | `data_adjustment='split'` est imposé par les schémas SQL (`database/sql/stock/stock_bars.sql:15-20`, `stock_bars_daily.sql:20-27`). | Convention saine, mais nécessite discipline stricte entre EODHD, corporate actions et backtesting. |
| IHM → backend | L’IHM construit réellement les commandes principales (`build_pipeline_command`, `PipelineStepDefinition`). | Bon alignement global, mais certaines options/configs restent non effectives ou peu visibles. |
| Exécution | `run_execution.py` bloque le fallback d’equity broker à 100k en paper/live (`run_execution.py:638-659`) et impose preflight live (`run_execution.py:576-620`). | Très bon garde-fou ; encore dépendant d’un opérateur humain et d’un processus local. |
| Corporate actions | Factory provider sélectionne EODHD si `bars_provider=eodhd` (`corporate_actions/provider.py:402-432`). | Cohérent, mais l’apply dépend de snapshots broker disponibles (`corporate_actions/engine.py:202-213`). |
| Backtesting | Beaucoup de briques de fidélité PIT existent, mais le backtest force EODHD dans la doc et probablement dans le loader ; la parité live n’est pas totale. | Bon outil de recherche, pas encore preuve institutionnelle. |
| Tests | Environ 298 fichiers de tests détectés ; plusieurs tests ciblés existent. La couverture JSON disponible est non fiable/partielle. | Bon volume, mais la robustesse réelle doit être verrouillée par des tests de conventions et E2E plus stricts. |

## Risques prioritaires

1. **P0 — Documentation et runbooks encore contradictoires sur EODHD vs Alpaca.** Le fichier `doc/dataIntegrityEngine.md` garde des séquences quotidiennes `import_alpaca_bar` alors que l’IHM route vers EODHD quand `bars_provider=eodhd`.
2. **P0 — `market_data.fallback_on_failure` est configuré mais non consommé par le code Python hors tests.** Cela crée un faux sentiment de fallback automatique.
3. **P1 — Schéma `stock_bars_daily` documente une cohabitation `alpaca_iex` + `eodhd_eod` sur la même clé `(symbol,date)`, mais la PK est `(symbol,date)`.** La cohabitation réelle n’est pas possible dans cette table sans écrasement.
4. **P1 — Le pipeline historique quotes depuis l’univers large peut être très lent et coûteux.** Les logs/résumés récents montrent un run de quotes interrompu après un long traitement.
5. **P1 — Les presets petits comptes sont pragmatiques mais parfois incohérents avec leur description.** Exemple : tranche `0_2000_eur` annonce ticket minimum bas mais fixe `risk_min_position_notional=500`, ce qui concentre fortement.
6. **P1 — Le backtesting reste crédible pour recherche avancée, mais pas encore preuve de parité live complète.** Les phases opt-in sont puissantes mais peuvent donner une fausse assurance si non activées.

## Ce qui est déjà fort

- Provider switch OHLCV explicite dans le code IHM et imports.
- Convention `split-only` matérialisée par CHECK SQL.
- Exécution avec preflight live, interdiction de fallback equity silencieux, modes `simulate/paper/live`, contraintes cash/PDT/swing.
- Nombreux modules de run summaries, audit trail et tables canoniques.
- Corporate actions séparées des prix historiques : dividendes via ledger, splits sur positions.
- Profil strict swing centralisé dans `core/filter_profiles.py` et alias rétrocompatible `selector/strict_filter_profiles.py`.

## Ce qui empêche le niveau institutionnel

- Pas d’orchestrateur transactionnel de bout en bout ; l’IHM lance des sous-processus.
- Documentation encore en partie post-correctifs, avec sections historiques contradictoires.
- Paramètres non consommés ou insuffisamment testés (`fallback_on_failure`, certains defaults market-aware).
- Parité backtest/live encore complexe, opt-in et difficile à garantir systématiquement.
- Observabilité riche mais distribuée : logs, artifacts, tables, run summaries ; manque une vue incident unique et des SLO/SLA opérationnels.
- Secrets et sécurité améliorés, mais pas encore politique complète rotation, séparation environnements, CI sécurité bloquante, runbook incident.

## Décision opérationnelle recommandée

- **Simulation/paper** : OK pour usage intensif avec monitoring.
- **Live réel très petit capital** : possible uniquement après traitement P0/P1, avec `simulate`/`paper` validé sur plusieurs cycles complets, `execution_mode=paper` comparé à backtest/replay et `live` limité à une allocation pilote.
- **Production quasi pro** : viser les sprints S0 à S4 du plan, puis évaluer un go-live discipliné.

