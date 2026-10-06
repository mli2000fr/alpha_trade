# Audit des droits de collecte des batchs FR — 6 octobre 2026

## Conclusion et limites

**Il n'est pas possible de déclarer tous les batchs autorisés sans réserve.**
La collecte Yahoo automatisée n'a pas d'autorisation explicite démontrée.
L'accès INPI est prévu par le fournisseur, mais notre gestion des retraits et
de la conservation doit être complétée. EODHD dépend de l'abonnement et du
statut personnel/professionnel de l'utilisateur. MiFIR bénéficie de conditions
spécifiques : il ne faut pas lui appliquer les restrictions des anciens Excel.

Cet audit technique et documentaire n'est pas une consultation juridique ni
une garantie d'absence de contentieux. Il confronte le catalogue actuel aux
endpoints utilisés et aux conditions officielles publiques. Les contrats du
compte, autorisations écrites et éventuelles conditions particulières n'ont pas
été consultés. Aucune collecte métier supplémentaire n'a été lancée, aucun
batch n'a été désactivé et aucune archive n'a été supprimée pendant cet audit.

Mise à jour après audit : `fr_pit_quality_daily`, contrôle local sans collecte,
a été retiré du catalogue et du planificateur le 6 octobre 2026. Ses rapports
sont conservés ; le catalogue FR contient désormais 13 sections. Sa ligne
ci-dessous documente le périmètre audité avant retrait.

Périmètre initial : les **14 sections** de `batch_fr.yaml`, leur code de
collecte et leurs sauvegardes. Les POC et imports historiques hors de ces batchs,
les collectes US/CN, la redistribution et les futurs usages par des tiers
nécessitent leur propre audit. Un statut `ACTIVE_RESEARCH` ou une quarantaine
n'est **jamais** une autorisation juridique.

## Tableau complet

Suite à l'autorisation utilisateur après remise de l'audit, les deux sections
Yahoo et INPI sont maintenant désactivées et portent respectivement
`BLOCKED_YAHOO_AUTOMATED_ACCESS` et `BLOCKED_INPI_RETENTION`. Les motifs et
conditions de déblocage sont affichés dans la page Batch. La phrase de non-modification
en introduction décrit uniquement la phase d'audit initiale. Aucune archive supprimée.

| Batch | Accès réel | Appréciation documentaire | Condition ou action |
|---|---|---|---|
| `fr_calendar_snapshot` | Bibliothèque locale XPAR | Pas de téléchargement de données externes par ce batch | Respecter les licences logicielles ; ce calendrier n'est pas une preuve officielle |
| `fr_security_master_sync` | Index public ESMA et archives `firds.esma.europa.eu` | Reproduction des registres autorisée sous conditions ESMA | Attribution, transformations signalées, pas d'endorsement ESMA ; vérifier exceptions/droits tiers |
| `fr_daily_bars_sync` | API EODHD `/eod/<symbole>` avec clé | Autorisé sous contrat, pas autorisation inconditionnelle | Abonnement couvrant ces données, usage personnel non commercial ou contrat professionnel adapté ; pas partage/revente |
| `fr_corporate_actions_sync` | API EODHD `/div`, `/splits` | Même réserve contractuelle | Pas de scraping Euronext ajouté par ce batch malgré le nom du fournisseur dans YAML |
| `fr_pit_quality_daily` | Rapports opérationnels locaux | Aucune nouvelle collecte externe | Ne certifie pas les droits des sources qu'il supervise |
| `fr_amf_short_sync` | Catalogue data.gouv puis CSV AMF public | Licence Ouverte 2.0 et automatisation explicitement prévue | Attribution AMF, date/source, respect des données personnelles éventuelles |
| `fr_dila_disclosures_sync` | API officielle Info-financière Explore v2.0, export JSON | API publiquement offerte, jeu sous Licence Ouverte | Attribution DILA/URL/fichier/date, quota et corrections ; batch actuel métadonnées seulement, pas PDF |
| `fr_fundamentals_sync` | API INPI authentifiée `bilans-saisis` | Accès officiel pour comptes publics ; réserve sur conservation | Licence acceptée par le compte, sécurité/PII, retraits et effacement à traiter |
| `fr_consensus_snapshot` | Yahoo via `yfinance`, session `curl_cffi` | **Permission automatisée non démontrée : suspendre recommandé** | Permission préalable expresse ou fournisseur licencié ; « recherche » et bibliothèque libre ne suffisent pas |
| `fr_borrow_snapshot` | Aucun collecteur actif | Désactivé, source non qualifiée | Ne pas activer sans contrat/source autorisée |
| `fr_options_mifir_trade_sync` | Download public MiFIR Paris + registre public FIRDS | Conditions MiFIR spécifiques favorables à l'usage interne | Distinguer usage/redistribution, respecter ESMA ; pas de droit général sur toutes les données Euronext |
| `fr_options_snapshot` | Aucun collecteur complet actif | Désactivé, source manquante | Ne pas activer ; les droits du MiFIR partiel ne couvrent pas OI/NBBO absents |
| `fr_db_backup` | Base locale `alpha_trade_fr` | Pas de nouvel accès fournisseur | Les copies n'élargissent pas les droits de conservation ou diffusion des données |
| `fr_artifacts_backup` | Archives locales FR et modèles FR | Pas de nouvelle collecte fournisseur | Copies Yahoo/INPI soumises aux mêmes restrictions ; retraits doivent aussi être gérés dans les backups |

## 1. Consensus Yahoo : réserve prioritaire

Le code `service/fr/consensus_daily.py` appelle les méthodes `yfinance.Ticker`
et utilise une session déclarée `impersonate='chrome'`. Ce n'est pas un contrat
API Yahoo ni une preuve de permission. Le caractère libre de la bibliothèque
ne confère aucun droit sur les contenus du fournisseur.

Les [conditions Yahoo actuelles consultées (US)](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
interdisent l'accès/collecte automatisés sans permission expresse préalable.
La [version européenne française antérieure](https://legal.yahoo.com/ie/fr/yahoo/terms/otos/previousversion-2025-01-29/index.html)
constitue une référence régionale complémentaire ; la page européenne courante
n'a pas pu être relue directement par l'outil. Il faut donc aussi conserver la
version contractuelle applicable à l'utilisateur en France, pas substituer
automatiquement le droit/contrat US au contrat européen.

Décision prudente : **suspendre `fr_consensus_snapshot` tant qu'une permission
écrite n'est pas fournie**, et ne pas diffuser/exploiter ses archives avant revue.
La présentation précédente « gratuit, recherche uniquement » était insuffisante.
L'audit recommande cette suspension mais ne l'a pas exécutée.

## 2. Euronext MiFIR : ne pas confondre avec Excel

Les [conditions spécifiques Delayed Trade Data](https://www.euronext.com/sites/default/files/stld/terms_and_conditions_for_delayed_data.pdf)
prévoient l'usage gratuit des données concernées. Elles encadrent séparément
leur distribution : attribution/mentions pour celle-ci et accord nécessaire
pour une distribution rémunérée ou commercialement bénéfique. L'[offre officielle](https://www.euronext.com/en/data/pricing-specs-agreements/mifid-ii-compliant-data)
prévoit le service de téléchargement différé.

Le batch utilise la route publique Paris du précédent jour de négociation ;
pas Excel, cookies, authentification empruntée ni contournement de refus.
La [politique Euronext](https://www.euronext.com/en/data/real-time-data/pricing-specs-agreements/market-data-pricing-policies)
confirme la gratuité de l'usage interne du différé. Cela ne valide pas toutes
les autres sources Euronext, les contenus tiers ou une exposition commerciale
dans l'application. La quarantaine technique reste indépendante de cette licence.

FIRDS : [mentions ESMA](https://registers.esma.europa.eu/publication/legalNoticePage).
Indiquer ESMA, les transformations éventuelles, et ne pas suggérer son approbation.
Les exceptions explicites et droits de tiers restent applicables.

## 3. INPI : collecte officielle, conservation à sécuriser

L'[API comptes annuels](https://data.inpi.fr/content/editorial/Acces_API_Entreprises)
est prévue pour accéder aux comptes publics. Le code filtre confidentialité,
suppression et identité avant archivage des contenus. Aucun téléchargement de
PDF/annexe n'est effectué par cette collecte actuelle.

La [licence homologuée INPI](https://data.inpi.fr/build/files/Licence_donn%C3%A9es_RNCS-Homologu%C3%A9e_par_etalab.pdf)
impose notamment attribution/date, droits de tiers et protection des données
personnelles. L'accès accordé au compte n'exonère pas de ces obligations.

La [documentation API v5](https://www.inpi.fr/sites/default/files/2025-06/documentation%20technique%20API_comptes_annuels%20v5.pdf)
indique le traitement des documents supprimés, notamment pour les rediffuseurs.
Le code saute les références `deleted` mais **n'efface pas les objets auparavant
archivés** : pas de procédure complète de retrait, ni propagation aux backups.
La portée exacte de conservation privée est à confirmer ; ne pas prétendre que
toute archive immuable serait exemptée. Suspendre par prudence si cette réserve
est incompatible avec la tolérance au risque de l'utilisateur, puis qualifier
une politique de retraits/sauvegardes et les obligations du compte.

## 4. EODHD : licence liée au compte et à l'usage

Les [conditions EODHD](https://eodhd.com/financial-apis/terms-conditions)
autorisent stockage et analyse privée non commerciale pour un utilisateur
non professionnel. Elles excluent le partage d'accès et la redistribution ;
l'usage pour une entreprise, un groupe ou d'autres personnes relève d'un cadre
professionnel. L'abonnement payé ne prouve pas à lui seul que tous ces usages
sont couverts.

Vérifier le contrat/facture et la couverture des endpoints, le quota réel du
compte et l'absence d'accès à des tiers. Si Alpha Trade devient un service ou
travaille pour une entreprise : demander confirmation contractuelle à EODHD.
Ne pas uploader les archives ou ouvrir l'IHM à des tiers sans revoir les droits.

## 5. Sources publiques françaises et routes autorisées

AMF : le [jeu précis](https://www.data.gouv.fr/datasets/historique-des-positions-courtes-nettes-sur-actions-rendues-publiques-depuis-le-1er-novembre-2012)
porte Licence Ouverte 2.0 et indique le téléchargement automatisé. Le fichier
public de positions n'est pas un droit d'accès au borrow ou au short interest complet.

DILA : le [jeu INFO-FINANCIERE](https://www.data.gouv.fr/datasets/info-financiere)
est sous Licence Ouverte ; l'[API officielle](https://www.data.gouv.fr/dataservices/api-info-financiere)
est ouverte avec une limite publiée de 10 000 appels/IP/jour. La
[page de l'API DILA](https://www.info-financiere.gouv.fr/pages/api0/?flg=fr-fr)
précise attribution, URL, fichier et date. La page export prévoit l'acceptation
des conditions du portail et du jeu.

Les [CGU génériques Huwise/OpenDataSoft](https://legal.opendatasoft.com/fr/terms-of-use.pdf)
restreignent les moyens automatisés hors permission ; leur portée doit être
distinguée de l'API délibérément publiée par DILA. L'autorisation API n'est pas
un droit général de scraper le site ou les PDF de tous les émetteurs. Pour la
prudence maximale demandée, conserver une confirmation DILA de cette route
et des conditions applicables ; le contact officiel est donnees-dila@dila.gouv.fr.

## Actions à décider avant de déclarer le périmètre conforme

1. Suspendre Yahoo et rechercher une permission/licence explicite ; aucune
   suppression d'archives sans décision réfléchie sur conservation/preuves.
2. Vérifier le contrat EODHD personnel/professionnel et la licence acceptée INPI.
3. Régler les retraits INPI et leur impact sur archives, index, observations et backups.
4. Conserver les conditions et confirmations de sources datées, les attributions,
   les quotas et les changements de licence ; demander confirmation DILA si nécessaire.
5. Revoir confidentialité, accès aux sauvegardes et transmissions aux services
   externes. Les notifications de comptes/statut ne sont pas une licence de diffusion.

Avant commercialisation, accès à d'autres utilisateurs, redistribution ou usage
professionnel non couvert : obtenir une revue juridique adaptée. **Aucune promesse
« zéro risque judiciaire » ne serait sérieuse sur la base de ce seul audit.**
