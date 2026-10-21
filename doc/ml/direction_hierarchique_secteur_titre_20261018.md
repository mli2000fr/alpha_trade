# Direction D1/D10 — diagnostic hiérarchique secteur/titre

## Objet et périmètre figés le 18 octobre 2026

GO utilisateur : vérifier d'abord si une spécialisation est justifiée, avec
comparaison d'une photographie à J et de trajectoires sur cinq/dix séances.
Les anciens essais per-symbol et Temporal V2 n'ont pas validé de direction.
Ce test ne les rebaptise pas : sa question est la persistance de **réponses
sectorielles régularisées**, puis de résidus propres aux titres, après référence
commune et correction du mouvement commun quotidien dans l'apprentissage.

**Aucune collecte, lecture/écriture SQL, connexion courtier, modification de
modèle servi, batch, univers actif, paramètre live ou calcul de performance.**
De petites régressions de diagnostic sont ajustées dans ce dossier de recherche.
Ce n'est ni un nouveau champion ni un apprentissage de spécialistes déployables.

## Protocole avant résultats

Configuration : `config/research/us_directional_hierarchy_20261018.json`.
Code : `scripts/research/us_directional_hierarchy_diagnostic.py`.

- Sources locales de l'Oracle parcours LightGBM de comparaison/confirmation du
  13 octobre ; même univers figé de 1 790 titres, sans reconstruire des modèles
  supprimés. Les dix anciens folds sont seulement inférés à nouveau ; scores
  originaux reproduits à 1e-7 et disponibilité train/validation contrôlée.
- Classement sur toute la population observable à J **avant** qualité future.
  Périmètre primaire : percentile Oracle >=0,80, environ TOP20 % ; sensibilités
  TOP10/20/50 **titres**, pas pour sauver un échec primaire.
- D1/D10 : déciles du **rendement terminal H20** dans tout l'univers éligible,
  selon `rank(method=max)` puis `ceil(percentile*10)`. Ce ne sont ni des déciles
  sectoriels ni le signe de l'excursion maximale. Couverture future >=95 % par
  date ; rendements manquants conservés comme inconnus. Les prix archivés imposent
  une qualification de chemin conservatrice ; pas de remplacement de candidat.
- Trois tâches : D1 contre D10 (diagnostic théorique limité aux queues), D10
  contre tout le reste et D1 contre tout le reste (périmètre réellement classable).
- Huit features prix/volume/bêta figées ; trajectoires = variation de chacune
  depuis J−5/J−10. Calcul sur calendrier NYSE complet avant sélection Oracle,
  observations intermédiaires requises, pas de remplissage à travers un trou.
  Ce n'est pas une recherche de la meilleure fenêtre, ni des séquences d'événements
  Oracle espacés prises à tort pour des séances consécutives.
- Référence logistique L2 commune, puis correction ridge des pentes/intercepts
  par secteur, puis petite correction d'intercept par titre. Le nombre de
  séances, pas uniquement les lignes répétées, gouverne la régularisation.
  Paramètres fixes ; référence commune si groupe inconnu ou insuffisant.
- Six bras : GLOBAL/SECTOR/HIERARCHY × J/PATH. L'ajout de la trajectoire est
  mesurable séparément de l'ajout de la spécialisation.
- Validation 2022 ; confirmations 2023 partielle, 2024, 2025, 2026 jusqu'au
  2 septembre. Ajustement annuel croissant depuis juillet 2018, seuls labels
  disponibles **strictement avant** janvier de l'année test. Imputation,
  winsorisation et standardisation apprises uniquement sur ces lignes.
- Référence Oracle récente figée avant 2024 ; pas les modèles annuels entraînés
  jusqu'à la fin de leur propre année de test.

## Mesures et décision bornée

AUC moyenne par date à poids égal, Brier quotidien, fraction de groupes
spécialisés, proportions D1/D10 dans la shortlist directionnelle TOP20 %.
La shortlist est figée avant exclusion de labels inconnus ou des déciles centraux.
Une bonne AUC sur D1/D10 seuls ne permet pas de reconnaître d'avance les queues.

Gate par bras spécialisé, toujours contre sa référence J ou PATH identique :
validation AUC >=0,53, gain >=0,01, Brier amélioré, >=30 dates et >=50 % de
couverture spécialisée ; au moins trois des quatre confirmations améliorent
l'AUC de >=0,005 et le Brier ; test de différences de Brier par blocs de 63
séances, 999 permutations signées, Holm sur les douze comparaisons, p<=0,05.
Ces seuils sont des décisions de recherche figées, pas des lois financières.

Un résultat positif ouvre seulement une confirmation indépendante et une
qualification PIT ; pas d'entraînement spécialisé automatique. Un résultat
négatif ferme cette formulation linéaire/intercepts, **pas toutes les interactions
possibles**. Aucun réglage après examen de 2024–2026.

## Réserves bloquantes pour une promotion

Classification sectorielle **actuelle**, groupée via le mapping du projet vers
les grands secteurs ; inconnus/Other n'apprennent pas de groupe sectoriel.
Pas d'affirmation de secteur historiquement connu. Univers actuel et prix
ajustés non certifiés en vintages. 2024–2026 déjà examinés, pas des holdouts
vierges. Chemins H20 et titres répétés corrélés ; blocs = approximation.
La seule validation historique du présent diagnostic ne débloque donc pas le live.

## Exécution et sorties

```powershell
python -u -m scripts.research.us_directional_hierarchy_diagnostic --output artifacts/research/us_directional_hierarchy/20261018-v1
```

`protocol.json` fige les empreintes avant calcul. `population.parquet` contient
le pool observable et ses labels inconnus ; `population-coverage.csv` décrit
le périmètre. Prédictions de diagnostic par année/tâche, `daily-metrics.parquet`,
`group-evidence.csv`, `correction-coverage.csv`, `summary.csv`, `report.json`,
`progress.json`. Les sources sont recontrôlées après calcul ; verrou exclusif
et écritures JSON atomiques avec reprise des erreurs Windows transitoires.

## Résultat

**TERMINÉ le 18 octobre 2026 à 13:11 Paris. Verdict :
`NO_STABLE_GROUP_STRUCTURE`. Zéro des douze bras spécialisés/tâches passe
le gate figé. Pas d'entraînement spécialisé supplémentaire ni de promotion.**

Dossier : `artifacts/research/us_directional_hierarchy/20261018-v1`.
Les dix anciens folds Oracle ont été reproduits avec **écart maximum zéro**.
Toutes les empreintes sources ont été revérifiées après calcul. Les
**32 tests ciblés** (19 nouveaux + 13 de l'audit précédent) passent ; un
avertissement NumPy connu concerne l'ancien test synthétique à trop peu de blocs.
Le premier lancement des seuls tests avec la couverture globale par défaut
échouait au seuil de 70 % de l'ensemble du dépôt, pas aux assertions ; le
lancement ciblé final sans couverture globale a terminé avec code zéro.

### Couverture réellement mesurée

Population TOP20 % : **670 602 couples titre/date, 1 930 séances, 1 256 titres**
ayant au moins une fois franchi le gate dans l'univers figé de 1 790.
662 143 labels terminaux qualifiés ; inconnus conservés et jamais remplacés.
Évaluation 2022–2026 : **375 754 candidats, 1 049 séances, 1 024 titres**,
dont 368 398 labels connus. Les autres observations alimentent uniquement
les entraînements chronologiques antérieurs et matures.

2023 couvre seulement les **128 séances archivées jusqu'au 7 juillet**.
2026 couvre **168 séances de décisions jusqu'au 2 septembre**, mais 148
seulement ont des déciles calculables : les vingt dates du 20 mai au 17 juin
sont laissées inconnues car la couverture des chemins dans l'univers global
est inférieure au minimum de 95 %. Ce n'est pas une absence de maturité de
septembre, et ces dates ne deviennent pas artificiellement des D1.
Sur toute la période d'évaluation, les trajectoires J−10 sont inconnues pour
environ **1,06 %** des candidats ; imputation par médiane du train uniquement.

### D1 contre D10 : discrimination moyenne quotidienne

AUC 0,50 = absence de classement informatif ; **ce n'est pas un taux de
trades gagnants**. La référence J n'est pas le score d'amplitude Oracle :
c'est la petite régression directionnelle commune entraînée sur les features J.

| Période | Global J | Global trajectoires | Secteur + trajectoires | Hiérarchie + trajectoires |
| --- | ---: | ---: | ---: | ---: |
| 2022 validation | 0,4642 | 0,4621 | 0,4313 | 0,4309 |
| 2023 partiel | 0,4778 | 0,4831 | 0,4963 | 0,4644 |
| 2024 | 0,5038 | 0,4983 | 0,5125 | 0,4948 |
| 2025 | 0,5199 | 0,5158 | 0,5144 | 0,5092 |
| 2026 partiel | 0,4761 | 0,4849 | 0,4761 | 0,4895 |
| Moyenne à poids égal des dates évaluables | 0,4908 | 0,4899 | 0,4859 | 0,4782 |

La trajectoire améliore parfois une année et en dégrade une autre. Il serait
incorrect de choisir J en 2025 et PATH en 2026 après examen des résultats,
ou d'inverser rétrospectivement un score parce qu'une AUC est inférieure à 0,50.
Les bras J sectoriel/hiérarchique sont également dans `summary.csv` ; aucun
ne sauve la validation 2022.

### Tâches sur le pool complet : distinguer une queue du reste

| Tâche | Global J | Global trajectoires | Secteur + trajectoires | Hiérarchie + trajectoires |
| --- | ---: | ---: | ---: | ---: |
| D10 contre reste, AUC quotidienne | 0,5278 | 0,5291 | 0,5175 | 0,5110 |
| D1 contre reste, AUC quotidienne | 0,5057 | 0,5083 | 0,5130 | 0,5263 |

Il existe donc un **petit effet de classement des D1** dans cette formulation
avec adaptation titre, mais pas une séparation D1/D10 stable. La qualité
probabiliste Brier du bras hiérarchique PATH se dégrade par rapport au global
PATH **dans chacune des cinq périodes** pour les trois tâches. Les p-values
ajustées significatives portent souvent sur cette dégradation, pas sur un gain.

Pour D10/reste, la shortlist directionnelle TOP20 % contient en moyenne
**23,99 % de D10** avec GLOBAL_PATH, contre **22,70 %** avec SECTOR_PATH et
**22,14 %** avec HIERARCHY_PATH. Le pool Oracle complet est à **20,70 %** de
D10. Ces associations historiques ne prouvent ni filtre rentable ni alpha :
le bras global échoue à la validation fixée et n'est pas une nouvelle piste promue.

### Décision et portée du NO_GO

Ne pas lancer des centaines de modèles par symbole, de spécialistes CatBoost,
de recherche de fenêtres ou de grille de régularisation à partir de ces années.
Cette comparaison bornée n'apporte pas la justification recherchée.

Le diagnostic ferme **ces huit features, ces différences 5/10 séances, ces
corrections ridge sectorielles et intercepts titre**, pas l'existence de toute
information directionnelle. Il ne teste pas de nouveau corpus consensus/news
PIT, ni tous les modèles non linéaires possibles. L'Oracle d'amplitude et les
modèles/paramètres utilisés en production restent inchangés.
