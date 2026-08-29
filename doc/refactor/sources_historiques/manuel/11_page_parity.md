# 11. Page 🔀 Parité Backtest ↔ Live

## À quoi sert cette page

Comparer les décisions **simulées** (backtest) aux décisions **réelles**
(live/paper) sur la même période, pour vérifier que le moteur est cohérent.

## Pourquoi c'est utile

- Détecter les **drifts** entre la simulation et le réel (ex. un fix data
  qui change rétroactivement les candidats).
- Justifier au régulateur ou à un audit que vos backtests reflètent
  réellement le comportement de production.

## Lecture du rapport

Pour chaque jour :
- Nb candidats backtest vs live
- Nb décisions risk identiques / différentes
- Symbole-par-symbole : taux de match

Score global de parité : **> 95 % = sain**, **< 90 % = à investiguer**.

## Pour un débutant

Cette page est **secondaire** au début. Vous pouvez l'ignorer pendant les
premières semaines.

## Pour aller plus loin

- Doc technique : [doc/backtesting.md](../backup/backtesting.md) + sous-section
  parité.

