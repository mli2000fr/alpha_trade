# Étape 12 — ancien import ADV/volatilité, 28 octobre 2026

## Incident

Le journal du run risque `404615885b1041ac`, filtre
`opt-917380c30aab40cbb99362b3ead15e7c`, séance signal du 27 octobre, présente
deux problèmes indépendants :

- Alpaca refuse les dernières quotes SIP par HTTP 403, faute de droits au
  temps réel ; le contrôle désactivé à l'étape 11 n'annule pas les contrôles
  distincts avant envoi d'ordre de l'étape 12.
- `_load_pre_submission_adv_vol` importe l'ancienne classe `RiskDbIo`, absente
  de `risk_management.db_io`. Cet import, placé avant le traitement d'erreur,
  interrompt l'exécution avant le moteur de soumission.

## Correctif

Le chargement utilise désormais le composant canonique **`RiskRepository`**,
méthode `load_prices_asof(symbols, trade_date, atr_window=20)`. Le choix du
fournisseur daily existant et la borne J sont conservés ; aucune lecture de la
séance J+1 encore non ouverte n'est demandée.

Une liste vide ne crée pas de dépôt SQL. Si le dépôt échoue, les dictionnaires
restent vides, sans inventer ADV ou volatilité. Les nombres non finis, ADV
négatifs/nuls et prix non positifs ne sont pas transmis comme données valides.
L'estimation existante ATR/close conserve son unité en fraction (0,02 = 2 %).

Les contrôles de spread ne sont pas assouplis. Le HTTP 403 reste un blocage
de données pour les nouvelles entrées nécessitant cette cotation ; le correctif
d'import n'accorde pas de droits API et ne transforme pas l'absence en GO.

## Vérification réelle bornée

Lecture seule de la base, sans appel d'exécution, pour **2026-10-27** :

| Symbole | ADV USD | ATR/close |
|---|---:|---:|
| OKTA | 662 248 847,57 | 0,04956, soit environ 4,96 % |
| P | 548 673 986,62 | 0,05659, soit environ 5,66 % |

Ce sont des entrées calculées par le dépôt, pas une qualification du bid/ask
actuel ni une autorisation d'achat. Aucun compte modifié, aucun ordre envoyé,
aucun run d'exécution relancé, aucun ancien verrou supprimé.

Les tests couvrent l'API de dépôt correcte et la date J, le cas sans cible,
les erreurs SQL et les valeurs invalides. Le refus de pré-soumission sans
spread reste vérifié. Les tests de quotes Tradier utilisent une horloge figée,
afin que leur fraîcheur ne dépende pas de la durée des autres tests.
**175 tests passent** sur le chargement corrigé, le lancement de l'exécution,
les précontrôles, le watcher automatique, les quotes Tradier/SIP et la liquidité.
