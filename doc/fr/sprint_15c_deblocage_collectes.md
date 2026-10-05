# Sprint 15-C — Déblocage des collectes possibles

5 octobre 2026. Raccordement quotidien fichiers uniquement, pas nouvelles
tables ni migrations, pas serving, pas modification d'un batch existant.
Aucune tâche Windows installée automatiquement. Les boutons de la page Batch
peuvent installer ces tâches maintenant ; configuration et installation sont
deux étapes distinctes.

## État après intervention

Six familles sont `enabled=true`, `ACTIVE_RESEARCH` dans `batch_fr.yaml` :
calendrier, barres EODHD, actions EODHD, AMF, DILA et supervision opérationnelle.
Les quatre dernières sont le nouveau périmètre de cette tranche.

| Batch | Collecte effective | Heure Paris | Limite importante |
|---|---|---|---|
| fr_corporate_actions_sync | EODHD div/splits, J−7/J, titres actifs vérifiés S6C | 23h lun–ven | Observation fournisseur, pas validation finale des droits cash/actions/paiement |
| fr_amf_short_sync | Export courant AMF complet, découverte du CSV via catalogue officiel, filtrage des ISIN vérifiés | 21h lun–ven | Export historique reconstruit, seuil public, absence ≠ zéro |
| fr_dila_disclosures_sync | Export métadonnées J−7/J sur transmission AMF, filtrage des ISIN vérifiés | 21h30 lun–ven | Pas téléchargement de PDF ni extraction/validation guidance |
| fr_pit_quality_daily | Dernier rapport des quatre collectes, succès/ancienneté/smoke | 6h lun–ven | Supervision des runs, pas audit PIT des tables ou fraîcheur individuelle des barres |

Ces heures sont une cadence de recherche, pas une attestation de disponibilité
complète de chaque source à cet instant. J−7/J permet le rattrapage des annonces
retardées. AMF fait un snapshot complet car les corrections peuvent être plus
anciennes que sept jours. DILA filtre la date de transmission, pas toutes les
possibles modifications tardives d'annonces anciennes.

## Stockage et dédoublonnage

Service : `service/fr/operational_collectors_15c.py`, appelé par le runner FR
et le launcher commun pour logs/email/Telegram. Transport HTTPS existant,
taille maximale de 20 Mo pour les exports publics, budget EODHD 400 titres,
intervalle configurable 0,5 seconde, deux appels par titre pour div/splits.
Une clé EODHD est nécessaire ; AMF/DILA ne demandent pas de nouvelle clé.

Racines `artifacts/fr/operations/<nom_du_batch>/` : contenus bruts adressés
par hash, observations horodatées séparées, vue latest, quarantaine et, pour
les actions, progression par titre/type/fenêtre. `.lock` empêche deux passages
simultanés du même collecteur. Vérifier l'absence du processus avant suppression
manuelle d'un verrou après arrêt brutal.

Actions : une réponse vide est normale (aucun événement), contrairement à une
fenêtre de barres attendues vide. Date hors fenêtre, valeur non positive/non
finie, ratio split mal formé ou doublon exact = échec du payload, brut conservé,
pas d'écrasement du latest. Les dates fournisseur sont conservées sans inventer
date de paiement ni décision finale. La vue de chaque titre/type est remplacée
pour les seules dates de la fenêtre ; les retraits fournisseur sont donc
reflétés dans la vue, mais les bruts antérieurs restent consultables. Une
relance normale re-fetch, `--resume` peut reprendre les payloads incomplets.

AMF : le latest représente l'export courant des déclarations acceptées ; un
retrait de l'export change cette vue mais n'efface pas les archives précédentes.
Les lignes historiques invalides sont conservées en quarantaine, comptées
séparément, pas présentées comme 15 échecs réseau actuels. Ratio exprimé en
pourcentage, pas short volume ou preuve de disponibilité d'emprunt.

DILA : dédoublonnage par contenu complet, versions distinctes conservées même
pour un même identifiant d'annonce. Pas de sélection arbitraire « dernière
ligne = bonne version », pas d'agrégation prédictive automatique. Les métadonnées
avec ISIN non couvert sont exclues ; celles rattachées mais sans ID/date valide
ou présentant une date publique future sont mises en quarantaine avec alerte.

`available_at` = observation effective UTC pour toutes ces collectes.
Ni la date de position AMF ni la date de transmission DILA ne deviennent
artificiellement une preuve de disponibilité historique intraday.

## Compteurs et supervision

Actions : demandés/reçus/persistés comptent des payloads titre/type ; un fichier
vide accepté et enregistré compte comme payload persisté. Ce ne sont pas des
lignes SQL ni nécessairement des événements. Public : demandé/reçu = export,
persisté = enregistrement unique nouveau/modifié dans la vue.
La seconde réception inchangée peut donc donner persistés zéro.

Le runner conserve les compteurs après exception et clôture FAILED ; les
rapports locaux alimentent la page Batch. Email/Telegram passent par le
launcher partagé ; les smokes Python directs ne vérifient pas leur livraison.

Supervision : quatre dépendances explicites, `max_run_age_hours: 96` pour
inclure le week-end, dernier statut SUCCESS, run non limité par `--max-symbols`.
Elle n'inclut jamais ses propres échecs. Un run absent/ancien/en échec donne
FAILED avec détail des contrôles et compteurs préservés. Elle peut légitimement
échouer au premier démarrage : il faut d'abord des collectes **complètes**.
Elle n'atteste pas la couverture titre par titre ni la continuité du master.

## Validation réelle

Deux passages, fenêtre 28 septembre–5 octobre 2026 :

- Actions, AB/ABCA/ABVX : premier 6 réponses/payloads persistés ; second 6
  réponses, 0 nouveau payload, 6 inchangés, aucun échec. Test limité, pas
  confirmation de couverture des 294 titres ni présence d'actions cette semaine.
- AMF : 14 076 déclarations uniques du référentiel, 0 nouvel enregistrement
  au second passage ; 15 lignes historiques en quarantaine. Licence du catalogue
  `lov2`. Nouvelle exécution via le runner réel également réussie.
- DILA : 298 métadonnées uniques, 0 nouvelle au second passage ; 15 en
  quarantaine, notamment `uin_dat_mar` en l'an 8887. Ne pas remplacer ce champ
  erroné arbitrairement pour prétendre avoir validé leur PIT.

Preuve des seconds passages :
`artifacts/fr/operations/validation_15c/second_pass.json` ; runs AMF/DILA
dans `artifacts/fr/operations/runs/`. Tests offline : correction, doublons,
quarantaine, schéma, host autorisé, compteurs après échec et isolation FR.
**132 tests ciblés FR/US/CN/Batch/sauvegardes passent** ; ce n'est pas la
suite complète de l'application. Aucune migration SQL n'a été nécessaire.

## Utilisation

Workflow & Orchestration → Batch → France — recherche uniquement : installer
les familles activées souhaitées, puis lancer immédiatement. Ne pas réinstaller
les tâches US/CN. Les commandes affichées utilisent le launcher/notificateur.
Pour une exécution directe (sans email/Telegram) :

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_corporate_actions_sync
python -u -m service.fr.operational_batch_15a --batch fr_amf_short_sync
python -u -m service.fr.operational_batch_15a --batch fr_dila_disclosures_sync
python -u -m service.fr.operational_batch_15a --batch fr_pit_quality_daily
```

Barres/actions complètes : lancements à faire avant le contrôle de qualité.
Aucun run complet 294 titres EODHD/actions n'a été lancé dans cette tranche.

## Ce qui reste bloqué et comment reprendre

| Famille | Motif réel | Travail nécessaire |
|---|---|---|
| fr_security_master_sync | Rejeu historique ESMA ≠ mise à jour quotidienne ; aucun handler quotidien installé | Collecte deltas, continuité/parties complètes, réconciliation Full, normalisation d'identités/intervalles avec corrections ; ne pas lever sur simple disponibilité du ZIP |
| fr_fundamentals_sync | Collecte active en quarantaine depuis 15-F ; utilisation bloquée | Extension 330 S6C : 254 retenues, 76 exclues ; lots/reprise. Qualifier unités/exercices/versions/PIT avant promotion. Voir inpi_univers_collecte_securisee.md |
| fr_consensus_borrow_options | Aucune source qualifiée | Identifier fournisseur, coût/droits, couverture et contrat ; pas substitution indicative silencieuse |
| fr_db_backup | Handler présent et mysqldump trouvé, restauration non prouvée | Dump réel puis restauration dans base de contrôle distincte ; vérifier tables/index/routines/triggers avant activation |
| fr_artifacts_backup | Handler présent, restauration/extraction non prouvée | Archiver les ~61,15 Go mesurés (14 419 fichiers avant nouveaux runs), contrôler espace/volume et extraction avec hashes ; pas prétendre que des tests unitaires remplacent ce contrôle lourd |

Le Sprint 15 complet n'est pas terminé : semaine d'exploitation, notifications
réelles, référentiel quotidien, publication staging SQL et restauration restent
à qualifier. Aucun abonnement supplémentaire souscrit et aucun modèle entraîné.
