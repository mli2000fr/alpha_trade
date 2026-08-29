# `report.json` et artefacts de backtesting

## Rôle

`report.json` est le contrat machine entre moteur, IHM, tests et analyses. Le producteur principal est `backtesting/report.py`. Le contrat minimal et sa validation résident dans `backtesting/report_schema.py`; `backtesting/report_schema_pydantic.py` offre un adaptateur Pydantic v2 optionnel.

## Structure racine

| Bloc | Statut | Rôle |
|---|---|---|
| `summary` | obligatoire | métriques agrégées |
| `params` | optionnel | configuration effective |
| `artifacts` | optionnel | sorties associées |
| `diagnostics` | optionnel | compteurs du simulateur |
| `run_metadata` | optionnel | reproductibilité |
| `fidelity` | optionnel | fidélité live/backtest |
| `corporate_actions` | optionnel | splits, dividendes et contrôles |
| `trade_export` | optionnel | métadonnées d’export des trades |

Les clés racine inconnues sont tolérées par défaut pour la compatibilité ascendante. `validate_report_payload(..., strict=True)` les refuse.

## Summary et unités

Le validateur exige `initial_equity`, `final_value`, `total_return_pct`, `sharpe_ratio`, `max_drawdown_pct`, `total_trades` et `win_rate_pct`. CAGR, Sortino, durée moyenne, profit factor, Calmar, Ulcer index et ventilations directionnelles sont facultatifs.

`profit_factor` accepte un nombre ou `"inf"`. L’adaptateur Pydantic convertit les variantes positives et négatives d’infini en flottants. Les champs `_pct` sont des pourcentages, pas des fractions implicites.

## Paramètres

`MicrostructureParamsSchema` décrit modèle/base/impact du slippage, stop initial, gap maximal, priorité intrabar et `is_default`. `RiskOverlayParamsSchema` décrit sizing, filtre de régime, cap sectoriel, breaker de drawdown, reprise et cible de volatilité. Ces blocs photographient la configuration ; les compteurs de `diagnostics` indiquent ce qui s’est produit.

## Diagnostics

Le schéma connaît sorties same-day bloquées, cash/gap bloqués, day trades, sorties stop initial/TP/trailing, régime, cap sectoriel et breaker. Un champ absent devient zéro. Zéro signifie « aucun événement enregistré par ce producteur », pas nécessairement « fonction désactivée » : croiser avec `params`, `fidelity` et les logs.

## Reproductibilité

`run_metadata` conserve selon le producteur commit, Python, plateforme, seed, hash dataset et horodatage. Les modèles existants acceptent historiquement `generated_at` ou `timestamp_utc`; un consommateur doit tolérer cette différence. Pour reproduire, archiver aussi config effective, univers PIT, batches ML, fingerprints, période et données.

## Validation

```python
import json
from backtesting.report_schema import validate_report_payload

payload = json.loads(path.read_text(encoding="utf-8"))
report = validate_report_payload(payload)
```

Avec Pydantic, vérifier `HAS_PYDANTIC` puis utiliser `PydanticBacktestReport.model_validate_json(text)`.

## Pièges

- ne pas comparer des contrats d’exécution différents ;
- ne pas déduire une parité live de la présence de `fidelity` ;
- gérer les sentinelles infinies ;
- conserver les artefacts référencés avec le rapport ;
- distinguer compteurs d’exits et attribution économique ;
- ne pas présenter un ancien rapport comme performance active.

`tests/test_report_schema_pydantic.py` couvre l’adaptateur. Toute nouvelle clé obligatoire doit préserver la lecture des rapports antérieurs ou introduire une version explicite.

