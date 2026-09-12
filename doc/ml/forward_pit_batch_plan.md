# Plan des batchs Forward PIT — P0 à P4

Ce plan transforme les besoins de données en collectes prospectives. Le RAW reste append-only et conserve l'heure réelle de réception.

## Audit des trois batchs existants

| Batch | Contenu réel | Décision |
|---|---|---|
| earnings_calendar | Finnhub : calendrier J-7/J+30, EPS/revenue estimate et actual, période fiscale | Conserver : calendrier/blackout, pas un historique de révisions |
| analyst_snapshot | Yahoo/yfinance : consensus EPS/revenue, objectifs de cours et recommandations | Conserver : couvre déjà une partie de P1 |
| market_cap_sync | Yahoo et Finnhub : capitalisation et secteur du profil uniquement | Conserver : ne pas recréer un batch capitalisation |

Earnings utilise Finnhub par défaut sur la fenêtre aujourd'hui moins 7 jours à aujourd'hui plus 30 jours. Il écrit `earnings_date`, estimates et actuals EPS/revenue et période fiscale par upsert symbole/date. Il ne conserve ni payload brut, ni observed_at/available_at, ni chaque révision. Le mode SEC alternatif n'est pas utilisé par le launcher ; dans ce mode, les colonnes estimate contiennent les valeurs réelles de la même période de l'année précédente comme baseline YoY, et non un consensus analyste. Il est configuré dimanche, mercredi et vendredi, pas quotidiennement.

Analyst appelle réellement les quatre familles yfinance `earnings_estimate`, `revenue_estimate`, `analyst_price_targets` et `recommendations`. Il est append-only par date et famille et conserve le payload brut, mais ne fournit pas les observations individuelles par broker. Les horizons Yahoo sont relatifs et `fiscal_period_end` reste généralement absent. Le launcher respecte désormais le kill switch `enabled`; la configuration reste explicitement à `true` pour préserver la collecte souhaitée. Les couvertures EPS et REVENUE sont maintenant calculées séparément : une ligne REVENUE seule ne compte plus comme couverture EPS. Un point de planification reste à arbitrer : avec deux passages à 9 h et 23 h, `--resume` et l'unicité journalière font que 23 h ne produit normalement rien après un succès à 9 h. Recommandation : un passage après clôture US.

Market cap passe par le point d'entrée générique `modelFactory.fundamental_features`, mais les adaptateurs réellement appelés ne renvoient que symbol, secteur, capitalisation, source et payload de profil. Ils ne produisent pas les ratios comptables utilisés par le ML. Une ligne est conservée par date de collecte et fournisseur dans stock_fundamentals_daily, puis Yahoo est préféré à Finnhub. Les fondamentaux comptables historiques proviennent de SEC EDGAR dans la configuration actuelle. Le batch tourne lundi et jeudi : suffisant pour un TTL, mais non quotidien. Il ne remplace ni security master, corporate actions, barres ou SEC.

## P0 — Fondation

1. daily_bars_sync : OHLCV brut/ajusté, source et corrections après clôture. Priorité immédiate car les barres locales ne progressent plus. Pour 2 300 titres par lots de 100, Business Quant consommerait environ 23 appels sur 30 par jour.
2. security_master_snapshot : Nasdaq Symbol Directory quotidien et Business Quant Universe hebdomadaire ; ticker, CIK, exchange, type, ETF flag et changements J/J-1. Une disparition n'est jamais automatiquement une radiation.
3. corporate_actions_sync : Business Quant market-wide, Alpaca secondaire ; dividendes, splits, fusions, spin-offs, faillites, radiations et changements de ticker. Conserver les conflits entre sources.
4. sec_edgar_incremental : partir des soumissions nouvelles et télécharger seulement les CIK modifiés. Le RAW commun alimente fondamentaux, 8-K/6-K et 13F/13D/13G ; ne pas télécharger trois fois EDGAR.
5. pit_data_quality_daily : couverture, fraîcheur, trous, doublons, schema hash, timestamps, volume reçu, conflits, prix et chute d'univers ; alertes email/Telegram. Une réponse vide n'est pas un succès.
6. market_cap_sync existant : conserver sans doublon.

## P1 — Direction

1. borrow_status_snapshot : Alpaca assets, idéalement 08:00, 09:25 et 15:45 ET ; symbol, shortable, borrow_status et timestamps. Le schéma doit accepter plusieurs observations/jour. Ce n'est pas borrow fee, utilization ou lendable supply.
2. analyst_snapshot existant : source consensus forward actuelle ; stabiliser l'horaire après clôture et le flag enabled.
3. oracle_consensus_snapshot_businessquant : optionnel après comparaison avec Yahoo ; EPS sur Oracle TOP20 ou EPS+revenue sur TOP15. C'est un consensus forward, pas des révisions individuelles.
4. finra_short_volume_sync : facultatif, fichier consolidé et corrections. Famille déjà NO_GO, seulement variable de contrôle.
5. auction_imbalance_sync : interface/schéma désactivés PENDING_PROVIDER pour paired shares, côté, prix indicatifs et séquences NYSE/Nasdaq.
6. securities_lending_sync : interface/schéma désactivés PENDING_PROVIDER pour fee, utilization, lendable supply, shares on loan et locates.

## P2 — Options
f
1. oracle_options_indicative_snapshot : Alpaca Basic indicative sur Oracle TOP20 et cohortes suivies, à 09:31/15:45/15:59 ET ; contrat, expiration, strike, call/put, quote, trade, tailles, Greeks et timestamps. Marquer indicative, jamais OPRA NBBO. Continuer à suivre le même contrat jusqu'à H3/H5/H10/H20.
2. official_options_nbbo_sync : interface désactivée en attente d'un fournisseur ; prévoir NBBO, trades, OI, volume, IV, Greeks, corrections et ajustements OCC.

## P3 — Entrée et événements

1. oracle_opening_window_sync : pilote minute seulement sur Oracle TOP20/cohortes, 04:00-10:30 ET si le prémarché existe. Cela définit une entrée retardée, différente du next-open.
2. sec_corporate_events_normalize : sans nouveau téléchargement, extraire du RAW EDGAR les 8-K/6-K, item codes, exhibits, texte, montants et amendements.
3. earnings_calendar existant : conserver. Ajouter une table append-only distincte si l'on veut étudier les révisions de calendrier.

## P4 — Positionnement et régime

1. sec_institutional_ownership_normalize : depuis le RAW EDGAR, normaliser 13F-HR/A, 13D/A et 13G/A avec filer, issuer, CUSIP, période, acceptation, shares, value, put/call et amendements.
2. fred_alfred_vintage_sync : séries, dates d'observation, valeur, realtime_start/end, release et received_at. ALFRED évite les révisions futures.
3. Ne pas créer un autre batch news/sentiment générique : famille déjà rejetée.

## Ordre conseillé

daily_bars_sync, security_master_snapshot, corporate_actions_sync, sec_edgar_incremental, pit_data_quality_daily, stabilisation analyst_snapshot, borrow_status_snapshot, FINRA facultatif, décision Business Quant analyst, options indicatives, opening window, normalisations SEC P3/P4, puis FRED/ALFRED.

Auction, lending complet, options officielles et révisions analyst-level restent désactivés jusqu'à découverte d'un fournisseur.
