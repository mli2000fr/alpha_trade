# Pipeline sentiment — notes de synthèse

## Objectif

Cette note résume les explications utiles sur le pipeline sentiment du projet, en particulier :

- la différence entre le wrapper PowerShell `scripts/windows/import_news_and_score_pending.ps1`,
- la commande principale `python -m event_sentiment`,
- la commande de maintenance `python -m event_sentiment.relevance_backfill`,
- le rôle de `history_backfill`, `relevance_backfill` et `relevance_score`.

---

## 1. Les trois niveaux de commande

### A. Wrapper PowerShell `import_news_and_score_pending.ps1`

Commande typique :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\projets\scripts\windows\import_news_and_score_pending.ps1 ...
```

Ce script est un **orchestrateur**. Selon les options, il peut enchaîner plusieurs étapes :

1. import brut des news (`importe_news.py`) ;
2. scoring des articles pending via `python -m event_sentiment` ;
3. reconstruction historique des features via `python -m event_sentiment.history_backfill` ;
4. recalcul de la pertinence historique via `python -m event_sentiment.relevance_backfill`.

Avec `-SkipImport`, il **saute seulement l'import brut**, mais il peut encore faire les trois étapes suivantes.

### B. Pipeline principal `python -m event_sentiment`

Commande typique :

```powershell
python -u -m event_sentiment --news-provider eodhd --enable-contextual-scoring ...
```

Cette commande exécute le **pipeline métier principal** :

1. ingestion news (sauf si `--skip-ingestion`) ;
2. remplissage de `news_raw` ;
3. remplissage de `news_ticker_map` ;
4. scoring FinBERT standard dans `news_sentiment` ;
5. scoring contextualisé dans `news_ticker_sentiment` si activé ;
6. reconstruction des features journalières :
   - `ticker_daily_sentiment_features`
   - `sector_daily_sentiment_features`

Elle **ne lance pas** `history_backfill` ni `relevance_backfill` en tant que commandes séparées.

### C. Maintenance dédiée `python -m event_sentiment.relevance_backfill`

Commande typique :

```powershell
python -u -m event_sentiment.relevance_backfill --batch-size 5000 --rescore-all --rescore-contextual ...
```

Cette commande sert à **rejouer l'historique de pertinence article → symbole** et, si demandé, à compléter le contextual sur l'historique.

Elle agit surtout sur :

- `news_ticker_map` (mise à jour de `relevance_score` et `relevance_components`) ;
- `news_ticker_sentiment` si `--rescore-contextual` est activé.

Elle **n'ingère pas** de nouvelles news et ne remplace pas un run principal complet.

---

## 2. Différences pratiques entre les commandes

### Wrapper PowerShell vs `python -m event_sentiment.relevance_backfill`

Le wrapper PowerShell est **plus large** :

- il peut scorer le backlog pending ;
- il peut lancer `history_backfill` ;
- il termine par `relevance_backfill`.

`python -m event_sentiment.relevance_backfill` ne fait que la partie **relevance / contextual historique**.

### Wrapper PowerShell vs `python -m event_sentiment`

`python -m event_sentiment` est **plus proche** du cœur fonctionnel :

- ingestion,
- scoring standard,
- scoring contextual,
- features journalières.

Mais il ne fait pas automatiquement :

- la boucle PowerShell “jusqu'à `pending=0`”,
- `history_backfill`,
- `relevance_backfill`.

### `python -m event_sentiment` vs `python -m event_sentiment.relevance_backfill`

- `python -m event_sentiment` = pipeline complet de production / backfill opérationnel.
- `python -m event_sentiment.relevance_backfill` = outil ciblé de maintenance historique sur la pertinence et le contextual.

---

## 3. À quoi sert `history_backfill` ?

Le module `event_sentiment.history_backfill` sert à **reconstruire l'historique des features journalières sentiment** à partir des données déjà scorées.

Concrètement, il :

1. liste les `trade_date` déjà scorées dans `news_raw` + `news_sentiment` ;
2. charge les données d'entrée via `load_feature_frames(...)` ;
3. recalcule les agrégats par ticker et par secteur ;
4. réécrit :
   - `ticker_daily_sentiment_features`
   - `sector_daily_sentiment_features`

### Quand l'utiliser ?

On l'utilise quand :

- on a déjà les articles et les scores en base ;
- on veut **rematérialiser proprement les tables de features** sur une fenêtre historique ;
- on a changé la logique d'agrégation ou enrichi les données en amont ;
- on a rempli `news_ticker_sentiment` après coup et on veut refléter ce nouveau signal dans les features.

### Ce qu'il ne fait pas

`history_backfill` :

- n'importe pas de news ;
- ne recalcule pas `relevance_score` ;
- ne score pas `news_sentiment` article par article.

Son rôle est : **reconstruire les agrégats downstream**.

---

## 4. À quoi sert `relevance_backfill` ?

Le module `event_sentiment.relevance_backfill` sert à **rejouer historiquement la pertinence article → symbole** sur les lignes déjà présentes dans `news_ticker_map`.

Concrètement, il :

1. relit les couples `(article_id, symbol)` dans `news_ticker_map` ;
2. joint `news_raw` pour récupérer `headline`, `summary`, `content` ;
3. joint `stock_metadata` pour récupérer `company_name` ;
4. recalcule `relevance_score` et `relevance_components` ;
5. met à jour `news_ticker_map`.

Si `--rescore-contextual` est activé, il peut ensuite :

6. charger les paires encore absentes de `news_ticker_sentiment` ;
7. lancer FinBERT contextualisé ;
8. écrire dans `news_ticker_sentiment`.

### Quand l'utiliser ?

On l'utilise quand :

- on a introduit ou fait évoluer l'heuristique de pertinence ;
- on veut recalculer l'historique de `relevance_score` ;
- on veut nettoyer le bruit article → ticker hérité d'anciens runs ;
- on veut compléter `news_ticker_sentiment` sur un historique déjà importé.

### Ce qu'il ne fait pas

`relevance_backfill` :

- n'importe pas de nouvelles news ;
- ne remplace pas un run complet `python -m event_sentiment` ;
- ne reconstruit pas à lui seul toutes les features historiques avales.

Après un `relevance_backfill` important, il est souvent pertinent de relancer `history_backfill` pour refléter les changements dans les features journalières.

---

## 5. À quoi sert `relevance_score` ?

`relevance_score` est un **score de pertinence article → symbole**, borné entre `0` et `1`.

Il répond à la question :

> “Cet article parle-t-il vraiment de ce symbole, ou bien le provider l'a-t-il juste taggé parmi d'autres ?”

### Où il est stocké ?

Dans :

- `news_ticker_map.relevance_score`
- `news_ticker_map.relevance_components`

### Comment il est calculé ?

Il est calculé par `event_sentiment.relevance.score_article_symbol(...)` à partir d'une heuristique simple et déterministe :

- nom de société trouvé dans le headline ;
- nom trouvé dans le résumé ;
- ticker présent dans le texte ;
- bonus si le ticker est primary ;
- pénalité si l'article tagge beaucoup de tickers.

### À quoi il sert métier ?

Il sert à **réduire le bruit** dans le mapping article → ticker.

Sans lui, un article multi-tickers peut propager le même sentiment vers beaucoup de symboles peu concernés.

Avec lui, on peut :

- **filtrer** les paires faibles (`min_relevance_score`) ;
- **pondérer** les agrégats ticker downstream.

Dans `build_ticker_daily_features(...)`, `relevance_score` sert de **poids** sur les moyennes de sentiment :

- sentiment net,
- positif,
- négatif,
- neutre,
- confiance.

Si `relevance_score` est absent, le code retombe sur `1.0` pour conserver la rétrocompatibilité.

### Interprétation simple

- `1.0` ≈ article très pertinent pour ce symbole ;
- `0.3` ≈ article mentionnant peut-être le symbole mais faiblement ;
- proche de `0.05` = pertinence minimale conservée par l'heuristique.

---

## 6. Résumé métier ultra-court

### `history_backfill`
Reconstruit les **features historiques journalières** (`ticker_daily_sentiment_features`, `sector_daily_sentiment_features`) à partir des données déjà scorées.

### `relevance_backfill`
Recalcule historiquement la **pertinence article → symbole** dans `news_ticker_map` et peut compléter `news_ticker_sentiment` si le contextual est activé.

### `relevance_score`
Score `[0,1]` qui mesure **à quel point un article concerne réellement un symbole** ; il sert ensuite à **filtrer** et **pondérer** le sentiment downstream.

---

## 7. Ordre pratique recommandé

### Nouveau bouton IHM 7.bis — scoring sentiment seul

Dans le bloc `7.bis Import des news brutes` de l'IHM, un bouton dédié permet désormais de lancer **uniquement le scoring sentiment** sur :

- la `Date de début` et la `Date de fin` choisies dans le panneau 7.bis ;
- l'`Univers de symboles pour l'import` choisi dans ce même panneau ;
- le `Event Sentiment — mode de scoring` choisi dans le bloc de paramétrage principal.

Ce bouton lance un `python -m event_sentiment --skip-ingestion ...` :

- sans réimporter de news ;
- avec le `ScoringMode` courant (`Standard only`, `Contextual only`, `Standard + contextual`) ;
- en réutilisant le scope 7.bis pour les symboles.

Cas d'usage typique :

- les news sont déjà présentes dans `news_raw` ;
- on veut seulement rejouer le scoring standard et/ou contextual sur un périmètre borné ;
- sans lancer le wrapper auto complet ni un `relevance_backfill`.

### Nouvelle case IHM 7.bis — réutiliser `news_ingestion_checkpoint`

Le bloc `7.bis Import des news brutes` expose aussi une case à cocher pour les boutons qui **contiennent réellement une étape d'import** :

- `Importer les news sur la période`
- `Import + score + history_backfill + relevance_backfill auto`

Quand cette case est cochée :

- l'import news ne repart plus systématiquement de la `Date de début` pour chaque symbole ;
- il réutilise `news_ingestion_checkpoint` pour reprendre au plus près du watermark connu ;
- si un symbole est déjà à jour par rapport à la `Date de fin` sélectionnée, ce symbole est sauté ;
- un overlap de checkpoint est conservé pour éviter de rater les dernières news autour de la frontière.

Objectif : éviter un refetch complet inutile quand la période ciblée est déjà presque entièrement couverte.

### Cas 1 — enrichir un historique déjà importé

1. `python -m event_sentiment.relevance_backfill ... --rescore-contextual`
2. `python -m event_sentiment.history_backfill ...`
3. éventuellement `python -m event_sentiment.signal_aggregator ...`

### Cas 2 — run principal complet

1. `python -m event_sentiment ...`
2. si maintenance historique nécessaire : `history_backfill` ou `relevance_backfill`

### Cas 3 — orchestration semi-automatique IHM / PowerShell

Utiliser le wrapper `scripts/windows/import_news_and_score_pending.ps1`, qui peut enchaîner les étapes utiles selon les options.

