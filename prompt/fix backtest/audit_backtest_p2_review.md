# Revue d’implémentation P2 — backtest et live pipeline

Date : 2026-06-04

## Objet

Vérification de l’implémentation réelle des points **Priorité 2 — très importante** de `prompt/audit_backtest.md` :

5. **Ajouter un cap sectoriel réel**
6. **Réduire l’exposition brute en mode `capital_preservation`**
7. **Activer un gap filter à l’entrée**

L’objectif ici est de distinguer :

- ce qui est **seulement configuré**,
- ce qui est **codé mais non branché**,
- ce qui est **réellement appliqué** dans les flux d’exécution,

à la fois côté **backtest** et côté **live pipeline**.

---

## Résumé exécutif

| Priorité P2 | Backtest | Live pipeline | Verdict |
|---|---|---|---|
| 5. Cap sectoriel réel | **Oui** | **Oui** | implémenté |
| 6. Réduction exposition brute en `capital_preservation` | **Oui** | **Oui** | implémenté |
| 7. Gap filter à l’entrée | **Oui** | **Oui** | implémenté |

### Conclusion courte

- **P2.5** est **bien implémenté** côté backtest et côté live pipeline.
- **P2.6** est désormais **implémenté** : le dépôt applique maintenant une règle **générique et explicite** `capital_preservation => réduction de max_gross_exposure`, côté backtest comme côté live pipeline.
- **P2.7** est **bien implémenté** côté backtest et côté live pipeline.

---

## 5) Ajouter un cap sectoriel réel

## Côté backtest — **Oui, réellement appliqué**

### Câblage de configuration

Le cap sectoriel est construit dans la config backtest :

- `backtesting/cli/_impl.py:2066-2080`
  - construction de `RiskOverlayConfig(...)`
  - construction de `SectoralCapConfig(...)`
  - activation si `max_sector_exposure_pct > 0`

Le preset capital peut aussi alimenter automatiquement ce paramètre :

- `common/capital_presets.py:298-325`
  - mapping `max_sector_exposure_pct <- backtesting_max_sector_exposure_pct`
- `config/capital_presets.yaml:42-47`
  - ex. micro-compte : `backtesting_max_sector_exposure_pct: 0.25`

L’IHM backtest expose bien ce champ :

- `ihm/pages/backtesting/__init__.py:1038-1047`
  - champ `Max exposure secteur`
- `ihm/services/backtesting_runner.py:253-254`
  - propagation en CLI via `--max-sector-exposure-pct`

### Application réelle dans le simulateur

Le simulateur backtest l’applique effectivement :

- `backtesting/simulator.py:726-735`
  - calcul de l’exposition sectorielle courante via `snapshot_sector_exposure(...)`
- `backtesting/simulator.py:807-824`
  - rejet d’une entrée si le cap est dépassé
- `backtesting/simulator.py:810`
  - incrément de `diagnostics.blocked_by_sectoral_cap`
- `backtesting/simulator.py:966-967`
  - mise à jour de l’exposition sectorielle après ouverture de position

Primitive utilisée :

- `backtesting/risk_overlay.py:73-88`
  - `SectoralCapConfig.is_entry_allowed(...)`
- `backtesting/risk_overlay.py:132-177`
  - `snapshot_sector_exposure(...)`

### Verdict backtest

Le cap sectoriel n’est **pas seulement déclaré** : il est **branché dans le simulateur** et **bloque réellement des entrées**.

---

## Côté live pipeline — **Oui, réellement appliqué**

Le cap sectoriel existe même à **deux niveaux**.

### Niveau 1 — contrainte principale dans le pipeline risk

Le pipeline envoie bien le paramètre de poids sectoriel maximal :

- `ihm/services/pipeline_runner.py:2142-2158`
  - envoi de `--max-sector-weight`
- `ihm/pages/_execution_center/__init__.py:1505-1517`
  - champ IHM `Risk — poids max par secteur`

Le module risk le charge :

- `risk_management/cli.py:840-846`
  - `RiskConfig(max_sector_weight=args.max_sector_weight, ...)`

Puis il l’applique réellement :

- `risk_management/constraints.py:90-101`
  - contrôle `max_sector_weight`
- `risk_management/portfolio_builder.py:254-282`
  - application via `RiskCheckerImpl` / `ConstraintChecker`

### Niveau 2 — garde-fou supplémentaire dérivé du régime live

Le snapshot marché peut encore durcir le cap sectoriel :

- `service/market/regime_manager.py:338-345`
  - tightening de `max_sector_weight`
- `risk_management/regime_apply.py:53-60`
  - propagation vers `RiskConfig`

En exécution live, un garde-fou supplémentaire est appliqué :

- `run_execution.py:950-979`
  - propagation vers `ExecutionConfig.regime_max_sector_weight`
- `execution_engine/order_intents.py:156-180`
  - filtrage `regime_max_sector_weight`
- `execution_engine/executor.py:215-232`
  - audit des cibles bloquées par garde-fou de régime

### Verdict live pipeline

Le cap sectoriel est **réel** côté live pipeline :

1. dans la **construction du portefeuille cible**,
2. puis comme **filet de sécurité d’exécution**.

---

## Verdict P2.5

**Implémenté côté backtest et côté live pipeline.**

---

## 6) Réduire l’exposition brute en mode `capital_preservation`

## Verdict global — **Implémenté**

Le dépôt applique désormais une règle métier explicite de la forme :

> si `mode == capital_preservation` alors resserrer `max_gross_exposure`

Cette règle est maintenant :

- **configurable** dans la config marché,
- **produite** par le snapshot de régime,
- **appliquée** au pipeline risk,
- **propagée** jusqu’au garde-fou d’exécution live,
- et **respectée** dans le simulateur backtest quand une limite de gross exposure est fournie via `RiskConfig` / `ExecutionConfig`.

---

## Ce qui existe réellement

### Config explicite du mode `capital_preservation`

Le YAML porte maintenant un plafond dédié au mode `capital_preservation` :

- `config.yaml`
  - `capital_preservation_max_gross_exposure: 0.50`
  - en complément des plafonds `soft` / `hard` déjà présents pour les shocks de taux

Le parser le charge explicitement :

- `service/market/config.py`
  - `MarketRegimesConfig.capital_preservation_max_gross_exposure`

### Snapshot régime

Le gestionnaire de régime sait désormais produire `max_gross_exposure` selon **trois** mécanismes :

- `service/market/regime_manager.py`
  - tightening `soft_max_gross_exposure` sur `yield_spike`
  - tightening `hard_max_gross_exposure` sur choc de taux dur
  - tightening **générique** `capital_preservation_max_gross_exposure` quand `mode == capital_preservation`

Le snapshot sérialise alors bien :

- `MarketRegimeSnapshot(... max_gross_exposure=...)`
- une trace de décision `capital_preservation_gross_exposure`

### Application au `RiskConfig`

- `risk_management/regime_apply.py:59-60`
  - `updates["max_gross_exposure"] = float(snapshot.max_gross_exposure)`

### Enforcement réel côté construction portefeuille

- `risk_management/constraints.py:72-80`
  - contrôle strict `max_gross_exposure`
- `risk_management/portfolio_builder.py:254-282`
  - les tailles sont réduites/rejetées si la contrainte s’active

---

## Côté live pipeline — **Oui, réellement appliqué**

### Oui, dans l’étape risk management

Le pipeline risk applique bien le snapshot de régime :

- `risk_management/cli.py:874-884`
  - `config = apply_snapshot(config, regime_snapshot)`

Donc si le snapshot contient un `max_gross_exposure` réduit — y compris via la règle générique `capital_preservation` — cette valeur est bien utilisée ensuite par les contraintes du portefeuille.

### Oui aussi comme garde-fou d’exécution live autonome

L’exécution live transporte désormais aussi ce garde-fou dans `ExecutionConfig` :

- `execution_engine/config.py`
  - présence de `regime_max_gross_exposure`

La propagation live depuis le snapshot transporte maintenant l’exposition brute :

- `run_execution.py`
  - propagation de `snapshot.max_gross_exposure` vers `ExecutionConfig.regime_max_gross_exposure`
- `execution_engine/order_intents.py`
  - filtrage cumulatif `regime_max_gross_exposure`
- `execution_engine/executor.py`
  - audit / métriques `SkippedByRegimeGuard[regime_max_gross_exposure]`

### Lecture correcte côté live

- **Oui** : réduction d’exposition brute dans le **pipeline risk**
- **Oui** : garde-fou spécifique côté **exécution live**
- **Oui** : règle générique “`capital_preservation` => baisse de gross exposure”

---

## Côté backtest — **Oui, réellement appliqué**

Ici il faut distinguer deux chemins.

### 1) Backtest pipeline avec `risk_bridge` — **Oui, dans la partie risk**

Le bridge applique le snapshot de régime avant la construction portefeuille :

- `backtesting/risk_bridge.py:307-322`
  - build snapshot
  - `cfg_for_day = apply_snapshot(risk_config, snap)`
- `backtesting/risk_bridge.py:331-332`
  - `PortfolioBuilder(cfg_for_day)`

Ensuite la contrainte `max_gross_exposure` est effectivement enforce via :

- `risk_management/constraints.py:72-80`
- `risk_management/portfolio_builder.py:254-282`

Le snapshot backtest contient maintenant aussi le plafonnement générique `capital_preservation_max_gross_exposure`, donc le chemin `risk_bridge` applique bien la règle métier complète.

### 2) Simulateur backtest pur — **Oui, limitation effective quand un cap de gross exposure est fourni**

Le simulateur pur applique désormais également un cap de gross exposure quand il reçoit une limite via `RiskConfig.max_gross_exposure` ou `ExecutionConfig.regime_max_gross_exposure` :

- `backtesting/simulator.py`
  - calcul de l’exposition brute courante
  - réduction / rejet des entrées si le plafond de gross exposure est atteint
  - audit `diagnostics.blocked_by_gross_exposure`

Cela homogénéise la couverture métier côté backtest :

- **pipeline risk bridge** : cap appliqué via snapshot régime,
- **simulateur pur** : cap respecté dès qu’une config de gross exposure est injectée.

---

## Le point qui a été comblé

L’écart initial a été fermé par trois ajouts cohérents :

1. **Règle explicite de snapshot**
   - `capital_preservation => max_gross_exposure resserrée`
2. **Propagation live complète**
   - `ExecutionConfig.regime_max_gross_exposure`
   - filtre live dans `execution_engine/order_intents.py`
3. **Couverture backtest homogène**
   - chemin `risk_bridge` via `apply_snapshot(...)`
   - simulateur pur via contrôle direct de gross exposure

---

## Verdict P2.6

**Implémenté.**

### Ce qui est vrai maintenant

- Le projet sait réduire `max_gross_exposure`.
- Cette réduction est **attachée explicitement** au mode `capital_preservation`.
- Elle est appliquée dans le **pipeline risk**.
- Elle est propagée jusqu’au **garde-fou d’exécution live**.
- Elle est couverte côté **backtest pipeline** et côté **simulateur backtest**.

---

## 7) Activer un gap filter à l’entrée

## Côté backtest — **Oui, réellement appliqué**

### Câblage

- `backtesting/cli/_impl.py:2056-2065`
  - `MicrostructureConfig(max_entry_gap_pct=...)`
- `common/capital_presets.py:298-325`
  - mapping `max_entry_gap_pct <- backtesting_max_entry_gap_pct`
- `config/capital_presets.yaml:44`
  - ex. `backtesting_max_entry_gap_pct: 0.03`
- `ihm/services/backtesting_runner.py:240-241`
  - propagation du paramètre CLI

### Application réelle

- `backtesting/microstructure.py:119-135`
  - `should_skip_entry_for_gap(...)`
- `backtesting/simulator.py:759-788`
  - calcul du gap
  - rejet de l’entrée si seuil dépassé
  - audit `blocked_entry_gap`

### Verdict backtest

Le gap filter d’entrée est **réellement actif** lorsque `max_entry_gap_pct > 0`.

---

## Côté live pipeline — **Oui, réellement appliqué**

### Câblage CLI / IHM

- `run_execution.py:507-565`
  - le runtime preset accepte `max_entry_gap_pct`
- `run_execution.py:1156-1159`
  - argument CLI `--max-entry-gap-pct`
- `ihm/services/pipeline_runner.py:2220-2225`
  - propagation du paramètre exécution
- `config/capital_presets.yaml:47`
  - `execution_max_entry_gap_pct: 0.03`

### Application réelle

L’exécuteur enrichit d’abord les cibles avec `previous_close` :

- `execution_engine/executor.py:193-213`

Puis il applique le filtre avant soumission :

- `execution_engine/executor.py:419-444`
  - récupération des derniers prix de marché
  - appel à `split_entry_intents_by_gap_filter(...)`
  - comptage `skipped_by_gap_filter`

Logique pure du filtre :

- `execution_engine/order_intents.py:206-247`
  - comparaison `previous_close` vs prix de décision/dernier prix marché
  - rejet si dépassement du seuil
- `backtesting/microstructure.py:119-135`
  - primitive partagée `should_skip_entry_for_gap(...)`

### Verdict live pipeline

Le gap filter est **bien branché de bout en bout** côté live pipeline.

---

## Verdict P2.7

**Implémenté côté backtest et côté live pipeline.**

---

## Conclusion finale

### Statut final des trois points P2

1. **Ajouter un cap sectoriel réel**
   - **Backtest : OK**
   - **Live pipeline : OK**

2. **Réduire l’exposition brute en mode `capital_preservation`**
   - **Backtest : OK**
   - **Live pipeline : OK**

3. **Activer un gap filter à l’entrée**
   - **Backtest : OK**
   - **Live pipeline : OK**

### Formulation de synthèse recommandée

> Les priorités P2 sont désormais couvertes sur les trois points visés : le cap sectoriel réel, la réduction d’exposition brute en mode `capital_preservation` et le gap filter d’entrée sont implémentés en backtest comme en live pipeline. En particulier, `capital_preservation` déclenche maintenant explicitement un resserrement de `max_gross_exposure`, propagé jusqu’au garde-fou d’exécution live et respecté dans les chemins backtest concernés.

---

## Validation effectuée

Tests ciblés lancés avec succès sur les briques concernées :

```powershell
Set-Location "F:\projets"
pytest -q --no-cov tests/test_market_regime.py tests/test_phase2_risk_bridge_regime.py tests/test_execution_engine_config.py tests/test_order_intents.py tests/test_execution_engine_executor.py tests/test_run_execution.py
pytest -q --no-cov tests/test_backtesting.py -k "enforces_max_gross_exposure_from_risk_config or config_from_risk_and_exec or backtest_engine_execution_replay_mode_uses_signal_share_override"
```

Résultat : **tests ciblés passants**.

