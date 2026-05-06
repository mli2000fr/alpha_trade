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

