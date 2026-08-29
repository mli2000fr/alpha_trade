# EODHD vs Alpaca (IEX) — usage réel du volume dans l'application

> Date d'analyse : 2026-05-10
> 
> Objet : déterminer si payer `EODHD` est rentable dans **cette** application, en traçant précisément où la donnée de `volume` est ingérée, stockée, lue et transformée.

---

## Conclusion exécutive

Oui, l'application utilise **réellement** le `volume` d'échange, et pas de manière marginale.

Le `volume` provenant des barres daily alimente directement :

- le **screener** via la liquidité en dollars,
- le **selector / alpha scanner** via `avg_dollar_volume_20d`,
- le **Model Factory / ML** via plusieurs features liées au volume,
- le **backtesting** via l'`ADV` et le **slippage volume-aware**.

En revanche, `EODHD` n'améliore **pas** directement :

- les **quotes temps réel**,
- l'**exécution live**,
- les appels broker Alpaca.

Donc la rentabilité de `EODHD` dépend de l'usage :

- **oui, rentable** si l'on utilise les modules d'analyse, de sélection, de ML et de backtesting ;
- **beaucoup moins utile** si l'on utilise surtout l'application pour le trading/exécution Alpaca sans exploiter ces analyses.

---

## 1. Où l'on choisit Alpaca/IEX vs EODHD dans l'application

### IHM Settings

La bascule du provider de barres OHLCV est exposée dans :

- `ihm/pages/settings.py:148-205`
- `ihm/services/market_data_provider.py:1-89`

Le texte de l'IHM indique explicitement que :

- la valeur persistée est `market_data.bars_provider` dans `config.yaml`,
- les pipelines IHM `Import Bars`, `corporate_actions_sync` et le backfill historique routent automatiquement vers le provider choisi,
- la metadata, les quotes live et l'exécution restent sur Alpaca.

### Configuration persistée

Dans `config.yaml:48-58` :

- `market_data.bars_provider: eodhd`

Le commentaire du fichier précise déjà :

- `alpaca` = historique avec **biais volume IEX**,
- `eodhd` = source daily recommandée.

### Routage runtime

Dans `ihm/services/pipeline_runner.py:911-923` :

- si `bars_provider == "eodhd"`, la step `import_alpaca_bar` route en réalité vers `dataIntegrityEngine.import_eodhd_bar --write`,
- sinon elle utilise `dataIntegrityEngine.import_alpaca_bar`.

Le switch de provider est donc **effectif**, pas seulement cosmétique.

---

## 2. Pourquoi le volume Alpaca gratuit pose problème

Dans `service/alpaca/clientAlpaca.py:32-38`, le projet documente clairement que :

- `feed="iex"` est le feed Alpaca gratuit,
- ce feed ne représente qu'une fraction du volume consolidé US,
- cela crée un biais sur les métriques de liquidité.

La documentation interne le répète dans `doc/service.md:261-279` :

- `avg_dollar_volume_20d` est sous-estimé en IEX,
- les filtres de liquidité peuvent donc être faussés.

Le projet a même un audit dédié : `scripts/eodhd_phase4_volume_audit.py:1-18`.

Cet audit vérifie explicitement :

- le ratio `volume_eodhd_eod / volume_alpaca_iex`,
- et si des large caps sont rejetées à tort quand on s'appuie sur Alpaca/IEX.

---

## 3. Où EODHD écrit le volume

### Tables de marché concernées

#### `stock_bars`

Schéma : `database/sql/stock/stock_bars.sql:1-20`

Colonnes clés :

- `volume`
- `data_source`
- `data_adjustment`

#### `stock_bars_daily`

Schéma : `database/sql/stock/stock_bars_daily.sql:1-27`

Colonnes clés :

- `volume`
- `data_source`
- `adj_close`
- `vwap`
- `daily_return`
- `is_filled`

La provenance est tracée par `data_source`, notamment :

- `alpaca_iex`
- `eodhd_eod`

### Adaptation EODHD -> schémas DB

Dans `service/eodhd/adapters.py` :

- `eodhd_to_split_only` (`153-190`) reconstruit les barres split-only,
- le volume historique est **multiplié** par le facteur de split,
- `to_stock_bars_daily_row` (`231-264`) écrit ce volume dans `stock_bars_daily.volume`,
- `to_stock_bars_row` (`267-294`) écrit ce volume dans `stock_bars.volume`.

### Ingestion effective

Dans `dataIntegrityEngine/eodhd/orchestrator.py:358-363`, chaque barre split-only produit :

- une ligne dans `stock_bars_daily`,
- une ligne dans `stock_bars`,
- un payload d'audit contenant aussi `{date, close, volume}`.

L'upsert effectif est visible dans `dataIntegrityEngine/import_eodhd_bar.py:218-247`.

---

## 4. Où le volume est utilisé dans les analyses

## 4.1 Screener — liquidité des titres

### Lecture source

Le screener lit `stock_bars_daily` via :

- `screener/db_io.py:_load_price_frame` (`93-121`)
- colonnes lues : `date`, `close_price`, `high_price`, `low_price`, `volume`

### Calcul métier

Dans `screener/pipeline.py:101-109` :

- `dollar_volume = volume * close_price`
- moyenne sur la fenêtre récente
- résultat stocké dans `liquidity_val`

Puis dans `screener/pipeline.py:221-233`, `liquidity_val` entre directement dans le score global.

### Persistance

Le screener persiste `liquidity_val` dans :

- `stock_scores` via `screener/db_io.py:438-477`
- schéma : `database/sql/stock/stock_scores.sql:5-10`

Puis archive ce snapshot dans :

- `stock_scores_history` via `screener/db_io.py:351-435`
- schéma : `database/sql/stock/stock_scores_history.sql:18-25`

### Impact métier

Si le volume Alpaca/IEX est sous-estimé, la liquidité calculée l'est aussi, ce qui peut :

- exclure de bons titres,
- dégrader le ranking,
- déformer l'univers candidat.

---

## 4.2 Selector / Alpha Scanner — `avg_dollar_volume_20d`

### Lecture source

Le selector lit `stock_bars_daily` via :

- `selector/db_io.py:50-74`

Colonnes lues :

- `symbol`
- `date`
- `close`
- `volume`
- `high`
- `low`

### Préfiltrage SQL

Dans `selector/db_io.py:317-338`, le préfiltre SQL utilise directement :

```sql
AVG(CASE WHEN rn <= :liquidity_lookback_days THEN close * volume END) > :liquidity_threshold
```

Donc la sélection initiale dépend déjà du `volume`.

### Calcul des facteurs

Dans `selector/factors.py:109-162` :

- le code exige la colonne `volume`,
- calcule `dollar_volume = close * volume`,
- calcule `avg_dollar_volume_20d`.

### Seuil métier

La documentation métier indique un seuil strict :

- `doc/selector.md:64-78`
- `doc/DOC_FONCTIONNELLE.md:107-122`

avec notamment :

- `avg_dollar_volume_20d >= 30 M$`

### Impact métier

Le volume influe ici sur :

- l'éligibilité des titres,
- la qualité de l'univers final,
- la robustesse d'exécution future d'une position.

---

## 4.3 Model Factory / ML — features volume-dépendantes

### Lecture source

Le Model Factory lit `stock_bars_daily` via :

- `modelFactory/data_loader.py:115-189`

Les colonnes lues incluent :

- `volume`
- `adj_close`
- `vwap`
- `daily_return`
- `is_filled`

### Features locales

Dans `modelFactory/features.py:115-149` :

- `volume_ratio_20 = volume / moyenne_20j(volume)`

### Features cross-sectionnelles

Dans `modelFactory/cross_sectional.py:53-101` :

- `dollar_volume_20 = mean(close * volume)`
- `volume_ratio_20`
- puis des ranks cross-sectionnels :
  - `dollar_volume_20_rank`
  - `volume_ratio_20_rank_xs`

### Impact métier

Le volume EODHD influe donc sur :

- les features d'entraînement,
- les features d'inférence,
- la qualité des prédictions,
- les comparaisons entre titres dans l'univers.

Autrement dit, un mauvais volume ne fausse pas seulement un filtre, il peut aussi fausser le **ML**.

---

## 4.4 Backtesting — ADV et slippage volume-aware

### Filtre explicite sur la source EODHD

Dans `backtesting/data_loader.py:44-64`, le backtesting impose explicitement :

- `data_source = 'eodhd_eod'`

La constante projet est :

- `BACKTEST_REQUIRED_BARS_DATA_SOURCE = "eodhd_eod"` (`backtesting/data_loader.py:23`)

Puis `load_ohlcv` (`67-106`) charge `volume` depuis `stock_bars_daily`.

Les tests valident ce comportement :

- `tests/test_backtesting.py:127-134`

### Utilisation en microstructure

Dans `backtesting/microstructure.py:60-75` :

- `compute_adv_usd(close, volume)` calcule l'ADV USD via `close * volume`

Dans `backtesting/simulator.py:424-425` :

- cet `ADV` est utilisé pour le **slippage volume-aware**.

### Impact métier

C'est un point fort en faveur d'EODHD :

- si le volume est biaisé à la baisse, l'ADV l'est aussi,
- la simulation de friction d'exécution devient moins réaliste,
- les backtests de stratégie deviennent moins fiables.

Le fait que le backtest force `eodhd_eod` montre que le projet considère déjà cette source comme la référence analytique.

---

## 4.5 Data Sanitizer — normalisation et remplissage

Dans `dataIntegrityEngine/data_sanitizer_daily.py:80-85`, le sanitizer :

- forward-fill les jours manquants,
- pose `volume = 0` sur les jours remplis artificiellement,
- réécrit `stock_bars_daily`.

L'upsert passe par `database/sanitizer_db_ops.py:186-218`.

### Impact métier

Le `volume` n'est donc pas un champ décoratif :

- il est normalisé,
- réingéré,
- propagé vers la table daily qui sert de base à la majorité des analyses.

---

## 5. Ce que EODHD n'améliore pas directement

Même lorsque `bars_provider=eodhd` :

- les **quotes live** restent Alpaca,
- l'**exécution** reste Alpaca,
- la metadata broker/market data temps réel n'est pas remplacée.

Le texte de l'IHM le précise dans `ihm/pages/settings.py:151-153`.

Donc l'intérêt principal d'EODHD est **analytique** et **backtest / sélection**, pas broker/live.

---

## 6. Tables réellement touchées par la chaîne volume

### Stockage brut / daily

- `stock_bars.volume`
- `stock_bars_daily.volume`

### Stockage de métriques dérivées

- `stock_scores.liquidity_val`
- `stock_scores_history.liquidity_val`

### Consommation sans persistance dédiée

Certaines transformations utilisent le volume sans écrire une colonne SQL dédiée :

- `selector` : `avg_dollar_volume_20d`
- `modelFactory` : `volume_ratio_20`, `dollar_volume_20_rank`, `volume_ratio_20_rank_xs`
- `backtesting` : `ADV USD`

---

## 7. Tableau final — module → table lue → champ volume → impact métier

| Module | Table lue | Champ volume lu/utilisé | Transformation principale | Impact métier |
|---|---|---|---|---|
| `screener` | `stock_bars_daily` | `volume` | `close * volume` -> `liquidity_val` | filtre de liquidité, ranking screener, univers scoré |
| `selector` / `alpha_scanner` | `stock_bars_daily` | `volume` | `close * volume` -> `avg_dollar_volume_20d` | préfiltrage des titres, sélection de positions plus exécutables |
| `modelFactory.features` | `stock_bars_daily` | `volume` | `volume_ratio_20` | feature ML de régime / activité volume |
| `modelFactory.cross_sectional` | `stock_bars_daily` | `volume` | `dollar_volume_20`, `volume_ratio_20`, ranks cross-sectionnels | comparaison relative entre titres, qualité des features ML |
| `backtesting.data_loader` + `microstructure` | `stock_bars_daily` | `volume` | `ADV USD = moyenne(close * volume)` | slippage volume-aware, réalisme du backtest |
| `data_sanitizer_daily` | `stock_bars` puis `stock_bars_daily` | `volume` | propagation / remplissage `volume=0` sur jours fillés | qualité et cohérence des séries daily utilisées par l'analyse |
| `scripts/eodhd_phase4_volume_audit.py` | `stock_bars_daily` | `volume` (`alpaca_iex` vs `eodhd_eod`) | ratios de volume et comparaison de dollar-volume | audit de la valeur réelle d'EODHD et détection des faux rejets de liquidité |

---

## 8. Réponse finale : faut-il payer EODHD ?

### Oui, si l'on utilise l'application pour :

- sélectionner les titres,
- filtrer par liquidité,
- entraîner ou servir le ML,
- backtester avec friction réaliste.

### Non, ou beaucoup moins, si l'on utilise surtout :

- les quotes live Alpaca,
- l'exécution d'ordres,
- une utilisation broker-centric sans pipeline analytique.

### Verdict projet

Dans **ce code**, payer EODHD est défendable car :

1. le volume est effectivement utilisé à plusieurs endroits stratégiques ;
2. le backtesting force déjà `eodhd_eod` comme source canonique ;
3. le projet documente explicitement le biais de volume `alpaca/iex` ;
4. un audit dédié existe pour prouver l'impact business de ce biais.

---

## 9. Trois requêtes SQL exactes pour vérifier en live l'usage de `eodhd_eod` et `liquidity_val`

> Hypothèse : base MySQL/MariaDB conforme aux schémas présents dans `database/sql/stock/*.sql`.

### Requête 1 — Vérifier que `stock_bars_daily` contient bien des barres `eodhd_eod` récentes

```sql
SELECT
    data_source,
    COUNT(*) AS rows_n,
    MIN(`date`) AS min_date,
    MAX(`date`) AS max_date
FROM stock_bars_daily
WHERE `date` >= (CURRENT_DATE - INTERVAL 30 DAY)
GROUP BY data_source
ORDER BY rows_n DESC;
```

**But :** prouver que l'instance exploite réellement des barres daily récentes avec `data_source = 'eodhd_eod'`.

---

### Requête 2 — Vérifier que la liquidité du screener (`liquidity_val`) est bien remplie dans `stock_scores`

```sql
SELECT
    COUNT(*) AS total_symbols,
    SUM(CASE WHEN liquidity_val IS NOT NULL THEN 1 ELSE 0 END) AS symbols_with_liquidity,
    ROUND(AVG(liquidity_val), 2) AS avg_liquidity_val,
    ROUND(MIN(liquidity_val), 2) AS min_liquidity_val,
    ROUND(MAX(liquidity_val), 2) AS max_liquidity_val
FROM stock_scores;
```

**But :** vérifier que le pipeline de screening a bien propagé une mesure dérivée du volume jusque dans `stock_scores.liquidity_val`.

---

### Requête 3 — Recalcul live du dollar-volume 20j à partir de `stock_bars_daily` et comparaison avec `stock_scores.liquidity_val`

```sql
WITH ranked AS (
    SELECT
        symbol,
        `date`,
        `close`,
        volume,
        data_source,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY `date` DESC) AS rn
    FROM stock_bars_daily
    WHERE data_source = 'eodhd_eod'
), avg20 AS (
    SELECT
        symbol,
        AVG(`close` * volume) AS avg_dollar_volume_20d_eodhd
    FROM ranked
    WHERE rn <= 20
    GROUP BY symbol
)
SELECT
    s.symbol,
    ROUND(a.avg_dollar_volume_20d_eodhd, 2) AS recomputed_avg_dollar_volume_20d,
    ROUND(s.liquidity_val, 2) AS stock_scores_liquidity_val,
    ROUND(s.liquidity_val - a.avg_dollar_volume_20d_eodhd, 2) AS delta
FROM stock_scores s
JOIN avg20 a ON a.symbol = s.symbol
ORDER BY ABS(s.liquidity_val - a.avg_dollar_volume_20d_eodhd) ASC, s.symbol
LIMIT 50;
```

**But :** montrer en live que la liquidité persistée dans `stock_scores` correspond bien à une logique basée sur `close * volume`, calculée à partir des barres `eodhd_eod`.

---

## 10. Références de code utilisées pour cette note

### Choix du provider
- `config.yaml:48-58`
- `ihm/services/market_data_provider.py:1-89`
- `ihm/pages/settings.py:148-205`
- `ihm/services/pipeline_runner.py:911-923`

### Ingestion EODHD / stockage
- `service/eodhd/adapters.py:153-190`
- `service/eodhd/adapters.py:231-294`
- `dataIntegrityEngine/eodhd/orchestrator.py:358-363`
- `dataIntegrityEngine/import_eodhd_bar.py:218-247`
- `database/sql/stock/stock_bars.sql:1-20`
- `database/sql/stock/stock_bars_daily.sql:1-27`

### Usages analytiques du volume
- `screener/db_io.py:93-121`
- `screener/pipeline.py:101-109`
- `screener/pipeline.py:221-233`
- `selector/db_io.py:50-74`
- `selector/db_io.py:317-338`
- `selector/factors.py:109-162`
- `modelFactory/data_loader.py:115-189`
- `modelFactory/features.py:115-149`
- `modelFactory/cross_sectional.py:53-101`
- `backtesting/data_loader.py:23-106`
- `backtesting/microstructure.py:60-75`
- `backtesting/simulator.py:424-425`
- `dataIntegrityEngine/data_sanitizer_daily.py:80-85`
- `database/sanitizer_db_ops.py:186-218`

### Audit et documentation interne
- `scripts/eodhd_phase4_volume_audit.py:1-18`
- `scripts/eodhd_phase4_volume_audit.py:55-75`
- `scripts/eodhd_phase4_volume_audit.py:132-185`
- `service/alpaca/clientAlpaca.py:32-38`
- `doc/service.md:261-279`
- `doc/selector.md:64-78`
- `doc/DOC_FONCTIONNELLE.md:107-122`
- `doc/data_lineage_matrix.md:31-40`

