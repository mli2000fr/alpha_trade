# E8-A — Audit de l'historique options PIT

## Verdict

E8-A est terminé en `BLOCKED_NO_DENSE_PIT_HISTORY`. L'artefact canonique est :

```text
artifacts/research/options_pit_audit/options-pit-audit-20260910181810/report.json
```

Le blocage concerne les données, pas une erreur technique du harnais. E8-B —
event study quotidien `volatilité réalisée contre volatilité implicite` — n'est
pas autorisé avec le patrimoine local actuel.

## Périmètre audité

L'audit `modelFactory.options_pit_history_audit` est local, read-only et sans
appel réseau. Il inspecte les tables MySQL, collectes directionnelles,
checkpoints bruts, snapshots courants et rapports de volumes options.

## Résultat par source

### Base MySQL

Aucune table options, contrats, dérivés ou Greeks n'existe. Les données ne sont
donc pas historisées durablement dans l'application.

### Surface historique échantillonnée

| Mesure | Valeur |
|---|---:|
| événements demandés | 625 |
| dates distinctes | 8 |
| période | 2022-05-03 → 2025-07-08 |
| symboles | 155 |
| surfaces complètes | 323 |
| taux complet | 51,68 % |

Cette collecte possède strikes, expirations et quatre quotes permettant de
calculer des spreads à la clôture du signal. Elle franchit les gates de nombre
de symboles et de taux de complétude, mais échoue la profondeur temporelle :
8 dates contre 504 exigées. Elle a été créée pour tester une surface
directionnelle ponctuelle, pas pour valoriser quotidiennement un straddle de
l'entrée jusqu'à la sortie. L'IV y est approximée depuis les midpoints. L'IV,
les Greeks et l'open interest historiques observés ne sont pas présents.

### Snapshots courants

Deux petits fichiers couvrent 12 symboles et respectivement 22 et 44 contrats.
Les quotes bid/ask et l'open interest sont disponibles ; IV et Greeks sont
présents pour une partie des contrats. Ces valeurs décrivent uniquement le
snapshot du jour de collecte. Les joindre rétrospectivement serait une fuite.

### Capacité distante déjà démontrée

Les preuves locales antérieures montrent un référentiel historique `as_of`, des
quotes NBBO REST depuis le 7 mars 2022 et des snapshots courants enrichis.
L'archive minute était précédemment autorisée mais son catalogue répondait 502 ;
les archives complètes quotes/trades n'étaient pas incluses dans l'autorisation
testée. Cette capacité distante ne constitue pas un historique local.

## Gates E8-A

| Gate | Résultat |
|---|---|
| stockage persistant | échec |
| au moins 504 dates | échec : 8 |
| au moins 100 symboles | passe : 155 |
| complétude ≥ 40 % | passe : 51,68 % |
| bid/ask historiques ponctuels | passe |
| contrats historiques `as_of` | passe |
| valorisations entrée/sortie quotidiennes | échec |
| IV historique observée | échec |
| Greeks historiques | échec |
| open interest historique | échec |
| taux/dividendes/corporate actions | échec |

## Données minimales pour ouvrir E8-B

Un stockage futur doit avoir comme grain minimal `contrat × timestamp/date` et
conserver : sous-jacent, ticker option, date `as_of`, expiration, strike,
call/put, bid, ask, timestamp de quote et prix du sous-jacent. Sont fortement
recommandés : IV, delta, gamma, vega, theta, open interest, volume, taux sans
risque, calendrier de dividendes, ajustements de contrats et corporate actions.

Pour un POC causal exact, la période réaliste commence au 7 mars 2022 :

```text
close J       : Oracle OOF observable
open J+1      : paire choisie sans futur, achat aux asks
H3/H5/H10/H20 : valorisation des mêmes contrats aux bids
```

Sans quotes historiques aux deux horloges, aucun rendement option net fiable ne
peut être calculé. Une simple série IV ou un snapshot de chaîne ne suffit pas.

## Relation avec les anciens POC

E6-B1/B2 avait déjà testé, sur huit dates, des straddles ATM avec DTE adapté.
Tous les horizons étaient négatifs après ask→bid et commissions. E8-A ne rouvre
pas ce résultat : il vérifie si un historique assez dense existe pour tester
une formulation `réalisée − implicite`. La réponse locale est non. Ne pas
étendre le POC sans une source historique nouvelle et une confirmation OOS.

