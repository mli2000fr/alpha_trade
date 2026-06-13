# Plan d’intégration du levier (mode long-only)

> **État d’implémentation (2026-06-13)**
>
> La V1 du support levier est désormais **implémentée** dans le dépôt :
>
> - bloc `leverage` ajouté dans `config.yaml` ;
> - `LeverageConfig` + `load_leverage_config_from_yaml()` dans `execution_engine/config.py` ;
> - résolution du budget effectif dans `execution_engine/account_state.py` ;
> - priorité `regt_buying_power` puis `buying_power` ;
> - garde-fous `margin`, `equity >= 2 000 $`, `entry_mode=normal`, plafond `2.0x` ;
> - visibilité dans les logs, les `execution_events`, `broker_account_snapshots.raw_payload_json` et les `run_summary` d’exécution.
>
> Le plan ci-dessous reste utile comme documentation d’architecture et de rollout.

## Verdict rapide

Oui, **ça peut être une bonne idée**, mais **pas comme un simple multiplicateur global toujours actif**.

Pour une application **long-only** avec un drawdown historique autour de **13%**, un levier léger peut améliorer le profil de performance **si et seulement si** il est :

- **désactivable par configuration** ;
- **limité au mode normal** ;
- **bloqué sous 2 000 $ d’equity** ;
- **plafonné à 2x maximum en swing overnight** ;
- **borné par le buying power réel du broker** ;
- **désactivé automatiquement en régimes défensifs**.

En pratique, je recommande un déploiement en **2 phases** :

1. **V1 prudente** : 1.25x à 1.50x max ;
2. **V2 optionnelle** : jusqu’à 2.0x, uniquement après validation backtest + paper + garde-fous live.

---

## Pourquoi ce n’est pas “gratuit”

Le fait que le drawdown passé soit faible **n’implique pas** qu’un levier 2x soit mécaniquement sûr :

- le **risque overnight** est non linéaire (gaps) ;
- la **liquidité** et le **slippage** montent quand la taille augmente ;
- un backtest long-only avec faible DD peut se dégrader vite en stress macro ;
- le levier augmente aussi les risques opérationnels : rejet d’ordre, pouvoir d’achat mal estimé, expositions cumulées.

Approximation simple si le comportement restait linéaire :

- DD 13% à **1.5x** → ~**19.5%** ;
- DD 13% à **2.0x** → ~**26%**.

En réel, le résultat peut être **pire** à cause des gaps et de l’exécution.

---

## Ce que j’ai vérifié dans le code actuel

### Points déjà présents

- `config.yaml` existe : `F:\projets\config.yaml`
- la config d’exécution supporte déjà un compte `cash` ou `margin` :
  - `F:\projets\execution_engine\config.py`
  - `ExecutionConfig.account_type`
- en simulation, il existe déjà une notion de buying power de marge :
  - `ExecutionConfig.simulated_margin_buying_power_multiplier = 2.0`
- le snapshot compte live/paper vient du broker via :
  - `F:\projets\service\alpaca\trading_client.py`
  - `AlpacaTradingClient.get_account()` → `GET /v2/account`
- le moteur de contraintes compte utilise aujourd’hui :
  - `equity`
  - `cash`
  - `buying_power`
  - `non_marginable_buying_power`
  - fichier : `F:\projets\execution_engine\account_state.py`

### Point important sur `regt_buying_power`

Je ne peux pas interroger ton compte réel depuis ici, donc je ne peux **pas confirmer sur ton compte live/paper exact** la présence du champ au runtime.

En revanche, pour **Alpaca `/v2/account`**, le champ **attendu côté Reg-T** est généralement bien **`regt_buying_power`**.

### Recommandation robuste

Pour le mode swing overnight, il faut utiliser la hiérarchie suivante :

1. `regt_buying_power` si présent ;
2. sinon `buying_power` ;
3. sinon fallback défensif ;
4. et **ne jamais dépasser `2.0x` d’exposition cible**.

Autrement dit :

- **oui**, `regt_buying_power` est la **bonne variable prioritaire à viser** pour le contrôle du pouvoir d’achat Reg-T ;
- mais en code il faut prévoir un **fallback sûr** car le payload peut varier selon compte / mode / broker adapter.

---

## Contraintes métier à imposer

### 1) Règle des 2 000 $

Le levier de marge ne doit jamais être autorisé si :

- `equity < 2000`, ou
- `account_type != "margin"`.

Action recommandée :

- si la config active le levier mais que `equity < 2000`, alors :
  - **désactivation automatique du levier** ;
  - log explicite ;
  - événement d’audit.

### 2) Swing overnight = 2x maximum

Même si le broker renvoie plus, on borne le système à :

- `max_effective_leverage = min(config.leverage.max_leverage, 2.0)`

Pour ton cas, le plafond opérationnel doit être :

- **2.0 maximum** en swing overnight.

### 3) Levier seulement en régime “normal”

Désactivation automatique si :

- `entry_mode != "normal"`, ou
- mode `capital_preservation`, `cash_only`, `close_only`, ou
- régime marché défensif.

### 4) Long-only uniquement

Le levier doit seulement :

- augmenter le **budget notionnel achetable** ;
- **ne rien changer** à la logique short (inexistante ici).

---

## Proposition de configuration YAML

À ajouter dans `config.yaml` :

```yaml
leverage:
  enabled: false
  mode: regt_swing
  max_leverage: 1.5        # plafond opérateur, borné en code à 2.0 max overnight
  min_equity_usd: 2000
  require_margin_account: true
  only_in_entry_mode: normal
  disable_in_capital_preservation: true
  disable_if_buying_power_field_missing: false
  buying_power_field_priority:
    - regt_buying_power
    - buying_power
  dry_run_simulated_leverage: 1.5
  audit_log: true
```

### Sémantique

- `enabled`: active/désactive la fonctionnalité ;
- `mode`: permet de documenter le cas d’usage, ici `regt_swing` ;
- `max_leverage`: objectif de levier ;
- `min_equity_usd`: règle des 2 000 $ ;
- `require_margin_account`: interdit sur compte cash ;
- `only_in_entry_mode: normal`: pas de levier en mode défensif ;
- `buying_power_field_priority`: ordre de lecture du snapshot broker ;
- `dry_run_simulated_leverage`: cohérent avec les runs simulés.

---

## Design technique recommandé

## Étape 1 — Étendre la configuration d’exécution

### Fichier
- `F:\projets\execution_engine\config.py`

### À ajouter
Créer une dataclass dédiée, par exemple :

- `LeverageConfig`

Champs recommandés :

- `enabled: bool = False`
- `mode: Literal["disabled", "regt_swing"] = "disabled"`
- `max_leverage: float = 1.0`
- `min_equity_usd: float = 2000.0`
- `require_margin_account: bool = True`
- `only_in_entry_mode: Literal["normal", "any"] = "normal"`
- `disable_in_capital_preservation: bool = True`
- `disable_if_buying_power_field_missing: bool = False`
- `buying_power_field_priority: tuple[str, ...] = ("regt_buying_power", "buying_power")`
- `dry_run_simulated_leverage: float = 1.0`
- `audit_log: bool = True`

Puis ajouter dans `ExecutionConfig` :

- `leverage: LeverageConfig = field(default_factory=LeverageConfig)`

### Validation à ajouter

- `1.0 <= max_leverage <= 2.0`
- `min_equity_usd >= 0`
- si `mode == "disabled"` alors `enabled = False` ou levier forcé à `1.0`
- `dry_run_simulated_leverage` borné à `[1.0, 2.0]`

---

## Étape 2 — Charger la config depuis `config.yaml`

### Fichier
- `F:\projets\run_execution.py`

Aujourd’hui, `ExecutionConfig` est instancié ici :

- `config = ExecutionConfig(**preset, account_id=..., trailing_stop=...)`

### À faire

Ajouter un chargeur YAML du bloc `leverage` puis injecter :

- `leverage=load_leverage_config_from_yaml()`

Option propre : créer un helper similaire à `load_trailing_stop_config_from_yaml()` dans `execution_engine/config.py`.

---

## Étape 3 — Résoudre le buying power broker en tenant compte du levier

### Fichier principal
- `F:\projets\execution_engine\account_state.py`

### Situation actuelle

La logique live fait aujourd’hui principalement :

- marge → `snapshot.get("buying_power")`
- cash → `snapshot.get("non_marginable_buying_power")`

### À changer

Créer un helper dédié, par exemple :

- `resolve_live_buying_power(snapshot, cfg) -> float`

### Algorithme recommandé

1. Lire `equity`
2. Si `cfg.leverage.enabled` est `False` → comportement actuel
3. Vérifier les préconditions :
   - `cfg.account_type == "margin"`
   - `equity >= cfg.leverage.min_equity_usd`
   - `cfg.entry_mode == "normal"` si requis
4. Chercher le pouvoir d’achat dans cet ordre :
   - `regt_buying_power`
   - `buying_power`
5. Calculer le plafond cible interne :
   - `target_budget = equity * min(cfg.leverage.max_leverage, 2.0)`
6. Calculer le budget réellement autorisé :
   - `effective_budget = min(target_budget, broker_buying_power_available)`
7. Utiliser `effective_budget` comme `buying_power_available`
8. Si préconditions non remplies → revenir au mode sans levier

### Important

Le levier ne doit **jamais inventer** du buying power.

Donc la formule correcte est :

```text
effective_budget = min(plafond_stratégie, buying_power_broker)
```

et non pas :

```text
effective_budget = equity * leverage sans contrôle broker
```

---

## Étape 4 — Ajouter une décision explicite d’activation du levier

### Recommandation

Créer un helper, par exemple :

- `is_leverage_active(cfg, snapshot) -> tuple[bool, str]`

Raisons possibles de désactivation :

- `feature_disabled`
- `cash_account`
- `equity_below_minimum`
- `entry_mode_not_normal`
- `capital_preservation`
- `missing_buying_power_field`
- `broker_buying_power_zero`

Cela rendra le comportement :

- traçable ;
- testable ;
- facile à auditer.

---

## Étape 5 — Journalisation / audit

### Où
- `execution_engine/account_state.py`
- éventuellement `execution_engine/audit.py` / events existants

### À logguer

Quand le levier est évalué :

- `equity`
- `account_type`
- `entry_mode`
- champ broker retenu (`regt_buying_power` ou `buying_power`)
- `broker_buying_power`
- `target_leverage`
- `effective_budget`
- raison de fallback si désactivé

Exemple d’événement utile :

- `LEVERAGE_APPLIED`
- `LEVERAGE_DISABLED`
- `LEVERAGE_FALLBACK_TO_BUYING_POWER`

---

## Étape 6 — UI / IHM plus tard (optionnel)

Si ton IHM lit déjà `config.yaml`, expose :

- un toggle `Activer le levier`
- un champ `Levier max` (1.0 à 2.0)
- un indicateur live :
  - `equity`
  - `regt_buying_power`
  - `budget utilisé`
  - `levier effectif`

Mais ce n’est **pas nécessaire** pour la première version.

---

## Plan d’implémentation concret par fichiers

## 1. `F:\projets\execution_engine\config.py`

Ajouter :

- `LeverageConfig`
- `load_leverage_config_from_yaml()`
- champ `leverage` dans `ExecutionConfig`
- validations métier

## 2. `F:\projets\config.yaml`

Ajouter le bloc :

- `leverage:`

Valeur initiale recommandée :

```yaml
leverage:
  enabled: false
  mode: regt_swing
  max_leverage: 1.5
  min_equity_usd: 2000
  require_margin_account: true
  only_in_entry_mode: normal
  disable_in_capital_preservation: true
  disable_if_buying_power_field_missing: false
  buying_power_field_priority:
    - regt_buying_power
    - buying_power
  dry_run_simulated_leverage: 1.5
  audit_log: true
```

## 3. `F:\projets\run_execution.py`

Injecter `leverage=load_leverage_config_from_yaml()` lors de la création de `ExecutionConfig`.

## 4. `F:\projets\execution_engine\account_state.py`

Ajouter :

- helper de lecture du pouvoir d’achat live
- helper d’activation/désactivation du levier
- plafond à 2x
- règle minimum 2 000 $
- fallback sécurisé

## 5. Tests

Créer / étendre des tests dans :

- `F:\projets\tests\test_execution_config.py`
- `F:\projets\tests\test_broker_snapshot_hardening.py`

---

## Cas de test indispensables

### Configuration

- refuse `max_leverage < 1.0`
- refuse `max_leverage > 2.0`
- accepte `1.0`, `1.25`, `1.5`, `2.0`

### Activation

- levier désactivé si `enabled = false`
- levier désactivé si `account_type = cash`
- levier désactivé si `equity < 2000`
- levier désactivé si `entry_mode = capital_preservation`
- levier activé si `margin + equity >= 2000 + mode normal`

### Lecture broker

- utilise `regt_buying_power` si présent
- fallback vers `buying_power` si `regt_buying_power` absent
- fallback sans crash si les deux sont absents

### Bornes

- `max_leverage=2.5` doit être refusé ou clampé selon politique choisie
- budget effectif ne dépasse jamais `2.0 * equity`
- budget effectif ne dépasse jamais le buying power broker

### Régression

- si `leverage.enabled = false`, comportement strictement identique à aujourd’hui

---

## Politique de rollout recommandée

### Phase 0 — Backtest

Comparer au minimum :

- `1.0x`
- `1.25x`
- `1.5x`
- `2.0x`

Mesurer :

- CAGR
- max drawdown
- ulcer index
- profit factor
- exposure moyenne
- volatilité portefeuille
- pire séquence de pertes
- sensibilité aux gaps

### Phase 1 — Paper trading

Activer :

- `enabled: true`
- `max_leverage: 1.25` ou `1.5`

Vérifier pendant plusieurs séances :

- cohérence `regt_buying_power` / budget interne
- rejets broker
- variation live du buying power
- comportement en ouverture / clôture

### Phase 2 — Live prudente

Commencer par :

- `1.25x` ou `1.5x`
- jamais `2.0x` dès le premier déploiement

---

## Recommandation finale

### Est-ce une bonne idée ?

**Oui, potentiellement**, mais **uniquement avec garde-fous stricts**.

### Ce que je recommande pour ton cas

- **Oui au levier**, mais :
  - seulement sur **compte margin** ;
  - seulement si **equity >= 2 000 $** ;
  - seulement en **mode normal** ;
  - **max 1.5x au départ** ;
  - **2.0x absolu maximum** en swing overnight ;
  - budget borné par **`regt_buying_power` prioritaire**, avec fallback `buying_power`.

### Ce que je déconseille

- un levier toujours actif ;
- un levier 2x par défaut dès la V1 ;
- un calcul de levier basé seulement sur l’equity sans lecture broker temps réel.

---

## Décision pratique proposée

### Valeur initiale sûre

```yaml
leverage:
  enabled: false
  mode: regt_swing
  max_leverage: 1.5
  min_equity_usd: 2000
  require_margin_account: true
  only_in_entry_mode: normal
  disable_in_capital_preservation: true
  disable_if_buying_power_field_missing: false
  buying_power_field_priority:
    - regt_buying_power
    - buying_power
  dry_run_simulated_leverage: 1.5
  audit_log: true
```

### Règle d’activation opérationnelle

Activer seulement après :

- validation backtest ;
- validation paper ;
- confirmation que le payload `get_account` expose bien `regt_buying_power` sur ton compte cible.

---

## Résumé en une phrase

**Le levier léger peut améliorer un système long-only robuste, mais dans ton application il doit être implémenté comme une capacité optionnelle, plafonnée, pilotée par `config.yaml`, bornée par `regt_buying_power`/`buying_power`, et automatiquement coupée sous 2 000 $, hors compte margin, ou hors régime normal.**

---

## Clarification importante — protections drawdown live vs backtest

Les trois paramètres backtest suivants ont bien des **équivalents live** dans
les presets capital :

- `backtesting_max_portfolio_dd_pct` ↔ `risk_max_drawdown_pct`
- `backtesting_dd_rolling_peak_window_days` ↔ `risk_drawdown_rolling_peak_window_days`
- `backtesting_dd_degraded_allocation_pct` ↔ `risk_degraded_entry_allocation_pct`

Autrement dit, **oui : le live est protégé contre le drawdown**.

La différence est surtout de **nomenclature** et de **couche de consommation** :

- les clés `backtesting_*` alimentent `backtesting/risk_overlay.py` ;
- les clés `risk_*` alimentent `RiskConfig` puis
  `risk_management.circuit_breaker.CircuitBreaker` côté pipeline live / risk / execution.

Le comportement live actuel est donc :

- arrêt du run si drawdown/perte journalière dépassent les seuils ;
- ou **mode dégradé** si `risk_degraded_entry_allocation_pct > 0` ;
- avec référence possible à un **pic roulant** via
  `risk_drawdown_rolling_peak_window_days`.

