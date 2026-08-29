# Réconciliation, reprise et Transaction Cost Analysis

Retour : [références Execution](README.md)

## Pourquoi réconcilier

Le broker est la vérité des exécutions observées ; la base locale porte l’intention, la causalité et l’audit. Une coupure entre soumission et réponse peut laisser un ordre accepté au broker mais inconnu localement. La réconciliation converge les deux mondes sans renvoyer aveuglément l’ordre.

`broker_state_sync.py` photographie compte, positions, ordres et fills. `reconciliation.py` compare targets, état interne et broker. `reconcile_statement.py` rapproche aussi les relevés. Les résultats sont persistés par run et compte.

## Entrées de la réconciliation

`reconcile_execution_state()` reçoit run id, account id, targets, positions broker, positions internes, ordres ouverts internes/broker, protections, tolérance de quantité et buying power éventuel.

Les symboles sont normalisés en majuscules et les quantités par `normalize_share_quantity`. La tolérance effective ne descend jamais sous `QUANTITY_EPSILON`, indispensable aux fractions et arrondis.

Le périmètre est l’union des symboles présents dans targets, broker, interne, ordres ouverts et protections. Une position broker sans target reste donc visible.

## Calcul et actions

`position_delta = broker_qty - target_qty`.

| Condition | Action |
|---|---|
| delta dans tolérance | `none` |
| broker et target de signes opposés | `side_flip` |
| symbole absent des targets | `investigate` |
| broker au-dessus de la cible | `sell_excess` |
| broker sous la cible | `buy_more` |

Les raisons additionnelles sont `internal_position_mismatch`, `open_orders_in_flight`, `missing_protection` et `insufficient_buying_power`. Une position long broker sans protection ouverte déclenche le contrôle de protection dans l’implémentation actuelle.

## Statuts d’action

- `SAFE_AUTO` : action calculée sans raison bloquante ou ambiguë ;
- `MANUAL_REVIEW` : symbole à investiguer, état interne divergent ou ordres en vol ;
- `BLOCKED` : buying power insuffisant ou protection manquante.

Le statut ne signifie pas que l’action a déjà été exécutée. Il classe la possibilité de correction. `side_flip` exige une séquence fermer puis ouvrir respectant les règles de protection et ne doit pas être réduit à une quantité nette envoyée sans contrôle.

## Reprise après incident

1. Geler les nouvelles entrées sur le compte.
2. Lire compte, positions, ordres ouverts et fills directement au broker.
3. Rechercher les client order ids avant toute nouvelle soumission.
4. Adopter/importer les ordres orphelins observables.
5. Rejouer les fills manquants de façon idempotente.
6. Reconstruire positions et lots.
7. Restaurer ou vérifier les protections.
8. Rapprocher cash, buying power et statement.
9. Relancer la réconciliation et n’ouvrir qu’après absence d’écart critique.

Un timeout broker ne prouve jamais qu’un ordre a échoué. La recherche par identifiant précède le retry.

## TCA : formules réellement utilisées

`execution_engine/tca.py` calcule :

- `slippage_bps = (fill_price - decision_price) / decision_price × 10 000` ;
- `implementation_shortfall = (fill_price - decision_price) × qty`.

Si le prix de décision vaut zéro, le slippage retourne 0 pour éviter une division ; ce cas doit néanmoins être signalé comme qualité de donnée, car 0 bps ne signifie pas exécution parfaite.

La formule n’oriente pas selon le côté : avec une quantité toujours positive, un achat plus cher donne un coût positif, mais une vente moins chère produit aussi une valeur négative. Toute agrégation interprétée comme « coût défavorable positif » doit intégrer le côté en amont ou séparer achats et ventes. Ne pas attribuer au code une orientation side-aware qu’il n’a pas.

## Agrégats

`build_tca_summary()` fournit nombre de fills, notional total, slippage moyen non pondéré, maximum absolu, shortfall total et nombre d’alertes dépassant `max_slippage_bps`. Le seuil par défaut CLI est 30 bps et la configuration valide [0,500].

`build_tca_aggregate_frame()` peut grouper par dimensions telles que mois, côté ou bucket et calcule fills, symboles, runs, quantité, notional, moyenne, maximum absolu et shortfall. Les buckets utilisent la valeur absolue : 0–10, 10–25, 25–50 et >50 bps.

La moyenne actuelle est une moyenne par fill, non pondérée par notional. Pour comparer des périodes, présenter aussi notional, distribution et quantiles afin qu’un petit fill ne pèse pas comme un gros sans le signaler.

## Ce que la TCA ne mesure pas seule

- ordres non remplis et coût d’opportunité ;
- délai entre décision et soumission séparément du fill ;
- spread payé contre impact marché ;
- changement de prix dû au marché pendant l’attente ;
- commissions/frais si absents du payload ;
- qualité de la référence de décision.

Ces composantes nécessitent des timestamps et benchmarks supplémentaires. Ne pas les confondre avec le slippage fill-versus-decision existant.

## Tolérances et criticité

La tolérance de quantité doit refléter fractional trading et normalisation commune. Une tolérance trop grande masque un risque, trop petite crée des faux positifs. Buying power est comparé à `abs(delta) × entry_price` pour une action `buy_more`.

Sont critiques : position broker inconnue, side flip non expliqué, protection manquante, ordre en vol ambigu, cash divergent et fill non adopté. Un écart critique non résolu empêche de déclarer le run sain.

## Diagnostic

| Écart | Recherche |
|---|---|
| broker ≠ interne | fills absents, adoption orpheline, ordre partiel |
| broker ≠ target | ordre ouvert, rejet, arrondi, buying power |
| protection absente | watcher, ordre bracket/stop, quantité protégée |
| shortfall extrême | decision price, split, côté, timestamp |
| TCA à zéro | absence de fills ou decision price nul |
| symbole sans target | position héritée, autre run ou mauvais compte |

## Tests attendus

Tester quantité entière/fractionnaire, tolérance zéro, position broker seule, side flip, ordres en vol, protection absente, buying power insuffisant, double import de fill, prix de décision nul, seuil de slippage, buckets et agrégats vides.

