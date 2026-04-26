# Audit — `service`

> Périmètre : `service/alpaca/` (`accounts.py`, `clientAlpaca.py`, `clientNewsAlpaca.py`,
> `trading_client.py`) et `service/finnhub/clientFinnhub.py`.
> Sources : `doc/service.md`, `doc/DOC_TECHNIQUE.md` §3-4, code listé.

---

## 1. Résumé exécutif

Le module `service/` est la **couche d'isolation HTTP** vers Alpaca (data, news, trading)
et Finnhub. Il porte le registre multi-comptes (`AccountRegistry`), la gestion des retries,
des timeouts et du throttling.

État global : **le périmètre est petit et bien circonscrit**, ce qui est une force.
Tests `tests/test_clientAlpaca.py`, `test_clientNewsAlpaca.py`, `test_trading_client.py`,
`test_clientFinnhub.py`, `test_alpaca_accounts.py` présents.

Principaux risques :

1. **Aucune notion de "feed"** explicite côté `clientAlpaca.fetch_bars` : le projet utilise
   implicitement IEX (gratuit). Aucune trace dans le code de ce choix, aucun warning quand
   on passe en mode payant. Source de confusion future.
2. **Retries non uniformes** : la doc indique "5 tentatives, backoff `1.0 * 2^attempt`,
   timeout retried". À vérifier que les trois clients Alpaca + Finnhub appliquent la même
   politique.
3. **`AccountRegistry` est un singleton** chargé au premier accès → les tests qui
   modifient l'env doivent appeler explicitement un `reset()` ; risque d'état partagé
   entre tests.
4. **Pas de circuit breaker HTTP** : si Alpaca renvoie des `5xx` sur 30 minutes, chaque
   appel fait toujours 5 retries avec backoff → le pipeline peut bloquer 30+ min sans
   alerter.
5. **Gestion des secrets** : `mask` à 4 chars + `****` à l'affichage est correct, mais
   pas de redaction structurée des logs HTTP en cas de DEBUG (les headers `APCA-API-KEY-ID`
   peuvent fuiter en log debug si on n'y prend pas garde).

Priorités immédiates :
- Documenter explicitement le `feed=iex` dans le code et dans la doc.
- Ajouter un circuit breaker HTTP global par client.
- Standardiser la politique de retry et exposer une métrique.

---

## 2. Constat détaillé

### 2.1 `accounts.py` — `AccountRegistry`

| Item | Détail |
|---|---|
| Constat | Singleton, charge depuis `config.yaml`, fallback env, fallback `default`. Bonne séparation de responsabilité. |
| Risque | Singleton + état mutable partagé → tests non hermétiques. Pas de méthode publique `reset()` documentée. |
| Risque 2 | `mode: paper|live` n'est pas validé strictement (un typo `paaper` passerait). |
| Recommandation | (a) Ajouter `AccountRegistry.reset_for_tests()` ; (b) valider `mode` via Literal/Enum ; (c) ajouter un test qui vérifie qu'un compte avec `mode='live'` mais `api_key` commençant par `PK` (pattern paper Alpaca) déclenche un warning. |

### 2.2 `clientAlpaca.py` — bars / assets

| Item | Détail |
|---|---|
| Constat | `fetch_bars(symbol, timeframe, start_date)` → utilise implicitement le feed IEX. `fetch_alpaca_assets()` → pagination. Retry/backoff sur timeout. |
| Risque critique | **Cohérence des données** : aucune trace explicite que `feed=iex` (vs `sip`) est utilisé. Le jour où un compte payant est ajouté, l'utilisateur ne saura pas s'il faut changer un paramètre quelque part. |
| Risque 2 | `adjustment` n'est pas centralisé : actuellement `dataIntegrityEngine` passe `adjustment="split"`, mais rien dans le client n'impose ou ne loggue ce choix. |
| Risque 3 | Pas de différenciation `429` (rate limit) vs `5xx` (server error) dans les warnings — un opérateur ne voit pas si le compte est throttlé ou si Alpaca est down. |
| Recommandation | (a) Faire de `feed` un paramètre de classe/config explicite (`feed: Literal["iex","sip"] = "iex"`) ; (b) `adjustment` idem, validé contre une liste fermée ; (c) compteur `last_429_count` exposé pour télémétrie ; (d) test qui vérifie que `feed=iex` part bien dans la query string. |

### 2.3 `clientNewsAlpaca.py`

| Item | Détail |
|---|---|
| Constat | Pagination, headers, timeout, rate limit. `iter_news_pages()` itérateur. |
| Risque | Plan free Alpaca News : limite stricte (~200 articles/req). À vérifier que la pagination ne tombe pas dans une boucle infinie en cas de `next_page_token` mal géré. |
| Recommandation | Ajouter une limite de sécurité `max_pages=1000` et logger explicitement quand atteinte. |

### 2.4 `trading_client.py`

| Item | Détail |
|---|---|
| Constat | Couvre `submit_order`, `get_order`, `list_orders`, `cancel_order`, `replace_order`, `get_positions`, `get_account`, `get_clock`. C'est la brique broker. |
| Risque | **Sécurité opérationnelle** : pas de "guard rail" sur `mode='live'`. Un appel `submit_order` en mode live ne déclenche aucune vérification additionnelle. La confirmation `oui` est dans `run_execution.py`, pas dans le client → contournable. |
| Risque 2 | Pas de timeout différencié par opération (un `submit_order` mérite un timeout court ; `list_orders` peut tolérer plus). |
| Risque 3 | Pas de TCA-friendly : `submit_order` ne capture pas `decision_price` (c'est fait au-dessus dans `OrderIntent`). OK mais à documenter. |
| Recommandation | (a) Ajouter un flag `confirm_live: bool = False` requis pour les méthodes destructives en mode live (idempotent, non bloquant pour les usages internes contrôlés) ; (b) timeouts par méthode ; (c) compteur de méthodes `submit_order` dans les logs / metrics. |

### 2.5 `clientFinnhub.py`

| Item | Détail |
|---|---|
| Constat | Profil société, secteur, earnings calendar. `MIN_REQUEST_INTERVAL_SECONDS = 1.1`. Retry/backoff. |
| Risque | Quota free Finnhub = 60 req/min. `1.1 s` d'intervalle théorique = 54 req/min, OK. **Mais** : pas de gestion des `429` après cumul si plusieurs scripts tournent en parallèle (sanitizer + sync_earnings + update_sector). |
| Risque 2 | Pas de cache local des profils société ; chaque `update_sector` re-interroge Finnhub pour les mêmes symboles s'ils ne sont pas filtrés au bon moment. |
| Risque 3 | Token Finnhub accepte deux noms (`FINNHUB_API_KEY` et `CLE_FINNHUB`) → friction maintenance. |
| Recommandation | (a) Singleton de throttling cross-process via `filelock` ou Redis si parallélisme massif ; (b) cache disque TTL 7j pour les profils société ; (c) déprécier `CLE_FINNHUB` avec warning. |

### 2.6 Couplage et politique de retry

| Constat | Documenté : 5 tentatives, backoff exponentiel. À vérifier l'uniformité réelle entre les 4 clients. |
| Recommandation | Extraire un helper commun `service/_http_retry.py` consommé par tous les clients, avec une signature : `retry_request(method, url, retries, backoff_base, retry_on=(429, 500, 502, 503, 504))`. |

---

## 3. Risques prioritaires

### Critique
- Aucune trace explicite du choix `feed=iex` dans le code Alpaca → bombe à retardement
  pour la migration vers un compte payant.

### Élevé
- Pas de circuit breaker HTTP : un Alpaca down peut bloquer le pipeline 30 min.
- Aucun guard rail intra-client sur `mode='live'`.
- Pas de cache profils Finnhub → quota gaspillé.

### Modéré
- `AccountRegistry` singleton sans `reset()` documenté.
- Politique de retry dispersée plutôt que centralisée.
- Headers Alpaca potentiellement loggés en DEBUG.

### Faible
- Double nom env `FINNHUB_API_KEY` / `CLE_FINNHUB`.
- Pagination Alpaca News sans `max_pages` de sécurité.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

C'est ici que se matérialise le choix IEX, mais il est **invisible dans le code**.
Le client `fetch_bars` accepte les paramètres `start`, `end`, `limit`, `adjustment`,
`feed` — mais le projet appelle sans préciser `feed`, donc Alpaca défaut = IEX.

Conséquences pour `service/` :

- aucune télémétrie sur le ratio "bars retournées vs bars attendues" (volume IEX vs
  consolidated → on n'a aucune idée de la couverture réelle) ;
- aucun fallback configuré vers une source alternative (Stooq, Yahoo) si Alpaca est down ;
- aucun warning si on appelle `fetch_bars` sans `feed` explicite alors qu'on a un compte
  potentiellement payant.

### Recommandation implémentation

```python
# service/alpaca/clientAlpaca.py
DEFAULT_FEED = os.getenv("ALPACA_DATA_FEED", "iex")  # iex | sip

def fetch_bars(symbol: str, timeframe: str, start_date: str | None = None,
               end_date: str | None = None, *, feed: str = DEFAULT_FEED,
               adjustment: str = "split") -> list[dict]:
    if feed not in ("iex", "sip", "otc"):
        raise ValueError(f"feed must be in iex|sip|otc, got {feed!r}")
    if adjustment not in ("split", "all", "raw"):
        raise ValueError(f"adjustment must be in split|all|raw, got {adjustment!r}")
    # ... appel HTTP, ajout du paramètre feed=feed dans la query string
```

Cela rend la coupure free / payant **explicite, testable et documentée**.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Le client doit refléter le choix global du projet :

- valider que `adjustment` est dans `("split", "all", "raw")` ;
- log INFO au démarrage du process : `"Alpaca client started with feed=iex, adjustment=split"` ;
- forcer le défaut à `"split"` côté `service/` même si `dataIntegrityEngine` le passe
  déjà — défense en profondeur.

---

## 6. Quick wins

1. **Faire de `feed` un paramètre explicite** avec défaut env-driven `ALPACA_DATA_FEED`.
2. **Faire de `adjustment` un paramètre validé** (Enum/Literal).
3. **Helper unique de retry** dans `service/_http_retry.py`.
4. **Cache TTL 7j** pour les profils Finnhub (fichier disque ou table SQL `finnhub_cache`).
5. **Log INFO de démarrage** des clients (compte, mode, feed, adjustment).
6. **Compteur 429 / 5xx** exposé par client, accessible via méthode `get_telemetry()`.
7. **Déprécier `CLE_FINNHUB`** avec warning.
8. **`max_pages` sécurité** sur la pagination news.

## 7. Recommandations structurelles

1. **Définir un `Protocol BrokerPort`** dans `core/interfaces.py` (déjà mentionné en
   dette technique côté `DOC_TECHNIQUE.md` §9 P2) → permet de tester `execution_engine`
   sans monter Alpaca.
2. **Définir un `Protocol MarketDataPort`** + une seconde implémentation Stooq/Yahoo
   pour le cross-check de volume / OHLC.
3. **Centraliser la télémétrie HTTP** : un `service/_telemetry.py` qui agrège durée /
   compteurs / erreurs par client, exposable côté IHM page Settings.
4. **Circuit breaker HTTP global** par client (`tenacity` ou implémentation maison) :
   après N erreurs consécutives, refus immédiat des appels pendant T minutes avec
   raise explicite (caught par les pipelines).
5. **Vault / secret store** pour les credentials live (DPAPI sur Windows déjà en place
   pour le watcher ; généraliser).

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 5, 8.
- Renforcement guard rails `submit_order` mode live.

### Moyen terme
- Cache Finnhub (quick win 4).
- Helper de retry centralisé + télémétrie.
- Circuit breaker HTTP par client.
- `Protocol BrokerPort` extrait.

### Long terme
- Seconde implémentation `MarketDataPort` (Stooq).
- Vault / secret store pour live.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Bonne couverture par client. **Manque** :
  - test paramétrique `feed=iex` vs `feed=sip` (vérifier la query string).
  - test "Alpaca down 30 min" (mock 503 puis 200) → mesure le temps total.
  - test guard rail mode live (méthode destructive sans `confirm_live=True`).
  - test `AccountRegistry.reset()` cross-tests.

### Monitoring
- Logs OK. **Manque** :
  - télémétrie agrégée (compteur 429, durée moyenne, erreurs).
  - exposition IHM "santé broker" (page Settings).

### Documentation
- `doc/service.md` clair. **Manque** :
  - section "feed IEX vs SIP" et impacts.
  - section "circuit breaker HTTP" quand implémenté.
  - troubleshooting "Alpaca renvoie des 429 en boucle".

