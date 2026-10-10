# Consensus FR — collecte prospective en quarantaine et promotion future

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Autorisation et périmètre courant

**Mise à jour du 6 octobre 2026 : batch suspendu**, `enabled: false`,
`BLOCKED_YAHOO_AUTOMATED_ACCESS`. L'autorisation utilisateur du pilote ne prouve
pas une permission de Yahoo pour la collecte automatisée. Obtenir cette permission
ou une source licenciée avant réactivation. Voir [audit des droits](audit_autorisations_collectes_20261006.md).
Les mentions d'activation ci-dessous décrivent l'état historique du 5 octobre.

Autorisation du 5 octobre 2026 : collecte de recherche sur tout le référentiel
actif, pas activation du ML, des backtests ou du live. Section
`fr_consensus_snapshot` dans `batch_fr.yaml` : `enabled: true`, `ACTIVE_RESEARCH`.
La réserve groupée reste remplacée ; borrow/options restent bloqués.
Le suivi Codex ponctuel `deuxi-me-observation-consensus-fr` est mis en pause.

Référentiel S6C figé : 330 identités, **294 actives**, 36 non actives exclues.
Les trois marchés Paris XPAR, ALXP (Growth), XMLI (Access) sont pris en compte.
Ce n'est pas une découverte quotidienne de tous les titres Euronext, ni une
preuve de négociabilité historique. Les radiés ne sont pas interrogés sur un
consensus actuel supposé représenter leur passé.

## Identités et couverture

Contrôle local : ISIN de forme/checksum valides, alias/symbole unique, identité
VERIFIED_RESEARCH active, nom présent dans une version ESMA courante du
référentiel. Contrôle Yahoo : même symbole, EQUITY, EUR et PAR/EPA ; au moins
un nom court/long concorde exactement avec un nom local après normalisation
des accents/ponctuation/suffixes juridiques. Pas de rapprochement flou.

Une concordance de nom ne certifie pas indépendamment un ISIN Yahoo, champ
non fourni ici. Les trois revues manuelles du pilote sont conservées tant
que fraîches ; leur expiration revient au contrôle de nom, sans qualification
manuelle automatique. Tous les snapshots conservent `ml_eligible=false`.

Chaque candidat est examiné. Ambiguïtés/contradictions : EXCLUDED_IDENTITY,
absence de consensus : NO_COVERAGE, erreurs techniques : FAILED et reprise.
Un échec réseau n'est jamais remplacé par zéro. Une table contenant seulement
currency=EUR, sans estimation moyenne numérique, n'est pas une couverture EPS.
Les métriques manquantes restent nulles ; famille présente ne signifie pas
que toutes les périodes de cette famille sont couvertes.

Source Yahoo via yfinance non officielle, recherche uniquement. Aucun quota
ou droit d'usage officiel Yahoo garanti par cette activation ; qualification
de licence obligatoire avant diffusion/production. Un signal D1/D10 n'est
pas démontré par la disponibilité du consensus.

## Exécution et reprise

Horaire : **20:00 Europe/Paris, lundi–vendredi**, après la clôture ordinaire
de Paris. Paramètres configurables : plafond 400 titres/run, intervalle
1,5 seconde, 2 400 appels logiques/jour, deux tentatives techniques/titre/jour.
Le compteur réserve avant chaque méthode Yahoo (info/EPS/revenus/tendance et
trois méthodes additionnelles configurables),
y compris en cas d'échec. Yfinance peut effectuer plusieurs requêtes physiques
par méthode : ce budget n'est pas un compteur HTTP ni un quota fournisseur.
TLS et vérification du nom restent actifs, autorités système/certifi incluses.

Service : `service/fr/consensus_daily.py`, dispatch depuis
`service/fr/consensus_snapshot.py`, runner
`service/fr/operational_batch_15a.py`. Le launcher FR commun applique horaire,
verrouillage, logs et notifications email/Telegram. L'installation depuis
la page Batch → France utilise uniquement la tâche `AlphaTrade-FrConsensusSnapshot`.
Le mode Interactive nécessite une session Windows ouverte ; PC éteint = pas
de collecte, pas reconstruction rétroactive d'une observation manquée.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_forward_pit_task.ps1 -BatchName fr_consensus_snapshot -BatchConfigPath F:\projets\batch_fr.yaml -LauncherPath F:\projets\scripts\windows\fr_operational_launcher_15a.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\windows\fr_operational_launcher_15a.ps1 -BatchName fr_consensus_snapshot -Force
```

Les observations sont persistées **titre par titre**, pas uniquement à la fin.
Répertoire `artifacts/fr/operations/fr_consensus_snapshot/` :

- `days/YYYY-MM-DD.json` : checkpoint Paris, compteurs, statuts et exclusions ;
- `daily_observations/YYYY-MM-DD/objects/` : objets de contenu par SHA256 ;
- `daily_observations/YYYY-MM-DD/observations/<symbole>/` : provenance UTC,
  available_at=observed_at, rattachement local et couverture ;
- rapports de runs : `artifacts/fr/operations/runs/fr_consensus_snapshot/` ;
- logs launcher : `log/batch_fr/fr_consensus_snapshot.txt`.

Relance le même jour : skip des succès, exclusions et absences déjà examinés ;
reprise des erreurs techniques. Jour suivant : nouveau vintage réellement
observé, compteur local neuf. Une pause 429/budget sauvegarde les compteurs et
signale l'incomplétude, sans répéter des requêtes en boucle. Au plus deux
tentatives d'erreurs ordinaires par titre/jour ; les pauses de budget ne
consomment pas une tentative achevée. Aucun verrou existant n'est supprimé.
Après crash entre archive et checkpoint, récupération de l'observation sans
doublon de snapshot. Vérification des objets hashés et chemins au rejeu.

« Tous examinés » ne signifie pas « tous couverts ». `coverage_ratio` mesure
les snapshots cumulés parmi les candidats ; `empty_count` les absences,
`excluded_identity_count` les contradictions, `pending_count` les non terminés.
Demandés = candidats éligibles du périmètre ; reçus/persistés = nouveaux
snapshots valides du passage, pas total cumulé. Les exclusions et compteurs
du jour sont visibles dans l'IHM, avec avertissement de quarantaine permanent.
Aucune nouvelle table ni SQL, aucun modèle ou profil ML modifié ici.

## Utiliser ces données en ML/backtest : étapes encore nécessaires

1. **Qualifier.** Identités indépendantes, devise/unités, EPS dilué/ajusté vs
   publié, exercice fiscal exact, données groupe/social. Les périodes Yahoo
   relatives 0y/+1y/0q/+1q ne suffisent pas à garantir un exercice constant :
   distinguer rollover, variation de couverture et vraie révision. Vérifier
   les droits d'usage avant production.
2. **Normaliser en staging FR versionné.** Contrat futur : ISIN, source,
   exercice/horizon, métrique, valeur, observed_at, available_at, hash et état
   de qualification. Conserver tous les vintages, ne pas écraser avec le dernier.
   Ce staging/promotion n'est pas créé par cette évolution.
3. **Créer les features PIT.** Exemples : variation EPS/revenus du même exercice
   entre deux observations réelles J-7/J-30, dispersion haut/bas, nombre
   d'analystes, révision de recommandation, objectif/cours disponible, âge du
   snapshot, indicateurs de manque. « 7daysAgo » reçu aujourd'hui ne prouve pas
   qu'on détenait cette donnée il y a sept jours. Ne pas comparer des unités
   ou des exercices différents comme une révision.
4. **Joindre à l'heure de décision.** Dernier snapshot qualifié avec
   `available_at <= decision_at`, fraîcheur maximale configurable, pas de
   jointure avec la dernière valeur actuelle. Observé à 20h Paris = inconnu à
   la clôture du même jour ; utilisable au plus tôt pour une décision ultérieure.
   Titres sans données : NA et politique d'abstention/manque déclarée, pas zéro.
5. **Tester OOF l'apport.** Labels D1/D10/rendement H20 calculés séparément après
   maturation ; splits temporels purgés tenant compte de H20. Prix seuls vs
   prix+consensus sur mêmes dates/titres, LONG/SHORT séparés, analyse couverture,
   stabilité et régimes. Ensuite seulement comparaison économique avec coûts.
6. **Promouvoir explicitement.** Après qualification et validation, raccorder
   chargeur de features, profils de modèles et backtest. Le collecteur actuel
   n'entraîne rien et ne raccorde aucun serving.

L'historique commence aux dates vraiment collectées : impossible d'utiliser
ces snapshots actuels dans un backtest 2019–2025 sans fuite temporelle.
H20 nécessite environ 20 séances futures pour ses labels, mais cela ne suffit
pas à valider un modèle ; il faut assez de révisions/périodes/régimes indépendants.
Cette activation sécurise la collecte, **pas une efficacité directionnelle**.

## Validation et premier démarrage réel

Tâche `AlphaTrade-FrConsensusSnapshot` installée le 05/10/2026, configuration
`batch_fr.yaml`, launcher FR, mode Interactive/invisible. Le premier passage
complet a démarré à 23:37 Paris (lancement manuel Force, après l'horaire du jour).
Logs dédiés : `log/batch_fr/consensus-universe-20261005/`. Un contrôle initial
a confirmé 26 snapshots archivés, aucune erreur technique/identité exclue
à cet instant, et un processus encore actif. Ce n'est pas le résultat final.

Suivre la progression dans la page Batch France ou le checkpoint
`artifacts/fr/operations/fr_consensus_snapshot/days/2026-10-05.json`.
Le launcher commun peut ne recopier les logs Python qu'à la fin ; un log
montrant seulement START ne suffit donc pas à conclure à un blocage.
Les notifications habituelles sont déclenchées en fin de passage.

53 tests ciblés passent : collecteur quotidien/pilote, comparaison datée,
catalogue FR, autres collectes FR et lecture du checkpoint IHM. Contrôles
de reprise même après archivage avant checkpoint, budget/rate-limit,
absence EPS, périmètres Paris et idempotence. Syntaxe des pages/services IHM
vérifiée ; aucun test ne prétend qualifier économiquement ces données.

## Archivage renforcé — 6 octobre 2026

Les nouvelles observations utilisent `fr-consensus-v2`. Les anciens fichiers
ne sont ni modifiés, ni complétés artificiellement avec une observation future.
La réponse complète **décodée par yfinance** de `get_info` est conservée dans
`raw_info`, en plus des champs normalisés existants : les métadonnées de devise,
de dates fiscales et tous les autres champs fournis restent consultables.
Ce n'est pas une capture des octets HTTP, de leurs headers ou du site HTML.
Les valeurs non finies sont normalisées en null ; ce traitement est explicite.

`archive_extra_methods` active `get_eps_revisions`, `get_recommendations` et
`get_upgrades_downgrades`. Avec info et les trois tableaux existants, sept
méthodes sont interrogées : 2 058 appels logiques pour 294 titres, avant reprises.
Elles utilisent le même compteur journalier et la même gestion de 429.
Absence/erreur d'une table : null et avertissement, jamais données inventées.
Ces champs ne certifient pas les dates de publication historiques annoncées
par Yahoo ; les valeurs `7daysAgo` ne constituent pas nos propres vintages PIT.

Chaque méthode a `started_at`, `received_at` ou `finished_at`, et un statut.
La version yfinance et la version du contrat d'archive sont enregistrées.
L'observation assemblée reste disponible seulement à sa réception finale.
Sous `daily_observations/<date>/endpoints/`, chaque réponse réussie
est aussi archivée immédiatement par hash avec sa référence titre et son heure.
Une pause ultérieure ne perd donc pas les réponses précédentes. Ces reçus
partiels ne sont pas des snapshots complets ni automatiquement des features.
Un échec de persistance reste bloquant ; les états d'erreur ne sont pas des succès.

`fiscal_period_state=UNQUALIFIED_PROVIDER_LABELS` et
`unit_state=UNQUALIFIED_PROVIDER_VALUES` empêchent de prétendre que les libellés
0y/+1y sont déjà raccordés à un exercice certain. Les métadonnées disponibles
permettent une revue ultérieure, mais ne garantissent pas que Yahoo expose
assez d'information pour lever toutes les ambiguïtés. Promotion toujours interdite.

La sauvegarde `fr_artifacts_backup` comprend toute la racine `artifacts/fr` :
objets, reçus, checkpoints, références et rapports sont donc inclus, contrairement
à un backup SQL seul ou à une sauvegarde limitée aux modèles. Vérification par
test d'archivage/extraction des deux quarantaines ; aucune nouvelle sauvegarde
de production n'est lancée dans cette évolution. La sauvegarde locale ne protège
pas contre la perte du disque : conserver une copie externe selon la politique choisie.

Les succès déjà enregistrés le même jour restent ignorés : aucun nouveau passage
ne transforme leurs anciennes observations en v2. Les prochains snapshots
emploieront le contrat renforcé. Aucun calendrier, modèle ni table SQL modifié.

Validation du renforcement : **77 tests ciblés passants** (consensus pilote/
quotidien/comparaison, INPI sécurisé/univers, sauvegarde/restauration et runner
FR), sans appel fournisseur. Le test de pause conserve la réponse info antérieure,
les méthodes ajoutées consomment le budget, les fichiers anciens restent lisibles.
