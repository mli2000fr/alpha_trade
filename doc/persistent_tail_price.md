# persistent_tail_price_confirmation — 2026-08-27

Expérience **diagnostique** (aucun réentraînement, aucun changement risk/PROD).
Question : la combinaison **persistance dans une queue du ranking (N jours)** +
**confirmation du prix (ret_N)** sélectionne-t-elle davantage de vrais bons
LONG/SHORT, en conservant assez de candidats ?

Paramètres **pré-enregistrés** (non étendus) : N ∈ {2,3,4,5} ; X ∈ {0,1,2,3}%.

- A. **Oracle Extreme** : TOP10% `proba_extreme` (extreme_pct ≥ 0.90) persistant N
  jours ; LONG = persistent AND ret_N ≥ +X ; SHORT = persistent AND ret_N ≤ −X.
- B. **Global Rank** (global_rank_20, H20) : TOP10 = rank ≥ 0.90 ; BOTTOM10 =
  rank ≤ 0.10 ; persistance N jours ; 4 diagnostics (TOP10/BOTTOM10 × +X/−X)
  dont les **inversions**.

Évaluation fwd H20 (`future_return` des labels Oracle) : « bon LONG » = fwd > 0,
« bon SHORT » = fwd < 0. Base pool mean fwd = +0.007.

## Résultats (CSV : artifacts/persistent_tail_price.csv, 95 lignes)

### Oracle TOP10 — **hypothèse NON soutenue**
BASE : n=151 704, good_rate 0.503, mean_fwd +0.025.
Persistance + confirmation prix : good_rate **plat ≈ 0.502-0.503** quel que soit
(N, X). Augmenter X (3%) **dégrade** même le rendement → le gros mouvement récent
sur un titre Extreme est déjà « consommé » (mean reversion). **Pas de gain.**

### Global Rank TOP10 (LONG) — **hypothèse soutenue**
BASE : good_rate 0.521, mean_fwd +0.025.
| N | X | n | mean_fwd | good_rate |
|---|---|---|---|---|
| 5 | 3% | 2 662 | +0.061 | **0.558** |
| 3 | 3% | 3 313 | +0.058 | **0.556** |
| 4 | 3% | 2 704 | +0.062 | **0.555** |
| 5 | 2% | 3 722 | +0.051 | 0.556 |

→ Persistance TOP10 + hausse ≥ 2-3% : good_rate 0.521 → 0.556 (+3.5 pp),
mean_fwd ×2.4 (0.025 → 0.06), n ≈ 2 700-3 700 (≈ 12-15 candidats/séance, viable).

### Global Rank BOTTOM10 (SHORT) — **faible gain**
BASE : good_rate 0.512 (fwd<0), mean_fwd −0.002.
Meilleur : N=2 X=1% → good_rate 0.529, mean_fwd −0.009, n=3 571. Gain modeste.

### INVERSION TOP10 + BAISSE — **signal le plus fort**
TOP10 persistant ET ret_N ≤ −X → forward **fortement POSITIF** :
| N | X | n | mean_fwd | good_rate |
|---|---|---|---|---|
| 4 | 2% | 5 247 | +0.062 | **0.567** |
| 4 | 3% | 3 559 | +0.062 | 0.565 |
| 5 | 2% | 5 139 | +0.059 | 0.564 |
| 3 | 2% | 6 341 | +0.058 | 0.563 |

→ Un nom **persistant dans le TOP10 du ranking qui a baissé** de 2-3 % sur N jours
**remonte** (mean reversion) : c'est un signal de « buy-the-dip » sur le top rank,
meilleur que le cas naturel LONG (TOP10 + hausse).

### INVERSION BOTTOM10 + HAUSSE — **dead-cat bounce confirmé**
BOTTOM10 persistant ET ret_N ≥ X → forward faible/négatif (good_rate ~0.47-0.51,
mean_fwd < 0) : la hausse sur un bottom persistant n'est pas suivie.

## Verdict

- **Oracle : la confirmation prix ne sert à rien** (le gate Extreme est déjà un
  signal de « gros mouvement », pas de direction ; le prix ne l'améliore pas).
- **Global Rank LONG : OUI** — persistance TOP10 + confirmation hausse sélectionne
  de vrais bons longs (0.556, n viable).
- **Global Rank SHORT : faible OUI** — bottom10 + baisse améliore peu (0.529).
- **Découverte d'inversion majeure** : TOP10 persistant + baisse récente =
  rebond fiable (0.567) — à creuser avant toute décision (pas de changement PROD).
