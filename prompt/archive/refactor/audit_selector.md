# Audit — `selector`

> Périmètre : `selector/alpha_scanner.py`, `selector/strict_filter_profiles.py`,
> `selector/__init__.py`.
> Sources : `doc/selector.md`, `doc/DOC_TECHNIQUE.md` §2.1, code listé,
> tests `tests/test_selector_*`, `tests/test_alpha_scanner.py`,
> `tests/test_strict_filter_profiles.py`.

---

## 1. Résumé exécutif

`selector/` exécute le `AlphaScanner` : enrichit `stock_scores` avec des facteurs
techniques avancés (Minervini trend, VCP, ATR/ATR%, beta_126 vs SPY, weekly trend,
high_52w_proximity, market_cap, spread_bps, earnings_blackout), applique le profil strict
swing cash (centralisé dans `strict_filter_profiles.STRICT_SWING_CASH_FILTERS`), neutralise
sectoriellement, ranke et sélectionne les candidats finaux (`is_candidate=1`).

État global : **module dense, central pour la qualité de la sélection**, bien testé.
La centralisation des filtres stricts dans un profil partagé est une vraie force
(évite la divergence entre live, backfill PIT et backtest). Architecture
`ThreadPoolExecutor` cohérente avec le caractère I/O-bound.

Principaux risques :

1. **Forte dépendance à des données fragiles** : `spread_bps` (snapshot quote IEX,
   souvent biaisé), `market_cap` (Finnhub free, figé à la première ingestion),
   `earnings_blackout` (Finnhub free, fenêtre rétrécie). Une dégradation silencieuse
   d'un seul de ces inputs casse toute la sélection.
2. **`beta_126` calculé localement vs SPY** : sain pour la cohérence, mais coûteux ; pas
   d'instrumentation de la dispersion (combien de symboles sortent avec `beta_126 < 1.0` ?).
3. **Profil strict swing cash hardcodé en `STRICT_SWING_CASH_FILTERS`** : pas de
   versioning de profil, pas de "feature flag" pour A/B tester un nouveau profil.
4. **Filtre `volatility_ratio = vol_10/vol_60`** appliqué après `apply_filters()` →
   complexité de pipeline. Documenté mais à risque pour un nouveau dev qui voudrait
   "déplacer" ce filtre par optimisation.
5. **Neutralisation sectorielle** : z-score intra-secteur. Si un secteur a < 5 titres
   (utilities sur petit univers), la neutralisation devient bruitée.
6. **Pas de fallback documenté** quand `stock_quote_snapshots` ou `stock_earnings_calendar`
   est absent / périmé : le scanner peut écarter des titres pour une raison purement
   data-quality.

Priorités immédiates :
- Instrumenter le `run_summary` avec un détail "raison de rejet" par symbole (combien
  rejetés sur spread, sur market_cap, sur earnings, etc.).
- Ajouter un mode "lenient fallback" si la fraîcheur de `stock_quote_snapshots` >
  N heures (refus du filtre spread plutôt que rejet du symbole).
- Extraire le profil strict swing cash dans `core/filter_profiles.py` partagé.

---

## 2. Constat détaillé

### 2.1 `alpha_scanner.py` — orchestration

| Item | Détail |
|---|---|
| Constat | Pipeline en chunks parallèles (`ThreadPoolExecutor`) : `fetch_market_data` → `compute_factors` → `merge_scores` → enrichissement instrument/quotes/earnings → `apply_filters` → neutralisation sectorielle (sur univers complet) → `rank_and_select`. |
| Force | Bonne séparation logique. Profil strict centralisé. `reference_date=...` permet PIT pour backfill. |
| Risque | **Maintenabilité** : fichier ~800 lignes. Plusieurs responsabilités. Difficile à comprendre pour un nouveau dev. |
| Risque 2 | **Cohérence** : la neutralisation sectorielle se fait *après* le merge cross-chunks, donc le résultat dépend du chunking — à priori non, mais à valider par test. |
| Recommandation | Découper en sous-modules : `factors.py` (calcul), `filters.py` (apply), `ranking.py` (neutralisation + sélection). |

### 2.2 `strict_filter_profiles.py` — `STRICT_SWING_CASH_FILTERS`

| Constat | Source unique de vérité pour : `min_close=10`, `liquidity 30M$`, `vol_ratio<=0.90`, `RS>=100`, `close>MA200`, `high52w_prox>=0.75`, `weekly_trend>=1.0`, `atr_pct in [1.5%, 6%]`, `market_cap>=2Md$`, `beta_126>=1.0`, `spread_bps<=25`, `earnings_blackout_days=3`. |
| Force | Centralisation impeccable. Garantit l'alignement live / backfill / backtest. |
| Risque | **Maintenabilité** : pas de versioning. Un changement futur ne sera pas tracé sans `git log`. |
| Risque 2 | **Maintenabilité** : pas de mécanisme `STRICT_SWING_CASH_FILTERS_V2` qui co-existerait pour comparaison. |
| Recommandation | (a) Ajouter un `profile_version: str` dans le dict ; (b) prévoir un `FILTER_PROFILES: dict[str, FilterProfile]` qui permet de référencer plusieurs profils par nom (`"strict_swing_cash_v1"`, `"strict_swing_cash_v2"`) ; (c) sérialiser le profil utilisé dans le `run_summary` du scanner. |

### 2.3 Filtres et leurs dépendances

| Filtre | Dépendance | Risque silencieux |
|---|---|---|
| `min_close >= 10` | `stock_bars_daily.close` | Faible. |
| `avg_dollar_volume_20d >= 30M$` | `stock_bars_daily.volume * close` | **IEX biais** → seuil à interpréter en équivalent IEX. |
| `volatility_ratio <= 0.90` | calc `vol_10/vol_60` sur returns | Acceptable. |
| `relative_strength_index >= 100` | calcul vs SPY | Si SPY incomplet, exclusion massive. |
| `latest_close > ma200` | `stock_bars_daily` | Faible. |
| `high_52w_proximity >= 0.75` | `MAX(high)` 252j | Risque sur jours `is_filled` (cf. audit screener). |
| `weekly_trend_score >= 1.0` | rééchantillonnage W | Demande ≥ 30 semaines de données. |
| `atr_pct_20 in [1.5%, 6%]` | ATR(20) / close | Robuste. |
| `market_cap >= 2 Md$` | `stock_metadata.market_cap` (Finnhub) | **Données figées** → faux négatifs et faux positifs. |
| `beta_126 >= 1.0` | régression returns vs SPY | Coûteux, mais robuste. |
| `spread_bps <= 25` | `stock_quote_snapshots` | **IEX biais** → faux négatifs probables. |
| `earnings_blackout = 0` | `stock_earnings_calendar` (Finnhub) | Si fenêtre Finnhub trop étroite, faux négatifs (positions juste avant earnings non détectées). |

### 2.4 `apply_filters()` — séquencement

| Constat | Le filtre `volatility_ratio` n'est **pas** dans la présélection SQL mais après `compute_factors()` car il dépend des fenêtres roulantes. |
| Risque | **Maintenabilité** : choix correct mais peu intuitif ; bien documenté, mais un nouveau dev pourrait être tenté de le pousser SQL pour optimisation et casser la logique. |
| Recommandation | Ajouter un commentaire de bloc explicite dans le code expliquant pourquoi (et un test qui casse si on déplace le filtre). |

### 2.5 Neutralisation sectorielle

| Constat | Z-score intra-secteur sur `final_score` partiel, sur l'univers **complet** (cross-chunks). Bien. |
| Risque | **Cohérence** : sur petit univers (post-strict), un secteur peut avoir 1-2 titres → z-score = 0 ou 1, neutralisation inopérante. |
| Risque 2 | Le `sector_cap_ratio = 30%` peut conduire à exclure un titre fortement scoré au profit d'un titre moins fort dans un autre secteur, sans alerte. |
| Recommandation | (a) Loguer dans le run_summary les secteurs avec < 3 titres post-filter ; (b) exposer une option `--sector-min-count 3` pour skipper la neutralisation sur secteurs trop petits. |

### 2.6 Persistance

| Constat | Met à jour `stock_scores` avec colonnes : `trend_score`, `vcp_score`, `final_score`, `sector`, `market_cap`, `beta_126`, `spread_bps`, `earnings_*`, `is_candidate`. |
| Risque | `atr_pct_20`, `weekly_trend_score`, `high_52w_proximity` ne sont **pas persistés** dans `stock_scores` — seulement utilisés en mémoire. |
| Impact | Pas de moyen de reconstruire la décision a posteriori sans rejouer le scanner. |
| Recommandation | Ajouter ces colonnes au schéma `stock_scores` (à faire pendant la réinitialisation prévue). |

---

## 3. Risques prioritaires

### Critique
- `market_cap` figé (Finnhub free, pas de TTL côté `update_sector`) →
  filtre `market_cap >= 2 Md$` peut être totalement faux. Gravité directe sur la sélection.

### Élevé
- `spread_bps` issu de `stock_quote_snapshots` IEX → faux négatifs.
- Pas de fallback explicite si une dépendance data manque (le scanner exclut au lieu
  de désactiver le filtre).
- `historical_range_score` / `high_52w_proximity` calcul basé sur `MAX(high)` non filtré
  des `is_filled`.
- Fichier `alpha_scanner.py` monolithique → maintenabilité.

### Modéré
- Profil strict non versionné.
- Facteurs `atr_pct_20`, `weekly_trend_score`, `high_52w_proximity` non persistés.
- Neutralisation sectorielle bruitée sur petit secteur.

### Faible
- `--preset strict` legacy maintenu inutilement.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

### `avg_dollar_volume_20d >= 30 M$` (IEX)
Sous-évalué d'un facteur 30-50× → en réalité ce seuil correspond environ à 1-1.5 Md$
consolidé. Acceptable et même cohérent avec un univers swing large/mid cap.

### `spread_bps <= 25` (IEX)
**Le plus problématique** :
- spread IEX souvent 2-5× plus large que NBBO sur mid caps ;
- 25 bps = 0.25 % → en NBBO ça filtre les illiquides ; en IEX ça filtre aussi des
  liquides ;
- conséquence : faux négatifs probables sur des titres exécutables en réalité.

**Recommandation** :
- soit assouplir le seuil par défaut à `spread_bps <= 50` (équivalent NBBO ~25) ;
- soit mieux : conditionner le filtre sur `bid_size`, `ask_size` (déjà disponibles dans
  `stock_quote_snapshots`) — un grand spread sur petits volumes IEX est moins révélateur
  qu'un grand spread sur gros volumes ;
- documenter le choix.

### `relative_strength_index >= 100` (vs SPY)
Pas d'impact IEX direct — SPY est le benchmark, les deux séries sont sous-évaluées
sur la même base.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct sur le scanner. Tous les calculs (MA, ATR, vol, beta) sont
auto-cohérents avec `split_adjusted`. Conservation recommandée.

---

## 6. Quick wins

1. **Instrumenter le `run_summary`** : ajouter `rejected_by_filter` (compteurs par
   filtre) → permet de diagnostiquer "pourquoi 0 candidat" en 1 clic.
2. **Mode "lenient fallback"** sur `spread_bps` et `earnings_blackout` si la table
   source est trop ancienne (option `--fallback-on-stale-data`).
3. **Versionner le profil** (`profile_version: "strict_swing_cash_v1"`).
4. **Ajouter `atr_pct_20`, `weekly_trend_score`, `high_52w_proximity`** au schéma
   `stock_scores` (à faire pendant le reset).
5. **Documenter pourquoi `volatility_ratio` est appliqué après `compute_factors`**
   (commentaire de code explicite).
6. **Loguer secteurs < 3 titres** post-filter dans le run_summary.
7. **Filtre `spread_bps` conditionnel à `bid_size`/`ask_size`** (≥ 100 par exemple).
8. **Supprimer l'alias legacy `--preset strict`** (deprecation propre).

## 7. Recommandations structurelles

1. **Découper `alpha_scanner.py`** en sous-modules :
   `factors.py` / `filters.py` / `ranking.py` / `enrichment.py`.
2. **Centraliser `STRICT_SWING_CASH_FILTERS` dans `core/filter_profiles.py`** pour
   sharing avec screener et backtest (cf. audit screener).
3. **`FilterProfile` typé (dataclass)** au lieu de dict, avec validation automatique
   à l'instanciation (`spread_bps > 0`, `market_cap > 0`, etc.).
4. **Système de "feature flags" sur les filtres** — chaque filtre activable/désactivable
   indépendamment via config, pour permettre des ablations en backtest.
5. **Ajouter une étape "data quality gate"** avant `apply_filters` : si une source
   data est trop périmée, refuser le run avec exit code clair plutôt que de produire
   silencieusement des résultats biaisés.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 3, 5, 6, 8.
- Documentation impact IEX dans `doc/selector.md`.

### Moyen terme
- Quick wins 2, 4, 7 (impacts schéma, à coupler avec reset DB).
- Découpage `alpha_scanner.py`.
- Centralisation `core/filter_profiles.py`.
- Data quality gate.

### Long terme
- `FilterProfile` typé + feature flags.
- Versioning multi-profils + A/B testing.
- Variante sectorielle (force relative vs ETF sectoriel — cf. screener).

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Bons tests unitaires (`tests/test_alpha_scanner.py`, `tests/test_strict_filter_profiles.py`).
  **Manque** :
  - test "0 candidat" déclenche un log critical avec les bonnes causes.
  - test fallback data quality (quote stale, earnings stale).
  - test cross-chunk : neutralisation sectorielle invariante au chunking.
  - test profil versionné dans le run_summary.

### Monitoring
- `run_summary` riche. **Manque** :
  - compteurs de rejet par filtre (ajout proposé).
  - distribution sectorielle vs distribution attendue.
  - comparaison run-over-run de la composition de la sélection (turnover de la sélection).

### Documentation
- Très bonne (`doc/selector.md`, exemples chiffrés). **Manque** :
  - section "limitations IEX" et impacts sur `spread_bps`.
  - section "comment ajouter un nouveau filtre" (workflow + tests).
  - tableau impact économique de chaque filtre (titres rejetés moyens).

