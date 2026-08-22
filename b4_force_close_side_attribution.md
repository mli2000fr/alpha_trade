# E44 — Test catastrophe B4 : KEEP vs CLOSE_ALL vs CLOSE_LONGS
## Attribution par side du force-close à DD ≥ 8 % (Vague 1)

**Date** : 2026-08-22 — **Chantier** : E44 (recherche uniquement, PROD non modifié)
**Périmètre** : 2022 + 2025, checkpoint DD −8 %, politique B4, CP-V2 (long 0.40 / short 0.25 / release 5), batch B25 H20, equity 4 000 $, seed 12345.

> **Méthode** : le hook `--research-force-close-at-dd-pct 0.08 --research-force-close-side {all|longs}` liquide UNE fois par épisode de drawdown (re-arm quand DD < 4 % ou nouveau peak) les positions du side demandé. **KEEP** = run CP-V2 actuel sans hook. La liquidation est tracée dans `trade_audit_log.csv` (`exit_reason="research_force_close"`).

---

## ⚠️ Correction préalable : la baseline KEEP e40 était invalide

Découverte en cours de route (documentée) :

| Fait | Détail |
|---|---|
| Run e40 (11:55) | tourné AVANT le commit `8dc834fd` (15:12) qui a ajouté **l'enforcement CP-V2 des budgets par side** (`max_long_exposure` 0.40 / `max_short_exposure` 0.25) dans le sizing du simulateur. |
| Run e44 (16:12) + KEEP re-run | tournés APRÈS → les budgets 0.40/0.25 sont appliqués. |
| Impact 2022 | KEEP re-run = **+11,60 %** (4 463,93 $) vs e40 **+11,83 %** (4 473,24 $) → différence de **9,31 $** = side-budget, **pas** la config (fingerprints identiques). |
| Impact 2025 | identique à e40 (+20,16 %) car **aucune capital_preservation** en 2025 → side-budget jamais activé. |

**Conclusion** : la comparaison équitable se fait avec le **KEEP re-run** (`cmp_b25_h20_{year}_e44_keep_current`, code + config actuels, hook inerte). Les runs e40 sont archivés mais **écartés comme baseline**.

**Test de non-régression** : 2022 KEEP re-run == 2022 CLOSE_ALL == 2022 CLOSE_LONGS exactement (4 463,93 $, +11,60 %) → le hook est **parfaitement inerte** sans déclenchement. ✅

---

## 1. Épisodes identifiés (DD ≥ 8 %)

| Année | Épisodes | Commentaire |
|---|---|---|
| **2022** | **0** | DD max 5,66 % < 8 % → hook jamais tiré. Année **contrôle no-op** (CP-V2 + shorts contiennent le drawdown). |
| **2025** | **1** | D = **2025-07-03** (DD 8,33 % en KEEP, franchi en intraday), épisode jusqu'au **2025-07-21**, trough ≈ 29/07. |

⚠️ **À −8 %, le test ne s'exerce que sur 2025.** Le bear 2022 ne déclenche jamais (c'est déjà un point favorable au CP-V2 : il de-risque avant −8 %). L'extension à −5 % serait le seul moyen de tester 2022 (DD max 5,66 %).

---

## 2. Tableau des 17 métriques — épisode 2025 (D = 2025-07-03)

| # | Métrique | KEEP | CLOSE_ALL | CLOSE_LONGS |
|---|---|---|---|---|
| 1 | Equity à D | 4 009,29 $ | 4 009,29 $ | 4 009,29 $ |
| 2 | P&L réalisé à la liquidation | 0,00 $ | **−16,03 $** (8 pos) | **+41,85 $** (3 pos) |
| 3 | P&L LONG après D | +328,61 $ | +303,34 $ | +172,58 $ |
| 4 | P&L SHORT après D | +455,01 $ | +407,51 $ | +319,41 $ |
| 5 | Return D→J+5 | **+3,29 %** | +1,41 % | +1,72 % |
| 6 | Return D→J+20 | **+7,81 %** | +2,79 % | +3,05 % |
| 7 | Return D→J+60 | **+16,90 %** | +9,94 % | +10,96 % |
| 8 | DD supplémentaire après intervention | −8,33 % | **−7,71 %** | −7,96 % |
| 9 | MaxDD final | 8,33 % | **7,71 %** | 7,96 % |
| 10 | Jours jusqu'au trough (après D) | 0 (déjà au trough) | 17 | 17 |
| 11 | Jours retour au peak (niveau de D) | 0 | 0 | 0 |
| 12 | Capture du rebound (à J+60) | **186 %** | 119 % | 129 % |
| 13 | Return fin de période (D→fin) | **+20,72 %** | +18,55 % | +14,39 % |
| 14 | Sharpe | **2,03** | 1,86 | 1,51 |
| 15 | Gross / Net moyen | 65,3 % / −23,7 % | 68,2 % / −28,2 % | 67,1 % / −27,5 % |
| 16 | Nombre de trades (L/S) | 149 (95/54) | 155 (97/58) | 144 (91/53) |
| 17 | Coût de liquidation (P&L réalisé négatif) | 0 | **16,03 $** | 0 |

**Synthèse annuelle** :

| Année | Politique | Return | MaxDD | Sharpe | longPnL | shortPnL |
|---|---|---|---|---|---|---|
| 2022 | KEEP / CLOSE_ALL / CLOSE_LONGS | +11,60 % | 5,66 % | 0,99 | +16 $ | +404 $ |
| 2025 | **KEEP** | **+20,16 %** | 8,33 % | **2,03** | +574 $ | +199 $ |
| 2025 | CLOSE_ALL | +18,82 % | **7,71 %** | 1,86 | +618 $ | +107 $ |
| 2025 | CLOSE_LONGS | +14,56 % | 7,96 % | 1,51 | +487 $ | +63 $ |

---

## 3. Attribution LONG / SHORT des positions liquidées à D (2025-07-03)

### CLOSE_LONGS (3 longs liquidés) — locked +41,85 $ vs KEEP +78,27 $ → **−36,42 $ sacrifiés**

| Symbole | Side | Verrouillé à D | PnL si KEEP | Δ | Sortie KEEP |
|---|---|---|---|---|---|
| MUR | long | +22,91 $ | +49,30 $ | **−26,31 $** | take_profit |
| SM | long | +13,05 $ | +34,69 $ | **−21,65 $** | take_profit |
| VFC | long | +5,89 $ | −5,70 $ | **+11,59 $** (sauvé) | trailing_stop |

**Lecture** : 2 longs sur 3 étaient des **gagnants** (take_profit atteint en KEEP après D), 1 seul était perdant (VFC). CLOSE_LONGS a **sacrifié 47,96 $ de gains pour éviter 11,59 $ de perte** → **net −36,42 $**. Il n'y avait **aucun « LONG destructeur »** à ce checkpoint.

### CLOSE_ALL (3 longs + 5 shorts liquidés) — locked −16,03 $ vs KEEP +107,74 $ → **−123,77 $ sacrifiés**

| Symbole | Side | Verrouillé à D | PnL si KEEP | Δ | Sortie KEEP |
|---|---|---|---|---|---|
| OBDC | short | −26,15 $ | **+47,86 $** | **−74,01 $** | take_profit |
| HST | short | −8,32 $ | −13,66 $ | +5,34 $ (sauvé) | trailing_stop |
| MUR | long | +22,91 $ | +49,30 $ | −26,31 $ | take_profit |
| FLR | short | −8,97 $ | −31,41 $ | +22,44 $ (sauvé) | trailing_stop |
| FLS | short | −15,25 $ | −28,81 $ | +13,56 $ (sauvé) | trailing_stop |
| SM | long | +13,05 $ | +34,69 $ | −21,65 $ | take_profit |
| (+2 autres) | — | — | — | — | — |

**Lecture** : CLOSE_ALL ferme les shorts **perdants** (HST/FLR/FLS : +41,34 $ sauvés) **mais** sacrifie le short **gagnant** OBDC (+47,86 $ → take_profit) et les longs gagnants MUR/SM (+47,96 $). Bilan **−123,77 $**.

### Réponse à la question d'attribution
> *« CLOSE_LONGS gagne-t-il parce qu'il élimine de vrais LONG destructeurs ou juste une trajectoire favorable ? »*

**Ni l'un ni l'autre : il ne gagne pas du tout.** Les longs présents à D étaient des gagnants (MUR, SM en take_profit en KEEP), pas des destructeurs. CLOSE_LONGS cède des gains nets. CLOSE_ALL n'est pas meilleur : le seul short réellement « hedge » utile (OBDC, +47,9 $) est sacrifié pour sauver des shorts perdants mineurs. **La liquidation à −8 % n'élimine pas du risque, elle élimine du P&L.**

---

## 4. Test V-rebound (OBLIGATOIRE) — coût vs KEEP (équité en $)

| Horizon | KEEP | CLOSE_ALL | CLOSE_LONGS | Coût CLOSE_ALL | Coût CLOSE_LONGS |
|---|---|---|---|---|---|
| J+5 | 4 112,41 | 4 065,65 | 4 074,96 | **−46,76 $** | **−37,45 $** |
| J+20 | 4 292,21 | 4 121,02 | 4 128,30 | **−171,19 $** | **−163,91 $** |
| J+40 | 4 351,39 | 4 150,99 | 4 164,35 | **−200,40 $** | **−187,04 $** |
| J+60 | 4 654,27 | 4 407,63 | 4 445,08 | **−246,64 $** | **−209,19 $** |

**Lecture** : le crash de juillet 2025 est un **V-rebond** (KEEP reprend +16,9 % à J+60). Liquider au fond du V **rate le rebond** : le coût s'aggrave avec l'horizon jusqu'à **−246 $ (CLOSE_ALL) / −209 $ (CLOSE_LONGS)**. CLOSE_LONGS rate le rebond presque autant que CLOSE_ALL.

---

## 5. Gates

| # | Gate | Résultat | Verdict |
|---|---|---|---|
| G1 | DD post-checkpoint < KEEP substantiel ? | 7,71 / 7,96 % vs 8,33 % → gain **0,37–0,62 pt**, marginal | ❌ NON |
| G2 | CLOSE_LONGS ≥ CLOSE_ALL sur plusieurs épisodes ? | 1 seul épisode ; CLOSE_ALL (+18,82 %) > CLOSE_LONGS (+14,56 %) | ❌ NON |
| G3 | Pas uniquement 2022 ? | 2022 = **no-op** (aucun épisode) ; 2025 seul testé → **pénalise** | ❌ NON |
| G4 | SHORT hedge mesurable ? | Shorts utiles après D en KEEP (+455 $) ; OBDC faisait TP +47,9 $ — CLOSE_ALL le sacrifie | ❌ NON |
| G5 | Coût V-rebound acceptable ? | **−209 à −246 $ à J+60** | ❌ NON |
| G6 | Return/Sharpe pas détruits ? | Sharpe 2,03 → 1,86 → 1,51 ; return −1,3 à −5,6 pts | ❌ NON |
| G7 | Stable aux checkpoints −5/−8/−10 ? | Non testé (Vague 1), mais −8 % déjà négatif → extension non justifiée | ❌ NON |

---

## 6. Verdict

### 🔴 **NO-GO** pour CLOSE_ALL **et** CLOSE_LONGS à −8 %

**Cas 4 du protocole** : `KEEP > liquidation` → le force-close catastrophe B4 **side-aware à −8 % détruit de la valeur** et doit être **remis en question / abandonné**.

| Dimension | Conclusion |
|---|---|
| Effet sur le risque | Négligeable : DD 8,33 % → 7,71–7,96 % (≤ 0,62 pt), alors que le drawdown était déjà ~au plancher à D. |
| Effet sur le rendement | Négatif : −1,3 pt (CLOSE_ALL) à **−5,6 pt** (CLOSE_LONGS). |
| Attribution | Les positions liquidées étaient des **gagnants** (MUR, SM, OBDC en take_profit). Pas de « longs destructeurs » à éliminer. |
| V-rebound | Manqué par les deux politiques (−209 / −246 $ à J+60). |
| CLOSE_LONGS vs CLOSE_ALL | CLOSE_LONGS **le pire** (sacrifie les longs gagnants pour un gain de DD quasi nul). CLOSE_ALL moins mauvais (sauve des shorts perdants) mais **toujours perdant** (−123,77 $ de P&L vs KEEP). |
| 2022 (bear) | Aucun épisode à −8 % → rien à protéger ; le CP-V2 de-risque avant. |

**Recommandation** : **garder la règle B4 actuelle (KEEP)**. Ne **pas** activer de force-close side-aware à −8 %. Le bénéfice de DD est marginal et coûte 1,3 à 5,6 pts de rendement en ratant le rebond.

---

## 7. Limites & suites possibles

- **Un seul épisode exploitable** (2025-07). Le verdict repose sur un V-rebond unique — robuste pour rejeter CLOSE_LONGS (pire dans tous les cas), plus fragile pour généraliser CLOSE_ALL.
- **Extension −5 %** : seul moyen de rendre 2022 actif (DD max 5,66 %). Compte tenu du verdict −8 % (négatif sur le seul épisode testé), **l'extension n'est pas recommandée** — elle liquiderait encore plus tôt, donc manquerait d'autant plus les rebonds.
- **Hook research inerte en PROD** : `research_force_close_at_dd_pct=None` par défaut → aucun impact production. Rien n'a été modifié en PROD (vérifié : config.yaml inchangé, 3 fichiers modifiés = hook research + budgets CP-V2 déjà commités à 15:12).
