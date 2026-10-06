# ADR-0004 — Règles d’exécution chinoises versionnées

- Statut : accepté pour la recherche et le backtest ; live différé
- Date : 19 septembre 2026
- Dépendances : ADR-0001 à ADR-0003

## Contexte

Les règles CN varient selon la place, le board, le statut du titre et la date. Un backtest réutilisant implicitement les règles US produirait des fills et un PnL non exécutables.

## Décision

Stocker des politiques versionnées avec périodes d’effet :

```text
exchange_mic
board_code
effective_from / effective_to
buy_lot_size
sell_odd_lot_policy
tick_size
same_day_sell_allowed
price_limit_up_pct / price_limit_down_pct
ipo_special_window
short_allowed
settlement_days
fee_profile
```

Le moteur CN doit modéliser au minimum :

- calendrier Shanghai/Shenzhen/Beijing ;
- T+1 sur les ventes lorsque applicable ;
- lots et arrondis ;
- suspensions et reprises ;
- limites hautes/basses et non-fills conservateurs ;
- corporate actions et ajustements ;
- devise CNY et FX PIT pour consolidation ;
- coûts et taxes selon leur période d’effet.

Le modèle SHORT est initialement un veto ou un score de risque. Il ne produit aucune vente à découvert tant que le canal, l’éligibilité, le prêt et les coûts PIT ne sont pas validés.

## Gates avant live

1. backtest CN validé avec scénarios conservateurs ;
2. symbologie broker réconciliée ;
3. shadow mode et rapprochement ;
4. limites de risque par marché ;
5. kill switch CN indépendant ;
6. autorisation explicite de l’opérateur.

## Rejeté

- Constantes réglementaires sans dates d’effet.
- Fill garanti à la limite de prix.
- Forward-fill rendant une suspension tradable.
- Activation automatique du short depuis un score ML.