# Risk Management — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `risk_management/` et les commandes utiles pour :

- construire un portefeuille cible à partir des candidats scorés,
- appliquer sizing, contraintes et filtre de corrélation,
- intégrer la composante ML dans le score de conviction,
- écrire les décisions et les cibles en base pour l'exécution.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `risk_management/__init__.py` | Package Python |
| `risk_management/__main__.py` | Point d'entrée package |
| `risk_management/run_risk.py` | Lanceur recommandé |
| `risk_management/cli.py` | CLI standalone |
| `risk_management/portfolio_builder.py` | Orchestrateur principal de construction du portefeuille |
| `risk_management/position_sizer.py` | Sizing ATR |
| `risk_management/kelly.py` | Sizing Kelly optionnel |
| `risk_management/constraints.py` | Contraintes portefeuille |
| `risk_management/risk_checker.py` | Vérifications de risque |
| `risk_management/circuit_breaker.py` | Suspension sur drawdown / perte quotidienne |
| `risk_management/concentration.py` | Trackers anti-concentration et anti-répétition (Plan v2 Sprint 5) |
| `risk_management/conviction.py` | Fusion score quant + prédiction ML |
| `risk_management/correlation_filter.py` | Filtre de corrélation |
| `risk_management/models.py` | Modèles métiers risk (dataclasses) |
| `risk_management/enums.py` | Valeurs canonisées `sizing_method` / `decision_reason_code` |
| `risk_management/db_io.py` | Chargement candidats, prix, prédictions, historique |
| `risk_management/audit.py` | Persistance décisions et cibles |
| `risk_management/config.py` | Paramètres immuables |
| `risk_management/regime_apply.py` | Application des overrides de régime live/backtest |
| `risk_management/live_pipeline_guards.py` | Garde-fous spécifiques au pipeline live |
| `risk_management/ml_gate.py` | Porte ML : validation des prédictions avant sizing |
| `risk_management/shadow_compare.py` | Diff offline/piloté entre deux runs risk |

---

## 2. Prérequis

### 2.1 Tables et données requises

#### Obligatoires

- `stock_scores_history`
- `stock_bars_daily`
- `risk_decisions`
- `portfolio_targets`
- `run_business_summaries`

#### Optionnelles mais très utiles

- `model_predictions`
- `model_metrics`
- `model_training_run`
- `account_risk_snapshots`
- `broker_account_snapshots`
- `broker_positions_snapshots`
- historique de rendements suffisant dans `stock_bars_daily`
- `portfolio_cash_ledger` si l'on veut réintégrer les dividendes PIT dans la décomposition d'equity
- `shadow_drift_runs` si l'on veut persister les comparaisons shadow

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

### 2.3 Entrées consommées par le module

Le module charge principalement :

- les candidats depuis `stock_scores_history` avec fallback PIT `snapshot_date <= trade_date`,
- les prix / ATR depuis `stock_bars_daily`,
- les prédictions depuis `model_predictions`,
- les win rates via `model_metrics` + `model_training_run`,
- l'equity effective via `account_risk_snapshots` ou fallback broker / CLI,
- le snapshot de régime live via `service.market` quand disponible.

---

## 3. Commandes utiles

### Lancement standard

```powershell
python -m risk_management.run_risk
```

### Lancement avec equity explicite

```powershell
python -m risk_management.run_risk --account-equity 100000 --max-positions 10
```

### Dry-run

```powershell
python -m risk_management.run_risk --account-equity 100000 --dry-run
```

### Date explicite

```powershell
python -m risk_management.run_risk --trade-date 2026-04-21
```

### Activation Kelly + paramètres de corrélation

```powershell
python -m risk_management.run_risk --enable-kelly-sizing --correlation-threshold 0.80 --correlation-lookback-days 60 --correlation-min-overlap 40
```

### Shadow compare piloté

```powershell
python -m risk_management.run_risk --enable-shadow-compare
```

### Shadow compare avec run de référence explicite

```powershell
python -m risk_management.run_risk --enable-shadow-compare --shadow-compare-run-id risk-20260520-001
```

### Multi-comptes

```powershell
python -m risk_management.run_risk --account-equity 100000 --account live1
```

---

## 4. Ce que fait le module

### 4.1 Chargement des données

Le CLI :

1. résout le compte et l'equity effective ;
2. construit un `RiskConfig` ;
3. résout le snapshot de régime live et applique `risk_management.regime_apply.apply_snapshot()` ;
4. charge les candidats PIT ;
5. charge les prix / ATR, prédictions ML, win rates et matrice de rendements ;
6. construit le portefeuille via `PortfolioBuilder.build()` ;
7. émet un `run_summary` riche (préflight, régime, ML gate, equity, post-mortem) ;
8. persiste décisions / targets, puis optionnellement un rapport de shadow compare.

### 4.2 Construction des entrées (direction-aware, Plan v2 Sprint 2-4)

`PortfolioBuilder.build()` :

1. enrichit les candidats avec `predicted_proba` / `predicted_side` et `historical_win_rate` ;
2. calcule `conviction_score` directionnel (long ET short) ;
3. trie les candidats par conviction décroissante ;
4. applique le filtre de corrélation ;
5. applique les trackers de concentration (`SymbolTradeTracker` + `ConsecutiveLossTracker`), **side-aware** ;
6. applique le sizing ATR ou Kelly, direction-aware (le sizing short utilise la même logique ATR mais avec `risk_per_share` inversé) ;
7. vérifie les contraintes (dont `short_max_positions`, `short_min_score`) ;
8. produit des `PortfolioEntry` avec statut `ACCEPTED`, `REDUCED` ou `REJECTED`.

### 4.2.ter Short selling (Plan v2 — Sprint 2-5)

Le module supporte désormais les **positions short** en complément des positions long :

- **Option B** : `short_score` dédié calculé par `selector/short_score.py` (trend 30%, RSI 25%, SMA50 25%, SMA200 20%). Les shorts sont taggés si le `short_score` dépasse `min_score_threshold_short`.
- **Option C** : injection directe du `predicted_side` (ternaire long/flat/short) issu de `model_predictions`. Prioritaire sur l'Option B si disponible.
- **min_score_threshold_short** (défaut `0.0`) : seuil minimal de score pour qu'un candidat soit éligible short. Relevable pour restreindre les shorts aux signaux les plus forts.
- **short_max_positions** (défaut `2`) : limite le nombre de positions short simultanées.
- **Capital preservation** : en régime de préservation du capital, les shorts sont automatiquement désactivés (sauf configuration contraire).

La colonne `side` est portée par `CandidateScore` et propagée dans `risk_decisions` et `portfolio_targets`.

### 4.2.quater Concentration trackers (Plan v2 — Sprint 5)

Deux nouveaux trackers side-aware dans `risk_management/concentration.py` :

| Tracker | Rôle |
|---|---|
| `SymbolTradeTracker` | Limite le nombre d'entrées par symbole sur une fenêtre glissante (défaut : 5 trades / 180 jours). Les entrées long et short sont comptabilisées **séparément**. |
| `ConsecutiveLossTracker` | Blackliste temporairement un symbole après N pertes consécutives sur le même side (défaut : 3). Uniquement les pertes **réalisées** (PnL ≤ 0). |

Ces trackers sont utilisables à la fois par le backtest (`backtesting/simulator.py`) et le pipeline live (`risk_management/portfolio_builder.py`).

### 4.2.bis Politique Kelly conditionnelle par tranche

La décision opératoire S6 est désormais explicite :

- **tranches < 25 k$** : `Kelly` reste désactivé dans les presets capital ;
- **tranches ≥ 25 k$** : `Kelly` peut être activé par preset (`risk_enable_kelly` → `enable_kelly_sizing`) ;
- même activé, le sizing Kelly reste encadré par les caps ATR, `max_position_weight` et `effective_min_notional`.

Objectif métier : éviter d'augmenter artificiellement la variance sur les petits comptes, tout en autorisant un sizing plus informatif sur les portefeuilles suffisamment capitalisés et diversifiables.

### 4.3 Conviction score (direction-aware, ML ternaire)

Le score de conviction combine :

- une composante quant (`score_weight`) ;
- une composante ML (`prediction_weight`).

En mode **ternaire** (`num_classes=3`, Plan ML v2), la composante ML est enrichie :
- `predicted_side` ∈ {`long`, `flat`, `short`} — issu de `model_predictions` (colonne ajoutée par la migration 0038)
- `proba_long`, `proba_flat`, `proba_short` — probabilités calibrées par classe
- Le `conviction_score` est **directionnel** : un score long élevé favorise une entrée `buy`, un score short élevé favorise une entrée `sell`

Par défaut, le builder marque `score_source = final_score_sentiment`, ce qui fait du module risk un consommateur direct de la fusion quant + sentiment si elle a déjà été calculée.

> **Phase 5.1.b — Centralisation `core/conviction.py`** :
> la formule est désormais hébergée nativement par `core.conviction.fuse(...)`
> (objet typé `ConvictionWeights`). `risk_management.portfolio_builder.PortfolioBuilder`
> et `event_sentiment.signal_aggregator` consomment la même API.
> Le module `risk_management.conviction` reste exposé en wrapper rétrocompat,
> mais émet désormais un `DeprecationWarning` ; à ne plus utiliser dans le code neuf.

### 4.3.bis Pondérations conviction (40 / 60) et calibration empirique

Convention historique du projet : `score_weight = 0.40`, `prediction_weight = 0.60`
(voir `RiskConfig` et `core.conviction.ConvictionWeights`).

Hypothèses :

- la prédiction ML (probabilité calibrée) est *plus* informative que le score
  quant pur sur l'horizon swing typique 5–15 jours ;
- les poids somment exactement à 1.0 (validation `__post_init__`).

Le `run_summary` expose désormais deux blocs complémentaires :

- `conviction_weights_calibration` pour la traçabilité des calibrations déjà transportées par les candidats ;
- `empirical_risk_calibration` pour la calibration empirique runtime appliquée depuis `weights_calibration_runs`.

Le bloc `conviction_weights_calibration` contient :

- `source` ;
- `calibration_run_id` ;
- `distinct_sources` ;
- `distinct_calibration_run_ids` ;
- `applied_candidates` ;
- `retained_candidates`.

Cela permet de tracer proprement une calibration upstream déjà transportée par
les candidats.

Le bloc `empirical_risk_calibration` contient notamment :

- `run_id` ;
- `metric_name` / `metric_value` ;
- `market_regime_mode` / `requested_market_regime_mode` / `market_regime_fallback_used` ;
- `segment_key` / `requested_segment_key` ;
- `horizon_days` / `lookback_months` ;
- `requested_horizon_days` / `requested_lookback_months` ;
- `eligible_for_live` / `eligibility_reason` / `status` / `fallback_level` ;
- `fallback_reason` / `fallback_journal` / `fallback_policy_source` ;
- `window_start` / `window_end` ;
- `best_weights` avec au minimum `score_weight`, `prediction_weight`, `kelly_fraction_multiplier`, `min_effective_probability`, `assumed_payoff_ratio`.

### 4.3.ter Convention `risk_max_drawdown_pct` par tranche

La monotonie croissante de `risk_max_drawdown_pct` dans `config/capital_presets.yaml` est volontaire :

- **micro / petit compte** : drawdown plus serré pour préserver le capital d'apprentissage ;
- **compte intermédiaire** : convergence progressive vers le profil swing standard ;
- **gros compte** : tolérance plus large, compatible avec un portefeuille plus diversifié et un bruit relatif mieux absorbé.

Ce choix n'est donc pas un relâchement accidentel, mais une convention métier assumée et testée dans la suite des presets capital.

Par défaut, le CLI applique en best-effort le dernier run `weights_calibration_runs`
de `scope = 'risk'` dont `window_end <= trade_date`, en privilégiant le segment
`market_regime_mode` correspondant au régime live courant (`normal`,
`capital_preservation`, `close_only`, `cash_only`) selon une hiérarchie
déterministe et gouvernée :

1. segment exact `(régime, horizon, fenêtre)` ;
2. segment `regime=all` à horizon/fenêtre identiques ;
3. segment du même régime à horizon identique et fenêtre la plus proche ;
4. segment `regime=all` à horizon identique et fenêtre la plus proche ;
5. segment du même régime à fenêtre identique et horizon le plus proche ;
6. segment `regime=all` à fenêtre identique et horizon le plus proche ;
7. segment du même régime le plus proche sur les deux dimensions ;
8. segment `regime=all` le plus proche sur les deux dimensions.

Depuis P3+, cette hiérarchie n'est plus figée en dur : elle peut être surchargée
dans `config.yaml` via `risk_management.empirical_calibration.fallback_levels`.
Si la configuration est absente, invalide ou illisible, le runtime conserve la
politique par défaut ci-dessus et trace la source effective dans
`fallback_policy_source` (`config_yaml`, `defaults`, `defaults_invalid_config`,
`defaults_on_config_error`).

Le runtime conserve également un journal détaillé de résolution :

- `fallback_reason` : raison synthétique humaine (niveau retenu, statut,
  segment demandé, segment résolu, source de politique) ;
- `fallback_journal` : liste ordonnée des niveaux tentés avec, pour chacun,
  le nombre de candidats éligibles, le nombre de candidats bloqués par la
  gouvernance et l'issue (`selected`, `blocked_candidate_available`,
  `no_candidate`).

Les garde-fous de gouvernance restent prioritaires : un segment n'est promu en
live que si `eligible_for_live = true`. Si aucun segment éligible n'est trouvé,
le runtime retourne soit un segment bloqué (`status="blocked_by_governance"`),
soit `None` et revient aux poids statiques de configuration. Le niveau exact de
repli est tracé dans `fallback_level`.

Cela permet de piloter réellement les poids conviction et les paramètres Kelly
clés avec une calibration cohérente du régime marché tout en conservant une
promotion live suffisamment alimentée en données.

Options associées :

```powershell
python -m risk_management.run_risk --disable-empirical-calibration
python -m risk_management.run_risk --empirical-calibration-run-id wcr-20260520-001
python -m risk_management.run_risk --empirical-calibration-horizon-days 5 --empirical-calibration-lookback-months 12
```

Exemple de surcharge YAML :

```yaml
risk_management:
  empirical_calibration:
    fallback_levels:
      - exact_segment
      - regime_all
      - regime_all_nearest_window
      - same_regime_nearest_window
```

Job batch associé :

```powershell
python -m scripts.run_quarterly_weights_calibration --end 2026-05-20 --lookback-months 12
```

### 4.4 Equity effective et dividendes PIT

Le moteur de risque :

- privilégie `account_risk_snapshots` pour l'equity de sizing ;
- fallback sur `broker_account_snapshots` quand nécessaire ;
- fallback final sur `--account-equity` côté CLI/IHM si aucun snapshot exploitable n'est disponible ;
- expose une décomposition best-effort via `broker_account_snapshots`, `broker_positions_snapshots` et `portfolio_cash_ledger`.

Les dividendes ne sont pas lus depuis un module abstrait `corporate_actions`,
mais depuis `portfolio_cash_ledger` avec filtre point-in-time quand la colonne
`created_at` est disponible.

### 4.5 Persistance

Si `--dry-run` n'est pas activé, le module écrit :

- les décisions dans `risk_decisions` ;
- les cibles dans `portfolio_targets`.

### 4.6 `run_summary` risk (Phase 5.1.a → 5.1.c)

Chaque exécution émet une ligne `::alpha_trade_run_summary::{...}` (parsée par
l'IHM). Champs Phase 5 :

| Clé | Description |
|---|---|
| `schema_version` | Version du payload (1, ajoutée Phase 5.1.a). |
| `account_equity_breakdown` | Décomposition de l'equity (cash, settled_cash, long_positions_value, short_positions_value, dividends_ledger, total, source). Source ∈ {`broker_account_snapshots`, `missing`}. |
| `equity_source` / `equity_fallback_used` / `snapshot_freshness_days` | Source effective de l'equity utilisée pour le sizing et niveau de fraîcheur. |
| `regime_snapshot_applied` / `regime_mode` / `regime_snapshot` | Traçabilité du régime live appliqué et des overrides effectifs. |
| `preflight_data_quality` | Contrat best-effort sur equity snapshot, fraîcheur candidats PIT, couverture ATR et matrice de corrélation. |
| `rejection_reason_code_counts` / `reduction_reason_code_counts` | Motifs structurés normalisés jusqu'au payload final. |
| `conviction_weights` | `{score_weight, prediction_weight, source: "core.conviction"}`. Trace l'utilisation de l'API centralisée. |
| `conviction_weights_calibration` | Trace la calibration upstream effectivement transportée (`source`, `calibration_run_id`, listes distinctes, volumes candidats). |
| `empirical_risk_calibration` | Calibration empirique live résolue depuis `weights_calibration_runs` (`run_id`, segment demandé/résolu, statut de gouvernance, `fallback_level`, meilleurs paramètres conviction/Kelly). |
| `shadow_compare` | Résultat optionnel d'un diff du run courant contre un run de référence (`--enable-shadow-compare`). |
| `postmortem_artifacts` | Artefacts enrichis : top rejets/réductions, détail secteur, résumé régime, couverture effective des sources externes. |

### 4.6.b Drifts inter-segments et IHM opérateur

Le job trimestriel `scripts.run_quarterly_weights_calibration` peut persister des
comparaisons inter-segments dans `weights_calibration_segment_drifts`. Deux
comparaisons sont suivies à ce stade :

- `vs_all_same_horizon_window` ;
- `vs_reference_live_segment`.

La page IHM `weights_calibration_runs` expose :

- l'historique des runs segmentés ;
- le statut de promotion live (`eligible_for_live`) ;
- un résumé des drifts par `comparison_kind` ;
- des graphes directionnels (Δ métrique et Δ `final_value`) pour le run sélectionné ;
- une timeline moyenne des drifts quand `compared_at` est disponible ;
- les drifts du run sélectionné ;
- le batch complet trié par ampleur de dérive absolue.

Cette vue sert d'outil de gouvernance opérateur : vérifier qu'un fallback live
plus large reste cohérent avec le segment de référence avant promotion.

Le `run_summary` IHM affiche désormais aussi un journal détaillé des fallbacks
de calibration empirique pour aider à comprendre pourquoi un segment exact a été
ignoré (absence de candidat, segment bloqué par gouvernance, recours à une
fenêtre/horizon plus large, etc.).

L'`account_equity_breakdown` est best-effort : aucune exception ne remonte au
CLI. Si les tables `broker_account_snapshots` / `broker_positions_snapshots` /
`portfolio_cash_ledger` sont absentes, le payload conserve `source="missing"`.

Le bloc `shadow_compare` est lui aussi best-effort :

- `status="disabled"` si l'option n'est pas activée ;
- `status="missing_reference"` si aucun run de référence n'est disponible ;
- `status="compared"` si le rapport a été calculé ;
- `status="unavailable"` si la comparaison ou la persistance a échoué.

---

## 5. Pourquoi peu de positions peuvent être retenues

### 5.1 Peu de candidats au départ

Causes probables :

1. `stock_scores_history` peu alimentée ;
2. pipeline amont non exécuté ;
3. `is_candidate = 1` trop restrictif.

### 5.2 Beaucoup de rejets

Causes probables :

1. filtre de corrélation trop strict ;
2. contraintes portefeuille trop strictes ;
3. prix ou ATR indisponibles ;
4. sizing insuffisant ;
5. circuit breaker actif (voir §5.4 pour le comportement dégradé et le ramp-up).

### 5.3 Composante ML absente

Le module peut continuer même si certaines prédictions ML sont absentes, et
peut même ignorer volontairement `model_predictions` si le `ml_gate` le
désactive. Le `run_summary` et l'IHM exposent cet état explicitement.

### 5.4 Circuit breaker — mode dégradé et ramp-up régimed

Le `CircuitBreaker` (`risk_management/circuit_breaker.py`) protège le compte en
réduisant les allocations quand le drawdown dépasse `max_portfolio_drawdown_pct`.

**Deux modes de dégradation :**

- **Blocage total** (`degraded_entry_allocation_pct = 0.0`) : le trading est suspendu.
- **Mode dégradé** (`degraded_entry_allocation_pct > 0.0`) : les entrées sont
  réduites à la fraction configurée (ex. 10% = positions ~$60 au lieu de ~$600).

**Ramp-up régimed** (quand `regime_ramp_up_enabled = true`) :

Quand le breaker est trippé, l'allocation dégradée de base peut être
progressivement augmentée si les conditions de marché s'améliorent :

| Condition | Effet |
|-----------|-------|
| Régime ≠ `normal` | Streak = 0, allocation = base dégradée |
| Régime = `normal`, equity ≤ veille | Streak gelé, allocation inchangée |
| Régime = `normal`, equity > veille | Streak++, allocation = base + streak × `pct_per_day` (cap `max_pct`) |

**Paramètres** (dans `RiskConfig` et `capital_presets.yaml`) :

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `degraded_entry_allocation_pct` | 0.10 | Allocation de base en mode dégradé |
| `regime_ramp_up_enabled` | `true` | Active le ramp-up |
| `regime_ramp_up_pct_per_day` | 0.025 | Bonus quotidien (+2.5%/jour) |
| `regime_ramp_up_max_pct` | 0.40 | Plafond (40%) |

**Exemple** : breaker trippé, base=10%, régime redevient normal et l'equity remonte :

```
Jour 1 normal + equity ↑ → 12.5%    Jour 5 → 22.5%    Jour 12 → 40% (cap)
Si equity stagne → streak gelé       Si régime dégrade → reset à 10%
```

---

## 6. Vérifications utiles

### Vérifier les dernières décisions de risque

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT run_id, trade_date, symbol, decision, approved_shares, account_id FROM risk_decisions ORDER BY created_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les dernières cibles de portefeuille

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT run_id, trade_date, symbol, shares, weight, account_id FROM portfolio_targets ORDER BY created_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

---

## 7. Tests

### Tests ciblés logique risque

```powershell
python -m pytest tests/test_portfolio_builder.py tests/test_position_sizer.py tests/test_constraints.py tests/test_circuit_breaker.py tests/test_risk_checker.py tests/test_kelly_sizer.py tests/test_risk_shadow_compare.py -q -o addopts=""
```

### Tests CLI et repository

```powershell
python -m pytest tests/test_risk_management_cli.py tests/test_risk_management_run_summary.py tests/test_db_io_v2.py tests/test_risk_regime_apply.py tests/test_position_sizer_telemetry.py -q -o addopts=""
```

### Lint ciblé package risk

```powershell
python -m ruff check risk_management tests/test_risk_management_cli.py tests/test_risk_management_run_summary.py tests/test_risk_shadow_compare.py --output-format concise
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. produire `stock_scores` et `final_score_sentiment` ;
2. produire les prédictions ML si disponibles ;
3. lancer `run_risk` ;
4. vérifier `portfolio_targets` et le `run_summary` risk (régime, preflight, ML gate, equity) ;
5. si besoin, activer `--enable-shadow-compare` pour auditer la dérive par rapport à un run de référence.

### Séquence recommandée

```powershell
python -m event_sentiment.signal_aggregator --trade-date 2026-04-21
python -m modelFactory --mode predict --accelerator auto
python -m risk_management.run_risk --account-equity 100000 --account live1
```
