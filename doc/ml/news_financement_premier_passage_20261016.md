# Premier passage news complet et revue intermédiaire — 16 octobre 2026

## État final actualisé — succès du cycle et revue bornée remis

Les échecs et contrôles ci-dessous sont historiques, pas le dernier statut.
Le run `eodhd_news_ingestion_sync-20261016121131-5ed4d540` a terminé OK à
14h59 Paris. Audit final READ ONLY : **1 790 checkpoints réussis**, compteurs
concordants et zéro défaut d'intégrité détecté dans les mappings du passage.
Corpus complet figé en partitions : 6 720 articles. Revue de 20 cas + 10 témoins,
zéro événement nouveau pleinement qualifié et zéro fenêtre intraday complète
sur l'échantillon ; pas encore de conclusion directionnelle ou économique.
[Bilan final, précautions PIT et artefacts](news_financement_validation_revue_20261016.md).
Le suivi automatique initial reste clôturé ; aucun nouvel entraînement lancé.

## Correctifs applicatifs du matin — pas de nouveau succès de collecte

Les retries d'un seul titre ne bloquent plus artificiellement les suivants ;
pause persistante et compteurs « incomplets / non interrogés » distingués.
Voir [paramètres, tests et contrôle réseau](../operations/eodhd_news_ingestion_sync.md).
406 tests passent. Les deux sondes réelles G/GABC expirent encore après 30 s,
sans écriture SQL ; aucune collecte complète relancée. Les archives et constats
historiques ci-dessous restent inchangés. Le suivi automatique reste clôturé ;
aucun entraînement ni backtest ajouté.

## Bilan final — collecte incomplète, arrêt réseau

**Run terminé FAILED le 16 octobre à 01h01 Paris**, après 22 min 48 s environ.
Le runner SQL et le launcher sont finalisés ; ce n'est plus une progression
en cours. Les sections intermédiaires ci-dessous conservent les constats datés.

| Compteur final | Valeur |
| --- | ---: |
| Titres demandés | 1 790 |
| Titres terminés par ce passage | 668 |
| Titre déjà terminé, ignoré par ce passage | 1 |
| Titres en échec | 3 |
| Titres non parcourus par ce passage | 1 118 |
| Occurrences d'articles reçues | 3 496 |
| Nouvelles versions brutes archivées | 2 738 |
| Titres sans article conservé | 144 |
| Tentatives HTTP | 676 |

Cause consignée : **timeout de lecture HTTP sur G.US (15 s)**, après la politique
de retry du client, puis ouverture du coupe-circuit EODHD. GABC et GAIN sont
ensuite arrêtés avant appel par ce circuit, pas démontrés invalides ou dépourvus
de news. Trois échecs consécutifs déclenchent l'arrêt global configuré. Ce n'est
ni l'épuisement du plafond de 4 000 tentatives, ni du budget de 120 min, ni la
réapparition de l'erreur TLS précédemment corrigée.

Audit final READ ONLY :
`artifacts/research/us_news_financing_feasibility/full-run-validation-20261016-failed-v1/report.json`.
Les compteurs SQL et fichier concordent ; 3 318 versions de mapping du run
contrôlées, **zéro reçu de mapping non scellé, référence brute manquante ou
fournisseur incohérent**. Les données archivées ne sont pas supprimées et restent
en quarantaine. La validation technique ne certifie pas leur identité/nouveauté
économique ni leur utilité directionnelle.

671 checkpoints du cycle sont en succès au contrôle : les 668 titres de ce
passage et les trois titres du smoke antérieur. Le passage n'en a encore
rencontré qu'un comme SKIP. Ne pas assimiler cette mesure de cycle au nombre
de titres parcourus par ce run.

Verdict **`FAILED_OR_INCOMPLETE_VALIDATION`** : environ 37,4 % des titres ont été
terminés ou ignorés comme déjà terminés par ce passage. Ce préfixe alphabétique
n'est pas présenté comme un corpus représentatif de l'univers entier. La revue
finale globale et la couverture intraday événementielle restent différées ;
les lectures intermédiaires existantes ne sont pas promues en résultat financier.

Le launcher a consigné un email accepté par SMTP et l'envoi Telegram ERROR.
**Aucune relance**, nouvel appel fournisseur, écriture SQL, modification de
batch, scoring, entraînement, backtest ou ordre dans ce contrôle final.
Le suivi automatique est clôturé après remise du bilan ; la tâche quotidienne
20h30 et sa configuration restent inchangées.

Suite proposée sur nouveau GO : qualifier la résilience timeout/coupe-circuit
(ne pas contourner le circuit ni désactiver TLS), puis reprendre la collecte.
Dans le même cycle, les succès déjà acquis peuvent être ignorés ; au cycle
suivant, le collecteur relit sa fenêtre J−7/J normalement. Aucun rattrapage ne
peut fabriquer les anciennes heures de réception.

## État à la remise intermédiaire

**Collecte complète lancée, pas encore terminée ni validée.** Il ne s'agit pas
d'un résultat directionnel. Nouveau passage manuel via le launcher habituel,
sans changement des listes ou horaires du workflow US, sans FinBERT, LLM,
entraînement ou ordre.

Le premier passage planifié n'avait pas encore eu lieu : tâche installée à
00h35 environ, prochain créneau effectif 20h30 Paris. Sur continuation, passage
manuel démarré le **16 octobre à 00h38 Paris** (15 octobre 22h38 UTC), pour
valider l'univers sans attendre le soir.

- Batch : `eodhd_news_ingestion_sync`.
- Run : `eodhd_news_ingestion_sync-20261015223851-cf9bbe96`.
- Univers : 1 790 titres de `config/univers_batch/univers_filtred_tradable.txt`.
- Limites existantes conservées : 4 000 tentatives/run et jour UTC, 120 min
  avant nouvel appel réseau, pause minimale 0,25 s, 25 tentatives/titre.
- Session complète en cours, aucun second passage simultané démarré.

Au contrôle de **00h43 Paris**, progression figée : **125 titres terminés**,
1 665 restants, 600 occurrences d'articles reçues, 530 versions brutes nouvelles,
20 titres sans article conservé, **zéro échec**. Ces chiffres ne sont ni la
couverture finale, ni 530 événements économiques distincts.

## Vérification opérationnelle intermédiaire

Rapport :
`artifacts/research/us_news_financing_feasibility/full-run-validation-20261016-interim-v1/report.json`.

- SQL explicitement `READ ONLY`, schéma `alpha_trade` imposé, timeout 15 s.
- Run SQL encore `RUNNING`, donc verdict **`RUNNING_NOT_YET_VALIDATED`**.
- Compteurs du dernier fichier de progression cohérents ; les compteurs SQL
  de `pit_collection_runs` restent initiaux jusqu'à la finalisation du runner.
- 128 checkpoints réussis dans le cycle courant à cet instant : les 125 titres
  terminés et les trois du smoke. Ils ne sont pas assimilés à 128 terminés par
  ce run ; une lecture concurrente peut aussi avoir un checkpoint d'avance.
- 563 versions de mapping rattachées à la fenêtre UTC exacte du run et à son
  début, **zéro reçu non scellé, référence brute manquante ou autre fournisseur**
  dans ce contrôle. Le writer continue pendant cette lecture.

Ces contrôles ne changent aucun checkpoint. Le rattachement d'archive utilise
`window_end_utc` exact et l'heure de début : aucun champ nouveau n'a été injecté
dans les contextes du collecteur pendant son exécution.

## Revue intermédiaire des annonces

Deux instantanés distincts, non confondus :

1. Avant le passage complet, `20261016-post-remediation-v1` : 72 articles,
   174 observations et 147 couples dans l'univers. Trois présélections, un
   texte distinct : toujours le rappel SNPS 2025, pas une nouvelle preuve.
2. Début de passage, `20261016-full-run-early-v1` : 201 articles nouvellement
   observés dans l'intervalle, 413 observations avec états nécessaires,
   492 couples. Cinq présélections dans **deux textes distincts**. Ces dossiers
   ne constituent pas le corpus du run complet et leurs nombres ne s'additionnent
   pas en nombre d'événements indépendants.

Lecture réelle des deux textes présélectionnés : ils parlent de l'IPO de
**Iambic Therapeutics (IAM)**, mais sont associés à **ABBV, NVDA et TAK**, partenaires
ou investisseurs cités. Leurs cinq couples sont réservés : ils ne prouvent
**aucune émission dilutive de ces trois entreprises**. IAM n'est pas dans le
fichier tradable actuel ; il n'a pas été ajouté à l'univers de collecte.
Deux publications sur la même IPO ne valent pas deux événements indépendants.

La grille est renseignée avec citations exactes, émetteur décrit dans le texte
et `identity_verified=false` pour les cinq couples. Nouveauté/communiqués
antérieurs non certifiés, aucun signal LONG/SHORT. Même assistant, **pas de
revue indépendante humaine**. Les 487 autres couples de ce dossier restent
non revus : aucune prétention de rappel exhaustif du dépistage.

L'outil de dossier utilise la borne `since` à la fois pour l'observation et
pour réserver les publications plus anciennes. Dans le dossier précoce dont
`since` est l'heure de lancement, les publications de l'après-midi sont donc
réservées temporellement aussi. Cela ne signifie pas que leur IPO est ancienne
ou fausse : ce dossier sert au diagnostic de mapping. Pour la qualification
événementielle finale, conserver une fenêtre de publication antérieure définie,
et ne jamais transformer l'heure publique en heure de réception historique.

Lecture enregistrée : `technical_review_filled.json`,
`technical_review_result.json`, `technical_review_summary.json` du dossier
précoce. `us_news_financing_issuer_review_20261016.py` reproduit seulement ces
deux lectures exactes et refuse les textes/tickers inconnus ; **ce n'est pas
un extracteur générique de financement**.

## Contrôle final prêt, à exécuter après la fin

`scripts/research/us_news_daily_run_validation.py` vérifie sans écriture :
statut final, compteurs SQL/fichier, titres terminés/restants, checkpoints du
cycle sur l'univers courant et intégrité des mappings reçus. Un échec, un
warning-run ou un run encore actif ne peut pas devenir un succès validé.
L'identité historique du fichier univers au départ n'est pas certifiée par sa
seule taille ; le rapport conserve son empreinte courante et cette limite.

```powershell
python -u -m scripts.research.us_news_daily_run_validation --run-id eodhd_news_ingestion_sync-20261015223851-cf9bbe96 --output artifacts/research/us_news_financing_feasibility/full-run-validation-20261016-final-v1
```

Utiliser un dossier nouveau. Si lancé trop tôt, le rapport reste intermédiaire :
ne pas le réécrire, refaire une lecture dans un autre dossier après la fin.
Un succès de validation signifie **collecte seulement**, pas signal validé.

Progression en attendant :

```powershell
Get-Content F:\projets\artifacts\operations\eodhd_news_ingestion_sync\eodhd_news_ingestion_sync-20261015223851-cf9bbe96\progress.json
```

`report.json` apparaît à la fin du collecteur ; puis attendre la finalisation
SQL et `FIN ... status=OK/ERROR` dans `log/batch/eodhd_news_ingestion_sync.txt`.
Notifications finales par le launcher habituel.

## Suite bornée

Sur accord explicite de l'utilisateur le 16 octobre, suivi automatique attaché
à cette conversation activé : `valider-la-collecte-news-us-et-reprendre-la-revue`.
Il contrôle périodiquement le run, reste silencieux pendant l'avancement normal,
reprend validation et revue à sa fin, puis se désactive après remise du bilan
(également si la collecte finit en échec/incomplète). Aucun second collecteur,
nouveau téléchargement fournisseur, scoring, LLM, entraînement, ordre ou
backtest autorisé par ce suivi.

Un autre dossier intermédiaire, `20261016-live-review-v1`, fige 1 139 articles,
2 621 couples et 48 présélections/19 textes, sans troncature. Ce n'est toujours
pas le corpus final : aucun jugement supplémentaire n'a été produit sur ces
19 textes, leur liste de titres n'est pas une revue sémantique.

**64 tests de recherche ciblés passent**, dont le validateur de run, l'absence
de promotion d'un run incomplet, la revue d'émetteur et la qualification/fenêtres
existantes. Tests sans API, LLM ou base métier en écriture.

Après fin : valider le run, figer les nouvelles archives sans troncature, revoir
un corpus borné d'annonces réellement nouvelles et vérifier leur couverture
intraday. Une troncature impose de partitionner le corpus, pas d'interpréter
les premiers articles comme l'intégralité de l'univers.
**Aucune nouvelle comparaison financière autorisée par ce rapport seul.**
