# E45 — Crash-test catastrophe au VRAI seuil −15 % : KEEP vs WORST_50 vs ALL
## Verdict airbag (2026-08-22) — seuil B4 gelé, aucun tuning

> **Protocole** : produire de VRAIS trips du breaker B4 (DD ≤ −15 %) **sans baisser le seuil**, via des
> stress réalistes pré-spécifiés, puis comparer KEEP / WORST_50 (`force_close_pct 0.5`) / ALL (`1.0`)
> sur les **mêmes scénarios**. Métrique principale : **ADD = MaxDD_après_trip − 15 %** (pts).
> ⚠️ S2 et S5 = **UN SEUL épisode indépendant** (juillet 2025) → verdict = « meilleur candidat provisoire ».

---

## 1. Phase A — quels stress déclenchent le vrai airbag ?

| Scénario | Stress | Gross | MaxDD | Trip −15 % |
|---|---|---|---|---|
| S0 PROD-like (ref) | — | ~60-65 % | 5,66 % / 8,33 % | non |
| S1_costs | spread 30 / slippage 15 / comm 5 bps | ~58-65 % | 5,66 % / 8,38 % | **non** |
| S2_expo | `--research-sizing` (equal-weight × levier) | **97-116 %** | 12,8 % / **16,9 %** | **2025 ✅** |
| S3_cpoff | CP-OFF propre (shorts gardés à 5) | ~60-67 % | 6,8 % / 8,4 % | **non** |
| S4_2020 | crash historique | — | — | **NOT TESTABLE** (coverage 81,3 % < 90 %, gate non contourné) |
| S5_combo | CP-OFF + exposure + coûts modérés | **96-116 %** | 10,9 % / **17,5 %** | **2025 ✅** |

**Enseignements durables (indépendants de Phase B)** :
- Le levier d'exposition (`--research-sizing`) est **le seul déclencheur** : il porte le gross de ~60 % à **~116 %**.
- **Même CP-OFF, la config normale (~60-67 % gross) ne dépasse pas ~8,4 % de DD** → le breaker −15 % est
  réellement un **airbag de dernier recours** (B4 n'intervient qu'en cas de défaillance conjointe des protections),
  pas un composant d'intervention régulière.

---

## 2. Phase B — verdict au vrai trip (−15 %)

### 2.1 ADD & rendements (objectif principal : réduire l'ADD)

**S2_expo 2025** (gross 116 %, trip 01/07) :
| Politique | ADD | annuel | Sharpe | longPnL | shortPnL |
|---|---|---|---|---|---|
| KEEP | **1,90 pts** | **+14,70 %** | 0,86 | +991 | −490 |
| WORST_50 | 1,47 pts (−0,43) | +10,42 % (−4,28) | 0,66 | +920 | −635 |
| ALL | 1,83 pts (−0,07) | **−1,97 % (−16,67)** | −0,04 | +452 | −562 |

**S5_combo 2025** (gross 116 %, trip 26/06) :
| Politique | ADD | annuel | Sharpe | longPnL | shortPnL |
|---|---|---|---|---|---|
| KEEP | 2,54 pts | +21,77 % | 1,23 | +1498 | −752 |
| WORST_50 | **1,24 pts (−1,30)** | **+25,59 % (+3,82)** | **1,42** | +1533 | −631 |
| ALL | 2,67 pts (+0,13) | +11,49 % (−10,27) | 0,73 | +1145 | −791 |

### 2.2 Coût du sauvetage (pts rendement / pt d'ADD évité, vs KEEP)
- **S2_expo** : WORST_50 coûte **9,95 pts** par pt d'ADD évité (coût annuel 4,28 pts pour 0,43 pt) ; ALL coûte **238 pts/pt** (catastrophique).
- **S5_combo** : WORST_50 a un **coût NÉGATIF** (−2,94 pts/pt : il réduit l'ADD **et** améliore le rendement) ; ALL coûte −79 pts/pt (ADD inchangé, −10,3 pts de rendement).

### 2.3 Contrefactuel des positions liquidées au trip (le point décisif)

**S5_combo (D=26/06, 8 positions ouvertes)** — reconstruction validée (match exact des diagnostics) :
WORST_50 ferme les **4 pires PnL = 4 SHORTS** ; ALL ferme les 8 (2 longs + 6 shorts).

| Position | Side | PnL à D | PnL si KEEP | Δ (manqué/gagné) |
|---|---|---|---|---|
| ARLO | short | −47 | −46 | +0,9 (neutre) |
| ADNT | short | −46 | −93 | +47,3 ✅ coupé à raison |
| RITM | short | −28 | −118 | +90,2 ✅ coupé à raison |
| OSK | short | −7 | −12 | +5,4 ✅ coupé à raison |
| **MUR** | **long** | +10 | **+116 (TP)** | **−106,4 ❌ récupération manquée** |

→ **WORST_50 gagne ici** : il coupe les shorts perdants (≈ +143 $ sauvés) **et conserve MUR** qui part en
take_profit (+116). **ALL ferme MUR → rate +106 $** → c'est ce qui le rend pire que KEEP.

**S2_expo (D=01/07, 6 positions ouvertes)** — note : un 2ᵉ trip possible (compteur 7 pour ALL) ; best-effort.

| Position | Side | PnL à D | PnL si KEEP | Δ |
|---|---|---|---|---|
| **OBDC** | **short** | −47 | **+114 (TP 18/11)** | **−161,4 ❌❌ énorme récupération manquée** |
| HST | short | +5 | −18 | +23,5 ✅ |
| FLS | short | +13 | −43 | +56,0 ✅ |
| FLR | short | +15 | −58 | +73,7 ✅ |
| MUR | long | +30 | +109 (TP) | +79,2 ❌ (fermé par ALL) |

→ **Confirme la critique du tri « pires PnL d'abord »** : **OBDC** était le short le plus perdant à D (−47)
et partait pourtant en **take_profit à +114** dans KEEP. Le classement par PnL courant est un **mauvais
prédicteur du risque résiduel** — une position proche de son stop (longue détention depuis 22/04) a peu de
risque de perte supplémentaire mais un gros potentiel de rebond.

### 2.4 ALL vs WORST_50
- **ALL est clairement destructeur** : ADD inchangé ou pire (+0,07 à −0,13 pt), rendement −10 à −17 pts.
  La cause : il ferme les **longs gagnants** (MUR +106 à +109 manqués) qui alimentent la reprise.
- **WORST_50 est neutre à positif** : S5_combo → dominant (ADD −1,30 pt ET +3,82 pts) ; S2_expo → ADD −0,43 pt
  mais coût 4,3 pts (piloté par le contrefactuel OBDC). En pratique il ne ferme que des **shorts** (les pires PnL
  au trip sont des shorts), ce qui le rend « side-aware de facto ».

---

## 3. Verdict (hiérarchie airbag)

| # | Critère | Constat |
|---|---|---|
| 1 | **Réduction de l'ADD** | WORST_50 réduit l'ADD sur les 2 scénarios (0,43 / 1,30 pt) ; ALL non (0,07 / −0,13). |
| 2 | **Coût du sauvetage** | WORST_50 : gratuit voire positif en S5_combo, coûteux en S2_expo (ratio ~10, OBDC). ALL : toujours très coûteux (−10 à −17 pts). |
| 3 | **Contrefactuel** | Le tri « pires PnL » ferme parfois des positions qui récupèrent fortement (OBDC −161, MUR −106). Confirmé : **classer par PnL courant est un mauvais prédicteur de risque résiduel**. |
| 4 | **ALL vs WORST_50** | ALL ajoute la fermeture des longs gagnants → destructeur. WORST_50 = seul candidat potentiellement utile (coupe les shorts perdants, garde les longs à rebond). |
| ⚠️ | **Statistique** | 2 scénarios = **1 seul épisode indépendant** (juillet 2025). Aucune validation définitive possible. |

### Conclusion
- **ALL (`force_close_pct 1.0`) : rejeté** — pire que KEEP sur l'unique épisode (ADD non réduit, −10 à −17 pts).
- **WORST_50 (`0.5`) : « meilleur candidat provisoire »** — jamais catastrophiquement pire que KEEP, et **dominant
  dans le scénario de défaillance combinée** (S5_combo : ADD −1,30 pt ET +3,82 pts). Le `force_close_pct: 0.5`
  actuel de PROD est donc **défendable à titre provisoire**, mais :
  - il n'est **pas validé** (1 épisode, non indépendant) ;
  - son talon d'Achille est le tri par PnL (contrefactuel OBDC) → une **V2 « sélection par risque résiduel »**
    (éviter de fermer les positions longuement détenues / proches de leur stop naturel) est le prolongement naturel.
- **KEEP reste la baseline sûre** ; **B4 à −15 % conservé** (airbag de dernier recours confirmé : la config normale
  n'atteint jamais −15 %).

### Recommandation PROD
**Garder** : `force_close_on_breaker: true`, `force_close_pct: 0.5` (provisoire), `policy: b4`, seuil **−15 % gelé**.
**Ne pas** revenir à `1.0` (prouvé destructeur) ni à KEEP (perd la protection gratuite du scénario combiné).
**Prochain chantier possible** : E46 — sélection par risque résiduel (V2) + plus d'épisodes indépendants (2020 si la
couverture ML est restaurée, ou stress supplémentaires).

---

## 5. Règle retenue (PROD — déjà active, vérifiée le 2026-08-22)

> **Quand le circuit breaker B4 atteint réellement −15 % de drawdown du portefeuille, on liquide 50 % des
> positions ayant les PnL les plus mauvais à cet instant.**

Concrètement (comportement du code `backtesting/simulator.py` ~l. 988-1060, identique en live
`execution_engine/executor.py` ~l. 344-415) :
1. Au **premier jour** où DD ≤ −15 % (`just_tripped()`), on calcule le PnL de **toutes** les positions
   (longs et shorts ; un short est « perdant » si son prix a monté).
2. On les classe de la plus perdante à la plus gagnante.
3. On ferme les **n = round(nb_positions × 0,5)** premières (pires PnL). Ex : 8 positions → 4 fermées.
4. Les autres continuent avec leur lifecycle normal (take-profit, time stop, etc.).
5. B4 continue de **bloquer / réduire les nouvelles prises de risque** selon sa politique de récupération.

⚠️ Ce n'est **pas** « dès qu'une position perd, on coupe 50 % des perdants » : cela ne se produit
**qu'au franchissement catastrophe de −15 % du portefeuille**, après l'échec de toutes les autres défenses
(CP-V2, sizing, stops, réduction d'exposition).

**Statut scientifique** : règle conservée comme **airbag provisoire raisonnable** — E45 montre que
**50 % > 100 %** et que **WORST_50 réduit l'ADD** dans les 2 stress testés, mais sur **un seul épisode
indépendant** (juillet 2025). Ce n'est **pas** un optimum démontré. Le défaut connu (contrefactuel OBDC :
un « pire perdant » au trip a ensuite repris jusqu'au TP) est **volontairement non traité** pour l'instant :
manque d'épisodes indépendants pour calibrer un tri plus fin sans surajuster (E46 plus tard).

**Config PROD actuelle (vérifiée)** : `risk.max_drawdown: 0.15` · `risk_management.force_close_on_breaker: true` ·
`force_close_pct: 0.5` · `policy: b4` · `force_close_losers_on_breaker: None`. **Aucun changement nécessaire.**

---

## 4. Fichiers & données
- Runs : `artifacts/backtesting/cmp_b25_h20_2025_e45_{S2_expo,S5_combo}_{keep,worst50,all}`
- Launcher : `scripts/e45_phaseA_launch.py` (`--scenario --year --policy`) ; Analyse : `scripts/e45_phaseB_analyze.py`
- Config stress : `config/market_regimes_cp_off_e45.yaml` (CP-OFF propre, shorts gardés à 5)
- Enabler CLI (backtest only, PROD inchangé sans flag) : `backtesting/cli/_impl.py` →
  `--force-close-on-breaker` / `--no-force-close-on-breaker` / `--force-close-pct`
