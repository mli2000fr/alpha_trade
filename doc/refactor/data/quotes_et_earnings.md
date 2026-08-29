# Quotes, spreads et calendrier earnings

Retour : [références Data](README.md)

## Quotes Alpaca

`sync_latest_quotes.py` normalise timestamps, bid/ask et tailles. Le spread en bps est calculé autour du mid seulement lorsque bid/ask sont valides. Le module accepte une fenêtre historique, une source de symboles, un point de reprise alphabétique, une limite et une taille de batch.

Pour l'historique, il découpe les requêtes en blocs et recherche une quote proche de la clôture de chaque séance. Les timestamps Alpaca UTC sont convertis en market date par calendrier/fuseau. Les snapshots ne doivent pas être joints seulement sur `MAX(timestamp)` global : la résolution doit être as-of par date.

Sans `from-date/to-date`, le mode latest envoie les symboles par batches ; la taille doit être ≥1. Avec une borne fournie, l’autre est complétée et `from ≤ to` est exigé. Les sources de symboles publiques sont `active-tradable`, `stock-scores`, `stock-scores-history`, `stock-scores-all` et `stock-bars-daily`. `start-symbol` permet une reprise alphabétique.

Une row contient `symbol`, `quote_date`, timestamp, bid/ask, tailles et spread. Le spread est `(ask-bid)/mid × 10 000` seulement si les deux prix sont strictement positifs. Le code ne rejette pas ici explicitement un marché croisé ask<bid : un spread négatif doit être traité comme anomalie par les contrôles aval.

`estimate_sync_latest_quotes_cost()` estime batches/appels/durée. En historique, l’ordre de grandeur est un appel par symbole-séance manquant plus un quick-check. Cette estimation sert d’avertissement opérateur, pas de quota contractuel.

## Biais IEX

Les quotes restent Alpaca/IEX même lorsque les barres viennent d'EODHD. Le module peut comparer spread/close à des données consolidées et produit des compteurs de staleness/biais. Cette mesure est un diagnostic ; elle ne transforme pas une quote IEX en NBBO consolidé.

Le proxy exact compare le mid bid/ask au close `stock_bars_daily` de la même séance. Le summary publie observations, candidats, closes manquants, moyenne absolue, moyenne signée et maximum avec symbole/date. Le statut `unavailable` ne doit pas être converti en biais nul.

## Earnings

`sync_earnings_calendar.py` propose Finnhub ou SEC. Il normalise les rows vers symbole, date et attributs disponibles, puis upsert. Le chemin SEC sélectionne des company facts trimestriels pertinents ; il n'est pas sémantiquement identique à un calendrier d'annonces fourni par Finnhub.

Le bookmark enregistre contexte et progression. À la reprise, fenêtre, provider, source et symboles doivent rester compatibles. `--clear-bookmark-on-success` évite qu'un état achevé soit repris par erreur. Le pacing Finnhub est explicite.

Les défauts sont J−7 à J+30. Provider valide : `finnhub` ou `sec`. Les batches sont validés dans les bornes définies par le module ; chaque batch réussi est upserté et ses symboles ajoutés au bookmark. Les symboles échoués ne sont pas marqués terminés. Si aucun échec ne subsiste, le bookmark est supprimé ; sinon il est conservé avec un summary partiel.

Le chemin SEC sélectionne des faits US-GAAP sur formulaires 10-Q, 10-K, 20-F et 20-F/A. Pour une période fiscale, il privilégie dépôt le plus récent, fin la plus tardive, durée la plus courte puis ordre des tags. `earnings_date` est la date de dépôt, donc PIT-safe pour le réalisé. Les champs « estimate » sont la même période de l’exercice précédent, pas un consensus analyste.

Finnhub fournit un calendrier passé/futur et des estimations selon son endpoint. Les deux providers ne sont donc ni interchangeables ni fusionnables sans colonne de provenance et sémantique.

## Blackout PIT

Le publisher d'univers utilise la date earnings pour bloquer une fenêtre configurée. Pour un backtest strict, il faut aussi connaître quand cette date a été disponible : une annonce corrigée aujourd'hui ne doit pas être injectée rétroactivement sans historique de disponibilité.

## Diagnostic

Quote absente : vérifier compte/feed, séance, mapping et fenêtre. Spread extrême : contrôler bid/ask nuls/croisés et âge. Earnings vides : vérifier provider/key, mapping SEC CIK, plage et bookmark. Dans tous les cas, relancer l'étape amont plutôt que forcer `ignore-quotes` ou désactiver durablement le blackout.

## Tests

Tester timestamps UTC avec fractions longues, changement de date de marché, bid/ask nuls/croisés, plage inversée, batch nul, reprise par symbole, fenêtre historique, proxy sans close, SEC tags multiples, 20-F, contexte bookmark modifié, batch partiellement échoué et suppression du bookmark après succès.
