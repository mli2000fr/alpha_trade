# Refactor demandé — fusion de l’étape 7 et suppression de 7bis

## Contexte produit
Dans l’IHM page Pipeline, il existe aujourd’hui :
- **Étape 7 — `Sentiment Pipeline`**
- **Étape 7bis — `Contextual FinBERT (7bis)`**

### Comportement actuel observé dans le code
Références principales lues dans le dépôt :
- `ihm/services/pipeline_runner.py`
- `ihm/pages/pipeline.py`
- `ihm/pages/_execution_center/__init__.py`
- `ihm/pages/_data_integrity.py`
- `ihm/pages/_workflow/__init__.py`
- `ihm/services/process_registry.py`
- `event_sentiment/pipeline.py`
- `event_sentiment/cli.py`
- `event_sentiment/relevance_backfill.py`
- `event_sentiment/config.py`
- `event_sentiment/db_io.py`
- `scripts/windows/import_news_and_score_pending.ps1`
- tests `tests/test_ihm_pipeline_runner.py`, `tests/test_pages_pipeline.py`, `tests/test_ihm_process_registry.py`, `tests/test_event_contextual_scoring.py`, `tests/test_event_relevance_backfill.py`

### État actuel exact
#### Étape 7 (`sentiment_pipeline`)
Dans `ihm/services/pipeline_runner.py`, `build_pipeline_command("sentiment_pipeline", ...)` construit aujourd’hui une **chaîne PowerShell de 3 sous-commandes** :
1. `python -m event_sentiment --skip-features`
   - import news
   - scoring FinBERT standard
   - pas de scoring contextuel dans cette commande
2. `python -m event_sentiment.relevance_backfill`
   - calcul `relevance_score` (Niveau 2/3)
3. `python -m event_sentiment.history_backfill`
   - agrégation des features journalières ticker/secteur

Le libellé de l’étape 7 dans `PIPELINE_STEPS` est cohérent avec ce comportement.

#### Étape 7bis (`relevance_backfill` côté IHM)
Dans `ihm/services/pipeline_runner.py`, `build_pipeline_command("relevance_backfill", ...)` exécute aujourd’hui :
- `python -m event_sentiment.relevance_backfill --contextual-only --rescore-contextual`
- donc **uniquement** le scoring FinBERT contextuel (Niveau 4) vers `news_ticker_sentiment`
- sans recalcul de `relevance_score`

#### Backend déjà disponible
Le backend `event_sentiment/pipeline.py` sait déjà exécuter le scoring contextuel dans `EventSentimentPipeline.run()` quand le mode vaut :
- `contextual_only`
- ou `standard_and_contextual`

Le CLI `event_sentiment/cli.py` supporte déjà :
- `--scoring-mode`
- `--enable-contextual-scoring`
- `--contextual-min-relevance`
- `--contextual-max-pairs`
- `--sentiment-pending-limit`
- `--sentiment-pending-max-batches`
- `--feature-flush-every-n-batches`
- `--finbert-batch-size`

#### Paramètres IHM existants
Dans `ihm/pages/_execution_center/__init__.py`, l’IHM expose déjà des réglages configurables pour :
- mode de scoring sentiment
- seuil `min_relevance_score`
- seuil contextual min relevance
- cap max paires contextuelles
- batch size contextuel / batch size FinBERT
- pending limit
- pending max batches
- feature flush
- purge threshold
- provider / symbol scope / fenêtre temporelle

Mais la présentation et la sémantique restent encore fortement marquées **7 / 7bis**, avec du texte, des explications et des boutons qui parlent encore de 7bis.

#### Workflow configurable actuel
Le workflow principal inclut encore explicitement `7bis` :
- `PIPELINE_STEPS` contient `relevance_backfill` avec `num="7bis"`
- `get_pipeline_workflow_steps()` l’inclut dans le workflow cœur
- `is_workflow_core_step_number()` a un cas spécial pour `7bis`
- `parse_pipeline_step_number("7bis") == 7`
- plusieurs tests vérifient la présence et l’ordre de `7bis` entre `7` et `8`

#### Wrappers / scripts auto actuels
Le script `scripts/windows/import_news_and_score_pending.ps1` enchaîne actuellement :
- import éventuel
- boucle de scoring pending standard/contextuel via `python -m event_sentiment`
- `event_sentiment.history_backfill`
- `event_sentiment.relevance_backfill`

Le panneau `ihm/pages/_data_integrity.py` expose aussi plusieurs actions auxiliaires encore nommées `7.bis`, `relevance_backfill`, `score + history_backfill + relevance_backfill auto`, etc.

---

## Objectif cible
Je veux que le refactor aboutisse à ce comportement métier visible :

### Nouvelle Étape 7 — `Sentiment Pipeline`
Elle doit faire **dans cet ordre affiché et documenté** :
1. **Import news**
2. **Scoring FinBERT standard (sans features)**
3. **Calcul `relevance_score` (Niveau 2/3, pur Python — sans FinBERT)**
4. **Agrégation features journalières (ticker/secteur)**
5. **Scoring FinBERT contextuel (Niveau 4 — `news_ticker_sentiment`)**

### Étape 7bis
- **supprimée de l’IHM pipeline**
- **retirée du workflow configurable complet**
- **retirée de la sélection personnalisée des étapes**
- **retirée des libellés, aides et tests du workflow**

### Contrainte forte
**Tous les paramètres aujourd’hui configurables dans l’IHM doivent rester disponibles** après refactor.

Le refactor doit être fait côté :
- **IHM**
- **backend**
- **flow / orchestration configurable**

Le backend doit aussi être rendu **plus propre / plus cohérent** : éviter la duplication de logique 7 vs 7bis et clarifier ce qui relève du pipeline principal versus d’un éventuel outil de maintenance.

---

## Attendu détaillé

## 1) Refactor IHM — fusion visuelle et fonctionnelle dans l’étape 7
Mettre à jour au minimum :
- `ihm/services/pipeline_runner.py`
- `ihm/pages/pipeline.py`
- `ihm/pages/_execution_center/__init__.py`
- `ihm/pages/_data_integrity.py`
- éventuellement les helpers associés si nécessaires

### Ce qu’il faut faire
1. **Supprimer l’étape `relevance_backfill` du `PIPELINE_STEPS` principal**.
2. **Mettre à jour la description de l’étape 7** pour refléter les 5 sous-étapes, y compris le contextual.
3. **Adapter la prévisualisation de commande** de l’étape 7 pour qu’elle inclue désormais le contextual dans la même étape.
4. **Conserver tous les réglages existants** de l’UI relatifs au contextual, mais les rattacher sémantiquement à l’étape 7 et non plus à 7bis.
5. Dans `ihm/pages/_execution_center/__init__.py` :
   - retirer le framing “7bis — Contextual FinBERT (Niveau 4)” en tant qu’étape séparée,
   - garder les champs configurables,
   - regrouper les paramètres sous une section étape 7 / Event Sentiment plus claire,
   - nettoyer les captions/commentaires obsolètes du type “toujours standard_only” / “toujours False” si elles sont devenues fausses ou trompeuses,
   - préserver au maximum la compatibilité de `st.session_state` pour éviter de perdre les préférences utilisateur.
6. Dans `ihm/pages/pipeline.py` :
   - retirer tout bloc / message qui fait encore de 7bis une étape pilotable du workflow cœur,
   - vérifier les verrous d’exécution (`active_by_step`, companion runs, warnings) pour ne plus dépendre d’un step 7bis supprimé.
7. Dans `ihm/pages/_data_integrity.py` :
   - supprimer ou renommer tout wording “7.bis” dans les aides utilisateur,
   - si certains boutons restent pertinents en maintenance, les conserver mais les présenter comme **outils auxiliaires de maintenance/backfill sentiment**, pas comme une étape 7bis du workflow principal,
   - aligner les textes sur la nouvelle réalité : le contextual est désormais intégré à l’étape 7.
8. Dans `ihm/pages/_data_integrity.py`, pour le bloc aujourd’hui intitulé **`7.bis Import des news brutes`** :
   - le renommer en **`7.bis Traitement par étape`**,
   - en faire un bloc de lancement **pas à pas** des sous-étapes de la nouvelle étape 7,
   - **supprimer les 5 boutons existants** de ce bloc,
   - **ajouter 5 nouveaux boutons** correspondant exactement aux 5 sous-étapes suivantes, dans cet ordre :
     1. **Import news**
     2. **Scoring FinBERT standard (sans features)**
     3. **Calcul `relevance_score` (Niveau 2/3, pur Python — sans FinBERT)**
     4. **Agrégation features journalières (ticker/secteur)**
     5. **Scoring FinBERT contextuel (Niveau 4 — `news_ticker_sentiment`)**
   - faire en sorte que ce bloc serve explicitement à **lancer le traitement étape par étape**, en réutilisant **les paramètres existants** déjà exposés dans l’IHM,
   - veiller à ce que ce bloc reste un **outil auxiliaire de pilotage manuel** et non la matérialisation d’une étape cœur `7bis` du workflow principal.

### Important
Si tu gardes des outils manuels type `import_news`, `score_sentiment_only`, `rebuild_daily_sentiment_features_only` ou wrappers auto pour maintenance, c’est acceptable, **mais ils ne doivent plus faire croire qu’il existe une étape cœur 7bis**.

---

## 2) Refactor backend — rendre l’orchestration plus propre
Mettre à jour au minimum :
- `ihm/services/pipeline_runner.py`
- `event_sentiment/pipeline.py`
- `event_sentiment/cli.py`
- `event_sentiment/relevance_backfill.py`
- `event_sentiment/config.py`
- `scripts/windows/import_news_and_score_pending.ps1`
- éventuellement `event_sentiment/db_io.py` si nécessaire, mais éviter les changements inutiles

### Ce qu’il faut faire
1. **Faire en sorte que l’étape 7 déclenche aussi le scoring contextuel**, au lieu de déléguer cela à une étape 7bis séparée.
2. **Réduire la duplication entre** :
   - la chaîne spéciale construite dans `build_pipeline_command("sentiment_pipeline")`
   - le support natif déjà présent dans `EventSentimentPipeline.run()` pour le contextual
   - le CLI `event_sentiment.relevance_backfill`
3. Décider proprement de l’architecture cible, avec préférence pour une solution lisible et maintenable :
   - soit l’étape 7 reste une chaîne de sous-commandes mais avec une 4e/5e sous-commande claire pour le contextual,
   - soit la logique est davantage recentrée dans le pipeline backend principal,
   - **mais dans tous les cas l’UI et le workflow ne doivent plus porter 7bis comme step cœur**.
4. **Préserver tous les paramètres configurables actuels** :
   - `sentiment_scoring_mode`
   - `sentiment_enable_contextual_scoring`
   - `sentiment_contextual_min_relevance`
   - `sentiment_contextual_max_pairs`
   - `sentiment_pending_limit`
   - `sentiment_pending_max_batches_per_run`
   - `sentiment_feature_flush_every_n_batches`
   - `sentiment_finbert_batch_size`
   - `backfill_relevance_batch_size`
   - `backfill_relevance_purge_below`
   - paramètres de fenêtre / provider / symboles / symbol_source / max_symbols
5. **Nettoyer la frontière de responsabilité** :
   - l’étape 7 = pipeline principal sentiment de production
   - `relevance_backfill.py` peut rester comme utilitaire technique / maintenance si utile,
   - mais il ne doit plus être la représentation d’une étape workflow principale “7bis”.
6. Si des flags ou aides CLI deviennent incohérents après fusion, les ajuster pour refléter la nouvelle architecture.

### Point d’attention important
Le backend `event_sentiment/pipeline.py` sait déjà faire du contextual via `standard_and_contextual` / `contextual_only`, mais le comportement exact de l’étape 7 historique est une chaîne :
- standard
- relevance
- history_backfill
- puis 7bis à part pour contextual

Il faut donc refactorer **sans casser les usages existants**, en veillant à la cohérence métier voulue par la cible.

---

## 3) Refactor du workflow configurable complet
Mettre à jour au minimum :
- `ihm/services/pipeline_runner.py`
- `ihm/pages/_workflow/__init__.py`
- `ihm/services/process_registry.py`
- tests associés

### Ce qu’il faut faire
1. **Retirer `7bis` du workflow cœur**.
2. Supprimer le cas spécial `7bis` dans :
   - `parse_pipeline_step_number()` si devenu inutile
   - `is_workflow_core_step_number()`
   - la logique de formatage des plages d’étapes
3. Mettre à jour `get_pipeline_workflow_steps()` pour que le workflow quotidien passe directement de `7` à `8`.
4. Adapter tous les libellés du workflow personnalisé :
   - plus de checkbox “7bis”
   - plus de texte “7bis between 7 and 8”
   - plus de dépendance `step_8 -> step_7bis`
5. Vérifier les dépendances déclarées :
   - `signal_aggregator` doit dépendre du `sentiment_pipeline` refactoré
   - aucune dépendance workflow ne doit rester accrochée à `relevance_backfill`

---

## 4) Compatibilité UX / paramètres — impératif
Je veux **garder tous les paramètres configurables dans l’IHM**.

### Règles à respecter
- ne pas supprimer un paramètre utile juste parce que 7bis disparaît
- si un paramètre change de section, conserver son comportement
- si possible conserver les clés de session/state ou assurer une migration douce
- ne pas casser les previews de commande
- ne pas casser les boutons manuels de maintenance si tu choisis de les conserver
- nettoyer les textes d’aide pour qu’ils n’annoncent plus un fonctionnement 7/7bis obsolète

---

## 5) Tests à adapter / compléter
Mettre à jour les tests existants et en ajouter si nécessaire.

### Fichiers de tests explicitement impactés
- `tests/test_ihm_pipeline_runner.py`
- `tests/test_pages_pipeline.py`
- `tests/test_ihm_process_registry.py`
- éventuellement tests liés aux commandes / workflow / sentiment

### Exemples de changements attendus dans les tests
1. `get_pipeline_steps()` ne doit plus contenir `relevance_backfill` comme étape cœur.
2. `get_pipeline_workflow_steps()` ne doit plus injecter `7bis`.
3. Les helpers de numérotation ne doivent plus réserver un traitement spécial à `7bis` si ce n’est plus nécessaire.
4. Les tests de preview de commande de l’étape 7 doivent vérifier le **nouveau comportement fusionné**.
5. Les tests UI qui vérifient l’affichage d’une checkbox 7bis doivent être réécrits pour vérifier l’absence de 7bis et la continuité `7 -> 8`.
6. Les tests de registre / format de plage d’étapes doivent être mis à jour pour refléter la disparition de `7bis` du workflow principal.
7. Ajouter si besoin un test qui garantit que les paramètres contextuels saisis dans l’IHM sont bien injectés dans la nouvelle étape 7 fusionnée.

### Validation attendue
Après refactor, exécuter au minimum les tests touchés par cette fusion.

---

## 6) Critères d’acceptation
Le travail est correct si :

1. Dans l’IHM Pipeline, il n’existe plus de **step cœur 7bis**.
2. L’étape 7 affiche et exécute bien la logique fusionnée incluant le **FinBERT contextuel**.
3. Le workflow configurable complet ne contient plus 7bis.
4. Tous les paramètres configurables actuellement exposés restent disponibles et utiles.
5. Le bloc manuel de `ihm/pages/_data_integrity.py` est renommé en **`7.bis Traitement par étape`** et propose bien **5 boutons** correspondant aux **5 sous-étapes** de l’étape 7, pour un lancement séquentiel manuel.
6. Le backend est plus lisible : moins de duplication, responsabilités clarifiées.
7. Les textes UI / captions / aides ne parlent plus d’une architecture obsolète.
8. Les tests impactés sont mis à jour et passent.

---

## 7) Contraintes de mise en œuvre
- faire le **plus petit refactor propre possible**
- éviter les changements de schéma DB inutiles
- ne pas casser les outils de maintenance si leur conservation apporte de la valeur
- mais **retirer totalement 7bis du workflow principal et de l’expérience utilisateur cœur**
- conserver le style de code existant
- ne pas introduire de breaking change silencieux sur les paramètres IHM

---

## 8) Livrable attendu
Je veux un refactor complet IHM + backend + workflow, avec :
- code modifié
- tests mis à jour
- comportement final aligné sur :

### Étape 7 finale
1. Import news  
2. Scoring FinBERT standard (sans features)  
3. Calcul `relevance_score` (Niveau 2/3, pur Python — sans FinBERT)  
4. Agrégation features journalières (ticker/secteur)  
5. Scoring FinBERT contextuel (Niveau 4 — `news_ticker_sentiment`)  

### Étape 7bis finale
- supprimée du workflow principal et de l’IHM pipeline.

