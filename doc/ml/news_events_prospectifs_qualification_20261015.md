# Qualification prospective des news : pilote financement primaire

> Remédiation du 16 octobre : [transport sécurisé et ingestion quotidienne séparée](../operations/eodhd_news_ingestion_sync.md)
> livrés après les constats ci-dessous. Le transport ordinaire a maintenant été
> corrigé ; smoke réel et reprise vérifiés, pas encore une qualification directionnelle.

> Suite du 16 octobre : [faisabilité collecte et intraday](news_financement_faisabilite_20261016.md).
> Corpus inchangé, collecte ordinaire non certifiée, quatre fenêtres techniques
> complètes mais aucune annonce nouvelle qualifiée. Aucun test financier lancé.

Livraison du 15 octobre 2026. **Outil livré, collecte pilote réelle et lecture
technique terminées ; zéro nouvelle annonce qualifiée dans cet échantillon.**
Ce n'est ni un modèle directionnel, ni un filtre live, ni un nouveau résultat
de backtest. Aucun fournisseur, abonnement ou batch supplémentaire.

## Pourquoi cette seule famille

On reprend la famille définie avant lecture des résultats dans
[l'étude de faisabilité](news_materiality_feasibility_20261014.md) : annonces
nouvelles de **financement primaire par émission d'actions**, avec risque de
dilution. L'ancien audit historique n'avait pas qualifié ses preuves temporelles.
Ce pilote exploite les nouvelles archives ; il ne répare pas le passé et ne
déclare pas qu'une annonce de financement prédit une baisse.

Une mention de « public offering » n'est pas une preuve. Il faut distinguer
levée effective par l'émetteur, revente par des actionnaires, dette, simple
enregistrement d'une capacité future d'émission et reprise d'une ancienne news.

Le sentiment générique et les avis GPT ont déjà fait l'objet d'expériences.
Il ne s'agit pas de changer leurs seuils après avoir observé des pertes.

## Périmètre et état réellement contrôlé

- Univers courant : `config/univers_batch/univers_filtred_tradable.txt`,
  **1 790 titres** à la lecture du 15 octobre ; empreinte enregistrée.
- L'ensemble de cet univers est couvert par le dépistage, sans sélectionner
  les articles selon le rang Oracle, un rendement futur ou une perte observée.
  Un éventuel test financier devra ensuite joindre les candidats Oracle connus
  avant la décision, selon un protocole distinct.
- Sources : archives locales des collectes existantes EODHD/Alpaca. Aucun accès
  fournisseur nouveau ni extension supposée des droits. Usage local de recherche.
- Lors de la première vérification, les trois tables étaient installées mais
  **vides** : `news_raw_versions`, `news_ticker_map_versions`,
  `news_archive_observations`. Zéro reçu en attente.
- Lecture initiale à partir du 14 octobre 2026 : **zéro article archivé**.
  Verdict : `BLOCKED_NO_PROSPECTIVE_ARCHIVE`, pas « aucune annonce de dilution ».
- Sorties initiales conservées :
  `artifacts/research/us_news_event_qualification/20261015-v1` et `20261015-v2`.
  V2 lie la validation finale interdisant
  d'antidater une analyse à partir de l'heure déclarée par son relecteur.
- Après le GO « continuer » : collecte bornée, **55 versions de textes,
  55 versions de mappings, 110 observations**, zéro reçu en attente.
- Dossier final de qualification et revue :
  `artifacts/research/us_news_event_qualification/20261015-v3`.
  **55 articles, 112 couples article/titre dans l'univers**, trois couples
  présélectionnés correspondant à **un seul texte distinct**.

Les compteurs initialement vides ne démontraient pas à eux seuls une panne des batchs. Le
raccordement de `NewsIngestionService` à `persist_news_page` est présent dans
le code ; ses tests passent. Aucun job en cours n'a été redémarré pour ce pilote.
La persistance effective est maintenant constatée sur le pilote. Recharger
d'anciens articles aujourd'hui ne permet pas de leur attribuer une disponibilité
passée : les heures de réception/commit sont celles du 15 octobre.

## Collecte réelle bornée et diagnostic TLS

12 titres choisis par ordre SHA-256 figé, sans regarder leurs prix ou résultats :
IRTC, WHD, SCCO, EBF, KEYS, WERN, PUK, RVT, DDS, GLNG, DLB et CSCO.
Fenêtre fournisseur de sept jours, une page de 25 articles maximum par titre,
**12 tentatives HTTP maximum, retries compris**, pas de pagination supplémentaire.
CSCO signale une page suivante : aucune prétention d'avoir collecté tout son flux.

La première tentative `collect-20261015-v1` échoue avant toute page : erreur de
vérification de certificat HTTPS dans cet environnement, puis circuit breaker.
Diagnostic borné : une tentative avec le transport par défaut reproduit
`SSLCertVerificationError`; une tentative avec le magasin système obtient HTTP200.

La reprise `collect-20261015-v2` utilise le contexte de confiance système Windows
dans **ce processus de recherche seulement**. Vérification du certificat et du
nom d'hôte maintenue (`CERT_REQUIRED`, `check_hostname=true`), pas de
`verify=False`, de certificat installé ou de changement global d'environnement.
Empreinte de l'adaptateur dans `tls-attestation.json`.

La reprise reçoit **57 lignes fournisseur**, dont deux exclues par le garde-fou
existant sur les articles portant trop de tickers ; **55 lignes persistées** et
396 associations soumises au writer. Les 55 articles distincts de l'archive
donnent 112 couples dans l'univers de qualification. Ces compteurs ont des
périmètres différents, ce ne sont pas des événements économiques indépendants.

Le pilote réutilise normalisation, filtres et writer atomique existants. Il écrit
les cinq tables news annoncées, **pas les checkpoints de production** : getter et
writer de checkpoint neutralisés dans son repository de processus. Égalité des
checkpoints contrôlée avant/après. Aucun batch, score FinBERT, modèle ou ordre modifié.

Au total sur cette continuation : six tentatives dans le pilote échoué, deux
diagnostics d'une tentative chacun, douze dans la reprise réussie. Aucun appel
GPT, aucune nouvelle souscription. Les erreurs sont consignées sans clé, URL
authentifiée ou message fournisseur pouvant contenir un token.

**Limite opérationnelle importante :** le transport TLS sécurisé est limité au
pilote. Le collecteur quotidien n'a pas été modifié ; son accès depuis ses propres
processus reste à vérifier/corriger avant de promettre une archive alimentée
chaque nuit. Le succès de cette commande ne prouve pas celui des tâches Windows.

## Lecture technique réelle : résultat

Lecture de **13 couples article/titre, soit neuf textes distincts** : les trois
présélections et dix témoins choisis sans prix. Même assistant, pas de seconde
revue humaine indépendante. Réponses, citations exactes, positions et empreintes
sont conservées dans `technical_review_filled.json`, `technical_review_result.json`
et `technical_review_summary.json` du dossier V3.

- Le seul texte présélectionné est un commentaire sur Synopsys publié le
  14 octobre 2026. Il rappelle explicitement un placement de **2025** : ce n'est
  pas une nouvelle annonce. Les nombres d'actions et de financement ont été
  extraits comme valeurs littérales sourcées, sans servir de features live.
- Ce financement concerne SNPS, **pas KEYS ni SIEGY**, qui sont cités comme
  concurrents. Un score de sentiment global ne doit pas devenir un signal de
  dilution sur tous les tickers associés.
- Un témoin associé à US KEYS parle explicitement de **Keystone Law Group
  (AIM:KEYS)**, pas de Keysight Technologies. Identité/marché réservé.
- Un autre témoin sur Southern Copper/SCCO porte aussi un mapping SO. Cet
  émetteur ne doit pas être assimilé au ticker SO.
- Deux textes témoins sont des aperçus très courts ; certains autres décrivent
  des valorisations, résultats et commentaires anciens, pas de nouvelles émissions.

**Zéro nouvelle annonce de financement primaire qualifiée** dans la lecture.
Quatre couples présentent un mauvais émetteur d'événement ou marché apparent.
Pas une estimation du taux d'erreur de tout le flux : échantillon petit et
sélectionné par dépistage/empreinte. Les mappings bruts restent archivés ; les
réserves sont locales à la qualification, aucune correction destructive SQL.
L'absence d'annonce qualifiée ne prouve pas l'absence d'événement dans l'univers.

## Fonctionnement technique

Entrée : intervalle de réception et cutoff **avec fuseau explicite**. Le cutoff
ne peut pas être dans le futur. C'est une borne de qualification documentaire,
pas une heure de décision boursière automatiquement choisie.

1. Lire les articles dont au moins une observation fournisseur confirmée est
   disponible dans l'intervalle. Lire aussi leurs états antérieurs nécessaires.
2. Retenir la dernière observation confirmée par flux, en ordre d'identifiants,
   strictement avant le cutoff. Les retours A → B → A restent corrects.
3. Joindre uniquement des mappings fournisseur complets référençant exactement
   cette version de texte. Pas de jointure avec les associations actuelles,
   de remplacement par une mise à jour partielle ou de relecture interne
   `CURRENT_ROW_REVIEW` présentée comme une collecte fournisseur.
4. Conserver titre, résumé, corps, URL, dates originales, identifiants,
   empreintes et réserves. Vérifier l'empreinte du texte et la cohérence des dates.
5. Dépister la famille de financement avec des mots-clés dans les trois champs.
   Ce dépistage est un **routage vers une lecture**, pas une classification validée.
6. Produire jusqu'à 20 couples article/titre présélectionnés et 10 témoins non
   présélectionnés, par ordre d'empreinte indépendant des prix. Ces témoins
   facilitent une recherche de faux négatifs sans prétendre mesurer le rappel
   sur tout le flux. Plusieurs couples peuvent concerner un même article.

Lecture MySQL explicitement `READ ONLY`, base `alpha_trade` imposée, timeout
serveur 15 secondes, cap de 2 000 articles par défaut, maximum 5 000. Un cap
supplémentaire borne les observations. **Toute troncature bloque la qualification**
des événements du dossier, elle ne devient pas une absence de news.

Les articles incomplets, hors fenêtre de publication, avec URL absente, date
seule/fuseau inconnu ou incohérence d'horloge restent réservés. Un vieux texte
nouvellement collecté n'est pas déclaré nouveau. L'absence d'article n'est
jamais un sentiment neutre ou une preuve d'absence d'événement.

## Dossier et revue

| Fichier | Contenu |
| --- | --- |
| `protocol.json` | Univers/empreintes, bornes UTC, version de l'outil, limites et interdictions |
| `archive_snapshot.json` | Versions et reçus réellement lus ; aucune écriture dans les tables métier |
| `evidence.json` | Couples article/titre, textes exacts et réserves, clé stable de preuve |
| `review_template.json` | Grille vierge de revue, aucune identité/annonce approuvée par défaut |
| `report.json` | Compteurs, statut et empreintes des quatre fichiers précédents |

Le relecteur remplit une **copie** du modèle de revue : identité de l'émetteur,
catégorie, caractère nouveau, comparaison des annonces antérieures et reprises,
citation exacte avec champ/positions dans le texte, nom du relecteur et date UTC.
Les montants, prix et nombres d'actions éventuels sont des valeurs **littérales**
rattachées à une citation, sans invention d'unité ou conversion de devise.

Les citations et références sont contrôlées automatiquement, pas la véracité
sémantique de chaque jugement humain. Une mauvaise annotation peut toujours
être fausse : `independent_review_certified=false` reste explicite. Une relecture
par le même assistant n'est pas une seconde revue humaine indépendante.

Le résultat `QUALIFIED_RESEARCH_EVENT` signifie seulement qu'une annotation
remplit ces exigences de preuve et ne porte aucune réserve technique. Il ne
signifie ni SHORT, ni veto LONG, ni signal rentable. Le champ `tradable_signal`
reste toujours faux et la direction reste inconnue.

**Pas d'antidatage de l'analyse** : son `available_at_utc` est au moins l'heure
de validation effective par l'outil, même si le relecteur déclare une date
antérieure. Le cutoff des textes et l'heure de disponibilité de l'analyse
sont deux choses différentes. On ne peut utiliser cette analyse dans une
décision historique antérieure à sa production.

## Sentiment et LLM

Ce pilote ne relit pas `news_ticker_sentiment` comme un historique immuable.
Il ne possède pas de preuve de liaison entre une ancienne version précise du
texte, la version du moteur de sentiment et le score connu au cutoff.
`sentiment=null` et `NO_VERSIONED_SCORE_BINDING_PROVEN` sont donc explicites.

Les analyses du pilote sont versionnées **dans des dossiers locaux non
écrasables**, pas dans une nouvelle table SQL. Les textes restent dans leurs
trois tables d'archive existantes. Les tables `llm_news_analysis_*` ne sont pas
alimentées par cet outil. Aucun appel GPT payant n'a été fait.

Ajouter ensuite du sentiment ou un extracteur LLM demanderait de figer l'entrée
exacte, son hash, la version du moteur/prompt, le résultat et l'heure de fin de
calcul. Une confiance de classification du texte ne deviendrait pas pour autant
une probabilité de TP avant SL. Ce complément n'est pas livré implicitement ici.

## Utilisation après une collecte réelle

Depuis `F:\projets`, prendre un dossier de sortie **nouveau** à chaque fois :

```powershell
python -u -m scripts.research.us_news_event_qualification --since 2026-10-14T00:00:00Z --output artifacts/research/us_news_event_qualification/NOUVEAU_DOSSIER
```

`--cutoff` permet une borne UTC explicite ; son défaut est l'heure de lancement.
`--universe` accepte un autre fichier. Pas besoin d'appeler le fournisseur :
l'outil consomme uniquement ce qui a été réellement archivé par la collecte.

Après lecture des textes, remplir une copie `review_filled.json`, puis :

```powershell
python -u -m scripts.research.us_news_event_qualification --review-pack artifacts/research/us_news_event_qualification/NOUVEAU_DOSSIER --reviews artifacts/research/us_news_event_qualification/NOUVEAU_DOSSIER/review_filled.json --output artifacts/research/us_news_event_qualification/NOUVEAU_DOSSIER/review_result.json
```

Le résultat de revue ne remplace aucun fichier initial. Les versions inconnues,
les clés dupliquées, les citations inventées et les sources modifiées sont refusées.
La lecture technique du dossier V3 est maintenant terminée ; la grille vierge
reste conservée séparément des annotations. Aucune revue humaine indépendante
n'est déclarée achevée.

## Vérifications et prochaine borne

73 tests passent : qualification, collecte bornée/TLS, revue, archive et entrée de collecte. Les bases de test sont
SQLite temporaires ; pas d'écriture MySQL. Couverture : limites, états antérieurs,
A/B/A, mapping révoqué/partiel, cutoff strict, dates imprécises, hash du texte,
identité, nouveauté, citations et chiffres, absence de données, fichiers immuables,
disponibilité effective d'une analyse et non-régression de la collecte.

Des archives réelles et une première lecture de témoins sont maintenant disponibles.
Il reste à vérifier le transport des collectes ordinaires, accumuler les annonces
réellement nouvelles et qualifier leurs identités. Quelques jours permettent une
qualification technique, pas une conclusion directionnelle. Aucun délai calendaire
ne remplace un nombre suffisant d'événements distincts.

**Pas encore fait** : rattachement aux candidats Oracle à chaque décision,
réaction de prix calculée sans futur, surprises de consensus PIT, score financier,
apprentissage et comparaison économique TP20/SL10. Un éventuel protocole ultérieur
devra figer ces éléments, les témoins et la période avant lecture des rendements.
