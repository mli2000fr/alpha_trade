# Acquisitions cash — premier test économique exploratoire, 20 octobre 2026

## Conclusion

**Positif mais faible, pas de stratégie validée.** Cinq opérations produisent
**31,49 USD de trading net de frais simulés**, pour 4 000 USD au départ, soit
**+0,79 %** sans rémunération du cash. Les cinq trades sont positifs dans le
scénario principal, mais les cinq acquisitions ont abouti : ce n'est pas un
taux de réussite généralisable ni une mesure du risque de rupture.

Avec un cash rémunéré **par hypothèse** à 4 % annuel, le capital final est
**4 097,83 USD**, contre **4 079,00 USD** si tout le capital restait en cash
au même taux. L'avantage est donc **18,83 USD**, environ **0,47 point** sur la
période, pas 97,83 USD d'alpha d'arbitrage. Aucune promotion en production.

Cette stratégie est distincte de l'Oracle. L'entrée est après le lancement
formel d'une offre, **pas à la première annonce mondiale**. Elle ne représente
ni toutes les acquisitions ni une stratégie professionnelle complète.

## Règles figées avant le calcul des profits

Sources : [cohorte et qualification](arbitrage_acquisitions_cash_cohorte_20261020.md).
Admissions figées avant lecture des issues ; protocole économique écrit avant
lecture des profits, **mais après connaissance des clôtures juridiques** :
exploratoire, pas confirmation sur échantillon vierge.

- Capital **4 000 USD**, cinq emplacements, **800 USD de cash par opération**,
  soit 20 % du capital initial. Pas de sélection par spread, remplacement,
  redimensionnement après gain, short, levier ou emprunt.
- Entrée à l'ouverture de la première séance après le jour du dépôt initial
  SC TO-T. Fractions de parts autorisées par hypothèse ; pas de fills réels.
- Frais principaux : **1 USD par achat et 10 bps de friction d'entrée**.
  Pas de TP, SL ou trailing : détention jusqu'au droit cash de fusion.
- La fusion n'est pas un ordre de vente : pas de spread de sortie fictif.
  Frais d'opération sur titre supposés nuls, non certifiés par un courtier.
- Une conversion en créance à la clôture juridique SEC, un paiement à la
  **date payable déclarée par Alpaca**, pas un crédit courtier prétendument
  observé. La créance ne finance aucune entrée et ne rapporte pas d'intérêt.
- Sensibilités de crédit : deux et cinq **séances NYSE** supplémentaires.
  Aucun T+2 ou jour d'expiration présumé égal au paiement réel.
- Compte suivi du **01/01/2024 au 30/06/2024**, sans nouvelles opérations du
  deuxième trimestre. **Pas d'annualisation** de ces six mois/cinq trades.
- Cash principal à **4 % annuel effectif hypothétique**, ACT/365, intérêt
  quotidien en fin de journée sur le cash après flux. Même convention pour
  le témoin tout-cash ; sensibilités 0 % et 5 %. **Pas les taux historiques
  réels du Trésor ou ceux effectivement payés par Alpaca.**
- Avant fiscalité/change, frais internes au courtier non certifiés. Cours
  bruts reportés seulement pendant les fermetures de marché pour valorisation,
  jamais pour remplacer une séance manquante ou prolonger un titre radié.

## Résultat de chaque opération

Budget **800 USD par ligne, frais compris**. Ouvertures fournisseur comme
proxies de fills, pas transactions réellement exécutées.

| Titre | Entrée | Ouverture brute USD | Cash par action | Paiement fournisseur retenu par hypothèse | Gain net de trading USD |
|---|---|---:|---:|---|---:|
| RYZB | 26/01/2024 | 62,05 | 62,50 | 26/02/2024 | **+3,99** |
| SNCE | 13/02/2024 | 5,73 | 5,75 | 15/03/2024 | **+0,99** |
| CBAY | 26/02/2024 | 32,23 | 32,50 | 27/03/2024 | **+4,89** |
| NGM, public non-rollover | 11/03/2024 | 1,53 | 1,55 | 09/04/2024 | **+8,64** |
| SCTL | 12/03/2024 | 1,08 | 1,10 | 09/04/2024 | **+12,98** |
| **Total** | | | | | **+31,49** |

Coût d'entrée d'environ **1,7982 USD par ligne**, soit **8,99 USD** au total.
Les gains du tableau ne comprennent pas d'intérêt du cash. Un gain nominal
ne prouve pas une surperformance sur le cash : SNCE immobilise notamment
800 USD environ un mois pour moins d'un dollar net. Un frais de fusion
supplémentaire pourrait réduire davantage ce résultat.

## Compte et référence cash

| Hypothèse | Capital final | Gain total | Rendement | Baisse maximale | Avantage sur cash comparable |
|---|---:|---:|---:|---:|---:|
| Cash non rémunéré, frais principaux | **4 031,49 USD** | +31,49 USD | +0,79 % | −1,03 % | +31,49 USD |
| **Cash 4 %, principal** | **4 097,83 USD** | **+97,83 USD** | **+2,45 %** | **−0,97 %** | **+18,83 USD** |
| Cash 5 %, frais principaux | 4 114,20 USD | +114,20 USD | +2,85 % | −0,96 % | +15,69 USD |

Principal : **31,49 USD de trading + 66,34 USD d'intérêt hypothétique**,
réconciliés avec le gain total. Le témoin cash à 4 % gagne **79,00 USD**.
Fractions de cent arrondies dans les tableaux.

**Cinq trades gagnants, zéro perdant**, après frais de trading nominaux,
sur ces cinq cas uniquement. Ce résultat ne rend pas une future acquisition
certaine. La baisse maximale inclut frais et valorisation quotidienne,
pas seulement les dates de paiement.

### Sensibilités prévues, sans choisir le meilleur réglage

| Variation isolée | Capital final | Avantage sur cash comparable | Gagnants / perdants |
|---|---:|---:|---:|
| Principal, 10 bps, crédit date fournisseur | 4 097,83 USD | +18,83 USD | 5 / 0 |
| 0 bps d'entrée, commission 1 USD maintenue | 4 101,90 USD | +22,90 USD | 5 / 0 |
| 25 bps d'entrée, commission 1 USD maintenue | 4 091,73 USD | +12,73 USD | **4 / 1** |
| Crédit retardé de 2 séances NYSE | 4 096,51 USD | +17,52 USD | 5 / 0 |
| Crédit retardé de 5 séances NYSE | 4 094,67 USD | +15,68 USD | 5 / 0 |

Les retards changent l'intérêt du cash, pas le montant contractuel. Dans ce
petit compte à budgets fixes, aucune entrée n'est refusée : il reste assez
de cash. Cela ne vaut pas pour un portefeuille fortement réinvesti.

Une baisse **hypothétique** de 10 % sur 800 USD représente environ 80 USD,
plus que les gains de trading de ce pilote. Ce n'est pas un stress backtest
exécuté ou une probabilité de rupture estimée : seulement l'ordre de grandeur
du risque absent de l'échantillon.

## Validation et réserves

La baisse maximale est mesurée sur les valeurs quotidiennes, **pas sur les
plus bas intrajournaliers**.

**27 tests ciblés** et **sept rejeux analytiques quotidiens** passent : cinq
émetteurs conservés, dates et quantités, ouvertures, frais, une seule
conversion/un paiement par opération, cash sans emprunt, créances non
dépensables, marks bruts et absence de remplissage sur séance manquante,
intérêts et référence, résultats par trade/compte et excédent au cash.
Un test montre qu'une acquisition achevée peut donner un trade perdant après
frais. Le paiement non arrivé en fin de test reste une créance, pas une vente.

Même assistant pour l'audit, pas revue humaine indépendante. Toutes les
sorties gardent **`broker_credit_proven=false`** et l'absence de parité live.
Petit échantillon de cinq cas, aucune rupture admissible observée, risque
sectoriel concentré et risque rare non estimés. Données historiques dans leur
version actuelle, pas reçus locaux PIT d'époque. Issues connues avant la
conception économique : ne pas présenter ce pilote comme holdout vierge.

## Archives et décision

Dans `F:/projets/artifacts/research/us_cash_merger_completion/20261020-v1` :

- `economic-v1/protocol.json` : sept scénarios scellés avant PnL ;
- `economic-v1/summary.csv` et `trades.csv` : résultats et cinq opérations ;
- `economic-v1/PRIMARY/{daily,trades,cash-flows}.parquet` : journal détaillé ;
- `economic-audit-v1/report.json` : sept contrôles quotidiens PASS.

Aucun nouvel appel fournisseur pendant le calcul, LLM, entraînement, ordre,
écriture SQL ou changement de batch/production. Aucun run laissé actif.

**Conserver comme petit pilote positif, ne pas déployer.** L'avantage sur
le cash est faible et le risque de rupture non mesuré. Ne pas optimiser les
entrées ou frais sur ces cinq gagnants pour présenter une amélioration.
Une suite utile serait une cohorte calendaire distincte, plus large et
pré-enregistrée, avec toutes les opérations admissibles et leurs ruptures
si elles existent. Aucun élargissement n'est lancé ici.
