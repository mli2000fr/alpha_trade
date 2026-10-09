# Sprint 17-D — Réconciliation synthétique et clôture des accès en lecture

## Situation au 9 octobre 2026 (Paris)

La nouvelle lecture Trading212 Invest **DEMO EUR** réussit sur les six endpoints,
dont l'historique des ordres qui échouait auparavant. Aucun ordre ouvert,
aucune position et aucun élément d'historique dans la page reçue. Aucun ordre
n'a été envoyé pour créer artificiellement un historique.

Preuve : `artifacts/fr/research/trading212_demo_17b/demo-20261008223330840725/report.json`.
L'horodatage du dossier est UTC ; la lecture a été effectuée le **9 octobre
à 00 h 33 Paris**. Statut : `READONLY_REACHABLE_NOT_RELEASED`.
Les anciens rapports HTTP 403 restent des preuves historiques conservées.

Le manifeste 17-C a été régénéré depuis cette preuve : toujours **138**
correspondances XPAR/Paris/EUR, **95** exclusions et aucun droit d'ordre.
Le blocage `HISTORY_ACCESS_REFUSED` est levé. L'accès à un historique vide
ne qualifie pas l'interprétation de vrais fills, taxes ou commissions.

## Banc de réconciliation livré

Module : `service/fr/trading212_reconciliation_17d.py`.
`SyntheticOrderJournal` travaille exclusivement en mémoire sur des intentions
FR artificielles validées par le contrat 17-A. Il n'utilise aucune clé, aucun
réseau, aucune base et ne satisfait pas `ExecutionBrokerPort`.

| Scénario synthétique | Comportement vérifié |
| --- | --- |
| Soumission expirée | État UNKNOWN ; aucun renvoi automatique de la même intention |
| Réception du statut après timeout | Mise à jour seulement avec identité courtier explicitement corrélée |
| Fill partiel puis annulation confirmée | La quantité déjà remplie est conservée |
| Fill gagnant la course contre l'annulation | État FILLED accepté ; demande d'annulation non assimilée à annulation effective |
| Reçu exact dupliqué | Aucune seconde application |
| Cumul décroissant, ancien reçu, état incohérent/inconnu | Quarantaine, état précédemment accepté conservé, revue requise |
| Identité courtier modifiée ou liée à deux intentions | Refus et quarantaine |
| Arrêt d'urgence | Nouvelles entrées bloquées, demandes locales d'annulation signalées ; positions non fermées fictivement |
| Doublons concurrents | Une seule inscription acceptée |
| US, USD, compte réel ou entrée short | Refus du contrat synthétique FR |

Les numéros de séquence sont ceux du **registre local d'évidence synthétique**,
pas un champ garanti par l'API du courtier. Un reçu ancien déclenche volontairement
une revue plutôt qu'une correction automatique hasardeuse.
Un état terminal modifié est mis en quarantaine : le banc ne prétend pas
résoudre automatiquement les corrections de transactions ultérieures.

## Tests

**83 tests ciblés passent**, dont 24 nouveaux cas de réconciliation. Les suites
17-A/B/C, routeur, doubles d'exécution et coûts FR restent vertes.

```powershell
python -m pytest tests/test_fr_trading212_reconciliation_17d.py tests/test_fr_trading212_mapping_17c.py tests/test_fr_trading212_demo_17b.py tests/test_fr_broker_contract_17a.py tests/test_execution_broker_router_18a.py tests/test_execution_broker_doubles_18d.py tests/test_fr_execution_costs.py --no-cov -q
```

## Limites : ce qui n'est pas livré

- Pas d'adaptateur réseau d'ordres ni raccordement au routeur.
- Pas d'idempotence durable après redémarrage ; le journal est en mémoire.
- Pas de réservation du cash ou de sizing portefeuille ; limite par intention seulement.
- Pas de comptabilité de positions/fills réels, de coûts, de taxes ni de PnL.
- Pas de stop/TP/OCO externe, de remplacement atomique ou de clôture automatique.
- Pas de preuve du MIC réel d'exécution ni de levée des réserves shadow du Sprint 16.

Le kill switch de ce banc n'envoie pas d'annulation au courtier. Il ne faut
donc pas le présenter comme un arrêt d'urgence opérationnel.

## Prochaine tranche bornée

**Mise à jour :** le [lot 17-E](sprint_17e_journal_persistant_et_reprise.md)
a livré la persistance et la reprise du banc synthétique. Cela ne qualifie
pas encore une persistance de production ou un transport courtier réel.

Préparer la persistance du journal et les règles de reprise après incident,
avec transport factice avant toute soumission. Qualifier ensuite les capacités
de protection effectivement disponibles chez Trading212 et la compatibilité
avec le contrat du moteur. En l'absence d'OCO/atomicité prouvés, le moteur ne
doit pas être raccordé en supposant ces capacités.

Un test d'ordre DEMO nécessite un GO explicite distinct et un protocole
limité ; il n'est pas autorisé par ce lot. Aucun PAPER autonome ni LIVE.
Le Sprint 17 reste **partiellement livré**, et non clôturé.
