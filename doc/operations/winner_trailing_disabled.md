# Winner : trailing désactivé et suivi sans intraday inutile

Modification demandée et vérifiée le 28 octobre 2026, compte principal PAPER.

## Configuration

```yaml
winner_pyramiding:
  trailing_stop_pct: null
  reinforcement_enabled: false
```

`null` désactive uniquement le trailing. Le SL fixe, le TP, les quantités,
le budget de risque, les exécutions et l'échéance de détention restent actifs.

Pour une position détenue sans trailing ni renforcement, le runtime termine
sa vérification après réconciliation des ordres/fills, protection des lots et
contrôle de sortie à échéance. Il n'appelle plus le fournisseur de données
de marché. L'adaptateur `NativeWinnerMarket` applique aussi ce contrôle :
aucun téléchargement de bougies 5 minutes, aucune lecture de cotation temps
réel, aucune donnée fictive de substitution.

Le snapshot éventuel signale `market_data_required=false` et
`market_data_skip_reason=TRAILING_AND_REINFORCEMENT_DISABLED`.

Les confirmations d'une nouvelle entrée et les renforcements ou trailing
encore activés gardent leurs exigences de données. Les lectures du compte,
positions, ordres et fills chez le courtier continuent normalement. Le moteur
de backtest conserve les bougies intraday nécessaires à la simulation des
SL/TP ; cette correction ne supprime pas ces données d'exécution.

## Positions P et OKTA déjà ouvertes

Modifier le YAML ne réécrit pas une politique figée. Une opération explicite
a donc changé leur seul `policy.trailing_stop_pct`, de 0,10 à `null`, sous
verrou d'exécution du compte. La méthode PAPER
`WinnerCampaignStore.disable_trailing` conserve les autres paramètres et
ajoute une trace `policy_amendments` avec autorisation, heure UTC,
empreintes des politiques et preuve des protections.

L'enregistrement ordinaire du runtime refuse toujours toute modification des
politiques figées ou de ces traces. Une version obsolète, un compte différent
ou un ordre ambigu empêche l'amendement. Répéter un amendement déjà appliqué
n'ajoute pas de trace et ne réinitialise rien. Un stop déjà resserré garde son
prix ; la désactivation du trailing ne le desserre jamais.

La procédure bornée
`scripts/operations/disable_winner_trailing_20261028.py` vérifie les positions
et les ordres SL/TP avec des requêtes GET seulement. Elle ne soumet, annule
ou remplace aucun ordre broker. Le service PAPER est rechargé sous le même
verrou ; les protections restent déposées chez le courtier.

## Vérification réelle

Contrôle à **17:15:44 Paris le 28 octobre 2026** :

| Position | Quantité conservée | SL conservé | TP conservé | Trailing |
| --- | ---: | ---: | ---: | --- |
| P | 1 | 132,29 $ | 164,31 $ | désactivé |
| OKTA | 1 | 211,50 $ | 262,70 $ | désactivé |

Les identifiants broker SL/TP sont identiques à ceux d'avant la modification.
Les stops OCO sont confirmés `held` et les TP `new`. Les lots et opérations
sont inchangés. Les deux plans conservent H20 et la sortie à l'ouverture de
la 21e séance, actuellement le 25 novembre à 14:30 UTC / 15:30 Paris.

Le watcher est sain. Les cycles `watch-f595fbb4ecaa4b5a` et
`watch-def48a05aa724321` suivent chacun les deux plans, sans nouvel achat,
sans blocage ni erreur intraday. Zéro `MARKET_DATA_UNQUALIFIED`, HTTP 403 ou
circuit fournisseur ouvert dans le journal du service rechargé.

Preuves immuables :
`artifacts/operations/winner_trailing_off_20261028/864db590f13e48eca9677c07acbb199b/`.
Le dossier contient `states_before.json`, `protection_proof.json`,
`receipt.json`, `final_verification.json` et les journaux `watcher-a9a20844/`.

## Validation

230 tests ciblés passent : absence de collecte intraday/quote inutile,
maintien de la confirmation initiale et des données nécessaires aux autres
signaux, réconciliation d'un stop exécuté, sortie à échéance sans marché,
amendement audité conservant un stop resserré, refus de modifications non
autorisées et régressions du runtime, du broker, des liquidations et du
backtest intraday.
