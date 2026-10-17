# Oracle parcours — comparaison économique appariée LightGBM / CatBoost

14 octobre 2026. GO utilisateur, recherche locale, aucune promotion en production.

## Question

La grille annuelle précédente changeait de champion : CatBoost en 2024,
LightGBM en 2025, CatBoost en 2026. Cela empêche d'attribuer toutes les différences
entre années au seul régime de marché. Cette expérience compare les deux familles
**dans chaque année**, sans changer les protections ni rechercher de nouveaux
hyperparamètres. Un modèle d'amplitude ne prédit pas le côté LONG gagnant.

## Contrat figé avant les résultats

- Modèles annuels fournis : `model-factory-20261014052407-a4bd20` pour 2024,
  `model-factory-20261014052414-155d09` pour 2025,
  `model-factory-20261014052423-4df571` pour 2026.
- Même fold causal, population actuelle de 1 790 titres, mêmes 173 features,
  mêmes dates de train/validation et données pour les deux familles.
- Deux poids **déjà entraînés** et archivés dans chaque fold ; aucun nouveau fit.
- TOP5 calculé sur la population observable complète, avant qualité/risque à J,
  par score décroissant ; symbole en tie-break. Pas de rendements futurs utilisés
  pour sélectionner les titres. Pas de remplacement du sixième après rejet du cinquième.
- TOP5 LONG, SL5 / trailing15 / TP20, protections ancrées au fill J+1.
- Capital 4 000 USD par portefeuille, plafond d'entrée ×2, mêmes frais,
  financement, contraintes, rejets de budget et risques que la grille précédente.
- Pas de renforcement d'un titre détenu, pas de sortie forcée H20 ni terminale.
- 2024 et 2025 complètes ; 2026 jusqu'au 30 septembre. Positions ouvertes valorisées,
  PnL latent séparé du réalisé. Six portefeuilles chronologiques, pas six sommes
  de rendements indépendants de titres.

| Année | Fold identique | Train / validation labels disponibles au plus tard | AUC validation LightGBM | AUC validation CatBoost | Champion archivé |
| --- | --- | --- | --- | --- | --- |
| 2024 | 2023-12-05 | 2023-06-05 / 2023-12-04 | 0,78855 | 0,78895 | CatBoost |
| 2025 | 2024-12-05 | 2024-06-05 / 2024-12-04 | 0,78458 | 0,78312 | LightGBM |
| 2026 | 2025-12-10 | 2025-06-10 / 2025-12-09 | 0,80151 | 0,80185 | CatBoost |

Les AUC indiquent la détection d'amplitude, **pas** une sélection par profit ni
une capacité prouvée de distinguer LONG/SHORT. L'écart d'AUC est faible ; le test
économique ne suppose pas que le meilleur de validation sera forcément rentable.

## Contrôles et réserves

Source : `us_oracle_path_top5_leverage/20261014-v3` et ses caches de features/prix.
Les poids des deux familles, contrats, caches, code, tests et résultats sont
identifiés par SHA-256. Classement, scores et qualité de chaque champion reproduits
**exactement** : 1 260 lignes 2024, 1 250 lignes 2025, 935 lignes 2026.
Le portefeuille du champion doit aussi reproduire trades et courbe d'equity
exactement avant que la comparaison soit acceptée.

Les frames de prix des deux bras contiennent l'union de leurs candidats, le
benchmark et les successeurs d'opérations sur titres : pas de ticker du challenger
oublié à cause du périmètre des anciens TOP5. Mêmes données pour les titres communs.
Le moteur et la comptabilité sont réutilisés sans modification de leurs sources.
Les prix/volumes détenus ou claims cash non qualifiés font échouer le cas ;
aucun titre n'est retiré après observation des pertes pour terminer le replay.

Recouvrement TOP5 avant rejets : 3,52 titres communs /5 en 2024 (70,48 %),
3,85 /5 en 2025 (76,96 %), 3,68 /5 en 2026 (73,69 %). Ce sont des memberships,
pas des positions assurées d'être exécutées.

Périodes et protections déjà inspectées : pas un nouveau holdout indépendant,
ni sélection d'un nouveau champion sur les profits de test. Univers de survivants,
secteurs actuels non PIT, macro sans vintages certifiés, prix ajustés, frais/fills
simulés, marginabilité historique et dividendes incomplets restent réservés.
**Pas une parité courtier ni un rendement total historique certifiés.**
Aucun SQL, API, ordre, modèle réentraîné, batch ou configuration de production modifié.

## Suivi et résultats

Run canonique : `artifacts/research/us_oracle_path_backend_economic/20261014-v1`.
37 tests ciblés réussis ; protocole figé, préparation et parités de scores terminées.
**Six backtests complets, zéro échec.** Les trois portefeuilles des champions
archivés reproduisent exactement les trades et les points des courbes d'equity
de leurs références. Sources, candidats et tous les fichiers des six cas
revérifiés après le calcul.

### Résultats appariés

| Période | Rendement LightGBM | Rendement CatBoost | Avantage CatBoost en points | DD LightGBM | DD CatBoost |
| --- | --- | --- | --- | --- | --- |
| 2024 | −34,83 % | −16,74 % | +18,09 | −39,44 % | −32,83 % |
| 2025 | +9,93 % | +33,12 % | +23,19 | −20,91 % | −21,79 % |
| 2026 janvier–septembre | +11,11 % | +36,14 % | +25,03 | −25,74 % | −26,19 % |

Même capital initial de 4 000 USD, frais et intérêts inclus ; valeur terminale
avec positions ouvertes, hors dividendes non qualifiés. Aucun résultat ne résulte
d'un nouveau choix TP/SL/trailing selon l'année.

| Période / backend | Capital final USD | PnL réalisé USD | PnL latent USD | Intérêts USD | Positions clôturées | Taux gagnant clôturé | Positions ouvertes | Levier moyen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 LightGBM | 2 606,82 | −1 339,24 | −16,46 | 37,49 | 159 | 18,24 % | 3 | ×0,947 |
| 2024 CatBoost | 3 330,30 | −578,08 | −22,81 | 68,81 | 151 | 20,53 % | 2 | ×1,030 |
| 2025 LightGBM | 4 397,34 | +385,31 | +64,16 | 52,12 | 146 | 28,77 % | 2 | ×0,709 |
| 2025 CatBoost | 5 324,92 | +1 277,57 | +118,24 | 70,89 | 140 | 29,29 % | 3 | ×0,825 |
| 2026 LightGBM | 4 444,59 | +357,57 | +108,95 | 21,94 | 152 | 26,32 % | 4 | ×0,496 |
| 2026 CatBoost | 5 445,76 | +1 257,15 | +205,56 | 16,95 | 146 | 26,71 % | 4 | ×0,485 |

CatBoost gagne en rendement sur **les trois périodes**. Ce bénéfice ne provient
pas seulement des gains latents : son PnL réalisé est aussi supérieur dans les
trois comparaisons. Son taux de réussite clôturé est légèrement meilleur, mais
la différence de PnL est beaucoup plus large que celle du taux de réussite.
La durée, la composition et le réinvestissement du portefeuille contribuent.

Ce n'est pas une supériorité uniforme en risque : le DD CatBoost est meilleur
en 2024, légèrement pire en 2025 et 2026. Le régime/sizing module toujours
l'exposition ; le plafond ×2 ne signifie pas ×2 en permanence. Zéro déficit de
maintenance observé selon les seules hypothèses génériques de cette recherche.

**2024 reste perdante pour les deux familles** : le changement de backend n'est
donc pas une explication suffisante ni une solution à la mauvaise année. De même,
la bonne année 2025 précédente n'était pas simplement due au recours à LightGBM :
CatBoost fait mieux dans le même fold et contrat économique.

Conclusion : **avantage économique apparié CatBoost observé**, candidat à une
confirmation indépendante sur ce contrat, pas nouveau champion de production
automatique. Les périodes/protections étaient déjà connues et les prix/PIT/coûts
restent réservés. Aucun modèle, seuil, batch, SQL, ordre ou configuration live modifié.

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_path_backend_economic\20261014-v1\progress.json
```

`protocol.json`, `score-parity.json`, `candidates.parquet`, `report.json` final.
Par backend puis année : courbe d'equity, trades, exécutions/rejets,
maintenance, positions ouvertes, `case-report.json` natif et `backend-report.json`
avec résultat de comparaison. Un cas FAILED n'est pas un rendement annuel complet.

Ce test peut mesurer l'effet du backend dans le contrat étudié. Il ne démontrera
pas, à lui seul, qu'une famille est supérieure pour tout régime, qu'il faut
changer de famille après une mauvaise année, ou qu'un modèle spécialisé par
période fonctionnerait. Aucun ajustement des protections après les résultats.
