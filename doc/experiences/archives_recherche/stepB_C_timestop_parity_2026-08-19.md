# 🟡 Étapes B + C — Time-stop parity test sur baseline post-fix TP + décision

**Date** : 2026-08-19
**Base** : baseline canonique post-fix TP (`cmp_b25_h20_{2025,2026}_postfix_tp_m8`)
**Méthode** : replay mécanique validé (match baseline vs officiel : **99% (2025) / 100% (2026)**) — seule différence : `time_stop` évalué en parallèle du trailing à partir de J20 (`max_business_days=20`, `min_tp_progress_ratio=0.5`, `near_zero=0.005`).

---

## Tableau parity

| Variante | 2025 Ret% | 2025 PF | 2025 DD% | 2025 ts | 2026 Ret% | 2026 PF | 2026 DD% | 2026 ts |
|---|---|---|---|---|---|---|---|---|
| **baseline (ts OFF)** | +4.28 | 1.04 | −11.43 | 0 | +11.84 | 1.31 | −4.69 | 0 |
| **time_stop J20 actif** | +4.30 | 1.05 | −12.11 | 8 | +12.43 | 1.33 | −4.42 | 1 |

## Détail des coupes time_stop

### 2025 — 8 positions coupées (toutes ≥ 20j)
- pertes évitées : 5 → **+$2 177**
- winners coupés : 3 → **−$2 156** (RYN +5.5%→−1.2%, OBDC +5.8%→+3.3%, USFD +1.7%→−0.3%)
- **Net ≈ +$20 (nul)** ; DD légèrement pire (−12.11 vs −11.43)

### 2026 — 1 position coupée
- perte évitée : 1 → **+$588**
- winners coupés : 0
- **Net +$588** ; DD amélioré (−4.42 vs −4.69)

---

## Décision (Étape C) : NE PAS CORRIGER — DOCUMENTER

**Critère appliqué** : corriger seulement si le time_stop est *bénéfique ou au minimum neutre ET réduit clairement les stagnants extrêmes sur plusieurs périodes*.

**Résultat** :
- 2025 : **strictement neutre** (net ≈ 0$), DD légèrement dégradé → coupe autant de futurs winners que de perdants.
- 2026 : **marginalement positif** (+0.6 pt, DD meilleur) mais 1 seule coupe.

→ Pas de bénéfice net robuste. **Le time_stop est redondant quand un trailing actif existe.**

### Verdict
1. **Laisser le comportement actuel** : `time_stop` neutralisé par la présence d'un ordre d'exit ouvert (trailing actif) — **comportement voulu**, pas un bug.
2. **Documenter explicitement** dans `config.yaml` et le doc go_live : « `time_stop` ne s'applique qu'aux positions SANS ordre d'exit actif (orphelines/manuelles) ; en P14 le trailing est LA protection. »
3. **Ne PAS toucher au code** (ni simulateur, ni watcher, ni watcher_replay).

### Note de prudence
- Le replay applique le time_stop au **close** (pas au niveau exact) et en parallèle du trailing — c'est une borne haute du bénéfice potentiel. Même à cette borne haute, le time_stop est neutre en 2025 → la conclusion est robuste.
- À laisser tel quel : la garde `has_open_exit_order_for_symbol` (`execution_engine/db_io.py:985`) et le court-circuit `exit_lifecycle_replay`.

## Fichiers
- Script : `scripts/b25_stepB_timestop_postfix.py`
- Rapports : `rebench_canonique_postfix_tp_2026-08-19.md` (A), `audit_execution_risque_r1_r4_2026-08-19.md` (R1-R4)
