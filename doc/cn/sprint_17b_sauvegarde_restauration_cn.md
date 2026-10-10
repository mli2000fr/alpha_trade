# Sprint 17-B — Sauvegarde et restauration isolées de la base CN

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Ce sprint traite le finding critique du [17-A](./sprint_17a_audit_exploitation_cn.md) : `alpha_trade_cn` n'avait pas de sauvegarde planifiée. Le périmètre est **CN_A / `cn_primary` uniquement**. Les deux sauvegardes US de `batch.yaml`, leur répertoire `backups/db` et les tâches D6/D9/D10 restent inchangés. Ce chantier ne valide ni stratégie de trading ni signal D1/D10.

## Contrat de sauvegarde

Le batch `cn_db_backup` est déclaré séparément dans [batch_cn.yaml](../../batch_cn.yaml). Le [runner CN](../../service/market/cn_db_backup_17b.py) refuse toute configuration visant une base autre que `alpha_trade_cn`, un alias autre que `cn_primary`, un préfixe autre que `alpha_trade_cn` ou une destination autre que `backups/cn/db`. Le dump MySQL complet inclut les routines et les triggers. Il est compressé au fil de l'eau dans `alpha_trade_cn_YYYYMMDD_HHMMSS.sql.gz`. `keep: 3` conserve trois archives de **ce seul préfixe** ; la rotation US reste indépendante.

La tâche prévue est hebdomadaire, dimanche à 04:00 **Europe/Paris**, avec le lanceur [CN dédié](../../scripts/windows/cn_db_backup_launcher_17b.ps1). Celui-ci utilise le journal commun et les notifications email/Telegram avec compteurs `demandés`, `reçus`, `persistés`, `échecs`, `alertes` et le message d'erreur. L'IHM *Workflow & Orchestration → Batch* expose la configuration, le statut, les commandes et le dernier rapport. En mode Windows `Interactive`, la tâche requiert une session utilisateur ouverte ; elle ne garantit pas une exécution PC éteint ou session fermée. Le délai maximal de tâche est 12 heures.

Les secrets MySQL proviennent de `LOGIN_DB` et `PASSWORD_DB` dans l'environnement du processus, jamais du YAML ou des arguments du client MySQL. Le compte utilisé doit disposer des droits de lecture sur CN et, **pour le test de restauration uniquement**, des droits de créer/supprimer une base temporaire. Les archives contiennent les données de la base en clair après décompression : restreindre l'accès au répertoire et prévoir une copie hors machine si une panne disque doit aussi être couverte.

## Preuve de restauration obligatoire

La présence d'un `.sql.gz` ne suffit pas. Le [contrôle 17-B](../../service/market/cn_backup_restore_17b.py) accepte uniquement une archive non vide dans `backups/cn/db` dont le nom correspond exactement au préfixe CN. Il crée une base aléatoire `alpha_trade_cn_restore_<8 caractères hexadécimaux>` après avoir vérifié qu'elle n'existe pas. Le dump est décompressé et importé par flux ; une empreinte SHA-256 est calculée. Le contrôle compare ensuite la liste des tables et le **nombre exact de lignes de chaque table** entre `alpha_trade_cn` et la restauration. Une écriture concurrente sur la source peut produire une différence et doit être investiguée, jamais ignorée. `--cleanup-on-success` supprime seulement la base temporaire créée par ce passage **après** une vérification intégrale réussie. En cas d'échec, elle est conservée pour diagnostic ; ni `alpha_trade` ni `alpha_trade_cn` ne sont ciblées par une suppression.

La commande de preuve, à exécuter avec une nouvelle archive et un nouveau nom de rapport, est :

```powershell
.\.venv\Scripts\python.exe -u -m service.market.cn_backup_restore_17b --archive "F:\projets\backups\cn\db\alpha_trade_cn_YYYYMMDD_HHMMSS.sql.gz" --mysql-path "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" --cleanup-on-success --report "F:\projets\artifacts\research\cn_backup_17b\restore-proof-NOUVELLE_DATE.json"
```

L'activation planifiée est interdite tant que le rapport ne contient pas `status: RESTORE_VERIFIED`, `verification_passed: true`, `cleanup_completed: true`, le même nombre de tables et aucune différence de lignes. Le contrôle établit la **restaurabilité de cette archive**, pas automatiquement celle des archives futures : refaire périodiquement ce test et après changement majeur du schéma. Une sauvegarde locale seule ne couvre ni la panne du disque, ni le chiffrement malveillant, ni la perte de la machine.

## Première exécution du 30/09/2026

La première archive a été créée sans erreur : `backups/cn/db/alpha_trade_cn_20260930_192427.sql.gz`, environ **2,93 GiB compressés** ; aucune archive US n'a été modifiée et aucune rotation CN n'a eu lieu. La base source comptait 21 tables et environ 23,43 GiB selon `information_schema` avant le dump. Le [rapport de restauration](../../artifacts/research/cn_backup_17b/restore-proof-20260930.json) donne le verdict `RESTORE_VERIFIED`, l'empreinte SHA-256 `1ca5e86a16777f29444a814a08d0a2db43f5c4ee6df8852ff4c6e83c6a56b442` et les effectifs par table.

| Vérification | État |
|---|---|
| Dump CN complet | Terminé, sans erreur |
| Base temporaire créée | `alpha_trade_cn_restore_ddc373d1` |
| Inventaire et comptes exacts | 21/21 tables ; 57 188 133 lignes, aucun écart |
| Nettoyage de la base temporaire | Vérifié : base `alpha_trade_cn_restore_ddc373d1` absente |
| Batch hebdomadaire | Activé, `ACTIVE` ; tâche `AlphaTrade-CnDbBackup` installée, état `Ready` |

Ce document suit l'état **effectivement vérifié**, pas simplement le résultat d'une commande planifiée. La tâche Windows déclenche son lanceur chaque heure à `:00`, mais ce dernier n'exécute réellement la sauvegarde que **dimanche à 04:00 Europe/Paris** (ou sur lancement manuel). Ainsi, le `NextRunTime` du Planificateur désigne le prochain contrôle horaire, pas le prochain dump. Le `LastRunTime` Windows peut encore afficher sa valeur par défaut tant que la tâche nouvellement installée n'a jamais été déclenchée ; le dump de preuve initial a été exécuté séparément. Les artefacts ML/recherche CN sous `artifacts` ne sont **pas** inclus dans le dump MySQL ; leur sauvegarde hors base est une politique distincte à définir.

## Validation et reprise

- Contrôler le rapport de restauration et l'absence de la base temporaire après succès.
- Activer `enabled: true` et `status: ACTIVE` seulement après la preuve ; tester le runner en `--dry-run`, puis installer la tâche `AlphaTrade-CnDbBackup` depuis la page Batch ou via l'installeur Windows en lui passant `batch_cn.yaml` et le lanceur CN.
- Vérifier dans l'IHM et le Planificateur Windows le prochain passage dominical ; un lancement manuel reste possible depuis la page Batch.
- Chaque exécution doit créer un rapport de run dans `artifacts/research/cn_backup_17b/runs/`, conserver au plus `keep` archives CN et notifier le succès ou l'échec. Un fichier incomplet ne doit pas être considéré comme sauvegarde réussie.
- Si la restauration échoue, laisser le batch désactivé, analyser le rapport et ne supprimer une base temporaire qu'après identification exacte de son nom et de son rôle.

Commandes opérateur après activation et preuve de restauration :

```powershell
# Simulation du contrat, sans créer de fichier ni faire tourner les archives.
.\.venv\Scripts\python.exe -m service.market.cn_db_backup_17b --batch cn_db_backup --batch-config batch_cn.yaml --dry-run

# Installation / réinstallation de la seule tâche de sauvegarde CN.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName cn_db_backup -TaskName AlphaTrade-CnDbBackup -RunAs Interactive -BatchConfigPath batch_cn.yaml -LauncherPath scripts/windows/cn_db_backup_launcher_17b.ps1

# Vérification de l'action et du dernier résultat Windows.
Get-ScheduledTask -TaskName AlphaTrade-CnDbBackup | Select-Object TaskName,State,Actions
Get-ScheduledTaskInfo -TaskName AlphaTrade-CnDbBackup | Select-Object LastRunTime,LastTaskResult,NextRunTime

# Exécution manuelle, indépendante du créneau dominical mais pas du verrou enabled/status.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/cn_db_backup_launcher_17b.ps1 -BatchName cn_db_backup -Force
```

Un état `COMPLETED` dans le rapport prouve que `mysqldump` a fini et que le fichier a été conservé ; il ne remplace pas un **test périodique de restauration**. En cas d'échec de sauvegarde, le runner écrit `FAILED`, expose son erreur dans le marqueur de résumé et retourne un code non nul au lanceur ; l'IHM et les notifications doivent refléter cette erreur. L'exécution manuelle ne contourne pas le verrou `PENDING_RESTORE_PROOF`.

Les [tests ciblés](../../tests/test_cn_db_backup_17b.py) et les [tests de restauration](../../tests/test_cn_backup_restore_17b.py) couvrent les gardes de routage, de nom et de configuration. Ils complètent, sans remplacer, la restauration réelle.
