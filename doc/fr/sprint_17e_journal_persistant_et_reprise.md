# Sprint 17-E — Journal persistant et reprise, transport factice exclusivement

## Livraison du 9 octobre 2026

`service/fr/trading212_durable_17e.py` ajoute un journal de recherche sur fichiers
au banc synthétique 17-D. **Aucun ordre DEMO ou réel, aucun accès réseau, aucune
clé, aucune écriture SQL, aucune modification des batchs ou du routeur.**

**97 tests ciblés passent**, dont 14 nouveaux cas. Rapport conservé :
`artifacts/fr/research/trading212_durable_17e/tests-20261009-v1/junit.xml`.
Les fichiers de test du journal sont créés dans les répertoires temporaires
des tests, pas dans une base de production.

## Fonctionnement

Le journal n'accepte que le contexte artificiel FR du contrat 17-A. Son
répertoire doit rester sous `artifacts/fr` ; le compte est `fr_simulated`.
Le transport accepté est exactement `FakeTransport`, qui ne contient aucun
appel réseau. Une implémentation quelconque ou même une sous-classe est refusée.

1. Inscrire l'intention, son identité et ses paramètres dans `events.jsonl`.
2. Valider la transition sur un état reconstruit.
3. Ajouter l'événement, vider les buffers et appeler `fsync`.
4. Seulement ensuite rendre l'état visible et invoquer le transport factice.
5. Journaliser les reçus, demandes locales d'annulation, quarantaines et kill switch.

Les événements sont numérotés et reliés par une chaîne SHA-256. La configuration
FR et le plafond notionnel sont inclus dans le premier événement. Un changement
de configuration sur un journal existant est refusé. Les intentions dupliquées
restent refusées après fermeture et réouverture du journal.

Un verrou système empêche deux processus coopérants d'écrire simultanément.
Un verrou en mémoire protège aussi les opérations concurrentes entre threads.
Le verrou système est libéré par Windows après la mort du processus : le fichier
`writer.lock` n'a pas besoin d'être supprimé pour reprendre.

## Reprise après incident

| Incident testé | Résultat |
| --- | --- |
| Timeout factice | UNKNOWN persisté, aucun renvoi automatique |
| Arrêt après inscription de la tentative | Au redémarrage, PENDING devient UNKNOWN ; aucun renvoi |
| Mort réelle d'un processus de test, sans fermeture propre | Verrou libéré ; reconstruction et UNKNOWN vérifiés |
| Échec de `fsync` | Instance bloquée, transport non invoqué |
| Fill partiel puis redémarrage | Cumul rempli conservé |
| Quarantaine / kill switch puis redémarrage | États conservés, nouvelles entrées refusées selon les règles du banc |
| Journal tronqué, vide ou empreinte incorrecte | Ouverture refusée, aucun effacement ni réparation automatique |
| Deux écrivains | Second refusé jusqu'à fermeture/mort du premier |

Si le stockage est incertain, ne pas créer une nouvelle intention pour contourner
le blocage. Préserver les fichiers et faire une revue. Une chaîne de hashes détecte
les altérations ordinaires mais n'est pas une signature : quelqu'un capable de
réécrire toutes les empreintes peut la falsifier. La suppression externe du fichier
n'est pas couverte par une garantie d'idempotence globale.

## Limites explicites

- Idempotence et reprise vérifiées pour **ce journal synthétique local seulement**.
  Le champ de qualification d'idempotence de production reste faux.
- Garantie dépendante du système de fichiers et de `fsync` ; aucune preuve de
  résistance à une panne matérielle ou à la perte du disque.
- Pas de corrélation automatique d'une intention inconnue avec des ordres réels.
  Les reçus factices sont explicitement corrélés dans les tests.
- Pas de cash réservé, portefeuille, coûts, taxes, positions réelles ou PnL.
- Pas de stop/TP/OCO externe, ni annulation réelle ou remplacement atomique.
- Journal borné à 32 Mio à l'ouverture ; reconstruction complète des événements,
  adaptée à un pilote, pas dimensionnée pour l'exploitation prolongée.
- Aucun fichier ni table de production créé. Aucune migration Alembic nécessaire
  pour ce stockage local de recherche ; une future persistance de production
  devra être conçue séparément.

## Vérification

```powershell
python -m pytest tests/test_fr_trading212_durable_17e.py tests/test_fr_trading212_reconciliation_17d.py tests/test_fr_trading212_mapping_17c.py tests/test_fr_trading212_demo_17b.py tests/test_fr_broker_contract_17a.py tests/test_execution_broker_router_18a.py tests/test_execution_broker_doubles_18d.py tests/test_fr_execution_costs.py --no-cov -q
```

## Prochaine tranche

Mise à jour : [17-F](sprint_17f_qualification_protections.md) livre l'audit
documentaire et les contrôles synthétiques de protection. La parité externe
reste bloquée, sans OCO natif/remplacement atomique qualifiés.

Qualifier et tester le contrat de protection : capacité native ou refus explicite,
courses stop/TP, remplacement de stop et gestion des incidents. Ne pas émuler un
OCO en supposant deux ordres atomiques. Le raccordement au moteur reste interdit
tant que ces capacités et la parité ne sont pas validées.

Les réserves shadow du Sprint 16 et la preuve du MIC réel d'exécution restent
ouvertes. Un test d'ordre DEMO nécessite un GO explicite séparé. Le Sprint 17
est **partiellement livré**, sans GO PAPER autonome ni LIVE.
