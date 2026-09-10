# Comparaison corrigée des ablations Oracle Extreme

## Statut

**Consolidation terminée — aucune promotion, aucun ensemble à ouvrir.**

Cette étude réévalue rétrospectivement les 14 ablations Oracle entraînées le
4 septembre 2026 contre la baseline complète
`model-factory-20260903174624-014164`. Elle remplace les anciens rendements
persistés par l'export corrigé des labels et conserve uniquement
`target_quality_valid=1`.

Harnais : `modelFactory/oracle_ablation_amplitude_compare.py`.

Artefact :
`artifacts/research/oracle_ablation_compare/comparison-20260907230557/`.

## Contrat de comparaison

- fenêtre OOF commune : 5 juillet 2018 au 5 janvier 2024 ;
- population strictement identique : 482 112 couples date/symbole ;
- 1 386 séances et 390 symboles ;
- même fingerprint des clés pour les 15 variantes ;
- rendement direction-neutral : valeur absolue du rendement H20 corrigé ;
- TOP20 et TOP10 recalculés chaque jour depuis le rang du score OOF ;
- anciennes colonnes `future_return` des prédictions ignorées ;
- comparaison rétrospective : aucun résultat ne peut promouvoir directement un
  profil vers le serving.

## Résultats principaux

| Profil | AUC extrême | Precision TOP10 | Lift amplitude TOP20 | Delta lift vs baseline | Jours meilleurs | Décision |
|---|---:|---:|---:|---:|---:|---|
| baseline complète | 0,6687 | 46,69 % | 7,046 % | — | — | référence |
| sans engineered transforms | 0,6995 | 46,92 % | 7,068 % | **+0,0215 pt** | 51,6 % | non promu |
| sans trend/position | 0,7053 | 46,90 % | 7,063 % | +0,0166 pt | 51,9 % | non promu |
| sans RSI/mean reversion | 0,6984 | 46,85 % | 7,060 % | +0,0136 pt | 53,1 % | non promu |
| sans momentum/returns | 0,6919 | 46,88 % | 7,055 % | +0,0084 pt | 50,4 % | non promu |
| sans régime relatif marché | 0,6965 | 46,99 % | 7,053 % | +0,0070 pt | 50,7 % | non promu |
| XS ranks seuls | 0,7106 | 46,60 % | 6,939 % | -0,1071 pt | 44,0 % | rejeté |
| sans volatility/range | 0,7149 | 45,98 % | 6,931 % | -0,1158 pt | 46,8 % | rejeté |
| raw simple | 0,6379 | 46,04 % | 6,456 % | -0,1642 pt | 43,7 % | rejeté |

Le classement par AUC est donc trompeur pour l'objectif économique. Le profil
`sans volatility/range` possède la meilleure AUC mais dégrade à la fois la
précision TOP10 et la concentration d'amplitude TOP20.

## Stabilité du meilleur profil

Le retrait des engineered transforms améliore huit semestres sur douze et en
dégrade quatre. Les écarts semestriels restent très petits, entre environ
-0,13 et +0,23 point. Son avantage journalier n'est positif que 51,6 % du
temps : il ne montre pas une domination stable.

## Complémentarité et ensemble

Les cinq meilleures variantes ont une corrélation de rang de 0,974 à 0,980
avec la baseline. Leur TOP20 recouvre celui de la baseline à 85–87 %, et elles
ne changent que 2,9–3,3 % des décisions quotidiennes.

Cette proximité exclut un ensemble maintenant : une moyenne des scores
combinerait essentiellement le même signal et risquerait de diluer l'Oracle
sans apporter une source indépendante d'amplitude.

## Décision

- ne pas remplacer `oracle.json` sur ces seuls résultats ;
- ne pas créer d'ensemble des ablations actuelles ;
- ne pas sélectionner une variante sur l'AUC seule ;
- conserver `sans engineered transforms` comme simple candidat de contrôle si
  une période réellement nouvelle devient disponible ;
- exiger une amélioration matérielle et stable de l'amplitude TOP20, et non un
  delta moyen de deux points de base.

La prochaine expérience doit apporter une information PIT nouvelle. Les
réglages supplémentaires des mêmes familles de prix ne sont plus prioritaires.
