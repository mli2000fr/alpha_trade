# 07 — Adéquation Swing Trade — Fitness Assessment

## 1. Style cible

Swing trade actions US, horizon 2-15 jours, biais long, leaders Minervini/VCP,
gestion ATR-based, trailing stop dynamique, blackout earnings, swing-only
(pas de daytrade).

## 2. Grille d'évaluation par axe

| Axe | Note | Commentaire |
|---|---|---|
| Sélection alpha (qualité du book cible) | 7.5 | Multi-facteurs, neutralisation sectorielle, profils stricts unifiés. Risque univers vide aux seuils max (A-009). |
| Sizing | 7.0 | ATR strict — robuste mais nécessite télémétrie (A-010). |
| Diversification | 7.5 | Sector cap + correlation filter explicites par préset. |
| Protection drawdown | 5.5 | Circuit breaker non branché PnL réel par défaut (A-007). |
| Exécution | 7.5 | Synthetic Bracket OCO, audit trail complet, multi-comptes. |
| Trailing stop | 7.0 | `multiple_r` configurable, watcher post-run optionnel. |
| Earnings blackout | 7.5 | Présent et configuré par préset (2-4 jours). |
| Backtesting (parité live) | 5.5 | Convention ledger dividendes à confirmer (A-006). |
| Sentiment | 6.0 | FinBERT branché ; bénéfice empirique à mesurer. |
| ML | 6.0 | LSTM + governance ; gouvernance à muscler. |
| Realisme microstructure | 6.5 | Spread bps + IEX bias counters propagés ; quotes Alpaca toujours valides. |
| Petit compte cash (PDT-safe) | 6.5 | `swing_only=true` + `account_type=cash` cohérent ; investissabilité réelle limite. |
| Compte intermédiaire | 7.5 | Bonne progression jusqu'à 25k/50k. |
| Grand compte | 7.5 | Préset standard équilibré ; vigilance A-009. |
| Sécurité opérateur | 6.5 | Améliorations récentes ; check env multi-comptes manquant (A-008). |
| Supervision quotidienne (IHM) | 6.5 | Bonnes pages mais dette `_execution_center.py`. |

**Note swing trade fitness globale : 6.7 / 10**.

## 3. Verdict par tranche de capital

| Tranche | Investissabilité | Discipline risk | Réalisme exécution | Verdict swing |
|---|---|---|---|---|
| 0–5 000 $ | Limite (A-010) | OK mais drawdown global 15 % élevé (A-011) | Cash, OK | ⚠️ Swing **discipliné mais frustrant** |
| 5 001–10 000 $ | Limite-acceptable | OK | Cash, OK | ✅ Swing **acceptable** |
| 10 001–25 000 $ | Bonne | OK | Cash, OK | ✅ Swing **adapté** |
| 25 001–50 000 $ | Bonne | OK | Margin, OK | ✅ Swing **adapté** |
| 50 001–100 000 $ | Bonne (mod A-009) | OK | Margin, OK | ✅ **Sweet spot du système** |
| 100 001 $+ | Bonne (mod A-009) | OK (drawdown 15 % réaliste) | Margin, OK | ✅ **Adapté grand compte** |

## 4. Compatibilités réglementaires US

| Item | Statut |
|---|---|
| PDT (Pattern Day Trader) US | ✅ `execution_pdt_rule="off"` + `swing_only=true` partout |
| Cash account T+2 | ✅ presets ≤ 25k$ en cash |
| Margin account ≥ 25k$ | ✅ |
| Short selling | ❌ pas exposé (cohérent biais long) |
| Options | ❌ hors scope |

## 5. Risques métier majeurs

1. **Pipeline silencieux** (A-003) : runbook obsolète → décisions sur
   données rassies. **Bloquant pour live.**
2. **Circuit breaker inactif** (A-007) : fausse sécurité.
3. **Backtest sous-estimant les rendements** (A-006) : fausse confiance.
4. **Petit compte non investissable** (A-010) : utilisateur frustré.
5. **Univers vide** sur weekly_trend=1.0 (A-009) : pipeline stérile certains
   jours.

## 6. Conditions de passage en swing trading réel discipliné

L'application est **prête pour un swing trading réel discipliné** si et
seulement si :

- ✅ Anomalies P0 corrigées (A-001, A-002, A-003).
- ✅ Anomalies P1 majeures corrigées : A-006 (backtest), A-007 (CB), A-008
  (env), A-010 (télémétrie sizing), A-011 (overrides risk).
- ✅ Doc `doc/dataIntegrityEngine.md`, `data_lineage_matrix.md`,
  `corporate_actions.md`, README §6 mises à jour.
- ✅ Tests A-001/2/3/6/7/8/9/10/11 verts en CI.

→ Atteint **après le sprint S3 inclus** du plan (cf. `08_sprint_plan.md`).

## 7. Recommandations métier

- Documenter explicitement « **mode debutant** = préset 25k–50k » comme
  point d'entrée recommandé : meilleur compromis investissabilité /
  discipline.
- Pour les comptes < 10k, exposer dans l'IHM un **avertissement explicite** :
  « le pipeline peut générer 0 ordre sur certaines journées, c'est attendu ».
- Activer par défaut le **watcher post-run** (A-018) pour les comptes
  margin afin de promouvoir le trailing stop systématiquement.

