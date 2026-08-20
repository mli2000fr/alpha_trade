# Recherche vs Pipeline — TP / SL / Trailing : pourquoi +175 % vs +9 % ?

**Date :** 2026-08-21 — **Objet :** expliquer l'écart de profil entre le backtest
**recherche** et le backtest **pipeline**, sur le même univers B25 long-only, avec
chiffres vérifiés sur les 208 trades partagés (prix d'entrée identiques à 100 %).

## 1. Les 2 backtests comparés

| | **Recherche** `e19_atrfixed_b25_longonly_preset4000` | **Pipeline** run IHM `20260820_225454_1aeb5716` |
|---|---|---|
| Mode | `--engine-mode research` (simulateur direct) | `--engine-mode pipeline` (phases 2→7 replay) |
| Univers | B25 long-only (batch `model-factory-20260811223551-ef2cd0`) | B25 long-only (même batch) |
| Ret % | **+175,7** | **+9,13** |
| Sharpe | 1,66 | ~1,1 |
| DD % | −28,2 | −16,46 |
| PF | 1,330 | 1,11 |
| Trades | 396 | 543 (535 audit + 8 force-close) |
| Win rate | **59,8 %** | 48,0 % |
| Expectancy/trade | **+1,38 %** | +0,92 % |
| DD breaker | **ABSENT** (research skips preset) | PRÉSENT (DD 15 % + force-close) |

> ⚠️ Le **DD breaker + force-close** du pipeline (absent en recherche) est un facteur
> supplémentaire, indépendant du TP/trailing : à −15 % le pipeline liquide des positions
> et réduit l'allocation (0,06) → reste en cash pendant la reprise. Ce doc traite des
> **mécaniques TP/SL/trailing**, pas du breaker (voir §7).

---

## 2. Comment calculer le SL (stop initial)

| | Pipeline | Recherche |
|---|---|---|
| Source ATR | `risk_bridge._compute_atr_20` = **moyenne simple** 20 TR | `atr_pct_20` path labels = **Wilder** 20 |
| Ancrage | **close de la veille** (prix de décision) | **prix d'entrée** |
| Formule long | `SL = close_veille − 2,5 × ATR20` | `SL = entrée − 2,5 × ATR20` |
| SMCI 2025-01-03 | 30,05 − 2,5×2,78 = **23,11** | 30,43 − 2,5×3,28 = **22,13** |

Code : `portfolio_builder.py` L1201-1206 → `compute_initial_stop_price`
(`core/direction.py` L129). Les deux modes utilisent **2,5×ATR** — écart mineur
(ancre + méthode de lissage), ce **n'est pas** la source principale du gap.

---

## 3. Comment calculer le TP (take-profit)

Formule **identique** dans les deux : `TP = min(3×ATR, 7 % du prix)`. La différence
est l'**ancre du 7 %** :

| | Pipeline | Recherche |
|---|---|---|
| Ancre du cap 7 % | **close de la veille** | **prix d'entrée** |
| SMCI | 30,05 × 1,07 = **32,15** (+5,64 % réel) | 30,43 × 1,07 = **32,56** (+7,0 %) |

Sur les 208 trades partagés (sorties TP) :

| TP | Recherche | Pipeline |
|---|---|---|
| n | 124 | 95 |
| ret moyen | **6,99 %** | 6,80 % |
| à exactement 7 % | **95 %** | 37 % |
| sous 6,9 % | ~0 % | **62 %** |

**Mécanisme** : le pipeline calcule le TP à la décision (avant le fill), donc sur le
close de veille. Si le titre **gape à la hausse** à l'entrée (fréquent dans cet
univers), le TP rejoué est mécaniquement < 7 % du prix réellement payé.
**Ce n'est pas un bug** — c'est la fidélité au live (on place l'ordre avant le fill).

---

## 4. Comment calculer le trailing — LA divergence majeure

| | Pipeline | Recherche |
|---|---|---|
| Trailing | **7 % FIXE** depuis le pic | **2,5×ATR** depuis le pic |
| Origine | `trailing_pct_long_override = 0.07` (**politique P14/P17 gelée**, `_impl.py` L3320, `config.py` L216) | `risk_per_share/entrée = 2,5×ATR` (simulateur, `use_live_protection_logic`) |
| SMCI (ATR 10,9 %) | pic − 7 % | pic − **27 %** |
| MBLY (ATR 7,6 %) | pic − 7 % | pic − **19 %** |

**Point clé** : le 7 % fixe a été documenté « parité recherche » mais correspond à
l'**ANCIEN E-LIFECYCLE** (e11 : trailing 7 %, TP 13 %), **pas** au PROD lifecycle
(2,5×ATR) qui produit le +175 %. Ce n'est **pas un bug de câblage** — la branche
risk-based existe (elle est utilisée pour les SHORTS), mais l'override long la
court-circuite. Il n'existe **pas de flag CLI** pour remettre le long à risk-based
(`--trailing-pct-long` absent → 0,07 forcé).

---

## 5. Chiffres des 2 backtests (sorties, perdants, gagnants)

### 5.1 Répartition des sorties

| Exit reason | Recherche | Pipeline |
|---|---|---|
| take_profit | 230 (58 %) @ **+7,02 %** | 252 (47 %) @ +6,72 % |
| trailing_stop | 95 (24 %) @ **−6,13 %** (min −17,05) | **282 (53 %)** @ −4,24 % (min −7,32) |
| initial_stop | 56 (14 %) @ **−8,59 %** (min −22,63) | **1 (0 %)** |
| time_stop | 15 (4 %) | 0 |

### 5.2 Gagnants / perdants

| | Recherche | Pipeline |
|---|---|---|
| Gagnants | 237 (59,8 %) @ +6,88 % (méd 7,00 %) | 258 (48,2 %) @ +6,58 % (méd 6,66 %) |
| **Perdants** | **159 (40,2 %)** @ **−6,82 %** (min **−22,63**) | **277 (51,8 %)** @ **−4,34 %** (min −7,32) |
| Expectancy | **+1,38 %**/trade | +0,92 %/trade |

> **La recherche perd PLUS gros par perdant (−6,8 % vs −4,3 %) mais a MOINS de
> perdants (40 % vs 52 %)** : son trailing/stop large laisse les plongeons survivre
> quand ils rebondissent → ils deviennent des TP +7 % au lieu de perdants.

---

## 6. Les 208 trades partagés (mêmes entrées, mêmes dates)

Croisement des sorties (prix d'entrée identiques à 100 %) :

```
                Recherche   Pipeline
TP              124 (60 %)   95 (46 %)
Trailing         45 (22 %)  113 (54 %)   ← le trait dominant
Initial stop     30 (14 %)    0
Time stop         9 ( 4 %)    0
ret moyen       +1,41 %     +0,85 %      (+0,56 pp/trade)
```

- **34 trades** qui finissent **TP +7 % en recherche** → **trailing en pipeline** :
  ret recherche **+6,97 %** vs pipeline **−3,04 %** → **+340 pp perdus**.
- **30 trades** initial_stop recherche → trailing pipeline : ret res **−9,69 %** vs pip −5,41 %.

### Cas concret SMCI 2025-01-03 (entrée 30,4343 $ identique)

- **Recherche** : TP 7 % sur l'entrée → sortie **32,56 = +7,00 %**.
- **Pipeline** : TP 7 % sur le close de veille (30,05) → **32,15 = +5,64 %** ; trailing 7 %
  fixe → tout pullback de 7 % du pic coupe tôt.
- Même titre, même jour, même prix → **+1,36 pp** perdus par le seul TP + trailing.

### Cas concret MBLY 2025-03-03 (entrée 16,04 $, ATR 7,6 %)

| Date | Événement | Recherche | Pipeline |
|---|---|---|---|
| 03-03 | entrée, low 14,29 | tient (SL 13,05 non touché) | tient |
| 04-03 | low 13,46 | **tient** (13,46 > 13,05) | **trailing 15,02 touché → −6,36 %** |
| 25-03 | gap up 17,30 | **TP 17,16 = +7,00 %** | déjà sorti |

Le pipeline vend au **creux** (J+1), la recherche **absorbe** et encaisse +7 % 3
semaines plus tard.

---

## 7. Rebond après le trailing stop (le cœur de l'edge recherche)

Sur les **282 trailing stops du pipeline** : dans combien de cas le titre a ensuite
atteint **≥ +7 %** (ce que la recherche aurait encaissé) ?

| Fenêtre après la sortie | % qui reviennent à +7 % |
|---|---|
| 10 jours | 17 % |
| 20 jours | 30 % |
| 40 jours | 45 % |
| 60 jours | **51 %** |
| à un moment donné | 73 % |

Contrefactuel « tenir jusqu'à +7 % » : trailing réel **−1195 pp** vs tenir **+1119 pp**
→ **+2314 pp**. ⚠️ Contrefactuel **optimiste** (les 27 % qui ne rebondissent pas sont
crédités de la sortie trailing ; le vrai gain est moindre).

---

## 8. Dépendance au RÉGIME — quand chaque mode gagne

**La largeur du trailing est un pari sur la probabilité de rebond `P(récupération)`.**
Le point de bascule : le titre plonge-t-il sous `pic − 2,5×ATR` **avant** d'atteindre +7 % ?

| Régime | P(rebond) | Mode gagnant | Pourquoi |
|---|---|---|---|
| **Haussier** (2025-2026) | haute (51 % en 60 j) | ✅ **Recherche** | le trailing 2,5×ATR laisse courir → TP +7 % ; le trailing 7 % fixe du pipeline vend au creux |
| **Baissier / latéral** | basse | ✅ **Pipeline** | le trailing 7 % fixe coupe à −4/−7 % ; la recherche encaisse −8/−22 % (SL 2,5×ATR) sur des plongeons qui ne rebondissent pas |

**Chiffres qui le prouvent (2025-2026, haussier)** :
- Recherche : 40 % de perdants à −6,8 %, mais 60 % de gagnants à +7 % → +1,38 %/trade.
- Pipeline : 52 % de perdants à −4,3 % (petits), mais moins de gagnants → +0,92 %/trade.
- 51 % des trailing du pipeline auraient rejoint +7 % en ≤ 60 j.

**En marché baissier, la recherche serait PÉNALISÉE** : son SL 2,5×ATR (jusqu'à
−22 %) et son trailing large ne protègent pas les titres qui ne remontent jamais.
Le trailing serré du pipeline est alors un **filet de sécurité** supérieur.

---

## 9. Synthèse / verdict

1. **TP** : même formule `min(3×ATR, 7 %)`, mais le pipeline ancre sur le **close de
   veille** (fidélité live) → TP effectif < 7 % quand le titre gape → −1 à −1,5 pp par TP.
2. **SL** : 2,5×ATR dans les deux modes (ancre + méthode ATR légèrement différents) —
   **n'est PAS** la source du gap.
3. **Trailing** : **7 % fixe** (pipeline, politique P14/P17) vs **2,5×ATR** (recherche) —
   **LA source majeure**. En 2025-2026, 51 % des stops du pipeline auraient rebondi à
   +7 % : la recherche laisse courir, le pipeline vend au creux.
4. **Régime** : l'avantage recherche est **conditionnel au marché haussier**. Le trailing
   2,5×ATR est un pari « laisser courir » qui paye si les plongeons rebondissent, et
   coûte (grosses pertes −8/−22 %) si le marché ne rebondit pas.
5. **Facteur annexe** : le **DD breaker + force-close** du pipeline (absent en
   recherche) amplifie l'écart en gardant le compte en cash pendant les reprises.

**Levier testable** : passer le trailing long du pipeline en **risk-based (2,5×ATR)**
(→ nécessite de modifier le défaut `trailing_pct_long_override` ou un flag `None`)
pour mesurer le gain potentiel — attendu significatif **en régime haussier**, à
revalider **en régime baissier** avant toute décision de mise en réel.

---

## 10. E20-EXIT v1 — Diagnostic « recovery classifier » au moment du trailing (gelé 2026-08-21)

### 10.1 Objectif

Le gap recherche/pipeline n'est **pas** un simple avantage ex post « avoir attendu plus
longtemps ». Question testée : **au moment où le pipeline déclenche son trailing 7 %,
peut-on prédire si le trade atteindra encore le TP (+7 %) avant le stop catastrophe
(2,5×ATR) ?** Si oui → une logique de sortie adaptative est justifiée. Si AUC ≈ 0,50-0,53
→ c'est un compromis de régime, pas quelque chose de prédictible.

### 10.2 Setup

- **Population** : les **282 trailing stops** du pipeline (run IHM `20260820_225454_1aeb5716`).
- **Label** : `RECOVERY = 1` si le close atteint `entrée × 1,07` dans ≤ N jours après la
  sortie ; `0` si le titre **ne récupère jamais** (sur tout l'historique disponible).
  Horizons N = 20 / 40 / 60 j.
- **Features PIT au moment du stop** (rien après la sortie) : `ret` (perte au stop),
  `hold` (âge), `rank` (rang B25), `gap` (gap d'entrée), `mfe` (pic atteint), `mae`
  (creux), `dd_peak` (drawdown depuis le pic), `mom5/10/20` (momentum court),
  `pe` (percentile Oracle), `atr` (ATR20), `reg5/reg20` (régime cross-sectionnel).
- Script : `scripts/_e19_exit_recovery_diag.py`.

### 10.3 Taux de base

```
hit ≤ 20j : 30 %   |   ≤ 40j : 45 %   |   ≤ 60j : 51 %   |   jamais : 75 (27 %)   |   ever : 207 (73 %)
```

### 10.4 Discrimination au moment du stop (RECOVERY vs NEVER)

Meilleures features univariées (AUC) :

| Feature | AUC @20j | AUC @40j | AUC @60j | Direction (RECOVERY vs NEVER) |
|---|---|---|---|---|
| **mom5** (momentum 5j au stop) | **0,640** | 0,571 | 0,553 | −3,9 % vs **−6,5 %** → moins en chute libre |
| **atr** (ATR20) | 0,608 | **0,604** | **0,605** | 6,1 % vs 5,5 % → ATR plus élevé |
| **mfe** (pic déjà atteint) | 0,624 | 0,563 | 0,551 | +3,9 % vs +2,8 % → avait déjà montré sa force |
| **ret** (perte au stop) | 0,611 | 0,553 | 0,538 | −3,6 % vs −4,4 % |
| mae (creux) | 0,579 | 0,534 | 0,524 | moins profond |
| mom10 | 0,597 | 0,558 | 0,544 | −5,4 % vs −9,7 % |
| pe (Oracle), rank | ~0,52-0,56 | | | faibles |
| **dd_peak** | 0,46 | 0,45 | 0,44 | **inversé** (faible) |
| **reg5 / reg20** (régime) | 0,51 / 0,49 | 0,46 / 0,46 | 0,46 / 0,44 | **≈ aucun signal** |
| gap, hold | ~0,49-0,51 | | | nuls |

**Logistique multivariée (CV 5-fold)** : AUC **0,617 ± 0,110** (@20j, n=160) ·
**0,620 ± 0,051** (@40j, n=199) · **0,604 ± 0,061** (@60j, n=218).

### 10.5 Verdict E20-EXIT v1

- **GO, mais modéré** : AUC ~0,60-0,62, nettement au-dessus de la zone « ne pas faire »
  (0,50-0,53) → l'écart recherche/pipeline contient une **information prédictible**.
- Profil RECOVERY cohérent : *titre qui se stabilise (mom5 peu négatif), très volatil
  (ATR haut), qui avait déjà montré sa force (MFE élevé), perte peu profonde, bon
  Oracle*. Profil NEVER : *en chute libre, faible ATR, jamais monté*.
- **2 surprises** : (1) le régime marché cross-sectionnel ne discrimine presque pas
  (à retester avec SPY réel) ; (2) `dd_peak` n'est pas prédictif (trailing quasi constant).
- La logistique n'apporte que peu au-delà de la meilleure feature univariée (features
  corrélées) → **E20-EXIT v2** doit chercher des **features PIT réellement nouvelles**
  + le **lift économique**, pas une chasse à l'AUC.

---

## 11. E20-EXIT v2 — Features nouvelles + lift économique (gate pré-déclaré)

> **Question** : est-ce que des features PIT réellement nouvelles améliorent la
> discrimination au-delà du bloc actuel `mom5 / ATR / MFE / ret` ?
> **Gate** (fixé avant lancement) : AUC CV ≥ 0,62 · gain ≥ +0,02 vs v1 sur ≥ 2 horizons
> (20/40/60j) · stabilité par semestre · **surtout lift économique** (top/bottom 20 %
> du score recovery), pas l'AUC seule.

### 11.1 Résultats E20-EXIT v2 (features : SPY réel ret5/20/vol20/SMA50-200, volume relatif
5/20j, EMA20/SMA50/SMA200 distance, pente 3j — script `scripts/_e19_exit_v2.py`)

**Gate : ÉCHEC (0/3 horizons)**

| Horizon | AUC v1 | AUC v2 | delta | n |
|---|---|---|---|---|
| 20j | 0,660 | 0,658 | −0,002 | 160 |
| 40j | 0,629 | 0,541 | **−0,088** | 199 |
| 60j | 0,623 | 0,561 | **−0,062** | 218 |

→ les nouvelles features **dégradent** le modèle multivarié (surnpprentissage sur
n~160-218 avec ~24 features dont plusieurs bruitées).

**AUC univariée des nouvelles features (label 40j vs never)** :

| Feature | AUC | Feature | AUC |
|---|---|---|---|
| **spy_vol20** (vol SPY) | **0,611** | relvol5 | 0,500 |
| **mom3** (pente 3j) | **0,602** | sma50_dist | 0,465 |
| ema20_dist | 0,519 | relvol20 | 0,461 |
| spy5 | 0,455 | spy_sma50 | 0,410 |
| spy20 | 0,423 | sma200_dist | 0,427 |
| | | **spy_sma200** | **0,269 (inversé)** |

→ seuls `spy_vol20` (0,61) et `mom3` (0,60, redondant avec mom5) sont informatives ;
le reste est faible ou **inversé** (SMA200, retours SPY).

**Lift économique (modèle v2, horizon 40j, OOF)** — AUC OOF = 0,533 :

| Bucket | n | rec40 réel | ret_si_tenu | valeur/bucket |
|---|---|---|---|---|
| Q1 (bottom20) | 40 | 57 % | +2,16 % | +260 pp |
| Q2 | 40 | 68 % | +3,38 % | +324 pp |
| Q3 | 39 | 54 % | +1,48 % | +226 pp |
| Q4 | 40 | 60 % | +2,45 % | +257 pp |
| Q5 (top20) | 40 | **72 %** | +4,01 % | +293 pp |

→ **lift réel mais faible** : top20 **72 %** vs bottom20 **57 %** (spread 15 pp) —
loin du profil « exploitable » (top20 ≈ 70 % / bottom20 ≈ 20 %). Et la valeur/bucket
n'est **pas** concentrée en haut (Q2 > Q5).

**Stabilité semestrielle** :

| Semestre | base rec40 | TOP20 | BOT20 |
|---|---|---|---|
| 2025H1 | 75 % | 100 % (n=17) | 75 % (n=8) |
| 2025H2 | 60 % | 100 % (n=**1**) | 54 % (n=28) |
| 2026H1 | 53 % | **50 %** (n=22) | **50 %** (n=4) |

→ **lift instable** : il disparaît en 2026H1 (top20 = bottom20 = 50 %), et la base de
récupération varie fortement par semestre (75 % → 60 % → 53 %) → **confirme la
dépendance au régime**.

### 11.2 Verdict E20-EXIT v2

- **GATE ÉCHEC** : AUC ≤ 0,62 et deltas **négatifs** sur tous les horizons.
- Le bloc de base `mom5 / ATR / MFE / ret` capte déjà l'essentiel du signal (AUC
  0,62-0,66) ; les features nouvelles (SPY, volume, EMA/SMA, SMA200) n'ajoutent **rien**
  de robuste, plusieurs sont inversées.
- Seul `spy_vol20` (vol du marché, AUC 0,61) mérite une **v3 minimale** : base +
  `spy_vol20` uniquement, pour tester un gain sans sur-apprentissage — attentes faibles
  (n ~ 160-218, risque de plafond).
- **Recommandation : NE PAS coder le switch adaptatif (trailing 7 % ↔ 2,5×ATR) tant que
  le lift n'est pas démontré et stable** — le diagnostic v1 reste la seule découverte
  solide : le signal recovery existe (AUC 0,62), mais il n'est **pas** étendu par les
  features testées et son lift économique est **faible et instable par semestre**.

---

## 12. E20-EXIT v3 — Base + `spy_vol20` [+ `mom3`] (le premier candidat exploitable)

### 12.1 Résultats (script `scripts/_e19_exit_v3.py`)

**AUC CV (LogReg 5-fold)** :

| Horizon | base | +vol20 | **+vol20+mom3** | n | Gate AUC ≥ 0,62 | +0,02 vs base |
|---|---|---|---|---|---|---|
| 20j | 0,660 | 0,710 | **0,718** | 160 | ✅ | **+0,058** ✅ |
| 40j | 0,629 | 0,636 | **0,640** | 199 | ✅ | +0,011 ❌ |
| 60j | 0,623 | 0,635 | **0,637** | 218 | ✅ | +0,014 ❌ |

→ AUC ≥ 0,62 sur tous les horizons ; le seuil strict « +0,02 sur ≥ 2 horizons » n'est
atteint que sur 1/3 (20j).

**Lift économique (base+vol20+mom3, horizon 40j, OOF)** — AUC OOF **0,629** (vs 0,533 v2) :

| Bucket | n | rec40 réel |
|---|---|---|
| Q1 (bottom20) | 40 | 60 % |
| Q2 | 40 | 48 % |
| Q3 | 39 | 54 % |
| Q4 | 40 | 65 % |
| Q5 (top20) | 40 | **85 %** |

→ top20 = **85 %** de récupération (vs 60 % bottom20) : spread 25 pp, gradient
quasi monotone sur le haut — nettement mieux que v2 (72 %/57 %).

### 12.2 Verdict v3 (vs gate pré-déclaré)

| Critère | v3 |
|---|---|
| AUC CV ≥ 0,62 | ✅ (0,718 / 0,640 / 0,637) |
| +0,02 sur ≥ 2 horizons | ⚠️ **1/3** (seulement 20j : +0,058) |
| Lift queue haute | ✅ **85 %** top20 vs 60 % bottom20 |
| Stabilité semestrielle | ❓ **non re-testée** en v3 |

- **Premier candidat exploitable côté queue haute** : « score recovery élevé → laisser
  courir jusqu'au trailing 2,5×ATR » serait correct ~85 % du temps sur le top quintile.
- **Mais** la queue basse n'est pas un signal de sortie fiable (60 % récupèrent encore)
  et le gate strict +0,02×2 n'est pas pleinement atteint.

### 12.3 Clôture E20-EXIT (décision 2026-08-21) — signal réel mais NON exploitable

**E20-EXIT est CLÔTURÉ. Le trailing adaptatif est FERMÉ (pas de switch ML 7 % ↔ 2,5×ATR).**

| Brique | Verdict |
|---|---|
| v1 (diagnostic) | ✅ **GO diagnostique modéré** (signal recovery réel, AUC 0,60-0,66) |
| v2 (+11 features) | ❌ **NO-GO incrémental** (dégradation, AUC 0,54-0,66) |
| v3 (base+spy_vol20+mom3) | ⚠️ amélioration AUC/lift (top20 85 %) mais **NON retenu** |
| Switch adaptatif | 🚫 **Fermé** |

**Point rédhibitoire** : instabilité semestrielle. En **2026H1, top20 = bottom20 = 50 %**
(plus aucun lift) ; la base de récupération varie fortement par semestre (75 % → 60 % →
53 %). Un petit gain moyen d'AUC avec `spy_vol20` produirait surtout une règle qui
fonctionne sur 2025 et **s'éteint dans le régime difficile** (le seul qui compte pour
la protection).

> **E20-EXIT = signal statistique réel, mais non exploitable de manière robuste pour
> piloter le trailing.** Le trailing 7 % vs 2,5×ATR reste un **compromis de régime**
> (haussier → 2,5×ATR ; baissier → serré), pas un problème que le ML résout à l'heure
> actuelle avec les features disponibles.

---

## 13. Audit SHORT — prod-like **+15,9 %** vs research **−31,5 %** (miroir du LONG)

### 13.1 Les 2 runs

| | **Research** `e19_atrfixed_b25_shortonly` | **Prod-like** `e19_prod_b25_shortonly` |
|---|---|---|
| Ret % | **−31,5** | **+15,9** |
| DD % | **−51,7** | **−13,8** |
| Trades | 329 | 251 |
| Win rate | 40,4 % | 47,0 % |
| **ret moyen/trade** | **+0,11 %** | **+0,60 %** |
| pnl total | −1 335 $ | +591 $ |

### 13.2 Le trailing : **PAS de divergence** (contrairement au LONG)

Le 7 % fixe (`trailing_pct_long_override = 0.07`) est **réservé aux LONGS**. Pour les
SHORTS l'override est `None` → **risk-based 2,5×ATR**, comme la recherche. Vérifié sur
`phase4_protection_replay` du prod-like : trailing pct de **0,6 % à 26,7 %** (médiane
7,6 %), seulement 92/693 à ~7 %. → **le mécanisme « trailing qui tue les gagnants » du
LONG n'existe pas sur les shorts.**

### 13.3 Trades communs (128, entrées 100 % identiques)

- **ret moyen : +0,46 % (research) vs +0,41 % (prod)** → **quasi égal**.
- Inversion gagnants/perdants **équilibrée (7/7)**.
- Exits similaires : TP 46↔46, trailing 43↔43 (croisement stable).

### 13.4 D'où vient l'écart de total (−31,5 % vs +15,9 %)

1. **DD breaker** : research **−51,7 % DD** (pas de breaker, stops 2,5×ATR sur squeezes
   + levier) vs prod **−13,8 %** (breaker 15 %) → le research **saigne à travers** les
   pertes, le prod coupe la casse.
2. **Sets de trades différents** : 329 vs 251, overlap seulement 128 (39 % research /
   51 % prod) → 201 trades research-only + 123 prod-only.
3. **Asymétrie de sizing** : research **+0,11 %/trade en pondéré égal** mais **−1 335 $
   en total** (pondéré par entry_cost : −0,52 %) → **les grosses pertes sont sur les
   grosses positions** ; prod +0,60 %/trade et +591 $.
4. **Queue des pertes** : research 196 losers (60 %) max −10,65 %, p95 −8,36 % ; prod
   133 losers (53 %) max −14,22 %, p95 −9,67 %. Les deux ont une queue de squeeze, mais
   le prod la gère (breaker).

### 13.5 Verdict SHORT — signal, trailing ou lifecycle ?

**Ni le signal, ni le trailing n'expliquent l'écart** (contrairement au LONG) :
- Sur **entrées identiques** (128 trades), les deux moteurs produisent **quasi le même
  per-trade** (+0,46 % vs +0,41 %) → pas de différence de mécanique de sortie sur le
  per-trade.
- Le trailing short est **risk-based dans les deux** → pas de « 7 % fixe » défavorable.

L'écart de total vient de la **gestion du risque (DD breaker) + du set de trades + du
sizing (pertes sur grosses positions)** → surtout **lifecycle/exécution**, mais **pas le
même mécanisme que le LONG**.

⚠️ **Point clé contre-intuitif** : le research short a un **per-trade moyen positif
(+0,11 %)** mais un total **−31,5 %** → le −31,5 % est un **artefact de sizing/DD** (le
−51,7 % de drawdown sur squeezes), pas un edge négatif par trade. Et le +15,9 % du
prod-like n'est **pas un « signal short »** : c'est surtout que le breaker limite la
casse (−13,8 % vs −51,7 %). Le verdict « SHORT = NO-GO » du §13.3 oracle reste valable
sur le fond (aucun des deux n'est un edge short probant) ; l'inversion de signe est un
artefact de gestion du risque.
