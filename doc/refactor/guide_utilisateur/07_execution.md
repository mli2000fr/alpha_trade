# Page Execution — du portefeuille cible au broker

## Chaîne d’objets

```text
cible de risque → execution request → ordre broker → ordre enfant/protection
                                    → fill → position/lot → réconciliation
```

Chaque niveau a son identifiant et son statut. Ne pas conclure qu’une cible est
exécutée parce qu’une request existe, ni qu’un ordre accepté est rempli.

## Cohérence pipeline trades

Le premier contrôle rapproche les objets transmis entre pipeline, risque et
exécution. Une rupture de cohérence doit être résolue avant d’interpréter les
statuts broker : elle peut révéler une mauvaise sélection de run ou un flux
incomplet.

## Réconciliation J+1

La réconciliation compare l’état attendu et l’état broker après le cycle. Le
bloc de relance permet une action ciblée. Avant relance, relever compte, date,
dernier statut et divergence. Une différence peut venir d’un fill partiel, d’un
ordre rejeté/expiré, d’un ajustement, d’une corporate action ou d’une écriture
locale manquante.

## TCA agrégé

Le TCA mesure des coûts/écarts selon les formules implémentées. Les formules
actuelles ne sont pas toutes side-aware : ne pas interpréter automatiquement le
signe comme favorable/défavorable de manière symétrique long/short. Voir
[TCA et réconciliation](../execution/reconciliation_et_tca.md).

## Kill switch

Le kill switch annule les ordres ouverts pour le compte/mode ciblé. Il demande
un contexte, le choix dry-run/live et un motif. Avant activation réelle :

1. vérifier le compte et l’environnement ;
2. inventorier les ordres concernés ;
3. comprendre l’effet sur les protections ;
4. utiliser dry-run si l’incident le permet ;
5. saisir un motif exploitable en audit ;
6. contrôler les résultats et positions après l’action.

Annuler les ordres ouverts ne liquide pas nécessairement les positions et peut
retirer une protection. La supervision secondaire doit être vérifiée ensuite.

## Contraintes et protections

La page expose les contraintes, protections initiales et indicateurs de risque,
puis les contraintes de compte réellement appliquées. Cela permet de distinguer
une réduction antérieure du risque d’un ajustement imposé au moment de
l’exécution (fractionnement, capacité, buying power ou règle broker).

Les ordres enfants et protections doivent être rapprochés de l’ordre parent et
de la position. Un parent rempli sans protection attendue est une anomalie
prioritaire.

## Requests, ordres et fills

Pour chaque anomalie, suivre la filiation : request interne, identifiant broker,
statut, quantités demandée/remplie/restante, prix, timestamps et erreurs. Les
fills sont la source de réalisation ; plusieurs fills peuvent appartenir au
même ordre.

## Positions, lots et contexte compte

Les positions/détentions du run décrivent son périmètre. L’expander de contexte
compte montre volontairement des éléments hors scope strict du run : utile pour
réconcilier, dangereux si on les attribue au run sélectionné. Les lots sont
importants pour fiscalité, clôture et traçabilité.

## Réconciliation actionnable et événements

Le bloc actionnable priorise les divergences pouvant nécessiter intervention.
Les événements forment la chronologie technique/métier. Avant correction,
identifier le niveau source ; éviter de modifier directement la DB pour faire
disparaître un écart broker.

## Watcher protections

Le watcher est une supervision secondaire des protections. Son historique et
son état sont visibles ici et dans Supervision Ops. Un watcher actif ne dispense
pas de vérifier les ordres broker ; un watcher arrêté n’implique pas que les
protections déjà placées ont disparu.

## Checklist de fin

- toutes les requests attendues ont un état explicable ;
- les ordres et fills se rapprochent des cibles ;
- les positions broker correspondent à l’état local attendu ;
- les protections sont présentes ou leur absence est justifiée ;
- les écarts J+1 sont traités ;
- aucun ordre orphelin n’est ignoré ;
- compte, mode et run sont consignés.

Voir [Moteur d’exécution](../11_execution_et_protections.md) et le
[module exécution détaillé](../execution/README.md).
