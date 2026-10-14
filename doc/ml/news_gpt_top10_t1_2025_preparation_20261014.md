# GPT sur les news du TOP10 Oracle — préparation du T1 2025

> Historique de préparation conservé. Le GO payant distinct a ensuite été donné
> le 14 octobre, initialement plafonné à 0,50 USD puis porté par l'utilisateur
> à 1 USD pendant la collecte. Le processus déjà lancé conserve sa limite plus
> stricte de 0,50 USD, sans refaire les appels payés. Les fichiers de préparation
> scellés ne sont pas réécrits par l'analyse ni par le replay.

Demande : élargir le pilote de septembre aux **60 séances US du 1er janvier au
31 mars 2025**, dix titres par séance. GO de préparation obtenu le 14 octobre.

**Périmètre de ce GO : préparer et chiffrer, sans appel GPT payant.** Le script
livré n'a volontairement aucune commande permettant d'appeler un LLM.
Ni écriture SQL, entraînement, ordre courtier, modification de batch ou de
configuration de production. Les news existantes ne sont pas retéléchargées.

## Oracle et contrôle de reproduction

Modèle annuel 2025 : `model-factory-20261014113226-102eca`, Oracle parcours H20
CatBoost, fold `2024-12-05`. Dernières disponibilités de labels d'entraînement
et validation : 5 juin et 4 décembre 2024, donc avant la période étudiée. Le
fait que la campagne contienne d'autres folds n'autorise pas à les utiliser.
Aucun choix du modèle après lecture des résultats de janvier–mars 2025.

Reconstruction sur les features déjà archivées : 72 tranches réunies, rangs
cross-sectionnels recalculés sur toute la population observable de chaque date,
avant sélection. Jamais un classement calculé séparément par tranche ou filtré
sur la qualité d'un rendement futur. Empreintes du modèle et des sources gelées.

**Résultat :** 107 399 couples observables scorés, 600 candidats TOP10 et
35 titres distincts, 60 séances du 2 janvier au 31 mars. Les 300 TOP5 de référence
du même modèle sont retrouvés exactement, symboles, rangs et scores compris
(écart maximal de score : 0). Le contrôle d'admission fondé sur l'historique à J
retrouve aussi celui de l'archive pour ces TOP5 ; 600/600 candidats passent ce
contrôle technique, sans garantie d'approbation future par le moteur de risque.

Les prix historiques nécessaires aux variables à J sont lus **au plus tard au
31 mars 2025**. Aucun rendement, cible, résultat de protection ou PnL futur n'est
calculé. L'univers reste celui du modèle archivé (fichier statique de 1 790 titres),
pas une reconstruction certifiée des cotations de 2025 : biais de survivance réservé.

## Protocole de news inchangé

Même protocole que [le pilote de septembre](news_gpt_septembre_pilote_20261014.md) :

- clôture officielle NYSE comme décision, borne strictement exclusive ;
- articles publiés dans les 24 heures précédentes, sans élargissement opportuniste ;
- date fournisseur explicite, avec fuseau et cohérente avec la normalisation ;
- dates imprécises exclues, sans inventer d'heure ;
- absence de texte qualifié = UNKNOWN, pas absence d'événement ni sentiment neutre ;
- titre, résumé et extrait de corps limités comme au pilote, troncature déclarée ;
- métadonnées d'émetteur actuelles, explicitement non PIT ;
- textes, associations, empreintes, paquets et plan des requêtes archivés localement ;
- aucune recherche Web, aucun score Oracle/prix/rendement futur transmis au LLM.

Le futur test conserverait une seule règle primaire : veto LONG si GPT relève un
fait matériel BEARISH, identité concordante, citations exactes et confiance >=0,75.
UNKNOWN et ABSTAIN restent dans le bras veto comme dans Oracle seul. Pas de
remplacement automatique par le 11e titre, pas de SHORT. La confiance n'est pas
une probabilité calibrée. TP20/SL5, sans trailing, prochain open et expiration
après vingt séances, frais/risque/marge identiques entre bras : règles du pilote,
pas paramètres choisis pour améliorer ce trimestre.

Le TOP10 est un nombre de titres, **pas le TOP10 %**. La présence quotidienne
du même titre ne représente pas autant d'ordres : pas de renforcement d'une
position détenue et contraintes natives de capital/risque à conserver.

## Lecture de la base et reprise

Requêtes uniquement SELECT dans `alpha_trade`, session en lecture seule/UTC,
limite de quinze secondes par requête. Métadonnées par tranches hebdomadaires,
textes par lots de 100 identifiants. Une requête interrompue ou tronquée arrête
la préparation : ce n'est jamais un jour « sans news ».

Les tranches et leurs empreintes sont enregistrées progressivement. Une reprise
réutilise seulement les fichiers vérifiés ; un texte modifié entre sa lecture
des métadonnées et la capture du corps provoque un refus. Aucun des trois nouveaux
historiques prospectifs n'est rempli artificiellement par cette préparation.

Script : `scripts/research/us_news_gpt_q1_2025_prepare.py`.
Run de référence : `artifacts/research/us_news_gpt_q1_2025/20261014-v2`.
`v1` est conservé comme arrêt technique avant lecture des news : le contrôle
d'admission cherchait `oracle_rank` dans les features de prix au lieu de le joindre
depuis les candidats. Corrigé et couvert par un test ; mêmes dates/modèle/règles,
aucun appel GPT dans l'une ou l'autre version.

Commande de préparation/reprise :

```powershell
python -u -m scripts.research.us_news_gpt_q1_2025_prepare --output artifacts/research/us_news_gpt_q1_2025/20261014-v2
```

## Coût à chiffrer avant toute analyse payante

GPT prévu : `gpt-6-luna`, même format de requête que le pilote, au maximum
1 800 tokens de sortie par requête, aucun outil ni Web. Le plan compte les seuls
paquets avec news utilisables et référence d'identité présente ; il ne lance pas
systématiquement 600 appels. Une requête trop grosse est signalée avant paiement,
sans supprimer discrètement des articles pour tenir dans le budget.

Tarifs standard vérifiés le 14 octobre : 0,10 USD/M tokens d'entrée et 0,50 USD/M
de sortie, [fiche officielle](https://developers.openai.com/api/docs/models/gpt-6-luna).
Les requêtes sont bornées en octets UTF-8, avec marge d'encadrement et totalité
des sorties possibles : borne conservatrice, sans remise de cache. Une projection
empirique est aussi fournie en utilisant la consommation du pilote de septembre ;
ce n'est pas une garantie de facturation. Taxes/change, autres tâches du compte,
modification de prix et nouveau modèle sont hors de cette estimation.

Le solde du compte n'est ni interrogé ni supposé. **Le lancement payant demande
un GO sur le budget présenté**, avec journal avant appel, réponse persistée avant
lecture, absence de retry automatique et réutilisation des réponses déjà payées.
Les analyses et comparaisons financières ne sont pas autorisées par ce seul état
de préparation, et leur code n'est pas encore raccordé à ce nouveau run.

## Réserves avant toute interprétation

Les textes de 2025 peuvent avoir été importés ou modifiés en 2026. La date de
publication ne prouve pas la version réellement connue en 2025. Les empreintes
capturées aujourd'hui protègent ce run, mais ne rendent pas l'ancien historique PIT.
Le LLM actuel peut en outre connaître des événements postérieurs à la période.
Un futur résultat serait **rétrospectif exploratoire**, pas une validation live.

Soixante séances et 600 couples titre/date ne signifient pas 600 observations
indépendantes : seulement 35 titres, souvent présents plusieurs jours de suite.
Le mois, le titre et les événements devront être explicités dans le reporting.
Les dates sans news ne pourront pas servir de contrôle « aucun événement » sans
qualification de la couverture du fournisseur et des associations.

## Préparation terminée — aucun appel GPT effectué

État final : **`PREPARED_AWAITING_PAID_ANALYSIS_GO`**.

| Mesure | Résultat |
| --- | ---: |
| Séances / couples titre-date | 60 / 600 |
| Titres distincts | 35 |
| Cas avec textes publiés qualifiés pour le paquet | **213 / 600 (35,5 %)** |
| Cas sans texte qualifié | 387 — UNKNOWN, pas absence d'événement |
| Associations article/titre dans les fenêtres avant filtre de précision | 980 |
| Associations après filtre de précision | 885 |
| Articles distincts sélectionnés | **880** |
| Extraits tronqués, sur les 885 associations | 573 |
| Articles du jour passant la garde historique conservatrice | **0** |
| Appels GPT prévus / déjà effectués | **213 / 0** |
| Crédit GPT consommé par cette préparation | **0 USD** |
| Projection empirique de coût | environ **0,07 USD** |
| Borne conservatrice standard de tokens | **0,4992202 USD** |
| Plafond proposé pour le futur GO payant | **0,50 USD** |
| Paquets bloqués pour identité absente / taille excessive | 0 / 0 |

Projection issue du pilote, non garantie ; la borne conservatrice réserve la
totalité des 1 800 tokens de sortie possibles par appel, contrairement à la
projection moyenne. La préparation représente 2 649 202 octets de requêtes.
**Ni réponse GPT, ni décision de filtre, ni rendement financier calculé ici.**

### Couverture par mois

| Mois | Couples titre-date | Avec news utilisables | Associations de news utilisables |
| --- | ---: | ---: | ---: |
| Janvier 2025 | 200 | 58 | 153 |
| Février 2025 | 190 | 61 | 297 |
| Mars 2025 | 210 | 94 | 435 |

Ces différences ne démontrent ni un régime plus propice ni l'absence d'annonces
sur les autres dates. Le protocole fixe seulement une fenêtre de 24 heures et
la base existante peut être incomplète. Les 95 associations écartées pour
précision de publication restent dans les métadonnées de contrôle, pas dans les
paquets destinés au LLM.

Les textes sélectionnés ont été insérés entre le **13 et le 26 mai 2026**.
Ils ne prouvent donc pas la version consultable avant une décision en 2025.
La [fiche GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
annonce en outre une borne de connaissances au 18 mai 2026, postérieure à tout le
trimestre testé. Cela ne prouve pas qu'il a mémorisé chaque événement, mais rend
le risque de connaissance de la suite particulièrement important. Aucun résultat
de ce futur pilote ne pourra être présenté comme hors échantillon pour le LLM.

### Audit final

**41 tests isolés réussis**, puis validation hors ligne des 600 clés, des 300
TOP5 de référence, de toutes les bornes de publication et de toutes les empreintes
des requêtes, du coût recalculé et des fichiers sources. Aucune réponse payée
créée. Une première assertion d'audit cherchant le mot `target` dans le texte
a été remplacée par le contrôle des champs JSON autorisés : un article peut
légitimement contenir « price target », sans que la cible future lui soit fournie.
Aucun paquet ni texte n'a été modifié pour contourner ce contrôle.

Vérification distincte des **seules clés date/symbole** des futures barres : les
600 fenêtres possèdent leurs vingt séances de détention et la séance d'expiration.
Dernière expiration théorique : **30 avril 2025**. Aucun OHLC ni volume futur lu
par cette vérification, aucun résultat de trajectoire calculé. La présence des
clés ne certifie ni les prix, ni les volumes, ni les actions sur titres et ne
remplace pas les gardes du futur replay.

Références du run : `protocol.json`, `scores-ready.json`, `prepare.json`,
`request-plan.json`, `availability.json`, `query-coverage.json` et
`completion-audit.json`. Treize requêtes hebdomadaires bornées, toutes complètes
et sans troncature ; 1 833 associations de métadonnées lues avant sélection des
fenêtres précises des candidats. Les captures de corps sont conservées en lots.

Cette étape attendait un GO payant distinct, obtenu ensuite : les 213 requêtes
préparées sont traitées une seule fois. Le solde restant n'est pas supposé et
aucun nouvel appel ne remplace automatiquement une réponse mal qualifiée.

### Complément de budget et qualification après le GO

La borne initiale de 0,4992202 USD utilisait le tarif d'entrée ordinaire ; elle
**n'incluait pas la majoration des écritures de cache**. Ce n'est donc pas une
borne garantie tous cas compris. Le compteur de continuation inclut cette
majoration (0,125 contre 0,10 USD/M tokens), ignore prudemment la remise des
lectures de cache et vérifie avant chaque nouvel appel : dépense cumulée
conservatrice + coût maximal du prochain appel <= 0,50 USD. Les taxes, le change
et les autres tâches du compte restent exclus. Aucun budget accru n'est requis
pour terminer ce lot si cette garde continue de passer.

Le premier contrôle de citations a arrêté le traitement après 12 réponses sur
une citation PLTR absente du texte. La réponse brute reste inchangée et n'est
pas repayée. La continuation distingue `UNKNOWN_INVALID_RESPONSE` d'`ABSTAIN` :
une réponse invalide ne peut déclencher de veto. S'il en reste, la comparaison
financière porte explicitement sur **les seuls avis valides**, pas sur un filtre
entièrement qualifié. Les prompts, extraits, dates, seuils et règles de trading
restent inchangés. Les réponses sont scellées avant lecture des résultats futurs.
