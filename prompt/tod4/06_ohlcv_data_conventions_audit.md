# 06 — Audit spécifique OHLCV / Provider / data_adjustment / Corporate Actions / Lineage

Date : mai 2026

---

## 1. Synthèse

La convention de prix et le choix de provider OHLCV sont **globalement cohérents et bien documentés**, avec un effort significatif de mise en cohérence depuis l'audit précédent (tod2). Quelques écarts résiduels persistent entre doc et code, principalement sur le provider news.

**Note OHLCV/Data : 7.5 / 10**

---

## 2. Convention de prix : `data_adjustment = 'split'`

### 2.1 Constat code réel

- `dataIntegrityEngine/import_alpaca_bar.py:35` : `DATA_ADJUSTMENT = "split"`
- `service/eodhd/adapters.py` : `DATA_ADJUSTMENT_SPLIT` et fonction `eodhd_to_split_only()`
- `database/sql/stock/` : contraintes `chk_bars_adj` / `chk_daily_adj` matérialisent cette convention

### 2.2 Constat documentation

- `doc/CONVENTIONS.md` §1 : « Convention de prix : `data_adjustment = "split"` uniquement. »
- `doc/dataIntegrityEngine.md` §8.1 : « Série canonique = `split` »
- `doc/DOC_FONCTIONNELLE.md` §2.9 : « Les barres OHLCV sont ingérées avec `adjustment="split"` »
- `corporate_actions/engine.py:27-42` : « Les **splits** sont déjà neutralisés dans les prix. Les **dividendes** ne sont PAS injectés dans les prix ; ils sont comptabilisés séparément via `portfolio_cash_ledger`. »

### 2.3 Verdict

✅ **COHÉRENT** — La convention `split` est portée de bout en bout : code, configuration DB, documentation, corporate actions. Aucune contradiction détectée.

---

## 3. Provider OHLCV primaire

### 3.1 Constat code réel

- `import_alpaca_bar.py:439-442` : `_resolve_bars_provider()` lit `config.yaml > market_data.bars_provider` (défaut `alpaca` en rétrocompat)
- `import_eodhd_bar.py:88-90` : `resolve_bars_provider()` lit la même clé (défaut `alpaca` aussi)
- Quand `bars_provider == "eodhd"` : `import_alpaca_bar` devient no-op avec `skipped_reason=wrong_provider`
- Quand `bars_provider == "alpaca"` : `import_eodhd_bar` devrait symétriquement être no-op (à vérifier)

### 3.2 Constat documentation

- `doc/CONVENTIONS.md` §1 : « **Provider OHLCV daily primaire** : `EODHD` via `config.yaml > market_data.bars_provider=eodhd`. »
- `doc/data_lineage_matrix.md` : « Provider actif : **EODHD (primaire)** »
- `README.md` §6 : « `bars_provider: eodhd` (**défaut recommandé actuel**) »
- `doc/DOC_FONCTIONNELLE.md` : « Le provider primaire des barres journalières est désormais **EODHD** »

### 3.3 Divergence détectée

⚠️ **ÉCART** : La documentation affirme qu'EODHD est le défaut (`bars_provider=eodhd`), mais le code de fallback dans `import_alpaca_bar.py:441` et `import_eodhd_bar.py:90` retourne `"alpaca"` comme défaut (`.get("bars_provider", "alpaca")`).

- **Code réel** : défaut = `alpaca` si la clé `market_data.bars_provider` est absente de `config.yaml`
- **Documentation** : défaut = `eodhd`

**Impact** : Si l'opérateur ne configure pas explicitement `bars_provider`, le pipeline utilise Alpaca au lieu d'EODHD, contrairement à ce que la doc affirme.

**Recommandation** : Soit modifier le défaut code à `eodhd`, soit aligner la documentation sur le défaut réel `alpaca`. La première option est préférable car EODHD est le provider recommandé.

---

## 4. Provider News

### 4.1 Constat code réel

À vérifier dans `event_sentiment/` :
- Le paramètre `--news-provider` est documenté dans le README comme ayant `eodhd` par défaut
- Mais `doc/DOC_FONCTIONNELLE.md` et `doc/DOC_TECHNIQUE.md` indiquent `alpaca` comme défaut

### 4.2 Divergence détectée

⚠️ **ÉCART MAJEUR** : Incohérence entre README.md et DOC_FONCTIONNELLE.md / DOC_TECHNIQUE.md / CONVENTIONS.md sur le provider news par défaut.

- `doc/CONVENTIONS.md` §2 : « **News provider par défaut** : `alpaca`. »
- `doc/DOC_TECHNIQUE.md` entête : « Provider NEWS par défaut : `Alpaca` »
- `doc/DOC_FONCTIONNELLE.md` entête : « Provider NEWS par défaut : `Alpaca` »
- `README.md` §6 : « `event_sentiment` utilise désormais `eodhd` comme provider news par défaut »

**Recommandation** : Vérifier le code réel de `event_sentiment/__main__.py` ou `event_sentiment/cli.py` pour déterminer le défaut canonique, puis aligner TOUTE la documentation sur cette valeur.

---

## 5. Corporate Actions — cohérence provider

### 5.1 Constat code réel

- `corporate_actions/provider.py` : factory `build_corporate_action_provider()` sélectionne `EodhdCorporateActionProvider` ou `AlpacaCorporateActionProvider` selon `bars_provider`
- Documentation associée : `doc/data_lineage_matrix.md` indique `EODHD (primaire)` pour `corporate_actions_events`

### 5.2 Verdict

✅ **COHÉRENT** — Le provider CA est aligné sur le provider OHLCV (EODHD → EODHD, Alpaca → Alpaca). La documentation reflète ce choix.

---

## 6. Conventions `stock_bars` / `stock_bars_daily` / lineage

### 6.1 Constat code réel

- `stock_bars` : PK `(symbol, timeframe, timestamp)`, stocke les barres brutes
- `stock_bars_daily` : PK `(symbol, date)`, **source unique active** par séance
- Colonne `data_source` : trace l'origine (`eodhd_eod`, `alpaca_iex`)
- Pas de cohabitation multi-provider simultanée possible pour un même `(symbol, date)`

### 6.2 Verdict

✅ **COHÉRENT** — La contrainte de source unique est documentée (`doc/data_lineage_matrix.md`, `doc/dataIntegrityEngine.md` §6.3) et appliquée dans le code. Le lineage est tracé via `data_source`.

---

## 7. Convention `adj_close = close`

### 7.1 Constat code réel

- `dataIntegrityEngine/import_alpaca_bar.py:23` : `DATA_ADJUSTMENT = "split"`
- Pas d'ajustement supplémentaire dans le sanitizeur

### 7.2 Constat documentation

- `doc/dataIntegrityEngine.md` §8.2 : « Dans `stock_bars_daily`, `adj_close` est aujourd'hui **identique** à `close`. Ce n'est pas une erreur : c'est une convention de compatibilité de schéma, puisque l'ajustement split a déjà été fait à l'ingestion. »

### 7.3 Verdict

✅ **COHÉRENT** — La convention est documentée et cohérente avec le choix `split`.

---

## 8. Cohérence Quotes IEX

### 8.1 Constat

- Les quotes viennent toujours d'Alpaca/IEX (pas d'alternative EODHD pour les quotes)
- Le biais IEX est documenté et mesuré via `quote_iex_vs_consolidated_bps`
- `core/filter_profiles.py` : `STRICT_SWING_CASH_FILTERS.max_spread_bps=40` avec extension IEX `max_spread_bps_iex=65`

### 8.2 Verdict

✅ **COHÉRENT** — Le biais IEX est reconnu, mesuré, et compensé par des seuils adaptés. Documentation (`doc/dataIntegrityEngine.md` bandeau IEX) alignée avec le code.

---

## 9. Synthèse des écarts détectés

| # | Écart | Sévérité | Correctif |
|---|---|---|---|
| 1 | Défaut `bars_provider` : doc dit `eodhd`, code dit `alpaca` | P2 | Aligner le défaut code sur `eodhd` |
| 2 | Provider news par défaut : README dit `eodhd`, docs techniques disent `alpaca` | P1 | Vérifier code, aligner toute la doc |
| 3 | `doc/data_lineage_matrix.md` mentionne `model_governance`, `model_metrics_full`, `ml_drift_runs` — tables non confirmées dans le code | P2 | Vérifier l'existence réelle de ces tables |

---

## 10. Recommandations

1. **Uniformiser le défaut `bars_provider` à `eodhd` dans le code** (P2)
2. **Vérifier et documenter le provider news par défaut canonique** (P1)
3. **Vérifier les tables ML listées dans la lineage matrix** (P2)
4. **Ajouter un test de non-régression sur le défaut du provider OHLCV** (P2)
5. **Ajouter un test de non-régression sur la cohérence doc ↔ code pour les providers** (P2)
