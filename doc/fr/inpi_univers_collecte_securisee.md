# INPI — Extension à l'univers FR et collecte en quarantaine

## État au 5 octobre 2026

**Mise à jour du 6 octobre : suspension de prudence**, `enabled: false`,
`BLOCKED_INPI_RETENTION`. L'accès API aux comptes publics est autorisé ; le
blocage concerne la gestion des retraits ultérieurs, des archives et des backups.
Qualifier et tester ce traitement avant réactivation. Voir
[audit des droits](audit_autorisations_collectes_20261006.md).

L'univers étudié est celui des **330 identités locales S6C**, pas tous les titres
Euronext et pas les 1 152 références brutes EODHD. Titres actifs et anciennes
identités présentes dans ce référentiel sont examinés ; cela ne les rend pas
négociables aujourd'hui. Aucun référentiel source n'a été modifié.

Recherche terminée : **254 correspondances retenues, 76 exclusions, zéro titre
en attente**. « Retenue » signifie admissible à une collecte brute selon le
contrat ci-dessous, pas comptes valides ni feature directionnelle démontrée.
Les dix correspondances du pilote ne sont pas automatiquement conservées si
une vérification actuelle introduit une réserve (exemple : LEI non actualisé).

Preuves et résultats :

- `artifacts/fr/operations/fr_fundamentals_sync/mapping/mapping_report.json` :
  chaque titre, statut, motif, preuve et hash, compteurs complets.
- `mapping/verified_manifest.json` : uniquement les correspondances retenues.
- `mapping/history/` : rapport précédent conservé lors d'une nouvelle recherche
  ou réévaluation ciblée ; ne pas le supprimer pour « nettoyer » les réserves.

## Vérifier ISIN → personne morale → SIREN

La [GLEIF](https://www.gleif.org/fr/lei-data/gleif-api/) fournit les relations
ISIN/LEI et les références d'enregistrement de la personne morale. La recherche
utilise `lei-records?filter[isin]=...`, puis vérifie **explicitement** la présence
de l'ISIN dans la relation inverse `/lei-records/<LEI>/isins`. Ce deuxième contrôle
évite de faire confiance à un filtre serveur sans preuve de correspondance.

Les conditions sont toutes nécessaires :

1. Identité locale `VERIFIED_RESEARCH`, paire symbole/ISIN unique.
2. Une seule entité LEI retrouvée pour l'ISIN, réponse non tronquée.
3. Personne morale de juridiction française, catégorie GENERAL, état ACTIVE.
4. LEI actuellement ISSUED, validation FULLY_CORROBORATED.
5. Registre explicitement qualifié :
   [RA000189 — SIRENE](https://api.gleif.org/api/v1/registration-authorities/RA000189),
   ou [RA000192 — RCS](https://api.gleif.org/api/v1/registration-authorities/RA000192).
6. Numéro enregistré et numéro validé identiques, neuf chiffres et clé de
   contrôle SIREN valide. La seule conversion de format autorisée enlève les
   espaces de la forme `xxx xxx xxx` ; aucune extraction dans une chaîne libre.
7. Présence de l'ISIN dans la relation inverse du LEI.
8. Pas de contradiction avec les preuves légales primaires du pilote lorsqu'elles
   existent. Les dénominations INPI doivent ensuite correspondre aux noms légaux
   ou alias explicites du manifeste ; aucune similarité floue n'est admise.

Des sociétés majeures comme Vinci étaient initialement exclues par une règle
limitée à SIRENE. Après vérification du registre officiel RA000192 et du format
SIREN du RCS, la règle a été étendue et les 19 cas concernés ont été réexaminés.
Le résultat final de 254/330 inclut cette correction documentée, pas une
acceptation arbitraire d'un autre registre.

La vérification est **actuelle**, observée le 5 octobre 2026. Ce n'est pas une
preuve de propriété juridique de l'ISIN ou de disponibilité du compte à une
date historique. La collecte refuse un mapping de plus de 30 jours ou futur.

## Les 76 exclusions

| Motif technique | Nombre | Pourquoi / comment qualifier ultérieurement |
| --- | ---: | --- |
| LEI_NOT_CURRENTLY_ISSUED | 42 | LEI non actualisé selon le contrat strict ; pas preuve que la société a disparu. Revue d'une source légale actuelle possible, pas acceptation automatique. |
| NON_FR_LEGAL_ENTITY | 20 | Société cotée à Paris mais personne morale étrangère ; ne pas attribuer les comptes d'une filiale française au groupe coté. |
| NO_GLEIF_ISIN_MATCH | 9 | Pas de relation trouvée ; rechercher une preuve explicite émetteur/ISIN/SIREN. Ne pas chercher le « nom le plus ressemblant ». |
| ISIN_NOT_FOUND_IN_REVERSE_RELATION | 3 | L'ISIN n'a pas été confirmé dans la relation inverse examinée ; revue indépendante nécessaire. Budget maximum cinq pages de 100 relations. |
| INVALID_SIREN_CHECKSUM | 1 | Numéro incohérent ; vérifier le registre ou une pièce légale. |
| NON_GENERAL_ENTITY_OR_BRANCH | 1 | Catégorie incompatible avec l'entité juridique attendue ; ne pas substituer une succursale ou un véhicule. |

Les motifs restent visibles titre par titre dans **Workflow & Orchestration →
Batch → France → fr_fundamentals_sync**. L'encadré indique les nombres vérifiés,
exclus et en attente. Une exclusion technique conservatrice peut être un faux
négatif ; elle ne constitue pas un diagnostic financier sur l'émetteur.

## Ce qui est collecté et ce qui ne l'est pas

`service/inpi/universe_collection.py` reprend les références de `/bilans-saisis`
par pages de dix, puis récupère **tous les comptes structurés publics accessibles
de cette liste**, et non seulement les quatre comptes récents du pilote.
La réception ne normalise pas les champs comptables et ne certifie aucun layout.
Les PDF de `/bilans` ne sont pas téléchargés par cette extension.

Avant archivage : identité externe/interne cohérente, ID identique à celui
demandé, document non retiré et public, confidentialité interne publique,
dénomination rapprochée. Un document refusé est consigné avec motif et la
collecte continue sur les autres références. La page Batch affiche aussi
**Comptes exclus pendant la collecte — motifs**. Des anciens noms juridiques
non rapprochés ne sont pas ajoutés automatiquement aux alias.

Un document accepté est archivé intégralement comme JSON public dans
`quarantine/objects/<SHA256>.json`. Toutes les observations sont marquées :

```yaml
qualification_state: QUARANTINED_UNQUALIFIED
ml_usable: false
canonical_go: false
historical_pit_qualified: false
```

Les modèles, backtests et le live ne lisent pas ce stockage. Aucun SQL, table
de fondamentaux, migration, nouveau modèle ou entraînement n'est effectué.
Les archives entrent dans le périmètre `artifacts/fr` du backup FR existant.
Les secrets, profils de connexion et tokens ne sont jamais archivés.

## Lots, quotas et reprise

Paramètres dans `batch_fr.yaml` :

| Paramètre | Valeur | Garantie réelle |
| --- | ---: | --- |
| max_issuers_per_run | 25 | Au plus 25 correspondances à examiner par passage |
| max_requests_per_run | 500 | Plafond réseau incluant le login |
| max_requests_per_day | 5 000 | Réservations persistantes par jour UTC pour ce collecteur ; augmenté sur GO du 05/10/2026, sans effacer les 2 000 appels déjà réservés |
| request_interval_seconds | 0,25 | Pause minimale avant chaque requête INPI |
| max_archive_bytes_per_run | 134 217 728 | Maximum 128 Mio de JSON accepté par passage |
| refresh_days | 7 | Une correspondance terminée n'est rescannée qu'après sept jours |

La documentation INPI septembre 2026, page 43, indique 10 000 appels API/IHM
et 10 000 Mo par jour/utilisateur, avec HTTP 429 si dépassement :
[document officiel](https://www.inpi.fr/sites/default/files/2026-09/documentation%20technique%20API_comptes_annuels%20v6-1-AA.pdf).
Notre plafond de 5 000 garde une marge ; il ne mesure pas les scripts externes utilisant la même
clé ni les usages IHM INPI. La documentation ne précise pas l'heure de
réinitialisation INPI : minuit UTC est uniquement notre convention locale.
Éviter les appels concurrents hors de ce collecteur. HTTP 429 interrompt
le passage ; il ne déclenche pas une boucle de retries immédiats.

Le fichier `request_quota.json` réserve une requête **avant l'envoi** : une
requête en erreur compte aussi. Ne pas supprimer/réinitialiser ce fichier pour
contourner le quota. `collection_state.json` conserve, par ISIN/SIREN, curseur,
références reçues, IDs terminés, comptes exclus, erreur et fin de traitement.
Un verrou `.lock` empêche les passages simultanés. Ne pas le supprimer sans
vérifier qu'aucun processus de collecte n'est en cours.

Les manifests d'observation et checkpoints sont écrits après chaque page et
document. Des reprises bornées protègent les remplacements atomiques contre
les verrous transitoires Windows. Si le quota interrompt un passage, le prochain
reprend la page ou le document restant. Les objets identiques sont vérifiés par
hash et réutilisés ; des contenus différents sont conservés comme versions.
Un crash entre archive et checkpoint peut répéter une observation, pas dupliquer
l'objet documentaire. Une corruption d'objet existant est bloquante.

Un passage avec pause budgétaire peut être techniquement réussi **sans que la
couverture soit complète**. Lire `pause_reason`, `pending_issuers`,
`coverage_complete`, et pas seulement SUCCESS. `requested` compte les
correspondances sélectionnées ; `received/persisted` compte les observations
publiques acceptées, pas les seuls objets nouveaux. `new_objects_count` distingue
les nouveaux fichiers. Les échecs réseau gardent les checkpoints et sont notifiés
comme échecs via le wrapper commun ; les documents exclus sont des réserves
distinctes, pas des données utilisables cachées.

Les correspondances jamais terminées ou encore en reprise sont **prioritaires**
sur les rescans arrivés à échéance. Cela évite qu'un univers de plus de sept
lots reste perpétuellement partiellement couvert à cause du rafraîchissement
hebdomadaire des premières sociétés de la liste.

## Exploitation

Le batch reste actif à **20 h Europe/Paris, lundi–vendredi**. Il utilise le même
nom et le même wrapper mail/Telegram : aucune tâche Windows existante n'a été
installée, arrêtée ou modifiée par cette extension. Les passages suivants
prendront automatiquement le nouveau manifeste. Installer/réinstaller depuis
la page Batch si la tâche n'existe pas encore.

Recherche/reprise des correspondances (les résultats déjà examinés sont conservés) :

```powershell
python -u -m service.inpi.universe_mapping --max-requests 1200
```

Renouvellement des preuves actuelles, **avant expiration de 30 jours**, avec
conservation du précédent rapport :

```powershell
python -u -m service.inpi.universe_mapping --refresh --max-requests 1200
```

Puis reprendre la même commande sans `--refresh` si le budget n'a pas permis
de terminer ; `--refresh` à chaque relance recommencerait la recherche.
La recherche GLEIF est distincte du quota INPI et n'appelle pas l'API INPI.
Elle est bornée à 1 200 appels, sans authentification, avec pagination inverse
limitée. Les erreurs temporaires restent en attente plutôt que devenant des
correspondances validées.

Collecte manuelle d'un lot et reprise automatique au prochain passage :

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_fundamentals_sync
```

Python direct ne déclenche pas mail/Telegram : utiliser le bouton IHM/launcher
FR pour bénéficier des notifications. Ne pas relancer pendant qu'un lot tourne.

Rattrapage initial borné (au maximum quatre lots, arrêt si quota/erreur), sans
changer les tâches Windows :

```powershell
python -u -m service.inpi.universe_catchup --max-passes 4
Get-Content artifacts/fr/operations/fr_fundamentals_sync/catchup_progress.json -Raw
```

Un tel rattrapage a été lancé le 05/10/2026. Le fichier de progression résume
chaque lot terminé ; `collection_state.json` progresse document par document
pendant un lot. Les deux ne doivent pas être confondus. À PAUSED_QUOTA, reprendre
après renouvellement de l'allocation UTC, pas en effaçant le ledger. À
PASS_BUDGET_REACHED, les checkpoints restent valides pour un autre passage.

Suivi léger :

```powershell
Get-Content artifacts/fr/operations/fr_fundamentals_sync/mapping/mapping_report.json -Raw
Get-Content artifacts/fr/operations/fr_fundamentals_sync/request_quota.json -Raw
Get-Content artifacts/fr/operations/fr_fundamentals_sync/collection_state.json -Raw
```

Les derniers rapports synthétiques sont sous
`artifacts/fr/operations/runs/fr_fundamentals_sync/`. La page Batch présente aussi
les comptes exclus et le nombre de correspondances examinées.

## Qualification ultérieure

### Conservation renforcée à partir du 6 octobre 2026

Les comptes publics acceptés restent archivés en JSON complet (réponse décodée,
pas octets/headers HTTP), par SHA256. Les nouvelles observations détaillent
`archive_version=inpi-structured-v2`, endpoint, début de requête et réception UTC.
Les unités et exercices restent explicitement non qualifiés. Ni identifiants,
ni mots de passe, ni tokens ou réponse de login ne sont archivés.

Chaque nouveau passage étendu conserve dans son dossier `observations/<run>/`
une copie du manifeste d'identité et du rapport de mapping utilisé. Les pages
de références sont conservées dans `reference_pages/<ISIN-SIREN>/` avec les
horodatages, curseurs et métadonnées id/SIREN/nom/clôture/dépôt/type/publicité/
retrait/mise à jour. Les corps confidentiels ou retirés ne sont pas ajoutés.
`issuer_reviews/` conserve les références examinées et exclusions à la fin
d'un émetteur, même quand le checkpoint courant sera remplacé au rafraîchissement.
Une reprise sans nouvelle page conserve les pages du passage précédent.

Les refus de nom ne sont pas automatiquement acceptés : les motifs et références
permettent la revue, mais le corps refusé n'est pas promu dans les comptes acceptés.
Le mécanisme de retrait de copies précédemment publiques reste à qualifier avant
redistribution/promotion. Aucun PDF, annexe ou nouvelle famille INPI n'est collecté
par ce renforcement. Aucun historique ancien n'est certifié PIT rétroactivement.

Les nouvelles preuves et les comptes sont sous `artifacts/fr`, déjà inclus dans
`fr_artifacts_backup`. Test de restauration des chemins de quarantaine ajouté ;
pas de sauvegarde lourde ni de nouvelle collecte lancée ici. Les anciens fichiers
ne reçoivent pas de faux horodatages ou de preuves reconstruits à partir du présent.

Collecter davantage ne corrige pas les incohérences comptables du pilote.
Unité, période, consolidation, rubrique, révisions et disponibilité PIT doivent
être rapprochées des publications avant tout usage. Les nouveaux snapshots
observés aujourd'hui ne deviennent jamais des vintages historiques au simple
motif que la date de clôture est ancienne. Retracts/versions/licence sont à
qualifier avant promotion. L'extension ne démontre aucun gain D1/D10.

## Vérifications réelles et tests

Le premier lot étendu a archivé 313 comptes avant un arrêt Windows temporaire
sur le remplacement du ledger ; ces objets ont été conservés. Après ajout de
retries atomiques bornés et distinction entre document exclu et erreur réseau,
la reprise a archivé 253 autres comptes, zéro échec, avec 58 exclusions de
documents motivées. À cette étape : 45 correspondances examinées, 566 comptes
acceptés, 209 correspondances restant à traiter. Ce n'est pas une couverture
complète de l'univers. Le rattrapage lancé ensuite fait progresser ces nombres.

**82 tests ciblés passants** : checksum/autorités, relation inverse, ambiguïtés,
identités/publicité, refus de promotion, plafonds, reprise de file documentaire,
idempotence, verrous Windows, priorité des correspondances non terminées,
runner/catalogue FR et collecteurs FR existants. Les tests utilisent des fixtures
et ne consomment pas de quota réseau.
