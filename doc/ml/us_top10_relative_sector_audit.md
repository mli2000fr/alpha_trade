# TOP10 Oracle — provenance et faiblesse relative pré-entrée

## Objectif et périmètre

Suite de l'[audit de contexte 2024](us_top10_2024_context_audit.md).
Vérifier la provenance du batch `model-factory-20261003082853-e98332`, puis
évaluer une seule hypothèse de faiblesse pré-entrée, sans entraînement,
requête SQL, écriture SQL, modification du serving ou calcul de PnL.

Résultat : **ne pas promouvoir le veto de faiblesse relative**. Il supprimerait
une population plus favorable aux LONG dans les deux années observées.
Ne pas inverser automatiquement la règle après lecture de ce résultat.

## Hypothèse et méthode figées avant ce calcul

À la clôture du signal, marquer comme faible un candidat TOP10 si :

1. son rendement ajusté sur vingt séances est inférieur à la médiane des
   rendements de ses pairs sectoriels sur les mêmes vingt séances ;
2. moins de 50 % de ces pairs ont un rendement vingt séances positif.

Le titre lui-même est exclu de ses pairs. Il faut au moins cinq pairs valides.
Une information absente reste `UNKNOWN` et ne déclenche pas le veto.
Aucun seuil alternatif, recherche de fenêtre, blacklist sectorielle ou
réentraînement n'a été utilisé. Une éventuelle décision serait connue après
la clôture J, donc exécutable au plus tôt en J+1.

Les panels de 2022 donnent le préchauffage ; les résultats sont calculés
sur 2023 et 2024. Les prix des pairs proviennent de tout l'univers archivé,
et non des seuls titres TOP10. Les rendements sont calculés sur une grille
commune de séances, sans remplissage des cours manquants. Les extrémités
doivent avoir prix ajusté positif, volume positif, barre non synthétique et
identifiant instrument identique et renseigné.

Cela ne certifie pas l'ensemble du chemin, les opérations sur titres ou les
vintages des ajustements. Les secteurs sont **actuels, NON-PIT** ; l'univers
est statique. Ce test est exploratoire sur des années déjà examinées :
« règle figée avant ce calcul » ne signifie pas confirmation indépendante.

## Résultats candidats, avant portefeuille

| Année / population | Occurrences | D1 réel | D10 réel | Rendement H20 moyen |
|---|---:|---:|---:|---:|
| 2023 faiblesse détectée | 569 | 13,71 % | 42,18 % | +11,46 % |
| 2023 autres, contexte connu | 1 883 | 23,95 % | 34,47 % | +5,67 % |
| 2024 faiblesse détectée | 544 | 20,77 % | 29,41 % | +4,43 % |
| 2024 autres, contexte connu | 1 974 | 31,51 % | 19,20 % | −1,08 % |

Contexte inconnu : 48 occurrences en 2023, deux en 2024. Les deux dernières
sont D1 ; cet échantillon minuscule ne permet aucune règle de remplacement.

Le signal proposé comme veto repère au contraire une population ayant
moins de D1 et davantage de D10. Il est compatible avec des rebonds, sans
en prouver la cause. Une hausse future moyenne n'est pas un rendement de
portefeuille : stops, gaps, sizing, capitaux et coûts ne sont pas rejoués ici.
Les occurrences quotidiennes se recouvrent sur H20 et ne sont pas des
observations indépendantes ni des transactions distinctes.

**Décision : rejet du veto dans sa formulation proposée.** Pas de test
économique de ce veto, pas de changement live. Transformer le groupe faible
en filtre d'achat constituerait une nouvelle hypothèse choisie après résultat,
à valider séparément sur une période non utilisée pour cette décision.

## Chronologie Oracle : qualification partielle uniquement

Le manifeste contient douze champions, du 5 juillet 2018 au 8 janvier 2024.
Tous les fichiers annoncés sont présents. Aucun des candidats 2023–2024
n'est affecté à un `fold_start` futur.

Le code actuel de `modelFactory/oracle/walk_forward.py` impose :

- labels train disponibles avant le début validation ;
- labels validation disponibles avant le début test ;
- early stopping sur validation, puis prédictions du test séparé.

Mais le manifeste sauvegardé ne contient que `t_start`, `model_file` et
`feature_columns`. Il ne fournit pas les dates extrêmes effectives du train,
de la validation, de disponibilité des labels, ni la fin exacte du test.
Le code actuel est une preuve du contrat prévu, pas une preuve complète de
l'exécution historique du batch. Les vintages des features et la composition
historique de l'univers restent également à qualifier. Les fichiers ont été
créés en 2026 : le serving des années antérieures est une reconstruction,
pas une preuve de déploiement réel à cette date.

Réserve supplémentaire : `predict_history.py` choisit le dernier champion
avec `t_start <= J`, mais utilise le premier champion lorsqu'aucun ne répond
à cette condition. Le commentaire qualifiant ce fallback de PIT est trop
fort : entraîner avant le premier test ne garantit pas entraîner avant
une date arbitrairement plus ancienne. Le cas ne concerne pas les candidats
2023–2024 de cette étude. Aucun correctif de production n'est réalisé ici.

Le maintien d'un champion au-delà de sa fenêtre test initiale est du serving
historique après son origine, pas automatiquement une observation appartenant
au test OOF d'origine. Verdict : **PARTIAL_LINEAGE_ONLY_NOT_FULL_PIT_CERTIFICATION**.

## Reproduction et fichiers

Commande depuis la racine du projet, avec un nouveau répertoire de sortie :

```powershell
python -m scripts.research.us_top10_relative_sector_audit --output artifacts/research/us_concentrated_replay/top10-relative-sector-20261007-v1
```

Le répertoire doit être nouveau pour ne pas écraser de résultats.
Le run est terminé : `report.json`, `lineage.json`, `candidates.parquet`,
`progress.json` et `protocol.json` (règle, réserves et hashes des entrées).
Le script ne contacte pas les fournisseurs ni la base.

Tests ciblés : absence de remplissage, causalité du rendement passé,
exclusion du candidat de ses pairs, seuil strict et contexte insuffisant.
La couverture globale du dépôt n'est pas une mesure pertinente pour ces
seuls tests de recherche ; lancer les tests ciblés avec `--no-cov`.

## Audit de provenance complémentaire

Le [rapport de reproductibilité](us_oracle_reproducibility_audit.md) retrouve
le journal global et la fin du test d'origine au 9 juillet 2024. Les résultats
2024 restent défavorables dans cette enveloppe, avant le prolongement du
champion. La certification PIT complète reste non établie.
