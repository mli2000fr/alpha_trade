# Audit — `event_sentiment`

> Périmètre : `event_sentiment/` (pipeline complet : `cli.py`, `pipeline.py`,
> `ingestion.py`, `scoring.py`, `aggregation.py`, `signal_aggregator.py`,
> `macro_rules.py`, `db_io.py`, `mapping.py`, `models.py`, `trading_calendar.py`,
> `importe_news.py`, `event_sentiment_pipeline.py`, `sentiment_pipeline.py`,
> `history_backfill.py`, `config.py`).
> Sources : `doc/event_sentiment.md`, code listé, tests `tests/test_event_*`,
> `tests/test_signal_aggregator.py`, `tests/test_finbert_preprocessor.py`,
> `tests/test_importe_news.py`, `tests/test_sentiment_pipeline.py`.

---

## 1. Résumé exécutif

`event_sentiment/` ingère les news Alpaca, score via **FinBERT** (`ProsusAI/finbert`),
détecte des règles macro, agrège en features journalières par ticker et par secteur,
puis fusionne dans `stock_scores.final_score_sentiment` (poids défaut : quant 75 % +
sentiment ticker 15 % + macro sectoriel 10 %).

État global : **module riche et bien structuré**. Bonne séparation pipeline / scoring /
agrégation / fusion. Tolérance aux données manquantes (fallback sur signal neutre,
score quant jamais supprimé). Tests nombreux et ciblés.

Principaux risques :

1. **FinBERT est pré-entraîné, non re-fine-tuné** → biais de domaine probable
   (FinBERT généraliste, pas spécifique au swing trading US). Pas de validation
   continue de la qualité du sentiment vs résultat de trade.
2. **Source de news unique : Alpaca News** → couverture limitée (pas de Bloomberg, pas de
   Reuters direct). Pour les small/mid caps, la couverture est inégale.
3. **Pondération `75/15/10` arbitraire** : pas de calibration empirique IC-weighted
   documentée (mentionné comme suggestion d'amélioration §7 DOC_FONCTIONNELLE).
4. **`macro_rules.py`** : règles macro hard-codées (taux Fed, CPI, etc.) → maintenance
   manuelle, source de divergence si on ne la met pas à jour.
5. **Throttling FinBERT** : pas d'info sur la batch size GPU/CPU côté `scoring.py`.
   Sur 1000+ articles/jour, le runtime peut exploser sans accélérateur.
6. **Trading calendar** : `trading_calendar.py` aligne les news sur la séance suivante.
   À vérifier pour les news publiées à 16:00:01 ET vs 15:59:59 ET (frontière fragile).

Priorités immédiates :
- Mesurer périodiquement la qualité du signal sentiment (IC vs forward returns).
- Documenter la batch size FinBERT et le coût par run.
- Versionner les règles macro et les poids quant/sentiment/macro.

---

## 2. Constat détaillé

### 2.1 `pipeline.py` — `EventSentimentPipeline`

| Item | Détail |
|---|---|
| Constat | Orchestrateur principal : résolution univers → checkpoints → ingestion → scoring → macro → agrégation. |
| Force | Reprise via `news_ingestion_checkpoint` → idempotence et reprise sur incident bien traitées. |
| Risque | **Cohérence** : si `news_ingestion_checkpoint` est corrompu, le pipeline peut sauter une période sans alerte. |
| Recommandation | Ajouter une vérification `(now - watermark) > 7d` qui force un backfill explicite ou un warning critical. |

### 2.2 `ingestion.py` — `NewsIngestionService`

| Constat | Pagination Alpaca News, normalisation, alignement calendrier, écriture `news_raw` + `news_ticker_map`. |
| Risque | **Qualité des données** : pas de déduplication explicite documentée si Alpaca renvoie le même article sur deux requêtes (ex: borne `published_at` chevauchante). |
| Recommandation | Confirmer la contrainte unique sur `news_raw.alpaca_id` (à vérifier dans le DDL) ; logger les duplications. |

### 2.3 `scoring.py` — FinBERT

| Constat | Charge `ProsusAI/finbert`, score `positive/neutral/negative` → `sentiment_net`. |
| Risque | **Performance** : pas de batch size par défaut documenté. Sur 1k articles + CPU, peut prendre des minutes. |
| Risque 2 | **Maintenabilité** : pas de pinning explicite du modèle (version HuggingFace). Le jour où ProsusAI publie une v2, le résultat change silencieusement. |
| Risque 3 | **Qualité** : FinBERT v1 est entraîné sur des financial news *générales* (souvent sur Financial PhraseBank). Risque de mismatch domaine sur les news US tech / biotech / penny stocks. |
| Recommandation | (a) Pinner `revision="..."` dans `transformers.AutoModel.from_pretrained` ; (b) batch size paramétrable `--finbert-batch-size 32` ; (c) métrique de cohérence IC sur 30j sentiment vs forward return par ticker. |

### 2.4 `macro_rules.py`

| Constat | Règles macro métier (ex: "rate hike → impact négatif sur tech"). |
| Risque | Hard-coding → ne suit pas la macro réelle. |
| Recommandation | Externaliser dans `config/macro_rules.yaml` versionnable. |

### 2.5 `aggregation.py` — features daily

| Constat | Calcule `news_count_*`, `sentiment_net_mean_*`, etc. par ticker et par secteur, sur fenêtres glissantes. |
| Risque | **Cohérence temporelle** : les fenêtres glissantes consomment `news_sentiment` ; si une news est rescorée (rare mais possible si on change FinBERT), les anciennes features ne sont pas recalculées automatiquement. |
| Recommandation | Ajouter une option `--rebuild-features-since YYYY-MM-DD`. |

### 2.6 `signal_aggregator.py` — fusion

| Item | Détail |
|---|---|
| Constat | Fusion `final_score_sentiment = w_quant * final_score + w_sent * sent_ticker + w_macro * macro_sector`. Poids par défaut `0.75/0.15/0.10`. Tolère les tables sentiment absentes (fallback neutre). Validation `w_sent + w_macro <= 1.0`. |
| Force | Backend tolérant. Bonne idempotence par `trade_date`. |
| Risque | **Modèle / ML** : pondération arbitraire non calibrée. Pas de validation que `final_score_sentiment` est meilleur que `final_score` seul (prouverait l'utilité du sentiment). |
| Risque 2 | `--time-decay-half-life-days` exposé en CLI mais peu documenté côté impact métier. |
| Recommandation | (a) Backtest A/B systématique : conserver `final_score` ET `final_score_sentiment` dans `stock_scores`, comparer en backtest les deux univers de candidats sur 1 an glissant ; (b) calibration auto IC-weighted des poids (suggestion 9 DOC_FONCTIONNELLE) ; (c) documenter le `time_decay_half_life`. |

### 2.7 `trading_calendar.py`

| Constat | Aligne `published_at_utc` sur la séance de trading effective (next trading session). |
| Risque | Frontière 16:00 ET fragile : une news publiée à 16:00:00 ET vs 16:00:01 doit-elle être attribuée à la séance du jour ou à J+1 ? |
| Recommandation | Convention explicite (ex: news après `cutoff_time = 15:30 ET` → J+1) + test paramétrique. |

### 2.8 `importe_news.py` — script ad-hoc

| Constat | Script séparé pour réinjecter une plage de news brute. Lancé depuis l'IHM. |
| Risque | **Maintenabilité** : duplique partiellement `ingestion.py`. |
| Recommandation | Refactor pour qu'`importe_news.py` ne soit qu'un wrapper CLI sur `NewsIngestionService.fetch_window(start, end, force=True)`. |

---

## 3. Risques prioritaires

### Critique
- Aucun, mais **risque latent fort** : pas de validation continue de la qualité du
  signal sentiment (peut empirer la performance au lieu de l'améliorer si mal calibré).

### Élevé
- FinBERT non versionné / non pinné.
- Pondération `75/15/10` arbitraire, non backtestée formellement.
- Source unique Alpaca News (couverture inégale).
- Macro rules hard-codées.

### Modéré
- Performance FinBERT non instrumentée.
- Trading calendar : frontière 16:00 ET non explicite.
- Pas de check sur la fraîcheur du `news_ingestion_checkpoint`.

### Faible
- `importe_news.py` partiellement dupliqué avec `ingestion.py`.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Le pipeline news est **moins impacté par IEX** car la news est extraite d'Alpaca News
(canal séparé du market data), pas du tape IEX.

**Limitations Alpaca News** (free) :
- couverture surtout focalisée sur les majors (Benzinga repackagé) → mid/small caps
  sous-couverts ;
- latence : pas de garantie temps réel, OK car le projet est batch ;
- pas de classification de source (Bloomberg vs press release vs blog) → pondération
  par "qualité de source" impossible.

**Alternatives gratuites pertinentes** :

| Source | Avantages | Limites | Pertinence |
|---|---|---|---|
| **Yahoo Finance RSS** | Gratuit, pas de quota strict | Qualité variable | Faible (déjà dans Alpaca) |
| **SEC EDGAR 8-K** | Filings officiels matériels | Format ESEF, parsing | **Élevée** pour event-driven |
| **Reuters / Reddit / Twitter via API** | Couverture large | Auth, quota | Modérée |
| **Newsdata.io free** | News API | 200 req/j en free | Faible |
| **Marketaux free** | News financières | 100 req/j | Faible |

**Recommandation** : ajouter un **second canal SEC EDGAR 8-K** (filings matériels :
fusions, démissions CEO, restatements) qui complète Alpaca News pour les events les
plus durs, avec un poids dédié dans `signal_aggregator`.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct (le pipeline news ne consomme pas de prix).

---

## 6. Quick wins

1. **Pinner la version FinBERT** (`revision="..."` dans `from_pretrained`).
2. **`--finbert-batch-size`** exposé + valeur par défaut documentée.
3. **Logger un warning critical** si `now - watermark > 7d` sur tout symbole.
4. **Externaliser `macro_rules`** dans `config/macro_rules.yaml`.
5. **Documenter `time_decay_half_life_days`** dans `doc/event_sentiment.md`.
6. **Test paramétrique trading calendar** (16:00 ET frontière).
7. **Versioning des poids** (`signal_aggregator_version: "v1"`) inclus dans le
   `run_summary`.

## 7. Recommandations structurelles

1. **Système A/B `final_score` vs `final_score_sentiment`** : exposer les deux en
   permanence dans `stock_scores` ; backtest auto comparant les deux univers,
   stocké dans `event_sentiment_quality_metrics`.
2. **Calibration IC-weighted des poids** (proposé §7 DOC_FONCTIONNELLE) :
   recalcul périodique (hebdo) basé sur backtest glissant 6 mois, écriture dans
   `signal_aggregator_weights_history`.
3. **Second canal news SEC EDGAR 8-K** intégré comme provider alternatif.
4. **Fine-tune léger de FinBERT** (LoRA) sur news Alpaca avec labels = forward
   returns 5j → option future.
5. **Cache scores FinBERT** : éviter de rescorer un article déjà traité (déjà
   probablement fait via `news_sentiment` table, à confirmer).

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 5, 7.
- Tests paramétriques calendar.

### Moyen terme
- A/B `final_score` vs `final_score_sentiment` documenté en backtest.
- Externalisation `macro_rules.yaml`.
- Refactor `importe_news.py` en wrapper.

### Long terme
- Calibration IC-weighted des poids (suggestion §7).
- Intégration SEC EDGAR 8-K.
- Fine-tune FinBERT.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Très bonne couverture. **Manque** :
  - test de drift FinBERT (modèle différent → résultats différents → alarm).
  - test bench performance scoring (régression > 50 % → fail CI).
  - test A/B `final_score` vs `final_score_sentiment` sur fixtures historiques.

### Monitoring
- `run_summary` riche. **Manque** :
  - métriques de qualité (IC sentiment vs forward return).
  - métriques de fraîcheur par symbole (`max(news.published_at) - now`).

### Documentation
- Très complète. **Manque** :
  - section "limitations Alpaca News" et alternatives.
  - guide "comment recalibrer les poids".
  - explication formelle du calcul `time_decay`.

