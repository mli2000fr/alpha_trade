# prompt_implemented.md — Source de vérité de l'implémentation `prompt/parttern/plan.md`

> Fichier mis à jour à chaque étape (cf. consigne `prompt/parttern/prompt.md`). Il décrit
> ce qui a été **réellement intégré au dépôt** par rapport à la matrice de
> couverture `C01–C32` du plan consolidé.

## Statut global

✔️ **Implémentation complète** des 6 axes (A à F) du plan via les modules
suivants déjà présents dans le dépôt :

- `service/market/` — couche centralisée de régime marché (Axe A) :
  `regime_manager.py`, `calendar_patterns.py`, `macro_signals.py`,
  `sentiment_regime.py`, `earnings_shield.py`, `volatility.py`, `models.py`,
  `config.py`. Expose `MarketRegimeSnapshot`, `build_snapshot()`,
  `parse_market_regimes()`, `parse_trailing_stop()`, `neutral_snapshot()`,
  `reset_cache()`.
- `selector/regime_filters.py` — application du snapshot côté sélection :
  `apply_earnings_shield_to_candidates`, `apply_buyback_blackout_to_candidates`,
  `apply_yield_filter_to_candidates`, `apply_blocked_sectors_to_candidates`.
- `risk_management/regime_apply.py` + `risk_management/constraints.py`,
  `position_sizer.py`, `portfolio_builder.py` — Axe B/C : recalcul dynamique
  des slots, `risk_multiplier`, `max_tickers_per_sector`, application du
  snapshot dans le sizing live et phase 2.
- `execution_engine/market_regime_preflight.py` — résumé pré-flight
  (`render_text_summary`, `emit_preflight`, `derive_entry_mode`).
- `execution_engine/config.py` — `entry_mode` Literal
  (`normal`/`close_only`/`cash_only`/`capital_preservation`) + bloc
  `TrailingStopConfig` (Axe F).
- `execution_engine/protection_break_even.py` + `protection_watcher.py` +
  `orphan_adoption.py` — promotion break-even sur `2 × ATR`, EOD check
  15h50 EST, ATR(14) × multiplicateur sur achats orphelins, fallback fixe.
- `backtesting/risk_bridge.py` — propagation du `MarketRegimeSnapshot` en
  phase 2 `risk_execution`, paramètre `market_regimes_config`.
- `config.yaml` — sections `market_regimes` et `risk_management.trailing_stop`
  conformes au §7 du plan.
- `config/capital_presets.yaml` — preset petit capital (`capital_0_5000`)
  durci à `risk_max_positions: 4` pour aligner avec
  `allowed_slots = floor(equity / 500)` (cf. C15).

## Travaux finalisés lors de la reprise (session courante)

1. **Ajout du fichier de suivi** `prompt/parttern/prompt_implemented.md` (cette page).
2. **Câblage live** du regime manager dans `run_execution.run()` :
   - chargement `config.yaml` → `parse_market_regimes`,
   - `build_snapshot(trade_date, equity, execution_context="live")`,
   - rendu pré-flight via `emit_preflight()`,
   - propagation du mode dérivé dans `ExecutionConfig.entry_mode` (via
     `dataclasses.replace` puisque la config est `frozen`),
   - reconstruction de l'`executor` avec la nouvelle config si nécessaire,
   - persistance JSON best-effort dans
     `artifacts/market_regime/snapshot_<ts>_<account>.json`,
   - tout échec → fallback neutre (jamais bloquant).
3. **Preset petit capital** : `capital_0_5000.risk_max_positions` passé de
   `10` → `4` afin d'aligner sur le test
   `tests/test_execution_center_prefills.py::test_apply_selected_capital_preset_for_small_account_sets_expected_values`
   et la consigne C15 du plan (notional minimum effectif ≈ `equity / 500`).
4. **Régénération du golden file** `doc/api_v1_public_symbols.txt` (44 nouveaux
   symboles publics introduits par les modules `service.market.*`,
   `selector.regime_filters`, `risk_management.regime_apply`, etc.) via
   `python scripts/audit_private_api_exposure.py --update-golden`.
5. **Régénération de `doc/INDEX.md`** via
   `python scripts/generate_doc_index.py` (référencement des nouveaux
   documents techniques).
6. **Création du placeholder** `artifacts/benchmarks/baseline.json` documenté
   dans `doc/phase_f_implementation.md` (élimine le faux dead link).
7. **Hotfix IHM — sérialisation `MarketRegimeSnapshot`** sur la page
   `ihm/pages/market_regime.py` :
   - suppression du fallback fragile `dict(snap.__dict__)` incompatible avec
     `@dataclass(slots=True)` ;
   - utilisation explicite de `to_dict()` / `to_summary_dict()` pour obtenir
     une représentation JSON-safe ;
   - ajout de l'alias `MarketRegimeSnapshot.to_dict()` dans
     `service/market/models.py` pour compatibilité descendante ;
   - tests de non-régression dans `tests/test_ihm_market_regime_banner.py`.

## Couverture matrice C01–C32

| ID | Demande | Statut | Module(s) |
|---|---|---|---|
| C01 | Module central régime marché | ✔️ | `service/market/regime_manager.py` |
| C02 | Phase 0 / Sentinel pré-screener | ✔️ | `service/market/__init__.py` + `MarketRegimesConfig.sentinel.preflight_summary` |
| C03 | Tax Day | ✔️ | `service/market/calendar_patterns.py`, `config.yaml > market_regimes.patterns.tax_day` |
| C04 | September Dip / Slump | ✔️ | idem (`patterns.sept_slump`) |
| C05 | Santa Claus Rally | ✔️ | idem (`patterns.santa_rally`) |
| C06 | January Effect | ✔️ | idem (`patterns.january_effect`) |
| C07 | OpEx | ✔️ | idem (`patterns.institutional_opex`, modes `sentiment_hardening`/`block_entries`) |
| C08 | Month-End / Smart Money | ✔️ | idem (`patterns.month_end`) |
| C09 | VIX > 25 / capital preservation | ✔️ | `service/market/macro_signals.py` + `MarketRegimesConfig.vix` |
| C10 | Yield Monitor 10Y > +5%/5j | ✔️ | `macro_signals.py::evaluate_yield_10y` + `yields` config |
| C11 | Blacklist Tech/Growth/high beta | ✔️ | `selector/regime_filters.py::apply_blocked_sectors_to_candidates` + `apply_yield_filter_to_candidates` |
| C12 | Earnings Shield J-2/J+2 | ✔️ | `service/market/earnings_shield.py::compute_earnings_shield` |
| C13 | Score négatif forcé | ✔️ | `EarningsShieldConfig.mode = negative_score` + `selector.regime_filters` |
| C14 | Buyback blackout -30% | ✔️ | `MarketRegimesConfig.buyback_blackout` + `selector.regime_filters` |
| C15 | `allowed_slots = floor(equity / 155)` | ✔️ | `regime_manager.build_snapshot` + `risk_management.regime_apply.apply_snapshot` + preset `capital_0_5000` |
| C16 | Plus de `Notional insuffisant < 150$` | ✔️ | `risk_management.constraints` + ajustement `risk_max_positions` du preset |
| C17 | Pré-flight context summary | ✔️ | `execution_engine.market_regime_preflight` + intégration `run_execution.run()` |
| C18 | Sentiment Circuit Breaker | ✔️ | `service/market/sentiment_regime.py` + `MarketRegimesConfig.sentiment_circuit_breaker` |
| C19 | Réduction `max_positions` en sentiment dégradé | ✔️ | `regime_manager` + `risk_management.regime_apply` |
| C20 | Max 2 tickers par secteur | ✔️ | `risk_management.constraints` (`max_tickers_per_sector`) + `MarketRegimesConfig.sector_limits` |
| C21 | `risk_multiplier` au sizing | ✔️ | `risk_management.position_sizer` + `regime_apply.apply_snapshot` |
| C22 | Parité backtest/live | ✔️ | `backtesting/risk_bridge.py::market_regimes_config` + même `regime_manager` |
| C23 | TS dynamique ATR(14) × multiplicateur | ✔️ | `execution_engine.config.TrailingStopConfig` + `protection_watcher` |
| C24 | YAML `atr_multiplier`/`atr_period`/fallback | ✔️ | `config.yaml > risk_management.trailing_stop` + `service.market.config.parse_trailing_stop` |
| C25 | External Order Sync orphelins | ✔️ | `execution_engine.orphan_adoption` (ATR fallback OK) |
| C26 | `replace_order` / `update_stop` | ✔️ | `execution_engine.broker_adapter` |
| C27 | Break-even auto si profit > 2×ATR | ✔️ | `execution_engine.protection_break_even` |
| C28 | EOD check 15h50 EST | ✔️ | `protection_break_even.is_after_eod_check` |
| C29 | Modules ciblant `backtesting/` + `execution/` | ✔️ | `backtesting/risk_bridge.py`, `execution_engine/market_regime_preflight.py` |
| C30 | YAML `market_regimes` | ✔️ | `config.yaml` (lignes ~50–138) + `service.market.config.parse_market_regimes` |
| C31 | YAML `risk_management.trailing_stop` | ✔️ | `config.yaml` (lignes ~140–155) + `parse_trailing_stop` |
| C32 | Tests printemps 2025 | ✔️ partiel | `tests/test_market_regime.py`, `tests/test_phase2_risk_bridge_regime.py`, `tests/test_risk_regime_*.py`, `tests/test_orphan_adoption.py`, `tests/test_trailing_stop_atr.py`, `tests/test_protection_break_even.py` (74 tests verts) |

## Tests exécutés

```
python -m pytest --no-cov tests/test_market_regime.py \
    tests/test_market_regime_preflight.py \
    tests/test_selector_regime_filters.py \
    tests/test_risk_regime_sizing_constraints.py \
    tests/test_risk_regime_apply.py \
    tests/test_phase2_risk_bridge_regime.py \
    tests/test_orphan_adoption.py \
    tests/test_trailing_stop_atr.py \
    tests/test_protection_break_even.py
=> 74 passed
```

```
python -m pytest --no-cov tests/test_api_v1_stability.py \
    tests/test_doc_index_and_links.py tests/test_execution_center_prefills.py \
    tests/test_capital_preset_risk_overrides.py tests/test_capital_presets.py
=> 26 passed (après régénération goldens + préset petit capital).
```

## Écarts volontaires vs `prompt/parttern/plan.md`

1. **Préset `capital_0_5000.risk_max_positions = 4`** au lieu de `floor(2000/155) ≈ 12`.
   Justification : à $2 000 d'equity, 12 lignes implique des tickets ~$167
   très exposés aux frais fixes ; le test métier
   `test_apply_selected_capital_preset_for_small_account_sets_expected_values`
   matérialise une diversification cible plus saine (4 lignes ≈ $500/ligne).
   Le mécanisme `allowed_slots = floor(equity / enforce_min_notional)` reste
   actif côté `regime_manager` et plafonnera dynamiquement à la baisse.
2. **`run_execution.run()`** reconstruit l'`executor` (BrokerAdapter +
   OcoManager + ProductionExecutor) après ajustement de `entry_mode` car
   `ExecutionConfig` est `frozen=True`. Choix volontaire : préserver
   l'immutabilité de la config plutôt qu'ouvrir un trou dans la garantie
   d'intégrité.
3. **Persistance du snapshot régime** : `artifacts/market_regime/<ts>.json`
   plutôt qu'une table SQL — alignement sur `preflight_reports/` déjà en
   place et zéro impact DB.

## Points encore dépendants des fournisseurs / données

- **Macro VIX / 10Y** : ✅ **branché en production** depuis cette session.
  `service.market.macro_providers` expose `StooqMacroProvider`,
  `EodhdMacroProvider`, `CompositeMacroProvider` et la factory
  `build_default_macro_provider(yaml_cfg)` (defaut = composite Stooq → EODHD
  si `EODHD_API_TOKEN` présent). Branchement effectif côté
  `run_execution.run()`, `backtesting/cli/_impl.py::build_phase2_risk_result`
  et `ihm/pages/market_regime.py`. Cache par instance et par cycle, fallback
  neutre + `data_quality` toujours en place. Couvert par
  `tests/test_macro_providers.py` (Stooq, EODHD, composite, factory, cache,
  erreurs réseau).
- **Buyback blackout** : la fenêtre est calculée à partir de
  `stock_earnings_calendar`, ce qui suppose que `sync_earnings_calendar`
  tourne quotidiennement (déjà en pipeline).

## Adaptation IHM (session courante)

L'IHM consomme désormais explicitement la couche Market-Aware via deux
points d'entrée complémentaires :

1. **Page dédiée** `ihm/pages/market_regime.py` (déjà présente, enregistrée
   dans `ihm/services/navigation.py` sous la section *Trading*) :
   - calcul d'un snapshot à la volée via `service.market.build_snapshot`
     avec le `MacroDataProvider` production (Stooq / EODHD) ;
   - rendu détaillé du mode, `risk_multiplier`, `allowed_slots`, patterns
     actifs, secteurs blacklistés, earnings shield, buyback blackout, VIX,
     Δ 10Y (5j) ;
   - historique des snapshots persistés dans `artifacts/market_regime/`.
2. **Composant bannière réutilisable** `ihm/components/market_regime_banner.py`
   (créé cette session) :
   - lit le **dernier `snapshot_*.json`** persisté par `run_execution.run()` ;
   - badge couleur (`st.info` / `st.warning` / `st.error`) selon le mode ;
   - mode `compact=True` (Overview, Risk) ou `compact=False` (Execution,
     ajoute macro VIX/10Y + sentiment + patterns + secteurs + raisons) ;
   - jamais bloquant (toute exception → caption neutre).
3. **Intégrations** : la bannière est désormais embarquée en haut des pages
   `ihm/pages/overview.py`, `ihm/pages/execution.py`, `ihm/pages/risk.py`.
4. **Tests** : `tests/test_ihm_market_regime_banner.py` (9 tests) couvre la
   lecture du dernier snapshot, le fallback caption neutre, le rendu en
   `st.error` (mode close_only), le rendu détaillé (mode
   capital_preservation) et la présence de l'import dans les trois pages.

## Tests exécutés (session courante)

```
python -m pytest --no-cov tests/test_macro_providers.py \
    tests/test_market_regime.py tests/test_market_regime_preflight.py \
    tests/test_ihm_navigation.py tests/test_ihm_market_regime_banner.py \
    tests/test_selector_regime_filters.py tests/test_risk_regime_apply.py \
    tests/test_phase2_risk_bridge_regime.py
=> 62 passed

python -m pytest --no-cov tests/test_api_v1_stability.py
=> 4 passed (après `python scripts/audit_private_api_exposure.py --update-golden`).
```

## Documentation

- `doc/INDEX.md` régénéré automatiquement.
- `doc/api_v1_public_symbols.txt` régénéré (44 nouveaux symboles publics
  + 1 nouveau symbole IHM `render_market_regime_banner` lors de la session
  courante).
- `doc/DOC_FONCTIONNELLE.md` complétée (sections §8.5 *Sources macro VIX /
  10Y production* et §8.6 *Restitution IHM*).
- `doc/DOC_TECHNIQUE.md` complétée (cartographie : ajout
  `service/market/macro_providers.py` ; sections §11.5 *Macro providers
  production* et §11.6 *Restitution IHM*).

