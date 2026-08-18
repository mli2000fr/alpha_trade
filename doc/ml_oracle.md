# Spécification — Oracle Layer au-dessus du Global Model

> **Statut** : 📐 Spécification (2026-08-18) — révisée suite au retour opérateur (même jour)
> **Contexte** : analyse Oracle du run `20260817_205031_2a2836d1`
> **Objectif** : construire une **Oracle Layer** (TOP / BOTTOM) qui apprend, sur
> l'historique, dans quelles configurations le Global Model réussit ou échoue à
> identifier les vrais extrêmes cross-sectionnels.
> **Règle cardinale** : l'Oracle est un **TARGET**, jamais une **FEATURE**. B25 reste
> **intact** pendant toute la 1ʳᵉ expérimentation.
>
> **Décisions actées (retour opérateur)** :
> - Target = **brut cross-sectionnel** (top ~40/~399 du jour), **H20 seul** ;
> - Univers = `global_rank_history`, **bit-for-bit** contre `model_predictions` ;
> - Oracle TOP = **second signal** (`adjusted_score = f(global_rank_20, P_top)`), B25 intouchable ;
> - **Anti-leakage non négociable** ; α/seuils/hyperparams **gelés avant l'OOS final** ;
> - Métrique principale = **TOP capture + monotonicité** ; le **backtest (niveau 3) décide**.

---

## Sommaire

1. [Objectif](#1-objectif)
2. [Principe fondamental : Oracle = Target, jamais Feature](#2-principe-fondamental)
3. [Table Oracle historique](#3-table-oracle-historique)
4. [Univers Oracle = univers Global Model](#4-univers-oracle)
5. [B25 intouchable](#5-b25-intouchable)
6. [Architecture des deux modèles Oracle](#6-architecture-des-deux-modèles-oracle)
7. [Features des modèles Oracle](#7-features-des-modèles-oracle)
8. [Features PIT obligatoires](#8-features-pit-obligatoires)
9. [Anti-leakage des labels Oracle](#9-anti-leakage-des-labels-oracle)
10. [Pré-calcul des Oracle historiques](#10-pré-calcul-des-oracle-historiques)
11. [Walk-forward causal](#11-walk-forward-causal)
12. [Taille du dataset](#12-taille-du-dataset)
13. [Quelle cible utiliser](#13-quelle-cible-utiliser)
14. [Architecture recommandée phase 1](#14-architecture-recommandée-phase-1)
15. [Combinaison des scores](#15-combinaison-des-scores)
16. [Calibration](#16-calibration)
17. [Métriques ML obligatoires](#17-métriques-ml-obligatoires)
18. [Décile monotonicity](#18-décile-monotonicity)
19. [Métriques trading obligatoires](#19-métriques-trading-obligatoires)
20. [Métriques trading](#20-métriques-trading)
21. [Le résultat le plus important](#21-le-résultat-le-plus-important)
22. [Tester d'abord LONG uniquement](#22-tester-dabord-long-uniquement)
23. [Comparaison des architectures](#23-comparaison-des-architectures)
24. [Ne pas remplacer B25 prématurément](#24-ne-pas-remplacer-b25-prématurément)
25. [Version avancée : Residual Model](#25-version-avancée-residual-model)
26. [Version avancée : distillation / ranking](#26-version-avancée-distillation--ranking)
27. [Anti-leakage tests automatisés](#27-anti-leakage-tests-automatisés)
28. [Réutiliser les prédictions B25 historiques](#28-réutiliser-les-prédictions-b25-historiques)
29. [Dataset final du Oracle Model](#29-dataset-final-du-oracle-model)
30. [Plan d'implémentation (Étape 1 → 7)](#30-plan-dimplémentation-étape-1--7)
31. [Critère de réussite](#31-critère-de-réussite)
32. [Architecture cible finale](#32-architecture-cible-finale)
33. [Baselines « sans oracle »](#33-baselines-sans-oracle)
34. [Bilan des expériences testées (S6 → S7) — toutes NO-GO](#34-bilan-des-expériences-testées-s6--s7--toutes-no-go)

---

## 1. Objectif

Le Global Model est entraîné pour produire un **ranking cross-sectionnel** des
~400 symboles disponibles chaque jour. La cascade de production utilise ensuite :

```
global_rank_20
      ↓
TOP 10%     → candidats LONG
BOTTOM 10%  → candidats SHORT
```

L'analyse Oracle récente montre :

| | Random | B25 |
|---|---|---|
| Vrai TOP 10 % capturé | 10 % | **16.7 %** |
| Vrai BOTTOM 10 % capturé | 10 % | **8.2 %** |

Donc :
- le Global Model possède un **signal réel côté LONG** ;
- le signal SHORT est actuellement **faible voire nul** ;
- une **partie importante des vrais TOP/BOTTOM n'est pas capturée** par le ranking actuel.

**Objectif du projet** : construire une **Oracle Layer** capable d'apprendre, à partir
de l'historique, **dans quelles configurations le Global Model réussit ou échoue** à
identifier les vrais extrêmes cross-sectionnels.

> ⚠️ **L'Oracle Layer ne remplace PAS B25 dans la première expérimentation.**

```mermaid
flowchart TB
    A[GLOBAL MODEL B25] --> B[global_rank_20]
    B --> C1[ORACLE-TOP MODEL<br/>P real TOP 10%]
    B --> C2[ORACLE-BOTTOM MODEL<br/>P real BOTTOM 10%]
    C1 --> D[score combiné]
    C2 --> D
    D --> E[final ranking] --> F[TOP/BOTTOM 10%]
```

---

## 2. Principe fondamental

**L'Oracle est un TARGET, jamais une FEATURE.**

L'Oracle est calculé à partir du rendement futur réel (ex. H20) :

```
future_return_20 = adj_close[D+20] / adj_close[D] − 1
```

Puis, pour chaque date D, sur l'univers réellement disponible :
`TOP 10% = 1` / `BOTTOM 10% = 1`.

Ces informations ne sont disponibles **qu'après réalisation du futur** :

```
D
│
├── Features disponibles à D
├── B25 prediction à D
│   >>> aucune information Oracle disponible
└────────────────────────────→ D+20
                                 │
                                 └── Oracle(D) devient connu
```

Définitions :
```
oracle_exit_date      = D + H
oracle_available_date = oracle_exit_date + 1 trading day
```

> La colonne **`oracle_available_date`** doit être stockée explicitement.

---

## 3. Table Oracle historique

Créer une table dédiée, par exemple **`global_oracle_labels`** (ou nom équivalent).

**Minimum recommandé** :

| Colonne | Description |
|---|---|
| `prediction_date` | Date D de la prédiction |
| `symbol` | Symbole |
| `id_batch` | Batch du Global Model |
| `horizon` | H (ex. 20) |
| `future_return` | Rendement futur réalisé |
| `oracle_pct_rank` | Percentile cross-sectionnel |
| `oracle_decile` | Décile (1–10) |
| `oracle_top10` | 1 si TOP 10 % |
| `oracle_bottom10` | 1 si BOTTOM 10 % |
| `oracle_exit_date` | D + H |
| `oracle_available_date` | exit + 1 jour ouvrés |

**Idéalement**, conserver aussi les sorties du Global Model au moment de la prédiction :
`global_rank_20`, `global_score_20`, `global_rank_10`, …

**Exemple** :

| prediction_date | symbol | id_batch | horizon | future_return | pct_rank | décile | top10 | bottom10 | exit_date | available_date |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022-01-03 | AAPL | batch_123456 | H20 | +0.143 | 0.96 | 10 | 1 | 0 | 2022-01-31 | 2022-02-01 |

---

## 4. Univers Oracle

**Impératif : le même univers que le Global Model.**

- L'Oracle **ne doit PAS** être calculé sur un univers différent.
- Utiliser les **~399 symboles/jour** réellement présents dans `model_predictions` et
  disponibles pour le Global Model à cette date.
- `Global universe(D) = Oracle universe(D)`.
- Le TOP 10 % = les 10 % meilleurs rendements futurs **parmi les titres que le Global
  Model pouvait réellement sélectionner ce jour-là**.
- ⛔ **Jamais** d'univers survivorship-biased ou d'un autre pool.

---

## 5. B25 intouchable

B25 doit rester **strictement identique**. Ne pas modifier :
- ses features ;
- son target ;
- son entraînement ;
- ses hyperparamètres ;
- son ranking ;
- son modèle ;
- son pipeline de production.

On ajoute **uniquement** :

```
B25
 +
Oracle Layer
```

→ pour répondre objectivement : *« Est-ce que l'Oracle Layer apporte réellement quelque
chose ? »*

---

## 6. Architecture des deux modèles Oracle

Construire **deux modèles indépendants** (pas de symétrie forcée).

### Oracle TOP Model
```
target : oracle_top10 = 1  si rendement futur ∈ TOP 10% cross-sectionnel du jour
                        0  sinon
objectif : P(real TOP 10% | information disponible à D)
```

### Oracle BOTTOM Model
```
target : oracle_bottom10 = 1  si rendement futur ∈ BOTTOM 10%
                          0  sinon
objectif : P(real BOTTOM 10% | information disponible à D)
```

> Les résultats actuels (TOP 16.7 % vs BOTTOM 8.2 %) montrent que les deux problèmes
> ont des patterns très différents → **entraînés séparément**.

---

## 7. Features des modèles Oracle

Trois catégories.

### A. Features du Global Model (disponibles à D)
`momentum`, `returns`, `volatilité`, `volume`, `relative strength`, `fundamentals PIT`,
`secteur`, `market regime`, etc. — **ne pas recréer artificiellement une information future**.

### B. Informations produites par le Global Model
Le Oracle Model peut recevoir `global_rank_20`, `global_score_20` (+ autres outputs).
Exemple : quand B25 donne 0.93, dans quelles configurations ce titre devient
réellement TOP 10 % ? → **seconde couche de décision**.

### C. Features spécifiques Oracle (orientées extrêmes)
- accélération du momentum ;
- momentum court vs long ;
- variation de volatilité ;
- volume expansion ;
- relative strength ;
- distance aux highs/lows ;
- drawdown récent ;
- dispersion cross-sectionnelle ;
- force/faiblesse sectorielle ;
- interactions momentum × volume / momentum × volatilité.

> Ne pas ajouter aveuglément des features. **Faire des ablations** — la question
> scientifique : *« B25 rate-t-il des gagnants parce que son **objectif** est mauvais,
> ou parce que ses **features** n'ont pas l'information ? »*
> - `O0` = features **exactes** de B25, **sans** `global_rank` → isole l'effet de l'objectif ;
> - `O1` = O0 + `global_rank_20` + features Oracle spécialisées (catégorie C) ;
> - `O2` = **seulement** certaines familles : momentum / volume / volatility / market
>   regime (sans le set complet B25) → teste si un set allégé suffit.

---

## 8. Features PIT obligatoires

Toutes les features doivent respecter :
```
feature timestamp <= prediction_date D
```

⛔ **Jamais** comme feature :
```
future_return · future_volatility · oracle_rank · oracle_decile ·
future_price · future_volume
```
Ces informations servent **uniquement** à créer les **targets historiques**.

---

## 9. Anti-leakage des labels Oracle

Exemple — `prediction_date = 2022-01-03`, H20 → Oracle connu le **2022-02-01**
(`oracle_available_date`).

- ❌ Prédiction le 2022-01-15 avec Oracle(2022-01-03) : **interdite** (pas encore disponible).
- ✅ Prédiction le 2022-02-02 : **autorisée**.

**Règle absolue d'entraînement :**
```sql
WHERE oracle_available_date <= training_cutoff_date
```

---

## 10. Pré-calcul des Oracle historiques

Il est **recommandé** de pré-calculer les Oracle historiques (ex. 2016 → 2025) pour
chaque `date × symbol × horizon`, puis stocker `oracle_available_date`.

- Connaître aujourd'hui l'Oracle de 2018 **n'est pas du leakage**.
- Le leakage n'existe que si une **simulation du passé** utilise une information non
  disponible à cette date.
- Oracle 2018 (available 2018 + 20 j) → utilisable pour apprendre une prédiction de
  **2019**, jamais pour modifier rétroactivement une prédiction de 2018.

---

## 11. Walk-forward causal

Le pipeline doit être **strictement temporel** :

```
TRAIN 2016 → 2020  (Oracle labels disponibles avant cutoff)
        ↓
Train Oracle-TOP / Oracle-BOTTOM
        ↓
VALIDATION 2021

2016 → 2021 (nouveaux Oracle disponibles)
        ↓
retrain Oracle models
        ↓
VALIDATION 2022
… (etc.)
```

> Le modèle de 2021 ne doit **jamais** voir Oracle 2021 si cet Oracle n'était pas
> encore disponible au moment de la prédiction 2021.

---

## 12. Taille du dataset

Ne pas sous-estimer le volume : chaque journée contient **~400 symboles**.

```
1 année ≈ 250 × 400 ≈ 100 000 observations
```

Le délai H20 **ne limite pas le nombre d'observations** ; il limite uniquement leur
**date de disponibilité**.

---

## 13. Quelle cible utiliser

**Première version recommandée** : TOP = classification, BOTTOM = classification.

Le target est **cross-sectionnel à l'intérieur de l'univers du jour** :
`oracle_top10 = 1` si le titre fait partie des **~40 meilleurs (~10 % de ~399)**
titres de ce jour-là. **Jamais** un seuil de rendement absolu (« > +5 % ») : la
question réelle est *« ce titre fait-il partie des meilleurs du jour ? »*, pas
*« ce titre gagne-t-il plus de X % ? »*.

Conserver aussi `oracle_pct_rank` et `oracle_decile` **pour les analyses**.

**Deuxième expérience** : target continu = `oracle_rank − global_rank`
(le *Residual Model*) — **pas la première implémentation à privilégier**.

> **Horizon canonique** : **H20 uniquement** pour la 1ʳᵉ expérience (H10 viendra
> ensuite si H20 valide). Le target de la 1ʳᵉ expérience est **brut** (rendement
> futur non neutralisé) ; la variante **neutralisée** (vol-scaled / sector / factor)
> sera testée en ablation après.

---

## 14. Architecture recommandée phase 1

```mermaid
flowchart TB
    A[FEATURES PIT] --> B[B25 GLOBAL] --> C[global_rank_20]
    C --> D1[ORACLE TOP MODEL<br/>target = top10]
    C --> D2[ORACLE BOTTOM MODEL<br/>target = bottom10]
    D1 --> E1[P_top]
    D2 --> E2[P_bottom]
    E1 --> F[COMBINATION LAYER]
    E2 --> F
    F --> G[final scores] --> H[TOP/BOTTOM 10%]
```

> **Précision (retour opérateur)** : l'Oracle TOP **ne remplace pas B25** — c'est un
> **second signal spécialisé**. On calcule `adjusted_score = f(global_rank_20, P_top)`,
> puis on applique le TOP 10 % sur `adjusted_score`. B25 reste intouchable.

---

## 15. Combinaison des scores

Ne pas commencer avec une formule compliquée. Tester d'abord des combinaisons simples.

**Baseline**
```
long_score  = global_rank_20
short_score = 1 − global_rank_20
```

**Variante 1**
```
long_score  = global_rank_20 × P_top
short_score = (1 − global_rank_20) × P_bottom
```

**Variante 2** (pondérée)
```
long_score  = α × global_rank_20 + (1 − α) × P_top
short_score = α × (1 − global_rank_20) + (1 − α) × P_bottom
```

> Tester plusieurs `α` **uniquement via calibration WF**, jamais sur l'OOS final.

---

## 16. Calibration

`P_top` / `P_bottom` ne doivent pas être supposées parfaitement calibrées. Tester :
- isotonic calibration ;
- Platt / logistic calibration ;
- ranking percentile plutôt que probabilité brute.

Garder une **version sans calibration comme baseline**.

---

## 17. Métriques ML obligatoires

Le 1ᵉʳ objectif n'est pas uniquement le P&L.

**Capture Oracle (TOP)**
```
Random        10%
B25          16.7%
Oracle layer   ?
```
Objectif expérimental : **16.7 % → 20 %+** (sans garantir 20-25 %).

**Bottom capture**
```
Random        10%
B25           8.2%
Oracle layer   ?
```
Objectif : **≥ 10 %**, puis éventuellement mieux.

---

## 18. Décile monotonicity

Métrique essentielle. Pour chaque modèle, calculer par décile `D1…D10` :
```
mean future return
median future return
```

On veut : `D1 < D2 < … < D10` (ou au minimum une relation **beaucoup plus monotone
que B25**). L'objectif réel n'est **pas** de « corriger une forme en U » (la courbe
rendement/décile est déjà monotone — cf. audit §19) mais d'obtenir :
`score élevé → probabilité plus élevée d'être dans le vrai TOP 10 %`.
La métrique principale reste **Oracle Top-10 Capture + monotonicité par déciles**.

---

## 19. Métriques trading obligatoires

Une amélioration de capture **ne suffit pas**. Évaluer avec le **moteur de backtest
réel**, même configuration que le candidat production :
- H20 cascade · H20 risk · stop 3.5×ATR · TP min(4×ATR, 13 %) · market entry · P14 ·
  m8 · coûts réels · overlays production.

Comparer **B25** vs **B25 + Oracle Layer** sur **exactement les mêmes dates**.

**Baselines « sans oracle » de référence** (déjà disponibles) :
- `20260817_211221_da7eb061` — backtest complet **2026** ;
- `20260817_205031_2a2836d1` — backtest complet **2025-2026**.

---

## 20. Métriques trading

Au minimum :
`rendement · PF · Sharpe · Sortino · max DD · win rate · trades · holding moyen ·
turnover · LONG P&L · SHORT P&L · contribution TOP/BOTTOM · frais · slippage ·
taux de rejet · exposition moyenne · gross exposure`.

---

## 21. Le résultat le plus important

On veut **éviter** :
```
Oracle capture : 16.7% → 25%   mais   PF : 1.76 → 1.20   ⇒  ÉCHEC trading
```

**Critère final** :
> **Oracle capture améliorée + ranking plus monotone + P&L OOS amélioré.**

---

## 22. Tester d'abord LONG uniquement

Vu les résultats (TOP 16.7 % / BOTTOM 8.2 %) :
1. Première expérience : **B25 + Oracle TOP** — sans toucher au SHORT.
2. Ensuite seulement : **B25 + Oracle TOP + Oracle BOTTOM**.

> **Asymétrie autorisée** : il est parfaitement possible que la meilleure architecture
> finale soit `B25 → Oracle TOP (LONG) + B25 original (SHORT)`, sans Oracle BOTTOM.
> **Le backtest décide.**

---

## 23. Comparaison des architectures

À terme, tester trois architectures.

**A — B25 actuel (baseline)**
```
B25 → rank → cascade
```

**B — B25 + Oracle (recommandée initialement)**
```
B25 → Oracle TOP/BOTTOM → adjusted rank → cascade
```

**C — Oracle models seuls (expérience secondaire)**
```
features → Oracle TOP/BOTTOM → cascade
```
→ permet de savoir si le Global Model est réellement indispensable.

---

## 24. Ne pas remplacer B25 prématurément

Même si les Oracle Models seuls fonctionnent mieux sur une période, **ne pas remplacer
B25 immédiatement**. Vérifier d'abord **2025**, **2026**, puis idéalement **plusieurs
fenêtres OOS**. Démontrer que l'amélioration est **robuste**.

---

## 25. Version avancée : Residual Model

Une fois la classification TOP/BOTTOM validée, tester :
```
residual = oracle_pct_rank − global_rank_20
```
Exemple : B25 = 0.62, Oracle = 0.94 → residual = **+0.32**.

Le modèle apprend :
```
features PIT + global_rank_20  →  predicted residual
adjusted_rank = global_rank_20 + predicted_residual
```
> Plus élégant si la classification Oracle fonctionne — **ne pas commencer par là**.

---

## 26. Version avancée : distillation / ranking

Si les expériences précédentes sont positives, tester ensuite :
`LambdaRank · RankNet · ListNet · pairwise ranking · NDCG-oriented objective`.

L'objectif devient : apprendre un ranking qui ressemble davantage au ranking Oracle.
**Après validation de l'idée fondamentale.**

---

## 27. Anti-leakage tests automatisés

| Test | Vérification |
|---|---|
| **Test 1** | `oracle_available_date > prediction_date` pour toutes les observations |
| **Test 2** | Modèle entraîné au cutoff D → `max(oracle_available_date) <= D` |
| **Test 3** | Aucune feature issue de D+1 ou plus |
| **Test 4** | `oracle_rank`, `oracle_decile`, `future_return` jamais en feature |
| **Test 5** | La production ne lit jamais une ligne Oracle avec `oracle_available_date > today` |

---

## 28. Réutiliser les prédictions B25 historiques

Pour l'apprentissage du second niveau, conserver les **sorties historiques du Global
Model telles qu'elles auraient été produites à l'époque** :
```
prediction_date · symbol · global_rank_20 · global_score
```

⛔ **Ne pas recalculer aujourd'hui un B25 différent** et prétendre que c'était le score
historique. Le second modèle doit apprendre les **erreurs réelles** du Global Model
historique.

---

## 29. Dataset final du Oracle Model

Chaque ligne contient conceptuellement :

```
prediction_date
symbol

# Global outputs
global_rank_20 · global_score_20 · global_rank_10 …

# Features PIT
momentum_5 · momentum_20 · volatility_20 · volume_ratio ·
relative_strength · sector_strength …

# Oracle targets
oracle_pct_rank · oracle_decile · oracle_top10 · oracle_bottom10

# Availability
oracle_exit_date · oracle_available_date
```

Avec la règle : `training_cutoff >= oracle_available_date`.

---

## 30. Plan d'implémentation (Étape 1 → 7)

Ne pas coder directement toute la version finale. Étapes séquentielles.

- [ ] **Étape 1 — Oracle dataset** : créer `global_oracle_labels` **H20**. Vérifier :
      univers **bit-for-bit** identique au pool consommé par la cascade
      (`global_rank_history` ↔ `model_predictions`) ; top/bottom 10 % corrects ;
      dates correctes ; `oracle_available_date` correcte.
- [ ] **Étape 2 — Audit Oracle** : reproduire exactement B25 TOP capture (16.7 %),
      BOTTOM capture (8.2 %), déciles, monotonicité → vérifier que la nouvelle
      infrastructure reproduit les résultats existants (baselines « sans oracle »
      `20260817_211221_da7eb061` et `20260817_205031_2a2836d1`).
- [ ] **Étape 3 — Oracle TOP Model (second signal)** : premier modèle simple,
      `features B25 + global_rank_20`, target `oracle_top10` ; ablations O0/O1/O2.
      Il **ne remplace pas** B25.
- [ ] **Étape 4 — Walk-forward strict** : respecter `oracle_available_date <=
      training_cutoff` (anti-leakage **non négociable**).
- [ ] **Étape 5 — Combinaison** : `adjusted_score = f(global_rank_20, P_top)` ;
      tester `global_rank` contre `global_rank × P_top` ; α/calibration gelés avant OOS.
- [ ] **Étape 6 — Backtest complet** : même moteur, mêmes coûts, mêmes paramètres,
      hiérarchie 3 niveaux (ML → ranking → trading ; le trading décide).
- [ ] **Étape 7 — seulement si positif** : ajouter `Oracle BOTTOM`, **sans symétrie
      forcée** (asymétrie possible : TOP pour LONG, B25 pour SHORT).

---

## 31. Critère de réussite

L'expérience n'est intéressante que si elle améliore **plusieurs dimensions simultanément** :

| Dimension | Exigence |
|---|---|
| **ML** : TOP capture | ↑ |
| **ML** : décile monotonicité | ↑ |
| **Trading** : PF | ↑ |
| **Trading** : Sharpe | ↑ |
| **Trading** : DD | stable ou ↓ |
| **Trading** : P&L | ↑ |
| **Robustesse** : 2025 OOS / 2026 OOS / stress coûts / bootstrap | validés |

> **Et surtout** : aucune amélioration ne doit dépendre d'un réglage effectué sur
> l'OOS final.

**Hiérarchie du test (le niveau 3 décide)** :
1. **Niveau 1 — ML** : TOP capture ↑ ;
2. **Niveau 2 — Ranking** : monotonicité déciles ↑ ;
3. **Niveau 3 — Trading** : PF / Sharpe / P&L ↑, DD stable/↓ — **c'est ce niveau qui décide**.

---

## 32. Architecture cible finale

Si tout fonctionne, le système pourrait devenir :

```mermaid
flowchart TB
    A[DATA PIT] --> B[GLOBAL MODEL B25] --> C[global_rank_20]
    C --> D1[ORACLE TOP MODEL<br/>P real TOP 10%]
    C --> D2[ORACLE BOTTOM MODEL<br/>P real BOTTOM 10%]
    D1 --> E[CALIBRATION LAYER]
    D2 --> E
    E --> F[ADJUSTED RANK] --> G[TOP/BOTTOM 10%]
    G --> H[P14 + m8] --> I[H20 RISK] --> J[TRADE]
```

### La philosophie du système

- **Global Model** répond : *« Comment classer les ~400 titres ? »*
- **Oracle-TOP** répond : *« Parmi ces titres, lesquels ressemblent historiquement aux
  vrais TOP 10 % ? »*
- **Oracle-BOTTOM** répond : *« Parmi ces titres, lesquels ressemblent historiquement
  aux vrais BOTTOM 10 % ? »*
- **Couche finale** répond : *« Comment combiner ces informations pour obtenir le
  meilleur ranking tradable ? »*

> **B25 reste intact pendant toute la première expérimentation.** Si Oracle-TOP/BOTTOM
> apporte réellement de l'alpha, on pourra ensuite envisager une intégration plus
> profonde dans le Global Model — **mais seulement après avoir prouvé que la couche
> séparée fonctionne en OOS**.

---

## 33. Baselines « sans oracle » (références de comparaison)

| Run | Période |
|---|---|
| `20260817_211221_da7eb061` | 2026 |
| `20260817_205031_2a2836d1` | 2025-2026 |

> Ces backtests complets **sans oracle** servent de référence pour mesurer l'apport
> de l'Oracle Layer (Étape 6) et de golden pour l'audit (Étape 2).


Note:
fillabck label : python.exe -u -m modelFactory.oracle.build_labels --batch-id model-factory-20260811223551-ef2cd0

S6 Le score cascade = rank × proba per-symbol. En mode oracle, rank = P_top et proba per-symbol = global_rank (run synthétique) → le score final est P_top × global_rank (= « variante 1 » de S5), pas P_top pur. C'est l'architecture B de la spec (§23), cohérente. S5 avait montré que P_top pur (23.2 %) devance légèrement P_top × rank (22.2 %) — nuance à garder en tête dans l'interprétation.

---

# 34. Bilan des expériences testées (S6 → S7) — toutes NO-GO

> **Statut** : investigation **clôturée** (2026-08-18). L'Oracle Layer ne peut pas
> améliorer la sélection B25 à partir des données disponibles. **B25 reste intact**
> et est le champion de production. Cette section documente, pour chaque expérience
> testée, l'hypothèse, le résultat, la raison de l'échec et la **preuve** chiffrée.

## 34.1 Tableau de synthèse

| # | Expérience | Hypothèse | Résultat | Verdict | Preuve |
|---|---|---|---|---|---|
| S6 | Oracle TOP (ranking) | P(top10) remplace le rang B25 | capture 22.5 % vs 18.5 % (ML ✅) mais trading 27.81 % vs 29.52 % | **NO-GO** | §34.2 |
| S6.1-B | Oracle = filtre τ=0.80 | B25 sélectionne, Oracle filtre | 26.61 %, PF 1.42, 303 trades | **NO-GO** | §34.3 |
| S6.1-C | pool B25 20 % → Oracle top 10 % | reranking local | 25.60 %, PF 1.38 | **NO-GO** | §34.3 |
| S6.1-D | rerank pool B25 identique | même exposition | **no-op** (score de cascade non consommé) | **NO-GO** | §34.3 |
| S6.1bis | Oracle BOTTOM | P(bottom10) sépare les extrêmes | corr(Ptop,Pbottom)=0.83, déciles identiques | **NO-GO** | §34.4 |
| S6.2 | Hard negatives 2/4/8× | sur-pondérer les faux top→bottom | corr 0.83→0.71 mais capture 21.4→16.7 %, contam ~inchangée | **NO-GO** | §34.5 |
| S6.4 | Error severity (SEV/REG) | cible distance au top | SEV sans effet ; REG capture 11.7 % ≈ aléatoire | **NO-GO** | §34.6 |
| S6.5 | Features directionnelles signées | momentum/trend/RS/volume signé | corr_ret ≈ 0 pour les 22 features | **NO-GO** | §34.7 |
| S6.6-A | Fondamentaux + sentiment | surprise/growth/sentiment | corr_ret ≈ 0 ; AUC détection ≈ 0.5 | **NO-GO** | §34.8 |
| S6.6-B | Catastrophic TOP Detector | valorisation → faux TOP | AUC 0.49–0.55 ; pe_ratio « AUC 0.70 » = faux positif | **NO-GO** | §34.9 |
| S6.6-C | Validation confound-free PE | PE vs random même univers | pe_ratio dispo sur 1 % des candidats ; PE = bruit | **NO-GO** | §34.10 |
| S7 | Per-symbol directional veto | hétérogénéité des 400 symboles | acc champion val 0.59 / WF 0.50 ; persistance corr ≈ 0 | **NO-GO** | §34.11 |

## 34.2 S6 — Oracle TOP (rank_mode=oracle)

- **Hypothèse** : P(vrai top10 H20) comme 2ᵉ signal remplace le rang B25 dans la cascade.
- **Résultat ML (OOS WF 2022-2026)** :
  - Niveau 1 — TOP capture : Oracle **22.5 %** vs B25 `global_rank_20` **18.5 %** (aléatoire 10 %) ✅
  - Niveau 2 — monotonicité déciles : Oracle **0.868** vs B25 0.832 ✅
  - Niveau 3 — backtest 2025-2026 : **27.81 %** (Sharpe 1.82, PF 1.44, win 43.4 %, 316 trades) vs B25 **29.52 %** (2.08, 1.52, 48.9 %, 237 trades) ❌
- **Raison** : l'Oracle **élargit** la sélection (316 vs 237 trades) avec des trades ajoutés de mauvaise qualité (PF 1.16, win 39 %, dont 50 shorts → −$23). Le score `P_top × global_rank` dilue l'edge B25.
- **Preuve** (décomposition P&L par groupe, `exit_closed`) :

| Groupe | n | win % | PnL | PF |
|---|---|---|---|---|
| B25 ∩ Oracle (accord) | 75 | 57.3 % | +$741 | **3.22** |
| B25 rejeté par Oracle | 162 | 45.1 % | +$424 | 1.22 |
| Oracle ajouté | 241 | 39.0 % | +$334 | 1.16 |

## 34.3 S6.1 — Variantes de combinaison (B / C / D)

Backtests 2025-2026, B25 intact, même moteur :

| Variante | Rendement | Sharpe | PF | Win | Trades | DD |
|---|---|---|---|---|---|---|
| A — B25 (baseline) | **29.52 %** | **2.08** | **1.52** | 48.9 % | 237 | 10.67 % |
| S6 — oracle ranking | 27.81 % | 1.82 | 1.44 | 43.4 % | 316 | 5.57 % |
| B — filter τ=0.80 | 26.61 % | 1.77 | 1.42 | 42.2 % | 303 | 8.70 % |
| C — pool 20 %→10 % | 25.60 % | 1.65 | 1.38 | 43.3 % | 323 | 5.40 % |
| D — rerank pool identique | 29.52 % (no-op) | 2.08 | 1.52 | 48.9 % | 237 | 10.67 % |

- **B (filtre)** : retirer des candidats B25 libère la capacité (`max_positions=8`) qui est
  **re-remplie par de moins bons titres** → 303 trades, turnover 30.8×, win 42 %.
- **C (pool)** : même mécanisme, 323 trades.
- **D (rerank)** : **no-op** — la cascade ne fait que **filtrer** ; `cascade_score` n'est
  jamais consommé en aval. L'ordre d'entrée est recalculé par `build_rankings()` qui trie
  uniquement par `p_side` B25 (le « ML est la seule autorité »). → D/E exigeraient d'injecter
  le score Oracle dans `build_rankings()`, pas dans la cascade.

## 34.4 Oracle BOTTOM (P(bottom10))

- **Résultat** : capture BOTTOM 20.1 % vs baseline 15.0 %, mais **monotonicité +0.891**
  (positive alors qu'un modèle bottom devrait être négatif) et **corr(Ptop, Pbottom) = 0.83**
  (rang intra-date).
- **Déciles de rendement identiques** entre P(top) et P(bottom) : D10 = +2.16 % (top) et
  +1.82 % (bottom) → **les deux modèles apprennent la même chose**.
- **Raison** : le modèle apprend « mouvement extrême » (amplitude), pas le signe. Les features
  ne permettent pas de distinguer top et bottom.

## 34.5 S6.2 — Hard negatives (conditionnels, poids 2/4/8×)

- Hard negatives = {vrai bottom10} ∩ {P(top) in-sample top 10 %}, sur-pondérés au train.
- Résultat (valid 2025-2026) :

| Variante | corr(Ptop,Pbot) | capture TOP | contamination | FP→bottom |
|---|---|---|---|---|
| catboost_H0 | 0.906 | 21.7 % | 16.6 % | 20.9 % |
| lightgbm_H0 | 0.825 | 21.4 % | 17.1 % | 21.5 % |
| lightgbm_HN8× | 0.713 | 16.7 % | 16.0 % | 19.0 % |

- **Raison** : les hard negatives **décorellent** (0.83→0.71) mais au prix de −5 pts de
  capture TOP pour ~1 pt de contamination en moins → **mauvais compromis**. La re-pondération
  ne suffit pas : le goulot est en amont (features).

## 34.6 S6.4 — Error severity (cible distance au top)

- **SEV** (binaire pondéré par `(0.90−r)²`) : quasi aucun effet (contamination <10 % : 16.4→16.1).
- **REG** (régression sur `oracle_pct_rank`) : capture 21.7→**11.7 %** (≈ aléatoire),
  `|corr|` magnitude → 0.00 → le modèle régressé ne trouve aucune information.
- **Raison** : l'objectif n'est PAS le problème ; les features n'ont aucune direction.

## 34.7 S6.5 — Features directionnelles signées (22 features)

- ret_1..120j, close/SMA−1, pente SMA, croisements, force relative vs SPY, volume directionnel,
  breakout/breakdown.
- **Résultat** : `corr_ret ≈ 0` pour TOUTES (|corr| < 0.02) ; ex. `sma50_above_sma200` = +0.010,
  `ret_10d` = −0.020. Le meilleur signal reste l'**amplitude** (`corr_abs ≈ 0.28` pour la volatilité).
- **Raison** : le momentum/tendance/RS ne prédit pas le rendement H20 cross-sectionnel.

## 34.8 S6.6-A — Fondamentaux + sentiment

- `eps_surprise` / `rev_surprise` (PIT), `eps_growth_yoy`, `forward_pe`, `peg_ratio`, sentiment.
- **Résultat** : `corr_ret ≈ 0` partout ; AUC de détection des catastrophes ≈ 0.5
  (`eps_surprise` 0.49, sentiment 0.50). Seuls `pe_ratio`/`ev_to_ebitda` semblent utiles (voir 34.10).

## 34.9 S6.6-B — Catastrophic TOP Detector (WF)

- Cible `cat10` (Oracle < 10 %) / `cat20` (< 20 %) parmi les B25 TOP, WF 5 folds.
- **Résultat** : CatBoost AUC 0.537–0.553, LightGBM 0.486–0.546 (cat10 : 0.55 ; cat20 : ~0.5).
  Rejeter 30 % ne réduit cat10 que de 14.0 → 12.7 %.
- **Raison** : les features de valorisation/croissance **diluent** le peu de signal ; le modèle
  ML est pire que `pe_ratio` seul (AUC 0.70) — ce qui s'est révélé être un artefact (34.10).

## 34.10 S6.6-C — Validation confound-free de PE (décisif)

- Sur le **même sous-ensemble** (candidats B25 TOP avec `pe_ratio`) : seulement **241 / 23 215
  candidats** (≈ **1 %**). L'« AUC 0.70 » de PE était un **artefact d'éparsité**.
- PE vs RANDOM sur le même univers : ratio catastrophes évitées/TOP sacrifiés **dans le bruit**
  (PE 0.86–1.29 vs random 0.59–0.67).
- **Cause** : `stock_fundamentals_daily` éparse (~47 lignes/symbole/10 ans) ; sentiment riche
  mais AUC 0.50 ; surprise SEC AUC 0.49.
- **Leçon** : un AUC calculé sur un sous-ensemble éparse est non représentatif. Validation
  « même sous-ensemble + baseline random » obligatoire avant de conclure.

## 34.11 S7 — Per-symbol directional veto

- **Hypothèse** : certains des 393 modèles per-symbol ont une vraie capacité directionnelle.
- **Résultat** (champion par symbole, batch f62322) :

| Split | Acc directionnelle moy. | > 0.52 | > 0.60 |
|---|---|---|---|
| val | 0.593 | 90 % | 39 % |
| test | 0.498 | 39 % | 8 % |
| **WF (OOS)** | **0.504** | **35 %** | **6 %** |

- **Persistance ≈ nulle** : corr(val→test) = −0.05, corr(val→WF) = 0.07, corr(test→WF) = 0.10.
- **Raison** : **multiple testing** (400 symboles × 3 modèles × 5 horizons ≈ 6 000 combinaisons)
  → des « champions » excellents sur validation par hasard, qui ne généralisent pas.
- **Conséquence** : S7.3 (génération des prédictions per-symbol) non lancé — pré-requis absent.

## 34.12 Diagnostic des erreurs (FP/FN) — pourquoi l'Oracle se trompe

- **Faux positifs** (prédit top, pas vrai top) : distribution **bimodale** — ~22 % dans le
  **vrai bottom 0–10 %** + ~13 % quasi-top (80–90 %). Le modèle confond les futurs losers
  avec les futurs gagnants.
- **Faux négatifs** (vrai top raté) : concentrés en 70–90 % du rang prédit (20 %) → quasi-ratés
  propres. L'erreur est **asymétrique** : le modèle détecte l'**amplitude**, pas la **direction**.

## 34.13 Conclusion finale

> **Les données disponibles (techniques, fondamentales, sentiment, per-symbol) ne contiennent
> pas assez d'information directionnelle H20 cross-sectionnelle.** Aucune transformation
> d'objectif, d'algo (LightGBM/CatBoost), de pondération ou d'architecture ne peut créer une
> direction qui n'existe pas dans les features.

- **B25 reste le champion** : 29.52 %, Sharpe 2.08, PF 1.52, 237 trades, DD 10.67 %.
- **L'edge de B25 vient du moteur risque/exécution, pas de la sélection** : décomposition du
  P&L → tout le profit vient des **take_profit** (+$3 212, 32 % des sorties) ; les
  **trailing_stop** (68 %) sont un drag (−$2 058). L'asymétrie TP 12 % / trailing 7 % est le
  vrai moteur (voir §34.14).
- Pour un jour : **nouvelles données externes** (consensus analyste réel, révisions, flux
  d'initiés) — pas les données actuelles.

## 34.14 Point 8 — Décomposition du P&L de B25 (edge = exécution)

| Sortie | n | Win | PnL | Retour moyen |
|---|---|---|---|---|
| take_profit | 76 | 100 % | **+$3 212** | +12.5 % |
| trailing_stop | 160 | 24.4 % | **−$2 058** | −3.5 % |
| time_stop | 1 | 100 % | +$12 | +3.5 % |

- Edge LONG (PF 1.85, +$765) > SHORT (PF 1.29, +$400).
- Durée 5–20 j = le cœur du profit (PF ~1.8) ; 0–5 j = perdant (PF 0.70).
- **Leviers** (sans toucher B25) : taux de capture du TP (`tp-atr-multiple`, `tp-max-pct`),
  gestion du trailing (activation/largeur), durée.

---

## Fichiers / modules des expériences (trace)

- `modelFactory/oracle/` : `config.py`, `leakage.py`, `build_labels.py`, `audit.py`,
  `dataset.py`, `train.py` (LightGBM + CatBoost), `walk_forward.py`, `combine.py`,
  `hard_negatives.py`, `feature_diagnostic.py`, `directional_features.py`,
  `fundamental_diagnostic.py`, `catastrophic_detector.py`, `confound_validation.py`.
- `modelFactory/predictor.py` : modes cascade `oracle` / `oracle_filter` / `oracle_rerank` / `oracle_pool`.
- Artifacts : `artifacts/models/oracle/*_report.json`.
- Mémoire projet : `/memories/repo/oracle_s6_backtest_2026-08-18.md`,
  `/memories/repo/oracle_s62_hard_negatives_2026-08-18.md`.