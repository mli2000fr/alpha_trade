# État actuel du backtest — synthèse de fin de phase

Date: 2026-05-04

## 1. Résumé exécutif

Le backtest `alpha_trade` est aujourd’hui dans un état **nettement plus mature qu’un simple replay de signaux**.

Il dispose désormais de deux niveaux d’usage :

1. **Mode research**
   - rapide ;
   - tolérant ;
   - compatible avec l’historique du projet ;
   - adapté à l’exploration alpha / robustesse.

2. **Mode pipeline-fidèle partiel**
   - plus strict ;
   - plus traçable ;
   - plus proche de la chaîne live sur les plans PIT, risk et execution lifecycle ;
   - mais **pas encore identique au pipeline live réel**.

Le point clé est le suivant :

> le backtest est maintenant capable de rejouer une part significative de la logique live, mais il reste un **replay daily simulé et documenté**, pas un jumeau broker/runtime parfait.

---

## 2. Ce qui est réellement livré aujourd’hui

## 2.1 Base du moteur

Le moteur de backtest sait aujourd’hui :

- charger `OHLCV` depuis la base ;
- charger les scores PIT via `stock_scores_history` ;
- gérer les prédictions ML et overlays sentiment ;
- reconstruire les signaux de conviction ;
- simuler les entrées/sorties avec contraintes de compte ;
- produire des artefacts et un `report.json` structuré.

---

## 2.2 Phases disponibles côté backtesting

### Phase 1 — Fidélité PIT amont

Disponible via :

- `--engine-mode research|pipeline`
- `--ml-pit-strategy ...`

Apporte notamment :

- contrat PIT plus strict ;
- manifeste de fidélité ;
- diagnostics scores / sentiment / ML ;
- distinction claire entre run tolérant et run strict.

### Phase 2 — Bridge risk / execution

Disponible via :

- `--phase2-mode off|risk|risk_execution`

Apporte :

- réutilisation du vrai `PortfolioBuilder` ;
- génération de cibles d’exécution ;
- intents et TCA simulés ;
- artefacts Phase 2.

### Phase 3 — Replay chronologique des entrées

Disponible via :

- `--phase3-mode off|execution_replay`

Apporte :

- injection des quantités remplies simulées dans le moteur ;
- exécution `J -> J+1 open` rejouée explicitement ;
- signaux enrichis par `execution_date`, `filled_qty`, `fill_price`.

### Phase 4 — Replay des protections

Disponible via :

- `--phase4-mode off|protection_replay`

Apporte :

- take-profit / initial stop / trailing issus des child intents ;
- priorité donnée à ces protections dans le simulateur.

### Phase 5 — Replay du watcher de protection

Disponible via :

- `--phase5-mode off|watcher_replay`

Apporte :

- trigger et promotion conservative du trailing ;
- lifecycle explicite `pending/transitioned/failed` ;
- artefacts d’événements du watcher.

### Phase 6 — Consolidation research-grade et opérabilité

Pas de `phase6_mode` dédié.

Cette phase correspond à un ensemble d’améliorations structurelles déjà intégrées :

- presets capital partagés ;
- coût explicite `commission_bps/slippage_bps` ;
- profils de backtest ;
- walk-forward score source ;
- run metadata ;
- risk-free rate ;
- dividendes ;
- microstructure ;
- risk overlays ;
- analytics / cache / validation statistique ;
- IHM backtesting plus complète.

### Phase 7 — Exit lifecycle replay terminal

Disponible via :

- `--phase7-mode off|exit_lifecycle_replay`

Apporte :

- sortie terminale explicite rejouée ;
- raison terminale d’exit (`take_profit`, `initial_stop`, `trailing_stop`) ;
- annulation OCO logique du sibling ;
- artefacts `phase7_exit_lifecycle_replay_*`.

---

## 2.3 IHM backtesting actuelle

La page `ihm/pages/backtesting.py` expose maintenant :

- presets capital ;
- paramètres PIT ;
- score source walk-forward ;
- phases 2 / 3 / 4 / 5 / 7 ;
- options microstructure ;
- options risk overlay ;
- logs et historique de runs ;
- rapport structuré et artefacts.

L’IHM ne force pas ces modes :

- les défauts restent neutres ;
- les activations avancées sont explicites.

---

## 3. Configuration la plus proche du pipeline live aujourd’hui

La configuration la plus proche du pipeline live actuellement n’est **pas** le mode par défaut.

Elle ressemble plutôt à un run du type :

```powershell
python -m backtesting run \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --engine-mode pipeline \
  --ml-pit-strategy use-persisted \
  --phase2-mode risk_execution \
  --phase3-mode execution_replay \
  --phase4-mode protection_replay \
  --phase5-mode watcher_replay \
  --phase7-mode exit_lifecycle_replay
```

Selon le contexte, on peut ajouter aussi :

- `--capital-preset-key ...`
- `--score-column final_score_walk_forward`
- `--walk-forward-artifacts-dir ...`

Cette configuration donne aujourd’hui le **meilleur rapprochement disponible** avec la chaîne live, tout en restant un replay/simulateur backtesting.

---

## 4. Différences principales entre le backtest actuel et le pipeline live

## 4.1 Vue courte

### Le backtest actuel

- travaille surtout à partir de **données déjà persistées** ;
- rejoue la logique sur des **barres daily** ;
- simule le risque et l’exécution dans une enveloppe contrôlée ;
- produit un PnL explicable et des diagnostics riches.

### Le pipeline live

- exécute la chaîne métier complète **en conditions réelles** ;
- dépend d’un broker, d’un compte, d’APIs et d’un état opérationnel vivant ;
- persiste des événements, ordres, fills, positions, réconciliation ;
- subit les aléas du monde réel.

---

## 4.2 Différences détaillées par grande étape

### A. Données amont : live recalculé vs backtest consommé

#### Pipeline live

Le pipeline quotidien lit et/ou calcule réellement les étapes :

1. import bars
2. sanitation daily
3. screener
4. latest quotes
5. earnings calendar
6. alpha scanner
7. event sentiment
8. signal aggregator
9. train ML
10. predict ML

#### Backtest actuel

Le backtest ne rejoue pas toute cette chaîne 1→10 au runtime d’un `run`.

Il s’appuie principalement sur :

- `stock_bars_daily`
- `stock_scores_history`
- `model_predictions`
- artefacts walk-forward éventuels

#### Différence concrète

Le backtest est **PIT-aware**, mais il n’est pas un orchestrateur complet de recalcul live-like des étapes 1→10 à chaque séance.

---

### B. Horizon temporel : daily replay vs runtime réel

#### Pipeline live

- réagit à des états réels de marché et de broker ;
- voit des ordres, des fills, des snapshots de compte, des transitions runtime ;
- peut vivre des latences, timeouts, refus, retries.

#### Backtest actuel

- raisonne principalement sur des barres daily ;
- résout des entrées `J+1 open` ;
- résout les exits via OHLC daily + logique intrabar simplifiée ;
- simule les transitions lifecycle de façon conservative.

#### Différence concrète

Le backtest ne voit pas la vraie séquence intraday d’événements ; il la **reconstruit**.

---

### C. Risque : bridge réel partiel vs runtime live complet

#### Pipeline live

Le live s’appuie sur :

- `RiskRepository`
- `PortfolioBuilder`
- snapshots compte / positions broker
- persistance DB des décisions risk

#### Backtest actuel

- en mode standard : bypass complet du vrai chemin risk ;
- en Phase 2 : bridge vers `PortfolioBuilder`, donc rapprochement fort ;
- mais toujours dans une enveloppe backtesting, sans être le même runtime opérateur complet.

#### Différence concrète

Le backtest peut réutiliser le vrai cœur de sizing/risk, mais pas encore toute la couche opérationnelle live dans les mêmes conditions d’exécution.

---

### D. Exécution : simulateur déterministe vs broker réel

#### Pipeline live

Le live passe par :

- `ProductionExecutor`
- `BrokerAdapter`
- ordres broker réels
- fills observés
- synchronisation broker
- réconciliation
- TCA live

#### Backtest actuel

Même avec les Phases 2 / 3 / 4 / 5 / 7 :

- aucun ordre réel n’est envoyé ;
- aucun broker n’est interrogé dans la boucle de PnL ;
- les fills restent simulés ;
- l’OCO est rejoué logiquement, pas constaté depuis un broker réel.

#### Différence concrète

Le backtest est aujourd’hui **execution-aware**, mais pas **broker-native**.

---

### E. Watcher et lifecycle : replay fidèle partiel vs service persistant réel

#### Pipeline live

Le watcher de protection est un composant runtime vivant, avec :

- état persistant ;
- polling ;
- transitions ;
- annulations ;
- interactions broker/DB.

#### Backtest actuel

Le backtest rejoue :

- les protections Phase 4 ;
- la promotion conservative du watcher Phase 5 ;
- l’exit terminal Phase 7.

#### Différence concrète

Le backtest reproduit **la logique métier utile au PnL**, mais pas tout le service persistant réel ni ses aléas d’exploitation.

---

### F. État du compte : compte simulé vs compte réel

#### Pipeline live

Le compte réel/paper porte :

- equity observée ;
- buying power ;
- settled cash ;
- positions réelles ;
- lots ;
- historiques d’ordres ;
- day trade count réel.

#### Backtest actuel

Le moteur simule :

- cash / settled cash ;
- PDT ;
- swing_only ;
- margin/cash ;
- allocations et sorties.

#### Différence concrète

Le backtest a de bonnes **contraintes métier**, mais il ne repart pas de la vérité opérationnelle broker d’un compte historique complet.

---

### G. Corporate actions et cashflows

#### Pipeline live

Le pipeline live exécute explicitement :

- sync corporate actions ;
- apply sur positions et cash ledger.

#### Backtest actuel

Le reporting sait intégrer :

- les dividendes déjà présents dans `portfolio_cash_ledger`.

Mais le `run` backtest ne rejoue pas à lui seul toute la séquence live `sync/apply` corporate actions.

#### Différence concrète

Le backtest sait **consommer** certains cashflows, pas orchestrer toute la mécanique live autour des corporate actions.

---

## 4.3 Matrice synthétique backtest vs live

| Sujet | Backtest actuel | Pipeline live |
|---|---|---|
| PIT scores | Oui, surtout via `stock_scores_history` | Oui, via pipeline amont + persistance |
| Walk-forward score | Oui | Partiellement selon artefacts/modèle |
| Vrai `PortfolioBuilder` | Oui en Phase 2 | Oui |
| Ordres broker réels | Non | Oui |
| Fills observés réels | Non | Oui |
| Réconciliation broker | Non dans la boucle PnL | Oui |
| Watcher de protection | Replay Phase 5 | Runtime persistant |
| Exit terminal explicite | Oui en Phase 7 | Oui, via événements réels |
| OCO sibling cancel | Rejoué logiquement | Constaté / géré runtime |
| Microstructure intraday réelle | Non | Partiellement via broker/runtime |
| Daily research rapide | Oui | Non |

---

## 5. Ce qu’on peut dire honnêtement aujourd’hui

## 5.1 Oui, on peut dire

- le backtest est devenu **nettement plus fidèle** au pipeline live qu’au départ ;
- il rejoue maintenant une partie importante de la chaîne risque/exécution/protection ;
- il produit des diagnostics structurés et des artefacts utiles ;
- il permet d’expliquer bien mieux les écarts de PnL ;
- il dispose d’une IHM backtesting réellement exploitable.

## 5.2 Non, on ne peut pas encore dire

- qu’il est identique au live ;
- qu’il reproduit un broker réel ;
- qu’il rejoue tout le runtime live 1→14 ;
- qu’il remplace une comparaison directe à des logs live réels.

---

## 6. Positionnement recommandé

### Utiliser le mode `research` si l’objectif est

- explorer rapidement des idées ;
- calibrer des paramètres ;
- tester robustesse et sensibilité ;
- itérer sans coût opérationnel élevé.

### Utiliser le mode `pipeline` + Phases 2/3/4/5/7 si l’objectif est

- approcher la décision live ;
- auditer la chaîne portfolio → execution lifecycle ;
- expliquer les divergences ;
- documenter la fidélité d’un run.

---

## 7. État des validations connues dans cette séquence

Les validations ciblées suivantes ont été exécutées avec succès :

```powershell
pytest tests/test_backtesting_refactor.py -q --no-cov
pytest tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_phase2_bridges.py tests/test_backtesting.py -q --no-cov
```

### Important

Ces validations confirment l’état fonctionnel des briques backtesting documentées ici.

En revanche, cela ne signifie pas qu’un `pytest` global de tout le dépôt a été relancé et validé dans cette même séquence.

---

## 8. Conclusion finale

Le backtest actuel est dans un état **solide, instrumenté et utile**, avec une vraie séparation entre :

- un chemin **research** rapide ;
- un chemin **pipeline-fidèle partiel** de plus en plus riche.

La différence principale avec le pipeline live reste la suivante :

> le live observe et persiste des événements réels de marché, de broker et de compte ; le backtest, lui, reconstruit ces événements à partir d’un historique PIT et d’un simulateur daily enrichi.

Autrement dit :

- **le backtest est aujourd’hui crédible pour la recherche avancée et l’audit de fidélité** ;
- **le pipeline live reste la source de vérité opérationnelle**.

