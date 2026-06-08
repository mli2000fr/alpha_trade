# 20. Guide micro-compte ~2 000 € — paramétrage et bonnes pratiques

> Ce manuel est **incontournable** si vous démarrez avec ~2 000 € (~2 150 USD).

## ⚠️ Avertissement préalable

- L'investissement boursier comporte un **risque de perte totale**.
- Avec 2 000 €, **un seul mauvais trade mal géré peut amputer 10-20 %** de
  votre capital. La discipline (stops, sizing) est non négociable.
- Ce guide n'est **pas** un conseil financier.

## 1. Pourquoi un preset spécifique ?

Le moteur a été initialement calibré pour des comptes ≥ 50 000 USD. À
2 000 € :
- Les filtres standards rendent l'**univers presque vide** (moins de
  10 candidats certains jours).
- Les frais fixes broker (≈ 1 USD/ordre) **mangent l'alpha** sur des
  tickets < 200 USD.
- Avec 15 positions max, chaque ligne ferait 130 USD ⇒ frictions trop
  élevées.

Le preset `capital_0_2000_eur` (Sprint S26) corrige ces 3 points. Voir
[doc/audit/preset_petit_capital_2000eur.md](../audit/preset_petit_capital_2000eur.md)
pour le détail des valeurs.

## 2. Activation dans l'IHM

1. Page **🔄 Pipeline** → bandeau « Capital » :
   - **Soit** vous saisissez `equity = 2150 USD` → le preset est résolu
     automatiquement.
   - **Soit** vous forcez la clé `capital_0_2000_eur` dans le sélecteur.
2. Vérifiez que le label affiché est bien **« 0 → 2 000 € (micro-compte) »**.
3. Lancez le pipeline.

## 3. Ce que le preset impose

| Réglage | Valeur | Pourquoi |
|---|---|---|
| **3 positions max** | concentration | éviter dispersion frais fixes |
| **1.5 % risque/trade** | ~30 € | tolérable psychologiquement |
| **200 USD ticket min** | | frais < 1 % de l'ordre |
| **35 % max par ligne** | | cohérent avec 3 lignes |
| **55 % max par secteur** | | permet 2 lignes même secteur |
| **Cash account** | | capital réutilisable uniquement après settlement |
| **Swing only** | | aucun day-trade |
| **DD max 7 %** | | ~140 € de perte max temporaire (circuit breaker portfolio). |
| **Min market cap 500 M$** | | exclut micro-cap manipulables |

## 4. Backtester avec frais réalistes

Les frais par défaut du backtest sont **trop optimistes** pour un
micro-compte. Lancez :

```powershell
python -m backtesting run `
  --capital-preset-key capital_0_2000_eur `
  --equity 2150 `
  --commission-bps 25 `
  --slippage-bps   15 `
  --start 2022-01-01 `
  --end   2026-04-30
```

Métriques cibles à valider **avant** tout passage en paper :

| Métrique | Cible minimale |
|---|---|
| Nombre de trades | ≥ 50 |
| Sharpe ratio | ≥ 0.8 |
| Max drawdown | ≤ 20 % |
| Win rate × payoff | > 1.0 (espérance positive) |

## 5. Workflow conseillé sur 6 mois

| Mois | Activité | Capital engagé |
|---|---|---|
| **Mois 1-2** | Mode `simulate` quotidien, observer | 0 € |
| **Mois 3** | Mode `paper` quotidien, observer P&L | 0 € (paper) |
| **Mois 4** | `paper` continue, ajuster preset si besoin | 0 € |
| **Mois 5** | Si paper > 0 sur 3 mois consécutifs : **live avec 500 €** | 500 € |
| **Mois 6+** | Si live > 0 : monter progressivement vers 2 000 € | 1 000 → 2 000 € |

> 🛑 **Ne sautez aucune étape.** 95 % des débutants qui passent direct en
> live perdent leur capital en < 6 mois.

## 6. Limites à respecter (rotation, fiscalité)

### Rotation du capital

Avec un compte **cash**, le capital réellement réutilisable dépend du
settlement. Le preset impose donc un style **swing only** et un rythme de
rotation volontairement modéré.

### Fiscalité française

- Les plus-values sur actions US sont imposées **PFU 30 %** (12.8 % IR +
  17.2 % PS) en France.
- Vous **devez** déclarer votre compte étranger (Alpaca) chaque année
  (formulaire 3916).
- Les dividendes US subissent une retenue à la source 15 % (récupérable).

> Consultez un comptable. Cette doc n'est pas un conseil fiscal.

## 7. Ce qu'il ne faut **jamais** faire

| Action | Pourquoi pas |
|---|---|
| Désactiver les stop-loss | Ruine garantie |
| Augmenter `risk_per_trade_pct` à 5 % | 10 trades suffisent à perdre 50 % |
| Passer en margin trop tôt | risque de levier + discipline opératoire plus fragile |
| Trader des options / leveraged ETF | Risque non modélisé par l'app |
| Ignorer les corporate actions | Désynchronisation cash |
| Couper le watcher 24/7 en live | Plus de protection des positions |

## 8. Que peut-on espérer ?

Un swing trader débutant **discipliné** vise :
- 12-25 % de gain annuel **brut** (avant impôts) en moyenne
- Sur 2 000 €, cela représente **240-500 € de gain annuel**, mais avec une
  **volatilité élevée** (peut-être -300 € sur un mois, +600 € le suivant).

> Pour multiplier votre capital ×2 en 1 an, soit vous prenez beaucoup plus
> de risque (et vous risquez de perdre), soit ce n'est pas possible
> régulièrement.

## 9. Pour aller plus loin

- Workflow type journalier : [40_workflow_type_swing_2000eur.md](40_workflow_type_swing_2000eur.md)
- Sécurité argent réel : [52_securite_et_argent_reel.md](52_securite_et_argent_reel.md)
- FAQ : [50_faq.md](50_faq.md)
- Glossaire : [30_glossaire_financier.md](30_glossaire_financier.md)


