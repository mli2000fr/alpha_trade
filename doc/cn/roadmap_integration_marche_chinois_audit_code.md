# Audit du code et roadmap d’intégration du marché chinois

> Statut : étude d’architecture et plan de réalisation.  
> Date de l’audit : 19 septembre 2026.  
> Révision du dépôt auditée : `8052fc18`, avec les modifications locales présentes à cette date.  
> Portée : coexistence durable des marchés US et Chine dans la même application, depuis l’ingestion jusqu’au backtest, puis exécution papier/live dans une phase ultérieure.  
> Aucun code source n’a été modifié pendant cet audit.

## 1. Décision d’architecture

L’intégration est faisable, mais elle ne doit pas être réalisée comme un POC isolé ni comme une copie de l’application US.

La cible recommandée est :

```text
                         α-Trade multi-marchés

 Sources US                                             Sources CN
 EODHD / Alpaca / SEC / Yahoo                           Tushare / RQData éventuel
          │                                                        │
          ▼                                                        ▼
 staging brut fournisseur US                           staging brut fournisseur CN
          │                                                        │
          └──────────────────────┬─────────────────────────────────┘
                                 ▼
                    modèle canonique commun
              instrument_id + market_code + MIC
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
          feature engine      ML/Oracle        backtest
                │                │                │
                └────────────────┴────────────────┘
                                 │
                                 ▼
                       portefeuille et risque
                                 │
                   phase 2 : routeur d’exécution
                      US broker / CN broker
```

Principes structurants :

1. une seule base canonique et un seul code métier ;
2. des tables de staging séparées par fournisseur lorsque les formats sont très différents ;
3. une identité d’instrument immuable, indépendante du ticker du fournisseur ;
4. un `MarketContext` explicite transmis à chaque run, batch et requête ;
5. des modèles entraînés et évalués séparément par marché ;
6. un backtest chinois réaliste avant toute recherche de broker ;
7. le chemin paper/live est différé, mais ses contrats sont prévus dès la fondation.

Il ne faut pas créer une branche Git permanente « Chine » ni une seconde base clonée. Cela conduirait rapidement à deux calendriers, deux moteurs ML, deux backtests et deux séries de correctifs divergentes.

## 2. Ce que l’audit du code montre réellement

### 2.1 Points réutilisables

Le projet dispose déjà de briques solides :

- couches ingestion, screener, selector, ML, backtest, risque et exécution séparées ;
- tables de provenance (`data_source`, `ingested_at`) ;
- contrat PIT dans `common/data_availability.py` ;
- univers configurables dans `config/univers/` ;
- campagnes ML identifiées par `batch_id` et runs par `run_id` ;
- Oracle Extreme, global ranking et modèles directionnels séparés ;
- manifests d’artefacts pour le bundle Oracle + LONG/SHORT ;
- backtest avec coûts, liquidité, risque et lifecycle ;
- `BrokerClient` générique déclaré dans `core/interfaces.py` ;
- tests de parité backtest/live et nombreux tests PIT/Oracle existants.

Ces éléments permettent de faire évoluer l’application sans réécrire les modèles.

### 2.2 Le contrat effectif reste américain

Les abstractions génériques sont incomplètes. Le comportement réel est encore dominé par :

```text
symbol seul
  + calendrier NYSE
  + America/New_York
  + benchmark SPY
  + VIX/VXN/MOVE
  + asset_class = us_equity
  + notionnels et seuils nommés USD
  + barres provenant principalement d’EODHD/Alpaca
  + exécution concrète Alpaca
```

Constats vérifiés dans le code :

| Zone | Vérité actuelle | Impact CN |
|---|---|---|
| Calendrier | `common/market_calendar.py` charge uniquement `NYSE`, expose `nyse_session_dates()` et utilise `America/New_York` | Bloquant pour dates, horizons, folds et cutoffs CN |
| PIT | `common/data_availability.py` a pour défaut New York et reconstruit souvent la disponibilité à `21:00 UTC` | Incorrect pour Shanghai et incorrect lors des changements DST si utilisé comme heure fixe |
| Référentiel | `stock_metadata` a `symbol` comme PK et `asset_class` documenté `us_equity` | Impossible d’assurer une identité multi-place robuste |
| Barres | `stock_bars_daily` a la PK `(symbol, date)` | Collision possible et aucune dimension marché/devise/session |
| Univers | plusieurs filtres exigent `asset_class='us_equity'` | Les A-shares seront exclues |
| ML | `modelFactory/data_loader.py` charge par `symbol` ; benchmark par défaut `SPY` | Risque de charger le mauvais instrument ou contexte |
| Cross-section | `modelFactory/cross_sectional.py` classe avec `groupby('date')` | Mélange US/CN si le scope marché n’est pas imposé en amont |
| Oracle | labels, déciles et prédictions sont identifiés par date/symbole/batch, sans marché explicite | Un batch mal construit peut contaminer ses labels silencieusement |
| Prédictions | unicité `model_predictions(symbol, prediction_date, run_id)` | Le run limite le risque, mais l’identité reste ambiguë dans les jointures |
| Backtest | `backtesting/cli/_impl.py` applique le calendrier NYSE et charge SPY en dur pour plusieurs overlays | Résultats CN temporellement et économiquement faux |
| Liquidité | `adv_usd`, `size_usd`, `min_ticket_usd`, market cap USD | Il faut séparer valeur locale, devise et conversion PIT |
| Exécution | `execution_engine/BrokerAdapter` adapte directement `AlpacaTradingClient` et construit des payloads Alpaca | Le nom est générique, l’implémentation ne l’est pas encore |
| IHM | univers et batches ne sont pas filtrés par marché | Risque de sélectionner un batch US pour une opération CN |

### 2.3 Risque le plus grave : contamination silencieuse

L’ajout de fichiers contenant des tickers chinois ne provoquerait pas forcément une erreur. Il pourrait produire un résultat apparemment valide mais faux.

Exemples vérifiés :

- les features cross-sectionnelles sont classées par date, pas par `(market_code, date)` ;
- les labels Oracle sont rangés au sein de la date, en supposant que l’univers fourni est homogène ;
- de nombreuses jointures utilisent seulement `(date, symbol)` ;
- les loaders de barres filtrent uniquement par `symbol` ;
- les secteurs sont groupés par `(date, sector)`, sans marché ;
- les historiques de sentiment, fondamentaux et analystes sont principalement liés au symbole ;
- `stock_scores` est un état courant avec PK `symbol` et pourrait être remplacé par un autre marché ;
- les contraintes de positions et ordres emploient souvent `(account_id, symbol)`.

Conclusion : **aucune donnée CN ne doit être chargée dans les tables canoniques actuelles avant la fin de la fondation P0**.

## 3. Périmètre fonctionnel cible

### 3.1 Phase initiale réellement utile

La première version doit permettre :

- ingestion historique et incrémentale des données chinoises ;
- univers PIT avec titres délistés, suspensions et changements de statut ;
- calcul des features ;
- entraînement Oracle Extreme, ranking et direction ;
- prédictions historiques et diagnostics ;
- backtests économiques réalistes ;
- consultation complète dans l’IHM ;
- comparaison US/CN sans mélange des observations.

### 3.2 Phase différée

Peuvent attendre :

- choix du broker donnant accès aux A-shares ou à Stock Connect ;
- paper trading broker natif ;
- ordres réels, rapprochement et statements CN ;
- short réellement exécutable ;
- flux temps réel complet.

Le moteur de backtest ne doit toutefois pas être simplifié sous prétexte que le broker viendra plus tard. Les règles de marché doivent être correctement simulées dès la première version.

## 4. `MarketContext` : contrat central à introduire

Créer une abstraction immuable, résolue au démarrage de chaque opération :

```python
MarketContext(
    market_code="CN_A",
    country_code="CN",
    base_currency="CNY",
    timezone="Asia/Shanghai",
    calendar_id="CN_A_CANONICAL",
    benchmark_instrument_id=...,
    sector_taxonomy="CITIC_OR_CSRC_VERSIONED",
    settlement_policy="CN_A_T1",
    execution_rules_profile="CN_A_RULES_V1",
    cost_profile="CN_A_RESEARCH_V1",
    feature_profile="cn_price_v1",
)
```

Le contexte doit être :

- passé explicitement par la CLI et les options IHM ;
- persisté dans les batches et runs ;
- inclus dans les manifests d’artefacts ;
- contrôlé au chargement d’un modèle ;
- transmis aux repositories ;
- affiché dans les diagnostics ;
- interdit de mutation pendant un run.

Valeurs initiales recommandées :

```text
US_EQ  = actions américaines actuelles
CN_A   = A-shares Shanghai + Shenzhen
CN_BJ  = Beijing Stock Exchange, phase ultérieure
```

Ne pas utiliser simplement `CN` pour toutes les places dès le début : les règles et distributions de Beijing peuvent nécessiter un profil distinct. `country_code='CN'` reste commun.

### 4.1 Registre de marchés

Créer à terme des fichiers versionnés :

```text
config/markets/us_eq.yaml
config/markets/cn_a.yaml
config/markets/cn_bj.yaml
```

Ils doivent définir les références, mais pas remplacer les historiques versionnés en base :

- calendrier et timezone ;
- benchmarks ;
- devise ;
- sources autorisées ;
- profils de coûts ;
- politique de lots ;
- politique T+1 ;
- politique de limites de prix ;
- éligibilité short ;
- familles de features compatibles.

## 5. Identité des instruments

### 5.1 Référentiel canonique

Créer une table dédiée, sans réutiliser `stock_metadata.symbol` comme identité :

```text
instruments
-----------
instrument_id            BIGINT PK
market_code              VARCHAR
country_code             CHAR(2)
exchange_mic             VARCHAR
local_symbol             VARCHAR
display_symbol           VARCHAR
name_local               VARCHAR
name_english             VARCHAR
currency                 CHAR(3)
asset_type               VARCHAR
board_code               VARCHAR
listing_date             DATE
delisting_date           DATE NULL
status                   VARCHAR
created_at / updated_at

UNIQUE(exchange_mic, local_symbol)
```

MIC initiaux :

- `XSHG` pour Shanghai ;
- `XSHE` pour Shenzhen ;
- `XBEI` pour Beijing lors de la phase dédiée ;
- MIC US existants pour le backfill.

### 5.2 Symboles fournisseurs

Créer une table historisée :

```text
instrument_provider_symbols
---------------------------
instrument_id
provider
provider_symbol
valid_from
valid_to
is_primary
metadata_json

UNIQUE(provider, provider_symbol, valid_from)
```

Exemples conceptuels :

```text
instrument 123 → local 600000 / XSHG
              → Tushare 600000.SH
              → EODHD éventuel 600000.SHG
              → broker futur <format broker>
```

Le suffixe fournisseur ne doit jamais devenir la clé métier.

### 5.3 Historique des états

Ajouter une table `instrument_status_history` :

- nom et ancien nom ;
- statut ST/*ST ou autre avertissement ;
- suspension/reprise ;
- board ;
- éligibilité Stock Connect ;
- éligibilité margin/lending ;
- listing/delisting ;
- `effective_from`, `effective_to`, `available_at`, source.

Une colonne mutable dans `stock_metadata` ne permet pas de reconstruire l’univers historique.

## 6. Stratégie de migration SQL

### 6.1 Ne pas faire un grand remplacement immédiat

Procéder par expansion, backfill, double lecture contrôlée, puis contraction :

1. créer `markets`, `instruments` et `instrument_provider_symbols` ;
2. backfiller tous les titres actuels comme `US_EQ` ;
3. ajouter `market_code` aux tables parentes de run/batch ;
4. ajouter `instrument_id` nullable aux tables canoniques ;
5. backfiller l’identité depuis les symboles US ;
6. écrire temporairement `symbol` et `instrument_id` ensemble ;
7. ajouter index, FK et contraintes de cohérence ;
8. basculer les lectures sur l’instrument ;
9. rendre `instrument_id` obligatoire ;
10. reconstruire les uniques qui reposent sur `symbol` seul ;
11. charger seulement ensuite les premières lignes CN canoniques.

Chaque étape doit avoir une migration Alembic et un SQL de référence, conformément aux conventions du projet.

### 6.2 Tables P0 à migrer avant tout chargement CN canonique

| Famille | Tables principales | Évolution minimale |
|---|---|---|
| Référentiel | `stock_metadata` | liaison `instrument_id`, marché, MIC, devise ; vue de compatibilité US si nécessaire |
| Barres | `stock_bars_daily`, `stock_bars` | `instrument_id`, session, devise, source ; nouvelles clés |
| Univers | `tradable_universe_runs`, `tradable_universe_history` | marché sur le run, instrument sur les membres |
| Scores | `stock_scores`, `stock_scores_history` | instrument, marché du run/preset, benchmark |
| ML parent | `model_training_batch`, `model_training_run`, registry/governance | marché, benchmark, calendrier, devise, fingerprint |
| ML sorties | `model_predictions`, `global_rank_history`, `global_oracle_labels`, `oracle_extreme_predictions` | instrument et barrières de cohérence marché/batch |
| Features | fondamentaux, sentiment, analystes, earnings | instrument, unité/devise, PIT, source |
| Backtest | runs et artefacts persistés | marché, devise, profils et versions de règles |

### 6.3 Tables P1 avant paper/live

- `risk_decisions` ;
- `portfolio_targets` ;
- positions, lots, ordres, fills et réconciliations ;
- corporate actions et cash ledger ;
- snapshots de compte ;
- idempotency keys et business keys.

Les contraintes actuelles telles que `(account_id, symbol)` devront employer `instrument_id`.

### 6.4 Héritage du marché

Il n’est pas nécessaire d’ajouter `market_code` partout si une ligne est strictement fille d’un parent immuable qui le porte. On peut cependant le dénormaliser lorsque nécessaire pour :

- empêcher une collision de clé ;
- partitionner ou requêter fréquemment ;
- imposer une barrière de sécurité ;
- produire un audit simple.

Toute dénormalisation doit être contrôlée contre le parent.

## 7. Calendrier, sessions et contrat PIT

### 7.1 Source de vérité

Le calendrier CN ne doit pas être un simple calendrier de jours de semaine, ni dépendre uniquement d’une bibliothèque Python.

Recommandation :

1. ingérer le calendrier officiel/fournisseur dans `market_sessions` ;
2. conserver `session_date`, place, ouvert/fermé, segments de session et heures UTC ;
3. exposer des fonctions génériques :

```text
session_dates(market_context, start, end)
session_bounds(market_context, session_date)
next_session(market_context, date, n)
previous_session(market_context, date, n)
advance_horizon(market_context, date, sessions)
decision_cutoff(market_context, session_date, dataset)
```

4. garder les wrappers NYSE pendant la transition pour préserver l’API US.

Le calendrier Tushare peut alimenter la base, puis être confronté à la place officielle. Cela couvre les jours fériés et changements exceptionnels. Les segments du midi doivent être représentables, même si les barres daily n’en ont pas besoin.

### 7.2 PIT

Chaque dataset CN doit porter :

```text
event_time
published_at
available_at
observed_at / ingested_at
source
source_revision
timezone
quality_state
```

Règle non négociable :

```text
available_at <= decision_cutoff
```

Interdictions :

- reconstruire toutes les disponibilités CN à une heure UTC fixe ;
- considérer la date comptable comme date de publication ;
- utiliser la dernière révision historique comme si elle était connue à l’époque ;
- forward-filler une suspension et rendre la valeur tradable ;
- utiliser une classification sectorielle actuelle sur tout le passé sans versionnement.

## 8. Architecture d’ingestion Chine

### 8.1 Adaptateur fournisseur

Introduire un contrat de fournisseur indépendant de Tushare :

```text
ChinaMarketDataProvider
├── fetch_security_master()
├── fetch_trade_calendar()
├── fetch_daily_bars()
├── fetch_adjustment_factors()
├── fetch_suspensions()
├── fetch_daily_limits()
├── fetch_money_flow()
├── fetch_margin_lending()
├── fetch_events()
├── fetch_financials()
└── fetch_forecasts_and_revisions()
```

La première implémentation sera Tushare. RQData pourra être ajouté sans changer les consommateurs.

Ne pas rendre le SDK Tushare obligatoire au cœur de l’application : isoler le client, les quotas, retries, cache et réponses brutes dans `service/tushare/`.

### 8.2 Staging brut

Les tables brutes Tushare peuvent rester spécifiques :

```text
cn_raw_security_master
cn_raw_trade_calendar
cn_raw_daily_bars
cn_raw_adj_factors
cn_raw_suspensions
cn_raw_daily_limits
cn_raw_money_flow
cn_raw_margin_lending
cn_raw_forecasts
cn_raw_research_reports
cn_raw_top_list
```

Chaque ligne brute doit inclure `provider_symbol`, `payload_hash`, `observed_at`, `available_at`, `run_id` et idéalement le payload source ou sa référence.

### 8.3 Canonicalisation des prix

Conserver séparément :

- OHLC brut réellement négociable ;
- volume et montant avec unité documentée ;
- facteur d’ajustement et sa provenance ;
- prix ajusté pour les features ;
- corporate actions ;
- statut de suspension ;
- prix limites haut/bas de la séance.

Pour le backtest, les fills utilisent les prix bruts. Pour les rendements/features, utiliser une convention ajustée documentée et testée. Il faut auditer si le facteur historique du fournisseur est révisé rétroactivement ; une série `qfq/hfq` reconstruite aujourd’hui ne doit pas être supposée automatiquement PIT.

### 8.4 Ordre des datasets

#### P0 — nécessaire à toute étude sérieuse

- référentiel complet avec délistés ;
- calendrier ;
- OHLCV et montant ;
- facteurs d’ajustement/corporate actions ;
- suspensions ;
- limites quotidiennes et statut de limite ;
- historique ST/nom/board ;
- indices benchmarks ;
- secteurs versionnés.

#### P1 — données recherchées pour D1/D10

- money flow ;
- margin financing et securities lending ;
- Dragon/Tiger list et motifs ;
- révisions de prévisions et rapports analystes ;
- annonces et événements structurés ;
- changements de holdings/institutionnels si disponibles PIT.

#### P2 — enrichissements

- données intraday ;
- order book/auction si accessibles légalement et à coût acceptable ;
- sentiment chinois avec modèle linguistique adapté ;
- relations actionnaire/groupe/chaîne industrielle.

Les données et fournisseurs sont détaillés dans :

- `doc/cn/comparaison_data_fournisseur.md` ;
- `doc/cn/actualisation_fournisseurs_chine.md`.

## 9. Univers chinois PIT

### 9.1 Première portée recommandée

Commencer avec des actions A ordinaires de Shanghai et Shenzhen :

- Main Board ;
- ChiNext et STAR conservés mais identifiés par `board_code` ;
- Beijing dans une étape séparée ;
- exclusion initiale des B-shares, ETF, fonds, obligations et produits structurés ;
- pas de survivorship bias ;
- présence des titres délistés dans l’historique ;
- exclusions quotidiennes motivées, pas un fichier statique construit aujourd’hui.

### 9.2 Publication quotidienne

Le résultat doit ressembler au flux US, mais avec des motifs CN :

```text
listed_as_of_date
not_delisted
not_suspended
history_sufficient
price_valid
liquidity_valid_local_currency
not_locked_limit_for_entry
st_policy_passed
board_policy_passed
corporate_action_quality_passed
```

Le statut `SHORT_SIGNAL_ONLY` doit être possible : l’instrument peut servir au modèle baissier comme veto sans être shortable.

### 9.3 Fichiers d’univers

Faire évoluer la convention vers :

```text
config/univers/us/*.txt
config/univers/cn/*.txt
```

avec un manifeste :

```json
{
  "market_code": "CN_A",
  "universe_id": "cn_a_liquid_research_v1",
  "symbols_file": "cn_a_liquid_research_v1.txt",
  "as_of_date": "2026-09-19",
  "currency": "CNY",
  "policy_version": "cn_a_universe_v1"
}
```

Le marché ne doit jamais être seulement déduit du chemin ou du suffixe du ticker.

## 10. Features et benchmarks

### 10.1 Baseline prix-only

La première baseline doit réutiliser seulement les familles compatibles :

- rendements et momentum ;
- trend/position ;
- volatilité/range/ATR ;
- volume et turnover correctement normalisés ;
- rangs cross-sectionnels CN ;
- relatif benchmark CN ;
- relatif secteur CN ;
- gaps et structure des trajectoires ;
- masques de suspension/limite/statut.

Ne pas injecter silencieusement SPY, VIX, VXN ou MOVE sous les mêmes noms.

### 10.2 Benchmark

Le benchmark doit être stocké dans le batch. La sélection doit dépendre de l’univers : indice large CN, CSI 300/500 ou benchmark composite. Avant de choisir, mesurer :

- couverture de l’univers ;
- stabilité de la relation ;
- historique disponible ;
- disponibilité PIT ;
- absence de biais créé par une population uniquement large-cap.

Les colonnes `SPY_*` devront devenir `benchmark_*`. Une compatibilité de noms peut être conservée pour les anciens artefacts US, mais un batch CN ne doit pas contenir un champ nommé `SPY_*` alimenté par un indice chinois.

### 10.3 Régime de marché

Créer un profil CN propre :

- tendance du benchmark ;
- breadth ;
- dispersion ;
- turnover ;
- proportion de titres limit-up/limit-down ;
- intensité margin/lending ;
- flux nordbound si la donnée est accessible et son contrat PIT valide.

Le service `service/market/` est injectable pour certaines sources, mais ses configurations et écrans restent aujourd’hui fortement VIX/US.

### 10.4 Secteurs

Choisir une taxonomie versionnée et stocker le mapping fournisseur → taxonomie canonique. Les neutralisations ne doivent pas mélanger des secteurs US et CN partageant un libellé similaire.

## 11. ML, Oracle et direction

### 11.1 Batches strictement mono-marché

Ajouter au manifeste et à `model_training_batch` :

```text
market_code
calendar_id/version
timezone
base_currency
benchmark_instrument_id
universe_id + fingerprint
sector_taxonomy/version
bars_source/version
feature_profile/version
label_policy/version
execution_rules_profile/version
```

Le chargement doit échouer si l’un de ces contrats est incompatible avec la demande de prédiction.

### 11.2 Oracle Extreme

Le code Oracle peut être réutilisé à condition de garantir :

1. univers quotidien uniquement CN ;
2. horizons avancés selon les sessions CN ;
3. labels D1–D10 classés uniquement au sein du marché et de l’univers du jour ;
4. minimum de titres par date ;
5. contrôle des suspensions et barres réelles à D et D+H ;
6. `oracle_available_date` construit avec le calendrier CN ;
7. folds strictement causaux ;
8. prédictions et artefacts marqués `CN_A`.

La fonction de ranking ne doit pas simplement rester `groupby('date')` en espérant que le dataset soit bien filtré. Ajouter une assertion bloquante d’homogénéité et, dans les composants réutilisables, supporter explicitement `(market_code, date)`.

### 11.3 Modèles directionnels

Ordre expérimental recommandé :

```text
CN-B0 : Oracle amplitude prix-only
CN-B1 : direction prix-only conditionnée sur Oracle OOF
CN-B2 : + money flow
CN-B3 : + margin/lending
CN-B4 : + analyst revisions/forecast changes
CN-B5 : combinaison pré-enregistrée des seules familles validées
```

Mesurer séparément :

- amplitude Oracle ;
- D1 vs D10 ;
- LONG vs abstention ;
- SHORT comme veto ;
- valeur économique après règles de marché et coûts.

Le transfert d’un champion US vers CN est autorisé uniquement comme expérience nommée. Il ne doit jamais être auto-sélectionné comme champion CN.

### 11.4 Modèle per-symbol

Le marché CN peut avoir plus de suspensions et moins d’historique pour certains titres. La couverture servable doit rester distincte de la couverture entraînée, comme dans le bundle actuel. Le modèle mutualisé/sectoriel doit être comparé au per-symbol ; ne pas supposer que le meilleur choix US reste le meilleur en Chine.

## 12. Backtest A-shares

### 12.1 Nouveau `ExecutionRulesProfile`

Les règles doivent être versionnées par place, board, statut et date :

```text
exchange_mic
board_code
effective_from / effective_to
timezone
session_segments
buy_lot_size
sell_odd_lot_policy
tick_size
same_day_sell_allowed
settlement_days
price_limit_policy
ipo_exception_policy
st_policy
short_allowed
```

Les règles évoluent. Elles ne doivent pas être codées comme un unique `10%` permanent. Les pages officielles SSE/SZSE montrent déjà des différences Main Board, STAR et ChiNext, ainsi que des exceptions IPO et des évolutions récentes.

Références de validation à conserver lors de l’implémentation :

- [SSE — Stock Trading Mechanism](https://english.sse.com.cn/start/trading/mechanism/) ;
- [SZSE — Trading Overview](https://investor.szse.cn/English/services/trading/tradOverview/index.html) ;
- [SZSE — Special Rules on Trading on ChiNext](https://www.szse.cn/English/rules/siteRule/P020200811392728112984.pdf).

Les règles définitives devront être revérifiées auprès des places et du broker au moment de l’activation live.

### 12.2 T+1

Le `swing_only` actuel interdit certaines sorties le jour d’entrée, mais ne constitue pas à lui seul un moteur de settlement CN complet.

Le backtest doit suivre les lots :

- quantité achetée aujourd’hui non vendable avant la prochaine session autorisée ;
- quantité antérieure vendable ;
- corporate actions et odd lots conservés ;
- cash et titres suivis séparément ;
- aucune protection simulée ne doit vendre une quantité encore bloquée.

### 12.3 Limites de prix et suspensions

Le moteur actuel n’a pas de politique CN complète.

Politique conservatrice initiale :

- aucune entrée sur titre suspendu ;
- aucune sortie pendant suspension ;
- achat considéré non rempli si le titre est verrouillé au limit-up sans liquidité démontrable ;
- vente considérée non remplie si verrouillée au limit-down ;
- si OHLC daily ne permet pas de prouver le fill, appliquer l’hypothèse défavorable ;
- enregistrer le motif de non-fill ;
- tester séparément une sensibilité plus permissive.

L’état de limite doit provenir d’un dataset dédié quand disponible, pas uniquement d’un calcul flottant à partir de la clôture précédente.

### 12.4 Lots et quantités

Le moteur actuel privilégie les fractions pour certains comptes US. Un profil CN doit :

- désactiver les fractions ;
- arrondir les achats au lot autorisé ;
- gérer la vente d’un reliquat conformément à la règle effective ;
- distinguer Main Board et boards particuliers ;
- rejeter ou réduire une position devenue inférieure au lot minimal d’achat.

### 12.5 Coûts et devise

Remplacer le contrat purement `*_usd` par des objets monétaires :

```text
Money(amount, currency)
Liquidity(notional_local, currency, fx_rate_asof)
CostBreakdown(commission, transfer_fee, stamp_duty, slippage, currency)
```

Le profil de coûts doit pouvoir exprimer :

- commission avec éventuel minimum ;
- frais de place/transfert ;
- taxe selon le côté ;
- slippage ;
- coût FX et frais du canal d’accès ;
- dates d’effet des barèmes.

Ne pas figer aujourd’hui des valeurs réglementaires dans le code. Construire la capacité, puis valider les montants avec le canal réel.

### 12.6 SHORT

Pour la première version :

```text
signal LONG  → peut générer un achat si tous les gates passent
signal SHORT → veto LONG / abstention / score de risque
```

La vente à découvert ne sera activée qu’avec :

- éligibilité instrument PIT ;
- disponibilité de prêt ;
- frais d’emprunt ;
- broker/canal compatible ;
- simulation et rapprochement validés.

## 13. Risque et portefeuille

Le code possède déjà des limites pays/devise, mais les objets en amont ne fournissent pas toujours ces attributs.

À rendre explicite :

- budget de risque par marché ;
- exposition par pays, devise, place et board ;
- cash par devise ;
- FX PIT pour consolidation ;
- corrélations avec calendriers non alignés sans forward-fill abusif ;
- limites sectorielles propres à la taxonomie CN ;
- haircut de liquidité ;
- concentration liée aux limites de prix et suspensions ;
- kill switch par marché.

Un portefeuille US+CN consolidé viendra après deux moteurs mono-marché fiables. Les rankings, labels et modèles restent mono-marché même si le risque agrège ensuite les expositions.

## 14. IHM et expérience opérateur

Ajouter un sélecteur de marché dans les pages concernées, mais ne pas utiliser un singleton global.

Le choix doit être propagé et persisté :

```text
IHM → options de commande → batch/run → repositories → artefacts
```

### 14.1 Pages à adapter

- Pipeline : marché, univers, fournisseur, benchmark et profils compatibles ;
- Diagnostic ML : batches filtrés par marché, badge marché/benchmark/horizon ;
- Prédiction : empêcher de charger un artefact US pour un univers CN ;
- Backtest : marché déduit du batch puis verrouillé, profils CN visibles ;
- Univers/screener : seuils dans la bonne devise ;
- Batch/data quality : fraîcheur par calendrier et fournisseur ;
- Positions/exécution : marché et broker compatibles ;
- rapports : PnL local et PnL converti séparés.

### 14.2 États UI recommandés

```text
US — Actions américaines            actif
CN A — Shanghai + Shenzhen          actif après gates P0–P4
CN Beijing                          désactivé / phase suivante
Tous marchés                        lecture/risque seulement au départ
```

Un batch doit être affiché ainsi :

```text
CN_A · H20 · Oracle + Direction · CSI xxx · batch-id
```

### 14.3 Contrôles bloquants

L’IHM et la CLI doivent refuser :

- batch sans `market_code` résolu ;
- fichier d’univers d’un autre marché ;
- benchmark incompatible ;
- mélange de marchés dans un entraînement cross-sectionnel ;
- prédiction CN avec modèle US hors mode transfert explicite ;
- backtest CN avec calendrier NYSE ou profil de coûts US ;
- activation live sans broker compatible.

## 15. Exécution future

`core/interfaces.py` déclare déjà un `BrokerClient`, mais `execution_engine/broker_adapter.py` est concrètement Alpaca : imports Alpaca, statuts Alpaca, payloads Alpaca et quotes Alpaca.

Avant un broker CN, refactorer ultérieurement en :

```text
ExecutionBrokerPort
├── submit_order
├── cancel/replace
├── get_orders/fills/positions/account
├── get_market_clock
├── get_instrument_capabilities
├── get_short_availability
└── stream_events

AlpacaBrokerAdapter
ChinaBrokerAdapter (futur)
Mock/ReplayBrokerAdapter
```

Ajouter un routeur `(market_code, account_id) → broker adapter`.

Cette phase n’est pas requise pour entraîner et backtester, mais l’identité instrument et les règles d’exécution doivent être prêtes afin de ne pas refaire les migrations.

## 16. Roadmap de réalisation

### P0 — Contrats et non-régression US

Objectif : rendre le système market-aware sans changer les résultats US.

Travaux :

1. écrire les ADR `MarketContext`, identité instrument et héritage du marché ;
2. créer registre des marchés ;
3. créer tables instruments/mappings/sessions/règles ;
4. ajouter marché aux parents de runs et batches ;
5. backfiller `US_EQ` ;
6. introduire APIs génériques de calendrier avec wrappers NYSE ;
7. faire porter le contexte aux loaders ;
8. enrichir les manifests d’artefacts ;
9. interdire les datasets cross-market ;
10. établir des runs US golden avant/après.

Gate :

- suite de tests actuelle verte ;
- parité bit-for-bit des signaux US de référence ;
- aucune variation de PnL hors métadonnées ajoutées ;
- toutes les lignes US P0 reliées à un `instrument_id` ;
- aucune requête canonique critique ne dépend uniquement du symbole.

### P1 — Connecteur et staging Tushare

Objectif : accumuler l’historique brut sans exposer encore le reste de l’application.

Travaux :

- client, authentification, quotas, retries et cache ;
- référentiel, calendrier, barres, ajustements, suspensions et limites ;
- payload hash, lineage et reprise idempotente ;
- rapports demandés/reçus/persistés/échecs/alertes ;
- batchs visibles dans Workflow & Orchestration ;
- data quality par endpoint.

Gate :

- couverture documentée ;
- unités validées manuellement sur échantillon ;
- idempotence ;
- délistés présents ;
- aucune écriture dans les tables US.

### P2 — Canonicalisation et univers CN PIT

Objectif : produire un panel quotidien de recherche fiable.

Travaux :

- mapping vers `instrument_id` ;
- barres brutes/ajustements ;
- sessions CN ;
- statuts/suspensions/limites ;
- secteurs ;
- univers PIT ;
- benchmark ;
- audits de continuité et corporate actions.

Gate :

- aucun survivorship bias détecté sur les dates tests ;
- sessions/horizons corrects ;
- suspensions non tradables ;
- limites correctement identifiées ;
- réconciliation fournisseur/canonique sur un échantillon multi-années.

### P3 — Baseline ML CN

Objectif : valider l’infrastructure ML avant les nouvelles données directionnelles.

Travaux :

- profil `cn_price_v1` ;
- features benchmark/secteur génériques ;
- Oracle H5/H10/H15/H20 selon protocole pré-enregistré ;
- ranking et modèles directionnels ;
- diagnostics par année, semestre, board et régime ;
- comparaison per-symbol, sectoriel et mutualisé.

Gate :

- folds OOS valides ;
- aucune fuite PIT ;
- Oracle détecte l’amplitude au-delà de la baseline ;
- résultats stables sur plusieurs fenêtres ;
- couverture servable explicite.

### P4 — Données directionnelles chinoises

Objectif : répondre à D1/D10 avec des données réellement nouvelles.

Travaux :

- money flow ;
- margin/lending ;
- analyst forecasts/revisions ;
- Dragon/Tiger et événements ;
- ablations une famille à la fois ;
- correction des comparaisons multiples ;
- combinaison seulement après preuve OOF.

Gate :

- gain incrémental OOF séparé LONG/SHORT ;
- stabilité temporelle ;
- amélioration économique nette ;
- pas seulement une amélioration moyenne dominée par quelques dates.

### P5 — Backtest économique CN

Objectif : convertir le signal en stratégie réaliste.

Travaux :

- T+1 par lots ;
- lots/ticks ;
- suspensions ;
- non-fills aux limites ;
- coûts et taxes versionnés ;
- devise/FX ;
- short-veto ;
- stress tests.

Gate :

- performance après coûts ;
- sensibilité conservatrice aux fills ;
- drawdown et liquidité acceptables ;
- aucune hypothèse impossible à exécuter.

### P6 — IHM et exploitation recherche

Objectif : permettre un usage quotidien sûr.

- switch par opération ;
- listes filtrées ;
- diagnostics CN ;
- monitoring de données ;
- comparaison de runs ;
- export des univers et candidats ;
- documentation opérateur.

### P7 — Paper/shadow puis live

Objectif : activer l’exécution seulement après choix du canal.

- adapter le port broker ;
- shadow mode sans ordre ;
- paper si le broker le permet ;
- rapprochement cash/positions/ordres ;
- préflight règles et permissions ;
- canary avec capital minimal ;
- kill switch CN indépendant ;
- promotion graduelle.

## 17. Backlog par module

| Module actuel | Évolution future |
|---|---|
| `common/market_calendar.py` | registre et APIs génériques ; conserver wrappers NYSE |
| `common/data_availability.py` | timezone/cutoff par source et marché ; supprimer les défauts implicites des appels critiques |
| `common/universe_files.py` | manifeste et validation marché, sans casser les fichiers US |
| `common/tradable_universe.py` | règles par marché et montants avec devise |
| `database/sql/stock/*` | migration instrument/marché/devise/identités |
| `database/sql/ml/*` | marché parent, instrument et clés sûres |
| `modelFactory/data_loader.py` | requêtes par instrument + marché |
| `modelFactory/cross_sectional.py` | scope marché explicite et assertions mono-marché |
| `modelFactory/oracle/*` | calendrier, labels, groupes et manifests market-aware |
| `modelFactory/orchestrator.py` | persister/valider `MarketContext` |
| `modelFactory/predictor.py` | refuser incompatibilités artefact/marché/univers |
| `screener/`, `selector/` | supprimer le contrat exclusif `us_equity`, généraliser benchmark/devise |
| `backtesting/data_loader.py` | scope instrument/marché obligatoire |
| `backtesting/cli/_impl.py` | retirer NYSE/SPY implicites, sélectionner profils CN |
| `backtesting/simulator.py` | T+1 lots, limites, suspensions, lots, coûts multi-devise |
| `backtesting/microstructure.py` | notionnels génériques et modèle CN |
| `risk_management/` | propagation pays/devise/marché/board/FX |
| `execution_engine/` | séparer port générique et adaptateur Alpaca concret |
| `ihm/pages/pipeline.py` | marché et options compatibles |
| `ihm/pages/ml.py` | batches et diagnostics filtrés |
| `ihm/pages/backtesting/` | marché déduit/verrouillé, profils CN visibles |
| `service/forward_pit/` | ne pas étendre aveuglément les batchs SEC/FINRA US au CN ; nouveaux handlers dédiés |

## 18. Plan de tests

### 18.1 Non-régression US

- calendriers NYSE identiques avant/après ;
- mêmes barres chargées ;
- mêmes features/rangs/labels ;
- mêmes prédictions ;
- mêmes ordres simulés et PnL ;
- mêmes commandes IHM par défaut ;
- batches anciens sans champ marché interprétés temporairement comme `US_EQ`, avec warning et date de fin de compatibilité.

### 18.2 Identité et isolation

- deux instruments ayant le même symbole local sur deux places restent distincts ;
- aucun upsert CN n’écrase une ligne US ;
- chaque batch a exactement un marché ;
- chaque prédiction hérite du marché du batch ;
- une jointure symbole seule est détectée dans les repositories critiques ;
- `ALL` interdit pour les rangs et labels.

### 18.3 Calendrier et PIT

- jours fériés US/CN indépendants ;
- horizon H20 = 20 sessions du marché ;
- cutoff converti correctement en UTC ;
- publication après cutoff disponible seulement à la session suivante ;
- suspension non forward-fillée comme tradable ;
- révision fondamentale/analyste non visible avant `available_at`.

### 18.4 ML

- rangs/secteurs par marché ;
- benchmark compatible ;
- folds sans chevauchement ni labels non disponibles ;
- manifest complet ;
- serving bloqué sur incompatibilité ;
- couverture entraînée vs servable ;
- anciens artefacts US toujours chargeables pendant la période de compatibilité.

### 18.5 Backtest CN

- pas de vente du lot acheté le jour même ;
- entrée/sortie bloquée sur suspension ;
- non-fill conservateur au limit-up/limit-down ;
- lots et odd lots ;
- tick size ;
- coûts asymétriques buy/sell ;
- devise locale et conversion FX PIT ;
- short bloqué ou transformé en veto ;
- corporate actions et délistage.

### 18.6 IHM

- aucune liste ne mélange les marchés ;
- changement de batch recalcule/verrouille le marché ;
- erreurs lisibles en cas d’incompatibilité ;
- marché affiché sur chaque run, artefact, prédiction et backtest ;
- CN live reste désactivé tant que P7 n’est pas validé.

## 19. Gates de sécurité obligatoires

Avant ingestion canonique CN :

- [ ] instruments et mappings créés ;
- [ ] migrations US terminées ;
- [ ] calendrier générique disponible ;
- [ ] loaders P0 scopés ;
- [ ] parité US validée.

Avant entraînement CN :

- [ ] univers PIT sans survivorship bias ;
- [ ] barres/ajustements validés ;
- [ ] suspensions et limites présentes ;
- [ ] benchmark/secteurs définis ;
- [ ] manifests market-aware.

Avant backtest CN publiable :

- [ ] T+1 ;
- [ ] lots/ticks ;
- [ ] limites/suspensions ;
- [ ] coûts versionnés ;
- [ ] devise/FX ;
- [ ] hypothèses de fill documentées.

Avant paper/live :

- [ ] broker et permissions validés ;
- [ ] symbologie broker réconciliée ;
- [ ] préflight CN ;
- [ ] rapprochement ;
- [ ] shadow/canary ;
- [ ] kill switch par marché.

## 20. Anti-patterns à éviter

- ajouter seulement une colonne `market` dans l’IHM ;
- charger `600000.SH` dans `stock_bars_daily` actuelle et considérer le suffixe comme identité ;
- créer une copie complète `china_*` de chaque table métier ;
- mélanger US et CN dans un rang quotidien ;
- réutiliser SPY/VIX sous des noms inchangés ;
- convertir toutes les valeurs en USD sans conserver valeur/devise locale ;
- forward-filler une suspension ;
- simuler un fill garanti à la limite de prix ;
- utiliser le modèle SHORT comme vente à découvert par défaut ;
- sélectionner les survivants actuels pour un backtest historique ;
- coder les règles chinoises comme constantes sans période d’effet ;
- activer live avant que le backtest et le shadow mode soient validés.

## 21. Ordre recommandé pour commencer l’implémentation

Le premier lot de travail ne doit contenir aucune donnée CN. Il doit uniquement créer la fondation multi-marché et prouver la non-régression US :

```text
Lot 1
  ADR + MarketContext + registre marchés
  instruments + provider symbols + market sessions
  market_code sur batches/runs
  backfill US
  APIs calendrier génériques
  manifests enrichis
  tests d’isolation et golden US

Lot 2
  instrument_id sur barres/univers/scores/ML
  double écriture contrôlée
  migration des loaders et jointures
  reconstruction des contraintes
  suppression progressive des lectures symbol-only critiques

Lot 3
  service/tushare + staging P0
  canonicalisation CN
  univers PIT CN
  contrôles qualité

Lot 4
  baseline ML + Oracle CN
  prédiction et diagnostic
  backtest CN réaliste

Lot 5
  données directionnelles et ablations
  IHM complète

Lot 6
  broker/shadow/paper/live
```

## 22. Verdict final

L’application peut accueillir durablement le marché chinois et réutiliser une grande partie de son moteur ML. Le principal effort ne concerne pas les architectures LSTM/LightGBM/CatBoost : il concerne l’identité, le temps, le scope des données et la simulation économique.

La priorité absolue est donc :

> **rendre α-Trade réellement market-aware tout en conservant une parité US démontrée, puis charger les données CN dans un modèle canonique commun.**

Une fois cette fondation achevée, Tushare permettra de produire les études, d’entraîner Oracle et les modèles directionnels, et d’exécuter des backtests CN sans attendre le choix d’un broker. Le broker deviendra ensuite un adaptateur supplémentaire, pas une raison de reconstruire le système.

## 23. Documents liés

- [Étude d’opportunité — Extension d’α-Trade au marché actions chinois](./Étude%20d’opportunité%20—%20Extension%20d’α-Trade%20au%20marché%20actions%20chinois.md) : étude métier et hypothèses initiales ; à lire comme contexte, pas comme vérité du code.
- [Comparaison des données fournisseurs](./comparaison_data_fournisseur.md) : couverture Tushare face aux données US actuelles.
- [Actualisation des fournisseurs Chine](./actualisation_fournisseurs_chine.md) : positionnement Tushare, RQData et sources institutionnelles.

