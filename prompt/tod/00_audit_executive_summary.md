# 00 — Synthèse exécutive de l'audit Alpha Trade

## 1. Contexte et périmètre

Alpha Trade est une plateforme Python orientée **swing trade actions US** couvrant
la chaîne complète : ingestion OHLCV/quotes/news → screener/selector → sentiment
& ML → risk management → exécution Alpaca paper/live → corporate actions →
backtesting → IHM Streamlit de supervision. La cible déclarée par le prompt
d'audit est un niveau **quasi-institutionnel** pour usage swing US réel.

Audit réalisé conformément à `prompt/demande_audit.md`, en lecture seule sur le
code applicatif, avec mise à jour documentaire prévue séparément.

## 2. Verdict global

| Indicateur | Valeur |
|---|---|
| Note globale | **6.4 / 10** |
| Positionnement | **Application indépendante avancée** — au-dessus du niveau amateur sérieux, en deçà du niveau buy-side professionnel |
| Verdict | **solide / quasi-pro partiel** |
| Prêt pour live trading discipliné ? | **Non, pas en l'état.** Prêt après exécution des Sprints S1→S3 (correctifs P0/P1, alignement provider EODHD, cohérence corporate actions). |
| Anomalies P0 | **3** |
| Anomalies P1 | **8** |
| Anomalies P2 | **12** |
| Anomalies P3 | **9** |

## 3. Forces structurelles

- **Couverture fonctionnelle complète** d'une chaîne swing : screener → selector
  multi-facteurs (Minervini/VCP, RS, ATR, beta, market cap, spread, blackout
  earnings) → risk avec ATR sizing strict + circuit breaker drawdown/daily-loss
  → exécution Synthetic Bracket avec OCO logique et watcher post-run.
- **Architecture modulaire propre** : séparation `service/` (providers) / `core/`
  (interfaces) / `database/` / modules métier ; `core.filter_profiles`
  désormais source de vérité unique pour les profils stricts swing
  (`core/filter_profiles.py:239`).
- **Idempotence et audit trail soignés** : `corporate_actions` avec
  `idempotency_key` scopée par compte, `execution_engine` avec snapshot des
  targets / requests / broker_orders / fills / lots / reconciliation.
- **Multi-comptes Alpaca** correctement modélisé (paper/live, `account_id`
  propagé sur les tables critiques — voir `README.md` §12).
- **Capital presets structurés** par 6 tranches d'equity, cohérents sur la
  progression (concentration sectorielle, spread, market cap, taille de book).
- **Bonne base de tests** (~190 fichiers de tests) avec couverture explicite des
  zones sensibles : sizing, contraintes, circuit breaker, executor, EODHD
  switch, profils stricts, idempotence CA.
- **Sécurité opérateur renforcée** récemment : ressaisie label compte live,
  rejet sentinelles `pass`/`user`/`changeme`, suppression du fallback equity
  100 000 $.

## 4. Faiblesses majeures

### 4.1 Convention OHLCV / provider primaire — **incohérences doc/code/config**

- `config.yaml:51` impose `bars_provider: eodhd` mais `config.yaml:55` déclare
  `eodhd.enabled: false`. La clé `eodhd.enabled` n'est **jamais lue par le code
  applicatif** (seul mention en docstring `service/eodhd/__init__.py:21`) → c'est
  un **paramètre fantôme** trompeur (P2).
- `corporate_actions/engine.py:36` (docstring `CorporateActionEngine`) affirme
  `« Les barres OHLCV sont ingérées avec Alpaca adjustment="all" »`. Or :
  - `dataIntegrityEngine/import_alpaca_bar.py:36` : `DATA_ADJUSTMENT = "split"`
  - `service/eodhd/adapters.py:262` : `data_adjustment = DATA_ADJUSTMENT_SPLIT`
  - `README.md:9` : convention canonique projet `data_adjustment='split'`
  → la docstring est **fausse** et **dangereuse** : un futur intervenant peut
  croire qu'aucun ajustement de prix CA n'est nécessaire alors que la convention
  est split-only avec dividendes en `portfolio_cash_ledger` (P0).
- `doc/dataIntegrityEngine.md` (bandeau lignes 3-22) et `doc/data_lineage_matrix.md`
  (lignes 27-31) décrivent **Alpaca IEX comme producteur primaire** des barres
  alors que le code et `config.yaml` ont bascué sur EODHD bulk EOD → écart doc
  ↔ code (P1).
- `README.md:142` instruit l'opérateur de lancer `python -m
  dataIntegrityEngine.import_alpaca_bar`. Quand `bars_provider == 'eodhd'`,
  cette commande devient un no-op (cf. `import_alpaca_bar.py:572`
  `_resolve_target_bars_provider`) → risque opérationnel : l'opérateur croit
  que ses barres sont ingérées alors que rien ne l'est (P1).

### 4.2 Cohérence IHM ↔ backend ↔ pipeline

- L'ordre de pipeline affiché dans `README.md` (sections 6) ne mentionne pas
  l'étape `import_eodhd_bar` alors que c'est l'étape réellement exécutée par
  l'IHM via `ihm/services/pipeline_runner.py` quand le provider est EODHD
  (P1).
- La page **Backtesting** lance désormais `diagnose-screener` /
  `recommend-screener` (cf. `README.md:390`) ; il n'existe pas de garde-fou
  documenté empêchant une concurrence avec un run pipeline en cours.

### 4.3 Risk / sizing / circuit breaker

- `position_sizer.py` est **strict ATR-only** (rejet sec si ATR absent ou
  notional < `min_position_notional`). C'est prudent mais **limite fortement
  l'investissabilité du préset 0–5 000 $** : avec 100 $ de risk budget et un
  notional minimum 150 $, peu de candidats passeront ; il manque une
  télémétrie « rejets pour notional » dans le `run_summary` du risk pour
  détecter cette friction (P2).
- `circuit_breaker.py` mesure le drawdown sur un `PnLSnapshot` injecté
  manuellement ; aucune source automatisée n'est branchée par défaut (le
  `risk_runs` lit un equity injecté en CLI via `--account-equity`). Risque
  d'être inactif en pratique si les snapshots ne sont pas alimentés (P1).
- Aucun preset de capital n'override `risk.max_drawdown` / `risk.max_daily_loss`
  de `config.yaml:39` (15 % / 5 %) ; ces seuils, agressifs pour un petit
  compte cash, devraient être adaptés par tranche (P2).

### 4.4 Documentation

- Doublon `doc/backetesting.md` vs `doc/backtesting.md` (faute de frappe non
  corrigée — P3, mais signal de dette doc).
- `doc/dataIntegrityEngine.md`, `doc/data_lineage_matrix.md`,
  `doc/corporate_actions.md` à réaligner avec la convention EODHD primaire +
  split-only.
- `doc/DOC_FONCTIONNELLE.md` et `doc/DOC_TECHNIQUE.md` à relire pour le même
  point.

### 4.5 Backtesting

- Le module `backtesting/` est riche (replay execution lifecycle, exit
  lifecycle, signal replay, walk forward, statistical validation), mais il
  faut vérifier explicitement que la **convention split-only + ledger
  dividendes** est appliquée pour la performance totale (cf. README:15-16
  `MTM(positions, stock_bars_daily.close) + cumulative(portfolio_cash_ledger)`).
  Si le backtest n'ajoute pas le ledger dividendes, la performance est
  sous-estimée vs live → biais de comparaison (P1, à confirmer dans
  `backtesting/analytics.py`).

### 4.6 Sécurité / readiness

- `config.yaml:10-11` contient encore les valeurs littérales `"PK..."` /
  `"..."` pour la section `alpaca:` rétrocompat ; ce n'est pas un secret réel
  mais c'est un anti-pattern. Le multi-comptes (`accounts:`) utilise bien des
  placeholders `${VAR}` (P3).
- Les check d'environnement dans `run_execution.py:60-62` n'incluent **pas**
  `ALPACA_<ID>_*` quand l'opérateur sélectionne un compte non-default ; risque
  d'erreur tardive (P2).

## 5. Adéquation swing trading par tranche de capital (résumé)

| Tranche | Verdict | Risque principal |
|---|---|---|
| 0 → 5 000 $ | **Fragile mais cohérent** | Faible investissabilité (ATR strict + min_notional) |
| 5 001 → 10 000 $ | **Cohérent mais perfectible** | Marge de manœuvre limitée, RS 97 très exigeant |
| 10 001 → 25 000 $ | **Cohérent** | Compte cash sans PDT → liquidité settled à surveiller |
| 25 001 → 50 000 $ | **Cohérent** | Bascule margin pertinente, réaliste |
| 50 001 → 100 000 $ | **Cohérent** | Preset standard, équilibré |
| 100 001 $+ | **Cohérent mais perfectible** | `selector_min_weekly_trend_score=1.0` peut vider l'univers |

Détail dans `04_parametrage_review.md` et `07_swing_trade_fitness_assessment.md`.

## 6. Top recommandations (Sprints S1→S3 prioritaires)

| Sprint | Objectif clé | Anomalies traitées |
|---|---|---|
| **S1 — Quick wins doc & config** (1 sem.) | Aligner README + `doc/` sur EODHD primaire ; corriger docstring `corporate_actions/engine.py:36` ; supprimer/clarifier `eodhd.enabled` ; corriger doublon `doc/backetesting.md` | A-001, A-002, A-003, A-004, A-005, A-022 |
| **S2 — Cohérence pipeline et IHM** (1 sem.) | Documenter et tester l'ordre réel `import_eodhd_bar` quand `bars_provider=eodhd` ; garde-fou pipeline vs backtest concurrent ; assert env multi-comptes avant lancement live | A-006, A-007, A-008, A-014 |
| **S3 — Risk/CA/backtest robustesse live** (2 sem.) | Brancher `PnLSnapshot` réel sur le circuit breaker ; vérifier intégration ledger dividendes dans backtesting analytics ; télémétrie rejets sizing notional ; assert convention split-only en runtime | A-009, A-010, A-011, A-012 |

Voir `08_sprint_plan.md` pour les sprints complets (S1 à S9) et le volet tests
détaillé.

## 7. Conclusion

Alpha Trade est une plateforme **bien architecturée, riche fonctionnellement et
sérieusement testée** sur ses zones critiques (sizing, executor, idempotence
CA, EODHD switch). Sa progression vers un niveau pro est handicapée
principalement par :

1. des **incohérences documentaires et de configuration** sur le provider
   OHLCV primaire et la convention CA (forte odeur de refactor en cours non
   terminé) ;
2. des **garde-fous opérationnels manquants** entre IHM et backend
   (commandes obsolètes dans le runbook, env multi-comptes non vérifié) ;
3. un **risk management dont les hooks (PnL réel, télémétrie sizing) sont
   incomplets** par défaut ;
4. une **dette documentaire** modérée mais persistante.

Aucun de ces points n'est rédhibitoire ; tous sont adressables en 4 à 6
semaines avec le plan de sprints proposé. **À l'issue du Sprint S3 inclus,
l'application atteint un niveau d'exploitation discipliné suffisant pour un
swing trade réel sur petit compte ; le niveau pro-grade complet exige les
sprints S4 à S9.**

