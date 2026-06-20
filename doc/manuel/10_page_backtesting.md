# 10. Page 🧪 Backtesting — tester sur l'historique

## À quoi sert cette page

Simuler la stratégie sur **plusieurs années passées** pour mesurer ses
performances **avant** de risquer un euro réel.

## Pourquoi c'est crucial

Avant tout passage en paper ou live, vous **devez** avoir vérifié sur
backtest que :
- la stratégie a une **espérance positive** (gain moyen > 0),
- le **drawdown maximum** est tolérable (perte temporaire vs sommet),
- le **nombre de trades** est suffisant (statistique fiable).

## Lancer un backtest

### Pas-à-pas

1. **Période** : choisir start (ex. `2022-01-01`) et end (`2026-04-30`).
2. **Capital** : entrez votre capital (ex. `2150 USD` pour 2 000 €).
3. **Preset** : sélectionnez `capital_0_2000` si applicable.
4. **Frais** :
   - Commission `--commission-bps` : **25** pour micro-compte (vs 5 défaut)
   - Slippage `--slippage-bps` : **15** pour micro-compte (vs 5 défaut)
5. Cliquez **« 🚀 Lancer le backtest »**.

⏱️ Comptez **5 à 30 minutes** selon la période et le nombre de candidats.

### Suivi en temps réel

Une barre de progression s'affiche, plus les logs.

### Lecture du rapport

À la fin, le rapport contient :

| Métrique | Bonne valeur cible |
|---|---|
| **CAGR** (taux annuel composé) | > 10 % |
| **Sharpe ratio** | > 1.0 (excellent > 2) |
| **Sortino ratio** | > 1.5 |
| **Max drawdown** | < 20 % (idéalement < 15 %) |
| **Win rate** | > 45 % (acceptable même 35 % si payoff > 2) |
| **Payoff ratio** | > 1.5 |
| **Nombre de trades** | > 100 (statistique fiable) |

> 💡 Un Sharpe de 0.5 sur 50 trades en 2 ans **n'est pas** statistiquement
> significatif. Étendez la période.

## Sous-onglets disponibles

### Sous-onglet « Run » (principal)

Décrit ci-dessus.

### Sous-onglet « Backfill scores history »

Permet de recalculer rétroactivement les `final_score` du Selector sur une
fenêtre passée. Utile pour préparer un backtest qui inclut le sentiment
calibré rétroactivement.

### Gaps connus

Les sous-commandes CLI suivantes ne sont pas encore exposées dans l'IHM
(cf. [matrice IHM↔CLI](../audit/matrice_ihm_cli.md)) :
- `diagnose-screener` : pourquoi 0 candidat ?
- `recommend-screener` : recommandations automatiques
- `calibrate-sentiment-weights` : calibration des poids sentiment
- `walk-forward-sentiment` : walk-forward dédié sentiment

En attendant, ouvrez PowerShell et lancez :
```powershell
python -m backtesting diagnose-screener --start 2022-01-01 --end 2026-04-30
```

## Walk-forward

L'option **« Walk-forward »** divise la période en N fenêtres glissantes
(train → val → test). C'est la méthode la plus rigoureuse pour évaluer
une stratégie. **Activez-la systématiquement** sauf pour un backtest
exploratoire rapide.

## Pièges courants

- ❌ Backtest sur 6 mois seulement → trop court, pas significatif.
- ❌ Frais à 5 bps sur micro-compte → résultats artificiellement bons.
- ❌ Optimiser 50 paramètres jusqu'à trouver le meilleur Sharpe → c'est de
  l'overfitting massif. Le live sera décevant.
- ❌ Comparer 2 backtests qui n'ont pas le même `start`/`end` → biais.

## Pour aller plus loin

- Doc technique : [doc/backtesting.md](../backtesting.md).
- Parité backtest ↔ live : [11_page_parity.md](11_page_parity.md).

