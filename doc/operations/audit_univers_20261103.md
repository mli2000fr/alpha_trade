# Audit des fichiers config/univers — 3 novembre 2026

> **Décision utilisateur appliquée après cet audit :** les neuf autres fichiers
> ont été archivés et leurs références de lancement remplacées par
> `config/univers/univers_filtred_tradable.txt`. Les décisions proposées ci-dessous
> décrivent l'état **avant** cette consolidation. Voir
> [le fonctionnement courant](univers_fichier_unique.md).

Audit en lecture seule ; aucun déplacement, suppression ou changement de configuration.

Les dix fichiers ont au moins une référence textuelle, parfois uniquement documentaire
ou historique. L'absence d'utilisation courante n'est donc pas l'absence de toute référence.

## Décisions proposées

| Fichier dans config/univers | Symboles | Décision | Justification |
|---|---:|---|---|
| ticket_recherche.txt | 400 | Archivable pour le fonctionnement courant | Identique octet pour octet à ticket_mid_cap_400.txt. Références documentaires/commentaires et test de résolution de chemin ; ce test ne lit pas le contenu. L'alias ticket-recherche charge désormais le premier fichier alphabétique, pas ce fichier. |
| univers_expert_confirmation_300.txt | 300 | Archivable pour le fonctionnement courant | Références trouvées dans des rapports d'anciens entraînements de septembre ; aucune référence de chargement dans le code/configuration courants inspectés. |
| univers_test_rapide.txt | 47 | Archivable pour le fonctionnement courant | Documentation/exemples et anciens rapports de tests exploratoires. Aucun chargement courant nommé trouvé. |
| univers_test_tres_rapide.txt | 12 | Archivable pour le fonctionnement courant | Ancien rapport d'entraînement de septembre ; aucun chargement courant nommé trouvé. |
| research_news_issuer_20261016.txt | 15 | Ancien pilote : archivage conditionnel | scripts/research/us_news_issuer_readiness_20261016.py:75 propose ce chemin et construit une commande de reprise du pilote. Le garder si ce pilote doit être relancé sans adapter son protocole. Aucun batch courant configuré avec ce fichier trouvé. |
| ticket_mid_cap_400.txt | 400 | Outil de recherche : archivage conditionnel | Valeur par défaut réelle de --symbol-file dans modelFactory/eroya_directional_poc.py:282. Les anciens YAML de régime citent config/ticket_mid_cap_400.txt, qui est un autre chemin, désormais absent : ils ne prouvent pas un chargement du fichier de config/univers. |
| oracle_balanced_400_202512.txt | 400 | Conserver avant changement explicite des défauts | Premier fichier alphabétique du répertoire. Les défauts génériques et l'alias ticket-recherche peuvent le charger implicitement. Les références de migration IHM ne constituent pas une utilisation de son contenu ; l'outil de construction le désigne comme sortie. |
| univers_filtred.txt | 2 688 | Conserver | Source par défaut des constructeurs d'univers et symbols_file de config/oracle_canary.yaml, dont enabled vaut true. Cela ne prouve pas à lui seul qu'un scheduler canary est effectivement lancé. |
| univers_filtred_equities.txt | 1 790 | Conserver | screener.custom_universe_file dans config.yaml:595 ; également plusieurs outils/protocoles de recherche. Le batch us_pipeline substitue son fichier partagé, mais les lancements manuels peuvent conserver ce défaut du screener. |
| univers_filtred_tradable.txt | 1 790 | Conserver | Defaults courts ML Train, ML Predict, Régime Marché et divers outils Oracle/LLM. Un identifiant court se résout dans config/univers, pas dans config/univers_batch. |

Archiver les quatre premiers retire aussi ces choix des listes déroulantes qui découvrent
automatiquement les fichiers présents. Leurs anciennes commandes devront utiliser le
chemin d'archive ou rétablir le fichier pour être rejouées.

## Dépendances implicites importantes

`common/universe_files.py` découvre les fichiers `.txt` du dossier et les trie par nom.
`default_universe_file_source`, `default_universe_file_source_or` et l'alias
`ticket-recherche` choisissent le premier, actuellement `oracle_balanced_400_202512.txt`.

Ces mécanismes sont utilisés notamment par les pages Fondamentaux, Swing Score et
certains réglages du backtest. Ils empêchent de déclarer le premier fichier inutilisé
sur la seule base d'une recherche de son nom.

`universe-file:univers_filtred_tradable.txt` désigne le fichier de **config/univers**.
`universe-file:config/univers_batch/univers_filtred_tradable.txt` désigne une autre copie.
Ces copies ont actuellement les mêmes octets et les mêmes 1 790 symboles, mais ne sont
pas interchangeables sans adaptation des références. Les autres deux copies identiques
dans config/univers sont `univers_filtred_equities.txt` et `univers_filtred_tradable.txt`.

## Étendue des contrôles et preuves

- Inventaire, nombres de symboles et SHA-256 des dix fichiers.
- Recherche des noms dans le code, configurations, scripts, tests et documentation.
- Inspection des chargements dynamiques et des références qui ne sont que des commentaires,
  sorties de génération, migrations de préférences ou anciens chemins inexistants.
- Recherche dans les manifestes/configurations/rapports historiques sélectionnés sous
  artifacts ; tous les JSON/YAML des modèles présents, préférences IHM, historiques
  pipeline et filtres options/LLM ont aussi été recherchés séparément.
- Aucune mention explicite de ces noms trouvée dans les lignes de commande des processus
  Python/PowerShell/cmd visibles au moment du contrôle. Cela ne prouve pas l'absence
  d'un chargement indirect par configuration ou d'un choix dans une session IHM en mémoire.

Les données binaires/compressées, sauvegardes, gros fichiers >8 Mio, journaux complets
et références éventuellement stockées uniquement dans MySQL n'ont pas fait l'objet
d'une recherche exhaustive. Les conclusions portent sur le fonctionnement courant
observable dans les sources/configurations et les artefacts inspectés, pas sur une
garantie d'absence de référence dans toutes les anciennes sauvegardes.

Preuves détaillées : `artifacts/operations/universe_usage_audit/20261103-v1/` :
`inventory.json`, `references.json`, `runtime-artifact-all-json-references.json`
et `batch-copy-comparison.json`.
