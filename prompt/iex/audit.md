# Audit IEX — options de mitigation, avis d’architecture et stratégie de tests

> Périmètre : limites du feed Alpaca gratuit **IEX** dans `alpha_trade`, alternatives proposées (Tiingo, Alpha Vantage, Yahoo Finance), et arbitrage sur les actions techniques à mener.
>
> Sources relues : `README.md`, `doc/dataIntegrityEngine.md`, `doc/service.md`, `doc/data_lineage_matrix.md`, `prompt/refactor/audit_global.md`, `prompt/refactor/audit_dataIntegrityEngine.md`, `prompt/refactor/audit_backtesting.md`, `prompt/refactor/audit_service.md`, `service/alpaca/clientAlpaca.py`, `service/stooq/clientStooq.py`, `dataIntegrityEngine/cross_check_stooq.py`, `selector/factors.py`, `selector/filters.py`, `backtesting/cli.py`, `core/filter_profiles.py`, `core/run_summary.py`, `alembic/versions/0012_market_data_provenance_and_check.py`, tests associés.

---

## 1. Résumé exécutif

Le diagnostic de départ reste valide : **le point faible principal d’Alpha Trade n’est pas seulement IEX, mais le fait que le pipeline principal consomme encore IEX comme source primaire pour les barres OHLCV daily et pour les quotes**.

En conséquence :

- `avg_dollar_volume_20d` et `liquidity_val` sont biaisés à la baisse ;
- les `high` / `low` peuvent manquer certaines mèches du marché consolidé ;
- `vcp_score`, `volatility_ratio`, `atr_pct_20`, `beta_126` peuvent être lissés ou déformés ;
- le filtre `spread_bps` est déjà partiellement assoupli pour IEX, mais pas les filtres de liquidité / structure de prix.

### Décision synthétique

| Sujet | Avis | Priorité |
|---|---|---|
| Rendre le feed Alpaca réellement configurable | **À faire absolument** | P0 |
| Brancher un cross-check Stooq automatique sur les daily bars | **Oui, en audit automatique best-effort** | P1 |
| Ne plus utiliser le volume IEX brut comme filtre principal de liquidité | **Oui, c’est la vraie correction métier** | P0 |
| Taguer et exploiter `data_source` | **Oui, indispensable pour auditabilité et migration multi-source** | P0/P1 |
| Sécuriser le backtesting/stops si la mèche consolidée est suspecte | **Oui, avec une convention conservatrice documentée** | P1 |
| Intégrer Tiingo | **Très bon candidat prioritaire** | P1 |
| Intégrer Alpha Vantage | **Utile seulement en complément ciblé, pas comme source cœur** | P3 |
| Utiliser Yahoo Finance / `yfinance` | **Très bon backup/backfill, mais pas comme dépendance live critique** | P1/P2 |

### Position recommandée

Si l’objectif est de rester compatible avec le plan Alpaca gratuit tout en fiabilisant le swing / quant daily :

1. **Conserver Alpaca/IEX comme source broker-compatible et source “live-equivalent”**.
2. **Introduire une seconde source daily consolidée** pour la liquidité et l’audit de prix.
3. **Séparer explicitement les usages** :
   - exécution / compatibilité broker : Alpaca,
   - volume daily / beta / proxy consolidé : Tiingo idéalement,
   - audit cheap / best-effort : Stooq,
   - backfill long historique / bootstrap ML : Yahoo,
   - indicateurs “prêts à l’emploi” : Alpha Vantage seulement pour des cas marginaux.

---

## 2. Rappel du problème IEX dans Alpha Trade

Le code courant confirme que :

- `service/alpaca/clientAlpaca.py` expose `DEFAULT_FEED = "iex"` ;
- `dataIntegrityEngine/import_alpaca_bar.py` appelle `fetch_bars(...)` **sans override du feed** ;
- `dataIntegrityEngine/sync_latest_quotes.py` consomme les latest quotes Alpaca ;
- `screener/pipeline.py` et `selector/factors.py` calculent la liquidité à partir de `close * volume` ;
- `selector/factors.py` calcule aussi `avg_dollar_volume_20d`, `atr_pct_20`, `volatility_ratio`, `vcp_score`, `beta_126` à partir des séries daily ;
- `backtesting/cli.py` injecte `open`, `high`, `low`, `close` dans le moteur de backtest.

### Impact métier concret

#### 2.1 Liquidité

Le filtre de liquidité daily est le plus exposé :

- `screener/pipeline.py` : `dollar_volume = volume * close_price`
- `selector/factors.py` : `avg_dollar_volume_20d`
- `core/filter_profiles.py` : `STRICT_SWING_CASH_FILTERS.min_avg_dollar_volume_20d = 30_000_000.0`

**Conséquence** : un titre liquide au niveau marché consolidé peut apparaître trop faible avec IEX.

#### 2.2 Stops et mèches

Le backtest consomme `high` / `low`. Si une mèche a existé sur le marché consolidé mais n’apparaît pas sur IEX :

- un stop peut ne pas être déclenché en simulation ;
- un trailing stop peut sembler plus robuste qu’en réalité ;
- le résultat du backtest devient optimiste.

#### 2.3 VCP / volatilité / bêta

Le `vcp_score` est dérivé de `volatility_ratio`, lui-même dérivé des rendements daily. Si la série IEX est plus lisse que le marché consolidé :

- la contraction de volatilité est sur-évaluée ;
- `atr_pct_20` peut être sous-estimé ;
- `beta_126` peut être plus bruité ou artificiellement amorti.

---

## 3. Avis sur les propositions techniques initiales

### 3.1 Rendre le feed réellement configurable

#### Avis
**Oui, priorité P0.**

#### Pourquoi
Le repo est **préparé** à `iex|sip`, mais pas encore branché de bout en bout :

- `service/alpaca/clientAlpaca.py` valide bien `feed in {"iex", "sip"}` ;
- mais `import_alpaca_bar.py` n’injecte pas `feed` explicitement ;
- aucun `os.getenv("ALPACA_DATA_FEED")` n’est lu actuellement dans le code ;
- la doc évoque `ALPACA_DATA_FEED=sip`, mais le wiring n’est pas complet.

#### Effet attendu
- migration propre si un accès SIP apparaît plus tard ;
- homogénéité inter-modules ;
- possibilité de tester `live-equivalent=iex` vs `ideal=sip` sans forker le code métier.

#### Limite
Cela **ne résout rien** tant que l’abonnement reste IEX-only ; cela prépare la migration et supprime l’ambiguïté.

#### Décision
**À faire en premier**, mais comme **socle de configurabilité**, pas comme correction métier immédiate.

### 3.2 Brancher un cross-check Stooq automatique sur les daily bars

#### Avis
**Oui, priorité P1.**

#### Pourquoi
Le projet possède déjà les briques :

- `service/stooq/clientStooq.py`
- `dataIntegrityEngine/cross_check_stooq.py`
- `tests/test_stooq_cross_check.py`

Le module sait déjà détecter :

- `close_mismatch`
- `volume_ratio_low`
- `missing_in_stooq`

#### Ce que cela apporte vraiment
- signaler les symboles dont le volume IEX est trop bas ;
- détecter des divergences daily anormales ;
- enrichir `cleaning_audit_runs.cross_check_anomalies` ;
- objectiver la dérive IEX dans les `run_summary` et diagnostics opérateur.

#### Ce que cela ne résout pas seul
- pas de vraies quotes consolidées ;
- pas d’intraday ;
- pas de remplacement automatique propre pour les stops ;
- pas de correction du screener tant que les barres utilisées restent IEX.

#### Décision
**Très bon quick win** : faible coût, bon rendement opérationnel.

### 3.3 Ne plus utiliser le volume IEX brut comme filtre principal de liquidité

#### Avis
**Oui, priorité P0. C’est la correction la plus importante.**

#### Pourquoi
Le principal faux signal métier aujourd’hui vient de là.

Le spread IEX est déjà partiellement traité via :

- `max_spread_bps_iex`
- `min_quote_size`
- `rescued_spread_iex`

En revanche, **la liquidité n’a pas de vraie mitigation équivalente**.

#### Position recommandée
Il faut dissocier :

- **source broker-compatible** : Alpaca/IEX ;
- **source de liquidité daily consolidée** : Tiingo de préférence ;
- **fallback audit** : Stooq / Yahoo.

#### Options techniques possibles

##### Option A — remplacer entièrement `avg_dollar_volume_20d` par une source consolidée
La meilleure option métier si Tiingo est intégré.

##### Option B — conserver IEX mais appliquer un facteur multiplicatif fixe
**Déconseillé**. Trop grossier, faux selon symboles, périodes et univers.

##### Option C — dual fields
Exemple :
- `avg_dollar_volume_20d_iex`
- `avg_dollar_volume_20d_consolidated`
- le filtre dur utilise le champ consolidé ;
- l’analyse live conserve le champ IEX pour l’écart opérationnel.

#### Décision
**À faire avant toute confiance accrue dans les filtres du selector.**

### 3.4 Taguer et exploiter `data_source`

#### Avis
**Oui, priorité P0/P1.**

#### Pourquoi
La base est déjà préparée :

- `alembic/versions/0012_market_data_provenance_and_check.py`
- `core/interfaces.py` documente `data_source="alpaca_iex"`

Mais l’exploitation métier de cette provenance reste faible.

#### Objectif
Rendre explicite :

- quelles lignes viennent de `alpaca_iex` ;
- lesquelles viendront demain de `alpaca_sip`, `tiingo`, `stooq`, `yahoo` ;
- quels scores ont été calculés sur quelle source.

#### Cas d’usage clés
- audit reproductible du backtest ;
- A/B `iex` vs `consolidated_proxy` ;
- exclusion de certaines séries dégradées ;
- affichage IHM du niveau de confiance par source.

#### Décision
**Indispensable** si l’on veut faire du multi-source propre sans dette cachée.

### 3.5 Sécuriser le backtesting/stops quand la mèche consolidée est suspecte

#### Avis
**Oui, priorité P1.**

#### Pourquoi
Le risque ici n’est pas seulement “moins bon signal”, mais **illusion de robustesse du système**.

#### Recommandation de convention
Quand la source daily consolidée (Tiingo ou Stooq/Yahoo proxy) indique une mèche significativement pire qu’IEX :

- soit on déclenche une convention conservatrice ;
- soit on marque le trade / jour comme “price integrity degraded” ;
- soit on fait tourner deux backtests :
  - `live_equivalent` : IEX brut,
  - `consolidated_proxy` : source externe.

#### Convention conservatrice suggérée
Pour un stop :
- si `low_consolidated < low_iex` d’un delta supérieur à un seuil, utiliser le scénario le plus pénalisant ;
- documenter précisément la règle dans le moteur de backtest.

#### Décision
À faire, mais **après** avoir une seconde source daily exploitable.

---

## 4. Avis sur Tiingo, Alpha Vantage et Yahoo Finance

### 4.1 Tiingo

#### Avis
**La meilleure alternative proposée pour Alpha Trade côté swing/quant daily.**

#### Pourquoi Tiingo est cohérent avec Alpha Trade
Tiingo est particulièrement pertinent pour ce projet car il cible précisément les zones où IEX fait mal :

- volume daily consolidé/proxy bien plus crédible ;
- OHLCV EOD utilisable pour screening et factors ;
- historique exploitable pour `avg_dollar_volume_20d`, `beta_126`, `atr_pct_20`, `volatility_ratio`, `vcp_score` ;
- intégration plus “propre quant” qu’un simple scraping non officiel.

#### Usage recommandé dans Alpha Trade

##### Priorité 1
Dans `selector/factors.py` et éventuellement `screener/pipeline.py` :
- calculer `avg_dollar_volume_20d` sur Tiingo ;
- recalculer `beta_126` sur Tiingo ;
- envisager à terme `atr_pct_20` et `volatility_ratio` sur la même source pour cohérence.

##### Priorité 2
Introduire un mode :
- `source_mode = live_equivalent | consolidated_proxy`

#### Bénéfices
- réduit les faux rejets de liquidité ;
- réduit le biais VCP ;
- rend le selector plus fidèle au marché réel ;
- prépare une architecture saine avant un éventuel SIP payant.

#### Risques / limites
- quotas à **revalider contractuellement** au moment d’intégrer ;
- nouvelle dépendance API + stockage + caching ;
- nécessité d’un mapping `symbol -> provider symbol` propre ;
- nécessité de tracer `data_source` et éventuellement `provider_latency`.

#### Verdict
**Oui, c’est le meilleur candidat externe à intégrer en premier.**

### 4.2 Alpha Vantage

#### Avis
**Utile mais secondaire ; à ne pas choisir comme source cœur du pipeline.**

#### Ce qui est intéressant
- endpoints d’indicateurs prêts à l’emploi ;
- quelques données fondamentales et techniques pratiques ;
- peut servir pour enrichir quelques symboles finaux ou des diagnostics ciblés.

#### Pourquoi ce n’est pas le bon pivot pour Alpha Trade
Le projet a déjà :
- son calcul de RSI / ATR / beta / volatility / VCP ;
- une logique PIT/backtesting qu’il faut garder reproductible ;
- une nécessité de recalcul batch sur un univers large.

Or des indicateurs “pré-calculés provider-side” posent souvent 4 problèmes :

1. **reproductibilité PIT plus faible** ;
2. dépendance à une boîte noire de calcul ;
3. quotas insuffisants pour un vrai moteur de sélection ;
4. risque de divergence entre live / backfill / backtest.

#### Usage recommandé
- enrichissement ponctuel de quelques `Top Picks` ;
- tests de cohérence contre vos indicateurs maison ;
- certaines données fondamentales si une vraie plus-value est démontrée.

#### Usage non recommandé
- source principale des indicateurs pour `ModelFactory` ;
- remplacement du calcul local d’ATR/RSI/MACD sur l’univers complet.

#### Verdict
**À garder en backlog opportuniste, pas en priorité.**

### 4.3 Yahoo Finance / `yfinance`

#### Avis
**Très bonne option comme backup historique et backfill ML ; pas comme dépendance live critique.**

#### Pourquoi c’est pertinent pour Alpha Trade
Le projet a déjà un précédent culturel compatible :
- `corporate_actions/cross_check_yahoo.py` existe déjà pour les dividendes.

Yahoo est particulièrement utile pour :
- backfill 5-10 ans ;
- bootstrap de datasets historiques ;
- réduction des coûts/quota sur Alpaca/Tiingo ;
- proxy consolidé pour backtests comparatifs.

#### Meilleur usage recommandé
Dans `backtesting/backfill_scores_history.py` et potentiellement `modelFactory` bootstrap :
- utiliser Yahoo comme **source initiale d’historique long** ;
- garder Alpaca/Tiingo pour les runs plus proches du présent et pour la compatibilité live.

#### Risques / limites
- non officiel ;
- plus fragile qu’un provider payant ;
- dépendance qu’il faut isoler derrière une abstraction ;
- attention aux ajustements historiques splits/dividendes, à harmoniser avec la convention projet `split`.

#### Verdict
**Oui pour le backfill et l’expérimentation ML ; non comme source primaire du pipeline live quotidien.**

---

## 5. Architecture cible recommandée

### 5.1 Principe directeur

Ne pas chercher un “provider unique miracle”, mais un **montage à rôles séparés**.

#### Rôle des sources

| Rôle | Source recommandée |
|---|---|
| Exécution / compatibilité broker | Alpaca |
| Source live-equivalent | Alpaca IEX |
| Source consolidée proxy daily | Tiingo |
| Audit best-effort indépendant | Stooq |
| Backfill long historique / bootstrap ML | Yahoo Finance |
| Indicateurs tiers ponctuels / fundamentals ciblés | Alpha Vantage |

### 5.2 Recommandation opérationnelle par module

#### `dataIntegrityEngine`
- rendre `feed` explicite et configurable ;
- enregistrer `data_source` à l’ingestion ;
- brancher `cross_check_stooq` automatiquement ;
- préparer un chemin Tiingo daily pour les symboles critiques.

#### `screener`
- conserver un mode IEX pour comparaison ;
- mais ne plus faire dépendre le filtre principal de liquidité du volume IEX brut.

#### `selector`
- recalculer `avg_dollar_volume_20d` et `beta_126` sur source consolidée ;
- garder `spread_bps` IEX assoupli comme indicateur opérationnel broker-facing.

#### `backtesting`
- supporter deux modes de replay :
  - `live_equivalent` ;
  - `consolidated_proxy`.
- documenter précisément la convention stop/gap/mèche.

#### `modelFactory`
- utiliser Yahoo pour bootstrap historique ;
- utiliser Tiingo pour certaines features daily si l’objectif est la qualité factorielle.

---

## 6. Ordre de priorités recommandé

### Phase 1 — correction du plus gros risque métier

1. rendre `feed` réellement configurable ;
2. intégrer `data_source` de bout en bout ;
3. sortir la liquidité du volume IEX brut.

### Phase 2 — audit et robustesse

4. cross-check Stooq automatique ;
5. alertes / compteurs d’écarts IEX ;
6. instrumentation `live-equivalent` vs `consolidated-proxy`.

### Phase 3 — amélioration de la qualité des signaux

7. intégrer Tiingo pour `avg_dollar_volume_20d`, `beta_126`, puis éventuellement ATR/VCP ;
8. sécuriser les stops/backtests sur mèches suspectes.

### Phase 4 — optimisation opportuniste

9. Yahoo pour backfill historique / bootstrap ML ;
10. Alpha Vantage seulement pour enrichissements ciblés si la valeur ajoutée est prouvée.

---

## 7. Tests existants déjà utiles

Les tests suivants existent déjà dans le repo et doivent rester verts pendant toute évolution IEX / multi-source.

### `tests/test_clientAlpaca.py`

Couvre déjà :
- importabilité du client ;
- `adjustment="split"` transmis dans `fetch_bars()` ;
- date de départ par défaut ;
- comportement sur timeouts répétés.

**Intérêt** : base de sécurité pour toute refonte de `feed` / `adjustment`.

### `tests/test_phase1_run_summary.py`

Couvre déjà :
- `attach_schema_version()` ;
- `merge_iex_bias_counters()` ;
- contrat des clés IEX :
  - `symbols_zero_volume_30d`
  - `stale_quote_pct`
  - `stale_market_cap_pct`

**Intérêt** : garde-fou de compatibilité des `run_summary`.

### `tests/test_stooq_cross_check.py`

Couvre déjà :
- parsing CSV Stooq ;
- `close_mismatch` ;
- `volume_ratio_low` ;
- `missing_in_stooq` ;
- normalisation du symbole Stooq.

**Intérêt** : excellente base pour automatiser le cross-check.

### `tests/test_selector_alpha_scanner.py`

Couvre déjà :
- propagation des extensions IEX/TTL ;
- validation de `max_spread_bps_iex` ;
- validation de `min_quote_size` ;
- validation de `market_cap_max_age_days` ;
- cas où le relâchement IEX sauve un titre à carnet épais.

**Intérêt** : montre que le repo gère déjà partiellement le biais IEX côté spread.

### `tests/test_selector_run_summaries.py`

Couvre déjà :
- présence de `max_spread_bps_iex` ;
- présence de `min_quote_size` ;
- présence de `market_cap_max_age_days` dans le `run_summary` selector.

**Intérêt** : garantit la visibilité opérateur des assouplissements IEX.

### `tests/test_backtesting.py`

Couvre déjà une large base du backtesting et du chargement OHLCV.

**Intérêt** : point d’ancrage si l’on introduit des modes `live_equivalent` / `consolidated_proxy`.

---

## 8. Tests à ajouter en priorité

### 8.1 Feed / provenance

#### Test 1 — `ALPACA_DATA_FEED` réellement pris en compte
But : garantir qu’un feed explicite pilote bien le client et le pipeline.

À vérifier :
- `fetch_bars(..., feed="iex")` envoie `feed=iex` ;
- `fetch_bars(..., feed="sip")` envoie `feed=sip` ;
- valeur invalide => `ValueError` ;
- le script d’ingestion transmet bien le feed choisi.

#### Test 2 — `data_source` persisté proprement
But : assurer la traçabilité.

À vérifier :
- `stock_bars` et `stock_bars_daily` stockent la provenance attendue ;
- les lignes Tiingo / Stooq / Yahoo ne se mélangent pas silencieusement avec `alpaca_iex`.

### 8.2 Liquidité consolidée

#### Test 3 — le filtre de liquidité n’utilise plus IEX brut seul
But : vérifier la correction métier.

Jeu de test recommandé :
- symbole A : volume IEX faible, volume consolidé élevé ;
- symbole B : volume faible partout ;
- symbole C : volume élevé partout.

Attendu :
- A passe avec la source consolidée ;
- B échoue ;
- C passe.

#### Test 4 — dual-run selector `iex` vs `consolidated_proxy`
But : mesurer l’écart de sélection.

Attendu :
- production d’un delta clair sur les candidats retenus ;
- pas de divergence silencieuse.

### 8.3 Cross-check Stooq automatique

#### Test 5 — anomalies Stooq bien injectées dans l’audit
But : confirmer que le cross-check n’est plus seulement une fonction isolée.

À vérifier :
- exécution automatique lors du pipeline daily ;
- anomalies persistées dans `cleaning_audit_runs.cross_check_anomalies` ;
- run non bloquant si Stooq échoue.

#### Test 6 — seuils de bruit maîtrisés
But : éviter les faux positifs.

À vérifier :
- large caps avec petits écarts => pas d’alerte ;
- gros écarts de volume / close => alerte.

### 8.4 Backtesting / stops / mèches

#### Test 7 — stop déclenché par la mèche consolidée mais pas par IEX
But : matérialiser le risque utilisateur.

Jeu minimal :
- IEX : `low = 181`
- consolidé : `low = 180`
- stop = `180.5`

Attendu :
- mode `live_equivalent` : stop non déclenché ;
- mode `consolidated_proxy` : stop déclenché ;
- différence explicitement visible dans le rapport.

#### Test 8 — convention de fill sur gap documentée et testée
But : ne pas avoir de biais implicite.

Attendu :
- si l’open traverse le stop, la convention de fill est stable, documentée et testée.

### 8.5 ML / backfill

#### Test 9 — bootstrap Yahoo isolé du pipeline live
But : éviter d’introduire une dépendance fragile sur la chaîne quotidienne.

À vérifier :
- Yahoo est utilisé uniquement en backfill / bootstrap ;
- indisponibilité Yahoo n’impacte pas le pipeline live.

#### Test 10 — cohérence d’ajustement historique
But : harmoniser Yahoo / Tiingo / Alpaca avec la convention projet `split`.

À vérifier :
- la série utilisée dans `modelFactory` et `backtesting` ne mélange pas des ajustements incompatibles.

---

## 9. Commandes de validation recommandées

### Batterie minimale actuelle

```powershell
python -m pytest tests/test_clientAlpaca.py tests/test_phase1_run_summary.py tests/test_stooq_cross_check.py tests/test_selector_alpha_scanner.py tests/test_selector_run_summaries.py -q -o addopts=""
```

### Batterie backtesting ciblée

```powershell
python -m pytest tests/test_backtesting.py -q -o addopts=""
```

### Batterie future à viser après intégration multi-source

```powershell
python -m pytest tests/test_clientAlpaca.py tests/test_phase1_run_summary.py tests/test_stooq_cross_check.py tests/test_selector_alpha_scanner.py tests/test_selector_run_summaries.py tests/test_backtesting.py -q -o addopts=""
```

---

## 10. Recommandation finale

### Ce qu’il faut faire maintenant

1. **Rendre le feed Alpaca réellement configurable**.
2. **Exploiter `data_source` pour préparer le multi-source propre**.
3. **Cesser d’utiliser le volume IEX brut comme vérité principale de liquidité**.
4. **Automatiser le cross-check Stooq en audit best-effort**.
5. **Préparer un mode de backtest conservateur face aux mèches suspectes**.

### Quel provider externe prioriser

#### 1er choix : **Tiingo**
Pour la liquidité, le bêta et la qualité factorielle daily.

#### 2e choix : **Yahoo Finance**
Pour le backfill long historique et le bootstrap ML.

#### 3e choix : **Alpha Vantage**
Pour de l’enrichissement ponctuel, pas pour le cœur du système.

### Formule simple de décision

- **Si l’objectif est d’améliorer la sélection live quotidienne** : intégrer **Tiingo**.
- **Si l’objectif est d’améliorer l’historique et le ML** : utiliser **Yahoo**.
- **Si l’objectif est d’avoir un audit indépendant à faible coût** : automatiser **Stooq**.
- **Si l’objectif est d’avoir des features pré-calculées sur quelques picks** : considérer **Alpha Vantage** en complément seulement.

---

## 11. Verdict net

Mon avis final sur vos idées et sur les propositions précédentes est le suivant :

- votre intuition sur **Tiingo** est la plus forte et la plus compatible avec le besoin réel d’Alpha Trade ;
- **Alpha Vantage** est intéressant mais trop limité pour devenir un pilier ;
- **Yahoo** est excellent comme backfill / bootstrap / backup, pas comme fondation du pipeline live ;
- parmi les actions proposées, **la plus importante n’est pas Stooq ni SIP, mais la sortie du volume IEX brut comme vérité de liquidité** ;
- **Stooq** doit être vu comme un garde-fou intelligent, pas comme la solution unique ;
- **les stops/backtests** ne seront vraiment fiabilisés qu’après introduction d’une seconde source daily crédible.


---

## 12. Note de revue expert (mise à jour 2026-04)

### 12.1 Position globale

**D’accord à ~95 %** avec l’audit. Les diagnostics sont conformes au code (vérifié sur `service/alpaca/clientAlpaca.py`, `dataIntegrityEngine/import_alpaca_bar.py`, `selector/factors.py`, `core/filter_profiles.py`, `alembic/versions/0012_*`). Les priorités P0/P1 sont les bonnes : *configurabilité du feed*, *exploitation de `data_source`*, *sortie du volume IEX comme vérité de liquidité*.

### 12.2 Précisions et nuances apportées

1. **Tiingo : attention au volume "consolidé"**. En pratique Tiingo EOD agrège lui aussi à partir de feeds tiers ; il est *significativement plus représentatif* qu’IEX (souvent x10–x30 sur les large caps), mais reste un *proxy*, pas un vrai SIP. Documenter cette nuance dans `doc/data_lineage_matrix.md` au moment de l’intégration.
2. **Yahoo / `yfinance` : risque de rupture silencieuse**. L’API n’est pas officielle ; prévoir dès le départ un **circuit-breaker** (désactivation auto si N erreurs consécutives) et un cache disque persistant sous `artifacts/yahoo_cache/` aligné avec `artifacts/finnhub_cache/`.
3. **Alpha Vantage** : confirmer le verdict *backlog opportuniste*. Le quota gratuit (5 req/min, 500/jour en 2026) est rédhibitoire pour tout usage univers-large.
4. **Convention d’ajustement**. Le projet utilise `adjustment="split"` côté Alpaca (vérifié). Tiingo expose `adjOpen/adjHigh/adjLow/adjClose` *split+dividend*, Yahoo idem. **Il faudra explicitement reconstruire un OHLCV "split-only"** côté adapters Tiingo/Yahoo pour ne pas mélanger les conventions. C’est un piège classique sous-estimé dans l’audit initial → à ajouter en test obligatoire (cf. test 10).
5. **Cross-check Stooq automatique** : maintenir `best-effort` ET *non bloquant* via un `try/except` enveloppant + métrique `cross_check_stooq.failed_total` dans `run_summary`, sinon une indispo Stooq cassera le pipeline daily.
6. **Mode dual `live_equivalent` vs `consolidated_proxy`** : préférer un **drapeau d’exécution explicite** plutôt qu’une variable d’environnement seule, pour permettre l’A/B sur une même journée sans recharger l’environnement (cf. `prompt/iex/plan_boolean_multi_source.md`).
7. **Stops & mèches** : la *convention conservatrice* doit être paramétrée (delta % et ATR-multiple) et journalisée par trade dans `backtesting/report.py` sous une colonne `price_integrity_flag`.

### 12.3 Ajustements de priorisation

| Action | Priorité audit | Priorité revue | Justification |
|---|---|---|---|
| Feed configurable bout-en-bout | P0 | **P0** | inchangé |
| `data_source` exploité partout | P0/P1 | **P0** | prérequis du multi-source, à faire avant Tiingo |
| Sortir liquidité du volume IEX | P0 | **P0 (mais après Tiingo branché)** | sans seconde source, la "correction" n’est qu’un assouplissement de seuil → faux confort |
| Cross-check Stooq automatique | P1 | **P1** | inchangé, quick win |
| Intégration Tiingo | P1 | **P1** | à packager avec le boolean multi-source |
| Convention stop/mèche conservatrice | P1 | **P2** | dépend de Tiingo opérationnel |
| Yahoo backfill ML | P1/P2 | **P2** | utile mais hors chemin critique live |
| Alpha Vantage | P3 | **P4 (parking)** | quotas insuffisants |

### 12.4 Décision opérationnelle

Le déploiement multi-source doit être **réversible et observable** :
- un **booléen unique** (`MULTI_SOURCE_ENABLED`) en config + IHM ;
- valeur par défaut `False` → comportement actuel 100 % Alpaca/IEX ;
- valeur `True` → branche les adapters Tiingo (et Stooq audit) selon une matrice de routage déterministe documentée ;
- chaque ligne persistée porte `data_source` ;
- chaque `run_summary` porte le flag pour audit a posteriori.

Le détail est dans `prompt/iex/plan.md` (plan d’exécution) et `prompt/iex/plan_boolean_multi_source.md` (spécification du switch).
