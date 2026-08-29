# 6 — Consommation, stacking, cascade et filtre DIP

## Usages du Global Ranking

Les rangs peuvent :

- alimenter le stacking des modèles per-symbol/per-sector ;
- servir de baseline ou feature à Oracle Extreme selon l’ablation ;
- produire directement des prédictions synthétiques rank-driven ;
- classer un pool construit par Oracle/Global Direction ;
- alimenter backtests, diagnostics et stratégies de filtre persistant.

Ces usages ne doivent pas être confondus. Un même batch peut contenir plusieurs
horizons sans que chacun pilote la sélection live.

## Stacking

Lorsque `stacking_enabled` est actif, l’orchestrateur fusionne les rangs OOS dans
le cache cross-sectionnel. Il crée `global_rank_available`, mesure la couverture
et utilise `0.5` pour les dates non couvertes. Une couverture globale trop faible
peut désactiver le stacking ; des symboles à couverture très faible sont
signalés ou neutralisés selon les contrôles du chemin.

L’usage OOF est essentiel : injecter les prédictions in-sample du modèle global
dans un modèle local créerait une fuite de stacking.

## Synthèse rank-driven

`synthesize_global_rank_predictions.py` transforme l’horizon choisi en lignes
de `model_predictions`. Pour un `top_pct` par défaut de 10 % :

```text
rank >= 1 - top_pct  → long
rank <= top_pct      → short
sinon                → flat
```

Les champs sont construits ainsi :

- `predicted_proba = rank` ;
- long : `proba_long=rank`, `proba_short=1-rank` ;
- short : les mêmes valeurs sont stockées mais `predicted_side=short` ;
- `proba_flat=0` ;
- `source=global_rank_synth` ;
- `selected_model=global_ranking_synth` ;
- un run synthétique `__GLOBAL_RANK_SYNTH__` relie les prédictions au batch.

Ces colonnes réutilisent le schéma de probabilités, mais les valeurs proviennent
d’un percentile de rang non calibré. Il ne faut donc pas les lire comme des
probabilités statistiques comparables à celles d’un classifieur.

## Persistent Rank DIP live

Le filtre optionnel s’applique uniquement à la branche long. Un candidat top
rank doit satisfaire persistance et baisse ; sinon son côté devient `flat` et il
n’atteint pas risque/exécution. Le chemin live implémente la forme D0 directe.

Le `reclaim_ratio` n’est pas supporté par ce chemin live : s’il est fourni, il
est journalisé puis ignoré. Le backtest peut appliquer un reclaim via
`selector/dip_filter.py`. Activer le reclaim uniquement en backtest crée donc
une divergence de contrat qu’il faut nommer.

## Pool Oracle + B25

Le pipeline Global Direction peut charger H10/H20 depuis
`global_rank_history`, construire un pool Oracle, puis retenir les meilleurs
rangs. Ici Oracle qualifie l’extrémité/magnitude et Global Ranking ordonne le
pool ; aucun des deux ne doit être interprété comme direction absolue sans la
politique qui les combine.

## Dépendance Oracle

Oracle O1 peut inclure `global_rank_20`. Le dataset Oracle relit cette colonne
depuis la table SQL et ne la recalcule pas. O0/O2 peuvent fonctionner sans cette
feature. L’orchestrateur peut préremplir l’historique Global Ranking avant la
jointure afin d’éviter un dataset Oracle vide lorsque la dépendance est requise.

## Règle d’audit

Pour une décision, conserver : batch Global Ranking, horizon, rang, mode de
consommation, batch Oracle éventuel, filtre DIP, side synthétique, run de risque
et contrat backtest/live.

