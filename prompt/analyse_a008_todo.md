📊 Analyse : stock_quote_snapshots + A-008
Ce que sert stock_quote_snapshots
La table stock_quote_snapshots est une table de stockage des dernières cotations bid/ask en temps quasi-réel (pré-marché ou EOD). Elle est alimentée par dataIntegrityEngine/sync_latest_quotes.py via Alpaca IEX (endpoint /v2/stocks/quotes/latest). Elle stocke : bid_price, ask_price, bid_size, ask_size, spread_bps, quote_timestamp, quote_date.
Usages dans le code :
Filtre spread_bps du selector (selector/filters.py:260-316) — exclut les titres trop illiquides (spread > seuil). C'est le filtre le plus critique.
Scanner AlphaScanner — fetch_quote_snapshots() → les données sont mergées avant filtrage.
IHM — affichage diagnostics alpha scanner, page _alpha_scanner_diagnostics.py.
Backfill PIT — utilisé pour reconstruire les scores historiques.
A-008 — Quotes IEX biaisées pour le filtre spread_bps
Le problème : Alpaca IEX distribue des quotes NBBO approximatives (pas toujours le vrai National Best Bid/Offer consolidé), spécialement en dehors des heures de marché. Les spreads IEX peuvent sur-estimer le vrai spread de 30–100% pour les mid/small caps (ex. 80bps IEX vs 40bps NBBO réel).
Peut-on utiliser EODHD à la place ?
❌ Non. EODHD est spécialisé en données EOD (End-of-Day) — il ne fournit pas de quotes bid/ask en temps réel. Ses APIs ne proposent ni bid_price ni ask_size.
Solutions viables :
✅ Mitigation déjà en place : max_spread_bps_iex (relâchement conditionnel dans filters.py:287-313). C'est la bonne approche.
✅ Amélioration possible : documenter le biais comme connu + ajouter un flag quote_source dans la table pour traçabilité future.
🔮 Long terme : Finnhub ou Polygon.io pour des quotes NBBO certifiées (hors scope S3).
Conclusion : L'architecture actuelle avec le double seuil max_spread_bps / max_spread_bps_iex est la bonne réponse architecturale à A-008. À documenter.