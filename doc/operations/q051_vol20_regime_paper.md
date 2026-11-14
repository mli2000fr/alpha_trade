# Q051 vol20 + régime dans le batch US

Le parcours est activé dans `config.yaml`, sous
`us_pipeline.q051_vol20_regime.enabled: true`. Il s'applique aux nouvelles
étapes 10/11/12 du **batch planifié US, en PAPER uniquement**. Les réglages du
pipeline manuel restent indépendants. LIVE est refusé, y compris si un compte
réel est passé au lanceur. Les autres étapes et les anciens états Winner ne
sont pas réécrits.

## Sélection et gestion de la position

Le modèle actif est celui de `model_batch_id`, actuellement
`model-factory-20261107222627-db80b0`, Oracle parcours H10 avec modèles LONG
par titre causaux pour 2026. Le modèle et les contrats sont contrôlés avant
utilisation ; aucun réentraînement ni substitution silencieuse de modèle.

1. Inférence sur l'univers complet du modèle : 1 790 titres actuellement.
2. TOP10 % Oracle : **179 candidats**, calculé depuis la taille du modèle.
3. Classement LONG per-symbol et prise des cinq premiers, puis score
   strictement supérieur à 0,50 et AUC de calibration au moins égale à 0,50.
   Aucun remplacement du sixième si l'un des cinq échoue à ces seuils.
4. Dimensionnement avec le capital, les positions et les ordres ouverts réels
   du compte PAPER ; aucun capital de secours. Risque 1,25 % par entrée,
   poids maximal 20 %, vingt positions, minimum 50 USD, quantités entières,
   plafond des nouveaux achats de 1×. La capacité du compte margin reste 2×,
   sous réserve de celle réellement accordée par Alpaca.
5. Budget de volatilité annualisée de 20 %, covariance sur les soixante
   dernières séances complètes ; réduction des nouveaux achats uniquement.
6. Nouvelles entrées autorisées si la clôture SPY de J dépasse
   98 % de sa moyenne mobile sur 200 séances.
7. Position complète, sans confirmation 5 minutes, renforcement, TP ni
   trailing. SL de 5 % depuis le prix réellement exécuté. Dix séances de
   détention, entrée incluse, puis sortie à l'ouverture de la onzième.

**Aucun preset de capital** n'est résolu pour ce parcours : ni
`capital_presets.yaml`, ni ses paliers selon l'equity ne changent ces règles.
Le profil risque figé est dans
`config/strategies/q051_vol20_regime_reference.json`. Le capital réel fait
varier les quantités, pas le choix du preset. Les autres parcours conservent
leur fonctionnement habituel.

Les filtres options/GPT, l'optimiseur générique, les contrôles factoriels,
sectoriels et de corrélation, B4/DD15 et sa liquidation sont absents de ce
parcours. Les limites **déjà présentes dans la référence** restent actives :
dix entrées par titre sur 90 jours calendaires, trois pertes consécutives
suivies d'une exclusion de 90 jours. La source qui fait foi pour ces limites
est le `RiskConfig` réellement utilisé par le replay Winner, et non les
anciens champs du simulateur générique.

## Couverture Oracle : décision utilisateur du 14 novembre 2026

Le seuil est inchangé :
`oracle_path.min_prediction_coverage_ratio: 0.93` dans `config.yaml`.
Pour **ce seul parcours PAPER**, le dénominateur contient les membres de
l'univers du modèle déclarés **active ET tradable** par Alpaca au lancement
de la prédiction. Le numérateur ne compte que les prédictions de ces membres.
Les autres prédictions ne peuvent donc pas gonfler artificiellement le ratio.

L'univers d'inférence, les rangs transversaux et le TOP179 restent ceux du
modèle complet. Il ne s'agit pas d'un nouvel univers d'entraînement ni d'un
filtre supplémentaire de classement. Le nombre négociable est relu chez le
broker à chaque lancement ; il peut évoluer depuis les 1 734 du premier
audit. L'éligibilité d'un candidat est encore vérifiée avant son admission.

Le reçu de couverture ne peut servir qu'à la dernière séance US terminée,
en une seule date, depuis un compte PAPER. Il doit avoir moins de dix minutes
au début de l'inférence ; les réutilisations historiques ou LIVE sont refusées.
Les prédictions et backtests standards gardent leur dénominateur habituel.
La liste brute Alpaca, sa projection sur le modèle, leurs empreintes et les
compteurs restent archivés avec la sélection.

## Traçabilité et exécution

`artifacts/q051_paper/q051-<uuid>/` contient :

- `started.json`, `alpaca_assets.json`, `coverage.json` : modèle, profil,
  déclaration du broker, horloge et périmètre du contrôle ;
- `selection.parquet`, `selection.json`, `seal.json` : classement, sélection
  et empreintes du profil, du modèle, du manifeste et des preuves de couverture ;
- `accounts/<compte>/risk.json`, `risk.seal.json`, `execution.json` et claims :
  décisions et exécutions isolées par compte.

Les étapes 11/12 utilisent la même sélection figée pour les comptes PAPER
configurés ; le risque est recalculé avec chaque compte. Les décisions et
cibles sont publiées atomiquement dans les tables canoniques de risque.
L'exécution vérifie les cibles exactes avant de créer les campagnes Winner.
Un résultat ambigu interdit une deuxième soumission automatique.

Le batch vérifie et, si nécessaire, démarre le watcher PAPER avant l'étape 12.
Un ancien service n'est remplacé qu'après contrôle de son identité et
acquisition du verrou d'exécution du compte. Les stops existants ne sont pas
retirés pour cela. Les campagnes Q051 utilisent leur profil figé ; les anciennes
campagnes gardent leurs règles.

Les entrées utilisent un ordre au marché à l'ouverture (`OPG`) de J+1,
jamais un achat tardif pour rattraper une ouverture manquée. La fenêtre est
bornée avant 09h28 New York et suit les séances officielles, avec les règles
d'acceptation des [ordres Alpaca](https://docs.alpaca.markets/us/docs/orders-at-alpaca).
Le watcher gère les exécutions partielles, les stops et l'échéance open11.
Les prix réellement exécutés, frais et décalages peuvent différer du replay :
le raccordement ne promet pas la reproduction de son rendement historique.

## Contrôle sans ordre

Depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe -m scripts.operations.q051_paper_readiness
```

Pour prévisualiser aussi les quantités des trois comptes depuis une sélection
exacte déjà publiée :

```powershell
.\.venv\Scripts\python.exe -m scripts.operations.q051_paper_readiness --selection-run-id q051-<uuid>
```

Ce validateur n'autorise que des lectures SQL et des GET HTTP : aucun ordre,
aucune cible, aucun watcher lancé. Les rapports vont dans un dossier neuf sous
`artifacts/operations/q051_paper_activation/`. Les quantités de cette
prévisualisation sont informatives : l'exécution relit encore le compte et
le budget avant d'envoyer un achat.

## Vérification du 14 novembre 2026

Prédiction de la séance du 13 novembre terminée : **1 643 / 1 738 = 94,53 %**,
minimum 1 617 à 93 %. Univers modèle 1 790, TOP Oracle 179. Sélection LONG :
CTVA, ZS, FLEX, IONS, GLW. Identifiant exact :
`q051-7f930187d5404f26b39e1b5c94a7614e`.

Le validateur avec cette sélection est **PASS** pour les trois comptes :

| Compte | Equity broker | CTVA | ZS | FLEX | IONS | GLW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default | 1 870,22 USD | 21 | 0 | 2 | 2 | 0 |
| test1 | 55 287,34 USD | 641 | 1 | 37 | 0 | 0 |
| test2 | 60 767,33 USD | 704 | 3 | 39 | 9 | 0 |

Ce sont des **quantités prévisualisées, pas des ordres**. Le budget vol20 réduit
les tailles et peut les ramener à zéro. Le compte, l'arrondi entier et les
réservations successives expliquent des compositions différentes, sans preset.
Les trois comptes n'avaient alors ni position ni ordre d'entrée ouvert et le
régime autorisait les entrées. Aucun contrôle supplémentaire n'a été ajouté.

Preuve de la prévisualisation :
`artifacts/operations/q051_paper_activation/20261114-sizing-preview/readiness.json`.
GET HTTP uniquement, zéro écriture SQL, zéro ordre, zéro watcher lancé par le
validateur. La prédiction séparée a enregistré ses scores, sa sélection et son
résumé ; aucune étape 11/12 n'a été exécutée pendant cette vérification.
550 tests de régression passent, ainsi que le test supplémentaire qui interdit
toute résolution de preset capital lors de la construction du risque Q051.
