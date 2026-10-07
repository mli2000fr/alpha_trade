# Sprint 15-E — Référentiel ESMA quotidien et prérequis INPI

5 octobre 2026. Collecte gratuite publique ESMA, fichiers de recherche FR
uniquement. Ce n'est ni une promotion SQL ni une réparation de l'historique.

## Périmètre et architecture

Service : `service/fr/security_master_daily_15e.py`, raccordé au runner FR
`operational_batch_15a` et au launcher commun (logs, email/Telegram).
Configuration exclusivement `batch_fr.yaml/fr_security_master_sync`.

Mise à jour du 7 octobre : [remédiation 16-F](sprint_16f_remediation.md).
Passage désormais à **7 h Paris**, toujours jusqu'à J−1, pour tenter de couvrir
la dernière séance avant ouverture. Disponibilité du référentiel complet datée
après téléchargement, contrôles et rejeu ; aucune réparation rétroactive de
la continuité historique ni activation shadow.

La base initiale est `history_2026_observed_v2.json`, terminée le 01/10/2026.
Seuls les **330 ISIN qualifiés S6C**, avec XPAR/ALXP/XMLI, sont suivis. Ils
incluent des titres historiquement radiés ; ce n'est pas une découverte de
toutes les introductions FR ni une mise à jour automatique des tickers EODHD.
Les **294 titres actifs** utilisés par EODHD restent issus du S6C figé.

```text
Référence S6C + historique ESMA figé et hashé
  → catalogue DLTINS officiel récent
  → toutes les partitions de chaque publication
  → ZIP/XML et MD5 officiel quand disponible, SHA-256 local
  → événements des 330 ISIN/MIC cibles
  → observations + versions + checkpoint fichiers
  → pas de SQL / pas d'ordres / pas de GO tradable
```

## Dates, reprise et sécurité

- Fin : J−1 Paris. La publication J peut être partielle même après clôture.
- Recouvrement : jusqu'à sept jours déjà observés pour contrôler l'intégrité.
- Rattrapage automatique depuis le checkpoint, limité à 31 jours et 128 ZIP.
  Un retard supérieur nécessite un rejeu manuel qualifié, pas un skip silencieux.
- Une date sans publication est **inconnue**, y compris le week-end ; elle
  n'est pas interprétée automatiquement comme une absence de changement.
- Numérotation `01of04` à `04of04` contrôlée. Partie manquante/dupliquée,
  mauvais domaine ou changement d'un hash connu : arrêt, checkpoint inchangé.
- Version publiée seulement après tous les contrôles ; checkpoint remplacé
  en dernier. Un crash entre les deux laisse une version orpheline inoffensive.
- Verrou local par batch + verrou du launcher ; reprise ne répète pas les
  événements déjà identifiés par archive/hash.
- Observation du catalogue conservée à chaque passage. Une même information
  peut être observée deux fois, mais les versions métier ne sont pas doublées.

Le checkpoint initial conserve `historical_continuity_confirmed: false` et
les dates historiques manquantes. Le succès récent ne transforme pas ce champ
en vrai. Les nouveaux enregistrements distinguent `publication_archive_date`
et **`available_at = observed_at` réel**, pour ne pas antidater une collecte.
Les intervalles hérités du rejeu restent des preuves as-of de publication,
pas des observations contemporaines effectuées en 2018.

Les événements New/Modified/Terminated/Cancelled recalculent les versions et
épisodes ISIN/MIC. Une anomalie d'ordre/date reste explicitement visible ; le
collecteur ne certifie pas l'ordre intraday de deux modifications le même jour.

## Données et compteurs

Sous `artifacts/fr/operations/fr_security_master_sync` :

- `archives/YYYY/*.zip` : sources publiques contrôlées ;
- `observations/*.json` : catalogue reçu, fenêtre, disponibilité/absences ;
- `versions/<hash>.json` : référence versionnée pour le périmètre ;
- `checkpoint.json` : dernière référence récente publiée avec succès.

Demandés/reçus comptent les archives ; persistés compte les **nouvelles
versions ISIN/MIC**, pas les fichiers ni les lignes SQL. Zéro nouvelle version
avec neuf archives reçues peut être normal : aucun changement ne concernait
les 330 ISIN. Ce n'est pas une preuve que tout le marché FR est inchangé.

Premier passage réel : `validation_15e/20261005T193034671049Z.json` :
02→04/10/2026, **9/9 ZIP**, zéro nouvelle version cible, zéro anomalie récente,
checkpoint au 04/10. Les trois journées disposent de toutes leurs partitions.
Second passage : `validation_15e/20261005T193200712355Z.json`, neuf archives
réutilisées/contrôlées, zéro version supplémentaire, même checkpoint, sans
anomalie. Activation **ACTIVE_RESEARCH** effectuée dans le catalogue, sans
installation Windows automatique. Le cas réel de la fenêtre ne contenait
aucun changement cible ; les transitions/radiations sont donc testées
unitairement, pas encore démontrées par un événement récent des 330 ISIN.

## Utilisation

Qualification manuelle, sans changer enabled ni installer de tâche :

```powershell
python -u -m service.fr.security_master_daily_15e --dry-run
python -u -m service.fr.security_master_daily_15e
```

Les rapports de qualification sont dans `artifacts/fr/operations/validation_15e`.
Une fois activé, utiliser les commandes/boutons FR de la page Batch. L'horaire
proposé reste **20:00 Europe/Paris**, et la fenêtre s'arrête à J−1.
Le lancement via le wrapper, contrairement à la CLI de qualification, utilise
les notifications du launcher commun. Livraison réelle à tester séparément.

## Fondamentaux : accès gratuit INPI à obtenir

Source officielle : [Data INPI — accès API entreprises](https://data.inpi.fr/content/editorial/Acces_API_Entreprises).
Créer un [compte Data INPI](https://data.inpi.fr/login), puis demander les accès
depuis **« Mes accès API / SFTP »**, rubrique comptes annuels/bilans.

L'INPI annonce des comptes déposés depuis 2017, non confidentiels, disponibles
en JSON/PDF et mis à jour quotidiennement. Cela ne garantit pas l'accès à
chaque groupe coté ni à tous ses comptes consolidés. Il faut encore qualifier :

1. authentification et droits d'accès effectivement accordés ;
2. mapping ISIN → entité légale/SIREN, sans confondre groupe et filiale ;
3. type de comptes : sociaux/consolidés, période et unité/devise ;
4. dépôt/publication/observation, corrections et confidentialité ;
5. champs comptables, comptes connus absents et couverture par émetteur ;
6. pertinence ML séparée, après qualification des données, sans promesse D1/D10.

Mise à jour du 05/10 : l'utilisateur confirme que l'accès est accordé.
Aucun identifiant INPI n'est encore disponible dans l'environnement du processus.
Configurer **INPI_USERNAME** (email du compte) et **INPI_PASSWORD** dans les
variables d'environnement utilisateur Windows, jamais dans le YAML/chat.
La [documentation officielle septembre 2026](https://www.inpi.fr/sites/default/files/2026-09/documentation%20technique%20API_comptes_annuels%20v6-1-AA.pdf)
décrit un POST sur `/api/sso/login`, puis un Bearer token. Ne jamais archiver
la réponse de login : elle contient le token et des informations personnelles.
Mise à jour après ces étapes : accès validé, pilote dix sociétés réalisé,
`fr_fundamentals_sync` activé **en quarantaine uniquement**, sans alimentation
SQL ni ML ; voir [15-F](sprint_15f_inpi_comptes_annuels.md). Les consignes
d'accès ci-dessus décrivent les prérequis déjà réalisés.
Le bloc consensus/borrow/options n'est pas remplacé par INPI : ces comptes ne
sont ni un consensus analystes, ni des frais de borrow, ni des options.

## Sauvegarde : incident distinct

La première qualification complète des artefacts a échoué pendant l'extraction
sur le remplacement de `progress.json` (`WinError 5`). Aucun hash incorrect n'a
été signalé, mais **aucun succès d'extraction complète ne peut être déclaré**.
Les sorties partielles sont conservées. Le writer applique désormais une
reprise bornée des PermissionError transitoires Windows ; test de non-régression.
Une nouvelle qualification complète est nécessaire. Le batch reste désactivé
jusqu'à `EXTRACTION_VERIFIED`. Voir [15-D](sprint_15d_sauvegardes_et_blocages.md).

Relance effectuée à **21:32 Paris**, PID de lancement 120056 (non persistant).
Le premier run échoué et ses fichiers partiels sont conservés pour inspection.
Suivre le **nouveau** dossier, pas celui du premier échec :

```powershell
Get-Content F:\projets\backups\fr\qualification\20261005T193256-a4610757\progress.json -Raw
Test-Path F:\projets\backups\fr\qualification\20261005T193256-a4610757\report.json
Get-Content F:\projets\log\batch_fr\backup-qualification-retry-20261005-213255\stderr.log -Tail 20
```

90 tests ciblés passent : service ESMA, transitions et idempotence, backup et
verrou Windows, runner FR, collecteurs FR, catalogue/IHM et routage FR/CN.
Aucune modification des tables ni des tâches Windows existantes.
