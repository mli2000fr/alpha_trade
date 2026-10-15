# News factuelles nouvelles : qualification historique avant test directionnel

Date : 14 octobre 2026. Recherche séparée, aucun modèle ni batch modifié.

Suite autorisée et livrée le même jour :
[archivage prospectif versionné dans la collecte existante](../signals/news_version_archive.md).
Cet ajout ne répare pas rétroactivement les versions manquantes de l'échantillon
ci-dessous ; le blocage historique et l'absence de résultat financier restent valides.

## Question et hypothèse figées

Le sentiment générique très positif/négatif n'a pas donné d'avantage stable dans
les expériences précédentes. Cette étude porte sur une information différente :
**une annonce nouvelle de financement primaire par émission d'actions**, avec
risque de dilution, pourrait-elle aider à écarter des achats Oracle défavorables ?

Le protocole choisit cette seule famille avant toute lecture des rendements.
Sont exclus : dette seule, simple enregistrement d'une capacité future d'émission,
revente secondaire par un actionnaire, rachat d'actions et opinion boursière.
Une occurrence de « public offering » dans le titre est seulement une présélection
pour lecture, jamais une preuve que l'émetteur lève effectivement du capital.

Si les données passent la qualification, la cible distincte serait TP +20 %
atteint avant SL −5 %, entrée au prochain open, horizon maximal de vingt séances.
Ce n'est ni la direction du rendement terminal H20 ni un nouveau réglage du stop.
**Cette commande s'arrête à la faisabilité : elle ne calcule pas cette cible.**

## Échantillon borné sans choix sur les performances

- Janvier et juillet 2025 ; janvier et juillet 2026.
- Les cinq premiers Oracles de chaque séance de ces mois, rang original conservé.
- Archive de candidats de la comparaison des protections des CatBoost annuels :
  `artifacts/research/us_oracle_path_protection_selector/20261014-v1/candidates.parquet`.
- Sources d'ingestion existantes EODHD et Alpaca seulement, aucune nouvelle API.
- Lecture des métadonnées avec trente jours calendaires d'antériorité.
- Quatre sous-échantillons de lecture : six articles présélectionnés et six autres
  par année, si disponibles, tri SHA-256 des identifiants, jamais selon les prix.
- Maximum 5 000 associations par symbole/période ; toute troncature est déclarée.
  Cet échantillon ne mesure pas la couverture exhaustive de tout l'univers.

La nouveauté envisagée compare aux dix articles précédents du même titre,
disponibles dans les trente jours précédents. Si dix antécédents qualifiés ne
sont pas disponibles, la nouveauté est **inconnue**, pas automatiquement élevée.
Le dépistage des annonces porte ici sur les dernières 24 heures avant la clôture.
Cela exclut certaines publications du week-end : ce n'est pas encore une fenêtre
d'événement de production. Aucun balayage d'autres fenêtres n'est réalisé.

## Ce que conserve réellement le code

`news_raw` conserve titre, résumé, corps, URL, publication normalisée et payload
fournisseur. Les archives mensuelles utilisées pour les études de sentiment
conservent les scores et identifiants, mais **pas les corps des articles**.

Dans `event_sentiment/db_io.py`, `_upsert` remplace les colonnes fournies lors
d'un doublon et force `updated_at` à l'heure courante. Cela concerne les corps,
payloads et associations `news_ticker_map`. Les collectes normales ne fournissent
pas `created_at` SQL : ce champ représente la première insertion locale.
Le schéma n'est pas une archive append-only de toutes les anciennes versions.

Attention aux deux sens de `created_at` : dans le payload normalisé EODHD, il
porte la **publication fournisseur** ; dans `news_raw.created_at`, il porte
l'**insertion en base**. Ils ne sont pas interchangeables.

`event_sentiment/ingestion.py` attribue UTC aux dates fournisseur naïves. L'audit
ne transforme pas cette convention en preuve : date seule, fuseau absent,
décalage de normalisation et minuit ambigu restent réservés. Aucun horaire n'est
inventé pour rendre un article utilisable.

## Garde temporelle conservatrice

La clôture officielle de la séance NYSE, avec DST et clôtures anticipées, est
le cutoff de décision. On exige strictement avant cette borne : publication,
première insertion du texte, dernière modification du texte, première insertion
et dernière modification de l'association article/titre. Corps d'au moins 200
caractères et publication fournisseur explicite et cohérente sont aussi requis.

Un texte importé en 2026 mais daté de 2025 peut servir à une lecture rétrospective ;
il ne démontre pas quelle version était consultable lors d'une décision en 2025.
Inversement, une version non modifiée depuis avant la décision peut passer ce
diagnostic conservateur : l'absence d'un historique append-only ne prouve pas
que toutes les lignes sont nécessairement inutilisables.

Même une ligne qui passe la garde ne certifie pas la complétude du corpus :
absence d'article et absence d'événement ne sont pas équivalentes. Le risque
de sélection des versions survivantes et la précision des dates restent à qualifier.
On ne réutilise pas la date de calcul du sentiment comme date du texte.

## Exécution et livrables

Commande de recherche, nouveau dossier de sortie requis :

```powershell
python -u -m scripts.research.us_news_materiality_feasibility --output artifacts/research/us_news_materiality_feasibility/NOUVEAU_RUN
```

SQL limité aux lectures de `alpha_trade`, transaction en lecture seule, session
UTC. Chaque requête est bornée à quinze secondes. La jointure commence par
l'index fournisseur/publication, puis charge les corps seulement des identifiants
retenus : elle évite un parcours de tout l'historique des titres très médiatisés.
Les arrêts techniques v1/v2/v3 restent conservés. La lecture finale choisit entre
index symbole et index période selon le nombre d'associations historiques, sans
changer la famille d'événements, les périodes, la sélection ou les hypothèses.
La version v4 est préliminaire et explicitement remplacée : le premier extracteur
de dates ne décodait pas les payloads JSON stockés comme chaînes.
**Seule v5 est la conclusion qualifiée**, après correction dans le script d'audit.
Les corps et dates d'origine étaient présents ; aucune correction SQL n'a été faite.

Livrables locaux : protocole horodaté, métadonnées/empreintes des corps,
disponibilité par candidat et séance, extrait borné de lecture, couverture des
requêtes et rapport. Les extraits sont des pièces de recherche locales, pas une
redistribution publique des articles. Pas de souscription ou d'extension de droits
supposée par cette étude. Les conditions d'usage existantes restent applicables.

## Résultats

**Terminé : `BLOCKED_HISTORICAL_TEXT_PIT`.** Qualification technique achevée,
mais test directionnel/financier non lancé, conformément au gate annoncé.

Artefacts finaux :
`artifacts/research/us_news_materiality_feasibility/20261014-v5`.

10 168 associations article/titre, 8 958 articles distincts, 420 décisions
titre/séance, soit 84 séances et cinq rangs chacune. Sources observées : EODHD
uniquement ; aucune ligne Alpaca dans cette lecture. Zéro troncature, zéro
requête manquante dans le résultat final. Les textes incluent les trente jours
de contexte : ce ne sont pas 8 958 annonces nouvelles faites aux TOP5 à J.

| Diagnostic | 2025, janvier + juillet | 2026, janvier + juillet |
| --- | ---: | ---: |
| Décisions titre/séance | 210 | 210 |
| Titres distincts | 24 | 30 |
| Au moins un article publié dans les trente jours | 168 | 210 |
| Au moins un ancien texte passant la garde temporelle | 0 | 92 |
| Article des dernières 24 h passant la garde | 0 | 0 |
| Présélection de financement à J des TOP5 effectifs | 0 | 0 |
| Contexte d'au moins dix textes antérieurs distincts passant la garde | 0 | 28 |

Les 92 décisions avec ancien texte temporellement admissible sont toutes en
juillet 2026. Elles ne prouvent pas un corpus complet ni une annonce récente.
Les articles publiés en 2025 dans l'échantillon ont été insérés en 2026,
au plus tôt le 13 mai. Pour 2026, les backfills et modifications tardives
empêchent ici de qualifier l'article du jour au cutoff choisi.

Après décodage, **10 004 associations ont une date fournisseur précise et
cohérente** avec la publication normalisée ; 164 restent réservées à minuit.
Le problème n'est donc pas une absence générale de dates de publication :
c'est surtout la preuve de la version de texte et de l'association réellement
disponibles avant la décision. Une collecte après la clôture pourrait être
utilisable pour une décision ultérieure, avec son propre cutoff figé ; cela
ne rend pas contemporains les backfills effectués plusieurs mois après.

### Lecture des contenus

14 articles de l'échantillon déterministe ont été contrôlés : lecture des deux
textes de financement présélectionnés et préfixes techniques de douze autres.
Il ne s'agit pas d'une annotation exhaustive de tous les corps ni d'une seconde
revue humaine indépendante. Les empreintes des extraits complets stockés ont
été réconciliées avec celles calculées en SQL ; aucune modification en cours
d'audit n'a été détectée sur l'échantillon.

- **Marvel Biosciences / MRVL** : financement en actions et warrants d'un
  émetteur canadien TSXV/OTCQB, associé au symbole MRVL de l'étude US.
  Cette association est exclue : le ticker seul ne qualifie pas l'identité.
- **DigitalOcean / DOCN** : émission d'actions annoncée pour racheter des
  obligations convertibles, avec compensations et intentions de rachat d'actions.
  L'émission est bien décrite, mais sa dilution nette n'est pas déductible du
  seul titre. Les 500 millions concernent le principal des obligations, pas
  un taux de dilution. Pas d'étiquette baissière automatique.
- Deux autres pièces ne donnent qu'un aperçu/une continuation payante,
  de 223 et 302 caractères. Le seuil technique de 200 caractères ne garantit
  pas un article complet. Aucun accès payant n'a été contourné.
- Plusieurs pièces sont des synthèses multi-émetteurs, des opinions ou des
  sollicitations de cabinets d'avocats. Une association fournisseur ne prouve
  pas un fait nouveau directement attribuable à chaque société mentionnée.

Les deux titres de financement sont présents dans le contexte des symboles
collectés, mais pas dans la fenêtre figée des TOP5 effectivement candidats à J.
Ce constat concerne le screen choisi ; il ne démontre pas que toutes les autres
familles d'événements ou toutes les formulations possibles sont absentes.

### Vérifications

10 tests ciblés réussis : publication date seule/fuseau absent, cohérence des
offsets, backfill tardif, mises à jour et association à la clôture, absence non
neutre, faux positifs du screen et répétitions ne remplissant pas le contexte.
La vérification hors ligne recalcule le panneau de disponibilité, contrôle
les empreintes, les 420 candidats et la clôture anticipée du 3 juillet 2025
à 17 h UTC. Résultat :
`ARTIFACTS_AVAILABILITY_PANEL_SAMPLE_HASHES_AND_CUTOFF_VERIFIED`.

Scripts : `scripts/research/us_news_materiality_feasibility.py` et
`scripts/research/us_news_materiality_review.py`. Tests :
`tests/test_us_news_materiality_feasibility.py`.

## Décision prévue

Sans corpus historiquement disponible et événements validés sur les deux années,
l'étude est **clôturée sur blocage de données**, pas sur un verdict financier négatif.
Un test ultérieur demanderait au minimum vingt événements validés et dix dates
d'événements par année, ainsi qu'une qualification des jours de contrôle et du
contexte de nouveauté. Ces minima sont des conditions de faisabilité, pas une
garantie de puissance statistique ou de rentabilité.

Une éventuelle suite consisterait d'abord à archiver prospectivement les versions
de texte, payloads et associations avec leur `observed_at`, précision de publication
et empreintes, sans écraser les premières observations. Cela nécessite un GO
distinct pour modifier la collecte. Aucun entraînement ni backtest économique
n'est autorisé par la seule réussite technique de cet audit.

Les collectes existantes **ne sont pas à jeter** : corps, payloads et dates
restent utiles pour le diagnostic rétrospectif, la qualification des événements
et la préparation d'une collecte future. La présente étude ne démontre ni
rentabilité ni inutilité financière des annonces factuelles nouvelles.
