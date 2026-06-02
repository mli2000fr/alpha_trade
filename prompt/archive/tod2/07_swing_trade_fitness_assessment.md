# 07 — Évaluation d’adéquation au swing trading réel

## Verdict métier

Alpha Trade est bien orienté **swing trading actions US** : timeframe daily, ingestion EODHD, filtres tendance/liquidité/spread/earnings, risk sizing, exécution overnight/cash/margin, `swing_only`, backtesting PIT et IHM opérateur. La base est supérieure à la plupart des applications personnelles.

**Aptitude actuelle : 8,1 / 10 en paper/simulation ; 7,4 / 10 en live réel discipliné.**

## Forces swing trade

- Daily OHLCV EODHD consolidé : meilleur que Alpaca/IEX pour volumes et liquidité.
- Filtres selector adaptés : `min_close`, ADV, ATR%, high 52w proximity, weekly trend, MA200, earnings blackout, spread.
- `execution_swing_only=true` dans les presets capital.
- Gestion cash/margin/PDT dans exécution et backtest.
- Corporate actions séparées proprement : split-only prices + cash ledger.
- Backtesting PIT avancé possible.

## Fragilités métier

| Sujet | Fragilité |
|---|---|
| Petits comptes | Trop concentrés et très sensibles aux frais/spreads. |
| Quotes IEX | Les spreads restent Alpaca/IEX, pas NBBO/SIP. |
| ML/sentiment | Valeur alpha non prouvée suffisamment par ablation. |
| Backtest | Parité production pas encore automatique. |
| Exécution | Processus local, sensible à interruption opérateur/machine. |
| Régimes marché | Market-aware utile mais peut rendre le pipeline non investissable ou bloquer sans compréhension opérateur. |

## Cohérence swing par module

| Module | Fitness swing | Commentaire |
|---|---:|---|
| Data OHLCV | 8,0 | EODHD et conventions split-only sont désormais beaucoup plus cohérents ; proxy VWAP reste à surveiller. |
| Screener | 7,7 | Bon premier filtre, avec meilleurs garde-fous IHM sur les runs lourds. |
| Selector | 8,0 | Filtres pertinents et plus crédibles pour leaders swing disciplinés. |
| Sentiment | 6,9 | Peut aider, avec gouvernance améliorée, mais bruit et coût restent élevés. |
| ML | 7,0 | Horizon 3–10 jours cohérent, gouvernance visible, validation encore à durcir pour un live plus ambitieux. |
| Risk | 8,0 | Sizing/contraintes cohérents et mieux adaptés aux petits comptes. |
| Execution | 8,2 | Garde-fous swing/live solides, approval token et run plan immuable appréciables. |
| Backtesting | 7,8 | Profil `production-parity` et replays renforcent la crédibilité. |
| IHM/Ops | 7,9 | Très utile pour piloter et superviser, malgré une UX encore dense. |

## Réponse aux questions clés

- **Est-ce cohérent ?** Oui globalement, surtout EODHD + split-only + CA ledger + swing_only.
- **Est-ce robuste ?** Oui, de façon crédible pour un usage discipliné. Les modules critiques sont bien mieux protégés ; les principales fragilités restantes sont l’orchestration locale et l’industrialisation sécurité/incident.
- **Est-ce maintenable ?** Oui, si la documentation est réalignée et si les tests de conventions deviennent bloquants.
- **Est-ce exploitable en production ?** Oui pour paper et live pilote très discipliné ; pas encore pour une montée en taille significative.
- **Est-ce vraiment adapté au swing trade réel ?** Oui, mais la preuve d’alpha ML/sentiment et la qualité quotes/spread doivent être durcies.

## Conditions minimales avant live réel

1. Exécuter plusieurs cycles paper complets 1→14 avec supervision quotidienne.
2. Comparer systématiquement paper vs backtest `production-parity`.
3. Garder le live initial sur un preset conservateur, capital pilote plafonné.
4. Versionner un workflow CI sécurité bloquant.
5. Finaliser des runbooks incidents exhaustifs (broker/provider/DB/partial fill).
6. Renforcer encore l’alerting centralisé et le monitoring incident.
7. Revalider périodiquement l’ablation sentiment/ML par régime avant montée en taille.

## Tests métier swing indispensables

- Parité selector live vs backtest PIT sur 20 sessions.
- Stress small account : frais, spread, gaps, settlement cash.
- Universe health : au moins N candidats après chaque filtre, sinon diagnostic actionnable.
- Execution dry-run vs paper : mêmes targets, mêmes contraintes, mêmes rejets.
- Corporate actions : split/dividend autour ex-date sans double comptage.
- Sentiment/ML ablation : performance avec/sans signal, par régime.

