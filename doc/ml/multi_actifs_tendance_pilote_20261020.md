# Pilote multi-actifs de tendance — bilan du 20 octobre 2026

## Conclusion

**Calcul et rejeu comptable terminés.** Avec 4 000 USD de départ, du 1er janvier
2016 au 30 septembre 2026, la règle de tendance finit à **7 790,34 USD**,
soit **+94,76 %**, après l'hypothèse principale de frais. Sa baisse maximale
est **−11,26 %**. Les deux références rapportent davantage, avec une baisse
maximale plus forte. Le Sharpe de la règle n'est pas supérieur non plus.

Ce pilote montre une réduction du risque et de l'exposition, **pas une
surperformance démontrée**, ni une résolution de D1/D10 parmi les titres Oracle.
Ne pas le promouvoir en production et ne pas chercher maintenant le meilleur
panier ou les meilleurs horizons sur ces mêmes résultats.

## Pourquoi cette piste professionnelle, et ce qu'elle n'est pas

Le suivi de tendance multi-actifs est une famille étudiée publiquement,
notamment par [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing).
Notre essai **n'en reproduit pas une stratégie professionnelle** : quatre ETF
LONG/liquidités au lieu de nombreux marchés à terme LONG/SHORT, pas de ciblage
de volatilité, pas de levier, pas de devises. Les résultats ne disent donc pas
que les stratégies professionnelles de tendance fonctionnent ou ne fonctionnent
pas. C'est un test simple et séparé, pas une modification de l'Oracle.

## Règle figée avant calcul des performances

- Panier fixé : **SPY** (actions US), **TLT** (obligations du Trésor longues),
  **GLD** (or), **DBC** (matières premières via contrats détenus par le fonds).
- À la clôture de la dernière séance du mois : calculer les rendements de
  l'indice de rendement total sur **63, 126 et 252 séances**.
- Si au moins deux sont strictement positifs : cible de **25 %** du portefeuille
  pour cet ETF. Sinon : zéro ; la quote-part reste en liquidités.
- Pas de redistribution des quotes-parts des ETF désactivés aux ETF actifs.
- Quantités calculées avec la valeur liquidative et les cours bruts de cette
  clôture ; exécution à l'ouverture suivante. Ventes d'abord, achats réduits
  proportionnellement si la trésorerie ne suffit pas après gaps et frais.
- Une seule intervention mensuelle, pas de TP/SL/trailing, ni de liquidation
  imposée au bout de vingt séances. Les poids peuvent dériver entre deux dates.
- Capital initial **4 000 USD**, fractions de parts autorisées par hypothèse,
  pas de découvert, short ou levier. Aucune rémunération des liquidités.
- Fenêtre **2016-01-01 / 2026-09-30**, première exécution le 4 janvier 2016,
  amorçage du signal depuis le 1er décembre 2014.

Le protocole est dans
[multi_asset_trend_pilot_20261020.json](F:/projets/config/research/multi_asset_trend_pilot_20261020.json).
Il a été scellé dans les artefacts avant l'acquisition et le calcul des rendements.
Le complément de données n'a pas changé la règle ni la fenêtre.

## Hypothèses économiques et références

Frais principaux : **10 bps (0,10 %) du montant de chaque achat ou vente**,
représentant une friction globale spread/slippage. Sensibilités figées **0 et
25 bps**, sans sélectionner la meilleure après coup. Commission fixe nulle,
avant fiscalité et conversion EUR/USD. Ce n'est pas un tarif courtier certifié.
Les frais internes aux ETF sont déjà reflétés dans leurs cours.

Deux références, mêmes données, dates, capital, distributions et frictions :

1. **Achat-conservation équipondéré au départ** : quatre achats initiaux,
   pas de rééquilibrage, distributions accumulées en liquidités.
2. **Équipondération mensuelle sans filtre** : cible 25 % dans chaque ETF à
   chaque date mensuelle, réinvestissement possible du cash alors disponible.

Fin de période : valorisation des positions à la dernière clôture, trésorerie
et distributions à recevoir. **Pas une liquidation réelle du portefeuille** :
pas de frais de vente finale non effectuée. Les gains/pertes annuels incluent
donc le réalisé et le latent ; ce ne sont pas des statistiques de trades clos.

## Résultats principaux — 10 bps

| Stratégie | Capital final USD | Gain USD | Rendement cumulé | Annualisé | Baisse maximale | Volatilité annualisée | Sharpe, cash à 0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tendance 2 horizons sur 3 | 7 790,34 | 3 790,34 | +94,76 % | 6,40 % | −11,26 % | 7,20 % | 0,90 |
| Achat-conservation initial | 11 359,06 | 7 359,06 | +183,98 % | 10,20 % | −16,69 % | 9,80 % | 1,04 |
| Équipondération mensuelle | 10 969,92 | 6 969,92 | +174,25 % | 9,84 % | −18,55 % | 9,53 % | 1,04 |

La tendance est investie en moyenne à **65,62 %**, avec **34,33 % de cash**
et le reste en distributions à recevoir. Son risque moindre n'est donc pas
une preuve de meilleure sélection à exposition comparable. Aucun levier ou
redimensionnement n'a été ajouté pour rendre artificiellement la comparaison
plus favorable.

Coûts directs cumulés : tendance **122,41 USD** / conservation **4,00 USD** /
mensuel **27,92 USD**. Il y a respectivement **380 / 4 / 516 ordres simulés**.
Le coût faible du mensuel vient des petits ajustements de poids, pas de sa gratuité.
La tendance paie **463,72 USD** de distributions pendant la période et conserve
**4,76 USD** à recevoir au 30 septembre, inclus dans les 7 790,34 USD.

### Rendements par année, mêmes 10 bps

| Année | Tendance | Achat-conservation | Équipondération mensuelle |
|---|---:|---:|---:|
| 2016 | +1,79 % | +9,42 % | +10,12 % |
| 2017 | +6,80 % | +11,88 % | +12,14 % |
| 2018 | −3,11 % | −4,96 % | −4,49 % |
| 2019 | +12,61 % | +18,44 % | +19,33 % |
| 2020 | +8,40 % | +13,45 % | +14,42 % |
| 2021 | +13,03 % | +13,42 % | +14,43 % |
| 2022 | −3,67 % | −7,25 % | −8,69 % |
| 2023 | +5,36 % | +9,21 % | +8,85 % |
| 2024 | +8,77 % | +14,54 % | +10,87 % |
| 2025 | +12,00 % | +26,42 % | +21,95 % |
| 2026, jusqu'au 30/09 | +8,39 % | +9,18 % | +10,74 % |

Chaque rendement annuel utilise le capital porté depuis l'année précédente,
pas un redémarrage annuel à 4 000 USD. **2026 n'est pas une année entière.**
L'annualisation globale n'est pas la moyenne arithmétique de ces rendements.

### Lecture séparée de 2024–2026

Pour la tendance :

| Année | Gain USD sur le capital porté | Rendement | Baisse maximale dans l'année |
|---|---:|---:|---:|
| 2024 | +517,24 | +8,77 % | −3,30 % |
| 2025 | +770,05 | +12,00 % | −5,58 % |
| 2026 au 30/09 | +603,14 | +8,39 % | −8,28 % |

Elle ne dépasse aucune référence en rendement sur ces trois périodes. En 2026,
la baisse maximale de l'équipondération mensuelle (**−7,51 %**) est même moins
forte que celle de la tendance : la réduction du risque n'est pas universelle.

### Sensibilité aux frais, pas optimisation

| Friction par sens | Tendance, capital final | Conservation | Mensuel |
|---|---:|---:|---:|
| 0 bps | 7 969,55 USD | 11 370,42 USD | 11 019,60 USD |
| **10 bps, scénario principal** | **7 790,34 USD** | **11 359,06 USD** | **10 969,92 USD** |
| 25 bps | 7 528,86 USD | 11 342,06 USD | 10 895,99 USD |

La conclusion de rendement ne vient donc pas seulement des frais.

## Données et anomalie corrigée dans cet essai uniquement

- Alpaca SIP : **2 701 séances** par ETF du 4 janvier 2016 au 30 septembre 2026,
  cours `raw`, `split`, `all` capturés séparément. Les versions `raw`/`split`
  coïncident ; aucune opération autre que cash n'est retournée pour ce panier.
- Amorçage local : **274 séances** par ETF avant 2016, provenance EODHD,
  cours ajustés des splits. Pas de barre remplie artificiellement ; calendrier,
  unicité et OHLCV vérifiés. Les vingt barres communes aux sources ont un écart
  OHLC maximal de **0,01635 %**, sans remise à l'échelle pour forcer l'accord.
- EODHD : quatre requêtes dividendes autorisées par le compte existant ;
  dates de paiement disponibles et montants USD. **197 distributions** dans
  l'archive complète amorçage/octobre inclus, pas 197 paiements du portefeuille.
- Montants communs rapprochés à la précision décimale fournie ; précision
  Alpaca conservée lorsque compatible avec l'arrondi EODHD.
- Quatre distributions de période absentes des actions Alpaca : SPY
  2016-03-18, 2018-06-15 et 2026-09-18, TLT 2016-08-01. Seule celle de
  septembre 2026 est corroborée par un saut significatif de l'ajustement
  Alpaca. Les trois autres sont reprises d'EODHD avec **réserve de source
  unique**, pas déclarées certifiées par l'émetteur. L'amorçage est également
  EODHD seul. L'exhaustivité indépendante des distributions n'est pas prouvée.
- DBC : les actions Alpaca renvoient deux fois **0,18853 USD**, les 24 et
  26 décembre 2018 ; sa série `all` répercute les deux. EODHD ne conserve
  qu'un détachement le 24, record le 26, paiement le 31. Le
  [rapport annuel SEC 2018 de DBC](https://www.sec.gov/Archives/edgar/data/1328237/000156459019005072/dbc-10k_20181231.htm)
  confirme un seul montant annuel de 0,18853 USD, record le 26 et paiement
  le 31. La ligne Alpaca du 26 est **écartée explicitement comme doublon**,
  avec source HTML et reçu archivés. Aucune correction en base de production.

La [documentation des actions Alpaca](https://docs.alpaca.markets/us/reference/corporateactions-1)
ne garantit pas leur disponibilité immédiate après annonce. Des données
historiques accessibles aujourd'hui ne prouvent pas leur version disponible
à une ancienne décision. Les dates de déclaration EODHD parfois incohérentes
ne sont pas utilisées comme disponibilité PIT.

### Pas de double comptage des distributions

L'indice du **signal seulement** est reconstruit par :

`TR[J] = TR[J−1] × (clôture brute[J] + distribution détachée[J]) / clôture brute[J−1]`.

Le portefeuille n'utilise **jamais** cette série ajustée pour valoriser ses
positions ou exécuter ses ordres. Il reçoit une créance au détachement, sur les
parts détenues avant l'ouverture, puis du cash **à la date de paiement**, au plus
tôt la première séance disponible après celle-ci. Un achat à l'ouverture du
détachement n'y a pas droit ; une vente ce matin-là conserve sa créance.
Une créance entre dans la valeur liquidative, mais n'est pas dépensable avant
paiement. Les créances finales non encore payées restent distinguées du cash.

## Validation et réserves

- **16 tests ciblés** : données invalides/incomplètes, arrondis, causalité du
  signal, absence d'influence des prix futurs sur les décisions passées,
  ouverture suivante, quantités fixées avant le gap, manque de trésorerie,
  paiement différé, acheteur/vendeur au détachement, créances finales,
  absence de double comptage, frais identiques, report annuel et drawdown initial.
- **Neuf rejeux arithmétiques passent** : signaux recalculés indépendamment
  du module de simulation, calendrier mensuel, prix d'ouverture, quantités,
  frais, cash à chaque ordre, positions, droits et paiements des distributions,
  valeur liquidative quotidienne, rendements annuels et baisse maximale.
- Les fichiers d'entrée, protocoles, scripts et sorties sont reliés par SHA256.
  Cette seconde implémentation est réalisée par **le même assistant**, pas
  une revue humaine indépendante.
- Versions historiques courantes, pas archives PIT de 2016. Panier de quatre
  ETF choisi aujourd'hui, donc biais de choix des marchés non exclu. Périodes
  déjà observées : pas d'échantillon vierge de toute exploration.
- Prix d'ouverture quotidiens fournisseur comme approximation de fill,
  fractions et friction hypothétiques, pas de quotes/fills historiques ni
  certification de disponibilité de ces ETF pour un particulier européen.
- Aucun résultat fiscal net, aucune conversion EUR, frais de financement ou
  rémunération du cash. Aucune étude de levier, short ou dérivés ici.
- Aucun entraînement, appel LLM, ordre, écriture SQL, batch modifié ou service
  de production changé. Aucun job laissé en cours après le bilan.

## Fichiers et reproduction

Dossier : `F:/projets/artifacts/research/multi_asset_trend/20261020-v1`.

| Sous-dossier | Contenu |
|---|---|
| `http` | Sept reçus Alpaca, bars brutes/ajustées et actions |
| `supplement-v1` | Export SQL en lecture seule de l'amorçage, quatre reçus dividendes EODHD |
| `dbc-proof-v1` | HTML SEC et reçu horodaté de la preuve DBC |
| `qualified-v1` | Cours raccordés, distributions et journal des écarts |
| `backtest-v1` | `summary.csv`, `annual.csv`, neuf dossiers de cash/positions/ordres/signaux/distributions |
| `ledger-audit-v1` | Rapport de contrôle final, neuf scénarios PASS |

Les dossiers sont immuables : ne pas relancer l'acquisition pour reproduire un
calcul déjà livré. Pour vérifier les tests :

```powershell
python -m pytest tests/test_multi_asset_trend_data.py tests/test_multi_asset_trend_qualify.py tests/test_multi_asset_trend_backtest.py tests/test_multi_asset_trend_audit.py -q -o addopts='' --no-cov --basetemp=artifacts/tmp/multi-asset-new-test
```

Les modules `scripts.research.multi_asset_trend_backtest` et
`scripts.research.multi_asset_trend_audit` ne lisent que les archives locales.
Pour une nouvelle version explicitement autorisée, utiliser un nouveau dossier
et conserver l'ancien ; ils refusent l'écrasement des sorties existantes.

## Suite proposée, non lancée

Archiver ce résultat comme **diversification défensive possible, sans avantage
de rendement démontré**. Ne pas ajouter un modèle ni affiner arbitrairement les
horizons pour effacer les pertes observées. Si une poursuite est décidée,
la question distincte serait une comparaison à risque comparable, avec cash
rémunéré et instruments réellement accessibles, protocole figé puis période
future. Cela ne doit pas être présenté comme la confirmation de ce pilote.
