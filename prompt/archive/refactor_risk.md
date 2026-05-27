# Audit et plan de refactor — module `risk_management`

_Date : 2026-05-20_

> **Mise à jour d'avancement — 2026-05-20 (après implémentation P2/P3 ciblée)**
>
> - **P2 livré sur le périmètre `risk_management`** : `ruff check risk_management` OK, doc réalignée, redondances builder réduites, standardisation `SizingMethod` / `DecisionReasonCode` effectivement utilisée.
> - **P0 / P1 revérifiés** : les items ciblés sont désormais effectivement câblés et couverts par tests ciblés (régime live, circuit breaker notify-once, Kelly effectif, agrégation notional, equity breakdown PIT, motifs structurés, preflight data-quality, métadonnées summary).
> - **P3 désormais livré à un niveau opérationnel avancé** : shadow compare pilotable depuis le runtime/IHM, artefacts de post-mortem enrichis exposés dans le `run_summary`, et boucle empirique de calibration conviction/Kelly branchée via `weights_calibration_runs` avec segmentation `régime × horizon × fenêtre`, gouvernance live, drifts inter-segments, fallback détaillé et politique YAML configurable.
> - **Reste ouvert en P3** : montée en gamme métier de cette boucle empirique (objectifs business plus riches, monitoring/audit persisté des fallbacks live, visualisations encore plus avancées, multi-objectifs éventuels).

## 1. Périmètre audité

Fichiers principaux relus :
- `risk_management/cli.py`
- `risk_management/config.py`
- `risk_management/models.py`
- `risk_management/db_io.py`
- `risk_management/portfolio_builder.py`
- `risk_management/position_sizer.py`
- `risk_management/kelly.py`
- `risk_management/constraints.py`
- `risk_management/risk_checker.py`
- `risk_management/circuit_breaker.py`
- `risk_management/correlation_filter.py`
- `risk_management/ml_gate.py`
- `risk_management/audit.py`
- `risk_management/regime_apply.py`
- `risk_management/shadow_compare.py`
- `risk_management/run_risk.py`
- `risk_management/__main__.py`

Intégrations relues :
- `ihm/services/run_summary.py`
- `ihm/pages/risk.py`
- `ihm/pages/_shared.py`
- `ihm/services/pipeline_runner.py`
- `service/market/models.py`
- `service/market/__init__.py`
- `database/sql/corporate_actions/portfolio_cash_ledger.sql`
- `doc/risk_management.md`

Tests relus / exécutés :
- `tests/test_portfolio_builder.py`
- `tests/test_risk_management_cli.py`
- `tests/test_risk_management_run_summary.py`
- `tests/test_db_io_v2.py`
- `tests/test_risk_regime_apply.py`
- `tests/test_risk_regime_sizing_constraints.py`
- `tests/test_risk_checker.py`
- `tests/test_run_risk_circuit_breaker_wired.py`
- `tests/test_risk_shadow_compare.py`
- `tests/test_position_sizer_telemetry.py`
- `tests/test_position_sizer.py`
- `tests/test_constraints.py`
- `tests/test_kelly_sizer.py`
- `tests/test_circuit_breaker.py`
- `tests/property/test_circuit_breaker_properties.py`
- `tests/test_ml_disable_modes.py`
- `tests/test_phase2_risk_bridge_regime.py`
- `tests/test_capital_preset_risk_overrides.py`

---

## 2. Résumé exécutif

Le module `risk_management` est **globalement sérieux, utile et déjà assez industrialisé** :
- la séparation des responsabilités est claire ;
- le repository SQL a une vraie sémantique **point-in-time** sur plusieurs flux critiques ;
- le `run_summary` est riche et bien branché à l’IHM ;
- la couverture de tests ciblés est bonne, y compris sur des invariants métier concrets.

### Conclusion
Le module est **fonctionnel, mature et désormais cohérent** sur les anomalies
structurantes initialement identifiées dans cet audit.

Les écarts qui motivaient le plan P0/P1/P2 ont été corrigés dans le runtime,
les tests ciblés et la documentation. Le travail P3 a en outre dépassé la
première boucle prévue initialement en ajoutant une segmentation gouvernée des
calibrations empiriques et une visibilité opérateur dédiée dans l’IHM.

Les écarts encore ouverts ne relèvent plus du “correctif de cohérence”, mais de
la **montée en gamme avancée** : politiques opérateur plus fines, audit persisté
des fallbacks live, enrichissement visuel, et optimisation multi-objectifs.

### Verdict
- **Fonctionnel** : oui.
- **Maintenable** : oui, plutôt.
- **Solide en tests** : oui.
- **Parité live / backtest / doc** : **nettement réalignée**.
- **Niveau “expert production”** : **proche sur le périmètre corrigé**, avec un reste de professionnalisation orienté gouvernance et exploitation avancée plutôt que corrections bloquantes.

---

## 3. Méthode d’audit

### Revue statique
- lecture prioritaire des sources du module `risk_management` ;
- vérification des contrats réels via les tests ;
- lecture des intégrations IHM les plus proches ;
- lecture de la doc, en la considérant comme **non canonique** quand elle diverge du code.

### Validation exécutée
- exécution d’une batterie de tests ciblée ;
- exécution d’un lint Ruff ciblé sur le module et ses tests directs.

### Commandes de validation utilisées

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_portfolio_builder.py tests\test_risk_management_cli.py tests\test_risk_management_run_summary.py tests\test_db_io_v2.py tests\test_risk_regime_apply.py tests\test_risk_regime_sizing_constraints.py tests\test_risk_checker.py tests\test_run_risk_circuit_breaker_wired.py tests\test_risk_shadow_compare.py tests\test_position_sizer_telemetry.py tests\test_ml_disable_modes.py tests\test_phase2_risk_bridge_regime.py tests\test_capital_preset_risk_overrides.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m ruff check risk_management tests\test_portfolio_builder.py tests\test_risk_management_cli.py tests\test_risk_management_run_summary.py tests\test_db_io_v2.py tests\test_risk_regime_apply.py tests\test_risk_regime_sizing_constraints.py tests\test_risk_checker.py tests\test_run_risk_circuit_breaker_wired.py tests\test_risk_shadow_compare.py tests\test_position_sizer_telemetry.py tests\test_ml_disable_modes.py tests\test_phase2_risk_bridge_regime.py tests\test_capital_preset_risk_overrides.py --output-format concise
```

### Résultat constaté
- batterie de tests ciblée : **OK** ;
- `ruff check risk_management` : **OK** ;
- la commande Ruff élargie sur les tests directs du périmètre a été nettoyée et
  sert désormais de garde-fou additionnel pour éviter un retour des dettes de
  qualité autour de `risk_management`.

---

## 4. Cartographie fonctionnelle du module

## 4.1 Flux principal réel

`risk_management/cli.py`
→ résout le compte / l’equity effective
→ construit `RiskConfig`
→ charge candidats, prix, prédictions, win rates, matrice de rendements via `risk_management/db_io.py`
→ appelle `risk_management/portfolio_builder.py::PortfolioBuilder.build()`
→ persiste décisions et cibles via `risk_management/audit.py`
→ émet un `run_summary` persisté + live.

## 4.2 Répartition des responsabilités

- `config.py` : paramètres et validations.
- `db_io.py` : chargement PIT + écritures SQL canonisées.
- `portfolio_builder.py` : orchestration métier principale.
- `position_sizer.py` : sizing ATR strict.
- `kelly.py` : sizing Kelly optionnel.
- `constraints.py` : contraintes portefeuille.
- `risk_checker.py` : façade circuit breaker + contraintes.
- `circuit_breaker.py` : coupure drawdown / daily loss.
- `correlation_filter.py` : filtre de corrélation greedy.
- `ml_gate.py` : kill-switch ML effectif.
- `audit.py` : sérialisation / persistance des sorties.
- `regime_apply.py` : adaptation `RiskConfig` à un `MarketRegimeSnapshot`.
- `shadow_compare.py` : comparaison auditée de runs, réutilisée par le runtime et l’IHM.

### Appréciation
L’architecture est bonne : le module n’est pas monolithique, et l’assemblage principal reste lisible.
Le vrai sujet n’est **pas** la structure, mais **quelques écarts de cohérence entre briques**.

---

## 5. Points forts constatés

### 5.1 Bonne séparation des couches
Le découpage est propre :
- les modèles sont centralisés ;
- le repository gère le SQL ;
- le builder orchestre ;
- les règles élémentaires restent localisées.

C’est un bon socle pour un module de gestion du risque.

### 5.2 Sémantique PIT déjà sérieuse
`risk_management/db_io.py` implémente une logique point-in-time utile sur :
- `stock_scores_history` ;
- `stock_bars_daily` ;
- `model_predictions` ;
- `model_metrics` / `model_training_run` ;
- `account_risk_snapshots`.

Le fallback `snapshot_date <= trade_date` côté candidats est particulièrement sain.

### 5.3 Observabilité de run déjà riche
Le `run_summary` expose déjà :
- exposition brute ;
- couverture ATR / ML ;
- décompte des rejets ;
- informations circuit breaker ;
- télémétrie selector transportée jusqu’au risk ;
- état du ML gate ;
- décomposition d’equity.

Le fait que l’IHM consomme réellement ces champs est un point fort concret.

### 5.4 Couverture de tests crédible
Le module bénéficie d’une couverture qui va au-delà du simple happy path :
- unitaires métier ;
- tests CLI ;
- tests repository ;
- tests d’intégration backtest/risk bridge ;
- property tests sur le circuit breaker ;
- tests IHM/summary indirects.

### 5.5 Compatibilité schéma pragmatique
Les écritures `risk_decisions` / `portfolio_targets` s’adaptent aux colonnes disponibles. Cette stratégie réduit le risque opérationnel lors des migrations progressives.

---

## 6. Anomalies initiales et statut de résolution

Les anomalies structurantes identifiées lors de l’audit initial ont été
revérifiées et sont désormais considérées comme **corrigées** sur le périmètre
runtime / tests / IHM correspondant.

## 6.1 A1 — câblage live du régime marché

**Statut : résolu.**

Le runtime `risk_management.cli` résout désormais un `MarketRegimeSnapshot`,
applique `apply_snapshot()` et expose les overrides effectifs dans le
`run_summary` (`regime_snapshot_applied`, `regime_mode`,
`risk_controls_effective`, etc.). La parité live / backtest est réalignée sur
ce point.

## 6.2 A2 — side effects répétés du circuit breaker

**Statut : résolu.**

Le circuit breaker sépare maintenant l’évaluation pure (`status()` /
`is_active()`) de la notification best-effort idempotente
(`notify_if_active()`). Les tests couvrent le comportement notify-once.

## 6.3 A3 — alignement Kelly / ATR régime-aware

**Statut : résolu.**

`KellySizer` tient compte de `risk_multiplier`, s’appuie sur
`effective_min_notional` et remonte des `SizingMethod` détaillés alignés avec le
chemin ATR.

## 6.4 A4 — agrégation des rejets notionnels

**Statut : résolu.**

Le `run_summary` additionne désormais `rejected_notional` et
`rejected_notional_below_enforced`, tout en exposant le détail fin pour audit.

## 6.5 A5 — cohérence PIT de `load_account_equity_breakdown()`

**Statut : résolu.**

Le cutoff `portfolio_cash_ledger.created_at <= trade_date` est appliqué, la
lecture broker est réalignée en best-effort sur la logique de snapshot, et le
summary expose explicitement la source/fraîcheur d’equity utilisée.

## 6.6 A6 — granularité des raisons de rejet

**Statut : résolu.**

Les refus/réductions sont désormais propagés via `DecisionReasonCode` jusque
dans les `PortfolioEntry`, les agrégats de `run_summary` et les détails IHM.

## 6.7 A7 — doc / outillage en retard

**Statut : résolu sur le package, avec garde-fous supplémentaires.**

`doc/risk_management.md` est réalignée sur le code réel, `ruff check
risk_management` est vert, et une passe supplémentaire sur les tests directs du
périmètre complète désormais le garde-fou qualité autour du module.

---

## 7. Risques résiduels / non bloquants

## 7.1 Pas de data-quality gate explicite avant construction du portefeuille
Aujourd’hui, le module continue même avec :
- zéro candidat ;
- faible couverture ATR ;
- couverture ML nulle ;
- snapshot equity fallback ;
- matrice de corrélation vide.

C’est parfois le bon comportement, mais il manque un contrat explicite du type :
- `block`
- `warn_continue`
- `skip_feature`

selon la criticité de la donnée.

## 7.2 Audit persistant des fallbacks live encore perfectible

Le runtime trace désormais finement `fallback_level`, `fallback_reason`,
`fallback_journal` et `fallback_policy_source` pour les calibrations empiriques.
Le prochain cran naturel serait de persister ces décisions dans une table dédiée
ou de les exposer plus largement dans les vues opérateur longitudinales.

## 7.3 Quelques nettoyages internes sont encore possibles
Exemples :
- reconstruction intermédiaire redondante de `EnrichedCandidate` dans `portfolio_builder.py` ;
- lookup `next(...)` en O(n) pour retrouver un candidat corrélé rejeté ;
- hétérogénéité de typing moderne.

Ce sont des sujets de qualité, pas des bugs critiques.

## 7.4 Calibration conviction / Kelly : boucle active, montée en gamme encore ouverte

Ce constat historique n’est plus vrai au premier ordre : une calibration
empirique active existe désormais côté runtime. Le risque résiduel se situe
désormais sur la montée en gamme de cette boucle (objectifs business,
visualisations plus riches, gouvernance avancée, multi-objectifs), pas sur son
absence.

---

## 8. Plan d’amélioration priorisé

## P0 — à traiter en premier
- [x] Câbler `service.market` + `risk_management/regime_apply.py` dans `risk_management/cli.py`.
- [x] Rendre `CircuitBreaker` idempotent côté alerting (une notification max par run/instance).
- [x] Harmoniser `KellySizer` avec `RiskConfig.effective_*` et `risk_multiplier`.
- [x] Corriger l’agrégation `rejected_for_notional` pour inclure les rejets “below_enforced”.
- [x] Corriger la logique PIT de `load_account_equity_breakdown()`.

## P1 — amélioration court terme recommandée
- [x] Propager des raisons de rejet/réduction structurées jusqu’au `run_summary`.
- [x] Ajouter un préflight data-quality pour : snapshot equity, couverture ATR, fraîcheur candidat PIT, matrice de corrélation.
- [x] Exposer dans le `run_summary` : `equity_source`, `equity_fallback_used`, `snapshot_freshness_days`, `regime_snapshot_applied`.
- [x] Ajouter les tests manquants :
  - Kelly + régime ;
  - anti-spam circuit breaker ;
  - dividendes PIT cutoff ;
  - comptage notional “below_enforced”.

## P2 — professionnalisation du package
- [x] Passer `ruff check risk_management` à **OK**.
- [x] Réaligner `doc/risk_management.md` sur le code réel.
- [x] Réduire les petites redondances du builder.
- [x] Standardiser les noms / enums de `sizing_method` et `decision_reason`.

## P3 — moyen terme / montée en gamme
- [x] Intégrer un mode shadow compare pilotable depuis le runtime/IHM.
- [x] Brancher une calibration empirique des poids conviction/Kelly.
  - état actuel : première boucle active branchée via `backtesting.weights_calibration.EmpiricalRiskCalibrator`, `scripts/run_quarterly_weights_calibration.py` et lecture live `weights_calibration_runs` dans `risk_management/cli.py`.
  - montée en gamme livrée : segmentation par `market_regime_mode`, fallback live `régime courant → all`, payload batch trimestriel consolidé par segment, page IHM dédiée `weights_calibration_runs`.
  - reste à faire : enrichir la gouvernance/optimisation de cette boucle (objectifs business, monitoring drift dédié, segmentation horizon multi-fenêtres / multi-objectifs).
- [x] Ajouter des artefacts de post-mortem plus riches par run :
  - top rejets par contrainte ;
  - détail secteur ;
  - résumé du régime appliqué ;
  - couverture effective des sources externes.

---

## 9. Proposition de plan d’exécution concret

### Étape 1 — corriger la cohérence runtime
1. brancher le snapshot de régime live ;
2. unifier le chemin Kelly / ATR ;
3. fiabiliser le circuit breaker.

### Étape 2 — fiabiliser l’auditabilité
1. corriger l’equity breakdown PIT ;
2. enrichir les raisons de rejet ;
3. exposer les sources/fallbacks dans le summary.

### Étape 3 — consolider l’exploitation
1. mettre à jour la doc ;
2. nettoyer Ruff ;
3. compléter les tests de non-régression ciblés.

---

## 10. État final observé à date

### Ce qui est déjà professionnel
- architecture lisible ;
- repository PIT utile ;
- couverture de tests solide ;
- run summary exploitable ;
- intégration IHM correcte ;
- compatibilité de persistance pragmatique.

### Ce qui empêche encore un verdict “expert production” plein
- politique de data-quality encore implicite avant construction du portefeuille ;
- audit longitudinal des fallbacks live encore perfectible ;
- montée en gamme métier de la boucle de calibration empirique encore ouverte.

### Mise à jour après livraison P2 / amorçage P3
- le retard **doc + lint** sur le périmètre `risk_management` est désormais résorbé ;
- le builder a été allégé (suppression de redondances et lookup corrélation optimisé) ;
- le shadow compare n'est plus un îlot isolé : il est pilotable via CLI/IHM et peut persister dans `shadow_drift_runs` ;
- la calibration conviction/Kelly n'est plus seulement tracée : une première boucle empirique est désormais disponible et applicable en live via `weights_calibration_runs` ;
- les items P0/P1 identifiés dans cet audit ont été revérifiés comme livrés par le runtime et les tests ciblés.

### Verdict
Le module `risk_management` est **bon et désormais cohérent** sur le périmètre
des anomalies initialement auditées.

La bonne nouvelle est que les écarts identifiés sont :
- **concrets** ;
- **limitables en portée** ;
- **corrigeables sans réécriture**.

Le reste du travail ne relève plus d’une remise à niveau P0/P1, mais d’une
montée en gamme de gouvernance, d’exploitation et d’ergonomie opérateur.

