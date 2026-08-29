# Backtesting, parité et validation

## Documents spécialisés

- [Architecture de replay broker-like](backtesting/replay_broker_like.md)
- [Microstructure, coûts et résolution intrabar](backtesting/microstructure_et_couts.md)
- [Parité live/backtest](backtesting/parite_live_backtest.md)
- [Validation statistique et promotion](backtesting/validation_statistique.md)

`backtesting/` rejoue signaux, risque et exécution avec données PIT et coûts réalistes. Sa fonction n'est pas seulement de calculer un PnL : il doit falsifier les hypothèses et mesurer la transférabilité au live.

## CLI

`python -m backtesting` expose des sous-commandes `run`, `backfill`, `calibrate`, `diagnose`, `recommend` et `walk-forward`. `profiles.py` fournit des profils nommés ; les flags CLI explicitement fournis priment sur les valeurs du profil.

## Composants

- `data_loader.py`, `cache.py` : données PIT et cache ;
- `signal_replay.py` : signaux/prédictions historiques ;
- `risk_bridge.py`, `risk_overlay.py` : règles du risque ;
- `simulator.py` : boucle portefeuille ;
- `execution_bridge.py`, `execution_broker_like.py` : interface d'exécution ;
- `execution_lifecycle_replay.py`, `exit_lifecycle_replay.py`, `protection_watcher_replay.py` : lifecycle et protections ;
- `microstructure.py` : coûts/slippage/volume ;
- `parity.py`, `fidelity.py` : écarts avec production ;
- `analytics.py`, `attribution.py`, `brinson_fachler.py` : métriques et attribution ;
- `statistical_validation.py`, `walk_forward*` : robustesse temporelle ;
- `adaptive_breaker.py`, `resilience.py`, `fuzz_*` : stress et invariants.

## Contrat d'exécution à figer

Tout résultat doit préciser : entry timing, prix d'entrée, initial stop ATR, TP, activation et distance du trailing, time-stop effectif, gap filter, résolution intrabar, frais, spread, slippage et capacité. Deux runs avec un seul de ces champs différent ne testent pas le même système.

## Coûts

Le moteur peut utiliser spread observé, slippage dépendant du volume, commissions tiercées et exécution intraday. En absence d'une donnée, le fallback doit être visible dans le rapport. Les coûts sont appliqués aux deux côtés et lors des sorties forcées.

## PIT et walk-forward

- univers résolu as-of ;
- prédictions OOS uniquement ;
- features disponibles à la date ;
- corporate actions correctement ajustées ;
- folds temporels sans mélange ;
- embargo/purge lorsque nécessaire ;
- sélection de paramètres séparée de l'évaluation finale.

## Métriques minimales

PnL net, CAGR, volatilité, Sharpe/Sortino, max drawdown et durée, turnover, exposition gross/net, win rate, profit factor, coûts, capacité, attribution long/short/secteur/régime/exit reason, stabilité par semestre et concentration des gains.

## Protocole de promotion

1. hypothèse et métrique pré-enregistrées ;
2. diagnostic univarié avant modèle complexe ;
3. train/validation/OOS stricts ;
4. sensibilité paramètres et seeds ;
5. coûts et capacité ;
6. comparaison au baseline canonique ;
7. replay exact du contrat PROD ;
8. shadow/paper ;
9. promotion explicite et rollback.

## Leçon de parité

Les analyses E11 sous lifecycle de recherche ne décrivaient pas le contrat PROD. Le recheck E12-A0b a invalidé la narrative de stops prématurés spécifiques à 2026H1. Cette règle est générale : aucune conclusion de lifecycle ne survit sans audit bit-for-bit du contrat exécuté.

---

## Architecture de replay par phases

Le moteur actuel ne se limite pas à un portefeuille vectorbt. Il possède un chemin broker-like destiné à reproduire les couches production :

| Phase | Fichier | Produit |
|---|---|---|
| signal | `signal_replay.py` | candidats datés et côté |
| risque | `risk_bridge.py` | `PortfolioEntry`, snapshots régime et artefacts |
| entrée/fills | `execution_replay.py` | tentatives, lifecycle d'ordres, fills synthétiques |
| protections | `execution_lifecycle_replay.py` | enfants stop/TP et groupes |
| watcher | `protection_watcher_replay.py` | activations et transitions post-entry |
| sorties | `exit_lifecycle_replay.py` | close intents et motifs |
| synthèse | `execution_broker_like.py` | frames normalisées et compteurs broker-like |

Chaque phase sauvegarde ses artefacts. Lorsqu'une divergence apparaît, comparer la première phase qui diffère plutôt que seulement le PnL final.

## CLI et profils

Les commandes sont implémentées dans `backtesting/cli/`. `profiles.py` applique un dictionnaire de profil aux arguments **uniquement** pour les attributs qui n'ont pas été passés explicitement. Ainsi `--profile X --tp Y` conserve Y. Le rapport doit enregistrer profil et overrides.

```powershell
python -m backtesting run --help
python -m backtesting walk-forward --help
python -m backtesting diagnose --help
python -m backtesting calibrate --help
```

Le grand nombre de flags rend les commandes copiées d'anciens rapports fragiles. Toujours consulter `--help` du commit courant et la metadata produite.

## Chargement et preflight

`data_loader.py` charge barres, scores, prédictions, univers, corporate actions et macro. Le preflight vérifie date/source/ajustement et couverture. Un backtest PIT nominal utilise les historiques de scores/univers, pas le snapshot courant répété sur le passé.

`resilience.py` classe les causes de prédictions absentes et peut reconstruire certaines frames selon le mode demandé. Cette reconstruction doit être annoncée (`rebuilt`, cause, batch) ; elle n'est pas identique à une prédiction historiquement publiée. Les overlays walk-forward sont appliqués seulement si leurs artefacts sont valides.

## Risk bridge

`build_phase2_risk_result` normalise les dates, transforme scores/prédictions en inputs ML-first, calcule ATR depuis les barres antérieures, construit une matrice de rendements pour corrélations et résout les snapshots de régime aux dates d'exécution. Il appelle les règles de portefeuille partagées puis convertit les entrées en signaux.

Le bridge doit utiliser une date de décision et une date d'entrée distinctes. `selection_contract.compute_entry_date` avance à la prochaine séance. Toute utilisation du close de la date de décision comme fill sans règle explicite est un lookahead/execution bias.

## Microstructure

### Gap gate

`should_skip_entry_for_gap` compare le prix d'exécution attendu à la référence selon un seuil. Il empêche une entrée dont le gap rend le target/stop incohérent. Un gap filter désactivé (`0`) constitue un contrat différent.

### Résolution intrabar

`resolve_intrabar_exit` traite le cas où high et low touchent plusieurs barrières dans une même barre. La politique conservative choisit le résultat défavorable selon le côté ; d'autres politiques doivent être explicitement nommées. Avec des barres daily, l'ordre réel des touches est inconnu : aucune politique ne peut prétendre le reconstruire.

### Prix d'exécution et slippage

`compute_execution_price` combine prix de référence, spread et impact/slippage orienté contre le trader. `compute_adv_usd` mesure la capacité. `should_split_order` décide si une taille doit être fractionnée. Les paramètres vivent dans `ExecutionModelConfig`, `SlippageConfig` et `MicrostructureConfig` et doivent être sérialisés dans le report.

## Lifecycle des sorties

Le replay de protections part des fills d'entrée agrégés, pas des targets. Il construit les enfants pour la quantité exécutée, puis le watcher recherche les dates de trigger sur les séances suivantes. Le mapping d'exit reason vers intent role permet de rapprocher stops, TP, trailing, time-stop et force-close.

Pour analyser MFE/MAE et post-exit, reconstruire depuis les OHLC du chemin réellement exécuté. Les labels ML ou excursions calculées sous un autre stop ne sont pas substituables. Un time-stop configuré mais neutralisé par trailing doit avoir zéro fill effectif et être décrit comme tel.

## Corporate actions et total return

`compute_total_return_with_dividends` ajoute le cash des dividendes au MTM. Les splits ajustent quantités/coûts sans créer de rendement. `load_dividends_received` et le résumé CA alimentent le report. Comparer une equity curve price-only à une benchmark total-return crée un biais.

## Analytics et attribution

`generate_report` assemble métriques, diagnostics, risk overlay et microstructure. Les exports comprennent report JSON, equity CSV/HTML, trades et audit détaillé. Le schéma est validé par `report_schema.py`/Pydantic ; le mode strict refuse types/champs incompatibles.

`report_schema_pydantic.py` porte la variante Pydantic lorsque la dépendance est disponible ; `report_schema.py` conserve le contrat léger. Les deux doivent rester cohérents sur champs obligatoires, types et sémantique.

Analyses disponibles : benchmark, rendement mensuel, secteurs, tail/VaR-like, ulcer index, Calmar, Brinson-Fachler, scénarios d'attribution et IC. L'attribution doit utiliser des groupes mutuellement compréhensibles et somme réconciliée au total.

## Validation statistique

`bootstrap_trades` estime une distribution par rééchantillonnage ; le block bootstrap préserve davantage la dépendance temporelle. `parameter_sensitivity` évalue la stabilité locale. `deflated_sharpe_ratio` corrige l'inflation liée à non-normalité et essais multiples. `multiple_testing_correction` ajuste les p-values. `compute_promotion_score` agrège les critères de promotion.

Le nombre d'expériences réellement tentées, y compris celles non retenues, doit entrer dans la correction. Relancer beaucoup de seeds puis ne présenter que la meilleure est une optimisation.

## Parité live/backtest

`parity.py` compare décisions par symbole/action/quantité et les couches de risque. Les tolérances actuelles par défaut sont 5 % relatif et 1 action absolue ; le seuil global de divergence est 10 %. Ces tolérances servent à classifier, pas à effacer les écarts.

Le rapport de parité doit distinguer : missing live, missing replay, action mismatch, quantity mismatch, reason/risk layer mismatch. `write_parity_artifacts` conserve lignes et résumé sous `artifacts/parity_runs` par défaut.

## Reproductibilité

`run_metadata.py` collecte git, environnement et hash des datasets. Un run reproductible conserve : commit/dirty state, Python/packages, config effective, commande, seed, batch ML, univers, hashes frames, calendrier, coûts et artefacts. Sans hash de données, un même commit peut produire un résultat différent après backfill.

## Diagnostic de résultats suspects

| Signal | Investigation |
|---|---|
| PnL anormalement élevé | lookahead, prix close/open, coûts zéro, survivorship |
| aucun short | target/side, long_only, borrow, régime, synthèse ML |
| stops trop nombreux | ATR/source, entry price, intrabar, activation trailing |
| time-stop inattendu | contrat effectif et neutralisation watcher |
| résultats changent | dataset hash, seed, batch, univers, cache |
| excellent global, mauvais semestres | concentration, régime, top trades |
| parité quantité seulement | arrondi fractionnaire, equity/buying power, positions initiales |
| dividendes incohérents | convention split-only et ledger |

## Matrice de tests

Les tests couvrent profils/overrides, fractional, data-source preflight, conviction PIT, total return, live parity golden, risk bridge régime, replay d'exécution, lifecycle, coûts, statistiques et fuzz différentiel. Pour toute évolution production du risque ou watcher, ajouter ou mettre à jour un golden de parité.
