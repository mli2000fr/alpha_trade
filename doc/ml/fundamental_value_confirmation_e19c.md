# E19-C — Confirmation verrouillée du facteur valeur PIT

Statut final : `COMPLETE_NO_GO`.

Ce protocole est figé avant lecture des deux périodes laissées hors des
métriques OOF d’E19-B. E19-C ne constitue ni une optimisation, ni une nouvelle
recherche de formule.

## Hypothèse et signal immuable

Les actions relativement peu chères doivent surperformer les actions chères à
H60 et H120, après neutralisation quotidienne secteur/taille. Le score est
exactement `score_value__sector_size_neutral` produit par E19-B : rangs inverses
de `pe_ratio`, `pb_ratio`, `ps_ratio` et `ev_to_ebitda`, tous strictement
positifs, au moins deux ratios présents, winsorisation 1/99, poids égaux, puis
régression quotidienne sur secteurs et `log10(market_cap)` PIT. Aucun signe,
ratio, poids, seuil, tail ou horizon ne pourra être modifié après le run.

## Données et holdouts

Source canonique : panel E19-B `fundamental-alpha-book-20260912112042`, dont les
empreintes sont enregistrées dans le rapport E19-C.

1. `EARLY_HOLDBACK` : 2 juillet 2018 au 1er juillet 2020 ;
2. `LATE_HOLDBACK` : 10 juillet 2025 au 31 décembre 2025.

Ces fenêtres n’ont pas contribué aux métriques OOF E19-B. La formule étant
déterministe et sans fit, le premier bloc avait servi de burn-in mais pas à
estimer des paramètres. Il s’agit de confirmations historiques laissées de
côté, pas d’un OOS prospectif collecté après pré-enregistrement.

## Portefeuilles, mesures et gates

- H60 primaire et H120 confirmation ; rebalance 20 séances ;
- top/bottom 20 %, équipondérés, minimum 10 titres par jambe ;
- coût aller-retour 6 bps par jambe ;
- IC sur rendement excédentaire à SPY, LONG/SHORT dollar-neutral ;
- LONG contre SPY et univers, bottom contre univers ;
- block-bootstrap 95 % ; cinq sous-univers `sha256(symbol) modulo 5` avec
  tails recalculés.

Un `GO_RESEARCH_SHADOW` exige simultanément : au moins 25 cohortes ; à H60,
IC et spread positifs avec bornes basses 95 % positives, LONG positif contre
SPY et univers, bottom sous-performant l’univers, spread positif dans les deux
holdouts ; à H120, IC et spread positifs, borne basse du spread positive et
deux holdouts positifs ; au moins quatre partitions hash sur cinq positives
aux deux horizons. Tout échec donne `NO_GO`. Aucune promotion production n’est
automatique.

Sorties : `report.json`, `cohorts.csv`, `daily_ic.csv` et
`hash_robustness.csv`.

## Résultats canoniques

Run : `fundamental-value-confirmation-20260912114827`.

La population contient 1 798 symboles, 1 074 031 observations et 626 séances.
Le test comprend 33 cohortes H60 et 32 cohortes H120, avec environ 185 actions
par jambe.

| Mesure | H60 | H120 |
|---|---:|---:|
| IC moyen | -3,61 % | -5,23 % |
| IC95 | [-5,15 % ; -2,01 %] | [-7,72 % ; -3,01 %] |
| LONG absolu net | +0,32 % | +3,07 % |
| SHORT absolu net | -2,31 % | -6,26 % |
| LONG/SHORT net | -0,99 % | -1,59 % |
| IC95 du LONG/SHORT | [-2,37 % ; +0,24 %] | [-4,80 % ; +0,58 %] |
| LONG contre SPY | -2,16 % | -2,70 % |
| LONG contre univers | -0,99 % | -1,10 % |
| bottom sous-performance univers | -1,00 % | -2,08 % |

La rupture est temporelle :

- `EARLY_HOLDBACK` : spread `-1,63 %` à H60 et `-2,71 %` à H120 ;
- `LATE_HOLDBACK` : spread `+1,35 %` à H60 et `+3,25 %` à H120.

Les cinq partitions hash sont négatives aux deux horizons. Aucun des quinze
gates ne passe à l’exception du nombre minimal de cohortes. Verdict : `NO_GO`.
Le résultat favorable E19-B était donc dépendant de période et ne confirme pas
un alpha valeur universel. Il est interdit de supprimer le holdout ancien,
d’inverser le score ou d’optimiser un filtre de régime sur ces résultats.

Artefact :
`artifacts/research/fundamental_value_confirmation/fundamental-value-confirmation-20260912114827`.
