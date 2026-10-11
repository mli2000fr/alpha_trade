# US — Résultats régime LONG, force relative et breadth

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

**Actualisation macro 2026 :** [recalcul avec couverture complète](us_2026_regime_macro_actualise.md).
Le constat initial d'absence macro ci-dessous décrit l'état du premier run.
Le nouveau calcul bloque les LONG le 30 mars, conserve 1 651 candidats
sur 1 680 et donne +8,29 % H20 moyen contre +8,68 % sans régime.

4 octobre 2026. [Protocole figé avant calcul](us_confirmation_secteur_breadth_protocole.md).
Statut : **TERMINÉ — pas d'amélioration directionnelle stable démontrée**.
Ne pas intégrer ces nouveaux filtres en production sur la base de ce test.
Ce constat ne recommande pas de supprimer les protections de régime existantes.

## 1. Le régime a-t-il été pris en compte ?

Oui, cette expérience complète explicitement l'audit précédent. Le code
`service/market/regime_manager.py` interdit les nouvelles entrées LONG en
`capital_preservation`, `close_only` et `cash_only`. Lire seulement
`allow_new_entries` manquerait le premier cas.

Nous avons joint les modes archivés exacts à J aux 50 471 observations MV
sélectionnées (50 467 labels valides). Toutes ont un mode reconnu et un
champ de permission renseigné. On ne remplace pas une permission absente
par une autorisation. La sélection sectorielle a un contexte suffisamment
fourni pour 50 144 observations ; 327 restent sans support admissible.

| Mode archivé | Observations | D10 réel | D1 réel | Rendement H20 moyen brut |
|---|---:|---:|---:|---:|
| normal | 35 922 | 26,94 % | 23,17 % | +2,82 % |
| capital_preservation | 465 | 32,04 % | 26,02 % | +5,94 % |
| close_only | 14 084 | 28,52 % | 22,46 % | +6,25 % |

Sur les observations en régime connu qui ne permet pas les LONG, le
rendement H20 moyen est +6,24 %, D10 28,64 %, D1 22,57 %. Le régime exclut
donc aussi des opportunités et des rebonds favorables dans cet historique.
Cela ne démontre pas que les protections sont mauvaises : elles répondent
à un risque, une exposition et un calendrier d'exécution que ce rendement
clôture–clôture ne simule pas.

**Février 2025 : 502 candidats avant régime, 502 après.** Rendement moyen
−13,74 % dans les deux cas. Le régime archivé n'interdit donc pas les LONG
sur cet épisode ; il ne peut pas expliquer une perte évitée dans ce test.

Les 1 680 observations du T1 2026 sont toutes autorisées par le mode
archivé, mais VIX/VXN/VIX3M/MOVE y sont absents. Ce « normal » est donc
marqué **macro incomplète**, pas certifié comme un régime économique calme.
Cela peut refléter un fallback ; l'expérience ne reconstitue pas son origine.

## 2. Comparaison des politiques figées

RS = rendement20 du titre supérieur à la moyenne20 de ses pairs sectoriels.
Breadth = majorité des pairs au-dessus SMA20. Le titre lui-même est exclu
des pairs ; minimum de 20 autres titres avec fenêtres valides. L'univers
des pairs est l'univers complet actuel, pas le seul pool Oracle. Aucun
candidat exclu n'est remplacé et le score MV n'est jamais recalculé.

| Période | Politique | Candidats conservés | D10 | D1 | H20 moyen brut |
|---|---|---:|---:|---:|---:|
| 2019–2022 | BASE | 100 % | 28,82 % | 23,90 % | +4,33 % |
| 2019–2022 | Régime | 57,53 % | 28,72 % | 24,71 % | +2,75 % |
| 2019–2022 | RS + breadth | 39,20 % | 29,87 % | 24,44 % | +4,40 % |
| 2019–2022 | Régime + RS + breadth | 25,34 % | 29,55 % | 25,18 % | +2,76 % |
| 2023–2025 | BASE | 100 % | 24,78 % | 22,71 % | +2,69 % |
| 2023–2025 | Régime | 87,68 % | 24,46 % | 22,88 % | +2,35 % |
| 2023–2025 | RS + breadth | 35,39 % | 24,69 % | 24,11 % | +2,19 % |
| 2023–2025 | Régime + RS + breadth | 32,96 % | 24,82 % | 24,05 % | +2,14 % |
| 2026 T1 | BASE | 100 % | 36,13 % | 11,19 % | +8,68 % |
| 2026 T1 | Régime | 100 % | 36,13 % | 11,19 % | +8,68 % |
| 2026 T1 | RS + breadth | 24,82 % | 25,90 % | 21,10 % | +0,65 % |
| 2026 T1 | Régime + RS + breadth | 24,82 % | 25,90 % | 21,10 % | +0,65 % |

Sur 2023–2025, RS seule et breadth seule donnent chacune environ 24,78 %
D10, soit quasiment la baseline ; D1 augmente à 23,73 % et 23,48 %. Leurs
rendements moyens sont +2,47 % et +2,43 %, contre +2,69 % sans ces filtres.
Ce n'est pas une confirmation d'un enrichissement D10 fiable.

## 3. Réduction du nombre de paris ≠ amélioration du modèle

En 2019–2022, RS + breadth augmente légèrement la moyenne des observations
retenues, mais ne conserve que 40,64 % des D10 initiaux et élimine 59,91 %
des D1. Cette élimination n'est pas très sélective : la majorité des
opportunités disparaît également.

Sur 2023–2025, la même règle conserve 35,26 % des D10 et élimine 62,43 %
des D1 ; elle conserve donc proportionnellement un peu plus de D1 que de
D10. Au T1 2026, elle ne conserve que **17,79 % des D10**, alors qu'elle
élimine seulement **53,19 % des D1**. C'est une dégradation de discrimination.

Pour tenir compte de l'abstention, la somme des rendements retenus divisée
par l'effectif initial vaut :

| Période | BASE | Régime | RS + breadth | Régime + RS + breadth |
|---|---:|---:|---:|---:|
| 2019–2022 | +4,33 % | +1,58 % | +1,73 % | +0,70 % |
| 2023–2025 | +2,69 % | +2,06 % | +0,77 % | +0,70 % |
| 2026 T1 | +8,68 % | +8,68 % | +0,16 % | +0,16 % |

Cette mesure fixe un budget d'observations et attribue zéro aux abstentions.
**Ce n'est ni un PnL, ni un portefeuille, ni une simulation du cash** : les
rendements H20 se chevauchent et les symboles se répètent. Elle évite
simplement de confondre une meilleure moyenne sur peu de titres avec une
meilleure contribution totale à exposition initiale comparable.

## 4. Les mois problématiques ne doivent pas dicter un seuil

En février 2025, RS + breadth conserve 101 observations sur 502, dont le
rendement moyen reste **−15,66 %**, pire que les −13,74 % de la baseline.
La contribution à budget initial tombe à −3,15 % seulement parce qu'environ
80 % des observations ne sont plus prises. Ce n'est pas une anticipation
directionnelle réussie des perdants.

En février 2026, RS + breadth conserve 145 observations et produit +0,73 %
contre −0,03 % initialement. Mais en mars, elle ne conserve que 39 sur 596,
avec **−7,05 %**, contre **+18,27 %** pour la sélection initiale. Le bénéfice
d'un mois ne généralise pas ; optimiser un seuil pour février serait trompeur.

## 5. Réserves et conclusion pratique

- Secteurs actuels, non certifiés PIT : ce résultat est exploratoire.
- Univers actuel survivant, pas un univers historique complet avec radiés.
- Fenêtres passées denses sur calendrier SPY, prix ajustés positifs,
  aucune interpolation de séances manquantes.
- Autorisation de régime à J, pas à l'entrée J+1 ; aucune position déjà
  ouverte n'est clôturée par le filtre.
- Modes archivés, pas parité intégrale de la politique actuelle CP-V2,
  de son hystérésis, des budgets, des plafonds et des protections individuelles.
- Les champs de base ne certifient pas la disponibilité économique PIT
  des données macro. Le trimestre 2026 est explicitement incomplet.
- Pas de coûts, stops, taxes, ordre exécuté ou réallocation des places libres.
- Ces périodes avaient déjà été consultées : pas de confirmation intacte.

**Réponse à l'idée de régime : oui, un blocage LONG peut supprimer des
pertes sur certaines dates ; non, les modes disponibles ne suppriment pas
la mauvaise période de février 2025 et ils écartent aussi beaucoup de gains.**
L'expérience ne justifie ni les nouveaux filtres sectoriels, ni la suppression
du régime existant. Pour connaître l'impact réel sur le portefeuille, il
faudrait un rejeu économique figé avec régime à l'entrée, sorties et coûts ;
ce n'est pas inclus dans le GO de cette expérience de discrimination.

## 6. Preuves et vérification

Script : `scripts/research/us_sector_breadth_confirmation.py`.
Résultats : `artifacts/research/us_atr_oracle_sentiment/sector-breadth-confirmation-20261004-v1/`.
`report.json` contient les huit variantes par année/mois/fenêtre, les modes,
la couverture et les hashes du protocole, de l'univers et des sources.
`selection_masks.parquet` conserve chaque décision ; `sector_context.parquet`
conserve les indicateurs et le support. `progress.json` est COMPLETED.

Deux tests ciblés passent : blocage LONG en capital_preservation même si
les entrées générales sont permises ; leave-one-out, minimum de pairs,
rejet des séances manquantes et invariance des features aux prix futurs.
Aucun entraînement, modification de modèle, écriture SQL ou batch existant.
