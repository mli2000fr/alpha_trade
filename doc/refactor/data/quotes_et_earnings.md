# Quotes, spreads et calendrier earnings

Retour : [références Data](README.md)

## Quotes Alpaca

`sync_latest_quotes.py` normalise timestamps, bid/ask et tailles. Le spread en bps est calculé autour du mid seulement lorsque bid/ask sont valides. Le module accepte une fenêtre historique, une source de symboles, un point de reprise alphabétique, une limite et une taille de batch.

Pour l'historique, il découpe les requêtes en blocs et recherche une quote proche de la clôture de chaque séance. Les timestamps Alpaca UTC sont convertis en market date par calendrier/fuseau. Les snapshots ne doivent pas être joints seulement sur `MAX(timestamp)` global : la résolution doit être as-of par date.

## Biais IEX

Les quotes restent Alpaca/IEX même lorsque les barres viennent d'EODHD. Le module peut comparer spread/close à des données consolidées et produit des compteurs de staleness/biais. Cette mesure est un diagnostic ; elle ne transforme pas une quote IEX en NBBO consolidé.

## Earnings

`sync_earnings_calendar.py` propose Finnhub ou SEC. Il normalise les rows vers symbole, date et attributs disponibles, puis upsert. Le chemin SEC sélectionne des company facts trimestriels pertinents ; il n'est pas sémantiquement identique à un calendrier d'annonces fourni par Finnhub.

Le bookmark enregistre contexte et progression. À la reprise, fenêtre, provider, source et symboles doivent rester compatibles. `--clear-bookmark-on-success` évite qu'un état achevé soit repris par erreur. Le pacing Finnhub est explicite.

## Blackout PIT

Le publisher d'univers utilise la date earnings pour bloquer une fenêtre configurée. Pour un backtest strict, il faut aussi connaître quand cette date a été disponible : une annonce corrigée aujourd'hui ne doit pas être injectée rétroactivement sans historique de disponibilité.

## Diagnostic

Quote absente : vérifier compte/feed, séance, mapping et fenêtre. Spread extrême : contrôler bid/ask nuls/croisés et âge. Earnings vides : vérifier provider/key, mapping SEC CIK, plage et bookmark. Dans tous les cas, relancer l'étape amont plutôt que forcer `ignore-quotes` ou désactiver durablement le blackout.

