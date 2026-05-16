# Plan d’implémentation consolidé — tous les `todo/todo_*.md`

## 1. Objectif du document

Ce document consolide **tous les points demandés** dans :

- `todo/todo_quantitatif.md`
- `todo/todo_Pattern.md`
- `todo/todo_Market-Makers.md`
- `todo/todo_pattern_smart_risk_ts.md`

Il remplace les livrables séparés demandés dans certains prompts (par ex. `todo_pattern.md`) par **un plan unique, exhaustif et traçable**.

## 2. Contraintes non négociables à respecter

- **Parité stricte Live / Backtest** : toute logique métier nouvelle doit être réutilisable côté `run_execution.py` et `backtesting/`.
- **Compatibilité EODHD + Alpaca** :
  - EODHD reste la source primaire OHLCV historique.
  - Alpaca reste le broker et la source d’état compte/ordres/positions.
  - Les nouvelles données macro ne doivent pas casser le mode fallback.
- **Pas de latence inutile en temps réel** :
  - aucune requête réseau répétée dans les boucles de soumission d’ordres ;
  - calcul du régime marché **une fois par cycle** avec cache court ;
  - priorité aux données déjà en base, sinon fallback provider.
- **Évolutions configurables** dans `config.yaml`, pas de seuils hardcodés.
- **Rétrocompatibilité** : les nouveaux filtres doivent être activables/désactivables proprement.

---

## 3. Synthèse fonctionnelle des demandes à couvrir

### 3.1 Couche "Market-Aware" / régime marché
Créer une couche centralisée qui décide du contexte de marché avant screening, sizing, exécution et backtest.

Cette couche doit couvrir :

- **Tax Day** : baisse automatique de l’exposition / `risk_mult`.
- **September Dip / Sept. Slump** : réduction du risque en septembre-octobre.
- **Santa Claus Rally** et **January Effect** : augmentation contrôlée de l’agressivité.
- **OpEx (3e vendredi)** : soit durcir le filtre sentiment, soit bloquer les nouvelles entrées, selon la configuration.
- **Month-End / Smart Money pattern** : durcir le seuil de validation des signaux.
- **VIX élevé / courbe inversée** : passage en mode défensif / capital preservation.
- **Hausse rapide du 10Y US Treasury** : blacklist Tech / Growth / high beta.
- **Sentiment global dégradé** : passage en `close_only` ou `cash_only`.

### 3.2 Gestion du capital et du risque
Adapter le moteur à un petit capital et aux drawdowns 2025 :

- recalcul dynamique de `max_positions` / slots disponibles ;
- garantie d’un **notional minimal** > 150–155 USD ;
- limitation sectorielle plus stricte ;
- réduction du nombre de positions en régime défensif ;
- intégration du `risk_multiplier` dans le sizing final.

### 3.3 Earnings / corporate actions / buyback blackout
Ajouter des protections liées aux événements d’entreprise :

- **Earnings Shield** : blocage d’ouverture de position dans une fenêtre **J-2 / J+2** ;
- **score négatif forcé** ou exclusion stricte selon le mode ;
- **buyback blackout** : réduction du score ML de 30% dans la fenêtre pré-résultats ;
- réutilisation des données alimentées par `sync_earnings_calendar`.

### 3.4 Trailing stop adaptatif ATR + sync externe
Remplacer le stop fixe des achats manuels / orphelins par une logique institutionnelle :

- stop initial basé sur **ATR(14) × multiplicateur** ;
- fallback en pourcentage fixe si ATR indisponible ;
- adoption/synchronisation des achats faits hors application ;
- passage à break-even quand le profit latent dépasse `2 × ATR` ;
- contrôle de fin de journée pour réviser les protections.

---

## 4. Matrice de couverture exhaustive des demandes

> Chaque point ci-dessous provient d’au moins un `todo_*.md`. Rien n’est volontairement omis.

| ID | Demande à couvrir | Source(s) |
|---|---|---|
| C01 | Nouveau module central de régime marché (`service/market/regime_manager.py`) | `todo_Pattern.md`, `todo_quantitatif.md` |
| C02 | Phase 0 / Sentinel avant screener | `todo_quantitatif.md` |
| C03 | Tax Day : réduction automatique du risque / exposition | les 3 fichiers pattern + `pattern/pattern_1.md` |
| C04 | September Dip / Sept. Slump | `todo_Pattern.md`, `todo_quantitatif.md` |
| C05 | Santa Claus Rally | `todo_Pattern.md`, `todo_Market-Makers.md` |
| C06 | January Effect | `todo_Pattern.md`, `todo_Market-Makers.md` |
| C07 | OpEx : durcissement du filtre ou blocage des entrées | `todo_Pattern.md`, `todo_quantitatif.md` |
| C08 | Month-End / Smart Money filter | `todo_Pattern.md` |
| C09 | VIX > 25 ou courbe VIX inversée => capital preservation | `todo_quantitatif.md` |
| C10 | Yield Monitor 10Y > +5% en 5 jours | `todo_Pattern.md`, `todo_quantitatif.md`, `todo_Market-Makers.md`, `pattern/pattern_1.md` |
| C11 | Blacklist Tech / Growth / high beta quand les taux montent | `todo_Pattern.md`, `todo_quantitatif.md`, `todo_Market-Makers.md` |
| C12 | Earnings Shield J-2 / J+2 | `todo_Pattern.md`, `todo_Market-Makers.md` |
| C13 | Score négatif forcé sur titres proches earnings | `todo_Market-Makers.md` |
| C14 | Buyback blackout : -30% sur score ML avant earnings | `todo_quantitatif.md` |
| C15 | Recalcul dynamique de `max_positions` / `allowed_slots = floor(equity / 155)` | `todo_quantitatif.md`, `todo_Pattern.md`, `todo_Market-Makers.md`, `pattern/pattern_1.md` |
| C16 | Éviter `Notional insuffisant < 150$` | `todo_quantitatif.md`, `todo_Pattern.md`, `todo_Market-Makers.md`, `pattern/pattern_1.md` |
| C17 | Pré-flight context summary dans `run_execution.py` | `todo_quantitatif.md`, `todo_Pattern.md` |
| C18 | Sentiment Circuit Breaker / Close Only / Cash Only | `todo_quantitatif.md`, `todo_Pattern.md`, `todo_Market-Makers.md`, `pattern/pattern_1.md` |
| C19 | Réduction de `max_positions` en régime sentiment dégradé | `todo_quantitatif.md`, `pattern/pattern_1.md` |
| C20 | Maximum 2 tickers par secteur | `todo_quantitatif.md` |
| C21 | Intégrer `risk_multiplier` calculé en amont dans le sizing final | `todo_quantitatif.md` |
| C22 | Maintenir parité backtest/live | `todo_quantitatif.md`, `todo_Pattern.md` |
| C23 | TS dynamique ATR(14) × multiplicateur | `todo_pattern_smart_risk_ts.md` |
| C24 | Paramètre YAML `atr_multiplier`, `atr_period`, fallback fixe | `todo_pattern_smart_risk_ts.md` |
| C25 | External Order Sync des achats hors application | `todo_pattern_smart_risk_ts.md` |
| C26 | `replace_order` / `update_stop` côté Alpaca | `todo_pattern_smart_risk_ts.md` |
| C27 | Break-even auto si profit latent > 2 × ATR | `todo_pattern_smart_risk_ts.md` |
| C28 | End-of-Day check vers 15h50 EST | `todo_pattern_smart_risk_ts.md` |
| C29 | Générer des extraits/modules ciblant `backtesting/` et `execution/` | `todo_Market-Makers.md` |
| C30 | Ajouter configuration YAML dédiée `market_regimes` | `todo_Pattern.md`, `todo_Market-Makers.md` |
| C31 | Ajouter configuration YAML dédiée `risk_management.trailing_stop` | `todo_pattern_smart_risk_ts.md` |
| C32 | Prévoir des tests de validation ciblant le printemps 2025 | les 4 fichiers |

---

## 5. Architecture cible recommandée

## 5.1 Nouveau noyau central : `service/market/regime_manager.py`

### But
Créer un service unique qui calcule un objet de contexte marché réutilisable partout.

### Pourquoi
Les demandes de `todo_Pattern.md` et `todo_quantitatif.md` convergent toutes vers une logique centralisée. Il faut éviter :

- des règles dupliquées dans `run_execution.py`, `risk_management/` et `backtesting/` ;
- des écarts entre live et backtest ;
- des seuils divergents selon les modules.

### Interface cible proposée
Créer un modèle du type :

- `MarketRegimeSnapshot`
  - `trade_date`
  - `risk_multiplier`
  - `mode` (`normal`, `capital_preservation`, `close_only`, `cash_only`)
  - `adjusted_max_positions`
  - `enforced_min_notional`
  - `blocked_sectors`
  - `blocked_symbols`
  - `blocked_high_beta`
  - `sentiment_threshold_addon`
  - `allow_new_entries`
  - `notes` / `reasons`

### Responsabilités métier à mettre dans ce module
1. **Calendrier saisonnier**
   - Tax Day
   - Sept. Slump
   - Santa Rally
   - January Effect
   - OpEx
   - Month-End

2. **Régime macro**
   - VIX absolu
   - pente / inversion de courbe VIX si disponible
   - variation du 10Y US Treasury sur 5 jours

3. **Régime sentiment global**
   - score agrégé 7 jours
   - seuil de blocage
   - choix entre `close_only` et `cash_only`

4. **Contraintes d’entrée corporate/earnings**
   - blocage J-2 / J+2
   - buyback blackout

5. **Contrainte de petit capital**
   - `allowed_slots = floor(equity / enforce_min_notional)`
   - plafonnement de `max_positions`

### Sous-modules optionnels à prévoir
Si le fichier grossit trop, scinder en :

- `service/market/regime_manager.py`
- `service/market/calendar_patterns.py`
- `service/market/macro_signals.py`
- `service/market/sentiment_regime.py`
- `service/market/earnings_shield.py`

---

## 6. Plan d’implémentation détaillé par chantier

## Chantier A — Créer la couche "Sentinel / Market Regime"

### Modules principaux visés
- **Nouveau** `service/market/regime_manager.py`
- éventuellement `service/market/__init__.py`
- éventuellement helpers `service/market/*.py`

### Détails à implémenter

#### A1. Calendrier saisonnier configurable
Créer une table/règle de patterns pilotée par `config.yaml` avec :

- `tax_day`
- `sept_slump`
- `santa_rally`
- `january_effect`
- `institutional_opex`
- `month_end`

Chaque pattern doit pouvoir agir sur :

- `risk_multiplier`
- `max_positions`
- `sentiment_threshold_addon`
- `screening_universe_expansion`
- `block_new_entries`

#### A2. Macro-Overlay : VIX + 10Y Yield
Implémenter des règles telles que :

- si `VIX > 25` => mode `capital_preservation`
- si courbe VIX inversée / short-term > long-term => mode défensif
- si 10Y monte de plus de 5% sur 5 jours =>
  - blacklist secteurs Tech/Growth ;
  - exclure les titres high beta ;
  - réduire `risk_multiplier`

#### A3. Sortie standardisée du régime
Le résultat du `regime_manager` doit être consommable par :

- `selector/` (filtrage d’univers / exclusions)
- `risk_management/` (sizing / max positions / sector cap)
- `run_execution.py` (mode close_only, résumé pré-flight)
- `backtesting/` (parité replay)

### Risques / points d’attention
- Les données VIX/10Y ne sont pas aujourd’hui visibles dans les modules lus : prévoir soit un chargement depuis DB/cache, soit un adaptateur provider best-effort.
- Il faut une stratégie de fallback : si donnée macro absente, **ne pas planter** ; journaliser et continuer en mode neutre.

---

## Chantier B — Intégrer le régime au screener / selector / sentiment / ML

### Modules probables à faire évoluer
- `selector/alpha_scanner.py`
- `selector/strict_filter_profiles.py`
- `event_sentiment/signal_aggregator.py`
- éventuellement `modelFactory/` ou couche d’assemblage des scores

### Détails à couvrir

#### B1. Earnings Shield J-2 / J+2
À partir de `stock_earnings_calendar` :

- blocage strict des nouvelles entrées dans la fenêtre **J-2 / J+2** ;
- en mode souple, possibilité de **forcer un score négatif** au lieu d’une exclusion stricte ;
- conserver un flag explicite de raison métier (`earnings_shield`, `earnings_score_penalty`, etc.).

#### B2. Buyback blackout
Ajouter un signal binaire ou un malus :

- si dans les 2 semaines avant earnings, réduire le score ML de **30%** ;
- ce malus doit être visible dans les diagnostics / reporting.

#### B3. Filtre taux / secteurs / high beta
Quand `regime_manager` active le yield filter :

- exclure `Tech` / `Growth` ;
- exclure les high beta ;
- annoter les rejets dans les stats du screener/backfill.

#### B4. Smart Money filters
Rendre configurable :

- hausse du seuil minimal de sentiment autour d’OpEx ;
- blocage total des entrées à OpEx en mode strict ;
- durcissement éventuel fin de mois.

#### B5. Santa Rally / January Effect
Prévoir deux modes configurables :

- **mode agressivité** : hausse modérée du `risk_multiplier` ;
- **mode screener élargi** : expansion contrôlée de `selection_size` ou relâchement de certains filtres très marginalement.

### Position d’implémentation recommandée
Ne pas coder ces règles directement dans chaque module. Les modules doivent seulement **consommer** un `MarketRegimeSnapshot`.

---

## Chantier C — Adapter `risk_management/` au petit capital et au régime

### Modules visés
- `risk_management/config.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/portfolio_builder.py`
- `risk_management/cli.py`
- éventuellement `risk_management/models.py`

### Détails à couvrir

#### C1. Intégrer `risk_multiplier` au sizing final
Le sizing ATR existant doit être multiplié par un facteur de régime.

Exemples :

- Tax Day / Sept. Slump : réduction de taille
- Santa Rally / January Effect : légère hausse de taille
- Capital Preservation : réduction forte / max 1 position

#### C2. Recalcul dynamique des slots pour éviter `Notional insuffisant < 150$`
Implémenter une règle centrale :

- `allowed_slots = floor(total_equity / enforce_min_notional)`
- `effective_max_positions = min(max_positions_config, allowed_slots)`
- `effective_max_positions >= 1` si le capital le permet

Cette logique doit être appliquée dans :

- `risk_management` live ;
- `backtesting` phase 2 (`risk_execution`) ;
- le résumé du pré-flight.

#### C3. Min notional configurable 150/155 USD
Le code actuel utilise déjà `min_position_notional`, mais le plan doit prévoir :

- un seuil d’exécution compatible Alpaca (`155` conseillé pour marge de sécurité) ;
- une journalisation explicite des rejets évités grâce au recalcul dynamique des slots.

#### C4. Sentiment Circuit Breaker
Ajouter un circuit breaker supplémentaire basé sur le score agrégé :

- seuil bas : réduction de `max_positions` (ex. 5 → 2) ;
- seuil critique : mode `close_only` en live ou `cash_only` côté risk/backtest.

#### C5. Capital Preservation
Quand VIX ou sentiment sont très dégradés :

- `max_positions = 1` ou très faible ;
- stops plus serrés ou overlays plus prudents ;
- blocage des nouvelles entrées si le régime l’exige.

#### C6. Filtre de diversification sectorielle par nombre de titres
Ajouter la contrainte demandée :

- **maximum 2 tickers par secteur**

Cette règle complète `max_sector_weight`, elle ne la remplace pas.

### Point d’adaptation important
Le prompt cite `service/market/risk_manager.py`, mais la base réelle du projet est `risk_management/`. Le plan recommande donc de **brancher la logique dans `risk_management/`**, avec au besoin un helper `service/market/` pour le calcul de régime.

---

## Chantier D — Intégrer le régime à `run_execution.py` et à l’exécution live

### Modules visés
- `run_execution.py`
- `execution_engine/config.py`
- `execution_engine/executor.py`
- éventuellement `execution_engine/broker_adapter.py`

### Détails à implémenter

#### D1. Appel du `regime_manager` au début de chaque cycle
Au démarrage du run :

- calculer le contexte marché ;
- afficher un **pré-flight summary** lisible ;
- enrichir le run summary avec les décisions de régime.

#### D2. Pré-flight Summary attendu
Le résumé devrait au minimum afficher :

- mode marché (`normal`, `capital_preservation`, `close_only`, `cash_only`) ;
- `risk_multiplier` ;
- VIX / variation 10Y si disponible ;
- patterns calendaires actifs ;
- `effective_max_positions` ;
- `min_notional` effectif ;
- secteurs blacklistés ;
- raison éventuelle du blocage d’entrées.

#### D3. Close Only / Cash Only
Définir clairement les modes :

- **close_only** :
  - on laisse la gestion des positions existantes ;
  - aucune nouvelle entrée.
- **cash_only** :
  - aucune nouvelle entrée ;
  - possibilité optionnelle d’alléger ou de sortir selon politique ;
  - en backtest, ce mode doit être représentable explicitement.

#### D4. Ajustement dynamique du capital
Avant de soumettre les ordres :

- recalculer `effective_max_positions` ;
- ajuster le nombre de cibles retenues ;
- éviter les ordres théoriquement destinés à être rejetés par le broker.

### Point de performance
Le `regime_manager` ne doit pas être rappelé pour chaque ordre. Un **snapshot par run** suffit.

---

## Chantier E — Étendre le backtesting pour conserver la parité métier

### Modules visés
- `backtesting/cli/_impl.py`
- `backtesting/simulator.py`
- `backtesting/risk_bridge.py`
- `backtesting/profiles.py`
- `backtesting/risk_overlay.py`
- éventuellement `backtesting/report.py` / `analytics.py`

### Détails à couvrir

#### E1. Phase 2 `risk_execution`
Le prompt demande explicitement de modifier la logique d’allocation dans `phase2_mode: risk_execution`.

À prévoir :

- injection de `effective_max_positions` calculé depuis le capital courant ;
- propagation du `risk_multiplier` de régime ;
- prise en compte du `min_notional` broker-compatible ;
- diagnostics dédiés dans les artefacts `phase2_risk_summary.json`.

#### E2. Replay des régimes dans le simulateur
Le backtest doit pouvoir rejouer :

- Tax Day / Sept. Slump
- Santa / January
- VIX high / capital preservation
- yield filter
- circuit breaker sentiment
- earnings shield

#### E3. Overlays de backtest à enrichir
Le plus cohérent est d’étendre `backtesting/risk_overlay.py` ou d’ajouter un adaptateur vers `MarketRegimeSnapshot` pour éviter une logique parallèle.

#### E4. Reporting de validation
Le reporting backtest doit exposer :

- nb de jours en mode défensif ;
- nb d’entrées bloquées par régime ;
- nb d’entrées bloquées par earnings shield ;
- nb de rejets évités par recalcul dynamique des slots ;
- impact du yield filter ;
- impact du sentiment circuit breaker.

#### E5. Profils de backtest dédiés
Ajouter des profils ou presets de validation du type :

- `spring_2025_defensive_regime`
- `spring_2025_baseline`
- `santa_january_aggressive`

---

## Chantier F — ATR trailing stop dynamique + sync externe des achats manuels

### Modules réels les plus pertinents
Plutôt que `service/market/risk_manager.py` (non présent), le dépôt actuel suggère d’implémenter dans :

- `execution_engine/config.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/orphan_adoption.py`
- `execution_engine/broker_adapter.py`
- éventuellement un helper nouveau : `service/market/volatility.py`

### Détails à couvrir

#### F1. Stop initial des achats orphelins basé sur ATR
Remplacer la logique fixe `manual_buy_stop_loss_pct` par :

- `ATR(14) × atr_multiplier`
- fallback `fallback_fixed_pct` si ATR indisponible

#### F2. Source ATR
Pour un achat hors application détecté via adoption orpheline :

- récupérer l’ATR depuis une source compatible EODHD/Alpaca ;
- préférer une source déjà historisée / cache local ;
- ne pas bloquer l’adoption si l’ATR échoue.

#### F3. Update des protections Alpaca
Après calcul :

- remplacer / mettre à jour le stop via broker adapter ;
- enregistrer l’événement de sync externe dans l’audit trail.

#### F4. Break-even institutionnel
Si profit latent > `2 × ATR` :

- remonter le stop au prix d’entrée ;
- logguer la promotion explicitement.

#### F5. End-of-Day Check 15h50 EST
Prévoir une routine légère côté watcher ou job dédié :

- réévaluer ATR / volatilité ;
- préparer la protection du lendemain ;
- ne pas déclencher une boucle coûteuse en temps réel.

### Point de prudence
Le watcher existe déjà et gère la promotion de protections. Le plan recommande donc **d’étendre le watcher**, pas de créer un deuxième moteur parallèle.

---

## Chantier G — Configuration YAML à ajouter

## 7.1 Bloc `market_regimes`

Ajouter une section centrale de ce type :

```yaml
market_regimes:
  enabled: true
  cache_ttl_seconds: 300
  enforce_min_notional: 155
  allow_neutral_fallback_on_missing_macro_data: true

  sentinel:
    enabled: true
    preflight_summary: true

  vix:
    enabled: true
    symbol: "VIX"
    high_threshold: 25.0
    inverted_curve_mode: capital_preservation

  yields:
    enabled: true
    symbol_10y: "US10Y"
    lookback_days: 5
    relative_spike_threshold: 0.05
    block_sectors: ["Technology", "Tech", "Growth"]
    block_high_beta: true
    high_beta_threshold: 1.2
    risk_mult: 0.6

  sentiment_circuit_breaker:
    enabled: true
    lookback_days: 7
    warning_threshold: -0.15
    critical_threshold: -0.30
    warning_max_positions: 2
    critical_mode_live: close_only
    critical_mode_backtest: cash_only

  sector_limits:
    enabled: true
    max_tickers_per_sector: 2

  earnings_shield:
    enabled: true
    days_before: 2
    days_after: 2
    mode: strict_block   # strict_block | negative_score
    negative_score_value: -1.0

  buyback_blackout:
    enabled: true
    days_before_earnings: 14
    ml_score_multiplier: 0.70

  patterns:
    tax_day:
      enabled: true
      start: "04-10"
      end: "04-20"
      risk_mult: 0.4
    sept_slump:
      enabled: true
      start: "09-15"
      end: "10-15"
      risk_mult: 0.4
    santa_rally:
      enabled: true
      start: "12-20"
      end: "12-31"
      risk_mult: 1.15
      screener_expansion_pct: 0.10
    january_effect:
      enabled: true
      start: "01-02"
      end: "01-15"
      risk_mult: 1.10
      screener_expansion_pct: 0.10
    institutional_opex:
      enabled: true
      rule: "3rd_friday"
      mode: sentiment_hardening  # sentiment_hardening | block_entries
      sentiment_threshold_addon: 0.20
    month_end:
      enabled: true
      business_days_from_month_end: 2
      sentiment_threshold_addon: 0.10
```

## 7.2 Bloc `risk_management.trailing_stop`

```yaml
risk_management:
  trailing_stop:
    enabled: true
    mode: dynamic_atr
    atr_period: 14
    atr_multiplier: 2.5
    fallback_fixed_pct: 5.0
    break_even_after_atr_multiple: 2.0
    eod_check_time_est: "15:50"
    apply_to_manual_orphan_buys: true
```

## 7.3 Bloc `execution`

Optionnel mais recommandé pour garder la configuration lisible :

```yaml
execution:
  modes:
    close_only_allows_position_management: true
    cash_only_allows_new_entries: false
```

---

## 8. Modules concrets à modifier en priorité

## Priorité 1 — Noyau de régime
- `service/market/regime_manager.py` **(nouveau)**
- `common/config_loader.py` (uniquement si besoin de lecture plus structurée)

## Priorité 2 — Risk management / phase 2
- `risk_management/config.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/portfolio_builder.py`
- `risk_management/cli.py`
- `backtesting/risk_bridge.py`
- `backtesting/simulator.py`

## Priorité 3 — Exécution live
- `run_execution.py`
- `execution_engine/config.py`
- `execution_engine/executor.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/broker_adapter.py`

## Priorité 4 — Screener / sentiment / ML / earnings
- `selector/alpha_scanner.py`
- `event_sentiment/signal_aggregator.py`
- éventuels modules `modelFactory/` côté score ML si buyback blackout branché à ce niveau
- éventuel accès DB earnings si nécessaire

## Priorité 5 — Tests et reporting
- `tests/` (nouveaux tests ciblés)
- `backtesting/report.py` / diagnostics phase 2

---

## 9. Ordre recommandé d’implémentation

### Étape 1 — Fondations
1. Créer `service/market/regime_manager.py`
2. Définir `MarketRegimeSnapshot`
3. Ajouter la config YAML
4. Brancher les fallbacks neutres si données absentes

### Étape 2 — Petit capital / risk management
5. Ajouter `effective_max_positions`
6. Implémenter `allowed_slots = floor(equity / 155)`
7. Intégrer `risk_multiplier` dans le sizing
8. Ajouter `max_tickers_per_sector = 2`

### Étape 3 — Earnings / sentiment / macro filters
9. Implémenter earnings shield J-2/J+2
10. Ajouter le mode `negative_score`
11. Ajouter buyback blackout ML -30%
12. Ajouter yield filter Tech/Growth/high beta
13. Ajouter VIX / capital preservation
14. Ajouter sentiment circuit breaker

### Étape 4 — Live execution
15. Appeler `regime_manager` depuis `run_execution.py`
16. Ajouter le pré-flight summary
17. Bloquer les nouvelles entrées en `close_only` / `cash_only`

### Étape 5 — Backtesting parity
18. Brancher le régime dans `backtesting/risk_bridge.py`
19. Reporter les diagnostics dans `backtesting/simulator.py`
20. Ajouter les scénarios de validation printemps 2025

### Étape 6 — ATR trailing / sync externe
21. Remplacer le stop fixe des achats orphelins par ATR dynamique
22. Ajouter break-even `2 × ATR`
23. Ajouter EOD check 15h50 EST
24. Ajouter la télémétrie et l’audit associés

---

## 10. Tests de validation à prévoir impérativement

## 10.1 Tests unitaires

### Régime marché
- activation Tax Day sur une date du 15 avril ;
- activation Sept. Slump ;
- activation Santa Rally ;
- activation January Effect ;
- calcul OpEx 3e vendredi ;
- durcissement month-end ;
- VIX > 25 => capital preservation ;
- 10Y +5% sur 5 jours => blacklist secteurs ;
- sentiment < seuil critique => mode `close_only` / `cash_only`.

### Risk management
- `allowed_slots = floor(equity / 155)` ;
- equity trop faible => réduction de `max_positions` ;
- aucun ordre proposé sous le seuil minimum ;
- max 2 tickers par secteur ;
- sizing avec `risk_multiplier` < 1 et > 1.

### Earnings / ML / sentiment
- J-2 / J+2 => blocage ;
- mode `negative_score` => score forcé ;
- buyback blackout => score ML réduit de 30%.

### ATR trailing
- ATR présent => stop dynamique calculé ;
- ATR absent => fallback fixe ;
- profit latent > `2 × ATR` => break-even ;
- position orpheline adoptée => stop synchronisé.

## 10.2 Tests d’intégration

### Exécution live/paper
- `run_execution.py` affiche le résumé de régime ;
- mode `close_only` interdit les nouveaux achats ;
- recalcul dynamique de slots empêche les ordres < 150$ ;
- yield filter retire Tech/Growth du flux.

### Backtesting / phase 2
- `--phase2-mode risk_execution` applique bien le `min_notional` effectif ;
- diagnostics phase 2 exposent les rejets évités / blocages de régime ;
- parité entre `risk_management` live et phase 2 backtest.

## 10.3 Scénarios de backtest obligatoires

### Scénario S1 — Printemps 2025 baseline vs market-aware
Comparer :
- **baseline** sans nouvelle couche de régime ;
- **market-aware** avec Tax Day + yield filter + sentiment breaker + slots dynamiques.

Mesures attendues :
- drawdown max ;
- nb d’ordres rejetés pour notional ;
- nb d’entrées bloquées ;
- exposition Tech/Growth ;
- vitesse de récupération.

### Scénario S2 — Tax Day isolé
Backtest focalisé sur `2025-04-10` à `2025-04-20` pour vérifier :
- baisse d’exposition ;
- diminution du drawdown ;
- baisse du nombre de nouvelles positions.

### Scénario S3 — Yield shock mai 2025
Vérifier :
- blacklist Tech/Growth ;
- baisse des trades high beta ;
- amélioration du comportement sur les symboles sensibles taux.

### Scénario S4 — Sentiment collapse
Simuler un score agrégé très négatif pour vérifier :
- passage en `close_only` live ;
- passage en `cash_only` backtest ;
- réduction de `max_positions` en zone warning.

### Scénario S5 — Earnings season
Autour des publications T1 2025 :
- aucun trade ouvert en J-2 / J+2 en mode strict ;
- score négatif forcé en mode soft.

### Scénario S6 — Santa Rally / January Effect
Valider :
- hausse contrôlée de l’agressivité ;
- absence de dérive excessive du risque ;
- gains éventuels de couverture d’opportunités.

### Scénario S7 — Petit capital 2 000 USD
Reproduire le cas utilisateur :
- plus d’ordres < 150$ ;
- `allowed_slots` cohérent ;
- phase 2 `risk_execution` stable avec capital réduit.

### Scénario S8 — Achat manuel hors application
Valider :
- adoption orpheline ;
- calcul ATR ;
- stop Alpaca correctement mis à jour ;
- break-even puis EOD check fonctionnels.

---

## 11. Risques techniques et arbitrages recommandés

## 11.1 Données VIX / 10Y non encore branchées
Arbitrage recommandé :
- d’abord implémenter l’API interne du régime avec fallback neutre ;
- brancher ensuite la source la plus fiable disponible ;
- ne jamais bloquer l’exécution si la donnée macro manque.

## 11.2 Divergence entre exclusion stricte et score négatif
Certains prompts demandent un **blocage strict**, d’autres un **score négatif forcé**.

Arbitrage recommandé :
- supporter les deux via config :
  - `strict_block`
  - `negative_score`

## 11.3 Divergence OpEx : durcissement vs blocage total
Arbitrage recommandé :
- mode soft = durcir le sentiment ;
- mode strict = bloquer les entrées.

## 11.4 Close Only vs Cash Only
Arbitrage recommandé :
- live : `close_only` par défaut pour ne pas casser la gestion des positions existantes ;
- backtest / risk : `cash_only` pour matérialiser l’arrêt de nouvelles allocations.

## 11.5 Trailing ATR sur achats orphelins
Le dépôt a déjà une logique d’adoption orpheline et de watcher de protections. Il faut **étendre l’existant**, pas réécrire une seconde chaîne.

---

## 12. Définition de done (DoD)

Le chantier sera considéré terminé quand :

1. tous les points `C01` à `C32` sont couverts en code et tests ;
2. `run_execution.py` affiche un résumé de contexte marché ;
3. `phase2_mode=risk_execution` n’émet plus de cibles impossibles pour un petit capital ;
4. les règles saisonnières et macro sont rejouées en backtest ;
5. les positions proches earnings sont bloquées ou pénalisées selon la config ;
6. les achats manuels orphelins reçoivent un stop ATR dynamique ;
7. les scénarios du printemps 2025 montrent une amélioration mesurable du comportement ;
8. EODHD et Alpaca restent compatibles ;
9. la logique live et backtest utilise bien la même couche centrale de régime.

---

## 13. Résumé exécutif

La meilleure trajectoire n’est pas d’ajouter des règles dispersées, mais de construire une **couche centrale de régime marché** qui pilote ensuite :

- le screener,
- le scoring sentiment/ML,
- le sizing,
- l’exécution live,
- le replay backtest,
- et les protections post-exécution.

Le dépôt actuel fournit déjà les briques utiles :

- `risk_management/` pour le sizing,
- `execution_engine/` pour l’exécution et le watcher,
- `backtesting/` pour la parité,
- `stock_earnings_calendar` pour le blackout résultats.

Le plan ci-dessus permet donc de couvrir **tous les points cités dans tous les fichiers `todo_*.md`**, sans casser l’architecture existante, tout en adaptant l’implémentation aux modules réellement présents dans le dépôt.

