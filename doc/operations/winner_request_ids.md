# Identifiants Winner : OMS et courtier

Correction du 28 octobre 2026 après l'échec local de l'entrée PAPER de P.

## Contrat corrigé

Les colonnes `request_id` des demandes, ordres et fills, ainsi que
`parent_request_id`, acceptent 32 caractères. Winner réutilisait à tort son
identifiant courtier de 39 caractères comme identifiant SQL.

`execution_engine.winner_broker.make_intent` distingue désormais :

- **Identifiant OMS** : `request_key(key)`, 32 caractères hexadécimaux dérivés
  de SHA-256 avec le domaine `winner-oms:`. Les relations parent/protections/fills
  utilisent cet identifiant.
- **Identifiant courtier** : `client_key(key)`, forme historique `wp-` suivie
  de 36 caractères hexadécimaux. `submission_key` et `idempotency_key` le
  conservent, afin que la recherche et la détection des doublons chez le
  courtier restent identiques.

Les intentions déjà enregistrées ne sont pas réécrites automatiquement.
Aucun élargissement de colonne SQL n'est nécessaire. Le contrôle anti-doublon
des stops de secours utilise l'identifiant courtier durable plutôt que de
supposer qu'il est égal à l'identifiant OMS.

## Reprise unique de P

Périmètre exact : compte principal `default`, PAPER, campagne
`wp-92e5c4eaa6d6365742c3f7e84633255a03827604`, risque
`404615885b1041ac`, exécution `619852eab35b421e`.

L'opération du 28 octobre à 15:15:30 UTC avait échoué sur l'insertion SQL
1406, avant la soumission broker. La vérification, sous verrou d'exécution
du compte et verrou du filtre exact, a exigé : zéro demande/fill canonique,
zéro position, zéro ordre ouvert, zéro ordre/fill du jour chez le broker,
recherche absente du client ID exact, journal de l'erreur locale et état
intact de la campagne. Une réponse 404 seule n'autorise jamais la reprise.

Le 28 octobre à 16:29 Paris, l'opération historique a été conservée avec son
ancienne intention, marquée `ABORTED_BEFORE_SUBMIT` et liée à la preuve. Une
seule nouvelle tentative initiale est permise, sous nouveau contrôle natif du
watcher. Les parents historiques sont conservés. Aucun claim d'exécution,
plan admis, quantité, prix limite ou protection n'est effacé ou modifié.

| Élément | Valeur conservée ou corrigée |
| --- | --- |
| Client ID broker | `wp-201e493bb116ce0822af4fa0a6c81ead44da` — inchangé |
| Nouvelle demande OMS | `3693228584234d4658105aa5847e48b0` — 32 caractères |
| Quantité maximale du plan | 1 action |
| Prix limite DAY | 142,89 $ |

La réparation ne soumet pas directement d'ordre. Le service PAPER rechargé
reprend le plan après ses contrôles habituels. La procédure est à usage
unique et refuse une campagne déjà réparée ou présentant un effet broker.

Preuves immuables :
`artifacts/operations/winner_request_id_20261028/36d964b1ba3c443483fcebe12f29d1df/`.
Ce dossier contient l'état antérieur, la preuve, le reçu de réparation et les
journaux du service `watcher-deee06a4`. La procédure bornée est
`scripts/operations/recover_winner_request_id_20261028.py` ; son lancement sans
`--apply` ne réarme aucun plan.

## Pourquoi OKTA était initialement refusé

Le contexte factoriel observé pour la séance du 27 octobre attribue le risque
d'OKTA aux composantes suivantes :

| Composante du modèle | Contribution au risque total |
| --- | ---: |
| Variations spécifiques au titre, résidu du modèle | 80,63 % |
| Momentum | 10,99 % |
| Marché | 8,18 % |
| Taille | 0,20 % |

`risk_management.min_factor_diversification: 2` exige deux facteurs communs
dont chacun contribue à plus de 10 % du risque total. Seul le momentum
franchit ce seuil. Le résidu spécifique ne compte pas comme un facteur
commun. Le contrôle renvoie donc `final_factor_diversification:1<2`.

Cette règle porte sur les sources de risque estimées par le modèle ; elle
n'est pas un compte de titres, de secteurs ou une prévision baissière. Elle
peut être contraignante pour une première position. Sa valeur, le seuil de
10 % et les autres limites de risque restent inchangés lors de cette correction.

## Résultat après reprise du watcher

À 16:31 Paris le 28 octobre, le watcher a exécuté une seule entrée PAPER par
titre, avec les mêmes plans et plafonds : P, 1 action à 139,25 $ ; OKTA,
1 action à 222,63 $. Les demandes OMS utilisent les identifiants de 32
caractères et leurs liens de protection sont persistés. L'ancien échec de P
reste dans l'historique avec le statut `ABORTED_BEFORE_SUBMIT`.

OKTA est devenu admissible après l'entrée de P : le risque contrôle le
portefeuille complet, pas une exigence individuelle figée pour chaque titre.
À 16:33 Paris, ses contributions communes combinées sont marché 20,03 %,
momentum 19,41 %, taille 0,32 % ; le spécifique représente 60,24 %. Deux
facteurs dépassent maintenant 10 %. Ni le minimum de deux facteurs ni les
autres seuils n'ont été modifiés pour obtenir ce résultat.

La vérification directe des ordres broker à 16:33:49 Paris confirme :

| Position | Stop OCO, état broker `held` | TP OCO, état broker `new` |
| --- | ---: | ---: |
| P, 1 action | 132,29 $ | 164,31 $ |
| OKTA, 1 action | 211,50 $ | 262,70 $ |

Ces prix proviennent des politiques Winner figées à l'admission, conservées
par la réparation. Le watcher est sain. Les contrôles intraday SIP continuent
toutefois à recevoir des 403 avec les droits actuels : les ajustements
dynamiques qui exigent ces données restent bloqués, sans suppression des
protections OCO déjà déposées. Les lectures du broker et la réconciliation des
fills restent accessibles. Aucune donnée IEX ou cotation fictive n'est
substituée pour qualifier le suivi.

Preuves : `live_verification.json` et `protection_verification.json` dans le
dossier de reprise ci-dessus. Les journaux montrent également une tentative
de trailing générique rejetée par le broker pour quantité déjà réservée ;
elle n'a pas remplacé ni annulé les stops OCO vérifiés.

À la demande suivante, le trailing figé de P et OKTA a été désactivé et la
collecte intraday inutile supprimée pour ces positions. Les cycles rechargés
ne produisent plus les 403 décrits ci-dessus. Les stops/TP et l'échéance sont
conservés : voir [la désactivation auditée](winner_trailing_disabled.md).

## Validation

169 tests ciblés passent : contrat SQL de 32 caractères avec clés étrangères,
stabilité du client ID, liens entrée/TP/SL/fills, arrêt avant HTTP sur erreur
SQL, absence de réenvoi après réponse perdue, stop de secours unique, reprise
auditable avec nouveau contrôle de risque et refus de libérer une tentative
ambiguë. Le runtime générique ne réarme jamais automatiquement un UNKNOWN.
