# Logs Structurés — Audit des fonctions de calcul critique

> **Date** : 2026-06-22
> **Statut** : ⚠️ Partiel — des trous noirs critiques subsistent
> **Verdict** : Le sizing/risk a de bons logs, mais la chaîne de scoring (fusion, neutralisation, corrélation) est majoritairement silencieuse.

---

## 1. La question posée

> *Vos fonctions de score font des calculs critiques en cascade, mais elles ne tracent rien. Si un trade échoue ou qu'une position est sous-dimensionnée, vous aurez beaucoup de mal à débugger. Il manque l'injection d'un logger pour enregistrer le détail.*

---

## 2. Cartographie complète : qui logue, qui ne logue pas ?

### 2.1 Chaîne de scoring (du screener au conviction_score)

| Fonction | Fichier | Niveau de log | Détail |
|---|---|---|---|
| `_percentile_score()` | `screener/pipeline.py` | ❌ Aucun | Utilitaire pure, acceptable |
| `winsorize_and_normalize()` | `selector/factors.py` | ❌ Aucun | Utilitaire pure, acceptable |
| `compute_factor_frame()` | `selector/factors.py` | 🟡 Minimal | `LOGGER.debug` d'entrée seulement. Pas de log des facteurs calculés par symbole, pas d'alerte sur les NaN. |
| `merge_scores()` | `selector/ranking.py` | ❌ **Aucun** | **Trou noir** : fusionne facteurs + scores auxiliaires, calcule `final_score`, applique les poids — zéro trace. |
| `apply_factor_neutralization()` | `selector/ranking.py` | 🟡 Agrégé | `LOGGER.info` des stats globales (univers, secteurs, facteurs). **Pas de détail par secteur** (combien de tickers par secteur, secteurs avec z-score dégénéré). |
| `apply_sector_neutrality()` | `selector/ranking.py` | 🟡 Agrégé | `LOGGER.info` des stats (candidats, cible, plafond). OK. |
| `rank_and_select()` | `selector/ranking.py` | 🟢 Correct | `LOGGER.info` début + fin + top3. Suffisant pour le debug. |
| `apply_regime_weights()` | `selector/regime_scoring.py` | 🟢 Correct | `LOGGER.info` mode + poids + candidats. OK. |
| `merge()` (signal aggregator) | `event_sentiment/signal_aggregator.py` | 🟢 Correct | `LOGGER.info` des stats agrégées (symboles actifs, delta moyen). OK pour le niveau macro. |
| **`compute_conviction()`** | `core/conviction.py` | ❌ **Aucun** | **Trou noir critique** : la fusion quant+ML est le point névralgique. Zéro log. Si ML prédit 0.51 et le quant 0.88, le résultat est 0.66 — mais on ne le saura jamais. |
| **`compute_conviction_short()`** | `core/conviction.py` | ❌ **Aucun** | Idem pour les shorts. |
| **`fuse_sentiment()`** | `core/conviction.py` | ❌ **Aucun** | Fusion ternaire quant+sentiment+macro. Zéro trace. |
| `_vectorized_fuse()` | `backtesting/signal_replay.py` | ❌ **Aucun** | Version vectorisée backtest. Pas de log. |

### 2.2 Chaîne risk management (sizing + contraintes)

| Fonction | Fichier | Niveau de log | Détail |
|---|---|---|---|
| `PositionSizer.compute()` | `risk_management/position_sizer.py` | 🟢 **Excellent** | Log chaque rejet avec raison détaillée (symbole, shares, prix, notional, min). Télémétrie complète. |
| `KellySizer.compute()` | `risk_management/kelly.py` | 🟢 **Excellent** | Log les fallbacks (p_eff trop faible, kelly ≤ 0) et les rejets. |
| `RiskCheckerImpl` | `risk_management/risk_checker.py` | 🟡 Correct | Log de décision, mais pas le détail du calcul. |
| `PortfolioBuilder.build()` | `risk_management/portfolio_builder.py` | 🟢 **Excellent** | Log par étape (breakout filter, score threshold, corrélation, sizing). Progress callback. |
| **`filter_correlated()`** | `risk_management/correlation_filter.py` | ❌ **Aucun** | **Trou noir** : un candidat rejeté pour corrélation → zéro trace dans cette fonction. Le log est fait dans le `PortfolioBuilder.build()` qui appelle, donc indirectement OK. Mais le détail (corrélation calculée, overlap) n'est logué qu'au niveau supérieur. |
| `apply_structural_market_guards()` | `risk_management/regime_apply.py` | ❌ **Aucun** | Applique les garde-fous petit compte. Aucun log de ce qui a été modifié. |

---

## 3. Les 3 trous noirs critiques

### 3.1 🔴 `core/conviction.py` — les 3 fonctions de fusion

```python
# compute_conviction() — AUCUN LOG
def compute_conviction(score_used, predicted_proba, score_weight, prediction_weight):
    if predicted_proba is not None:
        return float(np.clip(score_weight * score_used + prediction_weight * predicted_proba, 0.0, 1.0))
    return float(np.clip(score_used, 0.0, 1.0))
```

**Problème** : Si demain un trade échoue parce que le `conviction_score` est trop bas, vous ne pouvez PAS savoir si c'est à cause du quant (score_used faible) ou du ML (predicted_proba faible). Vous devez re-runner tout le pipeline pour le découvrir.

**Impact** : Tout le debugging post-mortem d'un trade raté ou sous-dimensionné est impossible sans re-exécution.

### 3.2 🔴 `selector/ranking.py` `merge_scores()` — la composition du final_score

```python
# merge_scores() — AUCUN LOG
def merge_scores(computed_df, scores_df, config):
    # winsorize + normalize → [0,1]
    # weight * component → final_score
    # AUCUNE trace de ce qui se passe
```

**Problème** : Si `total_score` est NaN pour 80% des candidats (ex: screener n'a pas tourné), `aux_mask` sera False pour eux → leur `final_score` = trend_vcp seulement. Vous ne le saurez jamais sans inspecter les DataFrames.

### 3.3 🟡 `selector/ranking.py` `apply_factor_neutralization()` — secteurs dégénérés

```python
# apply_factor_neutralization() — log agrégé seulement
LOGGER.info(
    "Neutralisation sectorielle appliquee | univers=%s secteurs=%s facteurs=%s",
    len(result), result["sector"].nunique(), factors_to_neutralize,
)
```

**Problème** : Si un secteur a 1 seul ticker, le z-score est 0.0 pour tout le monde (fallback `sigma < 1e-9`). Le log ne liste PAS les secteurs concernés. Impossible de savoir si la neutralisation a été effective ou dégénérée.

---

## 4. Plan d'action

### Priorité 1 (immédiat) : `core/conviction.py` — la fusion

Ajouter un logger dans les 3 fonctions de fusion avec niveau `DEBUG` :

```python
# core/conviction.py

import logging
LOGGER = logging.getLogger(__name__)

def compute_conviction(
    score_used: float,
    predicted_proba: float | None,
    score_weight: float,
    prediction_weight: float,
) -> float:
    if predicted_proba is not None:
        result = float(np.clip(
            score_weight * score_used + prediction_weight * predicted_proba, 0.0, 1.0
        ))
        LOGGER.debug(
            "conviction_fusion | quant=%.4f (w=%.2f) ml=%.4f (w=%.2f) → conviction=%.4f",
            score_used, score_weight, predicted_proba, prediction_weight, result,
        )
        return result
    LOGGER.debug(
        "conviction_fusion | quant=%.4f (w=%.2f) ml=N/A → conviction=%.4f (ml fallback)",
        score_used, score_weight, float(np.clip(score_used, 0.0, 1.0)),
    )
    return float(np.clip(score_used, 0.0, 1.0))
```

**Même chose pour** `compute_conviction_short()` et `fuse_sentiment()`.

> ⚠️ Attention : `compute_conviction()` est appelée **par candidat** (dans `_build_enriched_candidates`). En mode DEBUG, cela peut générer du volume. Utiliser `LOGGER.debug` (pas info) pour que ce soit désactivable en production.

### Priorité 2 (court terme) : `merge_scores()` — la composition

```python
# selector/ranking.py — merge_scores()

LOGGER.debug(
    "merge_scores | univers=%s aux_dispo=%s aux_manquants=%s",
    len(merged),
    int(aux_mask.sum()),
    int((~aux_mask).sum()),
)
```

Ajouter aussi une alerte `WARNING` si plus de 50% des candidats n'ont pas de scores auxiliaires :

```python
if aux_mask.sum() < len(merged) * 0.5:
    LOGGER.warning(
        "merge_scores | Moins de 50%% des candidats ont des scores auxiliaires "
        "(screener probablement non exécuté). aux_dispo=%s/%s",
        int(aux_mask.sum()), len(merged),
    )
```

### Priorité 3 (court terme) : `apply_factor_neutralization()` — secteurs dégénérés

```python
# selector/ranking.py — apply_factor_neutralization()

# Après le groupby, logger les secteurs avec < 3 tickers
sector_counts = result.groupby("sector").size()
small_sectors = sector_counts[sector_counts < 3]
if not small_sectors.empty:
    LOGGER.info(
        "Neutralisation sectorielle | secteurs_sous_3_tickers=%s (z-score dégénéré → 0.0)",
        dict(small_sectors),
    )
```

### Priorité 4 (moyen terme) : `filter_correlated()` — rejets silencieux

```python
# risk_management/correlation_filter.py

LOGGER.debug(
    "correlation_filter | %s REJETÉ (corr=%.4f > seuil=%.2f avec %s, overlap=%s)",
    sym, corr, threshold, kept_sym, len(pair),
)
```

> Note : le `PortfolioBuilder.build()` logue déjà les rejets au niveau supérieur. Ce log est un complément pour le détail technique.

### Priorité 5 (nice-to-have) : `compute_factor_frame()` — facteurs NaN

```python
# selector/factors.py — compute_factor_frame()

# En fin de fonction, logger les colonnes avec fort taux de NaN
nan_rates = {
    col: latest[col].isna().mean()
    for col in FACTOR_COLUMNS
    if col in latest.columns and latest[col].isna().any()
}
if nan_rates:
    LOGGER.info("compute_factor_frame | colonnes_avec_nan=%s", nan_rates)
```

---

## 5. Synthèse

| Catégorie | Nombre de fonctions | Avec logs | Sans logs | % couvert |
|---|---|---|---|---|
| Scoring / fusion | 9 | 3 | **6** | 33% |
| Sizing / risk | 5 | 4 | 1 | 80% |
| **Total critique** | **14** | **7** | **7** | **50%** |

### Verdict : ⚠️ Partiellement couvert

- ✅ **La chaîne sizing/rejet est bien loguée** : si une position est sous-dimensionnée ou rejetée, vous savez exactement pourquoi (PositionSizer, KellySizer, PortfolioBuilder).
- ❌ **La chaîne scoring/fusion est un trou noir** : si un `conviction_score` est anormal ou un `final_score` aberrent, vous ne pouvez PAS tracer l'origine sans relancer le pipeline en mode debug manuel.

### Les 3 fonctions à logger en priorité absolue :

1. **`core/conviction.py`** — `compute_conviction()`, `compute_conviction_short()`, `fuse_sentiment()` → **0 log aujourd'hui**
2. **`selector/ranking.py`** — `merge_scores()` → **0 log aujourd'hui**
3. **`selector/ranking.py`** — `apply_factor_neutralization()` → log agrégé seulement, **pas de détail par secteur**

---

## 6. Fichiers à modifier

| Fichier | Fonction(s) | Action | Effort |
|---|---|---|---|
| `core/conviction.py` | `compute_conviction`, `compute_conviction_short`, `fuse_sentiment` | Ajouter `LOGGER.debug` | 15 min |
| `selector/ranking.py` | `merge_scores` | Ajouter `LOGGER.debug` + `LOGGER.warning` | 10 min |
| `selector/ranking.py` | `apply_factor_neutralization` | Ajouter log secteurs < 3 tickers | 10 min |
| `risk_management/correlation_filter.py` | `filter_correlated` | Ajouter `LOGGER.debug` par rejet | 5 min |
| `selector/factors.py` | `compute_factor_frame` | Ajouter log colonnes NaN | 10 min |
| `risk_management/regime_apply.py` | `apply_structural_market_guards` | Ajouter log des modifications | 10 min |
| **Total** | | | **~1 heure** |
