# Audit d'implémentation des Sprints risque 0 à 15

Date de l'audit : 2026-07-12  
Document de référence : `prompt/md_risque.md`

## Conclusion exécutive

Le document décrit **seize Sprints numérotés de 0 à 15**, malgré la formulation « 15 Sprints ».

Les composants annoncés existent majoritairement et la couverture unitaire est importante. Après corrections, les suites auditées sont vertes :

- 726 tests `tests/test_risk_*.py` réussis ;
- 352 tests transversaux ML, PIT, labels, benchmark, bridge, portefeuille et walk-forward réussis ;
- 3 warnings pandas non bloquants dans `execution_lifecycle_replay.py`.

Le verdict n'est toutefois pas « go-live démontré ». Les commentaires du document confondent parfois trois niveaux différents :

1. une primitive ou un DTO existe ;
2. la primitive est raccordée à un chemin runtime ;
3. le gate est prouvé sur des données et artefacts opérationnels réels.

Le niveau 1 est largement atteint, le niveau 2 est atteint sur une grande partie de la chaîne, mais le niveau 3 ne l'est pas globalement. Aucun artefact réel n'a été trouvé dans le workspace pour les baselines, benchmarks, campagnes, réconciliations quotidiennes ou transitions de ramp-up. Le système doit donc rester **NO-GO live 100 %** tant que les preuves opérationnelles listées plus bas ne sont pas produites.

## Méthode

L'audit a confronté :

- les objectifs et gates des sections « Sprint maître 0 à 15 » ;
- les fiches Sprint et les commentaires `AUDIT 2026-07-12` ;
- les appels runtime dans `risk_management`, `modelFactory`, `backtesting`, `execution_engine` et `run_execution.py` ;
- les tests cités par le document ;
- la présence effective des artefacts annoncés sous `artifacts/`.

Statuts utilisés :

- **Implémenté** : code raccordé et tests exécutables cohérents avec le gate technique ;
- **Partiel** : primitives présentes, mais raccordement ou preuve opérationnelle incomplète ;
- **Non démontré** : aucune exécution réelle/artefact ne permet de fermer le gate de production.

## Résultat Sprint par Sprint

| Sprint | Sujet | Verdict | Éléments vérifiés | Réserve principale |
|---:|---|---|---|---|
| 0 | Baseline et décision ternaire | Partiel | Policy ternaire commune, timing et blocage `research_only` testés | Générateur présent, mais aucun JSON de baseline archivé dans `artifacts/baselines/` |
| 1 | Métriques, calibration, champion | Partiel | Métriques multiclasses, anti-collapse et sélection champion testés | Aucun rapport réel de promotion/benchmark trouvé ; migration des artefacts legacy non prouvée |
| 2 | Données PIT et univers historique | Implémenté techniquement | Enrichissement PIT, lineage univers, convention de prix, rapport qualité et entry gate raccordés | La couverture réelle de toutes les sources externes doit encore être prouvée par un rapport quotidien produit |
| 3 | Labels swing tradables | Implémenté techniquement | Triple-barrier, coûts canoniques, parité fixtures et isolation des folds testés ; le CLI et le dataset nominal servent désormais les labels triple-barrier avec purge `max_sessions` | Un entraînement complet et un rapport OOS réels restent à archiver |
| 4 | Benchmark et anti-collapse | Implémenté techniquement | LightGBM/CatBoost/LSTM/global, complexité et quality gates testés | Aucun benchmark multi-seeds sur données réelles n'est archivé |
| 5 | Contrat ML vers risque | Implémenté avec compatibilité | `MLRankedCandidate`, payload complet, persistance idempotente et parité bridge/CLI testés | Le builder reconvertit encore temporairement vers les DTO legacy internes |
| 6 | Contraintes directionnelles/config | Implémenté techniquement | Loader typé, revalidation finale, contraintes signées et factorielles raccordés | La parité effective IHM/CLI/backtest doit être certifiée par artefact de fingerprint commun |
| 7 | Walk-forward financier | Partiel | Moteur financier, CLI, bridge ML-first, métriques et rapport reproductible testés | Aucun rapport OOS réel n'est présent ; le tuning train-only reste en partie une responsabilité du caller |
| 8 | Edge net, abstention, sizing | Implémenté techniquement | `EdgeCalculator` et `AbstentionPolicy` sont appelés dans `PortfolioBuilder` | Les seuils doivent encore être validés sur résultats OOS réels, pas uniquement fixtures |
| 9 | Régime et événements | Partiel | Machine d'état, persistance de plan et exécution cancel puis liquidation raccordées | Le snapshot « réel » du CLI provient en partie de snapshots DB/décisions précédentes, pas d'une preuve broker fraîche de bout en bout |
| 10 | Liquidité, borrow, capacité | Partiel | Quotes, ADV PIT, covariance, pre-submission gate et borrow Alpaca raccordés | Alpaca ne fournit ici que des booléens asset : quantité, fee réel, locate et expiry ne sont pas disponibles ; ces champs ne doivent pas être inventés |
| 11 | Optimisation portefeuille | Partiel | Optimiseur, holdings, deltas, contraintes post-arrondi et action `side_flip` close-first raccordés | La nouvelle entrée est différée au cycle suivant, après confirmation broker de la clôture ; la preuve broker complète close-confirmed puis reopen reste à archiver |
| 12 | Parité, fills et protections | Partiel | Le fingerprint accompagne maintenant le payload OMS persistant ; chaque fill et réparation watcher persiste un `ProtectionState` atomique avec verdict de contrat | Le fingerprint n'a pas encore de colonne dédiée dans le schéma SQL ; une violation persistante déclenche désormais un force-close automatique quand configuré |
| 13 | MLOps, drift, rollback | Partiel | Freshness gate, registry JSON atomique et rollback persisté journalisé sont raccordés ; `scripts/rollback_model_registry.py` fournit l'entrypoint opérateur | La compatibilité feature schema/policy/calibrateur et données reste incomplète avant publication |
| 14 | Shadow et paper | Implémenté techniquement | Historique rechargé, runners risque/exécution non-shell configurables, résumés atomiques et manifest HMAC-SHA-256 | Les commandes et la clé de signature doivent être configurées, puis une campagne réelle doit être archivée |
| 15 | Go-live progressif/opérations | Implémenté techniquement | Réconciliation OMS avec ledger interne, `RampUpManager` autorité de transition, budget appliqué au CLI risque et force-close post-protection | Aucune preuve d'exécution réelle paper/live n'est encore archivée |

## Corrections appliquées pendant l'audit

### Sécurité opérationnelle

1. Les probes critiques ne passent plus silencieusement au vert quand le broker, le breaker, le registry ou le watcher sont absents.
2. Le watcher live est contrôlé via son heartbeat DB, avec une ancienneté maximale.
3. Un rapport `DailyReconciliation` vide est maintenant `PENDING` et non `MATCHED`.
4. La réconciliation utilise les vraies méthodes de `BrokerAdapter` (`get_all_positions`, `list_recent_orders`, `get_account_snapshot`) au lieu de méthodes inexistantes.

### Borrow et transitions

5. Une erreur Alpaca borrow ne produit plus un faux `EASY_TO_BORROW`. Le symbole devient `NOT_SHORTABLE`, avec quantité disponible nulle.
6. Les champs asset absents ont désormais des défauts fermés (`shortable=False`, `easy_to_borrow=False`).
7. Les liquidations/réductions de régime utilisent une nouvelle primitive `BrokerAdapter.submit_market_order()` ; l'ancien appel visait une méthode inexistante.
8. Un test vérifie que l'annulation précède la liquidation.

### Journal et campagne

9. Les transitions de ramp-up sont enregistrées avec les vraies API `ImmutableJournal.load()`, `append()` et `save_atomic()`. L'ancien code appelait `load_or_create()` et `add_entry()`, méthodes inexistantes, puis basculait vers un JSON non chaîné.
10. Le journal d'approbation de campagne utilise également la chaîne immuable réelle.
11. Une journée de campagne sans résumé risque, sans exécution paper ou sans shadow compare ne peut plus être marquée `completed`.

### Benchmark et cohérence ML-first

12. L'adaptateur benchmark LSTM importe maintenant `tabular_split` depuis son module réel.
13. Une assertion de stabilité multi-seeds déplacée par erreur a été restaurée dans le bon test.
14. Deux tests legacy ont été alignés sur le contrat ML-first : une probabilité ML absente est une erreur et les anciens poids de fusion ne déterminent plus le ranking.

## Écarts bloquants restants

### P0 — avant tout live

Les protections suivantes sont désormais présentes :

1. **Réconciliation OMS** : `run_execution.py` charge par `exec_run_id` les intentions, soumissions, fills liés à `request_id` et protections ouvertes depuis les tables OMS ; positions et cash broker restent des preuves externes. Le rapport reste `PENDING` si les preuves sont absentes.
2. **Ramp-up gouverné** : `CampaignOrchestrator` recharge l'état, délègue les promotions à `RampUpManager`, persiste le budget effectif dans les paramètres journaliers et écrit promotion ou rollback dans `ImmutableJournal` avec les métriques disponibles. La commande `promote` ne modifie plus directement la phase.
3. **Historique et preuves de campagne** : chaque résultat quotidien et manifest SHA-256 des résumés est atomique ; une nouvelle instance recharge l'historique avant rapport ou promotion. Les résumés risque, paper et shadow compare restent obligatoires et leur absence échoue le cycle.
4. **Protections post-fill** : le fingerprint est enregistré dans le payload OMS, et un état par fill avec vérification est persisté atomiquement. Le watcher consigne une violation résiduelle comme incident critique nécessitant une revue force-close après tentative de réparation.

Les écarts P0 de code sont fermés :

5. **PnL et cash internes** : `ExecutionRepository.load_internal_ledger_for_run()` calcule les flux de cash, le PnL réalisé et le mark-to-market depuis les fills, lots et positions OMS ; `run_execution.py` les rapproche du snapshot broker post-run.
6. **Budget appliqué aux entrypoints** : `--risk-budget-dollars` remplace explicitement le taux de risque par position après résolution de l'equity. Le runner campagne injecte le budget effectif de palier et le CLI risque l'emploie pour le sizing.
7. **Processus de campagne exécutable** : `risk_command` et `execution_command` sont des listes JSON non-shell. La campagne archive le reçu (code retour et hash stdout/stderr), exige les résumés atomiques produits par les CLI, et signe le manifest HMAC-SHA-256 avec la clé indiquée par `signing_key_env`. Hors shadow, l'absence de clé bloque le cycle.
8. **Remédiation finale de protection** : un contrat restant invalide après réparation arme un ordre marché opposé `force_close`, le persiste dans l'OMS et consigne soit la soumission, soit l'échec critique.

Les prérequis opérationnels maintiennent toutefois le **NO-GO live** jusqu'à leur réalisation : configurer les deux commandes de campagne et `ALPHA_TRADE_CAMPAIGN_SIGNING_KEY`, vérifier les permissions broker paper, puis archiver les résultats d'une campagne shadow et paper complète.

### P1 — fermeture des gates de modèle

5. **Triple-barrier servi** : le CLI expose les paramètres, le dataset nominal produit les labels, et l'optimisation train-only applique les barrières retenues avec une purge égale à `max_sessions`.
6. **Rollback MLOps** : `rollback_persisted_registry()` remplace le registre atomiquement, restaure en cas d'échec de journalisation et écrit l'avant/après dans `ImmutableJournal`; `scripts/rollback_model_registry.py` est l'entrypoint opérateur.
7. **Compatibilité complète** : reste ouverte. Vérifier modèle, calibrateur, policy, feature schema et fingerprints de données avant publication, en échec fermé lorsque la preuve est absente.
8. **Flip de side** : l'action de réconciliation `side_flip` ne soumet que la clôture de la position courante ; l'entrée opposée est différée jusqu'à une confirmation broker dans le cycle suivant. Une preuve broker intégrée reste requise.

### P2 — preuves opérationnelles

9. **Baseline réelle Sprint 0** : `scripts/produce_baseline_artifact.py` refuse désormais les placeholders ; il exige un JSON de métriques `long`/`short`/`flat` calculées et un fingerprint de données non `unknown` avant toute écriture sous `artifacts/baselines/`. Une exécution réelle reste à produire et archiver.
10. Produire un benchmark multi-seeds réel et un rapport de promotion Sprint 4.
11. Produire un walk-forward OOS réel avec coûts, régimes et holdout intact Sprint 7.
12. **Campagne shadow/paper** : les configurations, revues hebdomadaires et rapports de campagne sont maintenant écrits atomiquement. Exécuter et archiver quatre semaines shadow puis huit à douze semaines paper reste requis.
13. Conserver les artefacts de smoke tests, réconciliations, incidents et transitions de palier ; aucun artefact réel ne doit être déduit de l’existence des scripts.

## Tests exécutés

```text
pytest tests/test_risk_*.py -q -p no:cov -o "addopts="
726 passed

Suite transversale ciblée :
ML ternaire + timing + contrat, PIT + lineage + prix, qualité quotidienne,
entry gate, labels + optimisation, dataset, benchmark, walk-forward,
bridges, portfolio builder et contraintes.
352 passed, 3 warnings

Suites ciblées supplémentaires :
- Sprint 15 + execution DB IO : 74 passed
- CLI + liquidité : 102 passed
- campagne Sprint 14 : 47 passed
- run_execution + trading client : 20 passed
- benchmark complet : 49 passed
- P0 consolidé (campagne, CLI, ledger, réconciliation, watcher, config) : 169 passed
- P2 baseline de preuve : 2 passed
- P2 campagne (persistance des preuves) : 48 passed
```

Les tests DB/broker utilisent principalement des doubles ou des bases locales. Aucun appel live réel n'a été effectué pendant cet audit.

## Décision d'audit

- **Recherche/backtest local** : GO sous réserve des données utilisées.
- **Shadow** : GO technique après configuration des artefacts et du scheduler.
- **Paper** : GO conditionnel, seulement avec campagne réellement alimentée et réconciliation complète.
- **Live 5 %** : NO-GO tant que les prérequis de clés/commandes ne sont pas configurés et qu'une campagne paper conforme n'est pas archivée.
- **Live 10–100 %** : NO-GO ; aucune preuve de ramp-up réel n'est présente.

En conséquence, les Sprints peuvent être considérés comme **développés au niveau composants**, mais pas tous **terminés au niveau gate de production**.

## Compte rendu P0, P1 et P2

Non. J’ai fermé les écarts de code les plus concrets, mais je n’ai pas, et ne peux pas honnêtement, déclarer tous les P0/P1/P2 terminés.

**P0**
Le code est essentiellement fermé : réconciliation OMS et ledger interne, orchestration de ramp-up, commandes campagne, signatures, résumés atomiques, protections post-fill et force-close.  
Il reste le passage opérationnel obligatoire : configurer les commandes et la clé HMAC, vérifier les permissions broker paper, puis exécuter et archiver une campagne shadow et paper complète. Tant que ces preuves n’existent pas, le live reste **NO-GO**.

**P1**
Trois sujets ont été implémentés :
- triple-barrier réellement servi par le CLI/dataset/trainer ;
- rollback de registry persistant, atomique et journalisé ;
- flip de side close-first, avec réouverture différée au cycle suivant.

Il reste un sujet P1 majeur : la **compatibilité complète avant publication**. Le runtime doit vérifier et refuser en échec fermé le modèle, calibrateur, policy, schéma de features et fingerprint de données. Aujourd’hui, le registre absent ou illisible reste traité de façon trop permissive.

**P2**
Je n’ai pas produit de preuves réelles, car cela demande des données, des commandes configurées et potentiellement un broker paper. J’ai seulement renforcé l’outillage :
- une baseline ne peut plus être générée avec des métriques placeholder ;
- les rapports et revues de campagne sont écrits atomiquement.

Il reste à exécuter et archiver :
- une baseline réelle ;
- un benchmark multi-seeds et un rapport de promotion ;
- un walk-forward OOS avec coûts, régimes et holdout ;
- quatre semaines shadow puis huit à douze semaines paper ;
- les smoke tests, réconciliations, incidents et transitions associés.

L’état exact est maintenu dans ce document : P0 code fermé mais non prouvé en opérations, P1 partiellement fermé avec la compatibilité complète encore ouverte, et P2 à produire réellement.