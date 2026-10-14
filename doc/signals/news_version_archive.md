# Archivage versionné des actualités US

Livré le 14 octobre 2026. L'archivage accompagne la collecte existante ; aucun
nouveau fournisseur, abonnement, batch ou appel API n'est ajouté.

## À quoi cela sert

`news_raw` et `news_ticker_map` restent les projections courantes utilisées par
le pipeline. Elles peuvent être mises à jour. Les nouvelles tables conservent
les versions effectivement observées à partir de ce déploiement, pour savoir
ce qui était connu **avant une décision future**.

Cela ne reconstitue pas les versions manquantes de 2025. Les anciennes news
ne sont ni supprimées, ni déclarées rétroactivement disponibles à leur date de
publication. L'[audit historique](../ml/news_materiality_feasibility_20261014.md)
reste bloqué sur ses données : livrer le stockage ne démontre aucun gain ML.

## Tables dans `alpha_trade`

| Table | Contenu et clé |
| --- | --- |
| `news_raw_versions` | Identifiant canonique et identifiant reçu, texte, payload complet, URL/source, date fournisseur originale et précision, SHA-256 du texte et du snapshot. Unique : article + empreinte du snapshot. |
| `news_ticker_map_versions` | Ensemble des associations acceptées dans le payload reçu, contexte de filtrage et référence exacte à la version du texte. Peut aussi porter une mise à jour partielle clairement marquée. Unique : article + empreinte du snapshot. |
| `news_archive_observations` | Historique des changements d'état : article, version, origine, lot technique, ordre d'écriture, heure d'observation UTC et disponibilité locale confirmée après commit. |

Les dates d'archive sont des `DATETIME(6)` UTC explicites. Le fuseau de la session
MySQL n'en change pas le sens. Les corps/payloads et les ensembles d'associations
versionnés ne sont jamais remplacés par le writer.

Un texte et un payload inchangés réutilisent la version existante. Un changement
de payload ou de métadonnées pertinentes produit légitimement un nouveau snapshot,
même si le corps est identique ; `text_hash` permet de le distinguer. Le texte
complet peut donc se retrouver dans plusieurs snapshots de provenance différente :
ce n'est pas un stockage de blobs dédupliqués indépendamment des métadonnées.

Un retour **A → B → A** conserve deux corps/snapshots distincts et un nouvel état
pour le retour à A. Trier uniquement les versions par première observation serait
incorrect : la lecture utilise l'ordre des observations validées.

## Raccordement à la collecte

Le repository `EventSentimentRepository.persist_news_page` est appelé par
`NewsIngestionService`, utilisé par `importe_news` et les entrées du pipeline.
Il prend les articles et associations déjà calculés, sans refaire de téléchargement
ni de scoring. Les filtres existants et leur politique restent inchangés.

La même transaction écrit les projections courantes, les nouvelles versions et
les observations en attente. Une panne d'archive avant le commit annule les
écritures de la page. Une absence de table n'entraîne pas un fallback silencieux
vers une collecte non archivée.

Après ce commit, `available_at` est renseigné une seule fois, à l'heure UTC
courante : les textes et projections ont alors déjà été durablement écrits.
Le timestamp est une borne conservatrice de disponibilité locale, **pas la
première disponibilité mondiale chez le fournisseur**.

Si la confirmation échoue, l'erreur remonte et le checkpoint ne passe pas à
succès. Les observations non confirmées restent à `available_at = NULL` et sont
inutilisables pour une lecture historique. Une reprise peut créer une observation
confirmée plus tard, sans rétrodater les anciennes. Un recul de l'horloge système
provoque aussi un refus de confirmation. L'horloge du poste doit être synchronisée.

Les corps identiques ne créent pas une nouvelle version à chaque nouvelle collecte.
Les répétitions exactes dans une page sont dédupliquées ; des versions contradictoires
du même identifiant dans une seule page sont refusées plutôt qu'associées arbitrairement.
Les collisions de hash de déduplication fournisseur conservent l'identifiant canonique
et archivent aussi l'identifiant réellement reçu.

Les appels directs `upsert_news_raw` passent également par l'archive. Les mises à
jour de pertinence via `upsert_news_ticker_map` sont archivées comme **partielles**.
Une relecture de ligne ancienne lors de ce traitement porte l'origine
`CURRENT_ROW_REVIEW`, sur un flux séparé : elle ne prétend pas être une nouvelle
réponse API ni une collecte fournisseur de l'époque.

Les anciennes implémentations de repository fournies par des adaptateurs/tests
peuvent encore utiliser la branche compatible non versionnée du service.
Le repository de production livré utilise toujours le writer atomique ci-dessus.

## Associations, identité et limites de couverture

`payload_scope_complete=true` signifie que toutes les associations acceptées
**pour le payload reçu et la politique donnée** sont enregistrées, y compris un
ensemble vide. Cela ne certifie pas que le fournisseur a identifié toutes les
sociétés concernées, ni que son ticker désigne le bon marché/émetteur.

Le contexte conserve symbole interrogé, provider, fenêtre demandée, mode et poids
de pertinence, seuils et version de l'heuristique. `identity_qualified=false`
reste explicite. Le cas Marvel Biosciences/MRVL n'est pas réparé automatiquement
par la création d'une archive.

Une mise à jour partielle ne signifie pas que les symboles absents ont été retirés.
Un nouvel ensemble reçu est conservé dans son contexte de requête ; il ne supprime
pas automatiquement les autres relations de la projection opérationnelle.

Cette livraison archive les news que le collecteur persiste déjà. Les articles
écartés avant persistance par le garde-fou du nombre maximal de tickers restent
écartés comme avant. L'archive ne démontre donc pas une couverture exhaustive
du flux fournisseur. Des jours sans résultat ne deviennent pas des jours sans
événement. Les limites de quota, la qualité des identités, les aperçus payants et
la complétude des corps restent à qualifier séparément.

Les scores de sentiment eux-mêmes ne sont **pas versionnés par cette livraison**.
Ils ne doivent pas être traités comme des scores historiques immuables parce que
le texte source dispose désormais d'une archive.

## Dates de publication et payloads

La chaîne fournisseur originale est conservée. Une date seule reçoit
`publication_precision=DATE_ONLY` et **aucune heure n'est inventée**. Une date sans
offset reçoit `TIMEZONE_UNKNOWN`. Une date explicite conserve aussi sa conversion
UTC ; absence et erreur reçoivent `UNKNOWN`/`INVALID`. La comparaison avec la
publication normalisée et les cas minuit restent des contrôles d'admissibilité
nécessaires au futur test, pas une certification financière automatique.

Les nouveaux payloads et composants de pertinence sont écrits comme objets JSON
natifs. Les anciens payloads doublement encodés sont décodés lors d'une lecture
pour archive, sans réécriture en masse des anciennes tables. Le payload conserve
la réponse fournie à l'application, pas des en-têtes d'authentification ou des clés API.

## Lecture historique

`event_sentiment.news_archive.load_article_as_of(connection, article_id, cutoff)`
demande un cutoff avec fuseau et choisit la dernière observation fournisseur
confirmée strictement **avant** la décision. Elle ignore les confirmations en
attente et les relectures de lignes anciennes. Son retour contient aussi les dates,
l'origine et les empreintes. Elle ne filtre pas automatiquement un corps incomplet,
une publication ambiguë ou une mauvaise identité : ce sont des gates supplémentaires.

Pour les mappings, joindre `news_archive_observations.mapping_version_id` à
`news_ticker_map_versions.id` et appliquer les mêmes gardes temporelles avant
de lire `mapping_rows`. Conserver la distinction payload complet/mise à jour
partielle et le contexte de requête. Ne pas joindre les mappings **actuels** à
une version historique du texte.

Ne pas utiliser `first_observed_at` d'une version comme unique cutoff : une
première observation non confirmée ou une relecture interne ne prouve pas une
collecte fournisseur admissible. Utiliser les observations confirmées.

## Installation et exploitation

Migration canonique : `0104_news_versions`, après `0103_oatr_max_returns`.
DDL gelé : `database/sql/news/news_archive_versions.sql`.
L'upgrade ne crée que les trois tables, sans backfill. Le downgrade refuse
une suppression implicite d'historique ; une purge demanderait une autorisation
et une procédure distinctes.

Commandes ciblées :

```powershell
python -m event_sentiment.news_archive --install
python -m event_sentiment.news_archive --status
```

L'installeur refuse une base autre que `alpha_trade`, exige les tables US
existantes et n'exécute pas d'`upgrade head` global. Il est idempotent et ne change
pas le marqueur Alembic.

**État local vérifié le 14 octobre 2026** : trois tables installées, vides, aucun
reçu en attente. Le marqueur local restait
`0088_us_fact_instrument_constraints` alors que des schémas plus récents étaient
déjà déployés séparément. Seul le DDL additif de cette livraison a été appliqué ;
aucune prétention d'avoir exécuté les migrations intermédiaires. Le graphe du
dépôt a un seul head : `0104_news_versions`.

Les nouveaux processus de collecte utilisent automatiquement l'archive. Un
processus Python déjà lancé conserve le code qu'il avait chargé ; aucun job
existant n'est interrompu ou redémarré ici. Pas de commande de réentraînement,
de rattrapage historique ou de réinstallation de tâche Windows nécessaire.
Seule la liste informative des tables touchées par `us_pipeline` a été complétée
dans `batch.yaml`, pour le catalogue IHM : horaires, étapes, activation et quotas
n'ont pas été modifiés.

Les logs ajoutent `News archive | articles=… maps=… new_raw_versions=…
new_map_versions=… state_changes=…`. `--status` donne les volumes et reçus en
attente. Des reçus anciens en attente signalent une confirmation incomplète et
restent exclus ; ils ne sont ni antidatés ni purgés automatiquement.

## Sauvegarde et rétention

Aucune purge automatique ni cascade depuis `news_raw`. Les références entre
tables d'archive sont `ON DELETE RESTRICT`. Cela protège les preuves, mais le
volume augmentera avec les nouvelles versions ; surveiller l'espace disque.

Dans la configuration vérifiée, `db_core_backup` exclut seulement `news_raw` :
les trois nouvelles tables sont donc dans son dump complet, lorsqu'il s'exécute
avec succès. `db_news_raw_backup` ne sauvegarde que `news_raw`. Les horaires,
inclusions et rétentions des batchs ne sont pas modifiés par cette livraison.
Restaurer seulement la sauvegarde `news_raw` ne restaure pas les archives.

## Vérifications de livraison

Tests sur SQLite temporaire, jamais sur les tables métier : collectes identiques,
corps modifié et retour A/B/A, contexte et ensembles vides, mise à jour partielle,
alias canoniques, JSON natif/double encodage, rollback, confirmation manquante,
reprise, horloge reculant, cutoff strict et branche du collecteur sans appel API
supplémentaire. Vérification de l'ordre des écritures lorsque les confirmations
arrivent dans un autre ordre, garde de marché et DDL additif également testés.

Contrôle MySQL local : schéma, clés, précision UTC, compteurs, absence de backfill
et marqueur Alembic conservé. Aucun test synthétique n'a inséré de fausse news
dans les tables métier réelles. Aucune collecte fournisseur réelle, aucun modèle,
ordre courtier ou backtest financier n'est lancé pour valider cette infrastructure.

**Bilan : 91 tests ciblés réussis**, plus un smoke MySQL réel sur cinq copies
**temporaires de session**, toutes vérifiées comme telles avant écriture.
Collecte identique : zéro nouvelle version/observation. A/B/A : deux versions
de texte, deux snapshots de mapping et six observations, JSON natif `OBJECT`,
aucun reçu en attente. Les copies temporaires omettent les contraintes FK/check
non adaptées à ce test MySQL ; ces contraintes sont vérifiées séparément sur le
DDL installé et les tests isolés. Les tables permanentes restent vides après
fermeture de la session privée ; aucun identifiant de smoke dans `news_raw`.
Le premier essai de copie temporaire a été arrêté avant toute écriture de données
par une restriction MySQL sur `CREATE TEMPORARY … LIKE` de même nom ; le second
rejoue les définitions natives sans cette ambiguïté. Ce n'est pas une variante
de collecte, de dates ou de stratégie financière.

Le bilan et les empreintes des sources sont conservés dans
`artifacts/research/news_version_archive/20261014-v1/validation.json`.
