# Matrice ultra compacte — Backtest vs Live

Date: 2026-05-04

## Positionnement en une phrase

Le backtest est aujourd’hui **crédible pour la recherche avancée et l’audit de fidélité**, mais le pipeline live reste la **source de vérité opérationnelle**.

---

## Matrice compacte

| Sujet | Backtest actuel | Pipeline live | Écart résiduel |
|---|---|---|---|
| Données amont 1→10 | Consomme surtout des données déjà persistées (`stock_bars_daily`, `stock_scores_history`, `model_predictions`) | Recalcule/exécute réellement ingestion + screener + sentiment + ML | Le backtest est PIT-aware, mais ne rejoue pas toute la chaîne amont au runtime |
| Temporalité | Replay **daily** (`signal J -> exécution J+1 open`) + logique intrabar simplifiée | Runtime réel avec états marché/broker et aléas temporels | Pas de vraie séquence intraday observée |
| Risk | Peut réutiliser le vrai `PortfolioBuilder` via `--phase2-mode risk|risk_execution` | Runtime risk complet avec repository, snapshots compte/positions, persistance réelle | Très rapproché sur le cœur de décision, pas sur toute l’opérabilité live |
| Exécution | Intents/fills/TCA simulés, replay des quantités d’entrée (Phase 3) | `ProductionExecutor`, broker réel, fills observés, sync broker, réconciliation | Le backtest est execution-aware, pas broker-native |
| Protections / watcher | Replay protections (P4), watcher (P5), exit terminal + OCO logique (P7) | Watcher runtime persistant, transitions réelles broker/DB | Bonne fidélité métier, pas le service runtime complet |
| État du compte | Simule cash, settled cash, swing-only, margin/cash | Utilise l’état réel du compte broker/paper | Les contraintes sont bonnes, mais la vérité compte reste simulée |
| Corporate actions / cashflows | Sait consommer les dividendes déjà persistés dans le reporting | Exécute `sync` + `apply` sur la chaîne live | Les cashflows peuvent être intégrés, mais la mécanique CA n’est pas rejouée de bout en bout |

---

## Niveau de rapprochement actuel

### Ce qui est déjà bien rapproché du live

- **PIT amont** via `--engine-mode pipeline`
- **Risk** via `--phase2-mode risk_execution`
- **Entrées exécutées** via `--phase3-mode execution_replay`
- **Protections** via `--phase4-mode protection_replay`
- **Watcher** via `--phase5-mode watcher_replay`
- **Exit terminal / OCO logique** via `--phase7-mode exit_lifecycle_replay`

### Configuration la plus proche du live aujourd’hui

```powershell
python -m backtesting run \
  --engine-mode pipeline \
  --ml-pit-strategy use-persisted \
  --phase2-mode risk_execution \
  --phase3-mode execution_replay \
  --phase4-mode protection_replay \
  --phase5-mode watcher_replay \
  --phase7-mode exit_lifecycle_replay
```

---

## Si je veux aller plus loin — plan d’action priorisé

### Priorité 1 — Rejouer davantage la chaîne amont 1→10

Objectif : réduire l’écart “données déjà persistées” vs “pipeline live recalculé”.

Actions :
- créer un orchestrateur de replay PIT par séance ;
- pouvoir recalculer proprement screener / selector / sentiment / ML à date J ;
- tracer précisément quelles briques sont relues vs reconstruites.

### Priorité 2 — Rapprocher l’exécution du runtime broker réel

Objectif : réduire l’écart “execution-aware” vs “broker-native”.

Actions :
- introduire un repository / adapter de simulation plus proche du broker ;
- simuler états d’ordres, partial fills, retries, cancel/reject ;
- rapprocher davantage la réconciliation et l’état du compte dans la boucle PnL.

### Priorité 3 — Construire un vrai mode `compare-to-live`

Objectif : mesurer la dérive au lieu de seulement l’estimer.

Actions :
- comparer candidats, targets, ordres, fills, exits et PnL ;
- attribuer les écarts par étape : données / risk / execution / watcher ;
- produire un rapport de fidélité standardisé.

### Priorité 4 — Aller vers un “digital twin” partiel par fenêtre de test

Objectif : disposer de périodes de référence rejouables presque comme le live.

Actions :
- figer des snapshots complets (données + signaux + targets + événements) ;
- construire des suites de non-régression sur fenêtres courtes ;
- définir des seuils de divergence acceptables.

---

## Décision recommandée

- conserver le backtest actuel comme **moteur research + audit de fidélité** ;
- continuer à enrichir le mode pipeline-fidèle ;
- considérer le live comme **vérité opérationnelle**, et le backtest comme **reconstruction instrumentée**.

## Voir aussi

- roadmap détaillée par sprint : `prompt/backtest/backtest_vs_live_roadmap.md`
