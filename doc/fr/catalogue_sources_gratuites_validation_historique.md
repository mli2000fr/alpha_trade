# Catalogue des sources gratuites — validation historique du marché FR

## Actualisation guidance 11-F — 4 octobre 2026, dossier v4

[Sources, limites et procédure de seconde revue](sprint_11f_sources_gratuites_et_seconde_revue.md).
151 PDF extraits sans échec ; 23 paires proposées (13 UP/10 DOWN), non encore
validées indépendamment. Exports supplémentaires complets Ubisoft (534/534)
et SMCP (44/44), huit antécédents archivés. Page officielle SMCP récupérée,
mais pas preuve de vintage 2019. Wayback tenté : HTTP 429, aucune capture
historique qualifiée ; interruption réseau Virbac sans preuve d'absence.
Ne pas déduire de ces erreurs que le gratuit est épuisé ou le payant nécessaire.
Les sections 11-E ci-dessous décrivent la version v2 antérieure.

## Complément guidance11-E — 4 octobre2026

[Dossier de provenance, revue et support](sprint_11e_completion_gratuite_guidance.md).
API officielle info-financiere.gouv.fr `flux-amf-new-prod`, exports JSON complets
par ISIN et compteurs de contrôle ; PDF DILA sur fr.ftp.opendatasoft.com avec
fallback HTTPS de même chemin sur echanges.dila.gouv.fr.126 PDF supplémentaires
extraits sans échec ;143 avec11-D. Archives d'émetteurs antérieures retrouvées
pour Klépierre, Assystem et Ipsos : anciennes prévisions, pas résultats réalisés.

Réutilisation : conserver URL, SHA-256, transmissions et première observation,
vérifier les pages/notes et la période/périmètre ; ne jamais assimiler la date
de collecte actuelle à une disponibilité historique. Les exports complets évitent
de perdre les titres de publication financière non reconnus par un filtre lexical.
Second lecteur requis.15 annonces proposées, deux cas complexes réservés,
support Oracle trop faible. Pas de preuve PIT stricte, pas d'intégration production
automatique, pas de gain D1/D10 ; aucune source payante indispensable démontrée.

État de l'inventaire : **4 octobre 2026**. Périmètre : sources publiques
effectivement utilisées ou tentées pendant l'intégration FR, la qualification
des prix/identités et les Sprints économiques 12-A à 12-D. Ce n'est pas le
catalogue de toutes les collectes US/CN, ni une liste de fournisseurs seulement
recommandés sur Internet.

**Actualisation 12-D :** les alternatives
[ADP/Euronext](https://live.euronext.com/sites/default/files/company_press_releases/attachments/2025/02/19/cpr03_lesechos_16165_1316157_Aroports_de_Paris_SA__Rsultats_annuels_2024.pdf)
et [Artois/AMFBDIF](https://bdif.amf-france.org/back/api/v1/documents/2025/225C0150/5D20A8FF0BC0A996C0D22A290FFF0804005B6035371E63982D5C147E49DDBED4.pdf)
sont désormais reçues :137/209cas fiscaux positifs et72inconnus, au lieu des
134/75de la passe initiale documentée ci-dessous. Les essaisDILAéchoués sont
conservés comme historique. Bolloré reste non résolu. Référence courante
`free_blocker_review/review-20261004-v6`. Les sources réutilisées conservent
leur véritable date de collecte et sont vérifiées parSHA, sans nouvel antidatage.

### Décision : poursuivre sans abonnement ni extrait payant

Le 4 octobre 2026, l'utilisateur confirme qu'aucun abonnement ne sera pris
pour lever ces réserves. Les principales familles publiques identifiées ont
été consultées ou testées ; cela **ne constitue pas une recherche exhaustive
de toutes les sources gratuites**, ni une revue individuelle achevée des
70 autres cas fiscaux. Certaines pistes restent non archivées ou partielles.

La prochaine étape est une **qualification du périmètre exploitable avec les
preuves déjà disponibles** : dresser les exclusions et leurs motifs, mesurer
leur impact par fold et politique, puis vérifier s'il subsiste un périmètre
commun permettant une comparaison économique honnête. Les exclusions doivent
être annoncées ; elles ne doivent pas dépendre des rendements réalisés.
Un sous-ensemble restreint ne représentera pas automatiquement l'univers initial.

Les inconnus fiscaux ne deviennent pas exonérés. Les événements non documentés
ne deviennent pas absents. Aucun backtest économique qualifié n'est autorisé
par le seul renoncement à une source payante. Si aucun chemin ne satisfait le
contrat de preuve, le résultat reste bloqué ; un éventuel rejeu fondé sur des
hypothèses devra être explicitement séparé et autorisé comme tel.

Ce document prépare leur intégration officielle **pour le même usage de
validation et de corroboration**. Il ne transforme pas les prototypes de
recherche en services de production et ne crée ni batch ni table.

## 1. Comment lire ce catalogue

### Extension Sprint 11-B : source de positions courtes AMF

**Suite11-C exécutée :** [revue et test incrémental](sprint_11c_evenements_guidance_ablation.md).

**Suite11-D :** [nouveau corpus guidance et revue détaillée](sprint_11d_corpus_guidance_elargi.md).
API INFO-FINANCIERE/DILA, six exports 2018–2025 avec compteurs concordants :
105 candidats nouveaux, 17 PDF/16 nouveaux émetteurs revus. Quatre paires
prospectives comparables (3 UP/1 DOWN). Le repli `echanges.dila.gouv.fr/OPENDATA/AMF/`
conserve exactement le chemin/nom du document ; pas de TLS désactivé. Utile pour
preuves ancienne/nouvelle guidance, mais ne prouve pas la disponibilité Web
historique stricte ; aucun retrain AMF/DILA, aucune admission serving.
Les compteurs AMF/DILA testés n'apportent pas de signal passant les gates sur
deux folds. Les délais1/2 jours sont des hypothèses de recherche, pas des preuves
Web/vintage. La revue des PDF distingue désormais trois révisions prospectives
et un résultat provisoire ; aucune feature guidance validée pour le serving.

Le [registre AMF gratuit](https://www.data.gouv.fr/datasets/historique-des-positions-courtes-nettes-sur-actions-rendues-publiques-depuis-le-1er-novembre-2012)
est désormais collecté séparément du flux DILA INFO-FINANCIERE. Catalogue API
et CSV sont archivés avec SHA. Le lecteur conserve date de position et date
de publication distinctes ; aucune absence n'est assimilée à zéro et aucune
publication du jour n'entre dans les compteurs de couverture du même jour.
L'export courant n'est pas une collection de vintages historiques ; 15 lignes
contradictoires sont mises en quarantaine. La qualification de ce contrat reste
ouverte avant une feature ML. Voir le [rapport détaillé 11-B](sprint_11b_qualification_sources_evenementielles.md).

### Trois niveaux de preuve à ne pas confondre

- **Source réglementaire/de place** : ESMA, BOFiP, BCE/TARGET, Euronext,
  Wiener Börse, BALO. Autorité sur son domaine, pas sur tous les domaines.
- **Source primaire d'émetteur** : communication financière, document
  d'assemblée générale, historique des dividendes, page actionnaire. Autorité
  sur les informations qu'elle publie ; une proposition n'est pas un vote.
- **Source secondaire** : Yahoo, archives Bnains. Utile pour détecter un
  désaccord ou orienter une investigation, pas pour prouver automatiquement
  une négociabilité historique ou remplacer un avis officiel.

**Public/gratuit d'accès ne signifie pas licence d'exploitation illimitée.**
Les travaux actuels prouvent des accès ponctuels sans abonnement à ces sources.
Avant collecte planifiée, stockage commercial, redistribution ou trading,
vérifier les conditions de chaque source. Aucun SLA ni quota gratuit universel
n'est présumé ; aucun 403 n'autorise un contournement.

### Résultats actuellement établis

| Problème | Sources utiles | Résultat réel et limite |
| --- | --- | --- |
| Identité, classe, MIC et référence historique | ESMA FIRDS | Références datées/rejouées ; pas de preuve de transaction ou suspension quotidienne |
| Divergence EODHD/Yahoo sur les prix | Euronext historique et notices | Corroborations ciblées ; fenêtre publique limitée et conventions à vérifier |
| Incident de clôture du 19 octobre 2020 | Euronext communiqué + XLSX | 82/84 clôtures litigieuses corroborent EODHD ; aucune admission automatique des OHLCV |
| Absence d'ouverture Artois le 10 octobre 2024 | Tableau public Euronext | Clôture 9 550 EUR, volume nul, ouverture absente : refus causal, pas fill inventé |
| Taux et périmètre TTF 2024/2025 | BOFiP + ESMA + preuves d'identité | 137/209 couples titre/année positifs ; 72 inconnus, pas exonérés |
| Règlement standard EUR | BCE/TARGET + Euronext T+1 programme | Convention prévue T+2 ; pas observation d'un règlement courtier |
| Dates/montants de dividendes | Émetteurs, Wiener Börse, publications financières | Preuves de champs ; aucune couverture complète CA admise |
| Complétude de toutes les opérations sur titres | Aucun feed gratuit complet qualifié dans ces passes | Toujours bloquant ; ne pas déduire « aucun événement » d'une recherche infructueuse |

Il reste **0 chemin promu** pour une performance économique complètement
qualifiée. Ce catalogue ne constitue pas un GO de rentabilité ou de live.

## 2. ESMA FIRDS — identité et intervalles de référence

### Accès effectivement utilisé

- Index JSON/Solr :
  [registre des fichiers FIRDS](https://registers.esma.europa.eu/solr/esma_registers_firds_files/select).
- Hôte des archives : `firds.esma.europa.eu` ; les URL exactes sont celles
  retournées par l'index, pas des dates de fichier devinées.
- Archives initiales `FULINS_E_YYYYMMDD_…zip`, puis changements
  `DLTINS_YYYYMMDD_…zip` ; réconciliations avec les Full ultérieurs.

### Informations et problèmes traités

ISIN, nom de l'instrument, CFI/classe, MIC et versions datées de référence.
Ces informations relient le symbole fournisseur à une identité, distinguent
les marchés/segments et permettent d'examiner la continuité historique.
Elles sont aussi utilisées pour rapprocher les noms BOFiP de l'action
ordinaire correspondante, sans matching approximatif libre.

Le téléchargement est paginé, avec validation du nom de fichier, de l'hôte
HTTPS, du ZIP, SHA256 et MD5 lorsqu'il est publié. Le rejeu sépare changement
de référence, date de publication et période observée. Les lacunes de Delta
ne sont pas supprimées parce qu'un Full final concorde.

### Ce que cette source ne résout pas

Pas d'OHLCV, de prix d'ouverture, de suspension quotidienne vérifiée, de carnet
ou de corporate-action cash complet. Un ISIN présent ne garantit pas qu'un
ordre aurait été exécuté. Notre chaîne commence en 2018 ; les données 2016/2017
ne deviennent pas validées par extrapolation du premier Full.

### Code, archives et intégration future

- Modules : `service/fr/esma_firds_download.py`, `esma_firds_history.py`,
  `esma_firds_annual_chain.py`, `esma_firds_gap_audit.py`,
  `esma_firds_full_reconcile.py`, `esma_firds_bar_coverage.py`.
- Archives/rejeu : `artifacts/fr/esma_firds/replay_2018`.
- Identités consommées par les contrôles économiques :
  `artifacts/fr/sprint6c_reference/identities.jsonl.gz` et son `report.json`.
- Détails : [rejeu et contrôles Sprint 5](sprint_5_intervalles_esma_prix_radies_actions_2026-10-02.md).

Intégration recommandée : collecte incrémentale reprenable, archives brutes
immuables, vérification de complétude par publication, réconciliation périodique
avec Full, puis promotion de versions d'identité après validation. Ne pas
écraser l'état historique par la dernière fiche connue ; isoler `FR_EQ`.

## 3. Euronext public — prix et avis de place

### 3.1 Historique des instruments, y compris radiés récents

Accès découvert depuis les pages instrument :

```text
https://live.euronext.com/en/product/equities/{ISIN}-{MIC}
https://live.euronext.com/en/ajax/getHistoricalPricePopup/{product_data}
```

Le collecteur lit les réglages de la page, vérifie l'ISIN et utilise le
`product_data` découvert. La réponse du composant public est lue avec les
paramètres publiés par la page. Ce n'est pas une API contractuelle stable.
La requête actuelle utilise `adjusted=Y`, dates de début/fin et `nbSession`.
**Cette convention doit rester dans la provenance** : ce n'est pas une
attestation universelle de prix bruts non retraités.

Champs lus : date, open/high/low/close, volume ; les tirets/prix absents restent
absents. Le code interprète les séparateurs décimaux/milliers avant comparaison.
MICs explorés : XPAR, ALXP, XMLI ; le MIC retenu doit être celui de l'identité
historique pertinente, pas celui qui fournit opportunément une réponse.

Résolution obtenue : contre-vérification ciblée de barres EODHD, radiés récents,
et statut de l'ouverture Artois. Pour le fold 7, la collecte ciblée antérieure
a corroboré 98 couples sur les quatre OHLC, sans corriger EODHD ; les six cas
restants ont demandé un traitement séparé. Voir les rapports, ne pas confondre
ce nombre avec tous les titres/jours du marché.

Limites constatées : environ deux ans d'historique public lors des tests,
restriction exacte fournie par la page. Les quatre journées du 30 juillet 2024
ERA/GLE/MEDCL/VCT ne sont pas desservies par la fenêtre publique testée au
4 octobre 2026. Ne pas contourner cette restriction ou inventer des dates.

Modules : `service/fr/euronext_delisted_reference.py`,
`service/fr/euronext_price_reference_pilot.py`.
Archives des cinq cas récents :
`artifacts/fr/research/execution_evidence_12c/missing-prices-euronext-20261004`.
Détails : [audit de fiabilité](audit_fiabilite_eodhd_euronext.md),
[finalisation du sous-ensemble](sprint_5_finalisation_go_limite_2018_2026.md).

Intégration : **source de contrôle**, pas remplacement automatique de toute
la collecte EODHD. Cache par ISIN/MIC/période/convention, conservation HTML et
réponse brute, provenance/hashes, tolérance de comparaison figée par audit,
résultats champ par champ. Une clôture concordante ne valide ni volume ni open.

### 3.2 Correction officielle du 19 octobre 2020

- [Communiqué sur l'incident](https://www.euronext.com/en/news/more-info-about-19-october-2020-market-status).
- [XLSX officiel des clôtures corrigées](https://live.euronext.com/media/516/download).

La feuille utilisée, `Equities_closing_prices_1910202`, contient 906 lignes et
les colonnes ISINCode, MIC, CURRENCY, Symbol Index, Last Adjusted Closing Price.
Les autres feuilles ETF/indices ne sont pas assimilées à des actions.

Audit des 84 titres sélectionnés par le diagnostic gelé : EODHD concorde seul
sur 78, les deux fournisseurs sur 4, aucun sur 2. SAN/SW restent des cas de
convention de série à examiner. La notice explique l'incident et l'annulation
de transactions ; elle ne fournit pas les quatre OHLC ni tout le volume corrigé.
Le mot « Adjusted » dans cet en-tête n'est pas automatiquement l'`adj_close`
du fournisseur.

Code : `modelFactory/fr_official_close_audit.py`.
Archive/rapport :
`artifacts/fr/research/official_close_audit/euronext-20201019-audit-20261003-final`.
[Méthode et résultats](sprint_10c2_audit_prix_independants.md).
Intégration : registre de notices/corrections exceptionnelles, avec date,
champ, périmètre et convention. Ne pas en faire un feed quotidien complet.

### 3.3 Calendriers et règlement standard

[Programme Euronext T+1](https://www.euronext.com/en/regulation/t1-programme)
archivé pour documenter la convention T+2 historique examinée. Cette page ne
prouve pas la date réelle d'un règlement individuel et ne doit pas servir à
appliquer éternellement la même règle après une transition de marché.

## 4. Yahoo Finance — référence secondaire de prix

Endpoint réellement utilisé :

```text
https://query1.finance.yahoo.com/v8/finance/chart/{symbol}
```

Paramètres du pilote : `period1`, `period2` exclusif (fin demandée +1 jour),
`interval=1d`, `events=div,splits`. Réponse JSON : timestamps, OHLCV,
adjclose si présent, métadonnées et événements. Le normaliseur vérifie un
résultat unique, longueurs des tableaux et métadonnées ; conserver le fuseau
de la place et la convention de date.

Usage : contre-vérifier EODHD, repérer désaccords de prix/volume, rechercher
une alternative pour un jour manquant. Yahoo n'est **pas** une preuve officielle
d'ouverture ni un feed exhaustif d'opérations sur titres. Une concordance
Yahoo/EODHD n'établit pas une négociabilité PIT ; une divergence n'identifie
pas à elle seule lequel est erroné. L'audit officiel de 2020 en est un exemple.

Code : `service/fr/yahoo_price_reference_pilot.py`.
Caches : `artifacts/fr/yahoo_daily_reference/cache` ; enveloppes JSON avec
payload et fichiers indexés par hash du symbole/période. Les contrôles 12-C
relisent ces caches sans les promouvoir en données canoniques.

Intégration : contrôle secondaire explicite et facultatif, cache/reprise,
backoff si limitations, TLS vérifié, absence d'un endpoint contractuel stable
signalée. Pas de fallback silencieux remplaçant une preuve de place absente.

## 5. BOFiP — taux TTF et listes annuelles d'émetteurs

### Versions réellement archivées

| Pièce | URL datée | Usage |
| --- | --- | --- |
| Taux historique antérieur | [BOI-TCA-FIN-10-30, 3 mai 2017](https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20170503) | Référence du taux 0,3 % utilisé avant avril 2025 dans le périmètre testé |
| Taux à partir d'avril 2025 | [BOI-TCA-FIN-10-30, 28 mai 2025](https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20250528) | Référence du taux 0,4 % utilisé à partir du 1er avril 2025 |
| Liste 2024 | [annexe publiée le 20 décembre 2023](https://bofip.impots.gouv.fr/bofip/9789-PGP.html/identifiant=BOI-ANNX-000467-20231220) | Rapprochement des dénominations pour 2024 |
| Liste 2025 | [annexe publiée le 23 décembre 2024](https://bofip.impots.gouv.fr/bofip/9789-PGP.html/identifiant=BOI-ANNX-000467-20241223) | Rapprochement des dénominations pour 2025 |

Ces règles décrivent **le contrat historique 2024/2025 du code examiné**, pas
une qualification fiscale universelle ou une veille juridique à jour au-delà.
Le modèle distingue assujettissement de l'émetteur, date de règlement prévue,
quantité/prix d'acquisition et exceptions ; les ventes cash du protocole ne
sont pas traitées comme des achats taxables.

Le parseur cible le corps BOFiP, pas les menus ; contrôle le nombre de noms,
unicité et format. Les pages et leurs SHA sont archivés. Normalisation accents,
casse/ponctuation n'autorise pas à retirer librement les suffixes juridiques
ou à confondre une classe de certificat avec une action ordinaire.

Qualification : 112 positifs issus de BOFiP/ESMA, puis 22 ajouts par alias
explicites et source d'identité ; **134/209 positifs, 75 inconnus**.
L'absence dans une liste ou un préfixe ISIN étranger ne vaut pas exonération.

Modules : `service/fr/economic_qualification_12a.py`,
`service/fr/execution_evidence_12c.py`, `service/fr/free_blocker_review.py`.
Archives : `artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2`.
Sortie fiscale courante de recherche :
`artifacts/fr/research/free_blocker_review/review-20261004-v2/ttf_eligibility_research.yaml`.

Intégration : registre des règles datées et listes annuelles, identités
ISIN/classe, revue des alias et cas négatifs avec motif/preuve. Une version
2026 ne doit pas rétroagir sur 2024. La date d'effet juridique n'est pas la
date de collecte, ni nécessairement la date de publication de la page.

## 6. BCE / TARGET — jours de règlement EUR

[Document TARGET archivé](https://www.ecb.europa.eu/paym/target/consolidation/profuse/shared/pdf/2025.APR_p1_fundamentals.en.pdf).

Combiné à la convention Euronext, il sert à calculer un **règlement prévu**,
en sautant week-ends et fermetures TARGET. Les jours fériés français ou le
calendrier de négociation XPAR ne doivent pas remplacer le calendrier de
règlement EUR. `TARGET_CLOSED` est actuellement une liste explicite revue
pour 2024 et 2025 ; le code bloque hors périmètre, y compris un débordement.

Archive : `qualification-20261004-v4/target_calendar.pdf` sous
`artifacts/fr/research/execution_evidence_12c` ; calculs `settlements.json`.
Intégration : calendrier versionné par système de règlement/devise/date,
exceptions traçables, tests aux frontières. Ne jamais appeler cela une
confirmation de règlement courtier ; cette dernière exigerait des fills et
des relevés de règlement réels.

## 7. Publications primaires — rapprochements d'identité

Les sources ci-dessous ont été employées **pour relier une dénomination à un
ISIN**, pas pour déterminer par elles seules la TTF, le cours ou le rendement.
Le manifeste exige aussi ESMA annuel et BOFiP annuel. Les pages actuelles ou
documents anciens établissent une piste d'identité ; leur pertinence à l'année
visée reste contrôlée par les versions historiques et la revue explicite.

| Émetteur | Pièce primaire utilisée | Résultat du dossier 12-D |
| --- | --- | --- |
| BNP Paribas | [FAQ actionnaire](https://invest.bnpparibas/faq) | Archive reçue ; BNP PARIBAS ACT.A rapproché ; 2024/2025 positifs |
| JCDecaux | [Action JCDecaux](https://www.jcdecaux.com/fr/investisseurs/action-jcdecaux) | Archive reçue ; JCDECAUX SE ; ajout 2025 |
| Getlink | [Guide actionnaires 2021](https://www.getlinkgroup.com/content/uploads/2022/01/e-guide-actionnaires-FR-2021.pdf) | PDF reçu ; GETLINK SE ; 2024/2025 |
| GTT | [Document d'enregistrement universel 2020](https://www.gtt.fr/sites/default/files/GTT-2020-UNIVERSAL-REGISTRATION-DOCUMENT_0.pdf) | PDF reçu ; GAZTRANSPORT & TECHNIGAZ ; 2024/2025 |
| Maurel & Prom | [Cours/action](https://www.maureletprom.fr/fr/investisseurs/cours-de-l-action) | Archive reçue ; 2024/2025 |
| M6 | [FAQ actionnaire](https://www.groupem6.fr/fr/investisseurs/espace-actionnaire/faq/) | Archive reçue ; METROPOLE TV ; ajout 2025 |
| OVH | [Déclaration de rachats du 26 août 2024](https://corporate.ovhcloud.com/sites/default/files/2024-08/2024-08-26-ovh-groupe-declaration-des-transactions-sur-actions-propres.pdf) | PDF reçu ; OVH / OVH Groupe ; 2024/2025 |
| Publicis | [Stock information](https://www.publicisgroupe.com/en/investors/shareholders/stock-information) | Archive reçue ; PUBLICIS GROUPE SA ; 2024/2025 |
| Hermès | [FAQ financière](https://finance.hermes.com/fr/questions-frequentes/) | Archive reçue ; HERMES INTL ; 2024/2025 |
| Schneider | [Share price / information](https://www.se.com/ww/en/about-us/investor-relations/share-information/share-price/) | Archive reçue ; SCHNEIDER ELECTRIC SE ; 2024/2025 |
| Ubisoft | [Investisseurs](https://www.ubisoft.com/fr-fr/company/about-us/investors) | Archive reçue ; UBISOFT ENTERTAIN ; ajout 2025 |
| Opmobility | [Changement de nom/ticker, 22 mai 2024](https://www.opmobility.com/wp-content/uploads/2024/05/2024_05_22__Change_of_the_denomination_and_ticker_symbol_of_OPmobility_shares.pdf) | PDF reçu ; Plastic Omnium/Opmobility ; ajout 2024 |
| Compagnie de l'Odet | [Déclaration de rachats publiée par GlobeNewswire](https://www.globenewswire.com/fr/news-release/2025/09/08/3146308/0/fr/Compagnie-de-l-Odet-D%C3%A9claration-des-transactions-sur-actions-propres-r%C3%A9alis%C3%A9es-du-1-septembre-au-5-septembre-2025.html) | Archive reçue ; ODET(COMPAGNIE DE L-) ; 2024/2025 |

Archives : `artifacts/fr/research/free_blocker_review/review-20261004-v2`.
Chaque fichier est relié à l'URL, au SHA et à `observed_at` dans `report.json`.
Source de configuration : `config/research_fr/ttf_alias_review_20261004.yaml`.

### DILA/AMF : trois tentatives non qualifiées

| Émetteur | URL essayée | Statut local |
| --- | --- | --- |
| ADP | [DILA FCECO077550, 19 février 2025](https://echanges.dila.gouv.fr/OPENDATA/AMF/ECO/2025/02/FCECO077550_20250219.pdf) | Connexion interrompue ; cas 2024/2025 inconnus |
| Bolloré | [DILA FCMKW132125, 16 septembre 2024](https://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2024/09/FCMKW132125_20240916.pdf) | Connexion interrompue ; cas 2024/2025 inconnus |
| Artois | [DILA FCMKW133032, 14 janvier 2025](https://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2025/01/FCMKW133032_20250114.pdf) | Connexion interrompue ; cas 2024 inconnu |

DILA est une piste officielle d'archivage de publications, pas encore un
connecteur général FR validé. Ces essais ne prouvent ni couverture complète
des dépôts, ni extraction fiable de tous les contenus, ni accès permanent.
Une prochaine intégration devra gérer index/identifiants, révisions,
disponibilité et fichiers associés avant de normaliser les faits.

## 8. Publications de dividendes et d'assemblées générales

### Références initiales 12-C

| Source | Champs corroborés / usage | Ce qui reste non qualifié |
| --- | --- | --- |
| [Virbac — espace actionnaires](https://corporate.virbac.com/home/investors/shareholders-area.html) | Tableau archivé : 1,45 EUR, paiement 26 juin 2025 | Ex-date officielle absente du contrôle ; 24 juin reste une piste fournisseur |
| [Wiener Börse — avis du 24 juin 2025](https://www.wienerborse.at/en/news/vienna-stock-exchange-news/walt-disney-dividends-global-market-06242025) | Ligne Planisware ISIN FR001400PFU4 : 0,31 EUR, ex-date 24 juin, paiement 26 juin | Avis d'une autre place ; pas feed exhaustif XPAR, pas preuve de toutes les CA |
| [Ipsos — brochure AG 2025](https://www.ipsos.com/sites/default/files/Brochure%20AG%202025%20EN_vFINALE.pdf) | Piste de termes annoncés : ex-date 1er juillet, paiement 3 juillet, 1,85 EUR | Téléchargement 403 ; cette ex-date n'est pas promue comme archive qualifiée |
| [Argan — compte rendu AG du 21 mars 2025](https://www.argan.fr/wp-content/uploads/2025/03/20250321-AG-Argan-2025-Votes-et-plan-de-developpement.pdf) | Revue publique : 3,30 EUR, ex-date 26 mars, paiement 17 avril, option actions/cash | URL locale 404 ; pièce brute non reçue, modalités particulières à vérifier |

Les deux overlays 12-C sont séparés des archives fournisseur : Planisware
termes de l'avis et Virbac montant/paiement seulement. Ils ne rendent aucun
chemin entièrement admissible. Fichiers : `dividend_reviews.json`,
`dividend_field_overrides.json` dans `qualification-20261004-v4`.

### Passe complémentaire publique 12-D

Les URL et statuts ci-dessous proviennent du dossier
`artifacts/fr/research/execution_public_requests/public-pass-20261004-v4`.
Le code est `service/fr/public_evidence_requests.py`, constantes
`PUBLIC_SOURCES` et `REVIEWS`. Les lectures sémantiques restent manuelles.

| Pièce essayée | Résultat utile | Limite / réception locale |
| --- | --- | --- |
| [Lectra — dividende](https://www.lectra.com/fr/investisseurs/information-actionnaires/dividende) | 0,40 EUR approuvé, paiement annoncé 5 mai 2025 ; `LSS.PA` est Lectra | HTML reçu ; ex-date officielle toujours inconnue |
| [SES — résultat AG](https://www.ses.com/press-release/ses-announces-annual-general-meeting-voting-results) | Piste paiement 0,25 EUR par action A le 17 octobre 2024 | 403 ; matching action/FDR, ex-date et retenue étrangers non qualifiés |
| [SES — résultats T1 2025](https://www.ses.com/press-release/ses-q1-2025-results) | Piste paiement 0,25 EUR par action A le 17 avril 2025 | 403 ; mêmes réserves de classe et fiscalité |
| [ABC Arbitrage — AG 2025](https://www.abc-arbitrage.com/wp-content/uploads/2025/06/ABCA-CP-AG-2025-compte-rendu-assemblee-generale-VF.docx.pdf) | Solde 0,04 EUR, ex-date 8 juillet, paiement 10 juillet 2025 ; contradiction fournisseur paiement 1er juillet | PDF reçu ; terminologie net/brut et couverture globale restent distinctes |
| [ABC Arbitrage — calendrier](https://www.abc-arbitrage.com/fr/agenda-date/) | Corroboration de calendrier, non substitut du vote | HTML reçu ; page courante susceptible de changer |
| [Argan — AG sans www](https://argan.fr/wp-content/uploads/2025/03/20250321-AG-Argan-2025-Votes-et-plan-de-developpement.pdf) | Autre URL pour la même piste AG | 404 ; pas de preuve brute supplémentaire |
| [Argan — dividende en actions](https://www.argan.fr/dividende-en-actions-2025-evolution-du-capital/) | Modalités scrip et évolution de capital, cash par défaut à examiner | HTML reçu ; 0,80 EUR de remboursement d'apport à distinguer du dividende ordinaire |
| [STIF — rapport annuel proposé](https://investir.stif.fr/wp-content/uploads/2025/03/20250327_STIF_RA2024_VDef-1.pdf) | Proposition 0,59 EUR | 403 ; pas de vote final, pas paiement réel démontré |
| [STIF — BALO 2501055](https://investir.stif.fr/wp-content/uploads/2025/04/202504162501055.pdf) | Proposition de paiement 2 juin 2025 pour 0,59 EUR | 403 ; demeure proposition, ex-date manquante |
| [Opmobility — DEU 2024](https://www.opmobility.com/wp-content/uploads/2025/03/opmobility-deu-2024-fr.pdf) | Proposition de solde 0,36 EUR payé 2 mai 2025 ; ne pas confondre avec total annuel 0,60 EUR | PDF reçu ; approbation finale/ex-date à compléter |
| [Robertet — résolutions AG](https://www.robertet.com/wp-content/uploads/2025/12/ACTUS-0-16121-robertet-sa-agm-2025-texte-des-resolutions.pdf) | Résolution 3 : 10 EUR, paiement 1er juillet 2025 | PDF reçu ; relier au vote, vérifier classe et ex-date |
| [Robertet — résultat des votes](https://www.robertet.com/wp-content/uploads/2025/12/ACTUS-0-16359-robertet-resultat-du-vote_ag-4-juin-2025.pdf) | Pièce distincte permettant une future validation de la résolution | PDF reçu ; archivage seul n'est pas rapprochement sémantique validé |
| [Vetoquinol — publication](https://www.vetoquinol.com/fr/publication/6009/view) | Proposition 0,89 EUR, paiement au plus tard 6 juin | 403 ; une échéance maximale n'est pas une date de paiement exacte |
| [Jacquet Metals — T1 2025](https://www.jacquetmetals.com/fichiers/communiques/2025/JM_CP_T125_FR.pdf) | Calendrier annoncé : paiement 3 juillet 2025 | 403 ; montant approuvé et ex-date inconnus |
| [Ipsos — rapport semestriel via GlobeNewswire](https://ml-eu.globenewswire.com/Resource/Download/95074133-74a4-4290-b4da-9b2f33b86559) | Document au 30 juin 2025, section 6.4.6 : 1,85 EUR mis en paiement le 3 juillet 2025 | PDF reçu ; ex-date non fournie par cette pièce, terminologie net/brut à conserver |

Le titre de recherche du dernier PDF Ipsos mentionnait 2024 alors que la
couverture du PDF indique 2025 : vérifier le contenu, pas le titre indexé.
GlobeNewswire est ici le canal de diffusion d'un document d'émetteur, pas
une source officielle de cours ou de toutes les opérations sur titres.

### Ce qu'une intégration de ces publications doit préserver

Un événement possède plusieurs dimensions : proposition, résolution approuvée,
date de détachement, date d'enregistrement, date de paiement prévue/réalisée,
montant brut/net, devise, classe, cash/scrip, remboursement de capital et révision.
Une seule valeur `dividend` ne suffit pas. Ne pas calculer l'ex-date à partir
du paiement moins T+2. Ne pas utiliser un PDF collecté aujourd'hui comme une
feature disponible historiquement sans date de publication démontrée.

Les variantes de noms, tableaux/en-têtes et notes demandent une extraction
contrôlée, avec page/ligne/cellule et revue des ambiguïtés. Aucun parseur général
PDF/HTML de dividendes n'est actuellement validé par ces 12 revues partielles.

## 9. Sources secondaires explorées et pistes non admises

### Bnains

Des archives Bnains ont été explorées dans les audits antérieurs comme piste
secondaire de prix. Elles ne sont pas une preuve officielle de négociabilité
PIT ni le fondement des admissions fiscales/économiques 12-D. L'audit 10-C2
le rappelle explicitement. Sans archive exacte/provenance/convention reliée à
un cas, ne pas intégrer un scraper Bnains comme solution réputée qualifiée.
Site de la piste : `bnains.org` ; aucune URL générale ne remplace une pièce datée.

### LuxCSD et autres listes ISIN de dépositaires

Une liste publique LuxCSD de TTF datée de 2026 a été repérée lors de la recherche
complémentaire, mais aucun fichier historique 2024/2025 utilisable n'a été admis.
C'est une **piste à investiguer**, pas une source ayant résolu les 75 inconnus.
Ne pas rétroprojeter une liste courante sur des années passées. À intégrer
seulement après archivage de la bonne version, définition de son scope et
rapprochement avec les règles fiscales historiques.

### EODHD, volontairement hors catalogue gratuit

EODHD reste la source fournisseur des barres archivées comparées aux sources
publiques ; l'abonnement payé n'est pas renommé « gratuit ». Les vérifications
ne démontrent ni sa fiabilité universelle, ni qu'Euronext public peut le
remplacer totalement. Les données EODHD brutes restent conservées et un overlay
qualifié est distinct d'une réécriture destructrice.

## 10. Contrat d'intégration transversale proposé

### Architecture : collecte → preuve → qualification → consommation

```text
Source publique + règles d'accès
  → archive brute immuable / résultat d'échec
  → extraction versionnée avec identité et convention
  → qualification champ par champ + contradictions
  → overlay / référentiel validé
  → consommateur autorisé : audit, taxes, règlement ou rejeu
```

Les services doivent rester sous `/service`, les commandes dans les modules
CLI correspondants. Une éventuelle planification quotidienne va dans la
configuration **FR** des batchs, avec base `alpha_trade_fr`, notifications et
universe FR explicites. Aucun de ces ajouts n'est réalisé par ce document.

### Provenance minimale à stocker

| Champ proposé | Pourquoi |
| --- | --- |
| source/provider + URL réellement consultée | Retrouver la pièce, distinguer hébergeur et auteur |
| raw_path + SHA256 + format/taille | Rejouer et détecter toute modification |
| observed_at UTC | Quand Alpha Trade a effectivement reçu la pièce |
| published_at et sa preuve | Établir une disponibilité publique historique, sans l'inventer |
| effective_from/to ou event_date | Date d'effet distincte de publication/collecte |
| market_code/ISIN/MIC/classe/devise | Éviter ticker réutilisé, mauvaise place ou mauvais instrument |
| parser_version + configuration/revue | Reproduire extraction et règles d'admission |
| champ, valeur, convention, précision | Éviter de confondre net/brut, ajusté/non ajusté, proposé/réalisé |
| qualification_status + motif + reviewer | Séparer réception, lecture et admission |
| supersedes / conflict_reference | Conserver les corrections et désaccords sans perte d'historique |
| coverage_from/to + couverture attestée ou inconnue | Ne pas confondre quelques événements et feed exhaustif |

Ce schéma est une recommandation, pas une description de nouvelles colonnes
déjà déployées. Les archives existantes possèdent une partie de ces champs.
Une migration devra être dédiée, accompagnée de SQL/Alembic et tests.

### Gestion opérationnelle

- Timeouts, cache, reprise et concurrence limitée ; les collectes documentaires
  12-C/12-D utilisent TLS vérifié, timeout 40 secondes, limite 15 Mo et au plus
  trois téléchargements simultanés dans les passes parallèles.
- Vérifier le format : PDF avec signature `%PDF`, XML/ZIP intègres, tables
  attendues, identités et nombre de lignes. Pour Ipsos, l'URL sans `.pdf` est
  explicitement traitée comme PDF par la passe 12-D.
- Garder 403/404/connexion interrompue dans le rapport ; pas de `verify=False`,
  changement de statut en succès ou contournement d'accès.
- Répétition : dédupliquer le contenu métier sur identité/version/champ,
  conserver les observations distinctes et hashes. Ne pas créer un second
  dividende parce que le même communiqué a été relu.
- Notifier demandés/reçus/persistés/échecs/alertes, mais ne pas mesurer la
  couverture économique uniquement au nombre de pages téléchargées.
- Les pages actionnaires sont souvent courantes : archiver prospectivement
  leurs versions pour une future utilisation PIT, sans promettre de reconstruire
  toute la situation passée à partir de la dernière page.

### Tests et critères d'admission

Tester mauvais ISIN/MIC, noms ambigus, classes composées, gaps temporels,
HTML remplacé par une page d'erreur, PDF invalide, unités/devises, dividende
proposé vs payé, ex-date inconnue, révision et double ingestion. Pour les prix,
tester absence réelle d'ouverture vs champ simplement manquant et conventions
d'ajustement. Pour la TTF, tester changements annuels et de taux. Pour le
règlement, tester week-ends, TARGET et frontières du calendrier qualifié.

La couverture est un gate distinct : même une extraction parfaite de toutes
les pièces trouvées ne prouve pas que toutes les pièces nécessaires sont trouvées.

## 11. Ordre d'industrialisation recommandé

1. **Référentiel ESMA** : fondation d'identité et validation de ses publications.
2. **BOFiP + registre d'alias** : règles fiscales versionnées, revue des inconnus.
3. **Calendrier TARGET et convention de règlement** : gérer séparément du XPAR.
4. **Contrôles Euronext et registre d'incidents** : corroboration de champs,
   preuve d'absence d'ouverture, pas fournisseur OHLCV universel.
5. **Documents d'émetteurs/DILA/BALO/Wiener Börse** : collecte brute, normalisation
   par famille et revue ; ne promouvoir que les faits réellement prouvés.
6. **Yahoo secondaire facultatif** : détection de désaccords, jamais blanchiment
   d'un manque de preuve officielle.

Priorité d'intégration ne veut pas dire rentabilité directionnelle : ces
sources traitent surtout **qualité des données, identité, fiscalité et réalisme
économique**, pas une amélioration D1/D10 démontrée.

## 12. Références de reprise

### Passe 13-C du 4 octobre 2026

Yahoo fournit les quatre OHLCV manquants du 30 juillet 2024 pour ERA/GLE/MEDCL/VCT,
concordants sur les séances voisines : overlay **exploratoire**, pas prix officiel.
Le compte rendu d’AG OPmobility confirme le solde payé le 2 mai 2025 ; Virbac
documente l’approbation et le paiement du 26 juin 2025. SES/Lectra/Ipsos et
l’historique secondaire STIF complètent les paiements sous réserves distinctes.
Certaines pages restent en 403 : une revue web structurée n’est pas une archive
HTTP brute ni une qualification PIT. Voir [13-C : sources, données admises et limites](sprint_13c_reparations_decision_economique.md).

### Passe 12-F du 4 octobre 2026 — sources émetteur X-FAB

Les rapports officiels 2023/2024/2025 issus de la page investisseurs X-FAB
ont été archivés et les pages identité/siège/dividendes relues. Ils qualifient
une absence annuelle de dividendes en 2024–2025, pas une absence de toutes
les opérations sur titres ni une exonération fiscale continue. La doctrine
BOFiP de périmètre a également été archivée. Deux documents Nexity repérés
ont répondu 403 : aucune qualification nouvelle tirée des extraits indexés.
Voir [12-F : preuves, pages, empreintes et réserves](sprint_12f_priorites_fiscales_operations_titres.md).
Ces sources servent à la vérité historique et au coût fiscal, pas à démontrer
un alpha directionnel. Les rapports rétrospectifs ne sont pas antidatés en PIT.

- [Bilan de levée gratuite et travail restant](sprint_12d_levee_blocages_gratuits.md).
- [Demande précise des preuves manquantes, sans achat engagé](demande_preuves_historiques_manquantes.md).
- [Qualification 12-C](sprint_12c_qualification_preuves_execution.md).
- [Moteur économique et invariants](sprint_12b_moteur_rejeu_economique.md).
- [Planning FR](sprint_planning_integration_marche_francais.md).

Pour reprendre : relire d'abord les rapports datés et les constantes des
collecteurs. Les URL et statuts de ce catalogue sont des observations des
passes citées, pas la garantie que le fournisseur répondra pareil demain.
Actualiser source par source la date de vérification, l'accès, les droits,
la pièce, les champs admis et les limites avant tout GO d'intégration.
# Ajout opérationnel du 05/10/2026 — GLEIF / comptes INPI

La [GLEIF](https://www.gleif.org/fr/lei-data/gleif-api/) est utilisée pour rechercher
ISIN → LEI → SIREN, avec vérification inverse de l'ISIN et références légales
SIRENE RA000189 / RCS RA000192. Elle qualifie une correspondance actuelle, pas
un historique PIT. Résultat sur les 330 identités S6C : 254 retenues et 76
exclusions explicites. Les correspondances permettent uniquement la collecte
publique INPI en quarantaine, sans SQL/ML/backtest/live.

Contrat, sources précises, limites et reprise :
[INPI — univers et collecte sécurisée](inpi_univers_collecte_securisee.md).
