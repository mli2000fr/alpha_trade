# POC NYSE Auction History — déséquilibres post-auction

## Décision

Le batch de production `auction_imbalance_sync` reste désactivé avec le statut `BLOCKED_NO_FREE_OFFICIAL_FEED`.

- Nasdaq NOII est disponible uniquement par abonnement via Nasdaq TotalView, Nasdaq DataStore ou un distributeur.
- Les flux NYSE Order Imbalances live et les historiques TAQ complets sont commerciaux.
- L'interface graphique NYSE gratuite expose un historique récent après l'enchère, mais ne constitue pas une API publique documentée et ne permet pas une décision live avant le fixing.

Le POC `modelFactory.nyse_auction_history_poc` est séparé du batch. Il ne possède ni section dans `batch.yaml`, ni tâche Windows, ni table, ni migration, ni branchement au serving.

Sources officielles :

- [Nasdaq Opening and Closing Crosses](https://classic.nasdaqtrader.com/Trader.aspx?id=OpenClose)
- [NYSE Auction Data](https://www.nyse.com/nyse-auction-data)
- [NYSE Auction Tool — présentation](https://www.nyse.com/data-insights/nyse-introduces-the-enhanced-nyse-auction-tool-with-opening-imbalance-history)
- [NYSE TAQ Order Imbalances](https://www.nyse.com/market-data/historical/taq-order-imbalances)

## Ce que fournit l'interface NYSE

Le 13 septembre 2026, un smoke sur IBM et la séance du 11 septembre a confirmé une réponse JSON contenant six moyennes par minute, de 09:25 à 09:30 :

- symbole et MIC ;
- date/heure de la minute ;
- quantité appariée moyenne ;
- quantité déséquilibrée moyenne et signée ;
- prix moyen de clearing du carnet ;
- prix de référence ou prix d'enchère exposé par l'interface.

La liste publique contenait alors 2 273 symboles. Cette valeur est informative et peut évoluer.

La route utilisée par le site est non documentée. Son existence technique n'accorde ni garantie de stabilité, ni droit de collecte bulk. Le mode manuel impose donc au maximum 20 symboles et 20 dates. Le mode univers accepte jusqu'à 2 500 symboles, mais une seule séance par exécution, impose au moins une seconde entre les téléchargements et s'arrête dès que le site limite ou refuse les requêtes.

La collecte univers est reprenable avec `--resume-dir` : chaque réponse déjà présente est relue sans requête réseau. Cette reprise ne doit pas servir à contourner une limitation quotidienne ; elle sert à poursuivre lors d'une exécution ultérieure autorisée.

## Contrat temporel

L'interface est mise à jour après l'enchère. Pour chaque observation :

- `observed_at` et `available_at` correspondent à l'heure réelle du téléchargement ;
- `available_before_auction=false` ;
- aucune ligne ne peut simuler une entrée prise avant l'ouverture ou la clôture ;
- l'heure 09:25 portée par la donnée décrit l'état historique de l'enchère, pas l'heure à laquelle α-Trade l'a reçue.

Le POC sert uniquement à estimer la valeur économique potentielle de la famille avant un éventuel achat de données officielles.

## Exécution

Smoke minimal sans interrogation de la base :

`python -m modelFactory.nyse_auction_history_poc --symbols IBM --start-date 2026-09-11 --end-date 2026-09-11 --max-dates 1 --no-evaluate`

POC plafonné par défaut :

`python -m modelFactory.nyse_auction_history_poc`

Clôture au lieu de l'ouverture :

`python -m modelFactory.nyse_auction_history_poc --auction-type closing`


Audit de couverture, sans télécharger les historiques individuels :

`python -m modelFactory.nyse_auction_history_poc --symbol-source universe-file:univers_filtred_tradable.txt --start-date 2026-09-11 --end-date 2026-09-11 --max-dates 1 --eligibility-only --no-evaluate`

Collecte d'une seule séance sur tous les titres NYSE éligibles :

`python -m modelFactory.nyse_auction_history_poc --symbol-source universe-file:univers_filtred_tradable.txt --start-date 2026-09-11 --end-date 2026-09-11 --max-dates 1 --no-evaluate`

Reprise d'une collecte partielle :

`python -m modelFactory.nyse_auction_history_poc --symbol-source universe-file:univers_filtred_tradable.txt --start-date 2026-09-11 --end-date 2026-09-11 --max-dates 1 --no-evaluate --resume-dir artifacts/research/nyse_auction_history_poc/<répertoire-du-run>`

Le rapport expose `completed_pairs`, `resumed_pairs`, `stop_reason`, `errors` et `complete`. Un arrêt `RATE_LIMITED` ou `SOURCE_UNAVAILABLE` est un résultat partiel propre, pas une autorisation de relancer immédiatement en boucle.

## Résultat du test univers du 13 septembre 2026

L'univers contenait 1 798 symboles. L'intersection avec les 2 273 symboles annoncés par l'interface NYSE a produit 1 015 symboles éligibles et 783 exclus. Lors du test d'une séance, le serveur a interrompu la collecte après 51 réponses enregistrées : 29 observations exploitables et 22 réponses vides. Cela invalide l'idée d'une collecte quotidienne complète fiable via cette interface gratuite dans les conditions testées. Pour éviter que les collectes partielles portent toujours sur le début alphabétique, chaque nouvelle séance applique une rotation déterministe de l'ordre ; une reprise conserve l'ordre mis en cache. Le POC permet de conserver et reprendre les réponses partielles, mais `auction_imbalance_sync` reste désactivé.
La sortie est créée dans `artifacts/research/nyse_auction_history_poc/nyse-auction-history-poc-*/` :

- `raw/<type>/<date>/<symbol>.json` : réponse exacte du site ;
- `eligible_symbols.txt` et `excluded_symbols.txt` : intersection auditable avec l'univers NYSE ;
- en cas d'arrêt, les fichiers bruts déjà écrits restent utilisables par `--resume-dir` ;
- `observations.csv` : une ligne agrégée par symbole/date ;
- `report.json` : contrat de source, couverture, erreurs et diagnostics.

## Features diagnostiques

Le résumé calcule notamment :

- dernier déséquilibre signé ;
- accélération entre la première et la dernière minute ;
- persistance du côté final ;
- déséquilibre / quantité appariée ;
- prix de clearing / prix de référence ;
- déséquilibre / ADV20 lorsque les barres locales sont disponibles.

L'évaluation facultative joint les cours locaux et mesure les rendements ouverture → J+1, J+5 et J+20. Elle produit uniquement un IC de rang et un spread autour de la médiane. Ces métriques sont exploratoires : 400 couples symbole/date ne suffisent pas à promouvoir un modèle.

## Critères de poursuite

Le POC peut justifier de reconsidérer un fournisseur payant seulement si :

1. la couverture est suffisante sans sélection a posteriori ;
2. le signe et les ratios restent stables sur plusieurs sous-périodes ;
3. l'effet apparaît d'abord à court terme, où la microstructure d'enchère est économiquement plausible ;
4. H5/H20 apporte ensuite une valeur incrémentale ;
5. une validation OOS distincte confirme le résultat.

Même avec un signal fort, les données Web ne deviennent pas servables. Il faudra un flux officiel reçu avant l'enchère, couvrant les places nécessaires et autorisant l'historisation.

## Distinction avec les données déjà collectées

`oracle_opening_window_sync` mesure ce qui s'est exécuté pendant le prémarché et après l'ouverture. Il ne reconstitue pas les ordres appariés ou non appariés du carnet d'enchère.

Les futures features de clôture basées sur prix, volume et VWAP décriront également le résultat du marché. Elles ne doivent jamais être nommées « auction imbalance ».

