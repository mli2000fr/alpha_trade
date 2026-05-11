# PROMPT D’EXÉCUTION — IMPLÉMENTATION COMPLÈTE DU PLAN `prompt/parttern/plan.md`

## Rôle
Tu es un **ingénieur logiciel senior spécialisé en Python, trading algorithmique, backtesting, risk management et intégration broker**. Tu interviens directement dans ce dépôt pour **implémenter réellement** les évolutions décrites dans le plan consolidé.

## Mission
Ta mission est de **mettre en œuvre dans le code** l’ensemble des points décrits dans :

- `prompt/parttern/plan.md` **(source de vérité principale)**
- `todo/todo_quantitatif.md`
- `todo/todo_Pattern.md`
- `todo/todo_Market-Makers.md`
- `todo/todo_pattern_smart_risk_ts.md`

Le plan consolidé `prompt/parttern/plan.md` a déjà fusionné tous les besoins. Tu dois donc :

1. **lire ce plan intégralement** ;
2. **retrouver les modules réellement présents dans le dépôt** ;
3. **implémenter tous les objectifs fonctionnels sans omission** ;
4. **tester et valider** les changements ;
5. **laisser le dépôt dans un état cohérent et exécutable**.

---

## Instruction essentielle sur la liberté d’implémentation

Le plan `prompt/parttern/plan.md` fournit la trajectoire recommandée, **mais il n’est pas prescriptif au caractère près**.

### Règle importante
Si, en lisant le code du dépôt, tu identifies une **implémentation plus cohérente, plus robuste, plus idiomatique, mieux intégrée à l’architecture existante ou plus simple à maintenir**, **tu es autorisé à prendre cette décision et à implémenter de ta propre façon**.

### En revanche
Cette liberté n’est acceptable que si :

- **tous les objectifs fonctionnels du plan sont bien couverts** ;
- la solution reste **compatible avec l’architecture réelle du dépôt** ;
- la solution maintient la **parité live / backtest** quand elle est possible ou exigée ;
- la solution reste **compatible EODHD + Alpaca** ;
- la solution **n’ajoute pas de latence inutile** au pipeline temps réel ;
- tu documentes clairement dans ton compte-rendu final les **écarts volontaires** entre le plan et l’implémentation retenue, avec leur justification.

En résumé :

> **Le plan est obligatoire sur le fond, mais tu peux adapter la forme de l’implémentation si tu trouves mieux dans le codebase.**

---

## Exigence absolue : couverture exhaustive
Tu dois couvrir **tous les points fonctionnels** décrits dans `prompt/parttern/plan.md`, notamment ceux de la matrice de couverture `C01` à `C32`.

Tu n’as pas le droit de traiter seulement une partie du sujet.

Si certains points se recouvrent, tu peux mutualiser l’implémentation, mais **aucun besoin métier ne doit être oublié**.

---

## Contraintes de réalisation à respecter

### 1. Parité Live / Backtest
Toute nouvelle logique métier importante doit être pensée pour fonctionner à la fois dans :

- le flux live / paper (`run_execution.py`, `execution_engine/`, `risk_management/`),
- le flux backtest (`backtesting/`).

### 2. Compatibilité fournisseurs et broker
- **EODHD** reste la source primaire historique OHLCV.
- **Alpaca** reste la couche broker / ordres / positions / exécution.
- Toute nouvelle logique doit rester compatible avec ces deux composants.

### 3. Performance temps réel
- éviter les requêtes répétitives inutiles ;
- privilégier les données déjà historisées ou cachées ;
- calculer le contexte de régime marché **une fois par cycle**, pas par ordre ;
- ne pas introduire de ralentissement évitable dans le chemin critique d’exécution.

### 4. Configuration centralisée
Tous les nouveaux seuils et comportements doivent être **pilotables depuis `config.yaml`** ou un mécanisme déjà cohérent avec le dépôt.

### 5. Rétrocompatibilité
- les nouveaux comportements doivent être activables / désactivables ;
- les chemins existants ne doivent pas être cassés inutilement ;
- si une migration progressive est préférable, fais-la.

---

## Lecture préalable obligatoire
Avant toute modification, tu dois lire au minimum :

### Documents
- `prompt/parttern/plan.md`
- `doc/DOC_FONCTIONNELLE.md`
- `doc/DOC_TECHNIQUE.md`
- `doc/corporate_actions.md`
- tout autre document de `doc/` utile pour comprendre les modules réellement impactés

### Configuration
- `config.yaml`

### Code à inspecter en priorité
- `run_execution.py`
- `risk_management/config.py`
- `risk_management/position_sizer.py`
- `risk_management/constraints.py`
- `risk_management/portfolio_builder.py`
- `risk_management/cli.py`
- `backtesting/cli/_impl.py`
- `backtesting/simulator.py`
- `backtesting/risk_bridge.py`
- `backtesting/risk_overlay.py`
- `execution_engine/config.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/orphan_adoption.py`
- `execution_engine/broker_adapter.py`
- `selector/` si nécessaire
- `event_sentiment/` si nécessaire
- `tests/` pour identifier les patterns de validation existants

### Références opérationnelles utiles
- `todo/pattern/pattern_1.md`
- les logs et artefacts du dossier `todo/pattern/` si nécessaires pour reproduire les cas observés

---

## Résultat attendu
Tu dois **modifier réellement le dépôt** pour implémenter les besoins suivants, conformément à `prompt/parttern/plan.md`.

## Axes de travail obligatoires

### Axe A — Couche centralisée de régime marché / market-aware
Mettre en place une couche centralisée de type `regime_manager` ou toute alternative **plus cohérente** si le dépôt suggère un meilleur point d’intégration.

Cette couche doit couvrir au minimum :

- Tax Day
- Sept. Slump / September Dip
- Santa Claus Rally
- January Effect
- OpEx
- Month-End / Smart Money hardening
- VIX élevé / capital preservation
- hausse rapide du 10Y yield
- circuit breaker sentiment
- contrainte de petit capital / slots disponibles
- earnings shield / earnings scoring penalty
- buyback blackout si la donnée est exploitable de manière cohérente

### Axe B — Adaptation du risk management au régime et au petit capital
Implémenter une logique qui couvre notamment :

- `risk_multiplier` injecté dans le sizing ;
- recalcul dynamique de `max_positions` ;
- `allowed_slots = floor(equity / min_notional_effectif)` ;
- suppression des cas menant à des ordres impossibles de type `Notional insuffisant < 150$` ;
- max 2 tickers par secteur ;
- réduction du risque en mode défensif ;
- prise en compte du circuit breaker sentiment.

### Axe C — Intégration live / exécution
Au démarrage du flux d’exécution, intégrer un pré-flight ou résumé de contexte marché incluant au minimum :

- mode marché ;
- multiplicateur de risque ;
- `effective_max_positions` ;
- `min_notional` effectif ;
- patterns actifs ;
- secteurs blacklistés ;
- raison éventuelle du blocage des nouvelles entrées.

La logique doit permettre les modes :

- `close_only`
- `cash_only`
- `capital_preservation`

ou leurs équivalents les plus cohérents avec l’architecture réelle.

### Axe D — Intégration backtesting / phase 2 `risk_execution`
Faire en sorte que le backtesting rejoue de façon cohérente les décisions de régime et les contraintes de capital, en particulier dans :

- `phase2_mode: risk_execution`
- simulateur principal
- overlays / diagnostics
- reporting de validation

### Axe E — Earnings / corporate actions / event shielding
Implémenter une logique de protection autour des earnings qui couvre :

- fenêtre J-2 / J+2 ;
- blocage strict ou score négatif forcé selon la configuration ;
- intégration cohérente avec les données déjà disponibles dans le dépôt ;
- réutilisation de la chaîne `sync_earnings_calendar` si c’est le point d’entrée le plus propre.

### Axe F — Trailing stop ATR dynamique + sync externe
Faire évoluer la gestion des achats hors application / positions orphelines pour couvrir :

- stop dynamique ATR(14) × multiplicateur ;
- fallback stop fixe si ATR indisponible ;
- adoption/synchronisation broker ;
- break-even automatique si le profit latent dépasse `2 × ATR` ;
- contrôle de fin de journée vers 15h50 EST si cohérent avec l’architecture existante.

---

## Adaptation intelligente au code réel
Tu ne dois **pas forcer** l’architecture recommandée par le plan si le dépôt montre un point d’extension plus naturel.

### Exemples d’adaptation acceptée
- si `service/market/regime_manager.py` n’est pas le meilleur emplacement, tu peux créer un autre module mieux intégré ;
- si une logique existe déjà dans `risk_management/`, `execution_engine/` ou `backtesting/`, tu peux l’étendre plutôt que créer un nouveau système parallèle ;
- si un module mentionné dans le plan n’existe pas, adapte la solution au module équivalent réellement présent ;
- si certaines données macro ne sont pas encore branchées, tu peux implémenter un fallback neutre et un contrat d’extension propre.

### Exemples d’adaptation non acceptée
- ignorer un besoin métier ;
- repousser sans justification un point exigé ;
- casser la parité live/backtest sans raison solide ;
- introduire un design plus confus qu’avant.

---

## Configuration attendue
Ajouter ou faire évoluer la configuration nécessaire dans `config.yaml` pour couvrir proprement :

- `market_regimes`
- `risk_management.trailing_stop`
- éventuellement `execution`
- tout autre bloc si tu juges qu’une organisation différente est plus cohérente

Si tu modifies la structure proposée dans `prompt/parttern/plan.md`, tu peux le faire, mais :

- garde la configuration lisible ;
- documente le mapping entre le plan et la structure réellement implémentée.

---

## Tests et validation : obligation stricte
Tu dois **tester toi-même** ce que tu implémentes.

### Minimum attendu
1. exécuter les tests unitaires/integration existants pertinents ;
2. ajouter les tests manquants pour les nouvelles règles métier ;
3. vérifier explicitement les cas suivants :
   - Tax Day
   - sentiment breaker
   - yield filter
   - earnings shield
   - recalcul dynamique des slots / `max_positions`
   - suppression des ordres sous 150–155 USD
   - backtesting `phase2_mode=risk_execution`
   - stop ATR dynamique sur position orpheline
   - break-even automatique

### Validation attendue sur les scénarios de backtest
Tu dois, autant que possible, prévoir ou exécuter des scénarios qui valident :

- printemps 2025 baseline vs market-aware ;
- Tax Day isolé ;
- yield shock ;
- collapse sentiment ;
- earnings season ;
- Santa Rally / January Effect ;
- petit capital 2 000 USD ;
- achat manuel hors application.

Si certains scénarios ne peuvent pas être exécutés intégralement dans le contexte disponible, tu dois :

- implémenter les hooks nécessaires ;
- ajouter les tests les plus proches possibles ;
- expliquer précisément ce qui a été validé et ce qui reste dépendant des données/disponibilités externes.

---

## Qualité de rendu attendue
À la fin, tu dois fournir un compte-rendu structuré qui contient au minimum :

1. **Résumé des changements** ;
2. **Liste des fichiers créés / modifiés** ;
3. **Correspondance avec les objectifs du plan** ;
4. **Écarts volontaires par rapport au plan**, avec justification ;
5. **Tests exécutés** ;
6. **Résultats des validations** ;
7. **Points restant éventuellement dépendants des providers / données**.

---

## Directive finale
Tu dois agir comme un **agent autonome d’implémentation** :

- tu explores le dépôt ;
- tu lis les docs utiles ;
- tu prends les bonnes décisions techniques ;
- tu adaptes le plan si nécessaire ;
- tu implémentes proprement ;
- tu testes ;
- tu termines seulement quand l’ensemble est cohérent.

## Rappel final très important
Tu peux **adapter les détails d’implémentation** si tu trouves une meilleure approche dans le dépôt, **mais tu ne peux oublier aucun objectif fonctionnel** décrit dans `prompt/parttern/plan.md`.
A la fin, mettre à jour les documentations impactées, notamment `DOC_FONCTIONNELLE.md` et `DOC_TECHNIQUE.md`, pour refléter les changements réels.

## Créer un fichier `prompt/parttern/prompt_implemented.md` , mettre à jour ce fichier à chaque étape (n'attendez pas à la fin pour la mise à jour car si jamais on s'arret, on sait où on était), et le considérer comme la source de vérité finale de ce qui a été implémenté.
