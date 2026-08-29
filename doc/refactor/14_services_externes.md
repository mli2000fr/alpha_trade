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

`RetryPolicy` centralise le nombre de tentatives, le délai initial, le plafond et le jitter. Le délai croît exponentiellement et respecte `Retry-After` lorsqu’il est fourni. Les réponses transitoires et erreurs réseau sont réessayées ; les erreurs client non transitoires ne le sont pas. Cette politique ne rend pas une écriture idempotente : un appel qui crée un ordre doit posséder son propre identifiant d’idempotence avant tout retry.

Le circuit breaker est maintenu par hôte. Il évite de marteler une dépendance déjà en échec et se distingue du circuit breaker portefeuille : le premier protège les appels HTTP, le second protège le capital et les nouvelles entrées. Les logs HTTP expurgent les paramètres sensibles d’URL.

## Fabrique de cache

`service/cache/factory.py` sélectionne Redis lorsque `ALPHA_TRADE_CACHE_URL` commence par `redis://` ou `rediss://` et que le client Redis est disponible. Sinon, il utilise `InMemoryCache`. Le fallback mémoire est local au processus : il n’offre ni partage entre workers, ni persistance après redémarrage.

Chaque cache doit définir une clé comprenant les paramètres qui changent la réponse, un TTL lié à la volatilité de la donnée et une stratégie d’invalidation. Mettre en cache une erreur, une liste vide ou une réponse partielle ne doit être fait que volontairement et avec une durée courte. La provenance du résultat reste conservée hors cache.

## Multi-comptes Alpaca

`accounts.py` charge les entrées `alpaca.accounts`, résout les placeholders d'environnement et valide id, label, mode et préférences long-only. Toute opération de trading doit transporter l'account id ; un défaut implicite ne doit pas permettre de confondre paper et live.

Les variables préfixées sont détectées dynamiquement : `ALPACA_<ID>_API_KEY`, `ALPACA_<ID>_SECRET_KEY`, avec `MODE`, `LABEL` et `LONG_ONLY` optionnels. L’identifiant est normalisé en minuscules. Une paire incomplète est ignorée. Le registre est chargé une fois et offre `reset_for_tests` afin d’isoler les fixtures.

`resolve(None)` retourne le premier compte pour compatibilité historique. Ce comportement n’est pas un choix de compte sûr pour du live : les nouvelles commandes doivent exiger ou journaliser l’identifiant.

## Failover

`broker_failover.py` formalise certains scénarios de panne, mais un changement de broker ou provider ne garantit pas l'équivalence de données. La source, l'ajustement et la qualité doivent rester enregistrés. Pour les ordres, le broker choisi demeure une décision explicite et à haut risque.

Les adaptateurs normalisent les réponses vers les modèles internes. Ils ne doivent pas laisser le métier dépendre d’un nom de champ, d’un fuseau ou d’une pagination propre au provider. Toute conversion précise notamment : symbole, timestamp, timezone, devise, convention de prix, statut de marché et disponibilité effective.

## Contrat d’un adaptateur

Un adaptateur doit :

1. valider credentials et paramètres avant l’appel ;
2. poser des timeouts bornés ;
3. appliquer retry uniquement selon la sémantique de l’opération ;
4. paginer jusqu’au périmètre demandé ou déclarer le résultat partiel ;
5. normaliser types, dates et valeurs manquantes ;
6. exposer source, latence, quota et erreurs ;
7. ne jamais décider silencieusement qu’un fallback est équivalent ;
8. faciliter les tests via injection/mocks plutôt qu’un appel réseau réel.

## Modes de panne

| Panne | Comportement attendu |
|---|---|
| 401/403 | ne pas retry en boucle ; vérifier secret, droits et endpoint |
| 404 | distinguer ressource absente d’un symbole invalide |
| 429 | respecter `Retry-After`, quota et circuit |
| 5xx/timeout | retry borné si opération idempotente |
| réponse vide | enregistrer provider, scope et caractère attendu/inattendu |
| pagination partielle | marquer incomplet ; ne pas publier comme full |
| fallback utilisé | conserver source effective et motif |
| schéma changé | échouer sur validation plutôt que produire des champs faux |

## Ajouter un provider

Créer le client dans `service/<provider>/`, isoler authentification et transport, définir les modèles normalisés, intégrer télémétrie/retry/cache, puis ajouter des tests de pagination, erreurs, timezone et payload incomplet. Ensuite seulement brancher le provider dans le module métier et documenter les différences de couverture et de convention.

## Bonnes pratiques

- timeouts bornés ;
- retries uniquement sur erreurs idempotentes ;
- clés jamais loguées ;
- réponses normalisées avant la couche métier ;
- cache avec TTL et provenance ;
- quota visible ;
- fallback annoncé dans le run summary ;
- données manquantes traitées selon criticité.
