# E20-C — Ablation incrémentale du volume d’ouverture

## Verdict

E20-C est terminé avec le verdict pré-enregistré `NO_GO_INCREMENTAL_VOLUME`.
Ajouter le volume, le nombre de transactions, la taille moyenne et le VWAP
Alpaca SIP au modèle mutualisé price-only ne produit pas d’amélioration OOF
stable ni d’amélioration économique.

Cette expérience est exclusivement une recherche. Elle ne modifie ni le
serving, ni les prédictions, ni le backtest, ni le live.

Artefact canonique :

```text
artifacts/research/oracle_opening_volume_ablation/e20c-opening-volume-ablation-20260914170421
```

## Données et population

La référence Oracle est le batch `model-factory-20260909051302-323684`, horizon
H20. Le backfill Alpaca SIP historique est complet : 1 763 séances terminées,
zéro échec et 575 835 lignes de features consolidées. Il utilise les champs
minute `t/o/h/l/c/v/n/vw`, en ajustement `raw`, de 09:30 à 10:30 New York.

L’évaluation conserve le checkpoint pré-enregistré de 30 minutes. Après
appariement et contrôle de complétude, 559 513 événements sont éligibles. Les
prédictions réellement OOF couvrent 354 967 événements.

L’acquisition historique n’est pas une preuve de disponibilité PIT originale.
La causalité repose sur l’utilisation exclusive des barres terminées avant le
checkpoint. Aucun PnL d’entrée à 10:00 n’est revendiqué.

## Comparaison verrouillée

Deux LightGBM mutualisés sont entraînés sur exactement les mêmes lignes, dates,
folds et hyperparamètres :

1. `price_only` : probabilité Oracle et trajectoire OHLC aux checkpoints 5, 15
   et 30 minutes ;
2. `price_plus_volume` : mêmes variables, auxquelles sont ajoutés volume,
   nombre de transactions, taille moyenne, VWAP relatif à l’ouverture, rangs
   cross-sectionnels quotidiens et ratios d’accumulation 5/15/30 minutes.

Le protocole emploie neuf folds expanding-window, des fenêtres de test de 126
séances et un embargo de 20 séances correspondant à H20. La cible est le signe
du rendement futur H20. Le seuil de confiance secondaire est fixé à 0,55.

## Résultats OOF appariés

| Mesure | Prix seul | Prix + volume | Delta volume |
|---|---:|---:|---:|
| AUC | 0,5431 | 0,5409 | -0,0021 |
| Brier | 0,25148 | 0,25101 | -0,00047 |
| Log-loss | 0,69644 | 0,69546 | -0,00098 |
| Accuracy | 52,35 % | 52,76 % | +0,41 pt |
| Accuracy D1/D10 | 52,64 % | 53,30 % | +0,65 pt |
| Accuracy, confiance >= 0,55 | 54,17 % | 54,41 % | +0,24 pt |
| Rendement cible signé moyen | +1,298 % | +1,250 % | -0,047 pt |
| Rendement signé, confiance >= 0,55 | +2,206 % | +2,082 % | -0,123 pt |

Le volume améliore légèrement la calibration et la précision ponctuelle, mais
réduit l’AUC de classement et les deux mesures de rendement signé. Ce profil ne
correspond pas à une information directionnelle exploitable.

## Stabilité

- AUC améliorée dans 4 folds sur 9 seulement : 44,44 % ;
- rendement signé amélioré dans 4 folds sur 9 seulement : 44,44 % ;
- AUC améliorée dans 3 semestres sur 10 seulement : 30 % ;
- gains visibles surtout en 2021H2, 2022H1 et marginalement 2025H1 ;
- dégradations fortes en 2021H1, 2022H2, 2023H1 et 2023H2.

Un effet de régime est donc plus probable qu’un alpha volume stable.

## Gates et décision

Seul le gate de gain de précision D1/D10 passe. Échouent : delta AUC minimal,
gain Brier minimal, non-dégradation du rendement signé, stabilité par fold et
stabilité par semestre.

Conséquences :

- ne pas ajouter ces features au modèle directionnel de production ;
- ne pas optimiser leurs seuils sur les mêmes données ;
- ne pas lancer de réplication IEX : le SIP consolidé, informationnellement plus
  riche, échoue déjà ;
- conserver le backfill comme artefact de recherche reproductible ;
- la politique price-only E20-B reste la meilleure variante de cette famille,
  mais exige toujours un replay économique d’entrée retardée avant tout usage.

Voir [E20-B price-only](oracle_opening_price_confirmation_e20b.md) et le
[registre des expériences](experiences_done.md).
