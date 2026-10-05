# PENN, ROKU et GH — Diagnostic des probabilités LONG presque constantes

## Verdict du 5 octobre 2026

**Cause historique exacte non déterminable avec les artefacts disponibles.**
Le comportement est confirmé dans trois branches LONG CatBoost avec calibration
vectorielle. Il est compatible avec un calibrateur qui a fortement aplati les
sorties, mais les anciens états ne sont plus disponibles. Aucun bug responsable
de cet aplatissement n'est donc certifié.

Un **défaut distinct de robustesse a été reproduit puis corrigé** : avant le
correctif, une température négative était acceptée et traitée différemment par
le fit et le predict. Cette anomalie ne prouve pas la cause des anciens scores.

L'audit initial ne modifiait pas le code applicatif. Après GO, le correctif décrit
ci-dessous modifie uniquement la calibration applicative et ses tests ; aucun
modèle existant ni donnée SQL n'a été modifié. Les sections de preuve historique
conservent le comportement observé avant correction.

## Correctif appliqué après GO

- `TemperatureScaler` et `VectorScaler` optimisent désormais **log(T)**, puis
  utilisent `T=exp(log(T))` : température strictement positive au fit et au serving.
- Les températures nulles, négatives ou non finies sont rejetées dès la création
  et le chargement, puis contrôlées à nouveau au fit et au predict.
- Les logits, les labels et les biais sont contrôlés : valeurs finies, bonnes
  dimensions, indices de classe et effectifs cohérents. Un résultat non fini
  n'est pas admis comme calibration valide.
- La prédiction ne remplace plus silencieusement une température invalide par
  1e−6. Elle utilise le même paramètre positif que la formule optimisée.
- Le format des états sérialisés reste inchangé et les anciennes températures
  positives, même très petites ou très grandes, restent acceptées. Les calculs
  multiclasse utilisent la précision float64 ; de petits écarts numériques avec
  les sorties float32 antérieures sont possibles.
- Le fallback de serving existant reste en place : un calibrateur invalide chargé
  depuis un fichier est rejeté, un warning/counter est émis, et les probabilités
  brutes sont utilisées avec une méthode `none`, pas faussement déclarées calibrées.

Pas de plafonnement de grande température arbitraire : l'aplatissement valide
peut rester présent, et n'est pas promis comme résolu par ce correctif.

89 tests ciblés passent : calibration binaire et multiclasse, contrats positifs,
chargement/fallback, predictor, caches et artefacts tabulaires. `git diff --check`
ne relève pas d'erreur de patch. La preuve après correction est conservée dans
`calibration_probe_after_fix.json` ; `calibration_probe.json` reste la preuve initiale.

### Conséquences opérationnelles

Redémarrer les processus de prédiction/IHM pour charger le code modifié. Aucun
réentraînement général n'est nécessaire uniquement pour des calibrateurs existants
valides. Les futures calibrations utiliseront l'optimisation positive.
Un ancien calibrateur invalide devra être réestimé avec son jeu de validation
qualifié ; ce correctif ne réécrit pas son fichier. Refaire une prédiction change
potentiellement les sorties si elle utilisait auparavant un état invalide, mais
les prédictions existantes ne sont pas recalculées automatiquement.

## 1. Preuves des lignes SQL, consultées sans écriture

Batch : `model-factory-20260903174624-014164`. Les lignes retenues sont uniquement
`directional_bundle` liées à ses runs, sans `oracle_synth`.

| Symbole | Modèle LONG | Calibration LONG | Dates | Minimum P(LONG) | Maximum P(LONG) | Valeurs distinctes |
|---|---|---|---:|---:|---:|---:|
| PENN | CatBoost | vector | 501 | 0,331023 | 0,331025 | 3 |
| ROKU | CatBoost | vector | 501 | 0,543147 | 0,543153 | 7 |
| GH | CatBoost | vector | 501 | 0,329111 | 0,329114 | 4 |

Le comportement couvre **juillet 2024–juin 2026**, pas seulement le TOP20 de 2026.
SHORT utilise LSTM/temperature pour PENN, LightGBM/none pour ROKU et GH.
Ce sont les références enregistrées, pas une preuve de chaque sortie brute.
Les logs d'entraînement confirment l'entraînement des branches conditionnelles.
Les chemins de config, scaler et checkpoint du registre sont désormais absents.

`raw_proba` existe dans le résultat Python du predictor, mais n'est pas une
colonne de `model_predictions`. Ni les logits ni le vecteur brut ni les features
effectivement servis ne sont récupérables depuis les seules lignes SQL.
Le `predicted_proba` fusionné du bundle n'est pas une sortie brute à leur substituer.

## 2. Les quatre sauvegardes présentes ont été vérifiées

Lecture intégrale des entrées des archives, sans restauration dans la production :

- `ml_artifacts_20260913_200727.tar.gz` : 26 932 entrées, aucun membre de ce batch ;
- `ml_artifacts_20260918_230006.tar.gz` : 26 932 entrées, aucun membre de ce batch ;
- `ml_artifacts_20260925_230003.tar.gz` : six entrées, aucun membre de ce batch ;
- `ml_artifacts_20261002_230004.tar.gz` : six entrées, aucun membre de ce batch.

Les archives récentes ne conservent pas l'ancien historique. Une sauvegarde
extérieure avec les configs, modèles et calibrateurs de septembre serait nécessaire
pour reconstituer la cause exacte. Les archives existantes n'ont pas été modifiées.

## 3. Chaîne de calcul actuelle inspectée

### Features et modèle

Le chemin tabulaire de `modelFactory/predictor.py` construit les features à la
date demandée, vérifie leur dernière date, le contrat des colonnes et les valeurs
finies, puis appelle `model.predict_proba`. Les violations contrôlées provoquent
un rejet, pas un remplacement général du vecteur par une constante. Des features
présentes mais peu variables restent possibles ; leur variation historique n'a
pas pu être testée sur les artefacts absents.

Les caches de modèles et calibrateurs incluent chemin résolu et mtime/taille.
L'inspection ne révèle pas de cache ignorant le symbole qui expliquerait ces
trois constantes différentes. Le code actuel ne certifie pas le code de septembre.

### Calibration : mécanisme d'aplatissement démontré, cause historique non prouvée

Le ternaire tabulaire entraîne `VectorScaler` sur les pseudo-logits des probabilités.
Le serving reconstruit les mêmes pseudo-logits et calibre les trois classes ensemble.
Avec un calibrateur positif ordinaire, le test de concordance donne une différence
maximale **0** : pas d'écart de transformation démontré sur ce cas.

Formule : `softmax(log(p_brut)/T + biais)`. Si T est très grand, l'influence du
modèle disparaît presque et la sortie approche `softmax(biais)`.

Exemple synthétique : des P(LONG) brutes de 0,8 / 0,1 / 0,3 deviennent
0,33102453 / 0,33102372 / 0,33102405 avec T=1 000 000 et des biais choisis pour
la démonstration. **Ce ne sont pas les paramètres récupérés de PENN.**
Le mécanisme reproduit l'aspect presque constant sans exiger des features constantes.

Sur 96 exemples synthétiques de logits/labels aléatoires, la calibration peut
atteindre T≈91 717. Ce n'est pas nécessairement un bug : un modèle non informatif
peut légitimement perdre sa variation après calibration. Il faut vérifier en
validation séparée si le calibrateur retire du bruit ou détruit un signal utile.
Ne pas choisir une autre calibration après consultation des pertes de 2026.

### Arrondi et fusion

`_build_prediction_result` arrondit les trois probabilités à six décimales.
Cela explique quelques valeurs distinctes lorsque les variations sont déjà de
l'ordre du millionième. L'arrondi seul ne rendrait pas constant un score très
variable. Le SQL de référence déclare les colonnes en `DOUBLE` ; la persistance
transmet les nombres reçus.

Le bundle prend P(LONG) dans la branche LONG et P(SHORT) dans la branche SHORT,
avec le maximum des deux P(FLAT). Le code inspecté ne remplace pas une paire
directionnelle valide par des probabilités Oracle synthétiques.

## 4. Défaut reproductible : température non positive

`VectorScaler.fit` optimise T directement sans contrainte positive ;
`from_state_dict` accepte T=−1 ; `predict` utilise ensuite `max(T,1e−6)`.
`TemperatureScaler` présente le mécanisme analogue.

Sur les logits `[0,0,2]`, T=−1 et biais nuls :

- formule utilisée dans le fit : `[0,46831 ; 0,46831 ; 0,06338]` ;
- formule utilisée dans le predict : `[0 ; 0 ; 1]`.

L'état invalide est accepté et la distribution change radicalement selon l'étape.
La preuve utilise un état synthétique négatif ; elle ne prouve pas qu'un fit normal
parti de T=1 a produit un tel état dans les anciens calibrateurs.

### Recommandation de l'audit initial, désormais implémentée pour la positivité

Garantir T>0 pendant l'optimisation ; valider température et biais finis, dimensions
et convention au chargement ; garder une formule identique au fit et au serving.
Rejeter explicitement les états invalides ou employer un fallback traçable,
sans les convertir silencieusement en une autre calibration.

Une très grande température finie mérite un diagnostic de perte de dynamique,
pas un plafond arbitraire décidé sur les performances. L'admission d'un calibrateur
devrait examiner sa qualité en validation séparée, pas seulement `fitted=True`.

## 5. Conditions pour trancher la cause des trois symboles

Récupérer les anciens `config.json`, modèles CatBoost, calibrateurs, profils de
features et si possible logs de prédiction, puis :

1. inspecter les températures et biais réellement enregistrés ;
2. comparer la variation des features et des sorties brutes à plusieurs dates ;
3. appliquer le calibrateur et comparer aux valeurs SQL ;
4. vérifier la route du champion et les éventuels fallbacks.

Un nouvel entraînement ne reproduira pas la preuve historique manquante.
Le défaut de température négative a été corrigé séparément après GO,
sans prétendre résoudre l'aplatissement historique de PENN/ROKU/GH.

## Preuves et tests

Scripts : `scripts/research/us_constant_probability_evidence.py` et
`scripts/research/us_constant_probability_calibration_probe.py`.
Sortie : `artifacts/research/us_common_degradation/constant-probability-20261005-v1/`.

- `database_evidence.json`, `persisted_predictions.parquet` (1 503 lignes),
  `registered_runs.parquet` : références et distributions ;
- les quatre `*.inventory.json` : inventaires complets des sauvegardes ;
- `calibration_probe.json` : démonstrations et concordance des transformations.

L'audit initial comportait 17 tests ciblés. Le test caractérisant l'ancien défaut
a été remplacé par une assertion de rejet des températures négatives. Avec les
tests de non-régression du correctif, 89 tests ciblés passent. Aucun entraînement
de modèle réel n'a été effectué.
