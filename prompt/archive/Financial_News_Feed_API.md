# Intégrer EODHD Financial News Feed API dans `event_sentiment` et le définir par défaut

## Mission

Implémenter l’ajout de **EODHD Financial News Feed API** comme nouvelle source de news pour le module `event_sentiment`, l’exposer dans l’IHM Pipeline dans **Event Sentiment — source news**, et en faire la **valeur par défaut**.

> Si tu identifies une architecture ou une stratégie d’intégration **plus pertinente** que le plan ci-dessous, tu peux la suivre, à condition de rester compatible avec le projet, de documenter tes choix, de préserver les comportements attendus et de couvrir les tests.

---

## Contexte vérifié dans le code

### Providers news supportés aujourd’hui

#### `event_sentiment/config.py`
- `NewsProvider = Literal["alpaca", "finnhub"]`
- `PROVIDER_REGISTRY` contient seulement :
  - `alpaca -> ("alpaca_news", "alpaca")`
  - `finnhub -> ("finnhub_news", "finnhub")`
- `EventSentimentConfig` a encore les défauts :
  - `source_name = "alpaca_news"`
  - `provider_name = "alpaca"`
  - `news_provider = "alpaca"`

#### `event_sentiment/ingestion.py`
- le dispatch des providers existe déjà via `NEWS_PROVIDERS`
- il contient seulement :
  - `alpaca`
  - `finnhub`
- tout nouveau provider doit exposer le contrat :
  - `iter_news_pages(start_utc, end_utc, symbols=, limit=, page_token=, session=)`
  - et `yield (articles, next_token)`

#### `event_sentiment/cli.py`
- `--news-provider` existe déjà
- `choices=("alpaca", "finnhub")`
- `default="alpaca"`

#### `event_sentiment/importe_news.py`
- `--news-provider` existe déjà
- `choices=("alpaca", "finnhub")`
- `default="alpaca"`

### IHM Pipeline actuelle

#### `ihm/pages/_execution_center/__init__.py`
- le select `Event Sentiment — source news` existe déjà
- options actuelles : `("alpaca", "finnhub")`
- défaut session-state actuel : `alpaca`
- texte d’aide orienté Alpaca par défaut

#### `ihm/services/pipeline_runner.py`
- `DEFAULT_EVENT_SENTIMENT_CONFIG = EventSentimentConfig()`
- `PipelineLaunchOptions.sentiment_news_provider: Literal["alpaca", "finnhub"] = "alpaca"`
- `_extend_event_sentiment_cli_args()` fallback sur `alpaca`
- `_extend_event_sentiment_powershell_args()` fallback sur `alpaca`
- `_build_launch_options()` reconstruit aussi `sentiment_news_provider` avec fallback `alpaca`

### Support EODHD déjà présent dans le projet

#### Auth / config
- `service/eodhd/accounts.py` existe déjà
- le token EODHD est déjà résolu via `config.yaml` / `EODHD_API_TOKEN`
- `conf/var_env.json` contient déjà `EODHD_API_TOKEN`
- `config.yaml` contient déjà un bloc `eodhd:` configuré pour le plan à 19,99$

#### Client EODHD existant
- `service/eodhd/clientEodhd.py` existe déjà
- il couvre actuellement surtout :
  - EOD bars
  - splits
  - dividends
- **aucun client news EODHD n’existe encore** dans le code à ce stade

### Base de données / persistance
Le modèle actuel semble déjà compatible multi-provider sans migration structurelle lourde, tant que l’on garde la même logique :
- `source_name` distinct par provider
- `provider_name` / `ingestion_source` distincts
- `article_id` préfixé par provider
- checkpoints séparés par `source_name`

Constat important sur le schéma actuel :
- `news_raw` **n’a pas** de colonne dédiée `symbols`
- `news_raw` **n’a pas** de colonne dédiée `tags`
- la table stocke déjà `raw_payload JSON`
- le mapping article → symbole est aujourd’hui porté de façon canonique par `news_ticker_map`

Conséquence :
- l’absence de colonne `symbols` dans `news_raw` est **normale dans l’architecture actuelle**
- les symboles provider sont aujourd’hui exploités pour alimenter `news_ticker_map`
- les métadonnées riches provider peuvent déjà survivre dans `raw_payload`, même sans colonne dédiée

Le pipeline downstream (`scoring`, agrégations, signal aggregator) semble majoritairement provider-agnostic une fois `news_raw` et `news_ticker_map` correctement alimentés.

### Données provider à prendre explicitement en compte

Le provider EODHD Financial News Feed peut retourner, pour chaque news, des champs du type :
- `date`
- `title`
- `content`
- `link`
- `symbols`
- `tags`
- `sentiment.{polarity, neg, neu, pos}`

Exemple observé :
- `symbols` sous forme EODHD (`AAPL.US`, `IONQ.US`, etc.)
- `tags` métier / thématiques
- `sentiment` déjà calculé côté provider

Attention : cette structure peut différer sensiblement d’Alpaca / Finnhub. L’intégration ne doit donc pas supposer que l’adaptateur EODHD est un simple copier-coller des deux autres providers.

### Rappel utile sur les providers existants

- **Alpaca** : le payload news expose déjà une liste `symbols`
- **Finnhub** : l’adaptateur existant reconstruit une liste `symbols` à partir de `related`

Donc oui, le concept de `symbols` existe déjà dans l’application, même s’il n’est pas matérialisé par une colonne dédiée dans `news_raw`.

---

## Objectif fonctionnel attendu

À la fin :
- `eodhd` doit être disponible comme source dans `event_sentiment`
- l’IHM Pipeline doit proposer :
  - `eodhd`
  - `alpaca`
  - `finnhub`
- le défaut doit devenir **`eodhd`** pour l’Event Sentiment
- le backend CLI doit être cohérent avec ce défaut, ou au minimum l’IHM doit toujours transmettre explicitement `eodhd`
- la persistance DB doit rester compatible
- les tests doivent être mis à jour / complétés
- la documentation doit être mise à jour en fin d’implémentation

---

## Contraintes importantes

1. **Ne pas casser Alpaca ni Finnhub**
   - les deux providers existants doivent continuer à fonctionner
   - les anciens tests doivent être adaptés proprement, pas contournés

2. **Réutiliser le socle EODHD existant quand c’est pertinent**
   - auth via `service/eodhd/accounts.py`
   - conventions de retry / logs / redaction de secrets si possible

3. **Ne pas inventer le contrat EODHD sans le vérifier**
   - valider la documentation officielle du **Financial News Feed API**
   - confirmer les points suivants avant implémentation finale :
     - endpoint exact
     - paramètres de filtrage (`symbol`, `tickers`, `from`, `to`, `limit`, etc.)
     - format de pagination
     - format des timestamps
     - présence ou non des champs texte (`headline`, `summary`, `content`)
     - présence ou non d’une liste de tickers / symboles
     - format exact des symboles (`AAPL.US` vs `AAPL`)
     - présence et stabilité des `tags`
     - présence, sémantique et échelle du bloc `sentiment`
     - quota / coût d’appel éventuel

4. **Si le contrat EODHD diffère fortement d’Alpaca/Finnhub**, créer un adaptateur propre
   - ne pas polluer `NewsIngestionService` avec trop de logique spécifique
   - préférer une façade alignée sur `iter_news_pages(...)`

5. **Documenter les écarts éventuels**
   - ex. absence de vrai `next_page_token`
   - ex. symboles moins fiables que chez un autre provider
   - ex. champs textuels incomplets

6. **Étudier explicitement s’il faut faire évoluer le schéma**
   - aujourd’hui, `symbols` n’est pas une colonne de `news_raw`
   - aujourd’hui, `tags` n’est pas une colonne de `news_raw`
   - si l’IA juge qu’une colonne dédiée est utile, elle peut proposer / implémenter une migration, mais elle doit justifier ce besoin
   - à défaut, conserver l’information au minimum dans `raw_payload`

7. **Le downstream peut nécessiter des adaptations**
   - si la structure EODHD diffère substantiellement, il faudra peut-être adapter non seulement l’ingestion, mais aussi les traitements aval
   - cela peut concerner la normalisation des news, le mapping article→symbole, le scoring sentiment, les agrégations et les résumés de run
   - l’IA doit auditer ces impacts et adapter le code si nécessaire

---

## Plan d’implémentation recommandé

### 1. Étendre la configuration centrale `event_sentiment`

Modifier `event_sentiment/config.py` pour ajouter `eodhd` comme provider supporté.

À faire :
- étendre `NewsProvider` vers `Literal["alpaca", "finnhub", "eodhd"]`
- ajouter `eodhd` dans `PROVIDER_REGISTRY`, par exemple :
  - `eodhd -> ("eodhd_news", "eodhd")`
- faire évoluer les défauts vers `eodhd` si c’est la stratégie retenue globalement :
  - `source_name = "eodhd_news"`
  - `provider_name = "eodhd"`
  - `news_provider = "eodhd"`

Point de vigilance :
- le changement de défaut peut impacter les endroits qui instancient `EventSentimentConfig()` sans argument
- il faut donc auditer et mettre à jour les tests / assertions qui attendent encore `alpaca`

Fichiers impactés probables :
- `event_sentiment/config.py`
- tests associés, notamment :
  - `tests/test_event_sentiment_news_provider.py`
  - `tests/test_config.py`
  - autres tests qui supposent `alpaca` comme défaut

---

### 2. Créer un adaptateur EODHD News dédié

Créer un nouveau module, idéalement quelque chose comme :
- `service/eodhd/news_client.py`

But : exposer une API compatible avec `event_sentiment.ingestion`, sur le modèle de :
- `service.alpaca.clientNewsAlpaca.iter_news_pages`
- `service.finnhub.news_client.iter_news_pages`

Signature cible recommandée :
- `iter_news_pages(start_utc, end_utc, symbols=None, limit=50, page_token=None, session=None)`

### Exigences de cet adaptateur

- récupérer le token via le registre EODHD existant
- utiliser une `requests.Session` si fournie
- normaliser la réponse EODHD vers des payloads que `_normalize_article()` sait déjà consommer
- retourner des tuples `(articles, next_token)`
- si EODHD n’a pas un vrai `next_page_token`, encapsuler proprement la pagination interne
  - `next_token` peut être un token synthétique sérialisé si besoin
  - sinon renvoyer `None` et documenter le comportement
- convertir les symboles EODHD vers la notation projet quand nécessaire (`AAPL.US` -> `AAPL`), idéalement en réutilisant `service/eodhd/symbols.py`

### Champs à fournir au minimum par article normalisé

L’adaptateur doit produire un payload compatible avec `_normalize_article()` :
- `id`
- `created_at` ou `published_at`
- `headline`
- `summary` si disponible
- `content` / `body` si disponible, sinon `None`
- `source`
- `author` si disponible
- `url`
- `symbols` ou `tickers`

Et il doit aussi étudier / traiter explicitement les champs spécifiques EODHD :
- `date` -> mapping vers `created_at` / `published_at`
- `title` -> mapping vers `headline`
- `link` -> mapping vers `url`
- `symbols` -> normalisation vers les symboles projet
- `tags` -> conservation dans `raw_payload`, ou colonne dédiée si justifiée
- `sentiment` -> étude de coexistence avec FinBERT

### Cas délicats à gérer

- si EODHD ne fournit pas d’identifiant stable :
  - construire un identifiant déterministe à partir de champs stables (`url`, `headline`, `published_at`, symbole interrogé, etc.)
- si EODHD retourne des symboles absents / peu fiables :
  - garantir au minimum que le symbole demandé reste présent quand c’est cohérent
- si la fenêtre temporelle EODHD est plus grossière que la fenêtre UTC demandée :
  - filtrer côté client pour respecter `start_utc` / `end_utc`
- si la pagination est par page / offset et non par token :
  - adapter cela dans l’implémentation sans changer le contrat du pipeline
- si EODHD retourne `symbols` au format provider (`AAPL.US`) :
  - les convertir proprement vers le format projet (`AAPL`) avant insertion dans `news_ticker_map`
- si EODHD retourne `tags` :
  - décider s’ils restent dans `raw_payload` ou s’il faut une colonne / table dédiée
- si EODHD retourne un `sentiment` provider :
  - auditer comment l’utiliser sans casser la vérité métier actuelle basée sur FinBERT

Si EODHD expose un format plus riche ou plus fiable, tu peux améliorer la normalisation tant que tu ne casses pas les contrats existants.

### Décision à prendre sur `symbols` / `tags` dans `news_raw`

L’IA doit **étudier explicitement** si l’on garde le schéma actuel ou si l’on ajoute des colonnes dédiées.

Option A — recommandation conservative par défaut :
- garder `news_raw` inchangé
- conserver `symbols`, `tags`, `sentiment` dans `raw_payload`
- continuer à utiliser `news_ticker_map` comme source canonique du mapping article → symbole

Option B — si besoin métier / analytique justifié :
- ajouter `news_raw.symbols` (idéalement JSON)
- éventuellement ajouter `news_raw.tags` (idéalement JSON)
- mettre à jour le SQL d’initialisation, les migrations, le repository, les tests et la documentation

Le choix doit être argumenté. Ne pas ajouter de colonne juste “par réflexe” si `raw_payload` + `news_ticker_map` couvrent déjà le besoin.

### Décision à prendre sur le `sentiment` provider EODHD

Le provider EODHD semble exposer un bloc `sentiment` déjà calculé. L’IA doit étudier au minimum les stratégies suivantes :

- **Stratégie 1 — audit only**
  - stocker le sentiment provider uniquement dans `raw_payload`
  - conserver FinBERT comme unique source de vérité downstream

- **Stratégie 2 — persistance séparée**
  - stocker les scores provider dans une structure dédiée ou des colonnes dédiées, séparées de `news_sentiment`
  - continuer à calculer FinBERT en parallèle
  - permettre la comparaison provider vs FinBERT

- **Stratégie 3 — hybridation contrôlée**
  - utiliser le sentiment provider comme signal auxiliaire / fallback / audit / contrôle qualité
  - sans mélanger silencieusement les scores provider et FinBERT

Par défaut, sauf justification forte, **ne pas remplacer FinBERT** par le sentiment provider. Toute déviation doit être explicitement documentée, testée et compatible avec les traitements aval.

---

### 3. Brancher EODHD dans `event_sentiment/ingestion.py`

À faire :
- importer l’adaptateur EODHD news
- ajouter `eodhd` dans `NEWS_PROVIDERS`
- conserver le mécanisme `_resolve_iter_news_pages(provider)`
- ne pas casser le fallback / les tests existants

Objectif :
- `NewsIngestionService` doit rester simple
- le provider `eodhd` doit être sélectionné via `config.news_provider`

Important :
- si les champs EODHD ne rentrent pas naturellement dans le contrat actuel, l’IA peut adapter `_normalize_article()` ou les modèles associés
- si cela impacte le scoring, les agrégations ou les features downstream, ces adaptations doivent être faites proprement et documentées

---

### 4. Mettre à jour les CLIs Event Sentiment

#### `event_sentiment/cli.py`
Mettre à jour :
- `choices=("alpaca", "finnhub", "eodhd")`
- `default="eodhd"` si l’on veut que le backend soit aligné avec la nouvelle stratégie par défaut
- help texte à adapter
- vérifier que le `run_summary` reflète bien `news_provider` et `source_name`

#### `event_sentiment/importe_news.py`
Même évolution :
- ajouter `eodhd` dans les choix
- passer le défaut à `eodhd`
- adapter les tests de propagation de provider

But :
- comportement cohérent entre pipeline principal et import brut
- pas de divergence implicite entre IHM et CLI

---

### 5. Mettre à jour l’IHM Pipeline

#### `ihm/pages/_execution_center/__init__.py`
Dans `_render_event_sentiment_block()` :
- ajouter `eodhd` dans les options du select `Event Sentiment — source news`
- mettre `eodhd` par défaut dans le `session_state`
- adapter le help texte :
  - mentionner que `eodhd` est désormais le défaut recommandé
  - préciser que les checkpoints restent séparés par source

#### `ihm/services/pipeline_runner.py`
Mettre à jour :
- `PipelineLaunchOptions.sentiment_news_provider`
  - type `Literal["alpaca", "finnhub", "eodhd"]`
  - défaut = `"eodhd"`
- les fallbacks internes encore codés sur `alpaca`
- la propagation CLI / PowerShell pour `--news-provider`
- `DEFAULT_EVENT_SENTIMENT_CONFIG = EventSentimentConfig()` après changement des défauts

Objectif :
- la page Pipeline doit afficher `eodhd` par défaut
- les commandes générées doivent refléter la sélection
- pas de divergence entre l’état IHM et le backend appelé

---

### 6. Vérifier les impacts secondaires

Auditer aussi les usages indirects du défaut provider :
- `event_sentiment/history_backfill.py`
- autres endroits qui instancient `EventSentimentConfig()` sans argument
- tests E2E / smoke IHM qui attendent encore `alpaca`

Exemples de fichiers à inspecter / adapter :
- `tests/test_event_sentiment_news_provider.py`
- `tests/test_event_sentiment_importe_news.py`
- `tests/test_event_sentiment_run_summaries.py`
- `tests/test_ihm_pipeline_e2e.py`
- `tests/test_event_pipeline_defaults.py`
- `tests/test_event_pipeline_rerun.py`
- `tests/test_event_relevance_backfill.py`
- `tests/test_config.py`

Auditer aussi :
- `event_sentiment/models.py`
- `event_sentiment/scoring.py`
- `event_sentiment/pipeline.py`
- `event_sentiment/aggregation.py`
- `event_sentiment/signal_aggregator.py`

But : s’assurer qu’une structure provider plus riche / différente (notamment `symbols`, `tags`, `sentiment`) n’exige pas d’adaptations en aval.

---

## Stratégie DB recommandée

Sauf besoin justifié, **ne pas introduire de migration DB** juste pour ajouter EODHD.

Convention recommandée :
- Alpaca
  - `source_name = "alpaca_news"`
  - `provider_name = "alpaca"`
  - `article_id = "alpaca:<provider_id>"`
- Finnhub
  - `source_name = "finnhub_news"`
  - `provider_name = "finnhub"`
  - `article_id = "finnhub:<provider_id>"`
- EODHD
  - `source_name = "eodhd_news"`
  - `provider_name = "eodhd"`
  - `article_id = "eodhd:<provider_id>"`

Points de vigilance :
- stabilité de l’identifiant article EODHD
- absence de collision avec les providers existants
- checkpoints bien séparés par `source_name`
- `ingestion_source` cohérent avec `provider_name`
- si des colonnes `symbols` / `tags` sont ajoutées, elles doivent rester cohérentes avec `raw_payload` et `news_ticker_map`
- ne pas confondre sentiment provider EODHD et scoring FinBERT sans séparation explicite

### Politique recommandée pour `symbols`

- le mapping canonique article → symbole doit rester `news_ticker_map`
- si une colonne `news_raw.symbols` est ajoutée, elle doit être considérée comme un cache / audit de la donnée provider, pas comme une source concurrente de vérité
- toute divergence éventuelle entre `news_raw.symbols` et `news_ticker_map` doit être évitée ou au minimum documentée

### Politique recommandée pour `tags`

- à minima, les `tags` EODHD doivent être conservés dans `raw_payload`
- si usage produit / analytique justifié, l’IA peut proposer un stockage structuré supplémentaire
- si ce stockage est ajouté, il faut prévoir tests, migration et documentation

### Politique recommandée pour le `sentiment` provider

- ne pas écraser silencieusement `news_sentiment` qui reflète aujourd’hui le scoring FinBERT
- si le sentiment provider est persisté, le faire dans un espace distinct ou des champs explicitement nommés comme provider-side
- si l’IA choisit une autre stratégie, elle doit la justifier clairement

---

## Tests attendus

### Tests unitaires / d’intégration à ajouter ou adapter

1. **Config provider**
- `EventSentimentConfig.for_provider("eodhd")`
- validation de `source_name == "eodhd_news"`
- validation de `provider_name == "eodhd"`
- validation de la nouvelle valeur par défaut si modifiée

2. **Dispatch ingestion**
- `NewsIngestionService` route correctement vers `eodhd`
- le provider `eodhd` peut être mocké comme `alpaca` / `finnhub`

3. **Adaptateur EODHD news**
- normalisation des payloads
- gestion des timestamps
- fallback d’identifiant stable si nécessaire
- pagination / absence de pagination
- filtrage fenêtre UTC
- conversion `AAPL.US` -> `AAPL` / symboles projet
- traitement de `tags`
- traitement / décision sur le bloc `sentiment`

4. **CLI principal**
- `--news-provider eodhd` est accepté
- le résumé de run expose bien `news_provider = eodhd`

5. **CLI `importe_news.py`**
- `--news-provider eodhd` est accepté
- la config propagée à `NewsIngestionService` est correcte

6. **IHM Pipeline**
- le bloc Event Sentiment renvoie désormais `eodhd` par défaut
- `PipelineLaunchOptions.sentiment_news_provider` vaut `eodhd` par défaut
- la commande générée contient bien `--news-provider eodhd`

7. **Schéma / persistance si évolution retenue**
- si l’IA décide d’ajouter `news_raw.symbols` et/ou `news_raw.tags`, couvrir :
  - SQL d’initialisation
  - migration(s)
  - repository
  - tests
  - documentation

8. **Downstream / scoring**
- si le sentiment provider EODHD est pris en compte au-delà du simple audit, couvrir les tests garantissant qu’on ne casse pas le scoring FinBERT existant
- si aucun changement downstream n’est nécessaire, le démontrer dans l’analyse / tests

9. si la modification des schéma des tables de la base de données est nécessaire, je suis partant et pas besoin réfléchir la rétrocompatibilié des données car je vais tous importer à nouveau (mais n'oubliez pas de mettre à jour les sql ainsi .

### Validation à exécuter

Après implémentation, exécuter au minimum les tests pertinents ciblés, puis élargir si possible.

Exemples de cible minimale :
- `tests/test_event_sentiment_news_provider.py`
- `tests/test_event_sentiment_importe_news.py`
- `tests/test_event_sentiment_run_summaries.py`
- `tests/test_ihm_pipeline_e2e.py`
- tout nouveau test EODHD news ajouté

---

## Critères d’acceptation

Le travail est terminé si :
- `eodhd` apparaît dans la sélection `Event Sentiment — source news`
- `eodhd` est la valeur par défaut côté IHM Pipeline
- le backend `event_sentiment` accepte et exploite `eodhd`
- `event_sentiment/ingestion.py` sait dispatcher vers un adaptateur EODHD
- les providers `alpaca` et `finnhub` restent opérationnels
- les `symbols` EODHD sont correctement normalisés et exploités
- la décision sur `symbols` / `tags` en base est explicitement traitée
- la décision sur le `sentiment` provider EODHD est explicitement traitée
- les impacts downstream sont soit implémentés, soit explicitement écartés après vérification
- les tests pertinents passent
- les logs / run summaries permettent d’identifier clairement le provider utilisé
- la documentation a été mise à jour

---

## Documentation à mettre à jour en fin d’implémentation

**Important : la documentation doit être mise à jour à la fin de l’implémentation.**

Mettre à jour au minimum :
- `doc/event_sentiment.md`
- `README.md`
- `ihm/README.md`

Et si nécessaire :
- toute doc interne liée aux providers ou à l’IHM Pipeline
- exemples de commandes CLI montrant `eodhd`
- prérequis d’environnement (`EODHD_API_TOKEN`)
- description du comportement par défaut

---

## Remarque finale

Le plan ci-dessus est la trajectoire recommandée compte tenu du code observé. Si tu trouves une solution plus robuste, plus simple à maintenir ou mieux alignée avec le contrat réel de **EODHD Financial News Feed API**, tu peux l’adopter. Dans ce cas :
- explique brièvement pourquoi
- conserve une bonne compatibilité avec le projet existant
- mets à jour les tests
- mets à jour la documentation à la fin

