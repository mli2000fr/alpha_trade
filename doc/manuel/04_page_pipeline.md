# 4. Page 🔄 Pipeline — orchestrer le cycle quotidien

## À quoi sert cette page

C'est la page la plus utilisée. Elle permet de :
- lancer le workflow complet (1 clic),
- ou lancer chaque étape une par une (en cas de problème),
- voir l'avancement en temps réel,
- consulter les logs.

## Quand l'utiliser

Tous les jours de bourse, **après la clôture US** (22h00 heure française).

## Pré-requis

- ✅ DB connectée (badge vert dans la sidebar).
- ✅ Compte Alpaca sélectionné (sinon les étapes Risk/Execution échoueront).
- ✅ Variables `ALPACA_API_KEY` et `EODHD_API_TOKEN` configurées dans le `.env`.

## Pas-à-pas : votre premier pipeline en simulation

### a) Choisir le mode

En haut de la page, un sélecteur **« Mode d'exécution »** :

| Mode | Effet | Recommandé pour |
|---|---|---|
| `simulate` | Aucun ordre n'est envoyé, calculs locaux | **Première utilisation** |
| `paper`    | Ordres envoyés au compte paper Alpaca | Après quelques jours en simulate |
| `live`     | Ordres envoyés au compte réel | **JAMAIS au début** |

👉 Choisissez **simulate** pour ce premier essai.

### b) Choisir le preset de capital

Sélecteur **« Capital preset »** :
- Si vous avez ~2 000 € → choisissez **`0 → 2 000 € (micro-compte)`**
  (clé `capital_0_2000_eur`).
- Sinon, laissez la valeur résolue automatiquement à partir de l'equity de
  votre compte Alpaca.

### c) Lancer

Cliquez sur **« 🚀 Lancer le workflow complet »**. La page affiche
immédiatement une barre de progression :

```
[1/14]  ✅ Import Alpaca Assets         (12 s)
[2/14]  ✅ Import Alpaca Bar            (3 min 42 s)
[3/14]  ⏳ Data Sanitizer Daily         …
[4/14]  ⏸ En attente
...
```

> ⏱️ Comptez **15 à 30 minutes** pour un premier pipeline complet.

### c.bis) Départ différé si vous voulez dormir avant l'exécution

Dans le bloc **« 🚀 Workflow complet configurable »**, vous pouvez cocher
**« Départ différé »** puis choisir une **heure de démarrage souhaitée**
(par exemple `02:00`).

Comportement :

- si l'heure choisie est **dans le futur aujourd'hui**, le workflow démarre
  aujourd'hui à cette heure ;
- si l'heure choisie est **déjà passée**, le workflow est planifié pour
  **demain** à cette heure ;
- pendant l'attente, le run apparaît en état **🕒 Planifié** dans le centre
  d'exécution ;
- vous pouvez encore **l'arrêter** avant son démarrage effectif.
- si vous **arrêtez l'IHM / `python run.py`** avant l'heure prévue, le
  workflow différé **n'est pas repris automatiquement** au redémarrage : il
  faut le replanifier.

👉 Cas d'usage typique : vous préparez tout vers `23:00`, puis vous planifiez
le lancement automatique à `02:00`.

### d) Que faire pendant que ça tourne

Vous pouvez :
- ✅ fermer le navigateur (le pipeline continue en arrière-plan),
- ✅ aller voir les autres pages,
- ❌ **ne pas** relancer un autre pipeline en parallèle.

### e) À la fin

Le bandeau passe à 🟢 **« Pipeline terminé avec succès »** et la page
**🏠 Vue d'ensemble** affiche les top candidats du jour.

## Les 14 étapes du pipeline

| # | Step | Rôle | Durée typique |
|---|---|---|---|
| 1 | Import Alpaca Assets | Liste des actions cotées | < 1 min |
| 2 | Import Alpaca Bar (ou EODHD) | Cours OHLCV du jour | 3-10 min |
| 3 | Data Sanitizer | Détection anomalies prix | 2 min |
| 4 | Update Sector | Mise à jour secteurs | 1 min |
| 5 | Stock Screener | Filtre liquidité | 2-5 min |
| 6 | Alpha Scanner (Selector) | Top 15-50 candidats | 3-8 min |
| 7 | Event Sentiment | Ingest news | 2-5 min |
| 8 | Signal Aggregator | Boost sentiment | < 1 min |
| 9 | ML Train (si rebuild) | Entraînement modèles | 5-30 min |
| 10 | ML Predict | Prédictions | 1-2 min |
| 11 | Risk Management | Sizing & contraintes | < 1 min |
| 12 | Execution | Envoi ordres broker | 1-3 min |
| 12bis | Protection Watcher | (background, 24/7) | continu |
| 13 | Corporate Actions Sync | Synchronisation CA | 2-5 min |
| 14 | Corporate Actions Apply | Application CA | < 1 min |

## Étapes auxiliaires (B1, B2, B3)

Sous l'onglet « **Centre d'exécution avancé** » :

| Step | Quand l'utiliser |
|---|---|
| **B1 — Sync Latest Quotes** | Avant ouverture US, pour avoir les pre-market |
| **B2 — Sync Earnings Calendar** | 1×/semaine (résultats trimestriels) |
| **B3 — Backfill EODHD** | 1× au tout début (5-10 ans d'historique) |

## Sous-panneau `7.bis Import des news brutes`

Dans le bloc pipeline, l'étape `7.bis` permet maintenant de piloter finement l'import news avant relance du scoring sentiment.

Vous pouvez régler :

- la **date de début** / **date de fin** ;
- l'**univers de symboles** :
  - `stock_scores` (défaut recommandé),
  - `candidates`,
  - `stock_bars_daily` (mode large historique) ;
- une **liste explicite de symboles** (`CSV`) si vous voulez cibler quelques valeurs ;
- un **cap sécurité** `max-symbols` pour empêcher un lancement trop large.

Avant même de cliquer sur le bouton, la page affiche désormais un **résumé live** :

- nombre de symboles réellement résolus ;
- source effective retenue ;
- extrait des premiers symboles ;
- erreur visible si le cap `max-symbols` bloquerait le lancement.

👉 Conseil pratique : laissez `stock_scores` par défaut, ou renseignez une shortlist `CSV` si vous ne voulez retraiter que quelques titres. N'utilisez `stock_bars_daily` que si vous savez pourquoi vous acceptez un univers potentiellement très large.

## Event Sentiment — mini guide d'usage IHM

Le bloc **Event Sentiment** expose maintenant trois modes de scoring :

| Mode | À utiliser quand | Ce que fait le run |
|---|---|---|
| `Standard only` | vous avez un backlog d'articles à vider rapidement, ou de nouveaux imports bruts à scorer | remplit `news_sentiment` puis reconstruit les features journalières sentiment |
| `Contextual only` | `news_sentiment` est déjà présent et vous voulez enrichir le niveau `(article, symbole)` | remplit `news_ticker_sentiment` sans refaire le scoring standard |
| `Standard + contextual` | fenêtre courte/moyenne, ou vous voulez tout faire en une seule passe | exécute d'abord le standard puis le contextuel dans le même run |

### Point important : pas de doublon avec `7bis — Backfill relevance / contextual`

La case **`Ajouter le contextual à ce backfill 7bis`** du bloc `7bis` ne pilote **pas** le run principal `event_sentiment`.

Elle sert uniquement au step dédié `python -m event_sentiment.relevance_backfill` pour rejouer le backfill relevance/contextuel sur une fenêtre déjà importée.

En résumé :

- **mode de scoring** = comportement du run principal **Event Sentiment** ;
- **case 7bis contextuel** = comportement du **backfill dédié** `relevance_backfill`.

Dans le workflow complet IHM, `7bis` est exécuté automatiquement **entre `7. Sentiment Pipeline` et `8. Signal Aggregator`**.

### Ordre recommandé en pratique

#### Cas 1 — gros backlog ou première passe

1. Lancez **`Standard only`** pour remplir `news_sentiment`.
2. Si vous voulez ensuite affiner ticker par ticker, relancez **`Contextual only`** sur la même fenêtre.
3. Lancez **`Rebuild daily sentiment features only`** pour rematérialiser les agrégats journaliers downstream.
4. Si besoin, relancez **Signal Aggregator** pour propager le nouveau signal vers `stock_scores`.

#### Cas 2 — corpus déjà scoré standard, enrichissement seulement

1. Lancez **`Contextual only`**.
2. Lancez **`Rebuild daily sentiment features only`**.

#### Cas 3 — petite fenêtre, tout en une fois

1. Lancez **`Standard + contextual`**.
2. Le rebuild dédié n'est généralement pas nécessaire juste après, sauf si vous voulez rejouer uniquement les agrégats sur une fenêtre spécifique.

## Paramétrer TP / SL depuis la page Pipeline

Dans **Centre d'exécution avancé** → bloc **Execution** → section
**Stratégie de protection — sortie** :

- vous pouvez désormais régler le **take-profit cible (%)** directement dans l'IHM ;
- vous pouvez aussi régler le **trailing stop (%)** (`trailing_stop_pct`) ;
  c'est le pourcentage utilisé pour le trailing stop broker-side / fallback
  quand le moteur doit armer une protection de type trailing ;
- ce réglage est transmis à `run_execution.py` puis au watcher de protection ;
- le **stop initial** n'est pas saisi manuellement ici : il est calculé
  automatiquement par le step **11 Risk** (`stop_price_initial` /
  `risk_per_share`, basé sur l'ATR).

👉 Le bandeau de la page Pipeline rappelle maintenant, sous
**PANIER CAPITAL APPLIQUÉ** :

- le **TP actif** ;
- le **trigger trailing** actif ;
- le **trailing stop %** ;
- la **fenêtre de soumission** (`post_close` / `pre_open` / `both`) ;
- et le fait que le **stop initial** est calculé automatiquement.

## Lecture des résultats

### Bandeau « Run summary »

À la fin de chaque pipeline, un encart affiche :
- `run_id` : identifiant unique
- `n_candidates` : nombre de candidats sélectionnés
- `n_orders` : nombre d'ordres envoyés
- `business_summary` : phrase synthétique générée automatiquement

### En cas d'échec d'un step

- 🟠 Le step apparaît en orange.
- Cliquez sur **« Voir les logs »** pour identifier l'erreur.
- Cliquez sur **« Relancer ce step uniquement »** pour réessayer sans
  refaire les précédents.
- Voir [51_depannage.md](51_depannage.md) pour les erreurs courantes.

## Pièges courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| Step 2 très lent (> 30 min) | Connexion Internet faible | Patientez ou repassez sur EODHD (plus rapide) |
| Step 5 retourne 0 candidat | Filtres trop stricts | Vérifiez votre preset (cf. [05_page_screening.md](05_page_screening.md) §5) |
| Step 7 échoue (sentiment) | Token EODHD manquant | Désactivez sentiment dans les options ou ajoutez le token |
| Step 9 (ML) très long | Premier rebuild complet | Normal (30 min). Choisissez `refresh-stale` les jours suivants. |
| Step 12 « no orders » | Aucun candidat n'a passé les filtres risk | Normal certains jours (marché baissier) |

## Pour aller plus loin

- Comprendre le sizing : [07_page_risk.md](07_page_risk.md)
- Suivi des ordres : [08_page_execution.md](08_page_execution.md)
- Watcher 24/7 : [12_page_supervision_ops.md](12_page_supervision_ops.md)

