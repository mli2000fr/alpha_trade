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

---

## 14. E21-A — Régime × trailing (test contrôlé : SEUL le trailing varie) — **hypothèse REJETÉE**

### 14.1 Setup

- Moteur recherche **e11/e13** (gate Extreme TOP20, **m24**, coûts/gap/intrabar identiques),
  période **2023-2026**, signaux **identiques** (seed 7). **Seule la colonne
  `trailing_stop_pct` varie** (hook ajouté au simulateur : `_OpenPosition.trailing_stop_pct`,
  prioritaire sur la dérivée `risk_per_share`).
- Régime **`SPY close > SMA200`**, PIT à la **date du signal**, **gelé à l'entrée**.
  Couverture 100 %, **91 % BULL** sur la période.
- 4 contrefactuels : ALL-PIPELINE (7 %) · ALL-RESEARCH (2,5×ATR) · REGIME
  (bull=research, bear=pipeline) · INVERSE (bull=pipeline, bear=research).
- Script : `scripts/_e21a_regime_trailing.py`.

### 14.2 Résultats

| Variante | Ret % | DD % | Sharpe | PF | Trades | Win % | Worst20 |
|---|---|---|---|---|---|---|---|
| **ALL-PIPELINE** (7 % partout) | **81,1** | **−18,0** | **0,59** | 1,12 | 4241 | 42,5 | **−12,1** |
| ALL-RESEARCH (2,5×ATR partout) | 75,8 | −25,2 | 0,51 | 1,14 | 2470 | 60,7 | −15,4 |
| REGIME (hypothèse) | 78,8 | −22,3 | 0,53 | 1,15 | 2652 | 58,1 | −15,1 |
| INVERSE (placebo) | **95,9** | −22,4 | **0,64** | 1,14 | 4003 | 44,3 | −12,5 |

### 14.3 Verdict — l'hypothèse « bull → 2,5×ATR » est REJETÉE sur cet univers

| Critère | Résultat |
|---|---|
| `Return(REGIME) ≈ Research` | ✅ 78,8 ≈ 75,8 |
| `DD(REGIME) ≈ Pipeline` | ❌ −22,3 vs −18,0 |
| PF / Sharpe améliorés | ⚠️ PF 1,15 mais Sharpe 0,53 < 0,59 |
| **REGIME bat ALL-PIPELINE ?** | ❌ **NON** (78,8 < 81,1) |

1. **Sur le gate Extreme (2023-2026), le trailing serré 7 % bat le 2,5×ATR**
   (81,1 % vs 75,8 %, DD −18 vs −25) — **inverse** du récit B25 2025-2026.
2. **INVERSE est le meilleur** (95,9 %, Sharpe 0,64) : bull→7 %, bear→2,5×ATR —
   **direction opposée à l'hypothèse**, mais part bear minuscule (9 %) → peu robuste.
3. **Conséquence majeure (révision §9)** : le test **trailing-only ne reproduit PAS le
   gap +175 % vs +9 %**. Le trailing seul fait peu de différence ici (75,8 vs 81,1).
   → **Le +175 % vs +9 % vient surtout des AUTRES différences** : ancrage TP sur close
   de veille, DD breaker + force-close, sizing/capacité (8 vs 24), univers (B25 rank vs
   Extreme gate), période (2025-2026 vs 2023-2026). Le trailing 7 % vs 2,5×ATR n'est
   **pas** « LA source » — il est **dépendant de l'univers/période**.

⚠️ **Limites** : test sur le **gate Extreme**, pas sur les signaux **B25** du +175 % ;
régime 91 % BULL → l'interaction régime×trailing est **sous-échantillonnée côté bear**.
Un E21-A sur les signaux B25 (chemin CLI) et/ou avec plus de périodes BEAR (2022, 2024H1)
serait nécessaire avant de conclure sur la direction du régime.

---

## 15. E21-B25 — Attribution causale P0→P5 sur les MÊMES signaux B25 (2026-08-21)

### 15.1 Objectif & méthode

Expliquer **causalement** le gap **+175,7 % (recherche) vs +9,13 % (pipeline)** sur
**exactement les mêmes signaux B25 long-only** (batch `model-factory-20260811223551-ef2cd0`,
2025-01→2026-05, equity 4000, m8). Échelle cumulative : on part du **pipeline exact** et on
flippe **UNE différence à la fois** vers la recherche, sans chercher de paramètre optimal.

4 hooks CLI ajoutés (off par défaut, tests verts) : `--trailing-long-risk-based` (P1),
`--tp-anchor-entry` (P2), `--sl-anchor-entry` (P3), `--research-sizing` (P5).
Scripts : `scripts/_e21b25_launch_attribution.ps1`, `_e21b25_analyze.py`.

⚠️ **Piège coûts corrigé** : l'original recherche utilise le **modèle canonique**
(défaut `--use-canonical-costs`, ~5 bps entry : comm 1 + slip 2 + spread réel) — le
`slippage_bps 20` du report est affiché mais **ignoré** par le canonique. Un premier
TARGET avec `--no-use-canonical-costs` (21 bps) donnait +95,6 % (trades identiques mais
~4 $/trade de coûts en plus → -80 pts). Corrigé → **+175,72 % exact**.

### 15.2 Résultats

| Échelon | Ret % | Δ vs P0 | DD % | Sharpe | PF | Trades | Win % | Gross % |
|---|---|---|---|---|---|---|---|---|
| **P0** pipeline exact (ref) | 9,13 | — | −16,5 | 0,52 | 1,11 | 543 | 47,3 | 36 |
| **P1** + trailing 2,5×ATR | **48,94** | **+39,8** | −10,0 | 1,75 | 1,47 | 356 | 66,6 | 60 |
| **P2** + TP ancré entrée | 45,09 | −3,9 | −9,0 | 1,65 | 1,45 | 337 | 65,0 | 60 |
| **P3** + SL ancré entrée | 44,51 | −0,6 | −9,4 | 1,63 | 1,44 | 337 | 65,0 | 60 |
| **P4** + DD breaker off | 44,51 | 0,0 | −9,4 | 1,63 | 1,44 | 337 | 65,0 | 60 |
| **P5** + sizing research | 65,80 | +21,3 | −16,2 | 1,45 | 1,38 | 337 | 65,0 | 86 |
| **TARGET** recherche exact | **175,72** | +109,9 | −28,2 | 1,66 | 1,33 | 396 | 59,8 | 158 |

### 15.3 Décomposition du gap (+9,13 % → +175,72 %, soit 166,6 pts)

```
+9,1 %  P0 pipeline
  +39,8 pts  trailing 7 % → 2,5×ATR      (P1)   ← composante sortie DOMINANTE
   −3,9 pts  TP ancré close → entrée     (P2)   ← NÉGATIF (contre-intuitif)
   −0,6 pts  SL ancré close → entrée     (P3)   ← quasi neutre
    0,0 pts  DD breaker désactivé        (P4)   ← inactif sur cette trajectoire
  +21,3 pts  sizing ATR-risk → equal×lev (P5)   ← partiel (86 % gross seulement)
  +109,9 pts résiduel engine-mode        (TGT)  ← sélection + exécution + levier complet
+175,7 % TARGET recherche (reproduction exacte)
```

### 15.4 Verdict

1. **Le trailing 2,5×ATR vs 7 % est LE facteur de sortie dominant sur B25 : +39,8 pts
   (≈ 24 % du gap)**, win% 47→67, DD −16→−10. **Contrairement à E21-A (gate Extreme,
   où il ne faisait que ~5 pts)** → l'effet trailing est **fortement univers-dépendant**,
   et sur l'univers réel du +175 % il est bien la composante sortie n°1.
   → **Le trailing MÉRITE l'étude régime (E21-regime-v2)**, comme tu le soupçonnais.
2. **L'ancrage TP sur entrée COÛTE −3,9 pts** (contre-intuitif vs §3 : sur B25, attendre
   +7 % sur l'entrée retarde le TP et laisse des gagnants retomber sous le trailing large).
3. **L'ancrage SL : −0,6 pt** (neutre). **DD breaker : 0,0** (ne déclenchait pas ici).
4. **~66 % du gap (109,9 pts) n'est PAS dans les mécaniques de sortie** : il vient du
   **sizing/exposition** (pipeline 36 % de gross vs recherche 158 % = sous-exposition
   massive, P5 en pipeline ne monte qu'à 86 %) + **sélection** (le risk bridge rejette
   ~85 % des candidats : 396 trades recherche vs 337 en P5) + **chemin d'exécution/replay**.
5. **Le vrai problème du pipeline n'est donc pas seulement le trailing** : c'est surtout
   une **sous-exposition structurelle** (36 % de gross) + une **sélection restrictive**.
   Même avec le trailing 2,5×ATR (P1), le pipeline reste à +48,9 % (vs +175,7 %) tant que
   le sizing et la sélection ne sont pas alignés.

**Suite logique** : (a) E21-regime-v2 (états BULL/CORRECTION/BEAR/REBOUND) sur la
composante trailing B25 isolée par P1 ; (b) diagnostic sizing pipeline : pourquoi 36 %
de gross (target_annual_vol, structural guard, régime capital_preservation) et lever
2× jamais utilisé ; (c) ne PAS passer au ML de sortie avant d'avoir isolé la mécanique
(le trailing +39,8 pts est maintenant la cible claire).

---

## 16. E22 — Pipeline Capital Deployment Audit : pourquoi 36 % de gross vs 158 % (2026-08-21)

### 16.1 Funnel (moyennes par jour, P0 pipeline B25 long-only, equity 4000, m8)

```
GROSS POTENTIEL (levier 2×, 8 × 25 %)     200 %
GROSS POTENTIEL (equal-weight 1/8)        100 %
après risk bridge (approved)               ~87 %  (3 479 $/jour — le bridge ACCEPTE largement)
après execution (fills)                    ~87 %  (filled/approved = 1,000 — exécution 100 %)
GROSS RÉEL (trade_audit_log)               ~37 %  (1 467 $)  ← LE GAP EST ICI
```

**Le risk bridge et l'exécution ne sont PAS le goulot** : ~7,7 longs acceptés/jour (150-175/mois
y compris avril 2025), exécutés à 100 %. Le gap 87 % → 37 % se produit dans le **déploiement réel**.

### 16.2 Attribution des rejets risk bridge (phase 2)

| Cause | n (longs) | % notional |
|---|---|---|
| `max_long_positions` (slots pleins) | 4 688 | 66 % |
| `max_gross_exposure` | 1 029 | 20 % |
| `max_tickers_per_sector` | 1 020 | 14 % |
| corrélation / min_notional | ~405 | ~0 % |
| (shorts bloqués par no-shorts) | 7 929 | — |

→ Ces rejets limitent les jours chargés, mais ne sont **pas** le driver du 36 % (le bridge accepte déjà 87 %/jour).

### 16.3 LE VRAI COUPABLE : le DD breaker (03/04/2025)

Le **03/04/2025** (crash tarifaire), l'equity passe à **−16,8 % de DD** (> seuil 15 %) →
`tripped=True`, `allocation_scale=0.06` → **force-close de 8 positions** (le compte passe à 0 % gross).

| Période | allocation_scale | gross moyen | jours |
|---|---|---|---|
| Jan-Mar 2025 | 1,00 (full) | ~75 % | 60 |
| Avr 2025 | 0,06 → 0,12 (dégradé) | ~0-8 % | 19 trippés |
| **Mai-Déc 2025** | **0,25 (plafonné)** | **~21 %** | **~191 jours** |
| Fév-Mai 2026 | 1,00 (full) | ~60 % | 60 |

- **204/352 jours trippés (58 % du run !)** — le compte reste dé-risqué ~9 mois.
- Cause : `dd_recovery_pct=0.92` (l'equity doit remonter à **92 % du pic** de mars 2025 = 4 029 $)
  + `ramp_up_max_pct=0.25` → allocation plafonnée à 25 % tant que le pic n'est pas re-dépassé.
  L'equity est restée ~3 640-3 950 $ pendant des mois → **piège de sous-investissement prolongé**.

### 16.4 Le sizing structurel (même à plein)

- Sizing pipeline = **risk_budget 1,25 % / (2,5×ATR)** → positions **~5-13 %** (inversement
  proportionnel à la volatilité, médiane ~10,8 %), PAS equal-weight.
- Même à allocation 1,0 (2026) : gross ~60 % (pas 87 %) — ~5,5 slots ouverts, jamais les 8.
- **Le levier 2× est disponible (budget 161 %) mais JAMAIS utilisé** par ce sizing → jamais de 158 %.

### 16.5 Chaîne causale (réponse à « pourquoi 36 % vs 158 % »)

```
trailing 7 % fixe → pertes profondes avril 2025 → DD −16,8 % → DD breaker force-close
→ allocation 6-25 % pendant ~9 mois (204/352 jours) → gross moyen 37 % → 9,13 %
```

1. Le **DD breaker** est la cause n°1 du 36 % (dé-risquage 9 mois, 58 % du temps).
2. Le **sizing ATR-risk** est la cause n°2 (jamais de levier 2×, plafond ~60-87 %).
3. **Interaction clé** : avec le trailing **2,5×ATR** (P1/P3/P4), le breaker **ne trippe JAMAIS**
   (`force_close=0`) — le trailing 7 % est donc la cause profonde du déclenchement du breaker
   (pertes profondes avril 2025), en plus d'être la composante de sortie dominante (E21-B25 §15).

### 16.6 Implications

- Le « 36 % vs 158 % » n'est **pas** un problème de selection/execution, mais un **piège de
  récupération du DD breaker** (58 % du temps dé-risqué) + un **sizing qui n'utilise jamais le levier**.
- Le levier 2× complet n'est **pas** la cible (P23 : dilution capacité au-delà de ~1,5×) ;
  mais un **re-sizing equal-weight** + un **breaker moins « collant »** (recovery plus rapide,
  ramp_up plus haut) captureraient une partie du potentiel SANS le risque de levier 2×.
- Le **trailing 2,5×ATR** est d'autant plus prioritaire qu'il désamorce le breaker (P1 = +39,8 pts
  incluant cet effet indirect d'exposition).

Scripts : `scripts/_e22_capital_audit.py`, `_e22b_funnel.py`, `_e22c_daily.py` → `logs/_e22_*.txt`.

## 17. E21-v2 — Trailing adaptatif × régime (C0-C3, breaker on/off) (2026-08-21)

### 17.1 Objectif & méthode

Test contrôlé : **SEUL le trailing varie** via `--regime-trailing-policy {c0,c1,c2,c3}`,
sur les MÊMES signaux B25, breaker PROD gelé (DD 15 %, recovery 0.92, ramp 0.25).
Régimes SPY PIT (SMA50/SMA200, min_periods 50/200) : BULL / REBOUND / CORRECTION / SLIDE
(distribution BULL 68 %, CORRECTION 14 %, SLIDE 13 %, REBOUND 2 %).

- **C0** : trailing 7 % fixe (baseline prod / P0)
- **C1** : 2,5×ATR partout
- **C2** : **BULL/REBOUND → 2,5×ATR ; CORRECTION/SLIDE → 7 %**
- **C3** (placebo inverse) : **BULL/REBOUND → 7 % ; CORRECTION/SLIDE → 2,5×ATR**

Chaque politique × breaker ON/OFF (breaker OFF = diagnostic, pas la prod).
Critère GO pré-déclaré : *Return C2 ≈ Return C1 avec DD plus bas, sans plus de trips breaker*.

### 17.2 Résultats (reports `artifacts/backtesting/e21v2_*`)

| Pol | Trailing | Brk | Ret% | DD% | Sharpe | PF | Tr | Win% | w12 | gross% | tripJ | FC | alloc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0 | 7% fixe | on | 9.1 | 16.5 | 0.52 | 1.11 | 543 | 47.3 | −0.1 | 36 | 204 | 8 | 0.56 |
| C0 | | off | 43.8 | 13.0 | 1.60 | 1.35 | 541 | 47.5 | 0.3 | 62 | 0 | 0 | 1.00 |
| C1 | 2.5×ATR | on | 15.3 | 16.5 | 0.73 | 1.19 | 435 | 56.1 | 0.0 | 46 | 142 | 8 | 0.69 |
| C1 | | off | 52.6 | 13.0 | 1.87 | 1.49 | 433 | 56.4 | 0.4 | 60 | 0 | 0 | 1.00 |
| C2 | ATR sauf CORR/SLIDE | on | **20.0** | 16.5 | 0.91 | 1.24 | 467 | 54.8 | 0.0 | 46 | 142 | 8 | 0.69 |
| C2 | | off | **57.3** | 13.0 | 1.99 | 1.52 | 465 | 55.1 | 0.4 | 60 | 0 | 0 | 1.00 |
| C3 | inverse | on | 4.6 | 16.5 | 0.30 | 1.06 | 497 | 48.9 | −0.2 | 37 | 204 | 8 | 0.56 |
| C3 | | off | 39.4 | 13.0 | 1.46 | 1.33 | 495 | 49.1 | 0.2 | 63 | 0 | 0 | 1.00 |

Δbreaker = Return(off) − Return(on) : C0 +34.6 / C1 +37.3 / C2 +37.3 / C3 +34.8 pts.

### 17.3 Verdict

1. **Le breaker domine tout** : 34-37 pts perdus dès qu'il trip, quelle que soit la politique.
   Le régime seul (breaker off) vaut ~4-5 pts (C2 57.3 vs C1 52.6), réel mais secondaire.
2. **C2 est le meilleur trailing sous breaker PROD** : +20.0 % vs C1 +15.3 % vs C0 +9.1 %,
   trips breaker réduits 204 → 142 jours, alloc 0.56 → 0.69. C2 ≥ C1 partout, égal en trips.
3. **C3 (serrer en marché normal) casse tout** (4.6 %) — le ATR large en BULL est confirmé,
   le serrage 7 % en CORRECTION/SLIDE (C2) est une protection, pas un frein.
4. **Limite** : DD plafonnée à 16.5 par le breaker (indépendant du trailing) ; et aucun C
   n'atteint +175 % : il manque le sizing (E22 §16) + engine-mode (E21-B25 §15). C2 est donc
   la **composante trailing à retenir** pour un run combiné trailing×sizing×breaker révisé.

**Décision : adopter C2** (2,5×ATR en BULL/REBOUND, 7 % en CORRECTION/SLIDE) comme trailing
pipeline B25. Scripts : `scripts/_e21v2_*.py`, `backtesting/regime_trailing.py` → `logs/_e21v2_results.txt`.
