# 3. Workflow quotidien — comprendre le cycle complet

> Objectif : comprendre **dans quel ordre** les choses doivent être lancées
> et **pourquoi**, sans (encore) cliquer.

## 3.1 Vue d'ensemble du cycle journalier

Chaque jour de bourse (du lundi au vendredi, hors fériés US), le cycle
ressemble à ceci :

```
                  ┌──────────────────────────────────────┐
                  │  17 h — Marchés US clôturés          │
                  │  Vous lancez le pipeline             │
                  └──────────────────┬───────────────────┘
                                     ▼
        ┌────────────────────────────────────────────────────┐
        │ 1. DATA          : import des cours, secteurs       │
        │ 2. SCREENER      : trouver l'univers liquide        │
        │ 3. SELECTOR      : top 50 des candidats techniques  │
        │ 4. SENTIMENT     : actu / FinBERT / boost           │
        │ 5. ML            : prédire la probabilité de hausse │
        │ 6. RISK          : sizing, contraintes secteur      │
        │ 7. EXECUTION     : envoyer les ordres au broker     │
        │ 8. CORP ACTIONS  : appliquer dividendes / splits    │
        │ 9. SUPERVISION   : watcher de protection (24h)      │
        └────────────────────────────────────────────────────┘
                                     ▼
                  ┌──────────────────────────────────────┐
                  │  Le lendemain : ouverture des US     │
                  │  Vos ordres sont exécutés à l'ouverture │
                  └──────────────────────────────────────┘
```

## 3.2 Détail des 9 étapes

### Étape 1 — DATA (import & nettoyage)

**Quoi ?** L'application télécharge les cours OHLCV (Open / High / Low /
Close / Volume) du jour pour des milliers d'actions US, met à jour les
secteurs, les calendriers de résultats et nettoie les anomalies.

**Pourquoi ?** Sans données fraîches, tout le reste est faux.

**Durée** : 5-15 minutes selon votre connexion.

**Page IHM** : 🔄 Pipeline → étapes 1, 2, 3, 4 + auxiliaires B1, B2.

### Étape 2 — SCREENER (filtre liquide)

**Quoi ?** On garde uniquement les actions « investissables » : volume
suffisant, prix > X $, pas de penny stock manipulable, etc.

**Sortie** : table `stock_scores` (~ 500-2 000 lignes selon votre preset).

**Page IHM** : 📊 Screening pour consulter le résultat.

### Étape 3 — SELECTOR (alpha scanner)

**Quoi ?** Sur les actions screenées, on calcule des **facteurs de momentum**
(force relative, proximité du plus haut 52 semaines, beta, ATR…) et on
sélectionne les **15 à 50 meilleures** (selon votre preset).

**Sortie** : table `candidates` avec un `final_score` entre 0 et 100.

### Étape 4 — SENTIMENT (actualités + FinBERT)

**Quoi ?** L'application lit les news des dernières 24-48 h, les passe dans
FinBERT (un modèle d'IA spécialisé finance) et calcule un **score de
sentiment** (-1 = très négatif, +1 = très positif) par symbole et par
secteur.

**Effet** : ce score boost ou pénalise le `final_score` du selector
(`final_score_sentiment`).

### Étape 5 — ML (prédiction de hausse)

**Quoi ?** Pour chaque candidat, un modèle de Machine Learning
(LSTM + LightGBM en champion-challenger) prédit la **probabilité que le
cours soit > +2 % dans 5 jours**.

**Sortie** : table `ml_predictions` avec `probability_long` ∈ [0, 1].

**Page IHM** : 🤖 ML / Prédictions.

### Étape 6 — RISK (sizing & contraintes)

**Quoi ?** Le module risk décide :
- combien d'argent allouer à chaque ligne (selon votre `risk_per_trade_pct`),
- quelles positions tenir (en respectant `max_positions`, `max_sector_weight`,
  corrélations…),
- où placer le stop-loss et le take-profit.

**Sortie** : table `portfolio_targets` (= votre portefeuille cible
demain).

**Page IHM** : ⚖️ Risk.

### Étape 7 — EXECUTION (passage d'ordres)

**Quoi ?** Le module compare le portefeuille **actuel** au portefeuille
**cible** et envoie au broker (Alpaca) les ordres BUY/SELL nécessaires +
les ordres protecteurs (stop-loss, take-profit, trailing stop).

**Modes** :
- `simulate` : aucun ordre n'est envoyé (vous testez en local).
- `paper` : ordres envoyés au compte paper Alpaca (faux argent).
- `live` : ordres envoyés au compte réel.

**Page IHM** : 🚀 Execution.

### Étape 8 — CORPORATE ACTIONS

**Quoi ?** Si une de vos positions a payé un dividende, fait un split, etc.,
l'application l'enregistre et ajuste les quantités / le cash.

**Page IHM** : 📑 Corporate Actions.

### Étape 9 — SUPERVISION (watcher 24/7)

**Quoi ?** Un processus en arrière-plan (« protection watcher ») surveille
vos positions et vérifie que les stop-loss / take-profit sont bien en place
chez le broker. Si un ordre disparaît mystérieusement, il en remet un.

**Page IHM** : 🛟 Supervision Ops.

## 3.3 Quand exécuter chaque étape ?

| Étape | Fréquence | Heure idéale (heure française) |
|---|---|---|
| Data + screener + selector + sentiment + ML + risk | Tous les jours de bourse US | 22h30-23h30 (après clôture US 22h00) |
| Execution `paper` | Au choix, le matin avant ouverture US (15h00) | 14h00-15h00 |
| Execution `live` | Une fois prêt, idem | 14h00-15h00 |
| Corporate actions sync | 1×/semaine ou après chaque dividende attendu | week-end |
| Backtesting | Quand vous changez un paramètre | au calme |

## 3.4 Bonne nouvelle : tout est automatisable depuis 1 bouton

Sur la page **🔄 Pipeline**, le bouton **« Lancer le workflow complet »**
exécute les étapes 1 à 7 dans le bon ordre, en arrière-plan. Vous pouvez
fermer le navigateur, ça continue.

> Voir [04_page_pipeline.md](04_page_pipeline.md) pour le pas-à-pas.

## 3.5 Pour aller plus loin

- Détail page-par-page : voir le sommaire dans [00_README.md](00_README.md).
- Workflow concret pour 2 000 € : [40_workflow_type_swing_2000eur.md](40_workflow_type_swing_2000eur.md).

