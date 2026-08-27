# DirectionalDataResearch — Recherche de données directionnelles

> Suite à la clôture de `GlobalDirection` (**NO-GO** : direction non observable avec
> les 182 features actuelles), cette branche cherche de **nouvelles familles de
> données signées** capables de séparer les futurs mauvais longs (D1-D5) des bons
> longs (D6-D10) dans le pool Oracle TOP20%.

## Discipline (avant tout modèle)

Pour chaque nouvelle feature à J, dans le pool Oracle TOP20% :
- IC Spearman(feature, décile futur) ;
- AUC(D1-D5 vs D6-D10) et AUC(D1-D3 vs D8-D10) ;
- par fold / année / régime ; stabilité du signe par fold ;
- `direction_separability` vs `amplitude_separability` (ne pas réapprendre Oracle).

**Une famille ne passe au modèle multivarié QUE si plusieurs features montrent un
signal directionnel OOS stable.**

## Module

`modelFactory/directional_data_research/` :
- `harness.py` : `assemble_pool()` (pool Oracle TOP20% + labels décile/rendement +
  fold/année/régime) et `analyze_features()` (batterie de séparabilité) —
  réutilisable pour toute famille.
- `earnings_revisions.py` : famille 1 (estimate/earnings revisions).

Priorité : estimate/earnings revisions → news sentiment → options skew →
short interest / analyst revisions / insiders → premarket/flux directionnels PIT.

## Famille 1 — estimate/earnings revisions (2026-08-26)

Source : `stock_fundamentals_daily`. **Constats :**

- **GAP de données** : `eps_estimate_current` / `eps_estimate_next` = **0 ligne
  non-nulle** sur toute la table (194 755 lignes, 2009-2026) → `est_revision`
  (révision d'estimation signée, la feature prioritaire) **impossible à calculer**.
- Proxies disponibles (trailing) : `eps_growth_yoy` (IC −0.0007, AUC_dir 0.500 =
  bruit), `revenue_growth_yoy` (IC −0.045, AUC_dir 0.482 = **anti-direction**,
  signe stable), `eps_to_price` (IC −0.017, AUC_dir 0.493, faible anti).

**Verdict famille 1 : NON TESTABLE en l'état** (données estimates absentes) ; les
proxies trailing ne portent aucun signal directionnel utile.

## Famille 2 — news sentiment événementiel (2026-08-26)

`modelFactory/directional_data_research/news_sentiment.py` → `artifacts/directional_data_research_news.csv`.
Source : `news_ticker_sentiment` (FinBERT) JOIN `news_raw` (date PIT `effective_trade_date`).
Couverture confirmée : 207K (2022) / 220K (2023) / 139K (2024) articles scorés.

Features testées : `news_net_1d/5d/10d`, `news_count_5d`, `news_pos/neg_ratio_5d`,
`news_last_net` (PIT).

**VERDICT : NO-GO** — aucun signal directionnel dans le pool Oracle TOP20% :
- IC(décile) max |0.028| (bruit) ; AUC_direction ≈ 0.49-0.50 (≈ hasard) ;
- `dir_vs_amp` ≈ ±0.01 (pas de séparation direction) ;
- stabilité du signe par fold : majoritairement NON.

Les agrégats de sentiment (sommes/ratios/dernier) ne séparent pas D1-D5 de D6-D10.
→ soit affiner en features événementielles (spike de sentiment près d'un earnings,
surprise, intensité × signe), soit passer à la famille 3.

## Famille 3 — short interest / short volume (2026-08-26)

`modelFactory/directional_data_research/short_interest.py` → `artifacts/directional_data_research_short.csv`.
Sources (cache FINRA 400 symboles, couverture 2022-2026 confirmée) :
- `short_sale_volume_400.parquet` : short volume QUOTIDIEN (846 dates) → features PIT (shift 1j
  intra-symbole) `short_ratio_1d/5d/10d`, `short_vw_ratio_5d/20d` ;
- `short_interest_400.parquet` : short interest BIMENSUEL (106 dates, PIT via
  `publication_date` = settlement + 7j ouvrés, `merge_asof` backward) →
  `short_days_to_cover`, `short_interest_change_pct`, `short_interest_to_adv`.

**VERDICT : NO-GO** — aucune des 8 features ne sépare les futurs bons/mauvais longs :
- AUC_direction max 0.501 (bruit pur) ; IC(décile) max |0.044| ;
- **toutes** les `dir_vs_amp` sont **négatives** (−0.001 à −0.029) → le court terme
  ne porte que de l'amplitude (proxi du volume), pas de direction ;
- les ratios bimensuels (`days_to_cover`, `to_adv`) sont ≈ 0.50 (aucun lien), les
  ratios quotidiens sont légèrement anti-directionnels (signe négatif) mais
  négligeables.

Le short volume/interest publié (T+1, bi-mensuel) n'apporte aucun signal
directionnel dans le pool Oracle TOP20%. → famille 4 : options skew (si données
disponibles) ou analyst revisions (gap de données).

## Famille 4 — options skew / insiders (2026-08-26)

**Options skew : NON TESTABLE** — aucune donnée options dans le système :
- audit des 66 tables DB → aucune table option/chain/IV/skew ;
- aucun cache ni artifact options (`eodhd_cache` = splits uniquement, `finnhub_cache` = profils) ;
- aucun code fournisseur options (aucun downloader, aucune intégration API).

**Insiders (Form 4 SEC) : ABANDONNÉ** — le client `service/sec/form4.py`
(SEC EDGAR gratuit, PIT `filing_date`, parsing `nonDerivativeTable`) a été écrit
et validé, mais le backfill des 399 symboles du pool implique ~10⁵ XML Form 4
(≈2h+ de téléchargement à la limite SEC ~8 req/s) → téléchargement abandonné.
État des données insider :
- `sec_cache/form4_20symbols.parquet` : 7 672 transactions mais **19 symboles**
  seulement (couverture insuffisante pour le pool) ;
- `models/oracle/e4b4_insider_features_20.parquet` : grid 405 symboles × dates
  mais **seulement 19 symboles avec valeurs réelles** (14 535 lignes non-null).

## Bilan — 4 familles testées, aucun signal directionnel

| Famille | Source | Verdict |
|---|---|---|
| 1. Estimate/earnings revisions | `stock_fundamentals_daily` | **NON TESTABLE** (gap estimates) |
| 2. News sentiment | `news_ticker_sentiment` + `news_raw` | **NO-GO** (IC≤0.028, AUC≈0.50) |
| 3. Short interest / short volume | parquets FINRA | **NO-GO** (IC≤0.044, AUC≤0.501, dir_vs_amp<0) |
| 4. Options skew / insiders | — | **NON TESTABLE** (gap options) / **ABANDONNÉ** (Form 4) |

**Conclusion branche** : dans le pool Oracle TOP20%, aucune famille de données
signées externes testée ne sépare D1-D5 de D6-D10. La direction reste non
observable avec les sources disponibles — cohérent avec le NO-GO `GlobalDirection`.
Le harnais `modelFactory/directional_data_research/harness.py` reste réutilisable
pour toute future famille de données.

Évidences : `artifacts/directional_data_research_{news,short,earnings}.csv`.

## Famille 5 — analyst (surprise earnings / days-to-earnings) (2026-08-27)

`modelFactory/directional_data_research/analyst_revisions.py` →
`artifacts/directional_data_research_analyst.csv`.

**7 familles demandées INDISPONIBLES (gap)** : révisions d'estimates EPS 7/30/90j,
révision de revenue, nb révisions hauss./baiss., dispersion, changement de
consensus, changement de target price, upgrades/downgrades — aucune table
analyst/estimate/révision (loggées, non inventées).

**2 familles TESTABLES** via `stock_earnings_calendar` (15 262 événements,
1 323 symboles, 2015-2026, `eps_estimate/actual`, `revenue_estimate/actual`) :
- `earn_surprise_eps_prev` (surprise EPS précédente, PIT, fenêtre 130 j)
- `earn_surprise_rev_prev`, `earn_surprise_abs_eps`, `days_to_earnings`, `earn_count_90d`

**Résultats (pool Oracle TOP20%) :**
| Feature | AUC | IC/fold | IC std | stable | lift top-décile | dir_vs_amp | coverage |
|---|---|---|---|---|---|---|---|
| **earn_surprise_eps_prev** | **0.519** | **+0.034** | 0.021 | **3/3** | **−0.002 (≈0)** | **+0.023** | 0.78 |
| earn_count_90d | 0.508 | +0.016 | 0.030 | 2/3 | −0.016 | +0.026 | 1.00 |
| earn_surprise_abs_eps | 0.495 | −0.002 | 0.006 | 2/3 | +0.013 | −0.002 | 0.78 |
| days_to_earnings | 0.489 | −0.017 | 0.015 | 2/3 | −0.015 | +0.002 | 0.99 |
| earn_surprise_rev_prev | 0.488 | −0.009 | 0.032 | 2/3 | −0.004 | **−0.032** | 0.74 |

**Verdict : CANDIDAT FAIBLE (pas GO)** — `earn_surprise_eps_prev` est le meilleur
signal directionnel de toute la recherche (AUC 0.519, IC +0.034 stable 3/3,
direction > amplitude, GOOD5−BAD5 = +0.246) MAIS **lift top-décile ≈ 0** et
AUC < 0.53 → le critère GO (stable + lift + BAD5↓/GOOD5↑) n'est pas rempli.
Les autres features sont NO-GO.
