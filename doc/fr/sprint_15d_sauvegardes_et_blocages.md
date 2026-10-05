# Sprint 15-D — Sauvegardes vérifiées et référentiels encore bloqués

État au 5 octobre 2026. Ce document complète le catalogue 15-A et la collecte
15-C ; il ne clôture pas tout le Sprint 15 et n'autorise aucun trading FR.

## 1. Identifiants : partage autorisé, bases séparées

Le propriétaire a confirmé que les trois marchés utilisent les mêmes
identifiants MySQL. `config/databases.yaml` déclare donc pour `fr_primary` :

- priorité à `LOGIN_DB_FR` / `PASSWORD_DB_FR` lorsqu'ils existent ;
- fallback explicite `LOGIN_DB` / `PASSWORD_DB` ;
- base physique obligatoirement `alpha_trade_fr`, jamais `alpha_trade` ni CN.

Partager des identifiants ne fusionne pas les données. Les contrôles de
marché/alias/base réelle restent actifs ; les tests vérifient aussi qu'un
déploiement sans fallback échoue lorsque ses identifiants FR manquent.
Ne jamais placer les mots de passe dans les commandes, les YAML ou les docs.

## 2. Sauvegarde de la base FR : preuve réelle acquise

Qualification lancée par :

```powershell
python -u -m service.fr.backup_qualification_15d database
```

Preuve :
`backups/fr/qualification/20261005T191341-42dd10c5/report.json`.

Le dump `backups/fr/db/alpha_trade_fr_20261005_191343.sql.gz` mesure
55 783 109 octets. La restauration dans
`alpha_trade_fr_restore_6d86809f` a donné **28 tables et 2 850 495 lignes**,
identiques à la source. Les inventaires des colonnes, index, vues, routines et
triggers ont également été comparés. Des inventaires vides prouvent l'absence
d'objets dans cette source, pas la capacité à restaurer tous les objets futurs.

Le protocole :

1. Résout exclusivement la route `FR_EQ/fr_primary` et vérifie la base réelle.
2. Capture l'inventaire et les nombres de lignes avant le dump.
3. Crée un dump avec transactions, routines et triggers via le service commun.
4. Refuse les instructions qui changent/créent/suppriment une base et les
   références qualifiées aux bases de production. Ce filtre est conservateur :
   un dump contenant de telles chaînes dans des données peut être refusé,
   nécessitant une revue ; il ne constitue pas un analyseur SQL général.
5. Génère un nom temporaire aléatoire, vérifie qu'il n'existe pas, crée cette
   base et y restaure le dump sans `local_infile`.
6. Compare tables, nombres de lignes et structures ; vérifie que la source
   n'a pas changé entre les deux inventaires. Des écritures concurrentes qui
   changent les compteurs rendent la qualification invalide, pas la source.
7. Enregistre le hash du dump et le rapport. Aucun INSERT/UPDATE/DROP n'est
   exécuté dans les trois bases de production.

Ce n'est pas un checksum de toutes les valeurs SQL ni une preuve de reprise
point-in-time avec binlogs. Le dump reste la sauvegarde transactionnelle du
contenu ; la comparaison de restauration couvre les structures et compteurs.

La base temporaire est **conservée**, y compris en cas d'échec après création.
Son nettoyage n'est pas automatique : vérifier le rapport et le nom exact
avant toute suppression manuelle. Les archives FR sont conservées selon
`keep`, actuellement 3, sans toucher les répertoires US/CN.

`fr_db_backup` est désormais `enabled: true / ACTIVE`, dimanche **03:00
Europe/Paris**. Installer/réinstaller cette seule famille dans la page
Workflow & Orchestration → Batch → France. L'activation YAML n'installe pas
une tâche Windows et ne démontre pas encore la réception mail/Telegram.
Le launcher commun conserve ses notifications et son verrou par batch.

## 3. Artefacts : vérification complète lancée, activation conditionnelle

```powershell
python -u -m service.fr.backup_qualification_15d artifacts
```

Sources exclusives : `artifacts/fr` et, si présent,
`artifacts/models/fr_eq`. La seconde racine absente est ignorée, sans
substitution par les modèles US. `catboost_info` n'est pas requis par le
serving : ce sont des sorties de diagnostic d'entraînement.

Le premier contrôle complet porte sur **14 429 fichiers / 61 167 331 917
octets**, soit environ 61,17 Go décimaux. Les archives ESMA constituent une
grande part du volume. Une compression gzip niveau 1 limite le coût CPU ;
un ZIP déjà compressé ne rétrécit pas nécessairement.

Protocole implémenté dans `service/fr/backup_qualification_15d.py` :

- rejet des liens et jonctions ; refus d'une destination sous la source ;
- contrôle de l'espace disque avant création ;
- hash SHA-256 de chaque fichier et contrôle taille/date de modification
  pendant l'archivage ; contrôle de l'inventaire source ;
- création dans un nom `.partial`, jamais exposé comme archive validée ;
- relecture intégrale de l'archive et comparaison taille/hash au manifeste ;
- pour la qualification initiale, extraction réelle dans un répertoire neuf,
  puis nouvelle lecture/hash de chaque fichier restauré ;
- refus des chemins absolus, remontées `..`, autres racines, liens et membres
  inattendus. Aucun `extractall` ; répertoires vides conservés ;
- publication du `.tar.gz` et manifeste seulement après succès ; rotation
  limitée aux archives de ce service après vérification. La dernière archive
  est conservée même si deux créations ont lieu dans la même seconde.

Ce n'est pas un snapshot atomique du système de fichiers. Éviter les écritures
FR concurrentes pour la qualification : une modification détectée fait échouer
le contrôle. Les preuves d'extraction et fichiers partiels d'échec restent
disponibles pour inspection ; ils ne sont pas supprimés par la rotation
`keep` et consomment de l'espace.

Pour les futures exécutions planifiées, le handler FR vérifie intégralement
l'archive et ses hashes, sans refaire une copie extraite de 61 Go chaque semaine.
La qualification initiale conserve volontairement sa copie extraite.

Suivi du run lancé le 05/10/2026 à 21:15 Paris :

```powershell
Get-Content F:\projets\backups\fr\qualification\20261005T191520-c567efa8\progress.json -Raw
Test-Path F:\projets\backups\fr\qualification\20261005T191520-c567efa8\report.json
Get-Content F:\projets\log\batch_fr\backup-qualification-20261005-211520\stderr.log -Tail 20
```

Phases : `ARCHIVING`, `EXTRACTING_VERIFY`, `VERIFIED`. Le rapport final exige
`EXTRACTION_VERIFIED` pour qualifier cette branche. Un `report.json` présent
peut aussi contenir `FAILED` : lire son statut. PID de lancement 118884,
mais les PID ne sont pas des identifiants persistants.

`fr_artifacts_backup` demeure désactivé jusqu'à cette preuve finale. Aucun
batch existant n'a été arrêté, reconfiguré ou installé par cette qualification.

Mise à jour 15-E : ce premier run a finalement échoué pendant l'extraction
sur un verrou Windows de `progress.json`. Il n'est pas qualifié. Le writer
est corrigé avec retries bornés ; voir le [suivi 15-E](sprint_15e_referentiel_quotidien.md).

## 4. Référentiel FR : pas de faux déblocage

Évolution 15-E : un collecteur fichiers récent pour les 330 ISIN S6C est
désormais activé en recherche après deux passages réels. La checklist
ci-dessous demeure nécessaire pour un référentiel complet/promu en SQL,
pas pour cette collecte limitée. Voir [15-E](sprint_15e_referentiel_quotidien.md).

Le référentiel historique de départ est
`artifacts/fr/esma_firds/replay_2018/history_2026_observed_v2.json` :
2018-01-06 → 2026-10-01, 5 604 archives, 490 identités avec MIC cible,
4 139 versions. `complete: true` signifie que les archives indexées sont
présentes ; **`publication_continuity_confirmed: false`** signifie que cela
ne prouve pas une continuité quotidienne totale.

Ces 490 identités d'audit ne sont pas les 330 identités qualifiées S6C ni les
294 actives actuelles. Les périmètres ne doivent pas être confondus.

Avant d'activer `fr_security_master_sync`, il reste à :

1. fixer un checkpoint de référence admissible et expliciter ses lacunes ;
2. indexer tous les fragments DLTINS depuis le checkpoint sans écraser le
   rejeu historique ; conserver les dates de publication et d'observation ;
3. télécharger et vérifier chaque fragment (hash/ZIP), vérifier que la
   journée ne manque pas un fragment ;
4. rejouer Full/New/Modified/Terminated/Cancelled par ISIN/MIC, garder les
   versions et inconnus, sans inventer d'alias ticker EODHD ;
5. tester reprises, absence de publication, changement de référence,
   radiation et nouveau titre ; qualifier les intervalles avant promotion ;
6. valider deux passages réels idempotents et la liaison avec le staging FR.

Un snapshot Full courant ne remplace pas la preuve des intervalles entre deux
observations. Cette famille reste désactivée, sans nouvelle écriture canonique.

## 5. Référentiel/calendrier CN : collecte déjà prise en charge

`cn_master_calendar_sync` est marqué `DISABLED_DUPLICATE_D9`. D9 appelle
`dataIntegrityEngine.cn_sprint7c_incremental.prepare` pour chaque nouvelle
séance dont le manifeste n'existe pas. Cette préparation collecte
`stock_basic`, `trade_cal` et `index_daily` via BaoStock, puis prépare les
identités et chunks. Une reprise avec manifeste complet ne répète pas
aveuglément cette préparation.

Les écritures passent par le staging et la promotion existants, pas par un
deuxième batch générique. Le **calendrier annuel de planification** D9/D6
reste un contrat distinct : la collecte `trade_cal` ne réécrit pas
automatiquement son fichier YAML. Le renouveler explicitement pour une année
future. Ne pas activer `cn_daily_market_data_sync` ni le contrôle remplacé
par `cn_daily_quality_17c`.

## 6. Validation et suite

83 tests ciblés passent (qualification FR, catalogue, routage FR/CN,
séparation IHM des marchés, contrôles collecteurs et gestion Batch), sans exiger la couverture globale d'une suite
partielle. Ce nombre n'est pas la validation de tous les tests applicatifs.
Aucune migration : pas de nouvelle table métier.

Après le rapport final des artefacts : l'examiner, activer cette seule famille
si vérifiée, puis traiter le référentiel FR selon la checklist ci-dessus.
Les fondamentaux FR et consensus/borrow/options restent sous qualification
fournisseur ; cette tranche ne les débloque pas.

## Mise à jour finale — 05/10/2026

La reprise de la sauvegarde a réussi : rapport
`backups/fr/qualification/20261005T193256-a4610757/report.json`,
`EXTRACTION_VERIFIED`. Les 14 448 fichiers (61 268 388 163 octets source)
ont été archivés, extraits réellement et vérifiés par SHA256.
`fr_artifacts_backup` est désormais actif dans le catalogue, samedi 02:00 Paris,
keep 3 configurable. Les anciennes tentatives ont été conservées.
Cette validation remplace l'attente de preuve décrite plus haut.

Le référentiel quotidien est également actif après deux passages vérifiés,
voir `sprint_15e_referentiel_quotidien.md`. Le catalogue compte désormais dix familles
activables sur onze ; les tâches Windows ne sont pas installées automatiquement.
INPI a été testé sur dix émetteurs, puis étendu au référentiel S6C :
254 correspondances sur 330 retenues, 76 exclusions motivées. `fr_fundamentals_sync`
est actif en collecte publique **en quarantaine uniquement**, par lots avec reprise.
Fondamentaux utilisables/SQL/ML interdits
avant qualification ; seul consensus/borrow/options reste dormant. Voir
`sprint_15f_inpi_comptes_annuels.md`.
Extension opérationnelle : `inpi_univers_collecte_securisee.md`.
