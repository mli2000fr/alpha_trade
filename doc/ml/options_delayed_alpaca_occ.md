# Options retardées Alpaca et ajustements OCC

## Décision et périmètre

Deux collectes prospectives sont actives pour la recherche :

1. `options_delayed_bars_sync` conserve les barres historiques retardées d'une surface d'options ATM ;
2. `option_contract_adjustment_sync` conserve les avis publics OCC « Contract Adjustment ».

Elles ne remplacent pas `official_options_nbbo_sync`. Aucun endpoint gratuit validé ne fournit les quotes historiques NBBO complètes. Les barres Alpaca sont donc marquées `feed=historical_default` et `provenance_status=UNVERIFIED_OPRA`. Elles ne doivent servir ni à simuler un prix d'exécution NBBO, ni au serving live sans une validation supplémentaire.

## Flux `options_delayed_bars_sync`

### Univers et calendrier

Le batch parcourt tout `config/univers_batch/univers_filtred_tradable.txt`, sans dépendre du TOP20 d'un Oracle. Il s'exécute après la clôture options, avec un retard minimum de 16 minutes. Deux passages quotidiens permettent de rattraper une exécution manquée ; les contraintes uniques évitent les doublons métier tandis que les payloads RAW et les runs restent historisés.

### Sélection déterministe des contrats

Pour chaque sous-jacent :

1. récupérer un prix de référence IEX ;
2. interroger le catalogue de contrats actifs ;
3. chercher les échéances les plus proches des DTE 5, 10 et 20, dans une tolérance de cinq jours ;
4. retenir un CALL et un PUT dont le strike est le plus proche du spot pour chaque échéance ;
5. télécharger les barres retardées en paquets de 100 contrats.

Cette réduction se fait au niveau des contrats et non des actions. Elle limite le volume tout en conservant une surface symétrique et reproductible. Le prix du sous-jacent, le catalogue, les barres et leur heure d'observation sont conservés comme preuves PIT.

### Données persistées

- `stock_option_contract_versions` : identité du contrat, racine, échéance, strike, type, style, multiplicateur, taille, open interest disponible, close fournisseur et deliverables ;
- `stock_option_bars_delayed` : OHLC, volume, nombre de transactions, VWAP, timeframe, contrat, sous-jacent, `observed_at`, `available_at`, hash du payload et run ;
- `pit_raw_payloads` : réponses brutes reçues ;
- `pit_collection_runs` : résultat opérationnel et couverture.

La table de versions permet de constater prospectivement les modifications d'un contrat. Elle ne reconstruit pas rétroactivement un ajustement inconnu.

### Contrôles

Le batch refuse une exécution avant le délai minimum et échoue si aucun contrat ou aucune barre n'est obtenu. Il publie la couverture des sous-jacents, le nombre de contrats et le statut de provenance. Le seuil `min_underlying_coverage` est actuellement informatif : une couverture faible produit un avertissement parce qu'une partie de l'univers actions ne possède naturellement pas d'options.

## Flux `option_contract_adjustment_sync`

Le RSS officiel OCC fournit le numéro du mémo, sa date de publication, sa catégorie, son résumé et son URL. Le batch conserve chaque version avec `observed_at` et `available_at` dans `option_contract_adjustments`.

Le détail des mémos est actuellement protégé par Cloudflare lors d'un accès automatisé. Par conséquent, `effective_at`, le multiplicateur, le composant cash et le deliverable détaillé ne sont jamais inventés. Ils restent absents jusqu'à ce qu'une source fiable les expose ou qu'une modification soit observée dans `stock_option_contract_versions`.

## POC `options_delayed_trades_sync`

Le POC n'alimente aucune table de production. Il sélectionne, sur AAPL, MSFT, NVDA, TSLA et AMD, un CALL et un PUT ATM proches de DTE 10, puis compare les transactions brutes Alpaca aux barres une minute Alpaca de la même session et du même contrat.

Commande :

`python -m service.forward_pit.options_delayed --trade-poc`

Le rapport est écrit sous `artifacts/research/options_delayed_trade_poc/poc-*/report.json`. Il compare :

- volume brut et volume des barres ;
- nombre de transactions brutes et compteur des barres ;
- VWAP recomposé et VWAP pondéré des barres ;
- part des contrats dont le volume concorde à ±5 %.

Le verdict automatique `GO_RESEARCH_ONLY` exige au moins six contrats comparables, 80 % de concordance des volumes à ±5 %, et une erreur médiane de VWAP au plus égale à 1 %. Même en cas de GO, `serving_allowed=false` reste imposé et la provenance reste `UNVERIFIED_OPRA`. Un résultat `NO_GO_OR_MORE_DATA` interdit la création du batch transactions tant qu'un échantillon prospectif plus large n'a pas confirmé la qualité.


### Résultat du POC du 11 septembre 2026

Le smoke réel a comparé 10 contrats : CALL et PUT ATM sur AAPL, MSFT, NVDA, TSLA et AMD. Pour les 10 contrats, le volume brut, le volume des barres, le nombre de transactions brutes et le compteur des barres concordent exactement. Le ratio médian de volume et de nombre de transactions vaut 1,0 ; l'erreur relative médiane du VWAP vaut environ 2,64 × 10⁻⁹.

Décision : les transactions sont suffisamment cohérentes avec les barres Alpaca pour construire des features de **recherche prospective**. Cette comparaison entre deux endpoints du même fournisseur ne prouve cependant ni l'exhaustivité OPRA, ni la licence, ni l'absence de filtrage amont. Le batch transactions complet n'est donc pas activé automatiquement ; une confirmation multi-jours et sur des contrats moins liquides reste requise avant cette décision. Rapport : `artifacts/research/options_delayed_trade_poc/poc-20260912224359/report.json`.

## Exploitation ML autorisée

Les données peuvent servir à tester des features de recherche telles que momentum de prime, variation de volume CALL/PUT, nombre de transactions, VWAP, asymétrie CALL/PUT et trajectoire intrajournalière. Toute évaluation doit respecter `available_at`, séparer les horizons, conserver un jeu OOS et comparer une baseline sans options.

Sont interdits à ce stade : reconstruction du NBBO, estimation du spread bid-ask, slippage d'options supposé officiel, Greeks ou IV non fournis, open interest imputé et activation live automatique.

## Installation et exécution

Les deux batchs apparaissent dans **Workflow & Orchestration → Batch**. Ils utilisent le launcher générique, les journaux configurés dans `batch.yaml`, et les notifications email/Telegram communes.

Migration : `0079_delayed_options_occ`. SQL manuel : `database/sql/migration_0079_delayed_options_and_occ_adjustments.sql`.

