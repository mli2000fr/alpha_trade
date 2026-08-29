# Event Sentiment — référence

Retour : [vue signaux](../13_screener_selector_sentiment.md)

## Chaîne

`ingestion.py`/`importe_news.py` appellent le provider et écrivent `news_raw`. `mapping.py` relie articles/tickers. `relevance.py` filtre/pondère. `scoring.py` exécute FinBERT. `aggregation.py` construit les agrégats. `trading_calendar.py` calcule l'effective trade date. `signal_aggregator.py` fusionne le contexte aval.

`sentiment_pipeline.py` et `event_sentiment_pipeline.py` sont des façades/lanceurs historiques fins vers le pipeline courant. Ils ne constituent pas deux implémentations métier distinctes.

Le pipeline standard puis contextuel est orchestré par `pipeline.py`/`cli.py`. Les checkpoints permettent reprise sans doubler les articles. Une clé provider/article stable est requise. Les fenêtres UTC et dates de marché ne sont pas interchangeables.

Le score modèle est converti depuis probabilités positive/neutral/negative. La relevance ticker évite d'attribuer le sentiment général à chaque symbole mentionné. Les agrégats quotidiens pondèrent selon les règles code et séparent ticker/secteur.

Une news publiée après cutoff est disponible à la séance suivante. Le backfill doit reproduire ce mapping. Les tables finales sont `ticker_daily_sentiment_features` et `sector_daily_sentiment_features`, avec tables raw/map/sentiment/audit/checkpoint en amont.

Le fusionneur utilise les poids quant/sentiment/macro du contrat effectif et neutralise une composante inactive. Il met à jour le contexte, sans devenir ranking souverain.

Défaillances : modèle Transformers absent, provider quota, article sans mapping, score invalide, checkpoint incompatible et historique sparse. Chaque cas doit avoir compteur/fallback documenté.

## Modèle de données

`news_raw` conserve l'article/provider/timestamps/payload. `news_ticker_map` représente la relation article-symbole. Les tables sentiment séparent résultat article et attribution ticker. `macro_event_audit` trace règles macro. Les features daily ticker/secteur sont les sorties consommables.

## Ingestion

Le CLI accepte fenêtres UTC, symboles et options provider/batch. Les checkpoints empêchent de reprendre depuis zéro. La déduplication doit utiliser une identité provider stable ; titre seul est insuffisant.

## Mapping et relevance

Le mapping normalise tickers et exclut faux positifs selon règles. La relevance mesure si l'article concerne réellement le ticker, et peut être backfillée séparément. Un article général peut alimenter macro/secteur sans être idiosyncratique.

## FinBERT

Le scorer charge tokenizer/modèle, prépare les textes et produit probabilités positive/neutral/negative. Le score dérivé et la version du modèle doivent être persistés. Batches limitent mémoire. Une erreur d'un article ne doit pas corrompre tout le checkpoint sans compteur.

## Scoring contextuel

Le passage contextuel utilise le scope tradable ou override. Il combine relevance et contexte selon code. Standard et contextuel ne sont pas deux labels interchangeables ; conserver leur provenance.

## Calendrier

`TradingCalendarAligner` renvoie `TemporalAlignmentResult`. Pendant séance avant cutoff, la news peut être effective le jour même selon règle ; après cutoff/week-end/jour férié, prochaine séance. Tests aux frontières et timezone sont obligatoires.

## Agrégations

Les agrégats groupent effective trade date et ticker/secteur, avec compte, poids et statistiques. Un jour sans news est absence/neutre selon contrat, pas score négatif. Les backfills travaillent par batches de trade dates et scopes.

## Signal aggregator

Il prend quant score, sentiment normalisé et macro sectoriel, applique poids et clip [0,1]. Si signal sentiment inactive, la composante est neutralisée à 0,5. Le verrou par trade date empêche deux agrégations concurrentes.

## Providers et quota

EODHD, Alpaca/Finnhub selon clients disponibles. Retries/backoff et quota sont dans services. Un fallback change couverture ; le summary doit annoncer provider effectif.

## Commandes

```powershell
python -m event_sentiment --help
python -m event_sentiment.history_backfill --help
python -m event_sentiment.relevance_backfill --help
python -m event_sentiment.signal_aggregator
```

## Tests

Dédup, mapping, relevance, modèle mocké, effective date avant/après cutoff, week-end, agrégation vide, checkpoint resume, provider failure, fusion inactive et verrou concurrent.
