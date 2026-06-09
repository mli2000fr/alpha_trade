# Plan détaillé — évolution vers les achats fractionnaires

_Date : 2026-06-09_

## Checklist
- [x] Lire la source de vérité du code
- [x] Relever les contraintes documentaires Alpaca
- [x] Identifier les blocages backtest
- [x] Identifier les blocages live Alpaca
- [x] Structurer un plan d’évolution par sprint
- [x] Sauvegarder le plan dans `prompt/fraction/plan.md`

## Mise à jour — état réel au 2026-06-09 après implémentation

### Sprint 1
Le **Sprint 1 est désormais clôturé**.

Complété depuis la première revue :
- helper transverse créé dans `common/quantity_utils.py` ;
- normalisation / formatage broker branchés dans `execution_engine/order_intents.py` ;
- garde-fou runtime `fractionable` branché avant soumission live via :
  - `execution_engine/executor.py`,
  - `execution_engine/order_intents.py`,
  - `execution_engine/db_io.py` (`load_fractionable_asset_map`) ;
- tests ajoutés sur :
  - normalisation 9 décimales,
  - quasi-entier / epsilon,
  - formatage broker,
  - blocage d’un target fractionnaire sur asset non fractionable.

### Sprint 2
Le **Sprint 2 est également implémenté** sur le périmètre risk.

Complété :
- `risk_management/config.py` expose maintenant `allow_fractional_shares` ;
- `risk_management/position_sizer.py` sait produire des quantités fractionnaires sous feature flag ;
- `risk_management/constraints.py` réduit/rejette en float sans retroncature entière ;
- `risk_management/risk_checker.py` ne recaste plus en `int` ;
- `risk_management/portfolio_builder.py` propage les quantités fractionnaires avec comparaison epsilon ;
- `risk_management/cli.py` n’écrase plus les quantités décimales dans les exports/synthèses.

### Couverture validée
- `126 passed` sur le bundle ciblé Sprint 1 + Sprint 2 ;
- `64 passed` sur la revalidation Sprint 1 (`assets`, `execution_db_io`, `order_intents`).

---

## 1. Objectif

Permettre les **achats fractionnaires** :
1. en **backtest**,
2. en **live/paper Alpaca**,
3. sans casser les flux existants en parts entières,
4. avec une stratégie de déploiement progressive, contrôlée et réversible.

Le plan ci-dessous est basé sur la **source de vérité du code** et sur la **documentation publique Alpaca**.

---

## 2. Sources analysées

### 2.1 Source de vérité interne

#### Exécution live / modèles / persistance
- `execution_engine/order_intents.py`
- `execution_engine/models.py`
- `execution_engine/config.py`
- `execution_engine/db_io.py`
- `execution_engine/children_submission.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/broker_adapter.py`
- `service/alpaca/trading_client.py`
- `service/alpaca/clientAlpaca.py`
- `database/assets.py`
- `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`
- `tests/test_execution_db_io.py`

#### Risk / sizing / portefeuille cible
- `risk_management/models.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/risk_checker.py`
- `risk_management/portfolio_builder.py`
- `risk_management/cli.py`
- `core/interfaces.py`

#### Backtest / replay / reporting
- `backtesting/simulator.py`
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/fidelity.py`
- `backtesting/report.py`

#### Référence utile annexe
- `corporate_actions/processors.py`
- `corporate_actions/models.py`
- `tests/test_corporate_actions.py`

### 2.2 Documentation Alpaca consultée

Page : `https://docs.alpaca.markets/us/docs/fractional-trading`

Points explicitement relevés :
- Alpaca supporte les fractional shares en **live et paper**.
- Les ordres fractionnaires documentés sont : **market, limit, stop, stop limit**.
- La documentation indique un **`time_in_force = day`** pour le fractional trading.
- On peut transmettre soit **`qty`**, soit **`notional`**, mais pas les deux.
- `qty` et `notional` acceptent jusqu’à **9 décimales**.
- L’asset doit être **`fractionable = true`**, sinon rejet broker.
- Les ventes fractionnaires short ne sont pas supportées.

### 2.3 Conséquence documentaire majeure

Le code actuel du projet utilise des protections live principalement en **GTC**, ainsi que des **trailing stop** et des **OCO**. Or, la documentation Alpaca consultée ne documente pas ces modes comme supportés pour le fractional trading.

**Conclusion importante** :
- le support fractional **entry** est réaliste rapidement,
- le support fractional **protection swing overnight** n’est **pas un simple switch**, car il existe un **écart structurel** entre :
  - la stratégie actuelle du projet (protection durable / GTC / swing),
  - et la surface fonctionnelle fractional documentée chez Alpaca (`day`, types limités).

---

## 3. Diagnostic synthétique

## 3.1 Ce qui existe déjà et va dans le bon sens

### Live Alpaca
Dans `execution_engine/order_intents.py` :
- `OrderIntent.qty` est déjà en `float`.
- `intent_to_alpaca_payload()` formate déjà correctement `qty` en string, entier si entier, décimal sinon.
- `build_oco_protection_payload()` formate aussi une quantité décimale.
- `service/alpaca/trading_client.py` transmet le payload tel quel au broker.

=> **La couche de transport live n’est pas le principal blocage.**

### Couche exécution métier
Dans `execution_engine/models.py` :
- `OrderIntent.qty`, `ExecutionOrderRequest.target_qty`, `BrokerOrder.qty`, `BrokerOrder.filled_qty`, `ExecutionFill.filled_qty`, `ExecutionPosition.net_qty`, `ExecutionPositionLot.opened_qty`, `remaining_qty` sont déjà en `float`.

=> **Une partie importante du noyau exécution est déjà prête.**

### Corporate actions
Dans `corporate_actions`, les traitements gèrent déjà `fractional_shares`.

=> **Le projet n’est pas conceptuellement fermé au fractionnel.**

---

## 3.2 Blocages structurels côté risk / sizing / portefeuille

### Modèles risk : blocage de types déjà levé
Dans `risk_management/models.py` :
- `SizingResult.proposed_shares: float`
- `PortfolioEntry.proposed_shares: float`
- `PortfolioEntry.approved_shares: float`
- `RiskDecisionRow.proposed_shares: float`
- `RiskDecisionRow.approved_shares: float`
- `PortfolioTargetRow.shares: float`

=> **Le blocage “types entiers dans les modèles risk” est déjà levé.**

### Sizing force l’entier
Dans `risk_management/position_sizer.py` :
- `math.floor(risk_budget / risk_per_share)`
- rejet si `shares < 1`

=> **Impossible aujourd’hui d’obtenir 0.25, 0.5 ou 0.73 share.**

### Contraintes force l’entier
Dans `risk_management/constraints.py` :
- plusieurs usages de `int(max_notional // price)`
- plusieurs usages de `int(max_pos_notional // price)`
- plusieurs usages de `int(remaining // price)`
- rejet si `< 1`

=> **Les caps portefeuille / secteur / gross exposure cassent le fractionnel.**

### Contrôleur risque recaste en entier
Dans `risk_management/risk_checker.py` :
- `proposed_shares=int(proposed_shares)`
- `accept(... shares: int ...)`

=> **Même si le sizing devenait fractionnaire, le résultat serait tronqué ensuite.**

### Builder force des comparaisons entières
Dans `risk_management/portfolio_builder.py` :
- logique de rejet sur `sizing.proposed_shares < 1`
- `approved = int(checker.check_position_size(...))`
- signatures `_make_entry_v2(... proposed: int, approved: int ...)`

=> **Le portefeuille cible lui-même est construit comme un portefeuille à parts entières.**

---

## 3.3 Blocages structurels côté backtest

### Position backtest stockée en entier
Dans `backtesting/simulator.py` :
- `_OpenPosition.quantity: int`

=> **Le portefeuille backtest ne peut pas porter proprement une quantité fractionnaire.**

### Calculs d’entrée tronqués
Dans `backtesting/simulator.py` :
- `int(state.settled_cash // effective_unit_cost)`
- `int(quantity_override)`
- `int(candidate_budget // effective_unit_cost)`
- `int(remaining_gross_notional // entry_price)`

=> **Le sizing d’entrée du simulateur est explicitement entier.**

### Replay / bridge tronquent les tailles
Dans :
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/fidelity.py`

on trouve plusieurs conversions :
- `int(entry.approved_shares)`
- `int(risk_row.get("approved_shares"))`
- `_safe_int(...)`
- `target_shares=int(...)`

=> **Même si le moteur risk devenait fractionnaire, les ponts de replay/reporting tronqueraient encore.**

---

## 3.4 Blocages structurels côté live Alpaca

### Le flag existe mais n’est pas branché
Dans `execution_engine/config.py` :
- `allow_fractional_shares: bool = False`

=> **Le paramètre existe mais n’oriente pas réellement la logique.**

### Snapshot d’exécution : blocage de type déjà levé
Dans `execution_engine/models.py` :
- `ExecutionTarget.target_shares: float`
- `ReconcileDiff.target_qty: float`

Dans `execution_engine/db_io.py` :
- `target_shares=float(r["shares"])`
- `target_shares=float(r["target_shares"])`

Dans `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py` :
- `execution_targets_snapshot.target_shares` passe de `Integer` à `Float`

Dans `tests/test_execution_db_io.py` :
- `portfolio_targets.shares DOUBLE`
- `execution_targets_snapshot.target_shares DOUBLE`
- un test vérifie déjà une lecture à `100.5`

=> **L’amont de l’exécution live n’est plus bloqué par un type entier sur ce point.**

### Métadonnées asset : fondation posée, branchement runtime à terminer
La doc Alpaca impose `fractionable = true`. À date :
- `service/alpaca/clientAlpaca.py` récupère les assets bruts ;
- `database/assets.py` expose `_has_fractionable_column()` ;
- `insert_assets_to_db()` persiste déjà `fractionable` si la colonne existe ;
- la migration `0037_add_fractionable_and_fractional_target_shares.py` ajoute la colonne.

=> **Le blocage de schéma/persistance est levé, mais il reste à brancher clairement cette métadonnée dans la validation métier avant soumission live.**

### Problème critique sur les protections live
Le code actuel construit/soumet des protections live via :
- `execution_engine/children_submission.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/order_intents.py`

Or :
- `intent_to_alpaca_payload()` met `time_in_force = gtc` pour les enfants,
- `build_oco_protection_payload()` met `time_in_force = gtc`,
- le système s’appuie sur `OCO`, `stop`, `trailing_stop`, watchers et protections swing.

Mais la doc Alpaca fractional consultée documente surtout :
- `market`, `limit`, `stop`, `stop limit`,
- avec `time_in_force = day`.

=> **Le support fractional live des protections overnight est le principal risque produit/technique.**

---

## 4. Décision d’architecture recommandée

## 4.1 Cible recommandée

### Règle de représentation interne
- Utiliser **`float` applicatif** pour minimiser le diff dans le code existant.
- Introduire un helper central de normalisation de quantité au moment des frontières :
  - arrondi max 9 décimales,
  - epsilon pour comparaisons,
  - formatage string broker.

### Règle de compatibilité
- Conserver le comportement historique quand `allow_fractional_shares = false`.
- Activer le nouveau comportement seulement si le flag est vrai **et** si le broker / asset / mode d’ordre le permet.

### Règle broker live
Pour l’Alpaca live/paper :
- **MVP live** : support fractional sur les **ordres d’entrée buy**.
- **Ne pas promettre dès le sprint 1** un support complet des protections swing server-side.
- Introduire une **matrice de capacité broker** :
  - `fractional_entry_supported`
  - `fractional_day_stop_supported`
  - `fractional_oco_supported`
  - `fractional_trailing_supported`
  - `fractional_gtc_supported`

### Décision produit recommandée
Scinder le sujet en 2 niveaux :
1. **Fractional Backtest + Fractional Live Entry**
2. **Fractional Live Protection / Swing overnight**

Parce que le niveau 2 dépend d’une contrainte broker/documentation qui n’est pas levée par un simple refactor local.

---

## 5. Plan détaillé par sprint

# Sprint 0 — Cadrage, invariants et spike broker

## Objectif
Sécuriser la cible fonctionnelle avant de toucher au code métier profond.

## Travaux
- Écrire une mini-spécification fonctionnelle interne :
  - définition de “fractional enabled”,
  - actifs éligibles,
  - précision maximale supportée,
  - règles d’arrondi,
  - comportement quand la quantité calculée est `0 < qty < 1`.
- Formaliser une matrice de capacité Alpaca basée sur doc + tests papier.
- Faire un spike contrôlé en paper Alpaca pour vérifier :
  - `buy market day` avec `qty=0.5`,
  - `buy limit day` avec `qty=0.5`,
  - `sell stop day` fractionnaire,
  - `stop limit day` fractionnaire,
  - `trailing_stop` fractionnaire,
  - `oco` fractionnaire,
  - `gtc` fractionnaire.
- Décider la politique produit si `OCO/GTC/trailing` fractionnaire ne sont pas fiables :
  - soit on limite le live fractional aux entrées,
  - soit on crée un mode “fractional intraday/day only”,
  - soit on accepte une protection applicative partielle via watcher.

## Livrables
- Note d’architecture “fractional capability matrix”.
- Table de décisions produit/ops.
- Jeux de payloads validés en paper.

## Critères d’acceptation
- Chaque type d’ordre utile est classé : `supporté`, `non supporté`, `non documenté`, `à éviter`.
- La trajectoire MVP live est actée noir sur blanc.

## Risques traités
- Implémenter un support live théorique mais non exécutable chez Alpaca.

---

# Sprint 1 — Fondations de types et persistance partagée

## Objectif
Supprimer l’hypothèse “quantité entière” dans les modèles centraux.

## État au 2026-06-09
Sprint 1 est **terminé**.

## Travaux

### 1. Modèles risk
Statut : **✅ déjà fait**

Fichier vérifié :
- `risk_management/models.py`

Déjà en `float` :
- `SizingResult.proposed_shares`
- `PortfolioEntry.proposed_shares`
- `PortfolioEntry.approved_shares`
- `RiskDecisionRow.proposed_shares`
- `RiskDecisionRow.approved_shares`
- `PortfolioTargetRow.shares`

### 2. Modèles exécution
Statut : **✅ déjà fait**

Fichier vérifié :
- `execution_engine/models.py`

Déjà en `float` :
- `ExecutionTarget.target_shares`
- `ReconcileDiff.target_qty`

### 3. Persistance / schéma
Statut : **✅ déjà fait côté type DB / lecture Python**

Fichiers vérifiés :
- `execution_engine/db_io.py`
- `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`
- `tests/test_execution_db_io.py`

Constat :
- `db_io` lit déjà les quantités via `float(...)` ;
- la migration `0037` fait évoluer `execution_targets_snapshot.target_shares` en `Float` ;
- les schémas de test utilisent déjà `DOUBLE` ;
- la recommandation `Numeric(20,9)` reste valable si un durcissement DB est souhaité plus tard, mais elle n’est plus un prérequis bloquant pour Sprint 1.

### 4. Métadonnées assets
Statut : **✅ fait pour le périmètre Sprint 1**

Fichiers vérifiés :
- `database/assets.py`
- schéma `stock_metadata`
- sync Alpaca assets

Réalisé :
- `fractionable` est persisté ;
- `execution_engine/db_io.py` charge la capacité asset ;
- `execution_engine/executor.py` et `execution_engine/order_intents.py` bloquent désormais un target fractionnaire si l’asset n’est pas explicitement `fractionable=true`.

### 5. Helper transverse
Statut : **✅ fait**

Implémenté dans :
- `common/quantity_utils.py`

Responsabilités couvertes :
- normalisation à 9 décimales,
- epsilon de quantité,
- détection quasi-entier,
- formatage broker/log,
- clamp du bruit numérique autour de zéro.

## Livrables
- ✅ Modèles compatibles fractionnel.
- ✅ Migration DB de type / colonne (`0037`).
- ✅ Métadonnée `fractionable` disponible et consommée dans les garde-fous live d’entrée.
- ✅ Helper commun de quantité.

## Critères d’acceptation
- Le code compile toujours.
- Les snapshots et lectures DB restituent `0.5`, `0.125`, `3.654` sans troncature.
- Le mode entier historique reste inchangé si `allow_fractional_shares=false`.

## Verdict Sprint 1
- Sprint 1 est **clôturé**.
- Le reste du chantier se déplace maintenant vers le **backtest fractionnaire (Sprint 3)** et la suite live.

## Risques traités
- Propagation d’un type int caché dans plusieurs couches.

---

# Sprint 2 — Risk management fractionnaire complet

## Objectif
Permettre au moteur de sizing et contraintes de produire/propager des quantités fractionnaires.

## État au 2026-06-09
Sprint 2 est **implémenté** sur le périmètre risk applicatif, derrière un feature flag `allow_fractional_shares` conservant le comportement entier historique par défaut.

## Travaux

### 1. Sizer
Statut : **✅ fait**

Fichier modifié :
- `risk_management/position_sizer.py`

Réalisé :
- comportement entier historique conservé si `allow_fractional_shares=false` ;
- calcul float + normalisation 9 décimales si `allow_fractional_shares=true` ;
- rejet basé sur epsilon / quantité nulle au lieu d’un `shares < 1` forcé.

### 2. Contraintes
Statut : **✅ fait**

Fichiers modifiés :
- `risk_management/constraints.py`
- `risk_management/risk_checker.py`

Réalisé :
- suppression des troncatures `int(... // price)` dans les caps ;
- divisions flottantes et normalisation des quantités ;
- conservation du motif de réduction pour l’audit ;
- logs risk en format décimal.

### 3. Builder portefeuille
Statut : **✅ fait**

Fichier modifié :
- `risk_management/portfolio_builder.py`

Réalisé :
- suppression des casts entiers sur `approved` ;
- comparaison avec epsilon ;
- `Decision.ACCEPTED` / `REDUCED` maintenant cohérents pour des floats.

### 4. CLI / exports risk
Statut : **✅ fait sur `cli.py` ; `audit.py` était déjà float-safe**

Fichiers impactés :
- `risk_management/cli.py`
- `risk_management/audit.py`

Réalisé :
- les exports/shadow compare ne recastent plus les shares en entier ;
- les rangs restent entiers ;
- les synthèses conservent les quantités décimales.

## Livrables
- ✅ Risk pipeline fractionnaire derrière feature flag.
- ✅ Exports / shadow compare cohérents.

## Critères d’acceptation
- ✅ Un petit compte peut maintenant produire `0.5` share au lieu d’un rejet automatique.
- ✅ Les contraintes réduisent proprement `0.83` à `0.5` sur cap positionnel.
- ✅ Les décisions / exports risk ne perdent plus la précision décimale.

## Risques traités
- “Support fractionnaire” apparent, mais détruit avant l’exécution.

## Suite logique
- prochain vrai blocage : **Sprint 3 — backtest fractionnaire natif** ;
- puis **Sprint 4 — live fractional entry** sur un périmètre broker explicitement borné.

---

# Sprint 3 — Backtest fractionnaire natif

Statut : **✅ fait**

## Objectif
Rendre le backtest réellement capable de simuler des positions fractionnaires.

## Travaux

### 1. Position ouverte et clôture
Modifier :
- `backtesting/simulator.py`

Réalisé :
- `_OpenPosition.quantity` est désormais en `float`.
- les sizing `affordable / budget / gross exposure` n’utilisent plus de divisions entières bloquantes.
- la normalisation passe par `normalize_share_quantity()` avec respect du flag `allow_fractional_shares`.
- le mode historique entier reste conservé si `allow_fractional_shares=false`.
- recalcul cohérent de :
  - quantité achetable,
  - cap de gross exposure,
  - coût d’entrée,
  - proceeds de sortie,
  - PnL,
  - holdings / journaux.

### 2. Signal overrides / replay
Modifier :
- `_resolve_signal_quantity_override()` dans `backtesting/simulator.py`
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`

Réalisé :
- `_resolve_signal_quantity_override()` retourne maintenant un `float | None` normalisé.
- les bridges risk/exécution/replay ne tronquent plus `approved_shares` / `target_shares` en entier.
- les fills synthétiques partiels de `execution_replay.py` restent fractionnaires au lieu d’imposer des paliers entiers.

### 3. Reporting / fidélité
Modifier :
- `backtesting/fidelity.py`
- `backtesting/report.py`

Réalisé :
- `backtesting/fidelity.py` utilise désormais `_safe_float` / `normalize_share_quantity()` pour les quantités.
- les compare/parity frames ne perdent plus les décimales sur `approved_shares`.
- les conversions entières restent limitées aux compteurs / rangs.

### 4. Compatibilité historique
- ✅ mode “entier” implicite conservé si `allow_fractional_shares=false`.

## Livrables
- ✅ Simulateur backtest fractionnaire.
- ✅ Replay d’exécution compatible.
- ✅ Reporting fidèle aux décimales.

## Critères d’acceptation
- ✅ Un run backtest peut ouvrir/fermer des quantités fractionnaires (tests ajoutés sur `0.5` et replay synthétique fractionnaire ; pipeline prêt pour `0.25` / `1.75`).
- ✅ Les PnL, frais et slippage restent cohérents.
- ✅ Aucune troncature silencieuse dans les bridges / compare frames / sorties backtest concernées.

## Risques traités
- ✅ Backtest faux-ami : sizing float mais exécution simulée en int.

## Validation exécutée

Commandes exécutées :

```powershell
python -m pytest tests/test_backtesting_fractional.py -q -o addopts=""
python -m pytest tests/test_backtesting.py -q -o addopts="" -k "uses_integer_share_sizes or execution_replay_mode_uses_signal_share_override or enforces_max_gross_exposure_from_risk_config"
python -m pytest tests/test_phase2_risk_bridge_regime.py -q -o addopts=""
python -m pytest tests/test_execution_replay_parity.py -q -o addopts=""
python -m pytest tests/test_capital_preset_risk_overrides.py -q -o addopts=""
```

Résultat :
- **32 tests passés** sur le périmètre Sprint 3 + une correction de preset liée au flag fractionnaire.

---

# Sprint 4 — Live Alpaca MVP : fractional entry fiable

## Objectif
Livrer un **MVP live/paper** robuste sur les **entrées fractionnaires**.

## Travaux

### 1. Branchement du flag
Modifier :
- `execution_engine/config.py`
- points d’entrée runtime qui chargent cette config

Actions :
- activer le comportement fractionnaire seulement si le flag est vrai.
- ajouter éventuellement un sous-flag plus explicite si utile :
  - `allow_fractional_live_entries`
  - `allow_fractional_live_protections`

### 2. Snapshot et bridge exécution
Modifier :
- `execution_engine/db_io.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`

Actions :
- supprimer les casts `int(...)` sur `target_shares`.
- garantir la propagation décimale jusque dans `OrderIntent.qty`.

### 3. Validation broker/asset
Modifier :
- logique de sélection avant soumission live
- `database/assets.py` + consommateurs de `stock_metadata`

Actions :
- si `qty` fractionnaire et asset `fractionable != true` => rejet explicite côté app.
- si stratégie cherche à shorter une quantité fractionnaire => rejet explicite.
- journaliser la raison métier avant appel broker.

### 4. Payloads Alpaca
Modifier :
- `execution_engine/order_intents.py`

Actions :
- centraliser le formatage `qty`.
- borner la précision à 9 décimales.
- conserver le format entier sans décimales si la valeur est entière.
- ne pas introduire `notional` en MVP sauf besoin métier réel.

## Livrables
- Fractional buy live/paper sur les entrées.
- Garde-fous sur assets non fractionables.
- Logs et audits lisibles.

## Critères d’acceptation
- Un ordre d’entrée `buy qty=0.5` part en paper/live si asset fractionable.
- Un ordre non fractionable est bloqué avant broker avec message clair.
- Les fills et positions restituent bien des quantités décimales.

## Implémentation réalisée — 2026-06-09

Réalisé :
- `execution_engine/config.py`
  - ajout d’un sous-flag explicite `allow_fractional_live_protections` ;
  - ajout des propriétés runtime `fractional_live_entries_enabled` et `fractional_live_protections_enabled` pour clarifier le périmètre MVP.
- `execution_engine/order_intents.py`
  - blocage explicite des quantités fractionnaires si `allow_fractional_shares=False` (`reason=fractional_shares_disabled`) ;
  - rejet explicite d’un target short/sell fractionnaire (`reason=fractional_short_not_supported`) ;
  - conservation du garde-fou asset `fractionable=true` avant broker (`reason=asset_not_fractionable`).
- `execution_engine/children_submission.py`
  - borne MVP claire : une entrée fractionnaire live/paper est autorisée, mais les **protections fractionnaires broker-side** restent désactivées par défaut ;
  - en mode entry-only, les enfants fractionnaires sont journalisés puis différés proprement sans appel broker ;
  - rebalance/reconcile préparés à des quantités décimales côté logs et seuils de traitement.
- `execution_engine/executor.py`
  - suppression d’une troncature `int(...)` sur `ReconcileDiff.target_qty` afin de préserver les quantités fractionnaires jusque dans l’auto-rebalance.
- validation sans changement fonctionnel complémentaire de :
  - `execution_engine/db_io.py` (lecture snapshot / mapping `fractionable` déjà en `float` / `bool`) ;
  - `database/assets.py` (colonne `fractionable` déjà consommable côté application) ;
  - `execution_engine/order_intents.py` (payload Alpaca déjà centralisé via `format_share_quantity()`, validé par tests).

## Tests exécutés

```powershell
python -m pytest -q -o addopts="" tests/test_order_intents.py tests/test_executor.py tests/test_execution_engine_executor.py
```

Résultat :
- **67 tests passés** sur le périmètre Sprint 4.

## Risques traités
- Rejets Alpaca évitables.
- Déploiement trop ambitieux incluant les protections dès le premier lot live.

---

# Sprint 5 — Live fractional protections : décision produit puis implémentation ciblée

## Objectif
Traiter correctement le sujet le plus risqué : **protection des positions fractionnaires live**.

## Point dur à résoudre
Le projet actuel repose sur :
- `GTC`
- `OCO`
- `trailing_stop`
- logique watcher/protection swing

alors que la documentation fractional consultée n’apporte pas la même surface de support.

## Travaux

### Option A — support broker natif confirmé
Si le spike Sprint 0 confirme une capacité broker suffisante pour certains cas :
- adapter `execution_engine/order_intents.py`
- adapter `execution_engine/children_submission.py`
- adapter `execution_engine/protection_watcher.py`

Actions :
- séparer la logique de TIF et type d’ordre selon :
  - entier vs fractionnaire,
  - entry vs protection,
  - paper vs live.
- ne plus forcer `gtc` sur les protections fractionnaires si non supporté.

### Option B — support broker insuffisant (scénario probable)
Mettre en place une politique explicite :
- **fractional live autorisé pour les entrées**,
- protections server-side limitées ou désactivées pour les positions fractionnaires,
- surveillance applicative/watcher renforcée,
- ou restriction du fractional live à certains profils non overnight.

### Option C — mode produit dédié
Créer un mode :
- `fractional_live_mode = entry_only | intraday_only | full_if_supported`

Recommandation : **c’est la meilleure option produit** si les tests broker ne garantissent pas un swing overnight sûr.

## Livrables
- Politique live fractional explicite.
- Implémentation conforme aux capacités réelles Alpaca.
- Documentation opérateur.

## Critères d’acceptation
- Il n’existe plus de chemin où une position fractionnaire est envoyée avec une protection non supportée “par accident”.
- Les cas non supportés sont refusés explicitement.
- L’équipe sait précisément ce qui est garanti et ce qui ne l’est pas.

## Implémentation réalisée — 2026-06-09

Choix retenu : **Option C**.

Politique produit désormais codée :
- `fractional_live_mode = entry_only | intraday_only | full_if_supported`
- défaut sûr : `entry_only`
- compatibilité conservée avec le flag Sprint 4 `allow_fractional_live_protections=True` via une résolution implicite vers `full_if_supported`

Réalisé :
- `execution_engine/config.py`
  - ajout de `fractional_live_mode` ;
  - centralisation de la politique runtime :
    - `resolved_fractional_live_mode`
    - `can_submit_fractional_protection_orders(...)`
    - `resolve_fractional_protection_time_in_force(...)`
- `execution_engine/order_intents.py`
  - séparation du `time_in_force` selon le mode produit ;
  - protections fractionnaires en `intraday_only` => payloads `DAY` ;
  - protections fractionnaires en `entry_only` => erreur explicite si un payload broker est demandé malgré le garde-fou.
- `execution_engine/broker_adapter.py`
  - les soumissions réelles broker consomment maintenant la config Sprint 5 lors de la construction des payloads standards et OCO.
- `execution_engine/children_submission.py`
  - les enfants fractionnaires respectent désormais la politique produit :
    - `entry_only` => différés explicitement ;
    - `intraday_only` => autorisés seulement dans un contexte intraday compatible ;
    - `full_if_supported` => comportement broker-side complet conservé.
- `execution_engine/protection_watcher.py`
  - armement de protections manquantes et promotion stop->trailing alignés sur le mode produit ;
  - aucun armement/transition fractionnaire n’est tenté “par accident” hors politique autorisée ;
  - ajout d’une métrique explicite `fractional_policy_blocked_items`.

Conséquence produit :
- `entry_only` est maintenant un vrai mode explicite, pas seulement un effet de bord d’un flag ;
- `intraday_only` permet des protections fractionnaires **DAY** pour des profils non overnight ;
- `full_if_supported` reste un opt-in explicite pour les cas où le support broker est jugé suffisant.

## Tests exécutés

```powershell
python -m pytest -q -o addopts="" tests/test_order_intents.py tests/test_executor.py tests/test_protection_watcher.py
python -m pytest -q -o addopts="" tests/test_execution_engine_executor.py tests/test_broker_snapshot_hardening.py
```

Résultats :
- **79 tests passés** sur le périmètre Sprint 5 ciblé
- **23 tests passés** en régression complémentaire executor/broker
- **102 tests passés** au total sur le scope validé

## Risques traités
- Faux sentiment de protection sur les positions fractionnaires overnight.

---

# Sprint 6 — Réconciliation, migration, non-régression et rollout

## Objectif
Stabiliser la production, fiabiliser la data et ouvrir progressivement le feature flag.

## Travaux

### 1. Réconciliation
Modifier :
- `execution_engine/models.py`
- `execution_engine/children_submission.py`
- autres modules de rebalance/reconcile

Actions :
- supprimer les hypothèses `qty < 1 => ignore` si elles bloquent un rebalance réel.
- revoir les messages de log formatés avec `:.0f` pour les quantités.
- ajuster tolérances de comparaison avec epsilon configurable.

### 2. Migration des données et compatibilité historique
- migration de colonnes en DB.
- stratégie de lecture des anciennes lignes entières.
- tests de rétrocompatibilité.

### 3. Tests
Créer/adapter :
- tests unitaires risk
- tests backtest
- tests d’intégration exécution
- tests DB IO
- tests de formatting payload Alpaca

### 4. Rollout progressif
- activer d’abord en **paper**,
- puis en **live limité** sur quelques symbols fractionables,
- puis élargir.

## Livrables
- Suite de tests complète.
- Guide de mise en production.
- Dashboard / métriques de surveillance.

## Critères d’acceptation
- Aucun écart silencieux entre target, intent, fill, position et reconcile.
- Les runs historiques entiers continuent de fonctionner.
- Le flag peut être activé progressivement sans migration manuelle dangereuse.

## Implémentation réalisée — 2026-06-09

Réalisé :
- `execution_engine/config.py`
  - `reconcile_tolerance_shares` migré en `float` ;
  - ajout de `reconcile_tolerance_epsilon` ;
  - ajout de `effective_reconcile_tolerance_shares` pour borner la tolérance runtime par un epsilon configurable.
- `execution_engine/reconciliation.py`
  - toutes les quantités de réconciliation passent maintenant par une normalisation float-safe ;
  - les comparaisons utilisent une tolérance effective basée sur `QUANTITY_EPSILON` ;
  - suppression de la projection legacy `int(result.target_qty)` dans `reconcile_targets_vs_broker()`.
- `execution_engine/executor.py`
  - l’executor transmet désormais la tolérance effective de réconciliation au moteur de reconcile.
- `execution_engine/children_submission.py`
  - suppression des derniers logs `%.0f` / `:.0f` qui masquaient les quantités fractionnaires sur les cas `investigate`.
- `execution_engine/db_io.py`
  - validation de la persistance / relecture des `ExecutionReconciliationResult` fractionnaires sans troncature via tests dédiés ;
  - aucune migration de schéma supplémentaire n’a été requise sur ce sprint car les colonnes SQL concernées étaient déjà en `DOUBLE`.

Conséquence technique :
- plus d’hypothèse implicite “quantité entière” dans la réconciliation live ;
- un diff `0.5 -> 0.25` reste exploitable jusqu’au rebalance ;
- les audits et logs d’investigation restent lisibles sur des quantités décimales.

## Tests exécutés

```powershell
python -m pytest -q -o addopts="" tests/test_execution_engine_reconciliation.py tests/test_execution_db_io.py tests/test_executor.py
python -m pytest -q -o addopts="" tests/test_execution_engine_executor.py tests/test_order_intents.py tests/test_backtesting_fractional.py
```

Résultats :
- **74 tests passés** sur le périmètre Sprint 6 ciblé
- **48 tests passés** en régression complémentaire
- **122 tests passés** au total sur le scope validé

---

## 6. Priorisation recommandée

## MVP recommandé
1. **Sprint 0** — cadrage + spike broker
2. **Sprint 1** — fondations type/db/asset metadata
3. **Sprint 2** — risk fractionnaire
4. **Sprint 3** — backtest fractionnaire
5. **Sprint 4** — live fractional entry

=> À ce stade, on livre déjà une valeur forte :
- backtest crédible,
- sizing réel sur petits comptes,
- entrée live/paper fractionnaire.

## Lot 2
6. **Sprint 5** — protections live fractionnaires
7. **Sprint 6** — stabilisation / rollout

=> Ce lot dépend de la réalité broker/documentation et ne doit pas être fusionné trop tôt au MVP.

---

## 7. Matrice d’impacts par domaine

| Domaine | État actuel | Impact pour fractionnel | Priorité |
|---|---|---:|---:|
| Payload Alpaca entrée | plutôt prêt | faible | haute |
| Modèles risk | déjà migré en `float` | faible/résiduel | moyenne |
| Sizing ATR | bloquant | fort | critique |
| Contraintes portefeuille | bloquant | fort | critique |
| Backtest simulateur | bloquant | fort | critique |
| DB snapshots exécution | déjà migré en `float` | faible/résiduel | moyenne |
| Assets metadata `fractionable` | schéma + persistance en place, branchement runtime à finir | moyen | haute |
| Protections live swing | incertain / risqué | très fort | critique |
| Reporting / fidelity | troncature | moyen | haute |
| Réconciliation / rebalance | partiellement entier | moyen | haute |

---

## 8. Tests à prévoir absolument

## Unitaires
- sizing ATR avec `qty < 1`
- réduction par caps portefeuille/secteur/gross exposure en float
- normalisation / arrondi à 9 décimales
- formatage `qty` pour payload broker

## Intégration risk/backtest
- portfolio cible avec `approved_shares=0.37`
- simulateur avec entrée/sortie fractionnaire
- PnL avec frais/slippage fractionnaires

## Intégration live/paper
- entrée buy market `0.5`
- entrée buy limit `0.125`
- asset non fractionable rejeté localement
- position/fill/reconcile avec `0.333333333`

## Régression entier historique
- un run ancien en parts entières donne les mêmes ordres qu’avant
- aucun diff inattendu si `allow_fractional_shares=false`

---

## 9. Recommandation finale

## Recommandation produit/technique
Oui, il faut faire cette évolution, mais en **2 étages** :

### Étape A — à faire maintenant
- **fractional backtest**
- **fractional risk sizing**
- **fractional live entry Alpaca**

### Étape B — à traiter séparément
- **fractional live protections swing / overnight**

Parce que :
1. le code interne est surtout bloqué par des hypothèses entières qu’on peut lever proprement,
2. la doc Alpaca rend plausible l’entrée fractionnaire,
3. mais les **protections live actuelles** du projet (GTC/OCO/trailing) ne sont pas alignées, à ce stade, avec la surface fractional documentée.

## Conclusion opérationnelle
Le chemin le plus sûr est donc :
- **MVP par étapes**,
- **feature flag**,
- **paper d’abord**,
- **pas de promesse de swing fractional protégé overnight avant validation broker explicite**.

---

## 10. Liste courte des fichiers les plus critiques à modifier le moment venu

### Critiques immédiats
- `risk_management/models.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/risk_checker.py`
- `risk_management/portfolio_builder.py`
- `backtesting/simulator.py`
- `execution_engine/models.py`
- `execution_engine/db_io.py`
- `database/assets.py`
- `execution_engine/order_intents.py`

### Critiques second rideau
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/fidelity.py`
- `execution_engine/children_submission.py`
- `execution_engine/protection_watcher.py`
- `tests/test_execution_db_io.py`
- migrations Alembic liées aux snapshots/targets

---

## 11. Découpage conseillé des PR

- **PR1** : types + helpers + schéma DB
- **PR2** : risk management fractionnaire
- **PR3** : backtest fractionnaire
- **PR4** : asset metadata `fractionable` + validation live entry
- **PR5** : live fractional entry Alpaca
- **PR6** : protections live fractionnaires / ou restriction produit explicite
- **PR7** : hardening, metrics, rollout

---

## 12. Verdict

### Faisabilité
- **Backtest** : faisable, effort significatif mais maîtrisable.
- **Live Alpaca entry** : faisable rapidement.
- **Live Alpaca protection swing fractionnaire** : faisable seulement après validation broker précise ; sinon il faut une limitation produit explicite.

### Niveau de risque
- **Technique interne** : moyen.
- **Risque broker/documentation** : élevé sur les protections.
- **Risque métier si on mélange tout dans un seul sprint** : très élevé.

### Recommandation de pilotage
Lancer le chantier en **MVP 5 sprints**, puis traiter les protections live en **lot dédié**.

