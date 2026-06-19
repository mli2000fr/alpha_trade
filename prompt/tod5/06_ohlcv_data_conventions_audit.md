# 06 — OHLCV Data Conventions Audit

> **Audit spécifique des conventions de données OHLCV, provider, data_adjustment, corporate actions et lineage**

---

## 1. Provider OHLCV primaire actuel

**Constats** :
- Provider primaire : **EODHD** (bulk EOD consolidé)
- Configuré dans `config.yaml › market_data.bars_provider: eodhd`
- Le code source confirme : `dataIntegrityEngine/import_eodhd_bar.py` est le point d'entrée nominal
- `dataIntegrityEngine/import_alpaca_bar.py` produit un no-op explicite quand `bars_provider != 'alpaca'` (`skipped_reason=wrong_provider`, ligne 613)
- Le helper `bar_importer_common.resolve_bars_provider()` lit `config.market_data.bars_provider` avec fallback `'alpaca'` pour la rétrocompatibilité

**Verdict** : ✅ **Cohérent et bien implémenté**

---

## 2. Convention de prix : `data_adjustment = 'split'`

**Constats** :
- Convention canonique : `data_adjustment = 'split'` (splits neutralisés dans les prix, dividendes NON injectés)
- `dataIntegrityEngine/import_alpaca_bar.py:35` : `DATA_ADJUSTMENT = "split"`
- `service/eodhd/adapters.py` : `DATA_ADJUSTMENT_SPLIT` — reconstruction split-only depuis les données EODHD
- Contrainte SQL : `CHECK chk_bars_adj` sur `stock_bars`, `CHECK chk_daily_adj` sur `stock_bars_daily` (cf. `doc/database.md` §9)
- `corporate_actions/engine.py` : « Ce module NE TOUCHE PAS aux tables stock_bars / stock_bars_daily »

**Cohérence avec le reste du pipeline** :
- Backtesting : lit `stock_bars_daily.close` → les splits sont déjà neutralisés ✅
- Risk management : sizing ATR basé sur `stock_bars_daily` → cohérent ✅
- Performance totale = `MTM(positions, close) + cumulative(portfolio_cash_ledger)` → documenté et cohérent ✅

**Verdict** : ✅ **Cohérent, robuste, bien documenté**

---

## 3. Switch de provider

**Constats** :
- Le switch est **explicite** : l'opérateur change `market_data.bars_provider` dans `config.yaml` ou via l'IHM Paramètres
- **Pas de fallback automatique** : le flag `fallback_on_failure` a été supprimé (S0)
- En cas d'échec du provider actif, le run échoue (comportement documenté et assumé)
- L'IHM lit le provider actif via `_resolve_bars_provider_for_ihm()` (`ihm/services/pipeline_runner.py`)

**Verdict** : ✅ **Cohérent et sécurisé** (pas de bascule silencieuse dangereuse)

---

## 4. Conventions `data_source`

**Constats** :
- `stock_bars_daily.data_source` trace l'origine : `eodhd_eod` (mode défaut), `alpaca_iex` (rétrocompat)
- PK `(symbol, date)` → **source unique active** par séance
- Le backtesting filtre explicitement sur `data_source='eodhd_eod'`
- La doc (`data_lineage_matrix.md`) documente cette limitation

**Risque identifié** : Si un jour on veut cohabiter deux sources, il faudra une migration de schéma. Mais ce n'est pas le cas aujourd'hui.

**Verdict** : ✅ **Cohérent**, avec une limitation documentée

---

## 5. Cohérence Provider CA ↔ Provider OHLCV

**Constats** :
- La factory `corporate_actions.provider.build_corporate_action_provider()` sélectionne :
  - `EodhdCorporateActionProvider` si `bars_provider='eodhd'`
  - `AlpacaCorporateActionProvider` sinon
- La doc (`corporate_actions.md`, `data_lineage_matrix.md`) documente ce lien

**Verdict** : ✅ **Cohérent**

---

## 6. Qualité des données

### EODHD (primaire)

| Aspect | Qualité |
|---|---|
| Volume | Proxy consolidé US → acceptable ✅ |
| OHLC large caps | Bon ✅ |
| OHLC small caps | Bon ✅ |
| Spreads/Quotes | Non concerné (les quotes restent sur Alpaca) |

### Alpaca IEX (rétrocompat)

| Aspect | Qualité |
|---|---|
| Volume | Sous-évalué x30-50 ❌ |
| VWAP | Peu fiable ❌ |
| Spreads quotes | ~50 bps vs NBBO ⚠️ |
| OHLC large caps | OK ✅ |
| OHLC small caps | ±1-3% ⚠️ |

### Compteurs IEX

Les compteurs `symbols_zero_volume_30d`, `stale_quote_pct`, `stale_market_cap_pct` sont propagés dans les `run_summary` — bonne pratique. ✅

---

## 7. Incohérences détectées

### 7.1 Aucune incohérence majeure sur les conventions de prix
La convention `data_adjustment='split'` est remarquablement bien appliquée de bout en bout : ingestion, sanitizer, backtesting, risk, corporate actions. C'est un point fort du projet.

### 7.2 Step 1 IHM : `import_alpaca_bar` vs `import_eodhd_bar`
- L'IHM affiche `1. import_alpaca_bar` comme étape du workflow quotidien
- En mode `bars_provider=eodhd`, c'est `import_eodhd_bar` qui devrait être l'étape 1
- Heureusement, `import_alpaca_bar` est no-op en mode EODHD, donc le pipeline ne casse pas, mais le labelling IHM est trompeur

**Verdict** : ⚠️ **Écart mineur** — l'IHM devrait refléter le provider actif

### 7.3 Cohérence `bars_provider` ↔ documentation
- `doc/dataIntegrityEngine.md` §4.2 mentionne `python -m dataIntegrityEngine.import_eodhd_bar --write` comme commande nominale → cohérent ✅
- `DOC_FONCTIONNELLE.md` §1.3 mentionne l'ingestion depuis EODHD → cohérent ✅
- Le bandeau IEX dans `doc/dataIntegrityEngine.md` précise bien qu'il ne s'applique que si `bars_provider='alpaca'` → cohérent ✅

---

## 8. Recommandations

1. **Corriger le labelling IHM** : afficher `import_eodhd_bar` quand `bars_provider=eodhd`
2. **Ajouter un test de non-régression** qui vérifie que la convention `data_adjustment='split'` est respectée dans tous les importeurs
3. **Surveiller la disponibilité EODHD** : ajouter un healthcheck proactif avant le pipeline quotidien
4. **Documenter la procédure de switch de provider** dans le runbook opérateur

---

## 9. Verdict global OHLCV

| Critère | Note |
|---|---|
| Cohérence de la convention de prix | 9/10 |
| Robustesse du provider switch | 8/10 |
| Qualité des données (EODHD) | 8/10 |
| Traçabilité (data_source, lineage) | 8/10 |
| Documentation des conventions | 8/10 |
| Alignement IHM sur le provider actif | 6/10 |

**Note OHLCV / Data Conventions : 7.8/10** — **Solide**, avec un point d'amélioration sur l'IHM.
