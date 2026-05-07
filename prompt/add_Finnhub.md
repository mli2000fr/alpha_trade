# Ajouter Finnhub comme source news pour `event_sentiment` — refactor minimal

## Objectif

Implémenter un refactor pour permettre au pipeline `event_sentiment` d'utiliser **Finnhub** comme source de news, tout en **conservant les schémas de tables existants** si possible.

Le résultat attendu est :

- support de **2 providers news** : `alpaca` et `finnhub`
- choix de la source via CLI et via IHM
- **source par défaut dans l'IHM = `finnhub`**
- conservation du pipeline actuel de scoring **FinBERT local**
- **pas de migration DB** si ce n'est pas strictement nécessaire

---

## Contexte vérifié dans le code

### Pipeline sentiment actuel
- `event_sentiment/config.py`
  - `EventSentimentConfig.source_name = "alpaca_news"`
  - `EventSentimentConfig.provider_name = "alpaca"`
- `event_sentiment/ingestion.py`
  - l'ingestion est aujourd'hui **codée en dur sur Alpaca** via :
    - `from service.alpaca.clientNewsAlpaca import iter_news_pages`
- `event_sentiment/pipeline.py`
  - le pipeline garde un modèle :
    - ingestion news
    - scoring **FinBERT local** via `FinBERTSentimentService`
    - persistance dans `news_sentiment`
- `event_sentiment/cli.py`
  - expose aujourd'hui : `--start-utc`, `--end-utc`, `--symbols`, `--finbert-revision`

### IHM pipeline actuelle
- `ihm/pages/_execution_center/__init__.py`
  - `_render_event_sentiment_block()` expose actuellement :
    - `sentiment_start_utc`
    - `sentiment_end_utc`
    - `sentiment_symbols`
- `ihm/services/pipeline_runner.py`
  - `PipelineLaunchOptions` contient déjà :
    - `sentiment_start_utc`
    - `sentiment_end_utc`
    - `sentiment_symbols`
  - `build_pipeline_command(step_key="sentiment_pipeline", ...)` lance :
    - `python -u -m event_sentiment`

### Compatibilité DB vérifiée
Les tables actuelles sont déjà **compatibles avec plusieurs providers** sans migration, tant qu'on conserve le même modèle de données :

- `database/sql/news/news_raw.sql`
  - `article_id VARCHAR(128)`
  - `ingestion_source VARCHAR(50)`
  - `UNIQUE KEY uk_news_raw_source_hash (ingestion_source, dedupe_hash)`
- `database/sql/news/news_ingestion_checkpoint.sql`
  - clé primaire `(source_name, symbol)`

Donc on peut normalement garder les schémas existants en changeant seulement :
- `source_name` (ex: `alpaca_news`, `finnhub_news`)
- `provider_name` / `ingestion_source` (ex: `alpaca`, `finnhub`)
- le préfixe de `article_id` (ex: `alpaca:<id>`, `finnhub:<id>`)

---

## Ce qu'il faut implémenter

### 1. Introduire une notion de provider news dans `event_sentiment`

Objectif : enlever le couplage direct à Alpaca dans `event_sentiment/ingestion.py`.

À faire :
- introduire un type/provider explicite, par exemple :
  - `news_provider: Literal["alpaca", "finnhub"] = "finnhub"`
- faire dériver automatiquement :
  - `source_name`
  - `provider_name`
- ou, si plus simple et plus robuste, garder `source_name`/`provider_name` explicites mais validés à partir de `news_provider`

Exigences :
- **ne pas casser** le comportement existant Alpaca
- `finnhub` doit devenir l'option par défaut côté IHM
- conserver une API config claire et testable

---

### 2. Ajouter un adaptateur Finnhub pour les news

Créer un client ou helper dédié, par exemple :
- `service/finnhub/news_client.py`
- ou enrichir `service/finnhub/clientFinnhub.py`

Le but est d'offrir à `event_sentiment/ingestion.py` un contrat proche de l'existant Alpaca, idéalement une fonction du style :

- `iter_news_pages(start_utc, end_utc, symbols=None, limit=50, page_token=None, session=None)`

Même si Finnhub n'a pas exactement la même pagination, fournir un **adaptateur** qui renvoie :
- `articles: list[dict[str, Any]]`
- `next_token: str | None`

Si Finnhub n'a pas de vrai `next_page_token`, utiliser :
- `next_token = None`
- et documenter la différence

Exigences de normalisation minimales côté payload article :
- identifiant article
- timestamp de publication
- `headline`
- `summary` si dispo
- `content` si dispo, sinon `None`
- `source`
- `url`
- `symbols` / `tickers`

Important :
- rester cohérent avec `_normalize_article()` dans `event_sentiment/ingestion.py`
- ne pas modifier le modèle `NormalizedNewsArticle` sauf nécessité forte

#### Addendum métier — limite actuelle article → symbole

Le pipeline actuel est **centré sur l'article pour le scoring**, mais **centré sur le provider pour l'attribution des tickers**.

Concrètement :
- `FinBERTSentimentService` calcule **1 score de sentiment par article**
- le lien entre un article et un ou plusieurs symboles vient du provider news (`payload["symbols"]` / `payload["tickers"]`)
- ce score article est ensuite propagé aux symboles associés via `news_ticker_map`

Conséquence métier à expliciter dans le refactor :
- si le provider tagge incorrectement un article avec un symbole non pertinent, ce symbole héritera quand même du sentiment de l'article
- ce comportement existe déjà avec Alpaca et resterait le même avec Finnhub dans un refactor minimal
- le refactor Finnhub demandé **ne doit pas prétendre résoudre** la désambiguïsation sémantique article → entreprise ; il conserve le modèle actuel

En d'autres termes, le pipeline cible reste :

- `article -> 1 score FinBERT`
- `provider -> liste des symboles concernés`
- `article score -> propagation aux symboles fournis par le provider`

#### Garde-fous recommandés dans le refactor minimal

Sans casser l'architecture actuelle, prévoir au moins un garde-fou optionnel côté ingestion / mapping ticker.

Ajouter si possible une option de configuration du style :

- `provider_ticker_relevance_mode = "provider_default" | "strict"`

Comportement recommandé :

- `provider_default` : comportement actuel, on accepte tous les tickers fournis par le provider
- `strict` : on applique un filtrage conservateur avant insertion dans `news_ticker_map`

En complément, prévoir si possible un filtre simple du type :

- ignorer les articles avec trop de tickers
- ou ne conserver que le ticker principal si le provider fournit une notion de `primary ticker`

Exemples de garde-fous acceptables dans ce refactor minimal :

- ignorer un article si `len(symbols)` dépasse un seuil configurable
- limiter aux `N` premiers tickers
- conserver uniquement le premier ticker provider en mode `strict`
- journaliser combien d'articles ont été filtrés par cette logique

---

### 3. Refactor minimal de `NewsIngestionService`

Aujourd'hui `event_sentiment/ingestion.py` importe directement Alpaca.

Refactor attendu :
- sélectionner dynamiquement le provider à partir de la config
- appeler l'adaptateur correspondant (`alpaca` ou `finnhub`)
- conserver la logique existante pour :
  - checkpoints
  - déduplication
  - `news_raw`
  - `news_ticker_map`
  - alignement calendrier
  - mapping secteur

Objectif important :
- **ne pas toucher au downstream** (`pipeline.py`, `scoring.py`, agrégations) sauf si nécessaire pour propager le choix de source

---

### 4. Étendre le CLI `event_sentiment`

Dans `event_sentiment/cli.py`, ajouter une option explicite, par exemple :

- `--news-provider alpaca|finnhub`

Contraintes :
- défaut backend raisonnable : à décider
- si vous voulez aligner le backend avec l'IHM, mettre le défaut CLI sur `finnhub`
- sinon garder le défaut CLI historique mais **l'IHM enverra explicitement `--news-provider finnhub`**

Le plus important :
- le comportement doit être déterministe
- les logs / run summary doivent permettre de voir quelle source a été utilisée

Ajouter dans le run summary si pertinent :
- `news_provider`
- `source_name`

---

### 5. Ajouter l'option dans l'IHM pipeline

Modifier le bloc Event Sentiment dans :
- `ihm/pages/_execution_center/__init__.py`

Dans `_render_event_sentiment_block()` :
- ajouter un sélecteur IHM :
  - label recommandé : `Event Sentiment — source news`
  - options : `finnhub`, `alpaca`
  - **valeur par défaut = `finnhub`**
- persister la valeur dans `st.session_state`, par exemple :
  - `pipeline_sentiment_news_provider`

Ensuite propager cette valeur dans :
- `PipelineLaunchOptions` dans `ihm/services/pipeline_runner.py`
  - nouveau champ : `sentiment_news_provider: Literal["finnhub", "alpaca"] = "finnhub"`
- construction de `PipelineLaunchOptions(...)`
- `build_pipeline_command(step_key="sentiment_pipeline", ...)`
  - ajouter `--news-provider <value>`

Objectif UX :
- on doit pouvoir **switcher facilement** entre Alpaca et Finnhub depuis l'IHM
- le preview de commande doit refléter la source choisie

---

### 6. Garder les schémas de tables existants

Objectif prioritaire : **pas de migration** si possible.

Le refactor doit réutiliser tel quel :
- `news_raw`
- `news_ticker_map`
- `news_sentiment`
- `macro_event_audit`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`
- `news_ingestion_checkpoint`

Convention recommandée :
- Alpaca
  - `source_name = "alpaca_news"`
  - `provider_name = "alpaca"`
  - `article_id = "alpaca:<provider_article_id>"`
- Finnhub
  - `source_name = "finnhub_news"`
  - `provider_name = "finnhub"`
  - `article_id = "finnhub:<provider_article_id>"`

Point de vigilance :
- vérifier que l'identifiant Finnhub est suffisamment stable ; sinon construire un identifiant déterministe à partir d'un hash de champs stables (`headline`, `url`, `published_at`, source)
- ne pas casser l'unicité `(ingestion_source, dedupe_hash)`
- les checkpoints doivent rester **séparés par source** via `source_name`

---

## Ce qu'il ne faut PAS faire

- ne pas remplacer `FinBERTSentimentService` par le sentiment Finnhub
- ne pas refondre les tables ni l'agrégation aval
- ne pas faire un gros redesign si un petit seam provider suffit
- ne pas casser les imports ou tests existants Alpaca

---

## Si vous voulez améliorer ça plus tard

Vous pouvez ajouter un filtre de pertinence sans casser toute l'architecture.

### Niveau 1 — simple

Avant de mapper un article à un ticker :

- vérifier que le ticker demandé est bien dans `payload["symbols"]`
- et éventuellement limiter au primary ticker si le provider l'indique

### Niveau 2 — heuristique utile

Ajouter un score de pertinence par symbole :

- présence du nom société dans `headline`
- présence du ticker dans le texte
- nombre de tickers taggés
- bonus si le symbole est le premier ticker
- malus si l'article mentionne beaucoup de sociétés

### Niveau 3 — plus avancé

Faire :

- `article + symbol -> score de pertinence`
- voire `article + symbol -> sentiment spécifique`

Ces pistes sont **hors périmètre du refactor minimal** demandé ici, mais doivent être documentées comme évolutions futures possibles si la qualité du mapping provider → ticker devient un point bloquant.

---

## Plan d'implémentation recommandé

1. Ajouter le champ `news_provider` dans `EventSentimentConfig`
2. Créer un adaptateur provider dans `event_sentiment/ingestion.py`
3. Ajouter un client Finnhub news minimal
4. Étendre `event_sentiment/cli.py` avec `--news-provider`
5. Étendre `PipelineLaunchOptions`
6. Ajouter le widget IHM dans `_render_event_sentiment_block()`
7. Propager dans `build_pipeline_command()`
8. Ajouter/adapter les tests
9. Vérifier que `python -m event_sentiment --news-provider finnhub` fonctionne
10. Vérifier que la commande générée dans l'IHM contient bien le provider choisi

---

## Fichiers probablement à modifier

### Backend sentiment
- `event_sentiment/config.py`
- `event_sentiment/ingestion.py`
- `event_sentiment/cli.py`
- éventuellement `event_sentiment/pipeline.py`

### Services provider
- `service/finnhub/clientFinnhub.py` ou nouveau fichier dédié
- éventuellement petit adaptateur provider commun si utile

### IHM
- `ihm/services/pipeline_runner.py`
- `ihm/pages/_execution_center/__init__.py`
- éventuellement `ihm/pages/pipeline.py` si affichage complémentaire souhaité

### Tests
- tests unitaires / IHM existants à adapter
- ajouter des tests ciblés pour Finnhub provider

---

## Critères d'acceptation

### Fonctionnel
- `event_sentiment` supporte `alpaca` et `finnhub`
- l'IHM expose un choix `source news`
- la valeur par défaut dans l'IHM est `finnhub`
- la commande générée passe bien `--news-provider`
- le pipeline continue de scorer avec **FinBERT local**
- les tables existantes sont réutilisées **sans migration**

### Compatibilité
- un lancement Alpaca continue de fonctionner
- les checkpoints Alpaca et Finnhub sont séparés
- les articles Finnhub et Alpaca peuvent coexister dans `news_raw`
- `signal_aggregator` continue de fonctionner sans changement de schéma

### Qualité
- code typé, simple, localisé
- pas de duplication inutile
- tests ajoutés ou adaptés

---

## Vérifications / tests à exécuter

Après implémentation, exécuter au minimum :

```powershell
python -m pytest tests -k "event_sentiment or ihm_pipeline"
python -m event_sentiment --help
python -m event_sentiment --news-provider finnhub --symbols AAPL --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-03T00:00:00Z
python -m event_sentiment --news-provider alpaca --symbols AAPL --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-03T00:00:00Z
```

Vérifier aussi dans l'IHM :
- le widget `source news` apparaît
- la valeur par défaut est `finnhub`
- le preview de commande change quand on bascule la source

---

## Résultat attendu du refactor

Une intégration **sobre** et **réversible** :
- même modèle de tables
- même pipeline aval
- un provider news sélectionnable
- un défaut IHM sur Finnhub
- une bascule facile entre Finnhub et Alpaca

Si un choix de conception est ambigu, privilégier :
- le moins de changements possible
- la compatibilité rétro
- la lisibilité du seam provider

