# Sprint 10-B — Pilote directionnel mutualisé H5, train conditionnel Oracle OOF

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Protocole fixé avant les fits — 3 octobre 2026

H5 prix-only, 14 features figées FR. Les périodes de développement ont déjà été examinées en 9-A et 10-A : **aucun résultat de ce lot n'est une confirmation finale indépendante**. 2026 non utilisée ; H10/H20 non admis en couverture. Aucun SQL, serving, live, US/CN ou tâche planifiée modifié.

## Constituer le train sans fuite de l'Oracle

Les trois pools **test** 10-A ne suffisent pas à un train long suivi de plusieurs validations indépendantes. On peut cependant réutiliser les scores de **validation et test** archivés en 9-A, sous un contrat plus strict :

1. Fixer la branche Oracle `trees`, sans choix du champion par AP validation.
2. Le modèle arbres 9-A est ajusté sur le train seul ; `early_stopping=False`, aucun calibrateur, aucun refit train+validation. Ses scores validation sont donc hors fit de l'Oracle. Ils ne seraient **pas** une source causale admissible si l'on choisissait rétrospectivement le champion sur les labels de cette même validation.
3. Pour chaque date, employer le modèle fixe le plus récent effectivement disponible : début de sa validation atteint, train antérieur avec garde de disponibilité des labels. Jamais le modèle d'un fold futur.
4. Dédupliquer les scores par date/UID en gardant cette provenance, puis sélectionner le TOP20 chaque jour avant de regarder les déciles directionnels.
5. Les labels D1/MIDDLE/D10 des événements OOF alimentent alors un deuxième modèle. Sa propre séparation train/validation/test est chronologique, purgée selon les disponibilités et les bornes/embargos 8-A.

La branche et ses hyperparamètres ont été observés dans des expériences précédentes : ce gel est valable **pour ce nouveau pilote**, pas une pré-inscription antérieure à toute recherche FR. La population ne sera pas identique au champion/test seul de 10-A ; toutes les références seront recalculées dans le même pool 10-B.

## Cible et modèle mutualisé

Un modèle par fold, **commun à tous les titres** : chaque observation est un événement date/UID sélectionné Oracle. Ni symbole, ni UID, ni décile futur, ni rendement futur, ni score Oracle comme feature ; les 14 variables prix de 9-A, avec son transformateur log1p de valeur échangée. Pas de modèles Per-Symbol.

Cible ternaire : D1→0, déciles 2–9→1, D10→2. Un décile `TIE_BOUNDARY` n'entre pas dans le fit ni l'évaluation des classes, mais l'événement reste scoré et participe au classement et aux mesures de rendement connu. Tout autre label absent bloque. **Ces classes sont relatives au marché FR de la date : elles ne signifient pas directement baisse/flat/hausse.**

Deux variantes petites, sans sweep : logistique C=1/max_iter=500/scaler train seul ; HistGradientBoosting 100 itérations, learning_rate=0,05, profondeur 3, 7 feuilles, minimum 100 observations par feuille, L2=1, early stopping désactivé. Paramètres identiques aux références 9-A ; seed17, 2 threads. Pas de pondération de classes ni calibration.

Champion choisi par AUC D10/D1 **validation seulement**, priorité logistique si égalité. Pas de refit après choix. Classement directionnel = `P(D10) − P(D1)` ; top20 du pool diagnostique LONG et bottom20 SHORT. Pas de seuil d'exécution ni optimisation d'abstention dans ce lot. Les trois probas décrivent les déciles, ne sont pas des probas de rendement positif ou négatif.

## Support et gate

Tester les plans outer 4/5/6 existants, sans déplacer leurs bornes. Train directionnel : ≥126 dates OOF, ≥100 observations connues par classe. VAL/test : ≥40 séances, ≥80 % des 126 séances prévues, ≥30 D1 et D10. Les limites ne sont pas abaissées pour rendre un fold entraînable ; motifs et compteurs sont persistés. Les trous d'historique OOF antérieurs ne sont pas remplis avec des scores in-sample.

Les archives paraissent n'admettre qu'un fold directionnel complet. Ce n'est pas bloquant pour effectuer un **petit fit exploratoire** sur ce fold, mais c'est bloquant pour revendiquer une robustesse multi-fold.

Gate de signal : au moins deux folds test admissibles ; AUC moyenne champion ≥0,53 et gain AUC ≥0,01 face à momentum20 sur mêmes candidats ; IC moyen ≥0,03 ; spread brut moyen ≥0,002. Tous requis pour `PILOT_SIGNAL_REQUIRES_CONFIRMATION`, jamais GO production. Zéro fit admissible→`BLOCKED_DIRECTION_SUPPORT`; un seul test admissible→`LIMITED_PILOT_INSUFFICIENT_OOS_FOLDS`, indépendamment de sa performance. Pas de choix du meilleur variant sur test.

## Contrôles, mesures et sorties

Hashes des prix/labels/prédictions 9-A vérifiés ; configuration 9-A fixe ; timestamps features≤décision ; clés uniques ; fin labels train avant VAL, labels VAL avant test ; chaque score Oracle antérieur au test de la direction peut seulement venir d'un modèle Oracle déjà disponible. Les colonnes de la matrice sont celles du profil figé, jamais des cibles. Comparateurs random/momentum5/momentum20 sur le **même pool** ; mesures 10-A, bandes descriptives et sorties probas conservées par phase.

`python -u -m modelFactory.fr_direction_h5_shared`

Configuration : `config/research_fr/direction_h5_shared_v1.yaml` ; sorties nouvelles sous `artifacts/fr/research/direction_h5_shared/` : protocole avant fits, pool OOF complet/provenance, plans et support, modèles de recherche, prédictions directionnelles validation/test, métriques quotidiennes et rapport. Aucun modèle n'est servable. Relance identique refusée, anciennes sorties préservées.

Rendements bruts uniquement, pas coûts/fills/impôts/dividendes économiques/availability borrow. Séances H5 chevauchantes, faible représentation des radiés, secteur/taille non neutralisés, dépendance des folds et univers de recherche : pas de promesse économique ou de généralisation.

## Résultats

Run final : `artifacts/fr/research/direction_h5_shared/fr-shared-direction-h5-5387843f8432/`. Le premier run `9959b81ae5be` est préservé ; la relance après renforcement du contrôle des bornes de probabilité produit les mêmes résultats (aucun changement de cible, seuil, modèle, support ou choix champion).

L'historique Oracle fixe OOF contient **7 385 événements sur 459 séances**. SHA-256 : `7ebf41fbde36048d1533805fefa6e5cccd16da50e9765d112aa001ce1e75b2b1`. Dédupliquer validation/test des trois folds ne signifie pas cumuler deux scores différents pour le même titre/jour : seule la branche fixe du modèle déjà disponible le plus récent est retenue.

### Support et fits

| Plan directionnel | Train OOF | État | Motif |
|---|---:|---|---|
| Fold 4 | 0 séance / 0 ligne | BLOCKED | aucun événement OOF antérieur à sa validation |
| Fold 5 | 105 séances / 1 768 lignes | BLOCKED | inférieur au minimum 126 séances |
| Fold 6 | 219 séances / 3 438 lignes | ADMITTED | classes et support admis |

Pour fold 6, 3 437 lignes de train ont un décile connu : **652 D1, 2 186 intermédiaires, 599 D10** ; une égalité de frontière ne participe pas au fit. La borne train du plan est le 28/12/2023, avec labels strictement disponibles avant début de validation le 30/01/2024. Le début nominal 2019 du plan ne doit pas être interprété comme une couverture directionnelle OOF depuis 2019 : les événements disponibles commencent en 2023.

Validation effective : **103 séances et 1 681 événements**, du 14/02 au 18/07/2024 (bornes théoriques 30/01–26/07). Test : **126 séances, 2 091 événements et 47 UID**, du 29/07/2024 au 23/01/2025. Toutes les lignes respectent maturité et bornes du plan. Deux variantes directionnelles entraînées, zéro réentraînement Oracle.

### Choix uniquement sur validation

| Variante | AUC D10/D1 VAL | Décision |
|---|---:|---|
| Logistique | **0,5383** | champion |
| Arbres | 0,4791 | variante non retenue |

Le test a été évalué sans refit ni changement de champion. La table suivante montre toutes les variantes préfixées ; **elle ne permet pas de remplacer la logistique par les arbres après lecture du test**.

### Résultats sur le même test Oracle OOF

| Score | AUC D10/D1 | IC quotidien | Rendement LONG brut H5 | Rendement SHORT brut H5 | Spread |
|---|---:|---:|---:|---:|---:|
| Aléatoire | 0,4987 | +0,0046 | −0,240 % | +0,836 % | +0,595 % |
| Momentum 5 jours | 0,4893 | −0,0230 | +0,226 % | +0,290 % | +0,516 % |
| Momentum 20 jours | **0,5245** | +0,0474 | +0,156 % | +1,047 % | +1,203 % |
| Logistique — champion VAL | **0,5023** | +0,0392 | **−0,495 %** | +0,594 % | +0,100 % |
| Arbres — non retenus | 0,5556 | +0,0716 | −0,020 % | +0,692 % | +0,672 % |

Champion : delta AUC contre momentum20 **−0,02221** ; AUC sous 0,53, spread sous 0,20 %. Le classement appris choisi sur VAL ne bat donc pas la référence sur ce test, même avant coûts. Les arbres ont une AUC test intéressante mais ne produisent pas ici un LONG brut positif ; un seul fold et une sélection a posteriori ne permettraient pas un GO.

Logistique : D10 capturés dans la sélection LONG **18,92 %**, contre **19,39 %** dans le pool Oracle seul ; D1 capturés dans la sélection SHORT **24,80 %**, contre **20,52 %** dans Oracle seul. La branche SHORT trouve davantage de D1, mais son rendement brut reste inférieur au SHORT momentum20. D1/D10, signe de rendement et économie ne sont pas interchangeables.

### Verdict et suite

**`LIMITED_PILOT_INSUFFICIENT_OOS_FOLDS`**, un seul fold test admissible contre deux exigés. L'implémentation mutualisée fonctionne, mais aucune direction FR exploitable n'est confirmée. Ne pas afficher `NO_GO` comme si trois tests indépendants avaient été disponibles ; ne pas non plus promouvoir la variante arbres en contournant le choix validation.

La prochaine étape utile est de **qualifier une extension de l'historique Oracle OOF** avant de pré-enregistrer une nouvelle évaluation supervisée multi-fold. Les folds antérieurs du Sprint 8-B étaient bloqués par couverture ; réutiliser leur train in-sample, abaisser le minimum train de 126 à 105 ou réduire les gates 80 % pour débloquer artificiellement un résultat n'est pas autorisé par ce protocole. Une autre règle nécessiterait une nouvelle expérience explicitement exploratoire, pas la modification du verdict présent. 2026 reste intacte ; ce rapport ne propose pas de la consulter pour choisir la variante ou les hyperparamètres.

**95 tests ciblés FR passent**, dont dix nouveaux : cible ternaire et inconnus, branche Oracle fixe/dernière disponibilité/déduplication, rejet de modèle Oracle futur, support minimal, champion VAL, ordre des classes, un seul fold incapable de confirmation, features sans cibles/UID, purge des labels à la frontière. Ruff passe. Pas de validation de la suite entière de l'application, ni de production.
