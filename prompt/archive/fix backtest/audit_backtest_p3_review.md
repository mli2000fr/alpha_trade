# Revue P3 — backtest et live pipeline

_Date : 2026-06-03_

## Checklist

- [x] Vérifier le point **8. coûts d’exécution réalistes** côté backtest
- [x] Vérifier le point **8. coûts d’exécution réalistes** côté live pipeline
- [x] Vérifier le point **9. corporate actions / ajustements prix** côté backtest
- [x] Vérifier le point **9. corporate actions / ajustements prix** côté live pipeline
- [x] Vérifier le point **10. réconciliation des exports pipeline de trades** côté backtest
- [x] Vérifier le point **10. réconciliation des exports pipeline de trades** côté live pipeline
- [x] Sauvegarder la synthèse dans `audit_backtest_p3_review.md`

---

## Verdict exécutif

| Item P3 | Backtest | Live pipeline | Verdict court |
|---|---|---|---|
| 8. Coûts d’exécution réalistes | **Partiel** | **Partiel** | Les briques existent, mais la fidélité dépend encore beaucoup du paramétrage et il manque une modélisation plus complète des frais/coûts dans certains chemins. |
| 9. Corporate actions / ajustements prix | **Partiel** | **Partiel hors pipeline / absent dans le flux live principal** | La convention de données est claire et le module corporate actions existe, mais l’intégration n’est pas homogène de bout en bout, surtout dans le pipeline live principal et dans le replay backtest. |
| 10. Réconciliation des exports pipeline de trades | **Partiel** | **Partiel** | `trades.csv` a clairement progressé côté backtest, et la réconciliation live existe en base/IHM, mais l’export final n’est pas encore unifié partout. |

---

## 8. Rendre les coûts d’exécution réalistes

## 8.1 Côté backtest — **partiellement implémenté**

### Ce qui est bien en place

1. Le simulateur applique bien des coûts de transaction explicites :
   - `backtesting/simulator.py:47-63` expose `fees_pct`, `commission_bps`, `slippage_bps` et la configuration microstructure.
   - à l’entrée, le coût effectif inclut les frais et le slippage additionnel : `backtesting/simulator.py:831-863`.
   - à la sortie, le produit net retire aussi ces coûts : `backtesting/simulator.py:1140-1144`.

2. Une microstructure plus réaliste existe déjà dans le moteur :
   - `backtesting/microstructure.py:28-58` définit `SlippageConfig` (`fixed`, `linear`, `sqrt`).
   - `backtesting/microstructure.py:88-116` expose `MicrostructureConfig` avec `max_entry_gap_pct`, stop initial et résolution intrabar.

3. Les profils backtest ne sont pas tous à zéro :
   - `backtesting/profiles.py:17-36` met par défaut `commission_bps` et `slippage_bps` à `5.0` selon le profil.

4. Le replay d’exécution produit un TCA exploitable :
   - `backtesting/execution_replay.py:296-328` calcule `slippage_bps` et `implementation_shortfall` par fill synthétique.
   - `backtesting/execution_replay.py:751-768` agrège cela dans `tca_summary`.
   - `execution_engine/tca.py:15-22` centralise les calculs de slippage et d’implementation shortfall.

### Ce qui manque / limite le réalisme

1. Le replay Phase 2 / Phase 3 reste simplifié :
   - `backtesting/execution_bridge.py:84-108` remplit au `target.entry_price`.
   - `backtesting/execution_replay.py:400-427` remplit au `open_df` du jour d’exécution.
   - donc, si les prix de décision et d’exécution coïncident ou si les paramètres de microstructure sont nuls, le TCA peut rester artificiellement trop propre.

2. Les commissions ne sont pas intégrées dans le TCA lui-même :
   - `execution_engine/tca.py:91-107` résume slippage + implementation shortfall, mais pas de champ de commission/broker fee.

3. Le résultat final dépend fortement du paramétrage du run :
   - si `slippage_bps = 0`, `slippage_base_bps = 0`, `slippage_impact_coef = 0` et `max_entry_gap_pct = 0`, le moteur sait être réaliste, mais **le run ne l’est pas**.

### Conclusion backtest

Le point 8 est **implémenté au niveau des briques**, mais **pas garanti dans tous les chemins de replay ni par tous les paramètres de run**. Mon verdict est donc : **partiel**.

---

## 8.2 Côté live pipeline — **partiellement implémenté**

### Ce qui est bien en place

1. Le live utilise de vrais fills broker pour mesurer le coût réel ex post :
   - `execution_engine/executor.py:992-1007` construit un `ExecutionFill` à partir du `BrokerOrder` réel et calcule `slippage_bps` + `implementation_shortfall`.

2. Le pipeline agrège un TCA post-exécution :
   - `execution_engine/executor.py:880-898` construit et publie un résumé TCA.

3. Les presets live ont une tolérance plus stricte que paper/simulate :
   - `run_execution.py:362-384` fixe `max_slippage_bps = 20` en live contre `30` en paper/simulate.

### Ce qui manque / limite le réalisme

1. Je ne vois pas de modélisation explicite de commissions/frais broker dans les objets d’exécution :
   - `execution_engine/broker_adapter.py:223-239` mappe quantité, prix moyen, statut, mais pas de frais.
   - recherche sur `execution_engine/*.py` : pas de champ `commission`, `fee`, `fees` réellement exploité dans le calcul TCA.

2. Il n’existe pas de pré-trade cost model riche côté live principal :
   - le live mesure bien le slippage après coup, mais ne semble pas intégrer un modèle de coûts broker détaillé avant soumission.

### Conclusion live

Côté live, le système est **meilleur que le backtest sur le réalisme des prix d’exécution**, car il repose sur les fills broker réels. En revanche, **la chaîne coûts/frais n’est pas complète**. Verdict : **partiel**.

---

## 9. Unifier les données corporate actions / ajustements prix

## 9.1 Côté backtest — **partiellement implémenté**

### Ce qui est bien en place

1. La convention canonique projet est claire et testée :
   - `corporate_actions/engine.py:34-56` documente la convention : prix stockés en `data_adjustment='split'`, dividendes hors prix via `portfolio_cash_ledger`.
   - `dataIntegrityEngine/import_alpaca_bar.py:36` fixe `DATA_ADJUSTMENT = "split"`.
   - `service/eodhd/adapters.py:38-40` fixe `DATA_ADJUSTMENT_SPLIT = "split"`.
   - `tests/test_data_adjustment_convention.py:21-55` verrouille cette convention.

2. Le module corporate actions est réel et non cosmétique :
   - `corporate_actions/processors.py:22-61` traite les dividendes.
   - `corporate_actions/processors.py:68-138` traite splits / reverse splits.
   - `corporate_actions/reconciliation.py:27-72` compare état interne et broker après corporate actions.

3. Le reporting backtest commence à exposer cette convention :
   - `backtesting/report.py:284-316` ajoute `price_adjustment_convention` dans le résumé d’export de trades.
   - `backtesting/report.py:319-368` charge un résumé des flux `portfolio_cash_ledger`.

### Ce qui manque / limite l’unification

1. Le replay d’exécution backtest n’applique pas le moteur corporate actions aux positions simulées :
   - `backtesting/execution_replay.py:349-840` construit targets/intents/fills/artefacts, mais sans appel au moteur `CorporateActionEngine`.

2. Le backtest s’appuie surtout sur la convention de données de prix déjà ajustés split-only, mais pas sur une application end-to-end des événements corporate actions dans le pipeline de replay.

3. Les dividendes sont visibles côté reporting, mais pas via une intégration homogène de toutes les phases de replay avec le moteur corporate actions.

### Conclusion backtest

Le projet a **bien unifié la convention de prix** au niveau data layer, et **le reporting commence à la refléter**, mais **le pipeline de replay backtest n’applique pas encore cette logique de manière homogène de bout en bout**. Verdict : **partiel**.

---

## 9.2 Côté live pipeline — **partiel hors pipeline / absent dans le flux principal**

### Ce qui est bien en place

1. Le module corporate actions live existe vraiment :
   - `corporate_actions/engine.py:181-314` applique les événements pending sur les positions.
   - `corporate_actions/cli.py:126-196` fournit les commandes `sync`, `apply`, `status`, `run`.

2. Le moteur sait charger les snapshots broker, appliquer les événements et alimenter le ledger cash :
   - `corporate_actions/engine.py:202-223` charge les positions.
   - `corporate_actions/engine.py:288-314` insère les applications et les écritures cash.

### Ce qui manque / limite l’unification

1. Je ne vois **aucune intégration directe** dans le pipeline live principal :
   - `run_execution.py` ne référence pas le module `corporate_actions`.
   - `execution_engine/executor.py` ne déclenche ni `sync`, ni `apply`, ni réconciliation corporate actions.

2. En pratique, on a **un sous-système corporate actions séparé**, pas une intégration native dans le chemin principal d’exécution live.

### Conclusion live

Le point 9 n’est **pas absent du projet**, mais il est **absent du pipeline live principal**. Autrement dit : **implémenté comme module opérationnel séparé, pas comme brique intégrée au flux live d’exécution**.

---

## 10. Réconcilier les exports pipeline de trades

## 10.1 Côté backtest — **partiellement implémenté, avec nette amélioration**

### Ce qui est bien en place

1. `trades.csv` n’est plus limité au seul `closed_trades_df` si les signaux pipeline sont fournis :
   - `backtesting/report.py:143-281` construit un export pipeline à partir de `phase3 -> phase7`.
   - il récupère `execution_date`, `filled_qty`, `fill_price`, `replay_exit_date`, `replay_exit_price`, `replay_exit_reason`, `replay_exit_intent_role`, etc.

2. Il y a une vraie logique de rapprochement avec l’export legacy :
   - `backtesting/report.py:230-280` merge le pipeline export avec le legacy via séquence de merge (`symbol`, `execution_date`, compteur de rang).
   - il remplit les colonnes legacy manquantes et calcule des compteurs de rapprochement (`legacy_matches`, `legacy_unmatched_rows`).

3. Le bundle d’export formalise la provenance :
   - `backtesting/report.py:284-316` renvoie `source`, `legacy_source`, compteurs de rapprochement et `price_adjustment_convention`.
   - `backtesting/report.py:676-702` utilise ce bundle pour écrire `trades.csv`.

4. Le schéma de reporting attend explicitement cette nouvelle provenance :
   - `tests/test_backtesting_refactor.py:448-464` valide le bloc `trade_export` avec `source = phase3_to_phase7_pipeline`.

### Ce qui manque / limite encore la réconciliation

1. `trade_audit_log.csv` n’est pas reconstruit à partir de la vérité pipeline Phase 3 → 7 :
   - `backtesting/report.py:705-721` exporte uniquement `trade_events_df`.

2. Donc :
   - `trades.csv` est **nettement mieux réconcilié qu’avant**,
   - mais **l’audit détaillé n’est pas encore unifié sur la même source de vérité**.

### Conclusion backtest

Le point 10 est **largement avancé côté `trades.csv`**, mais **pas complètement terminé pour l’audit détaillé**. Verdict : **partiel, proche du bon sens visé pour l’export principal**.

---

## 10.2 Côté live pipeline — **partiellement implémenté**

### Ce qui est bien en place

1. La réconciliation d’exécution existe et est sérieuse :
   - `execution_engine/reconciliation.py:23-132` compare targets, positions broker, positions internes, ordres ouverts et protections.
   - statuts : `SAFE_AUTO`, `MANUAL_REVIEW`, `BLOCKED`.

2. Le pipeline live persiste ces résultats :
   - `execution_engine/executor.py:800-860` calcule la réconciliation après soumission.
   - `execution_engine/db_io.py:1972-2025` remplace/persiste `execution_reconciliation_results`.

3. L’IHM les exploite :
   - `ihm/services/queries.py:1680-1740` expose `get_execution_reconciliation_results()`.

4. Il existe aussi une réconciliation J+1 broker statement ↔ fills internes :
   - `execution_engine/reconcile_statement.py:68-116` exécute le job et peut écrire un rapport JSON via `--report-out`.

### Ce qui manque / limite encore la réconciliation des exports

1. Je ne vois pas d’export canonique live type `trades.csv` / blotter final unifié comparable au backtest.
2. La vérité live est surtout en base (`execution_*`, `broker_*`) et dans l’IHM, plus qu’en export artefact standardisé.
3. Le job `reconcile_statement.py` sait produire un rapport, mais cela reste un **rapport de réconciliation**, pas un **export unifié de trades pipeline**.

### Conclusion live

Le live a **une vraie réconciliation des états et des écarts**, mais **pas encore un export de trades unifié et standardisé au même niveau que le besoin exprimé dans l’audit**. Verdict : **partiel**.

---

## Conclusion finale

### Réponse courte

- **8. Coûts d’exécution réalistes** → **partiellement implémenté** en backtest et en live.
- **9. Corporate actions / ajustements prix** → **partiellement implémenté** côté backtest ; **module présent mais non intégré au flux live principal**.
- **10. Réconciliation des exports pipeline de trades** → **partiellement implémenté** des deux côtés, avec un vrai progrès côté backtest `trades.csv` et une vraie réconciliation d’état côté live, mais pas encore une unification complète de tous les exports.

### En une phrase

Le P3 est **engagé mais pas totalement fermé** : la base technique existe clairement, certaines briques sont déjà solides, mais il reste encore des zones non unifiées entre **simulation / replay / reporting** côté backtest, et entre **exécution / corporate actions / exports** côté live.

## Priorisation des gaps restants

1. **Point 9 live** — intégrer `corporate_actions` dans le flux opérationnel principal ou formaliser explicitement le découplage.
2. **Point 10 backtest** — faire de `trade_audit_log.csv` un export reconstruit depuis la même vérité pipeline que `trades.csv`.
3. **Point 8 live/backtest** — enrichir le TCA avec commissions/frais explicites quand disponibles, pas seulement slippage + shortfall.
4. **Point 9 backtest** — brancher les corporate actions dans les phases de replay si l’objectif est une fidélité portefeuille complète.

