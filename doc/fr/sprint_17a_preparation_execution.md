# Sprint 17-A — Préparation de l'exécution France

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Résultat et frontière du lot

**17-A livré : audit du port existant, contrat cible et banc d'essai local.**
Le Sprint 17 complet reste conditionnel : `BLOCKED_BROKER` et
`BLOCKED_SHADOW_DATA`. Aucun courtier n'est choisi, aucun compte connecté,
aucun ordre PAPER/live envoyé et aucun adaptateur FR n'est enregistré dans
le routeur de production. La clôture avec réserves du Sprint 16 reste inchangée.

Le banc d'essai valide des intentions synthétiques, pas des signaux investissables.
Il ne simule ni fills, ni performance, ni cash, ni protections effectivement placées.
Il n'est **pas** une preuve de parité complète signal → fill → portefeuille.

## Audit de réutilisation

| Composant existant | Usage possible | Limite France |
|---|---|---|
| `execution_engine/broker_router.py` | Frontière avant construction du client | Seul US_EQ autorisé ; FR/CN rejetés avant la factory |
| `ExecutionBrokerPort` dans ce même fichier | Interface cible OMS/watcher/CLI | Interface sans identité ISIN/MIC native dans plusieurs signatures : mapping FR explicite nécessaire |
| `execution_engine/broker_adapter.py` | Exemple d'adaptation du client au moteur | Adaptateur Alpaca US ; ne pas le réétiqueter FR |
| `execution_engine/broker_doubles_18d.py` | Doubles mock/replay et tests OMS | Double US, volontairement refusé par le routeur réel |
| `execution_engine/models.py` | Intentions, ordres, états et résultats d'annulation | Plusieurs champs orientés symbole ; mapping daté instrument/ISIN/MIC à qualifier |
| Moteurs OMS, protection, réconciliation | Logique susceptible d'être partagée | Pas encore auditée/intégrée complètement pour EUR/XPAR/courtier FR |
| `config/markets/fr_execution_research_v1.yaml` | Hypothèses économiques configurables | Commission/spread/slippage de recherche, pas un tarif ni une facture de courtier |

Le routeur reste inchangé : aucun risque de route FR vers Alpaca introduit.
La base FR reste `alpha_trade_fr`, alias `fr_primary` ; ce lot ne s'y connecte pas.

## Contrat du futur adaptateur

Le futur adaptateur devra satisfaire **toutes** les méthodes du port :

- soumettre une intention ou un ordre marché ; poller son statut ; annuler ;
- poser les protections OCO et remplacer un stop, ou refuser explicitement les
  capacités non supportées, sans annoncer une protection absente ;
- lire une position, toutes les positions, compte, equity et prix ;
- vérifier l'ouverture réelle du marché ; lister et annuler les ordres ;
- normaliser les réponses API vers les états canoniques.

L'identité doit être résolue avant soumission : `instrument_id`, ISIN, MIC,
devise, période effective et identifiant propre au courtier. Un ticker `.PA`
ou le seul ISIN ne suffisent pas. Un ISIN commençant par NL peut être coté
sur XPAR : ne pas confondre pays de l'ISIN et place de négociation.

Les comptes et credentials doivent être FR et séparés des routes US/CN. Le
choix de compte/mode ne se déduit pas d'un fallback US. Les quantités, pas de
cotation, minimums, capacités d'ordre et protections seront qualifiés auprès
du courtier choisi : ne pas imposer en production les hypothèses du banc local.

Tout timeout de soumission devra être réconcilié par identifiant client avant
une éventuelle nouvelle tentative. Les partial fills, annulations tardives,
OCO non atomiques, rejets, changement d'identité et événements devront être
testés. Aucun état inconnu ne doit être transformé en FILLED.

LONG seulement au démarrage ; ventes de positions détenues et protections
devront être distinguées de l'ouverture d'un SHORT. Ce banc ne teste pas encore
ce cycle de sortie. Aucune autorisation short sans emprunt qualifié.

## Banc d'essai livré

`service/fr/broker_contract_17a.py` expose :

- `FrenchTestIntent` : enveloppe immuable avec ISIN contrôlé par checksum,
  MIC XPAR, FR_EQ/fr_primary/EUR, compte artificiel `fr_simulated` ;
- `FrenchIntentHarness` : acceptation/annulation en mémoire, quantité entière
  positive, prix Decimal fini positif, limite notionnelle explicite par intention,
  rejet des identifiants dupliqués sous verrou, kill switch annulant les
  intentions locales et bloquant les nouvelles ;
- `readiness()` : statut de préparation et blocages explicites, sans permission.

Une acceptation signifie **ACCEPTED_SIMULATED**, avec quantité remplie zéro.
Ce banc n'implémente pas `ExecutionBrokerPort` et ne peut pas être branché comme
un courtier opérationnel. La limite par intention n'est pas une limite de
portefeuille ; il ne modélise ni capital disponible ni exposition cumulée.
La quantité entière est une convention de ce test, pas une règle universelle
des courtiers FR. Aucun calendrier ou cours réel n'est consulté.

## Tests exécutés

**39 tests ciblés passent**, dont 22 cas du nouveau lot. Identités/contextes
erronés, USD/US/CN, mauvais MIC/compte, ISIN invalide, quantités et prix invalides,
notionnel, doublons concurrents, kill switch, absence de fill et absence de route
vers la factory US sont couverts. Les suites existantes routeur/doubles/coûts
FR passent également. Ce n'est pas un test de bout en bout de trading FR.

```powershell
python -m pytest tests/test_fr_broker_contract_17a.py tests/test_execution_broker_router_18a.py tests/test_execution_broker_doubles_18d.py tests/test_fr_execution_costs.py --no-cov -q
```

## Suite bornée

Mise à jour du 8 octobre : l'utilisateur a choisi Trading212 Invest DEMO.
Le [POC 17-B en lecture seule](sprint_17b_trading212_demo_lecture_seule.md)
confirme l'accès EUR, avec une réserve HTTP 403 sur l'historique. Aucun ordre
n'est autorisé ; les travaux hors ligne ci-dessous restent nécessaires.

**17-B peut être préparé hors ligne** : spécifier une bande canonique de
réponses/fills synthétiques et tester réconciliation/protections, puis
identifier les adaptations réelles nécessaires. Toujours sans brancher de
courtier, sans SQL de production et sans prétendre qualifier les données S16.

**L'intégration externe nécessite une décision utilisateur** : courtier/API
XPAR, compte de test disponible, droits, tarif et capacités. Ne pas imposer
IBKR, précédemment écarté. Aucun abonnement ou ouverture de compte automatique.

**GO PAPER** uniquement après qualification des données/signal, adaptation
complète du port, tests de parité et autorisation explicite. **GO live** distinct
au Sprint 18. Aucun objectif de profit n'est validé dans ce lot.

Voir [planning FR](sprint_planning_integration_marche_francais.md) et
[clôture avec réserves du Sprint 16](sprint_16_cloture_bornee.md).
