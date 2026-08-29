# Contrôles opérationnels, circuit breaker et audit

Retour : [références Risk](README.md)

`DataAvailabilityGate` classe criticalité et renvoie `GateResult`. `FreshnessGate` vérifie plusieurs dimensions. `DriftMonitor` classe le drift. `PreLiveChecklist` agrège gates par stage shadow/paper/live. `OperationalControls` planifie smoke tests et probes.

`CircuitBreaker` inspecte drawdown, perte journalière et signaux opérationnels ; son état est persisté/alerté. `RampUpManager` gère les stages et transitions. `RegimeStateMachine` produit une transition et `TransitionHandler` la traduit en cancel/reduce/close.

`DecisionFingerprint` hash les inputs déterministes. `DecisionAuditLog`, `ImmutableJournal` et `ReplayVerifier` permettent de prouver/rejouer. `IdempotencyGate` détecte un calcul identique. `shadow_engine` produit un chemin alternatif sans mutation live ; `shadow_compare` explique les écarts.

Un contrôle bloquant ne doit pas être converti en warning pour terminer le pipeline. Conserver statut, preuve, horodatage, compte, config et action de reprise.

