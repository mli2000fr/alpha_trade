# 03 — Registre d'anomalies

> Sévérité : **P0** = bloquant production / risque immédiat ; **P1** = critique
> à corriger sous 1-2 sprints ; **P2** = important, dette technique ou
> opérationnelle ; **P3** = mineur / documentation / cosmétique.
>
> Toute anomalie **P0/P1** dispose d'un bloc test précis associé.

---

## ANOMALIES P0 — Bloquantes / risque immédiat

### A-001 — Docstring `corporate_actions/engine.py` contredit la convention projet

- **Sévérité** : **P0**
- **Domaine** : `corporate_actions/`, doc inline
- **Description** : la docstring de `CorporateActionEngine`
  (`corporate_actions/engine.py:34-39`) affirme : « Les barres OHLCV sont
  ingérées avec Alpaca adjustment="all". Les prix historiques sont DÉJÀ
  ajustés pour splits et dividendes. Ce module NE TOUCHE PAS aux tables
  stock_bars / stock_bars_daily. ». **C'est faux.** Le code réel est
  `data_adjustment='split'` (split-only) côté Alpaca
  (`dataIntegrityEngine/import_alpaca_bar.py:36`) ET côté EODHD
  (`service/eodhd/adapters.py:262`), avec dividendes comptabilisés
  séparément via `portfolio_cash_ledger` (cf. README.md:9-16). La docstring
  reflète une ancienne convention abandonnée.
- **Preuve** : `corporate_actions/engine.py:34-39` vs
  `dataIntegrityEngine/import_alpaca_bar.py:36`,
  `service/eodhd/adapters.py:262`, `README.md:9-16`.
- **Impact métier** : un nouvel intervenant lisant la docstring peut conclure
  à tort qu'il n'y a aucun ajustement à faire et **désactiver le ledger
  dividendes**, faussant la performance totale et la comptabilité fiscale.
- **Impact technique** : perte de cohérence sémantique du module qui justement
  *gère* les dividendes — la docstring s'auto-contredit (le module
  manipule `portfolio_cash_ledger` quelques lignes plus bas).
- **Probabilité d'incident** : **élevée** (la doc est lue dès qu'on touche au
  module).
- **Confiance** : **très élevée**.
- **Recommandation** : réécrire la docstring pour refléter la convention
  réelle (`data_adjustment='split'` + dividendes via ledger), citer la
  contrainte SQL `chk_bars_adj`. Sprint S1.
- **Test associé** : voir bloc ci-dessous.

> **Bloc test A-001**
> - **Objectif** : geler la convention projet `data_adjustment='split'` à
>   plusieurs niveaux (constante module + enregistrements DB + docstring).
> - **Type** : test unitaire + test de non-régression statique (lecture
>   docstring).
> - **Priorité** : P0.
> - **Modules** : `corporate_actions/`, `dataIntegrityEngine/`, `service/eodhd/`.
> - **Fichiers probables** : `tests/test_data_adjustment_convention.py`
>   (à créer), extension `tests/test_corporate_actions_engine.py`.
> - **Scénario Given/When/Then** :
>   - *Given* : code courant.
>   - *When* : on importe `dataIntegrityEngine.import_alpaca_bar.DATA_ADJUSTMENT`,
>     `service.eodhd.adapters.DATA_ADJUSTMENT_SPLIT`, et on parse la
>     docstring de `CorporateActionEngine` via `inspect.getdoc()`.
>   - *Then* : tous valent / mentionnent `'split'` ; la docstring **ne doit
>     pas** contenir la chaîne `adjustment="all"`.
> - **Fixtures/mocks** : aucune (test statique).
> - **Oracle** : assertion d'égalité de chaînes + `not in`.
> - **Régression empêchée** : régression de la docstring vers une ancienne
>   convention `'all'` ou désalignement Alpaca/EODHD sur l'adjustment.
> - **Si test partiel existe** : étendre `tests/test_eodhd_split_only.py`
>   (qui vérifie déjà `data_adjustment == "split"` en sortie d'adapter).

---

### A-002 — Configuration `eodhd.enabled: false` ignorée par le code

- **Sévérité** : **P0** (incohérence config qui ment activement à l'opérateur)
- **Domaine** : `config.yaml`, `service/eodhd/`, `dataIntegrityEngine/`
- **Description** : `config.yaml:55` déclare `eodhd.enabled: false`. Pourtant
  `config.yaml:51` impose `bars_provider: eodhd` et le code applicatif
  ingère effectivement EODHD via `import_eodhd_bar.py`. La clé
  `eodhd.enabled` n'est lue nulle part dans le code (recherche `grep_search`
  sur `eodhd.enabled` retourne **uniquement** la docstring de
  `service/eodhd/__init__.py:21`). C'est un **paramètre fantôme**.
- **Preuve** : `config.yaml:55`, `grep_search('eodhd.enabled')` → 1 résultat
  documentaire seulement, lecture de `import_eodhd_bar.py:151-154` (lit
  `market_data.bars_provider`, jamais `eodhd.enabled`).
- **Impact métier** : un opérateur prudent met `eodhd.enabled: false` croyant
  désactiver EODHD ; rien ne se passe ; ses ordres sont quand même générés
  sur des barres EODHD.
- **Impact technique** : drift config silencieux ; impossibilité de
  désactiver le provider sans changer `bars_provider`.
- **Probabilité d'incident** : **moyenne-élevée**.
- **Confiance** : **très élevée**.
- **Recommandation** : soit (a) supprimer la clé `eodhd.enabled` et la
  documenter comme non utilisée, soit (b) l'implémenter (court-circuit dans
  `import_eodhd_bar.resolve_bars_provider`). Recommandation : (a) +
  validation Pydantic du `config.yaml`.
- **Test associé** :

> **Bloc test A-002**
> - **Objectif** : empêcher la résurrection d'un paramètre fantôme.
> - **Type** : test unitaire de configuration.
> - **Priorité** : P0.
> - **Modules** : `common.config_loader`, `service/eodhd/`.
> - **Fichier probable** : `tests/test_config_yaml_schema.py` (à créer).
> - **Scénario** :
>   - *Given* : un schéma Pydantic listant les clés autorisées de `config.yaml`.
>   - *When* : on charge `config.yaml`.
>   - *Then* : aucune clé orpheline ; `eodhd.enabled` doit être soit
>     **absent** soit **effectivement consommé** (vérifier par grep ou par
>     branchement explicite).
> - **Fixtures** : copie temporaire de `config.yaml` pour modification.
> - **Oracle** : `ValidationError` si clé non reconnue.
> - **Régression empêchée** : ajout silencieux de clés non lues.

---

### A-003 — Ordre de pipeline obsolète dans `README.md` et `doc/`

- **Sévérité** : **P0** (risque opérationnel : le runbook conduit l'opérateur à
  une situation no-op)
- **Domaine** : doc + IHM
- **Description** : `README.md:142` instruit l'étape 1 du pipeline quotidien
  comme `python -m dataIntegrityEngine.import_alpaca_bar`. Quand
  `bars_provider == 'eodhd'` (cas par défaut actuel `config.yaml:51`), cette
  commande est **no-op** : `import_alpaca_bar.py:572`
  `_resolve_target_bars_provider` lit la config et retourne `eodhd` →
  l'import Alpaca s'arrête. L'opérateur croit avoir importé des barres mais
  rien n'a été écrit ; il faut lancer `import_eodhd_bar`. La doc et la table
  `data_lineage_matrix.md` listent EODHD seulement comme « Phase 6 », pas
  comme primaire.
- **Preuve** : `README.md:140-186`, `dataIntegrityEngine/import_alpaca_bar.py:572`
  (à confirmer ligne exacte mais résultat `grep_search` confirme la
  présence), `config.yaml:51`, `doc/data_lineage_matrix.md:27-31`,
  `doc/dataIntegrityEngine.md:3-22`.
- **Impact métier** : run quotidien apparemment réussi mais pas de nouvelles
  barres → screener/selector tournent sur données rassies → décisions
  trading sur historique périmé.
- **Impact technique** : zéro alerte ; la commande retourne exit code 0.
- **Probabilité** : **certaine** si un opérateur suit le README à la lettre.
- **Confiance** : **très élevée**.
- **Recommandation** : (1) réécrire `README.md` §6 pour expliquer
  conditionnellement l'étape selon `bars_provider` ; (2) lever un
  warning **fort** dans `import_alpaca_bar` si exit no-op ; (3) mettre à
  jour `doc/dataIntegrityEngine.md` (bandeau IEX) et
  `doc/data_lineage_matrix.md` ; (4) ajouter un test IHM qui vérifie que la
  page Pipeline route vers `import_eodhd_bar` quand `bars_provider=eodhd`.
- **Test associé** :

> **Bloc test A-003**
> - **Objectif** : verrouiller la cohérence runbook / IHM / code selon
>   `bars_provider`.
> - **Type** : intégration + non-régression IHM (au moins jusqu'au choix de
>   commande).
> - **Priorité** : P0.
> - **Modules** : `dataIntegrityEngine/`, `ihm/services/pipeline_runner.py`.
> - **Fichiers probables** : extension de
>   `tests/test_ihm_eodhd_provider_switch.py`, ajout de
>   `tests/test_import_alpaca_bar_noop.py`.
> - **Scénario** :
>   - *Given* : `config.yaml` avec `market_data.bars_provider = 'eodhd'`.
>   - *When* : on appelle `import_alpaca_bar.main()`.
>   - *Then* : exit code 0, **stdout/log contient un WARNING explicite**
>     `'no-op (bars_provider=eodhd)'`, et `_emit_run_summary` doit avoir un
>     champ `skipped_reason='wrong_provider'`.
> - **Fixtures** : monkey-patch `load_config`.
> - **Oracle** : présence du warning + champ `skipped_reason`.
> - **Régression empêchée** : retour à un no-op silencieux.

---

## ANOMALIES P1 — Critiques à corriger rapidement

### A-004 — `doc/dataIntegrityEngine.md` bandeau IEX non actualisé

- **Sévérité** : **P1**
- **Description** : le bandeau lignes 3-22 et le tableau d'impact IEX (volume
  sous-évalué x30-50, vwap, etc.) **présupposent que toutes les barres viennent
  d'Alpaca IEX** alors que `bars_provider=eodhd`. Le bandeau devient au mieux
  obsolète, au pire trompeur (l'opérateur croit avoir un volume biaisé alors
  qu'il a un volume EODHD ~consolidé).
- **Preuve** : `doc/dataIntegrityEngine.md:3-22` vs `config.yaml:51`.
- **Impact** : décisions de seuils (spread, market cap) prises sur de mauvais
  postulats.
- **Recommandation** : ajouter un bandeau « provider primaire actuel : EODHD ;
  bandeau IEX hérité conservé pour le mode rétrocompat alpaca ». Sprint S1.
- **Test associé** :

> **Bloc test A-004**
> - **Type** : test documentaire (parsing markdown) + lien vers config.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_doc_provider_alignment.py` (à créer).
> - **Scénario** : *Given* `config.yaml.bars_provider == 'eodhd'`. *When* on
>   parse `doc/dataIntegrityEngine.md`. *Then* la doc doit contenir un tag
>   marker `<!-- primary_provider: eodhd -->` (ou équivalent) cohérent.
> - **Oracle** : présence du marqueur.
> - **Régression empêchée** : doc qui dérive de la config.

---

### A-005 — `doc/data_lineage_matrix.md` cite Alpaca IEX comme producteur des bars daily

- **Sévérité** : **P1**
- **Description** : lignes 27-31 désignent `Alpaca IEX` comme source upstream
  primaire ; EODHD apparaît seulement comme « Phase 6 ».
- **Preuve** : `doc/data_lineage_matrix.md:27-31`.
- **Impact** : matrice lineage trompeuse pour audit data ; complique le
  diagnostic d'incident provider.
- **Recommandation** : ajouter colonne `provider_actif` ou marquer EODHD
  comme principal et Alpaca comme rétrocompat.
- **Test associé** : couvert par le test A-004 (parsing doc).

---

### A-006 — Convention CA / ledger dividendes non vérifiée par le backtesting

- **Sévérité** : **P1**
- **Domaine** : `backtesting/`
- **Description** : la convention canonique
  `MTM(stock_bars_daily.close) + cumulative(portfolio_cash_ledger)`
  (`README.md:15-16`) doit être appliquée par le backtest pour la performance
  totale. Aucune vérification automatisée n'a été trouvée dans le scan rapide
  du module `backtesting/`. Si l'analytics ne charge pas le ledger
  dividendes, le backtest **sous-estime** les rendements et fausse la parité
  backtest↔live.
- **Preuve** : `README.md:15-16`, absence visible d'un test
  `tests/test_backtest_total_return_with_dividends.py`.
- **Impact** : KPIs walk-forward et calibrations biaisés ; faux sentiment de
  robustesse.
- **Recommandation** : assertion d'intégration ledger dans `backtesting/analytics.py`
  + test dédié.
- **Test associé** :

> **Bloc test A-006**
> - **Objectif** : prouver que le rendement total backtest inclut bien les
>   dividendes du `portfolio_cash_ledger`.
> - **Type** : test d'intégration backtesting.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_backtest_total_return_with_dividends.py`.
> - **Scénario** : *Given* un mini-univers fixture avec un dividende cash de
>   10 $ sur AAPL. *When* on lance `backtesting/analytics.py` sur la
>   période. *Then* `total_return_with_dividends` ≈ `mtm_return +
>   dividend_yield`.
> - **Fixtures** : DB SQLite/in-memory peuplée avec quelques bars, une
>   position AAPL, un événement CA dividende dans `portfolio_cash_ledger`.
> - **Oracle** : différence `total_return - mtm_return` ≈ dividende.
> - **Régression empêchée** : oubli silencieux du ledger dans les analytics.

---

### A-007 — `circuit_breaker` non branché par défaut sur PnL réel

- **Sévérité** : **P1**
- **Description** : `risk_management/circuit_breaker.py:23-25`
  `CircuitBreaker.__init__` prend un `PnLSnapshot` optionnel ; si non
  fourni, toutes les checks `_check_drawdown` et `_check_daily_loss` retournent
  `False` (les valeurs `None` court-circuitent). Aucun branchement automatisé
  n'a été trouvé dans `run_risk.py` (à confirmer en lecture intégrale, mais
  l'absence de tests `test_circuit_breaker_real_pnl` est un signal).
- **Preuve** : `risk_management/circuit_breaker.py:36-58`.
- **Impact** : circuit breaker silencieusement inactif ⇒ aucune protection
  effective drawdown / daily loss.
- **Recommandation** : alimenter `PnLSnapshot` depuis
  `broker_positions_snapshots` + `execution_runs` historique au démarrage de
  `run_risk` ; logguer un WARNING si snapshot vide.
- **Test associé** :

> **Bloc test A-007**
> - **Objectif** : prouver que le circuit breaker reçoit un PnL non vide en
>   exécution nominale.
> - **Type** : intégration risk_management.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_run_risk_circuit_breaker_wired.py`.
> - **Scénario** : *Given* DB peuplée d'un snapshot positions et d'un
>   `execution_runs` historique avec `pnl_today`. *When* on appelle
>   `run_risk.main([...])`. *Then* le `CircuitBreaker` instancié doit avoir
>   `_pnl.portfolio_current_value is not None` et `daily_pnl is not None`.
> - **Fixtures** : DB éphémère + monkeypatch `CircuitBreaker.__init__`.
> - **Oracle** : valeurs non `None`.
> - **Régression empêchée** : retour silencieux à un breaker inactif.

---

### A-008 — Check env `run_execution.py` ne couvre pas les comptes multi-broker

- **Sévérité** : **P1**
- **Description** : `run_execution.py:60-62` vérifie uniquement
  `LOGIN_DB`, `PASSWORD_DB`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`. Quand
  l'opérateur lance `python run_execution.py live --account live1`, les
  variables `ALPACA_LIVE1_API_KEY` / `ALPACA_LIVE1_SECRET_KEY` ne sont pas
  contrôlées. L'erreur survient tardivement à la première requête broker
  (ou pire : retombe sur `default` si la résolution multi-comptes le permet).
- **Preuve** : `run_execution.py:60-62` + résolution multi-comptes
  `README.md:483-487`.
- **Impact** : risque d'envoi d'ordres sur le mauvais compte si fallback
  silencieux.
- **Recommandation** : factoriser un check env contextuel par `--account`,
  refuser le démarrage si les credentials du compte demandé manquent.
- **Test associé** :

> **Bloc test A-008**
> - **Type** : intégration CLI.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_run_execution_check_env_per_account.py`.
> - **Scénario** : *Given* aucune variable `ALPACA_LIVE1_*` dans l'env.
>   *When* on lance `run_execution.py live --account live1`. *Then* exit
>   code ≠ 0, message d'erreur explicite « variables ALPACA_LIVE1_* manquantes ».
> - **Fixtures** : `monkeypatch.delenv` ; capture stdout/stderr.
> - **Oracle** : code sortie + chaîne d'erreur.
> - **Régression empêchée** : check env oublieux du contexte multi-comptes.

---

### A-009 — `selector_min_weekly_trend_score=1.0` peut vider l'univers (presets ≥ 50k$)

- **Sévérité** : **P1**
- **Description** : presets `capital_50001_100000` (`config/capital_presets.yaml:222`)
  et `capital_100001_plus` (ligne 268) imposent
  `selector_min_weekly_trend_score: 1.0`. Or `weekly_trend_score` est borné
  dans [0, 1] (cf. validation `core/filter_profiles.py:67-68` `not 0 <=
  ... <= 1`). Imposer un seuil **strict-égal au max** filtre tous les
  candidats sauf cas extrêmes — risque d'univers vide.
- **Preuve** : `config/capital_presets.yaml:222,268`, validation
  `core/filter_profiles.py:67-68`.
- **Impact** : pipeline générant 0 candidat → aucun ordre → friction
  opérateur. À confirmer empiriquement (peut être intentionnel pour ne
  garder que les leaders parfaits, mais risqué).
- **Recommandation** : revoir à 0.9 ou ajouter un assouplissement automatique
  si univers < N candidats.
- **Test associé** :

> **Bloc test A-009**
> - **Type** : intégration selector.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_capital_preset_universe_yield.py`.
> - **Scénario** : sur un échantillon synthétique de 200 symboles
>   représentatifs (distribution `weekly_trend_score` réaliste), pour chaque
>   préset, l'univers final doit compter ≥ 5 candidats.
> - **Oracle** : `len(candidates) >= 5`.
> - **Régression empêchée** : durcissement aveugle des seuils selector.

---

### A-010 — Préset 0–5 000 $ : sizing ATR strict + min_notional 150 $ → quasi non-investissable

- **Sévérité** : **P1**
- **Description** : `risk_per_trade_pct=0.02` × 5 000 $ = 100 $ de risk
  budget. Avec ATR 1.5 % sur un titre à 50 $, `risk_per_share ≈ 0.75 $` →
  shares ≈ 133 → notional ≈ 6 650 $ qui dépasse toute contrainte ; mais sur
  un titre à 200 $ avec ATR 5 %, `risk_per_share ≈ 10 $` → shares = 10 →
  notional 2 000 $ ≥ 150 $ OK. Cependant le `min_position_notional=150 $`
  combiné à l'ATR strict (rejet sec) fait que les titres très volatils chers
  sont systématiquement rejetés. Pas de télémétrie « rejet pour notional ».
- **Preuve** : `config/capital_presets.yaml:9,13`,
  `risk_management/position_sizer.py:40-49`.
- **Impact** : opérateur petit compte voit 0 ordre sans diagnostic.
- **Recommandation** : (1) télémétrie `rejected_for_notional` dans le
  `run_summary` ; (2) considérer un override `min_notional` plus permissif
  pour le préset 0–5k (ex 100 $).
- **Test associé** :

> **Bloc test A-010**
> - **Type** : unitaire + intégration risk.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_position_sizer_telemetry.py`.
> - **Scénario** : *Given* un univers où 8/10 candidats finissent rejetés
>   pour notional. *When* on lance `run_risk`. *Then* `run_summary['rejected_for_notional']
>   == 8`.
> - **Oracle** : champ présent et valeur exacte.
> - **Régression empêchée** : invisibilité des rejets sizing.

---

### A-011 — `risk.max_drawdown` / `max_daily_loss` non override par préset

- **Sévérité** : **P1**
- **Description** : `config.yaml:39-40` impose 15 % drawdown / 5 % daily loss
  globalement. Aucun préset ne propose d'override. Pour un compte 0–5 000 $
  cash, 5 % de perte journalière = 250 $ — très élevé et asymétrique avec
  les contraintes selector très strictes.
- **Preuve** : `config.yaml:38-40`, `config/capital_presets.yaml` (aucune
  clé `risk_max_drawdown_pct` / `risk_max_daily_loss_pct` dans les `values`).
- **Impact** : politique de risque uniforme inadaptée aux petits comptes.
- **Recommandation** : ajouter `risk_max_drawdown_pct` /
  `risk_max_daily_loss_pct` aux presets (ex. 8 % / 3 % pour 0–5k, 15 % / 5 %
  pour 100k+).
- **Test associé** :

> **Bloc test A-011**
> - **Type** : configuration.
> - **Priorité** : P1.
> - **Fichier** : `tests/test_capital_preset_risk_overrides.py`.
> - **Scénario** : pour chaque préset, `RiskConfig` chargée doit avoir
>   `max_portfolio_drawdown_pct` et `max_daily_loss_pct` cohérents avec la
>   tranche d'equity.
> - **Oracle** : table de valeurs attendues par tranche.

---

## ANOMALIES P2 — Importantes / dette opérationnelle

### A-012 — `doc/backetesting.md` (faute) coexiste avec `doc/backtesting.md`

- **Sévérité** : **P2**
- **Preuve** : `doc/backetesting.md` + `doc/backtesting.md` listés ensemble.
- **Recommandation** : supprimer le doublon ou rediriger.

### A-013 — `config.yaml` contient encore `api_key: "PK..."` / `secret_key: "..."` rétrocompat

- **Sévérité** : **P2**
- **Preuve** : `config.yaml:10-11`.
- **Recommandation** : retirer les valeurs littérales, n'autoriser que les
  placeholders `${VAR}`.

### A-014 — IHM page Backtesting : pas de garde-fou contre concurrence avec un run pipeline

- **Sévérité** : **P2**
- **Preuve** : `README.md:390` mentionne le lancement asynchrone.
- **Recommandation** : verrou IHM par compte.

### A-015 — `selector/alpha_scanner.py` reste 1 421 lignes après extraction Phase 3.3.a

- **Sévérité** : **P2** (dette technique).
- **Recommandation** : finir l'extraction de la classe `AlphaScanner` en
  orchestrateur fin.

### A-016 — `ihm/pages/_execution_center.py` 2 550 lignes (TODO 2e passe documenté)

- **Sévérité** : **P2** (dette technique reconnue).
- **Preuve** : `ihm/pages/_execution_center.py:7-9` (commentaire TODO).
- **Recommandation** : découper `_build_launch_options` par sous-bloc
  thématique.

### A-017 — Lecture des barres ne filtre pas par `data_source`

- **Sévérité** : **P2**
- **Description** : `screener` et `selector` lisent `stock_bars_daily` sans
  filtrer `data_source` ; un mix Alpaca/EODHD pourrait cohabiter
  silencieusement après bascule provider.
- **Recommandation** : ajouter un filtre/log `data_source` à la lecture +
  télémétrie.

### A-018 — Watcher post-run optionnel : oubli probable opérateur

- **Sévérité** : **P2**
- **Preuve** : `README.md:177-179`.
- **Recommandation** : flag `--auto-watcher` lancé automatiquement par
  `run_execution`.

### A-019 — Pas d'autogen `data_lineage_matrix`

- **Sévérité** : **P2**
- **Preuve** : `doc/data_lineage_matrix.md:8-10`.
- **Recommandation** : implémenter `scripts/generate_data_lineage.py`.

### A-020 — `risk.max_drawdown` libellé `max_drawdown` ambigu (cf. config.yaml:39)

- **Sévérité** : **P2** (cosmétique mais source de confusion : c'est un
  pourcentage en absolu).

### A-021 — Pas de seuil drift ML → action automatique documenté

- **Sévérité** : **P2**.
- **Recommandation** : table `ml_drift_runs` exploitée par un policy gate.

### A-022 — `signal_aggregator` peut être lancé séparément, double application sentiment

- **Sévérité** : **P2**
- **Preuve** : `README.md:316`.
- **Recommandation** : flag idempotent + verrou.

### A-023 — Pas de check « provider OHLCV homogène » au démarrage du pipeline

- **Sévérité** : **P2**.
- **Recommandation** : check au démarrage que `% rows par data_source` >=
  seuil pour le provider attendu.

---

## ANOMALIES P3 — Mineures / cosmétiques

### A-024 — Bandeau ASCII `run_execution.py` peut casser sous certains terminaux Windows

### A-025 — Logs FR mélangés EN (`Corporate actions sync started`, `Aucun evenement…`) — cosmétique

### A-026 — `run.py` : pas de `--port` documenté pour Streamlit

### A-027 — Pas de `CHANGELOG.md` à la racine

### A-028 — `pyproject.toml` rapide à enrichir (tags, classifiers)

### A-029 — `.importlinter` présent sans documentation des contracts

### A-030 — README §11 Structure simplifiée omet plusieurs dossiers réels (`alembic/`, `service/`, `corporate_actions/`)

### A-031 — `prompt/` (refactor, audit) : massif et non versionné de manière organisée

### A-032 — `artifacts/` mélange runs, modèles, préférences sans politique de rétention documentée

---

## Synthèse anomalies

| Sévérité | Compte | Liste |
|---|---|---|
| P0 | 3 | A-001, A-002, A-003 |
| P1 | 8 | A-004, A-005, A-006, A-007, A-008, A-009, A-010, A-011 |
| P2 | 12 | A-012 → A-023 |
| P3 | 9 | A-024 → A-032 |
| **Total** | **32** | |

Voir `10_anomaly_test_matrix.md` pour le mapping anomalie → sprint → test.

