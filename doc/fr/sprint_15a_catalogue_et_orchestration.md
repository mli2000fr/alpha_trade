# Sprint 15-A — Catalogue et orchestration opérationnelle France

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

5 octobre 2026. GO Sprint 15 reçu. Première tranche implémentée ; **le Sprint
15 complet n'est pas terminé**. La semaine de collecte, les collecteurs
quotidiens fournisseur et la preuve de restauration restent à réaliser.
Mise à jour 15-B : la [collecte EODHD quotidienne fichiers](sprint_15b_eodhd_quotidien.md)
est désormais implémentée et activée en recherche après deux smokes réels.
Les chiffres de validation 15-A ci-dessous décrivent la tranche initiale.
Depuis le [15-C](sprint_15c_deblocage_collectes.md), actions EODHD, AMF,
métadonnées DILA et supervision des runs sont aussi activés en recherche.
La table d'état initial ci-dessous est historique ; le 15-C et batch_fr.yaml
décrivent les états actuels.

## Configuration et interface

`batch_fr.yaml` est distinct des catalogues US/CN. Ses sections héritent de
FR_EQ, fr_primary, XPAR, Europe/Paris et de l'interdiction des écritures
canoniques/serving dans cette première tranche. Aucun univers US n'est utilisé.

Dans **Workflow & Orchestration → Batch**, sélectionner **France — recherche
uniquement** (désormais libellé **France (FR)** dans le sélecteur à trois
périmètres). Depuis la [séparation US/CN/FR](../batchs_perimetres_marches.md),
les trois marchés partagent le même style de compteurs, filtres et boutons.
La vue affiche 11 familles, priorités, fournisseur, rôle,
tables prévues ou absence de SQL, couverture, horaire, prérequis, commandes,
état Windows et dernier rapport local. Les commandes globales ne concernent
que les tâches FR visibles dans ce périmètre. Les métriques SQL US ne sont
pas interrogées par cette vue. Des sections de même nom dans deux catalogues
font échouer la lecture ; aucun choix silencieux du premier fichier.

Les installateurs FR utilisent le launcher commun invisible, mais transmettent
explicitement `batch_fr.yaml` et `fr_operational_launcher_15a.ps1`. Les
installations directes/globales FR ne modifient pas les tâches désactivées ou
non qualifiées. La désinstallation conserve les fichiers/données/journaux.
Lancement manuel : `-Force` contourne l'horaire, jamais `enabled=false`.

**Aucune tâche Windows n'a été installée ou réinstallée pendant ce travail.**
Les batchs déjà en cours n'ont pas été arrêtés ni reconfigurés. Le calendrier
est actif dans la configuration, pas encore dans le Planificateur Windows.

## Catalogue et état réel

| Batch | Priorité | État dans cette tranche | Source / travail restant |
|---|---|---|---|
| fr_calendar_snapshot | P0 | Implémenté, enabled=true | Snapshot du calendrier de bibliothèque XPAR ; pas preuve officielle |
| fr_security_master_sync | P0 | Désactivé, non implémenté quotidiennement | Adapter ESMA/Euronext à l'incrémental, identités/intervalles et versions |
| fr_daily_bars_sync | P0 | Implémenté 15-B, enabled=true, fichiers et staging SQL depuis le 9 octobre | EODHD J−7/J ; [publication staging qualifiée](publication_quotidienne_staging_sql.md), canonicalisation et couverture complète non libérées |
| fr_corporate_actions_sync | P0 | Désactivé, non implémenté quotidiennement | Dividendes/splits/corrections, champs incomplets et preuves |
| fr_pit_quality_daily | P0 | Désactivé, contrôles à construire | Couverture/fraîcheur par séance XPAR, lineage, doublons et dépendances |
| fr_amf_short_sync | P1 | Désactivé, adaptateur quotidien à construire | Positions courtes publiées au-delà des seuils, pas short interest complet |
| fr_dila_disclosures_sync | P1 | Désactivé, adaptateur quotidien à construire | Annonces/pièces DILA, quotas/PIT ; guidance non validée indépendamment |
| fr_fundamentals_sync | P2 | Actif recherche depuis 15-F | INPI public, 254 correspondances retenues sur 330 S6C ; lots/reprise/quarantaine uniquement ; aucun fondamental utilisable/SQL/ML |
| fr_consensus_borrow_options (historique) | P3 | Retiré du catalogue le 06/10/2026 | Remplacé par les collectes séparées ; aucune entrée à installer |
| fr_consensus_snapshot | P3 | Collecte active en quarantaine | Univers FR S6C actif (294 titres), reprise quotidienne ; pas encore utilisé par ML/backtest |
| fr_borrow_snapshot | P3 | Fournisseur manquant | Disponibilité et coût d'emprunt, pas positions courtes AMF |
| fr_options_snapshot | P3 | Fournisseur manquant | Contrats FR/Euronext, licence et couverture à qualifier |
| fr_db_backup | P0 ops | Handler implémenté, désactivé | Dump alpha_trade_fr ; restauration réelle non démontrée |
| fr_artifacts_backup | P0 ops | Handler implémenté, désactivé | Volume/disque et extraction/hash à vérifier avant activation |

Mettre `enabled=true` sur une famille sans handler ne la transforme pas en
collecteur : le runner refuse et produit un échec visible. Mettre seulement
enabled=true sans lever le statut d'attente ne permet pas son installation.

## Calendrier local : réalisation et limites

Service `service/fr/operational_batch_15a.py`, handler fr_calendar_snapshot :
calendrier de J−7 à J+370, horaires UTC et provenance. Horaire proposé :
dimanche 06:00 Europe/Paris (avancé le 10/10 pour l'absence 07:30–20:00 ;
[planning actuel](../operations/horaires_fr_cn_presence_pc.md)). Les bascules heure d'été sont traitées par le
launcher commun ; il ne s'agit pas d'un horaire New York copié.

Le fichier d'observation est
`artifacts/fr/operations/calendar/YYYY-MM-DD.json`. Une deuxième exécution du
même jour remplace uniquement ce snapshot ; les autres jours sont conservés.
Les rapports d'exécution sont distincts : deux runs ne sont pas deux copies
métier du calendrier. Ce snapshot ne peuple pas `market_sessions` et ne
qualifie pas officiellement les exceptions Euronext.

Deux passages réels du 5 octobre 2026 ont chacun demandé/reçu/persisté 266
séances de bibliothèque, sans échec ni alerte. Un seul snapshot calendrier
du jour existe, avec deux rapports d'exécution séparés. Ces compteurs sont
des lignes de fichier, pas des insertions SQL.

## Suivi, erreurs et notifications

Rapports locaux isolés :
`artifacts/fr/operations/runs/<batch>/<timestamp>-<id>.json`.
Ils conservent début/fin UTC, statut, demandé/reçu/persisté/échoué/alertes,
message d'erreur, marché et périmètre. Une configuration incompatible donne
un rapport FAILED ; aucune connexion US n'est substituée. Un dry-run ne
crée pas de rapport/snapshot/backup et ses compteurs ne prouvent pas une
collecte réelle.

La CLI imprime `::alpha_trade_run_summary::` avec les compteurs et l'erreur.
Le launcher commun l'utilise pour les mails et Telegram, comme pour les
batchs existants. En échec, code retour 1 et message détaillé ; la page Batch
réutilise l'affichage rouge du dernier run en échec. L'IHM ne double pas les
notifications du launcher.

Le branchement notifications est réutilisé et testé ; **aucune réception réelle
mail/Telegram FR n'est déclarée validée** par les smokes Python directs.
Une exécution via le launcher devra vérifier cette livraison. Les horaires
des collecteurs fournisseur désactivés sont des propositions, pas une
qualification de leur délai de publication.

## Sauvegardes : isolation et activation

fr_db_backup résout fr_primary/FR_EQ et cible uniquement alpha_trade_fr,
`backups/fr/db`, préfixe alpha_trade_fr. Les identifiants viennent de la route
FR, pas d'un nom de base libre. Dump complet avec routines/triggers,
rétention `keep` paramétrable (3 initialement), dimanche 03:00 proposé.
Le smoke réalisé est un **dry-run**, pas un dump/restauration réel.

fr_artifacts_backup prend uniquement `artifacts/fr` et
`artifacts/models/fr_eq`, archives séparées dans `backups/fr/artifacts/data`
et `models`, keep=3, samedi 02:00 proposé. Si la racine modèles FR n'existe
pas encore, elle est ignorée explicitement ; jamais remplacée par les modèles
US. Les liens symboliques/jonctions dans les sources sont refusés.
Pas de `catboost_info`, fichier de diagnostic non requis pour servir un modèle.

Les archives FR historiques peuvent être volumineuses (notamment ESMA).
Mesurer volume, disque, durée et droits avant de créer une archive complète.
Les backups restent enabled=false / PENDING_RESTORE_PROOF jusqu'à preuve
d'extraction ou restauration sûre dans une destination de test dédiée.

## Commandes et validation

Mise à jour du 05/10/2026 : la [qualification 15-D](sprint_15d_sauvegardes_et_blocages.md)
a validé une restauration réelle de la base FR (28 tables / 2 850 495 lignes).
`fr_db_backup` est activé dans le catalogue, sans installation Windows automatique.
Le contrôle complet des artefacts est lancé ; cette seconde sauvegarde reste
désactivée jusqu'au rapport d'extraction vérifiée. Les paragraphes de dry-run
ci-dessus décrivent la validation initiale 15-A, désormais dépassée pour la DB.

```powershell
python -m service.fr.operational_batch_15a --batch fr_calendar_snapshot --dry-run
python -m service.fr.operational_batch_15a --batch fr_db_backup --dry-run
powershell -ExecutionPolicy Bypass -File scripts/windows/fr_operational_launcher_15a.ps1 -BatchName fr_calendar_snapshot -Force
```

La dernière commande effectue un vrai snapshot et utilise les notifications.
L'installation est disponible dans l'IHM ou via la commande affichée par
cette page ; aucun global US/CN n'est nécessaire.

La vue Batch a été rendue avec le moteur de test Streamlit : aucune exception,
11 configurés / 1 exécutable / 0 installé. Tests dédiés dans
`tests/test_fr_operational_batch_15a.py`, plus non-régressions Batch/notifications
et routage FR : **117 tests ciblés passent**. Ce nombre ne représente pas
la suite complète de l'application. Aucun changement de schéma SQL : aucune migration Alembic
n'est requise pour cette tranche exclusivement fichiers.

## Tranche suivante 15-B (désormais implémentée pour les fichiers)

Construire le collecteur EODHD J−7/J pour un sous-ensemble FR contrôlé, avec
limite d'appels, erreurs partielles, versions/corrections et reprise ; ne
jamais réutiliser le skip « archive complète » du backfill historique.
Qualifier le schéma et deux passages sur un petit univers avant toute
activation sur l'ensemble. Puis raccorder corporate actions, master,
AMF/DILA, qualité et preuves de backup/restauration.

Le gate final du Sprint 15 exige une semaine de collecte vérifiable,
reprise et notifications réelles : il n'est pas satisfait par le catalogue
ou par les deux passages du calendrier local.
