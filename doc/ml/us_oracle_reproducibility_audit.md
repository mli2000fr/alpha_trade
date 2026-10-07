# Oracle US — audit de reproductibilité et chronologie du batch e98332

## Résumé de décision

Batch : `model-factory-20261003082853-e98332`, Oracle amplitude H20.
Suite de l'[audit pré-entrée sectoriel](us_top10_relative_sector_audit.md).

Le journal global confirme douze fenêtres de test, du 5 juillet 2018 au
**9 juillet 2024**. Le dernier champion débute son test le 8 janvier 2024.
Les comparaisons annuelles antérieures mélangeaient donc les fenêtres test
d'origine et le prolongement historique du dernier champion.

La faiblesse directionnelle de 2024 existe **déjà à l'intérieur de l'enveloppe
test documentée**. Elle ne peut pas être attribuée uniquement au prolongement
du modèle après juillet. Cela ne démontre ni une fuite ni l'absence de fuite.

Le périmètre strictement certifié PIT, avec provenance complète des features,
labels et scores OOF immuables, **n'est pas établi**. Ne pas présenter les
statistiques ci-dessous comme une nouvelle certification indépendante.

## Preuves retrouvées

### Journal du batch versus journal global

L'archive `artifacts/rapport_ml/model-factory-20261003082853-e98332.log`
ne comporte que onze lignes d'entraînement archivées. Les lignes sans
identifiant batch, notamment les fenêtres et importances par fold, n'y sont
pas reprises. Ce n'est pas la totalité de l'exécution.

Le journal `log/model_factory.log` contient l'intervalle attribuable :

- début Oracle : 3 octobre 2026, 10:28:56 ;
- génération labels terminée à 10:40:11 : 3 874 908 lignes, 3 873 149
  labellisées, 1 759 invalides (80 sauts bruts extrêmes, 1 679 sorties absentes) ;
- fenêtres adaptatives à 10:48:36 : douze folds, paramètres
  train minimal 504, validation 126, test 126, pas 126, maximum demandé 15 ;
- premier test : 2018-07-05 / 2019-01-03 ;
- dernier test : 2024-01-08 / 2024-07-09 ;
- 2 616 012 prédictions OOS persistées et douze champions sauvegardés ;
- fin Oracle : 11:13:00, run `oracle-wf-20261003105719`.

Ces heures sont celles du journal local. Le rapport Markdown du batch donne
08:28:54 / 09:13:03 : ne pas mélanger les représentations UTC/locales pour
conclure à deux exécutions. L'identifiant batch et les événements concordent.

L'audit isole le bloc entre les marqueurs de début et fin de **ce batch**,
et exige une unique ligne de fenêtres attribuable. Les extraits et leurs
numéros de ligne sont archivés ; le journal global peut continuer à évoluer.

### Modèles et features

Les douze fichiers du manifeste sont présents. Pour chaque fichier, l'audit
archive le SHA-256 et vérifie que les noms et l'ordre des **173 features**
LightGBM correspondent au manifeste. Les douze folds ont une ligne
d'importance des features dans le bloc d'entraînement retrouvé.

Cela prouve la cohérence des fichiers présents et du manifeste, pas que les
fichiers n'ont jamais été remplacés depuis l'exécution : les hashes originaux
n'avaient pas été conservés dans un manifeste signé/immuable.

## Contrat temporel prévu par le code actuel

`modelFactory/orchestrator.py` construit les folds adaptatifs puis appelle
`run_walk_forward(..., ablation="O0")`. Le train est séparé de la validation ;
la validation pilote l'early stopping et les tests produisent les scores.

`modelFactory/oracle/walk_forward.py` applique :

```text
max(disponibilité labels train) < début validation
disponibilité labels validation < début test
test séparé du train et de l'early stopping
```

Le code sauvegarde dans le manifeste champion uniquement `t_start`,
`model_file`, `feature_columns`. Les dates effectives train/validation, leurs
maxima de disponibilité et les fins de test ne sont pas sauvegardés par fold.
Le journal donne la première et la dernière fenêtre, pas toutes les lignes
de membership. **Le code actuel ne remplace pas une preuve du code et du
dataset réellement exécutés en 2026.** Aucune reconstruction des dates
manquantes n'est déclarée comme preuve historique.

`predict_history.py` utilise le champion au `t_start` le plus récent qui
précède la décision. L'audit vérifie cette correspondance sur les TOP10
2023–2024 : **zéro discordance sur les 5 020 candidats**. Pour une date antérieure au premier champion, le fallback vers
le premier modèle n'est pas une garantie PIT ; aucun candidat de ce présent
périmètre n'est dans cette situation.

## Limite importante : scores OOF et serving partagent le stockage

Dans `modelFactory/oracle/predictions_store.py`, entraînement et prédiction
historique utilisent la même clé : date, symbole, batch. Un upsert ultérieur
remplace proba, rendement, label et fold. La clause de mise à jour n'actualise
pas `created_at` et ne conserve ni l'ancien score ni un identifiant de run.

Conséquences :

- `fold_start <= date` ne prouve pas à lui seul un score OOF d'origine ;
- `created_at` peut dater de la première insertion, pas du dernier scoring ;
- les panels actuels ne peuvent pas être comparés exactement à des scores
  OOF initiaux immuables qui n'ont pas été retrouvés ;
- la présence d'une ligne dans la fenêtre test est une qualification
  **provisoire de périmètre**, pas une certification complète du score.

Aucune requête SQL ni restauration n'a été effectuée dans cet audit.

## Statistiques recalculées sur les périmètres séparés

TOP10 **prédits**, dix candidats par séance, sans filtre directionnel.
Rendements futurs H20 clôture ajustée / clôture ajustée, pas PnL portefeuille.
Les labels utilisés satisfont les contrôles locaux du panel précédent.

| Périmètre | Séances / occurrences | D1 | D10 | Rendement moyen H20 |
|---|---:|---:|---:|---:|
| 2023, enveloppe test journalisée | 250 / 2 500 | 21,44 % | 36,24 % | +6,98 % |
| 2024, jusqu'au 9 juillet inclus | 130 / 1 300 | 32,00 % | 18,77 % | −0,54 % |
| 2024, après le 9 juillet | 122 / 1 220 | 26,31 % | 24,18 % | +0,76 % |

Les 130 séances 2024 comprennent les séances de début janvier servies par le
champion précédent, puis le dernier champion à partir du 8 janvier.
Les observations H20 se recouvrent ; les occurrences ne sont pas des trades
indépendants. Les labels et ajustements sont rétrospectifs, l'univers statique
et la provenance PIT des données n'est pas intégralement certifiée.

Même en retirant le prolongement après juillet, le contraste 2023/2024 reste
net. L'amélioration après juillet sous le même champion est descriptive :
elle ne prouve pas que le vieillissement serait favorable ou inoffensif.
Le rendement négatif moyen de candidats n'est pas directement le −10,92 %
du portefeuille annuel ; stops, sizing, frais et positions reportées diffèrent.

## Réserve qualité supplémentaire retrouvée dans les logs

Sur le dataset d'entraînement de 3 800 298 lignes, le journal indique :

- `daily_return` maximum **45 499** ;
- `overnight_gap` maximum **47 749** ;
- `rolling_volatility_20` maximum **10 173,9**.

Ces valeurs sont des unités de features, pas des pourcentages. Elles sont
suspectes pour des variations journalières et justifient une enquête ciblée
sur prix bruts/ajustés, identités et corporate actions. Le log agrégé n'indique
pas les symboles/dates responsables ni les folds qui les ont effectivement
utilisés. **Ne pas attribuer la perte 2024 à ces valeurs sans cette vérification.**
Le contrôle des labels extrêmes n'assainit pas automatiquement les fenêtres
historiques utilisées pour calculer les features.

## Ce qui manque encore et décision

Pour certifier intégralement l'exécution historique :

1. dataset ou manifestes des lignes train/validation/test par fold ;
2. dates maximales de disponibilité des labels train et validation ;
3. version source et environnement d'exécution figés ;
4. historique de membership et dates de disponibilité/vintages des features ;
5. scores OOF initiaux immuables avec hashes des modèles associés.

Ces éléments n'ont pas été retrouvés dans les fichiers examinés. Il n'est
pas nécessaire de relancer aveuglément le batch : cela ne recréerait pas les
preuves historiques perdues. Un futur entraînement pourra produire une
preuve plus complète, mais ce n'était pas autorisé ni lancé ici.

**Conclusion : audit terminé avec qualification partielle.** Pas de fuite
démontrée dans les folds 2023–2024, pas de certification totale non plus.
Pas de filtre ou modèle promu. La prochaine investigation utile est de
localiser les extrêmes de features et vérifier leur origine avant une
nouvelle expérience directionnelle.

## Reproduction

```powershell
python -m scripts.research.us_oracle_lineage_audit --output artifacts/research/us_concentrated_replay/oracle-lineage-20261007-v3
```

Utiliser une sortie nouvelle. Livrables : `protocol.json`, `report.json`,
`evidence-excerpts.json`, `classified-top10.parquet`. Les sources originales
restent intactes. Deux tests ciblés vérifient l'unicité de la preuve et la
séparation des dates futures/inconnues/post-test ; ils passent avec `--no-cov`.

## Suite réalisée : origine des maxima localisée

L'[audit des prix et features extrêmes](us_oracle_feature_outliers_audit.md)
reproduit les trois maxima sur KNTK en novembre 2018. La relecture fournisseur
split-only donne 99 → 91 dollars, alors que la base locale donne 0,002 → 91.
AMTB présente une autre rupture. Réparation non réalisée ; pas d'attribution
causale des pertes 2024 à ces erreurs sans comparaison qualifiée.
