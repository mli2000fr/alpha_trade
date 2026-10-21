# B4 : remédiation numérique de la grille de risque

## État

Le 21 octobre 2026 : **187 tests passent**. Les quatre cas auparavant rejetés
passent désormais leurs audits stricts, ainsi que quatre pilotes couvrant
LONG/SHORT et 2025/2026. La grille complète v2 est **terminée : 576/576,
zéro échec**, en 21 min 23 s. Les sources, entrées, fichiers de chaque cas et
audits ont été revérifiés ; 576 marqueurs de fin distincts. Le bilan technique
final est `PASS_COMPLETED_RISK_GRID_REVIEW`. Cela ne vaut pas validation live.

## Cause établie

La v1 s'est terminée avec 572 cas audités et quatre échecs, tous SHORT 2025 :

- `2025-SHORT-SL5-TR15-H20-TP20` ;
- `2025-SHORT-SL5-TR20-H10-TP10` ;
- `2025-SHORT-SL5-TROFF-H10-TP10` ;
- `2025-SHORT-SL5-TROFF-H10-TP20`.

Le contrôle reconstruit indépendamment le cash et la valorisation. Dans le
premier cas, l'equity calculée était 2962,909589372622 USD et sa reconstruction
2962,909589372618 USD. Ces valeurs économiquement identiques différaient
d'environ 4e-12 USD. La comparaison stricte au creux déclenchait une fausse
rechute B4 : streak remis à zéro et allocation 10 % au lieu de 50 %.
Les autres cas avaient le même type de divergence d'état, parfois initiée
avant la première allocation différente observée.

## Correctif et limites

La fonction partagée `backtesting/adaptive_breaker.py` utilise pour B4/B4a
une tolérance monétaire : maximum de **0,000001 USD** et de 32 ULP des montants
comparés (ULP : résolution de leur représentation flottante). Elle s'applique
au déclenchement, au nouveau creux, à la rechute de trois points de drawdown
et aux seuils de récupération 25/50/90 %.

La tolérance protège les frontières de décision ; elle **n'arrondit pas**
le cash, les prix, les frais ou le PnL. Les seuils de risque et la stratégie
restent inchangés. Une vraie baisse de 0,00001 USD ou d'un centime reste
détectée ; une succession de petits écarts finit par déclencher si la baisse
cumulée depuis le creux dépasse la tolérance. B0/B1/B2/B3 sont inchangés.

Ce module sert aussi au risque de production : le correctif numérique y est
donc partagé. Aucun exécuteur, réglage live, batch, modèle, SQL ou ordre n'est
modifié. Ce n'est ni un nouveau plafond dur de DD, ni un arrêt journalier ajouté.
Les réserves du [protocole de risque](grille_intraday_risque_production_20261021.md)
restent applicables, notamment la fréquence quotidienne et la liquidation partielle.

**Le validateur de la grille n'a pas été assoupli.** Il reconstruit toujours
les flux, les sorties, le contexte et la trace B4. Une allocation 50 % ne peut
pas être acceptée comme équivalente à 10 %.

## Conservation et reproduction

Ancien dossier :
`artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v1`.
Ses résultats/protocole restent inchangés. `source-snapshot/` conserve les
cinq fichiers antérieurs concernés ; `source-snapshot-manifest.json` vérifie
leurs empreintes et celles du protocole et du rapport originaux.

Nouveau dossier :
`artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2`.
Toutes les entrées préparées v1 sont recopiées avec vérification d'empreintes,
y compris `production-risk.json` et `risk-regimes.parquet` : aucune relecture
opportuniste de config actuelle, ni recalcul du régime. Les 576 comptes annuels
sont recalculés. Pas de mélange de résultats d'anciennes et nouvelles versions.

Preuves bornées :

- `regression-risk-20261021-v2/report.json` : 4/4, zéro échec, les cas ci-dessus ;
- `smoke-risk-20261021-v2/report.json` : 4/4, zéro échec, LONG/SHORT 2025/2026 ;
- `artifacts/tmp/pytest-b4-v2-20261021.xml` : 187 tests réussis ;
- `tests/test_b4_numeric_stability.py` : bruit au creux, vraies baisses,
  accumulation, frontières de trip/récupération/rechute, parité des composants
  de production/backtest malgré des sommes différentes et non-régression B0–B3.

Les deux dossiers de pilotes se trouvent sous
`artifacts/research/us_intraday_protection_grid/`. Leur statut `SMOKE_COMPLETED`
ne signifie pas que toute la grille est achevée. Tests et audits techniques
faits par le même assistant, pas seconde revue humaine indépendante.

## Suivi

```powershell
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2/progress.json
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2/stderr.log -Tail 20
```

La finalisation complète est vérifiée : 576 cas réussis, zéro échec et
`final-review.json` avec `PASS_COMPLETED_RISK_GRID_REVIEW`, fichiers et audits
de chaque cas contrôlés. L'écart maximal de reconstruction cash/equity est
1,46e-11 USD. `annual-summary.csv` et `comparison-risk-vs-baseline.csv` sont
disponibles. Voir le [bilan économique exploratoire](grille_intraday_risque_production_resultats_20261021.md).
