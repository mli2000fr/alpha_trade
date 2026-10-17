# GPT / TOP20 Oracle parcours : historique 2024–2026

Demande du 15 octobre 2026 : analyser les vingt premiers titres de chaque séance
du 1er janvier 2024 au 30 septembre 2026, conserver les analyses en base pour
plusieurs backtests ultérieurs, **8 USD maximum de nouveaux appels API**.

## Modèles et sélection figés

| Année de décision | Modèle demandé | Fold annuel utilisé |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 |
| 2026, jusqu'au 30 septembre | `model-factory-20261014113232-bc35a7` | 2025-12-10 |

Les folds sont les mêmes que dans les expériences annuelles précédentes. Leurs
labels de train et validation sont disponibles **avant** l'année testée. Aucun
réentraînement et aucune utilisation des folds futurs du même modèle.

Lecture des scores dans `oracle_extreme_predictions`, jointure obligatoire avec
`oracle_path_prediction_lineage`. Empreintes du modèle et du profil, cible parcours,
horizon, fold et date de disponibilité doivent tous correspondre. Les rendements
futurs/labels terminaux doivent rester absents. Les scores de tout le mois sont
contrôlés avant de garder le TOP20 quotidien : probabilité décroissante, symbole
alphabétique en cas d'égalité exacte. Pas de remplacement en fonction du futur.
Les effectifs observés par séance sont archivés ; la population n'est pas présentée
comme un univers historique sans biais de survivance.

Le classement de cette campagne vient des prédictions SQL courantes et non de la
copie de scores de l'ancien test T1. Contrôle du TOP10 sur ce trimestre : 578 des
600 couples titre/date communs, rangs pas tous identiques, différence maximale de
score sur les couples communs 0,018291. Il ne faut donc pas présenter un futur
backtest de cette campagne comme une reproduction exacte du portefeuille précédent.
Les **213 anciens lots GPT** se retrouvent toutefois tous dans les nouveaux TOP20
avec une requête strictement identique : ils sont réutilisables sans nouvel appel.

Une séance manquante ne devient pas une séance sans news : le mois est signalé
`WAITING_PREDICTIONS`, sans appel payant pour ce mois. Une reprise peut ensuite le
compléter, avec le **même** budget persistant et sans recontacter les requêtes connues.

## Ce que lit GPT

Même protocole de news stockées que le pilote de septembre et le T1 2025 :

- un lot d'articles par titre/date, dans les 24 heures strictement avant la clôture
  officielle NYSE de J, calendrier et changements d'heure inclus ;
- sources déjà présentes `eodhd`/`alpaca`, reliées au titre ;
- publication fournisseur avec heure/fuseau explicites, cohérente avec la date normalisée ;
- identité courante de l'émetteur, titre, résumé, extraits de texte et identifiants ;
- bornes d'extrait inchangées : titre 500, résumé 700, corps 2 400 caractères ;
- ni score/rang Oracle, rendement futur, portefeuille, prix ou résultat de trade ;
- pas de Web actuel, d'outil externe ou de conversation implicite.

Modèle API : `gpt-6-luna`, niveau Standard explicitement demandé,
raisonnement `none`, réponse structurée, maximum 1 800 tokens de sortie.
Le choix économique reste celui des pilotes, pas un changement du filtre Web
prospectif de production.

Avis : `BULLISH`, `BEARISH` ou `ABSTAIN`, confiance subjective, justification,
identité vérifiée et jusqu'à trois citations exactes vérifiées. Une citation
inventée/invalide produit `UNKNOWN_INVALID_RESPONSE`, pas un avis exploitable.
Un titre sans texte est `UNKNOWN_NO_QUALIFIED_TEXT`, jamais artificiellement neutre.
Identité manquante et requête trop volumineuse ont également un statut explicite.
Un article n'est pas réanalysé isolément à partir de l'avis portant sur un lot.

## Sauvegarde autonome en base US

Les quatre tables existantes sont réutilisées, sans modifier les tables Yahoo :

| Table | Usage dans cette campagne |
| --- | --- |
| `llm_news_analysis_cache` | Requête exacte, réponse brute, consommation, avis validé, statut, modèle et disponibilité UTC. |
| `llm_news_analysis_articles` | Articles/versions réellement transmis et position dans le lot. |
| `llm_news_analysis_uses` | Appel nouveau, reprise gratuite ou récupération d'une réponse déjà sauvegardée. |
| `llm_news_analysis_research_runs` | Par mois : snapshot préparé complet (tous les TOP20, textes, réserves PIT, modèles), puis résultats complets, y compris les inconnus sans appel. |

Consommateur mensuel : `us-news-top20-history-20261015-v1:YYYY-MM`.
Références des snapshots préparés et terminés : même préfixe avec suffixes
`:prepared` et `:completed` ; leurs identifiants SHA-256 sont dans chaque
`months/YYYY-MM/completed.json`. La présence de `:prepared` seule ne signifie pas
que les appels du mois sont terminés.

Chaque réponse est persistée immédiatement, pas seulement à la fin du mois.
Une copie locale durable est écrite avant la sauvegarde SQL. Les requêtes exactes
déjà connues, y compris les réponses invalides, sont reprises gratuitement.
Texte, symbole, modèle, prompt ou contexte différents : pas de réutilisation
approximative d'un avis incompatible.

Les analyses ne sont **pas** publiées dans les tables de décision/ordres live.
Pour un futur test, lire les snapshots mensuels puis les réponses liées par
`cache_key`. Changer TP/SL/sizing ne nécessite pas de rappeler GPT.

## Budget et incidents

Plafond de cette campagne : **8 USD de coût API estimé, hors taxes et conversion**,
indépendamment des autres travaux lancés sur le compte. Un registre persistant
réserve avant chaque appel un majorant : octets UTF-8 de la requête + marge de
2 000, au tarif d'écriture de cache, et sortie maximale autorisée. Les requêtes
dépassant 240 000 octets ne sont pas envoyées ; le tarif contexte long n'est donc
pas utilisé.

Tarifs Standard vérifiés le 15 octobre : 0,10 USD/M tokens d'entrée,
0,125 USD/M tokens écrits en cache, 0,50 USD/M tokens de sortie. Le calcul réel
inclut la surcharge d'écriture ; il ignore la réduction de lecture de cache par
prudence. Voir [documentation officielle OpenAI](https://developers.openai.com/api/docs/models/gpt-6-luna).

Quatre appels au maximum simultanément ; leurs réservations sont cumulées sous
verrou. Une réservation qui ferait dépasser 8 USD bloque l'appel **avant** envoi.
Transport ambigu, consommation inconnue ou anomalie SQL : arrêt des nouveaux
appels, sauvegarde des réponses en vol. **Aucun retry payant automatique.**
Les réponses durables peuvent être réimportées sans HTTP à la reprise.

## Exécution et suivi

Script de recherche séparé : `scripts/research/us_news_gpt_top20_history.py`.
Ni batch quotidien, ni configuration de production modifiés.

```powershell
python -u -m scripts.research.us_news_gpt_top20_history --phase prepare --output artifacts/research/us_news_gpt_top20_history/20261015-v1
python -u -m scripts.research.us_news_gpt_top20_history --phase analyze --workers 4 --budget-usd 8 --output artifacts/research/us_news_gpt_top20_history/20261015-v1
Get-Content artifacts/research/us_news_gpt_top20_history/20261015-v1/progress.json
```

Ne pas supprimer/recréer le dossier de budget pour contourner un arrêt. Le verrou
du dossier refuse les lancements concurrents de la même campagne.
`budget.json` conserve les dépenses et réservations ; `api/` les échanges bruts ;
`months/` les paquets, effectifs et réponses ; `report.json` le bilan courant.
Pendant les appels, `progress.json` est le suivi vivant ; `report.json` peut encore
être le bilan `PREPARED` de l'étape précédente jusqu'à la fin de l'analyse.
`COMPLETED` exige les 33 mois, toutes les séances attendues et toutes les réponses
ou absences explicites. Ce document décrit le protocole, **pas une attestation
de réussite anticipée** : consulter le bilan du run.

## Limites pour les futurs backtests

Cette campagne est exploratoire : les news historiques ont été importées et
peuvent avoir été révisées, les métadonnées d'identité sont actuelles et le LLM
peut connaître des événements postérieurs. Interdire le futur dans le prompt ne
prouve pas son absence dans les poids du LLM. Les contrôles de disponibilité
historique locale sont conservés par article ; une publication passée ne transforme
pas une importation d'aujourd'hui en preuve PIT passée.

Les timestamps d'analyse SQL restent ceux d'aujourd'hui, jamais antidatés à J.
Un backtest ultérieur devra annoncer ces limites et distinguer opinions valides,
abstentions, texte absent et réponses invalides. **Aucun PnL ni gain directionnel
n'est calculé ou démontré par la présente collecte.**

Tests ciblés : 37 tests cache/campagne passent, sans API réelle, dont plafond,
cache-hit, réponse invalide non repayée, transport ambigu et récupération durable.

## État au lancement — 15 octobre, 00:49 Paris

Préparation terminée : **33 mois, 689 séances, 13 780 couples titre/date** ; aucune
séance attendue manquante. 5 827 lots possèdent des articles, 7 953 n'en possèdent
pas dans la fenêtre qualifiée. Aucune identité courante manquante ; deux requêtes
dépassent la limite de 240 000 octets et resteront explicitement inconnues.
213 anciens lots du T1 2025 sont exactement réutilisables ; le modèle annuel et
le rang sont conservés dans le snapshot même quand l'avis est repris.

Campagne payante démarrée en processus de recherche séparé, quatre workers,
budget cumulé persistant de 8 USD. Le traitement en cours ne signifie pas que
les 33 mois sont déjà analysés : consulter le bilan final. Le majorant de toutes
les requêtes atteint environ 16,46 USD avant cache ; il n'est **pas** engagé d'un
coup. Les réservations sont faites appel par appel, puis remplacées par le coût
réel contrôlé. Le plafond peut donc arrêter une campagne encore incomplète.

Premier contrôle après démarrage : janvier 2024 terminé (420 couples), 91 nouveaux
appels, 88 réponses valides et trois invalides conservées, environ 0,021716 USD.
Sauvegarde SQL des réponses et des snapshots mensuels confirmée en lecture seule.
Ce point de contrôle n'est pas le bilan des 33 mois : les suivants continuent.
