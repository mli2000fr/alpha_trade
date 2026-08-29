# Corporate actions

Référence spécialisée : [dividendes, splits et réconciliation](operations/corporate_actions_reference.md).

Le module synchronise, applique et réconcilie dividendes et splits sur les positions. Il est volontairement séparé de l'ajustement des prix.

## CLI

```powershell
python -m corporate_actions sync --portfolio-only
python -m corporate_actions apply
python -m corporate_actions status
python -m corporate_actions run --portfolio-only
```

`sync` accepte symboles, scope all/portfolio, dates, batch size, compte et provider. Le scope portfolio-only est recommandé : il part des positions broker photographiées par l'exécution. `run` enchaîne sync puis apply.

## Architecture

- `provider.py` : interface et providers Alpaca/EODHD ;
- `models.py` : événements, applications, cash ledger, snapshot position ;
- `db_io.py` : repository ;
- `engine.py` : orchestration ;
- `processors.py` : règles dividend/split ;
- `reconciliation.py` : contrôle après application ;
- `cross_check_yahoo.py` : comparaison indépendante ;
- `cli.py` : garde-fous et commandes.

## Dividende

Un dividende éligible crée un crédit cash dans `portfolio_cash_ledger`, relié à l'événement et à l'application. Le traitement doit être idempotent : rejouer ne crédite pas deux fois. Le calcul dépend de la quantité détenue et des dates économiques pertinentes.

## Split

Un split ajuste quantité et cost basis de la position/lot sans créer artificiellement de PnL. La valeur notionnelle doit rester cohérente hors mouvement de marché. Les séries de prix étant split-adjusted, il faut éviter un double ajustement.

## États

Les événements ont un type et un statut ; l'application est enregistrée séparément. Les erreurs restent visibles et reprises de façon ciblée. La réconciliation vérifie positions, cash et invariants après traitement.
