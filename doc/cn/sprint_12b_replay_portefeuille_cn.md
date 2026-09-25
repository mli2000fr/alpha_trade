# Sprint 12-B — Replay de portefeuille CN_A

## État réel

Le moteur de replay CN et son adaptateur de lecture **sont implémentés**.
Ils sont isolés de `backtesting/` US, ne créent aucune table, ne modifient
aucune donnée de `alpha_trade_cn` et n'activent ni serving ni trading live.
Un smoke en lecture seule sur quatre séances réelles de mars 2024 a chargé
calendrier, board, barres et limites, puis produit un achat **hypothétique**.
Les scénarios synthétiques et l'ensemble des tests CN passent.

Ce sprint ne valide **pas encore la rentabilité OOS d'une politique**. Le
protocole de choix des signaux, allocation et sorties doit être figé avant
les comparaisons économiques du Sprint 13. Les 24 972 événements
`cn_corporate_actions` actuellement présents sont des changements de
facteur **non classifiés** ; ils ne sont jamais interprétés automatiquement
comme split ou dividende. Les positions touchées deviennent non résolues,
et un rendement de portefeuille final n'est pas publié comme valide.

## Composants

| Composant | Rôle |
| --- | --- |
| [Contrat 12-A](../../service/market/cn_execution_contract.py) | Résolution datée MIC/board et coûts, achats au lot, ventes T+1, éligibilité proxy |
| [Moteur 12-B](../../service/market/cn_portfolio_replay.py) | Ordres, cash, inventaire, suspensions/limites, corporate actions, journal et valorisations |
| [Adaptateur/CLI](../../modelFactory/cn_portfolio_replay.py) | Lecture seule des tables CN, entrée de signaux explicites, empreintes et rapport |
| [Tests](../../tests/test_sprint12b_cn_portfolio_replay.py) | Scénarios synthétiques incluant T+1, frais, blocages, événements, radiation et cash |

Le module 12-B consomme uniquement des IDs `instrument_id` CN_A et des
prix CNY bruts. Il utilise le routage `cn_primary` vers `alpha_trade_cn` ;
une exécution contre `alpha_trade` est refusée. Les frais de la migration
0008 restent des hypothèses `RESEARCH_PROXY`, chargées uniquement avec
un opt-in explicite. Il n'existe toujours aucune règle 2026 dans la
base CN : le replay échoue plutôt que prolonger 2025 implicitement.

## Cycle quotidien et absence de fuite d'exécution

```text
Après clôture J : signal daté, prix J non utilisé comme fill
       ↓
Séance ouverte J+1 ou plus tard : vente en attente, puis achat par priorité
       ↓
Règle MIC/board/date + coût/date + inventaire T+1 + cash + lot
       ↓
Barre, statut, limite dérivée, verrouillage et participation au volume
       ↓
HYPOTHETICAL_FILL ou motif de non-fill/report/refus/annulation
       ↓
Valorisation close du jour, avec positions et cash explicitement ouverts
```

L'ordre `BUY` est chiffré au prix d'ouverture du jour où il est tenté ;
`prepare_buy` retire les frais du budget avant de valider le lot. Les
ventes ne peuvent mobiliser que les lots acquis **avant** la date de la
séance ; une protection envoyée le jour de l'achat attend au moins la
séance suivante. Les ventes sont traitées avant les achats à date égale.
Le `priority` le plus élevé est traité en premier, avec `intent_id`
comme départage déterministe. Le pyramiding est désactivé par défaut.
Les ordres d'achat sans cash/lot/capacité sont refusés ou laissés en
attente selon la raison ; les refus ne créent jamais de position.

Le cash d'une vente est utilisable pour un nouvel achat le même jour,
mais ne devient `cash_withdrawable_cny` qu'à la séance suivante. Le
replay sépare donc cash dépensable, cash retirable et dividendes à
recevoir. Il ne modèle ni dépôt/retrait utilisateur ni conversion FX.

## Scénarios de fills et limites de preuve

| Scénario | Part maximale du volume quotidien observé pour un ordre |
| --- | ---: |
| `permissive` | 10 % |
| `base` | 5 % |
| `conservative` | 1 % |

Ces seuils sont des **hypothèses de liquidité pour stress-test**, non
une calibration boursière et non une preuve de fill à l'open. Le volume
total du jour et les limites dérivées ne sont connus complètement
qu'après clôture : ils servent à juger ex post la plausibilité du
scénario, **jamais de feature pré-entrée**. Même sous `permissive`, une
limite verrouillée, une suspension, une politique inconnue, une barre
absente, un volume nul/inconnu ou un prix d'ouverture invalide ne donnent
aucun fill. L'événement s'appelle toujours `HYPOTHETICAL_FILL`, jamais
`FILLED`. Aucun carnet d'ordres, rang de file ni volume à l'open n'est
disponible dans ce contrat.

Deux comportements des ordres différés sont configurables : `carry`
(jusqu'à `max_wait_sessions`, trois par défaut) ou `cancel_day` (annulation
après la première tentative). En fin de période, les ordres non exécutés
restent listés. Une position ouverte est marquée au dernier close connu,
sans forcer une vente fictive. Un close manquant produit `stale_marks`
et invalide le rendement économique. Une position encore détenue après
radiation reste à l'inventaire avec
`DELISTING_WITHOUT_VERIFIED_CASH_RECOVERY`, sans recouvrement inventé.

## Corporate actions

Le cœur sait appliquer un `SPLIT` entier explicite et un
`CASH_DIVIDEND` avec date de paiement explicite : le nombre d'actions
ouvrant droit au dividende est figé **avant** un éventuel split de même
date. Un ratio donnant des fractions, une action inconnue ou un événement
de facteur non classifié met la position en état non résolu. La CLI
transforme **toutes** les lignes actuelles `cn_corporate_actions` en
`UNRESOLVED` ; elle ne déduit pas la nature économique d'un simple
changement de facteur. Une normalisation PIT fiable et des termes de
transaction vérifiés sont nécessaires avant une évaluation économique
complète sur les titres concernés.

## Entrée et utilisation

La CLI lit un JSON de signaux explicites. Exemple de forme (remplacer
l'ID et les dates par un titre et des séances existant dans la base CN) :

```json
{
  "market_code": "CN_A",
  "signal_timing": "after_close",
  "start_date": "2024-03-04",
  "end_date": "2024-03-07",
  "signals": [
    {"intent_id": "exemple-achat", "signal_date": "2024-03-04",
     "instrument_id": 12345, "side": "BUY", "budget_cny": "10005",
     "priority": "0.8", "reason": "OOS_EXEMPLE"},
    {"intent_id": "exemple-vente", "signal_date": "2024-03-06",
     "instrument_id": 12345, "side": "SELL", "reason": "SORTIE_EXEMPLE"}
  ]
}
```

`SELL` sans `shares` signifie liquider la position entière déjà détenue.
L'entrée ne doit pas utiliser `oracle_decile`, `future_return`, la
validité du label ni le statut futur de la sortie pour choisir un signal.
Les artefacts Walk-Forward peuvent être exportés plus tard, mais seulement
avec leurs scores OOS et un contrat d'allocation/sortie pré-enregistré.
Le moteur n'effectue **aucune** sélection automatique de ces artefacts.

```powershell
F:\projets\.venv\Scripts\python.exe -m modelFactory.cn_portfolio_replay `
  --intent-file F:\projets\artifacts\cn\signals_oos.json `
  --output-dir F:\projets\artifacts\cn\portfolio_replay\run_unique `
  --scenario base --cost-profile-key cn_a_research `
  --initial-cash-cny 100000 --allow-research-proxy `
  --pending-policy carry --max-wait-sessions 3 --max-positions 8
```

Sans `--allow-research-proxy`, les règles/coûts de recherche sont
refusés. La sortie existante n'est jamais écrasée. La fenêtre est bornée
à deux ans et l'entrée à 100 000 signaux. Le rapport contient :

- `journal.jsonl` : intention, tentative, motif de non-fill, coût détaillé
  et scénario de chaque fill hypothétique ;
- `daily.jsonl` : cash, inventaire valorisé, frais cumulés, cash retirable,
  stale marks et validité du mark chaque séance ;
- `report.json` : compteurs et motifs, lots encore ouverts, événements
  non résolus, configuration et hashes de l'entrée, des données canoniques,
  du contrat et du code.

L'adaptateur lit les **données canoniques historiques révisées**, pas un
snapshot conservé tel qu'il était connu à chaque date. Le champ
`data_revision` du rapport le rappelle. L'empreinte des données permet
de détecter une révision entre deux runs, mais ne reconstitue pas le
snapshot PIT original. `marked_return_proxy` n'est renseigné que si
les marks sont valides ; même alors ce n'est **pas une liquidation
exécutable** si des positions restent ouvertes.

## Vérification et suite

Le [rapport smoke réel](../../artifacts/cn/portfolio_replay/sprint12b-smoke-20260925/report.json)
du 25/09/2026 a chargé un instrument `SH_MAIN` sur les quatre séances
04–07/03/2024 et produit uniquement un achat hypothétique à l'ouverture
suivante, sans modification de base. Le mark de fin sur cette unique
position encore ouverte est +0,13 % : **ce n'est ni une performance de
stratégie, ni une liquidation réalisable**. Les tests couvrent
notamment le stop sur le jour d'achat, une suspension, une limite
verrouillée, STAR, la radiation, une action non classifiée, un split, un
dividende et le réemploi du cash de vente.

Le **gate d'ingénierie** du Sprint 12-B (séparation US/CN, règles,
non-fills, coûts et inventaire visibles) est franchi. Le **gate
économique** reste ouvert : il faut normaliser les corporate actions,
figer les politiques Oracle/veto/allocation/sortie sans regarder les
résultats, puis produire les comparaisons OOS et sensibilités du
Sprint 13. Aucun résultat de 11-B ne peut être renommé « rendement net
de portefeuille » par ce seul sprint.
