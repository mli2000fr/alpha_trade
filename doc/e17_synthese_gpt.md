# Synthèse des tests — Gate Extreme vs B25 & ablation du rôle per-symbol (E16→E17)

**Contexte** : alpha-trade, backtest production-parity, preset `capital_2001_5000`, capital initial **4 000 $**,
période **2025-01-02 → 2026-05-29**, moteur CLI production complet (preset + risk + sizing + coûts canoniques).
Modèle per-symbol = **B25** (batch `model-factory-20260811223551-ef2cd0`). Oracle O0 OOS walk-forward 2025/2026.

---

## 1. Question posée

> Est-ce que retirer complètement le modèle **per-symbol B25** de la branche **Gate Extreme** (Oracle O0)
> conserve ou améliore la robustesse du **Gate Extreme m24** ?

Le per-symbol B25 intervient à 2 endroits dans le pipeline prod :
1. **VETO** : `long_prob > min_prob (0.55)` — rejette un candidat du top 20 %.
2. **RANG** : `replay_signals` classe par `proba_long` (= long_prob per-symbol) → c'est **lui** qui décide
   qui entre dans `max_positions` (pas `cascade_score`, inutilisé en aval).

## 2. Variantes testées (flag `--extreme-gate-per-symbol`)

| Variante | VETO `long_prob>0.55` | RANG / priorité |
|---|---|---|
| **A `filter`** (actuel) | ✅ oui | `long_prob` per-symbol |
| **B `no_filter`** | ❌ non | `long_prob` per-symbol |
| **C `bypass`** (Oracle pur) | ❌ non | **percentile Oracle O0** |

⚠️ **Bug corrigé en cours de route** : en A/B, un per-symbol B25 prédit "short" fuyait en **short**
(branche censée être LONG-only). 68 shorts parasites sur B. Correctif : forcer `predicted_side="long"`
+ `proba_short=0` pour tous les symboles retenus du gate Extreme (toutes variantes). Run B relancé propre.

## 3. Résultats production (preset 2001_5000, 4 000 $)

| Run | Return | Final $ | Sharpe | DD | PF | Trades (L/S) |
|---|---|---|---|---|---|---|
| **B25 L+S** | +69.1% | 6 763 $ | 1.12 | -29.0% | 1.25 | 335 (163/172) |
| B25 long-only | -48.7% ⚠️ | 2 052 $ | -0.22 | -61.5% | 1.39* | 447 (447/0) |
| **EXT A `filter`** | **+146.1%** | **9 846 $** | **1.47** | -34.2% | 1.29 | 499 (499/0) |
| EXT B `no_filter` (contaminé 68 shorts) | +39.1% | 5 565 $ | 0.75 | -29.6% | 1.10 | 486 (418/68) |
| EXT B2 `no_filter` propre | 🔄 en cours | — | — | — | — | (attendu : 0 short) |
| EXT C `bypass` (Oracle pur) | +62.3% | 6 491 $ | 0.96 | -31.1% | 1.16 | 537 (537/0) |

*B25 long-only : PF 1.39 incohérent avec return négatif → mark-to-market positions ouvertes / artefact `--no-shorts`, à ne pas utiliser comme référence.*

## 4. Résultats recherche (E17, m24, equal-weight 100 k, mêmes seeds/périodes)

### 4.1 Volet déterministe (rang naturel = ce que fait la prod)

| Variante | Trades | Return | PF | DD |
|---|---|---|---|---|
| A | 1034 | +65.0% | 1.35 | -16.2% |
| B | 1034 | +65.0% | 1.35 | -16.2% |
| C | 1007 | +30.5% | 1.16 | -13.4% |

Overlap trades : A∩B = **100 %** · B∩C = **12.9 %** (les 2 classements sélectionnent des trades très différents)

### 4.2 Volet 20 seeds (rang randomisé intra-pool — isole l'effet gate)

| Variante | médiane | P10 | P25 | P90 | pire seed | % positifs | std |
|---|---|---|---|---|---|---|---|
| A | 25.3% | 10.9% | 21.1% | 32.5% | -3.5% | 95% | 9.2 |
| B | 20.3% | 8.2% | 12.7% | 31.4% | +7.7% | 100% | 8.5 |
| C | 20.0% | 12.5% | 13.8% | 29.1% | +6.6% | 100% | 8.3 |

## 5. Verdicts

### V1 — Retirer le per-symbol (C) dégrade le Gate Extreme → NON
- Prod : C (+62.3 %) ≈ **moitié** de A (+146.1 %).
- Recherche déterministe : C (+30.5 %) ≈ moitié de A/B (+65 %).
- Le **rang par `long_prob` apporte une vraie valeur** : A/B et C ne se recouvrent qu'à 12.9 % des trades.

### V2 — Le VETO est quasi inopérant en déterministe
- A ≡ B (overlap 100 %, ret identique) : les candidats rejetés (`long_prob ≤ 0.55`) n'entrent de toute façon
  jamais (rang long_prob les place en queue). Le veto ne devient utile que sous rang randomisé (méd. A 25.3 %
  vs B 20.3 %).

### V3 — B25 gate vs EXT gate (gate pur, PAS de per-symbol)
- **Le gate B25 reste légèrement meilleur que le gate Extreme pur** (cohérent avec E16-C) :
  EXT C (+62.3 %) < B25 L+S (+69.1 %) en prod.
- **EXT A n'est PAS le gate Extreme pur** : c'est gate Extreme (top 20 %) + **per-symbol B25** + LONG-only.
  L'écart A − C = **+84 pp** vient entièrement du per-symbol, pas du gate.

### Pourquoi EXT A > B25 L+S si "B25 est meilleur" ?
1. **Redondance** : sur le pool B25 (top 10 % `global_rank_20`), `long_prob` ≈ même signal que le rang → le
   per-symbol n'ajoute presque rien.
2. **Orthogonalité** : sur le pool Extreme (top 20 % `proba_extreme`), `long_prob` est un signal indépendant →
   il élimine les extrêmes mauvais et classe les bons → gros gain.
3. **LONG-only** : B25 L+S porte 172 shorts (jamais validés, NO-GO E14/E15) ; EXT A les évite.

## 6. Recommandation architecturale

- **Conserver la variante A (`filter`)** comme config du Gate Extreme : per-symbol B25 = filtre + rang.
- **Ne PAS supprimer le per-symbol** (C) : dégradation mesurée, pas d'argument pour le retirer.
- Option de simplification possible : A vs B quasi identiques en déterministe → le **veto pourrait être retiré**
  sans changer le résultat (mais il ajoute une marge de robustesse sous incertitude de rang).

## 7. Réserves / limites

- +146 % (EXT A) = **un seul run déterministe**, non validé en seeds en prod (validation seeds faite en
  recherche uniquement).
- B25 long-only (-48.7 %) inexploitable (incohérence PF vs return).
- Comparaison asymétrique : EXT A = top 20 % + LONG-only vs B25 L+S = top 10 % + L/S.

## 8. Artefacts

- Reports : `artifacts/backtesting/e17_ext_{A,B,C}_preset4000/`, `e16d_b25_preset4000/`, `e16d_b25_longonly_preset4000/`
- Ablation recherche : `artifacts/models/oracle/e17_gate_per_symbol_ablation.parquet`
- Script : `scripts/e17_gate_per_symbol_ablation.py`
- Doc : `doc/oracle_extreme.md` (section 5.2 — variantes + câblage C)
