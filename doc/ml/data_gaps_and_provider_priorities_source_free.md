# Forward PIT Collector — sources gratuites vérifiées pour P0 à P4

**Date de vérification : 2026-09-12**  
**Objectif :** construire, à partir d'aujourd'hui, un historique *point-in-time* (PIT) propre en collectant chaque jour les données disponibles gratuitement, plutôt que d'acheter immédiatement un historique 2016–2025.

Ce document est destiné à être donné directement à une IA / un développeur pour implémentation.

---

## 1. Résumé exécutable

### Sources gratuites à implémenter en priorité

| Source | Gratuit vérifié | Compte / clé | Limites importantes | Usage recommandé |
|---|---:|---:|---|---|
| **SEC EDGAR / data.sec.gov** | ✅ Oui | ❌ Pas de clé | max ~10 req/s, User-Agent déclaré | P0 fondamentaux PIT, P3 8-K/6-K, P4 13F/13D/13G |
| **Business Quant Free** | ✅ Oui, plan $0 | ✅ API key | **30 appels/jour**, **0,1 Go/mois** | P0 OHLCV EOD, corporate actions, universe ; P1 consensus partiel ; P3 minute bars sur petit sous-univers |
| **Nasdaq Trader Symbol Directory** | ✅ Accès public | ❌ | usage **interne non commercial** pour certaines données | P0 universe/security master forward |
| **FINRA Daily Short Sale Volume** | ✅ Fichiers publics | ❌ pour fichiers | ne remplace PAS borrow/lending | P1 contrôle / contexte seulement |
| **FRED / ALFRED API** | ✅ API gratuite | ✅ clé gratuite | droits de certaines séries tierces à respecter | P4 macro + vintages PIT |
| **Alpaca Basic** | ✅ $0/mois | ✅ compte + API key | actions temps réel = **IEX seulement** ; options = **indicative** | backup corporate actions, borrow status partiel, P2 options partielles |
| **Cboe delayed options web** | ✅ consultation manuelle | — | ❌ extraction automatisée interdite | **NE PAS UTILISER pour le collecteur** |

### Ce qui n'a PAS de solution gratuite complète vérifiée

| Besoin | Statut |
|---|---|
| **P1 borrow fee + utilization + lendable supply + shares on loan** | ❌ Pas de source gratuite complète validée |
| **P1 NYSE/Nasdaq auction imbalance / NOII complet et automatisable** | ❌ Pas de source gratuite complète validée |
| **P1 révisions analystes individuelles PIT** | ❌ Pas de source gratuite complète validée |
| **P2 OPRA NBBO options complet + OI + historique contractuel dense** | ❌ Pas gratuit ; Alpaca Free ne donne qu'un flux indicatif partiel |

---

# 2. Règle architecturale principale

Le collecteur doit être conçu comme un **Forward PIT Collector**.

Il ne faut jamais écraser une observation ancienne.

```text
provider
  ↓
collecte brute
  ↓
RAW append-only
  ↓
normalisation versionnée
  ↓
PIT snapshots
  ↓
features ML
```

Chaque payload reçu doit être conservé brut, même si le parseur sait déjà l'interpréter.

Schéma minimal commun :

```text
provider
dataset
security_id
ticker
cik
exchange

economic_at
published_at
provider_timestamp
received_at
effective_from
effective_to

provider_event_id
revision
is_correction
is_deleted

raw_payload
raw_sha256

collector_version
schema_version
ingested_at
```

`received_at` doit être généré par notre propre serveur.

**RAW = append-only : aucun UPDATE/DELETE physique.**

Les corrections doivent créer une nouvelle version.

---

# 3. P0 — Fondation scientifique

## P0.1 — Universe / security master PIT

### Source primaire : Nasdaq Trader Symbol Directory

**Statut : gratuit/public pour consultation et téléchargement, mais attention à la licence.**

Fichiers :

```text
ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt
ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt
```

Documentation :

https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs

Nasdaq indique que les fichiers sont mis à jour périodiquement pendant la journée.

`otherlisted.txt` permet notamment de couvrir NYSE, NYSE Arca, BATS/Cboe et IEX.

### Contrainte de licence

La page Nasdaq indique que certaines données du Symbol Directory sont destinées à un **usage interne non commercial**, sauf licence séparée.

Donc :

- ✅ acceptable pour recherche personnelle/interne ;
- ⚠️ ne pas redistribuer ;
- ⚠️ vérifier licence avant utilisation commerciale/client-facing.

### Collecte

Snapshot complet chaque jour :

```text
raw/nasdaq_symbol_directory/YYYY-MM-DD/
    nasdaqlisted.txt
    otherlisted.txt
    metadata.json
```

Comparer J et J-1 pour dériver :

```text
NEW_LISTING
MISSING_FROM_DIRECTORY
SYMBOL_CHANGE_CANDIDATE
NAME_CHANGE
EXCHANGE_CHANGE
INSTRUMENT_CHANGE
ETF_FLAG_CHANGE
```

Une disparition du fichier **n'est pas automatiquement un delisting confirmé**.

---

## P0.2 — Universe secondaire / ticker ↔ CIK

### Source : Business Quant Universe API

**Statut : API gratuite.**

Endpoint :

```text
GET https://data.businessquant.com/universe?api_key=...
```

Documentation :

https://businessquant.com/docs/api/universe

Le endpoint retourne l'univers couvert en un seul appel et fournit notamment :

```text
ticker
CIK
name
exchange
security_type
sector
industry
```

### Usage

Faire **1 snapshot/jour**.

Utiliser principalement :

- validation du Symbol Directory ;
- mapping ticker ↔ CIK ;
- détection de nouvelles entrées/sorties ;
- enrichissement du security master.

Ne pas utiliser `sector/industry` comme vérité PIT sans versionnement quotidien.

---

## P0.3 — Corporate actions

### Source primaire recommandée : Business Quant Corporate Actions

**Statut : API gratuite ; clé requise ; aucune carte bancaire annoncée pour l'API corporate actions.**

Documentation :

https://businessquant.com/docs/api/corporate-actions

Types couverts annoncés :

```text
dividend
split
merger
acquisition
spinoff
bankruptcy
delisting
```

Le dataset expose également des variantes telles que :

```text
listed
delisted
ticker_adopted
ticker_retired
merged_into
merged_with
spinoff_from
spinoff_dividend
```

### Point très important pour le quota gratuit

Ne pas faire 500 appels par ticker.

Faire une requête **market-wide par date** :

```text
/corporate_actions?action=all&from_date=YYYY-MM-DD&till_date=YYYY-MM-DD&limit=10000
```

Puis paginer seulement si nécessaire.

Coût typique :

```text
1 à quelques appels / jour
```

### Source secondaire : Alpaca Corporate Actions

En septembre 2026, la documentation Alpaca expose :

```text
GET https://data.alpaca.markets/v1/corporate-actions
```

Types :

```text
reverse_split
forward_split
unit_split
cash_dividend
stock_dividend
spin_off
cash_merger
stock_merger
stock_and_cash_merger
redemption
name_change
worthless_removal
rights_distribution
```

Documentation :

https://docs.alpaca.markets/us/reference/corporateactions-1

Le plan Alpaca **Basic est actuellement affiché à $0/mois**, et la page de pricing indique Corporate Actions inclus.

Cependant :

- faire un test réel avec la clé Basic ;
- si réponse `403`, garder Business Quant comme primaire ;
- ne pas bloquer le pipeline P0 sur Alpaca.

### Réconciliation

```text
Business Quant event
        +
Alpaca event si disponible
        +
SEC filing lorsque pertinent
        ↓
canonical_corporate_action
```

---

## P0.4 — OHLCV quotidien

### Source recommandée : Business Quant EOD Stock Price API

**Statut : gratuit.**

Documentation :

https://businessquant.com/docs/api/quotes

Supporte les requêtes multi-tickers.

Exemple :

```text
/quotes?ticker=AAPL,MSFT,...&mode=eod&period=1d
```

### Pourquoi utiliser Business Quant plutôt qu'Alpaca Free comme source principale

Alpaca Basic est gratuit, mais le temps réel actions du plan Basic est limité à **IEX**.

Pour la recherche US cross-sectionnelle, éviter d'utiliser un flux temps réel IEX comme s'il était un flux consolidé SIP.

Business Quant est donc le candidat gratuit à auditer en priorité pour l'EOD.

### Implémentation

Pour ~500 actions :

```text
batch_size = 50 à 100 tickers
```

Faire quelques appels multi-tickers après la clôture.

Stocker :

```text
date
ticker
open
high
low
close
volume
provider_timestamp si disponible
received_at
```

### Contrôles

Chaque jour :

- comparer close à une seconde source sur échantillon ;
- vérifier split discontinuities ;
- vérifier volume anormalement nul ;
- conserver le payload brut.

---

## P0.5 — Fondamentaux SEC PIT

### Source : SEC EDGAR

**Statut : totalement gratuit, sans API key.**

Documentation officielle :

https://www.sec.gov/search-filings/edgar-application-programming-interfaces

Les API `data.sec.gov` donnent notamment :

- submissions history ;
- XBRL company facts ;
- 10-K ;
- 10-Q ;
- 8-K ;
- 20-F ;
- 40-F ;
- 6-K ;
- amendements.

### Fair Access

La SEC indique actuellement :

```text
maximum ≈ 10 requêtes / seconde
```

Le collecteur doit déclarer un User-Agent :

```http
User-Agent: Alpha-Trade contact@example.com
Accept-Encoding: gzip, deflate
```

### À conserver pour chaque filing

```text
CIK
accession_number
form
filing_date
acceptance_datetime
report_period
primary_document
all documents/exhibits
XBRL contexts
tags
units
values
raw filing
raw submission JSON
received_at
```

Ne jamais remplacer une valeur ancienne par un restatement ultérieur.

---

# 4. P1 — Données directionnelles

## P1.1 — Borrow / stock lending

### Gratuit réellement disponible : seulement PARTIEL

#### Alpaca Asset `borrow_status`

La documentation Alpaca a ajouté en juin 2026 :

```text
borrow_status
```

sur :

```text
GET /v2/assets
GET /v2/assets/{symbol_or_asset_id}
```

`easy_to_borrow` est en cours de dépréciation.

Documentation :

https://docs.alpaca.markets/us/changelog/2026-06-05-borrow-status-6b96a5a

### Ce que l'on peut stocker gratuitement

```text
symbol
shortable
borrow_status
timestamp_received
```

Faire un snapshot quotidien ou plusieurs snapshots intraday.

### Ce que cela NE fournit PAS

Ne pas inventer :

```text
borrow_fee
rebate_rate
global_utilization
lendable_supply
shares_on_loan
locate_price
locate_size
```

Le vrai P1 lending reste :

```text
PENDING_PAID_PROVIDER
```

et doit être distingué du simple `borrow_status`.

---

## P1.2 — FINRA Daily Short Sale Volume

### Source : FINRA

**Statut : fichiers publics téléchargeables gratuitement.**

Page officielle :

https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files

FINRA publie les fichiers quotidiens au plus tard vers **18:00 ET** et conserve les versions corrigées lorsqu'un fichier est mis à jour.

Le fichier consolidé NMS est disponible depuis août 2018.

### Collecte

```text
schedule_et = 18:30
```

Télécharger :

```text
Consolidated TRF/ADF Daily Short Sale Volume
```

Conserver toutes les versions :

```text
original
updated_v1
updated_v2
...
```

### Important

Cette donnée :

- n'est PAS le short interest ;
- n'est PAS le borrow fee ;
- n'est PAS l'utilisation du stock-loan ;
- n'est PAS la supply disponible.

Utiliser seulement comme :

```text
context/control feature
```

et non comme substitut au P1 stock lending.

---

## P1.3 — Auction imbalance / NYSE + Nasdaq NOII

### Statut

```text
NO_FREE_COMPLETE_AUTOMATABLE_SOURCE_VERIFIED
```

Ne pas scraper une page web publique pour simuler un feed.

Le besoin reste :

```text
paired shares
imbalance shares
imbalance side
reference price
indicative price
near/far prices
timestamps de chaque update
opening/closing auction
```

Créer l'interface maintenant :

```text
AuctionImbalanceProvider
```

mais implémenter :

```text
status = PENDING_PROVIDER
```

pour permettre l'ajout ultérieur de NYSE TAQ / Nasdaq NOII.

---

## P1.4 — Analyst estimates / revisions

### Source gratuite partielle : Business Quant Analyst Estimates

**Statut : API gratuite, MAIS limitée par le plan Free.**

Documentation :

https://businessquant.com/docs/api/estimates

Données :

```text
EPS consensus
Revenue consensus
high estimate
low estimate
reported actual
annual periods
quarterly periods
```

### Limitation critique

Le plan gratuit Business Quant est actuellement :

```text
$0
30 API calls / day
0.1 GB transfer / month
```

et l'endpoint analyst estimates prend **un ticker ou un CIK à la fois**.

Donc il est impossible de snapshotter correctement :

```text
500 tickers × EPS + Revenue
```

tous les jours gratuitement.

### Stratégie gratuite réaliste

Comme Alpha-Trade travaille conditionnellement sur l'Oracle Extreme :

Option A :

```text
TOP20 Oracle
EPS only
= 20 appels / jour
```

compatible avec le quota de 30.

Option B :

```text
TOP15 Oracle
EPS + Revenue
= 30 appels / jour
```

compatible avec le quota de 30.

### Stocker chaque snapshot

```text
ticker
metric = EPS | REVENUE
fiscal_period
period_end
consensus
high
low
actual_if_known
received_at
```

Puis reconstruire nos propres :

```text
consensus_revision_1d
consensus_revision_5d
breadth_proxy
dispersion_proxy = high - low
revision_acceleration
```

### Ne pas appeler cela "individual analyst revisions"

Ce dataset ne contient pas la trajectoire individuelle de chaque analyste/broker.

Marquer :

```text
dataset_class = CONSENSUS_SNAPSHOT_FORWARD
```

et non :

```text
dataset_class = ANALYST_LEVEL_REVISION_PIT
```

---

# 5. P2 — Options

## Source gratuite partielle : Alpaca Basic Options Indicative Feed

### Prix

Alpaca affiche actuellement :

```text
Basic = $0/mois
```

### Option chain

Endpoint :

```text
GET /v1beta1/options/snapshots/{underlying_symbol}
```

Documentation :

https://docs.alpaca.markets/us/reference/optionchain

Le endpoint fournit :

```text
latest trade
latest quote
greeks
```

Pour un compte sans abonnement OPRA :

```text
feed = indicative
```

La documentation précise :

- trades retardés ;
- quotes modifiées ;
- ce n'est pas le feed officiel OPRA temps réel.

### Usage recommandé

Collecter uniquement pour :

```text
Oracle TOP20
```

à quelques timestamps fixes :

```text
09:31 ET
15:45 ET
15:59 ET
```

et conserver :

```text
underlying
contract
expiration
strike
call_put
latest_trade
latest_quote
greeks
provider_timestamp
received_at
feed = indicative
```

### Limites scientifiques

Ce dataset gratuit ne doit PAS être présenté comme :

```text
OPRA NBBO
```

et ne satisfait pas nécessairement tout le contrat P2 :

```text
open_interest complet
quotes officielles NBBO
historique dense de chaque contrat
trade conditions complètes
```

Le garder comme :

```text
P2_FORWARD_EXPLORATORY
```

### Cboe Delayed Quotes

Cboe permet une consultation gratuite manuelle des chaînes retardées, mais indique explicitement que l'extraction automatisée des quote tables est interdite.

Donc :

```text
DO_NOT_SCRAPE_CBOE_DELAYED_QUOTES
```

---

# 6. P3 — Prémarché / ouverture / événements

## P3.1 — Minute bars

### Source : Business Quant Intraday 1-Minute API

**Statut : gratuit.**

Documentation :

https://businessquant.com/docs/api/quotes-intraday

Supporte plusieurs tickers dans une requête.

### Limite majeure : 0,1 Go / mois sur le plan Free

Ne pas collecter 1-minute pour les ~500 titres toute la journée.

Cela dépasserait probablement rapidement le quota de transfert.

### Stratégie recommandée

Collecter seulement :

```text
Oracle TOP20
```

Fenêtre :

```text
04:00–10:30 ET
```

si le fournisseur retourne bien le prémarché pour les symboles concernés.

Sinon :

```text
09:30–10:30 ET
```

au minimum.

Stocker :

```text
timestamp
ticker
open
high
low
close
volume
received_at
```

### Audit obligatoire

Avant production :

- vérifier si les bars 04:00–09:30 sont réellement présents ;
- vérifier le timezone ;
- comparer 10 symboles contre une seconde source ;
- mesurer le volume mensuel réel.

---

## P3.2 — 8-K / 6-K

### Source : SEC EDGAR

Utiliser le même collecteur SEC que P0.

Formes :

```text
8-K
8-K/A
6-K
```

Conserver :

```text
accession_number
acceptance_datetime
item_codes
full_text
documents
exhibits
99.1
raw payload
received_at
```

Cette partie peut être entièrement construite gratuitement.

---

# 7. P4 — Positionnement lent / macro

## P4.1 — 13F / 13D / 13G

### Source primaire : SEC EDGAR

Collecter :

```text
13F-HR
13F-HR/A
SC 13D
SC 13D/A
SC 13G
SC 13G/A
```

Conserver :

```text
filer_CIK
issuer
CUSIP
report_period
acceptance_datetime
shares
value
put_call
voting_authority
amendment
received_at
```

### Source optionnelle normalisée : Business Quant 13F

Business Quant propose également gratuitement :

https://businessquant.com/docs/api/institutional-ownership

Mais à cause du quota de 30 appels/jour :

- utiliser SEC comme vérité primaire ;
- Business Quant uniquement pour normalisation/validation ponctuelle.

---

## P4.2 — Macro PIT : FRED / ALFRED

### Statut

API gratuite, avec compte et API key.

Documentation :

https://fred.stlouisfed.org/docs/api/fred/

Clé API :

https://fred.stlouisfed.org/docs/api/api_key.html

ALFRED / real-time periods :

https://fred.stlouisfed.org/docs/api/fred/realtime_period.html

### Pourquoi ALFRED est important

FRED montre généralement ce que l'on sait aujourd'hui.

ALFRED permet de demander :

```text
realtime_start
realtime_end
```

et donc de reconstruire ce qui était connu à une date donnée.

### Stocker

```text
series_id
observation_date
value
realtime_start
realtime_end
release_id
received_at
```

### Licence

FRED est gratuit pour usage personnel/non commercial, mais certaines séries proviennent de tiers et peuvent avoir des restrictions spécifiques.

Ne pas redistribuer automatiquement tout FRED dans un produit commercial sans vérifier les droits de chaque série.

---

# 8. Business Quant — budget API quotidien conseillé

Plan Free vérifié au 2026-09-12 :

```text
$0
30 API calls / day
0.1 GB data transfer / month
```

Il faut exploiter les endpoints multi-tickers.

Budget cible :

```text
1 call   universe
1-2      corporate actions
5-10     EOD batches (~500 tickers)
20       analyst EPS snapshots pour Oracle TOP20
------------------------------
27-33 calls
```

Donc avec analyst estimates, il faut optimiser.

Recommandation :

```text
universe              1 fois / semaine plutôt que tous les jours
corporate actions     1-2 / jour
EOD                    batchs multi-ticker
analyst EPS TOP20     20 / jour
```

Objectif :

```text
<= 30 calls/day
```

Ne pas collecter Revenue en plus pour TOP20 sur le Free plan sauf quota restant.

---

# 9. Calendrier de collecte recommandé

Toutes les heures ci-dessous sont en **America/New_York**.

```yaml
sec_edgar:
  polling_interval: 5m
  max_requests_per_second: 8
  raw_append_only: true

nasdaq_symbol_directory:
  schedule:
    - "17:30"
  snapshot_full_files: true

businessquant_corporate_actions:
  schedule:
    - "18:00"
    - "next_day_reconciliation"
  mode: market_wide

businessquant_eod:
  schedule:
    - "18:15"
  universe: all_tracked_equities
  batch_size: 50-100

finra_short_volume:
  schedule:
    - "18:30"
  keep_corrected_versions: true

alpaca_borrow_status:
  schedule:
    - "08:00"
    - "09:25"
    - "15:45"

businessquant_analyst_estimates:
  universe: oracle_top20
  metric: eps
  schedule:
    - "after_oracle_selection"

alpaca_options_indicative:
  universe: oracle_top20
  schedule:
    - "09:31"
    - "15:45"
    - "15:59"

businessquant_intraday:
  universe: oracle_top20
  preferred_window_et: "04:00-10:30"
  fallback_window_et: "09:30-10:30"

fred_alfred:
  schedule:
    - "daily"
  preserve_vintages: true
```

---

# 10. Structure de projet recommandée

```text
forward_pit_collector/
│
├── collectors/
│   ├── sec_edgar/
│   ├── nasdaq_symbol_directory/
│   ├── businessquant/
│   │   ├── universe/
│   │   ├── eod/
│   │   ├── corporate_actions/
│   │   ├── analyst_estimates/
│   │   └── intraday/
│   ├── alpaca/
│   │   ├── corporate_actions/
│   │   ├── borrow_status/
│   │   └── options_indicative/
│   ├── finra/
│   └── fred_alfred/
│
├── raw/
├── normalized/
├── canonical/
├── snapshots/
├── reconciliation/
├── quality/
├── monitoring/
└── schemas/
```

---

# 11. Variables d'environnement

```text
BUSINESSQUANT_API_KEY=
ALPACA_API_KEY=
ALPACA_API_SECRET=
FRED_API_KEY=

SEC_USER_AGENT="Alpha-Trade your-email@example.com"
```

Aucune clé ne doit être committée dans Git.

---

# 12. Contrôles automatiques obligatoires

Pour chaque collecteur :

```text
HTTP status
response latency
record_count
payload_bytes
schema_hash
first_timestamp
last_timestamp
duplicates
null_rate
provider_timestamp
received_at
```

Alarmes :

```text
ZERO_RECORDS_ON_EXPECTED_DAY
SCHEMA_CHANGED
RATE_LIMITED
AUTH_FAILED
DATA_DELAYED
UNIVERSE_DROP_ABNORMAL
PRICE_GAP_ABNORMAL
CORPORATE_ACTION_CONFLICT
```

---

# 13. Tests de cohérence PIT

Pour toute donnée :

1. conserver le payload original ;
2. conserver `received_at` local ;
3. ne jamais backdater une observation avec une valeur apprise plus tard ;
4. conserver les corrections séparément ;
5. distinguer :
   - `economic_at`
   - `published_at`
   - `provider_timestamp`
   - `received_at`
   - `effective_at`
6. ne jamais joindre seulement sur le ticker si un CIK/security_id est disponible.

---

# 14. Données à NE PAS substituer

```text
FINRA short volume
    != borrow fee
    != short interest
    != utilization

Alpaca borrow_status
    != lendable supply
    != shares on loan
    != borrow fee

Business Quant consensus snapshots
    != analyst-level revisions PIT

Alpaca options indicative
    != OPRA NBBO

Nasdaq symbol missing
    != confirmed delisting

current SEC XBRL value
    != historical PIT value
```

---

# 15. Priorité d'implémentation

## Phase 1 — immédiate

```text
1. SEC EDGAR collector
2. Nasdaq Symbol Directory snapshots
3. Business Quant corporate actions
4. Business Quant EOD OHLCV
5. FRED/ALFRED
```

Ces cinq collecteurs apportent la plus grande valeur structurelle pour presque zéro coût.

## Phase 2

```text
6. FINRA daily short-sale files
7. Alpaca borrow_status
8. Business Quant analyst EPS snapshots sur Oracle TOP20
```

## Phase 3

```text
9. Alpaca indicative option snapshots sur Oracle TOP20
10. Business Quant minute bars sur Oracle TOP20
```

## Phase 4 — interfaces seulement

Créer les interfaces mais laisser sans fournisseur :

```text
AuctionImbalanceProvider
SecuritiesLendingProvider
AnalystLevelRevisionProvider
OfficialOptionsNBBOProvider
```

Statut :

```text
PENDING_PAID_OR_BETTER_FREE_SOURCE
```

---

# 16. Sources officielles utilisées pour la vérification

## SEC

- EDGAR APIs  
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces

- Developer Resources / Fair Access  
  https://www.sec.gov/about/developer-resources

## Nasdaq Trader

- Symbol Directory definitions  
  https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs

- Symbol Lookup / licence notice  
  https://www.nasdaqtrader.com/Trader.aspx?id=symbollookup

## Business Quant

- Pricing  
  https://businessquant.com/pricing

- Terms of Use  
  https://businessquant.com/terms-of-use

- API overview  
  https://businessquant.com/docs/api

- Corporate Actions  
  https://businessquant.com/docs/api/corporate-actions

- Universe  
  https://businessquant.com/docs/api/universe

- EOD prices  
  https://businessquant.com/docs/api/quotes

- 1-minute bars  
  https://businessquant.com/docs/api/quotes-intraday

- Analyst Estimates  
  https://businessquant.com/docs/api/estimates

- Institutional Ownership / 13F  
  https://businessquant.com/docs/api/institutional-ownership

## Alpaca

- Market Data pricing / Basic $0  
  https://alpaca.markets/data

- Market Data subscription details  
  https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api

- Corporate Actions  
  https://docs.alpaca.markets/us/reference/corporateactions-1

- Option Chain  
  https://docs.alpaca.markets/us/reference/optionchain

- Borrow status change  
  https://docs.alpaca.markets/us/changelog/2026-06-05-borrow-status-6b96a5a

## FINRA

- Daily Short Sale Volume Files  
  https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files

- Developer API  
  https://developer.finra.org/docs/api-explorer/query_api-equity-reg_sho_daily_short_sale_volume

## FRED / ALFRED

- API  
  https://fred.stlouisfed.org/docs/api/fred/

- API key  
  https://fred.stlouisfed.org/docs/api/api_key.html

- Real-Time Periods / ALFRED  
  https://fred.stlouisfed.org/docs/api/fred/realtime_period.html

- Legal / free API usage  
  https://fred.stlouisfed.org/legal/

## Cboe

- Delayed Quotes / prohibition d'auto-extraction  
  https://www.cboe.com/delayed_quotes/API/quote_table/

---

# 17. Conclusion

Pour construire gratuitement un historique à partir du 2026-09-12, la stack recommandée est :

```text
P0
├── SEC EDGAR
├── Nasdaq Symbol Directory
├── Business Quant Universe
├── Business Quant Corporate Actions
└── Business Quant EOD

P1
├── FINRA Short Volume            [contexte seulement]
├── Alpaca borrow_status          [partiel]
├── Business Quant EPS TOP20      [consensus forward partiel]
├── Auction imbalance             [PENDING]
└── Full securities lending       [PENDING]

P2
└── Alpaca Options Indicative     [exploratoire, pas OPRA NBBO]

P3
├── Business Quant 1m TOP20
└── SEC 8-K / 6-K

P4
├── SEC 13F / 13D / 13G
└── FRED / ALFRED
```

Cette architecture ne remplace pas les historiques institutionnels nécessaires pour re-tester 2016–2025, mais elle permet de commencer immédiatement à accumuler un **dataset prospectif PIT propre**, qui deviendra de plus en plus précieux avec le temps.
