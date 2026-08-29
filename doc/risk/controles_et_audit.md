# Contrôles opérationnels, circuit breaker et audit

Retour : [références Risk](README.md)

`DataAvailabilityGate` classe criticalité et renvoie `GateResult`. `FreshnessGate` vérifie plusieurs dimensions. `DriftMonitor` classe le drift. `PreLiveChecklist` agrège gates par stage shadow/paper/live. `OperationalControls` planifie smoke tests et probes.

`CircuitBreaker` inspecte drawdown, perte journalière et signaux opérationnels ; son état est persisté/alerté. `RampUpManager` gère les stages et transitions. `RegimeStateMachine` produit une transition et `TransitionHandler` la traduit en cancel/reduce/close.

`DecisionFingerprint` hash les inputs déterministes. `DecisionAuditLog`, `ImmutableJournal` et `ReplayVerifier` permettent de prouver/rejouer. `IdempotencyGate` détecte un calcul identique. `shadow_engine` produit un chemin alternatif sans mutation live ; `shadow_compare` explique les écarts.

Un contrôle bloquant ne doit pas être converti en warning pour terminer le pipeline. Conserver statut, preuve, horodatage, compte, config et action de reprise.

## Data criticality

`DataCriticality` classe les sources ; `AvailabilityStatus` décrit présence/fraîcheur ; `DataAvailabilityGate` renvoie go, blocages et dégradations. La fonction de convenance `check_data_availability` utilise les mêmes règles. La criticité dépend de l'usage : borrow est critique pour un short, pas pour un long.

## Freshness multidimensionnelle

`FreshnessDimension` couvre prix, prédiction/modèle, régime, calibration et autres timestamps configurés. `FreshnessConfig` fixe les âges max. `FreshnessGate` compare à `now/cutoff` et retourne par dimension age/status/reason.

Une date future est une erreur PIT, pas une donnée « très fraîche ». Les horloges timezone-aware/naive doivent être normalisées avant comparaison.

## Drift

`DriftMonitor` produit un statut par dimension et un `DriftReport`. Il distingue warning/critical selon seuils. Le drift peut venir de distributions de features, prédictions, couverture ou autres mesures prévues. Un drift critique peut activer gate/rollback ; il ne doit pas réentraîner automatiquement sur les données du jour.

## Pre-live checklist

`PreLiveChecklist` agrège des `ChecklistGate` en `GoLiveGate`. Les stages shadow, paper et live ont des exigences croissantes. `evaluate_pre_live_gates` fournit l'évaluation. Un gate `FAIL` empêche le GO ; warnings doivent être explicitement visibles.

## Smoke tests et probes

`OperationalControls` exécute des `SmokeTest` selon fréquence. `build_operational_probes` raccorde DB, broker, watcher, données et autres contrôles. `run_pre_session_smoke_tests` doit être lancé avant mutations. Les résultats persistés incluent durée, statut et erreur.

## Circuit breaker

Le breaker surveille limites de perte/drawdown et signaux opérationnels. Il renvoie `CircuitBreakerStatus`, persiste/alerte et met à jour Prometheus. L'état actif doit être lu par le risque et l'exécution ; un nouveau process ne le remet pas implicitement à zéro.

Le drawdown se calcule par rapport au peak défini par le contrat. Une correction de cash/dividende ne doit pas être confondue avec une perte de marché. Les seuils PROD et backtest sont distincts dans `config.yaml`.

## Ramp-up

`RampUpStage` et `RampUpManager` contrôlent la montée shadow→paper→live/exposition selon configuration. `StageTransition` conserve ancien/nouveau stage, raisons et date. `persist_ramp_up_transition` écrit l'audit.

Une période calme ne suffit pas si des gates restent en erreur. Une régression ou un incident peut ramener à un stage plus prudent.

## Machine de régime et transition portefeuille

`RegimeStateMachine` calcule `RegimeTransition`. `TransitionHandler` transforme cette transition en `PositionTransitionPlan` avec steps cancel/reduce/close. Le plan sépare les ordres ouverts des positions et reste déterministe.

## Fingerprint de run

`DecisionFingerprint` hash trade date, run id, config fingerprint, model run, policy version, universe, regime et candidate count. Comme le run id est inclus, deux runs logiquement identiques avec ids différents peuvent avoir des fingerprints différents ; l'usage exact doit être interprété selon le helper/gate courant.

`PositionDecisionFingerprint` ajoute symbole, côté, probabilités, edge, prix, ATR et ADV avec arrondis canoniques. Il permet de localiser quel input a changé entre deux décisions.

## Audit log et replay

`AuditLogEntry` conserve proposé/approuvé, entrée/stop, prédiction, edge, ATR, config, modèle et version. `DecisionAuditLog` agrège par journée et compte accepted/rejected/reduced.

`ReplayVerifier` compare fingerprint parent, nombre d'entrées, symboles, décision, shares, côté et fingerprint position. Décision/quantité/côté divergent = erreur ; fingerprint seul divergent = warning d'inputs. `parity_pct` est matching symbols / original count.

## IdempotencyGate

Le gate mémoire indexe fingerprint→run id et signale un duplicate. Il protège dans un process ; une idempotence inter-process exige aussi persistance/clé DB. `clear()` ne doit pas être utilisé pour contourner un doublon réel.

## Immutable journal

`ImmutableJournal` chaîne les entrées et leurs types afin de détecter modification. Une correction s'ajoute comme nouvel événement compensatoire ; elle ne réécrit pas l'entrée historique.

## Shadow

`ShadowEngine` calcule des décisions/fills simulés sans envoyer d'ordres. `compare_shadow_to_live` et `shadow_compare.compare_runs` mesurent drift de décisions/tailles. Les shadow rows sont clairement identifiées et ne doivent pas alimenter les targets live.

## Alertes

Les alertes doivent contenir event, run/account, seuil, valeur et action recommandée sans secret. Un échec d'envoi ne désactive pas le breaker ; il produit un incident d'observabilité séparé.

## Runbook incident

1. geler les nouvelles entrées ;
2. capturer statuses/gates et timestamps ;
3. vérifier equity/cash/positions au broker ;
4. identifier première dimension failed ;
5. corriger source, pas le seuil dans l'urgence ;
6. rejouer shadow/check ;
7. réarmer/ramp-up selon politique ;
8. conserver transition et justification.

## Tests

Critical/required/optional, future/stale, chaque dimension fraîcheur, drift warning/critical, checklist stages, breaker trip/recovery, ramp transitions, fingerprints déterministes, replay mismatches, duplicate gate, journal tampering, shadow isolation et alert failure.
