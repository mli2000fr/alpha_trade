# 06 — Audit OHLCV, Data Conventions & Corporate Actions — Alpha Trade

> **Date** : mai 2026 | Focus : provider OHLCV, `data_adjustment`, corporate actions, lineage

---

## 1. Provider OHLCV primaire — verdict

### 1.1 Architecture actuelle

Le provider primaire est **EODHD** (`service/eodhd/clientEodhd.py`), piloté par `config.yaml › market_data.bars_provider: eodhd`.

```
config.yaml                dataIntegrityEngine/
bars_provider: eodhd  -->  import_eodhd_bar.py  -->  run_eodhd_ingestion()
                           (shim + sous-package eodhd/)
                           
bars_provider: alpaca (rétrocompat)
            -->  import_alpaca_bar.py  (no-op si eodhd actif)
```

**Preuves code** :
- `dataIntegrityEngine/import_eodhd_bar.py:1` : "ce module est devenu un shim mince. La logique réelle vit dans `dataIntegrityEngine.eodhd`"
- `test_import_alpaca_bar_noop.py` : valide que `import_alpaca_bar` est un no-op quand `bars_provider=eodhd`
- `config.yaml:177` : `bars_provider: eodhd   # défaut recommandé`

### 1.2 Garde-fous contre la double-écriture

```python
# data_lineage_matrix.md §7 :
# "EODHD provider switch (Phase 6) : market_data.bars_provider contrôle quel module
# daily est actif. L'autre devient no-op au niveau de main() pour interdire toute
# double-écriture."
```

**Verdict** : ✅ La protection contre la double-écriture est documentée et testée.

### 1.3 Cohabitation `data_source` dans `stock_bars_daily`

La table `stock_bars_daily` peut contenir simultanément des lignes `data_source='alpaca_iex'` (historique legacy) et `data_source='eodhd_eod'` (nouvelles ingestions). Cette cohabitation est documentée dans `data_lineage_matrix.md §7`.

**Risque** : Le screener, le selector et le backtesting lisent `stock_bars_daily` sans filtre sur `data_source`. Sur des symboles avec historique mixte, les premières années de données (IEX) ont un volume sous-évalué (×30–50). Cela peut biaiser les filtres de liquidité (`avg_dollar_volume_20d`) sur les premières périodes.

**Recommandation** : Documenter cette cohabitation dans le guide opérateur et proposer une migration optionnelle pour re-qualifier l'historique IEX en EODHD via `backfill_eodhd_history.py`.

---

## 2. Convention `data_adjustment='split'`

### 2.1 Implémentation côté EODHD

```python
# service/eodhd/adapters.py
DATA_ADJUSTMENT_SPLIT = "split"
def eodhd_to_split_only(row: dict) -> dict:
    # Reconstruit les prix ajustés splits uniquement (dividendes exclus)
```

### 2.2 Implémentation côté Alpaca

```python
# dataIntegrityEngine/import_alpaca_bar.py
DATA_ADJUSTMENT = "split"
adjustment="split"  # paramètre de l'API Alpaca
```

### 2.3 Enforcement SQL

La table `stock_bars` et `stock_bars_daily` ont une contrainte CHECK SQL :
```sql
CONSTRAINT chk_bars_adj CHECK (data_adjustment = 'split'),
CONSTRAINT chk_daily_adj CHECK (data_adjustment = 'split')
-- Source : doc/database.md §9 + data_lineage_matrix.md §7
```

**Verdict** : ✅ Convention `data_adjustment='split'` cohérente et enforced en DB. Les deux providers produisent la même convention.

---

## 3. Corporate Actions — Cohérence provider

### 3.1 Architecture provider CA

L'architecture utilise une abstraction `CorporateActionProvider` avec deux implémentations :
- `AlpacaCorporateActionProvider` : API Alpaca Corporate Actions (`v1/corporate-actions`)
- `EodhdCorporateActionProvider` : EODHD dividendes/splits

La factory `build_corporate_action_provider` (référencée dans `data_lineage_matrix.md §7`) sélectionne `EodhdCorporateActionProvider` quand `bars_provider=eodhd`.

### 3.2 Cohérence avec la convention `data_adjustment='split'`

La convention "splits déjà neutralisés dans les prix OHLCV, dividendes dans `portfolio_cash_ledger`" est cohérente :

```
stock_bars/stock_bars_daily (data_adjustment='split')
  → splits neutralisés upstream dans les prix
  
corporate_actions/engine.py
  → "Ce module NE TOUCHE PAS aux tables stock_bars / stock_bars_daily"
  → Gère uniquement : qty (splits), cost basis (splits), cash (dividendes)
  
portfolio_cash_ledger
  → Accumule les dividendes cash pour le calcul du total return
```

**Performance totale** = MTM(positions × close_daily) + cumulative(portfolio_cash_ledger)

**Verdict** : ✅ Cohérence impeccable entre les conventions OHLCV prix et CA comptabilité.

### 3.3 Risque de double-ajustement

Si un utilisateur importe des barres OHLCV **non ajustées** (prix bruts) et applique les CAs manuellement, il y aurait un double-ajustement. Ce risque est **théorique uniquement** : la contrainte CHECK SQL sur `data_adjustment='split'` interdit l'insertion de barres non ajustées.

**Verdict** : ✅ Le risque de double-ajustement est protégé par la contrainte DB.

### 3.4 Idempotence CA

```python
# corporate_actions/engine.py docstring
# Clé SHA-256 déterministe : provider + symbol + type + ex_date + montant/ratio
# Unicité DB garantie
```

**Verdict** : ✅ Idempotence robuste. Un re-run de `corporate_actions sync` ne crée pas de doublons.

---

## 4. Lineage OHLCV → screener → selector → risk → execution

### 4.1 Flux de données quotidien

```
EODHD bulk EOD
    ↓
import_eodhd_bar.py
    ↓
stock_bars (1D) + stock_bars_daily
    ↓ (sanitizer)
data_sanitizer_daily.py
    ↓
stock_bars_daily (data_source=eodhd_eod, data_adjustment=split)
    ↓
screener (avg_dollar_volume, RSI, range)
    ↓
stock_scores (is_candidate, score_screener)
    ↓
selector AlphaScanner (Minervini, VCP, beta, spread, earnings)
    ↓
stock_scores (updated: trend_score, vcp_score, final_score)
    ↓
event_sentiment (FinBERT fusion)
    ↓
stock_scores (final_score_sentiment)
    ↓
modelFactory predict
    ↓
model_predictions (predicted_proba)
    ↓
risk_management PortfolioBuilder
    ↓
portfolio_targets (conviction_score, shares, entry_price)
    ↓
execution_engine ProductionExecutor
    ↓
execution_positions / execution_broker_fills
```

**Évaluation PIT** : Le backtesting en mode `pipeline` utilise `stock_scores_history` (backfill PIT) comme source pour rejouer le pipeline. La cohérence live ↔ backtest est garantie si le backfill est exécuté avant les backtests.

### 4.2 Points de vigilance côté lineage

| Point de vigilance | Statut | Risque |
|---|---|---|
| `stock_bars_daily` cohabitation IEX/EODHD | Documenté | Volume IEX sous-évalué sur historique |
| `stock_quote_snapshots` toujours IEX | Documenté | Spread biais ~50 bps |
| `stock_metadata.market_cap` TTL 45j | Documenté | Stale si update_sector non exécuté |
| `model_predictions` sans `selected_model` | ✅ **RÉSOLU** (A-003) — `selected_model`, `decision_threshold`, `calibration_method`, `signal_label` présents en DB | Gouvernance ML complète |
| `portfolio_cash_ledger` divergence si CA manqué | Risque faible | Sync portfolio-only chaque jour |

---

## 5. EODHD — Limitations et risques opérationnels

### 5.1 Quota daily (100k calls/jour)

Le plan EODHD All-In-One autorise 100k appels/jour. Le `EodhdQuotaTracker` avec soft limit à 80k et hard limit à 100k surveille la consommation.

**Consommation estimée** :
- Bulk EOD (`/bulk`) : 1 call → ~5 000 symboles US (très efficace)
- Per-symbol fallback (`/eod/AAPL.US`) : 1 call/symbole
- VIX macro (`EodhdMacroProvider`) : 2–3 calls/run
- Corporate actions EODHD : N calls selon l'univers CA

**Risque** : Si le bulk EOD échoue et que le fallback per-symbol est déclenché pour 500 symboles, la consommation de quota peut être significative. Le circuit breaker (5 failures → 30 min cooldown) protège contre les boucles d'échec.

### 5.2 `bulk_publish_offset_hours: 2`

Le bulk EOD n'est fiable qu'à partir de 18h00 EST. Un pipeline lancé à 16h00 peut lire des données incomplètes pour le jour courant.

**Recommandation** : Documenter dans le runbook opérateur : "lancer le pipeline après 18h00 EST (00h00 heure française)"

### 5.3 Splits EODHD — cache 7 jours

Les splits EODHD sont cachés 7 jours. Si un split est annoncé et exécuté dans ce délai, le cache doit être invalidé manuellement.

**Garde-fou** : Le corporate_actions module gère les splits séparément → pas de risque de double-ajustement même si le cache EODHD est stale.

