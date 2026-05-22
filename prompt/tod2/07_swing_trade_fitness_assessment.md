# 07 — Évaluation d’adéquation au swing trading réel

## Verdict métier

Alpha Trade est bien orienté **swing trading actions US** : timeframe daily, ingestion EODHD, filtres tendance/liquidité/spread/earnings, risk sizing, exécution overnight/cash/margin, `swing_only`, backtesting PIT et IHM opérateur. La base est supérieure à la plupart des applications personnelles.

**Aptitude actuelle : 7,0 / 10 en paper/simulation ; 6,2 / 10 en live réel discipliné.**

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
| Data OHLCV | 7,5 | EODHD améliore les volumes ; proxy VWAP à surveiller. |
| Screener | 7,0 | Bon premier filtre ; dépend upstream. |
| Selector | 7,5 | Filtres pertinents pour leaders swing. |
| Sentiment | 5,8 | Peut aider, mais bruit élevé. |
| ML | 5,8 | Horizon 3–10 jours cohérent, validation insuffisante. |
| Risk | 7,2 | Sizing/contraintes cohérents. |
| Execution | 7,4 | Garde-fous swing solides. |
| Backtesting | 6,8 | Bon potentiel, parité à renforcer. |
| IHM/Ops | 6,8 | Utilisable, mais dense. |

## Réponse aux questions clés

- **Est-ce cohérent ?** Oui globalement, surtout EODHD + split-only + CA ledger + swing_only.
- **Est-ce robuste ?** Partiellement. Les modules critiques sont protégés, mais les processus longs et le fallback provider restent fragiles.
- **Est-ce maintenable ?** Oui, si la documentation est réalignée et si les tests de conventions deviennent bloquants.
- **Est-ce exploitable en production ?** Pas encore en taille significative. Paper et petit live pilote uniquement après P0/P1.
- **Est-ce vraiment adapté au swing trade réel ?** Oui, mais la preuve d’alpha ML/sentiment et la qualité quotes/spread doivent être durcies.

## Conditions minimales avant live réel

1. Corriger/documenter `fallback_on_failure`.
2. Corriger docs provider-aware.
3. Ajouter preflight OHLCV source EODHD.
4. Exécuter un cycle paper complet 1→14 sur plusieurs semaines.
5. Comparer paper vs backtest production parity.
6. Activer alerting run_summary et incident runbook.
7. Limiter live initial à preset conservateur, pas micro-compte agressif.

## Tests métier swing indispensables

- Parité selector live vs backtest PIT sur 20 sessions.
- Stress small account : frais, spread, gaps, settlement cash.
- Universe health : au moins N candidats après chaque filtre, sinon diagnostic actionnable.
- Execution dry-run vs paper : mêmes targets, mêmes contraintes, mêmes rejets.
- Corporate actions : split/dividend autour ex-date sans double comptage.
- Sentiment/ML ablation : performance avec/sans signal, par régime.

