# Checklist d'amélioration du scanner swing

## Objectif
Amener `screener/` + `selector/` au niveau d'une checklist swing trading plus professionnelle, **sans inventer de données absentes**.

## Sources de données actuellement exploitables
- `stock_bars_daily` : OHLCV daily
- `stock_scores` : scores quantitatifs, qualité données, sentiment agrégé
- `stock_metadata` : univers tradable, secteur
- `event_sentiment/*` : signaux news / macro déjà calculés après le quant

## Critères à implémenter maintenant
- [x] Ajouter un filtre **ATR 20 en % du prix** (`atr_pct_20`) pour éviter les titres trop plats
- [x] Ajouter un filtre **force relative minimale vs SPY** (`relative_strength_index >= seuil`)
- [x] Ajouter un filtre explicite **prix au-dessus de la MA200**
- [x] Ajouter un filtre **proximité du plus haut 52 semaines**
- [x] Ajouter un filtre **alignement hebdomadaire** (weekly close > weekly MA10 et weekly MA10 > weekly MA30)
- [x] Exposer ces critères dans `AlphaScannerConfig`, le preset strict et la CLI
- [x] Ajouter les tests unitaires associés
- [x] Mettre à jour la documentation `doc/selector.md`

## Critères bloqués par manque de données dans le schéma actuel
- [ ] **Spread bid/ask** : impossible sans données de carnet ou quotes intraday
- [ ] **Market cap / mid-large cap** : non présent dans `stock_metadata` actuel
- [ ] **Beta > 1** : non calculé et non stocké
- [ ] **Earnings blackout (J-3/J+3)** : aucun calendrier earnings explicite dans le pipeline actuel

## État actuel après implémentation
- Le preset `strict` filtre désormais sur : liquidité, prix minimum, contraction de volatilité, ATR %, force relative, close > MA200, proximité du high 52w et alignement weekly.
- Les nouveaux facteurs sont calculés dans `selector/alpha_scanner.py` et validés par tests.
- Les critères encore bloqués nécessitent une extension de schéma et/ou une nouvelle source de données.

## Ordre d'implémentation
1. Config + preset strict
2. Facteurs ATR / weekly trend
3. Filtres swing explicites
4. Tests
5. Documentation

## Validation attendue
- Les tests existants `tests/test_selector_alpha_scanner.py` et `tests/test_alpha_scanner.py` restent verts
- De nouveaux tests couvrent ATR %, weekly trend et filtres swing explicites
- Le preset `strict` devient plus proche d'une checklist swing pro tout en restant déterministe


