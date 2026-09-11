# E16 — Reconstruction PIT de l’univers tradable et réplication E12/E15

## Verdict

**`NO_GO_OR_BLOCKED`.** E16 couvre 1 764/1 764 séances Oracle et
582 698/582 700 événements (99,9997 %) sans données futures. Malgré cette
couverture, aucune modification du lifecycle n’est promue.

Le contrat `prod_no_tp` est favorable sur l’ensemble 2018–2025, mais son delta
depuis 2023 vaut **−0,2277 % par date**. Il détériore aussi les queues de pertes :

| Contrat portefeuille | Rendement moyen | Q05 | Q01 |
|---|---:|---:|---:|
| PROD | +0,5444 % | −15,44 % | −22,18 % |
| PROD sans TP | +2,0341 % | −16,91 % | −22,65 % |

Le gain global sans TP est ancien, concentré et payé par une queue gauche plus
profonde. Il ne survit pas au gate de confirmation temporelle.

## Pourquoi E16 était nécessaire

E12 et E15 ne trouvaient que 60 dates `full` sur 1 764. La base contient en
réalité **1 750 dates** avec un run historique étiqueté `full`, mais seulement
60 sont encore canoniques. Pour 1 690 dates, un backfill `degraded` publié plus
tard a retiré `is_canonical` au run `full` antérieur. Le contenu n’a pas été
supprimé : c’est un défaut de gouvernance de la sélection canonique.

Le vieux libellé `full` ne constitue cependant pas une preuve suffisante selon
le contrat actuel :

| Champ de preuve des 427 541 lignes `full` | Couverture |
|---|---:|
| `history_days` | 0 % |
| `bars_available` | 0 % |
| `close_price` | 0 % |
| `adv_usd` | 0 % |
| `spread_bps` | 17,81 % |
| `market_cap` | 100 % |
| `atr_pct_20` | 100 % |
| `earnings_blackout` | 100 % |

E16 ne requalifie donc pas automatiquement ces anciennes lignes en preuve PIT
stricte.

## Contrat bar-PIT reconstruit

La sensibilité primaire est calculée uniquement avec les faits observables à J :

1. barre exacte à J, non synthétique (`is_filled = false`) ;
2. close ajusté et volume strictement positifs ;
3. au moins 252 séances valides connues jusqu’à J ;
4. prix ≥ 10 USD ;
5. volume moyen 20 séances ≥ 50 000 titres ;
6. ADV20 ≥ 10 M USD ;
7. action US, hors ETF, ETN, fonds, note structurée et produit à
   levier/inverse.

Tous les rollings sont backward-looking et incluent au maximum J. Un test
vérifie qu’une modification des barres futures ne change pas l’éligibilité à J.

La classification par nom et `asset_class` est un référentiel statique sans
`available_at`. Elle sert seulement à l’identité de l’instrument, jamais à
déduire son ancien état `tradable` ou `bars_available`.

## Couches non imputées

E16 n’invente pas la capitalisation historique, le spread absent ni les
earnings non couverts. Au moment du run, les capitalisations disponibles dans
`stock_fundamentals_daily` sont des snapshots Finnhub datés du 9 septembre
2026 : elles ne peuvent pas être rétro-projetées sur 2018–2025. Les quotes
commencent le 27 juillet 2020. Le contrat production strict complet reste donc
non reconstructible sur toute la période.

## Couverture et exclusions

- 582 700 événements audités ;
- 533 981 tradables selon le contrat bar-PIT, soit 91,64 % ;
- 1 253 symboles tradables au moins une fois ;
- 48 659 événements exclus par l’identité de l’instrument ;
- 45 rejetés par volume20 ;
- 13 par historique insuffisant ;
- 2 par barre absente ou invalide.

Le détail d’identité comporte 33 171 événements ETF/ETN, 10 547 produits à
levier/inverses, 2 532 autres produits collectifs et 2 409 fonds. Les REIT dont
le nom contient uniquement `Trust` ne sont pas exclus pour ce seul mot.

## Réplication E12

Après déduplication des signaux chevauchants et filtre bar-PIT :

- 34 492 événements admissibles ;
- capacité fixe de huit positions : 712 trades ;
- H20 fixe moyen : **+2,8080 %** ;
- IC95 journalier : **[+0,6308 % ; +5,3481 %]** ;
- lifecycle PROD dynamique : 1 999 trades sur 1 139 dates ;
- rendement PROD moyen : **+0,5444 %** ;
- IC95 journalier : **[−0,2728 % ; +1,0476 %]**.

La détection d’amplitude reste forte avant lifecycle, mais le résultat
exécutable PROD n’est pas statistiquement établi.

## Réplication E15

### Trailing après +0,5R

Le candidat primaire pré-enregistré échoue : delta événement **+0,0418 %** par
date, IC95 **[−0,0344 % ; +0,1136 %]**, puis delta portefeuille
**−0,1647 %**. La confirmation depuis 2023 vaut **−0,2643 %** et Q05/Q01 se
détériorent. La conclusion E15 est confirmée avec une bien meilleure couverture.

### Suppression du TP

Sur toute la période, `prod_no_tp` produit :

- delta événement +0,6297 % par date, IC95
  [+0,1993 % ; +1,0872 %] ;
- delta portefeuille +0,6549 % par date, IC95
  [+0,1099 % ; +1,2652 %] ;
- rendement portefeuille moyen +2,0341 %.

Les gates récents et de risque échouent pourtant :

- depuis 2023 : **−0,2277 %** par date ;
- 2024H2 : lift −1,2481 point ;
- 2025H1 : lift −0,7391 point ;
- Q05 passe de −15,44 % à −16,91 % ;
- Q01 passe de −22,18 % à −22,65 %.

Sans TP, la durée moyenne passe de 7,01 à 13,39 séances et le nombre de trades
de 1 999 à 1 028. La comparaison intègre donc correctement l’effet de capacité.

## Gates pré-enregistrés

| Gate | Résultat |
|---|---|
| Couverture séances ≥ 95 % | PASS — 100 % |
| Événements évaluables ≥ 90 % | PASS — 99,9997 % |
| Produits non-actions exclus | PASS |
| Aucune donnée post-J | PASS |
| Contrat production strict reconstructible | **FAIL** |
| No-TP positif depuis 2023 | **FAIL** |
| IC95 du delta portefeuille no-TP > 0 | PASS |
| Q05 non dégradé | **FAIL** |
| Q01 non dégradé | **FAIL** |

Le verdict ne vient donc pas seulement des capitalisations manquantes : la
sensibilité bar-PIT quasi complète rejette déjà le no-TP sur la période récente
et sur le risque de queue.

## Conséquences

- lifecycle PROD, stops, trailing et TP inchangés ;
- aucune écriture dans les tables et aucun changement du serving/backtest ;
- ne pas promouvoir `prod_no_tp` ;
- corriger séparément la gouvernance canonique afin qu’un `degraded` ne puisse
  pas détrôner silencieusement un `full` de meilleure qualité ;
- persister à l’avenir provenance et `available_at` des capitalisations et de
  l’identité instrument pour obtenir un grade production strict.

## Reproductibilité

```powershell
python -u -m modelFactory.oracle_tradable_pit_reconstruction --oracle-gate artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet --bootstrap-samples 2000 --log-level INFO
```

Artefact canonique :

```text
artifacts/research/oracle_tradable_pit_reconstruction/oracle-tradable-pit-reconstruction-20260911192318
```

`report.json` contient le verdict ; `bar_pit_membership.parquet` les clés
admises ; `bar_pit_event_audit.parquet` les variables et motifs ; les fichiers
`portfolio_<contrat>.csv` contiennent les huit replays. Le code vit dans
`modelFactory/oracle_tradable_pit_reconstruction.py` et ses tests dans
`tests/test_oracle_tradable_pit_reconstruction.py`.
