# P0e — Comparaison OOF ancien Oracle 400 vs Balanced 400

## Verdict

Le batch `model-factory-20260908183941-7826b4`, entraîné sur le nouvel univers
P0d, est techniquement valide et directement comparable au témoin
`model-factory-20260907170018-0e94ac`.

Le nouvel univers améliore légèrement l'AUC globale, mais dégrade de façon
robuste les métriques du gate réellement utilisé, notamment au TOP20. Il n'est
donc pas promu comme remplacement plus performant de l'ancien Oracle 400.

Cette décision ne réhabilite pas l'ancien univers comme univers canonique : P0
et P0b ont montré sa sélection biaisée vers les titres structurellement
volatils. `Balanced 400` reste l'échantillon de recherche diversifié. La suite
scientifique doit entraîner l'Oracle mutualisé sur l'univers large à admission
quotidienne P0b, plutôt que chercher le meilleur sous-ensemble statique de 400.

## Contrat de comparabilité

| Élément | Ancien | Nouveau |
|---|---|---|
| cible | binary extreme H20 | identique |
| définition | TOP10 ∪ BOTTOM10 cross-sectionnel | identique |
| profil | `oracle-o0-canonical-deduplicated-20260903` | identique |
| hash du profil | `2086e9e...5378c` | identique |
| features | 168 | 168 |
| folds | 14 | 14 |
| première/dernière date OOF | 2018-07-05 / 2025-07-11 | identique |
| symboles | 399 | 400 |
| lignes OOF valides | 630 340 | 682 744 |
| univers quotidien médian | 358 | 394 |

Les prédictions analysées sont celles de `oracle_extreme_predictions`, jointes
aux labels `global_oracle_labels` de même batch/H20 et limitées à
`target_quality_valid=1` et aux folds OOF non nuls.

## Résultats globaux

| Mesure | Ancien 400 | Balanced 400 | Delta |
|---|---:|---:|---:|
| AUC | 0,6851 | **0,6882** | +0,0031 |
| Brier brut | **0,2210** | 0,2303 | +0,0093, moins bon |
| précision TOP10 | **46,01 %** | 44,89 % | −1,12 pt |
| rappel TOP10 | **23,92 %** | 22,66 % | −1,27 pt |
| précision TOP20 | **40,00 %** | 38,94 % | −1,05 pt |
| rappel TOP20 | **41,37 %** | 39,14 % | −2,23 pt |
| lift amplitude TOP10 | **1,816** | 1,716 | −0,100 |
| rétention amplitude extrême TOP10 | **82,24 %** | 80,15 % | −2,09 pt |
| lift amplitude TOP20 | **1,591** | 1,515 | −0,076 |
| rétention amplitude extrême TOP20 | **72,67 %** | 71,10 % | −1,57 pt |
| monotonie des déciles | **0,988** | 0,964 | −0,024 |

L'AUC et le Brier ne doivent pas dominer la décision : les deux modèles sont
évalués sur des populations et des déciles reconstruits différents, et le gate
de trading retient le sommet du classement. Les métriques TOP20 et l'amplitude
capturée sont donc prioritaires.

## Robustesse temporelle

Sur 15 semestres disponibles, le nouvel univers gagne seulement :

- 2/15 semestres en AUC ;
- 5/15 en précision TOP10 ;
- 5/15 en précision TOP20 ;
- 3/15 en lift d'amplitude TOP20.

Il fait mieux sur certains régimes, notamment 2021H2, 2022H1 et 2025H2, mais la
baisse domine la période. Le dernier semestre n'est que partiel (3 200 lignes)
car les folds OOF s'arrêtent le 11 juillet 2025 ; il ne doit pas être surpondéré.

Le bootstrap mobile par blocs de 21 séances confirme au TOP20 :

| Delta nouveau − ancien | Moyenne | IC 95 % blocs |
|---|---:|---:|
| précision | −1,05 pt | [−1,90 ; −0,27] pt |
| rappel | −2,23 pt | [−3,07 ; −1,50] pt |
| lift amplitude | −0,0758 | [−0,1104 ; −0,0445] |
| rétention amplitude extrême | −1,57 pt | [−2,75 ; −0,38] pt |

Tous les intervalles TOP20 sont entièrement négatifs. La baisse n'est pas
attribuable à quelques séances isolées.

## Contrôle sur les 101 symboles communs

Les deux univers partagent 101 symboles et 169 650 lignes date × symbole. Les
rendements futurs sont identiques bit-for-bit sur ces lignes. La corrélation de
Spearman entre scores est 0,834 : le changement d'univers modifie donc aussi le
classement appris et les labels cross-sectionnels.

Sur ce sous-ensemble commun, le nouveau modèle présente une meilleure AUC
(0,6889 contre 0,6619) et une meilleure précision TOP20 (38,54 % contre
33,18 %), mais un rappel légèrement inférieur (39,17 % contre 39,93 %) et un
lift d'amplitude TOP20 pratiquement identique (1,4524 contre 1,4542).

Ce contrôle suggère que l'entraînement n'est pas intrinsèquement dégradé. La
perte globale vient surtout de la composition plus diversifiée et plus difficile
du nouvel univers, ainsi que de la redéfinition quotidienne des déciles.

## Diagnostic par strate du Balanced 400

| Strate | AUC | Précision TOP20 | Lift amplitude TOP20 |
|---|---:|---:|---:|
| small caps | 0,6860 | 43,66 % | 1,496 |
| mid caps | 0,6873 | 39,82 % | 1,498 |
| large caps | 0,6686 | 30,99 % | 1,483 |
| bêta Q1 | 0,6844 | 34,76 % | 1,615 |
| bêta Q2 | 0,6996 | 36,20 % | 1,555 |
| bêta Q3 | 0,6889 | 39,04 % | 1,433 |
| bêta Q4 | 0,6756 | 38,92 % | 1,448 |
| bêta Q5 | 0,6517 | 41,08 % | 1,338 |

La faiblesse n'est pas limitée à une seule catégorie, mais deux difficultés se
dégagent : les large caps sont moins séparables selon cette cible relative et le
quintile de bêta le plus élevé conserve mal l'amplitude au sommet du classement.
Cela ne justifie pas de les supprimer a posteriori : une telle suppression
recréerait précisément le biais de sélection que P0 cherchait à éliminer.

## Décision et prochaine étape

1. Conserver `model-factory-20260907170018-0e94ac` comme témoin historique,
   pas comme preuve d'un univers sain.
2. Conserver `oracle_balanced_400_202512.txt` pour smoke tests, ablations et
   diagnostics par strate.
3. Ne pas optimiser les quotas P0d en fonction de ces résultats OOF : ce serait
   une nouvelle sélection sur la performance.
4. Ouvrir P0f : intégrer l'admission quotidienne P0b dans le trainer Oracle et
   entraîner un modèle mutualisé sur la population large disponible à chaque
   date.
5. Comparer P0f aux deux 400 sur dates communes, avec les mêmes métriques et
   sans choisir de seuil sur 2026H1.

## Artefacts reproductibles

```text
artifacts/research/oracle_universe_p0e/p0e-20260908204108/report.json
artifacts/research/oracle_universe_p0e/p0e-20260908204108/old_by_fold.csv
artifacts/research/oracle_universe_p0e/p0e-20260908204108/new_by_fold.csv
artifacts/research/oracle_universe_p0e/p0e-20260908204108/old_by_semester.csv
artifacts/research/oracle_universe_p0e/p0e-20260908204108/new_by_semester.csv
```

Comparateur : `modelFactory/oracle_universe_p0e_compare.py`.
