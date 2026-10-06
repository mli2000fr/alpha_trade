# Sprint 13-A — Gel du protocole économique France et contrôle des gates

Suite technique préparée : [13-B — tapes et reporting](sprint_13b_assemblage_tapes_reporting.md).

Date : 4 octobre 2026. Nouveau GO utilisateur pour commencer Sprint 13, après
les expériences US. Ce GO remplace l’interdiction antérieure de préparer ce
sprint ; il **ne dispense pas** des preuves encore manquantes au Sprint 12.

## Résultat exécuté

Commande exécutée :

```powershell
python -u -m modelFactory.fr_validation_protocol_13a --output artifacts/fr/research/validation_protocol_13a/frozen-20261004-v1
```

Sorties : `report.json` et `protocol.json` dans ce dossier. État :
`PROTOCOL_FROZEN_ECONOMIC_REPLAY_BLOCKED`. Les 21 379 chemins et les intentions
des trois politiques sont conservés ; **zéro chemin complètement qualifié**.
`net_pnl=null`, aucun ordre exécuté, aucun entraînement, aucune écriture SQL,
aucune activation de serving. Ce résultat n’est ni un backtest négatif, ni un
NO-GO du modèle : la comparaison économique reste non mesurable sous le
contrat strict actuel.

Le gel est opérationnel pour préparer une comparaison reproductible. Le
Sprint 13 dans son ensemble n’est pas terminé. Aucun abonnement ni nouvel
achat de données n’a été engagé.

## Entrées, contrôle d’intégrité et population

Sources de vérité :

- protocole `config/research_fr/economic_references_11a_v1.yaml` ;
- scores et intentions `economic_references_11a/preflight-20261004-v2` ;
- qualification `exploitable_scope_12e/audit-20261004-v2` ;
- coûts `config/markets/fr_execution_research_v1.yaml` ;
- fiscalité `config/taxes/fr_ttf_eligibility.yaml` ;
- moteur `service/fr/portfolio_replay_12b.py` et calcul des coûts associés.

Le service `service/fr/validation_protocol_13a.py` vérifie les empreintes des
entrées et des sorties du dossier 12-E. Il reproduit les intentions depuis les
scores et compare leurs rangs au ledger gelé. Les clés des chemins sont
rapprochées avec la population de scores complète, puis avec les intentions
auditées. Un fichier modifié, une intention sans chemin, un doublon, une
politique supplémentaire ou une utilisation de labels futurs est bloquant.

Le dossier de sortie est nouveau et refuse d’écraser un dossier existant. Les
hashes des preuves, des configurations et des implémentations sont archivés.
Les réserves constatées par 12-F demeurent à traiter dans le TODO Sprint 12 :
ce gel ancre le dossier 12-E, il ne prétend pas appliquer automatiquement les
pièces partielles 12-F à une nouvelle qualification.

**Interdiction de sélectionner après coup les 16 032 chemins passant seulement
les contrôles partiels.** Leur couverture diffère selon les politiques. Le
rejeu ne peut pas exclure rétrospectivement des intentions Oracle problématiques
puis annoncer un PnL sur une population devenue favorable.

## Politiques et paramètres hérités

On conserve, sans chercher de nouveau seuil :

| Élément | Contrat |
|---|---|
| Folds de développement | 6 et 7, phase test |
| Oracle | Branche arbres, H5 |
| Pool | TOP20, univers minimum 20 |
| Contrôles | `atr_top20_long`, `oracle_top20_long`, `uniform_control_long` |
| Seed | 17, déjà fixé au 11-A |
| Capital | 4 000 EUR, cash, pas de levier |
| Capacité | 8 positions, quantités entières, pas de shorts |
| Entrée | Ouverture de la séance de décision, disponibilité causale requise |
| Sortie | Clôture à +5 séances, pas d’optimisation stops/TP/trailing |
| Confirmation | 2026 réservée, non lue/non évaluée |

Les règles d’allocation, réentrée, non-empilement et non-réutilisation intraday
du cash restent celles du protocole 11-A. Les directions du Sprint 10 non
validées ne sont pas promues artificiellement en quatrième politique.

La référence descriptive équipondérée de l’univers admissible ne se substitue
pas à un benchmark investissable total-return. Sa qualification demeure une
gate séparée. La présence de prix d’un indice ne garantit pas sa comparabilité
économique avec un portefeuille recevant ses dividendes.

## Coûts et comparaison nominal/stress

Le fichier de coûts reste configurable et archivé, sans courtier imposé.
Le moteur distingue commission, spread, slippage et taxes. Les valeurs de
spread/slippage sont des hypothèses, pas des quotes/fills observés.

Scénarios prévus : nominal ×1 et coûts d’exécution ×2. Le moteur existant double
commission, spread et slippage ; **il ne double pas la taxe**. Les taux fiscaux
et l’assujettissement suivent le contrat instrument/date du Sprint 12 ; aucun
inconnu n’est assimilé à une exonération.

Ces scénarios sont gelés mais n’ont pas été exécutés sur une tape réelle.

## Rapport économique à produire une fois les gates levées

Le protocole liste les sorties attendues, pas des métriques déjà calculées :

- PnL EUR et rendement nets, Sharpe quotidien, drawdown ;
- exposition brute/nette, turnover, capacité, ordres et trades clôturés ;
- taux de réussite, attribution par symbole et concentration ;
- commission/spread/slippage/taxes séparés et cash-flows dividendes ;
- décomposition par fold et semestre, nominal/stress sur les mêmes intentions.

Les conventions de calcul des métriques, le benchmark et les analyses de
sensibilité devront être explicitement validés avant les premiers PnL. Une
analyse de concentration ou de retard d’entrée ne doit pas devenir un nouveau
réglage choisi sur les pertes. Aucun GO live n’est autorisé par ce protocole.

## Gates et prochaine étape

Les quatre gates du rapport restent fausses :

1. Preuves d’exécution communes qualifiées : fiscalité, CA, prix/statuts et PIT
   restent incomplets — voir [TODO Sprint 12](TODO_sprint_12_reste_a_faire.md).
2. Benchmark total-return comparable qualifié.
3. Tapes d’exécution réellement qualifiées pour les trois politiques/folds.
4. Empreintes de runs US/CN représentatifs archivées, réserve héritée du Sprint 0
   avant adaptation du backtest commun ; aucune adaptation commune faite ici.

**13-B économique réel reste bloqué.** Pour avancer techniquement sans lever
les réserves : spécifier l’assemblage des tapes et les conventions de reporting,
avec jeux synthétiques et tests. Ne pas fabriquer une qualification des prix,
une couverture CA ou une taxe inconnue. Un protocole fournisseur-assumé serait
une autre expérience à autoriser explicitement ; il ne clôturerait pas le
protocole strict.

## Tests

`tests/test_fr_validation_protocol_13a.py` vérifie l’héritage des politiques,
la réservation 2026, la conservation des chemins bloqués, les doublons,
intentions futures et chemins absents. Les tests existants du moteur, de
l’audit de rejeu, de la couverture et du préflight sont exécutés en complément.
Résultat : **39 tests ciblés passent**. Cela ne constitue pas l’exécution de
toute la suite applicative ni une validation économique.
