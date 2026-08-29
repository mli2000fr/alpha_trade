# Services externes et adaptateurs

Le package `service/` isole les communications externes et les politiques de retry/cache/télémétrie.

## Matrice

| Service | Package | Usages |
|---|---|---|
| Alpaca | `service/alpaca/` | comptes, trading, positions, quotes, statements, news |
| EODHD | `service/eodhd/` | barres, news, corporate actions, fondamentaux, quota |
| Finnhub | `service/finnhub/` | secteurs/fondamentaux, calendrier/news |
| FRED | `service/fred/` | séries macro US |
| Stooq | `service/stooq/` | fallback macro/market |
| Yahoo | `service/yahoo/` | fondamentaux et cross-check |
| SEC EDGAR | `service/sec/` | company facts, XBRL, earnings |
| FMP | `service/fmp/` | provider financier alternatif |
| IBKR | `service/ibkr/` | client/credentials expérimental ou auxiliaire |

## Résilience

`_http_retry.py` applique retries/backoff aux erreurs récupérables. `_telemetry.py` et `prometheus_metrics.py` exposent compteurs et latences. Les caches peuvent être in-memory ou Redis via `service/cache/factory.py`. Les quotas EODHD sont suivis explicitement.

## Multi-comptes Alpaca

`accounts.py` charge les entrées `alpaca.accounts`, résout les placeholders d'environnement et valide id, label, mode et préférences long-only. Toute opération de trading doit transporter l'account id ; un défaut implicite ne doit pas permettre de confondre paper et live.

## Failover

`broker_failover.py` formalise certains scénarios de panne, mais un changement de broker ou provider ne garantit pas l'équivalence de données. La source, l'ajustement et la qualité doivent rester enregistrés. Pour les ordres, le broker choisi demeure une décision explicite et à haut risque.

## Bonnes pratiques

- timeouts bornés ;
- retries uniquement sur erreurs idempotentes ;
- clés jamais loguées ;
- réponses normalisées avant la couche métier ;
- cache avec TTL et provenance ;
- quota visible ;
- fallback annoncé dans le run summary ;
- données manquantes traitées selon criticité.

