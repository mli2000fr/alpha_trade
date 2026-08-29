# 🟢 C2+B4 — Contrôleur de drawdown robuste : GO LIVE PROD (2026-08-21)

**Date** : 2026-08-21
**Statut** : **C2+B4 = GO LIVE PROD** (config.yaml `policy: b4` actif, décision utilisateur 2026-08-21). Le gate « période paper représentative » était la porte d'entrée prévue ; elle est **remplacée par décision directe GO live** (validation backtest + parité logique prod jugées suffisantes). Le gate quotidien de parité reste en place comme garde opérationnelle. **Rollback = `policy: b0`.**
**Règle de gel** : `backtesting/adaptive_breaker.py`, seuils B4, C2 = **FROZEN**. Toute anomalie PROD = problème d'intégration/parité d'abord, **jamais** une raison de retuner le modèle.

---

## 1. Contexte

Le breaker historique PROD (`b0` : recovery 92% + cap 25%) est jugé trop lent à réarmer en conditions de marché normales, mais les variantes agressives testées (B2 « regime speed », B3 « combiné ») ont échoué en OOS 2022 (veto : réarmements en bear-market rally → retrips). B4 est le contrôleur robuste issu de cette campagne : il autorise le réarmement **par régime**, mais borne la remontée d'allocation par la **récupération d'equity** (equity confirmation) avec une règle **RELAPSE** anti-rechute.

---

## 2. B4 — le contrôleur (design figé)

Échelle d'allocation (ladder) dans `backtesting/adaptive_breaker.py::b4_allocation` :

| Régime | Condition | Allocation |
|---|---|---|
| SLIDE / CORRECTION | — | 10% |
| REBOUND | streak ≥ 3 jours | 25% |
| REBOUND | RR ≥ 25% | 50% |
| BULL | streak ≥ 3 jours | 50% (`bull_streak_level`) |
| BULL | RR ≥ 25% | 75% |
| BULL | RR ≥ 50% | 100% |

- **RR** = récupération mesurée depuis le peak de l'épisode (equity confirmation).
- **RELAPSE** : nouveau creux OU drawdown qui se dégrade ≥ 3 pts depuis le début du réarmement → retour à 10%, reset du streak, peak d'épisode figé. `relapse_day` = latch consommé à l'`allocate` suivante.
- Trip breaker : DD ≥ 15% (`TRIP_DD_PCT=0.15`, figé) → 10%.
- B4a (variante BULL streak → 75%) testée mais **écartée** : n'a pas corrigé 2020.

> ⚠️ **B4 est FROZEN. Ne pas modifier.**

---

## 3. Historique de validation

| Étape | Résultat | Verdict |
|---|---|---|
| E23-OOS 6 runs (B0/B2 × 2020/2022/2024H1) | B2 : 30 réarmements, DD 21.9% > B0+3pts | **B2 veté sur 2022** |
| B4 4 runs (main/2020/2022/2024H1) | 2020 : Ret −14.3% > −11% ? NON (RR plafonné ~16% < 25%) | **Gate 2020 échoué** (structural, assumé) |
| B4a (BULL streak ≥3 → 75%) | 2020 inchangé (−13.9%) | **Écarté** |
| **Freeze** | Décision user : B4 = candidat breaker PROD, B0 = fallback configurable, arrêt du tuning | **Acté** |
| Portage PROD OFF | Même machine d'état, mêmes seuils, mêmes règles PIT, même régime SPY que le backtest | **Acté** |
| Parité croisée backtest↔prod | 0 divergence (replay 2025/2022 via `CircuitBreaker` prod) | **Validé** |
| Validation intégrée C2+B4 (R0-R3) | **R3 = 34.6% / 1.33 / DD 16.7** bat R0 (9.1/0.52/16.5) ; interaction additive **+2.7 pts** | **R3 validé 8/8** |

### Pourquoi 2020 est sacrifié (assumé, pas un bug)

En 2020 l'equity ne récupère que ~16% (COVID) : B4 reste bloqué à 50% et ne débloque jamais 75/100%. B2 ne « gagnait » 2020 qu'en prenant le risque qui a causé le veto 2022. Optimiser 2020 = sur-apprentissage sur quelques épisodes historiques. **Refusé volontairement.**

### Validation intégrée C2+B4 — détail

| Run | Config | Ret% | Sharpe | DD% |
|---|---|---|---|---|
| R0 | 7% fixe + b0 | 9.1 | 0.52 | 16.5 |
| R1 | c2 + b0 | 20.0 | 0.91 | 16.5 |
| R2 | 7% fixe + b4 | 21.0 | 0.87 | 16.7 |
| **R3** | **c2 + b4** | **34.6** | **1.33** | **16.7** |

- Exits identiques à même trailing (R1=R3) : le breaker scale les **entrées**, pas les sorties.
- Gain = réallocation plus rapide (temps pour revenir à 100% : 110 j vs 299 j) ; 2025H2 +27.7% (vs R1 +13.0%).
- Coût : avril 2025 −8.7% (vs −8.3%).

---

## 4. Trois niveaux de sécurité (séparés)

1. **Logique B4** — figée et testée unitairement (`_test_adaptive_breaker.py`, prod breaker suite 21 tests, `test_executor.py` 31 tests).
2. **Parité backtest↔prod** — contrôlée au niveau des **états de risque** (replay 2025/2022, 0 divergence).
3. **Parité opérationnelle quotidienne** — `run_daily_parity.py` **bloque toute divergence opérationnelle** (gate strict, exit 2).

B4 reste **OFF par défaut** en PROD, B0 = rollback.

---

## 5. Gate quotidien strict (implémenté)

### Fonction pure : `backtesting/parity.py::compare_risk_layers(live_ctx, replay_ctx, *, float_tol=1e-6)`

**Discret — égalité stricte, zéro tolérance** : `regime` (C2), `trailing_policy`, `breaker_tripped`, `rearm_date`, `force_close`.

**Flottant — tolérance minuscule (1e-6)** : `allocation_scale` (B4), `episode_peak`, `episode_trough`, `episode_alloc`, + protections par symbole (`tp`, `sl`, `trailing`).

**Format du contexte** (live comme replay) :

```json
{
  "regime": "SLIDE", "trailing_policy": "c2",
  "allocation_scale": 0.10, "breaker_tripped": true,
  "episode_peak": 4200.0, "episode_trough": 3300.0, "episode_alloc": 0.10,
  "rearm_date": "2025-05-06", "force_close": false,
  "protections": {"AAPL": {"tp": 0.07, "sl": 0.025, "trailing": 0.07}}
}
```

### CLI : `scripts/run_daily_parity.py`

```
python -m scripts.run_daily_parity \
  --trade-date <YYYY-MM-DD> \
  --live-risk-context <json du contexte risk émis par le flux paper/live> \
  --replay-tag <tag B4>        # défaut: e23b4_main
```

- `--replay-tag` : lit `artifacts/backtesting/<tag>/drawdown_breaker_daily.csv` pour construire le **contexte risk attendu** (régime SPY, allocation B4, état breaker, rearm détecté par alloc +≥0.09). Régime construit uniquement si `policy != b0` → **tags B4/B4a uniquement** (pas B0).
- **Toute divergence discrète/flottante → exit 2 + alerte** (0 = parité OK).

### Persistance (rejouabilité)

Chaque jour, sous `artifacts/parity_runs/<date>/` :
- `risk_layers_live.json` / `risk_layers_replay.json` : contexte complet utilisé par le gate → **permet de rejouer toute divergence a posteriori** ;
- `risk_layers_divergences.json` : divergences du jour ;
- accumulation dans `artifacts/parity_runs/paper_coverage.json`.

---

## 6. Période paper représentative (gate GO live réel)

`backtesting/parity.py::summarize_paper_coverage(contexts)` :

- **Obligatoire** : ≥ 2 jours verts (`min_days`) **ET** ≥ 1 changement de régime (sinon on ne teste que le chemin nominal).
- **Idéal (non bloquant)** : ≥ 1 jour avec allocation < 1.0 (épisode non-nominal, contrôle effectif du breaker).

CLI : `scripts/check_paper_coverage.py` → **exit 0 = GO live réel / exit 1 = NO-GO**.

> ⚠️ **Ne PAS valider B4 après une seule journée verte.**

---

## 7. Procédure paper → GO live réel

> 🟢 **2026-08-21 : GO LIVE PROD acté directement** (décision utilisateur). Le gate paper représentatif reste documenté ci-dessous et la garde quotidienne de parité reste active en production.

1. **Activation PROD** : `config.yaml → policy: b4` (fait), carte régime SPY construite à chaque run (`run_execution.py`).
2. **Chaque jour** : `run_daily_parity` → doit sortir **exit 0** (0 divergence) ; contextes live/replay persistés (rejouables).
3. **Garde** : `check_paper_coverage` (≥2 jours verts + ≥1 changement de régime) utilisable comme suivi de la montée en charge ; toute divergence → exit 2 + alerte.
4. **Rollback** : `policy: b0` / `ALPHA_TRADE_CB_POLICY=b0` — immédiat, bit-à-bit historique.

---

## 8. B4 OFF par défaut + rollback B0

**Précédence** (`run_execution.py`) : `ALPHA_TRADE_CB_POLICY` (env) > `config.yaml risk_management.policy` > `b0`.

- **PROD par défaut** : `policy: b0` (comportement bit-à-bit inchangé).
- **Override test/paper** : `ALPHA_TRADE_CB_POLICY=b4` (test-only, jamais le défaut global).
- **Rollback B0** : unset env / `config.yaml → policy: b0`.

### État config.yaml au 2026-08-21 — B4 ACTIF EN PROD

`config.yaml` porte **`risk_management.policy: b4` ACTIF** : **B4 est le breaker PROD depuis le 2026-08-21** (GO live utilisateur). Conséquences :

- Sans override env, `run_execution.py` tourne en **B4** (carte régime SPY construite automatiquement, lookback 400j, PIT journalier).
- **Fail-safe** : si la carte régime SPY est indisponible/absente pour un jour, `b4_allocation(regime=None)` → cap **10%** (jamais d'exposition au-delà de 10% sans régime).
- **Rollback B0** = remettre `policy: b0` (ou `$env:ALPHA_TRADE_CB_POLICY = "b0"`), override env prioritaire.

---

## 9. Tests

| Suite | Résultat |
|---|---|
| `tests/test_parity_risk_layers.py` (gate + coverage) | 14 passed |
| `tests/test_breaker_prod_parity_b0.py` | PASS |
| `tests/test_breaker_prod_parity_b4.py` (synthetic trip+RELAPSE+100%) | PASS |
| Suite breaker prod (21) + `test_executor.py` (31) | PASS |

---

## 10. Fichiers

- Logique B4 (FROZEN) : `backtesting/adaptive_breaker.py` ; miroir backtest `backtesting/risk_overlay.py` ; PROD `risk_management/circuit_breaker.py`, `risk_management/config.py`.
- Hook journalier : `execution_engine/executor.py` ; entrée : `run_execution.py` (`_cb_policy`, carte régime SPY).
- Gate : `backtesting/parity.py` (`compare_risk_layers`, `summarize_paper_coverage`) ; CLI `scripts/run_daily_parity.py`, `scripts/check_paper_coverage.py`.
- Tests : `tests/test_parity_risk_layers.py`, `tests/test_breaker_prod_parity_b4.py`, `tests/test_breaker_prod_parity_b0.py`.
- Artefact backtest de référence : `artifacts/backtesting/e23b4_main/` (+ `e23b4_2020/2022/2024h1`, `e23b4a_*`).

---

## 11. Limites / rappels

- `portfolio_targets` est VIDE → `run_execution.py` n'est pas rejouable historiquement (limite d'architecture, couverte par la parité de couches déjà prouvée + gate quotidien).
- Les runs B0 n'ont pas de `spy_regime` dans `drawdown_breaker_daily.csv` → contexte replay uniquement pour tags B4/B4a.
- 2 tests préexistants cassés (hors périmètre) : `test_backtesting_refactor.py` référence `_vectorized_fuse` absent de `signal_replay.py`.
