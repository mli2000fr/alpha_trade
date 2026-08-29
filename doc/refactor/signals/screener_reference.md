# Stock Screener — référence

Retour : [vue signaux](../13_screener_selector_sentiment.md)

`stock_screener.py` orchestre le traitement par chunks/processus ; `pipeline.py` contient les calculs purs ; `db_io.py` charge et persiste ; `models.py` définit config, métriques chunk et rapport.

La passe 1 charge une fenêtre récente et évalue tradabilité objective. La passe 2 charge l'historique long seulement pour les candidats nécessaires au range. Les scores incluent liquidité/dollar volume, force relative 6 mois vs SPY et position dans le range historique. Les percentiles sont calculés dans la population du run.

`run_screener_with_report` crée run id, estime les rows, soumet chunks, agrège succès/erreurs, archive le snapshot puis upsert le latest. Les erreurs sont échantillonnées et comptées ; un chunk échoué ne doit pas disparaître du denominator.

Options : chunk size, workers, benchmark, seuil liquidité, RS min, fenêtre/range min, fenêtre première passe, désactivation two-pass et date PIT selon CLI courant. Le snapshot historique est indispensable à la publication d'univers d'une date passée.

Tables : lectures daily/metadata/audits ; écritures `stock_scores` et historique. Une purge de scores manquants ne doit être lancée que sur le scope explicitement prévu.

Diagnostics : candidats zéro (barres/source/seuils), RS aberrante (SPY/date), range faux (split/historique), mémoire élevée (two-pass off/chunk), run incomplet (chunk failures). Le screener produit contexte et admissibilité objective, jamais le côté final.

