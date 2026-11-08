# Import des archives historiques FIRDS en SQL FR

Import local autorisé le 6 novembre 2026, après le nettoyage du lot A.
Source : `F:/projets/artifacts/fr/esma_firds`, soit 5 671 fichiers,
59 903 375 259 octets : 5 630 ZIP et 41 documents JSON. Aucun téléchargement
fournisseur lors de l'import. Les copies locales ont ensuite été supprimées
après le raccordement et les contrôles détaillés en fin de document.

## Stockage

La base cible est exclusivement **alpha_trade_fr**. Les tables existantes
de la migration `0012_fr_sql_primary` conviennent ; aucune nouvelle table
n'est nécessaire :

- `fr_collection_objects` : empreinte SHA-256 et taille d'un contenu unique ;
- `fr_collection_object_parts` : contenu binaire original découpé en blocs
  de 1 000 000 octets, compatible avec la taille des paquets MySQL ;
- `fr_collection_versions` : association entre chemin logique et contenu ;
- `fr_collection_heads` : version courante de chaque ressource ;
- `fr_collection_runs` : compteurs et bilan de l'import.

Les ressources sont dans la famille `fr_reference_inputs`, avec des clés
comme `esma_firds/replay_2018/2018/DLTINS_20180104_01of01.zip`.
Deux fichiers identiques peuvent partager un objet binaire tout en conservant
leurs deux chemins. Le ZIP et les JSON sont conservés octet pour octet ; les
millions d'enregistrements XML ne sont pas importés automatiquement dans les
tables canoniques d'instruments ou de données de marché.

## Intégrité et disponibilité

Le manifeste local fige les chemins, tailles et dates de modification.
L'import vérifie l'immobilité du fichier pendant sa lecture, contrôle la
structure des ZIP, puis relit **tous les blocs depuis SQL** : ordre continu,
taille totale et SHA-256 identiques à la source. Ce contrôle certifie la copie
des octets ; il ne remplace pas une nouvelle qualification sémantique de tous
les enregistrements XML ou des anciennes preuves de publication ESMA.

Chaque fichier est traité par transactions. Une interruption ne nécessite
pas de recommencer les écritures déjà présentes ; les objets existants sont
relus et vérifiés. Une version courante SQL différente est préservée :
l'ancienne archive est stockée comme version historique sans remplacer la
tête utilisée par les collecteurs. `Repository.put(...,
preserve_existing_head=True)` est réservé à ce mode ; les écritures normales
des batchs conservent leur comportement précédent.

La disponibilité SQL est celle de l'import, **pas celle de l'année du ZIP**.
Aucune promotion PIT, ML, tradable ou marché canonique ; aucun ordre broker.
Les documents de preuve historiques gardent leurs dates internes originales.

## Suivi et reprise

```powershell
.\.venv\Scripts\python.exe -X utf8 -u -m service.fr.firds_sql_history_import `
  --output artifacts/operations/firds_sql_history_import/20261105-v1 `
  --workers 4 --executor process
```

L'exécuteur par processus évite le goulot de l'encodage Python des gros
binaires. Au plus quatre archives sont en mémoire/en transfert à la fois.
Chaque processus a sa propre connexion FR ; seul l'importeur possède son
verrou, sans arrêter les collecteurs quotidiens. Trois erreurs consécutives
arrêtent l'alimentation de nouvelles tâches ; les transactions en cours peuvent
finir et seront retrouvées lors de la reprise.

Le même répertoire et manifeste permettent la reprise. Si l'arbre source
change, l'import refuse de réutiliser ce manifeste. Les pilotes limités
`--max-files` ont un statut `PAUSED_LIMIT`, jamais un succès complet.

Fichiers de suivi sous le répertoire d'opération : `source-manifest.json`,
`progress.json`, `files.jsonl` et `report.json`. Le journal peut contenir
plusieurs vérifications d'un chemin après reprise ; la dernière entrée par
chemin fait foi pour le bilan final. Les requêtes SQL et les corps binaires ne
sont jamais écrits dans les logs.

Cette commande décrit l'import initial. Après la purge autorisée ci-dessous,
le manifeste est conservé mais les sources locales ne sont plus présentes :
ne pas relancer cet import pour lire les archives. Les lecteurs accèdent à SQL.

## Validation

20 tests ciblés réussis sur le stockage FR et l'import : aller-retour binaire,
plusieurs blocs, déduplication concurrente, reprise idempotente, préservation
d'une tête plus récente, rejet de corruption SQL, ZIP invalide et source
modifiée, et finalisation d'une version ou d'une tête après interruption entre
les deux transactions. Les résultats réels définitifs sont consignés ci-dessous.

## Lecture d'une archive en base

```python
import zipfile
from service.fr.batch_research_store import engine_fr
from service.fr.collection_storage import Repository, use, zip_source

engine = engine_fr()
repo = Repository(engine)
path = repo.root / 'esma_firds/replay_2018/2018/DLTINS_20180104_01of01.zip'
try:
    with use(repo), zipfile.ZipFile(zip_source(path)) as archive:
        print(archive.namelist())  # noms XML seulement, pas d'extraction locale
finally:
    engine.dispose()
```

La sauvegarde `fr_db_backup` porte sur toute la base FR et inclut ces tables.
L'import ajoute une copie SQL ; il ne supprime pas la copie ZIP du projet.

Cette phrase décrit l'étape d'import seule ; la suppression distincte et
autorisée est consignée ci-dessous.

## Résultat réel terminé et contrôlé

Import finalisé le **06/11/2026 00:35:41 Europe/Paris**, puis vérification SQL séparée terminée : **VERIFIED_COMPLETE**.

| Contrôle | Résultat |
|---|---:|
| Fichiers du manifeste | 5,671 |
| ZIP | 5,630 |
| Métadonnées JSON | 41 |
| Versions SQL vérifiées | 5,671 |
| Octets sources vérifiés | 59,903,375,259 |
| Objets binaires uniques | 5,665 |
| Octets uniques après déduplication | 59,886,846,186 |
| Blocs SQL numérotés vérifiés | 62,904 |
| Erreurs | 0 |
| Fichiers sources supprimés | 0 |
| Appels fournisseur | 0 |

Les 5 671 fichiers sont présents sous leur clé logique et leur contenu original,
avec relecture intégrale SHA-256 pendant l’import. Le contrôle séparé confirme
la finalisation du run SQL, les tailles/versions, tous les numéros de blocs et
la lecture SQL seule de neuf ZIP représentatifs (2018–2026), en interdisant
la lecture du contenu des fichiers locaux. Zéro conflit de tête courante ;
l’arbre source est inchangé. Ces contrôles certifient la copie des fichiers
existants, pas l’exhaustivité de toutes les publications ESMA sur la période.

Run SQL : `fr-firds-import-44259332f6fc4d498753cbfceb9b6eca`. Rapports : `artifacts/operations/firds_sql_history_import/20261105-v1/report.json`,
`verification.json`, `source-manifest.json`, `files.jsonl`. Les copies du code
utilisé sont conservées avec les rapports. La première exécution par threads a
été interrompue puis reprise avec quatre processus ; les transactions par
fichier déjà validées ont été conservées et revérifiées. Les entrées répétées
du journal reflètent cette reprise, sans objets binaires dupliqués en SQL.

## Lecteurs raccordés à SQL et suppression locale — 6 novembre 2026

**Terminé le 06/11/2026 à 18:56:51 Europe/Paris : 5 671 fichiers supprimés,
soit 59 903 375 259 octets (59,903 Go).** Aucun objet SQL supprimé, aucun
service métier arrêté. La copie locale et son répertoire temporaire de
vérification sont absents ; les données restent dans `alpha_trade_fr`.

`service/fr/firds_storage.py` résout automatiquement les chemins logiques sous
`artifacts/fr/esma_firds` vers `fr_collection_*`, même pour une commande Python
indépendante, sans contexte opérationnel hérité. Cela couvre les contrôles
de présence, listes récursives, rapports JSON, empreintes, ZIP et XML. Une
ressource absente/corrompue en SQL reste une erreur ; aucun repli sur disque.
Les chemins de fixtures hors de ce périmètre restent utilisables hors ligne.

Outils raccordés : téléchargement/reprise, rejeu historique, chaîne annuelle,
audit des lacunes, réconciliation Full, pilote de référence, recalcul des
intervalles, audit de couverture des barres, dossiers de qualification et
rejeux pré-ancre, contrôle des réserves et construction des identités 6-C.
Les empreintes d'entrées FIRDS des manifestes 5/6 passent aussi par SQL.
Les JSON produits dans ce périmètre et les nouveaux ZIP y sont enregistrés en
SQL ; les téléchargements n'utilisent qu'un espace temporaire de travail.
Le contexte SQL est transmis explicitement aux workers de téléchargement.
Les logs et résultats de recherche hors de ce périmètre gardent leur destination.

Validation réalisée avant effacement, avec le répertoire local effectivement
absent (déplacement temporaire réversible, et non simple préférence SQL) :

- **117 tests réussis**, dont tests sans aucun dossier local, corruption SQL,
  refus du MD5 incorrect, reprise et téléchargement évité pour un ZIP déjà en SQL.
- Nouvelle vérification des **5 671 versions / 62 904 blocs** contre le
  manifeste d'import inchangé ; aucun conflit de tête courante.
- Liste SQL exacte des **5 630 ZIP**, lecture et SHA-256 des **41 JSON**.
- Neuf ZIP 2018–2026 relus avec SHA-256 et contrôle CRC intégral.
- Neuf historiques annuels validés ; audit de **5 604 archives** identique au
  rapport figé, sans fichier manquant ; lacunes de publication anciennes conservées.
- Recalcul 2018 identique au rapport figé, **1 230 versions** ; rejeu réel du
  Full initial : **418 couples** pour les 490 candidats historiques.
- Réconciliation réelle des XML du Full 2018 : **431 couples**, mêmes résultats
  que le rapport figé ; commande en sous-processus également validée.

L'acceptation n'a effectué aucune écriture SQL ni aucun appel fournisseur.
Un dernier contrôle après suppression confirme les lectures SQL. Ces tests
ne constituent pas un nouveau rejeu intégral de tous les XML sur neuf ans,
ni une levée des réserves PIT/publications historiques.

Preuves : `artifacts/operations/firds_sql_removal/20261106-v1/`, notamment
`pre-removal-import-verification/verification.json`, `tests.xml`,
`absent-local-validation/report.json`, `removal-preflight.json`,
`removal-report.json` et `post-removal-sql-check.json`.
Les anciennes preuves d'import sont conservées intactes dans leur dossier initial.

Pour refaire l'acceptation en lecture seule après purge, avec un dossier neuf :

```powershell
.\.venv\Scripts\python.exe -X utf8 -u -m scripts.operations.validate_firds_sql_readers `
  --output artifacts/operations/firds_sql_removal/nouvelle-validation
```

Les chemins mentionnés par les anciens rapports sont désormais des clés
logiques. `Test-Path` et l'ouverture directe avec `Path.read_bytes()` ne sont
pas des moyens de vérifier ces archives ; utiliser `firds_storage.read_bytes`,
`read_text`, `is_file`, `paths` ou `zip_source`. Les sauvegardes de la base FR
incluent les objets ; une sauvegarde des seuls fichiers du projet ne les inclut pas.
