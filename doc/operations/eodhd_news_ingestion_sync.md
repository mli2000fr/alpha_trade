# Ingestion quotidienne des news US EODHD — 16 octobre 2026

Mise à jour du 17 octobre : la résilience de **l'étape 8 Sentiment Pipeline**
est décrite dans [le contrat de reprise](sentiment_pipeline_reprise_20261017.md).
Cette étape utilise `eodhd_news`, distinct du namespace `eodhd_news_daily` de ce
batch ; aucune fusion de checkpoints ni modification de sa planification.

## Dernier bilan vérifié — cycle complet terminé

Run `eodhd_news_ingestion_sync-20261016121131-5ed4d540` terminé OK à **14h59 Paris**,
durée 48 min 18 s : 1 005 titres terminés et 785 déjà terminés ignorés, zéro
échec/restant, 3 568 versions brutes nouvelles. SQL et launcher finalisés,
notifications email/Telegram OK. Audit READ ONLY : **1 790 checkpoints du cycle
réussis**, compteurs concordants et zéro défaut d'intégrité détecté dans les
mappings de ce passage. Validation de collecte seulement, pas du signal.
La tâche manuelle est terminée et sans déclencheur ; tâche quotidienne inchangée.
[Revue bornée, couverture intraday et limites PIT](../ml/news_financement_validation_revue_20261016.md).

## Reprise manuelle du 16 octobre à 14h11 Paris

Sur demande utilisateur, le run `eodhd_news_ingestion_sync-20261016104812-15a4f23c`
a été clôturé administrativement FAILED après constat d'absence du processus.
La dernière progression durable datait de 12h52 : 70 terminés, 713 ignorés,
1 007 non parcourus, 192 versions nouvelles, zéro échec de titre connu.
Les compteurs ont été rétablis dans `pit_collection_runs`, avec
`termination_kind=ORPHAN_RECONCILED`, empreinte du fichier de progression et
heure d'interruption réelle explicitement inconnue. La date `finished_at`
est la date de clôture administrative, pas une heure de sortie reconstituée.
Les fichiers historiques et les archives news n'ont pas été réécrits.

Nouveau run : `eodhd_news_ingestion_sync-20261016121131-5ed4d540`.
Départ via `AlphaTrade-EodhdNewsIngestionSync-ManualRecovery`, tâche Windows
**sans déclencheur**, même principal Interactive que la tâche quotidienne,
action PowerShell masquée et launcher standard avec `-Force`. Ce lancement
est indépendant de la commande de l'assistant ; il requiert toujours un PC
allumé et une session ouverte. Sa limite Windows est de trois heures ; le
budget applicatif de 120 min reste inchangé. Pas de reprise périodique ajoutée,
pas de changement de la tâche quotidienne 20h30. Le lancement ne certifie pas
la fin du run : consulter sa progression puis sa clôture SQL/launcher.
La tâche manuelle pourra être retirée après sa fin, sans toucher au catalogue
quotidien ni aux données.

## Correctif erreurs et reprises — 16 octobre, matin

Les relances de 06h57 et 07h01 ont retrouvé le timeout de G.US. L'ancien
transport comptait chaque retry comme une panne globale et classait ensuite
GABC/GAIN en échec sans les interroger. Le dernier de ces runs reste FAILED ;
les anciens rapports et checkpoints ne sont pas réécrits.

- `http_timeout_seconds: 30`, `http_max_attempts: 3` : paramètres YAML,
  appliqués à chaque page HTTP ; plafond de 25 tentatives/titre inchangé.
- Un timeout isolé, après retries, laisse le titre incomplet et permet de
  passer au suivant. Il ne devient ni un symbole invalide ni une absence de news.
  Le run reste FAILED s'il conserve un titre incomplet.
- Les retries réseau d'un même titre ne déclenchent plus à eux seuls le
  circuit global du quota ; toutes les tentatives restent comptabilisées.
  Le circuit HTTP est distinct par titre ; les erreurs HTTP serveur restent
  soumises au circuit global existant.
- Trois titres incomplets consécutifs arrêtent le passage et enregistrent une
  pause de `failure_cooldown_seconds: 1800`. `cooldown.json`, sous le dossier
  opérationnel du batch, est relu au démarrage et avant tout appel. Une pause
  du circuit global rencontrée avant HTTP est également conservée jusqu'à
  son échéance UTC. Ne pas supprimer ce fichier pour contourner la protection.
- Une relance pendant cette pause ne fait pas d'appel. Les titres non
  interrogés restent **pending**, pas artificiellement FAILED chacun. Une
  page déjà tentée avant l'arrêt laisse son titre incomplet. Le runner SQL et
  le résumé de notification préservent ces compteurs : un run FAILED peut
  avoir zéro titre en échec, avec un motif global et tous les titres en attente.
  Une exception non structurée garde un compteur d'erreur technique de 1.
- Après échéance, une nouvelle exécution est autorisée ; pas de relance
  automatique ajoutée. Checkpoints du cycle, reprise offset zéro des
  incomplets, archives et heures réelles de disponibilité inchangés.
- TLS, 401/403/429, redirections et limites de durée/quota restent bloquants.

Validation : **406 tests ciblés passent**, dont le vrai chemin de retry avec
transport simulé : AAA expire trois fois, BBB et CCC réussissent, puis reprise
du seul AAA. Test de pause persistante entre deux instances, expiration,
compteurs SQL/CLI, déduplication et archives inclus.

Contrôle réseau réel borné : deux GET `/news`, G puis GABC, chacun limité à
une tentative de 30 s, comptabilisés dans le budget local ; **tous deux en
ReadTimeout**. Aucun résultat/article ni écriture SQL, aucune collecte complète
relancée. Cela démontre que la réponse réseau n'est pas rétablie à cette heure,
pas une panne générale certaine d'EODHD, un refus d'abonnement ou un quota épuisé.
Le correctif applicatif ne promet pas de supprimer une indisponibilité réseau.

## État livré et planification

**`eodhd_news_ingestion_sync`** est activé dans `batch.yaml`, visible dans
Workflow & Orchestration → Batch → US, priorité P1. La tâche Windows
`AlphaTrade-EodhdNewsIngestionSync` a été installée séparément le 16 octobre,
avec lanceur masqué, mode Interactive et contrôle horaire commun.

- **20h30 Europe/Paris, tous les jours**, week-end compris ; news possibles
  hors des séances. Respect de l'absence PC 7h30–20h.
- Univers depuis le 18 octobre : `config/univers_batch/stock_bars_daily.txt`,
  **13 105 titres** dans cet export fixe. Il est relu à chaque lancement, sans
  actualisation SQL automatique. Le workflow US garde son fichier tradable.
  Les anciens bilans de 1 790 titres restent des constats de l'ancien périmètre.
- Durée (120 minutes) et budgets (4 000 tentatives HTTP par passage/jour) inchangés :
  **un passage ne peut pas couvrir les 13 105 titres avec ces plafonds**.
  Une collecte arrêtée sur limite reste incomplète et conserve ses checkpoints ;
  l'univers élargi ne vaut pas promesse de couverture quotidienne intégrale.
- Aucun changement de l'horaire de `us_pipeline` (23h05), de ses étapes
  lundi–jeudi `[1,2,3,4,5,6,7,9]` ou vendredi `[1,2,3,4,5,6,7,8,9]`.
- **Ingestion seulement : pas de FinBERT, GPT/DeepSeek, features, modèle ou ordre.**
  Le traitement sentiment complet reste sélectionné le vendredi. Les scores ne
  sont donc pas promis à jour quotidiennement par ce nouveau batch.
- Notifications mail/Telegram et résumé de run via le launcher Forward PIT
  commun. Le test limité direct n'a pas envoyé de notification artificielle.

La tâche requiert une session Windows ouverte et un PC allumé. Son installation
ne prouve pas que la première collecte planifiée de tout l'univers a terminé.
Les déclencheurs Windows sont horaires à `:30` ; le launcher n'exécute la
collecte qu'au créneau YAML 20h30, hors lancement manuel explicite.

## Connexion HTTPS corrigée

`NewsIngestionService` utilise maintenant, pour EODHD, la session existante
`common.verified_http.verified_session`. Le client news autonome utilise aussi
cette session lorsqu'aucune session n'est fournie. Alpaca/Finnhub ne changent pas.

Le contexte combine Certifi et les racines Windows ; vérification du certificat
et du nom d'hôte conservée. Pas de `verify=False`, de modification globale de
Requests, de racine installée ou de contournement d'authentification.
Les sessions explicitement fournies par un appelant restent sous sa responsabilité.

Autres corrections bornées :

- une page vidée par le filtre UTC exact, mais avec une page suivante, n'arrête
  plus prématurément l'ingestion ;
- un objet JSON d'erreur inattendu n'est plus présenté comme une liste vide ;
- les erreurs stockées dans les checkpoints et remontées par le client masquent
  les paramètres d'authentification. Aucun token dans le rapport ou les logs.

## Fenêtre, reprise et limites

Relecture des publications **J−7/J**, end UTC figé au début du run. Ce n'est
pas une reconstruction de leur heure de réception passée. L'observation et la
disponibilité restent les vraies heures de collecte/commit.

Checkpoints isolés dans `news_ingestion_checkpoint.source_name=eodhd_news_daily`,
pas `eodhd_news`. Les watermarks de l'étape hebdomadaire ne sont pas avancés.
Le stage `news_ingested_at` est marqué uniquement après le succès complet du
titre et l'archivage. Aucun stage de scoring/agrégation n'est marqué.

Un **cycle** démarre au dernier créneau 20h30 Paris : un lancement à 00h30
appartient encore au cycle précédent, et ne bloque pas celui du soir suivant.
Le calcul respecte les changements d'heure Europe/Paris.

- Titre réussi dans ce cycle → SKIP, sans nouvelle requête.
- Titre incomplet → reprendre **depuis offset zéro**, car la liste fournisseur
  bouge et un ancien offset ne garantit pas de ne rien manquer.
- Versions identiques dédupliquées par le writer d'archive ; les changements
  réels ou de contexte de mapping sont conservés, sans écrasement d'historique.

Paramètres YAML : page 100, intervalle minimal 0,25 s, **4 000 tentatives HTTP
par run et par jour UTC**, 25 par titre, 120 min et arrêt après trois titres en
échec consécutifs. Timeout 30 s et trois tentatives au maximum par page ; pause
persistante 30 min après trois titres incomplets consécutifs. Les tentatives
de retry sont comptées aussi, avant réseau.
Compteur journalier local durable et verrou OS de batch ; suivi EODHD global à
coût conservateur de cinq unités par tentative. Le compteur global existant
n'est pas un relevé officiel de facturation ni une garantie de synchronisation
de toutes les autres applications utilisant la clé.

Au prochain appel après 120 min : arrêt avec compteurs et titres restants ;
une requête/transaction déjà en cours peut finir après. C'est un budget
d'exploitation, pas une garantie de durée absolue. Le plafond est compatible
avec la nuit, sans promettre la couverture tant que le run complet n'est pas observé.

HTTP 401/403/429, redirection ou erreur TLS → arrêt global sans poursuite
aveugle. Budget, schéma invalide, SQL ou pagination incomplète ne deviennent
jamais une absence normale de news. Les échecs de titre isolables laissent les
autres avancer ; le run reste FAILED s'il subsiste un titre en échec.

## Tables, compteurs et archives

Aucune nouvelle table : même normalisateur/writer atomique et reçus scellés
après commit que les collectes précédentes.

| Table | Usage |
| --- | --- |
| `news_raw`, `news_ticker_map` | Projection courante et associations fournisseur |
| `news_raw_versions` | Versions immuables des textes et payloads |
| `news_ticker_map_versions` | Versions des associations et contexte de collecte |
| `news_archive_observations` | Réception réelle et disponibilité confirmée |
| `news_ingestion_checkpoint` | Progression quotidienne, namespace distinct |
| `pit_collection_runs` | Résumé du batch via runner standard, pas du smoke direct |

Pas d'écriture dans `pit_raw_payloads` : les payloads news sont déjà archivés
dans la famille news. Pas d'écriture dans les tables de sentiment/LLM, modèles,
prix ou FR/CN. Les sauvegardes existantes de la base s'appliquent à ces tables.

- **Demandés** : titres du périmètre.
- **Reçus** : occurrences d'articles, pouvant être associées à plusieurs requêtes.
- **Persistés** : nouvelles versions brutes après archivage confirmé, pas tous
  les articles réobservés ni le nombre d'upserts.
- **Échecs** : titres incomplets ; titres pas encore tentés détaillés à part.
- **Alertes** : avertissements explicites. Zéro news pour un titre n'est pas une alerte.

Les détails exposent aussi upserts soumis, mappings, versions/reçus ajoutés,
titres terminés/ignorés/restants, appels et erreurs. Un échec après plusieurs
pages conserve les compteurs des pages déjà archivées.

Rapports et progression :
`artifacts/operations/eodhd_news_ingestion_sync/<run_id>/progress.json` et
`report.json` ; journal planifié `log/batch/eodhd_news_ingestion_sync.txt`.

## Preuve réelle bornée et tests

Premier smoke : **CSCO, IRTC, WHD**, trois appels réels, 48 occurrences reçues,
46 articles soumis après filtres, **18 nouvelles versions brutes**, 46 versions
de mapping et 64 nouveaux reçus. Zéro échec, zéro GPT, zéro sentiment calculé.

- Premier passage : `smoke-20261015T223032-0ef19c89/progress.json`.
- Reprise : `smoke-20261015T223226-f431464d/report.json`, trois titres ignorés,
  **zéro appel, reçu, version ou upsert nouveau**.
- Contrôle SQL après smoke : 73 versions brutes, 101 mappings versionnés,
  174 observations au total ; **zéro reçu non scellé**. Trois checkpoints
  quotidiens en succès. Cela ne certifie pas tout l'univers ni l'identité
  économique des articles.

Le premier smoke précédait l'ajout du fichier final `report.json` et la précision
du cycle ; sa preuve `progress.json` est conservée sans réécriture. Le second
valide la reprise avec le contrat de cycle final.

**350 tests ciblés passent**, incluant quota/retries, TLS, pagination, archive,
compteurs, reprise minuit/DST, catalogue, notifications, planning et consensus FR.
Trois incohérences anciennes des tests de catalogue/planning (nouvelles sections
EODHD et horaire pipeline déjà passé à 23h05) ont été constatées avant l'ajout,
puis les attentes ont été alignées sur les configurations existantes, sans
changer ces horaires ou les collecteurs correspondants.

```powershell
python -u -m service.forward_pit.batch --batch eodhd_news_ingestion_sync --dry-run
python -u -m service.eodhd.news_ingestion_daily --smoke --symbols IRTC,WHD,CSCO
```

Le smoke écrit réellement les news/checkpoints de ces trois titres mais ne crée
pas un succès de batch complet dans `pit_collection_runs` et ne déplace jamais
les checkpoints hebdomadaires. Un run manuel complet doit passer par la carte
Batch/launcher pour conserver les notifications.

## Limite de recherche toujours ouverte

Historique du 16 octobre : [échecs initiaux, reprises et contrôles intermédiaires](../ml/news_financement_premier_passage_20261016.md).
Dernier état validé : [cycle complet et revue bornée](../ml/news_financement_validation_revue_20261016.md).
Le premier run de 00h38 a échoué ; le succès du cycle vient de la reprise
finale clôturée à 14h59, pas d'une réécriture de cet ancien échec.

Cette livraison répare l'alimentation, pas D1/D10. Les liens fournisseur ne
certifient pas l'émetteur de l'événement. Nouveauté, identité, doublons de
communiqués et heures doivent encore être qualifiés. Les événements détectés
ne sont ni des signaux LONG/SHORT ni des probabilités de TP avant SL.
La prochaine borne est la revue des nouvelles annonces et leur couverture
intraday ; pas de nouvel entraînement automatique.
