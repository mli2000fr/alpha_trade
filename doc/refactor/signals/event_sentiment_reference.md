# Event Sentiment — référence

Retour : [vue signaux](../13_screener_selector_sentiment.md)

## Chaîne

`ingestion.py`/`importe_news.py` appellent le provider et écrivent `news_raw`. `mapping.py` relie articles/tickers. `relevance.py` filtre/pondère. `scoring.py` exécute FinBERT. `aggregation.py` construit les agrégats. `trading_calendar.py` calcule l'effective trade date. `signal_aggregator.py` fusionne le contexte aval.

Le pipeline standard puis contextuel est orchestré par `pipeline.py`/`cli.py`. Les checkpoints permettent reprise sans doubler les articles. Une clé provider/article stable est requise. Les fenêtres UTC et dates de marché ne sont pas interchangeables.

Le score modèle est converti depuis probabilités positive/neutral/negative. La relevance ticker évite d'attribuer le sentiment général à chaque symbole mentionné. Les agrégats quotidiens pondèrent selon les règles code et séparent ticker/secteur.

Une news publiée après cutoff est disponible à la séance suivante. Le backfill doit reproduire ce mapping. Les tables finales sont `ticker_daily_sentiment_features` et `sector_daily_sentiment_features`, avec tables raw/map/sentiment/audit/checkpoint en amont.

Le fusionneur utilise les poids quant/sentiment/macro du contrat effectif et neutralise une composante inactive. Il met à jour le contexte, sans devenir ranking souverain.

Défaillances : modèle Transformers absent, provider quota, article sans mapping, score invalide, checkpoint incompatible et historique sparse. Chaque cas doit avoir compteur/fallback documenté.

