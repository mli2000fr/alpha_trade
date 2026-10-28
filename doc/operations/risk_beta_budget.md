# Budget bêta rapporté au capital du compte

Adaptation demandée le 28 octobre 2026 après qualification des facteurs US.
Le but est de permettre de petites positions dans des titres sensibles au
marché, tout en limitant l'exposition cumulée du compte. Le seuil numérique
reste 1,20 ; les autres protections ne sont pas assouplies.

## Configuration active

```yaml
risk_management:
  max_portfolio_beta: 1.2
  beta_exposure_basis: account_equity
```

En mode `account_equity`, le budget consommé est :

```text
exposition bêta brute = somme(|notionnel de chaque position × bêta observé|)
                       / equity actuelle du compte
```

Les liquidités inutilisées contribuent zéro. Le capital emprunté n'augmente
pas le dénominateur : le levier augmente les notionnels et donc l'exposition.
Les expositions LONG, SHORT et de bêta négatif sont comptées en valeur
absolue, sans crédit de couverture supposé.

| Situation, capital 4 000 $ | Exposition mesurée |
| --- | ---: |
| Achat de 100 $ d'un titre à bêta 3 | 0,075 |
| Achat de 4 000 $ du même titre | 3,00 |
| Achat de 8 000 $ du même titre avec levier | 6,00 |

Il s'agit d'un budget de sensibilité historique au marché, pas d'une perte
maximale garantie ni d'une prévision de direction.

L'ancien mode `invested_capital` reste disponible pour comparaison : il
normalise les poids par le seul capital investi. Les configurations
historiques sérialisées sans ce champ gardent ce défaut historique ; elles
ne sont pas réécrites. La configuration opérationnelle YAML sélectionne
explicitement la nouvelle base. Un nouveau backtest doit conserver cette
valeur dans sa configuration figée pour être comparable au nouveau contrôle.

## Application aux entrées

L'étape 11 ne filtre plus un titre pour son seul bêta avant de connaître sa
taille. Après sizing, le contrôle prend en compte les positions observées,
les quantités restantes des ordres d'entrée et les nouveaux montants proposés.
Une sortie non exécutée n'accorde aucune réduction anticipée du risque. Une
entrée en attente sans prix limite qualifié bloque les nouvelles cibles.
Les montants proposés qui recouvrent une position sont réservés de façon
conservatrice comme entrées additionnelles ; aucun allègement n'est présumé.

Le watcher applique la même base après sa revalidation de quantité, avec les
positions et ordres du broker. Les ajouts Winner consomment également le
budget. Les approbations enregistrent `factor_beta_basis`,
`factor_beta_exposure` et `factor_beta_limit`, en plus de l'empreinte des
données. Une modification du code impose de recharger le watcher.

La concentration factorielle à 60 %, la diversification minimale de deux
facteurs et la corrélation à 0,70 gardent leurs définitions et leurs valeurs.
Les SL/TP/trailing, quantités maximales, budgets par trade, plafonds de levier,
concentration titres/secteurs et protections de drawdown ne sont pas modifiés.

## Prévalidation du compte PAPER principal

La lecture réelle des deux plans existants, à 16:10:48 Paris le 28 octobre,
sur un capital broker de 1 974,30 $, donne :

| Plan | Quantité examinée | Prix limite conservé | Exposition bêta au plafond d'achat | Décision |
| --- | ---: | ---: | ---: | --- |
| P | 1 | 142,89 $ | 0,2182 | Admissible à cet instant |
| OKTA | 1 | 232,85 $ | 0,2127 | Diversification insuffisante : 1 < 2 |

Cette prévalidation n'envoie pas d'ordre et ne promet pas de fill. Le watcher
rechargé reprend uniquement les plans déjà admis, avec de nouvelles
vérifications et les mêmes plafonds de prix. Aucun claim n'est effacé et
aucun plan n'est recréé pour forcer une reprise.

Preuves :
`artifacts/operations/factor_input_remediation_20261028/native_preview_account_equity.json`
et `artifacts/operations/beta_equity_20261028/reload_receipt.json`. Le service
a été reconnu READY à 16:13:28 Paris. Ses journaux sont dans
`artifacts/operations/beta_equity_20261028/watcher-cad92a02/`.

### Incident distinct au premier cycle après rechargement

Le cycle `watch-9f9c1a58bd974040` à 16:15 Paris a bien appliqué
`account_equity`. P passe la revalidation puis échoue à la journalisation
OMS avant l'appel de soumission broker : son `intent_id` Winner mesure
39 caractères, alors que `execution_order_requests.request_id` en accepte
32. La réservation durable devient `UNKNOWN` et le runtime ne renvoie pas
automatiquement le même achat. Ce blocage n'est pas un refus de bêta.

Vérification en lecture seule à 16:17:39 Paris : zéro demande d'ordre pour
le risque concerné, zéro position et zéro ordre ouvert chez le broker ;
la recherche du `client_order_id` exact ne trouve aucun ordre. Aucun claim,
identifiant d'intention ou état UNKNOWN n'a été effacé ou réécrit pour forcer
une nouvelle tentative. OKTA reste refusé pour diversification.
Preuve : `artifacts/operations/beta_equity_20261028/live_verification.json`.
L'utilisateur a ensuite demandé la correction de cet incident. Les
identifiants OMS et broker sont maintenant séparés ; une reprise unique
auditée de P conserve le client ID et l'opération historique. Voir
[la correction des identifiants et la reprise](winner_request_ids.md).

## Validation

294 tests ciblés passent sur le risque, ses configurations, les facteurs,
les snapshots opérationnels, Winner, son broker et le démarrage du watcher.
Les scénarios ajoutés vérifient petite position à bêta élevé, levier,
valeurs négatives, positions déjà détenues, ordres partiellement exécutés,
absence de crédit sur les sorties, refus des données manquantes et maintien
des contraintes de concentration/diversification. La prévalidation réelle
utilise uniquement SQL en lecture et GET broker.
