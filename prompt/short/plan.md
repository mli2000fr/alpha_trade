# Plan d’intégration du **short** (hors ML)

_Date : 2026-06-13_

## 1. Objet et périmètre

Cette note est basée sur la **lecture du code source** du workspace, pas uniquement sur les conseils externes.

Objectif : préparer un plan de sprint pour faire évoluer l’application d’un mode **long-only** vers un mode **long + short**, en couvrant :

- le **backtest** ;
- le **pipeline live** (risk → targets → execution → protections → réconciliation → reporting) ;
- **sans traiter le ML** pour l’instant.

Hors périmètre immédiat :

- génération ML des signaux short ;
- amélioration des modèles de prédiction ;
- optimisation avancée des frais de borrow avec source broker temps réel.

---

## 2. Conclusion rapide

L’application est aujourd’hui **structurellement long-only**.

Le support du short n’est **pas** un simple ajout de `side="sell"` à l’entrée. Il faut traiter au minimum :

1. la **propagation du sens** (`buy` / `sell`) depuis les candidats jusqu’aux targets ;
2. la **gestion du risque** et des contraintes de portefeuille en exposition brute / nette ;
3. le **moteur de backtest** (cash, PnL, mark-to-market, stops, trailing, replay) ;
4. le **moteur live** (order intents, protections OCO, capacity checks, watcher, réconciliation) ;
5. le **reporting** et les exports ;
6. les **garde-fous broker** (compte margin, shortable, borrow, refus broker).

La bonne nouvelle : certaines briques sont déjà partiellement prêtes :

- `execution_engine.models.ExecutionTarget.side` existe déjà ;
- `execution_engine.models.ExecutionPosition.net_qty` est déjà signé ;
- `execution_engine.reconciliation` est en partie compatible avec des quantités signées ;
- `risk_management.db_io.load_account_equity_breakdown()` sait déjà distinguer long et short côté snapshots broker ;
- l’IHM lit déjà `asset_shortable` dans `ihm/services/alpaca_accounts.py`.

---

## 3. Recommandation d’architecture

### 3.1 Représentation canonique recommandée

Je recommande de **ne pas** encoder le short uniquement via des quantités négatives dans tout le pipeline métier.

### Canonique recommandé

- **Targets / intents / décisions de risque** :
  - `side`: `"buy" | "sell"`
  - `shares` / `qty`: **toujours positives** (quantité absolue)
- **Positions broker / réconciliation / snapshots live** :
  - `net_qty` peut rester **signé** (ce qui est déjà le cas)
- **Backtest interne** :
  - soit un champ `side` + quantité absolue,
  - soit un champ dérivé `direction = +1 / -1` pour les calculs de PnL.

### Pourquoi

- c’est cohérent avec les modèles d’exécution déjà existants (`OrderIntent.side`, `BrokerOrder.side`) ;
- cela évite l’ambiguïté entre **ouvrir un short** et **fermer un long** ;
- cela rend les règles TP/SL/OCO plus lisibles.

### Helpers à introduire

Créer des helpers directionnels centraux du style :

- `is_short_side(side)`
- `closing_side(entry_side)`
- `compute_take_profit_price(entry_side, entry_price, pct, risk_per_share)`
- `compute_initial_stop_price(entry_side, reference_price, ...)`
- `compute_trailing_activation_price(entry_side, fill_price, ...)`
- `compute_realized_pnl(entry_side, qty, entry_price, exit_price, fees)`
- `compute_mark_to_market(entry_side, qty, price)`
- `compute_gross_notional(...)` / `compute_net_exposure(...)`

Sans cette centralisation, le risque de régression long-only sera élevé.

### 3.2 Compatibilité future ML à figer dès maintenant

Même si ce premier plan est **hors ML**, sa mise en œuvre doit être conçue
comme la fondation de la future V2 directionnelle décrite dans
`prompt/short/plan_with_ml.md`.

### Contrats à figer dès V2.1

- **Champ `side` explicite partout** dans les objets métier décrivant une
  décision, une cible, un intent ou une sortie logique.
- **Quantités absolues** sur `shares` / `qty` pour les targets, intents,
  lignes d'audit et exports métier.
- **Positions nettes signées seulement** côté broker / réconciliation /
  snapshots internes (`net_qty`, vues broker, projections de positions).
- **Schémas et payloads extensibles** : prévoir des contrats versionnables pour
  les tables, JSON et artefacts afin de pouvoir brancher plus tard une couche
  ML directionnelle sans casser les lecteurs existants.
- **Feature flags dès le départ** : au minimum un flag global de type
  `short_selling_enabled = false` par défaut, avec capacité d'extension future.
- **Reports et exports capables d'afficher long / short séparément** même si le
  volume short initial est faible.
- **Logique de régime directionnelle ou facilement extensible** : préparer
  l'évolution vers `allow_long_entries` / `allow_short_entries` au lieu de
  figer le système sur un simple booléen global.

### Anti-patterns à éviter dès V2.1

- **Ne pas** coder le short comme « quantité négative partout » dans toutes les
  couches métier.
- **Ne pas** assimiler `short = sell` sans distinguer clairement :
  - ouverture short,
  - clôture de long,
  - réduction partielle,
  - buy-to-cover.
- **Ne pas** laisser des booléens trop rigides du type `allow_new_entries`
  comme seul contrat de régime sans prévoir une autorisation directionnelle.
- **Ne pas** introduire des raccourcis non versionnés dans les schémas ou les
  exports qui obligeraient à refaire la V2.1 au moment d'activer le ML.

---

## 4. Constat détaillé par sous-système

## 4.1 Sélection / risk management : le sens n’existe pas encore

### Fichiers clés

- `risk_management/models.py`
- `risk_management/portfolio_builder.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/audit.py`
- `risk_management/db_io.py`
- `risk_management/cli.py`
- `selector/ranking.py`

### Constats

#### A. Les modèles amont n’ont pas de `side`

- `risk_management.models.CandidateScore` : pas de champ `side`
- `risk_management.models.EnrichedCandidate` : pas de champ `side`
- `risk_management.models.PortfolioEntry` : pas de champ `side`
- `risk_management.models.RiskDecisionRow` : pas de champ `side`
- `risk_management.models.PortfolioTargetRow` : pas de champ `side`

Donc aujourd’hui, le pipeline risque **ne peut pas exprimer** « ce ticker est une entrée short ».

#### B. Le classement actuel du selector est long-only par construction

Dans `selector/ranking.py` :

- `merge_scores()` compose un `final_score` ;
- `rank_and_select()` trie **descendant** sur `final_score` ;
- aucune notion de `side`, de shortlist short, ni de sélection symétrique long/short.

👉 Comme le ML est hors scope pour l’instant, il ne faut **pas** coupler le sprint short à une refonte du ranking ML.
Le pipeline doit plutôt accepter un `side` explicite en entrée, avec défaut `buy`.

#### C. Le sizing ATR rejette implicitement le short

Dans `risk_management/position_sizer.py` :

- `compute()` calcule des `proposed_shares` **positives** ;
- les rejets portent sur `shares < ...`, `shares * price < min_notional`, etc.

Ce fichier n’est pas “cassé” conceptuellement, mais il est construit pour des **quantités d’ouverture longues**.

#### D. Les contraintes portefeuille sont long-only

Dans `risk_management/constraints.py` :

- `_normalize_approved_shares()` retourne `0.0` si `shares <= 0` ;
- `notional = proposed_shares * price` suppose implicitement une quantité positive ;
- `total_notional`, `sector_notional`, `max_position_weight`, `max_sector_weight`, `max_gross_exposure` sont tous pilotés comme si l’exposition était uniquement acheteuse.

👉 Pour le short, il faut distinguer :

- **gross exposure** = somme des expositions absolues ;
- **net exposure** = longs - shorts ;
- exposition sectorielle brute ;
- éventuellement un cap spécifique short.

#### E. Le builder construit un stop initial uniquement sous le prix d’entrée

Dans `risk_management/portfolio_builder.py` :

- `stop_price_initial = last_close - risk_per_share`

C’est correct pour un long, faux pour un short.

#### F. Le writer d’audit ne publie que des lignes `approved_shares > 0`

Dans `risk_management/audit.py` :

- `accepted = [e for e in entries if e.approved_shares > 0]`
- le record persisté n’écrit pas de `side`

👉 Même si on ajoutait du short dans les objets métier, il disparaîtrait à la persistance si on ne corrige pas cette étape.

#### G. Le repository `risk_management` n’écrit pas de colonne `side`

Dans `risk_management/db_io.py` :

- `write_portfolio_targets()` n’insère pas `side` dans `canonical_columns`
- idem côté `risk_decisions`

👉 La persistance risque doit être alignée avec le modèle live.

#### H. Le CLI risque bloque tout quand le régime interdit les nouvelles entrées

Dans `risk_management/cli.py` :

- `regime_allow_new_entries` pilote des sauts entiers de pipeline ;
- en régime bloquant, le chargement ATR/corrélation est marqué `skipped_by_regime`.

👉 Si on veut autoriser le short dans certains régimes défensifs, cette logique doit devenir **side-aware** au lieu d’être un booléen global « nouvelles entrées oui/non ».

---

## 4.2 Backtest : le moteur simule uniquement des longs

### Fichiers clés

- `backtesting/risk_bridge.py`
- `backtesting/simulator.py`
- `backtesting/microstructure.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/exit_lifecycle_replay.py`
- `backtesting/report.py`

### Constats

#### A. Le bridge risk → signals ne transporte pas le `side`

Dans `backtesting/risk_bridge.py` :

- `RISK_SIGNAL_COLUMNS` ne contient pas `side` ;
- `portfolio_entries_to_signals()` ne l’exporte pas ;
- `entry.approved_shares <= 0` est ignoré.

👉 Il faut enrichir le signal replay avec le sens de la position.

#### B. Le bridge risk → execution force `side="buy"`

Dans `backtesting/execution_bridge.py` :

- `portfolio_entries_to_execution_targets()` écrit `side="buy"`

Dans `backtesting/execution_replay.py` :

- `_entry_to_target()` écrit aussi `side="buy"`

👉 Toute la phase “parité backtest ↔ live execution” est actuellement câblée pour des entrées longues.

#### C. Le simulateur maintient des positions sans direction explicite

Dans `backtesting/simulator.py` :

- `_OpenPosition` n’a pas de champ `side` ;
- `peak_high` ne couvre qu’un trailing de long.

Pour le short, il faut au moins un miroir logique :

- `peak_high` pour les longs ;
- `trough_low` / `lowest_low` pour les shorts.

#### D. L’ouverture de position consomme toujours du cash

Dans `backtesting/simulator.py` :

- `entry_cost = quantity * effective_unit_cost`
- rejet si `entry_cost > settled_cash`
- puis `state.settled_cash -= entry_cost`

C’est la logique d’un achat cash. Pour un short, il faut définir clairement le modèle de compte backtest :

- **MVP recommandé** : backtest “margin simplifié” avec contrôle de buying power, pas un simple cash ledger ;
- modèle minimal : dépôt de marge + produit de vente short + réserve de couverture.

#### E. Le mark-to-market et l’exposition brute sont long-only

Dans `backtesting/simulator.py` :

- `current_gross_notional = max(self._mark_to_market(...), 0.0)`
- plusieurs calculs supposent une valeur de position positive.

Pour un short, il faut séparer :

- valeur économique signée ;
- exposition brute absolue ;
- exposition nette ;
- utilisation de marge.

#### F. Les niveaux TP / stop / trailing sont construits pour un long

Dans `backtesting/simulator.py` et `backtesting/microstructure.py` :

- TP = `entry_price * (1 + pct)`
- trailing stop = `peak_high * (1 - pct)`
- initial stop sous le prix d’entrée
- `resolve_intrabar_exit()` teste `day_high >= take_profit_price` et `day_low <= stop_price`

Dans `backtesting/exit_lifecycle_replay.py` :

- commentaire explicite “Garde-fou long-only” ;
- trailing basé sur `peak_high` uniquement.

👉 Il faut une version **symétrique** des résolutions intrabar :

- short TP atteint si `day_low <= take_profit_price` ;
- short stop atteint si `day_high >= stop_price` ;
- trailing short basé sur le **plus bas favorable**, pas le plus haut.

#### G. Le PnL de clôture est long-only

Dans `backtesting/simulator.py` :

- `proceeds = quantity * exit_price * (...)`
- `pnl = proceeds - entry_cost`
- `return_pct = proceeds / entry_cost - 1`

👉 Cette formule est correcte pour un long uniquement.
Pour un short, il faut calculer un PnL directionnel.

#### H. Le reporting backtest reconstruit aussi un PnL long-only

Dans `backtesting/report.py` :

- `estimated_pnl_price_only = (exit - entry) * quantity`
- `entry_cost = quantity * entry_price`
- `proceeds = quantity * exit_price`
- `return_pct = pnl / entry_cost`

👉 Même si le simulateur était corrigé, le reporting resterait faux si on ne l’aligne pas.

---

## 4.3 Pipeline live : l’OMS sait parler `side`, mais la logique métier est encore long-only

### Fichiers clés

- `execution_engine/models.py`
- `execution_engine/order_intents.py`
- `execution_engine/account_state.py`
- `execution_engine/executor.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/orphan_adoption.py`
- `execution_engine/broker_state_sync.py`
- `execution_engine/reconciliation.py`
- `execution_engine/db_io.py`
- `execution_engine/tca.py`
- `execution_engine/market_regime_preflight.py`
- `run_execution.py`

### Constats

#### A. Les modèles d’exécution sont partiellement prêts

Dans `execution_engine/models.py` :

- `ExecutionTarget.side` existe ;
- `OrderIntent.side` existe ;
- `BrokerOrder.side` existe ;
- `ExecutionPosition.net_qty` est signé.

👉 Le socle de données de l’OMS est exploitable.

#### B. Les entry intents ignorent encore tout short

Dans `execution_engine/order_intents.py` :

- `build_entry_intents()` saute les `target_shares <= 0` ;
- `side="buy"` est hardcodé.

👉 Pour un target short, rien n’est soumis aujourd’hui.

#### C. Les protections broker-side sont 100% orientées long

Toujours dans `execution_engine/order_intents.py` :

- `resolve_initial_stop_price()` exige un stop **sous** le prix ;
- `resolve_trailing_activation_price()` déclenche uniquement au-dessus du prix ;
- `build_take_profit_intent()` produit un `sell limit` au-dessus ;
- `build_initial_stop_intent()` produit un `sell stop` ;
- `build_trailing_stop_intent()` produit un `sell trailing_stop` ;
- `build_oco_protection_payload()` force `side="sell"`.

👉 Pour un short :

- TP = **buy limit** plus bas ;
- stop = **buy stop** plus haut ;
- trailing activation et trailing direction inversés ;
- OCO avec `side="buy"`.

#### D. Le contrôle de capacité de compte ne traite que les achats

Dans `execution_engine/account_state.py` :

- `reserve_account_capacity_for_intent()` retourne immédiatement `True` si `intent.side != "buy"`.

👉 Ouvrir un short n’est donc **jamais** contrôlé côté capacité/marge dans le moteur.

Il faut introduire des règles explicites :

- short interdit si `account_type != "margin"` ;
- short interdit si l’asset n’est pas shortable ;
- short bloqué si buying power / marge insuffisants ;
- gestion claire du cas borrow indisponible.

#### E. Le watcher de protections est pensé pour des achats et orphelins buy

Dans `execution_engine/protection_watcher.py` :

- logique spéciale `manual_buy_stop` ;
- sécurité orientée `watcher_orphan_buy_safety_net`.

Dans `execution_engine/orphan_adoption.py` :

- `adopt_orphan_buy()` crée un parent d’entrée buy ;
- `adopt_orphan_sell()` traite un sell comme sortie adoptée, pas comme ouverture short.

👉 Un **sell broker orphelin** peut être soit :

- une clôture de long,
- une vente partielle,
- **une ouverture short**.

Le système actuel ne sait pas distinguer ces cas proprement.

#### F. La reconstruction des lots est long-only

Dans `execution_engine/db_io.py` :

- `rebuild_execution_position_lots()` :
  - un `buy` ouvre un lot,
  - un `sell` ferme des lots existants.

👉 Cela ne sait pas reconstruire des **lots short**.
Il faut une logique miroir :

- `sell` peut ouvrir un lot short,
- `buy` peut le fermer.

Les requêtes de PnL de lots existantes sont aussi long-only (`(exit_price - entry_price) * qty`).

#### G. La réconciliation est seulement partiellement compatible

Dans `execution_engine/reconciliation.py` :

- le calcul de `delta = broker_qty - target_qty` fonctionne en grande partie avec des quantités signées ;
- `action = sell_excess / buy_more` peut rester valide si la sémantique est documentée.

Mais :

- `missing_protection` n’est déclenché que si `broker_qty > tolerance` ;
- donc une position short (`broker_qty < 0`) peut être ouverte **sans protection** sans être détectée.

#### H. Le TCA n’est pas directionnel

Dans `execution_engine/tca.py` :

- `compute_slippage_bps(fill_price, decision_price)` suppose qu’un prix plus élevé est toujours pire ;
- `compute_implementation_shortfall(fill_price, decision_price, qty)` suppose la même direction.

👉 Pour un short, vendre plus haut est meilleur ; acheter pour couvrir plus bas est meilleur.
Il faut intégrer la direction.

---

## 4.4 Régime de marché : gros point de conception produit

### Fichiers clés

- `service/market/models.py`
- `execution_engine/market_regime_preflight.py`
- `run_execution.py`
- `risk_management/cli.py`
- `backtesting/risk_bridge.py`

### Constat

Le régime pilote aujourd’hui surtout la question :

- « autorise-t-on de **nouvelles entrées** ? »

Or avec du short, la bonne question devient :

- « quelles **directions** sont autorisées dans ce régime ? »

### Problème actuel

- `allow_new_entries` est un booléen global ;
- `derive_entry_mode()` mappe `capital_preservation`, `close_only`, `cash_only` vers des modes qui restent sémantiquement défensifs ;
- `backtesting/risk_bridge.py` saute complètement la journée si `snap.allow_new_entries == False`.

### Recommandation produit

Ne pas surcharger silencieusement `cash_only` pour faire du short.

### Proposition plus propre

Introduire une matrice d’autorisation explicite, par exemple :

- `allowed_long_entries: bool`
- `allowed_short_entries: bool`
- `force_close_existing: bool`

### Politique initiale recommandée

- `normal` : long autorisé, short interdit
- `capital_preservation` : long très contraint ou interdit, short autorisé
- `close_only` : ni long ni short, closes uniquement
- `cash_only` : ni long ni short, closes uniquement

Si tu veux absolument shorter aussi en `cash_only`, il vaut mieux créer un mode explicite (`short_only`, `defensive_short`, etc.) plutôt que casser la sémantique historique de `cash_only`.

---

## 4.5 Données broker / contraintes externes encore absentes

### Constats

Je n’ai trouvé **aucun** support backend exploitable pour :

- borrow fees ;
- locate / disponibilité de titres à emprunter ;
- refus “asset not shortable” dans la logique de pré-check ;
- filtre squeeze / crowded short.

Recherche utile trouvée :

- `ihm/services/alpaca_accounts.py` expose `asset_shortable` et `asset_marginable` côté UI.

### Implication

Pour un MVP short robuste, il faudra au minimum :

1. un **pré-check shortable** avant soumission live ;
2. un blocage si `account_type != margin` ;
3. un modèle simple de **borrow fee** côté backtest ;
4. une gestion gracieuse des rejets broker liés au short.

---

## 5. Points déjà prêts ou proches d’être prêts

### Interaction short ↔ levier / marge (mise à jour 2026-06-13)

Depuis l’ajout du **levier optionnel long-only** dans l’exécution, il faut figer
dès maintenant la doctrine suivante pour la future V2 short :

- le levier actuel ne doit **pas** être implicitement réutilisé pour shorter ;
- l’ouverture short devra passer par une logique distincte de **marge / short
  buying power / gross exposure / net exposure** ;
- les contrôles actuels centrés sur `regt_buying_power` / `buying_power`
  restent une bonne base, mais ils devront être étendus avec :
  - validation `asset_shortable`,
  - règles de borrow / locate si disponibles,
  - budget par side,
  - caps d’exposition brute et nette,
  - reporting séparé du levier long et de l’utilisation de marge short.

### Implication de conception

Le contrat levier introduit en V1 doit donc être considéré comme :

- **V1** : levier optionnel **long-only** borné par `config.yaml` ;
- **V2 short** : gestion **directionnelle** de la marge, distincte du simple
  multiplicateur long.

### Implication pour les sprints short

- **Sprint 2 backtest** : le modèle de compte devra intégrer un usage de marge
  compatible long + short, et non seulement des achats cash/margin ;
- **Sprint 3 live** : `execution_engine.account_state.py` devra évoluer d’un
  budget de buying power orienté achat vers une couche de capacité directionnelle
  (`long buying power`, `short capacity`, `gross/net exposure`) ;
- **Sprint 4 reporting** : les rapports devront afficher séparément
  `effective_leverage_long`, exposition short, exposition nette et utilisation
  de marge.

## 5.1 Briques réutilisables

- `ExecutionTarget.side` existe déjà
- `ExecutionPosition.net_qty` signé existe déjà
- `replace_execution_positions()` sait stocker `qty` négatifs s’ils viennent du broker
- la réconciliation par delta signé est partiellement exploitable
- l’équity breakdown live sait déjà séparer long/short

## 5.2 Opportunité

Le socle live n’est pas à refaire entièrement.
Le plus gros travail est :

- la **propagation du side**,
- la **symétrie des protections**,
- la **refonte du moteur de backtest**,
- la **sémantique des régimes**.

---

## 6. Plan de sprint recommandé

Je recommande un découpage en **5 sprints techniques**, avec un **feature flag** global dès le départ :

- `short_selling_enabled = false` par défaut

Ainsi, on préserve le comportement long-only existant tant que la chaîne n’est pas prête de bout en bout.

---

## Sprint 0 — Cadrage technique et contrat de données

### Objectif

Fixer la représentation canonique du short avant d’éditer les moteurs.

### Travaux

- décider formellement :
  - `side` explicite partout en métier,
  - `qty` absolue sur targets/intents,
  - `net_qty` signé uniquement pour positions broker/interne ;
- figer un **contrat extensible** pour les schémas DB / JSON / artefacts afin
  de pouvoir enrichir plus tard la couche ML sans casser la V2.1 ;
- définir la matrice régime ↔ directions autorisées ;
- définir le MVP broker :
  - margin obligatoire,
  - borrow fee simplifié configurable,
  - rejet si asset non shortable ;
- introduire des **feature flags** dès l'amorçage :
  - `short_selling_enabled = false` par défaut,
  - extensible ensuite à des flags plus fins si nécessaire ;
- figer les besoins minimaux de reporting et d'exports séparés long / short.

### Livrables

- ADR / note d’architecture
- liste des champs à ajouter
- décision produit sur les régimes

### Critères de sortie

- plus aucune ambiguïté sur la représentation du short
- accord sur la sémantique de `capital_preservation` / `cash_only`
- compatibilité explicitement garantie avec une future couche ML directionnelle
  sans remise à plat des contrats métier

---

## Sprint 1 — Propagation du `side` dans le pipeline risk

### Objectif

Rendre le pipeline risk capable de produire des targets long **et** short, sans toucher au ML.

### Fichiers à traiter

- `risk_management/models.py`
- `risk_management/portfolio_builder.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/audit.py`
- `risk_management/db_io.py`
- `risk_management/cli.py`
- `backtesting/risk_bridge.py`

### Travaux

- ajouter `side` à :
  - `CandidateScore`
  - `EnrichedCandidate`
  - `PortfolioEntry`
  - `RiskDecisionRow`
  - `PortfolioTargetRow`
- faire remonter `side` jusqu’aux écritures `risk_decisions` / `portfolio_targets`
- garder un défaut rétrocompatible `side="buy"`
- rendre les contraintes de portefeuille side-aware :
  - gross exposure absolue,
  - net exposure,
  - caps sectoriels side-aware si nécessaire
- adapter `risk_bridge` pour exporter `side` dans les signaux de backtest
- remplacer le booléen global `allow_new_entries` par une autorisation directionnelle côté risk
- prévoir dès cette phase des modèles et écritures suffisamment extensibles pour
  qu'un futur ranking ML directionnel puisse fournir un `side` sans rupture de
  contrat

### Critères de sortie

- le risk pipeline peut publier un target short sans le perdre à la persistance
- le long-only historique reste identique quand `side` n’est pas fourni

### Risques

- casser les audits existants si les schémas DB ne sont pas alignés
- régression long-only si les filtres `> 0` restent disséminés

---

## Sprint 2 — Moteur de backtest vraiment bidirectionnel

### Objectif

Faire du backtest un moteur **long/short correct**, pas juste permissif.

### Fichiers à traiter

- `backtesting/simulator.py`
- `backtesting/microstructure.py`
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/exit_lifecycle_replay.py`
- `backtesting/report.py`

### Travaux

- ajouter la direction aux positions ouvertes
- gérer un trailing spécifique short
- corriger :
  - ouverture de position,
  - cash / marge simplifiée,
  - mark-to-market,
  - exposition brute / nette,
  - PnL réalisé et non réalisé,
  - return %,
  - intrabar exit short
- corriger le replay execution/protection pour des parents short
- corriger les exports report / pipeline
- ajouter un coût de borrow simplifié en backtest (paramétrable, même statique au départ)

### Critères de sortie

- un scénario bear 2022 peut générer des performances short plausibles
- un trade short simple (entrée, TP, stop, trailing) est correctement simulé
- le long-only existant reste bit-for-bit stable sur un jeu de non-régression, hors colonnes nouvelles

### Risques

- sous-estimer la complexité du cash/margin model
- produire un PnL “correct” mais une equity curve fausse si le ledger n’est pas cohérent

---

## Sprint 3 — Exécution live / OMS / protections broker-side

### Objectif

Permettre au pipeline live de soumettre, protéger et suivre des shorts.

### Fichiers à traiter

- `execution_engine/order_intents.py`
- `execution_engine/account_state.py`
- `execution_engine/executor.py`
- `execution_engine/broker_adapter.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/orphan_adoption.py`
- `execution_engine/broker_state_sync.py`
- `execution_engine/db_io.py`
- `execution_engine/reconciliation.py`
- `execution_engine/tca.py`
- `run_execution.py`
- éventuellement services broker / métadonnées d’assets

### Travaux

- `build_entry_intents()` doit respecter `target.side`
- générer TP/SL/trailing/OCO directionnels
- refondre les checks de capacité :
  - short interdit hors margin
  - contrôle de buying power / marge
  - contrôle asset shortable
- traiter proprement les rejets broker liés au short
- rendre le watcher compatible avec des parents short
- distinguer en adoption d’orphelins :
  - sell de clôture long
  - sell d’ouverture short
- rendre la reconstruction des lots compatible long/short
- rendre la réconciliation “missing protection” compatible positions short
- rendre le TCA directionnel

### Critères de sortie

- un target short peut produire :
  - 1 ordre d’entrée live/paper,
  - 1 OCO de protection cohérent,
  - 1 réconciliation correcte,
  - 1 position signée cohérente

### Risques

- différences de comportement broker paper/live sur short selling
- cas ambigus d’adoption d’ordres manuels
- conflits OCO si le broker réserve différemment la quantité sur les shorts

---

## Sprint 4 — Reporting, opérations, garde-fous et IHM minimale

### Objectif

Rendre le short observable et opérable.

### Fichiers à traiter

- `backtesting/report.py`
- `backtesting/report_schema.py`
- `execution_engine/db_io.py` (requêtes analytics/lots)
- composants IHM / summaries / exports pertinents
- configuration (`config.yaml`, presets, docs opératoires)

### Travaux

- ajouter `side` dans les exports et rapports
- corriger realized/unrealized PnL de lots
- afficher expositions :
  - gross long
  - gross short
  - net exposure
- exposer les refus short (non-shortable, margin insuffisante, borrow indispo)
- exposer les borrow fees backtest/live quand disponibles
- documenter les runbooks opératoires short

### Critères de sortie

- un opérateur peut comprendre pourquoi un short a été pris, bloqué ou clos
- les rapports distinguent clairement long et short

---

## Sprint 5 — Batterie de tests et validation fonctionnelle

### Objectif

Sécuriser la mise en production.

### Tests à ajouter

#### Unit tests

- propagation de `side` risk → targets → intents
- calcul des stops/TP/trailing long et short
- PnL directionnel
- reserve capacity buy vs short
- TCA directionnel
- réconciliation short avec et sans protection

#### Integration tests

- backtest d’un short isolé
- portefeuille mixte long/short
- replay execution avec parent short
- watcher de protections pour short
- adoption d’orphelin short
- lot rebuilding long/short

#### Non-régression

- tout le parcours long-only historique doit rester valide avec `short_selling_enabled=false`

#### Validation métier

- backtest focalisé 2022
- comparaison avant/après sur 2020, 2021, 2022
- vérifier que 2021 n’est pas dégradé par des shorts intempestifs

### Critères de sortie

- stabilité des tests long-only
- couverture spécifique short sur les points critiques
- feu vert pour activer le feature flag en paper

---

## 7. Ordre de priorité concret

Si l’objectif est d’aller vite sans casser la prod, voici l’ordre optimal :

1. **Propager `side` dans le pipeline risk et les tables**
2. **Corriger le moteur de backtest**
3. **Corriger l’OMS live et les protections**
4. **Traiter réconciliation / lots / orphan adoption**
5. **Finir reporting / IHM / runbooks**

Je déconseille fortement de commencer par l’exécution live avant d’avoir :

- un backtest bidirectionnel fiable,
- une sémantique de régime claire,
- une représentation canonique figée.

---

## 8. Risques majeurs à surveiller

### Risque 1 — Fausse symétrie long/short

Le short n’est pas juste “un long inversé”.
Les plus gros pièges sont :

- TP/SL mal orientés ;
- slippage/TCA mal signés ;
- trailing stop calqué sur `peak_high` ;
- PnL correct par trade mais faux au niveau equity/marge.

### Risque 2 — Régimes ambigus

Le système actuel sait bloquer ou autoriser des entrées, pas autoriser des **directions**.
C’est un point d’architecture, pas un détail de code.

### Risque 3 — Broker paper vs live

Le paper peut accepter des cas que le live refuse sur les shorts.
Il faudra prévoir des garde-fous conservateurs.

### Risque 4 — Adoption / reconciliation ambiguës

Un `sell` broker n’est pas forcément une clôture de long.
Sans classification explicite, l’OMS peut mal reconstruire l’historique.

---

## 9. Recommandation finale

### Recommandation technique

Faire une **V2 short-capable sous feature flag**, sans essayer de patcher le live en direct.

### Recommandation produit

Ne pas faire dépendre l’intégration short du ML.
Le sprint actuel doit uniquement rendre le système **capable de consommer une direction `side`** et de l’exécuter correctement.

### Recommandation de démarrage

Commencer par :

- **Sprint 0 + Sprint 1 + Sprint 2**
- puis faire tourner un backtest ciblé sur **2022**
- et seulement ensuite ouvrir **Sprint 3 live/paper**.

---

## 10. Résumé exécutable en une phrase

Le projet est aujourd’hui long-only dans le risk, le backtest, les protections et une partie de l’OMS ; pour intégrer le short proprement, il faut d’abord **introduire un `side` canonique**, puis rendre **directionnels** le backtest, les protections live, la réconciliation et le reporting, le tout sous **feature flag** avec validation prioritaire sur **2022**.

