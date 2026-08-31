# Audit de remplacement de l’ancienne documentation

## Verdict

Le référentiel `doc/refactor/` est autonome pour l'onboarding, l'exploitation,
la compréhension fonctionnelle et la lecture technique du code courant. Les
anciens documents ne sont pas utilisés comme dépendances de navigation. Les
journaux d'expérience restent des preuves historiques facultatives ; leurs
enseignements utiles sont synthétisés dans `experiences/`.

Cet audit porte sur le dépôt au 29 août 2026. Il ne garantit pas l’état d’une base, d’un broker ou d’artefacts absents du workspace.

## Contrôles réalisés

- inventaire des documents historiques pour identifier les sujets ;
- lecture des points d’entrée, packages métier, configurations, migrations et tests ;
- séparation entre comportement exécutable et résultats d’expériences ;
- guides globaux par domaine ;
- références dédiées pour les contrats complexes ;
- inventaires de classes/fonctions dans `api/` ;
- matrice packages→documents dans `COVERAGE_CODE.md` ;
- validation des liens Markdown internes ;
- recherche de marqueurs de contenu restant à compléter ;
- vérification qu’aucun lien de navigation ne dépend d’un ancien fichier.
- inventaire explicite des **178 Markdown historiques** dans
  `COUVERTURE_DOCUMENTS_HISTORIQUES.md` ;
- reconstruction du manuel à partir des **22 pages** enregistrées dans la
  navigation actuelle et de leurs services ;
- création de références dédiées pour Oracle Extreme, couverture/fallbacks,
  recalibration, granularités de modèles, cascade, datasets, ordre ML, sécurité
  live, performance, rétention, compliance et intégrité/lineage.

## Résultat mesuré

Au contrôle de migration du 29 août 2026 :

| Contrôle | Résultat |
|---|---:|
| fichiers Markdown sous `doc/refactor` | 317 |
| lignes documentaires, archives incluses | 66 845 |
| volume Markdown, archives incluses | 3 700 856 octets |
| liens Markdown internes cassés | 0 |
| liens relatifs sortant de `doc/refactor` | 0 |
| anciens Markdown inventoriés | 178 |
| fichiers conservés comme sources/expériences historiques | 88 |
| anciens répertoires `doc/backup`, `doc/ml`, `doc/monitoring` | supprimés après migration |
| fichiers restant hors `doc/refactor` sous `doc` | 0 |
| modifications détectées hors documentation | 0 |

Ces nombres sont un constat d'audit, pas un objectif de volume. La couverture
est structurée par contrats et responsabilités, avec des documents spécialisés
quand un sujet ne peut pas être expliqué correctement dans une vue globale.

## Couverture autonome

| Besoin d’un nouvel arrivant | Point de départ |
|---|---|
| comprendre le produit | `01_vue_fonctionnelle.md` |
| comprendre l’architecture | `02_architecture_globale.md` |
| installer et lancer | `03_installation_et_demarrage.md` |
| opérer le quotidien | `04_pipeline_quotidien.md`, `22_runbook_exploitation.md` |
| comprendre les données PIT | `05_donnees_et_univers_pit.md`, `data/` |
| développer le ML | `06_ml_vue_ensemble.md`, `ml/` |
| comprendre ranking/Oracle | `07_*.md`, `08_*.md` et références dédiées |
| comprendre le risque | `09_risque_et_portefeuille.md`, `risk/` |
| comprendre régime/exécution | `10_*.md`, `11_*.md`, `execution/` |
| valider/backtester | `12_backtesting_validation.md`, `backtesting/` |
| configurer/services/DB | `14_*.md`, `15_*.md`, `18_*.md` |
| utiliser l’IHM/superviser | `16_*.md`, `operations/` |
| apprendre toutes les pages et procédures | `guide_utilisateur/` |
| contribuer et tester | `19_tests_et_contribution.md` |
| retrouver une API | `21_catalogue_modules.md`, `api/` |
| retrouver le remplacement d'un ancien document | `COUVERTURE_DOCUMENTS_HISTORIQUES.md` |

## Traitement des expériences

Les longues campagnes de seeds, batches, ablations et variantes abandonnées ne
sont pas recopiées. `experiences/` conserve question, protocole générique,
conclusion durable, limites et relation avec le code actuel. `research/`
documente les branches de recherche encore présentes dans le code. Une ancienne
métrique n’est jamais présentée comme configuration ou performance actuelle.

## Points de vérité

En cas de divergence future, utiliser cet ordre :

1. code exécutable et migrations ;
2. tests contractuels ;
3. configuration effective du run ;
4. guides de cette refonte ;
5. archives historiques uniquement comme contexte.

Les valeurs de marché, batches promus et états broker restent des données runtime. Pour reproduire un run, conserver commande, config effective, commit, batch, fingerprints, date, compte et summaries.

## Maintenance

Pour chaque changement :

1. modifier le code et ses tests ;
2. mettre à jour le guide global du domaine ;
3. mettre à jour/créer la référence spécialisée si le contrat est complexe ;
4. régénérer ou corriger l’inventaire API concerné ;
5. vérifier les liens et `COVERAGE_CODE.md` ;
6. dater le nouvel audit de cohérence.

Un nouveau document expérimental reste hors du référentiel maintenu tant que sa conclusion n’est pas promue dans le code. Lors d’une promotion, documenter le comportement final, pas le journal complet de recherche.
