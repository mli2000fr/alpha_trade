# Contexte intraday de marché après Oracle TOP20

## Statut

**Expérience terminée — `NO_GO` direction et amplitude.**

Cette piste teste si la trajectoire intraday commune du marché explique le sens
des événements Oracle mieux que les prix du symbole seul. Elle utilise SPY,
QQQ, IWM et VXX ; VXX est explicitement un proxy de stress négociable, pas le
VIX.

Code : `modelFactory/directional_data_research/intraday_market_context_pilot.py`.

Artefact :
`artifacts/research/eroya_directional/intraday-market-context-20260908052823/`.

## Contrat PIT

- barres Eroya ajustées de cinq minutes ;
- séances régulières 09:30–16:00 America/New_York ;
- signal disponible uniquement après la clôture J ;
- première entrée possible à l'open J+1 ;
- événements issus des 393 dates uniques de la campagne intraday sous-jacent ;
- 852 dates communes aux quatre séries de marché ;
- 364 événements avec marché et labels corrigés, dont 305 tails H20 ;
- huit hypothèses corrigées ensemble par Bonferroni.

La collecte contient 172 831 barres SPY, 171 184 QQQ, 146 854 IWM et 144 860
VXX. Aucun marché manquant n'est forward-fillé.

## Signaux directionnels

| Feature | AUC D1/D10 | Spearman rendement | Stabilité | p corrigée | Verdict |
|---|---:|---:|---:|---:|---|
| rendement IWM moins SPY | **0,52** | +0,05 | 4/8 | 1,00 | `NO_GO` |
| risk-on actions moins VXX | 0,50 | -0,01 | 3/8 | 1,00 | `NO_GO` |
| rendement moyen SPY/QQQ/IWM | 0,49 | -0,01 | 3/8 | 1,00 | `NO_GO` |
| rendement QQQ moins SPY | 0,46 | -0,07 | 2/8 | 1,00 | `NO_GO` |

Le meilleur effet reste trop faible et instable. La dépendance au régime déjà
observée dans les anciens modèles directionnels n'est donc pas résolue par le
chemin intraday des grands indices/ETF.

## Signaux d'amplitude

| Feature | AUC extrême | Spearman amplitude | Stabilité | p corrigée | Verdict |
|---|---:|---:|---:|---:|---|
| volatilité réalisée SPY | 0,53 | +0,06 | 6/8 | 1,00 | `NO_GO` |
| mouvement absolu VXX | 0,53 | -0,05 | 7/8 | 1,00 | `NO_GO` |
| volatilité moyenne SPY/QQQ/IWM | 0,52 | +0,04 | 5/8 | 1,00 | `NO_GO` |
| dispersion des rendements actions | 0,51 | +0,01 | 4/8 | 1,00 | `NO_GO` |

La stabilité apparente du mouvement VXX ne s'accompagne ni du signe continu
attendu ni d'une significativité. Aucun bonus d'amplitude Oracle n'est permis.

## Décision

- ne pas ajouter ces huit features à Oracle, LONG ou SHORT ;
- ne pas entraîner de modèle de régime intraday ;
- ne pas inverser QQQ/SPY après lecture du résultat ;
- ne pas retester d'autres pondérations SPY/QQQ/IWM/VXX sur cette population ;
- conserver les artefacts comme résultat négatif reproductible.

La prochaine piste doit apporter une nouvelle donnée, pas une nouvelle moyenne
des mêmes prix de marché. La chaîne OPRA complète reste en attente du service
d'archives ; borrow fee/utilization et auction imbalance restent bloqués faute
de source PIT accessible.

