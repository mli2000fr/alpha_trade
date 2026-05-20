# Audit et plan de refactor — module `risk_management`

_Date : 2026-05-20_

> **Mise à jour d'avancement — 2026-05-20 (après implémentation P2/P3 ciblée)**
>
> - **P2 livré sur le périmètre `risk_management`** : `ruff check risk_management` OK, doc réalignée, redondances builder réduites, standardisation `SizingMethod` / `DecisionReasonCode` effectivement utilisée.
> - **P0 / P1 revérifiés** : les items ciblés sont désormais effectivement câblés et couverts par tests ciblés (régime live, circuit breaker notify-once, Kelly effectif, agrégation notional, equity breakdown PIT, motifs structurés, preflight data-quality, métadonnées summary).
> - **P3 désormais livré sur un premier niveau opérationnel** : shadow compare pilotable depuis le runtime/IHM, artefacts de post-mortem enrichis exposés dans le `run_summary`, et première boucle empirique de calibration conviction/Kelly branchée via `weights_calibration_runs`.
> - **Reste ouvert en P3** : montée en gamme de la calibration empirique au-delà de la première boucle désormais segmentée par régime marché (objectifs business plus riches, gouvernance/monitoring, optimisation plus fine, segmentation horizon multi-fenêtres).

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
Le module est **fonctionnel et plutôt mature**, mais il n’est **pas encore au niveau “professionnel / expert” homogène sur tout son périmètre**.

Les principaux écarts observés ne relèvent pas d’un manque de structure, mais de **quelques incohérences importantes entre le design annoncé et le runtime réel** :
1. le **régime marché n’est pas appliqué côté live** alors qu’un helper dédié existe et que la doc l’annonce ;
2. le **circuit breaker est side-effecting** et peut déclencher plusieurs alertes identiques sur un même run ;
3. le **chemin Kelly n’est pas aligné** avec les règles régime / télémétrie du chemin ATR ;
4. la **décomposition d’equity** n’est pas complètement cohérente point-in-time ;
5. l’**observabilité des raisons de rejet** reste trop agrégée à certains endroits ;
6. la **documentation du module n’est plus alignée** avec le code réel ;
7. le package n’est **pas Ruff-clean** sur son périmètre propre.

### Verdict
- **Fonctionnel** : oui.
- **Maintenable** : oui, plutôt.
- **Solide en tests** : oui.
- **Parité live / backtest / doc** : **encore incomplète**.
- **Niveau “expert production”** : **atteignable rapidement**, mais nécessite une passe ciblée sur les anomalies structurantes ci-dessous.

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
- lint Ruff ciblé : **KO** avec plusieurs remarques de qualité/statique, dont certaines dans `risk_management/` lui-même.

Exemples côté package :
- `risk_management/circuit_breaker.py` : import inutile ;
- `risk_management/cli.py` : `f-string` sans placeholder ;
- `risk_management/portfolio_builder.py` : imports/typing modernisables ;
- `risk_management/shadow_compare.py` : nom ambigu `l` ;
- `risk_management/ml_gate.py`, `risk_management/config.py`, `risk_management/regime_apply.py` : modernisation typing.

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
- `shadow_compare.py` : comparaison offline de runs.

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

## 6. Anomalies détectées

## 6.1 Anomalie A1 — `regime_apply.py` existe mais n’est pas câblé dans le live

### Symptôme
`risk_management/regime_apply.py` annonce explicitement être utilisé par :
- `risk_management/cli.py` (live),
- `backtesting/risk_bridge.py` (backtest).

En pratique, la recherche d’usage montre un câblage réel dans les tests et dans `backtesting/risk_bridge.py`, **mais pas dans `risk_management/cli.py`**.

### Impact
Le live `risk_management` ne bénéficie donc pas des ajustements de régime pourtant modélisés :
- `risk_multiplier` ;
- `effective_max_positions_override` ;
- `enforce_min_notional` ;
- `max_tickers_per_sector`.

Conséquence :
- **divergence live vs backtest** ;
- divergence live vs doc ;
- perte de valeur de la couche `service.market` pour le sizing live.

### Gravité
**Haute**.

### Recommandation
Brancher un vrai préflight régime dans `cli.py` :
- résolution du `MarketRegimeSnapshot` du jour ;
- application via `apply_snapshot()` ;
- exposition du snapshot / des overrides effectifs dans le `run_summary`.

---

## 6.2 Anomalie A2 — `CircuitBreaker.is_active()` a des effets de bord répétés

### Symptôme
`CircuitBreaker.is_active()` n’est pas purement évaluative : elle peut envoyer une notification email via `_try_send_alert()`.

Or cette méthode est appelée à plusieurs endroits sur un même run :
- par `RiskCheckerImpl.check_position_size()` pour chaque candidat ;
- indirectement lors de la construction finale du `run_summary`.

### Impact
Si le circuit breaker est actif, un même run peut produire :
- plusieurs alertes identiques ;
- du bruit opérateur ;
- des notifications redondantes ;
- une sémantique difficile à raisonner en production.

### Gravité
**Haute**.

### Recommandation
Séparer :
- une méthode **pure** d’évaluation (`evaluate()` / `status()`),
- une logique d’alerte **notify-once** ou **notify-on-transition**.

Ajouter un test garantissant qu’un run avec circuit breaker actif n’émet **qu’une seule notification**.

---

## 6.3 Anomalie A3 — `KellySizer` n’est pas cohérent avec le chemin ATR régime-aware

### Symptôme
`risk_management/kelly.py` ne réutilise pas complètement les règles effectives introduites côté config/sizer ATR :
- le budget ATR Kelly ne tient pas compte de `risk_multiplier` ;
- le contrôle de notional utilise `cfg.min_position_notional` au lieu de `cfg.effective_min_notional` ;
- les rejets remontent avec `method="rejected"`, alors que le chemin ATR distingue les causes (`rejected_atr_missing`, `rejected_notional`, etc.).

### Impact
Le comportement diffère selon que Kelly est activé ou non :
- le régime marché n’est pas appliqué de manière homogène ;
- la télémétrie de rejet devient moins exploitable ;
- les comptes petits / défensifs peuvent être traités différemment selon le sizer choisi.

### Gravité
**Haute**.

### Recommandation
Refactoriser le sizing pour partager un noyau commun :
- un calcul Kelly pour la proposition initiale ;
- puis un post-traitement commun de type `apply_effective_risk_controls(...)` ;
- et une télémétrie de rejet harmonisée.

Ajouter des tests spécifiques Kelly + `risk_multiplier` + `enforce_min_notional`.

---

## 6.4 Anomalie A4 — le `run_summary` sous-compte certains rejets notionnels

### Symptôme
`PositionSizer.compute()` peut retourner :
- `rejected_notional`
- `rejected_notional_below_enforced`

Mais `risk_management/cli.py` n’agrège dans `rejected_for_notional` que :
- `sizing_method_counts.get("rejected_notional", 0)`

### Impact
Dès qu’un régime ou une surcharge de config active `enforce_min_notional`, le compteur principal de rejet notionnel devient **partiellement faux**.

L’opérateur voit alors un run_summary incomplet alors même que le détail fin existe déjà dans `sizing_method_counts`.

### Gravité
**Moyenne à haute**.

### Recommandation
Agrégation à corriger pour inclure :
- `rejected_notional`
- `rejected_notional_below_enforced`

et, idéalement, exposer explicitement les deux dans le payload final.

---

## 6.5 Anomalie A5 — `load_account_equity_breakdown()` n’est pas totalement cohérent point-in-time

### Symptôme
Plusieurs points fragilisent `RiskRepository.load_account_equity_breakdown()` :

1. le cumul `portfolio_cash_ledger` ne filtre pas `created_at <= trade_date` ;
2. la sélection du snapshot broker n’est pas alignée avec la logique plus stricte de `load_account_risk_snapshot()` ;
3. la requête compte suppose `ORDER BY created_at DESC, id DESC` sans garde explicite sur la présence de `id` ;
4. la décomposition best-effort peut donc diverger silencieusement de l’equity réellement utilisée pour le run.

### Impact
- pollution PIT possible par des dividendes futurs ;
- incohérence entre `effective_equity` et `account_equity_breakdown` ;
- dégradation silencieuse à `source="missing"` selon le schéma disponible.

### Gravité
**Haute** pour la qualité d’auditabilité, **moyenne** pour le moteur de sizing lui-même.

### Recommandation
Introduire un helper unique “equity snapshot as-of” partagé :
- même logique de snapshot principal ;
- garde schema-aware sur `id`, `snapshot_kind`, `created_at` ;
- filtre PIT sur `portfolio_cash_ledger.created_at <= trade_date`.

Ajouter un test d’intégration dédié sur le cutoff des dividendes.

---

## 6.6 Anomalie A6 — la granularité des raisons de rejet est perdue en sortie builder

### Symptôme
`ConstraintChecker.check()` calcule une raison fine (`max_positions atteint`, `max_sector_weight atteint`, etc.).
Mais `PortfolioBuilder.build()` transforme ensuite une partie des refus en raisons génériques :
- `contrainte de risque`
- `réduit par contraintes`

### Impact
On perd une partie de l’explicabilité opérateur alors que l’information existe déjà au bon niveau.

En production, cela complique les diagnostics de type :
- saturation de slots ;
- secteur déjà plein ;
- plafond gross exposure ;
- min notional ;
- blocage circuit breaker.

### Gravité
**Moyenne**.

### Recommandation
Propager des raisons structurées jusqu’à `PortfolioEntry`, puis au `run_summary`, par exemple :
- `constraint_max_positions`
- `constraint_max_sector_weight`
- `constraint_max_gross_exposure`
- `constraint_max_tickers_per_sector`
- `circuit_breaker_active`

---

## 6.7 Anomalie A7 — documentation et outillage ne reflètent plus l’état réel du module

### Symptôme
`doc/risk_management.md` diverge du code sur plusieurs points importants :
- la doc parle encore de `stock_scores`, alors que le live lit `stock_scores_history` avec fallback PIT ;
- la doc décrit un ajout de dividendes “depuis corporate_actions”, alors que le code lit `portfolio_cash_ledger` ;
- la doc ne couvre pas correctement le `ml_gate`, le fallback d’equity broker, ni le transport de métadonnées selector ;
- le package n’est pas Ruff-clean.

### Impact
- onboarding trompeur ;
- erreurs d’exploitation ;
- dette de crédibilité documentaire.

### Gravité
**Moyenne**.

### Recommandation
Mettre à jour la doc **après** correction des anomalies P0/P1, puis faire une passe Ruff ciblée sur `risk_management/`.

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

## 7.2 `shadow_compare.py` reste un îlot utile mais isolé
Le composant est testable et propre, mais il n’est pas réellement intégré au runtime `risk_management`.
C’est un bon candidat pour une future montée en gamme, pas un défaut bloquant immédiat.

## 7.3 Quelques nettoyages internes sont encore possibles
Exemples :
- reconstruction intermédiaire redondante de `EnrichedCandidate` dans `portfolio_builder.py` ;
- lookup `next(...)` en O(n) pour retrouver un candidat corrélé rejeté ;
- hétérogénéité de typing moderne.

Ce sont des sujets de qualité, pas des bugs critiques.

## 7.4 Calibration conviction / Kelly encore très statique
Le module expose déjà un placeholder de calibration, mais la logique reste encore essentiellement paramétrique et non pilotée par calibration empirique active.

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
- incohérence live/backtest sur le régime ;
- side effects répétés du circuit breaker ;
- Kelly pas totalement aligné avec les règles effectives ;
- décomposition d’equity pas complètement PIT-safe ;
- doc et lint en retard sur le code.

### Mise à jour après livraison P2 / amorçage P3
- le retard **doc + lint** sur le périmètre `risk_management` est désormais résorbé ;
- le builder a été allégé (suppression de redondances et lookup corrélation optimisé) ;
- le shadow compare n'est plus un îlot isolé : il est pilotable via CLI/IHM et peut persister dans `shadow_drift_runs` ;
- la calibration conviction/Kelly n'est plus seulement tracée : une première boucle empirique est désormais disponible et applicable en live via `weights_calibration_runs` ;
- les items P0/P1 identifiés dans cet audit ont été revérifiés comme livrés par le runtime et les tests ciblés.

### Verdict
Le module `risk_management` est **bon**, mais **pas encore homogène** sur ses exigences de production avancée.

La bonne nouvelle est que les écarts identifiés sont :
- **concrets** ;
- **limitables en portée** ;
- **corrigeables sans réécriture**.

Une passe courte mais disciplinée sur les points P0/P1 suffirait à faire passer le module d’un niveau “robuste et utile” à un niveau **nettement plus professionnel, cohérent et expert**.

